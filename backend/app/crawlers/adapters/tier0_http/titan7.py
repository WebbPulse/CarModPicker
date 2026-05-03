"""
Titan7 (titan-7.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://titan-7.com/products/<handle>``

Titan7 migrated from the un-hyphenated ``titan7.com`` to ``titan-7.com`` in
2026. The legacy host still renders a static landing page (the storefront
Shopify theme is still live at ``/``), but every product URL on that host
now returns 404 — the Shopify sitemap and every ``/products/...`` URL live
on the hyphenated host. ``_is_product_url`` keeps the legacy host allow-
listed so archived CrawledPage rows that reference ``titan7.com`` still
parse during rescrape, but discovery / ingest both target ``titan-7.com``.

Titan7 is a direct-to-consumer forged / flow-formed wheel manufacturer. Tire
Rack does not list Titan7 and Mackin Industries only carries Volks, so this
is its own pricing island — the only way to capture Titan7 set pricing for
BMW / Porsche / Corvette / FK8+FL5 Civic Type R / GR Corolla / STI track
fitments. See ``adapters/RETAILER_BACKLOG.md`` (Tier-0, Shopify) for the
retailer's role in the wheels-forged-direct row.

The storefront is a modern Shopify theme and emits a standard schema.org
``Product`` JSON-LD block in the product HTML (name / description / brand /
sku / offers / image), so parsing reuses the shared
``extract_json_ld_product`` / ``scraped_payload_from_json_ld`` helpers with
one Titan7-specific rule:

- **Manufacturer collapse:** the Shopify vendor field shows up as either
  ``"Titan7"`` or ``"Titan 7"`` (and is occasionally empty on newly added
  SKUs). All of those collapse to the single canonical ``"Titan7"`` so the
  global part-manufacturer list doesn't split one brand across three rows.
  Co-branded SKUs with a distinct JSON-LD brand (rare — Titan7 is almost
  entirely first-party hardware) pass through unchanged.

Discovery: ``/sitemap.xml`` → child ``sitemap_products_N.xml`` urlsets
(standard Shopify shape). Override with ``CRAWLER_TITAN7_START_URLS``
(comma-separated) to use a fixed list.

Fetcher tier: plain HTTP. ``titan7.com`` is Shopify-hosted and serves
sitemap plus product pages to plain ``requests`` with the crawler
User-Agent. Promote to ``"tls"`` if Cloudflare ever begins fingerprinting
the storefront.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse
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
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

# Titan7 migrated its canonical domain to the hyphenated ``titan-7.com`` —
# the bare ``titan7.com`` still serves a legacy landing page but every
# ``/products/...`` URL 404s there now. Discovery and new ingests must use
# the hyphenated host; historical CrawledPage rows that still reference
# ``titan7.com`` are accepted as product-shaped by ``_is_product_url`` so
# the archive-rescrape path remains idempotent.
TITAN7_BASE = "https://titan-7.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://titan-7.com/products/titan-7-valve-stems",
]

# Canonical manufacturer name. Titan7's Shopify vendor field appears as
# ``"Titan7"`` or ``"Titan 7"`` (space) depending on when the product was
# set up, and is occasionally empty on just-launched SKUs. Collapse all
# three to a single canonical brand so the global part-manufacturer table
# doesn't end up with three rows that mean the same thing.
_TITAN7_CANONICAL_BRAND = "Titan7"
_TITAN7_BRAND_VARIANTS = frozenset({"titan7", "titan 7", "titan-7"})

# Shopify CDN thumbnail size suffix (file_300x300.jpg, file_100x100.webp).
# Rejected so we prefer full-resolution product media over picker /
# related-product thumbnails Shopify renders around the gallery.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (nav / footer / logos / banners),
# not product media. Same shape as the AWE / ADRO filters.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|titan7?\.svg|header_|footer_|megamenu|placeholder",
    re.IGNORECASE,
)


def _is_titan7_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of Titan7's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _TITAN7_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for a Titan7 product.

    - Empty / any Titan7-self variant (``"Titan7"``, ``"Titan 7"``,
      ``"titan-7"``) collapses to the single canonical ``"Titan7"``.
    - Anything else (rare co-branded SKU) is passed through unchanged — the
      global part-manufacturer table is authoritative and an unfamiliar brand
      will get its own row via ``get_or_create_part_manufacturer_by_name``.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_titan7_brand_variant(brand):
        return _TITAN7_CANONICAL_BRAND
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_TITAN7_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → each ``sitemap_products_N.xml`` urlset and
    collect every ``/products/...`` URL. Returns deduplicated list (by
    path, query stripped); empty on failure. Mirrors the Shopify discovery
    used by the AWE / ADRO / GMG adapters.
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
            if PRODUCT_PAGE_PATH not in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = TITAN7_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if "sitemap_products_" not in child_url:
                    continue
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                try:
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _canonical_image_key(url: str) -> str:
    """Dedupe key: drop Shopify ``v``/``width``/``height``/``crop`` params so width variants collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=\w+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _is_valid_shopify_product_image(url: str) -> bool:
    """Only Shopify CDN product media; reject site chrome and picker thumbnails."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    if _SHOPIFY_THUMBNAIL_RE.search(low):
        return False
    return True


def _normalize_image_url(url: str) -> str:
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against titan7.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return TITAN7_BASE + u
    return u


def _extract_titan7_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images only.

    Sources (in order): ``og:image``, ``<media-gallery>``, ``.product__media-wrapper``.
    Candidates pass through the Shopify-CDN allowlist + noise/thumbnail filter,
    are upgraded to https, and deduped by canonical URL (ignoring ``v``/``width``
    query params). Capped at 12 so color-swatch thumbnails don't inflate DB rows.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_shopify_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        wrapper = soup.select_one(".product__media-wrapper")
        if isinstance(wrapper, Tag):
            scope = wrapper

    if scope is not None:
        for img in scope.find_all("img", src=True):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())

    return ordered[:12]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a Titan7 ``/products/<handle>`` page.

    Accepts both the current canonical host (``titan-7.com``) and the
    legacy ``titan7.com`` so archived CrawledPage rows keyed off the old
    host still round-trip through this adapter during rescrapes.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host:
        is_new = host == "titan-7.com" or host.endswith(".titan-7.com")
        is_legacy = host == "titan7.com" or host.endswith(".titan7.com")
        if not (is_new or is_legacy):
            return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


class Titan7Adapter(RetailerCrawlerAdapter):
    """
    Titan7 adapter. Shopify storefront, plain HTTP fetch is sufficient.

    Discovery: ``CRAWLER_TITAN7_START_URLS`` env var wins. Otherwise walks
    ``/sitemap.xml`` and every ``sitemap_products_N.xml`` child urlset and
    collects each ``/products/...`` URL. Falls back to ``DEFAULT_START_URLS``
    if discovery returns nothing.

    Parsing: JSON-LD Product first (Shopify emits it by default with name /
    brand / sku / offers / image), then a DOM / og fallback. Manufacturer is
    collapsed to the canonical ``"Titan7"`` whenever the vendor field is
    empty or any self-spelling variant, so the global part-manufacturer
    list doesn't split one brand across multiple rows.
    """

    ADAPTER_NAME: ClassVar[str] = "titan7"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    # Real-corpus pattern: titan-7.com renders one ``<script type="application/ld+json">``
    # ``Product`` block per supported chassis fitment on a single wheel-model URL,
    # and abuses the schema.org ``sku`` field to hold the fitment label
    # (e.g. ``"Acura Integra Type S '23-"``, ``"BMW G80 M3 / G82 M4 '21-"``,
    # ``"Ford F150 Raptor 4 Wheels"``). ``extract_json_ld_product`` returns the
    # first Product, so the same fitment label was being stored as ``part_number``
    # for every wheel SKU on the page — and seven distinct wheel models on
    # ``"Acura Integra Type S '23-"`` would all collide on that one bogus PN.
    # Real Titan7 SKUs are unbroken alphanumeric blocks (``TACC58FADG4P``,
    # ``TASLN35C1215B``, ``TR10-1995-5X1143-CB73``) — they never contain
    # spaces. Reject any candidate that carries whitespace.
    _FITMENT_LIKE_SKU_RE: ClassVar[re.Pattern[str]] = re.compile(r"\s")

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Titan7 product page. JSON-LD Product is the authoritative
        source on Shopify; the DOM / og fallback covers the rare page
        without JSON-LD. Returns ``None`` when the URL is not product-shaped
        or when neither path yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_titan7_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Shopify default).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                raw_pn = payload.part_number
                if raw_pn and self._FITMENT_LIKE_SKU_RE.search(raw_pn):
                    raw_pn = None
                part_number = normalize_part_number(raw_pn) if raw_pn else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                return ScrapedPayload(
                    name=payload.name,
                    product_url=payload.product_url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback — no JSON-LD on the page (rare on Shopify).
        name: Optional[str] = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if isinstance(h1, Tag):
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
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

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if isinstance(sku_elem, Tag):
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # No JSON-LD brand available. Titan7's catalog is entirely their own
        # wheels, so default directly to the canonical brand rather than
        # running the title-first-word heuristic (which would pick up
        # car-make tokens like "BMW" / "Porsche" from fitment-led titles).
        part_manufacturer = _TITAN7_CANONICAL_BRAND

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
