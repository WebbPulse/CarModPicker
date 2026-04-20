"""
27WON Performance (27won.com) crawler adapter.

Product URLs: ``https://www.27won.com/products/<handle>``
Shopify storefront, modern theme — JSON-LD ``Product`` is emitted by default
with name, description, brand, sku (parent variant SKU), offers, and image.
Parsing reuses the shared ``extract_json_ld_product`` /
``scraped_payload_from_json_ld`` helpers and applies one 27WON-specific rule:

- **Manufacturer collapse:** the catalog is entirely first-party — engine bay
  dress-up, intake manifolds, short shifters, chassis bracing for Honda Civic
  Si / Type R (FK7/FK8/FL5) and Accord 2.0T. Shopify vendor / JSON-LD brand
  appears as any of ``"27WON"``, ``"27WON Performance"``, ``"27 WON"``, or
  empty. All of those collapse to a single canonical ``"27WON Performance"``
  so the global part-manufacturer table stays clean. Co-branded SKUs that
  carry a distinct third-party brand pass through unchanged.

Discovery: ``/sitemap.xml`` (sitemap index) → ``sitemap_products_*.xml`` child
urlsets only. Pages / collections / blog children are skipped. Override with
``CRAWLER_27WON_START_URLS`` (comma-separated).

Brand (the ``Why`` this retailer matters): 27WON is the second-vendor
comparison against PRL on FK8/FL5 (same pattern as Hondata vs. KTuner). The
SKU mix overlaps but isn't identical — PRL leads on intakes / intercoolers /
charge pipes, 27WON leads on dress-up, intake manifolds, and short shifters —
so both need to be in the index for a complete FK8/FL5 build price.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urlparse
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
    scraped_payload_from_json_ld,
)

TWENTYSEVENWON_BASE = "https://www.27won.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Only the products urlset matters for catalog discovery. Pages / collections /
# blogs children are skipped — those are CMS surfaces (about, dealer locator,
# tech blog posts), not product pages.
_PRODUCTS_SITEMAP_RE = re.compile(r"/sitemap_products_\d+\.xml(\?|$)", re.IGNORECASE)

DEFAULT_START_URLS = [
    "https://www.27won.com/products/fk8-civic-type-r-intake-manifold",
]

# Canonical manufacturer name. The Shopify vendor / JSON-LD brand field appears
# as any of ``"27WON"``, ``"27WON Performance"``, ``"27 WON"``, or is empty
# depending on when the product was set up — collapse to one row so the global
# part-manufacturer table doesn't split one brand across multiple entries.
_TWENTYSEVENWON_CANONICAL_BRAND = "27WON Performance"
_TWENTYSEVENWON_BRAND_VARIANTS = frozenset(
    {
        "27won",
        "27 won",
        "27-won",
        "27won performance",
        "27 won performance",
        "27-won performance",
        "27won performance inc",
        "27won performance, inc.",
    }
)

# Shopify CDN thumbnail / picker size suffix (file_300x300.jpg, file_64x64.webp)
# — rejected so we keep full-resolution gallery media rather than the picker
# thumbnails the theme renders in the sidebar.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (nav / footer / logos / banners)
# rather than product media. Same shape as the AWE / GReddy filters.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|27won\.svg|header_|footer_|megamenu|placeholder|favicon",
    re.IGNORECASE,
)


def _is_twentysevenwon_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of 27WON's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _TWENTYSEVENWON_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for a 27WON product.

    - Empty / any 27WON self-spelling (``"27WON"``, ``"27WON Performance"``,
      ``"27 WON"``) collapses to the single canonical ``"27WON Performance"``.
    - Anything else (rare co-branded SKU) is passed through unchanged — the
      global part-manufacturer table is authoritative and an unfamiliar brand
      will get its own row via ``get_or_create_part_manufacturer_by_name``.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_twentysevenwon_brand_variant(brand):
        return _TWENTYSEVENWON_CANONICAL_BRAND
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_27WON_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (sitemap index), then walk only the
    ``sitemap_products_*.xml`` children. Each child urlset's ``<loc>`` entries
    that contain ``/products/`` are collected (deduplicated by path). Returns
    an empty list on any failure so the caller can fall back to defaults.

    Pages / collections / blogs children are filtered out because they're CMS
    surfaces (about, dealer locator, tech blog) rather than product pages.
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
        index_url = TWENTYSEVENWON_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [
                loc.text.strip()
                for loc in _loc_elements(root)
                if loc.text and loc.text.strip() and _PRODUCTS_SITEMAP_RE.search(loc.text)
            ]
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


def _canonical_image_key(url: str) -> str:
    """Dedupe key: drop Shopify ``v``/``width``/``height``/``crop`` params so width variants collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=\w+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _is_valid_shopify_product_image(url: str) -> bool:
    """Only Shopify CDN product media; reject site chrome and picker thumbnails."""
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


def _normalize_image_url(url: str) -> str:
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against 27won.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return TWENTYSEVENWON_BASE + u
    return u


def _extract_twentysevenwon_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images only.

    Sources (in order): ``og:image``, ``<media-gallery>``, ``.product__media-wrapper``.
    Candidates pass through the Shopify-CDN allowlist + noise/thumbnail filter,
    are upgraded to https, and deduped by canonical URL (ignoring ``v``/``width``
    query params). Capped at 12 so we don't inflate DB rows with picker
    thumbnails or related-product images.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_shopify_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        wrapper = soup.select_one(".product__media-wrapper")
        if isinstance(wrapper, Tag):
            scope = wrapper

    if scope is not None:
        for img in scope.find_all("img", src=True):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())

    return ordered[:12]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a 27won.com ``/products/<handle>`` page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "27won.com" and not host.endswith(".27won.com"):
        return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


class TwentySevenWonAdapter(RetailerCrawlerAdapter):
    """
    27WON Performance adapter. Shopify storefront, plain HTTP is sufficient.

    Discovery: ``CRAWLER_27WON_START_URLS`` env var wins. Otherwise walks
    ``/sitemap.xml`` (sitemap index) and pulls every ``/products/...`` URL out
    of the ``sitemap_products_*.xml`` child urlsets only. Falls back to
    ``DEFAULT_START_URLS`` if discovery comes back empty.

    Parsing: JSON-LD Product first (Shopify default — name / brand / sku /
    offers / image), then a DOM / og fallback for the rare page without
    JSON-LD. Manufacturer is collapsed to the single canonical
    ``"27WON Performance"`` when the vendor field is empty or any
    self-spelling variant, so the global part-manufacturer list doesn't split
    one brand across multiple rows.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a 27WON product page. JSON-LD Product is the authoritative
        source on Shopify; the DOM / og fallback covers the rare page without
        JSON-LD. Returns ``None`` when the URL is not product-shaped or when
        neither path yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_twentysevenwon_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Shopify default).
        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                return ScrapedPayload(
                    name=payload.name,
                    product_url=payload.product_url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback — no JSON-LD on the page (rare on Shopify).
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

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if isinstance(sku_elem, Tag):
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # No JSON-LD brand available. 27WON's catalog is entirely first-party
        # (intake manifolds, short shifters, engine bay dress-up), so default
        # directly to the canonical brand rather than running the title-first-
        # word heuristic — the number "27" would fail the manufacturer rules
        # anyway, and product words (e.g. "Billet", "Short") are not brands.
        part_manufacturer = _TWENTYSEVENWON_CANONICAL_BRAND

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
