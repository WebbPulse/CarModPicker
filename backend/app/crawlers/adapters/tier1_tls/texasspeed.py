"""
Texas Speed & Performance (texas-speed.com) crawler adapter — Tier 1 (TLS).

Product URLs: ``https://www.texas-speed.com/brand/<brand-slug>/p-<sku-slug>/``
(Magento 2 on the Hyva frontend theme).

Fetcher: Cloudflare returns a ``Just a moment...`` interactive challenge to
plain ``requests`` and to curl with a full current-Chrome header set — every
path except ``/robots.txt`` is gated. ``curl_cffi`` with ``impersonate="chrome"``
clears the handshake, so ``FETCHER_TIER = "tls"``. Same profile as Cobb and
Turner; if the challenge escalates to a managed JS challenge, promote to
``"browser"`` without touching the parser.

Discovery: ``/sitemap/sitemap.xml`` is the sitemap **index** and points at a
handful of ``/media/sitemap/sitemap-1-<N>.xml`` child urlsets (5000 URLs each).
Note that the default Magento path ``/sitemap.xml`` also responds 200 on this
origin, but it is a stale 23k-URL urlset pointing at ``mcprod.texas-speed.com/*``
— those 302 to ``www.texas-speed.com/<same>.html`` where every URL is a
Magento ``no-route`` 404. The correct sitemap is the one under
``/sitemap/sitemap.xml``. Override via ``CRAWLER_TEXASSPEED_START_URLS``.

Parsing: JSON-LD ``Product`` at the page root (not inside ``@graph``). Pages
for products with size/oversize variants (e.g. pistons) instead emit
``@type: "ProductGroup"`` with ``hasVariant: [Product, ...]``; the parent
ProductGroup carries the same field set (name/sku/mpn/brand/image/description/
offers as AggregateOffer with ``lowPrice``), so we fall back to it directly
when the shared Product extractor returns nothing. Fields:

- **name** — clean, no site-name suffix.
- **brand.name** — clean brand (``"Texas Speed & Performance"``,
  ``"Procharger"``, ``"PRW"``, etc.). Authoritative.
- **mpn** — manufacturer part number (``CHOPacabra``, ``2634600``,
  ``12586768``). Preferred ``part_number``.
- **sku** — Texas Speed's internal, brand-prefixed retailer SKU
  (``TSP-CHOPacabra``, ``PRW-2634600``, ``PRO-1DH305-SCI``). We only use this
  when ``mpn`` is absent, so cross-retailer dedupe via ``mpn`` works where
  possible and we still keep a listing-local identifier where not.
- **offers.price** — clean USD string.
- **image** — single ``_1.jpg`` main photo. For multi-image products the Hyva
  theme embeds a JSON array under ``"images": [...]`` (``thumb``/``img``/
  ``full``/``position``/``isMain``/``type``) on the page. We extract ``full``
  URLs from that array (ordered by ``position``) and fall back to the JSON-LD
  ``image`` when the gallery JSON is absent.

Default manufacturer: Texas Speed's catalog is mostly third-party brands with
their own JSON-LD ``brand.name`` set (Procharger, PRW, GM, Whipple, Magnaflow,
…), so in practice the default rarely fires. When brand is missing we default
to ``"Texas Speed & Performance"`` rather than running the title-first-word
heuristic, which would grab product words like ``"Stage"`` or ``"Camshaft"``.
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

TEXASSPEED_BASE = "https://www.texas-speed.com"
SITEMAP_INDEX_URL = f"{TEXASSPEED_BASE}/sitemap/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical product URL shape on the Hyva frontend:
# /brand/<brand-slug>/p-<sku-slug>/  (trailing slash as shipped in sitemap).
_PRODUCT_PATH_RE = re.compile(
    r"^/brand/[a-z0-9][a-z0-9\-]*/p-[a-z0-9][a-z0-9\-]*/?$",
    re.IGNORECASE,
)

# Default manufacturer when JSON-LD brand is absent. Texas Speed is a
# multi-brand retailer that almost always ships brand.name, so this fires
# rarely; when it does, assigning the house brand beats running the
# title-first-word heuristic which picks up product words as manufacturers.
_DEFAULT_MANUFACTURER = "Texas Speed & Performance"

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://www.texas-speed.com/brand/texas-speed-performance/p-tsp-chopacabra-tsp-chopacabra-truck-cam/",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` matches the ``/brand/<slug>/p-<slug>/`` product shape on texas-speed.com."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.query:
        # robots.txt disallows /*? — any URL with query params is off limits.
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "texas-speed.com" or host.endswith(".texas-speed.com")):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_TEXASSPEED_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_TEXASSPEED_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _find_product_group_json_ld(html: str) -> Optional[Dict[str, Any]]:
    """
    Find the first top-level ``ProductGroup`` JSON-LD block on the page.

    Texas Speed emits ``@type: "ProductGroup"`` (with ``hasVariant: [Product,
    ...]``) for product family pages that have size/oversize variants — the
    parent URL itself isn't a variant, so the shared ``extract_json_ld_product``
    returns None on these. The parent ProductGroup carries the full set of
    fields we need (``name``, ``sku``, ``mpn``, ``brand``, ``image``,
    ``description``, ``offers`` as AggregateOffer with ``lowPrice``), so we
    can feed it straight into ``scraped_payload_from_json_ld`` without
    descending into the variants.
    """
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            items = cast(List[Dict[str, Any]], data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = cast(List[Dict[str, Any]], data["@graph"])
            else:
                items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "ProductGroup" or (isinstance(t, list) and "ProductGroup" in t):
                return item
    return None


def _extract_gallery_full_urls(html: str) -> List[str]:
    """
    Extract ``full`` URLs from the Hyva theme gallery JSON embedded on the page.

    The multi-image gallery is serialized as ``"images": [ {thumb, img, full,
    caption, position, isMain, type, videoUrl}, ... ]``. Standard JSON with
    escaped slashes inside a larger Alpine ``x-data`` block — not a ``<script
    type="application/ld+json">`` tag. We locate the ``"images": [`` marker
    and walk bracket depth (skipping contents inside quoted strings) until the
    array closes, then ``json.loads`` it and return the ``full`` URLs in
    ``position`` order.

    Single-image products embed exactly one item in the array; products with
    no gallery JSON (rare) return [] so the caller can fall back to JSON-LD
    ``image``.
    """
    marker = '"images": ['
    idx = html.find(marker)
    if idx < 0:
        return []
    start = idx + len('"images":')
    depth = 0
    end = start
    in_str = False
    esc = False
    for k in range(start, min(start + 200_000, len(html))):
        c = html[k]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    else:
        return []

    try:
        data = json.loads(html[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    entries: list[tuple[int, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("type") and item.get("type") != "image":
            continue
        full = item.get("full")
        if not isinstance(full, str) or not full.strip():
            continue
        try:
            position = int(item.get("position") or 0)
        except (TypeError, ValueError):
            position = 0
        entries.append((position, full.strip()))

    entries.sort(key=lambda e: e[0])
    seen: set[str] = set()
    out: List[str] = []
    for _, u in entries:
        base = u.split("?", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        out.append(u)
    return out[:12]


class TexasSpeedAdapter(RetailerCrawlerAdapter):
    """
    Texas Speed & Performance adapter.

    Fetcher tier: ``tls`` — Cloudflare interactive challenge on every path but
    ``/robots.txt``; ``curl_cffi``'s Chrome TLS impersonation clears it.

    Discovery: ``CRAWLER_TEXASSPEED_START_URLS`` wins. Otherwise walk
    ``/sitemap/sitemap.xml`` (the index — **not** ``/sitemap.xml``, which is a
    stale ``mcprod.*`` urlset that 404s on www) → each ``sitemap-1-N.xml``
    child via the TLS fetcher, keeping only ``/brand/<slug>/p-<slug>/`` URLs.

    Parsing: JSON-LD Product is authoritative. ``mpn`` → ``part_number`` when
    present; ``sku`` (retailer-prefixed) is only used as fallback. Gallery
    images come from the Hyva ``"images": [...]`` JSON array when present,
    else JSON-LD ``image``.
    """

    ADAPTER_NAME: ClassVar[str] = "texasspeed"
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
        Fetch ``/sitemap/sitemap.xml`` via the TLS fetcher, then each child
        ``sitemap-1-N.xml`` urlset. Returns the concatenated list of
        product-shaped URLs, empty on failure.
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
            index_text = self.fetcher.fetch(SITEMAP_INDEX_URL, timeout=30)
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
                    child_text = self.fetcher.fetch(child_url, timeout=60)
                except Exception:
                    continue
                parse_urlset_locs(child_text)
        else:
            parse_urlset_locs(index_text)

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Texas Speed product page. JSON-LD Product is authoritative.
        Returns None when the URL is not product-shaped or when JSON-LD is
        missing / malformed (typical soft-404 landing pages).
        """
        if not _is_product_url(url):
            return None

        item = extract_json_ld_product(html, product_url=url)
        if not item:
            item = _find_product_group_json_ld(html)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        # Prefer mpn (clean manufacturer PN) over sku (brand-prefixed retailer
        # SKU like "TSP-CHOPacabra"). scraped_payload_from_json_ld already
        # picked sku-or-mpn; redo the preference here so cross-retailer dedupe
        # on mpn still matches Texas Speed rows.
        mpn_val = item.get("mpn") if isinstance(item, dict) else None
        part_number: Optional[str] = None
        if isinstance(mpn_val, str) and mpn_val.strip():
            part_number = normalize_part_number(mpn_val)
        if not part_number:
            part_number = normalize_part_number(payload.part_number) if payload.part_number else None

        part_manufacturer = (payload.part_manufacturer or "").strip() or _DEFAULT_MANUFACTURER

        gallery_images = _extract_gallery_full_urls(html)
        image_urls = gallery_images or (payload.image_urls or None)

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        if title_tag and title_tag.get_text(strip=True).startswith("404 Not Found"):
            return None

        return ScrapedPayload(
            name=payload.name,
            product_url=url,
            description=payload.description,
            price_cents=payload.price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )
