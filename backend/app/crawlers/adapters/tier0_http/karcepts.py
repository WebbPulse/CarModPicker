"""
Karcepts (karcepts.com) crawler adapter — Tier 0 (plain HTTP).

Platform: **Shopify** (Cloudflare passive in front, older "Simple" theme —
``powered-by: Shopify`` plus the standard ``/sitemap.xml`` → ``sitemap_products_N.xml``
index, and the usual ``_shopify_*`` cookies). No JS challenge; plain
``requests`` + the crawler UA returns HTTP 200 on robots, sitemap, and every
product page we've probed. ``FETCHER_TIER`` stays at the default ``"http"``.

Host: ``karcepts.com`` (apex, no ``www`` redirect).

Product URLs: ``https://karcepts.com/products/<handle>``

Discovery: ``/sitemap.xml`` is a standard Shopify sitemap index whose
``sitemap_products_1.xml?from=...&to=...`` child lists every product. The
``?from=&to=`` query must be preserved verbatim when fetching the child
(same behaviour seen on ETS). Override with ``CRAWLER_KARCEPTS_START_URLS``
(comma-separated) for ad-hoc runs. The live catalog is tiny (~31 products
as of 2026-04-21) — one child urlset covers it.

PDP data shape — **JSON-LD is absent**. Karcepts runs Shopify's legacy
"Simple" theme (``Shopify.theme = {"schema_name":"Simple", ...}``) and
emits **no** ``<script type="application/ld+json">`` block at all — not
even a BreadcrumbList / Organization graph. The shared
``extract_json_ld_product`` returns ``None`` on every page. The two real
sources are:

- **Inline ``var meta = {"product":{...},"page":{...}};``** analytics blob
  carrying ``vendor``, ``type``, ``handle``, and every variant's integer
  ``price`` (Shopify cents), ``sku``, and ``name``. This is the
  authoritative SKU source — the HTML itself has no ``sku`` anywhere else
  except inside image filenames.
- **Open Graph product meta** — ``og:title``, ``og:description``,
  ``og:price:amount`` / ``og:price:currency``, and one ``og:image`` per
  product photo (the theme emits multiple ``og:image`` meta tags, already
  upgraded to ``_1200x1200`` resolution — we use those directly rather
  than the thumbnail ``<img src>`` tags in the gallery DOM, which are all
  ``_200x200``). ``og:title`` *is* the product name on this theme
  (unlike Flyin' Miata, where it's the SEO tagline).

Brand rule — **house brand ``"Karcepts"`` is force-applied**. Every SKU
we've observed has ``vendor: "Karcepts"`` in the ``var meta`` blob, even
on co-branded listings like ``"MCS / Karcepts 86 Suspension Package"``
(where the suspension is MCS and Karcepts is the tuner selling the package).
Product titles frequently lead with the target vehicle (``"Karcepts S2000
Rear Hubs"``, ``"Karcepts ND Front Sway Bar Kit"``) so the generic
title-heuristic fallback would otherwise pick ``"Karcepts"`` for most
pages but ``"Honda"`` / ``"Civic"`` / ``"Integra"`` / ``"S2000"`` / ``"ND"``
/ ``"86"`` for any page that opens with the platform name. We guard
against that by coercing anything in the ``_CAR_MAKES_AND_CODES`` blocklist
(plus empty / reject tokens) to the canonical ``"Karcepts"``, and by
collapsing JSON-LD-style ``"Karcepts Inc"`` / ``"Karcepts Performance"``
variants back to the base name.

Variant rule per VARIANTS.md §5 (loss case). Karcepts is a **suspension /
geometry specialist** (sway bars, camber bushings, hubs, subframe
reinforcements, fuel rails). Suspension hardware is one of the axes VARIANTS.md
calls out as functionally distinct: sway-bar kits ship in **spring-rate /
diameter** variants that have different MPNs *and* different effective
behaviour (``KFSB-ND-1.07`` vs ``KFSB-ND-1.13`` vs ``KFSB-ND-1.25`` —
three bar diameters at the same price, genuinely different parts even
though they share a listing). Option packages from MCS ship in damper-
compound variants (``1WNR`` / ``2WNR`` / ``2W`` — one-way non-remote,
two-way non-remote, two-way) with **distinct prices** and empty per-
variant SKUs.

Like every Phase 1 Shopify adapter today (§3), we emit exactly one
``ScrapedPayload`` per URL. The "winning" variant rule is the **first
variant** from the ``var meta`` blob — Shopify's native ordering is the
merchant's picker order, which on Karcepts means the smallest-diameter
bar / lightest damper. Price falls back to the lowest integer variant
price when the first variant itself is priceless (MCS-style packages
where the 1WNR SKU is empty but ``og:price:amount`` carries the floor).
This is the VARIANTS.md §5 loss case: spring rates + bushing compounds
*do* matter for fitment, and a buyer on the 1.25" bar gets the 1.07"
row. Acceptable today, sharpest candidate if we ever implement Option D.

Part-number format: house-brand SKUs use a ``K<prefix>`` shape plus
descriptive suffixes — ``KWHAPR`` (S2000 hubs), ``KFSB-ND-1.07`` (ND
front sway bar, 1.07" diameter), ``KFCB-ND`` (ND front camber bushings),
``KFR01`` (K-series fuel rail). Both forms pass through
``normalize_part_number`` unchanged. Empty SKUs (MCS package variants)
fall through to ``None`` rather than being fabricated from the URL
handle — cross-retailer dedupe falls back to ``retailer + url`` there.

Images: ``og:image`` meta tags are the cleanest source (pre-upgraded to
``_1200x1200``, one per product photo, emitted in display order). DOM
gallery ``<img src>`` tags are all ``_200x200`` thumbnails — unusable as
gallery media. We sweep every ``og:image`` / ``og:image:secure_url`` on
the page, normalize ``//`` → ``https://`` and ``http://`` → ``https://``
(the theme emits one http og:image and one https og:image:secure_url per
photo; both collapse to the same canonical key), strip Shopify size
suffixes so width-variants don't inflate the count, and cap at 12.

Caveats:
- **No JSON-LD at all.** This is the first Shopify adapter to parse
  exclusively from ``var meta`` + og meta. ``scraped_payload_from_json_ld``
  is deliberately not imported — the shared JSON-LD extractor will
  always return ``None`` on this site.
- The analytics blob occasionally lists a variant with ``"sku": ""``
  (observed on the MCS package). We skip empties when choosing the
  authoritative SKU rather than storing the blank string.
- Cookies: first request sets ``_shopify_y`` / ``_shopify_s`` / etc.
  None are required to re-fetch; the crawler session keeps them around
  anyway via ``requests.Session``.
- robots.txt is the standard Shopify boilerplate — nothing under
  ``/products/`` is disallowed.

Tier rationale: Plain Shopify with Cloudflare passive; ``curl`` with a
browser UA returns full HTML + all meta on first try. Tier 0 is correct.
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional
from urllib.parse import urlparse
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

KARCEPTS_BASE = "https://karcepts.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Verified live product URLs used as a fallback when sitemap discovery fails
# and no env override is provided. Picked to cover both single- and multi-
# variant pages so the first crawl exercises both branches.
DEFAULT_START_URLS = [
    "https://karcepts.com/products/karcepts-s2000-rear-hubs",
    "https://karcepts.com/products/karcepts-nd-front-sway-bar-kit",
    "https://karcepts.com/products/karcepts-k-series-fuel-rail",
]

# Canonical house-brand manufacturer. Every SKU in the catalog is first-
# party; cf. module docstring (brand rule).
_KARCEPTS_BRAND = "Karcepts"

# Tokens that the title heuristic sometimes surfaces as "brand" but are
# really the target vehicle make / platform / chassis. Karcepts focuses on
# Honda (S2000, Civic, Integra, K-series swaps) plus a Mazda line (ND
# Miata, 86/BRZ package). Any of these as a "brand" → coerce to "Karcepts"
# so the catalog doesn't grow phantom "Honda"/"Mazda"/"S2000"/"ND" part
# manufacturer rows from our scrape.
_CAR_MAKES_AND_CODES = frozenset(
    {
        "honda",
        "civic",
        "integra",
        "s2000",
        "acura",
        "mazda",
        "miata",
        "mx-5",
        "mx5",
        "nd",
        "nb",
        "na",
        "nc",
        "toyota",
        "subaru",
        "scion",
        "86",
        "brz",
        "frs",
        "fr-s",
        "k-series",
        "kseries",
        "mcs",
    }
)

# Generic words that the first-token title heuristic occasionally picks.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem", "pro", "track"})

# Inline Shopify analytics blob: ``var meta = {"product":{...},"page":{...}};``.
# Anchored on the keyword so a stray ``meta`` substring elsewhere (there
# are many — meta tags, shopify-digital-wallet ids, etc.) can't match.
_META_VAR_RE = re.compile(r"\bvar\s+meta\s*=\s*(\{.*?\})\s*;", re.DOTALL)

# Shopify image URL size suffixes emitted by the Simple theme. ``_200x200``
# (gallery thumbs) / ``_1200x1200`` (og:image upgraded resolution) are
# both observed; strip so width-variants of one asset collapse under one key.
_SHOPIFY_DIMENSION_SUFFIX_RE = re.compile(r"_\d{2,4}x\d{0,4}(?=\.\w{2,5}(?:$|\?))", re.IGNORECASE)

# Image paths that are site chrome rather than product media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on karcepts.com and under ``/products/<slug>``."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "karcepts.com" or host.endswith(".karcepts.com")):
        return False
    path = parsed.path or ""
    if not path.startswith(PRODUCT_PAGE_PATH):
        return False
    trimmed = path[len(PRODUCT_PAGE_PATH) :].strip("/")
    # Require a single non-empty slug segment; no ``/products/`` index or
    # doubled-up ``/products/foo/bar`` paths.
    if not trimmed or "/" in trimmed:
        return False
    return True


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap.xml, then hard-coded default."""
    raw = os.environ.get("CRAWLER_KARCEPTS_START_URLS", "").strip()
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
    Walk ``/sitemap.xml`` → each ``sitemap_products_N.xml`` child urlset and
    collect every ``/products/<handle>`` URL. The child URL's
    ``?from=&to=`` query must be preserved verbatim — stripping it returns
    HTTP 400 on Shopify. Returns a deduplicated list (by URL with the
    *product* query stripped); empty on failure.
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
            if not _is_product_url(base) or base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = KARCEPTS_BASE + "/sitemap.xml"
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
                    # Pass the URL verbatim — the ``?from=&to=`` query is
                    # required by Shopify for these child sitemaps.
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_meta_var_product(html: str) -> Optional[Dict[str, Any]]:
    """
    Pull the ``product`` object from the inline ``var meta = {...};``
    analytics blob. Returns ``None`` when the blob is missing or JSON
    parsing fails.
    """
    match = _META_VAR_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    product = data.get("product")
    return product if isinstance(product, dict) else None


def _first_variant_sku(product: Dict[str, Any]) -> Optional[str]:
    """
    First variant's ``sku`` from the ``var meta`` ``product.variants`` list.
    Skips empty strings (observed on MCS-style package variants where the
    merchant hasn't stamped a SKU per size/damper configuration). Returns
    ``None`` when no variant has a usable SKU.
    """
    variants = product.get("variants")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if not isinstance(v, dict):
            continue
        sku = v.get("sku")
        if isinstance(sku, str) and sku.strip():
            return sku.strip()
    return None


def _first_variant_price_cents(product: Dict[str, Any]) -> Optional[int]:
    """
    First positive variant ``price`` (Shopify emits cents as an integer)
    from ``product.variants``. Used as a fallback when ``og:price:amount``
    is absent or unparseable. Returns ``None`` if no variant has a
    positive int price (draft / call-for-quote listings).
    """
    variants = product.get("variants")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if not isinstance(v, dict):
            continue
        raw = v.get("price")
        if isinstance(raw, int) and raw > 0:
            return raw
    return None


def _vendor(product: Dict[str, Any]) -> Optional[str]:
    """Return the ``vendor`` string from the meta-var product, stripped."""
    vendor = product.get("vendor")
    if isinstance(vendor, str) and vendor.strip():
        return vendor.strip()
    return None


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for a Karcepts product page.

    Because the entire catalog is first-party (house brand), the rule
    collapses almost everything to ``"Karcepts"``:

    - Empty / missing → ``"Karcepts"``.
    - Car make / platform / chassis code in blocklist → ``"Karcepts"``
      (guards against a title like ``"S2000 Rear Hubs"`` leaking
      ``"S2000"`` as the manufacturer name).
    - Generic reject token → ``"Karcepts"``.
    - ``"Karcepts"`` / ``"Karcepts Inc"`` / ``"Karcepts Performance"``
      → collapse to canonical ``"Karcepts"``.
    - Anything else → pass through (defensive: on a hypothetical page
      where Karcepts ever sells a third-party SKU with a populated
      ``vendor``, we'd keep the real manufacturer instead of clobbering
      it — unlikely but cheap to support).
    """
    brand = (part_manufacturer or "").strip()
    if not brand:
        return _KARCEPTS_BRAND
    low = brand.lower()
    if low in _CAR_MAKES_AND_CODES or low in _BRAND_REJECT_TOKENS:
        return _KARCEPTS_BRAND
    if low == "karcepts" or low.startswith("karcepts ") or low.startswith("karcepts-"):
        return _KARCEPTS_BRAND
    return brand


def _normalize_image_url(url: str) -> str:
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against the host."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return KARCEPTS_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify CDN product media (storefront proxy or bare cdn.shopify.com); reject chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _strip_shopify_image_sizing(url: str) -> str:
    """Drop Shopify ``_WxH`` suffixes so width-variants collapse to one gallery entry."""
    return _SHOPIFY_DIMENSION_SUFFIX_RE.sub("", url)


def _canonical_image_key(url: str) -> str:
    """Dedupe key: drop Shopify ``v=`` / ``width=`` params and size suffix."""
    stripped = _strip_shopify_image_sizing(url)
    stripped = re.sub(r"[?&](?:v|width|height)=\w+", "", stripped)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_og_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect every ``og:image`` / ``og:image:secure_url`` meta tag on the
    page, normalized and deduped. The Simple theme emits one pair (http +
    https) per product photo, both upgraded to ``_1200x1200`` — the best
    source for full-res product media on this storefront (gallery ``<img
    src>`` tags are all ``_200x200`` thumbnails). Capped at 12.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        u = _strip_shopify_image_sizing(u)
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    for prop in ("og:image", "og:image:secure_url"):
        for meta in soup.find_all("meta", property=prop):
            if not isinstance(meta, Tag):
                continue
            content = meta_content(meta)
            if content and content.strip():
                add(content.strip())

    return ordered[:12]


def _extract_name(soup: BeautifulSoup, product: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Product name. ``og:title`` is the product name on the Karcepts theme
    (not a tagline, unlike Flyin' Miata) — prefer it. Fall back to the
    ``var meta`` product ``variants[0].name`` and then ``<h1>``.
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            return content.strip()

    if product is not None:
        variants = product.get("variants")
        if isinstance(variants, list):
            for v in variants:
                if not isinstance(v, dict):
                    continue
                name = v.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Description from ``og:description`` → ``<meta name="description">``."""
    for finder in (
        lambda: soup.find("meta", property="og:description"),
        lambda: soup.find("meta", attrs={"name": "description"}),
    ):
        tag = finder()
        if isinstance(tag, Tag):
            content = meta_content(tag)
            if content and content.strip():
                normalized = normalize_description_text(content, max_len=2000)
                if normalized:
                    return normalized
    return None


def _extract_og_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """Price (cents) from ``og:price:amount`` / ``product:price:amount``."""
    for prop in ("og:price:amount", "product:price:amount"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta_content(meta)
            if content:
                cents = parse_price_cents(content)
                if cents is not None:
                    return cents
    return None


class KarceptsAdapter(RetailerCrawlerAdapter):
    """
    Karcepts adapter. Shopify "Simple" theme (no JSON-LD); parsing relies on
    the inline ``var meta = {...}`` analytics blob and Open Graph meta tags.

    Discovery: Shopify sitemap index → ``sitemap_products_N.xml`` children,
    with the ``?from=&to=`` query preserved verbatim. Override via
    ``CRAWLER_KARCEPTS_START_URLS`` (comma-separated).

    Parsing: ``og:title`` / ``og:description`` / ``og:price:amount`` +
    ``var meta`` vendor + variants[0].sku / price. Brand is force-coerced
    to ``"Karcepts"`` (house brand) for empties, car-make / platform / chassis
    codes, and ``"Karcepts <qualifier>"`` variants.

    Variant strategy — VARIANTS.md §5 loss case: suspension hardware with
    spring-rate / bushing-compound axis collapses to the first variant in
    the meta-var ``variants[]`` list. Per-variant SKUs and per-variant
    prices are dropped.
    """

    ADAPTER_NAME: ClassVar[str] = "karcepts"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``sitemap.xml``. Set
        ``CRAWLER_KARCEPTS_START_URLS`` (comma-separated) to override with a
        fixed list. A jittered delay is applied between sitemap-child
        fetches inside ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Karcepts product page.

        Returns ``None`` when the URL isn't product-shaped or when no
        usable name can be extracted. JSON-LD is absent on this storefront;
        this adapter does not call ``extract_json_ld_product``.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        product = _extract_meta_var_product(html)

        name = _extract_name(soup, product)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)

        # Price: prefer og:price:amount (reliable, emitted in dollars on
        # this theme), fall back to the first variant's integer cents in
        # the meta-var blob for products where og:price is missing.
        price_cents = _extract_og_price_cents(soup)
        if price_cents is None and product is not None:
            price_cents = _first_variant_price_cents(product)

        # Part number: first non-empty variant SKU from the meta-var blob.
        # Empty strings (MCS package variants) fall through to None; the
        # ingest pipeline then dedupes on ``retailer + url`` instead of MPN.
        part_number: Optional[str] = None
        if product is not None:
            raw_sku = _first_variant_sku(product)
            if raw_sku:
                part_number = normalize_part_number(raw_sku)

        # Brand: force to "Karcepts" for empty / car-make / platform /
        # chassis / "Karcepts <qualifier>". The ``var meta`` vendor is
        # always "Karcepts" on the live catalog; this path is the
        # belt-and-suspenders guard for future listings.
        vendor_brand = _vendor(product) if product is not None else None
        part_manufacturer = _normalize_part_manufacturer(vendor_brand)

        image_urls = _extract_og_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
