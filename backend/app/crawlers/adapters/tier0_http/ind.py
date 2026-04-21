"""
IND Distribution (ind-distribution.com) crawler adapter.

Product URLs: https://ind-distribution.com/products/<handle>[?variant=<id>]
IND is a multi-brand Shopify retailer (LCK, Dinan, Akrapovic, KW, Eventuri, …).
JSON-LD brand is the real manufacturer — the Booster Apps SEO plugin emits a
proper Product schema with ``brand.name`` populated (see the /products/... page
source) — so pass it through unchanged. Do NOT coerce brand to "IND
Distribution"; that would wipe the useful information.

Discovery: sitemap.xml (Shopify sitemap index → sitemap_products_N.xml children).
Override with CRAWLER_IND_START_URLS (comma-separated) to use a fixed list.
"""

import os
import re
import time
from typing import Iterator, List, Optional
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
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

IND_BASE = "https://ind-distribution.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://ind-distribution.com/products/lck-bmw-m-carbon-bucket-seat-bolster-protector-set",
]

# Car makes that the title heuristic sometimes picks when a product title leads
# with the target vehicle (e.g. "BMW G87 M2 …"). IND carries dozens of third-
# party manufacturers, so unlike ADRO we can't collapse these to a house brand —
# the honest answer is "unknown", so we drop the value and let the description /
# fallback heuristics try next.
_TITLE_CAR_MAKES = frozenset(
    {
        "bmw",
        "porsche",
        "toyota",
        "honda",
        "lexus",
        "subaru",
        "nissan",
        "audi",
        "mercedes",
        "mercedes-benz",
        "ford",
        "chevrolet",
        "chevy",
        "tesla",
        "hyundai",
        "kia",
        "genesis",
        "mini",
        "vw",
        "volkswagen",
    }
)


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> Optional[str]:
    """
    Trim whitespace; drop car-make values that the title heuristic may have
    picked. Returns None rather than a coerced fallback so downstream heuristics
    can try; JSON-LD brand (the primary path) always wins before we reach here.
    """
    if not part_manufacturer:
        return part_manufacturer
    brand = part_manufacturer.strip()
    if not brand:
        return None
    if brand.lower() in _TITLE_CAR_MAKES:
        return None
    return brand


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_IND_START_URLS is set, return that list. Else discover via sitemap (or fallback)."""
    raw = os.environ.get("CRAWLER_IND_START_URLS", "").strip()
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
    that contain /products/. Returns deduplicated list (by path); empty on failure.
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
        index_url = IND_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if PRODUCT_PAGE_PATH[:-1] not in child_url and "sitemap_products" not in child_url:
                    # Skip pages / collections / blogs sitemaps — we only want products.
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
    DOM description fallback when JSON-LD description is missing/short. Scans
    Shopify theme selectors and long <p> tags in <main>. Takes the longest match
    (full product description rather than a truncated lead paragraph).
    """
    candidates: List[str] = []
    for selector in (
        "[class*='product__description']",
        "[class*='product-single__description']",
        ".product-description",
        "#product-description",
        "[class*='rte']",
    ):
        for elem in soup.select(selector):
            if not isinstance(elem, Tag):
                continue
            text = elem.get_text(separator=" ", strip=True)
            if text and len(text) > 150:
                candidates.append(text)
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main and isinstance(main, Tag):
        for p in main.find_all("p"):
            if not isinstance(p, Tag):
                continue
            t = p.get_text(strip=True)
            if t and len(t) > 150:
                candidates.append(t)
    if not candidates:
        return None
    best = max(candidates, key=len)
    return normalize_description_text(best, max_len=max_len)


def _normalize_image_url(url: str) -> str:
    """Upgrade // or http:// to https://; resolve absolute paths against IND_BASE."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return IND_BASE + u
    return u


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images. og:image first, then img tags scoped to the product
    media container (media-gallery / product__media-wrapper), with site chrome
    filtered out. Capped at 12.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or len(urls) >= 12:
            return
        u = _normalize_image_url(u)
        if not u.startswith("http"):
            return
        low = u.lower()
        if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
            return
        # Strip Shopify's width/height/v/crop params so width variants collapse.
        key = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", u).replace("?&", "?").rstrip("?&")
        if key in seen:
            return
        if re.search(r"logo|favicon|placeholder|mega_?menu|/banner_|_banner", low):
            return
        seen.add(key)
        urls.append(u)

    og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        wrapper = soup.select_one(".product__media-wrapper, [class*='product-media']")
        if isinstance(wrapper, Tag):
            scope = wrapper

    if scope is not None:
        for img in scope.find_all("img", src=True):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())
    else:
        for img in soup.find_all("img", src=True):
            if not isinstance(img, Tag) or len(urls) >= 12:
                break
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())

    return urls[:12]


class INDAdapter(RetailerCrawlerAdapter):
    """
    IND Distribution adapter. Discovery: sitemap or CRAWLER_IND_START_URLS.
    Parsing: JSON-LD first (Booster Apps SEO emits Product schema with accurate
    brand/sku/price), then DOM fallback via shared helpers. Brand is passed
    through unchanged — IND is a multi-brand retailer and the JSON-LD value is
    the actual part manufacturer.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from sitemap.xml → sitemap_products_N.xml.
        Set CRAWLER_IND_START_URLS (comma-separated) to override with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an IND product page. JSON-LD first (Shopify), then DOM fallback.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD (authoritative on Shopify + Booster Apps SEO).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                description = payload.description
                if not description or len(description) < 50:
                    dom_desc = _extract_full_description_from_dom(soup)
                    if dom_desc and len(dom_desc) > len(description or ""):
                        description = dom_desc
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                return ScrapedPayload(
                    name=payload.name,
                    product_url=payload.product_url,
                    description=description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM fallback: og:meta, h1, description, price, SKU, brand, images.
        name = None
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
                    description = normalize_description_text(d, max_len=2000) or d.strip()[:2000]
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000) or d.strip()[:2000]

        price_cents = extract_dom_price(soup)
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if sku_elem:
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer)

        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
        )
