"""
APR LLC (goapr.com) crawler adapter — Tier 1 (TLS).

Product URLs: ``https://www.goapr.com/products/<category>/.../parts/<PART_ID>``

APR is the largest VAG software vendor (ECU upgrades, TCU tunes) and also sells
hardware (catbacks, intakes, intercoolers, downpipes, wheels). The backlog
prioritizes them for hardware coverage — VAG cross-shoppers compare APR against
034 and IE. Software pricing is reference-only (no arbitrage), but still useful
for build-list completeness.

Fetcher tier: ``tls``. Plain ``requests`` / ``curl`` hit Cloudflare's
``cf-mitigated: challenge`` rule (HTTP 403 with the Sec-CH-UA ACC-CH list
response); curl_cffi's Chrome impersonation passes. No JS challenge has been
observed — if CF adds one, promote to the browser tier without touching the
parser.

Discovery: ``/sitemap/`` is a ``sitemapindex`` pointing at per-category
``/sitemap_products/<category>/`` urlsets (``exhaust_systems``, ``software``,
``engine_hardware``, ``wheel``, ``brakes``, ``suspension``, ``transmission``,
``packages``, ``fluids``, ``cosmetics_and_gear``, ``electronics``, ``deals``,
``discontinued``). Each urlset is flat: category landing pages (no ``/parts/``
segment) mixed with product URLs (``/parts/<PART_ID>``). We filter to
``/parts/<id>``. Platform, brand, blog, support, and other sitemaps are
skipped — they contain navigation pages, not product SKUs.

Override the sitemap walk with ``CRAWLER_APR_START_URLS`` (comma-separated).

Parsing: APR emits no JSON-LD. Every product page carries the full product
record in a single ``<script type="application/json" id="product_data">``
block — name, APR part number, ``mfg_partnumber`` (often empty on APR-branded
SKUs), brand (always "APR"), description, short description, UPC, price, and
an ordered image list. That blob is the authoritative source; DOM fallback is
unnecessary.

Images live at ``https://images.goapr.com/<filename>``. Filenames are usually
40-hex SHA-like hashes (``0f25efea....jpg``) but can be plain names on older
SKUs (``apr-ecu-box.png``). We keep the ``default`` image first, then
``additional`` and ``lifestyle`` entries in their JSON order. Other image
types (``attribute``, ``installation``, ``promo``) are skipped — they are
variant-color swatches, install diagrams, or marketing banners, not the
gallery.

Brand: APR's catalog is first-party — every SKU emits ``"brand": "APR"`` in
``product_data``. When the field is missing we default to ``"APR"`` rather
than running a title heuristic (titles are chassis-led, e.g. "APR MK8 Golf R
Catback Exhaust System", which would otherwise be mis-parsed as "APR" from
the first word anyway — but the default keeps behavior stable if APR's JSON
schema ever drops the brand field).

Part number: prefer ``mfg_partnumber`` when non-empty (some SKUs reference an
external manufacturer's code), otherwise ``partnumber`` (APR's own SKU, which
is also the MPN for APR-branded hardware).
"""

import json
import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
)

APR_BASE = "https://www.goapr.com"
APR_IMAGE_BASE = "https://images.goapr.com"
SITEMAP_INDEX_URL = f"{APR_BASE}/sitemap/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

APR_BRAND = "APR"

# Product URL shape: /products/<category>/[<sub>/...]parts/<PART_ID>. The
# sitemaps also carry bare category URLs like /products/exhaust_systems/ and
# /products/software/ecu_upgrade/gasoline/4/; the ``/parts/<id>`` segment is
# what distinguishes an actual SKU page from a category listing.
_PRODUCT_PATH_RE = re.compile(
    r"^/products/[a-z0-9_][a-z0-9_\-/]*/parts/[A-Za-z0-9][A-Za-z0-9_\-]*/?$",
    re.IGNORECASE,
)

# Only walk product sitemaps. Platform, brand, blog, support, and "other"
# sitemaps contain navigation / landing pages, not product SKUs.
_PRODUCT_SITEMAP_PATH_RE = re.compile(r"/sitemap_products/", re.IGNORECASE)

# The JSON blob is a single <script type="application/json" id="product_data">
# element. It can carry a nonce attribute (CSP), so match id= liberally.
_PRODUCT_DATA_SCRIPT_RE = re.compile(
    r'<script[^>]*\bid="product_data"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

# Image type values in ``product_data.images`` that belong in the gallery.
# Skipped types (``attribute``, ``installation``, ``promo``, ``thumbnail``,
# etc.) are swatches / install diagrams / marketing art — not the product
# gallery the extension would surface.
_GALLERY_IMAGE_TYPES = frozenset({"default", "additional", "lifestyle"})

# Default smoke-test URL for a fresh run when the sitemap walk returns nothing
# (e.g. CF starts blocking the TLS fetcher and we want the adapter to still
# exercise ``parse_product_page`` end-to-end against a known-good SKU).
DEFAULT_START_URLS = [
    "https://www.goapr.com/products/exhaust_systems/catback_exhaust_systems/parts/CBK0052",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is an APR product SKU page (``/products/.../parts/<id>``)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "goapr.com" and not host.endswith(".goapr.com"):
        return False
    if parsed.query:
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_APR_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_APR_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _extract_product_data(html: str) -> Optional[dict]:
    """
    Return the parsed ``product_data`` JSON blob, or None if the page doesn't
    carry one (non-product page, soft-404, or the SKU is gone).
    """
    match = _PRODUCT_DATA_SCRIPT_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except (ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _price_cents_from_data(data: dict) -> Optional[int]:
    """
    Read the current price in cents from ``product_data``. ``price`` is the
    authoritative current-price field (APR sets it to the promo price if one
    is active, otherwise the web/retail price). Fall back to the first
    ``web``-type entry in ``pricing`` when ``price`` is missing or non-numeric.
    """
    raw = data.get("price")
    if isinstance(raw, (int, float)) and raw >= 0:
        return int(round(float(raw) * 100))
    pricing = data.get("pricing")
    if isinstance(pricing, list):
        for entry in pricing:
            if not isinstance(entry, dict):
                continue
            if entry.get("type") != "web":
                continue
            val = entry.get("price")
            if isinstance(val, (int, float)) and val >= 0:
                return int(round(float(val) * 100))
    return None


def _part_number_from_data(data: dict) -> Optional[str]:
    """
    Prefer ``mfg_partnumber`` when non-empty (external OEM / co-branded SKUs
    sometimes reference a manufacturer code). Otherwise use ``partnumber``,
    which is APR's own SKU and serves as the MPN for APR-branded hardware.
    """
    mfg = data.get("mfg_partnumber")
    if isinstance(mfg, str) and mfg.strip():
        return normalize_part_number(mfg)
    part = data.get("partnumber")
    if isinstance(part, str) and part.strip():
        return normalize_part_number(part)
    return None


def _gtin_from_data(data: dict) -> Optional[str]:
    """Return ``upc`` when present and non-empty, else None."""
    upc = data.get("upc")
    if isinstance(upc, str) and upc.strip():
        return upc.strip()
    return None


def _description_from_data(data: dict) -> Optional[str]:
    """
    Prefer the long ``description`` field, falling back to ``shortdescription``
    when it's missing (some software SKUs ship only the short line). Both are
    plain text on APR — HTML entities get decoded and whitespace collapsed
    through the shared helper.
    """
    for key in ("description", "shortdescription"):
        raw = data.get(key)
        if isinstance(raw, str) and raw.strip():
            normalized = normalize_description_text(raw, max_len=2000)
            if normalized:
                return normalized
    return None


def _image_urls_from_data(data: dict) -> List[str]:
    """
    Build the product gallery from ``product_data.images``. Keep entries whose
    ``type`` is in ``_GALLERY_IMAGE_TYPES`` (default / additional / lifestyle)
    in their JSON order, dedupe by filename, and expand each to
    ``https://images.goapr.com/<filename>``. Capped at 12.
    """
    images = data.get("images")
    if not isinstance(images, list):
        return []
    urls: List[str] = []
    seen: set[str] = set()
    for entry in images:
        if not isinstance(entry, dict):
            continue
        img_type = entry.get("type")
        if not isinstance(img_type, str) or img_type not in _GALLERY_IMAGE_TYPES:
            continue
        filename = entry.get("filename")
        if not isinstance(filename, str) or not filename.strip():
            continue
        key = filename.strip()
        if key in seen:
            continue
        seen.add(key)
        urls.append(f"{APR_IMAGE_BASE}/{key}")
        if len(urls) >= 12:
            break
    return urls


def _name_from_data(data: dict) -> Optional[str]:
    """Trim and validate the product name; reject blank / too-short values."""
    raw = data.get("name")
    if not isinstance(raw, str):
        return None
    name = raw.strip()
    if len(name) < 3:
        return None
    return name


class APRAdapter(RetailerCrawlerAdapter):
    """
    APR LLC adapter.

    Fetcher tier: ``tls`` — plain requests get Cloudflare's managed challenge
    response; curl_cffi Chrome impersonation passes.

    Discovery: ``CRAWLER_APR_START_URLS`` wins. Otherwise walk ``/sitemap/``
    via the TLS fetcher, pull children under ``/sitemap_products/``, and
    extract ``/parts/<id>`` URLs from each flat urlset.

    Parsing: ``<script type="application/json" id="product_data">`` is the
    single source of truth — name, APR SKU, brand ("APR" default),
    description, images, UPC, and current price.
    """

    ADAPTER_NAME: ClassVar[str] = "apr"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; otherwise walk the sitemap."""
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
        Fetch ``/sitemap/`` via the TLS fetcher and walk children matching
        ``/sitemap_products/``. Returns every ``/parts/<id>`` URL found,
        deduped; empty list on any failure.
        """
        try:
            index_text = self.fetcher.fetch(SITEMAP_INDEX_URL, timeout=30)
        except Exception:
            return []
        try:
            root = ET.fromstring(index_text)
        except ET.ParseError:
            return []

        child_urls: List[str] = []
        for loc in _loc_elements(root):
            if not loc.text:
                continue
            u = loc.text.strip()
            if _PRODUCT_SITEMAP_PATH_RE.search(u):
                child_urls.append(u)
        if not child_urls:
            return []

        seen: set[str] = set()
        product_urls: List[str] = []
        for i, child_url in enumerate(child_urls):
            if i > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                child_text = self.fetcher.fetch(child_url, timeout=30)
            except Exception:
                continue
            try:
                child_root = ET.fromstring(child_text)
            except ET.ParseError:
                continue
            for loc in _loc_elements(child_root):
                if not loc.text:
                    continue
                u = loc.text.strip()
                if not _is_product_url(u):
                    continue
                if u in seen:
                    continue
                seen.add(u)
                product_urls.append(u)
        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an APR product page. Returns ``None`` when the URL is not a
        product SKU page or when the ``product_data`` JSON blob is missing /
        unparseable — both indicate the page isn't an ingestable product.
        """
        if not _is_product_url(url):
            return None

        data = _extract_product_data(html)
        if data is None:
            return None

        name = _name_from_data(data)
        if not name:
            return None

        brand = data.get("brand")
        part_manufacturer = brand.strip() if isinstance(brand, str) and brand.strip() else APR_BRAND

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=_description_from_data(data),
            price_cents=_price_cents_from_data(data),
            part_manufacturer=part_manufacturer,
            part_number=_part_number_from_data(data),
            image_urls=_image_urls_from_data(data) or None,
            gtin=_gtin_from_data(data),
        )
