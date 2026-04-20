"""
Integrated Engineering (performancebyie.com) crawler adapter.

Product URLs: https://performancebyie.com/products/<handle>
Shopify store that emits a clean JSON-LD Product block with name, description,
sku (top-level), price (from offers[0]), brand (plain string
``"Integrated Engineering"``), and a single ImageObject. JSON-LD is the
authoritative source for everything except the image gallery — JSON-LD ships
only the hero image, so the full gallery is pulled from the DOM
``.product-slideshow`` / ``[data-product-photos]`` container.

Brand: IE's JSON-LD consistently emits ``"Integrated Engineering"``. First-party
catalog — every product is IE-branded. When JSON-LD omits the brand we still
default to ``"Integrated Engineering"`` rather than relying on the title
heuristic (titles lead with the chassis, e.g. ``"iE Catback Exhaust System For
VW MK7 Golf R"``, which would otherwise get picked up as "VW").

Discovery: ``/sitemap.xml`` → ``sitemap_products_N.xml`` children, filtered to
``/products/`` URLs. Override with ``CRAWLER_IE_START_URLS`` (comma-separated).
"""

import os
import re
import time
from typing import Iterator, List, Optional
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

IE_BASE = "https://performancebyie.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

IE_BRAND = "Integrated Engineering"

DEFAULT_START_URLS = [
    "https://performancebyie.com/products/ie-catback-exhaust-system-for-vw-mk7-golf-r-audi-8v-s3",
]

# Shopify CDN path marker — our gallery/noise filters key off this.
_SHOPIFY_CDN_MARKER = "/cdn/shop/"

# Site chrome: logos, sprites, payment-method icons that live in the shared
# Shopify theme and can leak into a loose <img> sweep.
_NON_PRODUCT_MEDIA_RE = re.compile(
    r"/logo[/_-]|favicon|sprite|mega_?menu|placeholder|payment[_-]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then default."""
    raw = os.environ.get("CRAWLER_IE_START_URLS", "").strip()
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
        index_text = fetch_page(IE_BASE + "/sitemap.xml", timeout=15)
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
        s = IE_BASE + s
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
    the Shopify ``.product-slideshow`` / ``[data-product-photos]`` container so
    hero/promo banners elsewhere on the page don't leak in. Falls back to the
    ``.product__photos`` wrapper if the slideshow container is absent.
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
    for selector in (".product-slideshow", "[data-product-photos]", ".product__photos"):
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


class IEAdapter(RetailerCrawlerAdapter):
    """
    Integrated Engineering adapter. Discovery via ``/sitemap.xml`` →
    ``sitemap_products_N.xml``. Parsing uses the JSON-LD Product block for
    name/sku/price/description/brand; DOM is used only to expand the image
    gallery beyond the single hero JSON-LD ships.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an IE product page into a ``ScrapedPayload``. Returns ``None``
        when no JSON-LD Product is present — IE emits it on every real product
        page, so a missing block means the URL is a soft-404 or non-product.
        """
        item = extract_json_ld_product(html)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_images(soup)

        part_manufacturer = (payload.part_manufacturer or "").strip() or IE_BRAND
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
