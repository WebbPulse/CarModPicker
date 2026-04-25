"""
Subispeed (subispeed.com) crawler adapter.

Product URLs: https://www.subispeed.com/products/<handle>
Shopify storefront emitting plain ``Product`` JSON-LD (not the ``ProductGroup``
shape MAPerformance uses), so ``extract_json_ld_product`` +
``scraped_payload_from_json_ld`` cover the happy path. SKU / brand / price /
description / image all live in the JSON-LD block.

Discovery: ``/sitemap.xml`` is a sitemap index pointing at three
``sitemap_products_N.xml?from=…&to=…`` child urlsets (plus pages / collections /
blogs which we skip). Override with ``CRAWLER_SUBISPEED_START_URLS``
(comma-separated) for a fixed list.

Brand: Subispeed is a multi-brand reseller — Cusco, Perrin, GrimmSpeed,
OpenFlash, COBB, IAG, Subaru OEM, etc. — and Shopify ``brand.name`` is
populated per product from the vendor field. Pass it through unchanged so
each manufacturer keeps its identity in the catalog.

SKUs: Subispeed brands prefix the manufacturer code (e.g. ``CUS660 911 SET``
for a Cusco 660-911-SET mount kit). The internal space is meaningful and
``normalize_part_number`` preserves it; we don't try to split the prefix
because the pattern varies by brand.

Images: JSON-LD ``image`` is a single string on Subispeed (not the array
that ADRO/MAP emit), and points at the storefront proxy
(``www.subispeed.com/cdn/shop/products/…``) rather than bare ``cdn.shopify.com``.
DOM sweep of ``<media-gallery>`` / ``.product__media-wrapper`` is the source
of additional gallery images, deduped against the JSON-LD entry.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
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

SUBISPEED_BASE = "https://www.subispeed.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.subispeed.com/products/cus-660-911-set-cusco-engine-transmission-mount",
]

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg, file_100x100.webp).
# Stripped / rejected so we keep full-resolution gallery images, not the
# thumbnails Shopify renders for the product picker / related products rail.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (logo, mega-menu, banners) rather
# than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap.xml, then default."""
    raw = os.environ.get("CRAWLER_SUBISPEED_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` child sitemap."""
    return "/sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → each ``sitemap_products_N.xml``
    child urlset and collect every ``/products/<handle>`` URL. Skips the
    ``sitemap_pages_*`` / ``sitemap_collections_*`` / ``sitemap_blogs_*``
    siblings since none of those host product pages. Returns deduplicated
    list (by canonical path, query stripped); empty on failure.
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
        index_url = SUBISPEED_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if not _is_products_child_sitemap(child_url):
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


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against Subispeed."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return SUBISPEED_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify product CDN images (storefront proxy or bare cdn.shopify.com); reject chrome and tiny thumbnails."""
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
    """
    Gather product gallery image URLs from the DOM (Shopify CDN only), deduped,
    capped at 12. Looks at ``<media-gallery>`` first and falls back to
    ``.product__media-wrapper`` — the two patterns Shopify themes use for the
    main product image rail.
    """
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

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        wrapper = soup.select_one(".product__media-wrapper")
        if isinstance(wrapper, Tag):
            scope = wrapper

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            for attr in ("src", "data-src", "data-original"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break

    return ordered[:12]


class SubispeedAdapter(RetailerCrawlerAdapter):
    """
    Subispeed adapter. Discovery: sitemap index → ``sitemap_products_N.xml``
    children. Parsing: plain ``Product`` JSON-LD via the shared extractor,
    with og:/DOM fallbacks (price, title, description, SKU) for the rare
    page that doesn't render JSON-LD.
    """

    ADAPTER_NAME: ClassVar[str] = "subispeed"
    category_targets: ClassVar[list[str]] = ["universal"]
    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Subispeed product page. Tries JSON-LD ``Product`` first
        (the path real product pages take), then a DOM/og fallback.
        Returns ``None`` when no name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. Plain Product JSON-LD (the path real product pages take).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                # JSON-LD image is a single string; merge with DOM gallery so
                # we end up with the full carousel rather than just the cover.
                image_urls = list(payload.image_urls or [])
                seen_keys = {_canonical_image_key(u) for u in image_urls}
                for u in dom_images:
                    key = _canonical_image_key(u)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    image_urls.append(u)
                    if len(image_urls) >= 12:
                        break
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=payload.part_manufacturer,
                    part_number=normalize_part_number(payload.part_number) if payload.part_number else None,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
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
