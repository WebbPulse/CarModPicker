"""
Driveshaft Shop (driveshaftshop.com) crawler adapter.

Product URLs: https://driveshaftshop.com/product/<slug>/
WooCommerce storefront on WordPress (Yoast SEO). Every product page renders
two JSON-LD blocks — Yoast's WebPage/Organization ``@graph`` and a second
``@graph`` that contains the ``Product`` node. The shared
``extract_json_ld_product`` helper walks both and returns the Product,
so parsing mostly reuses ``scraped_payload_from_json_ld`` and applies three
DSS-specific adjustments:

- **Price lives in ``priceSpecification``.** Yoast/WooCommerce on DSS emits
  ``offers[0].priceSpecification[0].price`` instead of ``offers[0].price``,
  which the shared ``_price_from_json_ld`` reader doesn't recurse into. We
  pull it out explicitly when the shared reader returns ``None``.
- **Manufacturer part code is embedded in the description.** JSON-LD ``sku``
  holds the WooCommerce numeric product id (e.g. ``"510520"``, ``"610002"``)
  — not the real manufacturer code. DSS appends ``"PART# <code>"`` as the
  last line of every product description (e.g. ``"PART# BMWSH3-CV"``). We
  prefer that over the numeric sku so cross-retailer dedupe on
  (manufacturer, part_number) works.
- **Brand is always null.** DSS is a single-brand manufacturer shop (axles
  and driveshafts are all their own), so ``part_manufacturer`` defaults to
  ``"Driveshaft Shop"`` rather than falling through to the title heuristic.

Discovery: ``/sitemap_index.xml`` (Yoast index) → ``product-sitemap.xml``
(plus any numbered ``product-sitemap{N}.xml`` children Yoast generates when
the catalog outgrows a single file). Non-product children (posts, pages,
categories, tags, attribute taxonomies) are skipped. Override with
``CRAWLER_DRIVESHAFTSHOP_START_URLS`` (comma-separated) for a fixed list.
"""

import os
import re
import time
from typing import Any, ClassVar, Iterator, List, Optional, Tuple, cast
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

from app.core.car_inference import (
    extract_year_ranges,
    infer_car_generations,
    narrow_triples_by_year_range,
)
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
    scraped_payload_from_json_ld,
)

DSS_BASE = "https://driveshaftshop.com"
SITEMAP_INDEX_URL = DSS_BASE + "/sitemap_index.xml"
PRODUCT_PAGE_PATH = "/product/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://driveshaftshop.com/product/2020-2023-g80-bmw-m3-axles/",
]

# Yoast groups sitemaps by post type. Only ``product-sitemap.xml`` (and
# numbered variants Yoast emits once the catalog outgrows one file) contain
# product URLs — everything else is post/page/taxonomy noise.
_PRODUCT_SITEMAP_RE = re.compile(r"/product-sitemap\d*\.xml$", re.IGNORECASE)

# Yoast appends the site name as a title suffix on WebPage nodes. Product
# JSON-LD is usually clean, but strip defensively in case a page leaks it in.
_NAME_SITE_SUFFIX_RE = re.compile(r"\s*[-–]\s*(?:The\s+)?Driveshaft\s+Shop\s*$", re.IGNORECASE)

# Manufacturer part code embedded in product descriptions. DSS terminates
# every description with a line like ``PART# BMWSH3-CV`` (or ``PART# 510520``
# when the manufacturer code equals the WooCommerce id). Capture the token
# up to whitespace / end of string.
_DESCRIPTION_PART_RE = re.compile(
    r"PART\s*#\s*([A-Za-z0-9][A-Za-z0-9\-\./]*)",
    re.IGNORECASE,
)

_DSS_DEFAULT_BRAND = "Driveshaft Shop"

# WooCommerce "size variant" stubs that DSS uses internally as configurator
# options (driveshaft lengths in inches: ``/product/34/``, ``/product/34-5/``,
# ``/product/36-5/`` — ~43 entries in the sitemap). These pages have no
# JSON-LD Product block, an empty <p class="price">, an "Uncategorized"
# breadcrumb, and an H1 like ``34"``. They always 0-parse downstream, so we
# skip them at discovery to save a fetch per stub. Real product slugs carry
# alphabetic tokens (e.g. ``2020-2023-g80-bmw-m3-axles``).
_NUMERIC_ONLY_SLUG_RE = re.compile(r"^\d+(?:-\d+)?$")


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap index, then default."""
    raw = os.environ.get("CRAWLER_DRIVESHAFTSHOP_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a ``product-sitemap[N].xml`` urlset."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return bool(_PRODUCT_SITEMAP_RE.search(path))


def _is_numeric_only_product_slug(url: str) -> bool:
    """True if ``url`` ends in a ``/product/<digits-only>/`` slug (size stub)."""
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return False
    parts = [p for p in path.split("/") if p]
    # Expect exactly ["product", "<slug>"].
    if len(parts) != 2 or parts[0].lower() != "product":
        return False
    return bool(_NUMERIC_ONLY_SLUG_RE.match(parts[1]))


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap_index.xml`` → each ``product-sitemap[N].xml`` urlset and
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
            if _is_numeric_only_product_slug(base):
                continue
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
    """Drop the trailing ``" - Driveshaft Shop"`` suffix if Yoast appended it."""
    stripped = _NAME_SITE_SUFFIX_RE.sub("", name).strip()
    return stripped or name


def _price_cents_from_price_specification(item: dict[str, Any]) -> Optional[int]:
    """
    Read price from ``offers[0].priceSpecification[0].price`` — the shape
    WooCommerce uses on DSS. Returns ``None`` when no usable number is found.
    """
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = cast(dict[str, Any], offers[0])
    elif isinstance(offers, dict):
        offer = offers
    else:
        return None
    specs = offer.get("priceSpecification")
    if isinstance(specs, list) and specs:
        spec = cast(dict[str, Any], specs[0])
    elif isinstance(specs, dict):
        spec = specs
    else:
        return None
    price = spec.get("price")
    if price is None:
        return None
    try:
        num = float(str(price).replace(",", ""))
    except (ValueError, TypeError):
        return None
    if not (num > 0):
        return None
    return int(round(num * 100))


def _part_number_from_description(description: Optional[str]) -> Optional[str]:
    """Extract the manufacturer code from the ``PART# <code>`` line."""
    if not description:
        return None
    match = _DESCRIPTION_PART_RE.search(description)
    if not match:
        return None
    return normalize_part_number(match.group(1))


# Driveshaft Shop product titles overwhelmingly start with a year-range
# prefix: ``"2009-2014 Dodge Challenger SRT8 / R/T ..."``,
# ``"1991-1999 Toyota MR2 Turbo Level 5 ..."``,
# ``"2005-2008 Charger 5.7L/300C 5.7L/Magnum 5.7L ..."``. ~93% of the
# universal-flagged DSS catalog matches the leading-year-range shape;
# the remaining 7% are spec-only listings (driveshaft lengths, gear sets,
# transmission yokes) that legitimately have no fitment.
#
# The hook strategy is: extract the leading year range, run the universal
# phrase pipeline, then narrow the resulting triples to those whose
# generation window overlaps the title's year range. This handles the
# Mitsubishi Eclipse case (universal pipeline returns every Eclipse gen
# on a "Mitsubishi Eclipse" mention; year-narrowing trims to the actually
# fitted generation) and falls through to None when the universal pipeline
# can't identify a make+model at all (so ingest tries again with the
# default keyword scorer rather than emitting no fitment at all).
_DSS_LEADING_YEAR_RANGE_RE = re.compile(r"^\s*(\d{4})\s*[-–—]\s*(\d{2,4})\+?\b")


def _extract_leading_year_range(name: str) -> Optional[Tuple[int, int]]:
    """
    Pull a (start_year, end_year) range from the leading ``"YYYY-YYYY "``
    prefix of a Driveshaft Shop title. Two-digit tails carry the first
    year's century (``"2005-08"`` → ``2005..2008``). Returns ``None`` when
    the title doesn't start with a year-range prefix so the hook falls
    through to the universal pipeline.
    """
    m = _DSS_LEADING_YEAR_RANGE_RE.match(name)
    if not m:
        return None
    try:
        y1 = int(m.group(1))
        tail = m.group(2)
        y2 = int(tail) if len(tail) == 4 else (y1 // 100) * 100 + int(tail)
        if y2 < y1:
            y2 += 100
    except ValueError:
        return None
    if y1 < 1960 or y1 > 2030 or y2 < y1 or y2 > 2035:
        return None
    return (y1, y2)


class DriveshaftShopAdapter(RetailerCrawlerAdapter):
    """
    Driveshaft Shop adapter. Discovery via ``/sitemap_index.xml`` →
    ``product-sitemap[N].xml``. Parsing uses the JSON-LD ``Product`` block,
    with a nested-priceSpecification price fallback, the ``PART# <code>``
    line from the description used as the preferred part number over the
    WooCommerce numeric sku, and a brand default of ``"Driveshaft Shop"``.
    """

    ADAPTER_NAME: ClassVar[str] = "driveshaftshop"
    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Driveshaft Shop product page into a ``ScrapedPayload``.
        Returns ``None`` when no JSON-LD Product is present (soft-404 or
        non-product landing page).
        """
        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        clean_name = _strip_site_suffix(payload.name)

        price_cents = payload.price_cents
        if price_cents is None:
            price_cents = _price_cents_from_price_specification(item)

        part_number = _part_number_from_description(payload.description)
        if not part_number:
            part_number = normalize_part_number(payload.part_number) if payload.part_number else None

        part_manufacturer = (payload.part_manufacturer or "").strip() or _DSS_DEFAULT_BRAND

        return ScrapedPayload(
            name=clean_name,
            product_url=payload.product_url,
            description=payload.description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=payload.image_urls,
            gtin=payload.gtin,
        )

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Layer year-range narrowing on top of the universal phrase pipeline.

        DSS titles lead with ``"YYYY-YYYY "``; the universal pipeline
        already extracts make/model phrases from the rest of the title
        (``"Mitsubishi Eclipse"``, ``"BMW E92"``, ``"GT-R"``) but returns
        every generation of that model. We narrow that set down to the
        generations whose production window overlaps the title's leading
        year range. Returns ``None`` (NOT an empty list) when no leading
        year range is found, when the universal pipeline finds no triples,
        or when narrowing leaves nothing — so ingest falls through to the
        universal pipeline rather than short-circuiting to
        ``is_universal=True``.
        """
        name = parsed.name or ""
        if not name:
            return None
        # Migrated year extraction to the canonical extract_year_ranges helper
        # (issue #5). DSS titles always lead with the year range, so we keep
        # the leading-only constraint by checking that the FIRST extracted
        # range starts at or near position 0 in the title. Pre-migration this
        # was a hand-rolled `^\s*YYYY-YYYY\+?\b` regex; the new helper reads
        # the same shapes (YYYY-YYYY, YYYY-YY, YYYY+) plus a few more for free.
        #
        # The model→gen path stays on infer_car_generations + narrow_triples_by_year_range
        # because the alias-rich universal pipeline catches forms like
        # "2009-2014 Challenger" (CAR_ALIASES entry) that extract_fitment_candidates
        # — which only walks bare CAR_GENERATIONS — would miss. The new
        # extract_fitment_candidates is the right tool for adapters that
        # currently maintain their own _<ADAPTER>_MODEL_PATTERNS dict
        # (Steeda / Hasport / Perrin / Mishimoto); DSS never did, so the
        # universal-pipeline approach is preserved.
        ranges = extract_year_ranges(name)
        if not ranges:
            return None
        # Leading-only guard: the first range must occupy the title's leading
        # span. extract_year_ranges returns ranges in title order, so we only
        # need to verify the first one starts within the leading whitespace
        # prefix. Fall back to None for "Universal 2020-2023 Driveshaft" cases
        # where the year is mid-title (DSS catalog convention is "<year>
        # <chassis>" leading).
        leading_re = re.compile(r"^\s*(\d{4})\s*[-–—]\s*\d{2,4}\+?")
        if not leading_re.match(name):
            return None
        year_range = ranges[0]
        triples = infer_car_generations(name, parsed.description, parsed.product_url)
        if not triples:
            return None
        narrowed = narrow_triples_by_year_range(triples, year_range)
        return narrowed or None
