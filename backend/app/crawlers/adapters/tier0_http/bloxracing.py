"""
BLOX Racing (bloxracing.com) crawler adapter — Tier 0 (plain HTTP).

Honda / JDM house brand — camshafts, fuel (rails, regulators, injector
resistors), valvetrain hardware, intake manifolds, throttle bodies, clutch
masters, coilovers, wheels, Tuner-Series brake kits, and the usual catch-all
of shift knobs / bushings / dress-up bits. The entire catalogue is
first-party (no third-party reselling observed in 2026-04-21 recon), which
shapes the brand-normalisation rule below.

Platform: **Shopify**. Evidence — ``powered-by: Shopify`` response header,
``_shopify_y`` / ``_shopify_s`` cookies, ``shopify-complexity-score`` header,
``Link: <https://cdn.shopify.com>; rel="preconnect"``, ``cdn/shop/products``
image paths, and the standard Shopify sitemap index shape
(``sitemap_products_N.xml?from=…&to=…`` children under
``https://bloxracing.com/sitemap.xml``). Cloudflare is in front of the origin
but does **not** challenge plain ``requests`` with a normal browser UA —
``cf-cache-status: DYNAMIC`` passes the HTML straight through. Default
``FETCHER_TIER = "http"`` is sufficient; no TLS impersonation or FlareSolverr
needed.

Product URLs: ``https://bloxracing.com/products/<handle>``. Apex serves
directly (no ``www`` redirect). Only `bloxracing.com` is canonical; there is
no secondary marketing domain to alias.

Discovery: ``/sitemap.xml`` is a Shopify sitemap **index** pointing at six
``sitemap_products_N.xml?from=…&to=…`` children alongside the usual
``sitemap_pages_*`` / ``sitemap_collections_*`` / ``sitemap_blogs_*``
siblings. Only the ``sitemap_products_*`` children host real product URLs,
the rest are skipped. Between sitemap-child fetches we apply the shared
polite-crawler jittered delay. Override with
``CRAWLER_BLOXRACING_START_URLS`` (comma-separated) for ad-hoc runs.

JSON-LD shape: every product page emits three JSON-LD blocks —
``BreadcrumbList``, a clean ``@type: "Product"``, and a ``WebSite`` block.
The Product carries ``name``, ``description`` (HTML, stripped by the shared
normaliser), ``image`` (single-element array holding the storefront-proxy
cover URL), ``brand: {"@type": "Brand", "name": "BLOX Racing"}``, the real
retailer SKU in ``sku`` (``"BXBS-10501"``, ``"BXEX-51001"`` — prefix ``BX``
+ family code + running number), and ``mpn`` **holding the Shopify variant
ID (e.g. ``"10799793732881"``)**. That numeric ``mpn`` is platform noise, not
a manufacturer part number — we explicitly discard it so `part_number` ends
up as the real SKU from ``sku``. ``offers`` is a plain ``Offer`` with
``price`` / ``priceCurrency`` / ``availability``; the shared
``scraped_payload_from_json_ld`` handles it.

Variant rule (per ``adapters/VARIANTS.md`` §3, "Most Shopify adapters"):
nearly every BLOX product page recon'd is a single-variant Shopify product
with ``title: "Default Title"`` — the JSON-LD's top-level ``sku`` / ``price``
/ ``image`` already reflects the one and only variant, so taking those
top-level fields is lossless. The handful of multi-variant pages (select
exhaust / brake kits for different chassis) fall back to the "first variant
wins" behaviour documented in VARIANTS.md §3 for plain-theme Shopify — the
same loss pattern as ``ie`` / ``corksport`` / ``grimmspeed``. No
``hasVariant`` / ``ProductGroup`` descent is required; the ``extract_json_ld_product``
helper plus ``scraped_payload_from_json_ld`` cover it end-to-end.

Brand rule: BLOX Racing is a **100% house-brand catalogue**. JSON-LD
consistently emits ``brand.name = "BLOX Racing"``, which is exactly the
canonical form we want to store, so the happy path is a pass-through. The
defensive normaliser below only fires when:

1. JSON-LD ``brand`` is missing or empty;
2. The title-heuristic fallback lands on a car make (titles regularly lead
   with the target vehicle — ``"BLOX Racing T304 Exhaust System - 2015+
   Subaru WRX / STi"`` — so ``Honda`` / ``Acura`` / ``Civic`` / ``Integra``
   / ``RSX`` / ``Subaru`` / ``Mitsubishi`` / ``Nissan`` / ``Toyota`` can
   easily slip through the generic first-token scan); or
3. The value is a BLOX spelling variant (``"Blox"`` / ``"Blox Racing"`` /
   ``"BLOX"``) that should collapse into the canonical ``"BLOX Racing"`` so
   the global ``PartManufacturer`` row stays unified.

No third-party brands need to survive this coercion on BLOX's own domain —
the entire on-site catalogue is manufactured by BLOX.

Part-number rule: prefer the JSON-LD ``sku`` (``"BXBS-10501"`` shape — real
catalogue code used in print and packaging). The ``mpn`` field holds the
Shopify variant ID (13-digit numeric) on this storefront; that is platform
bookkeeping, not a manufacturer part number, and storing it would create
useless noise and bad cross-retailer dedupe keys, so we discard it
explicitly rather than relying on ``sku`` winning the default fallback.

Image gallery: JSON-LD ships a single-element array with the storefront
cover image (``https://bloxracing.com/cdn/shop/products/<slug>_1024x1024.jpg``).
The full gallery lives in a standard Shopify theme wrapper — we do the same
DOM sweep as ``grimmspeed`` (``<media-gallery>`` → ``.product__media-wrapper``
→ ``.product-single__media`` → ``.product-images`` → ``.product-gallery``),
dedupe on a cache-key that drops ``?v=``/``width=``/``height=``/``crop=``
query params and Shopify size suffixes (``_300x300.jpg``), and cap at 12
images. Site-chrome patterns (``logo``, ``banner``, ``favicon``, ``sprite``,
``icon-``, ``mega_menu``) are rejected.

Tier rationale: Plain Shopify behind Cloudflare with **no JS challenge** —
``curl`` with a normal browser UA returns fully rendered HTML plus JSON-LD
on the first try. Tier 0 (``"http"``) is the obvious choice; Tier 1 TLS
impersonation and Tier 2 FlareSolverr would be pure cost with no benefit.

Caveats:

- Robots.txt is standard Shopify boilerplate (no ``Disallow: /``) — a full
  crawl is allowed. Unlike Skunk2, there is no blanket disallow to work
  around, so this adapter operates normally in discovery mode.
- Multi-variant product pages (exhaust kits covering multiple chassis, brake
  kits covering 4-stud vs 5-stud) silently collapse to the first variant's
  SKU/price/image per the Shopify plain-theme rule in VARIANTS.md §3. Most
  of the catalogue is genuine Default-Title single-variant so the real-world
  impact is narrow.
- SKU prefix ``BX`` is stable across the catalogue (``BXBS-``, ``BXEX-``,
  ``BXFU-``, ``BXCM-``, …); nothing for the adapter to strip or normalise
  beyond ``normalize_part_number``.
"""

import os
import re
import time
from typing import Iterator, List, Optional
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
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

BLOXRACING_BASE = "https://bloxracing.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
BRAND_CANONICAL = "BLOX Racing"

# Verified live product URLs used as a fallback when sitemap discovery fails
# and no env override is provided. Picked across the catalogue so the first
# crawl exercises the JSON-LD path end to end.
DEFAULT_START_URLS = [
    "https://bloxracing.com/products/tuner-series-brake-kit",
    "https://bloxracing.com/products/t304-exhaust-system-2015-subaru-wrx-sti",
    "https://bloxracing.com/products/4-piston-calipers",
]

# Car makes / chassis / model families that the generic title-first-word
# heuristic regularly promotes to "brand" on BLOX product titles. All of
# them are the target vehicle rather than a manufacturer, so we coerce the
# answer to the house brand. BLOX's Honda/JDM core is listed explicitly in
# the instructions; the Subaru / Mitsubishi / Nissan / Toyota / Mazda entries
# cover the handful of cross-platform exhaust / fuel / clutch SKUs (e.g. the
# Subaru WRX/STi T304 exhaust surfaced during recon).
_CAR_MAKE_BRANDS = frozenset(
    {
        "honda",
        "acura",
        "civic",
        "integra",
        "rsx",
        "crx",
        "prelude",
        "s2000",
        "subaru",
        "mitsubishi",
        "evo",
        "evolution",
        "nissan",
        "toyota",
        "mazda",
        "scion",
    }
)

# Generic words that sometimes win the first-token title heuristic on
# descriptive / cross-platform product names.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem", "universal", "tuner"})

# Every plausible spelling of the house brand collapses to the canonical
# ``"BLOX Racing"``. Keeps the global PartManufacturer row unified regardless
# of what an upstream heuristic returned.
_BLOX_BRAND_VARIANTS = frozenset(
    {
        "blox",
        "blox racing",
        "bloxracing",
        "blox-racing",
        "blox performance",
    }
)

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg, file_100x100.webp).
# Rejected so we keep full-resolution gallery media over theme thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)

# Shopify variant IDs are pure 10+ digit numerics; JSON-LD on this store
# stuffs them into the ``mpn`` field. We reject those so they never land in
# `part_number`.
_SHOPIFY_VARIANT_ID_RE = re.compile(r"^\d{10,}$")


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap.xml, then hard-coded default."""
    raw = os.environ.get("CRAWLER_BLOXRACING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` child sitemap."""
    return "/sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → each ``sitemap_products_N.xml``
    child urlset and collect every ``/products/<handle>`` URL. Skips
    ``sitemap_pages_*`` / ``sitemap_collections_*`` / ``sitemap_blogs_*``
    siblings — none host product pages. Returns a deduplicated list
    (by URL with query stripped); empty on failure.
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
        index_url = BLOXRACING_BASE + "/sitemap.xml"
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
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _is_blox_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of BLOX's own brand-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _BLOX_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> str:
    """
    Return the canonical manufacturer for a BLOX Racing product page.

    BLOX is a 100% first-party catalogue; we only need to (a) collapse
    spelling variants to the canonical ``"BLOX Racing"`` and (b) rescue
    car-make / reject-token false positives the generic title heuristic
    produces on titles that lead with the target vehicle. We never want a
    pass-through here — anything unrecognised on bloxracing.com is still a
    BLOX part, not a real third-party brand.

    product_name is kept in the signature for symmetry with sibling
    adapters and for potential title-level overrides later.
    """
    _ = product_name
    brand = (part_manufacturer or "").strip()
    if not brand:
        return BRAND_CANONICAL
    if _is_blox_brand_variant(brand):
        return BRAND_CANONICAL
    low = brand.lower()
    if low in _CAR_MAKE_BRANDS or low in _BRAND_REJECT_TOKENS:
        return BRAND_CANONICAL
    # Anything starting with "BLOX " / "Blox-" / etc. also collapses.
    if low == "blox" or low.startswith("blox ") or low.startswith("blox-"):
        return BRAND_CANONICAL
    return brand


def _select_part_number(sku: Optional[str], mpn: Optional[str]) -> Optional[str]:
    """
    Pick the real retailer SKU, discarding Shopify variant IDs.

    This storefront writes the Shopify variant ID (``10799793732881``, pure
    numeric, 10+ digits) into JSON-LD ``mpn``. Treat that as noise. Prefer
    the real ``sku`` (``"BXBS-10501"``-shape) and explicitly reject a
    numeric-only ``mpn`` fallback.
    """
    if sku and sku.strip():
        normalized = normalize_part_number(sku)
        if normalized:
            return normalized
    if mpn and mpn.strip():
        candidate = mpn.strip()
        if _SHOPIFY_VARIANT_ID_RE.match(candidate):
            return None
        return normalize_part_number(candidate)
    return None


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against bloxracing.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return BLOXRACING_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify CDN product media (storefront proxy or bare cdn.shopify.com); reject chrome and thumbnails."""
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
    """Drop Shopify v/width/height/crop params so width variants of the same asset collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs from the DOM (Shopify CDN only),
    deduped and capped at 12.

    BLOX runs a fairly vanilla Shopify theme; gallery media is usually under
    ``.product__media-wrapper`` / ``.product-single__media`` depending on
    template version. We try the modern ``<media-gallery>`` custom element
    first (future-proof) and fall back through the legacy selectors.
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

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            for attr in ("src", "data-src", "data-original", "data-srcset"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    # data-srcset is a comma-separated list; take the first URL.
                    first = val.strip().split(",")[0].strip().split(" ")[0]
                    if first:
                        add(first)
                        break

    return ordered[:12]


class BloxRacingAdapter(RetailerCrawlerAdapter):
    """
    BLOX Racing adapter. Discovery: Shopify sitemap index →
    ``sitemap_products_N.xml`` children. Parsing: JSON-LD ``Product`` first,
    DOM / og fallback for the rare page that ships no JSON-LD. Brand is
    always coerced to ``"BLOX Racing"`` (100% first-party catalogue). The
    JSON-LD ``mpn`` carries a Shopify variant ID on this store — the
    adapter discards it and uses ``sku`` as the part number.
    """

    # Default Tier 0 — plain HTTP is enough (Cloudflare on this origin does
    # not challenge ``requests``). Left explicit so the choice is documented
    # on the class itself rather than only in the module docstring.
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``sitemap.xml`` (minus non-product
        children). Set ``CRAWLER_BLOXRACING_START_URLS`` (comma-separated)
        to override with a fixed list. A jittered delay is applied between
        sitemap-child fetches inside ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a BLOX Racing product page.

        1. JSON-LD ``Product`` (authoritative on this Shopify storefront) —
           name, description, brand, sku, price, cover image. Merge DOM
           gallery images on top of the single-URL JSON-LD cover so we keep
           the full carousel. The JSON-LD ``mpn`` is the Shopify variant ID
           on this store and is explicitly discarded.
        2. DOM / og fallback — h1/og:title, meta description, DOM price,
           SKU via text scan, brand via shared title/description heuristics
           (then coerced to the canonical ``"BLOX Racing"``).

        Returns ``None`` when no usable name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Shopify default schema, plus a Breadcrumb and
        #    WebSite block that the shared extractor ignores).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price

                # Discard Shopify variant-ID mpn; prefer the real sku.
                raw_sku = item.get("sku") if isinstance(item.get("sku"), str) else None
                raw_mpn = item.get("mpn") if isinstance(item.get("mpn"), str) else None
                part_number = _select_part_number(raw_sku, raw_mpn)

                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)

                # JSON-LD image is typically a single-element array; merge DOM
                # gallery so we get the full product carousel.
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
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
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

        price_cents = dom_price
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if sku_elem:
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # Title / description heuristics, then collapse to the canonical
        # house brand (BLOX is a 100% first-party catalogue).
        part_manufacturer_guess = part_manufacturer_from_title(str(name))
        if not part_manufacturer_guess and description:
            part_manufacturer_guess = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer_guess:
            part_manufacturer_guess = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer_guess, str(name))

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
