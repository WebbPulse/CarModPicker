"""
Fortune Auto North America (fortuneauto-na.com) crawler adapter.

Fortune Auto is a first-party coilover manufacturer; their North American
storefront runs on Shopify. Product lines — 500, 510, Gen8 Dreadnought, Muller —
are the mid-premium tier that coilover shoppers cross-shop against KW V2/V3,
so landing this retailer is what makes the coilover-comparison story exist in
the catalog. See ``adapters/RETAILER_BACKLOG.md`` (Priority 3 verticals).

Product URLs: ``https://fortuneauto-na.com/products/<handle>``. Shopify's
default theme emits a full JSON-LD ``Product`` block (name, sku, brand.name,
description, image, offers.price), so parsing reuses
``extract_json_ld_product`` / ``scraped_payload_from_json_ld`` the same way
the AMS / Driveshaft Shop adapters do. ``og:`` meta and the embedded
``ShopifyAnalytics.meta`` JSON blob are fallbacks for the rare page that
ships without JSON-LD (or with an empty offers block).

Fetcher tier: ``http``. The backlog flagged this as Tier-0/1; default Shopify
on a Cloudflare-free origin clears plain ``requests``. If a later probe shows
a client-fingerprint challenge, move this module to ``tier1_tls/`` and set
``FETCHER_TIER = "tls"`` — no other changes required.

Discovery: ``/sitemap.xml`` is a sitemap index; Shopify emits numbered
``sitemap_products_N.xml`` children. We only follow children whose URL
contains ``sitemap_products`` (skipping collection / page / blog sitemaps)
and keep ``/products/<handle>`` entries. Override with
``CRAWLER_FORTUNEAUTO_START_URLS`` (comma-separated) for ad-hoc runs.

Brand policy: the storefront is first-party — every SKU is a Fortune Auto
coilover, damper, or accessory. Shopify's ``brand.name`` typically reads
``"Fortune Auto"`` but some themes substitute the store name or omit it.
We normalize anything that starts with ``"fortune auto"`` (and any
empty / car-make vendor string, because Shopify stores that ship without a
brand field sometimes fall through to the first-word-of-title heuristic,
which picks the chassis code) to ``"Fortune Auto"`` so cross-retailer
dedupe on (manufacturer, part_number) matches consistently.
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
    extract_json_ld_product,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    scraped_payload_from_json_ld,
)

FORTUNEAUTO_BASE = "https://fortuneauto-na.com"
SITEMAP_INDEX_URL = FORTUNEAUTO_BASE + "/sitemap.xml"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# First-party manufacturer storefront — every SKU is a Fortune Auto product.
# Used both as the normalized brand when JSON-LD vendor reads any "fortune
# auto …" variant and as the fallback when JSON-LD brand is missing entirely.
FORTUNEAUTO_BRAND = "Fortune Auto"

# SKU fallback: the embedded ``ShopifyAnalytics.meta`` blob carries
# ``"variants":[{"id":...,"sku":"500-BMW-E46"}]``. Same shape as Function Werk.
_SHOPIFY_META_SKU_RE = re.compile(r'"sku"\s*:\s*"([^"]+)"')

# Shopify sitemap index children are keyed by prefix. Only the product
# children contain ``/products/`` URLs; collections / pages / blogs do not.
_PRODUCTS_SITEMAP_MARKER = "sitemap_products"

DEFAULT_START_URLS = [
    "https://fortuneauto-na.com/products/500-series-coilovers",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` points at a ``/products/<handle>`` page on the Fortune Auto host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "fortuneauto-na.com" or host.endswith(".fortuneauto-na.com")):
        return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap index, then default."""
    raw = os.environ.get("CRAWLER_FORTUNEAUTO_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (Shopify sitemap index) → each
    ``sitemap_products_N.xml`` child urlset and collect every
    ``/products/<handle>`` URL. Returns deduplicated list (by path, query
    stripped); empty on failure.
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
        index_text = fetch_page(SITEMAP_INDEX_URL, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if _PRODUCTS_SITEMAP_MARKER not in child_url:
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
            # Single urlset served directly — uncommon on Shopify but handle it.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _normalize_fortuneauto_brand(raw: Optional[str]) -> str:
    """
    Any vendor string starting with ``"fortune auto"`` (including ``"Fortune
    Auto USA"`` / ``"Fortune Auto Performance"``) collapses to the canonical
    ``"Fortune Auto"``. Empty / missing falls back to the same default — the
    storefront is first-party, so every product belongs to this brand. Non-
    empty values that don't start with ``"fortune auto"`` are passed through
    untouched so a rare co-branded SKU keeps its real vendor.
    """
    cleaned = (raw or "").strip()
    if not cleaned:
        return FORTUNEAUTO_BRAND
    if cleaned.lower().startswith("fortune auto"):
        return FORTUNEAUTO_BRAND
    return cleaned


def _part_number_from_shopify_meta(raw_html: str) -> Optional[str]:
    """Pull the first SKU from the embedded ``ShopifyAnalytics.meta`` JSON."""
    match = _SHOPIFY_META_SKU_RE.search(raw_html)
    if not match:
        return None
    return normalize_part_number(match.group(1))


def _price_cents_from_og(soup: BeautifulSoup) -> Optional[int]:
    """Read ``<meta property="product:price:amount" content="1295.00">``."""
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if not isinstance(meta, Tag):
            continue
        content = meta_content(meta)
        if not content:
            continue
        cents = parse_price_cents(content)
        if cents is not None:
            return cents
    return None


def _name_from_dom_fallback(soup: BeautifulSoup) -> Optional[str]:
    """
    Recover a product name when JSON-LD is missing. ``og:title`` first
    (cleanest on the Shopify default theme), then any bare ``<h1>``.
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            return content.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    return None


def _description_from_og(soup: BeautifulSoup) -> Optional[str]:
    """``og:description`` → ``<meta name="description">`` as a last resort."""
    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        d = meta_content(og_desc)
        if d and d.strip():
            return normalize_description_text(d, max_len=2000)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        d = meta_content(meta_desc)
        if d and d.strip():
            return normalize_description_text(d, max_len=2000)
    return None


class FortuneAutoAdapter(RetailerCrawlerAdapter):
    """
    Fortune Auto North America adapter.

    Discovery: ``/sitemap.xml`` (Shopify sitemap index) →
    ``sitemap_products_N.xml`` children, collecting every ``/products/<handle>``
    URL. ``CRAWLER_FORTUNEAUTO_START_URLS`` env var (comma-separated) overrides
    with a fixed list. Falls back to ``DEFAULT_START_URLS`` when discovery
    returns nothing.

    Parsing: JSON-LD ``Product`` first (name, sku, brand.name, description,
    image, offers.price). ShopifyAnalytics-meta SKU and og: price/title cover
    the rare page where JSON-LD is absent or incomplete. Brand is normalized
    to ``"Fortune Auto"`` because the storefront is first-party.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Fortune Auto product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL isn't product-shaped or when neither JSON-LD nor
        the DOM fallback yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents
                if price_cents is None:
                    price_cents = _price_cents_from_og(soup)

                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                if not part_number:
                    part_number = _part_number_from_shopify_meta(html)

                part_manufacturer = _normalize_fortuneauto_brand(payload.part_manufacturer)

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=payload.image_urls,
                    gtin=payload.gtin,
                )

        # Fallback: no JSON-LD Product. Recover at least a name + price + SKU
        # so an extension capture or archive rescrape still stores something
        # useful and cross-retailer dedupe keeps working.
        name = _name_from_dom_fallback(soup)
        if not name or len(name) < 3:
            return None

        description = _description_from_og(soup)
        price_cents = _price_cents_from_og(soup)
        part_number = _part_number_from_shopify_meta(html)

        og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
        image_urls: Optional[List[str]] = None
        if isinstance(og_img, Tag):
            content = meta_content(og_img)
            if content and content.strip():
                image_urls = [content.strip()]

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=FORTUNEAUTO_BRAND,
            part_number=part_number,
            image_urls=image_urls,
        )
