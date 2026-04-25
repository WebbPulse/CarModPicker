"""
Function Werk (functionwerk.com) crawler adapter.

Product URLs: https://functionwerk.com/products/<handle>
Shopify store that does NOT emit a JSON-LD Product block (only Organization),
so parsing leans on og:meta tags and the embedded ``ShopifyAnalytics.meta``
JSON blob for SKU/vendor, plus a DOM sweep for the full description and
product-gallery images.

Discovery: sitemap.xml (sitemap index → sitemap_products_N.xml) filtered to
``/products/`` URLs. Override with CRAWLER_FUNCTIONWERK_START_URLS
(comma-separated) to use a fixed list.
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
    extract_dom_price,
    meta_content,
    normalize_description_text,
    normalize_part_number,
)

FUNCTIONWERK_BASE = "https://functionwerk.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# First-party store: every product is branded "Function Werk". Vendor in the
# embedded Shopify analytics blob is always "Function Werk" on the pages
# inspected, so we hardcode rather than pattern-match.
FUNCTIONWERK_BRAND = "Function Werk"

DEFAULT_START_URLS = [
    "https://functionwerk.com/products/2021-acura-tlx-v6-3-0t-type-s-titanium-sport-exhaust",
]

# Non-product media on Function Werk (logos / site assets that sneak into
# the media-gallery DOM region on a few pages).
_NON_PRODUCT_MEDIA_RE = re.compile(
    r"Function_Werk_Logo|/logo[/_-]|favicon|sprite",
    re.IGNORECASE,
)

# SKU lives in the embedded ShopifyAnalytics.meta JSON blob, e.g.
# "variants":[{"id":...,"price":475000,"sku":"FW-AE-02-C"}]
_SHOPIFY_META_SKU_RE = re.compile(r'"sku"\s*:\s*"([^"]+)"')


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_FUNCTIONWERK_START_URLS is set, return that list. Else discover via sitemap (or fallback)."""
    raw = os.environ.get("CRAWLER_FUNCTIONWERK_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch sitemap.xml (and child sitemaps if index), collect all <loc> URLs
    that contain /products/. Returns deduplicated list; empty on failure.
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
            product_urls.append(u)

    try:
        index_url = FUNCTIONWERK_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if PRODUCT_PAGE_PATH not in child_url and "sitemap_products" not in child_url:
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


def _extract_full_description_from_dom(soup: BeautifulSoup, max_len: int = 2000) -> Optional[str]:
    """
    Pull the main product description from the theme's ``.truncate-text`` wrapper
    (Function Werk uses this to wrap the product body copy). Falls back to the
    generic Shopify ``[class*='product__description']`` / ``.rte`` selectors if
    ``.truncate-text`` is absent. Avoids the ``.rte`` inside ``collapsible-tab__content``
    (return/shipping policy) by preferring the product wrapper first.
    """
    for elem in soup.select(".truncate-text"):
        if not isinstance(elem, Tag):
            continue
        text = elem.get_text(separator=" ", strip=True)
        if text and len(text) > 40:
            normalized = normalize_description_text(text, max_len=max_len)
            if normalized:
                return normalized

    for selector in (
        "[class*='product__description']",
        "[class*='product-single__description']",
        ".product-description",
        "#product-description",
    ):
        for elem in soup.select(selector):
            if not isinstance(elem, Tag):
                continue
            text = elem.get_text(separator=" ", strip=True)
            if text and len(text) > 100:
                normalized = normalize_description_text(text, max_len=max_len)
                if normalized:
                    return normalized
    return None


def _extract_sku(raw_html: str) -> Optional[str]:
    """Pull the first SKU from the embedded ShopifyAnalytics meta JSON."""
    match = _SHOPIFY_META_SKU_RE.search(raw_html)
    if not match:
        return None
    return normalize_part_number(match.group(1))


def _canonical_image_url(src: str) -> Optional[str]:
    """
    Return https://host/path (preserving the ?v= cache-buster, dropping ?width=N
    responsive-srcset params) or None when the URL should be skipped.

    - Protocol-relative ``//...`` → ``https://...``
    - Scheme ``http://`` → ``https://``
    - Strips ``width``, ``height``, ``crop`` query params so multiple srcset
      entries for the same image collapse into one.
    - Filters non-product site assets (logo, favicon, sprite).
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = FUNCTIONWERK_BASE + s
    if not s.startswith("http"):
        return None
    parsed = urlparse(s)
    scheme = "https"
    netloc = parsed.netloc
    # Preserve ?v=... (Shopify CDN cache key) but drop responsive-image params.
    keep_params: list[tuple[str, str]] = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair:
                continue
            key, _, value = pair.partition("=")
            if key.lower() in {"width", "height", "crop", "padding_color"}:
                continue
            keep_params.append((key, value))
    query = urlencode(keep_params)
    canonical = urlunparse((scheme, netloc, parsed.path, "", query, ""))
    if _NON_PRODUCT_MEDIA_RE.search(canonical):
        return None
    return canonical


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs.

    Prefers the Shopify ``[id^='MediaGallery__']`` container (the main product
    media carousel) so hero/promo banners elsewhere on the page don't leak in.
    Falls back to og:image:secure_url as the primary image when the gallery
    container isn't found.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(src: Optional[str]) -> None:
        if not src:
            return
        canonical = _canonical_image_url(src)
        if not canonical:
            return
        if canonical in seen:
            return
        seen.add(canonical)
        ordered.append(canonical)

    og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content.strip())

    for gallery in soup.select("[id^='MediaGallery__']"):
        if not isinstance(gallery, Tag):
            continue
        for img in gallery.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            for attr in ("src", "data-src"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break
        if len(ordered) >= 12:
            break

    return ordered[:12]


class FunctionwerkAdapter(RetailerCrawlerAdapter):
    """
    Function Werk adapter. Discovery: start URLs from env or sitemap.
    Parsing: og:meta + embedded ShopifyAnalytics.meta JSON + DOM description;
    no JSON-LD Product block is emitted by the site.
    """

    ADAPTER_NAME: ClassVar[str] = "functionwerk"
    category_targets: ClassVar[list[str]] = ["universal"]
    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Uses sitemap.xml (and child sitemaps) to find all
        /products/ URLs. Set CRAWLER_FUNCTIONWERK_START_URLS (comma-separated)
        to override with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Function Werk product page. Pulls name/description/price from
        og:meta + DOM, SKU from the embedded ShopifyAnalytics meta JSON, and
        images from og:image plus Shopify CDN URLs in the main-area HTML.
        """
        soup = BeautifulSoup(html, "html.parser")

        name: Optional[str] = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if h1:
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
        if not name or len(name) < 3:
            return None

        description = _extract_full_description_from_dom(soup)
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

        price_cents = extract_dom_price(soup)
        part_number = _extract_sku(html)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=FUNCTIONWERK_BRAND,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
