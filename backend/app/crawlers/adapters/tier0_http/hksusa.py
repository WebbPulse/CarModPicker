"""
HKS USA (hksusa.com) crawler adapter.

Product URLs: ``https://hksusa.com/product/<CODE>`` where ``<CODE>`` is the HKS
part number (e.g. ``11003-AN020``, ``80300-AA005C``). First-party brand site —
every SKU is HKS-manufactured and pricing shown is MSRP (reference only, not
resale), which matches the backlog entry's intent ("Reference pricing for
HKS-branded SKUs across multiple chassis").

Platform: Next.js 13 App Router on Vercel, backed by a Strapi CMS. Plain
``requests`` passes — no Cloudflare / JS challenge, so this is Tier 0. Pages
are server-rendered with the full product record inlined in the RSC streaming
payload (``self.__next_f.push([1,"..."])``), which is **JSON-inside-JS-string**:
each inner double-quote appears as ``\\"`` in the HTML source. There is no
JSON-LD ``Product`` block and the og:* tags carry only title + hero image —
every other field (MSRP, remarks, part code linkage) has to come from the
escaped RSC blob, so the parser below is a set of targeted regexes keyed on
the URL's part code rather than a full JSON parse of the stream (RSC uses a
stateful custom format that isn't trivially JSON-parseable).

Discovery: ``/sitemap.xml`` is a single flat urlset (~2k entries, mixed
product + category + CMS pages). We keep only ``/product/<code>`` paths.
Override with ``CRAWLER_HKSUSA_START_URLS`` (comma-separated) for a fixed list.

Brand policy: every SKU ships as HKS — hardcoded as the default manufacturer.
No per-product brand field to fall back on.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
)

HKSUSA_BASE = "https://hksusa.com"
SITEMAP_URL = HKSUSA_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# HKS brand label — storefront is first-party, every SKU is HKS-manufactured.
_HKS_BRAND = "HKS"

# og:title on this theme always ends with this suffix; strip it for a clean name.
_OG_TITLE_SUFFIX = " | HKS High Performance Auto Parts"

# Product URL shape: single path segment under /product/ whose body is the
# HKS part code (alphanumeric plus ``-`` / ``.``). Anchored so /productlist/
# (category landing pages) and /product/ alone don't match.
_PRODUCT_PATH_RE = re.compile(r"^/product/([A-Za-z0-9][A-Za-z0-9\-\._]*)$")

DEFAULT_START_URLS = [
    "https://hksusa.com/product/11003-AN020",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` has a ``/product/<code>`` path on the hksusa.com host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "hksusa.com" or host.endswith(".hksusa.com")):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _product_code_from_url(url: str) -> Optional[str]:
    """Extract the trailing ``<code>`` segment from a ``/product/<code>`` URL."""
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return None
    match = _PRODUCT_PATH_RE.match(path)
    return match.group(1) if match else None


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_HKSUSA_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_HKSUSA_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _unescape_rsc_string(raw: str) -> str:
    """
    Decode the subset of JSON string escapes that appear in HKS's RSC stream.

    Values inside ``self.__next_f.push([1,"..."])`` are JSON embedded inside a
    JS string literal, so a text value like ``a "quoted" word`` reaches us as
    ``a \\"quoted\\" word``. Handle the common escapes (quote, backslash,
    slash, newline, tab, carriage return) — remarks on this storefront is
    plain prose, so we don't need a full JSON parser.
    """
    return (
        raw.replace('\\"', '"')
        .replace("\\/", "/")
        .replace("\\n", " ")
        .replace("\\r", " ")
        .replace("\\t", " ")
        .replace("\\\\", "\\")
    )


def _extract_name_for_code(html_text: str, code: str) -> Optional[str]:
    """
    Pull the product's display name out of the RSC blob by pairing it with the
    URL's part code. The CMS emits ``"name":"<display>","code":"<code>"`` for
    every product record (escaped once through the RSC stream); anchoring on
    the code disambiguates the current product from related-product records
    that ride along on the same page.
    """
    pattern = r'\\"name\\":\\"([^"\\]{1,300})\\",\\"code\\":\\"' + re.escape(code) + r'\\"'
    match = re.search(pattern, html_text)
    if not match:
        return None
    name = _unescape_rsc_string(match.group(1)).strip()
    return name or None


def _extract_remarks_for_code(html_text: str, code: str) -> Optional[str]:
    """
    Pull ``remarks`` (short plain-text note, e.g. box dimensions, racing-use
    disclaimer, fitment note). It's the only human-readable copy on the page —
    the ``product_description`` field is HTML wrapping product-sheet images
    with no body text, so there's nothing else worth promoting to the catalog
    description. Anchored on the URL's code so we don't pick up the remarks
    off a related-product record.
    """
    pattern = r'\\"code\\":\\"' + re.escape(code) + r'\\",\\"remarks\\":\\"([^"\\]{0,2000})\\",\\"discontinued\\"'
    match = re.search(pattern, html_text)
    if not match:
        return None
    remarks = _unescape_rsc_string(match.group(1)).strip()
    if not remarks:
        return None
    return normalize_description_text(remarks)


# Price lives on the ``product-unit.product-unit-us`` Strapi component as an
# integer MSRP in whole USD (no cents). Duplicate instances of the same value
# appear because the RSC stream ships the product record twice (once inline,
# once via the streaming patch) — picking the first match is fine since both
# reference the same product-unit.
_MSRP_RE = re.compile(r'\\"msrp\\":\s*(\d+)')


def _extract_price_cents(html_text: str) -> Optional[int]:
    """Parse ``"msrp": N`` (USD whole dollars) out of the RSC blob → cents."""
    match = _MSRP_RE.search(html_text)
    if not match:
        return None
    try:
        dollars = int(match.group(1))
    except ValueError:
        return None
    if dollars <= 0:
        return None
    return dollars * 100


def _extract_hero_image(soup: BeautifulSoup) -> Optional[str]:
    """
    Read ``og:image`` for the hero image. The Strapi media host
    (``cheerful-bouquet-*.media.strapiapp.com``) serves the original-size JPG
    here; resized variants live nested under ``formats.{large,medium,small,…}``
    in the RSC blob and aren't needed for the catalog thumbnail.
    """
    og_img = soup.find("meta", property="og:image")
    if not isinstance(og_img, Tag):
        return None
    content = meta_content(og_img)
    if not content:
        return None
    content = content.strip()
    return content or None


def _extract_name_fallback(soup: BeautifulSoup) -> Optional[str]:
    """
    Name fallback when the code-anchored RSC match misses (CMS field layout
    change, truncated response, etc.). ``og:title`` on this theme is always
    ``<NAME> | HKS High Performance Auto Parts`` — strip the site suffix. Last
    resort is ``<title>`` with the same suffix logic.
    """
    for prop in ("og:title",):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta_content(meta)
            if content:
                cleaned = _strip_title_suffix(content)
                if cleaned:
                    return cleaned

    title = soup.find("title")
    if isinstance(title, Tag):
        text = title.get_text(strip=True)
        cleaned = _strip_title_suffix(text)
        if cleaned:
            return cleaned
    return None


def _strip_title_suffix(raw: Optional[str]) -> Optional[str]:
    """Remove the trailing ``" | HKS High Performance Auto Parts"`` site suffix."""
    if not raw:
        return None
    cleaned = raw.strip()
    if cleaned.endswith(_OG_TITLE_SUFFIX):
        cleaned = cleaned[: -len(_OG_TITLE_SUFFIX)].strip()
    return cleaned or None


class HKSUSAAdapter(RetailerCrawlerAdapter):
    """
    HKS USA adapter.

    Fetcher tier: ``http`` — Vercel origin, no Cloudflare / JS challenge.

    Discovery: ``CRAWLER_HKSUSA_START_URLS`` env var wins. Otherwise fetch
    ``/sitemap.xml`` (single flat urlset, ~2k entries) and keep only
    ``/product/<code>`` URLs. Falls back to ``DEFAULT_START_URLS`` when the
    sitemap fetch fails.

    Parsing: the RSC-embedded product record, anchored on the URL's part code.
    Name + remarks come from code-paired regex matches on the escaped-JSON
    stream; MSRP comes from the ``product-unit.product-unit-us`` component
    (USD whole-dollars → cents); hero image comes from ``og:image``. Brand is
    hardcoded to ``HKS`` — no per-product manufacturer field exists on this
    first-party storefront, and there's nothing else on-site to disambiguate.
    """

    ADAPTER_NAME: ClassVar[str] = "hksusa"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins when set."""
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
        Fetch ``/sitemap.xml`` via the HTTP fetcher and collect every
        ``/product/<code>`` URL. Returns ``[]`` on any failure so the caller
        can fall back to the hardcoded default.
        """
        try:
            xml_text = self.fetcher.fetch(SITEMAP_URL, timeout=15)
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
            raw = loc.text.strip()
            if not raw or not _is_product_url(raw):
                continue
            if raw in seen:
                continue
            seen.add(raw)
            product_urls.append(raw)
        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an HKS USA product page. Returns ``None`` when the URL isn't
        product-shaped or when we can't recover a name from the RSC blob or
        og/title fallback.
        """
        if not _is_product_url(url):
            return None
        code = _product_code_from_url(url)
        if not code:
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name_for_code(html, code) or _extract_name_fallback(soup)
        if not name or len(name) < 2:
            return None

        description = _extract_remarks_for_code(html, code)
        price_cents = _extract_price_cents(html)
        image_urls: Optional[List[str]] = None
        hero = _extract_hero_image(soup)
        if hero:
            image_urls = [hero]

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=_HKS_BRAND,
            part_number=normalize_part_number(code),
            image_urls=image_urls,
        )
