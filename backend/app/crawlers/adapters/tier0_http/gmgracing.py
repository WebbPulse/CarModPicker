"""
GMG Racing (shop.gmgracing.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://shop.gmgracing.com/products/<handle>``

GMG Racing is a Shopify storefront, but on an older theme that does **not**
emit a JSON-LD ``Product`` block in the static HTML (what AWE / Enjuku /
AMS rely on). In its place the page exposes two usable data sources:

- Open Graph product meta (``og:title`` / ``og:description`` / ``og:image``
  / ``og:price:amount`` / ``og:price:currency``).
- An inline ``var meta = {"product":{...}, "page":{...}};`` analytics blob
  that carries ``vendor``, ``handle``, and every variant's ``price`` (in
  Shopify cents-int) and ``sku``.

Parsing uses the ``var meta`` blob as the authoritative source for vendor,
variant SKU, and price-in-cents, and falls back to og: meta for name,
description, images, and (when the blob is missing) price. When neither
side yields a name, the page is treated as a non-product (soft-404 / empty
handle / drafts) and we return ``None``.

Brand collapse: Shopify's vendor field for GMG's own SKUs appears as either
``"GMG"`` or ``"GMG Racing"`` depending on when the product was set up. Both
collapse to a single canonical ``"GMG Racing"`` so we don't split the brand
across two part-manufacturer rows. Third-party vendor strings
(``"Brembo"``, ``"BBS"``, ``"Recaro"``, …) pass through unchanged — GMG
re-sells some hardware under the real manufacturer and those rows should
land on the canonical brand.

Discovery: ``/sitemap.xml`` → child ``sitemap_products_N.xml`` urlsets
(standard Shopify shape). Override with ``CRAWLER_GMGRACING_START_URLS``
(comma-separated) to use a fixed list.

Fetcher tier: plain HTTP. ``shop.gmgracing.com`` is Shopify-hosted and
serves both robots.txt and product pages to plain ``requests`` with the
crawler User-Agent.
"""

import json
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

GMG_BASE = "https://shop.gmgracing.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://shop.gmgracing.com/products/gmg-wc-991-gt3-exhaust-center-section",
]

# Canonical brand for GMG's own hardware. Shopify vendor appears as either
# "GMG" or "GMG Racing" (and occasionally empty); treat all three as one
# brand so the global part-manufacturer list stays clean.
_GMG_CANONICAL_BRAND = "GMG Racing"
_GMG_BRAND_VARIANTS = frozenset({"gmg", "gmg racing", "gmgracing", "gmg-racing"})

# ``var meta = {...};`` sits in an inline <script> that wires up Shopify's
# analytics. The regex is anchored on the keyword + assignment so a stray
# ``meta`` substring elsewhere on the page can't match.
_META_VAR_RE = re.compile(r"\bvar\s+meta\s*=\s*(\{.*?\})\s*;", re.DOTALL)

# Shopify image URL sizing suffixes (``_grande``, ``_large``, ``_medium``,
# ``_small``). The theme emits og:image tags with ``_grande`` (600px) —
# stripping the suffix yields the canonical full-resolution URL that the
# product sitemap uses, so the same image in the sitemap and the product
# page dedup to one entry.
_SHOPIFY_NAMED_SIZE_RE = re.compile(
    r"_(pico|icon|thumb|small|compact|medium|large|grande|master)(?=\.\w{2,5}(?:$|\?))",
    re.IGNORECASE,
)

# Explicit WxH dimension suffixes (``_300x300.jpg``). Same idea as AWE —
# full-resolution media is always preferred over picker thumbnails so the
# DB doesn't grow with duplicate gallery rows at different sizes.
_SHOPIFY_DIMENSION_SUFFIX_RE = re.compile(r"_\d{2,4}x\d{0,4}(?=\.\w{2,5}(?:$|\?))", re.IGNORECASE)

# Image paths that are site chrome (nav / banners / logos), not product
# media. Same shape as the AWE / ADRO filters.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder",
    re.IGNORECASE,
)


def _is_gmg_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of GMG's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _GMG_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Collapse GMG's self-spellings (``"GMG"`` / ``"GMG Racing"`` / empty) to
    the single canonical ``"GMG Racing"``. Third-party vendor strings —
    Brembo, BBS, Recaro, etc. — pass through unchanged so re-sold hardware
    lands on the real manufacturer in the global part-manufacturer list.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_gmg_brand_variant(brand):
        return _GMG_CANONICAL_BRAND
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_GMGRACING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → each ``sitemap_products_N.xml`` urlset and
    collect every ``/products/...`` URL. Returns deduplicated list (by
    path, query stripped); empty on failure. Mirrors the Shopify discovery
    used by the AWE and ADRO adapters.
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
        index_url = GMG_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if "sitemap_products_" not in child_url:
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


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on a GMG host (shop or myshopify) with ``/products/`` in the path."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host:
        is_gmg_host = host == "gmgracing.com" or host.endswith(".gmgracing.com") or host == "gmgracing.myshopify.com"
        if not is_gmg_host:
            return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


def _extract_meta_var_product(html: str) -> Optional[dict]:
    """
    Pull the ``product`` object from the inline ``var meta = {...};``
    analytics blob. Returns ``None`` when the blob is missing or JSON
    parsing fails — older theme tweaks occasionally break the assignment.
    """
    match = _META_VAR_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except (ValueError, json.JSONDecodeError):
        return None
    product = data.get("product") if isinstance(data, dict) else None
    return product if isinstance(product, dict) else None


def _variant_min_price_cents(product: dict) -> Optional[int]:
    """
    Lowest variant price (in cents) from ``product.variants[].price``.
    Shopify emits this as an integer cents value (e.g. ``229500``).
    Returns ``None`` when no variant has a positive integer price — which
    is rare but happens on draft products and "Call for quote" items.
    """
    variants = product.get("variants")
    if not isinstance(variants, list):
        return None
    prices: List[int] = []
    for v in variants:
        if not isinstance(v, dict):
            continue
        raw = v.get("price")
        if isinstance(raw, int) and raw > 0:
            prices.append(raw)
    return min(prices) if prices else None


def _first_variant_sku(product: dict) -> Optional[str]:
    """
    First variant's ``sku`` from the meta blob. Most GMG products have a
    single variant whose SKU is the canonical part number; multi-variant
    products (exhaust finishes, titanium vs stainless) get the default
    selected variant's SKU, matching what the page price / og:image reflect.
    """
    variants = product.get("variants")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if not isinstance(v, dict):
            continue
        sku = v.get("sku")
        if isinstance(sku, str) and sku.strip():
            return sku.strip()
    return None


def _strip_shopify_image_sizing(url: str) -> str:
    """
    Drop the Shopify named-size suffix (``_grande``, ``_large``, …) and
    WxH dimension suffixes from a CDN URL so the gallery-og-image form
    collapses onto the canonical full-resolution form that the product
    sitemap uses.
    """
    stripped = _SHOPIFY_NAMED_SIZE_RE.sub("", url)
    stripped = _SHOPIFY_DIMENSION_SUFFIX_RE.sub("", stripped)
    return stripped


def _is_valid_shopify_product_image(url: str) -> bool:
    """Only Shopify CDN product media; reject site chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _normalize_image_url(url: str) -> str:
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against the shop host."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return GMG_BASE + u
    return u


def _canonical_image_key(url: str) -> str:
    """Dedupe key: drop Shopify ``v`` query param so cache-bust variants collapse."""
    stripped = re.sub(r"[?&]v=\w+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images. The theme emits one ``og:image`` tag per
    gallery photo (plus a parallel ``og:image:secure_url`` which we merge
    into the same set via canonical dedup). Candidates pass through the
    Shopify-CDN allowlist + noise filter, get their named-size suffix
    stripped, and are deduped by canonical URL so the ``_grande`` form
    and the sitemap's no-suffix form collapse to one entry. Capped at 12.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_shopify_product_image(u):
            return
        u = _strip_shopify_image_sizing(u)
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    for meta in soup.find_all("meta", property=("og:image", "og:image:secure_url")):
        if not isinstance(meta, Tag):
            continue
        content = meta_content(meta)
        if content and content.strip():
            add(content.strip())

    return ordered[:12]


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """og:title first (always present on Shopify product pages), then h1."""
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """og:description (fulltext Shopify blurb) → meta description fallback."""
    for selector in (("meta", {"property": "og:description"}), ("meta", {"name": "description"})):
        tag_name, attrs = selector
        tag = soup.find(tag_name, attrs=attrs)
        if isinstance(tag, Tag):
            v = meta_content(tag)
            if v and v.strip():
                return normalize_description_text(v, max_len=2000)
    return None


def _extract_og_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    Fallback price source when the ``var meta`` blob is absent. The theme
    emits ``og:price:amount`` formatted as ``"2,295.00"`` — commas are
    handled by ``parse_price_cents``.
    """
    tag = soup.find("meta", property="og:price:amount")
    if not isinstance(tag, Tag):
        return None
    v = meta_content(tag)
    if not v:
        return None
    return parse_price_cents(v)


class GMGRacingAdapter(RetailerCrawlerAdapter):
    """
    GMG Racing adapter. Shopify storefront, plain HTTP fetch is sufficient.

    Discovery: ``CRAWLER_GMGRACING_START_URLS`` env var wins. Otherwise walks
    ``/sitemap.xml`` and every ``sitemap_products_N.xml`` child urlset and
    collects each ``/products/...`` URL. Falls back to ``DEFAULT_START_URLS``
    if discovery returns nothing.

    Parsing: the inline ``var meta = {...};`` blob is authoritative for
    vendor, variant SKU, and variant prices (in Shopify cents-int). og:
    meta fills in name, description, and gallery images, and acts as the
    price fallback when the meta blob is missing. Vendor is collapsed to
    the canonical ``"GMG Racing"`` for GMG's own SKUs; third-party vendors
    pass through.
    """

    ADAPTER_NAME: ClassVar[str] = "gmgracing"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a GMG Racing product page. Returns ``None`` when the URL is
        not product-shaped or when og:title and h1 both fail to produce a
        usable name (soft-404 / draft / empty handle).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        product = _extract_meta_var_product(html)
        if product is not None:
            price_cents = _variant_min_price_cents(product)
            part_number = normalize_part_number(_first_variant_sku(product))
            vendor_raw = product.get("vendor") if isinstance(product.get("vendor"), str) else None
        else:
            price_cents = None
            part_number = None
            vendor_raw = None

        if price_cents is None:
            price_cents = _extract_og_price_cents(soup)

        part_manufacturer = _normalize_part_manufacturer(vendor_raw)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=_extract_description(soup),
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=_extract_images(soup) or None,
        )
