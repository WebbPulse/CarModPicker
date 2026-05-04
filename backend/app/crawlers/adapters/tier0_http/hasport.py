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
from typing import ClassVar, Iterator, List, Optional, Tuple
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.core.car_inference import generations_for_make_model_year_range
from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_description_text,
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

# A non-trivial subset of Hasport's catalog uses the bare SKU as the JSON-LD
# ``name`` (e.g. ``"EFRB"``, ``"BBRB"``) with the descriptive text living
# only in ``.woocommerce-product-details__short-description``. This regex
# detects that "name is just the SKU" case so we can splice the short
# description into the catalog name. Anchored end-to-end; allows internal
# dashes for codes like ``DC2-K``.
_BARE_SKU_NAME_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,15}$")

# Truncation cap when composing ``<SKU> - <short description>``. Keeps the
# catalog row's ``name`` under the same effective ceiling as other adapters
# while leaving room for the SKU prefix.
_NAME_COMPOSE_MAX_LEN = 200

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


def _extract_short_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull the WooCommerce ``.woocommerce-product-details__short-description``
    block. On Hasport this is consistently a single descriptive sentence
    (``"Rear Engine Bracket for 88-91 Civic/CRX..."``) — the place to look
    when JSON-LD ``name`` is just the SKU code. Returns ``None`` when the
    block is missing or empty after normalization.
    """
    block = soup.select_one(".woocommerce-product-details__short-description")
    if not isinstance(block, Tag):
        return None
    text = block.get_text(separator=" ", strip=True)
    if not text:
        return None
    return normalize_description_text(text, max_len=_NAME_COMPOSE_MAX_LEN)


def _compose_name(json_ld_name: str, short_description: Optional[str]) -> str:
    """
    Return the catalog ``name`` to use for the part. When the JSON-LD
    ``name`` is just a bare SKU code (``"EFRB"``, ``"BBRB"``) and we have a
    short description, splice them as ``"<SKU> - <short description>"`` so
    the catalog row carries something the user can read at a glance.
    Otherwise return the JSON-LD name unchanged.
    """
    name = (json_ld_name or "").strip()
    if not name or not short_description or not _BARE_SKU_NAME_RE.match(name):
        return name
    composed = f"{name} - {short_description.strip()}"
    if len(composed) > _NAME_COMPOSE_MAX_LEN:
        # Reserve one char for the trailing ellipsis so the final string
        # respects the cap exactly.
        composed = composed[: _NAME_COMPOSE_MAX_LEN - 1].rstrip() + "…"
    return composed


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


# Hasport's catalog is Honda-only (with Acura sub-makes for Integra/RSX/NSX).
# Titles encode fitment as a 2-digit year-pair embedded in the description
# (``"K Series Wiring Conversion for 92-95 Civic / 94-99 Integra"``,
# ``"Engine Mount kit B-series engine with 3 bolt left hand mount for 96-00 Civic"``,
# ``"K-Series Swap Mount Kit for 90-93 Integra"``). About 75% of the
# universal-flagged catalog uses ``YY-YY``; ~12% use ``YYYY-YYYY`` for newer
# parts (``"FG4STK - Mount kit for 2012-2014 Civic SI"``,
# ``"FERR Replacement Rear Mount for 2022-2026 Civic"``).
#
# Multiple model tokens may appear in one title (``"92-95 Civic / 94-99
# Integra"``); each year-range/model pair is matched independently so we
# emit triples for both. The ``infer_car_for_part`` hook iterates the
# title once with a combined regex and accumulates into a deduped triple
# list.
#
# Acura sub-make handling: Integra, RSX, and NSX are sold as Acura in the US.
# CR-V/Civic/Accord/etc map to Honda. The static
# ``car_generations_data`` rows mirror the make split.
_HASPORT_MODEL_TOKENS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    # Acura first so "Integra" doesn't accidentally swap to Honda Integra.
    (re.compile(r"\bIntegra\b", re.IGNORECASE), "Acura", "Integra"),
    (re.compile(r"\bRSX\b", re.IGNORECASE), "Acura", "RSX"),
    (re.compile(r"\bNSX\b", re.IGNORECASE), "Acura", "NSX"),
    (re.compile(r"\bTL\b", re.IGNORECASE), "Acura", "TL"),
    (re.compile(r"\bTSX\b", re.IGNORECASE), "Acura", "TSX"),
    # Honda
    (re.compile(r"\bCivic\b", re.IGNORECASE), "Honda", "Civic"),
    (re.compile(r"\bAccord\b", re.IGNORECASE), "Honda", "Accord"),
    (re.compile(r"\bPrelude\b", re.IGNORECASE), "Honda", "Prelude"),
    (re.compile(r"\bS2000\b", re.IGNORECASE), "Honda", "S2000"),
    (re.compile(r"\bCRX\b", re.IGNORECASE), "Honda", "CRX"),
    (re.compile(r"\bCR-?Z\b", re.IGNORECASE), "Honda", "CR-Z"),
    (re.compile(r"\bCR-?V\b", re.IGNORECASE), "Honda", "CR-V"),
    (re.compile(r"\bElement\b", re.IGNORECASE), "Honda", "Element"),
    (re.compile(r"\bFit\b"), "Honda", "Fit"),  # case-sensitive — "fit" is a common verb
)

# Year-range patterns: "92-95" (canonical 2-digit), "01-05", "2012-2014"
# (newer parts), "2022-2026". The 2-digit form needs century resolution
# (`92` → 1992, `01` → 2001) and pair-aware (``92-00`` is 1992-2000).
_HASPORT_YY_YY_RE = re.compile(r"\b(\d{2})\s*[-–—]\s*(\d{2})\b")
_HASPORT_YYYY_YYYY_RE = re.compile(r"\b(\d{4})\s*[-–—]\s*(\d{4})\b")
_HASPORT_YYYY_YY_RE = re.compile(r"\b(\d{4})\s*[-–—]\s*(\d{2})\b")


def _yy_to_yyyy(yy: int, anchor: Optional[int] = None) -> int:
    """
    Resolve a 2-digit year to 4 digits. ``anchor`` is the previous year
    in a range pair: when present, prefer the same century; if that
    yields an end-before-start, bump up by 100.

    Without an anchor: years 70+ → 19xx (Hasport's earliest titles are
    84-87 Civic), years <70 → 20xx.
    """
    if anchor is None:
        return 1900 + yy if yy >= 70 else 2000 + yy
    century = (anchor // 100) * 100
    candidate = century + yy
    if candidate < anchor:
        candidate += 100
    return candidate


def _extract_hasport_year_ranges(name: str) -> list[Tuple[int, int]]:
    """
    Return every year-range tuple extracted from ``name``. Tries
    ``YYYY-YYYY``, then ``YYYY-YY``, then ``YY-YY``. Multiple ranges in
    one title (``"92-95 Civic / 94-99 Integra"``) all come back so each
    can be paired with its corresponding model token.
    """
    out: list[Tuple[int, int]] = []
    seen: set[Tuple[int, int]] = set()

    def add(y1: int, y2: int) -> None:
        if y1 < 1960 or y1 > 2030 or y2 < y1 or y2 > 2035:
            return
        if (y1, y2) in seen:
            return
        seen.add((y1, y2))
        out.append((y1, y2))

    for m in _HASPORT_YYYY_YYYY_RE.finditer(name):
        try:
            add(int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
    for m in _HASPORT_YYYY_YY_RE.finditer(name):
        try:
            y1 = int(m.group(1))
            y2 = _yy_to_yyyy(int(m.group(2)), anchor=y1)
            add(y1, y2)
        except ValueError:
            continue
    # YY-YY last so 4-digit matches above don't get re-matched as their
    # 2-digit suffix.
    for m in _HASPORT_YY_YY_RE.finditer(name):
        # Skip if the surrounding chars indicate a 4-digit year was already
        # matched: ``2012-2014`` re-matches as ``12-14`` here.
        start, end = m.span()
        if start > 0 and name[start - 1].isdigit():
            continue
        if end < len(name) and name[end].isdigit():
            continue
        try:
            y1_raw = int(m.group(1))
            y2_raw = int(m.group(2))
            y1 = _yy_to_yyyy(y1_raw)
            y2 = _yy_to_yyyy(y2_raw, anchor=y1)
            add(y1, y2)
        except ValueError:
            continue
    return out


def _extract_hasport_models(name: str) -> list[Tuple[str, str]]:
    """
    Return every (make, model) pair whose token appears in ``name``,
    deduped, in priority order. Multi-model titles (``"92-95 Civic /
    94-99 Integra"``) yield both pairs.
    """
    out: list[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for pat, make, model in _HASPORT_MODEL_TOKENS:
        if (make, model) in seen:
            continue
        if pat.search(name):
            seen.add((make, model))
            out.append((make, model))
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

    ADAPTER_NAME: ClassVar[str] = "hasport"
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

        # Hasport's JSON-LD ``name`` is sometimes the bare SKU code (e.g.
        # ``"EFRB"``) with the descriptive copy only in the WooCommerce
        # short-description block. Compose ``"<SKU> - <short desc>"`` for
        # those rows so the catalog isn't full of opaque four-letter codes.
        short_desc = _extract_short_description(soup)
        composed_name = _compose_name(payload.name, short_desc)

        gallery = _extract_gallery_images(soup)
        image_urls = gallery or (payload.image_urls or None)

        return ScrapedPayload(
            name=composed_name,
            product_url=canonical_url,
            description=payload.description,
            price_cents=payload.price_cents,
            part_manufacturer=_HASPORT_BRAND,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Pair year-ranges with model tokens in the title and intersect each
        pair against the static generation windows. Multi-model titles
        (``"92-95 Civic / 94-99 Integra"``) emit triples for both. Single
        model with multiple year ranges (``"FERR Replacement Rear Mount
        for 2022-2026 Civic"``) intersects against the single model.

        Returns ``None`` (NOT empty list) when no pair fires so ingest
        falls through to the universal pipeline. Generic items without a
        model token (``"Urethane mount bushings"``, T-shirts) correctly
        return ``None``.
        """
        name = parsed.name or ""
        if not name:
            return None
        models = _extract_hasport_models(name)
        if not models:
            return None
        year_ranges = _extract_hasport_year_ranges(name)
        if not year_ranges:
            return None

        out: list[Tuple[str, str, str]] = []
        seen: set[Tuple[str, str, str]] = set()
        for make, model in models:
            for y_range in year_ranges:
                for triple in generations_for_make_model_year_range(make, model, y_range):
                    if triple not in seen:
                        seen.add(triple)
                        out.append(triple)
        return out or None
