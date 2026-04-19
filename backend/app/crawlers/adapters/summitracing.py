"""
Summit Racing (summitracing.com) crawler adapter.

Product URLs: https://www.summitracing.com/parts/<slug> (e.g. /parts/bdd-2001102).
Discovery: starts from one or more /search/... category URLs and walks pagination
(?page=N) collecting all linked /parts/<slug> product URLs.

Parsing is straightforward because product pages expose a complete JSON-LD Product
block with name, brand, mpn, sku, offers.price, description, and image. We prefer
``mpn`` over ``sku`` as the part_number because Summit Racing prefixes its SKU with
a retailer code (e.g. "BDD-2001102" vs real MPN "2001102"); using MPN keeps cross-
retailer dedupe on part_manufacturer + part_number working.

Start URLs come from CRAWLER_SUMMITRACING_START_URLS (comma-separated) and default
to the diesel exhaust brakes category so a fresh run exercises the full pipeline
against a small, bounded set of pages.
"""

import json
import os
import re
import time
from dataclasses import replace
from typing import Iterator, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
    fetch_page,
)
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

SUMMITRACING_BASE = "https://www.summitracing.com"
PRODUCT_PATH_PREFIX = "/parts/"

DEFAULT_START_URLS = [
    "https://www.summitracing.com/search/department/brake-systems/section/exhaust-brakes/part-type/diesel-engine-exhaust-brakes",
]

# Safety cap so a mis-parsed "Page X of Y" can't walk forever.
MAX_SEARCH_PAGES_PER_URL = 200

# Pattern for a product page slug — alphanumerics, dashes, underscores.
_PRODUCT_SLUG_RE = re.compile(r"^/parts/[a-z0-9][a-z0-9\-_]*/?$", re.IGNORECASE)

# "Page X of Y" in the pagination bar (both rendered variants use this phrasing).
_PAGE_OF_RE = re.compile(r"Page\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise fall back to the default category URL."""
    raw = os.environ.get("CRAWLER_SUMMITRACING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return list(DEFAULT_START_URLS)


def _with_page_param(url: str, page: int) -> str:
    """Return the URL with ?page=<page> set (replacing any existing page param)."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["page"] = [str(page)]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def _extract_product_urls_from_search_html(html: str) -> List[str]:
    """Return unique /parts/<slug> absolute URLs found in a Summit search page."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str):
            continue
        href = href.strip()
        if not href.startswith(PRODUCT_PATH_PREFIX):
            continue
        # Drop /parts/<slug>/reviews and similar subpaths; keep only the product page itself.
        path_only = href.split("?", 1)[0].split("#", 1)[0]
        if not _PRODUCT_SLUG_RE.match(path_only):
            continue
        absolute = SUMMITRACING_BASE + path_only.rstrip("/")
        if absolute in seen:
            continue
        seen.add(absolute)
        out.append(absolute)
    return out


def _parse_total_pages(html: str) -> Optional[int]:
    """Parse "Page X of Y" from the pagination bar; return Y or None if not found."""
    match = _PAGE_OF_RE.search(html)
    if not match:
        return None
    try:
        return int(match.group(2))
    except ValueError:
        return None


def _discover_from_search_urls(start_urls: List[str]) -> List[str]:
    """Walk each start URL's pagination and collect unique product URLs."""
    seen: set[str] = set()
    results: List[str] = []
    for start in start_urls:
        total_pages: Optional[int] = None
        page = 1
        while page <= MAX_SEARCH_PAGES_PER_URL:
            page_url = _with_page_param(start, page) if page > 1 else start
            if page > 1:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                html = fetch_page(page_url, timeout=30)
            except Exception:
                break
            if total_pages is None:
                total_pages = _parse_total_pages(html)
            found = _extract_product_urls_from_search_html(html)
            new_on_page = 0
            for u in found:
                if u in seen:
                    continue
                seen.add(u)
                results.append(u)
                new_on_page += 1
            if total_pages is not None:
                if page >= total_pages:
                    break
            elif new_on_page == 0:
                break
            page += 1
    return results


def _absolutize_image(url: str) -> str:
    """Summit's JSON-LD uses protocol-relative image URLs (//static.summitracing.com/...)."""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return SUMMITRACING_BASE + url
    return url


def _extract_part_media_files_images(html: str) -> List[str]:
    """
    Pull full-size product images from <script id="part-media-files">. Summit's JSON-LD
    image block typically returns one URL; the part-media-files JSON exposes the full
    gallery with xlarge variants.
    """
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="part-media-files")
    if not isinstance(script, Tag):
        return []
    raw = script.string
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    urls: List[str] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if entry.get("MediaType") != "Image":
            continue
        filename = entry.get("FileName")
        if isinstance(filename, str) and filename.strip():
            urls.append(filename.strip())
    return urls


def _choose_part_number(item: dict) -> Optional[str]:
    """
    Prefer MPN over SKU for Summit Racing: the SKU is the Summit-prefixed code
    ("BDD-2001102") while MPN is the real manufacturer part number ("2001102").
    Using MPN lets us dedupe with other retailers carrying the same part.
    """
    mpn = item.get("mpn")
    if isinstance(mpn, str) and mpn.strip():
        normalized = normalize_part_number(mpn)
        if normalized:
            return normalized
    sku = item.get("sku")
    if isinstance(sku, str) and sku.strip():
        return normalize_part_number(sku)
    return None


class SummitRacingAdapter(RetailerCrawlerAdapter):
    """
    Summit Racing adapter. Discovery walks search/category pages by ?page=N and
    collects /parts/<slug> URLs; parsing reads the page's JSON-LD Product block
    and enriches images from the part-media-files JSON.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs found across the configured start URLs' paginated
        search results. Set CRAWLER_SUMMITRACING_START_URLS (comma-separated)
        to crawl different categories; runner applies --limit.
        """
        for url in _discover_from_search_urls(_resolve_start_urls()):
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse a Summit Racing product page. JSON-LD covers everything we need."""
        item = extract_json_ld_product(html)
        if not item:
            return None
        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        part_number = _choose_part_number(item) or payload.part_number

        images: List[str] = []
        seen: set[str] = set()
        for src in (payload.image_urls or []) + _extract_part_media_files_images(html):
            absolute = _absolutize_image(src)
            if not absolute.startswith("http"):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            images.append(absolute)

        return replace(
            payload,
            part_number=part_number,
            image_urls=images[:12] if images else None,
        )
