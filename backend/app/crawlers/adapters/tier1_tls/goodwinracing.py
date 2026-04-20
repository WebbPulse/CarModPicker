"""
Good-Win Racing (good-win-racing.com) crawler adapter — Tier 1 (TLS).

Second-vendor Miata coverage alongside Flyin' Miata. Good-Win's ND-era
catalog (and the Fiat 124 / BRZ-86 crossover lines they resell) overlaps
FM only partially, so landing them closes the "three comparable sources"
gap on the Miata platform. See ``adapters/RETAILER_BACKLOG.md``.

Product URLs: ``https://www.good-win-racing.com/Mazda-Performance-Part/<sku>.html``

The URL path is **singular** — ``/Mazda-Performance-Part/``. The plural
form ``/Mazda-Performance-Parts/<chassis>/<category>[/<sub>].html`` is
the category / browse shape and must NOT enter the parse pipeline. The
SKU segment mixes hyphens, digits, and letters (e.g. ``61-3447``,
``13-1063``, ``BB1221``, ``GWR-031``); the regex allows any of those.

Both ``good-win-racing.com`` and ``www.good-win-racing.com`` are
accepted. The bare host 302-redirects to the www host, but the Chrome
extension may capture either one.

Fetcher tier: ``tls``. The site is fronted by Cloudflare with a managed
challenge that returns a ``Just a moment...`` interstitial for plain
``requests`` and plain ``curl`` (browser UA included). ``curl_cffi`` with
``impersonate="chrome"`` clears both the sitemap and every product /
category fetch — the block is client-fingerprint-based, not IP- or
cookie-based, so no warm-up or JS challenge solve is needed. If the
protection tightens to a JS-challenge form, promote ``FETCHER_TIER`` to
``"browser"`` without touching the parser.

Platform: a classic Interchange (Akopia / Red Hat) storefront — the
``mv_session_id`` / ``mv_todo`` / ``mv_nextpage`` hidden fields and the
``/ord/basket.html`` checkout path are the giveaway. The theme is older
but every product page emits a well-formed ``<script type=
"application/ld+json">`` ``Product`` block with ``sku``, ``name``,
``description``, ``brand.name``, ``image``, and ``offers.price`` in USD.
That alone covers the payload — no fallback parsing has been needed in
live sampling. A minimal DOM fallback (``img#mainimage`` + ``<h1>`` +
meta description) is still implemented for defense in depth, since the
theme does vary slightly across vehicle lines.

Brand policy: Good-Win is a reseller across many manufacturer lines
(DBA, EBC, Koyo, ACT, Competition Clutch, Sparco, RoadsterSport,
Jackson Racing, …) and also ships a small amount of own-branded gear
under ``GWR-``-prefixed SKUs. The JSON-LD ``brand.name`` reliably
carries the real manufacturer in either case, so no static default or
vendor-variant collapse is applied — we pass ``brand.name`` through and
let cross-retailer dedupe on ``(manufacturer, part_number)`` work off
the actual brand.

Discovery: ``/sitemap.xml`` is a flat urlset (not an index) listing
~4000 URLs dominated by ``/mazda/miata/gallerycar/...`` photo pages.
The product-bearing URLs in the sitemap are the category browse pages
at ``/Mazda-Performance-Parts/<chassis>/<category>[/<sub>].html``
(despite the path prefix, this segment covers every chassis — BRZ/86,
Fiat 124, Ridgeline, Maverick, Rivian, MINI, etc., not just Mazda).
Top-level depth-3 category pages (``/Miata/Brakes.html``) only link to
sub-categories, so we walk every ``/Mazda-Performance-Parts/*`` URL in
the sitemap indiscriminately and extract singular ``/Mazda-Performance-
Part/<sku>.html`` links from each. Depth-3 pages return zero products;
that's a cheap no-op. Override with ``CRAWLER_GOODWINRACING_START_URLS``
(comma-separated) for ad-hoc runs.

robots.txt: disallows admin / login / review / order / gift-certificate
/ captcha / scan paths. None of those intersect with product or
category URLs. No ``Crawl-delay`` directive.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    extract_json_ld_product,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    scraped_payload_from_json_ld,
)

GOODWIN_HOST = "www.good-win-racing.com"
GOODWIN_BASE = f"https://{GOODWIN_HOST}"
SITEMAP_URL = f"{GOODWIN_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Category browse pages. The plural path prefix. Used to filter the
# sitemap urlset down to URLs worth walking for product-link extraction.
CATEGORY_PATH_PREFIX = "/Mazda-Performance-Parts/"

# Singular product URL segment. Note the trailing slash: we match it
# exactly so the plural ``/Mazda-Performance-Parts/…`` URLs can't leak
# through the product-shape gate.
PRODUCT_PATH_PREFIX = "/Mazda-Performance-Part/"

# Canonical product URL: ``/Mazda-Performance-Part/<sku>.html``. SKUs in
# the live catalog span hyphenated numerics (``61-3447``, ``13-1063``),
# letter-prefixed codes (``BB1221``, ``GWR-031``, ``VH060650``), and
# pure numerics. The character class stays permissive so unfamiliar SKU
# shapes don't silently drop.
_PRODUCT_PATH_RE = re.compile(r"^/Mazda-Performance-Part/[A-Za-z0-9][A-Za-z0-9\-_]*\.html$")

# Extracts ``/Mazda-Performance-Part/<sku>.html`` hrefs from category
# HTML. The trailing query string (``?id=<session>``) is common on this
# Interchange theme and is stripped by the capture group boundary —
# ``base`` below pulls the URL before ``?``.
_PRODUCT_LINK_RE = re.compile(
    r'href=["\']([^"\']*?/Mazda-Performance-Part/[A-Za-z0-9][A-Za-z0-9\-_]*\.html)',
    re.IGNORECASE,
)

# Fallback gallery image on the product page. The Interchange theme
# always renders the hero photo as ``<img id="mainimage" src="/images/
# items/485x485/<file>.webp">``. Related-product tiles below it use
# ``data-src="/images/items/300x300/…"`` for lazy loading and must NOT
# be picked up as gallery entries — they belong to other SKUs.
_MAIN_IMAGE_ID = "mainimage"

# Smoke-test seed. 61-3447 is a current DBA XP pad with a clean JSON-LD
# block and an in-stock $89 price — exercises the primary parse path.
DEFAULT_START_URLS = [
    "https://www.good-win-racing.com/Mazda-Performance-Part/61-3447.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a Good-Win product SKU page (``/Mazda-Performance-Part/<sku>.html``).

    Accepts both ``www.good-win-racing.com`` and the bare host. Rejects
    the plural category path prefix, anything off-host, and anything
    that doesn't match the SKU shape.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "good-win-racing.com" and not host.endswith(".good-win-racing.com"):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _is_category_url(url: str) -> bool:
    """True if ``url`` is a ``/Mazda-Performance-Parts/...`` category browse page on the host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "good-win-racing.com" and not host.endswith(".good-win-racing.com"):
        return False
    return (parsed.path or "").startswith(CATEGORY_PATH_PREFIX)


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_GOODWINRACING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_GOODWINRACING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_product_links(html: str) -> List[str]:
    """
    Pull ``/Mazda-Performance-Part/<sku>.html`` hrefs from a category
    listing page. Both absolute (``https://www.good-win-racing.com/...``)
    and site-root (``/...``) forms appear; we normalize everything to
    the absolute www-host form, strip query strings (``?id=<session>``),
    and dedupe in document order.
    """
    seen: set[str] = set()
    out: List[str] = []
    for match in _PRODUCT_LINK_RE.finditer(html):
        raw = match.group(1)
        # Strip protocol+host if present so we can rebuild under the canonical host.
        path_only = raw
        if raw.startswith("http"):
            try:
                parsed = urlparse(raw)
            except ValueError:
                continue
            path_only = parsed.path or ""
        if not path_only.startswith(PRODUCT_PATH_PREFIX):
            continue
        # Strip anything after the .html (query / fragment).
        base_path = path_only.split("?", 1)[0].split("#", 1)[0]
        url = GOODWIN_BASE + base_path
        if not _is_product_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(url)
    return out


class GoodWinRacingAdapter(RetailerCrawlerAdapter):
    """
    Good-Win Racing adapter.

    Fetcher tier: ``tls``. Cloudflare returns a ``Just a moment...``
    managed-challenge interstitial for plain HTTP and plain curl with
    browser UA; ``curl_cffi`` Chrome impersonation clears it for
    sitemap + category + product fetches alike.

    Discovery: ``CRAWLER_GOODWINRACING_START_URLS`` env override wins.
    Otherwise fetch ``/sitemap.xml`` (a flat urlset) through the TLS
    fetcher, filter to ``/Mazda-Performance-Parts/*`` category URLs,
    fetch each one, and harvest ``/Mazda-Performance-Part/<sku>.html``
    links. Categories are walked in sitemap order with per-request
    jitter to match the global crawl policy.

    Parsing: JSON-LD ``Product`` is authoritative — every product page
    emits a block with ``name``, ``sku``, ``brand.name``, ``description``,
    ``image``, and ``offers.price`` in USD. A minimal DOM fallback
    (``img#mainimage``, ``<h1>``, ``<meta name=description>``) covers
    pages where the JSON-LD block is missing or malformed. Brand is
    passed through unchanged — Good-Win is a multi-line reseller and
    the JSON-LD brand reliably names the real manufacturer.
    """

    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; otherwise walk sitemap + categories."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in self._discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def _discover_via_sitemap(self) -> List[str]:
        """
        Fetch ``/sitemap.xml`` through the TLS fetcher, pick out every
        ``/Mazda-Performance-Parts/*`` category URL, fetch each, and
        return the concatenated list of product URLs in sitemap order
        (deduped). Empty list on fetch / parse failure at the sitemap
        level; per-category failures are swallowed individually.
        """
        try:
            xml_text = self.fetcher.fetch(SITEMAP_URL, timeout=30)
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        category_urls: List[str] = []
        seen_cats: set[str] = set()
        for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
            if not loc.text:
                continue
            u = loc.text.strip()
            if not _is_category_url(u):
                continue
            # Strip query string so ``?id=<session>``-tagged mirror
            # entries collapse to a single fetch.
            base = u.split("?", 1)[0]
            if base in seen_cats:
                continue
            seen_cats.add(base)
            category_urls.append(base)

        product_urls: List[str] = []
        seen_products: set[str] = set()
        for idx, cat_url in enumerate(category_urls):
            if idx > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                cat_html = self.fetcher.fetch(cat_url, timeout=30)
            except Exception:
                continue
            for product_url in _extract_product_links(cat_html):
                if product_url in seen_products:
                    continue
                seen_products.add(product_url)
                product_urls.append(product_url)

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Good-Win product page. Returns ``None`` when the URL is
        not product-shaped or when neither JSON-LD nor the DOM fallback
        yields a usable name (soft-404, broken listing, or a category
        page captured by mistake).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        item = extract_json_ld_product(html)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                # JSON-LD already wins on image(s); only seed a DOM image
                # when the block omitted an ``image`` field entirely.
                image_urls = payload.image_urls
                if not image_urls:
                    dom_image = _extract_main_image(soup)
                    image_urls = [dom_image] if dom_image else None

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=payload.price_cents,
                    part_manufacturer=payload.part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # DOM fallback: theme ships an ``<h1>`` with the product name
        # and an ``img#mainimage`` hero. Description falls back to the
        # meta description, which on this theme is ``"<Category>: <Sub>:
        # <Fitment> - Price: $X"`` — not rich, but better than empty for
        # soft-404 recovery.
        name = _extract_dom_name(soup)
        if not name or len(name) < 3:
            return None

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=_extract_dom_description(soup),
            price_cents=_extract_dom_price_cents(soup),
            part_manufacturer=None,
            part_number=None,
            image_urls=_extract_dom_image_list(soup),
        )


def _extract_dom_name(soup: BeautifulSoup) -> Optional[str]:
    """First ``<h1>`` text, stripped. The Interchange theme wraps it in
    ``<span class="matrix_description">…</span>``; ``get_text`` flattens it."""
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_main_image(soup: BeautifulSoup) -> Optional[str]:
    """Return ``img#mainimage`` src, resolved to an absolute URL, or None."""
    img = soup.find("img", id=_MAIN_IMAGE_ID)
    if not isinstance(img, Tag):
        return None
    src = img.get("src")
    if not isinstance(src, str) or not src.strip():
        return None
    return _resolve_image_url(src.strip())


def _extract_dom_image_list(soup: BeautifulSoup) -> Optional[List[str]]:
    """Single-element list wrapping ``img#mainimage``, or None when absent."""
    url = _extract_main_image(soup)
    return [url] if url else None


def _resolve_image_url(raw: str) -> str:
    """Upgrade ``//`` and root-relative URLs to the canonical https host."""
    if raw.startswith("//"):
        return "https:" + raw
    if raw.startswith("/"):
        return GOODWIN_BASE + raw
    return raw


def _extract_dom_description(soup: BeautifulSoup) -> Optional[str]:
    """``<meta name=description>`` — the only description-like node the theme
    ships when JSON-LD is missing. Short and SEO-shaped but non-empty."""
    meta = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta, Tag):
        content = meta_content(meta)
        if content and content.strip():
            return normalize_description_text(content, max_len=2000)
    return None


def _extract_dom_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    Pull a price from the DOM when JSON-LD is unavailable. The theme
    surfaces the current price inside ``<h5 class="price">$X</h5>`` on
    the product view; we ignore ``.retail_price`` (MSRP / strike-through)
    so the returned value reflects what the shopper actually pays.
    """
    price_tag = soup.find("h5", class_="price")
    if isinstance(price_tag, Tag):
        text = price_tag.get_text(strip=True)
        if text:
            cents = parse_price_cents(text)
            if cents is not None:
                return cents
    return None
