"""
Flyin' Miata (flyinmiata.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://flyinmiata.com/products/<handle>``

Flyin' Miata is the primary catalog for the Mazda MX-5 Miata (NA/NB/NC/ND)
and LS V8 swap hardware. The RETAILER_BACKLOG entry guessed "custom
platform / older cart", but the live site is a standard Shopify storefront
— same shape as GMG Racing / AWE / ADRO, served from Shopify's CDN with
Cloudflare passive in front. Plain ``requests`` + crawler UA returns HTTP
200 on robots.txt, sitemap, and product pages.

Product pages expose three usable data sources:

- ``<script type="application/ld+json">`` with a full ``Product`` block
  (name, sku, brand.name, description, image, offers.price). Authoritative
  when present and parseable.
- Inline ``var meta = {"product":{...}};`` analytics blob carrying
  ``vendor``, ``handle``, and every variant's ``price`` (in Shopify cents-
  int), ``sku``, and ``name`` (which equals the product title on the
  single-variant products that dominate the catalog).
- Open Graph product meta. ``og:image`` / ``og:image:secure_url`` are
  reliable. ``og:title`` and ``og:description`` on this theme are the SEO
  meta fields (tagline, not product name) — **not** usable as a name
  fallback, so we skip them and fall through to the ``var meta`` variant
  name and then ``<h1>``.

Parsing strategy: JSON-LD Product is the primary source. A subset of
products have a malformed ``gtin13`` offer field (e.g. ``"gtin13":
NAY139040   Q,`` — a raw unquoted token that breaks ``json.loads``); we
pre-sanitize HTML with ``_BROKEN_GTIN_RE`` to strip those pairs before
JSON parsing. When JSON-LD is still unusable we fall back to the ``var
meta`` blob for vendor / SKU / min-variant price and ``variants[0].name``
for the product name, and to og: meta for images.

Brand policy: Flyin' Miata is both a direct manufacturer (their own
turbo kits, V8 swap hardware, cooling parts) and a reseller of third-
party Miata lines (Mazda North American Operation, IL Motorsports, Racing
Beat, Koni, Tein, Hard Dog roll bars, …). JSON-LD ``brand.name`` and
``var meta`` ``vendor`` are populated per-SKU and carry the real
manufacturer across the catalog, so no static default is used. When both
are missing we fall through to the shared title/description heuristics.

Discovery: ``/sitemap.xml`` → child ``sitemap_products_N.xml`` urlsets
(standard Shopify shape; Flyin' Miata's index also includes an ``en-ca``
locale mirror that we filter out so we don't double-crawl). Override with
``CRAWLER_FLYINMIATA_START_URLS`` (comma-separated) for ad-hoc runs.
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
    extract_json_ld_product,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

FLYINMIATA_BASE = "https://flyinmiata.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://flyinmiata.com/products/mazda-competition-motor-mount",
]

# Shopify emits ``var meta = {"product":{...},"page":{...}};`` in an inline
# <script> for analytics. Anchor on the ``var meta =`` keyword so a stray
# ``meta`` substring elsewhere on the page (there are many) can't match.
_META_VAR_RE = re.compile(r"\bvar\s+meta\s*=\s*(\{.*?\})\s*;", re.DOTALL)

# A subset of Flyin' Miata product pages emit a malformed JSON-LD ``Product``
# block with an unquoted ``gtin13`` offer value (e.g.
# ``"gtin13": NAY139040   Q,``) — a raw token that breaks ``json.loads``.
# Stripping the whole key-value pair produces valid JSON and we don't use
# gtin anyway. The value shape is restricted to "starts with a letter,
# ends at the next ``,`` or ``}``", so legitimate ``"gtin13": "12345"``
# / ``"gtin13": 12345`` values are preserved.
_BROKEN_GTIN_RE = re.compile(r'"gtin\d*"\s*:\s*[A-Za-z][^,}\n]*,')

# Shopify image URL sizing suffixes — the theme serves gallery thumbnails
# as ``..._grande.jpg`` / ``..._large.jpg`` while the sitemap emits the
# unsuffixed canonical URL. Stripping both suffix forms lets the two
# representations dedupe to a single gallery entry.
_SHOPIFY_NAMED_SIZE_RE = re.compile(
    r"_(pico|icon|thumb|small|compact|medium|large|grande|master)(?=\.\w{2,5}(?:$|\?))",
    re.IGNORECASE,
)
_SHOPIFY_DIMENSION_SUFFIX_RE = re.compile(r"_\d{2,4}x\d{0,4}(?=\.\w{2,5}(?:$|\?))", re.IGNORECASE)

# Image paths that are site chrome (nav banners, logos, placeholders), not
# product media. Same shape as the GMG / ADRO / AWE filters.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|FM_icon_stack",
    re.IGNORECASE,
)


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on the flyinmiata host with ``/products/`` in the path."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "flyinmiata.com" or host.endswith(".flyinmiata.com")):
        return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


def _is_en_ca_locale_url(url: str) -> bool:
    """True if ``url`` is on Flyin' Miata's ``/en-ca/...`` locale mirror.

    The Shopify sitemap index lists the canonical US storefront and an
    ``/en-ca`` mirror that renders the same catalog in Canadian currency.
    Crawling both would produce duplicate products with different prices;
    we keep only the canonical locale.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    path = parsed.path or ""
    return path.startswith("/en-ca/") or path == "/en-ca"


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_FLYINMIATA_START_URLS", "").strip()
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
    collect every ``/products/...`` URL on the canonical locale. Returns
    deduplicated list (by path, query stripped); empty on failure. The
    ``/en-ca/`` locale mirror is filtered out so we don't double-crawl.
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
            if _is_en_ca_locale_url(u):
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = FLYINMIATA_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if "sitemap_products_" not in child_url:
                    continue
                if _is_en_ca_locale_url(child_url):
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


def _sanitize_json_ld(html: str) -> str:
    """
    Strip malformed ``"gtin*": <unquoted-token>,`` pairs from the HTML so
    ``extract_json_ld_product`` (which calls ``json.loads`` on each script
    block) can parse pages that were otherwise emitting broken offers.
    Cheap no-op on pages without the wart.
    """
    if '"gtin' not in html:
        return html
    return _BROKEN_GTIN_RE.sub("", html)


def _extract_meta_var_product(html: str) -> Optional[dict]:
    """
    Pull the ``product`` object from the inline ``var meta = {...};``
    analytics blob. Returns ``None`` when the blob is missing or JSON
    parsing fails.
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
    Shopify emits this as an integer cents value. Returns ``None`` when
    no variant has a positive integer price (draft / "Call for quote").
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
    """First variant's ``sku`` — the canonical part number for single-variant products."""
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


def _first_variant_name(product: dict) -> Optional[str]:
    """
    First variant's ``name`` — on single-variant products this equals the
    product title. On multi-variant products it typically reads as
    ``"<product title> - <option>"`` which is still usable as a name fallback.
    """
    variants = product.get("variants")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if not isinstance(v, dict):
            continue
        name = v.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _strip_shopify_image_sizing(url: str) -> str:
    """Drop Shopify named-size and WxH suffixes so CDN variants of one image collapse."""
    stripped = _SHOPIFY_NAMED_SIZE_RE.sub("", url)
    stripped = _SHOPIFY_DIMENSION_SUFFIX_RE.sub("", stripped)
    return stripped


def _is_valid_shopify_product_image(url: str) -> bool:
    """Only Shopify CDN product media; reject site chrome and data URIs."""
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
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against the host."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return FLYINMIATA_BASE + u
    return u


def _canonical_image_key(url: str) -> str:
    """Dedupe key: drop Shopify ``v=`` and ``width=`` query params so variants collapse."""
    stripped = re.sub(r"[?&](?:v|width|height)=\w+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_images(soup: BeautifulSoup, extra: Optional[List[str]] = None) -> List[str]:
    """
    Product gallery images from og:image* meta tags plus any URLs passed in
    from JSON-LD ``image``. All candidates pass through the Shopify-CDN
    allowlist + noise filter, get their size suffix stripped, and are
    deduped by canonical URL. Capped at 12.
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

    for raw in extra or []:
        add(raw)

    for meta in soup.find_all("meta", property=("og:image", "og:image:secure_url")):
        if not isinstance(meta, Tag):
            continue
        content = meta_content(meta)
        if content and content.strip():
            add(content.strip())

    return ordered[:12]


def _extract_name_fallback(html: str, soup: BeautifulSoup) -> Optional[str]:
    """
    Recover a product name when JSON-LD is missing / unparseable. The
    Shopify theme on Flyin' Miata puts the SEO tagline in ``og:title``
    rather than the product name, so ``og:title`` is intentionally skipped
    — we fall through to the ``var meta`` variant name and then to ``<h1>``.
    """
    product = _extract_meta_var_product(html)
    if product is not None:
        variant_name = _first_variant_name(product)
        if variant_name:
            return variant_name

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_og_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """``og:price:amount`` fallback. Commas are handled by ``parse_price_cents``."""
    for prop in ("product:price:amount", "og:price:amount"):
        tag = soup.find("meta", property=prop)
        if not isinstance(tag, Tag):
            continue
        v = meta_content(tag)
        if v:
            cents = parse_price_cents(v)
            if cents is not None:
                return cents
    return None


class FlyinMiataAdapter(RetailerCrawlerAdapter):
    """
    Flyin' Miata adapter. Shopify storefront, plain HTTP fetch is sufficient.

    Discovery: ``CRAWLER_FLYINMIATA_START_URLS`` env var wins. Otherwise
    walks ``/sitemap.xml`` and every ``sitemap_products_N.xml`` child
    urlset on the canonical locale (``/en-ca/`` mirror filtered out) and
    collects each ``/products/...`` URL. Falls back to
    ``DEFAULT_START_URLS`` if discovery returns nothing.

    Parsing: JSON-LD Product is authoritative for name, description, SKU,
    brand, and price. A broken-``gtin13`` wart in some offers is
    pre-sanitized so ``json.loads`` succeeds. When JSON-LD is still
    unusable the adapter falls back to the inline ``var meta`` blob for
    vendor / SKU / min-variant price / variant name, and to og: meta for
    images and price. ``og:title`` / ``og:description`` on this theme are
    SEO meta (tagline, not product copy) and are intentionally not used
    as name / description sources.
    """

    ADAPTER_NAME: ClassVar[str] = "flyinmiata"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins when set."""
        for url in _resolve_start_urls():
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Flyin' Miata product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL isn't product-shaped or when no source yields
        a usable name (soft-404 / draft / empty handle).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        meta_product = _extract_meta_var_product(html)

        sanitized_html = _sanitize_json_ld(html)
        item = extract_json_ld_product(sanitized_html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents
                if price_cents is None and meta_product is not None:
                    price_cents = _variant_min_price_cents(meta_product)
                if price_cents is None:
                    price_cents = _extract_og_price_cents(soup)

                part_manufacturer = (payload.part_manufacturer or "").strip() or None
                if not part_manufacturer and meta_product is not None:
                    vendor = meta_product.get("vendor")
                    if isinstance(vendor, str) and vendor.strip():
                        part_manufacturer = vendor.strip()
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_from_title(payload.name)
                if not part_manufacturer and payload.description:
                    part_manufacturer = part_manufacturer_from_description(
                        payload.description, product_name=payload.name
                    )
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_fallback_from_title(payload.name)

                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                if not part_number and meta_product is not None:
                    part_number = normalize_part_number(_first_variant_sku(meta_product))

                image_urls = _extract_images(soup, extra=payload.image_urls or [])

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls or payload.image_urls,
                    gtin=payload.gtin,
                )

        # JSON-LD missing or still unparseable after sanitization — fall
        # back to the ``var meta`` blob + og: meta. Name comes from the
        # variant blob (or <h1>), price / SKU / vendor from the blob,
        # images from og: tags.
        name = _extract_name_fallback(html, soup)
        if not name or len(name) < 3:
            return None

        vendor_raw: Optional[str] = None
        price_cents: Optional[int] = None
        part_number: Optional[str] = None
        if meta_product is not None:
            price_cents = _variant_min_price_cents(meta_product)
            part_number = normalize_part_number(_first_variant_sku(meta_product))
            vendor = meta_product.get("vendor")
            if isinstance(vendor, str) and vendor.strip():
                vendor_raw = vendor.strip()

        if price_cents is None:
            price_cents = _extract_og_price_cents(soup)

        part_manufacturer = (
            vendor_raw or part_manufacturer_from_title(name) or part_manufacturer_fallback_from_title(name)
        )

        description: Optional[str] = None
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if isinstance(meta_desc, Tag):
            v = meta_content(meta_desc)
            if v and v.strip():
                description = normalize_description_text(v, max_len=2000)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=_extract_images(soup) or None,
        )
