"""
034Motorsport (034motorsport.com) crawler adapter.

Product URLs: https://www.034motorsport.com/<slug>.html (flat namespace —
there is no ``/products/`` prefix; product slugs sit at the site root next
to CMS pages, so we can't filter on a path substring).

Parsing: JSON-LD ``Product`` first (the Magento theme emits a clean block
with name / sku / brand / description / offers.price), then shared DOM
fallbacks (og:meta, h1, extract_dom_price, part_manufacturer_from_title).
The JSON-LD ``gtin8`` field is misused by the site to hold the SKU (not a
real 8-digit GTIN), but ``scraped_payload_from_json_ld`` only reads
``sku``/``mpn``, so the bad gtin never reaches the ScrapedPayload.

Discovery: robots.txt points to /media/sitemaps/sitemap.xml — a single
flat urlset (not an index) where every <loc> is a product page. Override
with CRAWLER_MOTORSPORT034_START_URLS (comma-separated) for a fixed list.

Brand: the JSON-LD brand is almost always ``034Motorsport`` (they carry
their own parts). When brand is missing or the generic title heuristic
trips on a car make (Audi/VW/BMW — this site's entire catalog is those
platforms), we normalize to ``034Motorsport``.
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

MOTORSPORT034_BASE = "https://www.034motorsport.com"
SITEMAP_URL = f"{MOTORSPORT034_BASE}/media/sitemaps/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
BRAND_CANONICAL = "034Motorsport"

DEFAULT_START_URLS = [
    "https://www.034motorsport.com/034motorsport-m10-main-stud-kit-ea837-3-0t.html",
]

# Car makes 034 builds for. When the title heuristic picks one of these as
# part_manufacturer it's a false positive — the title leads with the target
# platform (e.g. "Audi B9 S4/S5 …") — fall back to the house brand.
_CAR_MAKE_BRANDS = frozenset({"audi", "volkswagen", "vw", "porsche", "bmw"})

# Sitemap <loc>s we don't want even though they live on the same host —
# CMS pages, landing pages, the homepage. Product slugs on this site don't
# collide with any of these, so a simple substring match is enough.
_NON_PRODUCT_SLUGS = (
    "/home",
    "/privacy-policy",
    "/terms",
    "/return-policy",
    "/shipping-policy",
    "/contact",
    "/about",
    "/blog",
    "/news",
    "/warranty",
)


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Collapse brand variants to the canonical ``034Motorsport`` and rescue the
    car-make false positive. Third-party brands (rare on this site) pass through.
    """
    if not part_manufacturer or not part_manufacturer.strip():
        return BRAND_CANONICAL
    b = part_manufacturer.strip()
    low = b.lower().replace(" ", "").replace("-", "")
    if low in ("034motorsport", "034", "034motorsports"):
        return BRAND_CANONICAL
    if b.lower() in _CAR_MAKE_BRANDS:
        return BRAND_CANONICAL
    return b


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_MOTORSPORT034_START_URLS is set, use it; else discover via sitemap."""
    raw = os.environ.get("CRAWLER_MOTORSPORT034_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _looks_like_product_url(url: str) -> bool:
    """
    Product URLs on 034 end in ``.html`` and live at the site root. Reject CMS
    pages by slug substring. Extremely short slugs (<= 3 chars before ``.html``)
    are almost always category/CMS pages, not product pages.
    """
    if not url.endswith(".html"):
        return False
    low = url.lower()
    for bad in _NON_PRODUCT_SLUGS:
        if bad in low:
            return False
    # Require a reasonably long slug — product names are always descriptive.
    try:
        tail = url.rsplit("/", 1)[-1]
    except Exception:
        return False
    return len(tail) >= 10


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch /media/sitemaps/sitemap.xml (a flat urlset on this site) and collect
    every <loc> that looks like a product URL. Returns deduplicated list (by
    canonical path, query stripped); empty on failure.
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


# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"/logo|logo\.|placeholder|favicon|sprite|icon[-_]|/banner|banner[-_]|cms/",
    re.IGNORECASE,
)


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against the site."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return MOTORSPORT034_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Magento product media; reject site chrome and data-URIs."""
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


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """Collect product gallery images (Magento /media/catalog/product/...), deduped, capped at 12."""
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        # Collapse Magento cache-hash variants of the same asset.
        key = re.sub(r"/cache/[a-f0-9]+/", "/", u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src", "data-original", "data-lazy"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break
    return ordered[:12]


class Motorsport034Adapter(RetailerCrawlerAdapter):
    """
    034Motorsport adapter. Discovery: flat urlset at /media/sitemaps/sitemap.xml.
    Parsing: JSON-LD Product first (Magento emits clean schema), then DOM/og
    fallback using the shared parsing helpers.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from /media/sitemaps/sitemap.xml. Set
        CRAWLER_MOTORSPORT034_START_URLS (comma-separated) to override.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a 034Motorsport product page. Tries JSON-LD Product first, then
        DOM/og fallback. Returns None when no name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (present on every real product page).
        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=None,  # site misuses gtin8 to hold the SKU; never a real GTIN
                )

        # 2. DOM / og fallback.
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

        price_cents = dom_price
        if price_cents is None:
            # Magento sometimes exposes product:price:amount in og meta.
            og_amount = soup.find("meta", property="product:price:amount")
            if isinstance(og_amount, Tag):
                amt = meta_content(og_amount)
                if amt and amt.strip():
                    try:
                        price_cents = int(round(float(amt.strip()) * 100))
                    except ValueError:
                        price_cents = None

        part_number = extract_sku_from_text(soup.get_text())
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
