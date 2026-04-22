"""
Injen Technology (injen.com) crawler adapter.

**Host.** Live storefront is ``https://injen.com``. The original recon hosts
``injenonline.com`` (DNS dead) and ``injenusa.com`` (DNS dead) don't resolve;
``injentech.com`` IS live but is a GoDaddy Website Builder 8.0 marketing
site (``generator`` meta tag + ``dps_site_id`` cookie + ``Server: DPS/2.0``),
and its ``/sitemap.ols.xml`` points at a ``*.mysimplestore.com`` Online
Store subdomain that 404s — i.e. there's no working storefront at
``injentech.com``. ``injen.com`` is the real, active e-commerce domain
(Apache + WSM-stamped cookies + a populated 1,845-URL sitemap). We wire
the adapter against ``injen.com`` only; the other hosts are not added to
the adapter's accept list.

**Platform — WSM Commerce** (a.k.a. Web Street Merchant / WSM; the class
prefix ``wsm-`` and the ``wsmsess`` session cookie are the giveaways;
jQuery glue lives in a ``WSM.Product`` global). No Shopify, Magento,
BigCommerce, or WooCommerce fingerprints on the page. URL shape:

- Products: ``/i-<product_id>-<slug>.html`` (e.g.
  ``/i-30497553-injen-evolution-cold-air-intake-system-evo1102.html``)
  — ~1,329 of these in the sitemap.
- Categories: ``/c-<id>-<slug>.html`` (77 entries).
- Static / CMS pages: ``/p-<id>-<slug>.html`` (32), ``/g-<id>-<slug>.html``
  (140), ``/gi-<id>-<slug>.html`` (162), ``/series-<N>-<slug>.html`` (5),
  ``/n-<id>-<slug>.html`` news (82), ``/b-<id>-<slug>.html`` brand (3).

**Platform first — WSM Commerce.** Phase 1 added CS-Cart, AbleCommerce,
Odoo; this is the first WSM adapter in the tree. Future WSM sites should
be able to reuse the microdata-scope pattern below verbatim.

**Sitemap / discovery.** ``/robots.txt`` advertises
``https://injen.com/sitemap_index.xml`` (a sitemap index pointing to a
gzipped ``sitemap.xml.gz``), but ``/sitemap.xml`` returns the same urlset
uncompressed and our fetcher does not handle gzip transparently for
``.xml.gz`` URLs (none of our other adapters do either — see FCP Euro's
note in the README). So we walk ``/sitemap.xml`` directly, filter to the
``/i-<id>-<slug>.html`` product shape, and strip everything else.

**JSON-LD shape — none.** Product pages emit **Schema.org microdata**
(``itemscope itemtype="https://schema.org/Product"``), NOT JSON-LD. The
shape matches what Modern Muscle Xtreme and Verus Engineering already
ship in Phase 1:

- Outer scope: ``<div class="wsm-product-wrapper-id-<id>" itemscope
  itemtype="https://schema.org/Product">`` — exactly one per page (no
  related-product Product cards to guard against, unlike MMX).
- Name: ``<h1 itemprop="name" class="wsm-prod-title">Injen EVOLUTION
  Cold Air Intake System - EVO1102</h1>``. Titles typically read
  ``<Name> - <SKU>`` or ``<Name>`` alone; no car-make-lead ordering
  like ADRO / 034Motorsport.
- SKU: ``<span itemprop="sku" class="wsm-prod-sku">EVO1102</span>``.
  Injen's own part-number family — two or three letters (EVO / SES /
  SP / PF / IS / RD / IC / INT) + digits, sometimes with a C/R suffix
  for the oiled-filter or replacement variant.
- MPN: ``<span itemprop="mpn">843115022761</span>`` — actually the UPC
  barcode on this site, misused as ``mpn``. We route it to ``gtin``
  (UPC-A is GTIN-12 ≈ 12 digits) rather than ``part_number`` so the
  stored SKU stays ``EVO1102`` for cross-retailer dedupe. The pattern
  is identical to 034Motorsport's ``gtin8`` misuse, but here UPCs
  really are 12 digits, so we keep them as ``gtin``.
- Price: nested ``<div itemprop="offers" itemscope
  itemtype="https://schema.org/Offer">`` → ``<span itemprop="price">810.55</span>``.
- Description: ``<div itemprop="description" class="wsm-prod-tab-content">``
  — rich HTML, decent length (2 KB+), always present.
- Brand: ``<a itemprop="brand" itemscope
  itemtype="http://schema.org/Brand" ...>Injen Technology</a>``. Always
  ``Injen Technology`` on this storefront.

**Brand rule — house brand, always.** Injen's storefront is 100 % their
own catalog (intakes / exhausts / intercoolers / air filters / throttle
controllers / apparel — all Injen-branded). The microdata emits the
brand verbatim on every page, so the natural behaviour is to **pass
JSON-LD / microdata brand through unchanged when non-empty**. For defence
in depth we still coerce to ``"Injen Technology"`` when the microdata
brand is empty, or when a title-heuristic fallback lands on a car make
(product titles sometimes lead with the target vehicle — e.g. *"for the
Jeep JK"* — and the stock ``part_manufacturer_from_title`` would
otherwise pick ``Jeep`` / ``Toyota`` / ``Ford`` / ``BMW`` / ``Chevy``
as the "brand"). This follows the pattern Mishimoto, ADRO, and
034Motorsport use for the same reason — single-brand storefronts where
the title heuristic is a liability.

**Variant rule (per VARIANTS.md).** Injen's model mostly side-steps the
multi-permutation problem: every purchasable SKU gets its own ``i-<id>``
product URL (the Evolution cold-air intake for a given chassis ships as
``EVO1102`` at ``/i-30497553-…-evo1102.html``, and the oiled-filter
variant ships as a separate ``EVO1902`` SKU at its own URL). There's no
ProductGroup parent page that lists N variants behind a picker, so each
URL → one ``ScrapedPayload`` is the correct representation. Parallel-row
drift (same family, different oversizes) is mild and matches how
Mishimoto's catalog works — different chassis applications are
genuinely different parts. Treat as **per-URL Product**, same as
Mishimoto / Modern Muscle Xtreme. No ``hasVariant`` / ``ProductGroup``
handling needed.

**Image gallery.** Microdata ``itemprop="image"`` is the
``/images/M<id>.jpg`` hero (M = Medium/Main). Additional shots live in
a ``<ul id="productImageBar" class="wsm-prod-image-bar">`` list where
each ``<li>`` has an ``<a href="/images/F<id>.jpg">`` pointing at the
full-resolution copy (F = Full) and a thumbnail ``<img src="/images/T<id>.jpg">``
(T = Thumb). We collect the ``F<id>.jpg`` links — prefer F over M/T —
dedupe, and cap at 12 to match other adapters.

**Tier rationale — plain HTTP.** ``curl -A 'Mozilla/5.0' https://injen.com/``
returns a fully rendered HTML page with microdata intact, HTTP 200, no
Cloudflare interstitial, no ``cf-mitigated`` header, no ``Just a
moment…`` challenge. Only a stock Apache + a small WSM session cookie.
No TLS fingerprint blocking observed. ``FETCHER_TIER`` stays at the
default ``"http"``.

**Caveats.**

- Alternate hosts (``injenonline.com``, ``injenusa.com``, ``injentech.com``)
  do **not** serve a real storefront — don't add them to the host map.
- ``robots.txt`` disallows ``AhrefsBot`` and ``GPTBot`` outright; our
  default UA is allowed (covered by ``User-agent: *``). The runner's
  robots check will pass for every product URL.
- Sitemap is advertised as ``sitemap_index.xml`` → ``sitemap.xml.gz``
  but ``/sitemap.xml`` returns the uncompressed urlset directly. We fetch
  ``/sitemap.xml`` to avoid gzip handling (see FCP Euro note).
- ``itemprop="mpn"`` carries the UPC barcode rather than a manufacturer
  part number — routed to ``gtin``, not ``part_number``.
- Only ONE ``schema.org/Product`` microdata block per product page (no
  related-product cards with their own microdata — different from MMX).
- ``CRAWLER_INJENTECHNOLOGY_START_URLS`` (comma-separated) overrides the
  default sitemap discovery.
"""

import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_dom_price,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

INJEN_BASE = "https://injen.com"
SITEMAP_URL = f"{INJEN_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
BRAND_CANONICAL = "Injen Technology"

# WSM product URL shape: /i-<digits>-<slug>.html
_PRODUCT_URL_RE = re.compile(r"^/i-\d+-[^/]+\.html$", re.IGNORECASE)

DEFAULT_START_URLS = [
    # Evolution intake — exercises the core microdata shape end-to-end.
    "https://injen.com/i-30497553-injen-evolution-cold-air-intake-system-evo1102.html",
    # Exhaust muffler — non-intake product, confirms cross-category parsing.
    "https://injen.com/i-30497624-injen-60mm-universal-muffler-ses225c.html",
]

# Car-make / chassis / model tokens that the title heuristic sometimes
# picks as "brand" when Injen names a product like "... for the Jeep JK"
# or leads with a platform name. Drop these and coerce to Injen Technology
# rather than grow a phantom "Jeep" / "Toyota" / "Ford" manufacturer.
# Injen advertises across almost every major consumer platform so the
# list is broad; keeping it here rather than in parsing.py so it doesn't
# leak into multi-brand adapters.
_TITLE_CAR_MAKES = frozenset(
    {
        "bmw",
        "audi",
        "volkswagen",
        "vw",
        "porsche",
        "mercedes",
        "mercedes-benz",
        "toyota",
        "scion",
        "lexus",
        "subaru",
        "honda",
        "acura",
        "nissan",
        "infiniti",
        "mitsubishi",
        "mazda",
        "ford",
        "chevrolet",
        "chevy",
        "gmc",
        "cadillac",
        "dodge",
        "chrysler",
        "jeep",
        "ram",
        "hyundai",
        "kia",
        "genesis",
        "tesla",
        "volvo",
        "fiat",
        "mini",
        "suzuki",
    }
)

# Non-gallery image noise under /images/ (site chrome: logo, icons,
# main-menu/* thumbnails, homepage/* backgrounds, ui/* icons). Every
# legitimate gallery URL matches the /images/[FMT]<digits>.<ext> pattern,
# so positive matching is cleaner than a noise regex.
_GALLERY_IMAGE_RE = re.compile(
    r"/images/[FMT]\d{4,}\.(?:jpg|jpeg|png|webp)(?:\?|$)",
    re.IGNORECASE,
)

# UPC-A / GTIN-12 shape — 12 digits exactly. Some products have 13-digit
# EAN-13 values; accept 8 / 12 / 13 / 14 digits total per the GTIN family.
_GTIN_DIGITS_RE = re.compile(r"^\d{8}$|^\d{12,14}$")

_MAX_GALLERY_IMAGES = 12


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk the sitemap; fall back to DEFAULT_START_URLS."""
    raw = os.environ.get("CRAWLER_INJENTECHNOLOGY_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap urlset."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _looks_like_product_url(url: str) -> bool:
    """
    True if ``url`` is a WSM product page on injen.com: path shape
    ``/i-<digits>-<slug>.html``. Everything else in the sitemap
    (``/c-``, ``/p-``, ``/g-``, ``/gi-``, ``/n-``, ``/b-``, ``/series-``)
    is non-product and gets dropped.
    """
    if not url or not url.endswith(".html"):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "injen.com" and not host.endswith(".injen.com"):
        return False
    return bool(_PRODUCT_URL_RE.match(parsed.path or ""))


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (a single flat urlset — 1,845 URLs, no sitemap
    index; the advertised ``sitemap_index.xml`` is just a pointer to a
    gzipped copy of the same urlset) and collect every ``/i-<id>-<slug>.html``
    product URL. Returns a deduplicated list (query-stripped); empty on
    any fetch / parse failure.
    """
    seen: set[str] = set()
    product_urls: List[str] = []

    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=20)
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

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

    return product_urls


def _find_main_product_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Return the outer ``<div class="wsm-product-wrapper-id-<id>" itemscope
    itemtype="https://schema.org/Product">`` container. WSM emits exactly
    one Product microdata block per product page (no related-product cards
    to guard against, unlike AbleCommerce), so the first match is safe —
    but we still pin to the ``wsm-product-wrapper-*`` class so any future
    layout change that introduces related-card microdata can't leak in.
    """
    # Preferred: any element whose class includes a ``wsm-product-wrapper-id-*``
    # marker and carries the Product itemtype.
    for node in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Product$", re.IGNORECASE)}):
        if not isinstance(node, Tag):
            continue
        classes = node.get("class")
        if isinstance(classes, list) and any(
            isinstance(c, str) and c.startswith("wsm-product-wrapper-id-") for c in classes
        ):
            return node
    # Fallback: first Product microdata block anywhere on the page.
    for node in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Product$", re.IGNORECASE)}):
        if isinstance(node, Tag):
            return node
    return None


def _microdata_value(scope: Tag, prop: str) -> Optional[str]:
    """
    Return the first ``itemprop="<prop>"`` value within ``scope`` that
    does NOT live inside a nested ``itemscope`` sub-block. Prevents the
    nested ``offers`` / ``brand`` subtrees (each with their own
    ``itemprop="name"`` and ``itemprop="url"``) from overwriting the
    Product-level name / url.
    """
    for tag in scope.find_all(attrs={"itemprop": prop}):
        if not isinstance(tag, Tag):
            continue
        nested = False
        parent = tag.parent
        while parent is not None and parent is not scope:
            if isinstance(parent, Tag) and parent.has_attr("itemscope"):
                nested = True
                break
            parent = parent.parent
        if nested:
            continue
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        text = tag.get_text(strip=True)
        if text:
            return text
    return None


def _brand_from_scope(scope: Tag) -> Optional[str]:
    """
    Read the nested ``<a itemprop="brand" itemscope itemtype="http://schema.org/Brand">``
    anchor text — on Injen this is always ``"Injen Technology"`` but we
    pass whatever is there through (belt-and-suspenders so a future
    third-party brand on the storefront keeps its identity).
    """
    brand = scope.find(attrs={"itemprop": "brand"})
    if not isinstance(brand, Tag):
        return None
    # Some layouts nest a <meta itemprop="name"> inside the brand block;
    # prefer that when present, otherwise use the anchor text.
    name_tag = brand.find(attrs={"itemprop": "name"})
    if isinstance(name_tag, Tag):
        content = name_tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        text = name_tag.get_text(strip=True)
        if text:
            return text
    text = brand.get_text(strip=True)
    return text if text else None


def _price_from_scope(scope: Tag) -> Optional[int]:
    """
    First plausible ``itemprop="price"`` under the main Product scope.
    On WSM the price lives inside a nested ``itemprop="offers"`` block,
    so we have to look through that sub-itemscope — the naive
    "reject any nested-itemscope" rule would drop every price candidate.
    Policy mirrors ``modernmusclextreme`` but simpler: there is no inner
    ``schema.org/Product`` to guard against here, so the first price
    under the main scope wins. Zero / negative values are skipped.
    """
    for tag in scope.find_all(attrs={"itemprop": "price"}):
        if not isinstance(tag, Tag):
            continue
        raw = tag.get("content")
        if not isinstance(raw, str) or not raw.strip():
            raw = tag.get_text(strip=True)
        if not raw:
            continue
        cents = parse_price_cents(raw)
        if cents is None or cents <= 0:
            continue
        return cents
    return None


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Canonicalize the part_manufacturer value for an Injen product page.

    - Non-empty, non-car-make, non-Injen-variant value → pass through.
      (Future-proofing: if the storefront ever ships a third-party SKU,
      keep the real manufacturer instead of mislabelling it "Injen".)
    - Empty / car make / "Injen …" variant → coerce to
      ``"Injen Technology"``. Covers the microdata-missing fallback path
      plus the title-heuristic case where the first word is the target
      vehicle ("Jeep JK Evolution …").
    """
    brand = (part_manufacturer or "").strip()
    if not brand:
        return BRAND_CANONICAL
    low = brand.lower()
    if low in _TITLE_CAR_MAKES:
        return BRAND_CANONICAL
    # Collapse "Injen", "Injen Tech", "Injen Technology Inc.", etc. into
    # the canonical form regardless of case / trailing qualifier.
    if low == "injen" or low.startswith("injen "):
        return BRAND_CANONICAL
    return brand


def _looks_like_gtin(value: Optional[str]) -> bool:
    """True if ``value`` looks like a GTIN-8 / UPC-A / EAN-13 / GTIN-14 barcode."""
    if not value:
        return False
    digits = re.sub(r"\s+", "", value)
    return bool(_GTIN_DIGITS_RE.match(digits))


def _collect_gallery_images(soup: BeautifulSoup, scope: Optional[Tag], primary: Optional[str]) -> List[str]:
    """
    Collect product gallery image URLs.

    Priority:
    1. ``ul#productImageBar li a[href]`` — each anchor's ``href`` is the
       full-resolution ``/images/F<id>.jpg`` (best quality).
    2. The microdata ``itemprop="image"`` ``src`` (``/images/M<id>.jpg``
       hero) as a tail-end fallback, in case the image bar is missing or
       only has one shot.

    Deduplication keys on the numeric photo id (the ``<id>`` after the
    single-letter resolution prefix), so an F / M / T variant of the same
    photo collapses to one slot regardless of which selector picked it up.
    Capped at ``_MAX_GALLERY_IMAGES``.
    """
    ordered: List[str] = []
    seen_ids: set[str] = set()

    id_re = re.compile(r"/images/[FMT](\d+)\.(?:jpg|jpeg|png|webp)", re.IGNORECASE)

    def _normalize(u: str) -> Optional[str]:
        s = (u or "").strip()
        if not s or s.startswith("data:"):
            return None
        if s.startswith("//"):
            s = "https:" + s
        elif s.startswith("/"):
            s = INJEN_BASE + s
        elif s.startswith("http://"):
            s = "https://" + s[len("http://") :]
        if not s.startswith("http"):
            return None
        if not _GALLERY_IMAGE_RE.search(s):
            return None
        return s

    def add(raw: str) -> None:
        if len(ordered) >= _MAX_GALLERY_IMAGES:
            return
        normalized = _normalize(raw)
        if not normalized:
            return
        match = id_re.search(normalized)
        if not match:
            return
        photo_id = match.group(1)
        if photo_id in seen_ids:
            return
        seen_ids.add(photo_id)
        ordered.append(normalized)

    # 1. Full-resolution gallery anchors (F<id>.jpg).
    bar = soup.find(id="productImageBar")
    if isinstance(bar, Tag):
        for a in bar.find_all("a", href=True):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if isinstance(href, str) and href.strip():
                add(href)
                if len(ordered) >= _MAX_GALLERY_IMAGES:
                    break

    # 2. Microdata hero (M<id>.jpg) — only adds if its photo_id isn't
    # already represented by an F<id> link.
    if primary:
        add(primary)

    # 3. Last-resort: scan scope for any <img itemprop="image"> that
    # didn't surface through the image bar.
    if len(ordered) < _MAX_GALLERY_IMAGES and scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src)
                if len(ordered) >= _MAX_GALLERY_IMAGES:
                    break

    return ordered[:_MAX_GALLERY_IMAGES]


class InjenTechnologyAdapter(RetailerCrawlerAdapter):
    """
    Injen Technology adapter. WSM Commerce storefront at ``injen.com`` —
    platform-first for this tree (previously-seen platforms in the
    backend: Shopify, BigCommerce, Magento 2 / Hyva, WooCommerce,
    CS-Cart, AbleCommerce, Odoo, custom).

    Discovery: flat ``/sitemap.xml`` urlset → filter to ``/i-<id>-<slug>.html``
    product URLs (1,329 of 1,845 total URLs). Override with
    ``CRAWLER_INJENTECHNOLOGY_START_URLS`` (comma-separated).

    Parsing: schema.org **microdata** first (the only structured data the
    page emits — no JSON-LD), scoped to the outer
    ``<div class="wsm-product-wrapper-id-*" itemscope itemtype=".../Product">``
    block so any future related-product cards can't leak in. UPC values
    (currently in ``itemprop="mpn"``) are routed to ``gtin`` so SKU-based
    dedupe keeps using the real Injen part number (``EVO1102`` /
    ``SES225C`` / ``SP1470`` / …).

    Brand: pass through when non-empty and not a car make; coerce to
    ``"Injen Technology"`` when empty or when the title heuristic trips
    on a vehicle platform (``"Jeep JK …"``, ``"Toyota Tundra …"``, etc.).
    Matches the Mishimoto / ADRO / 034Motorsport single-brand pattern.

    Gallery: ``ul#productImageBar li a[href]`` → ``F<id>.jpg`` full-res,
    deduped by numeric photo id, capped at 12. Falls back to the
    microdata ``M<id>.jpg`` hero if the image bar is missing.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``/sitemap.xml`` (flat urlset,
        no sitemap index to walk). Set
        ``CRAWLER_INJENTECHNOLOGY_START_URLS`` (comma-separated) to override
        with a fixed list for smoke tests.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Injen product page. Microdata first; DOM / og fallbacks
        for any field the microdata block leaves blank. Returns ``None``
        when no usable name can be extracted (not a product page).
        """
        soup = BeautifulSoup(html, "html.parser")
        scope = _find_main_product_scope(soup)

        # --- Name ---
        name: Optional[str] = None
        if scope is not None:
            h1 = scope.find("h1", attrs={"itemprop": "name"}) or scope.find("h1")
            if isinstance(h1, Tag):
                text = h1.get_text(strip=True)
                if text:
                    name = text
            if not name:
                name = _microdata_value(scope, "name")
        if not name:
            og_title = soup.find("meta", property="og:title")
            if isinstance(og_title, Tag):
                content = meta_content(og_title)
                if content and content.strip():
                    name = content.strip()
        if not name:
            h1_any = soup.find("h1")
            if isinstance(h1_any, Tag):
                text = h1_any.get_text(strip=True)
                if text:
                    name = text
        if not name or len(name) < 3:
            return None

        # --- Microdata fields (when the Product block is present) ---
        price_cents: Optional[int] = None
        part_number: Optional[str] = None
        gtin: Optional[str] = None
        part_manufacturer: Optional[str] = None
        primary_image: Optional[str] = None

        if scope is not None:
            price_cents = _price_from_scope(scope)

            # SKU — Injen's own part number (EVO1102, SES225C, SP1470, …).
            sku_raw = _microdata_value(scope, "sku") or _microdata_value(scope, "productID")
            part_number = normalize_part_number(sku_raw) if sku_raw else None

            # MPN on this storefront carries the UPC barcode, not a
            # manufacturer part number. Route to gtin if it looks like a
            # GTIN; otherwise treat as a secondary SKU candidate.
            mpn_raw = (
                _microdata_value(scope, "mpn")
                or _microdata_value(scope, "gtin")
                or _microdata_value(scope, "gtin13")
                or _microdata_value(scope, "gtin12")
                or _microdata_value(scope, "gtin8")
            )
            if mpn_raw:
                if _looks_like_gtin(mpn_raw):
                    gtin = re.sub(r"\s+", "", mpn_raw)
                elif not part_number:
                    part_number = normalize_part_number(mpn_raw)

            part_manufacturer = _brand_from_scope(scope)

            # Hero image from microdata <img itemprop="image" src="...">.
            img_tag = scope.find("img", attrs={"itemprop": "image"})
            if isinstance(img_tag, Tag):
                src = img_tag.get("src")
                if isinstance(src, str) and src.strip():
                    primary_image = src.strip()
            if not primary_image:
                primary_image = _microdata_value(scope, "image")

        # --- Fallbacks ---
        if price_cents is None:
            price_cents = extract_dom_price(soup)

        description: Optional[str] = None
        if scope is not None:
            desc_tag = scope.find(attrs={"itemprop": "description"})
            if isinstance(desc_tag, Tag):
                text = desc_tag.get_text(separator=" ", strip=True)
                if text and len(text) > 30:
                    description = normalize_description_text(text, max_len=2000)
        if not description:
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

        if not part_number:
            candidate = extract_sku_from_text(soup.get_text())
            if candidate:
                part_number = candidate
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # Brand cascade: microdata brand is authoritative when present and
        # non-car-make. Otherwise try title / description / fallback
        # heuristics; final _normalize_part_manufacturer pins us to
        # "Injen Technology" for the house-brand common case.
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer)

        image_urls = _collect_gallery_images(soup, scope, primary_image) or None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=gtin,
        )
