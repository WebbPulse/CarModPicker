"""
Brian Tooley Racing (briantooleyracing.com) crawler adapter.

BTR is the reference-price retailer for LS / LT / Gen-III HEMI valvetrain
(cams, springs, rockers, pushrods). The RETAILER_BACKLOG entry guessed
BigCommerce; the live site is actually **Magento** — robots.txt lists the
``/catalog/product/view/`` and ``/catalogsearch/`` paths, and the product
pages emit the standard ``page-title-wrapper`` / ``product attribute
description`` / ``mage/gallery/gallery`` markup.

Fetcher tier: ``http`` — plain ``requests`` returns HTTP 200 on
``/robots.txt``, ``/sitemap.xml``, and product pages without any Cloudflare
interstitial.

Discovery: ``/sitemap.xml`` is a **flat urlset** (no index). It mixes
homepages, categories, CMS pages, and products in a single document and
distinguishes them via the ``<priority>`` tag:

- ``1.0`` — products (and the site root). ~5.8k URLs.
- ``0.5`` — categories and brand landing pages. ~400 URLs.
- ``0.2`` — CMS / policy pages. ~30 URLs.

A handful of ``<priority>1.0</priority>`` entries point at the legacy Magento
``/catalog/product/view/id/<N>`` URL shape, which ``robots.txt`` disallows.
We filter discovery to ``<priority>1.0</priority>`` entries whose path ends
in ``.html`` and is not the site root — that set is all products and nothing
else. Override with ``CRAWLER_BRIANTOOLEYRACING_START_URLS`` (comma-separated)
for ad-hoc runs.

Parsing: JSON-LD ``Product`` is authoritative (name, brand.name, sku, mpn,
offers.price, image). ``brand.name`` is populated per-SKU — ``"Brian Tooley
Racing"`` on house SKUs, ``"Procharger"`` / ``"Mopar"`` / ``"ARP"`` etc. on
the resold brands — so no static default manufacturer is needed.

Two augmentations on top of the shared JSON-LD helper:

- **Multi-image gallery.** The JSON-LD ``image`` field is a single URL; the
  real gallery lives in the Magento ``x-magento-init`` block keyed on
  ``"mage/gallery/gallery"`` with a ``"data":[{thumb,img,full,position,
  isMain,type}, ...]`` array. Same shape as the Hyva theme gallery that the
  Texas Speed adapter handles; we parse it locally and order by ``position``.
- **Description.** JSON-LD ``description`` is almost always empty on BTR;
  the product copy lives under ``<div class="product attribute description">
  <div class="value">...</div></div>``.

Title cleanup: BTR listing titles routinely carry a trailing ``" - <MPN>"``
token (``"03-08 5.7 HEMI CAM BOLT - MOPAR 06504429"``,
``"BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT - SP011-16"``). We strip
the suffix only when it exactly matches the JSON-LD MPN, so cross-retailer
display reads cleanly without guessing at a split.
"""

import json
import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

BTR_BASE = "https://briantooleyracing.com"
SITEMAP_URL = f"{BTR_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html",
]

# Trailing ``" - <token>"`` (or ``" – "`` / ``" — "`` / ``": "`` /
# ``", "``) suffix on a BTR title. We only strip when ``<token>`` exactly
# matches the JSON-LD MPN, so titles like ``"Gen V LT - Camshaft"`` stay
# intact (the trailing ``"Camshaft"`` is not an MPN).
_TRAILING_MPN_RE = re.compile(
    r"[\s,;:\-\u2013\u2014]+([A-Za-z0-9][A-Za-z0-9._/\-]*)\s*$",
)


def _is_product_url(url: str) -> bool:
    """True if ``url`` looks like a BTR product page (``/<slug>.html`` at root)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "briantooleyracing.com" or host.endswith(".briantooleyracing.com")):
        return False
    path = parsed.path or ""
    if not path.endswith(".html"):
        return False
    # Root-slug only — reject nested category URLs like
    # ``/camshafts-lifters-pushrods/camshafts/ls3-naturally-aspirated-cams.html``.
    trimmed = path.strip("/")
    if "/" in trimmed:
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_BRIANTOOLEYRACING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_BRIANTOOLEYRACING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap() -> List[str]:
    """
    Walk the flat ``/sitemap.xml`` urlset and return every ``<priority>1.0</priority>``
    entry whose path ends in ``.html`` at the site root — i.e. products, not
    categories (0.5), CMS pages (0.2), or the ``<priority>1.0</priority>`` site
    root. Empty list on failure.
    """
    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=30)
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []

    url_tag = f"{{{SITEMAP_NS}}}url"
    loc_tag = f"{{{SITEMAP_NS}}}loc"
    priority_tag = f"{{{SITEMAP_NS}}}priority"
    for url_el in root.findall(url_tag):
        priority_el = url_el.find(priority_tag)
        if priority_el is None or not priority_el.text:
            continue
        try:
            priority = float(priority_el.text.strip())
        except ValueError:
            continue
        # 1.0 is the products bucket on BTR (homepage also 1.0 but fails
        # _is_product_url because its path is "/").
        if priority < 0.99:
            continue
        loc_el = url_el.find(loc_tag)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip().split("?", 1)[0]
        if not _is_product_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        product_urls.append(url)

    return product_urls


# ``<script type="text/x-magento-init">{...}</script>`` on BTR products holds
# the gallery config under ``"mage/gallery/gallery"."data"``. Structure:
#   {"[data-gallery-role=gallery-placeholder]":{"mage/gallery/gallery":{
#     "data":[{"thumb":...,"img":...,"full":...,"position":"1","isMain":true,
#              "type":"image","videoUrl":null}, ...]
#   }}}
# We find the ``"mage/gallery/gallery"`` marker, then walk bracket depth to the
# closing ``]`` of its ``"data"`` array. Same approach as the Texas Speed Hyva
# gallery parser, but keyed on a different marker.
_GALLERY_MARKER = '"mage/gallery/gallery"'
_GALLERY_DATA_RE = re.compile(r'"data"\s*:\s*\[')


def _extract_gallery_full_urls(html: str) -> List[str]:
    """
    Extract ``full`` URLs from the Magento ``mage/gallery/gallery`` data array,
    ordered by ``position`` and deduplicated by the un-querystringed URL.

    Returns [] when the gallery JSON is absent or malformed — callers should
    then fall back to the single JSON-LD ``image``.
    """
    marker_idx = html.find(_GALLERY_MARKER)
    if marker_idx < 0:
        return []
    data_match = _GALLERY_DATA_RE.search(html, marker_idx)
    if not data_match:
        return []
    start = data_match.end() - 1  # position of the opening '['
    depth = 0
    end = start
    in_str = False
    esc = False
    for k in range(start, min(start + 500_000, len(html))):
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
        full = item.get("full") or item.get("img")
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


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Read the Magento ``<div class="product attribute description">
    <div class="value">...</div></div>`` block. JSON-LD ``description`` is
    almost always empty on BTR so this is the primary source.
    """
    container = soup.find("div", class_=re.compile(r"\bproduct attribute description\b"))
    if not isinstance(container, Tag):
        return None
    value = container.find("div", class_=re.compile(r"\bvalue\b"))
    target = value if isinstance(value, Tag) else container
    text = target.get_text(" ", strip=True)
    if not text:
        return None
    return normalize_description_text(text, max_len=2000)


def _strip_trailing_mpn(name: str, mpn: Optional[str]) -> str:
    """
    Drop a trailing ``" - <mpn>"`` (or comma/en-dash/em-dash separator) from
    the title when the token is exactly the JSON-LD MPN. Keeps the suffix
    intact when the trailing token isn't the real MPN — we don't guess at
    which of several dashes separates the product name from the SKU.
    """
    if not mpn:
        return name
    match = _TRAILING_MPN_RE.search(name)
    if not match:
        return name
    candidate = match.group(1).strip()
    if candidate.lower() != mpn.strip().lower():
        return name
    trimmed = name[: match.start()].rstrip(" ,;:-\u2013\u2014")
    return trimmed or name


class BrianTooleyRacingAdapter(RetailerCrawlerAdapter):
    """
    Brian Tooley Racing adapter. Magento storefront; plain HTTP fetches.

    Discovery: env override wins. Otherwise walk the flat ``/sitemap.xml`` and
    keep ``<priority>1.0</priority>`` root-slug ``.html`` entries (products).

    Parsing: JSON-LD ``Product`` for name/brand/sku/mpn/price; Magento
    ``mage/gallery/gallery`` ``"data"`` array for the image gallery; the
    ``product attribute description`` DOM block for the description.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; sitemap next; fixed fallback last."""
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
        Parse a BTR product page. JSON-LD Product is authoritative; returns
        None when the URL is not product-shaped, when JSON-LD is missing, or
        when no name can be recovered (typical Magento soft-404).
        """
        if not _is_product_url(url):
            return None

        # BTR 301s retired slugs (e.g. ``/ac-delco-oil-filter-pf46-19210283-...``
        # → ``/ac-delco-oil-filter-pf46-12731172.html``) to the canonical product
        # page; the fetcher follows, and the JSON-LD on the landed page declares
        # the canonical URL, not the requested one. The URL-strict helper then
        # rejects it. Retry without URL-matching and accept the result only when
        # it declares a same-host URL — that still excludes the Wix/a90shop
        # cross-product JSON-LD footgun (different host / unrelated product).
        item = extract_json_ld_product(html, product_url=url)
        if not item:
            fallback = extract_json_ld_product(html)
            if fallback:
                declared = fallback.get("url")
                if isinstance(declared, str) and _is_product_url(declared):
                    item = fallback
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        # Prefer mpn (clean manufacturer PN) over sku when both are present
        # and differ — mirrors the Texas Speed preference so cross-retailer
        # dedupe lines up on the same key.
        mpn_val = item.get("mpn") if isinstance(item, dict) else None
        mpn_str: Optional[str] = None
        if isinstance(mpn_val, str) and mpn_val.strip():
            mpn_str = mpn_val.strip()

        part_number = normalize_part_number(mpn_str) if mpn_str else None
        if not part_number:
            part_number = normalize_part_number(payload.part_number) if payload.part_number else None

        clean_name = _strip_trailing_mpn(payload.name, mpn_str)

        soup = BeautifulSoup(html, "html.parser")
        description = payload.description or _extract_description(soup)

        gallery_images = _extract_gallery_full_urls(html)
        image_urls = gallery_images or (payload.image_urls or None)

        return ScrapedPayload(
            name=clean_name,
            product_url=url,
            description=description,
            price_cents=payload.price_cents,
            part_manufacturer=payload.part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )
