"""
Link Engine Management (linkecu.com / dealers.linkecu.com) crawler adapter.

Platform: **NetSuite SuiteCommerce Advanced (SCA 2024.2.0)** running at the
sub-domain ``dealers.linkecu.com``. The marketing site at ``linkecu.com`` is
WordPress + Yoast and has no product listings of its own — every "Products"
link in the top nav redirects into the SCA storefront. We target the SCA
host exclusively; ``linkecu.com`` is only kept in the host map for archive
replay of old extension-captured pages.

Link is a New Zealand-based **house-brand** standalone ECU manufacturer
(WireIn G5 / G4X + PlugIn ECUs for Subaru, Nissan, Mitsubishi, Toyota, Honda,
BMW, Audi, Mazda, Mini, Holden/GM), plus their own accessories (CAN Lambda,
CAN Keypads, DI Driver, PDM, looms, sensors). **Every SKU is a Link ECU
product** — third-party resales don't appear on this storefront.

Discovery
---------
NetSuite does not publish a product sitemap. The SEO-rendered category
landing pages (``/products/*``) also hide their item list behind the SCA
JS bundle, so scraping the category HTML is a dead end. Instead, discovery
uses the **public SuiteCommerce "cacheable items" JSON API**:

    GET /api/items?c=3994359&n=2&limit=100&offset=0&fieldset=details

The API returns every published item (~260 SKUs at the time of writing)
with ``itemid`` (MPN like ``246-5000``), ``urlcomponent`` (the PDP URL
slug — e.g. ``TB48``, ``G5-Voodoo-Neo-6``), ``displayname``, HTML
description blocks (``storedetaileddescription`` / ``featureddescription``),
gallery image URLs, and ``onlinecustomerprice`` in NZD. Page size is 100;
we walk ``offset`` until fewer than ``limit`` items come back.

Each discovered URL has the shape ``https://dealers.linkecu.com/<urlcomponent>``
(no ``/product/`` prefix — SuiteCommerce keeps PDP slugs at the site root).
Override with ``CRAWLER_LINKECU_START_URLS`` (comma-separated).

Parsing
-------
The PDP HTML carries Schema.org **microdata** (``itemtype="https://schema.org/Product"``)
with ``itemprop="name"``, ``itemprop="sku"``, ``itemprop="description"``,
``itemprop="featdescription"``, and multiple ``itemprop="image"`` tags.
**No JSON-LD ``Product`` is emitted** and ``og:price:standard_amount`` is
rendered as the literal string ``"undefined"`` on the public (non-dealer)
view — the SCA theme hides retail prices in the SEO output even though the
JSON API returns them unauthenticated.

To still produce a useful ``ScrapedPayload`` with price, the adapter keeps a
**module-level item cache** keyed by ``urlcomponent``, populated when
``discover_product_urls()`` runs (and also lazily seeded from the API if the
cache is empty when ``parse_product_page`` is called — this is the
archive-rescrape path, where ``discover`` is skipped). When a cache hit is
available, name / sku / description / price / image come from the API
payload (authoritative). The HTML-microdata fallback runs only when the API
is unreachable or has dropped the SKU since ingest.

Images live under ``/SSP Applications/NetSuite Inc. - SCA 2020.1/Development3/img/<itemid>.<N>.jpg``
(yes, with literal spaces — the API returns them un-encoded, but the Akamai
image server 404s on spaces, so the adapter URL-encodes them before storage).

Brand rule (per VARIANTS.md / Phase 1 playbook)
-----------------------------------------------
**House brand always ``"Link ECU"``.** Titles routinely lead with the
target vehicle ("ECU Plugin G5 Nissan Patrol TB48DE 2017+",
"G4X XtremeX ECU + LS Engine Harness Bundle - Gen3"), so the shared
``part_manufacturer_from_title`` heuristic would otherwise pick the car
make (Nissan / Toyota / Subaru / Mitsubishi / Honda / BMW / Audi / Mazda /
Holden / GM / Ford / Mini) as the brand. The API ``custitem_facet_engine_manufacturer``
field stores exactly those car-make values and must never be used as brand.
Any empty / missing / car-make / "GM" / "LS" / generic-product-word value
coerces to ``"Link ECU"`` — modelled on ADRO's and GrimmSpeed's normalizer.

Variant rule
------------
NetSuite item groups would appear as sibling SKUs in the API list (each
already emitted at its own ``urlcomponent``), so the ``parent-with-variants``
case from VARIANTS.md does not apply here in the ProductGroup sense —
every purchasable SKU has its own URL already (Option B state, naturally).
A small handful of PDPs describe bundles with multiple included items
(e.g. ``XtremeX_Gen4_LS_fusebox_bundle`` — bundle SKU ``109-9025B``);
those are kept as one Part row using the bundle's own SKU and price, same
as every other adapter's bundle handling. No ``ProductGroup`` JSON-LD to
walk.

Tier rationale
--------------
``FETCHER_TIER = "http"``. ``dealers.linkecu.com`` is fronted by
NetSuite's own CDN (not Cloudflare) and the JSON API + SEO HTML both
return 200 to plain ``requests`` with no UA acrobatics. ``linkecu.com``
(marketing) is behind Cloudflare but has no challenge for our UA.
``/robots.txt`` on both hosts is permissive (``Crawl-Delay: 20`` / ``30``);
the runner honors whichever is larger between ``--delay`` and the
directive.

Caveats
-------
- **Multi-currency.** The storefront is NZD-native (``locale.currency = "NZD"``
  in every API response); there is no user-facing currency switcher. We
  ingest NZD prices as-is. Downstream consumers should not assume USD.
- **Dealer login.** The ``Dealer Login`` link gates *dealer* pricing, not
  the catalog. The adapter uses only the public (non-authenticated) API,
  which returns the ``pricelevel1`` / ``onlinecustomerprice`` retail
  figure. If Link ever moves retail prices behind the login, the adapter
  falls back to the HTML (which today has no price), and ``price_cents``
  goes to ``None`` rather than the wrong number.
- **SEO HTML price hole.** ``og:price:standard_amount`` is literally
  ``""`` / ``"undefined"`` on the public PDP — do NOT route it through
  the shared ``extract_dom_price`` helper, which would happily parse
  the empty string to ``None`` (harmless, but also useless). The cache
  is the real source of truth.
- **NetSuite image URLs contain spaces.** ``SSP Applications/NetSuite Inc.
  - SCA 2020.1/Development3/img/…`` — we URL-encode to ``%20`` before
  storage so image-proxy fetches succeed.
- **Marketing-site URLs in archive.** Old extension captures may point at
  ``linkecu.com/products/<slug>/`` rather than ``dealers.linkecu.com/<slug>``.
  Those are marketing pages with no product data; ``parse_product_page``
  returns ``None`` for any URL outside the SCA host.
"""

import html as html_module
import json
import os
import re
from typing import ClassVar, Dict, Iterator, List, Optional
from urllib.parse import quote, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import DEFAULT_USER_AGENT, ScrapedPayload
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
)

LINKECU_BRAND = "Link ECU"
SCA_HOST = "dealers.linkecu.com"
SCA_BASE = "https://dealers.linkecu.com"

# NetSuite tenant/site id (the ``c=`` query param on every SCA request). Baked
# into the live storefront's HTML; hard-coded here because it identifies *this*
# Link storefront and will not drift between crawl runs.
_NS_SITE_ID = "3994359"

# Public "cacheable items" JSON API. ``fieldset=details`` gives us the full
# description/image payload; ``n=2`` is SCA's catalog index for this site.
_ITEMS_API = f"{SCA_BASE}/api/items?c={_NS_SITE_ID}&n=2&fieldset=details&limit=100&offset={{offset}}"

# NetSuite API page size. 100 is the largest the site accepts before silently
# capping; we fetch until fewer items come back than requested.
_API_PAGE_SIZE = 100

# Module-level cache populated by ``discover_product_urls`` and/or
# ``_seed_item_cache`` on first parse. Keyed by urlcomponent (the PDP slug);
# value is the raw NetSuite item dict. Safe to share across runs because the
# runner instantiates a fresh adapter per crawl, and the cache is re-seeded
# from the live API each time discovery walks it.
_ITEM_CACHE: Dict[str, Dict] = {}
_ITEM_CACHE_SEEDED = False

# Car makes & generic tokens that the title heuristic or the API
# ``custitem_facet_engine_manufacturer`` field can surface as "brand" but are
# really the target vehicle. Link's catalog covers every one of these over
# its PlugIn range. Any hit coerces back to ``"Link ECU"``.
_CAR_MAKES = frozenset(
    {
        "nissan",
        "subaru",
        "toyota",
        "mitsubishi",
        "honda",
        "bmw",
        "audi",
        "mazda",
        "mini",
        "holden",
        "gm",
        "general motors",
        "ford",
        "chevrolet",
        "chevy",
        "vw",
        "volkswagen",
    }
)
_BRAND_REJECT_TOKENS = frozenset({"ls", "dbw", "the", "new", "oem", "ecu", "kit", "bundle"})

# NetSuite image URLs include literal spaces in the directory name (e.g.
# ``/SSP Applications/NetSuite Inc. - SCA 2020.1/Development3/img/246-5000.0.jpg``).
# The Akamai edge 404s on unencoded spaces, so we percent-encode them while
# leaving ``/``, ``?``, ``=``, ``&``, ``:`` alone so the URL still parses.
_SAFE_URL_CHARS = "/:?=&%,+"


def _is_sca_host(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == SCA_HOST or host.endswith("." + SCA_HOST)


def _urlcomponent_from_url(url: str) -> Optional[str]:
    """
    Extract the SCA URL slug from a product URL. Returns ``None`` when the
    URL is not on ``dealers.linkecu.com`` or its path is empty / points at a
    category (``/products/...``).
    """
    if not _is_sca_host(url):
        return None
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return None
    # Strip leading/trailing slash, split on /
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return None
    # Category pages are ``/products/<cat>/<subcat>`` — real PDP slugs are
    # a single path segment at the site root.
    if parts[0].lower() == "products":
        return None
    # A PDP slug is always the single path segment. ``.aspx``-style suffixes
    # don't appear on this storefront.
    if len(parts) > 1:
        return None
    return parts[0]


def _encode_netsuite_image_url(url: Optional[str]) -> Optional[str]:
    """Percent-encode spaces (and other unsafe chars) in NetSuite image URLs
    while leaving path/query delimiters alone."""
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = SCA_BASE + u
    # quote with safe list so only the spaces (and similar) get encoded.
    return quote(u, safe=_SAFE_URL_CHARS)


def _fetch_items_page(offset: int) -> Optional[Dict]:
    """Fetch one page of the SCA items API; return the parsed JSON body or
    ``None`` on any transport/parse failure (we fall back to the cached
    default list, so a flake here shouldn't break discovery entirely).

    Bypasses the shared ``fetch_page`` because NetSuite's content negotiation
    rejects its hardcoded ``Accept: text/html,...`` with HTTP 406 on JSON
    endpoints; we send ``Accept: application/json`` instead.
    """
    try:
        resp = requests.get(
            _ITEMS_API.format(offset=offset),
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _walk_items_api() -> List[Dict]:
    """Walk the paginated SuiteCommerce items API and return every item dict.
    Stops when a page returns fewer than ``_API_PAGE_SIZE`` items or on
    any transport failure (returns whatever we have so far)."""
    out: List[Dict] = []
    offset = 0
    while True:
        page = _fetch_items_page(offset)
        if page is None:
            break
        items = page.get("items")
        if not isinstance(items, list) or not items:
            break
        for it in items:
            if isinstance(it, dict):
                out.append(it)
        if len(items) < _API_PAGE_SIZE:
            break
        offset += _API_PAGE_SIZE
        # NetSuite caps listings around ``total`` — stop if we've walked past it
        total = page.get("total")
        if isinstance(total, int) and offset >= total:
            break
    return out


def _seed_item_cache() -> None:
    """Populate ``_ITEM_CACHE`` from the live API if we haven't already this
    process. Safe to call from either ``discover_product_urls`` (normal crawl)
    or ``parse_product_page`` (archive rescrape, where discovery is skipped).
    Silent on failure — callers handle the empty-cache case."""
    global _ITEM_CACHE_SEEDED
    if _ITEM_CACHE_SEEDED:
        return
    for item in _walk_items_api():
        slug = item.get("urlcomponent")
        if isinstance(slug, str) and slug.strip():
            _ITEM_CACHE[slug.strip()] = item
    _ITEM_CACHE_SEEDED = True


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise seed the cache and yield one URL per
    discovered SKU. We keep discovered URLs unchanged even when the cache
    seed fails, because the archive-replay path can still parse microdata
    without the API."""
    raw = os.environ.get("CRAWLER_LINKECU_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    _seed_item_cache()
    return [f"{SCA_BASE}/{slug}" for slug in _ITEM_CACHE.keys()]


def _normalize_part_manufacturer(candidate: Optional[str]) -> str:
    """House brand always wins. Empty / car-make / reject-token / "Link"
    variants all coerce to ``"Link ECU"``."""
    if not candidate:
        return LINKECU_BRAND
    value = candidate.strip()
    if not value:
        return LINKECU_BRAND
    low = value.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return LINKECU_BRAND
    # "Link", "Link ECU", "Link Engine Management", "LinkECU" all canonicalise.
    if re.fullmatch(r"link\s*(engine management|ecu)?", low):
        return LINKECU_BRAND
    return value


def _strip_html(raw: Optional[str]) -> Optional[str]:
    """NetSuite ships descriptions as HTML-in-JSON; strip tags & cap length via
    the shared normalizer so stored descriptions are clean plain text."""
    if not raw:
        return None
    return normalize_description_text(raw, max_len=2000)


def _description_from_item(item: Dict) -> Optional[str]:
    """Prefer the long-form store description; fall back to the shorter
    featured blurb if the detailed field is empty."""
    for key in ("storedetaileddescription", "featureddescription"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            desc = _strip_html(val)
            if desc:
                return desc
    return None


def _images_from_item(item: Dict) -> List[str]:
    """Pull every image URL under ``itemimages_detail.urls``, percent-encode
    spaces, cap at 12."""
    detail = item.get("itemimages_detail")
    if not isinstance(detail, dict):
        return []
    urls = detail.get("urls")
    if not isinstance(urls, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for entry in urls:
        if not isinstance(entry, dict):
            continue
        raw = entry.get("url")
        if not isinstance(raw, str) or not raw.strip():
            continue
        encoded = _encode_netsuite_image_url(raw)
        if not encoded or encoded in seen:
            continue
        seen.add(encoded)
        out.append(encoded)
        if len(out) >= 12:
            break
    return out


def _price_from_item(item: Dict) -> Optional[int]:
    """Pull a price in cents from the API response. Prefer
    ``onlinecustomerprice`` (the public NZD retail figure), fall back to
    ``pricelevel1`` when missing. Returns ``None`` if the price is zero or
    unusable — matches the MAP/dealer-gated handling in ``radium``."""
    detail = item.get("onlinecustomerprice_detail")
    if isinstance(detail, dict):
        raw = detail.get("onlinecustomerprice")
        if isinstance(raw, (int, float)) and raw > 0:
            return int(round(float(raw) * 100))
    for key in ("onlinecustomerprice", "pricelevel1"):
        raw = item.get(key)
        if isinstance(raw, (int, float)) and raw > 0:
            return int(round(float(raw) * 100))
    return None


def _payload_from_api_item(item: Dict, url: str) -> Optional[ScrapedPayload]:
    """Build a ScrapedPayload straight from an SCA API item dict. Returns
    ``None`` when the item has no usable display name (should be rare — every
    SKU in the live catalog has one)."""
    name_raw = item.get("displayname") or item.get("pagetitle") or item.get("storedisplayname2")
    if not isinstance(name_raw, str) or not name_raw.strip():
        return None
    name = html_module.unescape(name_raw.strip())

    itemid = item.get("itemid")
    part_number = normalize_part_number(itemid) if isinstance(itemid, str) else None

    description = _description_from_item(item)
    price_cents = _price_from_item(item)
    images = _images_from_item(item)

    # Brand candidate from the engine-manufacturer facet is almost always a
    # car make; the normalizer drops it to Link ECU. Passing the value in
    # anyway keeps the path consistent with the HTML-fallback branch below.
    brand_candidate = item.get("custitem_facet_engine_manufacturer")
    if isinstance(brand_candidate, str):
        brand_candidate = brand_candidate.replace("&nbsp;", "").strip()
    part_manufacturer = _normalize_part_manufacturer(brand_candidate)

    return ScrapedPayload(
        name=name,
        product_url=url,
        description=description,
        price_cents=price_cents,
        part_manufacturer=part_manufacturer,
        part_number=part_number,
        image_urls=images if images else None,
    )


def _find_main_product_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """Return the outermost ``schema.org/Product`` microdata block. The SCA
    theme also emits ``itemtype=Product`` microdata on every related-item
    card; the main product's scope sits inside ``.product-details``."""
    container = soup.select_one(".product-details")
    if isinstance(container, Tag):
        scope = container.find(attrs={"itemtype": re.compile(r"schema\.org/Product", re.IGNORECASE)})
        if isinstance(scope, Tag):
            return scope
        return container
    scope = soup.find(attrs={"itemtype": re.compile(r"schema\.org/Product", re.IGNORECASE)})
    return scope if isinstance(scope, Tag) else None


def _microdata_value(scope: Tag, prop: str) -> Optional[str]:
    """Find the first ``itemprop="<prop>"`` descendant inside ``scope`` and
    return its content/text. Works for ``<meta>`` (content attr), ``<img>``
    (src attr), ``<a>`` (href attr), and plain text nodes (inner text)."""
    for el in scope.find_all(attrs={"itemprop": prop}):
        if not isinstance(el, Tag):
            continue
        # related-item scopes nest a Product inside; skip values that live
        # inside a nested Product itemscope to avoid mixing parent/child data.
        parent_scope = el.find_parent(attrs={"itemtype": re.compile(r"schema\.org/Product", re.IGNORECASE)})
        if parent_scope is not None and parent_scope is not scope:
            continue
        if el.name == "meta":
            val = el.get("content")
            if isinstance(val, str) and val.strip():
                return val.strip()
        if el.name == "img":
            val = el.get("src")
            if isinstance(val, str) and val.strip():
                return val.strip()
        if el.name == "a":
            val = el.get("href")
            if isinstance(val, str) and val.strip():
                return val.strip()
        text = el.get_text(separator=" ", strip=True)
        if text:
            return text
    return None


def _microdata_all_images(scope: Tag) -> List[str]:
    """Collect every ``itemprop="image"`` src inside the product scope."""
    urls: List[str] = []
    seen: set[str] = set()
    for img in scope.find_all("img", attrs={"itemprop": "image"}):
        if not isinstance(img, Tag):
            continue
        parent_scope = img.find_parent(attrs={"itemtype": re.compile(r"schema\.org/Product", re.IGNORECASE)})
        if parent_scope is not None and parent_scope is not scope:
            continue
        src = img.get("src")
        if not isinstance(src, str) or not src.strip():
            continue
        encoded = _encode_netsuite_image_url(src)
        if not encoded or encoded in seen:
            continue
        seen.add(encoded)
        urls.append(encoded)
        if len(urls) >= 12:
            break
    return urls


def _payload_from_html(html: str, url: str) -> Optional[ScrapedPayload]:
    """Last-ditch fallback when the API cache is empty and a PDP is being
    rescraped from its raw HTML. Pulls name/sku/description/images from
    Schema.org microdata; price is always ``None`` on this storefront's SEO
    HTML (see module docstring). Returns ``None`` when no name is found."""
    soup = BeautifulSoup(html, "html.parser")
    scope = _find_main_product_scope(soup)
    if scope is None:
        # og:title-only fallback for theme drift — still better than nothing.
        og_title = soup.find("meta", property="og:title")
        name = meta_content(og_title) if isinstance(og_title, Tag) else None
        if not name or len(name.strip()) < 2:
            return None
        og_desc = soup.find("meta", property="og:description")
        description = _strip_html(meta_content(og_desc)) if isinstance(og_desc, Tag) else None
        return ScrapedPayload(
            name=name.strip(),
            product_url=url,
            description=description,
            price_cents=None,
            part_manufacturer=LINKECU_BRAND,
            part_number=None,
            image_urls=None,
        )

    name = _microdata_value(scope, "name")
    if not name:
        return None

    sku = _microdata_value(scope, "sku")
    part_number = normalize_part_number(sku) if sku else None

    description_raw = _microdata_value(scope, "description") or _microdata_value(scope, "featdescription")
    description = _strip_html(description_raw) if description_raw else None
    if not description:
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            description = _strip_html(meta_content(og_desc))

    images = _microdata_all_images(scope)
    if not images:
        og_image = soup.find("meta", property="og:image")
        if isinstance(og_image, Tag):
            encoded = _encode_netsuite_image_url(meta_content(og_image))
            if encoded:
                images = [encoded]

    return ScrapedPayload(
        name=name,
        product_url=url,
        description=description,
        price_cents=None,
        part_manufacturer=LINKECU_BRAND,
        part_number=part_number,
        image_urls=images if images else None,
    )


class LinkEcuAdapter(RetailerCrawlerAdapter):
    """
    Link Engine Management adapter. Discovery walks the SCA items JSON API
    and caches each item by ``urlcomponent``; parsing reads from the cache
    when available (API is authoritative — it has the NZD price) and falls
    back to on-page microdata for archive-rescrape of URLs not in the cache.
    """

    ADAPTER_NAME: ClassVar[str] = "linkecu"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield one PDP URL per SuiteCommerce item. Set
        ``CRAWLER_LINKECU_START_URLS`` (comma-separated) to override with a
        fixed list for smoke testing."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse a Link PDP. Prefer the cached SCA API item (price-bearing);
        fall back to HTML microdata when the cache miss is real (archive
        rescrape, or a SKU that's been retired since the last discovery)."""
        if not _is_sca_host(url):
            # Marketing-site URLs (linkecu.com) reach here only via archive
            # replay; none carry product data, so decline rather than invent one.
            return None

        slug = _urlcomponent_from_url(url)
        if slug:
            _seed_item_cache()
            item = _ITEM_CACHE.get(slug)
            if item is not None:
                payload = _payload_from_api_item(item, url)
                if payload is not None:
                    return payload
        # HTML microdata fallback (no price).
        return _payload_from_html(html, url)
