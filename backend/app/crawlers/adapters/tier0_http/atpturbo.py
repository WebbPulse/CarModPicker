"""
ATP Turbo (atpturbo.com) crawler adapter.

ATP (Advanced Tuning Products) is the de-facto distributor for Garrett
aftermarket turbos, stocking the Gen2, G-Series, and GTX lineups plus
Precision / BorgWarner hardware and full turbo kits for Mazdaspeed, Evo,
STI, GTI, and 350Z/G35. Anchors the forced-induction retail tier
alongside Full-Race; where Full-Race leads with house-brand manifolds,
ATP leads with OEM-Garrett cartridges, so the two catalogs complement
rather than overlap.

Site platform: **Miva Merchant 5**, late-2000s-vintage custom theme. All
catalog URLs live under ``/mm5/merchant.mvc`` with a ``Screen`` query
param: ``PROD`` for products, ``CTGY`` for category indexes, ``SFNT``
for the catalog home. Product URLs look like
``/mm5/merchant.mvc?Screen=PROD&Store_Code=tp&Product_Code=GRT-TBO-562``.
There is no JSON-LD, no OpenGraph, no sitemap, and no robots.txt — the
site predates all of them. Pages declare ``charset=WINDOWS-1252`` which
is effectively Latin-1 for the catalog data we care about.

Discovery: no sitemap. We BFS the category tree from ``/mm5/`` (catalog
home), collecting ``Product_Code`` hidden-input values and following
``Category_Code`` subcategory links. Categories have no pagination — each
index page lists every product in that branch. BFS is capped at 500
categories and 5000 products to bound runtime; the catalog has roughly
3000 products today.

Parsing: DOM-only. The **URL's ``Product_Code`` param is the MPN** — it
matches the value printed as ``Code: <b>…</b>`` on the page, and unlike
the page DOM (which contains multiple ``Product_Code`` hidden inputs,
one per related-product quick-buy form), the URL param is unambiguous.
Title is the ``<title>`` minus the ``: atpturbo.com`` suffix; price is
``<span id="price-value">$X</span>``; description is the text of
``<div class="product_display">`` with the inner add-to-cart block
stripped out (BS4's ``extract()``); images come from
``<img id="ProductMainImage">`` resolved against the ``<base href>`` of
``/mm5/``.

Brand attribution: ATP's product codes encode the manufacturer as a
fixed prefix — ``GRT-*`` = Garrett, ``ATP-*`` = ATP's own house SKU,
``PRE-*`` = Precision, ``BW-*`` = BorgWarner, ``TIAL-*`` = TiAL,
``MIA-*`` = Mishimoto. We map the prefix first; unknown prefixes fall
back to title-token heuristics so a new brand doesn't orphan.

404: missing Miva products return a 200 with ``<title>atpturbo.com :
Not Found</title>``. We reject that title plus any page lacking a
Product_Code query param (category URLs handed to the parser by mistake).
"""

import os
import re
from collections import deque
from typing import Callable, ClassVar, Deque, Iterator, List, Optional, Set
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_title,
)

ATPTURBO_HOST = "www.atpturbo.com"
ATPTURBO_BASE = f"https://{ATPTURBO_HOST}"
ATPTURBO_MM5_BASE = f"{ATPTURBO_BASE}/mm5/"
ATPTURBO_MERCHANT_PATH = "/mm5/merchant.mvc"
ATPTURBO_STORE_CODE = "tp"

# Catalog home — first hop of BFS. Exposes every top-level category
# (Turbos, Intercoolers, Wastegates, BOVs, Flanges, etc.) in the left nav.
ATPTURBO_CATALOG_HOME = f"{ATPTURBO_BASE}/mm5/"

# House brand: ATP-*** product codes are ATP's own fabricated parts
# (flanges, oil lines, fittings). Non-ATP prefixes carry the real
# manufacturer — see ``_PART_CODE_BRAND_PREFIXES``.
ATPTURBO_HOUSE_BRAND = "ATP Turbo"

# Product-code prefix → manufacturer. ATP's codes are stable and encode
# the brand as the first dash-delimited token — far more reliable than
# title parsing, since ATP's titles frequently omit the brand name
# entirely for Garrett parts ("GEN2 GTX3071R Turbo") once they're deep
# in a Garrett-tagged category tree.
_PART_CODE_BRAND_PREFIXES: dict[str, str] = {
    "ATP": ATPTURBO_HOUSE_BRAND,
    "GRT": "Garrett",
    "PRE": "Precision",
    "BW": "BorgWarner",
    "TIAL": "TiAL",
    "MIA": "Mishimoto",
    "TRE": "Treadstone",
    "GFB": "GFB",
    "HKS": "HKS",
    "TRB": "Turbosmart",
    "TS": "Turbosmart",
    "AEM": "AEM",
    "PW": "Precision",
    "FP": "Forced Performance",
}

# Miva Merchant "not found" title — the 404 is served with a 200 OK and
# the full site chrome, so the only reliable tell is the <title>.
_NOT_FOUND_TITLE_RE = re.compile(r"\batpturbo\.com\s*:\s*Not\s*Found\b", re.IGNORECASE)

# Title suffix stripped before emitting the product name. Miva appends
# "<separator> <site>" to every page title — strip the last ": atpturbo.com".
_TITLE_SUFFIX_RE = re.compile(r"\s*:\s*atpturbo\.com\s*$", re.IGNORECASE)

# BFS caps. ATP's catalog is ~3000 products across ~300 categories
# today; the limits are sized for 2x growth headroom, with the category
# cap bounding latency when the runner is pointed at ATP from cold cache.
_MAX_CATEGORIES = 500
_MAX_PRODUCTS = 5000

# Category codes we don't want to walk — NEW / latest / announcements
# land in the catalog-home nav but duplicate products already reachable
# via the product-type trees. Skipping keeps the BFS tighter and avoids
# double-visiting the same Product_Code hundreds of times.
_SKIP_CATEGORY_CODES = frozenset(
    {
        "NEW",
        "NEWGARRETT",
        "BAR",  # "Turbo Specials" — overlaps other trees
    }
)

DEFAULT_START_URLS = [
    f"{ATPTURBO_BASE}{ATPTURBO_MERCHANT_PATH}" "?Screen=PROD&Store_Code=tp&Product_Code=GRT-TBO-562",
]

_Fetch = Callable[[str], str]


def _is_atpturbo_host(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == ATPTURBO_HOST or host == "atpturbo.com"


def _query_param(url: str, key: str) -> Optional[str]:
    """Return a single-valued query-param from ``url`` (case-insensitive key)."""
    try:
        qs = parse_qs(urlparse(url).query, keep_blank_values=False)
    except ValueError:
        return None
    lowered = {k.lower(): v for k, v in qs.items()}
    values = lowered.get(key.lower())
    if not values:
        return None
    return values[0]


def _is_product_url(url: str) -> bool:
    """True if ``url`` targets Miva's PROD screen with a Product_Code."""
    if not _is_atpturbo_host(url):
        return False
    parsed = urlparse(url)
    if parsed.path.lower() != ATPTURBO_MERCHANT_PATH:
        return False
    screen = _query_param(url, "Screen")
    if not screen or screen.upper() != "PROD":
        return False
    return bool(_query_param(url, "Product_Code"))


def _is_category_url(url: str) -> bool:
    """True if ``url`` targets Miva's CTGY screen with a Category_Code."""
    if not _is_atpturbo_host(url):
        return False
    parsed = urlparse(url)
    if parsed.path.lower() != ATPTURBO_MERCHANT_PATH:
        return False
    screen = _query_param(url, "Screen")
    if not screen or screen.upper() != "CTGY":
        return False
    return bool(_query_param(url, "Category_Code"))


def _canonical_product_url(code: str) -> str:
    """Build the canonical PROD URL for ``code`` so dedupe keys off one shape."""
    return (
        f"{ATPTURBO_BASE}{ATPTURBO_MERCHANT_PATH}" f"?Screen=PROD&Store_Code={ATPTURBO_STORE_CODE}&Product_Code={code}"
    )


def _canonical_category_url(code: str) -> str:
    return (
        f"{ATPTURBO_BASE}{ATPTURBO_MERCHANT_PATH}" f"?Screen=CTGY&Store_Code={ATPTURBO_STORE_CODE}&Category_Code={code}"
    )


def _strip_fragment(url: str) -> str:
    """Drop the #fragment so ``?Category_Code=X#top`` and ``?Category_Code=X`` dedupe."""
    try:
        p = urlparse(url)
    except ValueError:
        return url
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def _extract_codes_on_page(html_text: str, base_url: str) -> tuple[List[str], List[str]]:
    """
    Return ``(product_codes, category_codes)`` discovered on ``html_text``.

    Categories and products are always referenced by their ``_Code`` query
    param — the canonical URL shape we care about. We parse hrefs rather
    than scraping ``Product_Code`` hidden inputs directly because every
    related-product quick-buy block on a product page also emits a hidden
    Product_Code input; the ``<a href>`` form is scoped to the actual
    anchor the user would click.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    product_codes: List[str] = []
    category_codes: List[str] = []
    seen_products: Set[str] = set()
    seen_categories: Set[str] = set()

    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        absolute = _strip_fragment(urljoin(base_url, href.strip()))
        if not _is_atpturbo_host(absolute):
            continue

        if _is_product_url(absolute):
            code = _query_param(absolute, "Product_Code")
            if code and code not in seen_products:
                seen_products.add(code)
                product_codes.append(code)
            continue

        if _is_category_url(absolute):
            code = _query_param(absolute, "Category_Code")
            if code and code not in seen_categories:
                seen_categories.add(code)
                category_codes.append(code)

    return product_codes, category_codes


def _discover_via_bfs(fetch: _Fetch) -> List[str]:
    """
    BFS the category tree from the catalog home. Returns a deduped list of
    canonical product URLs. Empty on initial-fetch failure.

    The walk is intentionally breadth-first so a crash partway produces a
    broad sample of the catalog rather than exhausting one tree. Category
    visits are capped at ``_MAX_CATEGORIES`` and product collection at
    ``_MAX_PRODUCTS`` to bound runtime; per-fetch failures log-and-skip so
    one broken subcategory doesn't halt the discovery.
    """
    try:
        home_html = fetch(ATPTURBO_CATALOG_HOME)
    except Exception:
        return []

    _, root_categories = _extract_codes_on_page(home_html, ATPTURBO_CATALOG_HOME)

    visited_categories: Set[str] = set()
    visited_products: Set[str] = set()
    product_urls: List[str] = []
    queue: Deque[str] = deque()

    for code in root_categories:
        if code in _SKIP_CATEGORY_CODES or code in visited_categories:
            continue
        visited_categories.add(code)
        queue.append(code)

    while queue and len(visited_categories) <= _MAX_CATEGORIES and len(product_urls) < _MAX_PRODUCTS:
        code = queue.popleft()
        cat_url = _canonical_category_url(code)
        try:
            cat_html = fetch(cat_url)
        except Exception:
            continue

        products_on_page, subcategories = _extract_codes_on_page(cat_html, cat_url)

        for p_code in products_on_page:
            if p_code in visited_products:
                continue
            visited_products.add(p_code)
            product_urls.append(_canonical_product_url(p_code))
            if len(product_urls) >= _MAX_PRODUCTS:
                break

        for sub in subcategories:
            if sub in _SKIP_CATEGORY_CODES or sub in visited_categories:
                continue
            if len(visited_categories) >= _MAX_CATEGORIES:
                break
            visited_categories.add(sub)
            queue.append(sub)

    return product_urls


def _resolve_start_urls(fetch: _Fetch) -> List[str]:
    """Env override wins; otherwise BFS-discover; fallback seed."""
    raw = os.environ.get("CRAWLER_ATPTURBO_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_via_bfs(fetch)
    return urls if urls else list(DEFAULT_START_URLS)


def _is_not_found_page(soup: BeautifulSoup) -> bool:
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return False
    text = title_tag.get_text(strip=True)
    return bool(_NOT_FOUND_TITLE_RE.search(text))


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Return the page title with the ``: atpturbo.com`` suffix removed."""
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    text = title_tag.get_text(strip=True)
    if not text:
        return None
    cleaned = _TITLE_SUFFIX_RE.sub("", text).strip()
    return cleaned or None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """Price is always in ``<span id="price-value">$X.YZ</span>``."""
    tag = soup.find(id="price-value")
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(strip=True)
    if not text:
        return None
    return parse_price_cents(text)


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    The description block is the ``<div class="product_display">`` element
    rendered below the main image (there are two ``product_display``
    elements on a PDP — an outer ``<span>`` wrapping image+form and an
    inner ``<div>`` with the long-form text copy). We pick the ``<div>``
    and strip nested ``<style>``, ``<script>``, and embedded related-
    product forms so only the descriptive body ends up in the payload.
    """
    candidate: Optional[Tag] = None
    for node in soup.find_all("div", class_="product_display"):
        if isinstance(node, Tag):
            candidate = node
            break
    if candidate is None:
        return None

    # BeautifulSoup returns a new tree from the copy so we don't mutate
    # the caller's soup when stripping noise nodes.
    working = BeautifulSoup(str(candidate), "html.parser")
    for drop in working.find_all(["script", "style", "form", "noscript"]):
        drop.decompose()

    raw = working.get_text(" ", strip=True)
    return normalize_description_text(raw, max_len=2000)


def _extract_image_urls(soup: BeautifulSoup) -> List[str]:
    """
    ATP uses exactly one main image per PDP (``<img id="ProductMainImage">``)
    and a handful of embedded reference / chart images inline in the copy.
    The main image is relative to the ``<base href="/mm5/">`` so we always
    resolve against ``/mm5/`` before returning. Returns a singleton list
    or empty — multi-image galleries don't exist on this platform.
    """
    hero = soup.find(id="ProductMainImage")
    if not isinstance(hero, Tag):
        return []
    src = hero.get("src")
    if not isinstance(src, str) or not src.strip():
        return []
    absolute = urljoin(ATPTURBO_MM5_BASE, src.strip())
    if not absolute.lower().startswith("http"):
        return []
    return [absolute]


def _resolve_part_manufacturer(part_number: Optional[str], title: str) -> Optional[str]:
    """
    Prefer the product-code prefix (stable, machine-curated) over title
    parsing. Title tokens are a fallback for codes with an unknown prefix
    and for the handful of house-keyed codes that don't follow the
    brand-prefix convention.
    """
    if part_number:
        prefix = part_number.split("-", 1)[0].upper()
        brand = _PART_CODE_BRAND_PREFIXES.get(prefix)
        if brand:
            return brand
    brand = part_manufacturer_from_title(title)
    if brand:
        return brand
    return part_manufacturer_fallback_from_title(title)


class ATPTurboAdapter(RetailerCrawlerAdapter):
    """
    ATP Turbo adapter — Miva Merchant storefront, BFS discovery, DOM parsing.

    Fetcher tier: ``http`` — the origin is plain nginx, no CDN or TLS
    fingerprint challenge. If ATP ever fronts with Cloudflare, promote
    ``FETCHER_TIER`` to ``"tls"``.

    Discovery: BFS from ``/mm5/`` (catalog home) through all
    ``Category_Code`` subcategories, collecting ``Product_Code`` values
    from ``<a href>``. Bounded by ``_MAX_CATEGORIES`` / ``_MAX_PRODUCTS``.
    Override with ``CRAWLER_ATPTURBO_START_URLS`` (comma-separated).

    Parsing: DOM-only. The URL's ``Product_Code`` query param is the
    authoritative MPN (matches ``Code: <b>…</b>`` on page). Title is the
    ``<title>`` with ``: atpturbo.com`` stripped. Price is
    ``#price-value``. Description is ``div.product_display`` with
    scripts / styles / embedded related-product forms removed. Image is
    ``#ProductMainImage`` resolved against the page's ``<base href>`` of
    ``/mm5/``. Manufacturer is derived from the product-code prefix
    (``GRT-`` → Garrett, ``ATP-`` → ATP Turbo, etc.) with title-token
    fallback for unknown prefixes.
    """

    ADAPTER_NAME: ClassVar[str] = "atpturbo"
    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from BFS discovery; env override wins when set."""

        def fetch(url: str) -> str:
            return self.fetcher.fetch(url, timeout=30)

        for url in _resolve_start_urls(fetch):
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an ATP Turbo PDP. Returns None when the URL is missing a
        Product_Code (category page handed to the parser), when the page
        is a Miva 404 (200 status, "Not Found" title), or when no title
        can be extracted.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        if _is_not_found_page(soup):
            return None

        title = _extract_title(soup)
        if not title or len(title) < 3:
            return None

        code_from_url = _query_param(url, "Product_Code")
        part_number = normalize_part_number(code_from_url) if code_from_url else None

        price_cents = _extract_price_cents(soup)
        description = _extract_description(soup)
        image_urls = _extract_image_urls(soup)
        part_manufacturer = _resolve_part_manufacturer(part_number, title)

        return ScrapedPayload(
            name=title,
            product_url=_canonical_product_url(code_from_url) if code_from_url else url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
