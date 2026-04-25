"""
Tomei USA (products.tomeiusa.com) crawler adapter.

The marketing site at ``www.tomeiusa.com`` is a WordPress brochure; the actual
catalog lives on the PrestaShop subdomain ``products.tomeiusa.com``. This
adapter targets the PrestaShop store.

Product URLs:
``https://products.tomeiusa.com/<category-slug>/<id>-<product-slug>``

The site sits behind CloudFront, which 403s the default crawler User-Agent
even though the underlying HTTP/TLS stack is unremarkable. We use the TLS
fetcher (curl_cffi Chrome impersonation) so the request looks like a real
browser end-to-end; promoting tiers is the codebase's standard fix for
CDN UA / fingerprint blocks (see also: cobbtuning, texasspeed).

The site has no JSON-LD and no ``og:price`` meta. Parsing is DOM-driven from
PrestaShop's tomei-child theme, which renders product specs in a single
``<table>`` keyed by ``<th>`` labels (``parts #``, ``msrp``, ``engine``,
``model``, ``main category``, ``sub category``, etc.).

Discovery: walk the storefront homepage to enumerate every category index
(URL pattern ``/<id>-<slug>``), then each category page to collect product
URLs. Categories are small (~15 items) and the few that paginate use
``?page=N`` — we walk pages until a fetch yields no new product URLs.
Override with ``CRAWLER_TOMEIUSA_START_URLS`` (comma-separated) for a fixed
list (useful in tests / one-off backfills).

Brand: the storefront is first-party — every product is Tomei. We hardcode
``"Tomei"`` so cross-retailer dedupe matches whatever any third-party stockist
emits for the same SKU.
"""

import os
import re
import time
from typing import Callable, ClassVar, Dict, Iterator, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC, ScrapedPayload, apply_delay_jitter
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

TOMEIUSA_BASE = "https://products.tomeiusa.com"

# Storefront is first-party; cross-retailer dedupe joins on this name.
_TOMEI_BRAND = "Tomei"

# PrestaShop category index URL pattern, e.g. /9-oil-lubrication, /62-oil-pump.
# Anchored at start to reject deeper /<slug>/<id>-... product paths.
_CATEGORY_PATH_RE = re.compile(r"^/(\d+)-[a-z0-9-]+/?$", re.IGNORECASE)

# PrestaShop product URL pattern, e.g. /oil-pump/814-oversized-oil-pump-rb26dett-...
_PRODUCT_PATH_RE = re.compile(r"^/[a-z0-9-]+/(\d+)-[a-z0-9-]+/?$", re.IGNORECASE)

# Cap discovery work. The full catalog has ~125 categories; we still want a
# safety stop so a future site change can't put the runner in an infinite loop.
_MAX_CATEGORIES = 200
_MAX_CATEGORY_PAGES = 20  # tomei categories are small but allow growth headroom

# Product spec table rows we want to surface in the description (in display
# order). Other rows (msrp, parts #, shipping size/weight, qty in stock, note)
# are either captured separately or are operational noise.
_DESCRIPTION_ROWS = (
    "engine",
    "model",
    "main category",
    "sub category",
)

DEFAULT_START_URLS = [
    "https://products.tomeiusa.com/oil-pump/814-oversized-oil-pump-rb26dett-rb25det-rb20det",
]

# Type alias for the fetcher closure passed to discovery helpers — lets the
# helpers stay module-level (and unit-testable in isolation) without coupling
# them to the Fetcher class.
_Fetch = Callable[[str], str]


def _strip_query(url: str) -> str:
    """Drop query/fragment so dedupe collapses ``?q=…`` filter variants."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _is_tomeiusa_host(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == "products.tomeiusa.com"


def _is_category_url(url: str) -> bool:
    if not _is_tomeiusa_host(url):
        return False
    path = urlparse(url).path or ""
    return bool(_CATEGORY_PATH_RE.match(path))


def _is_product_url(url: str) -> bool:
    if not _is_tomeiusa_host(url):
        return False
    path = urlparse(url).path or ""
    return bool(_PRODUCT_PATH_RE.match(path))


def _extract_links(html: str, base_url: str, predicate: Callable[[str], bool]) -> List[str]:
    """Absolute, query-stripped, deduped URLs on the page that match ``predicate``."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        absolute = _strip_query(urljoin(base_url, href.strip()))
        if not predicate(absolute) or absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
    return out


def _discover_category_urls(fetch: _Fetch) -> List[str]:
    """All category index URLs reachable from the storefront homepage."""
    try:
        home_html = fetch(TOMEIUSA_BASE + "/")
    except Exception:
        return []
    return _extract_links(home_html, TOMEIUSA_BASE + "/", _is_category_url)[:_MAX_CATEGORIES]


def _discover_products_in_category(fetch: _Fetch, category_url: str) -> List[str]:
    """
    Walk a category, following ``?page=N`` pagination, until a page yields no
    new product URLs. Out-of-range pages on PrestaShop return a 200 response
    rendering the page-not-found template, so the empty-result check is the
    natural termination.
    """
    seen: set[str] = set()
    products: List[str] = []
    for page in range(1, _MAX_CATEGORY_PAGES + 1):
        page_url = category_url if page == 1 else f"{category_url}?page={page}"
        if page > 1:
            time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
        try:
            html = fetch(page_url)
        except Exception:
            break
        new_on_page = 0
        for url in _extract_links(html, page_url, _is_product_url):
            if url in seen:
                continue
            seen.add(url)
            products.append(url)
            new_on_page += 1
        if new_on_page == 0:
            break
    return products


def _discover_product_urls(fetch: _Fetch) -> List[str]:
    seen: set[str] = set()
    products: List[str] = []
    categories = _discover_category_urls(fetch)
    for i, cat_url in enumerate(categories):
        if i > 0:
            time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
        for url in _discover_products_in_category(fetch, cat_url):
            if url in seen:
                continue
            seen.add(url)
            products.append(url)
    return products


def _resolve_start_urls(fetch: _Fetch) -> List[str]:
    raw = os.environ.get("CRAWLER_TOMEIUSA_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls(fetch)
    return urls if urls else list(DEFAULT_START_URLS)


def _spec_table(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Build {label: value} from the product spec ``<table>``. PrestaShop's
    tomei-child theme always renders the product info as a striped two-column
    table inside ``#single__body__main__meta__table``; the wrapper id is the
    most reliable anchor since the page also contains other tables (cart,
    related-product specs).
    """
    out: Dict[str, str] = {}
    wrap = soup.find(id="single__body__main__meta__table")
    if not isinstance(wrap, Tag):
        return out
    for tr in wrap.find_all("tr"):
        if not isinstance(tr, Tag):
            continue
        th = tr.find("th")
        td = tr.find("td")
        if not isinstance(th, Tag) or not isinstance(td, Tag):
            continue
        key = th.get_text(strip=True).lower()
        val = td.get_text(separator=" ", strip=True)
        if key and val:
            out[key] = val
    return out


def _build_description(spec: Dict[str, str]) -> Optional[str]:
    """
    Compose a description from fitment-relevant spec rows. Tomei ships almost
    no narrative copy on product pages, but the spec table carries the
    information shoppers need (engine and chassis fitment).
    """
    parts: List[str] = []
    for key in _DESCRIPTION_ROWS:
        val = spec.get(key)
        if not val:
            continue
        parts.append(f"{key.title()}: {val}")
    if not parts:
        return None
    return normalize_description_text(". ".join(parts))


_THUMB_LARGE_ATTRS = ("data-image-large-src", "data-image-medium-src")


def _absolute(url: str) -> Optional[str]:
    if not url:
        return None
    s = url.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = TOMEIUSA_BASE + s
    return s if s.startswith("http") else None


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Gallery URLs from the product image carousel. PrestaShop's default theme
    emits each thumbnail with ``data-image-large-src`` pointing at the
    full-resolution variant — that is what we want to store. Falls back to
    ``og:image`` when the carousel is missing (single-image products).
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(candidate: Optional[str]) -> None:
        absolute = _absolute(candidate or "")
        if not absolute or absolute in seen:
            return
        seen.add(absolute)
        ordered.append(absolute)

    gallery = soup.find("ul", class_="js-qv-product-images") or soup.find("ul", class_="product-images")
    if isinstance(gallery, Tag):
        for img in gallery.find_all("img"):
            if not isinstance(img, Tag):
                continue
            for attr in _THUMB_LARGE_ATTRS:
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break

    if not ordered:
        og = soup.find("meta", property="og:image")
        if isinstance(og, Tag):
            add(meta_content(og))

    return ordered[:12]


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    h1 = soup.find("h1", attrs={"itemprop": "name"}) or soup.find("h1", class_="h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    og = soup.find("meta", property="og:title")
    if isinstance(og, Tag):
        title = meta_content(og)
        if title and title.strip():
            return title.strip()
    return None


class TomeiUsaAdapter(RetailerCrawlerAdapter):
    """
    Tomei USA adapter. Discovery: storefront homepage → category indexes →
    paginated product lists. Parsing: DOM-only against PrestaShop's
    tomei-child theme (no JSON-LD, no useful Open Graph price/description).

    TLS tier: CloudFront in front of products.tomeiusa.com 403s the default
    crawler UA; curl_cffi Chrome impersonation gets through.
    """

    ADAPTER_NAME: ClassVar[str] = "tomeiusa"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from the PrestaShop storefront. Set
        ``CRAWLER_TOMEIUSA_START_URLS`` (comma-separated) to override.
        """

        def fetch(url: str) -> str:
            return self.fetcher.fetch(url, timeout=15)

        for url in _resolve_start_urls(fetch):
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Tomei product page. Returns ``None`` when no product name is
        found (category listing, 404 served as 200, etc.).
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 2:
            return None

        spec = _spec_table(soup)
        part_number = normalize_part_number(spec.get("parts #"))
        # MSRP is the only price the storefront publishes (catalog-only,
        # no cart pricing); store it as the listing price.
        price_cents = parse_price_cents(spec.get("msrp", ""))
        description = _build_description(spec)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=_strip_query(url),
            description=description,
            price_cents=price_cents,
            part_manufacturer=_TOMEI_BRAND,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
