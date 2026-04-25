"""
Fortune Auto (fortune-auto.com) crawler adapter — Tier 1 (TLS impersonation).

Fortune Auto retired the ``fortuneauto-na.com`` Shopify storefront somewhere
between 2023 and 2026 (the old NA subdomain is now ``NXDOMAIN``). The live
site is ``fortune-auto.com``, a WordPress + Yoast marketing catalog sitting
behind Cloudflare: plain ``requests`` gets a 403 challenge, but a Chrome-
impersonated TLS handshake via ``curl_cffi`` passes the WAF. Hence
``FETCHER_TIER = "tls"`` and this module lives in ``tier1_tls/``.

Catalog shape: the new site is *product-line*-shaped rather than
per-SKU-shaped — each coilover series (500, 510, 520, Pro 2-way, Pro 3-way,
Muller MSC, Super Low Spec, VHLS, Offroad) has its own page under
``/coilovers/<series>/``. Fortune Auto builds per-fitment so a single series
covers thousands of orderable SKUs; the old Shopify storefront handled that
with one product per variant, but the new WordPress catalog doesn't. We
mirror this by treating each series page as one catalog entry and leaving
``part_number=None`` — same posture as HRE Wheels and Wheels Boutique (other
build-to-order / per-fitment catalogs in the registry).

Discovery: ``/sitemap.xml`` is a Yoast sitemap *index* pointing at per-CPT
child sitemaps; ``/page-sitemap.xml`` is the urlset that holds the
``/coilovers/<series>/`` pages. We filter on that path shape rather than
crawling every page (Yoast mixes the coilovers with legal pages, vendor
sheets, etc.). The bare ``/coilovers/`` collection root is rejected so it
doesn't pollute the catalog with a marketing landing.

Parse: WordPress/Yoast doesn't emit a JSON-LD ``Product`` block (only
``CollectionPage`` / ``WebPage``), so we read ``og:title`` / ``<title>`` for
the name, ``og:description`` / ``<meta name="description">`` for the
description, and ``og:image`` for the hero. Fortune Auto only sells Fortune
Auto, so ``part_manufacturer`` is the constant ``"Fortune Auto"``.

Env override: ``CRAWLER_FORTUNEAUTO_START_URLS`` (comma-separated) for
adhoc crawls against a specific series page.
"""

import os
import re
from typing import Callable, ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import meta_content, normalize_description_text

FORTUNEAUTO_BASE = "https://fortune-auto.com"
SITEMAP_INDEX_URL = FORTUNEAUTO_BASE + "/sitemap.xml"
PAGE_SITEMAP_URL = FORTUNEAUTO_BASE + "/page-sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Fortune Auto sells only Fortune Auto — brand is a site-level constant.
FORTUNEAUTO_BRAND = "Fortune Auto"

# ``/coilovers/<slug>/`` — a single non-empty segment under the catalog root.
# The bare ``/coilovers/`` landing is rejected because it's the collection
# page, not a product line. Trailing slash is optional for URL guards used
# by archive replay, even though Yoast emits the canonical trailing form.
_PRODUCT_PATH_RE = re.compile(r"^/coilovers/[^/]+/?$", re.IGNORECASE)

DEFAULT_START_URLS = [
    FORTUNEAUTO_BASE + "/coilovers/500series/",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on fortune-auto.com and matches the coilovers path shape."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "fortune-auto.com" or host.endswith(".fortune-auto.com")):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return CRAWLER_FORTUNEAUTO_START_URLS if set, else None."""
    raw = os.environ.get("CRAWLER_FORTUNEAUTO_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _loc_elements(root) -> list:
    """Find all ``<loc>`` elements regardless of whether the doc is an index or urlset."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_via_sitemap(fetch: Callable[..., str]) -> List[str]:
    """
    Walk the Yoast sitemap index → page-sitemap and collect coilover-series URLs.

    ``fetch`` is a callable ``(url, *, timeout) -> str`` — the adapter passes
    ``self.fetcher.fetch`` so Cloudflare doesn't trip us up mid-discovery.
    Returns an empty list on any fetch/parse failure so the caller can fall
    back to ``DEFAULT_START_URLS``.
    """
    # Step 1: find the page-sitemap in the index. If the index parse fails we
    # still try the conventional ``/page-sitemap.xml`` path as a best-effort.
    page_sitemap_url = PAGE_SITEMAP_URL
    try:
        index_xml = fetch(SITEMAP_INDEX_URL, timeout=30)
        index_root = ET.fromstring(index_xml)
        for loc in _loc_elements(index_root):
            text = (loc.text or "").strip()
            if text.endswith("/page-sitemap.xml"):
                page_sitemap_url = text
                break
    except Exception:
        pass

    try:
        page_xml = fetch(page_sitemap_url, timeout=30)
        root = ET.fromstring(page_xml)
    except Exception:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []
    for loc in _loc_elements(root):
        text = (loc.text or "").strip()
        if not text or not _is_product_url(text):
            continue
        if text in seen:
            continue
        seen.add(text)
        product_urls.append(text)
    return product_urls


_BRAND_SUFFIX_RE = re.compile(r"\s*[-–|]\s*Fortune Auto\s*$", re.IGNORECASE)


def _strip_brand_suffix(name: str) -> str:
    """Trim "- Fortune Auto" / "– Fortune Auto" / trailing hyphens from a title."""
    trimmed = _BRAND_SUFFIX_RE.sub("", name).strip()
    # Yoast sometimes leaves a dangling " -" when the suffix is empty.
    trimmed = re.sub(r"\s*[-–|]\s*$", "", trimmed).strip()
    return trimmed or name


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer ``og:title`` because Yoast cleans it; fall back to ``<title>``
    with the trailing ``" – Fortune Auto"`` / ``" - Fortune Auto"`` suffix
    stripped so the catalog row doesn't double-brand itself (the adapter
    also sets ``part_manufacturer`` to the same string).
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return _strip_brand_suffix(v.strip())
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        v = title_tag.get_text(strip=True)
        if v:
            return _strip_brand_suffix(v)
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Prefer og:description, fall back to <meta name="description">."""
    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        v = meta_content(og_desc)
        if v and v.strip():
            return normalize_description_text(v, max_len=2000)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        v = meta_content(meta_desc)
        if v and v.strip():
            return normalize_description_text(v, max_len=2000)
    return None


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """Single hero image from ``og:image``. Absolutized; Fortune Auto emits https already."""
    og_img = soup.find("meta", property="og:image")
    if not isinstance(og_img, Tag):
        return []
    v = meta_content(og_img)
    if not v:
        return []
    v = v.strip()
    if v.startswith("//"):
        v = "https:" + v
    elif v.startswith("/"):
        v = FORTUNEAUTO_BASE + v
    if not v.startswith("http"):
        return []
    return [v]


class FortuneAutoAdapter(RetailerCrawlerAdapter):
    """
    Fortune Auto adapter — series-level catalog entries from the WordPress
    marketing site. Brand is a constant (``Fortune Auto``), part numbers
    are left ``None`` because each page covers many fitments, and prices
    are quote-driven so ``price_cents`` is also always ``None``.

    Live crawling uses the TLS tier so the Cloudflare WAF sees a
    curl_cffi-impersonated Chrome handshake instead of Python's default
    TLS fingerprint.
    """

    ADAPTER_NAME: ClassVar[str] = "fortuneauto"
    category_targets: ClassVar[list[str]] = ["coilover", "universal"]
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield coilover-series URLs; env override wins, then sitemap, then ``DEFAULT_START_URLS``."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in _discover_via_sitemap(self.fetcher.fetch) or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse a Fortune Auto coilover-series page into a ScrapedPayload."""
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
            part_manufacturer=FORTUNEAUTO_BRAND,
            part_number=None,
            image_urls=images if images else None,
        )
