"""
Unplugged Performance (unpluggedperformance.com) crawler adapter.

Platform: **WordPress + WooCommerce** with the **Rank Math SEO Pro** plugin
emitting structured data. ``<meta name="generator" content="WordPress 6.9.4">``
on every page; product URLs live at ``/product/<slug>/`` (the classic
WooCommerce permalink shape, not Shopify's ``/products/``). Cloudflare fronts
the origin but only on caching duty — no JS challenge or TLS fingerprinting
block for the default crawler UA on product pages, ``/robots.txt``, or the
sitemap index. Plain ``requests`` returns a fully rendered ~500 KB HTML page
with complete JSON-LD on first try, so ``FETCHER_TIER`` stays at the default
``"http"`` (Tier 0).

Host: ``unpluggedperformance.com`` (apex only — ``www.unpluggedperformance.com``
301s back to the apex, confirmed 2026-04-21; the sitemap advertises the apex).

Discovery: ``/sitemap.xml`` 301-redirects to ``/sitemap_index.xml`` — a Rank
Math sitemap index with eight children
(``post-sitemap.xml``, ``page-sitemap.xml``, ``featured-vehicles-sitemap.xml``,
**``product-sitemap.xml``**, ``faq-sitemap.xml``,
``featured-category-sitemap.xml``, ``product_cat-sitemap.xml``,
``local-sitemap.xml``). Only ``product-sitemap.xml`` hosts real
``/product/<slug>/`` URLs (~390 products as of 2026-04-21); the rest are
skipped. We follow the apex redirect to the index once and then only fetch
the products child. Override with ``CRAWLER_UNPLUGGEDPERFORMANCE_START_URLS``
(comma-separated) for a fixed list.

JSON-LD shape: **two ld+json blocks per product page.**

- **Block 0** — a Rank Math Pro ``@graph`` carrying ``Place`` / ``Organization``
  / ``WebSite`` / ``ImageObject`` / ``WebPage`` / **``ProductGroup``** (or just
  ``Product`` for a non-variable single-SKU product). The ``ProductGroup`` is
  the parent: ``name`` / ``brand.name`` / ``description`` / ``category`` /
  ``url`` / ``productGroupID`` / ``hasVariant: [Product, ...]``. Brand is
  always ``{"@type":"Brand","name":"Unplugged Performance"}``.
- **Block 1** — a bare ``@graph`` of the individual variant ``Product`` blocks
  (one per variant, each with its own ``sku`` / per-variant ``offers.price`` /
  ``offers.url=?attribute_pa_...``). For a ~16-variant spring set we see 16
  ``Product`` entries (sometimes with duplicates).

Variant strategy: **parent-ProductGroup-first, ``hasVariant[0]`` for sku /
price / image** — the same rule ``maperformance`` / ``ets`` /
``burgermotorsports`` use for their Shopify ``ProductGroup`` pages (see
``adapters/VARIANTS.md`` §3). The parent row carries the clean name
(``"Tesla Model 3 - Dual Rate Linear Lowering Springs Set"``) and full
description; the first variant carries the authoritative SKU (``UP-M3-310-...``)
and a real price. Other variants are silently lost under the one-Part-per-URL
contract — acceptable here since Unplugged Performance's UI picker is
non-addressable without the variant query string anyway, and their SKU prefix
follows the parent family (``UP-M3-310-<N>.<rev>``) so the first SKU stands
in for the family. When a page ships only a ``Product`` block (no
``ProductGroup`` — single-SKU items), we fall through to the shared
``extract_json_ld_product`` → the first ``Product`` whose canonical URL
matches. Because Rank Math declares every variant's top-level ``url`` with
the ``?attribute_...`` query appended, the shared extractor's URL-match
canonicalization (query-stripped) picks the first variant — effectively the
same as ``hasVariant[0]``.

Brand rule: **coerce to "Unplugged Performance" whenever a car make appears.**
Their catalog titles lead with either ``Model 3 …`` / ``Model Y …`` /
``Cybertruck …`` or the full ``Tesla Model 3 …`` / ``Tesla Model Y …`` — so
the shared ``part_manufacturer_from_title`` heuristic, on pages where the
JSON-LD brand goes missing, would cheerfully pick "Tesla", "Model", or one of
the Tesla model names as the part manufacturer. We block:

1. JSON-LD brand missing/empty → ``"Unplugged Performance"``.
2. JSON-LD / title-heuristic brand equal to a car make
   (``"tesla"``, ``"model s"``, ``"model 3"``, ``"model x"``, ``"model y"``,
   ``"cybertruck"``, ``"roadster"``) → ``"Unplugged Performance"``.
3. ``"Unplugged Performance Inc"`` / ``"Unplugged Performance INC"`` /
   ``"Unplugged"`` variants → canonical ``"Unplugged Performance"``.
4. Generic reject tokens (``"the"``, ``"new"``) → ``"Unplugged Performance"``.

Everything else passes through. Unplugged Performance sells a small number of
OEM-replacement or partner items (rarely) — if the brand ever comes back as a
real third-party (e.g. BBS wheels with BBS branding), we keep that value.

SKU format: house SKUs are ``UP-<MODEL>-<FAMILY>-<VARIANT>.<REV>``
(``UP-MU-001-2.1``, ``UP-M3-310-16.1``, ``UP-PLAID-FXXX``). The trailing
``-<variant>.<rev>`` suffix is real catalog data and part of how Unplugged
identifies the SKU in-house, so we preserve it unchanged through
``normalize_part_number`` (no extra stripping).

Images: Under ``/wp-content/uploads/`` (the standard WordPress upload path).
ProductGroup's ``image`` field is sometimes a single string, sometimes a
``{"@id":"..."}`` reference, sometimes absent. Variants carry one
``image`` string each. We merge JSON-LD image(s) + every
``<img src="…/wp-content/uploads/…">`` found in the DOM, dedupe by canonical
URL (stripping WooCommerce's ``-300x300`` / ``-600x600`` size suffixes so the
full-res and thumbnail copies of the same asset collapse), drop site chrome
(logos, banners, email-protect icons), and cap at 12.

Price: first variant's ``offers.price`` on ``ProductGroup`` pages; JSON-LD
``offers.price`` on plain ``Product`` pages; ``extract_dom_price`` fallback.
Some products (custom/quote items like the Ascension front fascia) emit
``price=0`` — those are stripped so we store ``price_cents=None`` rather than
a misleading zero.

Tier rationale: Plain Cloudflare caching in front of WordPress — full HTML
returned with default headers. No TLS fingerprinting, no managed JS challenge.
If Cloudflare ever escalates, promote to Tier 1 (``"tls"`` / ``curl_cffi``)
first, then Tier 2 (``"browser"`` / FlareSolverr).

Caveats:

- **Tesla-as-brand guard.** Unplugged Performance titles bake the car make
  into the product name (``"Tesla Model Y Ascension Front Fascia…"``). The
  JSON-LD brand is always correct (``"Unplugged Performance"``), but the
  title-heuristic fallback would otherwise pick ``"Tesla"`` or a Tesla model
  name — see brand rule above.
- **Variant "winner" bias.** On variable products we emit one ``ScrapedPayload``
  carrying ``hasVariant[0]``'s SKU / price. Variants with different finishes
  / sizes / lengths collapse into the family row. Known limitation documented
  in ``VARIANTS.md``; no current plan to expand.
- **Zero-price quote items.** Rank Math emits ``"price": "0.00"`` on
  made-to-order parts that don't have a fixed price. We treat any ``price=0``
  as missing and leave ``price_cents`` unset.
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

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
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

UNPLUGGEDPERFORMANCE_BASE = "https://unpluggedperformance.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
PRODUCT_PAGE_PATH = "/product/"

# Verified live product URLs used as a fallback when sitemap discovery fails
# and no env override is provided. Both returned 200 OK with full ProductGroup
# JSON-LD on 2026-04-21; cover the two common shapes (multi-variant lug nuts
# with priced variants + multi-variant lowering springs).
DEFAULT_START_URLS = [
    "https://unpluggedperformance.com/product/superlight-titanium-lug-nuts-set-tesla/",
    "https://unpluggedperformance.com/product/tesla-model-3-lowering-springs/",
]

# Canonical house-brand name. Every Unplugged Performance page we've inspected
# emits exactly this string in JSON-LD ``brand.name``; the variants below come
# from the Rank Math Organization schema emitting the legal name.
CANONICAL_BRAND = "Unplugged Performance"

# Car-make / Tesla model-name tokens that the fallback title heuristic (or a
# missing JSON-LD brand) sometimes surfaces as "brand" but are really the
# target vehicle. Unplugged Performance is a **Tesla-only** shop, so this
# list is short and explicit — plus a few non-Tesla makes as belt-and-suspenders
# in case catalog expands.
_CAR_MAKES = frozenset(
    {
        "tesla",
        "model s",
        "model 3",
        "model x",
        "model y",
        "cybertruck",
        "roadster",
        # Cheap belt-and-suspenders for future catalog expansion.
        "bmw",
        "porsche",
        "toyota",
        "honda",
        "ford",
        "nissan",
    }
)

# Tokens that the first-token title heuristic sometimes picks but are generic.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem", "for"})

# WooCommerce thumbnail size suffixes — ``-300x300.jpg``, ``-600x600.webp``, etc.
# Matched on the full URL so we can both reject thumbnails when a full-res
# copy is available AND canonicalize (size-stripped) for dedupe.
_WOOCOMMERCE_SIZE_SUFFIX_RE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.\w{2,5}(?:$|\?))", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product media.
_IMAGE_NOISE_RE = re.compile(
    r"/logo|logo[-_]|-logo\.|placeholder|favicon|sprite|icon[-_]|"
    r"email-protect|cdn-cgi|megamenu|mega_?menu|banner_|_banner",
    re.IGNORECASE,
)

# Product image path on this WordPress install. Anything outside
# ``/wp-content/uploads/`` is dropped from the gallery.
_PRODUCT_IMAGE_PATH_PART = "/wp-content/uploads/"


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap index, then hard-coded defaults."""
    raw = os.environ.get("CRAWLER_UNPLUGGEDPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is the ``product-sitemap.xml`` child (the only one with real products)."""
    return url.endswith("/product-sitemap.xml")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap_index.xml`` (``/sitemap.xml`` 301s to it) → the
    ``product-sitemap.xml`` child urlset and collect every ``/product/<slug>/``
    URL. Skips the seven non-product siblings (post / page / featured-vehicles
    / faq / featured-category / product_cat / local). Returns a deduplicated
    list (by URL with query stripped); empty on failure.
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
            if PRODUCT_PAGE_PATH not in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        # ``/sitemap.xml`` 301s to ``/sitemap_index.xml`` on this Rank Math
        # install; fetch_page follows redirects so either path works, but we
        # ask for the index directly to avoid the extra hop.
        index_url = UNPLUGGEDPERFORMANCE_BASE + "/sitemap_index.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if not _is_products_child_sitemap(child_url):
                    continue
                if fetched > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                fetched += 1
                try:
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            # Some installs flatten the index into a single urlset; cover it.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Return the first ``ProductGroup`` JSON-LD block on the page. Unplugged
    Performance's Rank Math Pro emits ProductGroup at the page level with a
    ``hasVariant: [Product, ...]`` array; the shared
    ``extract_json_ld_product`` only matches plain ``Product`` so we look it
    up directly here. Same pattern as ``burgermotorsports`` /
    ``maperformance`` / ``ets``.
    """
    soup = BeautifulSoup(html_text, "html.parser")
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


def _first_variant(group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the first Product entry from a ProductGroup's hasVariant array."""
    variants = group.get("hasVariant")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if isinstance(v, dict):
            return v
    return None


def _offer_price_cents(item: Dict[str, Any]) -> Optional[int]:
    """
    Pull the first usable price from an ``offers`` field (list or dict). Zero
    is treated as missing — Rank Math emits ``"price": "0.00"`` on quote-only
    items (custom made-to-order bumpers, etc.) and we don't want to store a
    misleading $0 price.
    """
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else None
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = None
    if not isinstance(offer, dict):
        return None
    for key in ("price", "lowPrice"):
        raw = offer.get(key)
        if raw is None:
            continue
        try:
            num = float(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if num > 0:
            return int(round(num * 100))
    return None


def _image_urls_from_json_ld_field(img: Any) -> List[str]:
    """Flatten a JSON-LD ``image`` field (string | dict | list[str|dict]) into a list of URLs."""
    if not img:
        return []
    raw_list = [img] if not isinstance(img, list) else img
    out: List[str] = []
    for entry in raw_list:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
        elif isinstance(entry, dict):
            # ProductGroup sometimes references an ImageObject by {"@id":"..."};
            # variant ``image`` blocks use ``url`` (or the @id as URL).
            url_val = entry.get("url") or entry.get("@id")
            if isinstance(url_val, str) and url_val.strip():
                out.append(url_val.strip())
    return out


def _payload_from_product_group(group: Dict[str, Any], product_url: str) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a ProductGroup JSON-LD block. Reads name /
    brand / description from the group root and sku / price / image from the
    first variant (same strategy as ``burgermotorsports``,
    ``maperformance``, ``ets``). Brand canonicalization is deferred to the
    adapter so the raw JSON-LD value survives unchanged here — the caller
    applies ``_canonical_brand`` after merging with DOM fallbacks.
    """
    name_val = group.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None

    brand_val = group.get("brand")
    brand: Optional[str] = None
    if isinstance(brand_val, str) and brand_val.strip():
        brand = brand_val.strip()
    elif isinstance(brand_val, dict):
        bn = brand_val.get("name")
        if isinstance(bn, str) and bn.strip():
            brand = bn.strip()

    description: Optional[str] = None
    desc_val = group.get("description")
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    variant = _first_variant(group) or {}
    sku_val = variant.get("sku") or variant.get("mpn") or group.get("productGroupID")
    part_number = normalize_part_number(sku_val) if isinstance(sku_val, str) else None
    price_cents = _offer_price_cents(variant) if variant else None

    gtin_val = variant.get("gtin13") or variant.get("gtin12") or variant.get("gtin")
    gtin = gtin_val.strip() if isinstance(gtin_val, str) and gtin_val.strip() else None

    # Prefer the variant's image; fall back to the group's. ProductGroup's
    # ``image`` is often a ``{"@id": "..."}`` reference pointing at an
    # ImageObject in the same @graph — the helper below resolves it.
    images = _image_urls_from_json_ld_field(variant.get("image")) if variant else []
    if not images:
        images = _image_urls_from_json_ld_field(group.get("image"))

    return ScrapedPayload(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=price_cents,
        part_manufacturer=brand,
        part_number=part_number,
        image_urls=images[:12] if images else None,
        gtin=gtin,
    )


def _canonical_brand(brand: Optional[str]) -> str:
    """
    Return the canonical manufacturer for an Unplugged Performance product page.

    - Non-empty JSON-LD / title / description brand that is NOT a car make
      (``"tesla"``, Tesla model names), NOT a reject token, and NOT an
      ``"Unplugged Performance"`` legal variant → pass through (future-proofs
      the rare third-party resell).
    - Empty / car-make / reject-token / ``"Unplugged …"`` variant → coerce to
      canonical ``"Unplugged Performance"``.

    **Tesla-as-brand guard.** The title heuristic on pages where JSON-LD
    brand is missing would otherwise pick ``"Tesla"`` from
    ``"Tesla Model Y Ascension Front Fascia…"`` or ``"Model"`` from
    ``"Model 3 - Dual Rate Linear Lowering Springs"``. Both are blocked here.
    """
    raw = (brand or "").strip()
    if not raw:
        return CANONICAL_BRAND
    low = raw.lower()
    # Block Tesla and Tesla model names (single-token and two-token forms).
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return CANONICAL_BRAND
    # Collapse "Unplugged Performance INC", "Unplugged Performance, Inc.",
    # "Unplugged" into the canonical form regardless of case.
    if low == "unplugged" or low == "unplugged performance":
        return CANONICAL_BRAND
    if low.startswith("unplugged performance ") or low.startswith("unplugged performance,"):
        return CANONICAL_BRAND
    if low.startswith("unplugged-"):
        return CANONICAL_BRAND
    # Belt-and-suspenders: if the first token of a multi-word brand is a
    # Tesla model name, coerce. Covers ``"Model 3 Performance"`` style
    # title-heuristic leakage on pages with no JSON-LD brand.
    first_two = " ".join(low.split()[:2])
    if first_two in _CAR_MAKES:
        return CANONICAL_BRAND
    return raw


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against the apex."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return UNPLUGGEDPERFORMANCE_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only WordPress upload images on the Unplugged host; reject chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if _PRODUCT_IMAGE_PATH_PART not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """
    Drop WooCommerce size suffixes (``-300x300``, ``-600x600``, ``-scaled``)
    and cache-busting query params so the thumbnail, the full-res copy, and
    the JSON-LD-referenced version of the same asset collapse to one key.
    """
    no_size = _WOOCOMMERCE_SIZE_SUFFIX_RE.sub("", url)
    no_query = no_size.split("?", 1)[0]
    # WordPress's ``-scaled`` suffix is applied to oversized uploads; both the
    # ``-scaled`` and the bare filename refer to the same source asset.
    no_scaled = re.sub(r"-scaled(?=\.\w{2,5}$)", "", no_query, flags=re.IGNORECASE)
    return no_scaled


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs from the DOM (Unplugged uploads only),
    deduped and capped at 12. WooCommerce's default ``<div class="woocommerce-product-gallery">``
    holds the hero + thumbnails; Unplugged uses a custom theme but the assets
    still live under ``/wp-content/uploads/``, so a straight ``<img>`` sweep
    with canonical-key dedupe is the simplest correct filter.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break
    return ordered[:12]


def _merge_images(json_ld_images: Optional[List[str]], dom_images: List[str]) -> List[str]:
    """
    Merge JSON-LD images with DOM gallery images, deduped by canonical key
    (size-suffix / query-stripped) and capped at 12. JSON-LD order is
    preserved as primary; DOM entries fill remaining slots. Rank Math
    sometimes emits the hero image twice in the same ``image`` array (same
    asset, no size suffix) — the canonical-key dedupe collapses those too.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []
    for u in list(json_ld_images or []) + list(dom_images or []):
        if len(ordered) >= 12:
            break
        if not u or not u.strip():
            continue
        normalized = _normalize_image_url(u)
        if not normalized.startswith("http"):
            continue
        if not _is_valid_product_image(normalized):
            continue
        key = _canonical_image_key(normalized)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ordered.append(normalized)
    return ordered


class UnpluggedPerformanceAdapter(RetailerCrawlerAdapter):
    """
    Unplugged Performance adapter. Tier 0 (plain HTTP is sufficient).

    Discovery: Rank Math ``/sitemap_index.xml`` → ``product-sitemap.xml``
    child urlset, filtered to ``/product/<slug>/`` URLs.
    ``CRAWLER_UNPLUGGEDPERFORMANCE_START_URLS`` (comma-separated) overrides.

    Parsing: ``ProductGroup`` JSON-LD first (the schema Rank Math emits on
    variable WooCommerce products — first ``hasVariant`` carries sku / price /
    image), then plain ``Product`` JSON-LD via the shared URL-aware extractor
    (which picks the first variant because all Rank Math variant ``url``
    values share the canonical product URL once the ``?attribute_...`` query
    is stripped), then a DOM / og fallback. Brand is canonicalized to
    "Unplugged Performance" when empty, a Tesla/car-make token, or an
    "Unplugged …" legal-name alias; otherwise the JSON-LD value passes
    through unchanged.
    """

    ADAPTER_NAME: ClassVar[str] = "unpluggedperformance"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``/sitemap_index.xml`` →
        ``product-sitemap.xml``. Set
        ``CRAWLER_UNPLUGGEDPERFORMANCE_START_URLS`` (comma-separated) to
        override with a fixed list. Runner applies ``--limit`` to cap how
        many are processed.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Unplugged Performance product page.

        1. ``ProductGroup`` JSON-LD — the schema Rank Math Pro emits on every
           variable WooCommerce product. Merge DOM gallery on top of the
           variant/group JSON-LD image(s) so we keep the full carousel.
        2. Plain ``Product`` JSON-LD (via the shared URL-aware extractor) —
           catches the rare single-SKU product that skips ``ProductGroup``.
           The extractor's query-stripped URL match picks the first variant
           when Rank Math emits N variants on a single page.
        3. DOM / og fallback — h1 / og:title, meta description, DOM price,
           SKU via text scan, brand via shared title/description heuristics.

        Returns ``None`` when no usable name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. ProductGroup JSON-LD (the path that fires on most Unplugged pages).
        group = _extract_product_group_from_json_ld(html)
        if group:
            payload = _payload_from_product_group(group, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                if price_cents == 0:
                    price_cents = None

                # Merge ProductGroup / variant JSON-LD images with DOM gallery.
                # Dedupe by canonical key (Rank Math sometimes emits the hero
                # image twice in the same ``image`` array).
                image_urls = _merge_images(payload.image_urls, dom_images)
                part_manufacturer = _canonical_brand(payload.part_manufacturer)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=payload.part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. Plain Product JSON-LD (single-SKU products / older Rank Math output).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                if price_cents == 0:
                    price_cents = None
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                part_manufacturer = _canonical_brand(payload.part_manufacturer)

                image_urls = _merge_images(payload.image_urls, dom_images)

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 3. DOM / og fallback.
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
        if price_cents == 0:
            price_cents = None

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if sku_elem:
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer_raw = part_manufacturer_from_title(str(name))
        if not part_manufacturer_raw and description:
            part_manufacturer_raw = part_manufacturer_from_description(description, product_name=str(name))
        part_manufacturer = _canonical_brand(part_manufacturer_raw)

        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
        )
