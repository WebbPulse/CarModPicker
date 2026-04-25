"""
English Racing (englishracing.net) crawler adapter — Tier 0 (plain HTTP).

Platform: **Shopify** (legacy storefront; no JSON-LD, old-style theme). The
primary domain is ``englishracing.net`` — the ``.com`` apex currently resolves
to a Verizon residential IP on ``siteamerica.com`` hosting (151.202.18.39) that
does not answer on ports 80/443, so live crawls go to ``englishracing.net``.
We keep ``englishracing.com`` in the host list for archive replay only (in
case the apex is ever restored). The Shopify internal host
``englishracing.myshopify.com`` 301s to ``englishracing.net`` with
``x-redirect-reason: primary_domain_redirection``.

English Racing is a Mitsubishi Evo / DSM / Subaru specialist that sells a
mix of **house-brand** hardware (Speed Density intakes, EVO 8/9 short blocks,
4G63 crate motors, rebuilt transmissions, etc. — ``vendor = "English Racing"``)
and **third-party resale** (GSC Power-Division billet camshafts, Fuel
Injector Clinic / FIC high-impedance injectors, AEM, Tomei, Cobb, and other
DSM/Evo-community staples). The resale brand set overlaps substantially with
Road Race Engineering / Buschur Racing; the vendor field on this store is
the authoritative source of truth for whose part the listing is.

Discovery: ``/sitemap.xml`` is a standard Shopify sitemap index pointing at
``sitemap_products_1.xml?from=<id>&to=<id>`` plus the usual pages /
collections / blogs siblings. **The ``?from=&to=`` query must be preserved**
when fetching the child sitemap — stripping it returns HTTP 400 on Shopify
(same gotcha that bit the ETS adapter). Override with
``CRAWLER_ENGLISHRACING_START_URLS`` (comma-separated) for ad-hoc runs.

Parse shape — no JSON-LD. We worked out the path the hard way:

- The PDP emits **schema.org microdata** (``itemtype="http://schema.org/Product"``)
  with ``itemprop`` children for ``name``, ``description`` (full HTML body),
  ``image``, ``offers``, ``price``, ``priceCurrency``, ``availability``.
  Microdata is our source for name, price, image, description.
- **Brand (vendor) and SKU** are not in microdata. They live in an inline
  ``var meta = {"product": {"vendor": "...", "variants": [{"sku": "..."}, ...]}};``
  JSON blob that every PDP ships. We parse that single-line regex-addressable
  blob for vendor + ``variants[0].sku`` — same "first variant wins" contract
  every other Shopify adapter uses (see ``VARIANTS.md`` §3).
- Open-graph meta (``og:title``, ``og:description``, ``og:price:amount``,
  ``og:image``) is populated on every page and is our fallback when
  microdata is damaged by a theme change.

Brand rule — **multi-brand reseller**, pass-through semantics (same as
``ind.py`` / ``grimmspeed.py``'s non-house path):

- ``vendor`` from the inline Shopify meta, when non-empty and not a car make
  or reject token, **passes through unchanged**. "GSC Power-Division",
  "Fuel Injector Clinic", "AEM", "Tomei", "Cobb", etc. keep their identity
  so the global part-manufacturer list stays clean and cross-retailer dedupe
  on MPN keeps working.
- Empty, blank-whitespace, ``unknown``, ``n/a`` → coerce to canonical
  ``"English Racing"`` (house brand) only as a last resort.
- **Car-make / chassis / platform blocklist** (Mitsubishi, Subaru, Evo, DSM,
  Eclipse, Lancer, Impreza, WRX, STI, plus the broader site-agnostic car
  makes) → drop the value and fall through to the title heuristic / house-
  brand coercion. The vendor field has never been observed as a car make on
  this storefront in practice, but the guard is free and consistent with the
  Phase 1 reseller-adapter playbook.

SKU format: House-brand SKUs use ``ER_`` prefixes (``ER_SD_Intake-1``,
``ER_2.0L_Crate-7``). Third-party SKUs are the manufacturer's native
identifier (``GSC7008S2``, ``IS126-1000H-1`` for FIC). Both pass through
``normalize_part_number`` unchanged. Variant pages collapse to ``variants[0]``
per the project-wide "one Part per URL" rule — documented in
``VARIANTS.md``. Multi-variant configurations on this store are common
(the Speed Density intake has 54 variants across inlet size × finish ×
outlet size), so the first-variant SKU is representative but not complete.

Image gallery: microdata ``image`` is a single ``<meta>`` for the hero shot.
We merge that with the Shopify theme ``.product-images`` /
``.product__media-wrapper`` / ``.product-gallery`` DOM scan and dedupe on
Shopify CDN asset stem (dropping width/height/v/crop query params) so the
full carousel lands on the payload. Thumbnail-sized variants
(``_100x100.jpg``, ``_300x300.jpg``, ``_compact.jpg``, etc.) are rejected so
we keep full-resolution images.

Tier rationale: No Cloudflare challenge, no TLS fingerprint block. Plain
``requests`` returns fully-rendered HTML on the first try (tested against
a house-brand product, a GSC third-party product, and a FIC injector set).
``FETCHER_TIER`` stays at the default ``"http"``.

Caveats:

- The ``englishracing.com`` apex does not resolve to a working web server at
  the time of adapter authoring. All live discovery + product fetches use
  ``englishracing.net``. If the ``.com`` apex is ever restored, the adapter's
  host match already accepts it so archive rescrape / extension capture will
  route here without changes.
- Legacy theme: no JSON-LD. If Shopify ever backfills JSON-LD on this store
  the shared ``scraped_payload_from_json_ld`` path will start returning data
  and the microdata branch becomes dead code — delete the microdata branch
  at that point, don't stack both.
- Variant coverage is first-variant only (see ``VARIANTS.md``). The Speed
  Density intake's 54 SKUs collapse to ``ER_SD_Intake-1``; the FIC 1000cc
  injector set's 3 SKUs collapse to ``IS126-1000H-1``. Consumers who need a
  specific variant must still click through.
- The sitemap products child URL ships with ``?from=&to=`` query string;
  stripping it returns HTTP 400 (Shopify-wide behaviour).
"""

import html as html_mod
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

ENGLISHRACING_BASE = "https://englishracing.net"
SITEMAP_INDEX_URL = ENGLISHRACING_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
PRODUCT_PAGE_PATH = "/products/"

# Canonical house-brand form. Used only when vendor is missing / blocklisted.
_HOUSE_BRAND_CANONICAL = "English Racing"

# Variant spellings of the house brand that we collapse onto the canonical form.
_HOUSE_BRAND_VARIANTS = frozenset(
    {
        "english racing",
        "englishracing",
        "english-racing",
        "english racing performance",
    }
)

# Car makes / chassis / platform / model tokens that are sometimes surfaced as
# "brand" by naive title heuristics on a Mitsubishi-specialist storefront. The
# vendor field on English Racing has not been observed holding these values,
# but the guard is free and keeps the adapter consistent with the Phase 1
# reseller-adapter playbook (ind.py / corksport.py). A hit here drops the
# value and falls through to the house-brand coercion, so the global
# part-manufacturer list does not grow a phantom "Mitsubishi" row.
_CAR_MAKE_AND_PLATFORM_BLOCKLIST = frozenset(
    {
        # Mitsubishi Evo / DSM / Eclipse / Lancer platform (primary)
        "mitsubishi",
        "mitsu",
        "evo",
        "evolution",
        "dsm",
        "eclipse",
        "lancer",
        "4g63",
        "4g64",
        "mivec",
        # Subaru / EJ / FA platform (secondary)
        "subaru",
        "impreza",
        "wrx",
        "sti",
        "ej20",
        "ej25",
        # Broader car-make guard — observed on sibling Phase 1 adapters
        "toyota",
        "scion",
        "honda",
        "nissan",
        "mazda",
        "ford",
        "chevrolet",
        "chevy",
        "porsche",
        "bmw",
        "audi",
        "vw",
        "volkswagen",
    }
)

# Tokens that sometimes slip through from a vendor string but are not a real
# brand (blank-ish markers set by Shopify stores with a misconfigured catalog).
_BRAND_REJECT_TOKENS = frozenset(
    {
        "unknown",
        "n/a",
        "na",
        "none",
        "null",
        "default",
        "misc",
        "miscellaneous",
        "vendor",
    }
)

# Matches the inline ``var meta = { ... };`` blob that Shopify's legacy theme
# emits on every PDP. Non-greedy so we stop at the first closing brace + semi.
# The blob is single-line and contains the product's vendor + variants[0].sku.
_SHOPIFY_META_RE = re.compile(r"var\s+meta\s*=\s*(\{.*?\})\s*;", re.DOTALL)

# Matches storefront CDN image URLs (both ``cdn.shopify.com`` and the
# storefront proxy at ``englishracing.net/cdn/shop/``).
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg, file_100x100.webp,
# file_compact.jpg). Rejected so we prefer full-resolution gallery media.
# ``_grande`` (largest standard named size) and ``_large`` (fallback when no
# bigger asset is uploaded) are *kept* — this store's OG meta always uses
# ``_grande`` for the hero shot, and rejecting it leaves the payload with no
# images at all.
_SHOPIFY_THUMBNAIL_RE = re.compile(
    r"_(?:\d{2,4}x\d{2,4}|compact|small|medium|icon|thumb)\.\w{2,5}(?:$|\?)",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """
    Env override wins; otherwise discover via ``/sitemap.xml``; otherwise fall
    back to a verified pair of PDPs that exercises both the house-brand path
    and the multi-brand reseller path.
    """
    raw = os.environ.get("CRAWLER_ENGLISHRACING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    if urls:
        return urls
    return [
        "https://englishracing.net/products/english-racing-speed-density-intake-kit",
        "https://englishracing.net/products/gsc-power-division-billet-evolution-4-9-camshafts",
    ]


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` child sitemap."""
    return "/sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → each ``sitemap_products_N.xml``
    child urlset and collect every ``/products/<handle>`` URL. Skips
    ``sitemap_pages_*`` / ``sitemap_collections_*`` / ``sitemap_blogs_*``
    siblings — none host product pages. The child sitemap URL ships with a
    ``?from=&to=`` query string and **must be fetched with it intact**
    (stripping it returns HTTP 400 on Shopify). Returns a deduplicated list
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
            # Shopify sometimes includes the site root as a <loc> in the
            # products sitemap — skip anything without a slug.
            try:
                parsed = urlparse(u)
            except ValueError:
                continue
            if not parsed.path.startswith(PRODUCT_PAGE_PATH) or parsed.path == PRODUCT_PAGE_PATH:
                continue
            base = u.split("?", 1)[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_text = fetch_page(SITEMAP_INDEX_URL, timeout=15)
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


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is an English Racing product page — on ``englishracing.net``
    (primary) or ``englishracing.com`` (kept for archive replay) with a
    non-empty ``/products/<handle>`` path.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (
        host == "englishracing.net"
        or host.endswith(".englishracing.net")
        or host == "englishracing.com"
        or host.endswith(".englishracing.com")
    ):
        return False
    path = parsed.path or ""
    if not path.startswith(PRODUCT_PAGE_PATH):
        return False
    handle = path[len(PRODUCT_PAGE_PATH) :].strip("/")
    return bool(handle)


def _normalize_part_manufacturer(vendor: Optional[str]) -> Optional[str]:
    """
    Apply the multi-brand reseller brand rule.

    - Empty / whitespace-only → ``None`` (caller coerces to house brand).
    - Car-make / chassis / platform blocklist → ``None``.
    - Reject-token blocklist (``"unknown"``, ``"n/a"``, …) → ``None``.
    - House-brand variants (``"English Racing"``, ``"EnglishRacing"``, …) →
      canonical ``"English Racing"``.
    - Everything else → passed through, trimmed, unchanged. This is how
      "GSC Power-Division", "Fuel Injector Clinic", "AEM", "Tomei", "Cobb",
      and the long tail of DSM/Evo-community third-party manufacturers keep
      their real identity.
    """
    if not vendor:
        return None
    brand = vendor.strip()
    if not brand:
        return None
    low = brand.lower()
    if low in _HOUSE_BRAND_VARIANTS:
        return _HOUSE_BRAND_CANONICAL
    if low in _CAR_MAKE_AND_PLATFORM_BLOCKLIST:
        return None
    if low in _BRAND_REJECT_TOKENS:
        return None
    return brand


def _extract_shopify_meta(html: str) -> Dict[str, Any]:
    """
    Pull the inline ``var meta = {...};`` JSON blob and return the nested
    ``product`` dict (vendor, id, type, handle, variants[]). Returns an empty
    dict when the blob is missing or unparseable so callers can fall through
    to the microdata + OG path without branching on None.
    """
    m = _SHOPIFY_META_RE.search(html)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}
    product = data.get("product") if isinstance(data, dict) else None
    return product if isinstance(product, dict) else {}


def _first_variant_sku(product_meta: Dict[str, Any]) -> Optional[str]:
    """
    Return the ``sku`` from ``variants[0]`` of the Shopify meta blob.
    Multi-variant products collapse to the first variant per the project-wide
    ``one Part per URL`` contract (see ``VARIANTS.md``). Handles both the
    ``variants: [...]`` array shape and the legacy single-variant inline shape.
    """
    variants = product_meta.get("variants")
    if isinstance(variants, list) and variants:
        first = variants[0]
        if isinstance(first, dict):
            sku = first.get("sku")
            if isinstance(sku, str) and sku.strip():
                return sku.strip()
    # Fallback: some themes put sku on the product dict directly.
    sku = product_meta.get("sku")
    if isinstance(sku, str) and sku.strip():
        return sku.strip()
    return None


def _extract_microdata_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull ``name`` from the schema.org Product microdata scope. Falls back to
    the OG title and then to the first ``<h1>`` so damaged microdata doesn't
    leave the payload nameless.
    """
    scope = soup.find(
        attrs={
            "itemtype": lambda v: isinstance(v, str) and "schema.org/Product" in v,
        }
    )
    if isinstance(scope, Tag):
        name_el = scope.find(attrs={"itemprop": "name"})
        if isinstance(name_el, Tag):
            content = name_el.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            text = name_el.get_text(" ", strip=True)
            if text:
                return text

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            return content.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(" ", strip=True)
        if text:
            return text
    return None


def _extract_microdata_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull the full description from the ``itemprop="description"`` block (the
    Shopify product body copy lives there as HTML). Falls back to the OG
    description / meta description when microdata is absent. Caller is
    responsible for ``normalize_description_text``.
    """
    desc_el = soup.find(attrs={"itemprop": "description"})
    if isinstance(desc_el, Tag):
        # Descriptions are HTML-rich (tables, <em>, inline styles). Get text
        # with separator so paragraph structure is preserved for the helper.
        text = desc_el.get_text(" ", strip=True)
        if text and len(text) >= 20:
            return text

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        content = meta_content(og_desc)
        if content and content.strip():
            return content.strip()

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        content = meta_content(meta_desc)
        if content and content.strip():
            return content.strip()
    return None


def _extract_price_cents(soup: BeautifulSoup, product_meta: Dict[str, Any]) -> Optional[int]:
    """
    Resolve price in cents. Preference order:

    1. Shopify meta ``variants[0].price`` — already in cents, authoritative.
    2. ``og:price:amount`` meta content (dollars, Shopify populates this
       reliably on every PDP).
    3. ``itemprop="price"`` microdata content / text.
    """
    variants = product_meta.get("variants")
    if isinstance(variants, list) and variants:
        first = variants[0]
        if isinstance(first, dict):
            raw_price = first.get("price")
            # Shopify stores price in cents as an int for recent objects, but
            # older themes sometimes emit a float/dollar value — sniff.
            if isinstance(raw_price, int) and raw_price > 0:
                return raw_price
            if isinstance(raw_price, float) and raw_price > 0:
                # Float here is almost always a dollar amount (Shopify stringly-
                # typed a currency). Round to cents.
                return int(round(raw_price * 100))
            if isinstance(raw_price, str) and raw_price.strip():
                cents = parse_price_cents(raw_price)
                if cents is not None:
                    return cents

    og_price = soup.find("meta", property="og:price:amount")
    if isinstance(og_price, Tag):
        content = meta_content(og_price)
        if content:
            cents = parse_price_cents(content)
            if cents is not None:
                return cents

    price_el = soup.find(attrs={"itemprop": "price"})
    if isinstance(price_el, Tag):
        content = price_el.get("content")
        if isinstance(content, str) and content.strip():
            cents = parse_price_cents(content)
            if cents is not None:
                return cents
        text = price_el.get_text(" ", strip=True)
        if text:
            cents = parse_price_cents(text)
            if cents is not None:
                return cents
    return None


def _normalize_image_url(raw: str) -> Optional[str]:
    """Upgrade scheme-relative / http URLs to https; reject empties."""
    s = raw.strip()
    if not s:
        return None
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("http://"):
        return "https://" + s[len("http://") :]
    if s.startswith("/"):
        return ENGLISHRACING_BASE + s
    if not s.startswith("http"):
        return None
    return s


def _is_valid_product_image(url: str) -> bool:
    """Accept only Shopify CDN product media; reject chrome and thumbnails."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    # englishracing.net's storefront proxy and cdn.shopify.com are both valid.
    if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    if _SHOPIFY_THUMBNAIL_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """
    Collapse ``?v=…`` / ``?width=…`` / ``?height=…`` / ``?crop=…`` variants
    of the same underlying Shopify asset onto one key.
    """
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_image_urls(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs. Order of preference:

    1. ``itemprop="image"`` microdata meta (hero shot).
    2. All ``og:image`` / ``og:image:secure_url`` meta tags (Shopify emits
       one per gallery photo on this theme).
    3. DOM gallery scan inside ``.product-images`` / ``.product__media-wrapper``
       / ``.product-gallery`` / ``.product-single__media`` (legacy theme
       variants) as a belt-and-suspenders step.

    Deduped on canonical asset key, capped at 12.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or not _is_valid_product_image(normalized):
            return
        key = _canonical_image_key(normalized)
        if key in seen:
            return
        seen.add(key)
        ordered.append(normalized)

    # 1. microdata hero image.
    hero = soup.find(attrs={"itemprop": "image"})
    if isinstance(hero, Tag):
        content = hero.get("content")
        if isinstance(content, str) and content.strip():
            add(content.strip())
        src = hero.get("src")
        if isinstance(src, str) and src.strip():
            add(src.strip())

    # 2. All OG images (Shopify emits one per gallery photo on this theme).
    for og_key in ("og:image:secure_url", "og:image"):
        for meta in soup.find_all("meta", property=og_key):
            if not isinstance(meta, Tag):
                continue
            content = meta_content(meta)
            if content and content.strip():
                add(content.strip())

    # 3. DOM gallery scan.
    scope: Optional[Tag] = None
    for selector in (
        ".product-images",
        ".product__media-wrapper",
        ".product-gallery",
        ".product-single__media",
    ):
        candidate = soup.select_one(selector)
        if isinstance(candidate, Tag):
            scope = candidate
            break

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            for attr in ("src", "data-src", "data-original", "data-srcset"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    first = val.strip().split(",")[0].strip().split(" ")[0]
                    if first:
                        add(first)
                        break

    return ordered[:12]


class EnglishRacingAdapter(RetailerCrawlerAdapter):
    """
    English Racing adapter. Shopify storefront on ``englishracing.net`` (the
    ``.com`` apex is dead at adapter-authoring time; kept in the host match
    for archive replay only). Plain HTTP — no Cloudflare challenge, no
    TLS-fingerprint block.

    Discovery: Shopify ``/sitemap.xml`` index → ``sitemap_products_N.xml``
    child (fetched with ``?from=&to=`` query intact) → ``/products/<handle>``
    URLs, deduped on path.

    Parsing: the store emits **no JSON-LD**. We read schema.org microdata
    for name / description / price / image, the inline
    ``var meta = {"product": {...}};`` blob for vendor + first-variant SKU,
    and OG meta as fallback. Brand is passed through unchanged when the
    vendor is a real manufacturer (GSC Power-Division, Fuel Injector Clinic,
    AEM, Tomei, Cobb, …); only empty / car-make / reject-token vendors get
    coerced to the canonical ``"English Racing"`` house brand.

    Multi-variant pages collapse to the first variant per the project-wide
    ``one Part per URL`` contract (see ``VARIANTS.md``).
    """

    ADAPTER_NAME: ClassVar[str] = "englishracing"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``sitemap.xml`` (products child
        only). ``CRAWLER_ENGLISHRACING_START_URLS`` (comma-separated)
        overrides with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an English Racing PDP. Returns ``None`` when the URL isn't a
        product page or when no name can be extracted (category page, 404,
        etc.).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        product_meta = _extract_shopify_meta(html)

        name = _extract_microdata_name(soup)
        if not name or len(name) < 3:
            return None
        name = html_mod.unescape(name)

        description_raw = _extract_microdata_description(soup)
        description = normalize_description_text(description_raw, max_len=2000) if description_raw else None

        price_cents = _extract_price_cents(soup, product_meta)

        # --- Brand resolution ---------------------------------------------------
        # Vendor from the Shopify meta blob is the authoritative source on this
        # store. Pass-through for real manufacturers; coerce to house brand only
        # as a last resort.
        vendor_raw = product_meta.get("vendor") if isinstance(product_meta, dict) else None
        if isinstance(vendor_raw, str):
            part_manufacturer = _normalize_part_manufacturer(vendor_raw)
        else:
            part_manufacturer = None
        if not part_manufacturer:
            # Title-level house-brand signal (rare; vendor is reliable on this
            # store). "English Racing ..." titles on a missing-vendor page.
            if name.lower().startswith("english racing") or name.lower().startswith("er "):
                part_manufacturer = _HOUSE_BRAND_CANONICAL
        if not part_manufacturer:
            part_manufacturer = _HOUSE_BRAND_CANONICAL

        # --- SKU ---------------------------------------------------------------
        sku = _first_variant_sku(product_meta) if product_meta else None
        part_number = normalize_part_number(sku) if sku else None

        image_urls = _extract_image_urls(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
