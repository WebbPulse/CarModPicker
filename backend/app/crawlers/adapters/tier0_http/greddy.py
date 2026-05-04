"""
GReddy / Trust (greddy.com) crawler adapter.

Product URLs: ``https://www.greddy.com/products/<handle>``
Shopify storefront on a custom theme. Plain HTTP works (no Cloudflare on
greddy.com today). JSON-LD ``Product`` is emitted by default with name,
description, brand, sku (parent variant SKU), offers, and image — so parsing
reuses the shared ``extract_json_ld_product`` / ``scraped_payload_from_json_ld``
helpers and then applies two GReddy-specific cleanups:

- **Manufacturer collapse:** the catalog is overwhelmingly first-party. Shopify
  vendor / JSON-LD brand appears as any of ``"GReddy"``, ``"Greddy"``,
  ``"GReddy Performance Products"``, ``"GPP"``, or ``"Trust"`` (the JDM parent
  brand sold under the same family). All of these collapse to a single
  canonical ``"GReddy"`` so the global part-manufacturer table doesn't end up
  with several rows that mean the same thing. Co-branded SKUs that carry a
  distinct third-party brand pass through unchanged.
- **Image scope:** the theme uses a custom ``<product-gallery>`` element with
  ``.product-gallery__media`` divs (not Dawn's ``<media-gallery>`` /
  ``.product__media-wrapper``), so the AWE-style scope selector won't find
  anything here. Gallery extraction targets ``<product-gallery>`` directly,
  then the ``og:image`` meta as a final fallback.

Discovery: ``/sitemap.xml`` (sitemap index) → ``sitemap_products_*.xml`` child
urlsets only. Pages, collections, and blog children are skipped. Override with
``CRAWLER_GREDDY_START_URLS`` (comma-separated).
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
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

GREDDY_BASE = "https://www.greddy.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Only the products urlset matters for catalog discovery. Pages / collections /
# blogs children are skipped — they're CMS surfaces, not product pages.
_PRODUCTS_SITEMAP_RE = re.compile(r"/sitemap_products_\d+\.xml(\?|$)", re.IGNORECASE)

DEFAULT_START_URLS = [
    "https://www.greddy.com/products/greddy-supreme-sp-cat-back-honda-ef-crx-civic",
]

# Canonical manufacturer name. The Shopify vendor / JSON-LD brand fields show
# up as any of ``"GReddy"``, ``"Greddy"``, ``"GReddy Performance Products"``,
# ``"GPP"``, or ``"Trust"`` (the Japanese parent brand under the same family) —
# collapsed to a single canonical ``"GReddy"`` so the global part-manufacturer
# table doesn't end up with several rows that mean the same thing.
_GREDDY_CANONICAL_BRAND = "GReddy"
_GREDDY_BRAND_VARIANTS = frozenset(
    {
        "greddy",
        "greddy performance products",
        "greddy performance products, inc.",
        "greddy performance products inc",
        "gpp",
        "trust",
        "trust greddy",
        "greddy / trust",
        "greddy/trust",
        # GReddy's Shopify theme emits ``"brand": "CATALOG"`` on the JSON-LD
        # block of every product (it's the storefront's internal product-feed
        # tag, not a real brand). Collapse it to the canonical name so 870+
        # parts don't end up under a junk "CATALOG" manufacturer row.
        "catalog",
        # Shopify ``vendor`` field on a handful of legacy SKUs reads the
        # storefront slug ``"shopgreddy"`` rather than any of the regular
        # brand spellings — same first-party catalog, fold to canonical.
        "shopgreddy",
    }
)

# GReddy's parent SKU mirrors the part_number into the JSON-LD ``sku`` field
# with a trailing ``" - CTLG"`` (catalog) marker — e.g. ``"16520701 - CTLG"``.
# That suffix is internal feed metadata, not part of the part number, and must
# be stripped before normalization or downstream consumers see noise.
_GREDDY_PN_CATALOG_SUFFIX_RE = re.compile(r"\s*-\s*(?:CTLG|CATALOG)\s*$", re.IGNORECASE)


def _strip_greddy_catalog_suffix(part_number: Optional[str]) -> Optional[str]:
    """Drop GReddy's trailing ``" - CTLG"`` / ``" - CATALOG"`` marker."""
    if not part_number:
        return part_number
    return _GREDDY_PN_CATALOG_SUFFIX_RE.sub("", part_number).strip() or None


# Shopify CDN thumbnail / picker size suffix (file_300x300.jpg, file_64x64.webp)
# — rejected so we keep full-resolution gallery media instead of the 56–192px
# thumbnails the theme renders under the carousel.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (logos, favicons, payment badges,
# theme assets) rather than product media. Same shape as the AWE filter.
_IMAGE_NOISE_RE = re.compile(
    r"/cdn/shop/t/\d+/assets/|/preview_images/|favicon|logo|placeholder|cursor[-_]|checkmark",
    re.IGNORECASE,
)


def _is_greddy_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of GReddy's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _GREDDY_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for a GReddy product.

    - Empty / any GReddy self-spelling (``"GReddy"``, ``"Greddy"``,
      ``"GReddy Performance Products"``, ``"GPP"``, ``"Trust"``) collapses to
      the single canonical ``"GReddy"``.
    - Anything else (rare co-branded SKU) is passed through unchanged — the
      global part-manufacturer table is authoritative and an unfamiliar brand
      will get its own row via ``get_or_create_part_manufacturer_by_name``.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_greddy_brand_variant(brand):
        return _GREDDY_CANONICAL_BRAND
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_GREDDY_START_URLS", "").strip()
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
    surfaces (about, contact, dealer locator, blog posts) rather than product
    pages.
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
        index_url = GREDDY_BASE + "/sitemap.xml"
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
    """
    Shopify CDN product media only.

    GReddy serves images either through the Shopify CDN (``cdn.shopify.com``)
    or proxied through their own domain at ``/cdn/shop/files/``. Both are
    accepted; theme assets (``/cdn/shop/t/<theme>/assets/``) and the YouTube
    video preview thumbnails (``/preview_images/``) are rejected.
    """
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/cdn/shop/files/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    if _SHOPIFY_THUMBNAIL_RE.search(low):
        return False
    return True


def _normalize_image_url(url: str) -> str:
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against greddy.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return GREDDY_BASE + u
    return u


def _extract_greddy_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images only.

    Sources (in order): ``og:image``, the custom ``<product-gallery>`` element.
    Candidates pass through the Shopify-CDN allowlist + noise/thumbnail filter,
    are upgraded to https, and deduped by canonical URL (ignoring ``v``/``width``
    query params). Capped at 12 so we don't inflate DB rows with thumbnail
    variants from the carousel page-dots row.
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

    gallery = soup.find("product-gallery")
    if isinstance(gallery, Tag):
        for media in gallery.select(".product-gallery__media img[src]"):
            if not isinstance(media, Tag):
                continue
            src = media.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())

    return ordered[:12]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a greddy.com ``/products/<handle>`` page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "greddy.com" and not host.endswith(".greddy.com"):
        return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


class GReddyAdapter(RetailerCrawlerAdapter):
    """
    GReddy / Trust adapter. Shopify storefront, plain HTTP fetch is sufficient.

    Discovery: ``CRAWLER_GREDDY_START_URLS`` env var wins. Otherwise walks
    ``/sitemap.xml`` (sitemap index) and pulls every ``/products/...`` URL out
    of the ``sitemap_products_*.xml`` child urlsets only. Falls back to
    ``DEFAULT_START_URLS`` if discovery comes back empty.

    Parsing: JSON-LD Product first (Shopify default — name / brand / sku /
    offers / image), then a DOM / og fallback for the rare page without
    JSON-LD. Manufacturer is collapsed to the single canonical ``"GReddy"``
    when the vendor field is empty or any self-spelling variant
    (``"GReddy Performance Products"``, ``"Trust"``, ``"GPP"``, …), so the
    global part-manufacturer list doesn't split one brand across multiple rows.
    """

    ADAPTER_NAME: ClassVar[str] = "greddy"
    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a GReddy product page. JSON-LD Product is the authoritative
        source on Shopify; the DOM / og fallback covers the rare page without
        JSON-LD. Returns ``None`` when the URL is not product-shaped or when
        neither path yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_greddy_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Shopify default).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = (
                    normalize_part_number(_strip_greddy_catalog_suffix(payload.part_number))
                    if payload.part_number
                    else None
                )
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
        # DOM-side ``" - CTLG"`` suffixes leak through the same way the JSON-LD
        # ones do — the theme prints the SKU as ``"<code> - CTLG"`` in the
        # product meta block too.
        part_number = normalize_part_number(_strip_greddy_catalog_suffix(part_number))

        # No JSON-LD brand available. GReddy's catalog is overwhelmingly their
        # own hardware (intercoolers, intakes, oil coolers, exhausts, turbo
        # kits), so default directly to the canonical brand rather than
        # running the title-first-word heuristic (which would pick up product
        # words like "Supreme" / "Spectrum" / "Profec").
        part_manufacturer = _GREDDY_CANONICAL_BRAND

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
