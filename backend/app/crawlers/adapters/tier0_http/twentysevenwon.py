"""
27WON Performance (store.27won.com) crawler adapter.

The main ``27won.com`` domain is a Squarespace marketing/blog site and does
not expose product pages. The actual storefront lives on the
``store.27won.com`` subdomain, which runs CS-Cart (the ``ty-*`` class
convention plus ``/images/detailed/<id>/<file>`` gallery paths). Plain
``requests`` fetches the sitemap, robots.txt, and product pages without any
challenge.

Discovery: ``/sitemap.xml`` is a sitemap index pointing at
``products_<n>.xml``, ``categories_<n>.xml``, and ``pages_<n>.xml`` child
urlsets. Only the ``products_*.xml`` children matter for catalog ingest;
category and CMS children are filtered out the same way the old Shopify
adapter did. Product URLs are root-slug ``.html`` (e.g.
``/10th-gen-civic-performance-downpipe.html``), sometimes with a
``?variation_id=...`` query string (a different variant SKU of the same
base page). We strip the query string so we ingest one canonical page per
product — the ingest layer dedupes by ``product_url``. Override via
``CRAWLER_27WON_START_URLS`` (comma-separated).

Parsing: JSON-LD ``Product`` is authoritative on CS-Cart and carries
``name``, ``description``, ``sku``, ``image`` (single URL), and
``offers.price`` (an ``AggregateOffer``). There is no ``brand`` field on
the JSON-LD — the catalog is entirely first-party (intakes, intercoolers,
downpipes, exhaust, dress-up for Honda Civic Si / Type R / Integra), so we
default the manufacturer to the canonical ``"27WON Performance"`` rather
than guessing at the first word of the title.

Image gallery: JSON-LD only emits a single ``image``, but the full gallery
lives in the DOM under ``/images/detailed/<product_id>/<file>.<ext>``
(CS-Cart's full-resolution path). The ``<product_id>`` is a per-product
integer that appears in every full-res image on the page. We read the id
out of the JSON-LD image URL and then collect every
``/images/detailed/<same_id>/`` reference — that excludes ``/images/
thumbnails/…`` entries that point at *related* products, which otherwise
leak into the gallery.

Brand (the ``Why`` this retailer matters): 27WON is the second-vendor
comparison against PRL on FK8/FL5 (same pattern as Hondata vs. KTuner).
SKU mix overlaps but isn't identical — PRL leads on intakes / intercoolers
/ charge pipes, 27WON leads on dress-up, intake manifolds, and short
shifters — so both need to be in the index for a complete FK8/FL5 build.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urlparse, urlunparse
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

STORE_BASE = "https://store.27won.com"
STORE_HOST = "store.27won.com"
SITEMAP_URL = f"{STORE_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Only products_*.xml children matter for catalog discovery. categories_*.xml
# and pages_*.xml are category landing / CMS surfaces, not product pages.
_PRODUCTS_SITEMAP_RE = re.compile(r"/products_\d+\.xml(\?|$)", re.IGNORECASE)

# CS-Cart gallery full-res path: ``/images/detailed/<product_id>/<file>.<ext>``
# The ``<product_id>`` is a stable per-product integer. We use it to filter
# *this* product's gallery out of cross-product thumbnail references that also
# appear on the page (``/images/thumbnails/…/detailed/<other_id>/…``).
_DETAILED_IMAGE_RE = re.compile(
    r"/images/detailed/(\d+)/[^\s\"'<>?#]+?\.(?:jpg|jpeg|png|webp|gif)",
    re.IGNORECASE,
)

DEFAULT_START_URLS = [
    "https://store.27won.com/10th-gen-civic-performance-downpipe.html",
]

# Canonical manufacturer name. The catalog is entirely first-party, but the
# vendor spelling may appear as any of ``"27WON"``, ``"27WON Performance"``,
# ``"27 WON"``, or be absent — collapse to one row so the global part-
# manufacturer table doesn't split one brand across multiple entries.
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


def _is_twentysevenwon_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of 27WON's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _TWENTYSEVENWON_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for a 27WON product.

    - Empty / any 27WON self-spelling collapses to ``"27WON Performance"``.
    - Anything else (rare co-branded SKU) is passed through unchanged — the
      global part-manufacturer table is authoritative and an unfamiliar brand
      will get its own row via ``get_or_create_part_manufacturer_by_name``.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_twentysevenwon_brand_variant(brand):
        return _TWENTYSEVENWON_CANONICAL_BRAND
    return brand


def _strip_query(url: str) -> str:
    """Drop query/fragment so ``?variation_id=33425`` variants collapse to the parent page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    return urlunparse(parsed._replace(query="", fragment=""))


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is a root-slug ``.html`` page on ``store.27won.com``.

    Rejects nested paths (``/civic-si-10th-gen/foo.html`` — those are category
    pages' child listings, not products) and the system ``store_closed.html``
    page disallowed by robots.txt.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host != STORE_HOST:
        return False
    path = parsed.path or ""
    if not path.lower().endswith(".html"):
        return False
    trimmed = path.strip("/")
    if "/" in trimmed:
        return False
    if trimmed.lower() == "store_closed.html":
        return False
    return True


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
    ``products_*.xml`` children. Each child urlset's ``<loc>`` entries that
    pass ``_is_product_url`` are collected, deduped by the query-stripped URL.
    Returns an empty list on any failure so the caller falls back to defaults.
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
            raw = loc.text.strip()
            canonical = _strip_query(raw)
            if not _is_product_url(canonical):
                continue
            if canonical in seen:
                continue
            seen.add(canonical)
            product_urls.append(canonical)

    try:
        index_text = fetch_page(SITEMAP_URL, timeout=15)
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
            # Flat urlset — older store sitemaps sometimes dropped the index.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_product_image_id(json_ld_image: Optional[str]) -> Optional[str]:
    """Pull the CS-Cart product id out of a ``/images/detailed/<id>/…`` URL."""
    if not json_ld_image:
        return None
    match = _DETAILED_IMAGE_RE.search(json_ld_image)
    if not match:
        return None
    return match.group(1)


def _extract_gallery_images(html: str, product_image_id: Optional[str]) -> List[str]:
    """
    Collect every ``/images/detailed/<product_image_id>/…`` URL in the page
    and return them as absolute ``https://store.27won.com/...`` URLs, deduped
    and capped at 12.

    When ``product_image_id`` is ``None`` (JSON-LD image was missing or not a
    ``/images/detailed/...`` URL), use the most common id in the page as a
    best-effort inference.
    """
    ids_seen: dict[str, list[str]] = {}
    for m in _DETAILED_IMAGE_RE.finditer(html):
        pid = m.group(1)
        path = m.group(0)
        ids_seen.setdefault(pid, []).append(path)

    if not ids_seen:
        return []

    target_id = product_image_id
    if target_id is None or target_id not in ids_seen:
        # Fall back to the id with the most references (usually the current
        # product; related-product thumbnails appear once each).
        target_id = max(ids_seen, key=lambda k: len(ids_seen[k]))

    seen: set[str] = set()
    ordered: List[str] = []
    for path in ids_seen[target_id]:
        absolute = STORE_BASE + path if path.startswith("/") else path
        if absolute in seen:
            continue
        seen.add(absolute)
        ordered.append(absolute)
        if len(ordered) >= 12:
            break
    return ordered


class TwentySevenWonAdapter(RetailerCrawlerAdapter):
    """
    27WON Performance adapter. Storefront is CS-Cart on
    ``store.27won.com``; plain HTTP fetches work for robots.txt, the sitemap
    index, and product pages.

    Discovery: ``CRAWLER_27WON_START_URLS`` env var wins. Otherwise walks
    ``/sitemap.xml`` (sitemap index) and pulls every root-slug ``.html``
    entry out of the ``products_*.xml`` child urlsets. ``?variation_id=...``
    query strings are stripped so variants collapse to one ingest per base
    product. Falls back to ``DEFAULT_START_URLS`` if discovery comes back
    empty.

    Parsing: JSON-LD Product for name / description / sku / image / price;
    the product image id from the JSON-LD URL drives a DOM sweep for the
    full gallery (``/images/detailed/<id>/…``). Manufacturer is collapsed
    to the single canonical ``"27WON Performance"`` when the JSON-LD brand
    is empty or any self-spelling variant.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a 27WON product page. JSON-LD Product is the authoritative
        source on CS-Cart; the DOM / og fallback covers the rare page without
        JSON-LD. Returns ``None`` when the URL is not product-shaped or when
        neither path yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (CS-Cart emits this on every product page).
        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                json_ld_image = payload.image_urls[0] if payload.image_urls else None
                product_id = _extract_product_image_id(json_ld_image)
                gallery = _extract_gallery_images(html, product_id)
                image_urls = gallery if gallery else payload.image_urls
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

        # 2. DOM / og fallback — no JSON-LD on the page (rare on CS-Cart).
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

        gallery = _extract_gallery_images(html, None)

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=gallery if gallery else None,
        )
