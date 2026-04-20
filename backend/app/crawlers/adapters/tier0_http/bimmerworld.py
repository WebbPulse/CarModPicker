"""
Bimmerworld (bimmerworld.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://www.bimmerworld.com/<Category>/[<Sub>/]<Slug>.html``

Bimmerworld is a NetSuite SuiteCommerce storefront (compid ``3750282``;
images served from ``/core/media/media.nl?id=...``). Plain ``requests`` with
the crawler User-Agent loads ``robots.txt``, ``/sitemap.xml`` (which 301s to
``/Sitemap-https.xml``), the homepage and product pages all with HTTP 200,
so this adapter sits at the Tier-0 plain-HTTP level. Override the discovery
list with ``CRAWLER_BIMMERWORLD_START_URLS``.

Discovery: ``/sitemap.xml`` is a single flat urlset (~5.5MB, ~34K product
URLs). Product URLs end with ``.html``; category, "About", and other CMS
URLs end with ``/`` and are filtered out.

Parsing: Bimmerworld's JSON-LD ``Product`` block is built **client-side** —
the static HTML emits an empty ``<script id="dynamicJSONLD">`` and a jQuery
``ready()`` handler populates it from page state. We can't run JS, so the
adapter pulls product data from where the JS reads it from:

- Name: ``<span id="productName">`` (hidden span used by the JSON-LD builder).
- Description: ``#tabs-1 .tab-content1`` (the "Description" tab — full copy
  with feature bullets and BMW fitments). Falls back to ``<span id=
  "productDescription">`` (the short blurb), then og:description.
- Price: ``<span id="priceDisplay">`` (e.g. ``$3,959.46``).
- Image: og:image first, then every ``data-zoom`` on ``.product-image-slider
  .slide`` (the highest-quality variant exposed in the gallery). NetSuite
  ``media.nl`` URLs are deduped by their ``id`` query param so resized
  variants of the same photo collapse to one entry.
- Brand and itemid (Bimmerworld's MPN-equivalent): pulled by regex from the
  inline ``<script>`` that defines ``var brand="..."`` and ``var itemid=
  "..."``. The same script computes ``mpn = "" || itemid`` — Bimmerworld
  treats ``itemid`` (e.g. ``83.154.6800``) as the canonical part number for
  every product they sell, including third-party SKUs whose true MPN is not
  surfaced anywhere on the page. Storing it as ``part_number`` follows
  Bimmerworld's own JSON-LD shape; cross-retailer dedup on ``(manufacturer,
  part_number)`` will work for house BimmerWorld items but won't match a
  third-party site's view of the same StopTech / Brembo / etc. SKU.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import parse_qs, urlparse
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

BIMMERWORLD_BASE = "https://www.bimmerworld.com"
SITEMAP_URL = BIMMERWORLD_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Product URL shape: lives anywhere under the site root and ends with ``.html``.
# Category, "About", and other CMS URLs end with ``/`` (no extension), so the
# extension is the only structural separator.
_PRODUCT_PATH_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9_\-/]*\.html$")

# CMS / cart / account paths that occasionally end in ``.html`` and would
# otherwise pass the shape guard. Bimmerworld's main offenders are gift-card
# and wishlist pages.
_NON_PRODUCT_PATH_RE = re.compile(
    r"^/(" r"Gift-Certificate|Wishlist|cart|checkout|login|register|search" r")(/|\.html)?$",
    re.IGNORECASE,
)

# The inline ``<script>`` that builds the dynamic JSON-LD reads these vars from
# page state. Capturing them is the cheapest way to get an authoritative brand /
# part number without re-running the JS.
_JS_VAR_RE = {
    "itemid": re.compile(r'\bvar\s+itemid\s*=\s*"([^"]*)"\s*;'),
    "brand": re.compile(r'\bvar\s+brand\s*=\s*"([^"]*)"\s*;'),
    "mpn": re.compile(r'\bvar\s+mpn\s*=\s*"([^"]*)"\s*\|\|\s*itemid\s*;'),
}

# Fallback ``itemid`` source: the static <meta name="description"> always
# starts with ``"This is BMW parts item <ID> described as ..."`` — useful
# when the inline-script regex misses (theme tweak, minified bundle, etc.).
_META_DESC_ITEMID_RE = re.compile(r"BMW parts item\s+([A-Za-z0-9][A-Za-z0-9\.\-_/]+)")

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://www.bimmerworld.com/Brakes/StopTech-ST60-380-Big-Brake-Kit-E9X-335i.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on the Bimmerworld host and its path ends with ``.html``."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "bimmerworld.com" and not host.endswith(".bimmerworld.com"):
        return False
    path = parsed.path or ""
    if not _PRODUCT_PATH_RE.match(path):
        return False
    if _NON_PRODUCT_PATH_RE.match(path):
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_BIMMERWORLD_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_BIMMERWORLD_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (which 301s to ``/Sitemap-https.xml`` — ``requests``
    follows redirects) and collect every product-shaped URL. Walks one level
    of sitemap-index nesting in case Bimmerworld ever splits the urlset, but
    today the file is a single flat urlset.
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
            if not _is_product_url(u):
                continue
            base = u.split("?", 1)[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_text = fetch_page(SITEMAP_URL, timeout=30)
    except Exception:
        return []

    try:
        root = ET.fromstring(index_text)
    except ET.ParseError:
        return []

    tag = root.tag
    if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
        child_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
        for i, child_url in enumerate(child_urls):
            if i > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                child_text = fetch_page(child_url, timeout=30)
            except Exception:
                continue
            parse_urlset_locs(child_text)
    else:
        parse_urlset_locs(index_text)

    return product_urls


def _extract_js_var(html: str, name: str) -> Optional[str]:
    """Read a ``var <name> = "<value>";`` literal from inline-script source. Returns None when absent or empty."""
    pattern = _JS_VAR_RE.get(name)
    if pattern is None:
        return None
    match = pattern.search(html)
    if not match:
        return None
    val = match.group(1).strip()
    return val or None


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """``<span id="productName">`` first (the JSON-LD builder reads this), then og:title, then h1."""
    span = soup.find("span", id="productName")
    if isinstance(span, Tag):
        text = span.get_text(strip=True)
        if text:
            return text
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Full copy from the "Description" tab when present (``#tabs-1 .tab-content1`` —
    feature bullets + BMW fitments), then the short ``#productDescription``
    blurb, then og:description / meta description.
    """
    tab = soup.select_one("#tabs-1 .tab-content1")
    if isinstance(tab, Tag):
        text = tab.get_text(separator=" ", strip=True)
        if text:
            normalized = normalize_description_text(text, max_len=2000)
            if normalized:
                return normalized
    short = soup.find("span", id="productDescription")
    if isinstance(short, Tag):
        text = short.get_text(strip=True)
        if text:
            normalized = normalize_description_text(text, max_len=2000)
            if normalized:
                return normalized
    for selector in (("meta", {"property": "og:description"}), ("meta", {"name": "description"})):
        tag_name, attrs = selector
        meta = soup.find(tag_name, attrs=attrs)
        if isinstance(meta, Tag):
            v = meta_content(meta)
            if v and v.strip():
                return normalize_description_text(v, max_len=2000)
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """Read ``<span id="priceDisplay">$3,959.46</span>``. Returns ``None`` when missing or unparseable."""
    span = soup.find("span", id="priceDisplay")
    if not isinstance(span, Tag):
        return None
    text = span.get_text(strip=True)
    return parse_price_cents(text) if text else None


def _media_nl_id(url: str) -> Optional[str]:
    """Return the ``id`` query param of a NetSuite ``media.nl`` URL, else None."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if "media.nl" not in (parsed.path or "").lower():
        return None
    qs = parse_qs(parsed.query or "")
    values = qs.get("id")
    if not values:
        return None
    return values[0] or None


def _normalize_image_url(raw: str) -> Optional[str]:
    """Resolve site-relative gallery image URLs against ``BIMMERWORLD_BASE``. Drops empty / data-uri values."""
    s = (raw or "").strip()
    if not s or s.startswith("data:"):
        return None
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return BIMMERWORLD_BASE + s
    if s.startswith("http"):
        return s
    return None


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Gallery images: og:image first, then every ``data-zoom`` on the product
    slider (highest-quality variant). NetSuite ``media.nl`` URLs are deduped
    on the ``id`` query param so the same photo at different sizes / hashes
    collapses to one entry. Capped at 12.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized:
            return
        media_id = _media_nl_id(normalized)
        key = f"id:{media_id}" if media_id else normalized.split("?", 1)[0]
        if key in seen:
            return
        seen.add(key)
        ordered.append(normalized)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        v = meta_content(og_img)
        if v:
            add(v)

    for slide in soup.select(".product-image-slider .slide"):
        if not isinstance(slide, Tag):
            continue
        for attr in ("data-zoom", "data-thumb"):
            v = slide.get(attr)
            if isinstance(v, str) and v.strip():
                add(v)
                break

    return ordered[:12]


def _extract_part_number(html: str, soup: BeautifulSoup) -> Optional[str]:
    """
    Bimmerworld's ``itemid`` (e.g. ``83.154.6800``) — pulled from the inline
    ``<script>`` that builds the dynamic JSON-LD. Falls back to the
    ``"BMW parts item <ID>"`` lead in the static meta description when the
    script regex misses.
    """
    raw = _extract_js_var(html, "itemid")
    if raw:
        return normalize_part_number(raw)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        content = meta_content(meta_desc)
        if content:
            match = _META_DESC_ITEMID_RE.search(content)
            if match:
                return normalize_part_number(match.group(1))
    return None


def _extract_brand(html: str) -> Optional[str]:
    """``var brand = "..."`` from the inline JSON-LD builder. Empty-string values are treated as missing."""
    return _extract_js_var(html, "brand")


class BimmerworldAdapter(RetailerCrawlerAdapter):
    """
    Bimmerworld adapter.

    Fetcher tier: ``http`` — robots.txt, sitemap, homepage and product pages
    all return 200 to plain ``requests`` with the crawler User-Agent.

    Discovery: ``CRAWLER_BIMMERWORLD_START_URLS`` env var wins. Otherwise we
    walk ``/sitemap.xml`` (which 301-redirects to ``/Sitemap-https.xml``;
    ``requests`` follows that automatically) and keep every URL whose path
    ends with ``.html``. Falls back to ``DEFAULT_START_URLS`` when discovery
    returns nothing.

    Parsing: NetSuite SuiteCommerce builds its JSON-LD ``Product`` block in
    JavaScript at runtime, so the static HTML's ``<script id="dynamicJSONLD">``
    is empty. We extract data from the same DOM IDs the JS reads
    (``#productName`` / ``#productDescription`` / ``#priceDisplay``) and pull
    ``brand`` / ``itemid`` directly from the inline-script source.
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
        """
        Parse a Bimmerworld product page. Returns ``None`` when the URL is not
        a product page or no name can be recovered.
        """
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
            part_manufacturer=_extract_brand(html),
            part_number=_extract_part_number(html, soup),
            image_urls=_extract_images(soup) or None,
        )
