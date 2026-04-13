"""
Generic (site-agnostic) crawler adapter.

Used as the fallback parser when no site-specific adapter matches the URL.
Strategy mirrors the chrome-extension content script:
  1. JSON-LD Product schema (Shopify, WooCommerce, most modern e-commerce)
  2. Open Graph / meta tags
  3. DOM heuristics (h1, price selectors, gallery images, SKU elements)

This adapter's discover_product_urls() is intentionally a no-op — it is only
ever instantiated for parse_product_page() calls from the /scrape endpoint or
the admin archive rescrape pipeline.
"""

import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    brand_fallback_from_title,
    brand_from_description,
    brand_from_title,
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

# URL path patterns for part number extraction (e.g. /product/ABC-123 or /p/ABC-123)
_PRODUCT_PATH_RE = re.compile(
    r"/(?:product|p|item|parts?|shop)s?/([A-Za-z0-9][\w\-\.]+)(?:/|$)",
    re.IGNORECASE,
)

# Minimum image dimensions (width/height attrs) to consider a product image
_MIN_IMAGE_DIMENSION = 100

# URL path segments that strongly indicate non-product images (logos, icons, tracking)
_NON_PRODUCT_IMAGE_PATH_RE = re.compile(
    r"logo|icon|banner|pixel|tracking|analytics|badge|placeholder|spinner|avatar|"
    r"1x1|2x2|spacer|blank|loading|fallback",
    re.IGNORECASE,
)

# Image file extensions we accept
_IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif)(\?|$)", re.IGNORECASE)


def _is_likely_product_image(url: str) -> bool:
    """Heuristic filter: reject tracking pixels, logos, icons; accept product-looking images."""
    if not url or len(url) < 10:
        return False
    if url.startswith("data:"):
        return False
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
    except Exception:
        return False
    if _NON_PRODUCT_IMAGE_PATH_RE.search(path):
        return False
    # Only accept common image extensions (rejects SVG, fonts, etc.)
    if not _IMAGE_EXT_RE.search(path) and "?" not in path:
        return False
    return True


def _extract_generic_images(soup: BeautifulSoup) -> List[str]:
    """
    Extract product image URLs using a broad, site-agnostic strategy:
    1. og:image meta tag (most reliable single image)
    2. Common product gallery / featured image selectors
    3. Any <img> tags with width/height >= MIN_IMAGE_DIMENSION
    """
    seen: set[str] = set()
    images: List[str] = []

    def add(url: str) -> None:
        url = url.strip()
        if not url or url in seen:
            return
        if url.startswith("//"):
            url = "https:" + url
        if not _is_likely_product_image(url):
            return
        seen.add(url)
        images.append(url)

    # 1. og:image
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content)

    # 2. Common product image container selectors (Shopify, WooCommerce, Magento, BigCommerce, etc.)
    product_image_selectors = [
        # Shopify
        "[data-product-featured-image]",
        ".product__media img",
        ".product-single__photo img",
        ".product-featured-media img",
        # WooCommerce
        ".woocommerce-product-gallery__image img",
        ".wp-post-image",
        # Generic product patterns
        ".product-image img",
        ".product-gallery img",
        ".product-photo img",
        "#product-image",
        "[data-main-image]",
        "[data-zoom-image]",
        ".main-image img",
        '[itemprop="image"]',
        # BigCommerce
        ".productView-image img",
        ".productView-thumbnail img",
    ]
    for selector in product_image_selectors:
        for el in soup.select(selector):
            for attr in ("src", "data-src", "data-zoom-image", "data-large-image", "data-full"):
                val = el.get(attr) if isinstance(el, Tag) else None
                if isinstance(val, str) and val.strip():
                    add(val)
                    break
            if len(images) >= 12:
                break
        if len(images) >= 12:
            break

    # 3. Fallback: <img> tags with size attributes suggesting a product photo
    if len(images) < 3:
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue
            w = img.get("width")
            h = img.get("height")
            try:
                if w and int(str(w)) < _MIN_IMAGE_DIMENSION:
                    continue
                if h and int(str(h)) < _MIN_IMAGE_DIMENSION:
                    continue
            except (ValueError, TypeError):
                pass
            for attr in ("src", "data-src", "data-lazy-src", "data-original"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val)
                    break
            if len(images) >= 12:
                break

    return images[:12]


def _extract_generic_description(soup: BeautifulSoup) -> Optional[str]:
    """og:description → meta description → first long paragraph."""
    for prop, attr in [("og:description", "property"), ("description", "name")]:
        meta = soup.find("meta", {attr: prop})
        if isinstance(meta, Tag):
            d = meta_content(meta)
            if d and len(d.strip()) > 10:
                return d.strip()[:2000]
    # First long paragraph outside of nav/header/footer
    for p in soup.find_all("p"):
        if not isinstance(p, Tag):
            continue
        # Skip paragraphs inside navigation/header/footer
        parents = [a.name for a in p.parents if isinstance(a, Tag)]
        if any(t in parents for t in ("nav", "header", "footer")):
            continue
        t = p.get_text(separator=" ", strip=True)
        if t and len(t) > 80:
            return t[:2000]
    return None


def _extract_part_number_from_url(url: str) -> Optional[str]:
    """Extract part number candidate from URL path (e.g. /product/ABC-123)."""
    try:
        path = urlparse(url).path
    except Exception:
        return None
    m = _PRODUCT_PATH_RE.search(path)
    if not m:
        return None
    candidate = m.group(1).strip()
    return normalize_part_number(candidate)


class GenericHtmlParser(RetailerCrawlerAdapter):
    """
    Site-agnostic HTML parser used as fallback when no specific adapter matches.

    Mirrors the chrome-extension scraping pipeline:
    JSON-LD → OG/meta tags → DOM heuristics.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Not applicable for a generic parser — yields nothing."""
        return iter([])

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse any product page. JSON-LD first, supplemented with DOM fallbacks
        for missing fields (images, price, brand, part number).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_generic_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (covers Shopify, WooCommerce, BigCommerce, most modern stores)
        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                # Supplement missing images and price from DOM
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls if payload.image_urls else (dom_images or None)
                image_url = (image_urls[0] if image_urls else None) or payload.image_url
                # Supplement missing brand from title heuristics
                brand = payload.brand
                if not brand:
                    brand = brand_from_title(payload.name)
                if not brand and payload.description:
                    brand = brand_from_description(payload.description, product_name=payload.name)
                if not brand:
                    brand = brand_fallback_from_title(payload.name)
                # Supplement missing part number
                part_number = payload.part_number
                if not part_number:
                    part_number = _extract_part_number_from_url(url)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    brand=brand,
                    part_number=part_number,
                    image_url=image_url,
                    image_urls=image_urls[:12] if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM fallback: og:title → h1
        name: Optional[str] = None
        og_title = soup.find("meta", property="og:title")
        if isinstance(og_title, Tag):
            t = meta_content(og_title)
            if t and t.strip():
                name = t.strip()
        if not name:
            h1 = soup.find("h1")
            if isinstance(h1, Tag):
                t = h1.get_text(strip=True)
                if t:
                    name = t
        if not name:
            title_tag = soup.find("title")
            if isinstance(title_tag, Tag):
                t = title_tag.get_text(strip=True)
                # Strip common site name suffixes like " | StoreName"
                for sep in (" | ", " - ", " :: "):
                    if sep in t:
                        t = t.split(sep)[0].strip()
                        break
                if t and len(t) > 3:
                    name = t
        if not name or len(name) < 3:
            return None

        description = _extract_generic_description(soup)
        price_cents = dom_price

        # Part number: SKU element → body text → URL path
        part_number: Optional[str] = None
        sku_elem = soup.find(class_=re.compile(r"\bsku\b", re.I)) or soup.find(id=re.compile(r"\bsku\b", re.I))
        if isinstance(sku_elem, Tag):
            part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(name))
        if not part_number:
            part_number = _extract_part_number_from_url(url)

        # Brand: title → description → fallback
        brand: Optional[str] = brand_from_title(name)
        if not brand and description:
            brand = brand_from_description(description, product_name=name)
        if not brand:
            brand = brand_fallback_from_title(name)

        image_url = dom_images[0] if dom_images else None
        image_urls: Optional[List[str]] = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            brand=brand,
            part_number=part_number,
            image_url=image_url,
            image_urls=image_urls,
        )
