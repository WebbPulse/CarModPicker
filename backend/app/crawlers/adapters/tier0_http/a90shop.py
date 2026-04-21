"""
A90 Shop (a90shop.com) crawler adapter.

Uses JSON-LD first (like the chrome-extension), then A90/Wix-specific DOM:
h1 title, "SKU: ...", "From $...", og:meta, and product description.

Discovery: sitemap.xml (and child sitemaps) to find all /product-page/ URLs.
Override with CRAWLER_A90SHOP_START_URLS (comma-separated) to use a fixed list.
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
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

# Default start URL for PoC; used only when sitemap discovery fails
A90SHOP_BASE = "https://www.a90shop.com"
DEFAULT_START_URLS = [
    "https://www.a90shop.com/product-page/rays-gram-lights-57cr-a90-supra-wheels-bronze",
]

# Sitemap protocol namespace (Wix and standard sitemaps)
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
PRODUCT_PAGE_PATH = "/product-page/"


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_A90SHOP_START_URLS is set, return that list. Else discover via sitemap (or fallback)."""
    raw = os.environ.get("CRAWLER_A90SHOP_START_URLS", "").strip()
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
    that contain /product-page/. Returns deduplicated list; empty on failure.
    """

    def add_product_url(url: str, seen: set[str], out: List[str]) -> None:
        url = (url or "").strip()
        if not url or PRODUCT_PAGE_PATH not in url or url in seen:
            return
        seen.add(url)
        out.append(url)

    def parse_urlset_locs(xml_text: str, seen: set[str], out: List[str]) -> None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return
        for loc in _loc_elements(root):
            if loc.text:
                add_product_url(loc.text, seen, out)

    seen: set[str] = set()
    product_urls: List[str] = []

    try:
        index_url = A90SHOP_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                try:
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text, seen, product_urls)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text, seen, product_urls)
    except Exception:
        return []

    return product_urls


# Wix image URL pattern: only product media from wixstatic (excludes tracking, placeholders)
_WIX_MEDIA_URL_RE = re.compile(
    r"https?://static\.wixstatic\.com/media/[^\s\"'<>]+",
    re.IGNORECASE,
)

# Path segments that indicate promo/logo/banner, not product gallery
_WIX_NON_PRODUCT_PATH = re.compile(
    r"top-promotion|/logo|banner|affirm|icon\.(png|jpg|webp|gif)|1x1|pixel\.gif",
    re.IGNORECASE,
)

# Known A90 Shop non-product media ids (Wix file id after prefix, before ~ or %7E)
# Add ids here when we find logo/site assets that appear before "Related Products"
_A90_NON_PRODUCT_MEDIA_IDS = frozenset(
    {
        "d186b081cecb49fe8cb18f7792c8f0f1",  # A90 shop logo
        "6e48084c31ac47b6bccb899c400fa622",  # "S" / small site icon
    }
)


def _wix_url_to_base(url: str) -> str:
    """Strip /v1/fill/ or /v1/fit/... from Wix URL to get full-size base image."""
    for suffix in ("/v1/fill/", "/v1/fit/"):
        if suffix in url:
            return url.split(suffix)[0]
    return url


def _wix_media_file_id(url: str) -> str:
    """Extract Wix media file id (e.g. ad9611cdf1fd45229cca26cfc549c419) from .../media/0f8225_xxx~mv2.webp."""
    if "/media/" not in url:
        return ""
    segment = url.split("/media/")[-1]
    # 0f8225_xxx~mv2.webp or 0f8225_xxx%7Emv2.png
    if "_" in segment:
        rest = segment.split("_", 1)[1]
        for sep in ("~", "%7e", "%7E"):
            if sep in rest:
                return rest.split(sep)[0].lower()
        return rest.split(".")[0].lower() if "." in rest else rest.lower()
    return ""


def _is_valid_wix_product_image(url: str) -> bool:
    """
    Only allow Wix product media URLs. Reject tracking, data: placeholders,
    bucket URLs, and known promo/logo paths.
    """
    if not url or len(url) < 30:
        return False
    lower = url.lower()
    # Reject non-Wix: tracking, analytics, data: placeholder, bucket
    if lower.startswith("data:"):
        return False
    if "base64" in lower or "clickcease" in lower or "monitor." in lower:
        return False
    if "storageapi.dev" in lower or "stats.aspx" in lower:
        return False
    # Only accept Wix media
    if "static.wixstatic.com/media/" not in lower:
        return False
    # Reject promo/logo/banner paths
    if _WIX_NON_PRODUCT_PATH.search(url):
        return False
    # Reject known A90 Shop logo/site assets (not product gallery)
    if _wix_media_file_id(url) in _A90_NON_PRODUCT_MEDIA_IDS:
        return False
    return True


def _extract_a90_images(soup: BeautifulSoup, raw_html: str) -> List[str]:
    """
    Extract product gallery image URLs for A90 Shop (Wix). Only Wix product media;
    excludes tracking, placeholders, bucket URLs, logos, promo.
    Restricts to HTML before "Related Products" or the comments section so we
    don't include related-product images or comment user avatars.
    """
    # Cut at the earliest of: "Related Products", Wix comments widget, or comment prompts.
    # Comment section profile pictures are also Wix media URLs and would otherwise be included.
    _SECTION_CUTOFFS = [
        "related products",
        "wix-comments",
        'data-hook="comments',
        "add a comment",
        "leave a comment",
        "be the first to comment",
        "comments section",
    ]
    raw_lower = raw_html.lower()
    cut_pos = len(raw_html)
    for marker in _SECTION_CUTOFFS:
        pos = raw_lower.find(marker)
        if pos >= 0:
            cut_pos = min(cut_pos, pos)
    main_html = raw_html[:cut_pos]

    seen_bases: set[str] = set()
    ordered: List[str] = []

    def add_url(src: str, only_if_in_main: bool = False) -> None:
        if not _is_valid_wix_product_image(src):
            return
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = A90SHOP_BASE + src
        src = _wix_url_to_base(src)
        if src in seen_bases:
            return
        if only_if_in_main:
            # URL in HTML often has /v1/fill/...; check if this media file id appears in main area
            if "/media/" in src:
                segment = src.split("/media/")[-1]
                if segment not in main_html:
                    return
            elif src not in main_html:
                return
        seen_bases.add(src)
        ordered.append(src)

    # 1. og:image (in head, always before related)
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add_url(content.strip())

    # 2. img src / data-src: only add if this URL appears in main_html (before Related Products or comments)
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-image"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add_url(val.strip(), only_if_in_main=True)
                break
        else:
            val = img.get("data-srcset")
            if isinstance(val, str) and val.strip():
                first = val.split(",")[0].strip().split()
                if first:
                    add_url(first[0], only_if_in_main=True)

    # 3. Regex on main_html only (so we only get URLs from product area)
    for match in _WIX_MEDIA_URL_RE.findall(main_html):
        add_url(match)
        if len(ordered) >= 12:
            break

    return ordered[:12]


class A90ShopAdapter(RetailerCrawlerAdapter):
    """
    A90 Shop adapter. Discovery: start URLs from env or default list.
    Parsing: JSON-LD first, then Wix-style DOM (h1, SKU:, From $..., og:meta).
    """

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Uses sitemap.xml (and child sitemaps) to find all
        /product-page/ URLs. Set CRAWLER_A90SHOP_START_URLS (comma-separated) to
        override with a fixed list. Runner applies --limit to cap how many are processed.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse A90 Shop product page. JSON-LD first, then A90-specific selectors.
        We always run DOM image extraction (Wix often omits images from JSON-LD)
        and merge images into the payload before returning.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_a90_images(soup, html)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD (same strategy as chrome-extension)
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                # Merge DOM images and price when JSON-LD omits them (common on Wix)
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                if dom_images or price_cents is not None:
                    payload = ScrapedPayload(
                        name=payload.name,
                        product_url=payload.product_url,
                        description=payload.description,
                        price_cents=price_cents,
                        part_manufacturer=payload.part_manufacturer,
                        part_number=payload.part_number,
                        image_urls=dom_images[:12] if dom_images else payload.image_urls,
                        gtin=payload.gtin,
                    )
                return payload

        # 2. DOM fallback: og:meta, h1, SKU, price, description
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

        description = None
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            d = meta_content(og_desc)
            if d and d.strip():
                description = d.strip()[:2000]
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = d.strip()[:2000]
        if not description:
            # First long paragraph in main content
            for p in soup.find_all("p"):
                t = p.get_text(strip=True)
                if t and len(t) > 80 and "related" not in t.lower()[:50]:
                    description = t[:2000]
                    break

        price_cents = extract_dom_price(soup)

        part_number = None
        sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
        if sku_elem:
            part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))

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
