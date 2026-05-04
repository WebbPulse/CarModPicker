"""
Seibon Carbon (seiboncarbon.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://seiboncarbon.com/<slug>.html``. This is a Magento
storefront where product pages sit at the site root (flat namespace, no
``/products/`` prefix), next to CMS pages like ``/products.html`` (a category
listing), ``/news.html``, ``/dealers.html``, etc. The sitemap also exposes
Magento permalinks of the form ``/catalog/product/view/id/14931`` which 301
to the descriptive slug; we skip those so every URL crawled carries real
product metadata in the path.

Seibon is a **house-brand-only** manufacturer — they design and sell their
own carbon-fiber aero (hoods, trunk lids, spoilers, lips, fenders, side
skirts, strut braces, fitment-specific dry-carbon parts) with no third-party
brands in the catalog. Every product is branded ``SEIBON CARBON`` on the
page. This matters for the parser because product titles lead with the
target vehicle — "Carbon fiber Hood for 2009-2010 Honda Civic", "MB-style
carbon fiber side skirts for 2019-2024 Toyota Corolla Hatchback" — so the
generic title-first-word heuristic would otherwise pick *Honda* / *Toyota*
/ *BMW* / *Nissan* etc. as the part manufacturer. ``_normalize_part_manufacturer``
catches the car-make false positive and also catches blank / house-brand-
variant vendor strings, always returning the canonical ``"Seibon"`` (the
global part-manufacturer table stores the short form rather than the "Seibon
Carbon" on-page spelling so the row reads cleanly alongside other aero
brands like ADRO, APR Performance, Varis).

SKU format: position-encoded fitment tags. Observed examples:
  - ``HD0910HDCV-OE``  — **H**oo**D**, **09**-**10**, **H**on**D**a **C**i**V**ic, OE style
  - ``TL19TYCORHB``    — **T**runk **L**id, **19**+, **TY**ota **COR**olla **H**atch**B**ack
  - ``SS19TYCORHB-MB`` — **S**ide **S**kirts, 19+, Toyota Corolla HB, **MB** style
  - ``SB23TYGRCOR-R``  — **S**trut **B**race, 23+, Toyota GR Corolla, **R**ear
The "-XX" suffix (``-OE``, ``-MB``, ``-R``, ``-TS``, ``-VS``, …) encodes the
style variant; these are real distinguishing SKU components, not fitment
metadata, so we keep them verbatim in ``part_number``. No GTIN is published.

Parsing: **DOM-only** — there is no JSON-LD ``Product`` block on Seibon
pages (the theme is an older Magento 2 storefront that never enabled rich
snippets). We pull:
  - name   → ``h1`` (fallback ``og:title`` / ``<title>``)
  - price  → ``meta[property="product:price:amount"]`` / ``og:price:amount``,
             then the shared ``extract_dom_price`` DOM fallback
  - SKU    → any "SKU:" callout in body text (``extract_sku_from_text``);
             further fallback: the first gallery image filename often starts
             with the lowercased SKU (``…/s/b/sb23tygrcor-r_01_1.jpg``)
  - images → ``/media/catalog/product/…`` gallery entries, with Magento
             ``/cache/<hash>/`` variants collapsed to one canonical key so
             a single asset doesn't appear at five sizes. Gallery pages
             usually carry 4–8 photos per listing (front, rear, underside,
             fitment shots); we cap at the shared 12-image limit.
  - brand  → always normalized to ``"Seibon"`` via
             ``_normalize_part_manufacturer``.

Discovery: ``/sitemap.xml`` is a flat urlset (not an index) with everything
— product slugs, CMS pages, category pages, and permalink stubs — in one
file. We filter to ``<loc>`` entries that look like product pages (``.html``
suffix, path depth 1, deny-listed against CMS / permalink patterns). The
alternate path ``/pub/sitemap.xml`` serves the same content but is blocked
by ``robots.txt`` (``Disallow: /pub/``), so we never touch it. Override
with ``CRAWLER_SEIBONCARBON_START_URLS`` (comma-separated) for a fixed list.

``robots.txt`` sets ``Crawl-delay: 10`` for ``User-agent: *``. The runner
respects that automatically (``get_crawl_delay_sec`` → ``max(--delay,
crawl_delay)``), so no adapter-level delay override is needed.

Fetcher tier: FlareSolverr browser. The Magento storefront sits behind
Cloudflare Bot Management with ``cf-mitigated: challenge`` — plain
``requests`` and ``curl_cffi`` Chrome JA3 impersonation (every profile
through chrome136) both 403 immediately, so the check is gating on JS
execution, not TLS fingerprint. FlareSolverr's headless Chromium solves
the managed challenge and reuses the ``cf_clearance`` cookie across the
session, so amortized per-page cost stays close to a normal page load.
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Iterator, List, Optional
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
    fetch_page,
)
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

SEIBONCARBON_BASE = "https://seiboncarbon.com"
SITEMAP_URL = f"{SEIBONCARBON_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

#: Canonical name used in the global ``part_manufacturer`` table. The on-page
#: spelling is "SEIBON CARBON"; we store the short form "Seibon" so brand
#: rows stay consistent with other house-brand aero manufacturers.
BRAND_CANONICAL = "Seibon"

DEFAULT_START_URLS = [
    "https://seiboncarbon.com/carbon-fiber-trunk-lid-for-2019-2022-toyota-corolla-hatchback.html",
    "https://seiboncarbon.com/carbon-fiber-rear-strut-brace-for-2023-2026-toyota-gr-corolla.html",
]

# Car makes and house-brand variants that should collapse to the canonical
# "Seibon" manufacturer. Seibon's titles lead with the target vehicle
# ("Carbon fiber Hood for 2009-2010 Honda Civic Sedan"), so the generic
# title-first-word heuristic would otherwise pick *Honda* / *Toyota* / etc.
# as the part manufacturer.
_CAR_MAKE_BRANDS = frozenset(
    {
        "acura",
        "audi",
        "bmw",
        "chevrolet",
        "chevy",
        "dodge",
        "ford",
        "honda",
        "hyundai",
        "infiniti",
        "lexus",
        "mazda",
        "mercedes",
        "mercedes-benz",
        "mitsubishi",
        "nissan",
        "porsche",
        "scion",
        "subaru",
        "tesla",
        "toyota",
        "volkswagen",
        "vw",
    }
)

#: Normalised form of every house-brand vendor spelling we've observed (plus
#: common typos). Any of these → ``BRAND_CANONICAL``.
_SEIBON_BRAND_VARIANTS = frozenset(
    {
        "seibon",
        "seiboncarbon",
        "seibon carbon",
        "seibon-carbon",
        "seiboncarbonfiber",
        "seibon carbon fiber",
    }
)

#: Sitemap ``<loc>`` paths that are not product pages: Magento permalink
#: stubs (``/catalog/product/view/id/NNNN``), customer / cart / search
#: surfaces, and the top-level CMS tabs. Product slugs never collide with
#: these because they're descriptive multi-word kebab slugs ("mb-style-
#: carbon-fiber-side-skirts-for-2019-2024-toyota-corolla-hatchback").
_NON_PRODUCT_PATH_SUBSTRINGS = (
    "/catalog/",
    "/customer/",
    "/checkout/",
    "/cart/",
    "/wishlist/",
    "/search",
    "/product-search",
    "/sales/",
    "/contacts",
    "/support/",
    "/news",
    "/gallery",
    "/dealers",
    "/about",
    "/account",
    "/sale/",
    "/pub/",
)

#: Top-level ``.html`` slugs that are CMS pages, not products. Seibon uses a
#: flat ``/<slug>.html`` namespace so we can't filter by directory depth
#: alone; a short deny-list catches the handful of known CMS landing pages.
_NON_PRODUCT_TOP_LEVEL_SLUGS = frozenset(
    {
        "products.html",
        "news.html",
        "gallery.html",
        "dealers.html",
        "support.html",
        "sale.html",
        "about.html",
        "contact.html",
        "contacts.html",
        "faq.html",
        "terms.html",
        "privacy.html",
        "shipping.html",
        "returns.html",
        "warranty.html",
        "product-search.html",
    }
)

#: Image URL patterns that are site chrome (nav/logo/banner) rather than
#: product gallery media. Rejected from image extraction.
_IMAGE_NOISE_RE = re.compile(
    r"/logo|logo\.|placeholder|favicon|sprite|icon[-_]|/banner|banner[-_]|/wysiwyg/|/cms/",
    re.IGNORECASE,
)

#: Magento cache-hash segment — collapsed for dedupe so the same asset at
#: multiple rendered sizes counts as one image. Path example:
#: ``/media/catalog/product/cache/<hash>/s/b/sb23tygrcor-r_01_1.jpg`` →
#: ``/media/catalog/product/s/b/sb23tygrcor-r_01_1.jpg``.
_MAGENTO_CACHE_RE = re.compile(r"/cache/[a-f0-9]+/", re.IGNORECASE)

#: Seibon SKU shape — alpha prefix (part-type code), digits (year), more
#: alpha (make/model), optional ``-STYLE`` suffix. Used only as a last-ditch
#: part-number guess from the first gallery image filename when no SKU
#: callout is on the page.
_SKU_FROM_IMAGE_RE = re.compile(
    r"/([A-Za-z]{2,3}\d{2,4}[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,4})?)_",
    re.IGNORECASE,
)

#: Inline Magento Fotorama gallery JSON — an array of objects with
#: ``thumb`` / ``img`` / ``full`` / ``caption`` / ``position`` / ``isMain``
#: keys. The blob is embedded inside a ``data-mage-init`` attribute or an
#: inline script as ``"data": [ {...}, {...} ]``. We pull the array text
#: by balancing brackets so nested arrays in captions can't break parsing.
_FOTORAMA_DATA_RE = re.compile(r'"data"\s*:\s*\[\s*\{\s*"thumb"', re.IGNORECASE)

#: Ancestor class-name tokens that mark a ``<img>`` as belonging to the
#: "related products" / "you may also like" rail rather than the main
#: product gallery. Used to reject those images from the fallback DOM walk.
_RELATED_ANCESTOR_MARKERS = (
    "related-available",
    "related-",
    "products-related",
    "products-upsell",
    "products-crosssell",
    "block-related",
    "block-upsell",
    "block-crosssell",
    "product-item-",
    "upsell",
    "crosssell",
)


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Collapse empty / house-brand / car-make values to the canonical ``"Seibon"``.

    Seibon is a house-brand-only catalog, so *any* extracted vendor string
    that looks like a Seibon spelling, a car make (title heuristic false
    positive), or a whitespace-only blank should fall back to the canonical
    brand. A genuinely third-party name (hypothetical collab — none seen in
    the catalog as of writing) would pass through unchanged so it lands on
    the real brand row.
    """
    if not part_manufacturer or not part_manufacturer.strip():
        return BRAND_CANONICAL
    raw = part_manufacturer.strip()
    key = raw.lower().replace("  ", " ")
    if key in _SEIBON_BRAND_VARIANTS:
        return BRAND_CANONICAL
    if key in _CAR_MAKE_BRANDS:
        return BRAND_CANONICAL
    return raw


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_SEIBONCARBON_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _looks_like_product_url(url: str) -> bool:
    """
    True if ``url`` is a ``/<slug>.html`` product page (flat namespace).

    Rejects:
    - Magento permalink stubs (``/catalog/product/view/id/NNNN``).
    - Customer / cart / checkout / search / news / gallery / CMS paths.
    - Top-level CMS ``.html`` landing pages (``products.html``, ``news.html``, …).
    - Paths more than one segment deep — real product slugs live at the root.
    """
    if not url.endswith(".html"):
        return False
    low = url.lower()
    for bad in _NON_PRODUCT_PATH_SUBSTRINGS:
        if bad in low:
            return False
    # Single trailing segment only (e.g. ``/foo-bar.html``). Two-segment
    # paths on this site are always CMS children (``/support/…``,
    # ``/sale/…``), already caught above — keep the belt-and-suspenders.
    path = url.split("://", 1)[-1].split("/", 1)
    if len(path) < 2:
        return False
    tail_path = path[1]
    if "/" in tail_path:
        return False
    if tail_path in _NON_PRODUCT_TOP_LEVEL_SLUGS:
        return False
    # Descriptive product slugs are long; a 4-char tail almost certainly is not one.
    return len(tail_path) >= 10


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (flat urlset on this site) and collect every
    ``<loc>`` that passes ``_looks_like_product_url``. Returns deduplicated
    list (by canonical path, query stripped); empty on failure so the caller
    falls back to ``DEFAULT_START_URLS``.

    The sitemap is **not** an index here — it's a single urlset with ~1500
    entries mixing products, category pages, CMS content, and permalink
    stubs. If Magento ever gets reconfigured to emit a sitemap index, the
    child-walk branch below handles it automatically.
    """
    seen: set[str] = set()
    product_urls: List[str] = []

    def parse_urlset_locs(xml_text: str) -> None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return
        for loc in _loc_elements(root):
            if not loc.text:
                continue
            u = loc.text.strip()
            if not _looks_like_product_url(u):
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_text = fetch_page(SITEMAP_URL, timeout=20)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                try:
                    child_text = fetch_page(child_url, timeout=20)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against the site."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return SEIBONCARBON_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Magento product media; reject site chrome, placeholders, and data-URIs."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    # Magento stores product images under /media/catalog/product/
    if "/media/catalog/product/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """Dedupe key: collapse Magento ``/cache/<hash>/`` variants to the source asset path."""
    return _MAGENTO_CACHE_RE.sub("/", url)


def _is_inside_related_block(tag: Tag) -> bool:
    """
    True if any ancestor carries a class marking this ``<img>`` as part of a
    related-products / upsell / crosssell rail rather than the main product
    gallery. Lets us reuse Magento's own class names as a scope boundary
    without needing a hand-maintained selector list.
    """
    for anc in tag.parents:
        if not isinstance(anc, Tag):
            continue
        classes = anc.get("class") or []
        if not isinstance(classes, list):
            classes = [str(classes)]
        joined = " ".join(classes).lower()
        if not joined:
            continue
        for marker in _RELATED_ANCESTOR_MARKERS:
            if marker in joined:
                return True
    return False


def _extract_fotorama_gallery(html: str) -> List[str]:
    """
    Pull the full product image gallery from the inline Magento Fotorama
    JSON (``"data": [{ "thumb": "...", "img": "...", "full": "...", ...}, …]``).

    This is the authoritative gallery source on Seibon pages — the initial
    HTML only renders the first image ``<img>``; the carousel entries 2..N
    come from this JSON blob which the theme later hydrates with
    ``mage/gallery/gallery``. Parsing it directly means we capture the full
    4–8 photo set even though only one ``<img>`` is in the static DOM.

    Returns the ``full``-size URLs (falling back to ``img`` then ``thumb``)
    in position order.
    """
    match = _FOTORAMA_DATA_RE.search(html)
    if not match:
        return []

    # Walk forward from the opening ``[`` to find the matching ``]`` so we
    # can json-decode the whole array. Seibon captions are plain (no
    # embedded brackets) so a simple bracket counter with string awareness
    # suffices.
    start = html.find("[", match.start())
    if start < 0:
        return []
    depth = 0
    in_string = False
    escape = False
    end = -1
    for i, ch in enumerate(html[start:], start=start):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        return []

    try:
        items: Any = json.loads(html[start:end])
    except ValueError:
        return []
    if not isinstance(items, list):
        return []

    urls: List[str] = []
    for entry in items:
        if not isinstance(entry, dict):
            continue
        # Skip video entries — not product gallery photos.
        if (entry.get("type") or "").lower() == "video":
            continue
        for key in ("full", "img", "thumb"):
            val = entry.get(key)
            if isinstance(val, str) and val.strip():
                urls.append(val.strip())
                break
    return urls


def _extract_dom_images(html: str, soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery images (Magento ``/media/catalog/product/…``),
    deduped by canonical (cache-hash-stripped) key, capped at 12.

    Preference order:
      1. Inline Fotorama ``"data": [...]`` JSON — authoritative, carries the
         full 4–8 photo gallery even though only one ``<img>`` is in the
         static HTML.
      2. ``og:image`` meta — the hero photo, for pages whose Fotorama blob
         couldn't be parsed.
      3. DOM ``<img>`` walk, rejecting any image whose ancestor class marks
         it as a related / upsell / crosssell item (Magento tags those rails
         with ``related-available`` / ``products-related`` / etc.).

    Magento renders each asset at several ``/cache/<hash>/`` sizes;
    ``_canonical_image_key`` collapses them so we don't end up with
    12 slots filled by the hero image at 5 widths.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    # 1. Fotorama JSON (authoritative gallery).
    for u in _extract_fotorama_gallery(html):
        add(u)
        if len(ordered) >= 12:
            return ordered[:12]

    # 2. og:image hero.
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    # 3. DOM <img> walk — scope-aware (reject related-products ancestors).
    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        if _is_inside_related_block(img):
            continue
        for attr in ("src", "data-src", "data-original", "data-lazy"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break

    return ordered[:12]


def _extract_price_from_meta(soup: BeautifulSoup) -> Optional[int]:
    """Read ``product:price:amount`` / ``og:price:amount`` meta tags (Magento OG)."""
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta_content(meta)
            if content and content.strip():
                try:
                    return int(round(float(content.strip()) * 100))
                except ValueError:
                    continue
    return None


def _sku_from_first_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Last-ditch SKU guess: the first product image filename usually starts
    with the lowercased SKU (``…/s/b/sb23tygrcor-r_01_1.jpg`` → ``sb23tygrcor-r``).
    Only used when no "SKU:" callout appears in body text.
    """
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-original"):
            val = img.get(attr)
            if not isinstance(val, str) or not val.strip():
                continue
            if "/media/catalog/product/" not in val.lower():
                continue
            match = _SKU_FROM_IMAGE_RE.search(val)
            if match:
                raw = match.group(1)
                # Seibon SKUs on the site are rendered uppercase in the body;
                # upper-case to match the "SKU:" callout form where present.
                return normalize_part_number(raw.upper())
    return None


class SeibonCarbonAdapter(RetailerCrawlerAdapter):
    """
    Seibon Carbon adapter. Magento storefront behind Cloudflare Bot
    Management's managed JS challenge — TLS-fingerprint impersonation
    isn't enough (every ``curl_cffi`` Chrome profile 403s), so this
    runs on the ``browser`` tier via FlareSolverr.

    Discovery: ``CRAWLER_SEIBONCARBON_START_URLS`` env var wins. Otherwise
    walks the flat urlset at ``/sitemap.xml`` and yields every ``/<slug>.html``
    entry that isn't a CMS page or permalink stub. Falls back to
    ``DEFAULT_START_URLS`` when discovery returns nothing.

    Parsing: **DOM-only** — the theme emits no JSON-LD. We pull the name
    from ``h1`` (fallback ``og:title``), price from ``product:price:amount``
    meta / DOM scan, SKU from body-text "SKU:" callouts (fallback: first
    gallery image filename), and the image gallery from
    ``/media/catalog/product/…`` with Magento cache-hash variants collapsed.
    Manufacturer is always normalized to ``"Seibon"`` because the catalog
    is house-brand-only and title heuristics would otherwise pick the car
    make (Honda / Toyota / BMW …) out of titles that lead with the vehicle.
    """

    ADAPTER_NAME: ClassVar[str] = "seiboncarbon"
    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from ``/sitemap.xml``; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Seibon Carbon product page.

        Returns ``None`` when the URL is not product-shaped or when no name
        can be extracted. JSON-LD is attempted defensively in case the theme
        is upgraded — if a ``Product`` block ever appears, we use it — but
        the DOM path is the primary source today.
        """
        if not _looks_like_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(html, soup)
        dom_price = _extract_price_from_meta(soup) or extract_dom_price(soup)

        # 1. Defensive JSON-LD path — Seibon doesn't emit Product schema today
        #    but a Magento upgrade could enable rich snippets. If present,
        #    use it and still force the house brand.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                if not part_number:
                    part_number = extract_sku_from_text(soup.get_text()) or _sku_from_first_image(soup)
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=_normalize_part_manufacturer(payload.part_manufacturer),
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM path (primary).
        name: Optional[str] = None
        h1 = soup.find("h1")
        if isinstance(h1, Tag):
            h1_text = h1.get_text(strip=True)
            if h1_text:
                name = h1_text
        if not name:
            og_title = soup.find("meta", property="og:title")
            content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
            if content_title and content_title.strip():
                name = content_title.strip()
        if not name:
            title_tag = soup.find("title")
            if isinstance(title_tag, Tag):
                t = title_tag.get_text(strip=True)
                # Magento titles are usually "Product Name | Seibon Carbon"
                if t:
                    name = t.split(" | ")[0].strip() or t
        if not name or len(name) < 3:
            return None

        description: Optional[str] = None
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            d = meta_content(og_desc)
            if d and d.strip():
                description = normalize_description_text(d, max_len=2000)
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000)
        if not description:
            # Magento product-description block — the theme renders the
            # catalog "description" attribute inside a div with class
            # containing "description"; take the first such non-empty block
            # that's longer than the boilerplate Prop-65 warning.
            desc_elem = soup.select_one("div.product.attribute.description") or soup.select_one(
                ".product-info-main .description, #description, .product.description"
            )
            if isinstance(desc_elem, Tag):
                text = desc_elem.get_text(separator=" ", strip=True)
                if text and len(text) > 80:
                    description = normalize_description_text(text, max_len=2000)

        # SKU: body-text "SKU:" callout first (Magento theme renders one in
        # the product-info block). Fallback to the image-filename heuristic
        # for the rare listing where the SKU is only shown as a data attr.
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = _sku_from_first_image(soup)

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=BRAND_CANONICAL,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
