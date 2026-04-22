"""
APR Performance, Inc. (aprperformance.com) crawler adapter.

**IMPORTANT — NOT the APR tuning shop.** APR Performance is a US track-aero
manufacturer (carbon fiber GT wings, splitters, diffusers, side rockers,
fender vents, mirrors, engine-bay panels). The APR tuning shop / VAG ECU
vendor on ``goapr.com`` is a different company already handled by the
``apr`` adapter — see ``app/crawlers/adapters/tier1_tls/apr.py``. Keep the
two adapters strictly separate: no host overlap, no brand collapse. The
canonical brand string here is ``"APR Performance"`` (with the trailing
word); plain ``"APR"`` belongs to goapr.com and must not be produced by
this parser.

Platform: **Shopify**. Storefront domain is ``shop.aprperformance.com``
(the apex ``aprperformance.com`` and ``www.aprperformance.com`` both 301 to
the shop subdomain via Shopify's primary-domain redirect; ``apr-performance.com``
does not resolve at all). Cloudflare fronts the origin but serves a real
HTML body on the first ``requests`` GET — no managed JS challenge, no
``curl_cffi``-worthy TLS wall. ``FETCHER_TIER`` stays at the default
``"http"``.

Discovery: ``/sitemap.xml`` is a standard Shopify **sitemap index** pointing
at ``sitemap_products_1.xml?from=…&to=…`` plus pages / collections / blogs
siblings — only the ``sitemap_products_*`` children host ``/products/<handle>``
URLs, and fetching those children requires preserving the ``?from=&to=``
query exactly as Shopify renders it (stripping it returns HTTP 400 on this
store, matching ETS's behavior). Override with
``CRAWLER_APRPERFORMANCE_START_URLS`` (comma-separated) for a fixed list.

JSON-LD shape: mixed. Single-configuration SKUs (``Ford F-150 Raptor
Fender Vents`` at ``CF-207002``) emit plain ``@type: "Product"``; multi-SKU
listings where one product page sells a matrix of configurations
(``Chevrolet Corvette C8 Engine Cover Package`` → full package / plenum
cover / appearance panels at three SKUs ``CBE-C8ENGPKG`` / ``CBE-C8ENG`` /
``CBE-C8ENGBAY``) emit ``@type: "ProductGroup"`` with ``hasVariant: [Product, …]``
carrying per-variant ``sku``/``offers[].price``/``image``. The adapter
handles both: try ``ProductGroup`` first (group-level ``name``/``brand``/
``description`` + first-variant ``sku``/``price``/``image``), then fall
through to the shared plain-``Product`` extractor. This follows the
precedent from ``ets.py``, ``burgermotorsports.py``, and ``maperformance.py``
— all Shopify stores running the same SEO app emitting ``ProductGroup``.

Variant rule (per ``VARIANTS.md`` §5 and §3): first variant wins.
ProductGroup ``hasVariant[0]`` supplies the representative SKU / price /
image; the other variants are dropped silently. This is fine for APR —
the variants within a listing are always close relatives of the same
physical part (full wing vs wing + stand-alone mounts, or CF vs dry-CF
finishes of the same wing), and they share the same brand ("APR
Performance") and visual identity. Cross-retailer dedupe works on the
first variant's MPN. If a first-class Variant model lands later
(Option D in ``VARIANTS.md``), this adapter is a good fit for migration —
MPNs differ across variants (the ``CBE-C8ENG*`` family above), prices
differ materially, and fitment does not.

Brand rule: JSON-LD ``brand.name`` is authoritative and reads
``"APR Performance"`` on every live PDP sampled. We pass that through
verbatim. **Blocklist: never coerce to plain "APR" — that's the goapr.com
tuning shop's canonical name.** If the ProductGroup / Product block
omits brand (not observed, but defensive), coerce missing values to
``"APR Performance"`` — APR Performance's catalog is first-party
(house-brand-only; no third-party resells), and every title leads with
the target vehicle make ("Chevrolet Corvette C8 …", "Ford F-150 Raptor
…", "Subaru STI …") so the shared ``part_manufacturer_from_title``
heuristic would otherwise mis-assign the car make as the manufacturer —
modeled on ``adro.py`` and ``verusengineering.py`` which force a
canonical brand for the same reason.

SKU format: APR Performance uses short alpha prefixes + numerics, e.g.
``CF-207002`` (carbon fiber parts), ``CBE-C8ENG`` (carbon body
enhancement), ``AB-830012`` (aerodynamic bodykit bits), ``AS-105908``
(aero spoilers). All shapes go through ``normalize_part_number`` unchanged.

Images: Shopify CDN product media (``/cdn/shop/products/…``,
``/cdn/shop/files/…``, and ``cdn.shopify.com`` variants). We take the
JSON-LD / variant ``image`` URL(s) first, then merge the DOM gallery
sweep on top (JSON-LD typically ships a single hero URL; the full
carousel lives in the theme's ``<media-gallery>`` / ``.product-images``
wrappers). Responsive thumbnail suffixes (``_300x300``, ``_100x100``) and
site chrome (logos, mega-menu banners) are rejected; Shopify ``?v=`` /
``?width=`` params are stripped for dedup. Capped at 12.

Tier rationale: plain Shopify + Cloudflare with no bot-management
challenge. Verified 2026-04-21 that ``curl -sI https://shop.aprperformance.com/``
returns a real 200 with real HTML body on a default UA — no ``cf-mitigated``,
no JS interstitial. No reason to pay the Tier 1 / Tier 2 cost.

Caveats:
- **Do not confuse with ``apr.py`` (goapr.com / Audi-VW tuning).** That
  adapter exists and is live. The two companies only share the first
  three letters of their names. Merging them would silently split or
  collide both catalogs under ``PartManufacturer``.
- **ProductGroup first-variant bias.** On multi-SKU pages we emit one
  ``ScrapedPayload`` per URL and pick ``hasVariant[0]``. The other SKUs
  are invisible to ingest today. See ``VARIANTS.md`` §3.
- **Host map.** The apex ``aprperformance.com`` redirects to
  ``shop.aprperformance.com``; both should route to this adapter in the
  host-to-adapter map. ``goapr.com`` must remain pointed at the ``apr``
  adapter.
"""

import json
import os
import re
import time
from typing import Any, Dict, Iterator, List, Optional, cast
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
    scraped_payload_from_json_ld,
)

# The store lives on ``shop.aprperformance.com``; ``aprperformance.com`` and
# ``www.aprperformance.com`` both 301 here via Shopify's primary-domain
# redirect. ``apr-performance.com`` (hyphen) does not resolve — not a host
# of this retailer. ``goapr.com`` belongs to the separate APR tuning shop
# (``tier1_tls/apr.py``) and must NOT appear in any host set derived from
# this module.
APRPERFORMANCE_BASE = "https://shop.aprperformance.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical form of the house brand on this site. The trailing " Performance"
# is load-bearing: plain "APR" is the goapr.com tuning shop's brand, which
# already has its own adapter. Never coerce a value down to just "APR" here.
APRPERFORMANCE_HOUSE_BRAND = "APR Performance"

# Verified 200 OK against the live site 2026-04-21. Used when the sitemap
# walk returns nothing (e.g. Shopify temporarily 5xxs the index) and no env
# override is set. Picks a single-variant Product page and a multi-variant
# ProductGroup page so a fresh crawl exercises both JSON-LD shapes.
DEFAULT_START_URLS = [
    # Single-variant Product JSON-LD
    "https://shop.aprperformance.com/products/ford-f-150-raptor-fender-vents-2017-2020",
    # Multi-variant ProductGroup JSON-LD (3 SKUs behind one URL)
    "https://shop.aprperformance.com/products/chevrolet-corvette-c8-engine-cover-package-2020-up",
]

# Tokens that the generic title heuristic or a missing JSON-LD brand could
# land on and which should be coerced to the house brand. APR Performance's
# catalog is house-brand-only, and titles lead with the target vehicle make
# ("Chevrolet Corvette C8 …", "Subaru Impreza STI …", "Ford F-150 Raptor …",
# "Acura Integra …"). Matched space-stripped and lowercased. Note: the plain
# "apr" token is intentionally absent — see the "Brand rule" in the module
# docstring.
_CAR_MAKES = frozenset(
    {
        "acura",
        "bmw",
        "chevrolet",
        "chevy",
        "chrysler",
        "dodge",
        "ford",
        "honda",
        "hyundai",
        "infiniti",
        "lexus",
        "mazda",
        "mitsubishi",
        "nissan",
        "pontiac",
        "porsche",
        "scion",
        "subaru",
        "toyota",
        "volkswagen",
        "vw",
    }
)

# First-token words that the generic heuristic sometimes picks but that are
# clearly not a manufacturer name on APR Performance titles. Kept separate
# from _CAR_MAKES so the two sets stay readable.
_BRAND_REJECT_TOKENS = frozenset(
    {
        "carbon",
        "new",
        "the",
        "oem",
    }
)

# Shopify CDN responsive-size suffix (``_300x300.jpg``, ``_1024x1024.webp``).
# Rejected so the stored gallery is full-resolution product photography
# instead of the theme's picker thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap index, then default."""
    raw = os.environ.get("CRAWLER_APRPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` child sitemap."""
    return "/sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (Shopify sitemap index) → each
    ``sitemap_products_N.xml?from=&to=`` child urlset and collect every
    ``/products/<handle>`` URL. Returns a deduplicated list keyed by the
    URL minus any trailing query (product ``<loc>`` entries don't carry
    tracking params today, but we strip defensively); empty on failure.

    Note: APR Performance's Shopify index publishes child sitemap URLs
    including a required ``?from=<id>&to=<id>`` range query. Fetching the
    child without that query returns HTTP 400 — preserve the URL verbatim.
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
        index_url = APRPERFORMANCE_BASE + "/sitemap.xml"
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
            # Flat urlset fallback (defensive; Shopify emits the index form).
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Find the first ``ProductGroup`` JSON-LD block. Shopify's SEO app emits
    ``ProductGroup`` with ``hasVariant: [Product, ...]`` on multi-SKU PDPs;
    the shared ``extract_json_ld_product`` only matches ``@type == "Product"``
    so we need our own walker. Mirrors ``ets._extract_product_group_from_json_ld``.
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
    """Return the first Product entry from a ProductGroup's ``hasVariant`` array."""
    variants = group.get("hasVariant")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if isinstance(v, dict):
            return v
    return None


def _offer_price_cents(variant: Dict[str, Any]) -> Optional[int]:
    """Pull the first usable price from a variant's ``offers`` (list or dict)."""
    offers = variant.get("offers")
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


def _images_from_variant(variant: Dict[str, Any]) -> List[str]:
    """Normalize the ``image`` field of a variant into a plain list of URLs."""
    img = variant.get("image")
    if not img:
        return []
    raw_list = [img] if isinstance(img, str) else (img if isinstance(img, list) else [])
    out: List[str] = []
    for entry in raw_list:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
        elif isinstance(entry, dict) and entry.get("url"):
            out.append(str(entry["url"]).strip())
    return out


def _brand_from_group(group: Dict[str, Any]) -> Optional[str]:
    """Extract ``brand.name`` from a ProductGroup (string or ``{name}`` dict)."""
    brand_val = group.get("brand")
    if isinstance(brand_val, str) and brand_val.strip():
        return brand_val.strip()
    if isinstance(brand_val, dict):
        bn = brand_val.get("name")
        if isinstance(bn, str) and bn.strip():
            return bn.strip()
    return None


def _payload_from_product_group(group: Dict[str, Any], product_url: str) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a ProductGroup JSON-LD block. Reads brand /
    description / name from the group root and price / sku / image from the
    first variant (per VARIANTS.md §5 — first-variant-wins on house-brand
    catalogs where variants share an identity). Returns None if the group
    has no name.
    """
    name_val = group.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None

    brand = _brand_from_group(group)

    description: Optional[str] = None
    desc_val = group.get("description")
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    variant = _first_variant(group) or {}
    sku_val = variant.get("sku") or variant.get("mpn") or group.get("productID") or group.get("productGroupID")
    part_number = normalize_part_number(sku_val) if isinstance(sku_val, str) else None
    price_cents = _offer_price_cents(variant) if variant else None

    gtin_val = variant.get("gtin") or variant.get("gtin13") or variant.get("gtin12")
    gtin = gtin_val.strip() if isinstance(gtin_val, str) and gtin_val.strip() else None

    images = _images_from_variant(variant) if variant else []
    if not images:
        group_imgs = group.get("image")
        if isinstance(group_imgs, str) and group_imgs.strip():
            images = [group_imgs.strip()]
        elif isinstance(group_imgs, list):
            images = [str(i).strip() for i in group_imgs if isinstance(i, str) and i.strip()]

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


def _normalize_part_manufacturer(raw_brand: Optional[str]) -> str:
    """
    Return the canonical manufacturer for an APR Performance product.

    - JSON-LD brand that is already ``"APR Performance"`` (or any whitespace
      / case variant) → pass through the canonical string.
    - Missing brand, car-make brand, generic-token brand → coerce to
      ``"APR Performance"``. Catalog is house-brand-only; titles lead with
      the car make so the generic title heuristic can't be trusted.
    - Legit third-party brand (never observed on this store, defensive) →
      pass through unchanged so a future resell doesn't silently merge into
      the house brand.

    **Never produces plain ``"APR"``** — that name belongs to the goapr.com
    tuning shop handled by the ``apr`` adapter.
    """
    if not raw_brand or not raw_brand.strip():
        return APRPERFORMANCE_HOUSE_BRAND

    normalized = raw_brand.strip()
    low = normalized.lower()
    stripped = re.sub(r"\s+", "", low)

    # Canonical forms and all-lowercase / space-stripped variants.
    if stripped in {"aprperformance", "aprperformanceinc", "aprperformanceinc."}:
        return APRPERFORMANCE_HOUSE_BRAND
    if "aprperformance" in stripped:
        return APRPERFORMANCE_HOUSE_BRAND

    # Bare "APR" is the goapr.com tuning shop — NOT this retailer. If it
    # somehow arrives here (extension miscapture, archive replay, etc.),
    # coerce to the full "APR Performance" form so we don't leak goapr.com's
    # brand into this catalog.
    if stripped == "apr":
        return APRPERFORMANCE_HOUSE_BRAND

    # Car-make or generic reject tokens the title heuristic could pick.
    if stripped in _CAR_MAKES or stripped in _BRAND_REJECT_TOKENS:
        return APRPERFORMANCE_HOUSE_BRAND

    return normalized


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against the shop."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return APRPERFORMANCE_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify product-CDN images; reject site chrome and thumbnail-sized variants."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    if _SHOPIFY_THUMBNAIL_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """Drop Shopify ``?v=``/``?width=``/``?height=``/``?crop=`` so responsive variants collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs from the DOM (Shopify CDN only),
    deduped and capped at 12. Used to augment the JSON-LD hero image —
    APR Performance's Shopify theme renders the full carousel under
    ``<media-gallery>`` or ``.product-images`` / ``.product-single__media``
    wrappers depending on template version.
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

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        for selector in (
            ".product__media-wrapper",
            ".product-single__media",
            ".product-images",
            ".product-gallery",
        ):
            candidate = soup.select_one(selector)
            if isinstance(candidate, Tag):
                scope = candidate
                break

    # Prefer og:image first for a consistent hero, then sweep in-scope <img>.
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    img_iter = scope.find_all("img") if scope is not None else soup.find_all("img")
    for img in img_iter:
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src", "data-original", "data-srcset"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                # data-srcset is a comma-separated list; take the first URL.
                first = val.strip().split(",")[0].strip().split(" ")[0]
                if first:
                    add(first)
                    break

    return ordered[:12]


class APRPerformanceAdapter(RetailerCrawlerAdapter):
    """
    APR Performance, Inc. adapter (aprperformance.com — US track aero,
    CF wings / splitters / fender vents / engine-bay panels).

    **Not to be confused with ``APRAdapter`` in ``tier1_tls/apr.py``** —
    that's the goapr.com VAG tuning shop, a different company.

    Tier 0 (``http``) — plain ``requests`` clears Cloudflare without
    incident; no JS challenge, no JA3 wall.

    Discovery: ``/sitemap.xml`` Shopify sitemap index →
    ``sitemap_products_1.xml?from=&to=`` children (query preserved; the
    store returns HTTP 400 without it). Env override:
    ``CRAWLER_APRPERFORMANCE_START_URLS`` (comma-separated).

    Parsing: ``ProductGroup`` JSON-LD (multi-SKU listings) or plain
    ``Product`` JSON-LD (single-SKU pages); first variant wins on
    ProductGroup per ``VARIANTS.md`` §5. Brand is normalized so missing /
    car-make / bare-"APR" values all resolve to ``"APR Performance"``;
    legitimate third-party brands (not observed, defensive) pass through
    unchanged.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an APR Performance product page.

        1. ``ProductGroup`` JSON-LD (multi-SKU pages; first variant wins).
        2. Plain ``Product`` JSON-LD (single-SKU pages — the common case
           on single-configuration items like fender vents / mirrors).
        3. DOM / og fallback — kept for archive replay / extension capture
           paths where the JSON-LD block may have been stripped.

        Returns ``None`` only when no name can be recovered. Missing brand /
        price / SKU are tolerated (brand defaults to the house brand,
        price falls back to a DOM ``$…`` scan).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. ProductGroup JSON-LD (multi-variant pages like wing / package kits).
        group = _extract_product_group_from_json_ld(html)
        if group:
            payload = _payload_from_product_group(group, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                # JSON-LD variant ``image`` is typically a single-URL string;
                # merge the DOM gallery so we keep the full carousel.
                image_urls = list(payload.image_urls or [])
                seen_keys = {_canonical_image_key(u) for u in image_urls}
                for u in dom_images:
                    key = _canonical_image_key(u)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    image_urls.append(u)
                    if len(image_urls) >= 12:
                        break
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=_normalize_part_manufacturer(payload.part_manufacturer),
                    part_number=payload.part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. Plain Product JSON-LD (single-SKU pages — ``CF-207002`` etc.).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = list(payload.image_urls or [])
                seen_keys = {_canonical_image_key(u) for u in image_urls}
                for u in dom_images:
                    key = _canonical_image_key(u)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    image_urls.append(u)
                    if len(image_urls) >= 12:
                        break
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=_normalize_part_manufacturer(payload.part_manufacturer),
                    part_number=normalize_part_number(payload.part_number) if payload.part_number else None,
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
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # Title heuristic is untrustworthy here (titles lead with the car
        # make), so skip it and force the house brand — the catalog is
        # first-party.
        part_manufacturer = _normalize_part_manufacturer(None)

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
