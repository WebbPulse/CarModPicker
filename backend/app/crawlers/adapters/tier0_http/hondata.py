"""
Hondata (hondata.com) crawler adapter.

Product URLs: https://www.hondata.com/index.php?route=product/product&product_id=<N>
OpenCart storefront. No JSON-LD, no Open Graph meta tags — parsing is entirely
DOM-driven from the default OpenCart product template:

- ``<h1>`` for the product name.
- ``<ul class="list-unstyled">`` with lines ``Brand: ...``, ``Product Code: ...``,
  ``Availability: ...`` for the metadata block.
- ``<ul class="list-unstyled">`` with an ``<h2>$XXX.XX</h2>`` (or plain text) for
  the price.
- ``#tab-description`` tab panel for the long-form description.
- ``<img>`` tags whose src contains ``/image/cache/catalog/`` for the gallery
  (OpenCart's image cache path).

Discovery: Hondata has no ``/sitemap.xml`` — the HTML site map page at
``/index.php?route=information/sitemap`` is the canonical index. The adapter
walks that page for category links (``route=product/category``), then each
category for product links (``route=product/product``). Override with
``CRAWLER_HONDATA_START_URLS`` (comma-separated) for a fixed list.

Brand: the storefront is first-party — every product page renders
``Brand: Hondata, Inc.`` The adapter normalizes this to ``"Hondata"`` and uses
that as the hardcoded fallback when the brand row is missing so cross-retailer
dedupe matches whatever KTuner/other adapters emit for the same manufacturer.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

HONDATA_BASE = "https://www.hondata.com"
SITEMAP_PAGE_URL = HONDATA_BASE + "/index.php?route=information/sitemap"

# OpenCart route query-param values that identify category and product pages.
_CATEGORY_ROUTE = "product/category"
_PRODUCT_ROUTE = "product/product"

# Query params that are pure localization / navigation noise on OpenCart.
# Stripped from discovered URLs so we don't store multiple rows for the same
# product under different ``language`` settings.
_URL_NOISE_PARAMS = frozenset({"language", "path"})

# OpenCart image cache path. The default theme emits resized versions under
# ``/image/cache/catalog/<slug>/<name>-<W>x<H>.jpg``; we collect only these so
# site chrome (logos, payment-method icons) doesn't leak into image_urls.
_IMAGE_CACHE_PATH = "/image/cache/catalog/"

# Storefront is first-party: brand row always reads "Hondata, Inc." — normalize
# to the shorter form and use as the default when the row is missing.
_HONDATA_BRAND = "Hondata"

DEFAULT_START_URLS = [
    "https://www.hondata.com/index.php?route=product/product&product_id=30",
]


def _strip_noise_params(url: str) -> str:
    """
    Drop ``language`` and ``path`` from an OpenCart URL. ``language`` is pure
    localization noise; ``path`` only encodes the breadcrumb trail used to
    render the page — ``product_id`` alone is enough to identify the product.
    Other params (``route``, ``product_id``) are preserved.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if not parsed.query:
        return url
    kept = [
        (k, v) for k, v in parse_qs(parsed.query, keep_blank_values=True).items() if k.lower() not in _URL_NOISE_PARAMS
    ]
    query = urlencode([(k, vv) for k, vs in kept for vv in vs], doseq=False)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, ""))


def _route_of(url: str) -> Optional[str]:
    """Return the ``route`` query-param value of an OpenCart URL, or None."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if not parsed.query:
        return None
    qs = parse_qs(parsed.query)
    values = qs.get("route")
    return values[0] if values else None


def _is_product_url(url: str) -> bool:
    """True if ``url`` is an OpenCart product page on hondata.com."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not (host == "hondata.com" or host.endswith(".hondata.com")):
        return False
    return _route_of(url) == _PRODUCT_ROUTE


def _extract_links_by_route(html: str, base_url: str, route: str) -> List[str]:
    """Absolute URLs on ``base_url`` whose ``route`` query param equals ``route``."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        absolute = urljoin(base_url, href.strip())
        if _route_of(absolute) != route:
            continue
        cleaned = _strip_noise_params(absolute)
        if cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _discover_product_urls_via_sitemap_page() -> List[str]:
    """
    Walk the HTML sitemap page → each category → yield product URLs.

    OpenCart sites ship a CMS sitemap at ``/index.php?route=information/sitemap``
    (not an XML sitemap). It lists every category link, which we then fetch to
    collect product links. Returns an empty list on any failure so the caller
    can fall back to the hardcoded default.
    """
    try:
        index_html = fetch_page(SITEMAP_PAGE_URL, timeout=15)
    except Exception:
        return []

    category_urls = _extract_links_by_route(index_html, SITEMAP_PAGE_URL, _CATEGORY_ROUTE)
    if not category_urls:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []
    for cat_url in category_urls:
        try:
            cat_html = fetch_page(cat_url, timeout=15)
        except Exception:
            continue
        for product_url in _extract_links_by_route(cat_html, cat_url, _PRODUCT_ROUTE):
            if not _is_product_url(product_url) or product_url in seen:
                continue
            seen.add(product_url)
            product_urls.append(product_url)
    return product_urls


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk sitemap → categories → products."""
    raw = os.environ.get("CRAWLER_HONDATA_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap_page()
    return urls if urls else list(DEFAULT_START_URLS)


def _info_lines(soup: BeautifulSoup) -> List[str]:
    """
    All ``<li>`` text fragments from the product info ``<ul class="list-unstyled">``
    blocks. OpenCart renders ``Brand: ...`` / ``Product Code: ...`` / ``Availability: ...``
    each in its own ``<li>``; collecting them once keeps the extractor helpers
    below independent of DOM position.
    """
    lines: List[str] = []
    for ul in soup.select("ul.list-unstyled"):
        if not isinstance(ul, Tag):
            continue
        for li in ul.find_all("li"):
            if not isinstance(li, Tag):
                continue
            text = li.get_text(separator=" ", strip=True)
            if text:
                lines.append(text)
    return lines


def _extract_part_number(info_lines: List[str]) -> Optional[str]:
    """Find ``Product Code: XYZ`` among the info ``<li>`` lines."""
    for line in info_lines:
        m = re.match(r"^\s*Product\s*Code\s*:\s*(.+?)\s*$", line, re.IGNORECASE)
        if not m:
            continue
        return normalize_part_number(m.group(1))
    return None


def _normalize_hondata_brand(raw: Optional[str]) -> Optional[str]:
    """
    ``"Hondata, Inc."`` → ``"Hondata"``. Leaves anything else (unlikely on
    this storefront) untouched so a co-branded SKU we haven't seen yet still
    passes through with its original label.
    """
    if not raw:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    if re.fullmatch(r"Hondata(?:\s*,?\s*Inc\.?)?", cleaned, re.IGNORECASE):
        return _HONDATA_BRAND
    return cleaned


def _extract_brand(info_lines: List[str]) -> Optional[str]:
    """Find ``Brand: Hondata, Inc.`` among the info ``<li>`` lines."""
    for line in info_lines:
        m = re.match(r"^\s*Brand\s*:\s*(.+?)\s*$", line, re.IGNORECASE)
        if not m:
            continue
        return _normalize_hondata_brand(m.group(1))
    return None


# Price on OpenCart's default theme lives in a ``<ul class="list-unstyled">``
# with an ``<h2>`` child (e.g. ``<h2>$595.00</h2>``). Scanning all info_lines
# for the first ``$…`` match picks up that block and ignores unrelated dollar
# strings that appear later in descriptions.
_PRICE_IN_LINE_RE = re.compile(r"\$[\s,]?\d+(?:\.\d{1,2})?")


def _extract_price_cents(info_lines: List[str], soup: BeautifulSoup) -> Optional[int]:
    """
    Price in cents. Prefer a ``$…`` hit inside the info ``<li>`` lines (that is
    the product price block). Fall back to scanning any ``<h2>`` on the page
    so theme variants that move the price out of the info list still work.
    """
    for line in info_lines:
        match = _PRICE_IN_LINE_RE.search(line)
        if match:
            cents = parse_price_cents(match.group(0))
            if cents is not None:
                return cents
    for h2 in soup.find_all("h2"):
        if not isinstance(h2, Tag):
            continue
        text = h2.get_text(strip=True)
        match = _PRICE_IN_LINE_RE.search(text)
        if not match:
            continue
        cents = parse_price_cents(match.group(0))
        if cents is not None:
            return cents
    return None


def _extract_description(soup: BeautifulSoup, max_len: int = 2000) -> Optional[str]:
    """
    Long-form description from the OpenCart ``#tab-description`` panel. Falls
    back to the first long ``<p>`` in ``#content`` when the default theme's
    tab id is missing (rare, but some OpenCart themes rename the panel).
    """
    tab = soup.find(id="tab-description")
    if isinstance(tab, Tag):
        text = tab.get_text(separator=" ", strip=True)
        if text and len(text) > 40:
            normalized = normalize_description_text(text, max_len=max_len)
            if normalized:
                return normalized

    content = soup.find(id="content")
    if isinstance(content, Tag):
        for p in content.find_all("p"):
            if not isinstance(p, Tag):
                continue
            text = p.get_text(separator=" ", strip=True)
            if text and len(text) > 80:
                normalized = normalize_description_text(text, max_len=max_len)
                if normalized:
                    return normalized
    return None


def _absolute_image_url(src: str) -> Optional[str]:
    """Protocol/relative → absolute ``https://www.hondata.com/...`` URL."""
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = HONDATA_BASE + s
    if not s.startswith("http"):
        return None
    return s


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect ``/image/cache/catalog/...`` URLs. OpenCart resizes every product
    image into that cache path; matching on the path is a tighter filter than
    scanning all ``<img>`` tags (which would sweep in header logos, payment
    icons, and the cart badge).

    Gathers ``<a href>`` (full-size) before ``<img src>`` (thumbnail) so the
    first image is the high-res one that the lightbox links to.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(candidate: Optional[str]) -> None:
        if not candidate or _IMAGE_CACHE_PATH not in candidate:
            return
        absolute = _absolute_image_url(candidate)
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        ordered.append(absolute)

    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag) or len(ordered) >= 12:
            break
        href = a.get("href")
        if isinstance(href, str):
            add(href)

    for img in soup.find_all("img", src=True):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        src = img.get("src")
        if isinstance(src, str):
            add(src)

    return ordered[:12]


class HondataAdapter(RetailerCrawlerAdapter):
    """
    Hondata adapter. Discovery: HTML sitemap page → categories → product
    pages. Parsing: DOM-only against the default OpenCart product template
    (no JSON-LD, no Open Graph on this storefront).
    """

    ADAPTER_NAME: ClassVar[str] = "hondata"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered via the ``/index.php?route=information/sitemap``
        page. Set ``CRAWLER_HONDATA_START_URLS`` (comma-separated) to override.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Hondata product page. Returns ``None`` when the page has no
        ``<h1>`` (non-product page — category listing, account page, etc.).
        """
        soup = BeautifulSoup(html, "html.parser")

        h1 = soup.find("h1")
        name = h1.get_text(strip=True) if isinstance(h1, Tag) else None
        if not name or len(name) < 2:
            return None

        info_lines = _info_lines(soup)
        part_number = _extract_part_number(info_lines)
        part_manufacturer = _extract_brand(info_lines) or _HONDATA_BRAND
        price_cents = _extract_price_cents(info_lines, soup)
        description = _extract_description(soup)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=_strip_noise_params(url),
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
