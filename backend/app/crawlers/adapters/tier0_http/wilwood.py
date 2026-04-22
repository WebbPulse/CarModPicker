"""
Wilwood Disc Brakes (wilwood.com) crawler adapter — Tier 0 (plain HTTP).

Platform: **ASP.NET WebForms / Microsoft-IIS/10.0**. The headers give it away
— ``x-aspnet-version``, ``x-powered-by: ASP.NET``, ``Wilwood_SessionID`` and
``__AntiXsrfToken`` cookies, and product URLs of the shape
``/<Category>/<Thing>Prod.aspx?itemno=<SKU>``. A request to
``/Calipers/CaliperProd.aspx?...`` 302-redirects to the extensionless
``/Calipers/CaliperProd?...`` variant; ``requests`` with ``allow_redirects=True``
(the default in ``fetch_page``) follows it and the final page returns
a fully-rendered ~150 KB HTML document on first try. No Cloudflare, no JS
challenge, no UA block — plain ``requests`` works with either the default
or a browser UA. Tier 0 is the right home.

Host: apex ``wilwood.com`` plus the ``www.wilwood.com`` canonical. Both
serve the same content; the sitemap advertises the ``www.`` form, so that's
what the adapter emits.

Discovery: flat ``/sitemap.xml`` urlset (no sitemap index, ~50K loc
entries, ~2 MB). The sitemap mixes real products with CMS / category /
color-picker / PDF / tech-tip pages; we filter to the catalog's product
page shapes:

- ``/Bearing/BearingProd.aspx``
- ``/BrakeFluid/BrakeFluidProd.aspx``
- ``/BrakeKits/BrakeKitsProdFront.aspx``
- ``/BrakeKits/BrakeKitsProdRear.aspx``
- ``/BrakePads/BrakePadsProd.aspx``
- ``/Calipers/CaliperProd.aspx``
- ``/Hardware/{BoltKit,Bracket,Hardware,ORingKit,Piston}Prod.aspx``
- ``/Hats/HatProd.aspx``
- ``/Hubs/HubProd.aspx``
- ``/LineKits/LineKitsProd.aspx``
- ``/MasterCylinders/MasterCylinderProd.aspx``
- ``/Pedals/PedalProd.aspx``
- ``/Rotors/RotorProd.aspx``
- ``/Spindles/SpindleProd.aspx``

A single regex (``_PRODUCT_PATH_RE``) matches all of them. Every real
product page carries an ``?itemno=<code>`` query — discovery also
requires that to reject pagination / listing pages like
``BrakeKitListFront.aspx?mcat=102``. **No ``/products/`` convention**:
Wilwood is a first-party manufacturer storefront and the entire robots.txt
``Disallow: /products/...`` block refers to *old* ASP pages that no
longer exist at those paths; the live catalog lives under ``/Calipers/``,
``/Rotors/``, etc., none of which are disallowed.

At ~7,200 real product URLs across the catalog the list is large but
very tractable for a Tier 0 crawl. A ``MAX_FETCHES`` cap is not needed
on discovery (the sitemap is a single fetch); the runner's ``--limit`` is
the right lever for a throttled first pass, and ``MAX_DISCOVERED_URLS``
below provides a safety ceiling so a future sitemap explosion can't
accidentally enqueue tens of thousands of URLs in one run.

Product URL shape: ``https://www.wilwood.com/<Category>/<Thing>Prod[Front|Rear]?.aspx?itemno=<SKU>``.
Every URL has a unique ``?itemno=`` query; the canonical form includes the
``.aspx`` extension (the extensionless variant 302s to the same page). The
shared URL canonicalizer preserves ``itemno`` because it's not in
``_TRACKING_PARAMS``.

Override the discovered list with ``CRAWLER_WILWOOD_START_URLS``
(comma-separated) for a fixed smoke-test slice.

JSON-LD shape: every product page emits exactly one JSON-LD
``<script type="application/ld+json">`` block with ``@type: "Product"``
and a nested ``offers: {"@type": "Offer", ...}``. The block is
well-formed schema.org in the lowercase fields we care about (``name``,
``brand``, ``description``, ``image``, ``mpn``, ``url``) but has two
legacy quirks:

1. The offer price is spelled ``"Price"`` (capital P) instead of the
   schema.org canonical ``"price"``. The shared
   ``_price_from_json_ld`` helper only reads lowercase keys, so Wilwood
   would silently produce zero-price Parts if we relied on it. The
   adapter overrides price extraction to accept either case.
2. Custom top-level fields (``"ProductId"``, ``"Category"``,
   ``"gtin12"``, ``"manufacturer"``) live alongside the standard ones.
   We ignore these — ``manufacturer`` duplicates ``brand`` (both say
   ``"Wilwood"``), ``ProductId`` duplicates ``mpn``, and ``Category`` is
   free-form marketing copy (``"Front Brake Kits"``,
   ``"Master Cylinders"``) that doesn't map to our own category table.
   ``gtin12`` is a real UPC; we forward it to ``ScrapedPayload.gtin``.

Parsing: prefer the JSON-LD ``Product`` block via the shared URL-aware
extractor (``extract_json_ld_product``). Fall back to an ``og:title`` /
``<h1>`` sweep if JSON-LD is absent (not observed in the wild — defensive
only). A product-page guard rejects category / advisor pages that the
``_is_product_url`` filter let through by looking for the JSON-LD
Product block plus the ``?itemno=`` query.

Images: Wilwood ships product imagery at multiple sizes under predictable
``/Images/<Section>/..._Photos-{XSmall,Small,Medium,Large,XLarge}/<itemno>-{xs,sm,med,lg,xl}.jpg``
paths. The JSON-LD ``image`` field always points at the large variant. We
forward the JSON-LD image and add the ``-xl`` (XLarge) variant when
present in the page markup as a higher-resolution sibling. Related-product
thumbnails also live under ``/Images/`` and reuse the same path shape; we
restrict the DOM sweep to images whose filename starts with the page's
``itemno=`` value so related-product photos do not leak in. ``og:image``
is not emitted on this storefront and is not used.

Brand rule: Wilwood is a **first-party manufacturer store** — every
product in the catalog is Wilwood-branded (calipers, rotors, pads, master
cylinders, pedal boxes, hubs, spindles, brake fluid, line kits). The
JSON-LD reliably emits ``brand: "Wilwood"``; we pass it through, and when
absent (not observed but defensive) we coerce to ``"Wilwood"``. No
multi-brand reseller behavior to worry about — the "house brand only"
rule applies cleanly.

Variant axis (per VARIANTS.md): **per-PDP** in almost every case. The
sitemap already contains a separate product page per SKU, including
caliper color variants (``120-10000``, ``120-10000-BK``, ``120-10000-RD``
are three distinct URLs with three distinct pages and three distinct
``mpn`` values). Brake pads give each compound its own ``itemno``; rotor
variants differ in hat height, offset, and vane geometry and each get
their own ``itemno``. That matches VARIANTS.md Option B (one Part row per
variant URL) which we already implement today — no ProductGroup extractor
needed.

A small exception: a single caliper PDP may list two or three color
variants in its picker when ``120-10000-BK`` / ``120-10000-RD`` pages
exist, but each color still has its own distinct URL and JSON-LD block.
We ingest each one as a separate Part, which produces N rows sharing a
family prefix — consistent with the rest of the catalog and the
``summitracing`` / ``jegs`` precedent in VARIANTS.md §3.

Tier rationale: plain ``requests`` works end to end — sitemap, robots.txt,
product pages all return 200 with no challenge. IIS/ASP.NET WebForms with
server-rendered HTML means there's nothing to gain from Tier 1 (TLS
impersonation) or Tier 2 (headless browser). The only UA sensitivity is
that ``Python-urllib/3`` also returns 200, so the default crawler UA is
fine.

Caveats:

- **Large catalog.** ~7.2 K product URLs in the sitemap. Running without
  ``--limit`` fetches them all; pair ``--delay 5`` with a full sweep. The
  ``MAX_DISCOVERED_URLS`` ceiling (see below) is a safety belt against
  sitemap explosions, not a per-run budget.
- **Uppercase ``"Price"`` in JSON-LD.** Handled by a local price
  extractor; do not swap the adapter onto the shared helper without
  re-verifying.
- **Capital-letter custom fields.** ``ProductId``, ``Category``,
  ``manufacturer`` exist alongside ``mpn``, (nothing), ``brand``. We
  stick with the lowercase schema.org-native fields.
- **Aggregate landing pages in the sitemap.** ``BrakeKitAdvisor.aspx``,
  ``BrakeKitLanding2.aspx``, ``BrakeKitSearch.aspx``,
  ``BrakeKitListFront.aspx?mcat=N``, ``Calipers/ColorSelect.aspx?id=N``,
  and friends are listed alongside real products. The product-URL filter
  requires both the ``*Prod*.aspx`` shape **and** an ``?itemno=`` query,
  which rejects all of them in one pass.
- **Extensionless 302.** Each ``.aspx`` URL 302-redirects to the
  extensionless variant. ``fetch_page`` follows redirects by default so
  this is invisible. Dedup uses the canonical URL key (query preserved).
- **Robots.txt.** Permits every product URL template we emit. The only
  interesting rules are ``Disallow: /index.aspx/<Cat>/`` (stale
  Google-URL aliases that 404 anyway) and ``Disallow: /products/<...>/``
  (old ASP pages, not the current catalog under ``/Calipers/``,
  ``/Rotors/``, etc.). No ``Crawl-delay`` is declared.
"""

import html as html_lib
import json
import os
import re
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast
from urllib.parse import urljoin, urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_json_ld_product,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

WILWOOD_BASE = "https://www.wilwood.com"
SITEMAP_URL = WILWOOD_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# First-party manufacturer store — every SKU is branded Wilwood.
WILWOOD_BRAND = "Wilwood"

# Defensive seed URLs used when sitemap discovery fails and no env override
# is set. Picked across several catalog sections so the first crawl
# exercises the JSON-LD path on multiple page templates (caliper,
# front/rear brake kit, rotor, master cylinder).
DEFAULT_START_URLS = [
    "https://www.wilwood.com/Calipers/CaliperProd.aspx?itemno=120-10000",
    "https://www.wilwood.com/BrakeKits/BrakeKitsProdFront.aspx?itemno=140-10016",
    "https://www.wilwood.com/Rotors/RotorProd.aspx?itemno=160-0277",
    "https://www.wilwood.com/MasterCylinders/MasterCylinderProd.aspx?itemno=260-10375",
]

# Hard ceiling on URLs yielded per discovery run. Wilwood today exposes
# ~7,200 products; this leaves ~40% headroom for catalog growth without
# forcing a code change, and prevents a future sitemap explosion (or a
# future URL-shape migration that accidentally matches non-products) from
# ballooning the queue. Use the runner's ``--limit`` to clamp actual
# crawl work below this.
MAX_DISCOVERED_URLS = 10_000

# Real product pages live under a ``*Prod*.aspx`` path. We anchor on the
# Category/Thing/Prod* layout so listing pages (``*ListFront.aspx``,
# ``*Landing*.aspx``, ``*Advisor.aspx``, ``ColorSelect.aspx``) are
# rejected in one shot. The trailing ``Front|Rear|{empty}`` allows the
# BrakeKit front/rear split.
_PRODUCT_PATH_RE = re.compile(
    r"^/(?:Bearing|BrakeFluid|BrakeKits|BrakePads|Calipers|Hardware|Hats|Hubs|"
    r"LineKits|MasterCylinders|Pedals|Rotors|Spindles)"
    r"/[A-Za-z]+Prod(?:Front|Rear)?\.aspx$",
    re.IGNORECASE,
)

# Every real product URL carries an ``itemno=<code>`` query. Listing /
# advisor pages use ``mcat=`` or no query at all.
_ITEMNO_QUERY_RE = re.compile(r"(?:^|&)itemno=([A-Za-z0-9][A-Za-z0-9\-]*)", re.IGNORECASE)

# Acceptable image path prefix under ``/Images/`` — all product photos
# live here regardless of section. Filters out data:URIs, external CDNs,
# and navigation chrome.
_PRODUCT_IMAGE_PATH_PART = "/Images/"

# Theme-chrome assets that live under ``/Images/`` but are definitely
# not product imagery.
_NON_PRODUCT_MEDIA_RE = re.compile(
    r"/Promo/|/Category_Images/|/Color(?:Caliper)?Wheel|logo|sprite|favicon|placeholder",
    re.IGNORECASE,
)


def _is_product_url(url: str) -> bool:
    """
    Cheap pre-parse filter: ``url`` is on the Wilwood host, matches the
    ``*Prod*.aspx`` path shape, and carries an ``?itemno=`` query. This
    alone rejects every listing / advisor / color-picker page in the
    sitemap. ``parse_product_page`` remains the final authority via the
    JSON-LD Product guard.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host != "wilwood.com" and host != "www.wilwood.com":
        return False
    if not _PRODUCT_PATH_RE.match(parsed.path or ""):
        return False
    if not _ITEMNO_QUERY_RE.search(parsed.query or ""):
        return False
    return True


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, falling back to the seed list."""
    raw = os.environ.get("CRAWLER_WILWOOD_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch the flat ``/sitemap.xml`` urlset and return every URL that
    passes ``_is_product_url``. Deduplicated by canonical URL
    (``scheme://host/path?itemno=...``) so ``.aspx`` and extensionless
    variants (should they ever both appear) collapse to one entry.
    Capped at ``MAX_DISCOVERED_URLS``. Empty on fetch / parse failure.
    """
    seen: set[str] = set()
    product_urls: List[str] = []
    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=30)
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        u = loc.text.strip()
        if not _is_product_url(u):
            continue
        # Canonical dedupe key — preserve itemno, drop everything else.
        parsed = urlparse(u)
        match = _ITEMNO_QUERY_RE.search(parsed.query or "")
        if not match:
            continue
        key = f"{parsed.scheme.lower()}://{parsed.hostname or ''}{parsed.path}?itemno={match.group(1)}"
        if key in seen:
            continue
        seen.add(key)
        product_urls.append(u)
        if len(product_urls) >= MAX_DISCOVERED_URLS:
            break
    return product_urls


def _is_wilwood_brand(brand: Optional[str]) -> bool:
    """Case/whitespace-insensitive match for ``Wilwood`` (plus ``wilwood engineering``)."""
    if not brand:
        return False
    b = re.sub(r"\s+", "", brand).lower()
    return b in {"wilwood", "wilwoodengineering", "wilwooddiscbrakes"}


def _normalize_brand(raw: Optional[str]) -> str:
    """
    Canonicalize to the ``"Wilwood"`` brand name. Empty / missing /
    variant spellings all coerce; anything else passes through
    unchanged (defensive — no resold SKUs observed, but the guard is
    free).
    """
    if not raw or not raw.strip() or _is_wilwood_brand(raw):
        return WILWOOD_BRAND
    return raw.strip()


def _price_cents_from_offer(offer: Any) -> Optional[int]:
    """
    Extract price in cents from a JSON-LD ``Offer`` dict. Wilwood spells
    the field ``"Price"`` (capital P) rather than the schema.org canonical
    ``"price"``. We try both case variants, then the ``lowPrice`` /
    ``highPrice`` pair in case a future template switches to
    ``AggregateOffer``. Accepts numeric or string values.
    """
    if not isinstance(offer, dict):
        return None
    for key in ("price", "Price", "lowPrice", "LowPrice", "highPrice", "HighPrice"):
        val = offer.get(key)
        if val is None:
            continue
        try:
            num = float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if not (num > 0):
            continue
        return int(round(num * 100))
    return None


def _price_cents_from_json_ld(item: Dict[str, Any]) -> Optional[int]:
    """
    Pull price from the JSON-LD Product's ``offers`` field. Accepts
    either a single Offer dict or a list, and tolerates Wilwood's
    capital-P ``"Price"``.
    """
    offers = item.get("offers") or item.get("Offers")
    if isinstance(offers, list) and offers:
        for offer in offers:
            cents = _price_cents_from_offer(offer)
            if cents is not None:
                return cents
        return None
    return _price_cents_from_offer(offers)


def _images_from_json_ld(item: Dict[str, Any]) -> List[str]:
    """Collect image URLs from the JSON-LD ``image`` field (str, list, or object)."""
    img = item.get("image")
    if not img:
        return []
    urls: List[str] = []
    for entry in ([img] if isinstance(img, str) else img):
        if isinstance(entry, str) and entry.strip():
            urls.append(entry.strip())
        elif isinstance(entry, dict):
            u = entry.get("url")
            if isinstance(u, str) and u.strip():
                urls.append(u.strip())
    return urls


def _gtin_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """
    Wilwood emits ``gtin12`` (the 12-digit UPC) on every product. Fall
    back to any other gtin-shaped field for defensiveness.
    """
    for key in ("gtin12", "gtin13", "gtin14", "gtin8", "gtin"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _itemno_from_url(url: str) -> Optional[str]:
    """
    Return the ``?itemno=`` value from a Wilwood product URL, or None
    when absent / malformed.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    match = _ITEMNO_QUERY_RE.search(parsed.query or "")
    return match.group(1) if match else None


def _canonical_image_url(src: str, page_url: str) -> Optional[str]:
    """
    Normalize a Wilwood image URL. Accepts relative (``/Images/...``),
    protocol-relative (``//www.wilwood.com/...``), and absolute URLs.
    Returns a full ``https://www.wilwood.com/Images/...`` form, or
    ``None`` when the URL doesn't point at product media.
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = urljoin(page_url, s)
    if not s.lower().startswith("http"):
        return None
    try:
        parsed = urlparse(s)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host and "wilwood.com" not in host:
        return None
    if _PRODUCT_IMAGE_PATH_PART not in parsed.path:
        return None
    if _NON_PRODUCT_MEDIA_RE.search(parsed.path):
        return None
    if not re.search(r"\.(?:jpe?g|png|webp)$", parsed.path, re.IGNORECASE):
        return None
    return s


def _extract_extra_images(html: str, page_url: str, itemno: str) -> List[str]:
    """
    Sweep the product page HTML for additional ``/Images/.../<itemno>*.jpg``
    references. Restricts to files whose basename starts with the page's
    ``itemno`` so related-product thumbnails (which live under the same
    ``/Images/`` tree) don't leak in.
    """
    if not itemno:
        return []
    # Escape the itemno for regex (it may contain dashes — safe, but be
    # explicit).
    itemno_escaped = re.escape(itemno)
    # Image references — both relative and absolute, with any size suffix.
    # Excludes dimension diagrams (those don't start with the itemno).
    pattern = re.compile(
        rf"(?:https?:)?(?://[^\"' >]+?)?(/Images/[^\"' >]+?{itemno_escaped}[^\"' >]*?\.(?:jpe?g|png|webp))",
        re.IGNORECASE,
    )
    found: List[str] = []
    for match in pattern.finditer(html):
        raw = match.group(0)
        canonical = _canonical_image_url(raw, page_url)
        if canonical:
            found.append(canonical)
    return found


def _dedupe_keep_order(urls: List[str], cap: int = 12) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= cap:
            break
    return out


def _build_payload_from_json_ld(
    item: Dict[str, Any],
    html: str,
    url: str,
) -> Optional[ScrapedPayload]:
    """
    Turn a Wilwood JSON-LD ``Product`` dict into a ``ScrapedPayload``.
    Returns ``None`` when the block is missing its ``name`` (defensive —
    not observed).
    """
    name_val = item.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None
    name = html_lib.unescape(name)

    desc_val = item.get("description")
    description: Optional[str] = None
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    brand_raw: Optional[str] = None
    brand_field = item.get("brand")
    if isinstance(brand_field, str):
        brand_raw = brand_field
    elif isinstance(brand_field, dict):
        brand_name = brand_field.get("name")
        if isinstance(brand_name, str):
            brand_raw = brand_name
    # ``manufacturer`` is a non-schema-org mirror of ``brand`` on Wilwood
    # pages; use it only if ``brand`` is missing/empty.
    if not brand_raw:
        man = item.get("manufacturer")
        if isinstance(man, str):
            brand_raw = man
        elif isinstance(man, dict):
            man_name = man.get("name")
            if isinstance(man_name, str):
                brand_raw = man_name
    brand = _normalize_brand(brand_raw)

    sku_val = item.get("mpn") or item.get("sku") or item.get("ProductId")
    part_number: Optional[str] = None
    if isinstance(sku_val, str) and sku_val.strip():
        part_number = normalize_part_number(sku_val)
    # Fall back to the URL's itemno — on Wilwood this is always the MPN.
    if not part_number:
        itemno = _itemno_from_url(url)
        if itemno:
            part_number = normalize_part_number(itemno)

    price_cents = _price_cents_from_json_ld(item)
    gtin = _gtin_from_json_ld(item)

    itemno_for_images = _itemno_from_url(url) or (part_number or "")
    images: List[str] = []
    for raw in _images_from_json_ld(item):
        canonical = _canonical_image_url(raw, url)
        if canonical:
            images.append(canonical)
    images.extend(_extract_extra_images(html, url, itemno_for_images))
    image_urls = _dedupe_keep_order(images, cap=12)

    return ScrapedPayload(
        name=name,
        product_url=url,
        description=description,
        price_cents=price_cents,
        part_manufacturer=brand,
        part_number=part_number,
        image_urls=image_urls if image_urls else None,
        gtin=gtin,
    )


def _json_ld_product_items(html: str) -> List[Dict[str, Any]]:
    """
    Raw enumerate of every ``Product`` JSON-LD item on the page. Wilwood
    emits exactly one but we iterate defensively.
    """
    out: List[Dict[str, Any]] = []
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items: List[Any] = []
        if isinstance(data, list):
            items = list(data)
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                items = list(graph)
            else:
                items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                out.append(cast(Dict[str, Any], item))
    return out


def _is_product_page(html: str, url: str) -> bool:
    """
    A Wilwood product page has both the ``?itemno=`` query in its URL
    and a JSON-LD ``Product`` block. Missing either → not a product.
    """
    if not _itemno_from_url(url):
        return False
    return bool(_json_ld_product_items(html))


def _fallback_payload_from_dom(html: str, url: str) -> Optional[ScrapedPayload]:
    """
    Defensive fallback when JSON-LD is absent (not observed in
    production). Pulls name from ``<h1>`` or ``og:title``, uses the URL's
    itemno as the part number, leaves price and description empty.
    """
    soup = BeautifulSoup(html, "html.parser")
    name: Optional[str] = None
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            name = content.strip()
    if not name:
        h1 = soup.find("h1")
        if isinstance(h1, Tag):
            text = h1.get_text(strip=True)
            if text:
                name = text
    if not name or len(name) < 3:
        return None

    itemno = _itemno_from_url(url)
    part_number = normalize_part_number(itemno) if itemno else None

    # Try DOM price as a last resort. ``parse_price_cents`` finds the first
    # ``$...`` in body text; acceptable since we only reach this path when
    # JSON-LD is missing entirely.
    body_text = soup.get_text(" ", strip=True)
    match = re.search(r"\$[\s,]?\d+\.?\d*", body_text)
    price_cents = parse_price_cents(match.group(0)) if match else None

    return ScrapedPayload(
        name=name,
        product_url=url,
        description=None,
        price_cents=price_cents,
        part_manufacturer=WILWOOD_BRAND,
        part_number=part_number,
        image_urls=None,
        gtin=None,
    )


class WilwoodAdapter(RetailerCrawlerAdapter):
    """
    Wilwood Disc Brakes adapter. Discovery: flat ``/sitemap.xml`` urlset →
    ``_is_product_url`` filter on the Category/Thing/Prod*.aspx shape with
    a required ``?itemno=`` query. Parsing: JSON-LD ``Product`` block →
    local price extractor for the uppercase-``"Price"`` quirk → image
    sweep restricted to ``/Images/.../<itemno>...`` paths. Brand is always
    ``"Wilwood"`` (single-brand manufacturer store).
    """

    ADAPTER_NAME: ClassVar[str] = "wilwood"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Wilwood product page. Returns ``None`` for listing /
        advisor / CMS pages (no ``?itemno=`` or no JSON-LD Product).
        """
        if not _is_product_page(html, url):
            return None

        # Prefer the URL-aware extractor — it correctly rejects JSON-LD
        # Products whose declared ``url`` disagrees with the page URL. On
        # Wilwood the declared URL always matches, but the guard is free.
        item = extract_json_ld_product(html, product_url=url)
        if item is not None:
            payload = _build_payload_from_json_ld(item, html, url)
            if payload is not None:
                return payload

        # Extremely defensive path — Wilwood has not been observed without
        # JSON-LD, but if a template changes we still want a best-effort
        # row rather than dropping the URL silently.
        return _fallback_payload_from_dom(html, url)
