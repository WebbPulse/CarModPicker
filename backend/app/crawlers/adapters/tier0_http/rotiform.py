"""
Rotiform Wheels (rotiform.com) crawler adapter — Tier 0 (plain HTTP).

Host: ``www.rotiform.com`` (the bare apex 301s to ``www``). The candidate
``rotiformwheels.com`` is a **parked domain for sale on Spaceship**, not a
brand-owned storefront — we intentionally do not map it.

Rotiform is a **direct-to-consumer** consumer wheel brand owned by Wheel
Pros (alongside fifteen52, KMC, Fuel, TSW, etc.). The storefront lists
SKU-level pricing publicly (no dealer login), so this is ingest-bearing
unlike HRE or Wheels Boutique which are quote-driven. See
``RETAILER_BACKLOG.md`` Batch 2C #34.

Platform: **Magento 2 / Adobe Commerce** (Wheel Pros family stack).
Evidence: ``Magento_PageCache`` / ``Magento_PageBuilder`` / ``adminhtml``
paths in the page body, ``/index.php/`` in ``robots.txt``, and the
familiar Magento-shaped ``jsonConfig`` / ``/checkout/cart/add/uenc/`` cart
endpoints. Product URLs live at the site root (``/<handle>``) — there is
no ``/products/`` prefix on this theme, same as the 034Motorsport case.

JSON-LD shape: **``@type: ProductGroup``** (the canonical parent-with-
variants schema, §4 of ``VARIANTS.md``) with a ``hasVariant[]`` array of
``Product`` blocks. The group carries ``name``, ``brand``, and
``productGroupID``; each variant carries its own ``sku``, ``name``,
``price``, ``image``, ``color``, and ``size``. The page also renders a
Magento ``jsonConfig`` with per-variant prices and image paths; we do not
read it because the JSON-LD variant[0] already suffices for the
"parent + one winner" contract.

Variant rule — **this is the canonical known-loss case from VARIANTS.md
§5.** Wheels hit all three yes/yes/yes criteria:

- *Different MPNs?* Yes. Every fitment ships as its own SKU
  (``R143189525+35`` = R143 LAS-R gloss silver 18×9.5 +35 5x112/5x120,
  ``R142198523+45`` = R142 LAS-R matte black 19×8.5 +45 5x108/5x120, …).
- *Different prices?* Yes. The LAS-R PDP spans roughly $243–$504 across
  its variants.
- *Different fitment?* Yes — the variant axes **are fitment**: diameter ×
  width × offset × bolt pattern × finish/color. A 19×8.5 +45 5x112 wheel
  does not fit a car that needs 18×9.5 +35 5x120.

Collapsing N fitments to one Part row is lossy (Option A from
VARIANTS.md §6). This adapter does it anyway — it reads the ProductGroup
root for ``name`` / ``brand`` / ``productGroupID`` (becomes
``part_number``) and the first variant for a representative ``image``.
Price is intentionally left ``None`` because a single "starting at" /
"cheapest variant" number would mis-price the Part card for most
fitments (the LAS-R floor is $243, but the common 5x112 BMW fitment is
higher). Matches the posture Wheels Boutique and HRE chose for the same
reason.

Brand rule: always canonical ``"Rotiform"``. The JSON-LD
``brand.name`` is reliable on PDPs but occasionally empty on the
vehicle-gallery pages (which we filter out); regardless, every product
on rotiform.com is Rotiform's own manufacture, so we hard-code the brand
rather than running title heuristics.

Non-product URL shapes we must reject (all under the same ``/<slug>``
root, so the URL shape alone is not enough):

- **Vehicle gallery pages** — ``/rotiform-<model>-<year>-<make>-<vehicle>-<id>``
  (e.g. ``/rotiform-lse-2024-bmw-m2-235``). These emit ``@type: Product``
  with ``price: 0``, ``sku: "rotiform-gallery-<id>"``, empty brand, and
  ``Categories: ["Vehicle Gallery"]``. They are fitment showcases, not
  purchasable inventory. Filter by the trailing ``-<digits>`` segment at
  URL time and, defensively, by the ``rotiform-gallery-`` SKU prefix in
  the parser.
- **CMS / brand pages** — ``/privacy-policy``, ``/warranty``, ``/home``,
  ``/motorsports``, ``/galleries``, category indexes like ``/wheels``,
  ``/merch``, ``/products``, ``/vehicle-gallery``, ``/catalog/category/view/id/208``.
  These either lack a ``/rotiform-`` prefix or are the category landings
  themselves; both are handled by the URL filter.
- **Merch** (``/rotiform-rt-*``, ``/rotiform-rf-*``, shirts, hats,
  stickers) — *accepted*. They also emit ProductGroup JSON-LD with
  usable sku/price/image; the catalog category mapping will route them
  correctly even though the default ``CRAWLER_DEFAULT_CATEGORY_NAME`` is
  ``wheels``. Not worth a separate URL filter.

Discovery: ``/sitemap.xml`` is a **single flat urlset** (not a sitemap
index), same shape as HRE. Every ``<loc>`` is either a product or CMS
page; the filter is URL-shape-based: must start with ``/rotiform-`` or
``/rotiform`` and must not match the vehicle-gallery trailing-id
pattern. Override with ``CRAWLER_ROTIFORM_START_URLS`` (comma-separated).

Robots: ``/robots.txt`` allows catalog crawling — disallows only the
Magento admin surfaces (``/app/``, ``/var/``, ``/vendor/``, ``/index.php/``,
``/catalog/category/view/``, ``/catalog/product/view/``, ``/catalogsearch/``,
``/checkout/``, ``/customer/``, etc.) plus sort/filter query params. Our
product URLs are under ``/rotiform-<handle>`` and are clean.

Fetcher tier: ``http``. Plain ``requests`` with the crawler UA clears
the Fastly CDN front on both ``/sitemap.xml`` and PDPs (``x-served-by:
cache-<pop>`` headers, no ``cf-ray`` / ``cf-mitigated`` markers). Promote
to ``"tls"`` if Fastly ever starts JA3-fingerprinting us off.

Caveats:

- Wheel Pros ownership: if Rotiform pricing ever gets rolled into a
  shared Wheel Pros dealer portal and pulled from the public PDP, this
  adapter flips into HRE-style catalog-only mode (``price_cents=None``).
  Not the case today.
- ``product:price:amount`` meta tag is always ``0`` on these configurable
  Magento PDPs (the price renders per-variant via ``jsonConfig``), so
  ``extract_dom_price`` would return $0.00 if asked. We explicitly do not
  use it; price is intentionally ``None`` anyway to avoid mis-pricing
  across fitments.
- Merch products inherit the ``wheels`` default category unless the
  operator sets ``CRAWLER_DEFAULT_CATEGORY_NAME=apparel`` for a separate
  merch crawl.
"""

import json
import os
import re
from typing import Any, Dict, Iterator, List, Optional, cast
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
)

ROTIFORM_BASE = "https://www.rotiform.com"
SITEMAP_URL = ROTIFORM_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical brand. Every product on rotiform.com is Rotiform's own manufacture,
# so collapse empty / case-variant brand strings to one row in the global
# part-manufacturer table (same posture as the fifteen52 / Titan7 adapters).
ROTIFORM_BRAND = "Rotiform"

# Vehicle-gallery PDPs are shaped ``/rotiform-<model>-<year>-<make>-<vehicle>-<id>``
# (e.g. ``/rotiform-lse-2024-bmw-m2-235``). They emit @type:Product but with
# price=0 and sku="rotiform-gallery-<id>" — they are fitment showcases, not
# real inventory. Reject by the trailing ``-<digits>`` segment. Real product
# slugs (e.g. ``rotiform-forged-917``, ``rotiform-customspec-356``) use model
# codes that happen to be numeric too, so we must match a hyphen + digits AT
# END and additionally require the preceding path structure to look like a
# gallery slug (at least two hyphen-separated tokens after ``rotiform-``).
# Heuristic: ``/rotiform-<tok>-<tok>...-<N>`` where ``<N>`` is a bare integer
# AND there are >= 4 hyphen-separated segments after the leading ``rotiform-``
# (model + year + make + ... + id). The ``rotiform-forged-917`` shape only has
# 2 segments (forged + 917) after the prefix and is preserved.
_VEHICLE_GALLERY_RE = re.compile(
    r"^/rotiform(?:-[a-z0-9]+){4,}-\d+/?$",
    re.IGNORECASE,
)

# Non-product site-root slugs we've seen in the sitemap. Not exhaustive —
# the URL filter is an allowlist on the ``/rotiform-`` prefix, so most CMS
# pages (``/privacy-policy``, ``/warranty``, ``/merch``, ``/wheels``,
# ``/vehicle-gallery``, ``/motorsports``, …) are already excluded. This set
# is only the slugs that happen to START with ``/rotiform`` but are not PDPs.
_NON_PRODUCT_ROTIFORM_SLUGS = frozenset(
    {
        "rotiform",  # the brand-overview landing page (last entry in sitemap)
    }
)

# Magento ships its catalog images under ``/media/catalog/product/...`` on the
# origin CDN, and Wheel Pros also uses Scene7 (``s7d9.scene7.com/is/image/
# wheelpros/...``) for some hero renders. Both are valid product-image hosts;
# anything else (logos, banners, payment-method icons, etc.) is chrome.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|"
    r"favicon|sprite|icon[-_]|recently_(viewed|compared)",
    re.IGNORECASE,
)


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_ROTIFORM_START_URLS`` (comma-separated) if set; else ``None``."""
    raw = os.environ.get("CRAWLER_ROTIFORM_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is a Rotiform PDP candidate.

    Accepts any ``/rotiform-<handle>`` path on ``rotiform.com`` (www. or apex)
    that is not a vehicle-gallery showcase and not the brand-overview slug.
    The parser does a second-line defense by rejecting ``rotiform-gallery-``
    SKU prefixes in ProductGroup JSON-LD.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "rotiform.com" and not host.endswith(".rotiform.com"):
        return False
    path = parsed.path or "/"
    # Trim trailing slash for comparison; sitemap emits both shapes occasionally.
    check = path.rstrip("/")
    if not check.lower().startswith("/rotiform"):
        return False
    # Reject the bare ``/rotiform`` landing page.
    slug = check.lstrip("/").lower()
    if slug in _NON_PRODUCT_ROTIFORM_SLUGS:
        return False
    # Reject vehicle-gallery URLs (``-<year>-<make>-...-<numeric-id>``).
    if _VEHICLE_GALLERY_RE.match(check + "/"):
        return False
    # Require a hyphen after ``/rotiform`` so we don't accept ``/rotiform``
    # itself, and require at least one non-digit character after it (the
    # model slug).
    if not re.match(r"^/rotiform-[a-z0-9][a-z0-9\-]*$", check, re.IGNORECASE):
        return False
    return True


def _discover_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (flat urlset, not an index) and filter locs to
    product-shaped URLs. Returns an empty list on fetch/parse failure so
    the caller falls through to ``DEFAULT_START_URLS``.
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
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        raw = loc.text.strip()
        if not raw:
            continue
        base = raw.split("?")[0]
        if not _is_product_url(base):
            continue
        if base in seen:
            continue
        seen.add(base)
        product_urls.append(base)
    return product_urls


DEFAULT_START_URLS = [
    "https://www.rotiform.com/rotiform-las-r",
]


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Find the first ``@type: ProductGroup`` JSON-LD block on the page.

    Mirrors the helper on ``maperformance.py`` / ``ets.py`` / ``burgermotorsports.py``
    / ``texasspeed.py`` (VARIANTS.md §4 — the shared ``extract_json_ld_product``
    only accepts ``Product``, so each ProductGroup-emitting adapter currently
    ships its own). When a fifth adapter needs this, lift it into
    ``parsing.py``.
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
    """Return the first ``Product`` entry from a ``ProductGroup.hasVariant`` list, if any."""
    variants = group.get("hasVariant")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if isinstance(v, dict):
            return v
    return None


def _image_from_variant_or_group(
    variant: Optional[Dict[str, Any]],
    group: Dict[str, Any],
) -> Optional[str]:
    """
    Prefer the first variant's image (higher-resolution hero per fitment) and
    fall back to the group's image (series hero). Rotiform's group image is
    the first variant's hero rendered at a smaller size; picking the variant
    first gets us the higher-res asset when both are present.
    """

    def _first_url(value: Any) -> Optional[str]:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            for entry in value:
                u = _first_url(entry)
                if u:
                    return u
        if isinstance(value, dict):
            nested = value.get("url") or value.get("contentUrl")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
        return None

    if isinstance(variant, dict):
        u = _first_url(variant.get("image"))
        if u:
            return u
    return _first_url(group.get("image"))


def _is_valid_product_image(url: str) -> bool:
    """True for Rotiform origin (``/media/catalog/product/``) or Scene7 (``s7d9.scene7.com``) assets."""
    if not url:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    is_magento = "rotiform.com/media/catalog/product/" in low
    is_scene7 = "s7d9.scene7.com" in low and "/wheelpros/" in low
    if not (is_magento or is_scene7):
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _collect_images(hero: Optional[str]) -> List[str]:
    """
    Return a one-image gallery (Rotiform's JSON-LD gives exactly one image per
    variant, and the per-fitment photo is the highest-signal asset we have).
    Deduped, validated against the product-CDN allowlist.
    """
    if not hero:
        return []
    candidate = hero.strip()
    if not candidate.startswith("http"):
        # Occasionally the URL has a stray ``//`` prefix from JSON-LD escaping;
        # upgrade to https so the Part image loads.
        if candidate.startswith("//"):
            candidate = "https:" + candidate
        elif candidate.startswith("/"):
            candidate = ROTIFORM_BASE + candidate
        else:
            return []
    if not _is_valid_product_image(candidate):
        return []
    return [candidate]


def _payload_from_product_group(
    group: Dict[str, Any],
    product_url: str,
) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a Rotiform ProductGroup.

    - ``name`` — the group's name (e.g. ``"Rotiform LAS-R"``).
    - ``part_number`` — the group's ``productGroupID`` (stable family SKU,
      e.g. ``"rotiform-rc-las-r"``). Per-variant SKUs (R143189525+35 etc.)
      are lost under Option A. Using ``productGroupID`` keeps cross-retailer
      dedupe usable at the family level even if it can't price-match a
      specific fitment.
    - ``part_manufacturer`` — hard-coded ``"Rotiform"``.
    - ``description`` — the group's ``description`` when present; for wheel
      PDPs this is usually empty (merch pages have real copy).
    - ``price_cents`` — ``None`` (see module docstring — conflating a
      $243–$504 range into one number is worse than no number).
    - ``image_urls`` — first variant's image, or the group's image as
      fallback. Exactly one hero.

    Returns ``None`` when ``name`` is missing or when the group's SKU has
    the ``rotiform-gallery-`` prefix (second-line defense against the
    vehicle-gallery pages — those don't actually emit ProductGroup, but
    guard anyway so the contract survives theme changes).
    """
    name_val = group.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None

    group_sku_val = group.get("sku") or group.get("productGroupID")
    group_sku = group_sku_val.strip() if isinstance(group_sku_val, str) and group_sku_val.strip() else None
    if group_sku and group_sku.lower().startswith("rotiform-gallery-"):
        return None

    description: Optional[str] = None
    desc_val = group.get("description")
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    variant = _first_variant(group)
    hero = _image_from_variant_or_group(variant, group)
    images = _collect_images(hero)

    part_number = normalize_part_number(group_sku) if group_sku else None

    return ScrapedPayload(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=None,
        part_manufacturer=ROTIFORM_BRAND,
        part_number=part_number,
        image_urls=images if images else None,
    )


class RotiformAdapter(RetailerCrawlerAdapter):
    """
    Rotiform Wheels adapter — Magento 2 storefront, ProductGroup JSON-LD,
    plain HTTP fetch.

    Discovery: ``CRAWLER_ROTIFORM_START_URLS`` env var wins. Otherwise
    walks the flat ``/sitemap.xml`` urlset and filters to
    ``/rotiform-<handle>`` PDP URLs (rejecting the vehicle-gallery and
    brand-overview slugs). Falls back to ``DEFAULT_START_URLS`` if the
    sitemap fetch fails.

    Parsing: reads the page's ``@type: ProductGroup`` JSON-LD — the
    canonical multi-variant schema. Emits one ScrapedPayload per URL with
    the group's name/brand/productGroupID (per-variant SKUs + prices are
    lost under VARIANTS.md §6 Option A — see module docstring). Returns
    ``None`` for non-product URLs or when no ProductGroup can be found.

    Fetcher tier: ``"http"``. Promote to ``"tls"`` only if Fastly starts
    JA3-fingerprinting us off the CDN front.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins, then sitemap, then ``DEFAULT_START_URLS``."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return
        discovered = _discover_via_sitemap()
        for url in discovered or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Rotiform PDP into a ScrapedPayload.

        Returns ``None`` for non-product URLs (vehicle-gallery showcases,
        CMS pages, category indexes) and for pages without a ProductGroup
        JSON-LD block. No DOM / og fallback: every live PDP on this theme
        emits ProductGroup, and without it the page is almost certainly
        not a product (a vehicle-gallery leak, a 404 styled as a CMS page,
        etc.) — parsing it via og: would produce misleading rows.
        """
        if not _is_product_url(url):
            return None
        group = _extract_product_group_from_json_ld(html)
        if not group:
            return None
        return _payload_from_product_group(group, url)
