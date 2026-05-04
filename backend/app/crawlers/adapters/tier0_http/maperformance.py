"""
MAPerformance (maperformance.com) crawler adapter.

Product URLs: https://www.maperformance.com/products/<handle>
Shopify storefront, but JSON-LD is emitted as ``ProductGroup`` (with a
``hasVariant`` array of Products) instead of a plain ``Product``. The shared
``extract_json_ld_product`` only matches ``@type == "Product"``, so we look up
ProductGroup directly here and read the first variant for sku/price/image.

Discovery: sitemap.xml is a sitemap index pointing at ``sitemap_products_N.xml``
child urlsets. Override with CRAWLER_MAPERFORMANCE_START_URLS (comma-separated)
to use a fixed list.

Brand: MAP carries many third-party brands (Perrin Performance, COBB, Cusco,
Mishimoto, …). JSON-LD brand.name is reliable; we pass it through unchanged
so each manufacturer keeps its identity in the catalog.

Part numbers: MAP emits ``sku`` / ``mpn`` as their internal supplier code —
a 2–4-letter uppercase prefix (the brand they buy from), a space, then the
manufacturer's real SKU (``"WHI W53382"``, ``"WIS 6501M775"``,
``"PER PSP-ENG-630"``). The leading prefix is meaningless to anyone looking
the part up at another retailer or on the manufacturer's own site, so it is
stripped here. The stored ``part_number`` matches what every other adapter
records — and what the part shows up as on the manufacturer's product page.
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast
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

MAPERFORMANCE_BASE = "https://www.maperformance.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# MAP's storefront emits ``sku`` / ``mpn`` as their internal code:
# a 2–4-letter uppercase supplier prefix, a space, then the manufacturer's
# real part number (e.g. ``"WHI W53382"``, ``"WIS 6501M775"``, ``"PER PSP-ENG-630"``).
# The prefix encodes the brand MAP buys from (WHI=Whiteline, WIS=Wiseco,
# PER=Perrin, …) and is meaningless to users searching for a manufacturer SKU
# in another retailer's catalog. Strip it so the stored ``part_number`` is the
# manufacturer's actual code, which matches what every other adapter records
# and what shows up on the manufacturer's own product pages.
_MAP_SUPPLIER_PREFIX_RE = re.compile(r"^[A-Z]{2,4} (?=\S*\d)")


def _strip_map_supplier_prefix(value: Optional[str]) -> Optional[str]:
    """
    Drop MAP's leading supplier-code prefix from a SKU string. Returns the
    input unchanged when there is no prefix or the tail does not look like a
    real part number (must contain at least one digit, otherwise the prefix
    is probably the actual SKU).
    """
    if not value:
        return value
    stripped = _MAP_SUPPLIER_PREFIX_RE.sub("", value)
    return stripped if stripped else value

DEFAULT_START_URLS = [
    "https://www.maperformance.com/products/perrin-turbo-sump-restrictor-2018-2023-subaru-wrx-psp-eng-630",
]

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg). Stripped from image
# candidates so we keep full-resolution gallery images, not picker thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (logos, mega-menu, banners) rather
# than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_MAPERFORMANCE_START_URLS is set, use it; else discover via sitemap."""
    raw = os.environ.get("CRAWLER_MAPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk sitemap.xml (a sitemap index on Shopify) → child ``sitemap_products_N.xml``
    urlsets and collect every ``/products/<handle>`` URL. Returns deduplicated list
    (by canonical path, query stripped); empty on failure.
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
        index_url = MAPERFORMANCE_BASE + "/sitemap.xml"
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
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Find the first ``ProductGroup`` JSON-LD block. MAP's Shopify SEO app emits
    ProductGroup at the page level with a ``hasVariant: [Product, ...]`` array;
    most other adapters only see plain ``Product`` so the shared extractor skips it.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            items = cast(List[Dict[str, Any]], data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = cast(List[Dict[str, Any]], data["@graph"])
            else:
                items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "ProductGroup" or (isinstance(t, list) and "ProductGroup" in t):
                return item
    return None


def _first_variant(group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the first Product entry from a ProductGroup's hasVariant array."""
    variants = group.get("hasVariant")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if isinstance(v, dict):
            return v
    return None


def _offer_price_cents(variant: Dict[str, Any]) -> Optional[int]:
    """Pull the first usable price from a variant's ``offers`` (list or dict)."""
    offers = variant.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else None
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = None
    if not isinstance(offer, dict):
        return None
    for key in ("price", "lowPrice"):
        raw = offer.get(key)
        if raw is None:
            continue
        try:
            num = float(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if num > 0:
            return int(round(num * 100))
    return None


def _images_from_variant(variant: Dict[str, Any]) -> List[str]:
    img = variant.get("image")
    if not img:
        return []
    raw_list = [img] if isinstance(img, str) else (img if isinstance(img, list) else [])
    out: List[str] = []
    for entry in raw_list:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
        elif isinstance(entry, dict) and entry.get("url"):
            out.append(str(entry["url"]).strip())
    return out


def _payload_from_product_group(group: Dict[str, Any], product_url: str) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a ProductGroup JSON-LD block. Reads brand /
    description / name from the group root and price / sku / mpn / gtin / image
    from the first variant. Returns None if the group has no name.
    """
    name_val = group.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None

    brand_val = group.get("brand")
    brand: Optional[str] = None
    if isinstance(brand_val, str) and brand_val.strip():
        brand = brand_val.strip()
    elif isinstance(brand_val, dict):
        bn = brand_val.get("name")
        if isinstance(bn, str) and bn.strip():
            brand = bn.strip()

    description: Optional[str] = None
    desc_val = group.get("description")
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    variant = _first_variant(group) or {}
    sku_val = variant.get("sku") or variant.get("mpn") or group.get("productID")
    if isinstance(sku_val, str):
        sku_val = _strip_map_supplier_prefix(sku_val)
    part_number = normalize_part_number(sku_val) if isinstance(sku_val, str) else None
    price_cents = _offer_price_cents(variant) if variant else None

    gtin_val = variant.get("gtin") or variant.get("gtin13") or variant.get("gtin12")
    gtin = gtin_val.strip() if isinstance(gtin_val, str) and gtin_val.strip() else None

    images = _images_from_variant(variant) if variant else []
    if not images:
        group_imgs = group.get("image")
        if isinstance(group_imgs, str) and group_imgs.strip():
            images = [group_imgs.strip()]
        elif isinstance(group_imgs, list):
            images = [str(i).strip() for i in group_imgs if isinstance(i, str) and i.strip()]

    return ScrapedPayload(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=price_cents,
        part_manufacturer=brand,
        part_number=part_number,
        image_urls=images[:12] if images else None,
        gtin=gtin,
    )


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against MAP."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return MAPERFORMANCE_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify product CDN images; reject site chrome and tiny thumbnails."""
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


def _canonical_image_key(url: str) -> str:
    """Drop Shopify v/width/height/crop params so width variants of the same asset collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """Collect product gallery image URLs from the DOM (Shopify CDN only), deduped, capped at 12."""
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src", "data-original"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break
    return ordered[:12]


class MAPerformanceAdapter(RetailerCrawlerAdapter):
    """
    MAPerformance adapter. Discovery: sitemap_products_N.xml children of
    sitemap.xml. Parsing: ProductGroup JSON-LD first (variant 0 carries
    sku/price/image), then plain Product JSON-LD, then DOM/og fallback.
    """

    ADAPTER_NAME: ClassVar[str] = "maperformance"
    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from sitemap.xml. Set
        CRAWLER_MAPERFORMANCE_START_URLS (comma-separated) to override.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a MAPerformance product page. Tries ProductGroup JSON-LD first
        (the schema MAP actually emits), then plain Product JSON-LD, then a
        DOM/og fallback. Returns None when no name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. ProductGroup JSON-LD (the path that fires on real MAP product pages).
        group = _extract_product_group_from_json_ld(html)
        if group:
            payload = _payload_from_product_group(group, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=payload.part_manufacturer,
                    part_number=payload.part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. Plain Product JSON-LD (rare on MAP, but cheap to try).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                stripped_pn = _strip_map_supplier_prefix(payload.part_number) if payload.part_number else None
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=payload.part_manufacturer,
                    part_number=normalize_part_number(stripped_pn) if stripped_pn else None,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 3. DOM / og fallback.
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

        price_cents = extract_dom_price(soup)
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))
        part_number = _strip_map_supplier_prefix(part_number)

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
