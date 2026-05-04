"""
KW automotive North America (kwsuspensions.com) crawler adapter — Tier 1 (TLS).

Product URLs: ``https://www.kwsuspensions.com/products/<kebab-slug>.html``

KW is the most cross-shopped premium coilover brand and the first direct-mfr
coilover source in the index (see ``RETAILER_BACKLOG.md`` — coilovers is a
vertical previously at zero). Every SKU on the site is KW-branded, so
``part_manufacturer`` is hardcoded to ``KW_BRAND``.

Fetcher tier: ``tls``. The site is a legacy Magento 1 storefront fronted by
a geo/cookie interstitial:

- ``GET /`` returns 302 → ``/fwd_custom/ip2country/public/ip2country.php`` and
  sets ``Set-Cookie: cookieCheck=1``.
- Without a ``langselector`` cookie every request gets a Refresh-0 interstitial
  with an empty HTML body.
- Visiting ``/en-us/`` once sets ``langselector=subpage_no_redirect`` and
  subsequent requests return real content.

We handle this with a one-time warm-up to ``/en-us/`` at the start of
``discover_product_urls()``. The TLS fetcher keeps a single curl_cffi session
across calls so the cookie persists for every URL the runner fetches after
discovery returns. Plain HTTP would work too, but the Tier 0 ``HttpFetcher``
built by ``get_fetcher("http")`` does not share a requests.Session across
calls, so cookies wouldn't carry over — Tier 1 is the cleaner fit and matches
the backlog's guess that the site is bot-protected.

Discovery: no usable sitemap (``/sitemap.xml`` 404s; ``/sitemap`` is a human-
readable HTML page listing top-level categories only). The ``/products.html``
catalog is the authoritative SKU list — walk ``?p=1`` upward until the "next
page" link disappears. Magento caps at the last real page, so asking for
``?p=9999`` silently re-serves the final page; we detect the end by the
absence of the ``i-next`` pagination arrow rather than by HTTP status.
Override with ``CRAWLER_KWSUSPENSIONS_START_URLS``.

Parsing: no JSON-LD, no microdata, no OpenGraph — the Magento theme strips
them. Parse the DOM directly:

- Name: ``<div class="product-name"><h3>…</h3></div>``. The ``<title>`` tag
  is always the literal ``"KW Suspensions"`` (storefront chrome) and useless.
- Part number: ``<div class="kw-prod-view-part-no">Part #: …</div>``. The
  theme renders the SKU here and also in the product URL's trailing segment
  (``…-coilover-kit-10210005.html``); we prefer the DOM source because the
  URL slug is lowercase while the SKU is mixed case (``1021000T``).
- Price: ``<span class="map-price"><span class="price">$1,479.00</span></span>``.
  Some SKUs are MAP-suppressed ("Please call for availability") with no
  price shown — we emit ``price_cents=None`` rather than inventing one.
- Description: ``<div class="kw-decription-text">…</div>`` (yes, the typo'd
  class name is theirs; it's consistent across every product page). Contains
  the one-liner copy and a ``<b>Fits:</b>`` block with vehicle applications
  that car-inference can pick up downstream.
- GTIN: ``<table class="kw-metrics-table">`` row where the first cell text
  is ``"UPC Code:"``. Not every SKU has one (apparel / accessories); emit
  ``gtin=None`` when missing.
- Images: ``/media/catalog/product/cache/<n>/image/<size>/<hash>/k/w/
  kw_<sku>_<idx>_<…>.jpg``. The same image is rendered twice (256x thumb +
  1920x modal). We dedupe on the raw filename (``kw_<sku>_<idx>_…``) and
  keep the largest size variant we saw per filename.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

KW_BASE = "https://www.kwsuspensions.com"
KW_WARMUP_URL = f"{KW_BASE}/en-us/"
KW_CATALOG_URL_TEMPLATE = f"{KW_BASE}/products.html?p={{page}}"
KW_BRAND = "KW Suspensions"

# Safety stop: 1896 SKUs / 15 per page ≈ 127 pages. 500 is a wide margin for
# catalog growth but cheap if the "no next" detection ever breaks.
MAX_CATALOG_PAGES = 500

# Canonical product URL: /products/<kebab-slug>.html — anything else under
# /products (bare /products, /products/coilovers/v1, /products.html itself)
# is category chrome, not a SKU page.
_PRODUCT_PATH_RE = re.compile(r"^/products/[a-z0-9][a-z0-9\-]*\.html$", re.IGNORECASE)

# Pagination next-page arrow on /products.html. When this class disappears
# we've reached the last real page (Magento silently re-serves it for any
# higher ?p=N so HTTP status doesn't change).
_PAGINATION_NEXT_RE = re.compile(r'class="[^"]*\bi-next\b', re.IGNORECASE)

# Product image URL inside the Magento catalog cache. Group 1 = cache size
# segment (e.g. "256x" or "1920x") so we can prefer the large variant over
# the thumbnail. Group 2 = the raw filename we dedupe on (``kw_<sku>_<idx>…``).
_PRODUCT_IMAGE_RE = re.compile(
    r"https?://www\.kwsuspensions\.com/media/catalog/product/cache/\d+/image/(\d+x\d*)"
    r"/[0-9a-f]+/[a-z]/[a-z]/(kw_[A-Za-z0-9_\-]+\.(?:jpg|jpeg|png|webp))",
    re.IGNORECASE,
)

# Fallback so a fresh run still exercises parsing when catalog discovery breaks.
DEFAULT_START_URLS = [
    "https://www.kwsuspensions.com/products/kw-suspensions-kw-v1-coilover-kit-10210005.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a KW product SKU page (``/products/<slug>.html``)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "kwsuspensions.com" and not host.endswith(".kwsuspensions.com"):
        return False
    # /products.html is the catalog listing, not a SKU.
    if (parsed.path or "").lower() == "/products.html":
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_KWSUSPENSIONS_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_KWSUSPENSIONS_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_product_links(html: str) -> List[str]:
    """Pull ``/products/<slug>.html`` hrefs from a listing page in document order, deduped."""
    seen: set[str] = set()
    out: List[str] = []
    for match in re.finditer(
        r'href="(https?://www\.kwsuspensions\.com/products/[a-z0-9][a-z0-9\-]*\.html)"',
        html,
        re.IGNORECASE,
    ):
        url = match.group(1)
        if not _is_product_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


def _has_next_page(html: str) -> bool:
    """True if the listing page has a "next" pagination arrow."""
    return bool(_PAGINATION_NEXT_RE.search(html))


def _first_class(soup: BeautifulSoup, tag_name: str, class_name: str) -> Optional[Tag]:
    """First element of ``tag_name`` bearing ``class_name``; None when absent."""
    found = soup.find(tag_name, class_=class_name)
    return found if isinstance(found, Tag) else None


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """Pull the product title from ``.product-name h3``. The page ``<title>`` is always
    the literal storefront string and is useless here."""
    container = _first_class(soup, "div", "product-name")
    if container is not None:
        h3 = container.find("h3")
        if isinstance(h3, Tag):
            text = h3.get_text(strip=True)
            if text:
                return text
    # Defensive fallback: any h3 inside a .product-name-like region.
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_part_number(soup: BeautifulSoup) -> Optional[str]:
    """Read the SKU from ``.kw-prod-view-part-no`` and strip the ``Part #:`` prefix."""
    tag = _first_class(soup, "div", "kw-prod-view-part-no")
    if tag is None:
        return None
    text = tag.get_text(separator=" ", strip=True)
    if not text:
        return None
    # normalize_part_number handles the "Part #:" prefix (see parsing._PART_NUMBER_PREFIXES).
    return normalize_part_number(text)


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """Read the current retail price. ``.map-price .price`` is the only price on
    page; MAP-suppressed SKUs render no price at all and we return ``None``."""
    # Prefer the explicit .map-price container so we don't pick up related-product
    # prices from a "You may also like" block on the same page.
    for container_class in ("map-price", "price-box"):
        container = _first_class(soup, "span", container_class) or _first_class(soup, "div", container_class)
        if container is None:
            continue
        price_tag = container.find("span", class_="price")
        if isinstance(price_tag, Tag):
            raw = price_tag.get_text(strip=True)
            if raw:
                cents = parse_price_cents(raw)
                if cents is not None:
                    return cents
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Pull ``.kw-decription-text`` (their typo). Carries the one-line copy plus
    a ``<b>Fits:</b>`` block with vehicle applications that downstream car-inference
    picks up. Falls back to ``<meta name=description>`` (HTML-encoded) if missing."""
    tag = _first_class(soup, "div", "kw-decription-text")
    if tag is not None:
        text = tag.get_text(separator=" ", strip=True)
        if text:
            normalized = normalize_description_text(text, max_len=2000)
            if normalized:
                return normalized
    meta = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta, Tag):
        content = meta.get("content")
        if isinstance(content, str) and content.strip():
            return normalize_description_text(content, max_len=2000)
    return None


def _extract_gtin(soup: BeautifulSoup) -> Optional[str]:
    """UPC from the spec table (``<table class="kw-metrics-table">`` row where the
    first ``<td>`` starts with ``"UPC Code"``). Apparel / accessories SKUs skip this
    row; return ``None`` rather than a blank."""
    table = _first_class(soup, "table", "kw-metrics-table")
    if table is None:
        return None
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).lower()
        if "upc" not in label:
            continue
        value = cells[1].get_text(strip=True)
        if value:
            return value
    return None


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """Collect product images from the gallery. The same file is rendered at
    both 256x (thumbnail) and 1920x (lightbox) — we dedupe on filename and
    keep the largest variant we saw per file. Capped at 12."""
    # Map filename → (pixel_width, full_url_with_best_size).
    by_file: dict[str, tuple[int, str]] = {}
    order: List[str] = []

    def _collect(raw: Optional[str]) -> None:
        if not raw:
            return
        for match in _PRODUCT_IMAGE_RE.finditer(raw):
            size_segment = match.group(1)  # e.g. "256x" or "1920x"
            filename = match.group(2)
            size_match = re.match(r"(\d+)", size_segment)
            width = int(size_match.group(1)) if size_match else 0
            existing = by_file.get(filename)
            if existing is None or width > existing[0]:
                by_file[filename] = (width, match.group(0))
                if filename not in order:
                    order.append(filename)

    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-lazy-src", "data-zoom-image"):
            val = img.get(attr)
            if isinstance(val, str):
                _collect(val)

    for source in soup.find_all("source"):
        if not isinstance(source, Tag):
            continue
        for attr in ("srcset", "data-srcset"):
            val = source.get(attr)
            if isinstance(val, str):
                _collect(val)

    urls: List[str] = []
    for filename in order:
        urls.append(by_file[filename][1])
        if len(urls) >= 12:
            break
    return urls


class KWSuspensionsAdapter(RetailerCrawlerAdapter):
    """
    KW Suspensions USA adapter.

    Fetcher tier: ``tls`` — persistent session needed so the ``langselector``
    cookie set by the warm-up request carries through every subsequent fetch.

    Discovery: ``CRAWLER_KWSUSPENSIONS_START_URLS`` wins. Otherwise warm up
    ``/en-us/`` to set cookies, then paginate ``/products.html?p=N`` until
    there is no next-page link.

    Parsing: DOM-only (no JSON-LD / microdata / OG on this Magento theme).
    Brand is always ``KW_BRAND`` — every SKU on the site is KW-made.
    """

    ADAPTER_NAME: ClassVar[str] = "kwsuspensions"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; otherwise walk the catalog."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in self._discover_via_catalog() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def _warmup(self) -> None:
        """One-shot fetch of ``/en-us/`` to set ``langselector=subpage_no_redirect``
        on the TLS session. Best-effort: discovery can still proceed if the
        warm-up fails because the catalog responses carry the same Set-Cookie
        themselves — the first catalog page would then be an empty body and
        we'd recover on page 2."""
        try:
            self.fetcher.fetch(KW_WARMUP_URL, timeout=30)
        except Exception:
            pass

    def _discover_via_catalog(self) -> List[str]:
        """Walk ``/products.html?p=1..`` through the TLS fetcher. Stops when a
        page has no "next" pagination link, when we hit ``MAX_CATALOG_PAGES``,
        or on any fetch failure. Returns the concatenated list of product URLs
        in listing order, deduped."""
        self._warmup()

        seen: set[str] = set()
        product_urls: List[str] = []
        for page in range(1, MAX_CATALOG_PAGES + 1):
            if page > 1:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            url = KW_CATALOG_URL_TEMPLATE.format(page=page)
            try:
                html = self.fetcher.fetch(url, timeout=60)
            except Exception:
                break
            for product_url in _extract_product_links(html):
                if product_url in seen:
                    continue
                seen.add(product_url)
                product_urls.append(product_url)
            if not _has_next_page(html):
                break
        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse a KW product page. Returns ``None`` when the URL is not a
        product page or the DOM is missing the product name (storefront chrome
        or soft 404)."""
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=_extract_description(soup),
            price_cents=_extract_price_cents(soup),
            part_manufacturer=KW_BRAND,
            part_number=_extract_part_number(soup),
            image_urls=_extract_images(soup) or None,
            gtin=_extract_gtin(soup),
        )
