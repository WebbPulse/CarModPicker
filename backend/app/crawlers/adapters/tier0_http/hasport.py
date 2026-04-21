"""
Hasport Performance (hasportperformance.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://hasportperformance.com/products/<slug>/``

Hasport is the Honda swap-mount specialist — EG/EK/DC/EP K-swap, B-swap, and
J-swap engine mounts sold direct, with no cross-retailer listings anywhere.
The marketing domain ``hasport.com`` 301-redirects to ``hasportperformance.com``;
both hosts are routed to this adapter so extension scrapes from either land
here.

Fetcher tier: ``http`` — plain nginx + WordPress/WooCommerce, no Cloudflare
challenge on robots, sitemap, or product pages.

Platform: WordPress + WooCommerce + Yoast SEO. Product pages emit two JSON-LD
blocks:

- ``<script class="yoast-schema-graph">`` — WebPage / BreadcrumbList /
  Organization (no Product), authored by Yoast.
- A second, unclassed ``<script type="application/ld+json">`` — the
  WooCommerce/Yoast Product block with name, description, image, sku,
  offers.price. Authoritative for this adapter.

``extract_json_ld_product`` walks both script tags and picks the first
``@type: Product``, so no special script selection is needed.

Discovery: ``/sitemap.xml`` is a Yoast sitemap index; ``/product-sitemap.xml``
is the child urlset with every ``/products/<slug>/`` URL. Override with
``CRAWLER_HASPORT_START_URLS`` (comma-separated) for ad-hoc runs.

Part number policy: the JSON-LD ``sku`` field is the WooCommerce post ID
(e.g. ``643``, ``614``) — a stable but meaningless identifier that does not
match any user-facing code. The real SKU is the leading uppercase token of
the product name (``FDSTK`` from ``"FDSTK Stock replacement mount kit ..."``,
``EGK`` from ``"EGK K-series Mount Kit ..."``) which also matches the
retailer's URL-slug convention. We extract that token and drop the numeric
JSON-LD sku on the floor. When the title has no uppercase leading token
(descriptive-only products like ``"Urethane Mount Bushings"``) we return
``None`` so the ingest pipeline doesn't store a noise SKU.

Brand policy: the JSON-LD Product has no ``brand`` field on this storefront
— the offer ``seller`` is ``"Hasport Performance"``, which is the vendor,
not a manufacturer field. Every SKU in Hasport's catalog is first-party, so
we stamp a hardcoded ``"Hasport"`` manufacturer unconditionally.

Images: JSON-LD ``image`` is a single URL. The real gallery is in the
WooCommerce ``<div class="woocommerce-product-gallery__image"><a href="...">``
blocks where each ``<a href>`` points to the full-res WordPress upload.
We sweep those in document order and fall back to the JSON-LD image when
the DOM gallery is empty.
"""

import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

HASPORT_BASE = "https://hasportperformance.com"
SITEMAP_INDEX_URL = f"{HASPORT_BASE}/sitemap.xml"
PRODUCT_SITEMAP_URL = f"{HASPORT_BASE}/product-sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

_PRODUCT_PATH_PREFIX = "/products/"

# Hardcoded manufacturer: every Hasport SKU is first-party, JSON-LD emits no
# brand field, and the offer seller is the retail vendor name. See module docstring.
_HASPORT_BRAND = "Hasport"

# Leading uppercase alphanumeric token of a product name — Hasport's real
# SKU. 2–16 chars of [A-Z0-9] with optional internal dashes; rejects
# mixed-case descriptive words like "Urethane". Anchored at string start
# with a trailing word boundary so ``"EGK K-series"`` matches ``EGK``,
# ``"FDSTK Stock ..."`` matches ``FDSTK``, and ``"Urethane Mount ..."``
# does not match.
_LEADING_SKU_TOKEN_RE = re.compile(r"^([A-Z0-9][A-Z0-9\-]{1,15})\b")

DEFAULT_START_URLS = [
    "https://hasportperformance.com/products/fdstk/",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on hasportperformance.com and under ``/products/<slug>``."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (
        host == "hasportperformance.com"
        or host.endswith(".hasportperformance.com")
        or host == "hasport.com"
        or host.endswith(".hasport.com")
    ):
        return False
    path = parsed.path or ""
    if not path.startswith(_PRODUCT_PATH_PREFIX):
        return False
    # Require a non-empty slug segment after ``/products/`` so the shop
    # landing (``/products/``) and malformed doubles don't count.
    trimmed = path[len(_PRODUCT_PATH_PREFIX) :].strip("/")
    if not trimmed or "/" in trimmed:
        return False
    return True


def _canonical_product_url(url: str) -> str:
    """Drop query / fragment and collapse to the canonical host so dedupe works across the hasport.com alias."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = (parsed.hostname or "").lower()
    # The hasport.com marketing domain 301s to hasportperformance.com; fold
    # it onto the canonical host here so an extension capture on the old
    # alias doesn't produce a separate product row.
    if host == "hasport.com" or host.endswith(".hasport.com"):
        host = "hasportperformance.com"
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = path + "/"
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}{path}"


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_HASPORT_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_HASPORT_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → ``/product-sitemap.xml`` and collect every
    ``/products/<slug>/`` URL. Falls through to fetching the product
    sitemap directly when the index can't be parsed, since the child URL
    is stable and known. Returns [] only on total failure.
    """
    child_urls: List[str] = []
    try:
        index_text = fetch_page(SITEMAP_INDEX_URL, timeout=30)
    except Exception:
        index_text = ""

    if index_text:
        try:
            root = ET.fromstring(index_text)
        except ET.ParseError:
            root = None
        if root is not None:
            tag = root.tag
            if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
                for loc in _loc_elements(root):
                    if loc.text and "product-sitemap" in loc.text:
                        child_urls.append(loc.text.strip())

    # The index sometimes can't be parsed (xml-stylesheet PI variants across
    # Yoast versions have caused trouble elsewhere); the product sitemap
    # path is stable, so probe it directly when discovery via the index
    # yields nothing.
    if not child_urls:
        child_urls.append(PRODUCT_SITEMAP_URL)

    seen: set[str] = set()
    product_urls: List[str] = []
    for child_url in child_urls:
        try:
            child_text = fetch_page(child_url, timeout=30)
        except Exception:
            continue
        try:
            child_root = ET.fromstring(child_text)
        except ET.ParseError:
            continue
        for loc in _loc_elements(child_root):
            if not loc.text:
                continue
            url = _canonical_product_url(loc.text.strip())
            if not _is_product_url(url) or url in seen:
                continue
            seen.add(url)
            product_urls.append(url)

    return product_urls


def _extract_leading_sku(name: str) -> Optional[str]:
    """
    Return the leading uppercase alphanumeric token of ``name`` (the SKU
    code) or ``None`` when the title doesn't open with one. See module
    docstring for why the JSON-LD numeric ``sku`` is unusable.
    """
    if not name:
        return None
    match = _LEADING_SKU_TOKEN_RE.match(name.strip())
    if not match:
        return None
    token = match.group(1)
    # Reject trivial leading tokens like single letters promoted to uppercase.
    if len(token) < 2:
        return None
    return normalize_part_number(token)


def _extract_gallery_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect every ``<a href>`` inside a ``.woocommerce-product-gallery__image``
    block. The ``href`` points at the full-res WordPress upload; the inner
    ``<img src>`` is a resized thumbnail we don't want. Returns unique,
    document-ordered URLs capped at 12.
    """
    seen: set[str] = set()
    out: List[str] = []
    for container in soup.select(".woocommerce-product-gallery__image"):
        if not isinstance(container, Tag):
            continue
        anchor = container.find("a", href=True)
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        href = href.strip()
        if not href.startswith("http"):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append(href)
        if len(out) >= 12:
            break
    return out


class HasportAdapter(RetailerCrawlerAdapter):
    """
    Hasport Performance adapter. WordPress/WooCommerce storefront, plain HTTP.

    Discovery: env override wins. Otherwise walk the Yoast sitemap index →
    ``/product-sitemap.xml`` and yield every ``/products/<slug>/`` URL.

    Parsing: JSON-LD ``Product`` is authoritative for name, description, and
    price. The JSON-LD ``sku`` is the WooCommerce post ID and is replaced
    with the leading uppercase token of the product name (the real SKU).
    Manufacturer is hardcoded to ``"Hasport"`` because every SKU is
    first-party and the JSON-LD has no brand field. Images come from the
    ``.woocommerce-product-gallery__image`` anchors (full-res uploads),
    falling back to the single JSON-LD ``image`` when the DOM gallery is
    absent.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; sitemap next; fixed fallback last."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                canonical = _canonical_product_url(url)
                if _is_product_url(canonical):
                    yield canonical
            return

        for url in _discover_via_sitemap() or list(DEFAULT_START_URLS):
            canonical = _canonical_product_url(url)
            if _is_product_url(canonical):
                yield canonical

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Hasport product page. JSON-LD Product is authoritative;
        returns ``None`` when the URL isn't product-shaped or when no
        JSON-LD Product yields a usable name (Yoast-only / non-product page).
        """
        canonical_url = _canonical_product_url(url)
        if not _is_product_url(canonical_url):
            return None

        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, canonical_url)
        if not payload or not payload.name:
            return None

        part_number = _extract_leading_sku(payload.name)

        soup = BeautifulSoup(html, "html.parser")
        gallery = _extract_gallery_images(soup)
        image_urls = gallery or (payload.image_urls or None)

        return ScrapedPayload(
            name=payload.name,
            product_url=canonical_url,
            description=payload.description,
            price_cents=payload.price_cents,
            part_manufacturer=_HASPORT_BRAND,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )
