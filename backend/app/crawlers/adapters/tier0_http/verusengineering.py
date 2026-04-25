"""
Verus Engineering (verus-engineering.com) crawler adapter.

Track-focused aero specialist — splitters, diffusers, rear spats, fender vents
— for the Miata MX5 (ND), FRS/BRZ/GT86, GR86/BRZ (ZN8/ZD8), GR Corolla, WRX,
MK5 Supra, S550 Mustang, C8 Corvette, Porsche 981/987/992, FK8/FL5 Civic Type
R, and related platforms. **House brand only** — every product is Verus
Engineering's own part.

Platform: **Odoo Website Sale** (``<meta name="generator" content="Odoo">``;
``/shop/<slug>-<id>`` URL shape; ``/web/image/product.product/<id>/image_*``
media). No JSON-LD ``Product`` on product pages — only a YouTube ``VideoObject``
block — but the page carries rich Schema.org microdata
(``itemscope itemtype="http://schema.org/Product"`` on ``#wrap``) plus an
authoritative ``data-product-tracking-info`` JSON blob on ``#product_detail``
with ``item_id`` / ``item_name`` (bracketed-SKU prefix like
``[A0723A-V1] Ventus 1 Package``) / ``item_category`` / ``price`` / currency.

**Tier 0 — plain HTTP.** Confirmed against the live site with the default
crawler UA: ``/robots.txt``, ``/sitemap.xml``, and product pages all serve
200 OK with real HTML. There is Cloudflare email obfuscation on the site,
but no managed JS challenge or TLS fingerprinting block — the Odoo instance
itself is the origin and happy with plain ``requests``.

Discovery: flat ``/sitemap.xml`` urlset (no sitemap index) containing ~600
real product URLs mixed with ``/shop/category/…``, ``/blog/…``, ``/website/…``,
and utility endpoints. We filter to ``/shop/<slug>`` (excluding
``/shop/category/…`` and the cart/checkout/login/payment paths listed in the
site's own robots.txt) and drop the pagination query strings robots.txt also
disallows (``?search=``, ``?order=``).

Override the discovered list with ``CRAWLER_VERUSENGINEERING_START_URLS``
(comma-separated).

**Brand normalization — house brand, always "Verus Engineering".** Verus
titles bake the target vehicle's make right into the name ("Rear Diffuser -
BRZ/FRS/GT86", "Ventus 1 Package -  Miata MX5 (ND)", "Carbon Rear Diffuser
- Corvette Stingray C8", "Rear Diffuser - S550 Ford Mustang"). The shared
``part_manufacturer_from_title`` heuristic would otherwise pick "Rear",
"Carbon", or — worst — the car make ("Ford", "Toyota", "Subaru", "Mazda",
"Porsche", "Honda", "Chevrolet") as the brand. There is no JSON-LD brand
and no ``<meta property="product:brand">`` to fall back to, so we force
``"Verus Engineering"`` unconditionally — modeled on ADRO's normalizer,
which does the same thing for the same reason.

**Part number.** The SKU prefixes both the URL slug
(``/shop/a0192a-…-1194``) and the ``item_name`` in the
``data-product-tracking-info`` JSON (``[A0192A] Rear Diffuser …``). Variant
products carry a suffix on both (``A0723A-V1``). Pulled from the tracking
JSON first, then from the URL slug as a backup (the trailing ``-<digits>``
is Odoo's internal record ID — not a part number — so we strip it). Verus
also renders ``PART NUMBER`` as a free-form content block in the description
section, but that's inside ``<font>`` / ``<h5>`` tags with no stable class,
so parsing it is a fallback only.

**Cover image / gallery.** Hero image comes from
``<img itemprop="image">`` (the Schema.org microdata), plus ``og:image``,
plus every ``/web/image/product.product/…`` and ``/web/image/product.image/…``
``<img>`` in the ``#o-carousel-product`` carousel. Odoo also emits thumbnail
variants (``image_128``) in the gallery picker strip — those are deduped out
by collapsing ``image_{64,128,256,512,1024,1920}`` down to a single canonical
key per product.image record.
"""

import json
import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import unquote, urljoin, urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_dom_price,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

VERUSENGINEERING_BASE = "https://www.verus-engineering.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    # Verified 200 OK with full product markup 2026-04-20.
    "https://www.verus-engineering.com/shop/a0030a-rear-diffuser-brz-frs-gt86-737",
    "https://www.verus-engineering.com/shop/a0192a-rear-diffuser-fk8-honda-civic-type-r-10th-gen-1194",
]

# Canonical brand for every part in the Verus catalog. See module docstring.
CANONICAL_BRAND = "Verus Engineering"

# Path prefixes under /shop/ that are NEVER real product pages. Matches the
# site's own robots.txt disallow list plus the cart/account paths Odoo always
# exposes. Compared against the first segment after ``/shop/``.
_NON_PRODUCT_SHOP_PREFIXES = frozenset(
    {
        "cart",
        "category",
        "checkout",
        "login",
        "payment",
        "account",
        "confirmation",
    }
)

# Trailing "-<digits>" on a /shop/ slug is Odoo's internal product.template id
# (e.g. ``-737``, ``-1194``, ``-5110``). Used to derive a SKU fallback from
# the URL when the tracking JSON doesn't parse.
_URL_ID_SUFFIX_RE = re.compile(r"-(\d+)$")

# Matches bracketed SKU prefix in ``item_name`` from Odoo's tracking JSON
# (``[A0723A-V1] Ventus 1 Package -  Miata MX5 (ND)``). Captured group is the
# raw SKU; the remainder of the string is the clean product name.
_TRACKING_NAME_SKU_RE = re.compile(r"^\s*\[\s*([^\]\s]+)\s*\]\s*(.+?)\s*$")

# Collapse all Odoo image size variants (image_64 / image_128 / image_256 /
# image_512 / image_1024 / image_1920) to a single canonical key so the
# hero + gallery + 128px thumbnail strip don't produce 3x duplicate entries.
# Trailing delimiter can be ``/`` (``image_1024/filename``), end-of-URL
# (``image_1024``), or ``?`` (``image_1024?unique=...``) when the Odoo route
# omits the filename segment (like the og:image URL does).
_ODOO_IMAGE_SIZE_RE = re.compile(r"/image_\d{2,4}(?=[/?]|$)", re.IGNORECASE)

# Product-image URL prefix on this Odoo instance. Anything outside this path
# (site logo, mega-menu banners, category thumbnails, the Cloudflare
# email-obfuscation decode icon) is dropped from the gallery.
_PRODUCT_IMAGE_PATH_PART = "/web/image/product."


def _is_product_url(url: str) -> bool:
    """
    True iff ``url`` looks like a Verus product page: verus-engineering.com
    host, ``/shop/<slug>`` path (at least one path segment after ``/shop/``),
    first segment not in the known non-product prefix list, and no search /
    sort / filter query string (robots.txt disallows those anyway).

    This is a cheap pre-parse filter; ``parse_product_page`` still has the
    final say via the Schema.org microdata guard.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host != "www.verus-engineering.com" and host != "verus-engineering.com":
        return False
    # robots.txt disallows ?search= and ?order=; a real product URL never carries them.
    query = (parsed.query or "").lower()
    if "search=" in query or "order=" in query:
        return False
    path = parsed.path.strip("/")
    if not path.startswith("shop/"):
        return False
    rest = path[len("shop/") :]
    if not rest:
        return False
    first = rest.split("/", 1)[0].lower()
    if first in _NON_PRODUCT_SHOP_PREFIXES:
        return False
    # Verus product slugs all end with "-<id>" (Odoo record id). If a /shop/
    # URL has no trailing id, it's almost certainly a CMS landing page — let
    # the microdata guard filter it rather than rejecting here.
    return True


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, falling back to DEFAULT_START_URLS."""
    raw = os.environ.get("CRAWLER_VERUSENGINEERING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (a flat urlset, no index) and return all URLs that
    pass ``_is_product_url``. Deduplicated by full URL; empty on failure.
    """
    seen: set[str] = set()
    product_urls: List[str] = []
    try:
        xml_text = fetch_page(VERUSENGINEERING_BASE + "/sitemap.xml", timeout=15)
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        u = loc.text.strip()
        if not _is_product_url(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        product_urls.append(u)
    return product_urls


def _is_product_page(soup: BeautifulSoup) -> bool:
    """
    Product-page guard. Odoo Website Sale flags product pages with
    ``<div itemscope itemtype="http://schema.org/Product" id="wrap">`` plus a
    ``<section id="product_detail">``. Either on its own is sufficient — both
    show up together on every real product, and neither appears on category /
    blog / CMS pages.

    ``og:type`` is NOT reliable: Verus emits ``og:type=website`` on product
    pages too (not ``product``), so we don't use it.
    """
    product_scope = soup.find(attrs={"itemtype": re.compile(r"schema\.org/Product$", re.IGNORECASE)})
    if isinstance(product_scope, Tag):
        return True
    return soup.find(id="product_detail") is not None


def _parse_tracking_info(soup: BeautifulSoup) -> Optional[dict]:
    """
    Read the Odoo ``data-product-tracking-info`` JSON blob off
    ``#product_detail``. Shape:

        {
          "item_id": 6564,
          "item_name": "[A0723A-V1] Ventus 1 Package -  Miata MX5 (ND)",
          "item_category": "Aerodynamics",
          "currency": "USD",
          "price": 1649.95
        }

    This is the single cleanest source of truth on the page — it carries the
    SKU (as a bracketed prefix on ``item_name``), the Odoo-side category, the
    price as a float, and the product name. Returns ``None`` if the node is
    missing or the JSON is malformed (bs4 already HTML-entity-decodes the
    attribute value for us, so no ``html.unescape`` needed).
    """
    node = soup.find(id="product_detail")
    if not isinstance(node, Tag):
        return None
    raw = node.get("data-product-tracking-info")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(data, dict):
        return data
    return None


def _split_sku_and_name(item_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Split ``[A0723A-V1] Ventus 1 Package`` into ``("A0723A-V1", "Ventus 1 Package")``.

    Verus always renders the SKU as a bracketed prefix on the tracking-JSON
    ``item_name`` (and in the Google Analytics payload, which uses the same
    string). Variant SKUs carry a suffix (``-V1``, ``-BLEM``, ...) that is
    part of the real part number — keep it intact.

    When the bracket pattern doesn't match (older products, rare edge cases),
    return ``(None, item_name.strip())`` — the caller will fall back to URL
    parsing for the SKU.
    """
    if not item_name or not item_name.strip():
        return (None, None)
    match = _TRACKING_NAME_SKU_RE.match(item_name)
    if match:
        sku = match.group(1).strip()
        name = re.sub(r"\s{2,}", " ", match.group(2)).strip()
        return (sku or None, name or None)
    return (None, item_name.strip())


def _sku_from_url(url: str) -> Optional[str]:
    """
    Pull a SKU candidate from the ``/shop/<slug>-<id>`` path.

    Verus slugs always lead with the SKU (``a0030a-rear-diffuser-…-737``,
    ``a0723a-v1-ventus-1-package-…-5110``). We drop the trailing ``-<id>``
    (Odoo record ID, not a part number) and take the leading token(s) that
    match the Verus SKU shape: ``A0NNNA`` or ``A0NNNA-V1``/``A0NNNA-BLEM``
    (letter + digits + letter, optionally with a variant suffix of
    letters/digits). Matches are uppercased to match how the product pages
    display the SKU.

    Returns ``None`` if the slug doesn't look like a Verus SKU (e.g. the
    2021-era slugs that start with just the product description:
    ``bottom-mount-ucw-rear-wing-kit-subaru-brz-…-5784``). The caller then
    leaves ``part_number`` unset rather than inventing one from a
    description-only slug.
    """
    try:
        path = urlparse(url).path
    except ValueError:
        return None
    slug = path.rstrip("/").rsplit("/", 1)[-1]
    slug = _URL_ID_SUFFIX_RE.sub("", slug)
    if not slug:
        return None
    # Verus SKU shape: leading token A\d+[A-Z]? optionally followed by a
    # single variant suffix. Anchor to start of slug.
    match = re.match(r"^(a\d{3,}[a-z]?)(?:-([a-z0-9]{1,6}))?", slug, re.IGNORECASE)
    if not match:
        return None
    sku = match.group(1).upper()
    variant = match.group(2)
    # Only append a variant when it's (a) a letter+digit code like V1/V2/R1
    # (always contains at least one digit) OR (b) the explicit BLEM/BLEMISH
    # marker Verus uses for cosmetic-blemish listings. Descriptive slug words
    # like "rear", "front", "kit", "brz" look like variants by length but
    # must NOT be pulled into the SKU — matching only against the digit/BLEM
    # shape keeps those out.
    if not variant:
        return sku
    variant_upper = variant.upper()
    if re.match(r"^[A-Z]+\d+$", variant_upper) or variant_upper in ("BLEM", "BLEMISH"):
        return f"{sku}-{variant_upper}"
    return sku


def _extract_name(soup: BeautifulSoup, tracking_name: Optional[str]) -> Optional[str]:
    """
    Prefer the tracking-JSON ``item_name`` (with ``[SKU]`` prefix stripped) —
    that's what Verus shows in analytics and matches the in-DOM H1. Fall back
    to ``<h1 itemprop="name">``, then ``og:title``, then bare ``<h1>``.
    """
    if tracking_name:
        return tracking_name
    h1 = soup.find("h1", attrs={"itemprop": "name"})
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            return content.strip()
    plain_h1 = soup.find("h1")
    if isinstance(plain_h1, Tag):
        text = plain_h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_price_cents(soup: BeautifulSoup, tracking_price: Optional[float]) -> Optional[int]:
    """
    Prefer the tracking-JSON ``price`` float (already the sell price, no
    currency symbol), then ``<span itemprop="price">`` (Schema.org microdata
    on the offers block), then ``<span class="oe_price"><span
    class="oe_currency_value">…</span></span>``. ``extract_dom_price`` is a
    last resort — the page text starts with related-product prices in the
    sidebar on some layouts, so we scope tightly to the offers block first.
    """
    if tracking_price is not None:
        try:
            cents = int(round(float(tracking_price) * 100))
            if cents > 0:
                return cents
        except (TypeError, ValueError):
            pass

    offer_price = soup.find("span", attrs={"itemprop": "price"})
    if isinstance(offer_price, Tag):
        raw = offer_price.get("content")
        if isinstance(raw, str) and raw.strip():
            cents = parse_price_cents(raw)
            if cents is not None:
                return cents
        text = offer_price.get_text(strip=True)
        if text:
            cents = parse_price_cents(text)
            if cents is not None:
                return cents

    oe_price = soup.find(class_="oe_price")
    if isinstance(oe_price, Tag):
        cents = parse_price_cents(oe_price.get_text(" ", strip=True))
        if cents is not None:
            return cents

    oe_cv = soup.find(class_="oe_currency_value")
    if isinstance(oe_cv, Tag):
        cents = parse_price_cents(oe_cv.get_text(strip=True))
        if cents is not None:
            return cents

    return extract_dom_price(soup)


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer ``<div itemprop="description" id="product_full_description">`` —
    the full Odoo content block with overview / features / science / install
    sections. Fall back to ``og:description`` and ``<meta name="description">``.
    """
    desc_node = soup.find(attrs={"itemprop": "description"})
    if isinstance(desc_node, Tag):
        text = desc_node.get_text(" ", strip=True)
        normalized = normalize_description_text(text, max_len=2000)
        if normalized and len(normalized) >= 40:
            return normalized

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        v = meta_content(og_desc)
        if v and v.strip():
            normalized = normalize_description_text(v, max_len=2000)
            if normalized:
                return normalized

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        v = meta_content(meta_desc)
        if v and v.strip():
            normalized = normalize_description_text(v, max_len=2000)
            if normalized:
                return normalized

    return None


def _description_block_sku(soup: BeautifulSoup) -> Optional[str]:
    """
    Last-resort SKU scrape from the content block Verus renders in
    ``#product_full_description`` as ``<h5><b>PART NUMBER</b></h5>`` followed
    by a ``<p>`` / ``<font>`` carrying the bare SKU (e.g. ``A0030A``). Only
    used when the tracking JSON and the URL both fail — they almost never do,
    but older Odoo record migrations sometimes drop one or the other.
    """
    desc_node = soup.find(id="product_full_description")
    if not isinstance(desc_node, Tag):
        return None
    text = desc_node.get_text("\n", strip=True)
    if not text:
        return None
    match = re.search(
        r"PART\s*NUMBER\s*\n+\s*([A-Za-z]\d{3,}[A-Za-z]?(?:-[A-Za-z0-9]{1,6})?)",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).upper()
    return None


def _canonical_image_key(url: str) -> str:
    """
    Key for dedupe: collapse Odoo's image size variants
    (``image_64``/``image_128``/``image_256``/``image_512``/``image_1024``/
    ``image_1920``) and strip the ``?unique=<hash>`` cache-buster so a hero
    photo that appears once in the main carousel, once in the 128px thumbnail
    strip, and once as og:image is treated as a single image.
    """
    no_size = _ODOO_IMAGE_SIZE_RE.sub("", url)
    no_query = no_size.split("?", 1)[0]
    try:
        return unquote(no_query)
    except Exception:
        return no_query


def _is_product_image(url: str) -> bool:
    """
    True for ``/web/image/product.product/<id>/…`` and
    ``/web/image/product.image/<id>/…`` URLs only. Rejects
    ``/web/image/website/1/logo``, megamenu banners, Cloudflare email-protect
    decode icons, and any category/nav assets.
    """
    if not url:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    return _PRODUCT_IMAGE_PATH_PART in low


def _extract_images(soup: BeautifulSoup, page_url: str) -> List[str]:
    """
    Collect product image URLs in display order.

    Sources (priority): ``<span itemprop="image">`` (the Schema.org-declared
    canonical image, always at size ``image_1920``), then ``og:image``, then
    every ``<img>`` inside ``#o-carousel-product`` (the main product
    carousel), then ``data-zoom-image`` attributes on those imgs (zoom gives
    us the highest-res URL when the visible ``src`` is the ``image_1024``
    variant). All non-``/web/image/product.*`` assets are dropped; the
    gallery's 128px thumbnail strip collapses into its 1024px/1920px peers
    by canonical key. Capped at 12 images.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = raw.strip()
        if not u:
            return
        if u.startswith("//"):
            u = "https:" + u
        elif not u.startswith("http"):
            u = urljoin(page_url, u)
        if not _is_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    canonical_img = soup.find(attrs={"itemprop": "image"})
    if isinstance(canonical_img, Tag):
        # Schema.org microdata renders itemprop=image as a hidden <span>
        # carrying the absolute URL as text. Fall back to src if it's an
        # <img> element on some Odoo themes.
        text_url = canonical_img.get_text(strip=True)
        if text_url:
            add(text_url)
        src = canonical_img.get("src")
        if isinstance(src, str):
            add(src)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    carousel = soup.find(id="o-carousel-product")
    if isinstance(carousel, Tag):
        for img in carousel.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            # Prefer the zoom URL (image_1920) when Odoo exposes it.
            zoom = img.get("data-zoom-image")
            if isinstance(zoom, str):
                add(zoom)
            src = img.get("src")
            if isinstance(src, str):
                add(src)

    return ordered[:12]


class VerusEngineeringAdapter(RetailerCrawlerAdapter):
    """
    Verus Engineering adapter. Discovery: flat ``/sitemap.xml`` urlset
    filtered to ``/shop/<slug>-<id>`` product URLs. Parsing: Odoo Website
    Sale DOM — Schema.org microdata + Odoo's ``data-product-tracking-info``
    JSON for name / SKU / price / category, ``#product_full_description``
    for description, ``#o-carousel-product`` for images. Brand is forced
    to "Verus Engineering" on every part (house-brand-only catalog;
    product titles all lead with the car make, so the generic
    ``part_manufacturer_from_title`` heuristic can't be used).
    """

    ADAPTER_NAME: ClassVar[str] = "verusengineering"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Verus product page. Returns ``None`` for category / blog /
        CMS pages (no Schema.org Product microdata and no ``#product_detail``
        tracking section) or when the product name cannot be recovered.
        """
        if not _is_product_url(url):
            return None
        soup = BeautifulSoup(html, "html.parser")
        if not _is_product_page(soup):
            return None

        tracking = _parse_tracking_info(soup) or {}
        tracking_item_name_raw = tracking.get("item_name") if isinstance(tracking, dict) else None
        tracking_item_name = tracking_item_name_raw if isinstance(tracking_item_name_raw, str) else None
        tracking_price_raw = tracking.get("price") if isinstance(tracking, dict) else None
        tracking_price: Optional[float] = None
        if isinstance(tracking_price_raw, (int, float)):
            tracking_price = float(tracking_price_raw)
        elif isinstance(tracking_price_raw, str):
            try:
                tracking_price = float(tracking_price_raw)
            except ValueError:
                tracking_price = None

        bracket_sku, cleaned_name = _split_sku_and_name(tracking_item_name)
        name = _extract_name(soup, cleaned_name)
        if not name or len(name) < 3:
            return None

        # SKU resolution order: tracking-JSON bracketed prefix, then URL slug,
        # then the PART NUMBER block in the description. All three converge on
        # the same value for every product we checked; order is purely a
        # reliability ranking in case one source is missing.
        part_number = bracket_sku or _sku_from_url(url) or _description_block_sku(soup)
        part_number = normalize_part_number(part_number) if part_number else None

        description = _extract_description(soup)
        price_cents = _extract_price_cents(soup, tracking_price)
        image_urls = _extract_images(soup, url)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            # House-brand-only catalog: force canonical brand on every part.
            # See module docstring for rationale (titles lead with car make,
            # no JSON-LD brand, no meta tag fallback, every product is Verus).
            part_manufacturer=CANONICAL_BRAND,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
        )
