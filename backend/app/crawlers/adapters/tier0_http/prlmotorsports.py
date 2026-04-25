"""
PRL Motorsports (prlmotorsports.com) crawler adapter.

Product URLs: https://www.prlmotorsports.com/products/<handle>
Shopify storefront. PRL emits a standard JSON-LD Product block on product
pages (name, sku, description, brand, offers.price, hero image), which is the
authoritative source for everything except the gallery — JSON-LD ships only
the hero, so we expand with the DOM slideshow.

Brand: PRL is a first-party catalog — the FK8/FL5/10th-gen Si intake, IC, and
downpipe tier is all PRL-branded. JSON-LD ``brand`` is consistently
``"PRL Motorsports"``. We default to that when the field is blank and override
when JSON-LD leaks the target vehicle (``"Honda"``/``"Acura"``) as brand.
Third-party SKUs PRL resells (Hondata FlashPro, KTuner, JB4, etc.) keep their
own brand so cross-retailer dedupe against the house-brand adapters works.

Discovery: ``/sitemap.xml`` → ``sitemap_products_N.xml`` children, filtered to
``/products/`` URLs. Override with ``CRAWLER_PRLMOTORSPORTS_START_URLS``
(comma-separated).
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlencode, urlparse, urlunparse
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
    extract_json_ld_product,
    meta_content,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

PRL_BASE = "https://www.prlmotorsports.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

PRL_BRAND = "PRL Motorsports"

DEFAULT_START_URLS = [
    "https://www.prlmotorsports.com/products/prl-motorsports-2023-honda-civic-type-r-fl5-hi-volume-intake-system",
]

# Shopify CDN path marker — our gallery/noise filters key off this.
_SHOPIFY_CDN_MARKER = "/cdn/shop/"

# Site chrome: logos, sprites, payment-method icons that live in the shared
# Shopify theme and can leak into a loose <img> sweep.
_NON_PRODUCT_MEDIA_RE = re.compile(
    r"/logo[/_-]|favicon|sprite|mega_?menu|placeholder|payment[_-]",
    re.IGNORECASE,
)

# JSON-LD ``brand`` values that should be forced back to ``PRL Motorsports``:
# the vehicle make rather than the actual part manufacturer. PRL's FK8/FL5
# catalog occasionally renders ``"Honda"`` or ``"Acura"`` as brand when the
# Shopify vendor field was left blank and the theme fell back to a meta tag.
_CAR_MAKES = frozenset({"honda", "acura"})

# PRL's own vendor string varies — ``PRL``, ``PRL Motorsports``, ``PRL Motorsports, Inc.``
# all mean the same brand. Collapse any ``prl`` / ``prl …`` prefix to the canonical
# label so cross-page dedupe keys off one manufacturer row.
_PRL_BRAND_RE = re.compile(r"^\s*prl(?:\s|,|-|$)", re.IGNORECASE)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then default."""
    raw = os.environ.get("CRAWLER_PRLMOTORSPORTS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` urlset."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return "sitemap_products" in path


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → each ``sitemap_products_N.xml`` urlset and collect
    every ``/products/`` URL. Skips pages/collections/blogs children. Returns
    deduplicated list (keyed by path, query stripped); empty on failure.
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
        index_text = fetch_page(PRL_BASE + "/sitemap.xml", timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if not _is_product_child_sitemap(child_url):
                    continue
                if fetched > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                fetched += 1
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


def _normalize_part_manufacturer(raw: Optional[str]) -> str:
    """
    Collapse PRL's vendor variants and reject car-make brand values.

    - Empty / whitespace → ``"PRL Motorsports"`` (first-party default).
    - ``"PRL"`` / ``"PRL Motorsports"`` / ``"PRL Motorsports, Inc."`` → ``"PRL Motorsports"``.
    - ``"Honda"`` / ``"Acura"`` (target vehicle leaked into the brand slot) → ``"PRL Motorsports"``.
    - Anything else (Hondata, KTuner, JB4, aFe) passes through unchanged so
      third-party SKUs keep their own manufacturer identity.
    """
    brand = (raw or "").strip()
    if not brand:
        return PRL_BRAND
    if _PRL_BRAND_RE.match(brand):
        return PRL_BRAND
    if brand.lower() in _CAR_MAKES:
        return PRL_BRAND
    return brand


def _canonical_image_url(src: str) -> Optional[str]:
    """
    Return https://host/path (preserving ``?v=`` cache-buster, dropping
    ``?width=N`` responsive-srcset params) or None when the URL should be
    skipped. Restricted to the Shopify CDN path so site-chrome images can't
    sneak in.
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = PRL_BASE + s
    if not s.startswith("http"):
        return None
    if _SHOPIFY_CDN_MARKER not in s and "cdn.shopify.com" not in s:
        return None
    parsed = urlparse(s)
    keep_params: list[tuple[str, str]] = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair:
                continue
            key, _, value = pair.partition("=")
            if key.lower() in {"width", "height", "crop", "padding_color"}:
                continue
            keep_params.append((key, value))
    canonical = urlunparse(("https", parsed.netloc, parsed.path, "", urlencode(keep_params), ""))
    if _NON_PRODUCT_MEDIA_RE.search(canonical):
        return None
    return canonical


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs.

    Starts with ``og:image:secure_url`` / ``og:image`` (the hero), then walks
    the Shopify ``.product-slideshow`` / ``[data-product-photos]`` container
    used by the default Dawn/Debut-family themes. Falls back to the generic
    ``.product__media`` / ``.product__photos`` wrappers if those aren't
    present on a given page's theme variant.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(src: Optional[str]) -> None:
        if not src or len(ordered) >= 12:
            return
        canonical = _canonical_image_url(src)
        if not canonical or canonical in seen:
            return
        seen.add(canonical)
        ordered.append(canonical)

    og = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og, Tag):
        content = meta_content(og)
        if content:
            add(content.strip())

    scope: Optional[Tag] = None
    for selector in (
        ".product-slideshow",
        "[data-product-photos]",
        ".product__media-list",
        ".product__media",
        ".product__photos",
    ):
        found = soup.select_one(selector)
        if isinstance(found, Tag):
            scope = found
            break

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            for attr in ("src", "data-src"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break

    return ordered[:12]


class PRLMotorsportsAdapter(RetailerCrawlerAdapter):
    """
    PRL Motorsports adapter. Discovery via ``/sitemap.xml`` →
    ``sitemap_products_N.xml``. Parsing uses the JSON-LD Product block for
    name/sku/price/description/brand; DOM is used only to expand the image
    gallery beyond the single hero JSON-LD ships.
    """

    ADAPTER_NAME: ClassVar[str] = "prlmotorsports"
    category_targets: ClassVar[list[str]] = ["universal"]
    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a PRL product page into a ``ScrapedPayload``. Returns ``None``
        when no JSON-LD Product is present — PRL emits it on every real
        product page, so a missing block means a soft-404 or non-product URL.
        """
        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_images(soup)

        part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
        part_number = normalize_part_number(payload.part_number) if payload.part_number else None
        image_urls = dom_images[:12] if dom_images else payload.image_urls

        return ScrapedPayload(
            name=payload.name,
            product_url=payload.product_url,
            description=payload.description,
            price_cents=payload.price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=payload.gtin,
        )
