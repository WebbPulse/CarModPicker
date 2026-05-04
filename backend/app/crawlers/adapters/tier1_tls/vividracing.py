"""
Vivid Racing (vividracing.com) crawler adapter — Tier 1 (TLS-impersonating fetcher).

Product URLs: https://www.vividracing.com/<slug>-p-<digits>.html
Vivid is behind Cloudflare with a TLS/JA3 fingerprint block (see
``site_problem_notes/vividracing.md``). Real-browser access from our egress works, so
the block is client-fingerprint based rather than IP-based. This adapter sets
``FETCHER_TIER = "tls"`` so the runner hands it a ``TlsFetcher`` (curl_cffi
with Chrome impersonation), which the TLS handshake check accepts.

Notes:

- Product URL pattern is ``/<slug>-p-<digits>.html``. The numeric suffix after
  ``-p-`` is Vivid's internal product id, **not** a manufacturer SKU; it's
  safe as a per-site dedup key but must not be written as ``part_number``.
- Slug encodes the manufacturer in the leading tokens (e.g.
  ``agency-power-oval-taper-air-filter-...`` → "Agency Power"). Used only as a
  last-resort manufacturer fallback when JSON-LD/meta do not supply one.
- ``Disallow: /*?*`` in robots.txt means any URL with a query string is off
  limits. ``canonicalize_url()`` already strips known tracking params, and
  ``discover_product_urls()`` drops anything that still has a query string.
- Vivid serves only gzipped sitemaps (``/sitemap_index.xml.gz`` and the
  per-section ``/sitemaps/sitemapNNN.xml.gz`` children it indexes); the
  bare ``/sitemap.xml`` and ``/sitemap_index.xml`` return a 404 HTML page.
  The ``Fetcher`` protocol returns decoded ``str``, so discovery bypasses
  it for the sitemap path and calls ``curl_cffi`` directly to pull raw
  bytes and ``gzip.decompress`` them. Falls back to ``DEFAULT_START_URLS``
  (or ``CRAWLER_VIVIDRACING_START_URLS``) when even the gzipped walk
  fails or yields nothing.
"""

import gzip
import logging
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
)
from app.crawlers.fetchers import DEFAULT_TLS_IMPERSONATE
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

VIVIDRACING_BASE = "https://www.vividracing.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
GZIPPED_INDEX_URL = VIVIDRACING_BASE + "/sitemap_index.xml.gz"
_GZIP_MAGIC = b"\x1f\x8b"

logger = logging.getLogger(__name__)

# Canonical product URL: /<slug>-p-<digits>.html. The slug is kebab-case ASCII;
# the numeric id after "-p-" is Vivid's internal product id (not an MPN).
_PRODUCT_PATH_RE = re.compile(r"^/([a-z0-9][a-z0-9\-]*)-p-(\d+)\.html$", re.IGNORECASE)

# Safe default so a fresh run exercises parsing against a single known URL
# even when sitemap discovery comes back empty (e.g. if Cloudflare starts
# blocking the TLS fetcher too). Override via CRAWLER_VIVIDRACING_START_URLS.
DEFAULT_START_URLS = [
    "https://www.vividracing.com/agency-power-oval-taper-air-filter-wrap-enclosed-top-tapers-bottom-tall-p-152475800.html",
]

# Manufacturer tokens in the leading slug that are actually car-make / generic
# words, not part manufacturers. Used by the slug-derived fallback so we don't
# assign "Bmw" or "Toyota" as a manufacturer.
_SLUG_MANUFACTURER_REJECT = frozenset(
    {
        "bmw",
        "audi",
        "mercedes",
        "porsche",
        "toyota",
        "honda",
        "lexus",
        "subaru",
        "nissan",
        "ford",
        "chevrolet",
        "chevy",
        "tesla",
        "hyundai",
        "kia",
        "genesis",
        "vw",
        "volkswagen",
        "mini",
        "dodge",
        "ram",
        "jeep",
        "infiniti",
        "acura",
        "mitsubishi",
        "mazda",
    }
)


def _is_product_url(url: str) -> bool:
    """True if ``url`` matches Vivid's ``/<slug>-p-<digits>.html`` pattern."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.query:
        # robots.txt disallows /*?*; any URL with a query string is off limits.
        return False
    host = (parsed.hostname or "").lower()
    if host and not host.endswith("vividracing.com"):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_VIVIDRACING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_VIVIDRACING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _manufacturer_from_slug(slug: str) -> Optional[str]:
    """
    Last-resort manufacturer fallback: take the leading 1–2 tokens of the URL
    slug up to the first car-make / generic product word / digit-bearing token.
    Returns Title-Cased name (e.g. "agency-power-oval-..." → "Agency Power").

    Capped at 2 tokens because real part manufacturers are almost always one
    or two words ("Perrin", "Agency Power", "VF Engineering"). Three leading
    tokens would frequently pick up descriptors like "Agency Power Oval".
    """
    if not slug:
        return None
    tokens = [t for t in slug.split("-") if t]
    if not tokens:
        return None
    lead: List[str] = []
    for t in tokens[:2]:
        low = t.lower()
        if low in _SLUG_MANUFACTURER_REJECT:
            break
        if any(ch.isdigit() for ch in t):
            # Once we hit a token with digits we're out of the brand and into
            # model/part territory (e.g. "agency-power-svg-2018-wrx").
            break
        lead.append(t)
    if not lead:
        return None
    return " ".join(tok.capitalize() for tok in lead)


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product image URLs: og:image first, then <img> tags. Normalizes
    protocol-relative and site-root paths to absolute https URLs. Capped at 12.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        if not raw or len(urls) >= 12:
            return
        u = raw.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = VIVIDRACING_BASE + u
        if not u.startswith("http"):
            return
        if u in seen:
            return
        seen.add(u)
        urls.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img", src=True):
        if not isinstance(img, Tag) or len(urls) >= 12:
            break
        src = img.get("src")
        if isinstance(src, str) and src.strip():
            add(src.strip())
    return urls[:12]


class VividRacingAdapter(RetailerCrawlerAdapter):
    """
    Vivid Racing adapter.

    Fetcher tier: ``tls`` — Vivid blocks plain requests at the TLS handshake,
    but lets curl_cffi's Chrome impersonation through (see site notes).

    Discovery: ``CRAWLER_VIVIDRACING_START_URLS`` env var wins. Otherwise we
    try ``/sitemap.xml`` via ``self.fetcher`` (so it goes through the TLS
    fetcher, not plain requests which the block page serves 403 to), extract
    any ``/<slug>-p-<digits>.html`` URLs, and fall back to
    ``DEFAULT_START_URLS`` if the sitemap returns nothing usable.

    Parsing: JSON-LD Product first (when present), then DOM/og fallback. We
    deliberately do NOT use the ``p-<digits>`` portion of the URL as a part
    number — it is Vivid's internal id, not a manufacturer SKU.
    """

    ADAPTER_NAME: ClassVar[str] = "vividracing"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Env override (``CRAWLER_VIVIDRACING_START_URLS``)
        wins; otherwise walks ``/sitemap.xml`` via the TLS fetcher. Falls back
        to ``DEFAULT_START_URLS`` when discovery fails or returns nothing.
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
        Walk ``/sitemap_index.xml.gz`` → each ``/sitemaps/sitemapNNN.xml.gz``
        child urlset and collect every ``/<slug>-p-<digits>.html`` URL.

        Vivid only serves gzipped sitemaps; the bare ``/sitemap.xml`` returns
        a 404 HTML page and the plain ``/sitemap_index.xml`` does the same.
        The ``Fetcher`` protocol returns decoded text, so this helper bypasses
        ``self.fetcher`` and uses ``curl_cffi`` directly to pull raw bytes,
        then ``gzip.decompress`` the payload. Returns [] on any failure and
        lets the caller fall back to ``DEFAULT_START_URLS``.
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
            from curl_cffi import requests as cc_requests  # type: ignore[import-not-found]
        except ImportError:
            return []

        try:
            session = cc_requests.Session(impersonate=DEFAULT_TLS_IMPERSONATE)
        except Exception:
            return []

        def fetch_gz_xml(url: str) -> Optional[str]:
            try:
                resp = session.get(url, timeout=20, allow_redirects="safe")
            except Exception:
                return None
            if getattr(resp, "status_code", 0) != 200:
                return None
            content = getattr(resp, "content", None)
            if not isinstance(content, (bytes, bytearray)) or len(content) < 2:
                return None
            # Servers sometimes serve .gz files with Content-Encoding: gzip
            # (double-encoded) and sometimes as raw gzip bytes with no encoding
            # header — and curl_cffi transparently decompresses only the former.
            # Treat the leading magic bytes as authoritative.
            payload = bytes(content)
            if payload[:2] == _GZIP_MAGIC:
                try:
                    payload = gzip.decompress(payload)
                except OSError:
                    return None
            try:
                return payload.decode("utf-8", errors="replace")
            except Exception:
                return None

        try:
            index_text = fetch_gz_xml(GZIPPED_INDEX_URL)
            if not index_text:
                return []
            try:
                root = ET.fromstring(index_text)
            except ET.ParseError:
                return []

            tag = root.tag
            if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
                child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
                for i, child_url in enumerate(child_sitemap_urls):
                    if i > 0:
                        time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                    child_text = fetch_gz_xml(child_url)
                    if child_text:
                        parse_urlset_locs(child_text)
            else:
                parse_urlset_locs(index_text)
        except Exception as e:
            logger.warning("Vividracing sitemap discovery failed: %s", e)
            return []
        finally:
            try:
                session.close()
            except Exception:
                pass

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Vivid Racing product page. JSON-LD Product first (authoritative
        when present), then DOM/og fallback. Never emits Vivid's internal
        ``p-<digits>`` id as ``part_number``.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD (when Vivid emits a Product block, it carries name / brand
        #    / mpn / offers, which is everything we need.)
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                description = payload.description
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = payload.part_manufacturer
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_from_title(payload.name) or _manufacturer_from_slug(
                        _slug_from_url(url)
                    )
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback.
        name: Optional[str] = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if isinstance(h1, Tag):
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
        if not name or len(name) < 3:
            return None

        description: Optional[str] = None
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            d = meta_content(og_desc)
            if d and d.strip():
                description = normalize_description_text(d, max_len=2000)
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000)

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if isinstance(sku_elem, Tag):
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        if not part_manufacturer:
            part_manufacturer = _manufacturer_from_slug(_slug_from_url(url))

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )


def _slug_from_url(url: str) -> str:
    """Return the slug portion of a Vivid product URL (everything before -p-<digits>.html)."""
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return ""
    m = _PRODUCT_PATH_RE.match(path)
    if not m:
        return ""
    return m.group(1)
