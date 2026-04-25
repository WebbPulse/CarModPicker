"""
Apex Wheels (apexwheels.com) crawler adapter.

Apex rebranded from "Apex Race Parts" to "Apex Wheels" and migrated off
Shopify onto a Nuxt + Sanity CMS + Vercel stack. The old storefront at
``www.apexraceparts.com/products/<handle>`` no longer exists; requests to
``apexraceparts.com`` 301-redirect to ``https://apexwheels.com/`` (root),
not a matching path. We also handle captured pages that still carry the
old ``apexraceparts.com`` host (Chrome-extension submissions, archive
rescrapes of stored HTML) by routing both hosts to this adapter in
``adapter_name_for_product_url``.

**Fetch blocker:** every surface on ``apexwheels.com`` — including
``/robots.txt`` and ``/sitemap.xml`` — is behind **Vercel Security
Checkpoint** (the ``[data-astro-cid-nbv56vs3]`` JS challenge served via
``/.well-known/vercel/security/static/challenge.v2.min.js``). Plain
``requests`` / ``curl`` return HTTP 429 + the challenge HTML regardless of
UA. TLS impersonation alone (Tier 1) is not enough either, because the
challenge needs JS execution and a cookie round-trip before the real page
is served. Hence ``FETCHER_TIER = "browser"`` — the runner swaps in
FlareSolverr (Tier 2) once ``FLARESOLVERR_URL`` is configured. See
``site_problem_notes/apexwheels.md`` for the probe log.

**Current scope:** parse-only. ``parse_product_page`` handles HTML that
arrives via the Chrome extension (``POST /crawled-pages/scrape``) or the
archive rescrape pipeline — both route through
``adapter_name_for_product_url`` so registering ``apexwheels.com`` (and
``apexraceparts.com`` for legacy submissions) there gives captured pages
a site-specific parser instead of the generic fallback.
``discover_product_urls`` is a stub until Tier 2 is wired up; when it is,
the sitemap is the first thing to probe.

Product URL shape: ``/wheels/<tier>/<line>/<model>`` (e.g.
``/wheels/flow-formed/classic-line/arc-8``) or
``/accessories/<subcat>``. Categories have their own pages at the shorter
paths, so the guard requires at least three path segments for the wheels
tree and keeps ``/accessories/<slug>`` pages too — Apex sells center caps,
spacers, and hardware as standalone SKUs under ``/accessories/``.

Parsing strategy: JSON-LD ``Product`` is authoritative (Nuxt emits a
``[{Product}]`` list with ``name``, ``description``, ``sku``, ``image``,
``offers``), then OG / meta fallback for pages that lack structured data.

- **Manufacturer default / collapse:** Apex's catalog is almost entirely
  their own wheels (ARC-8, EC-7, SM-10, VS-5RS, FL-5, ML-10RT), track
  accessories, and wheel hardware. The JSON-LD does not carry a ``brand``
  field, so we default the manufacturer to ``"Apex"``. Vendor-field
  spellings ``"Apex Wheels"``, ``"Apex Race Parts"``, ``"APEX"``, and
  ``"Apex"`` all collapse to the one canonical ``"Apex"`` row so the
  global part-manufacturer table doesn't fragment across old/new brand
  names. Co-branded / resold third-party SKUs (e.g. PFC pads, G-LOC,
  Motul) that carry a distinct JSON-LD brand pass through unchanged.

Brand (the ``Why`` this retailer matters): Apex wheels are not resold
anywhere — neither Tire Rack nor Mackin carries them. This is the only
source of truth for the track community's default forged / flow-formed
wheel across BMW M, Porsche, Corvette, Civic Type R, and GR Corolla build
lists, which is why we eat the cost of a Tier 2 fetcher.
"""

import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

APEX_BASE = "https://apexwheels.com"

# Canonical manufacturer name. JSON-LD does not carry a brand field on Apex
# product pages, and the old Shopify vendor field historically showed up as
# any of ``"Apex Race Parts"``, ``"APEX"``, ``"Apex"`` (and now ``"Apex
# Wheels"`` post-rebrand). Collapse them all so the global part-manufacturer
# list isn't fragmented across old-brand / new-brand / shorthand rows that
# all mean the same company.
_APEX_CANONICAL_BRAND = "Apex"
_APEX_BRAND_VARIANTS = frozenset(
    {
        "apex",
        "apex wheels",
        "apex-wheels",
        "apexwheels",
        "apex race parts",
        "apex-race-parts",
        "apexraceparts",
        "apex race",
    }
)

# Product page path shapes on apexwheels.com:
#   /wheels/<tier>/<line>/<model>         e.g. /wheels/flow-formed/classic-line/arc-8
#   /accessories/<subcat>                 e.g. /accessories/wheel-hardware
#
# The wheels tree requires >=4 segments (``/wheels``, tier, line, model) so
# we don't misclassify category landings like ``/wheels/flow-formed`` or
# ``/wheels/flow-formed/classic-line``. The accessories tree is only 2
# segments deep (``/accessories`` + slug) because each subcategory *is*
# shoppable — e.g. ``/accessories/hubcentric-wheel-centering-rings`` is a
# product, not a listing.
_WHEELS_PRODUCT_RE = re.compile(
    r"^/wheels/[^/]+/[^/]+/[^/]+/?$",
    re.IGNORECASE,
)
_ACCESSORY_PRODUCT_RE = re.compile(
    r"^/accessories/[^/]+/?$",
    re.IGNORECASE,
)


def _is_apex_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of Apex's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _APEX_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for an Apex product.

    - Empty / any Apex self-spelling (``"APEX"``, ``"Apex Wheels"``,
      ``"Apex Race Parts"``) collapses to the single canonical ``"Apex"``.
    - Anything else (rare co-branded SKU like PFC pads or Motul fluid)
      passes through unchanged so the global part-manufacturer table gets
      a real third-party row.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_apex_brand_variant(brand):
        return _APEX_CANONICAL_BRAND
    return brand


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is a product-shaped page on ``apexwheels.com``.

    Shapes accepted:
        /wheels/<tier>/<line>/<model>       (four path segments)
        /accessories/<subcat>                (two path segments)

    Category landings (``/wheels/flow-formed`` → two segments,
    ``/wheels/flow-formed/classic-line`` → three segments) are rejected
    because they list multiple model pages rather than being shoppable.

    Also accepts legacy ``apexraceparts.com/products/<handle>`` URLs so
    captured HTML from before the rebrand still routes to this parser —
    the actual page body is no longer reachable, but the ingest pipeline
    may still replay archived copies through ``parse_product_page``.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host not in {
        "apexwheels.com",
        "www.apexwheels.com",
        "apexraceparts.com",
        "www.apexraceparts.com",
    }:
        return False
    path = parsed.path or ""
    # Legacy Shopify shape — accept for archive-replay routing only.
    if host.endswith("apexraceparts.com") and path.startswith("/products/") and len(path.split("/")) >= 3:
        return True
    if _WHEELS_PRODUCT_RE.match(path):
        return True
    if _ACCESSORY_PRODUCT_RE.match(path):
        return True
    return False


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Gallery images from the DOM. Apex runs on Nuxt + Sanity, so product
    media lives on the Sanity CDN (``cdn.sanity.io/images/...``) — we also
    accept same-origin absolute URLs for any local fallback asset.

    og:image is the canonical hero; remaining ``<img>`` tags are swept in
    document order and capped at 12 so picker thumbnails or related-product
    leaks from the page footer don't pad the gallery.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or len(urls) >= 12:
            return
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = APEX_BASE + u
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


class ApexWheelsAdapter(RetailerCrawlerAdapter):
    """
    Apex Wheels adapter (successor to Apex Race Parts after the 2024
    rebrand).

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a no-op; flesh it out once Tier 2 is wired up — try ``/sitemap.xml``
    first (though the Vercel challenge gates that too, so it may need a
    warm FlareSolverr session).
    """

    ADAPTER_NAME: ClassVar[str] = "apexwheels"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Stub: live crawling requires FlareSolverr. The extension-capture path
        does not go through discovery, so returning an empty iterator is safe
        and keeps the runner from throwing when an operator accidentally
        kicks this adapter off before Tier 2 is deployed.
        """
        return iter(())

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Apex Wheels product page.

        JSON-LD Product is authoritative (Nuxt emits it as a single-element
        list ``[{...}]`` with name / description / sku / image / offers).
        Falls back to OG meta + DOM heuristics when JSON-LD is missing or
        incomplete. Returns ``None`` when the URL is not product-shaped or
        when no name can be recovered.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Nuxt / Sanity default on apexwheels.com).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                image_urls = payload.image_urls or (dom_images if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls[:12] if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback — no JSON-LD on the page (rare on Nuxt but
        # possible during SSR hiccups).
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

        # Apex's catalog is entirely first-party (ARC-8, EC-7, SM-10,
        # VS-5RS, FL-5, ML-10RT, wheel hardware). Default to the canonical
        # brand rather than running the title-first-word heuristic — the
        # title first word is usually a model code (``"ARC-8"``) which is
        # a product, not a manufacturer.
        part_manufacturer = _APEX_CANONICAL_BRAND

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
