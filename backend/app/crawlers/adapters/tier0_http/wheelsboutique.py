"""
Wheels Boutique (wheelsboutique.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs:
    - Wheels:   ``/wheels/<brand-slug>/<series-slug>/<model-slug>/`` (most common)
                ``/wheels/<brand-slug>/<model-slug>/`` (2-level)
    - Exhausts: ``/exhausts/<slug>/``

Wheels Boutique is a WordPress site on a custom theme (``webtista``) — no
WooCommerce, no JSON-LD ``Product`` block, and **no prices**: every product
page has a "Request a Quote" button and a vTiger lead form instead of an
add-to-cart. The adapter captures name / description / image / brand and
leaves ``price_cents=None``; the ingest pipeline stores the listing for
catalog completeness but appends nothing to price history. See
``site_problem_notes/wheelsboutique.md`` for why this retailer is still
worth crawling even without pricing.

Fetcher tier: ``http`` — plain nginx + WordPress, no Cloudflare challenge,
no TLS-fingerprint check. Sitemap and product pages all return 200 to the
crawler User-Agent.

Discovery: the canonical entrypoint is ``/custom-sitemap.xml`` (redirects
from ``/sitemap.xml`` and from ``/custom-sitemap.xml`` → trailing-slash).
It indexes five child sitemaps (``posts``, ``pages``, ``taxonomies``,
``exterior``, ``exhausts``, ``gallery``) — only ``exhausts`` has product
URLs. Wheels live in an **unindexed** ``/custom-sitemap-wheels.xml`` that
the sitemap-index file does not reference; the adapter fetches it
explicitly. Override with ``CRAWLER_WHEELSBOUTIQUE_START_URLS``
(comma-separated).
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse
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
from app.crawlers.parsing import meta_content, normalize_description_text

WHEELSBOUTIQUE_BASE = "https://wheelsboutique.com"
SITEMAP_INDEX_URL = WHEELSBOUTIQUE_BASE + "/custom-sitemap.xml"
# Wheels sitemap is not referenced by the sitemap-index file but exists at
# this well-known path — fetch it unconditionally in addition to the index.
WHEELS_SITEMAP_URL = WHEELSBOUTIQUE_BASE + "/custom-sitemap-wheels.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Child-sitemap slugs that contain product URLs. Other slugs in the index
# (posts, pages, taxonomies, gallery) link to CMS / blog / tag pages and
# must not be crawled as products.
_PRODUCT_SITEMAP_SLUGS = frozenset({"exhausts", "exterior", "wheels"})

# Product URL shapes. Wheels must have at least ``wheels/<brand>/<rest>``
# (3 segments) so the ``/wheels/<brand>/`` brand-landing page is rejected.
# Exhausts are always ``/exhausts/<slug>``.
_WHEEL_PATH_RE = re.compile(r"^/wheels/[^/]+/[^/]+(/[^/]+)?/?$", re.IGNORECASE)
_EXHAUST_PATH_RE = re.compile(r"^/exhausts/[^/]+/?$", re.IGNORECASE)

# Display names for the known wheel brand slugs. The slug is the first path
# segment after ``/wheels/``. Unknown slugs fall through to a heuristic that
# strips a trailing ``-wheels`` and title-cases (e.g. ``vossen-wheels`` →
# ``Vossen``) so newly-added brands still get a sensible manufacturer.
_WHEEL_BRAND_DISPLAY: dict[str, str] = {
    "1886-wheels": "1886",
    "ag-luxury-wheels": "AG Luxury",
    "anrky-wheels": "ANRKY",
    "bbs-wheels": "BBS",
    "forgiato-wheels": "Forgiato",
    "hre-wheels": "HRE",
    "ipe-wheels": "iPE",
    "rotiform-wheels": "Rotiform",
    "techart-wheels-porsche": "TechArt",
}

# Exhaust taxonomy currently has only ``ipe-exhaust``, and every exhaust
# product description includes the literal token ``iPE``. Look for it
# (case-insensitive, word-boundary) before giving up on the brand field.
_IPE_EXHAUST_TOKEN_RE = re.compile(r"\bi[Pp]E\b|\bIPE\b")
_IPE_EXHAUST_BRAND = "iPE"

DEFAULT_START_URLS = [
    "https://wheelsboutique.com/wheels/hre-wheels/520-series/hre-520/",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on wheelsboutique.com and matches a product path shape."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "wheelsboutique.com" and not host.endswith(".wheelsboutique.com"):
        return False
    path = parsed.path or ""
    return bool(_WHEEL_PATH_RE.match(path) or _EXHAUST_PATH_RE.match(path))


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_WHEELSBOUTIQUE_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_WHEELSBOUTIQUE_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_sitemap(url: str) -> bool:
    """True if a child-sitemap URL names one of the product slugs we crawl."""
    path = urlparse(url).path
    match = re.search(r"/custom-sitemap-([a-z0-9]+)\.xml/?$", path, re.IGNORECASE)
    if not match:
        return False
    return match.group(1).lower() in _PRODUCT_SITEMAP_SLUGS


def _discover_via_sitemap() -> List[str]:
    """
    Walk the sitemap-index file + the unindexed ``/custom-sitemap-wheels.xml``
    and return every URL whose path matches the product shape. Returns an
    empty list on fetch/parse failure.
    """
    seen: set[str] = set()
    product_urls: List[str] = []

    def collect_product_urls(xml_text: str) -> None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return
        for loc in _loc_elements(root):
            if not loc.text:
                continue
            u = loc.text.strip().rstrip("/")
            if not _is_product_url(u):
                continue
            if u in seen:
                continue
            seen.add(u)
            product_urls.append(u)

    child_urls: list[str] = []

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
                    if loc.text and _is_product_sitemap(loc.text.strip()):
                        child_urls.append(loc.text.strip())
            else:
                collect_product_urls(index_text)

    # The wheels sitemap isn't listed in the index, but it exists at a
    # predictable path — pull it explicitly so wheel coverage isn't empty.
    if WHEELS_SITEMAP_URL not in child_urls:
        child_urls.append(WHEELS_SITEMAP_URL)

    for i, child_url in enumerate(child_urls):
        if i > 0:
            time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
        try:
            child_text = fetch_page(child_url, timeout=30)
        except Exception:
            continue
        collect_product_urls(child_text)

    return product_urls


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """``<main> <h1>`` first (the product title lives here), then og:title."""
    main = soup.select_one("main")
    search_root = main if isinstance(main, Tag) else soup
    h1 = search_root.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer the theme's ``.prose`` copy block (the "Product Description" body).
    Fall back to og:description / meta description because wheel pages often
    leave the prose block empty.
    """
    prose = soup.select_one("main .prose")
    if isinstance(prose, Tag):
        text = prose.get_text(separator=" ", strip=True)
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
                normalized = normalize_description_text(v, max_len=2000)
                if normalized:
                    return normalized
    return None


def _extract_hero_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Only return the og:image hero. Wheel pages render a "More wheels on:
    <series>" cross-sell row of ``<img>`` tags *of other products* — a DOM
    sweep would pull those in, so we deliberately don't widen the selector.
    """
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        v = meta_content(og_img)
        if v and v.strip():
            return v.strip()
    return None


def _brand_slug_from_url(url: str) -> Optional[str]:
    """Return the brand slug for a wheel URL (e.g. ``hre-wheels``), else None."""
    try:
        path = urlparse(url).path
    except ValueError:
        return None
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2 or parts[0].lower() != "wheels":
        return None
    return parts[1].lower()


def _wheel_brand_display(slug: str) -> str:
    """
    Map a wheel brand slug to a display name. Known slugs use the curated
    map; unknowns strip a trailing ``-wheels`` / ``-wheels-<suffix>`` and
    title-case so new brands don't land as literal slugs.
    """
    if slug in _WHEEL_BRAND_DISPLAY:
        return _WHEEL_BRAND_DISPLAY[slug]
    base = re.sub(r"-wheels(-[a-z0-9]+)*$", "", slug, flags=re.IGNORECASE)
    return base.replace("-", " ").title() if base else slug


def _extract_brand(url: str, name: Optional[str], description: Optional[str]) -> Optional[str]:
    """
    Wheel products: brand is the first path segment after ``/wheels/``.
    Exhaust products: Wheels Boutique's exhaust taxonomy today is iPE-only,
    and the vendor embeds the literal ``iPE`` token in every exhaust
    description. Detect the token on the page; return None when absent so
    the ingest path stores the part under ``Unknown`` rather than guessing.
    """
    path = urlparse(url).path or ""
    if path.lower().startswith("/wheels/"):
        slug = _brand_slug_from_url(url)
        return _wheel_brand_display(slug) if slug else None
    if path.lower().startswith("/exhausts/"):
        haystack = " ".join(s for s in (name, description) if s)
        if haystack and _IPE_EXHAUST_TOKEN_RE.search(haystack):
            return _IPE_EXHAUST_BRAND
        return None
    return None


class WheelsBoutiqueAdapter(RetailerCrawlerAdapter):
    """
    Wheels Boutique adapter.

    Catalog-only retailer: no prices on product pages. The payload keeps
    ``price_cents=None`` so the ingest pipeline records the listing without
    appending to price history. Brand comes from the URL for wheels (the
    only way it's surfaced) and from a description-text check for exhausts.
    """

    ADAPTER_NAME: ClassVar[str] = "wheelsboutique"
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
        """Parse a Wheels Boutique product page. Returns ``None`` for non-product URLs or when no name is found."""
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        # BBS wheel models are routinely 2 chars ("FI", "RN", "XA", "CH") —
        # a 3-char floor silently drops legit wheel-model pages. Accept any
        # non-empty H1; brand comes from the URL path regardless.
        if not name:
            return None

        description = _extract_description(soup)
        hero_image = _extract_hero_image(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=None,
            part_manufacturer=_extract_brand(url, name, description),
            part_number=None,
            image_urls=[hero_image] if hero_image else None,
        )
