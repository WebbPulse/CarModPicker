"""
Katech Engines (katechengines.com) crawler adapter.

Katech is the reference retailer for LT-specific internals and SC systems
(C7/C8 Corvette, CT4/CT5-V Blackwing) plus LS race engines and GM forced
induction — the LT-side overlap that Texas Speed's LS-biased catalog does not
fully cover.

**Domain note.** The v2 backlog listed ``katech.com``; that host actually
belongs to Kinetic Art & Technology (a motion-system / electric-motor shop,
unrelated). The engine builder lives at ``katechengines.com``. The host
routing in ``adapters/__init__.py`` points only at the engine-builder domain
so chrome-extension captures from the unrelated site fall through to
``generic``.

Platform: Web Shop Manager (custom e-commerce, ``https://webshopmanager.com``).
No JSON-LD Product block, but each product page emits schema.org **microdata**
on a predictable DOM skeleton:

- ``<h1 itemprop="name" class="wsm-prod-title">`` — product name.
- ``<span class="wsm-prod-sku" itemprop="sku">`` — SKU (``KAT-XXX``).
- ``<div itemprop="offers">`` with nested ``<span itemprop="price">`` and
  ``<link itemprop="availability">``.
- ``<div itemprop="description" class="wsm-prod-tab-content">`` — HTML-formatted
  description (line-breaks, bolds) that we flatten via
  ``normalize_description_text``.
- ``<a itemprop="brand" href="/b-<id>-<slug>.html">Katech Engineering</a>`` —
  populated on every in-catalog SKU.

SKUs are retailer-prefixed (``KAT-A4824``, ``KAT-C7ZR1-1``) but Katech is
both the manufacturer and the retailer here, so the prefixed SKU *is* the
MPN — we keep it as-is rather than guessing at a split.

Image gallery lives under ``<ul class="wsm_product_thumbs">`` with one
``<li class="wsm_product_thumb">`` per photo; each thumbnail anchor points
at the full-size image under ``/images/F<N>.<ext>`` (the ``M`` prefix is
medium, ``T`` is thumbnail, ``F`` is full). We collect the ``F`` URLs and
fall back to the OG image (``/images/I<product-id>.jpg``) when the gallery
markup is absent — rare but a handful of legacy SKUs have only the single
auto-generated thumbnail.

Discovery: ``/sitemap.xml`` is a flat urlset (``sitemap_index.xml`` only
points at a gzipped copy of the same file). URLs are split by shape:

- ``/i-<id>-<slug>.html`` — products (priority 0.7).
- ``/c-<id>-<slug>.html`` — categories (priority 0.8).
- ``/p-<id>-<slug>.html`` — CMS content pages (priority 0.9).
- ``/rt-<id>-<slug>.html`` — resource type pages (priority 0.7 — shares the
  products bucket, so priority-filtering alone is not sufficient).
- ``/ft-<id>-<slug>.html`` — footer/legal pages (priority 0.6).
- ``/b-<id>-<slug>.html`` — brand landing pages.

We filter discovery by path shape (``/i-`` prefix, ``.html`` suffix), not
priority. Override with ``CRAWLER_KATECH_START_URLS`` (comma-separated) for
ad-hoc runs.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

KATECH_BASE = "https://katechengines.com"
SITEMAP_URL = f"{KATECH_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://katechengines.com/i-30497554-katech-c7-corvette-zr1-stage-1-package.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` looks like a Katech product page (``/i-<id>-<slug>.html``)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "katechengines.com" or host.endswith(".katechengines.com")):
        return False
    path = parsed.path or ""
    if not path.endswith(".html"):
        return False
    trimmed = path.strip("/")
    if "/" in trimmed:
        return False
    return trimmed.startswith("i-")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_KATECH_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_KATECH_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap() -> List[str]:
    """
    Walk the flat ``/sitemap.xml`` urlset and keep every URL whose path starts
    with ``/i-`` and ends in ``.html`` — i.e. products. Empty list on failure.
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
    for url_el in root.findall(url_tag):
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


def _find_scope(soup: BeautifulSoup, itemtype_suffix: str) -> Optional[Tag]:
    """
    Return the first element whose ``itemtype`` URL ends in ``itemtype_suffix``
    (e.g. ``"schema.org/Product"``). Katech mixes ``https`` and ``http`` schema
    URLs (Product uses ``https``, Brand uses ``http``), so we match on suffix
    rather than full URL to keep both sources working.
    """
    for tag in soup.find_all(attrs={"itemtype": True}):
        if not isinstance(tag, Tag):
            continue
        itemtype = tag.get("itemtype")
        if isinstance(itemtype, str) and itemtype.rstrip("/").endswith(itemtype_suffix):
            return tag
    return None


def _extract_name(scope: Tag) -> Optional[str]:
    tag = scope.find(attrs={"itemprop": "name"})
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(" ", strip=True)
    return text or None


def _extract_sku(scope: Tag) -> Optional[str]:
    tag = scope.find(attrs={"itemprop": "sku"})
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(strip=True)
    return text or None


def _extract_price_cents(scope: Tag) -> Optional[int]:
    """
    Read ``<span itemprop="price">175.99</span>`` from the hidden Offer scope.
    Katech renders the price plain-dollars; ``parse_price_cents`` handles the
    float → cents conversion and rejects non-positive values.
    """
    tag = scope.find(attrs={"itemprop": "price"})
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(strip=True)
    if not text:
        content = tag.get("content")
        if isinstance(content, str):
            text = content.strip()
    return parse_price_cents(text) if text else None


def _extract_description(scope: Tag) -> Optional[str]:
    tag = scope.find(attrs={"itemprop": "description"})
    if not isinstance(tag, Tag):
        return None
    # Katech ships the description with inline HTML (``<br>``, ``<div>``,
    # ``<strong>``); ``normalize_description_text`` flattens it.
    raw_html = tag.decode_contents()
    return normalize_description_text(raw_html, max_len=2000)


def _extract_brand(scope: Tag) -> Optional[str]:
    """
    Read the microdata ``<a itemprop="brand">Katech Engineering</a>``. Every
    in-catalog Katech SKU carries this anchor; we fall back to the Brand
    scope's nested ``itemprop="name"`` on the rare theme variant that emits
    one.
    """
    tag = scope.find(attrs={"itemprop": "brand"})
    if not isinstance(tag, Tag):
        return None
    name_child = tag.find(attrs={"itemprop": "name"})
    if isinstance(name_child, Tag):
        text = name_child.get_text(" ", strip=True)
        if text:
            return text
    # Anchor text form — ``<a itemprop="brand">Katech Engineering</a>``.
    text = tag.get_text(" ", strip=True)
    return text or None


# Full-size image URLs on WSM are served under ``/images/F<digits>.<ext>`` —
# the ``M<digits>`` and ``T<digits>`` prefixes are medium and thumbnail sizes
# that we never store. Single-image pages render a ``colorbox[product]``
# anchor at the top of the product body; multi-image pages additionally wrap
# each photo in a ``<li class="wsm_product_thumb">`` inside
# ``<ul id="productImageBar">``. In both layouts, the ``<a href="…/F<N>.<ext>">``
# hrefs themselves are the same value — so we scan every href on the page
# and let ``seen``-dedup collapse the duplicate anchors the multi-image
# layout emits for the first photo.
_FULL_IMAGE_RE = re.compile(
    r"^https?://[^/]*katechengines\.com/images/F\d+\.(?:jpe?g|png|webp|gif)(?:\?[^\"'\s]*)?$",
    re.IGNORECASE,
)


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect full-size image URLs from the page in document order. Every
    anchor whose href matches ``/images/F<digits>.<ext>`` is a gallery image
    (no cross-sell bleed on WSM — related products link to ``/i-`` product
    pages, not image URLs). Fall back to the OG image when no F-anchor is
    present, which covers legacy SKUs that only rendered an auto-generated
    thumbnail.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw:
            return
        s = raw.strip()
        if s.startswith("//"):
            s = "https:" + s
        if not s.startswith("http"):
            return
        key = s.split("?", 1)[0]
        if key in seen:
            return
        seen.add(key)
        ordered.append(s)

    for anchor in soup.find_all("a", href=True):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not isinstance(href, str) or not _FULL_IMAGE_RE.match(href):
            continue
        add(href)

    if not ordered:
        og = soup.find("meta", property="og:image")
        if isinstance(og, Tag):
            add(meta_content(og))

    return ordered[:12]


class KatechAdapter(RetailerCrawlerAdapter):
    """
    Katech Engines adapter. Web Shop Manager storefront; plain HTTP fetches.

    Discovery: env override wins. Otherwise walk the flat ``/sitemap.xml``
    and keep every ``/i-<id>-<slug>.html`` path (products).

    Parsing: schema.org microdata. ``<h1 itemprop="name">`` + the Offer
    scope's ``itemprop="price"`` + ``itemprop="sku"`` +
    ``itemprop="description"`` + ``itemprop="brand"``; gallery via the
    ``wsm_product_thumbs`` DOM with an OG-image fallback.
    """

    ADAPTER_NAME: ClassVar[str] = "katech"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def infer_category_for_part(self, parsed: ScrapedPayload) -> Optional[str]:
        """Pin category to ``engine`` unless a more-specific slug applies.

        Katech ships engine builds, internals (pistons, rods, cams, head
        studs), and dyno/tuning services — every SKU is engine-domain.
        Tier-2 audit (2026-05-02): default here so platform-named
        products ("LS7 7.0L Stage 2") that don't surface a part-class
        keyword still land in ``engine`` instead of ``other``.
        """
        from app.core.category_inference import infer_category

        inferred = infer_category(parsed.name, parsed.description)
        if inferred and inferred not in ("other", "engine"):
            return inferred
        return "engine"

    def discover_product_urls(self) -> Iterator[str]:
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
        Parse a Katech product page. Returns ``None`` when the URL is not
        product-shaped or when no microdata Product block is found (typical
        WSM soft-404 / discontinued-SKU landing page).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        product_scope = _find_scope(soup, "schema.org/Product")
        if product_scope is None:
            return None

        name = _extract_name(product_scope)
        if not name or len(name) < 3:
            return None

        offer_scope = _find_scope(soup, "schema.org/Offer") or product_scope
        price_cents = _extract_price_cents(offer_scope)

        part_number = normalize_part_number(_extract_sku(product_scope))
        description = _extract_description(product_scope)
        part_manufacturer = _extract_brand(product_scope)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
