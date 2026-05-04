"""
Mishimoto (mishimoto.com) crawler adapter.

**Platform — Magento 2 + Hyva theme.** The response carries the dead-giveaway
``x-built-with: Hyva Themes`` header, and the URL shape matches classic
Magento 2 (product slugs live at the site root with a ``.html`` suffix,
category listings live under multi-segment paths like ``/truck-jeep/...``,
and gallery media sits under ``/media/catalog/product/``). ``robots.txt``
confirms the stack — ``/catalog/``, ``/catalogsearch/``, ``/customer/``,
``/checkout/``, ``/downloader/``, ``/pkginfo/`` are the Magento defaults.

**Sitemap shape.** ``robots.txt`` advertises
``https://www.mishimoto.com/sitemap.xml`` as a sitemap index with two
children at ``/media/sitemap/sitemap_full_us-1-N.xml`` (custom naming,
not Magento's default ``sitemap_N.xml``, not Shopify's
``sitemap_products_N.xml``). Each child is a flat ``<urlset>`` carrying
about 4.6k URLs — a mix of product pages, category pages, video/landing
pages, and CMS content. Products are the overwhelming majority.

**Discovery filter.** Product URLs are at depth 1 (one path segment) and
end in ``.html``; category pages live at depth >= 2 under
``/automotive/``, ``/truck-jeep/``, ``/mx-atv/`` etc. We reject depth >= 2
outright. For the depth=1 pool we still have to filter out CMS/landing
pages (``sale.html``, ``videos.html``, ``team-mishi.html``, ``automotive.html``
— the category anchor pages) and a handful of category pages that happen
to use single-word slugs (``radiators.html``, ``intakes.html``,
``catch-cans.html``, ``bundles.html``). A short deny-list of known
non-product slugs handles those. Anything else gets emitted; the parser
does a last-mile URL-match check (see below) to reject category pages
that slip through.

**SKU / part-number extraction.** Mishimoto's JSON-LD ``Product`` block
ships a clean ``sku`` field — the canonical Mishimoto part number
(e.g. ``MMRAD-TAC-24`` radiator, ``MMAI-TAC-24`` air intake,
``MMOC-RSX-02`` oil cooler, ``MMBE-TAC-24`` block-off). No ``mpn``,
no ``gtin*``; just ``sku``. The shared ``scraped_payload_from_json_ld``
helper reads that directly.

**Brand canonicalization — house brand, always.** Mishimoto's catalog is
effectively 100% house brand (cooling, intakes, apparel) and the JSON-LD
block *omits* the ``brand`` field — it encodes the manufacturer only as
``offers[0].seller.name`` (``"Mishimoto"``). The shared helper reads only
``brand``, so without intervention every part manufacturer would come
back ``None`` and the title heuristic (``part_manufacturer_from_title``)
would trip on the car make — Mishimoto names products like
*"Mishimoto Honda Civic Si Performance Aluminum Radiator"* and the
stock title heuristic picks up ``Honda`` / ``Ford`` / ``Subaru`` /
``BMW`` etc. as the "brand". We coerce the manufacturer to
``"Mishimoto"`` for every page (unconditional default), which is correct
for the whole catalog. ADRO and 034Motorsport both take the same
approach for the same reason — a single-brand storefront.

**Image gallery.** JSON-LD only carries the hero image. The Hyva-themed
gallery is Alpine.js-driven: a single ``<script>`` block sets
``window.productMediaMeta = {"images": [...]}`` with every gallery image
in three resolutions (``url`` — 700x700, ``thumb`` — 100x100,
``full`` — uncropped). We parse that blob out of the raw HTML with a
regex (the JSON is assigned to a global, not embedded in a
``<template>`` tag, so BeautifulSoup alone won't reach it) and prefer
the ``full`` variant per image. Size-parameter variants of the same
base filename collapse to one entry so width/height query strings don't
create dedupe noise. Capped at 12 to match other adapters.

**Fetcher tier — plain HTTP.** Curl'd fine with a normal desktop UA,
HTTP 200, no ``cf-mitigated``, no ``Just a moment…`` interstitial. No
signs of TLS fingerprint blocking (the response came back through
Varnish + Fastly, not Cloudflare). ``FETCHER_TIER`` stays at the default
``"http"``.
"""

import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.core.car_inference import generations_for_make_model_year_range
from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
    fetch_page,
)
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

MISHIMOTO_BASE = "https://www.mishimoto.com"
SITEMAP_INDEX_URL = f"{MISHIMOTO_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
BRAND_CANONICAL = "Mishimoto"

DEFAULT_START_URLS = [
    "https://www.mishimoto.com/performance-aluminum-radiator-2024-toyota-tacoma.html",
    "https://www.mishimoto.com/performance-air-intake-toyota-tacoma-2024-non-trailhunter-24.html",
]

# Depth-1 ``.html`` slugs that are NOT products — top-level CMS/landing pages
# and single-word category pages that emit ``"@type":"Product"`` JSON-LD for
# the first listed item (category pages on Hyva ship a Product schema block
# for SEO, which would otherwise be mis-ingested as the category page itself).
# Stored without the ``.html`` suffix; comparison is case-insensitive.
_NON_PRODUCT_SLUGS = frozenset(
    {
        # CMS / landing / brand pages
        "sale",
        "videos",
        "press",
        "team-mishi",
        "get-sponsored",
        "bogo-20-off",
        "evo-joe",
        "classic",
        "liquid-chill",
        "shop-all",
        "all-products",
        "best-sellers",
        "new-releases",
        "top-picks",
        "bundles",
        # Top-level category anchors (there's a full page at /<name>.html AND
        # a tree at /<name>/... — the .html page itself is a listing, not a
        # product).
        "automotive",
        "truck-jeep",
        "mx-atv",
        # Single-word category pages (sub-category listings at depth 1).
        "radiators",
        "intakes",
        "intake-systems",
        "fan-shrouds",
        "fan-clips",
        "catch-cans",
        "oil-coolers",
        "thermostats",
        "radiator-caps",
        "radiator-hoses",
        "intercoolers",
        "silicone-hoses",
        "coolant",
        "apparel",
        "stickers",
        "accessories",
        "universal-cooling-fans-oil-coolers",
    }
)

# Mishimoto's own SKU prefix family — every house-brand part number starts
# with ``MM`` followed by a product-class code (RAD / AI / OC / BE / BHD / BU /
# INT / SIL / TC / STC / HO …). A JSON-LD ``sku`` that matches this is a
# strong positive signal for a real product page; a JSON-LD ``sku`` that
# does NOT match is either a non-product or a third-party reseller SKU,
# neither of which we want to ingest here.
_MISHIMOTO_SKU_RE = re.compile(r"^MM[A-Z0-9]{1,6}[-_][A-Z0-9]", re.IGNORECASE)

# window.productMediaMeta = {"activeItem":0,"images":[...], ...};
# Hyva emits it as a global assignment in a plain <script> block. We pull
# the ``images`` array out with a balanced-ish bracket capture (regex is
# fine because the inner objects don't themselves contain ``]`` in string
# values — verified on recon pages). Matches anywhere on the page.
_PRODUCT_MEDIA_META_RE = re.compile(
    r"window\.productMediaMeta\s*=\s*\{[^{]*?\"images\"\s*:\s*(\[.*?\])\s*,\s*\"video\"",
    re.DOTALL,
)

# Size-parameter query patterns on Mishimoto Magento image URLs. Collapse
# ``?...&height=700&width=700...`` to a size-agnostic key so a thumb and a
# full image of the same photo don't both end up in the gallery. Same
# pattern as other Magento adapters (034Motorsport collapses
# ``/cache/<hash>/`` the same way).
_IMAGE_SIZE_PARAMS_RE = re.compile(
    r"[?&](?:optimize|bg-color|fit|height|width|canvas)=[^&]*",
    re.IGNORECASE,
)

# Image URLs that aren't product gallery media (site chrome, warranty seals,
# navigation icons). All legitimate gallery URLs live under
# ``/media/catalog/product/``.
_IMAGE_NOISE_RE = re.compile(
    r"/static/|/images/mseal|/frontend/Mishimoto/mishimoto/en_US/images/|placeholder|logo\.|favicon|sprite",
    re.IGNORECASE,
)

# Image gallery cap (matches other adapters; ingest truncates to 12 anyway).
_MAX_GALLERY_IMAGES = 12


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk the sitemap; fall back to DEFAULT_START_URLS."""
    raw = os.environ.get("CRAWLER_MISHIMOTO_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _slug_from_url(url: str) -> str:
    """Return the final path segment without the ``.html`` suffix, lowercased."""
    try:
        path = urlparse(url).path
    except ValueError:
        return ""
    tail = path.rsplit("/", 1)[-1]
    if tail.endswith(".html"):
        tail = tail[: -len(".html")]
    return tail.lower()


def _looks_like_product_url(url: str) -> bool:
    """
    Mishimoto product URLs are a single ``.html`` slug at the site root
    (e.g. ``/performance-aluminum-radiator-2024-toyota-tacoma.html``).
    Multi-segment paths (``/truck-jeep/...``) are category pages — reject.
    CMS/landing slugs (``sale.html``, ``radiators.html``) are rejected by
    deny-list. Very short slugs are almost always category pages even if
    they aren't in the deny-list.
    """
    if not url or not url.endswith(".html"):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "mishimoto.com" and not host.endswith(".mishimoto.com"):
        return False
    # Depth = number of path segments. Root-only product slugs have path
    # ``/<slug>.html`` → segments=['', '<slug>.html'] after split on '/',
    # so one non-empty segment means depth 1.
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) != 1:
        return False
    slug = _slug_from_url(url)
    if not slug or slug in _NON_PRODUCT_SLUGS:
        return False
    # Product slugs on this site are descriptive and long. Under ~10 chars
    # is almost always a landing page we didn't put in the deny-list.
    if len(slug) < 10:
        return False
    return True


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (a sitemap index) and every child urlset it
    references, yielding deduplicated product URLs (query string stripped).
    Returns ``[]`` on any outer failure; per-child failures are ignored so
    one bad child doesn't abort the whole walk.

    Polite delay between child-sitemap fetches so we don't hammer Fastly.
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
            if not _looks_like_product_url(u):
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_text = fetch_page(SITEMAP_INDEX_URL, timeout=20)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                try:
                    child_text = fetch_page(child_url, timeout=30)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _normalize_image_url(raw: str) -> Optional[str]:
    """Upgrade protocol-relative / site-root URLs to absolute https. Reject data: / empty."""
    s = (raw or "").strip()
    if not s or s.startswith("data:"):
        return None
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return MISHIMOTO_BASE + s
    if s.startswith("http://"):
        return "https://" + s[len("http://") :]
    if not s.startswith("http"):
        return None
    return s


def _is_valid_product_image(url: str) -> bool:
    """Only Magento product media; reject site chrome, placeholders, seals."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if "/media/catalog/product/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _image_dedup_key(url: str) -> str:
    """
    Identity key for a Mishimoto product photo — the ``/media/catalog/product/``
    path with all size/cache query params stripped. Collapses the ``url``
    (700px), ``thumb`` (100px), and ``full`` (uncropped) resolutions of the
    same photo to one dedup bucket.
    """
    base = url.split("?", 1)[0]
    base = _IMAGE_SIZE_PARAMS_RE.sub("", base)
    return base.lower()


def _extract_gallery_images_from_meta(html: str) -> List[str]:
    """
    Pull the gallery images out of ``window.productMediaMeta.images`` (the
    Alpine.js-driven gallery data). Prefers each photo's ``full`` variant
    (uncropped, no height/width caps) over ``url`` / ``thumb``. Returns
    deduplicated list, capped at ``_MAX_GALLERY_IMAGES``.

    Returns an empty list on any parse failure — the caller falls back to
    the JSON-LD hero image or the og:image tag.
    """
    match = _PRODUCT_MEDIA_META_RE.search(html)
    if not match:
        return []

    raw_array = match.group(1)
    try:
        import json

        items = json.loads(raw_array)
    except (ValueError, TypeError):
        return []
    if not isinstance(items, list):
        return []

    ordered: List[str] = []
    seen: set[str] = set()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") not in (None, "image"):
            continue  # skip video entries
        # Prefer full (uncropped), then url (700x700), then thumb.
        for key in ("full", "url", "thumb"):
            raw = entry.get(key)
            if not isinstance(raw, str) or not raw.strip():
                continue
            normalized = _normalize_image_url(raw)
            if not normalized or not _is_valid_product_image(normalized):
                continue
            dedup = _image_dedup_key(normalized)
            if dedup in seen:
                break  # already captured this photo from a lower-priority key
            seen.add(dedup)
            ordered.append(normalized)
            if len(ordered) >= _MAX_GALLERY_IMAGES:
                return ordered
            break  # move to next photo after we pick one resolution
    return ordered


def _extract_dom_images_fallback(soup: BeautifulSoup) -> List[str]:
    """
    DOM-level image fallback for pages where ``productMediaMeta`` is missing
    or failed to parse. Walks the rendered ``<img>`` tags under the gallery
    and collects ``/media/catalog/product/`` URLs, size-deduped.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not isinstance(raw, str) or not raw.strip() or len(ordered) >= _MAX_GALLERY_IMAGES:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or not _is_valid_product_image(normalized):
            return
        dedup = _image_dedup_key(normalized)
        if dedup in seen:
            return
        seen.add(dedup)
        ordered.append(normalized)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content)

    gallery = soup.find(id="gallery")
    if isinstance(gallery, Tag):
        for img in gallery.find_all("img"):
            if not isinstance(img, Tag):
                continue
            for attr in ("src", "data-src", "data-original"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val)
                    break

    if not ordered:
        # Last resort: scan all <img> tags.
        for img in soup.find_all("img"):
            if not isinstance(img, Tag):
                continue
            if len(ordered) >= _MAX_GALLERY_IMAGES:
                break
            for attr in ("src", "data-src", "data-original"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val)
                    break

    return ordered


def _canonical_url(url: str) -> str:
    """Lowercase host + strip query/fragment so JSON-LD and fetched URLs compare equal."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    return f"https://{host}{path}".rstrip("/").lower()


def _json_ld_url_matches(item: Dict[str, Any], fetched_url: str) -> bool:
    """
    Category pages on Hyva emit a ``Product`` JSON-LD block for the first
    listed item, with ``"url"`` pointing at that item — NOT the category
    page URL. If the JSON-LD ``url`` doesn't match the URL we fetched, this
    is a category page dressed up as a product and we should reject it.
    """
    raw = item.get("url")
    if not isinstance(raw, str) or not raw.strip():
        # No url field → be lenient (real product pages usually include it,
        # but we don't want to hard-reject if Mishimoto ever drops the field).
        return True
    return _canonical_url(raw) == _canonical_url(fetched_url)


def _looks_like_mishimoto_sku(sku: Optional[str]) -> bool:
    """True if ``sku`` matches the ``MM<CLASS>-<REST>`` Mishimoto house-brand pattern."""
    if not sku or not sku.strip():
        return False
    return bool(_MISHIMOTO_SKU_RE.match(sku.strip()))


# Mishimoto product titles encode fitment as a ", fits <Make> <Model token(s)>
# [<engine/trim qualifiers>] <year-range>" suffix. The universal pipeline only
# matches single make+model phrases adjacent to each other and so misses these
# whenever the engine token sits between make+model and the year (or whenever
# the model is a sub-trim like "Mustang EcoBoost"). The hook below extracts
# the suffix, identifies the make, finds the trailing year-range, and pattern-
# matches the model against a make-scoped dictionary.
#
# Engine-platform titles ("fits Dodge 5.9L Cummins 1994-2002", "fits Ford
# 6.7L Powerstroke 2017+") have no vehicle model token — they fit a family of
# trucks across nameplates. We can't attribute them to a single car_generations
# row, so the hook returns None and the part stays universal. This is the
# correct behavior given the schema; engine-platform attribution would need a
# separate "engines" table that doesn't exist today.
_MISHIMOTO_FITS_RE = re.compile(r",\s*fits\s+(.+)$", re.IGNORECASE)

# Year-range shapes — accept YYYY-YYYY, YYYY-YY (two-digit tail), YYYY.5-YYYY
# (mid-MY Cummins/Duramax introductions), and YYYY+ for open-ended ranges.
_MISHIMOTO_YEAR_RANGE_RE = re.compile(
    r"\b((?:19|20)\d{2})(?:\.5)?\s*[-–—]\s*((?:19|20)?\d{2})(?:\.5)?\b"
)
_MISHIMOTO_YEAR_OPEN_RE = re.compile(r"\b((?:19|20)\d{2})\s*\+")

# Make-token aliases. "Chevy" is Chevrolet; "GM" is treated as Chevrolet for
# attribution because seed lacks a separate GM row and shared C/K/Duramax
# fitments overlap Chevy + GMC at the platform level. The hook only fires when
# a model token resolves anyway, so this fallback can't over-attribute.
_MISHIMOTO_MAKE_ALIASES: dict[str, str] = {
    "chevrolet": "Chevrolet",
    "chevy": "Chevrolet",
    "gm": "Chevrolet",
    "gmc": "GMC",
    "dodge": "Dodge",
    "ford": "Ford",
    "jeep": "Jeep",
    "mazda": "Mazda",
    "nissan": "Nissan",
    "subaru": "Subaru",
    "toyota": "Toyota",
    "honda": "Honda",
    "acura": "Acura",
    "hyundai": "Hyundai",
    "scion": "Scion",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "bmw": "BMW",
    "mini": "Mini",
}

# Model-token patterns scoped per canonical make. Each pattern resolves to a
# (model_name) string that exists in CAR_GENERATIONS — year-narrow then drops
# off-window gens. Sub-trims map to their parent model so a single regex covers
# "Mustang", "Mustang EcoBoost", and "Mustang 5.0L".
_MISHIMOTO_MODEL_PATTERNS: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    "Ford": (
        (re.compile(r"\bF-?150\s*Raptor\b", re.IGNORECASE), "F-150 Raptor"),
        (re.compile(r"\bRaptor\b", re.IGNORECASE), "F-150 Raptor"),
        (re.compile(r"\bF-?150\b", re.IGNORECASE), "F-150"),
        (re.compile(r"\b(F-?2[05]0|F-?3[05]0|F-?4[05]0|Super\s*Duty)\b", re.IGNORECASE), "F-Series Super Duty"),
        (re.compile(r"\bMustang\b", re.IGNORECASE), "Mustang"),
        (re.compile(r"\bFiesta\s*ST\b", re.IGNORECASE), "Fiesta ST"),
        (re.compile(r"\bFiesta\b", re.IGNORECASE), "Fiesta"),
        (re.compile(r"\bFocus\s*RS\b", re.IGNORECASE), "Focus RS"),
        (re.compile(r"\bFocus\s*ST\b", re.IGNORECASE), "Focus ST"),
        (re.compile(r"\bFocus\b", re.IGNORECASE), "Focus"),
        (re.compile(r"\bBronco\s*Sport\b", re.IGNORECASE), "Bronco Sport"),
        (re.compile(r"\bBronco\b", re.IGNORECASE), "Bronco"),
        (re.compile(r"\bRanger\b", re.IGNORECASE), "Ranger"),
        (re.compile(r"\bMaverick\b", re.IGNORECASE), "Maverick"),
        (re.compile(r"\bThunderbird\b", re.IGNORECASE), "Thunderbird"),
    ),
    "Chevrolet": (
        (re.compile(r"\bCamaro\b", re.IGNORECASE), "Camaro"),
        (re.compile(r"\bCorvette\b", re.IGNORECASE), "Corvette"),
        (re.compile(r"\bSilverado\b", re.IGNORECASE), "Silverado"),
        (re.compile(r"\bSuburban\b", re.IGNORECASE), "Suburban"),
        (re.compile(r"\bTahoe\b", re.IGNORECASE), "Tahoe"),
    ),
    "GMC": (
        (re.compile(r"\bSierra\b", re.IGNORECASE), "Sierra"),
        (re.compile(r"\bYukon\b", re.IGNORECASE), "Yukon"),
    ),
    "Dodge": (
        (re.compile(r"\bChallenger\b", re.IGNORECASE), "Challenger"),
        (re.compile(r"\bCharger\b", re.IGNORECASE), "Charger"),
        (re.compile(r"\bDurango\b", re.IGNORECASE), "Durango"),
        (re.compile(r"\bMagnum\b", re.IGNORECASE), "Magnum"),
        (re.compile(r"\bViper\b", re.IGNORECASE), "Viper"),
    ),
    "Jeep": (
        # Wrangler sub-platforms (JL/JK/TJ/YJ) appear in titles — match on
        # "Wrangler" plus optional platform code; year-narrow picks the gen.
        (re.compile(r"\bWrangler\b", re.IGNORECASE), "Wrangler"),
        (re.compile(r"\bGrand\s+Cherokee\b", re.IGNORECASE), "Grand Cherokee"),
        (re.compile(r"\bCherokee\b", re.IGNORECASE), "Cherokee"),
    ),
    "Mazda": (
        (re.compile(r"\bMiata\b", re.IGNORECASE), "Miata"),
        (re.compile(r"\bRX-?7\b", re.IGNORECASE), "RX-7"),
        (re.compile(r"\bRX-?8\b", re.IGNORECASE), "RX-8"),
        (re.compile(r"\bMazda\s*3\b", re.IGNORECASE), "Mazda3"),
        (re.compile(r"\bMazda\s*6\b", re.IGNORECASE), "Mazda6"),
    ),
    "Nissan": (
        (re.compile(r"\b240SX\b", re.IGNORECASE), "240SX"),
        (re.compile(r"\b300ZX\b", re.IGNORECASE), "300ZX"),
        (re.compile(r"\b350Z\b", re.IGNORECASE), "350Z"),
        (re.compile(r"\b370Z\b", re.IGNORECASE), "370Z"),
        (re.compile(r"\bGT-?R\b", re.IGNORECASE), "GT-R"),
    ),
    "Subaru": (
        (re.compile(r"\bWRX\b", re.IGNORECASE), "WRX"),
        (re.compile(r"\bSTI\b", re.IGNORECASE), "WRX"),
        (re.compile(r"\bImpreza\b", re.IGNORECASE), "Impreza"),
        (re.compile(r"\bForester\s*XT\b", re.IGNORECASE), "Forester XT"),
        (re.compile(r"\bForester\b", re.IGNORECASE), "Forester"),
        (re.compile(r"\bOutback\s*XT\b", re.IGNORECASE), "Outback XT"),
        (re.compile(r"\bOutback\b", re.IGNORECASE), "Outback"),
        (re.compile(r"\bCrosstrek\b", re.IGNORECASE), "Crosstrek"),
        (re.compile(r"\bBRZ\b", re.IGNORECASE), "BRZ"),
    ),
    "Toyota": (
        (re.compile(r"\bSupra\b", re.IGNORECASE), "Supra"),
        (re.compile(r"\bMR2\b", re.IGNORECASE), "MR2"),
        (re.compile(r"\bGR\s*Corolla\b", re.IGNORECASE), "GR Corolla"),
        (re.compile(r"\bGR\s*Yaris\b", re.IGNORECASE), "GR Yaris"),
        (re.compile(r"\bGR\s*86\b", re.IGNORECASE), "GR86"),
        (re.compile(r"\bTacoma\b", re.IGNORECASE), "Tacoma"),
        (re.compile(r"\bTundra\b", re.IGNORECASE), "Tundra"),
        (re.compile(r"\b4Runner\b", re.IGNORECASE), "4Runner"),
        (re.compile(r"(?<![\d-])\b86\b(?![\d-])", re.IGNORECASE), "86"),
        (re.compile(r"\bCelica\b", re.IGNORECASE), "Celica"),
        (re.compile(r"\bCorolla\b", re.IGNORECASE), "Corolla"),
        (re.compile(r"\bCamry\b", re.IGNORECASE), "Camry"),
    ),
    "Honda": (
        (re.compile(r"\bCivic\s*Type\s*R\b", re.IGNORECASE), "Civic Type R"),
        (re.compile(r"\bCivic\b", re.IGNORECASE), "Civic"),
        (re.compile(r"\bAccord\b", re.IGNORECASE), "Accord"),
        (re.compile(r"\bS2000\b", re.IGNORECASE), "S2000"),
        (re.compile(r"\bNSX\b", re.IGNORECASE), "NSX"),
    ),
    "Acura": (
        (re.compile(r"\bIntegra\b", re.IGNORECASE), "Integra"),
        (re.compile(r"\bRSX\b", re.IGNORECASE), "RSX"),
        (re.compile(r"\bTL\b", re.IGNORECASE), "TL"),
        (re.compile(r"\bTSX\b", re.IGNORECASE), "TSX"),
        (re.compile(r"\bMDX\b", re.IGNORECASE), "MDX"),
    ),
    "Hyundai": (
        (re.compile(r"\bGenesis\s*Coupe\b", re.IGNORECASE), "Genesis Coupe"),
        (re.compile(r"\bElantra\s*N\b", re.IGNORECASE), "Elantra N"),
        (re.compile(r"\bElantra\b", re.IGNORECASE), "Elantra"),
        (re.compile(r"\bVeloster\b", re.IGNORECASE), "Veloster"),
        (re.compile(r"\bKona\s*N\b", re.IGNORECASE), "Kona N"),
        (re.compile(r"\bTiburon\b", re.IGNORECASE), "Tiburon"),
    ),
    "Scion": (
        (re.compile(r"\bFR-?S\b", re.IGNORECASE), "FR-S"),
        (re.compile(r"\btC\b", re.IGNORECASE), "tC"),
    ),
    "BMW": (
        (re.compile(r"\bM3\b", re.IGNORECASE), "M3"),
        (re.compile(r"\bM4\b", re.IGNORECASE), "M4"),
    ),
}


def _extract_mishimoto_year_range(text: str) -> Optional[tuple[int, int]]:
    """
    Pull a (start_year, end_year) from a Mishimoto fits-suffix. Supports
    canonical YYYY-YYYY, YYYY-YY two-digit tails (carry the century), the
    YYYY.5 mid-MY notation Mishimoto uses for Cummins/Duramax introductions
    (we coerce to the integer year), and open-ended YYYY+. Returns ``None``
    when no shape matches.
    """
    m = _MISHIMOTO_YEAR_RANGE_RE.search(text)
    if m:
        try:
            y1 = int(m.group(1))
            tail = m.group(2)
            y2 = int(tail) if len(tail) == 4 else (y1 // 100) * 100 + int(tail)
            if y2 < y1:
                y2 += 100
        except ValueError:
            return None
        if y1 < 1960 or y1 > 2030 or y2 < y1 or y2 > 2035:
            return None
        return (y1, y2)
    m = _MISHIMOTO_YEAR_OPEN_RE.search(text)
    if m:
        try:
            y1 = int(m.group(1))
        except ValueError:
            return None
        if y1 < 1960 or y1 > 2030:
            return None
        return (y1, 9999)
    return None


def _extract_mishimoto_make(fits_tail: str) -> Optional[str]:
    """
    Read the first non-empty token of the fits suffix and resolve it through
    the make-alias dictionary. Mishimoto sometimes writes ``"Chevrolet/GMC"``
    or ``"Chevy"`` so we split on common separators and try each alias before
    giving up.
    """
    # Take the leading token(s) up to the next separator. "Chevrolet/GMC" must
    # split into ["Chevrolet", "GMC"] so either resolves; "Chevy Monte Carlo"
    # must split into ["Chevy", "Monte", ...] so the first token resolves.
    leading = fits_tail.strip().split()
    if not leading:
        return None
    first = leading[0]
    for token in re.split(r"[/&,]", first):
        token = token.strip().lower()
        if token in _MISHIMOTO_MAKE_ALIASES:
            return _MISHIMOTO_MAKE_ALIASES[token]
    return None


def _extract_mishimoto_model(fits_tail: str, make: str) -> Optional[str]:
    """
    Walk the make-scoped pattern dictionary and return the canonical model
    name for the first match, or None if no pattern fires. Pattern order is
    significant: sub-trims (Civic Type R, Focus RS, F-150 Raptor) come before
    their parent model so they win when both tokens are present.
    """
    patterns = _MISHIMOTO_MODEL_PATTERNS.get(make)
    if not patterns:
        return None
    for pattern, model_name in patterns:
        if pattern.search(fits_tail):
            return model_name
    return None


class MishimotoAdapter(RetailerCrawlerAdapter):
    """
    Mishimoto adapter. Magento 2 + Hyva storefront, plain HTTP suffices.
    Discovery: sitemap index at ``/sitemap.xml`` → two
    ``/media/sitemap/sitemap_full_us-1-N.xml`` children (flat urlsets).
    Parsing: JSON-LD ``Product`` first (clean sku/name/description/offer),
    then DOM/og fallback. Brand is always coerced to ``"Mishimoto"`` — the
    entire catalog is house brand, and JSON-LD omits the ``brand`` field
    (it only carries ``offers[0].seller.name``), so without this the title
    heuristic would pick up ``Honda``/``Ford``/``Subaru`` etc. as the
    "brand" on titles like *"Mishimoto Honda Civic Si Radiator"*.
    Gallery: ``window.productMediaMeta.images`` regex → full-resolution URL
    per photo, size-deduped, capped at 12. Falls back to og:image + DOM
    when the meta blob is missing.
    """

    ADAPTER_NAME: ClassVar[str] = "mishimoto"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from ``/sitemap.xml`` (sitemap index → child urlsets).
        Set ``CRAWLER_MISHIMOTO_START_URLS`` (comma-separated) to override
        with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Mishimoto product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL looks like a category/CMS page, when no
        JSON-LD (or DOM fallback) yields a name, or when the JSON-LD
        ``url`` doesn't match the fetched URL (category-page pretender).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images_fallback = _extract_gallery_images_from_meta(html) or _extract_dom_images_fallback(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (every real product page emits a clean block).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            # Category-page pretender check: JSON-LD url must match fetched url.
            if not _json_ld_url_matches(item, url):
                return None

            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                # Tighten: if the SKU doesn't look like a Mishimoto house-brand
                # SKU (``MM...-...`` pattern), drop it rather than store noise.
                if part_number and not _looks_like_mishimoto_sku(part_number):
                    part_number = None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = (
                    dom_images_fallback[:_MAX_GALLERY_IMAGES]
                    if dom_images_fallback
                    else (payload.image_urls[:_MAX_GALLERY_IMAGES] if payload.image_urls else None)
                )
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    # House brand always; see module docstring for rationale.
                    part_manufacturer=BRAND_CANONICAL,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=None,  # not emitted by Mishimoto
                )

        # 2. DOM / og fallback — used only when JSON-LD is absent (rare).
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

        price_cents = dom_price
        if price_cents is None:
            og_amount = soup.find("meta", property="product:price:amount")
            if isinstance(og_amount, Tag):
                amt = meta_content(og_amount)
                if amt and amt.strip():
                    try:
                        price_cents = int(round(float(amt.strip()) * 100))
                    except ValueError:
                        price_cents = None

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))
        if part_number and not _looks_like_mishimoto_sku(part_number):
            part_number = None

        image_urls = dom_images_fallback[:_MAX_GALLERY_IMAGES] if dom_images_fallback else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=BRAND_CANONICAL,
            part_number=part_number,
            image_urls=image_urls,
            gtin=None,
        )

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[List[tuple[str, str, str]]]:
        """
        Extract make/model/generation triples from the ", fits <Make>
        <Model> ... <year-range>" suffix on Mishimoto product titles.

        Returns ``None`` (NOT empty list) when:
          * the title has no fits suffix
          * the make token doesn't resolve to a known nameplate
          * no model pattern fires for the resolved make
          * no year-range token is extractable

        ``None`` causes the ingest layer to fall through to the universal
        keyword pipeline; an empty list would short-circuit ingest to
        ``is_universal=True``, which is wrong for these inputs because the
        universal pipeline can still rescue some titles.

        Engine-platform titles (``"fits Dodge 5.9L Cummins 1994-2002"``,
        ``"fits Ford 6.7L Powerstroke 2017+"``) deliberately don't resolve:
        no model token fires for the make, so the hook punts. There's no
        car_generations row representing "any truck with a 5.9L Cummins".
        """
        name = parsed.name or ""
        if not name:
            return None
        m = _MISHIMOTO_FITS_RE.search(name)
        if not m:
            return None
        fits_tail = m.group(1)
        make = _extract_mishimoto_make(fits_tail)
        if make is None:
            return None
        model = _extract_mishimoto_model(fits_tail, make)
        if model is None:
            return None
        year_range = _extract_mishimoto_year_range(fits_tail)
        if year_range is None:
            return None
        triples = generations_for_make_model_year_range(make, model, year_range)
        return triples or None
