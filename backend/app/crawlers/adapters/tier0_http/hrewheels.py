"""
HRE Performance Wheels (hrewheels.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``/wheels/<series-slug>/<model-slug>`` (e.g.
``/wheels/series-p1/p101``, ``/wheels/classic-series/305m``,
``/wheels/hre-flowform/ff15``). Anything shorter (``/wheels``,
``/wheels/grid``, ``/wheels/<series>``) is a category / landing page and
is rejected.

HRE runs a custom PHP stack on nginx + Plesk — no Shopify, no WooCommerce,
no JSON-LD ``Product`` block. All product facts live in bespoke class
names on a server-rendered page:

- ``h1.WheelName`` — model code (``P101``)
- ``.SeriesName`` — series (``Series P1``)
- ``.MainImage img[src]`` — hero image (422x409 Shopify-style variant)
- ``.WheelAltImages a[href]`` / ``a[data-large]`` — full-resolution
  gallery (same asset at the ``wheel-original`` size variant)
- ``og:title`` — ``Series P1 - P101`` (richer than ``h1`` alone; used as
  the preferred name so the catalog entry shows the series)
- ``og:description`` — always empty on HRE; the description copy is a
  run of direct-child ``<p>`` tags inside ``.MainInformation``

Pages also render a ``.SeriesDisplayPrice`` "Starting at $X USD each"
line for some series. Per the RETAILER_BACKLOG policy this adapter is
catalog-only (wheels are quote-driven and configured per-customer), so
``price_cents`` is always ``None`` — same stance as ``wheelsboutique.py``.
The ingest pipeline records the listing without appending to price
history. See ``site_problem_notes/hrewheels.md``.

Fetcher tier: ``http``. The backlog entry hedged "Tier-1/2"; an AWS
egress probe showed the origin returns 200 to a plain Chrome UA with no
Cloudflare fronting (``server: nginx`` + ``x-powered-by: PHP/7.4`` + no
``cf-ray``). If that changes, promote to ``tier1_tls/``.

Discovery: ``/sitemap.xml`` is a single flat ``<urlset>`` (not a
sitemap-index) that mixes product URLs with CMS pages (``/gallery``,
``/news``, ``/corporate/*``, ``/dealers``, etc.), so the filter is the
product URL regex rather than a child-sitemap name. Loc values use the
``http://`` scheme even though the site 301s to ``https://``; the
adapter normalizes to ``https://www.hrewheels.com`` before yielding.
Override with ``CRAWLER_HREWHEELS_START_URLS`` (comma-separated).

Brand: HRE only sells HRE. Unlike Wheels Boutique (multi-brand reseller
where the brand is in the URL's first path segment), every hrewheels.com
product is by definition an HRE wheel, so the adapter returns the
constant ``"HRE"``.

Part numbers: model codes like ``P101`` / ``305M`` / ``FF15`` are
series-level identifiers, not true SKUs — the same model ships in many
diameters, widths, offsets, and finishes, each a distinct part. Leaving
``part_number=None`` matches Wheels Boutique's posture and avoids
collapsing real fitments into a single catalog row downstream.
"""

import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import meta_content, normalize_description_text

HREWHEELS_BASE = "https://www.hrewheels.com"
SITEMAP_URL = HREWHEELS_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Product paths are ``/wheels/<series>/<model>`` — exactly two segments
# after ``/wheels/``. The ``/wheels`` root and ``/wheels/grid`` index both
# fall one segment short and are rejected by this shape.
_PRODUCT_PATH_RE = re.compile(r"^/wheels/[^/]+/[^/]+/?$", re.IGNORECASE)

DEFAULT_START_URLS = [
    "https://www.hrewheels.com/wheels/series-p1/p101",
]

# HRE's brand is invariant — the whole site is their catalog.
HRE_BRAND = "HRE"

# The Affirm monthly-payment promo renders as a ``<p>`` inside
# ``.MainInformation``. Its copy is always "As low as $X/mo with ... Apply
# now" — strip these before joining description paragraphs so the catalog
# row isn't polluted with financing text.
_AFFIRM_PROMO_RE = re.compile(r"\bas low as\b.*\b(apply now|/mo)\b", re.IGNORECASE)


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on hrewheels.com and matches the product path shape."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "hrewheels.com" and not host.endswith(".hrewheels.com"):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _canonicalize_sitemap_url(url: str) -> str:
    """Normalize sitemap loc URLs to ``https://www.hrewheels.com/<path>``.

    Sitemap locs are emitted as ``http://www.hrewheels.com/...`` but the
    origin 301s to the ``https`` + ``www`` pair. Rewriting up-front keeps
    the fetcher from eating a redirect per URL.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip()
    path = parsed.path or "/"
    return f"{HREWHEELS_BASE}{path}"


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_HREWHEELS_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_HREWHEELS_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` and filter its flat urlset down to product paths.

    HRE's sitemap is a single ``<urlset>`` (not an index), so there's no
    child-sitemap step — just one fetch, one XML parse, one regex filter.
    Returns an empty list on fetch/parse failure so the caller can fall
    through to ``DEFAULT_START_URLS``.
    """
    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=30)
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        canonical = _canonicalize_sitemap_url(loc.text)
        if not _is_product_url(canonical):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        product_urls.append(canonical)
    return product_urls


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer ``og:title`` (``Series P1 - P101``) because it pairs the model
    code with the series; ``h1.WheelName`` alone (``P101``) is ambiguous
    across series once parts land in the global catalog. Fall back to the
    bare model code, then to ``<title>`` as a last resort.
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    wheel_name = soup.select_one("h1.WheelName")
    if isinstance(wheel_name, Tag):
        text = wheel_name.get_text(strip=True)
        if text:
            return text
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        text = title_tag.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Join the prose ``<p>`` tags inside ``.MainInformation``.

    Skip the Affirm financing promo (matched by ``_AFFIRM_PROMO_RE``) and
    the ``.ViewFinishes`` anchor-wrapper ``<p>``. Empty paragraphs and
    ones without real text are dropped. Returns ``None`` when nothing
    meaningful remains rather than returning an empty string so the
    ingest payload stays tidy.
    """
    main_info = soup.select_one(".MainInformation")
    if not isinstance(main_info, Tag):
        return None

    parts: List[str] = []
    for p in main_info.find_all("p", recursive=False):
        if not isinstance(p, Tag):
            continue
        classes = p.get("class")
        if isinstance(classes, list) and "ViewFinishes" in classes:
            continue
        text = p.get_text(separator=" ", strip=True)
        if not text:
            continue
        if _AFFIRM_PROMO_RE.search(text):
            continue
        parts.append(text)

    if not parts:
        return None
    joined = " ".join(parts)
    return normalize_description_text(joined, max_len=2000)


def _normalize_image_url(src: str) -> Optional[str]:
    """Return ``https://<host>/<path>`` for a product image URL, else None.

    HRE hosts images on ``s3.amazonaws.com/cdn.hrewheels.com`` and emits
    them as protocol-relative ``//s3.amazonaws.com/...`` links. Rejects
    anything outside that CDN path so shared theme chrome (logos, PDF
    icons, sponsor badges like ``/img/logo-Brembo.jpg``) doesn't leak in.
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = HREWHEELS_BASE + s
    if not s.startswith("http"):
        return None
    low = s.lower()
    if "cdn.hrewheels.com" not in low:
        return None
    return s


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect gallery image URLs for the product.

    Preferred source is ``.WheelAltImages a[data-large]`` — those point
    at the ``wheel-original`` (full-resolution) variant of each photo.
    ``a[href]`` on the same anchor is a 422x409 mid-size variant and is
    only used when ``data-large`` is missing. Falls back to the hero
    ``.MainImage img[src]`` and finally the smaller og:image thumbnail
    so a product with no alt gallery still has one image. Deduped and
    capped at 12.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        ordered.append(normalized)

    alt_scope = soup.select_one(".WheelAltImages")
    if isinstance(alt_scope, Tag):
        for anchor in alt_scope.find_all("a"):
            if not isinstance(anchor, Tag):
                continue
            data_large = anchor.get("data-large")
            href = anchor.get("href")
            if isinstance(data_large, str) and data_large.strip():
                add(data_large.strip())
            elif isinstance(href, str) and href.strip():
                add(href.strip())

    main_scope = soup.select_one(".MainImage")
    if isinstance(main_scope, Tag):
        img = main_scope.find("img")
        if isinstance(img, Tag):
            src = img.get("src")
            if isinstance(src, str):
                add(src.strip())

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content.strip())

    return ordered[:12]


class HREWheelsAdapter(RetailerCrawlerAdapter):
    """
    HRE Performance Wheels adapter — catalog-only, quote-driven pricing.

    Discovery walks ``/sitemap.xml`` (flat urlset, not an index) and
    filters to ``/wheels/<series>/<model>`` paths. Parsing reads bespoke
    class names (``h1.WheelName``, ``.MainInformation``, ``.MainImage``,
    ``.WheelAltImages``) because the custom PHP stack emits no JSON-LD
    Product block.

    Like Wheels Boutique, this adapter leaves ``price_cents=None`` and
    skips part numbers — HRE wheels are configured per-fitment and a
    single page represents many orderable SKUs.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins, then sitemap, then ``DEFAULT_START_URLS``."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in _discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse an HRE product page. Returns ``None`` for non-product URLs or when no name is found."""
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)
        images = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=None,
            part_manufacturer=HRE_BRAND,
            part_number=None,
            image_urls=images if images else None,
        )
