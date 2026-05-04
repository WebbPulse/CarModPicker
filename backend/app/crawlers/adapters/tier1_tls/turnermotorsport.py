"""
Turner Motorsport (turnermotorsport.com) crawler adapter — Tier 1 (TLS).

Product URLs: ``https://www.turnermotorsport.com/p-<digits>-<slug>/``

Turner is behind Cloudflare with a TLS/JA3 fingerprint block: plain ``requests``
and a curl with a browser User-Agent both get a 403 "Sorry, you have been
blocked" page. curl_cffi's Chrome impersonation handshake passes, so
``FETCHER_TIER = "tls"``.

Discovery: ``/sitemap_index.xml`` points at 40+ child urlsets
(``/sitemap_product_<N>.xml``) with 5000 URLs each. The child sitemaps are
**malformed XML** — every closing tag is URL-encoded into the URL content
(``...slug/</loc><lastmod>...</lastmod></url>`` becomes
``...slug%2F%3C%2Floc%3E%3Clastmod%3E...%3C%2Flastmod%3E%3C%2Furl%3E``),
so defusedxml raises ``mismatched tag``. We extract URLs via regex and URL-
decode instead. Override with ``CRAWLER_TURNERMOTORSPORT_START_URLS``.

Parsing: no JSON-LD. Product pages emit schema.org **microdata** with
``itemprop`` for brand, description, sku, mpn, price, priceCurrency, image.
Notes:
- ``itemprop="sku"`` is Turner's internal "T#" (``3``, ``33``, matches the
  ``/p-<digits>-`` in the URL). It is NOT a manufacturer SKU — we must use
  ``itemprop="mpn"`` (first occurrence; later siblings are dash/space-
  formatted variants of the same number). Using T# would create spurious
  per-retailer part numbers like ``3`` / ``33`` / ``48``.
- House-brand parts carry ``itemprop="brand" content="Packaged by Turner"``
  (or ``Genuine BMW``, ``AFE``, ``H&R``, ...). We pass the value through; the
  backlog notes Turner house-brand prices are reference values, not arbitrage
  candidates, but they still matter for build-list completeness.
- Image gallery lives at ``assets.turnermotorsport.com/product_library_tms/
  <id>_x<size>.(jpg|webp)``. The same gallery image appears at several sizes
  and in both webp/jpg; we dedupe on the numeric ``<id>`` and keep the jpg
  variant at ~600px.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

TURNER_BASE = "https://www.turnermotorsport.com"
SITEMAP_INDEX_URL = f"{TURNER_BASE}/sitemap_index.xml"

# Canonical product URL: /p-<digits>-<slug>/. The digits are Turner's internal
# "T#" (itemprop="sku" on the page); the slug is kebab-case ASCII.
_PRODUCT_PATH_RE = re.compile(r"^/p-\d+-[a-z0-9][a-z0-9\-]*/?$", re.IGNORECASE)

# Child sitemap URLs within the index — match both the plain product sitemaps
# and keep defensive matching in case Turner ships other sibling sitemaps.
_SITEMAP_CHILD_RE = re.compile(r"<loc>(https?://[^<]+?\.xml)</loc>", re.IGNORECASE)

# In the malformed child sitemaps, a URL is followed by `%3C%2Floc%3E`
# (the URL-encoded ``</loc>``). We capture everything between ``<loc>`` and
# that sentinel, then urldecode — the trailing ``%2F`` decodes to ``/``.
_SITEMAP_LOC_RE = re.compile(r"<loc>(https?://[^<%]+?%2F)%3C%2Floc%3E", re.IGNORECASE)

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://www.turnermotorsport.com/p-3-e46-m3-motorsport-thermostat-55-degree-c/",
]

# Product images live under this asset host with a `<numeric-id>_x<size>.<ext>` shape.
_PRODUCT_IMAGE_RE = re.compile(
    r"https://assets\.turnermotorsport\.com/product_library_tms/(\d+)_x(\d+)\.(jpg|jpeg|png|webp)",
    re.IGNORECASE,
)


def _is_product_url(url: str) -> bool:
    """True if ``url`` matches the ``/p-<digits>-<slug>/`` product pattern on turnermotorsport.com."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "turnermotorsport.com" and not host.endswith(".turnermotorsport.com"):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_TURNERMOTORSPORT_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_TURNERMOTORSPORT_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_urls_from_malformed_sitemap(xml_text: str) -> List[str]:
    """
    Pull product URLs from a Turner child sitemap whose closing tags are
    URL-encoded into the URL content. Captures text between ``<loc>`` and
    ``%3C%2Floc%3E``, URL-decodes, and keeps only ``/p-<digits>-<slug>/`` URLs.
    Deduplicated in insertion order.
    """
    seen: set[str] = set()
    out: List[str] = []
    for raw in _SITEMAP_LOC_RE.findall(xml_text):
        decoded = unquote(raw)
        if not _is_product_url(decoded):
            continue
        if decoded in seen:
            continue
        seen.add(decoded)
        out.append(decoded)
    return out


def _extract_sitemap_index_children(xml_text: str) -> List[str]:
    """Pull child sitemap URLs (``.xml``) from the sitemap index."""
    seen: set[str] = set()
    out: List[str] = []
    for loc in _SITEMAP_CHILD_RE.findall(xml_text):
        if loc in seen:
            continue
        seen.add(loc)
        out.append(loc)
    return out


def _first_itemprop(soup: BeautifulSoup, name: str) -> Optional[Tag]:
    """First element bearing ``itemprop=<name>`` anywhere in the document."""
    tag = soup.find(attrs={"itemprop": name})
    return tag if isinstance(tag, Tag) else None


def _microdata_value(tag: Optional[Tag]) -> Optional[str]:
    """
    Read the value of a microdata element: ``content`` attr for <meta>/<link>,
    ``href`` for links, otherwise the element text. Returns a stripped string or None.
    """
    if not isinstance(tag, Tag):
        return None
    for attr in ("content", "href"):
        val = tag.get(attr)
        if isinstance(val, str) and val.strip():
            return val.strip()
    text = tag.get_text(strip=True)
    return text if text else None


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """og:title → itemprop="name" → h1. Trim trailing whitespace Turner leaves in H1s."""
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    named = _first_itemprop(soup, "name")
    val = _microdata_value(named)
    if val:
        return val
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Prefer ``itemprop="description"`` (product copy) over og:description (marketing blurb)."""
    desc_tag = _first_itemprop(soup, "description")
    if isinstance(desc_tag, Tag):
        text = desc_tag.get_text(separator=" ", strip=True)
        if text:
            normalized = normalize_description_text(text, max_len=2000)
            if normalized:
                return normalized
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


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """Read ``itemprop="price"`` under the Offer microdata."""
    price_tag = _first_itemprop(soup, "price")
    raw = _microdata_value(price_tag)
    if not raw:
        return None
    return parse_price_cents(raw)


def _extract_part_manufacturer(soup: BeautifulSoup) -> Optional[str]:
    """Read ``itemprop="brand"`` (a <meta> element with ``content``)."""
    brand_tag = _first_itemprop(soup, "brand")
    val = _microdata_value(brand_tag)
    return val if val else None


def _extract_part_number(soup: BeautifulSoup) -> Optional[str]:
    """
    First ``itemprop="mpn"`` value. Turner renders the same MPN several times
    (``11531417215``, ``11-53-1-417-215``, ``11 53 1 417 215``) — the first is
    the clean form. We never use ``itemprop="sku"``: that is Turner's internal
    T# (e.g. ``3``, ``33``) which would collide with other retailers' parts.
    """
    mpn_tag = _first_itemprop(soup, "mpn")
    val = _microdata_value(mpn_tag)
    if not val:
        return None
    return normalize_part_number(val)


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images. Collect every ``assets.turnermotorsport.com/
    product_library_tms/<id>_x<size>.<ext>`` URL referenced in src/href/srcset
    attributes, dedupe by numeric id, and emit the jpg variant at the largest
    size we saw (usually 600 or 800). Capped at 12.

    The og:image seed goes in first so it leads the list. Brand-logo URLs
    (``/static/img/brands/...``) are filtered by the regex — it only matches
    the product_library_tms path.
    """
    by_id: dict[str, tuple[int, str]] = {}
    order: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw:
            return
        for match in _PRODUCT_IMAGE_RE.finditer(raw):
            img_id = match.group(1)
            size = int(match.group(2))
            ext = match.group(3).lower()
            # Prefer .jpg over .webp so downstream consumers (thumbnails,
            # preview cards) get a universally decodable asset. Within the
            # same format, prefer the largest size we've seen.
            is_jpg = ext in ("jpg", "jpeg")
            existing = by_id.get(img_id)
            if existing is None:
                by_id[img_id] = (size if is_jpg else -size, match.group(0))
                order.append(img_id)
                continue
            existing_size = existing[0]
            prefer = (is_jpg and existing_size < 0) or (is_jpg == (existing_size >= 0) and size > abs(existing_size))
            if prefer:
                by_id[img_id] = (size if is_jpg else -size, match.group(0))

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    for link in soup.find_all("link", attrs={"itemprop": "image"}):
        if isinstance(link, Tag):
            href = link.get("href")
            if isinstance(href, str):
                add(href)

    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-lazy-src", "data-zoom-image"):
            val = img.get(attr)
            if isinstance(val, str):
                add(val)

    for source in soup.find_all("source"):
        if not isinstance(source, Tag):
            continue
        for attr in ("srcset", "data-srcset", "data-lazy-srcset"):
            val = source.get(attr)
            if isinstance(val, str):
                add(val)

    urls: List[str] = []
    for img_id in order:
        if img_id in by_id:
            urls.append(by_id[img_id][1])
            if len(urls) >= 12:
                break
    return urls


class TurnerMotorsportAdapter(RetailerCrawlerAdapter):
    """
    Turner Motorsport adapter.

    Fetcher tier: ``tls`` — Cloudflare TLS-fingerprint block.

    Discovery: ``CRAWLER_TURNERMOTORSPORT_START_URLS`` wins. Otherwise walk
    ``/sitemap_index.xml`` → ``/sitemap_product_<N>.xml`` children via the
    TLS fetcher, regex-extracting ``/p-<digits>-<slug>/`` URLs from the
    malformed sitemap bodies.

    Parsing: schema.org microdata (no JSON-LD). ``itemprop="mpn"`` becomes
    ``part_number``; ``itemprop="sku"`` (Turner's T#) is ignored.
    """

    ADAPTER_NAME: ClassVar[str] = "turnermotorsport"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Env override wins; otherwise walk the sitemap and
        fall back to ``DEFAULT_START_URLS`` if discovery returns nothing.
        """
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
        Fetch ``/sitemap_index.xml`` through the TLS fetcher, then each
        ``/sitemap_product_<N>.xml`` child. Returns the concatenated list of
        ``/p-<digits>-<slug>/`` URLs, empty on any failure.
        """
        try:
            index_text = self.fetcher.fetch(SITEMAP_INDEX_URL, timeout=30)
        except Exception:
            return []
        child_urls = _extract_sitemap_index_children(index_text)
        if not child_urls:
            return []

        seen: set[str] = set()
        product_urls: List[str] = []
        for i, child_url in enumerate(child_urls):
            if i > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                child_text = self.fetcher.fetch(child_url, timeout=60)
            except Exception:
                continue
            for u in _extract_urls_from_malformed_sitemap(child_text):
                if u in seen:
                    continue
                seen.add(u)
                product_urls.append(u)
        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Turner Motorsport product page. Microdata only (no JSON-LD).
        Returns ``None`` if no product name or the URL is not a product page.
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
            part_manufacturer=_extract_part_manufacturer(soup),
            part_number=_extract_part_number(soup),
            image_urls=_extract_images(soup) or None,
        )
