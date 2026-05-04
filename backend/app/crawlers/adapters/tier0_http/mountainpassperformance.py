"""
Mountain Pass Performance (mountainpassperformance.com) crawler adapter.

Tesla-only performance specialist — coilovers, spring kits, sway bars,
control arms, upgrade kits, and a handful of resold track consumables
(Castrol SRF, Pagid brake fluid) for Model 3 (RWD/AWD/Performance/Highland),
Model Y (incl. 2026 Performance), Model S (Plaid), and Model X. **House
brand on every part** — MPP re-SKUs even the resold consumables under
their own ``CAS-*`` / ``PAG-*`` prefix scheme, so the catalog really is
one brand as far as our data model is concerned.

Platform: **WordPress + WooCommerce** with Yoast SEO and Jetpack sitemaps.
The site runs behind nginx on a shared host; plain ``requests`` gets a
complete HTML response with JSON-LD on first try (no Cloudflare challenge,
no TLS fingerprinting). Apex ``mountainpassperformance.com`` 301s to
``www.mountainpassperformance.com`` — all real URLs live on the ``www``
host and that's what the sitemap advertises.

Host: ``www.mountainpassperformance.com`` (apex 301 → www).

Discovery: Yoast emits ``/sitemap_index.xml`` pointing at a flat
``/product-sitemap.xml`` urlset (~92 product URLs at time of writing,
each ``/product/<slug>/`` with a trailing slash) plus post / page /
category sibling sitemaps we don't care about. We fetch the product
sitemap directly — it's a plain urlset, not a sitemap index — and filter
to ``/product/<slug>/`` URLs, dropping the ``/shop/`` landing page that
the sitemap also lists. Override with
``CRAWLER_MOUNTAINPASSPERFORMANCE_START_URLS`` (comma-separated).

JSON-LD shape: Every product page ships **two** ``<script
type="application/ld+json">`` blocks.

  1. Yoast ``yoast-schema-graph`` (``@graph`` of ``WebPage`` + ``WebSite``
     + ``BreadcrumbList`` + ``Organization`` + ``ImageObject``) — NO
     ``@type: Product`` entry. The shared extractor correctly ignores
     this one because none of its ``@graph`` items are products.
  2. A second script the WooCommerce-SEO plugin emits, also wrapped in
     ``@graph`` but containing ``@type: Product`` with ``name``, ``url``,
     ``description``, ``image`` (single URL), ``sku`` / ``mpn``, ``brand``
     (``@type: Brand``, ``name: "Mountain Pass Performance"``), and an
     ``offers`` array. **The offers never carry a ``price`` field** —
     just ``priceValidUntil`` + ``availability`` + ``seller``. This is a
     WooCommerce-SEO plugin quirk, not a MAP-policy decision. We have to
     source price elsewhere (see below). The shared URL-aware
     ``extract_json_ld_product`` picks the right Product from this block
     because it unwraps ``@graph``.

Variant strategy (per VARIANTS.md §5 — suspension hardware has a
**spring-rate / damping axis**): WooCommerce "variable product" pages
(e.g. the MPP/KW Sports Coilovers, Road Upgrade Kits) carry multiple
child SKUs varying by spring rate / kit level / damping tune. The JSON-LD
Product at the parent URL exposes only one SKU + image and no price; the
DOM shows a price range (``$485.00 – $665.00``). Like every other
adapter we emit **one ``ScrapedPayload`` per URL** and accept the parent
representation — price lands at the floor of the range via the DOM price
pattern; variant-specific part numbers are lost. Documented here so the
next hand knows where the axis hides. Option D (first-class Variant
model) would lift this; see VARIANTS.md §6 for the menu.

Price resolution order (JSON-LD has no price, so we have to reach):

  1. ``<span class="woocommerce-Price-amount"><bdi>$<…>$X.YY</bdi></span>``
     — the rendered sell price. For variable products this is the low
     end of the range (first ``woocommerce-Price-amount`` in the offers
     panel is the range start).
  2. ``window.ga4w.data.product.prices.price`` — WooCommerce's Google
     Analytics integration emits the sell price in minor units (cents)
     in an inline ``<script>``. This is authoritative and survives when
     the DOM markup shifts. Used as fallback because the regex is
     coarser.
  3. ``extract_dom_price`` shared helper — final last-ditch match on
     ``og:price:amount`` and the first ``$...`` token in the body. Cheap
     noise-floor catch.

SKU rule: JSON-LD ``sku`` / ``mpn`` when non-empty AND not a bare
integer. MPP re-SKUs every product under their own prefix scheme —
``MPP-TM3-DMPR-005`` (Model 3 damper 005), ``MPP-TMY-SPNG-*`` (Model Y
springs), ``CAS-15AFA4`` (Castrol SRF), ``PAG-*`` (Pagid) — so the SKU
is authoritative and cross-retailer dedupe works. **Integer-only SKUs
are the WordPress post ID** (e.g. ``"sku": 24642``) leaking through when
the product owner didn't enter a real SKU; those are rejected so we
don't store the post ID as a part number.

Brand rule — **always "Mountain Pass Performance"**. The catalog is
Tesla-only and every product title leads with the target vehicle
(``"Comfort Adjustable Coilovers for Tesla Model 3 RWD"``, ``"MPP Tesla
Model 3 Highland Performance Road Upgrade Kit Level 1"``, ``"Castrol SRF
Racing Brake Fluid"``). The shared ``part_manufacturer_from_title``
heuristic would otherwise pick ``"Tesla"`` (car make), ``"Comfort"`` /
``"MPP"`` (product descriptor / acronym we don't want as a brand row),
or — for resold products — the resold-brand name (``"Castrol"``,
``"Pagid"``). The JSON-LD ``brand.name`` is uniformly ``"Mountain Pass
Performance"`` on every PDP, **including resold-brand products**
(verified on ``/product/castrol-srf-racing-brake-fluid/``), because the
WooCommerce-SEO plugin pulls from the shop "brand" taxonomy and MPP has
every product tagged under their own house brand. So we follow Verus /
ADRO and force the canonical brand unconditionally:

- Empty / whitespace JSON-LD brand → ``"Mountain Pass Performance"``
- Car make (``tesla``, plus ``ford`` / ``chevrolet`` / ``honda`` / etc.
  in case MPP ever broadens beyond Tesla) → ``"Mountain Pass Performance"``
- Generic reject token (``the`` / ``new`` / ``oem``) →
  ``"Mountain Pass Performance"``
- An ``"MPP"`` / ``"Mountain Pass …"`` variant → canonical form
- Anything else → pass through unchanged (belt-and-suspenders in case
  MPP ever exposes real resold-brand metadata in the future)

**Tesla is explicitly in the car-make blocklist.** Titles like "Tesla
Model 3 Highland Performance Road Upgrade Kit" would otherwise let
"Tesla" leak through the heuristic when JSON-LD brand is missing.

Images: JSON-LD ``image`` is a single URL (the hero). WooCommerce
renders the gallery as ``<div class="woocommerce-product-gallery__image">``
with the real image URL in ``data-src`` (not ``src`` — the src is a
base64 placeholder for lazy-loading). We collect the hero + every
``data-src`` inside ``.woocommerce-product-gallery__wrapper`` and
dedupe. All media lives under ``/wp-content/uploads/YYYY/MM/…`` on the
same host; any ``<img>`` outside that path (site chrome, Divi theme
widgets, social icons) is dropped. Capped at 12.

Tier rationale: Plain Tier 0. ``curl`` and the default crawler UA both
return 200 OK with complete HTML. ``robots.txt`` disallows only
``/wp-admin/`` and ``/readme.html`` / ``/refer/`` — every product page
is allowed.

Caveats:
- JSON-LD ``offers.price`` is always missing. Price must come from DOM
  or the ``window.ga4w`` inline script. Don't trust an ingest that
  produces ``price_cents = None`` on this site — something upstream
  broke.
- Integer ``sku`` fields are the WP post ID (WooCommerce default when
  no SKU is set in the product admin). Reject them — they'd otherwise
  ride through ``normalize_part_number`` as-is since our numeric-only
  guard in ``normalize_part_number`` doesn't exist yet.
- Variable products collapse to the parent representation (one SKU,
  range-start price). See VARIANTS.md §5 — suspension hardware is one
  of the three cases where this matters most.
- The Yoast ``@graph`` JSON-LD script is misleading if read naively —
  it has no ``@type: Product`` entry, only ``WebPage``/``Organization``/
  etc. The shared URL-aware extractor correctly walks both scripts and
  picks the one containing the Product.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urljoin, urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    scraped_payload_from_json_ld,
)

MPP_BASE = "https://www.mountainpassperformance.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Yoast emits a dedicated product sitemap (flat urlset, not an index).
PRODUCT_SITEMAP_URL = f"{MPP_BASE}/product-sitemap.xml"

# Verified live product URLs used as a fallback when sitemap discovery
# fails and no env override is provided. Picked across MPP's own Tesla
# platforms so the first crawl exercises the JSON-LD path end to end.
DEFAULT_START_URLS = [
    "https://www.mountainpassperformance.com/product/mpp-model-3-comfort-adjustable-coilovers-rwd/",
    "https://www.mountainpassperformance.com/product/mpp-model-3-sports-coilovers/",
]

# Canonical brand for every part in the MPP catalog. See module docstring.
CANONICAL_BRAND = "Mountain Pass Performance"

# Car makes that the title heuristic would otherwise surface as a brand.
# **Tesla is first** — MPP is Tesla-only and every title leads with
# "Tesla Model 3 …" / "Tesla Model Y …". The other makes are
# belt-and-suspenders in case MPP ever broadens the catalog or lists a
# cross-platform track consumable.
_CAR_MAKES = frozenset(
    {
        "tesla",
        "ford",
        "chevrolet",
        "chevy",
        "honda",
        "toyota",
        "subaru",
        "nissan",
        "bmw",
        "mazda",
        "porsche",
    }
)

# Generic words the title heuristic sometimes lands on (shared shape with
# `grimmspeed`). These + car makes → coerce to canonical MPP brand.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem", "mpp"})

# `window.ga4w.data.product.prices.price` is the WooCommerce Google
# Analytics integration's inline sell price in minor units (cents).
# This regex is resilient to whitespace and key-order changes.
_GA4W_PRICE_RE = re.compile(
    r'"prices"\s*:\s*\{[^{}]*?"price"\s*:\s*(\d+)',
    re.DOTALL,
)

# SKU shape guard: an integer-only value is almost certainly the
# WordPress post ID leaking through from a product where no real SKU
# was entered in admin. Reject it so we don't store e.g. "24642" as a
# part number. Real MPP SKUs all contain at least one letter
# (`MPP-TM3-*`, `CAS-*`, `PAG-*`).
_INT_ONLY_SKU_RE = re.compile(r"^\d+$")

# Image URL patterns that are site chrome rather than product gallery media.
# Mirrors the shape from `grimmspeed` — MPP's Divi theme + WooCommerce
# gallery share the same Wordpress chrome vocabulary.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via the Yoast product sitemap."""
    raw = os.environ.get("CRAWLER_MOUNTAINPASSPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _is_product_url(url: str) -> bool:
    """
    True iff ``url`` looks like an MPP product page: www host,
    ``/product/<slug>/`` path (at least one segment after ``/product/``),
    no query string in play. The shop landing page at ``/shop/`` is
    explicitly excluded — the Yoast product-sitemap lists it alongside
    real products.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host not in ("www.mountainpassperformance.com", "mountainpassperformance.com"):
        return False
    path = parsed.path.strip("/")
    if not path.startswith("product/"):
        return False
    rest = path[len("product/") :]
    if not rest:
        return False
    # Any ``/product/<slug>[/…]`` URL is a candidate; the Product JSON-LD
    # guard in ``parse_product_page`` is authoritative.
    return True


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/product-sitemap.xml`` (Yoast flat urlset) and return every
    ``/product/<slug>/`` URL. Deduplicated by full URL (query stripped).
    Empty list on failure; the caller falls back to DEFAULT_START_URLS.
    """
    seen: set[str] = set()
    product_urls: List[str] = []
    try:
        xml_text = fetch_page(PRODUCT_SITEMAP_URL, timeout=15)
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        u = loc.text.strip().split("?", 1)[0]
        if not _is_product_url(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        product_urls.append(u)
    return product_urls


def _normalize_brand(raw: Optional[str]) -> str:
    """
    Return the canonical manufacturer for an MPP product page.

    - Empty / whitespace → ``"Mountain Pass Performance"``.
    - Car make (``tesla``/etc.) or reject token (``the``/``new``/``oem``/
      ``mpp``) → ``"Mountain Pass Performance"``.
    - Any ``"Mountain Pass …"`` or ``"MPP …"`` variant → canonical form.
    - Anything else → pass through unchanged. In practice the JSON-LD
      always delivers ``"Mountain Pass Performance"`` (MPP re-brands
      resold parts under their own catalog), so the pass-through path
      is belt-and-suspenders for future behavior changes.
    """
    brand = (raw or "").strip()
    if not brand:
        return CANONICAL_BRAND
    low = brand.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return CANONICAL_BRAND
    if (
        low == "mountain pass performance"
        or low.startswith("mountain pass performance ")
        or low == "mountain pass"
        or low.startswith("mountain pass ")
        or low.startswith("mpp ")
        or low.startswith("mpp-")
    ):
        return CANONICAL_BRAND
    return brand


def _is_valid_sku(raw: Optional[str]) -> bool:
    """Non-empty and not a bare integer (WP post ID leak)."""
    if not raw or not raw.strip():
        return False
    return not _INT_ONLY_SKU_RE.match(raw.strip())


def _extract_ga4w_price_cents(html_text: str) -> Optional[int]:
    """
    Pull the sell price in cents out of the WooCommerce GA integration's
    inline ``window.ga4w = { data: {..., "product": {..., "prices": {"price": N, ...}} } }``
    script. N is minor units (cents) — no multiplication needed.
    """
    match = _GA4W_PRICE_RE.search(html_text)
    if not match:
        return None
    try:
        cents = int(match.group(1))
    except (TypeError, ValueError):
        return None
    return cents if cents > 0 else None


def _extract_dom_woocommerce_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    WooCommerce renders the sell price inside
    ``<span class="woocommerce-Price-amount">$<bdi>X.YY</bdi></span>``.
    On variable products the first ``Price-amount`` in the offers panel
    is the low end of the price range (e.g. ``$485.00`` in
    ``$485.00 – $665.00``).
    """
    for span in soup.find_all(class_="woocommerce-Price-amount"):
        if not isinstance(span, Tag):
            continue
        text = span.get_text(" ", strip=True)
        if not text:
            continue
        cents = parse_price_cents(text)
        if cents is not None and cents > 0:
            return cents
    return None


def _normalize_image_url(url: str, page_url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths."""
    u = url.strip()
    if not u:
        return u
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return urljoin(page_url, u)
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only ``wp-content/uploads/…`` media; reject chrome and data: URIs."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/wp-content/uploads/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _extract_dom_images(soup: BeautifulSoup, page_url: str) -> List[str]:
    """
    Collect product gallery image URLs. WooCommerce renders each gallery
    image as
    ``<div class="woocommerce-product-gallery__image">
         <a href="<full-res>">
           <img src="<base64-placeholder>" data-src="<full-res>" … />
         </a>
       </div>``
    inside ``.woocommerce-product-gallery__wrapper``. We prefer the
    ``<a href>`` (highest-res zoom target) and fall back to
    ``data-src`` / ``src`` on the img. Capped at 12.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw, page_url)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        if u in seen:
            return
        seen.add(u)
        ordered.append(u)

    gallery = soup.find(class_="woocommerce-product-gallery__wrapper")
    if not isinstance(gallery, Tag):
        gallery = soup.find(class_="woocommerce-product-gallery")
    if isinstance(gallery, Tag):
        for image_div in gallery.find_all(class_="woocommerce-product-gallery__image"):
            if not isinstance(image_div, Tag) or len(ordered) >= 12:
                break
            link = image_div.find("a")
            if isinstance(link, Tag):
                href = link.get("href")
                if isinstance(href, str):
                    add(href)
            for img in image_div.find_all("img"):
                if not isinstance(img, Tag):
                    continue
                for attr in ("data-src", "data-large_image", "src"):
                    val = img.get(attr)
                    if isinstance(val, str) and val.strip() and not val.strip().startswith("data:"):
                        add(val.strip())
                        break

    return ordered[:12]


class MountainPassPerformanceAdapter(RetailerCrawlerAdapter):
    """
    Mountain Pass Performance adapter. Discovery: Yoast
    ``/product-sitemap.xml`` flat urlset filtered to ``/product/<slug>/``.
    Parsing: JSON-LD ``Product`` (second ``@graph`` script — the Yoast
    graph has no Product entry) for name / description / sku / mpn /
    brand / cover image, then DOM / ``window.ga4w`` for price (JSON-LD
    offers have no price field on this site), then
    ``.woocommerce-product-gallery__image`` for the full gallery. Brand
    is forced to "Mountain Pass Performance" on every part (Tesla-only
    house-brand catalog; resold parts are re-SKUed under MPP's own
    scheme and tagged under MPP in the WooCommerce brand taxonomy).
    Variant axis (spring rate / kit level / damping tune on suspension
    hardware) is **not** expanded — one payload per URL per VARIANTS.md
    §5; the parent SKU and low-end-of-range price win.
    """

    ADAPTER_NAME: ClassVar[str] = "mountainpassperformance"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the Yoast product sitemap; env override wins."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an MPP product page.

        1. JSON-LD ``Product`` via the shared URL-aware extractor — walks
           both ``@graph`` scripts and picks the one with the Product
           entry. Yields name / description / sku / mpn / brand / cover
           image. Price is always missing from JSON-LD offers here.
        2. Price: DOM ``.woocommerce-Price-amount`` (low end for variable
           products) → ``window.ga4w`` inline data → shared
           ``extract_dom_price`` fallback.
        3. Gallery: merge JSON-LD cover + every ``data-src`` inside
           ``.woocommerce-product-gallery__image``.
        4. Brand: always canonicalized to "Mountain Pass Performance"
           (see ``_normalize_brand`` / module docstring).

        Returns ``None`` when the page has no JSON-LD Product (category,
        blog, landing page) or when the product name can't be recovered.
        """
        if not _is_product_url(url):
            return None
        soup = BeautifulSoup(html, "html.parser")

        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None
        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        # Price: JSON-LD carries none; DOM first, then ga4w, then generic.
        price_cents: Optional[int] = payload.price_cents
        if price_cents is None:
            price_cents = _extract_dom_woocommerce_price_cents(soup)
        if price_cents is None:
            price_cents = _extract_ga4w_price_cents(html)
        if price_cents is None:
            price_cents = extract_dom_price(soup)

        # SKU: JSON-LD value when it's a real SKU; reject bare-integer
        # values (WooCommerce falls back to the WordPress post ID when
        # no SKU is entered in admin).
        part_number: Optional[str] = None
        if _is_valid_sku(payload.part_number):
            part_number = normalize_part_number(payload.part_number)

        # Description: prefer JSON-LD (WooCommerce-SEO ships the full
        # long description); fall back to og:description / meta description.
        description = payload.description
        if not description:
            og_desc = soup.find("meta", property="og:description")
            if isinstance(og_desc, Tag):
                val = og_desc.get("content")
                if isinstance(val, str) and val.strip():
                    description = normalize_description_text(val, max_len=2000)
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                val = meta_desc.get("content")
                if isinstance(val, str) and val.strip():
                    description = normalize_description_text(val, max_len=2000)

        # Images: merge JSON-LD cover with the DOM gallery, dedup.
        image_urls: List[str] = []
        seen_images: set[str] = set()
        for u in payload.image_urls or []:
            if u and u not in seen_images:
                seen_images.add(u)
                image_urls.append(u)
        for u in _extract_dom_images(soup, url):
            if u in seen_images or len(image_urls) >= 12:
                continue
            seen_images.add(u)
            image_urls.append(u)

        part_manufacturer = _normalize_brand(payload.part_manufacturer)

        return ScrapedPayload(
            name=payload.name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            # Tesla-only house-brand catalog: force canonical brand on
            # every part. See module docstring for rationale (titles
            # lead with "Tesla Model 3 …", "Tesla" is in the car-make
            # blocklist, JSON-LD brand always returns MPP even on
            # resold Castrol/Pagid parts).
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )
