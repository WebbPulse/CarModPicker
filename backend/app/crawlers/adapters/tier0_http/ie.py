"""
Integrated Engineering (performancebyie.com) crawler adapter.

Product URLs: https://performancebyie.com/products/<handle>
Shopify store. The current Impulse theme no longer emits a JSON-LD Product
block, so parsing is DOM-first:

- ``og:title`` / ``og:image:secure_url`` / ``meta[name=description]`` supply
  the product name, hero image, and (truncated) description.
- The inline ``<script data-pdp-variant-json>`` array ships the authoritative
  SKU and cents-denominated price for each variant; we read variant[0].
- The ``.sidebar`` inside ``section.product-main#videos-photos`` holds the
  full gallery as ``.sidebar-item[data-type="image"]`` thumbnails whose
  ``data-src`` points at the full-resolution Shopify CDN image.

Brand: every product on performancebyie.com is IE's own line. We default the
manufacturer to ``"Integrated Engineering"`` rather than running a title
heuristic — titles lead with the chassis (e.g. ``"iE Catback Exhaust System
For VW MK7 Golf R"``), which the generic heuristic would misread as "VW".

Discovery: ``/sitemap.xml`` → ``sitemap_products_N.xml`` children, filtered to
``/products/`` URLs. Override with ``CRAWLER_IE_START_URLS`` (comma-separated).
"""

import html as html_lib
import json
import os
import re
import time
from typing import Any, Iterator, List, Optional
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
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

# Inline ``<script data-pdp-variant-json>`` array the Impulse theme ships on
# every product page. variant[0] is authoritative for sku + price (cents).
_VARIANT_JSON_RE = re.compile(
    r"<script[^>]*\bdata-pdp-variant-json\b[^>]*>(.*?)</script>",
    re.DOTALL | re.IGNORECASE,
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
    the current Impulse-theme gallery: ``.sidebar-item[data-type="image"]``
    inside ``section.product-main#videos-photos``. ``data-src`` holds the
    full-resolution URL; the nested ``<img>`` is a 220px thumbnail that would
    dedupe to the same canonical form. Older themes exposed
    ``.product-slideshow`` / ``[data-product-photos]`` / ``.product__photos``
    — kept as fallbacks so a theme rollback doesn't break parsing.
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

    # Current theme: sidebar thumbnails with data-src pointing at full-res file.
    for item in soup.select('section.product-main#videos-photos .sidebar .sidebar-item[data-type="image"]'):
        if len(ordered) >= 12:
            break
        if not isinstance(item, Tag):
            continue
        ds = item.get("data-src")
        if isinstance(ds, str) and ds.strip():
            add(ds.strip())

    if len(ordered) <= 1:
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


def _extract_variant_data(html: str) -> tuple[Optional[str], Optional[int]]:
    """
    Read sku and price (cents) from the first entry of the inline variant
    JSON. Shopify ships ``price`` already in integer cents; we trust it
    rather than rebuilding from decimal formatting.
    """
    m = _VARIANT_JSON_RE.search(html)
    if not m:
        return None, None
    try:
        variants = json.loads(m.group(1))
    except (json.JSONDecodeError, ValueError):
        return None, None
    if not isinstance(variants, list) or not variants:
        return None, None
    first = variants[0]
    if not isinstance(first, dict):
        return None, None
    sku_raw: Any = first.get("sku")
    price_raw: Any = first.get("price")
    sku: Optional[str] = sku_raw.strip() if isinstance(sku_raw, str) and sku_raw.strip() else None
    price_cents: Optional[int] = None
    if isinstance(price_raw, bool):
        price_raw = None
    if isinstance(price_raw, int) and price_raw > 0:
        price_cents = price_raw
    elif isinstance(price_raw, float) and price_raw > 0:
        price_cents = int(price_raw)
    elif isinstance(price_raw, str) and price_raw.strip():
        try:
            num = float(price_raw)
        except ValueError:
            num = 0.0
        if num > 0:
            # Impulse emits cents as a plain integer; fall back to decimal-dollars
            # only if the string has a decimal point.
            price_cents = int(num) if "." not in price_raw else int(round(num * 100))
    return sku, price_cents


def _extract_og_content(soup: BeautifulSoup, *props: str) -> Optional[str]:
    """Return the first populated meta content from the given og-style property names."""
    for prop in props:
        tag = soup.find("meta", property=prop)
        if isinstance(tag, Tag):
            content = meta_content(tag)
            if content and content.strip():
                return html_lib.unescape(content.strip())
    return None


def _extract_meta_description(soup: BeautifulSoup) -> Optional[str]:
    """Fallback description source — ``<meta name="description">`` mirrors og:description."""
    tag = soup.find("meta", attrs={"name": "description"})
    if isinstance(tag, Tag):
        content = meta_content(tag)
        if content and content.strip():
            return html_lib.unescape(content.strip())
    return None


class IEAdapter(RetailerCrawlerAdapter):
    """
    Integrated Engineering adapter. Discovery via ``/sitemap.xml`` →
    ``sitemap_products_N.xml``. Parsing is DOM-first: og:title / og:description
    / og:image for name/description/hero, ``data-pdp-variant-json`` for
    sku + cents price, and the Impulse sidebar gallery for the remaining
    images. Brand defaults to the IE house brand (``IE_BRAND``).
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an IE product page into a ``ScrapedPayload``. Returns ``None``
        when the page carries neither an ``og:title`` nor an ``<h1>`` — i.e.
        a soft-404 or non-product page.
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_og_content(soup, "og:title")
        if not name:
            h1 = soup.find("h1")
            if isinstance(h1, Tag):
                text = h1.get_text(strip=True)
                if text:
                    name = html_lib.unescape(text)
        if not name:
            return None

        description_raw = _extract_og_content(soup, "og:description") or _extract_meta_description(soup)
        description = normalize_description_text(description_raw, max_len=2000) if description_raw else None

        sku, price_cents = _extract_variant_data(html)
        part_number = normalize_part_number(sku) if sku else None

        dom_images = _extract_images(soup)
        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=IE_BRAND,
            part_number=part_number,
            image_urls=image_urls,
            gtin=None,
        )
