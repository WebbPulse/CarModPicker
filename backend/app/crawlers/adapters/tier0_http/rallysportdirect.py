"""
RallySport Direct (rallysportdirect.com) crawler adapter.

The RETAILER_BACKLOG v2 entry listed RSD as BigCommerce Stencil "historically",
but the live storefront is now Shopify (``Powered-By: Shopify`` response header,
``shopify-complexity-score``, ``/cdn/shop/`` image CDN, ``/products/<handle>``
URL shape). Same crawler shape as IE / MAP — plain Product JSON-LD on every
product page, Shopify-standard ``/sitemap.xml`` sitemap index.

Product URLs: ``https://www.rallysportdirect.com/products/<handle>``. Bare-host
requests 301 to the ``www`` subdomain, so the sitemap / DEFAULT_START_URLS use
the canonical host directly.

Fetcher tier: ``http`` — plain ``requests`` with a Chrome UA returns HTTP 200
on the sitemap and product pages. Cloudflare fronts the origin but does not
challenge non-browser clients. Promote to ``tls`` if ``cf-mitigated: challenge``
ever appears in logs.

Parsing: single-variant products ship a plain ``@type=Product`` JSON-LD block;
multi-variant products ship a ``@type=ProductGroup`` block with the variants
nested under ``hasVariant`` (each one a ``Product``). We handle both shapes:
for ProductGroup we collapse the first variant's offers/gtin/image into the
parent so downstream code sees a single Product-shaped dict. Fields pulled:
name, sku, brand.name, description, gtin, image (single hero), offers.price /
priceCurrency. DOM gallery (``.product__media-list``) expands past the
JSON-LD hero; og:image is a last-ditch hero source.

Brand policy: RSD is a Subaru-focused reseller (ACL, Cobb, Perrin, GrimmSpeed,
Whiteline, Cusco, …). JSON-LD ``brand.name`` is populated per-SKU with the
actual manufacturer, so we trust it directly — no retailer house brand. Title /
description heuristics cover the rare page that omits the brand field.
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast
from urllib.parse import urlencode, urlparse, urlunparse
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
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

RSD_BASE = "https://www.rallysportdirect.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.rallysportdirect.com/products/acl-5m8309h-50-acl-race-main-bearing-set-50-oversized-position-5",
]

# Shopify CDN path marker — gallery / noise filters key off this.
_SHOPIFY_CDN_MARKER = "/cdn/shop/"

# Shared-theme chrome (logos, sprites, payment icons) that can slip into a
# loose <img> sweep if the gallery scope isn't respected.
_NON_PRODUCT_MEDIA_RE = re.compile(
    r"/logo[/_-]|favicon|sprite|mega_?menu|placeholder|payment[_-]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then default."""
    raw = os.environ.get("CRAWLER_RALLYSPORTDIRECT_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` urlset."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return "sitemap_products" in path


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (Shopify sitemap index) → each
    ``sitemap_products_N.xml`` urlset and collect every ``/products/`` URL.
    Skips pages/collections/blogs children. Returns deduplicated list (keyed
    by path, query stripped); empty on failure.
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
        index_text = fetch_page(RSD_BASE + "/sitemap.xml", timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if not _is_product_child_sitemap(child_url):
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


def _canonical_image_url(src: str) -> Optional[str]:
    """
    Return https://host/path (preserving ``?v=`` cache-buster, dropping
    ``?width=N`` responsive-srcset params) or None when the URL should be
    skipped. Restricted to the Shopify CDN path so site-chrome images can't
    sneak in.
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = RSD_BASE + s
    if not s.startswith("http"):
        return None
    if _SHOPIFY_CDN_MARKER not in s and "cdn.shopify.com" not in s:
        return None
    parsed = urlparse(s)
    keep_params: list[tuple[str, str]] = []
    if parsed.query:
        for pair in parsed.query.split("&"):
            if not pair:
                continue
            key, _, value = pair.partition("=")
            if key.lower() in {"width", "height", "crop", "padding_color"}:
                continue
            keep_params.append((key, value))
    canonical = urlunparse(("https", parsed.netloc, parsed.path, "", urlencode(keep_params), ""))
    if _NON_PRODUCT_MEDIA_RE.search(canonical):
        return None
    return canonical


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs.

    og:image first (hero), then the Shopify ``.product__media-list`` slideshow
    — the tight scope for RSD's Dawn-lineage theme. Falls back to
    ``.product__media`` / ``.product-gallery`` when the list container isn't
    present (older theme variants). Dedupes by canonical form so width variants
    of the same file collapse.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(src: Optional[str]) -> None:
        if not src or len(ordered) >= 12:
            return
        canonical = _canonical_image_url(src)
        if not canonical or canonical in seen:
            return
        seen.add(canonical)
        ordered.append(canonical)

    og = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og, Tag):
        content = meta_content(og)
        if content:
            add(content.strip())

    scope: Optional[Tag] = None
    for selector in (".product__media-list", ".product__media", ".product-gallery"):
        found = soup.select_one(selector)
        if isinstance(found, Tag):
            scope = found
            break

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            for attr in ("src", "data-src"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break

    return ordered[:12]


def _flatten_product_group(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collapse a ``ProductGroup`` into a single Product-shaped dict by merging
    its first ``hasVariant`` entry's offers / gtin / image / sku onto the
    group. Multi-variant products emit the group; the group carries the
    shared name + description + brand, and each variant carries its own
    price / sku / gtin / image. We use the first variant as the canonical
    row — RSD's grid view and listing price key off the same variant.
    Single-variant products already arrive as plain ``Product``; this is a
    no-op for them.
    """
    t = item.get("@type")
    is_group = t == "ProductGroup" or (isinstance(t, list) and "ProductGroup" in t)
    if not is_group:
        return item
    variants = item.get("hasVariant")
    if not isinstance(variants, list) or not variants:
        return item
    first: Any = None
    for v in variants:
        if isinstance(v, dict):
            first = v
            break
    if not isinstance(first, dict):
        return item
    merged = dict(item)
    merged["@type"] = "Product"
    # Variant fields win where the group doesn't already have them.
    for key in ("offers", "gtin", "gtin13", "gtin12", "gtin8", "gtin14", "sku", "mpn", "image"):
        if key not in merged and key in first:
            merged[key] = first[key]
    return merged


def _extract_product_or_group(html: str, url: str) -> Optional[Dict[str, Any]]:
    """
    Find the JSON-LD Product or ProductGroup that represents this page.

    ``extract_json_ld_product`` only knows about ``@type=Product``; RSD's
    Dawn-lineage theme emits ``ProductGroup`` for multi-variant items with
    variants nested under ``hasVariant``. We walk the page's JSON-LD scripts
    ourselves, collapse any ProductGroup into a Product-shaped dict, and fall
    back to the shared helper for single-variant pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        candidates: List[Any]
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            graph = data.get("@graph")
            candidates = graph if isinstance(graph, list) else [data]
        else:
            continue
        for item in candidates:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "ProductGroup" or (isinstance(t, list) and "ProductGroup" in t):
                return _flatten_product_group(item)
    return extract_json_ld_product(html, product_url=url)


def _gtin_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """
    Pull a GTIN from the JSON-LD Product. RSD emits ``gtin`` at the product
    level; some variant-heavy stores use the ``gtin13`` / ``gtin12`` keys, so
    we check both shapes. The shared ``scraped_payload_from_json_ld`` helper
    doesn't extract gtin, so this is adapter-local.
    """
    for key in ("gtin", "gtin13", "gtin12", "gtin8", "gtin14"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else None
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = None
    if isinstance(offer, dict):
        for key in ("gtin", "gtin13", "gtin12", "gtin8", "gtin14"):
            raw = cast(Optional[Any], offer.get(key))
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


class RallysportDirectAdapter(RetailerCrawlerAdapter):
    """
    RallySport Direct adapter. Discovery via ``/sitemap.xml`` →
    ``sitemap_products_N.xml``. Parsing uses JSON-LD Product for
    name/sku/price/brand/description/gtin; the DOM gallery expands past the
    single hero image JSON-LD ships.
    """

    ADAPTER_NAME: ClassVar[str] = "rallysportdirect"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an RSD product page into a ``ScrapedPayload``. Returns ``None``
        when no Product / ProductGroup JSON-LD is present — RSD emits one on
        every real product page, so a missing block means the URL is a
        soft-404 or non-product.
        """
        item = _extract_product_or_group(html, url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_images(soup)

        part_manufacturer = (payload.part_manufacturer or "").strip() or None
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(payload.name)
        if not part_manufacturer and payload.description:
            part_manufacturer = part_manufacturer_from_description(payload.description, product_name=payload.name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(payload.name)

        part_number = normalize_part_number(payload.part_number) if payload.part_number else None
        image_urls = dom_images[:12] if dom_images else payload.image_urls
        gtin = _gtin_from_json_ld(item)

        return ScrapedPayload(
            name=payload.name,
            product_url=payload.product_url,
            description=payload.description,
            price_cents=payload.price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=gtin,
        )
