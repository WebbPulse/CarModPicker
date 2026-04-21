"""
AMS Performance (amsperformance.com) crawler adapter.

Product URLs: https://www.amsperformance.com/product/<slug>/
WooCommerce storefront on WordPress (Rank Math SEO). Every product page renders
a JSON-LD ``@graph`` block that contains a ``Product`` item with name, sku,
brand, category, description, image[], and offers.price — so parsing reuses
the shared ``extract_json_ld_product`` / ``scraped_payload_from_json_ld``
helpers and then applies two AMS-specific cleanups:

- **Name suffix:** every JSON-LD name ends with ``" - AMS Performance"`` (the
  WooCommerce/Rank Math site-name suffix). Stripped so stored names read
  cleanly.
- **SKU trailing dash:** variable-product parent SKUs are emitted as
  ``"ALP.07.11.0001-"`` (no variant chosen). Trailing dashes are trimmed so
  cross-retailer dedupe on the clean MPN still matches.

Brand: JSON-LD ``brand.name`` is authoritative for third-party lines
(Driveshaft Shop, Seibon Carbon, HKS, …). When it's missing, fall back to the
shared title heuristic, then default to ``"AMS Performance"`` — AMS's own
house brands (Alpha Performance, AMS Performance) always lead the title.

Discovery: ``/sitemap_index.xml`` (Rank Math sitemap index) → each
``product-sitemap{N}.xml`` child urlset. Non-product children
(posts, pages, categories, careers, dealers, videos) are skipped. Override
with ``CRAWLER_AMSPERFORMANCE_START_URLS`` (comma-separated) for a fixed list.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
    fetch_page,
)
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_part_number,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

AMS_BASE = "https://www.amsperformance.com"
SITEMAP_INDEX_URL = AMS_BASE + "/sitemap_index.xml"
PRODUCT_PAGE_PATH = "/product/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.amsperformance.com/product/ams-performance-infiniti-q50-q60-80mm-air-intakes/",
]

# Rank Math groups sitemaps by post type. We only want the ``product-sitemap{N}.xml``
# urlsets — skipping ``post-``, ``page-``, ``category-``, ``career-``, ``dealer-``,
# ``build-``, ``instructions-``, and ``video-`` children keeps discovery focused.
_PRODUCT_SITEMAP_RE = re.compile(r"/product-sitemap\d+\.xml$", re.IGNORECASE)

# Name suffix appended by Rank Math's "Document Title" template on every
# product. Trimmed case-insensitively with any surrounding whitespace.
_NAME_SITE_SUFFIX_RE = re.compile(r"\s*-\s*AMS\s+Performance\s*$", re.IGNORECASE)

# Default brand when JSON-LD brand is empty and the title heuristic finds
# nothing (rare — AMS always leads with the manufacturer name).
_AMS_DEFAULT_BRAND = "AMS Performance"


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap index, then default."""
    raw = os.environ.get("CRAWLER_AMSPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a ``product-sitemap{N}.xml`` urlset."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return bool(_PRODUCT_SITEMAP_RE.search(path))


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap_index.xml`` → each ``product-sitemap{N}.xml`` urlset and
    collect every ``/product/...`` URL. Returns deduplicated list (keyed by
    path, query stripped); empty on failure.
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


def _strip_site_suffix(name: str) -> str:
    """Drop the trailing ``" - AMS Performance"`` suffix Rank Math appends."""
    stripped = _NAME_SITE_SUFFIX_RE.sub("", name).strip()
    return stripped or name


def _clean_part_number(raw: Optional[str]) -> Optional[str]:
    """
    Normalize WooCommerce variable-product SKUs. Bare trailing dashes appear
    when the parent SKU is a template with no variant chosen (e.g.
    ``"ALP.07.11.0001-"``); trim them so cross-retailer dedupe on the clean
    MPN still matches. Numeric variant suffixes (``"-1"``, ``"-2"``) are kept
    so distinct variants don't collapse onto a single row.
    """
    cleaned = normalize_part_number(raw)
    if not cleaned:
        return None
    cleaned = re.sub(r"-+$", "", cleaned).strip()
    return cleaned or None


class AMSPerformanceAdapter(RetailerCrawlerAdapter):
    """
    AMS Performance adapter. Discovery via ``/sitemap_index.xml`` →
    ``product-sitemap{N}.xml``. Parsing uses the JSON-LD ``Product`` block
    (inside the Rank Math ``@graph``), with AMS-specific cleanups to the
    name suffix and trailing-dash variant SKUs, and a brand fallback that
    defaults to ``"AMS Performance"`` when no third-party brand is set.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an AMS Performance product page into a ``ScrapedPayload``.
        Returns ``None`` when no JSON-LD Product is present (the page isn't a
        product — typically a soft-404 landing page with the site chrome).
        """
        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        clean_name = _strip_site_suffix(payload.name)

        part_number = _clean_part_number(payload.part_number)

        part_manufacturer = (payload.part_manufacturer or "").strip() or None
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(clean_name)
        if not part_manufacturer:
            part_manufacturer = _AMS_DEFAULT_BRAND

        return ScrapedPayload(
            name=clean_name,
            product_url=payload.product_url,
            description=payload.description,
            price_cents=payload.price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=payload.image_urls,
            gtin=payload.gtin,
        )
