"""
aFe Power (afepower.com) crawler adapter.

Platform: **Magento 2** (Adobe Commerce). The response headers, the
``frontend/Ecommerce121/afe`` theme path in every preload ``<link>``, the
``mcprod.afepower.com`` media origin advertised in the CSP, the ``/static/``
and ``/media/`` asset paths, and the stock Magento ``robots.txt`` boilerplate
(``Disallow: /catalog/customer/``, ``/checkout/``, ``/catalogsearch/`` …)
all line up. Served through a **Fastly + Varnish** edge (``x-served-by:
cache-pao…``, ``x-cache: HIT``, ``x-timer`` headers), not Cloudflare — there
is no ``cf-mitigated`` and no JS challenge. Plain ``requests`` with a
desktop UA returns fully-rendered HTML on first try, so ``FETCHER_TIER``
stays at the default ``"http"``.

Hosts: apex ``afepower.com`` (also advertises ``afepowerperformance.com``
in marketing copy but that domain is not used for canonical URLs — the
live catalog lives entirely under ``afepower.com``).

Product URLs: **Magento rewrites at the site root** — every product is
``https://afepower.com/afe-power-<sku-hyphenated>-<slug>`` with no
``.html`` suffix and no ``/catalog/product/view/`` prefix. Example:
``/afe-power-52-12352-c-black-series-cold-air-intake-system``. aFe's SKU
shape is two to three digits, a dash, four to five digits, and an
optional letter suffix (``46-10011``, ``52-12352-C``, ``58-10001R``,
``49c36412``) — the SKU is always encoded into the URL slug.

JSON-LD shape: ``@type: "Product"`` (not ``ProductGroup``). Each PDP
emits **two** Product blocks — one wrapped with aggregateRating + reviews,
one with clean ``offers.price`` — plus a BreadcrumbList. Both Product
blocks carry the same clean ``sku`` (the aFe part number) and ``name``;
the shared ``extract_json_ld_product`` returns whichever matches the
fetched URL via ``@id``. One-Part-per-URL is the correct model here:
every fitment/year/chassis combination has its own SKU and its own
product page (per-variant URLs in VARIANTS.md terms). aFe's "variants"
are actually separate products, so we emit one ``ScrapedPayload`` per
URL and don't need a ProductGroup extractor — option **A** (parent-only)
from ``VARIANTS.md`` applies trivially because there is no parent.

**Brand rule — house brand, always coerce to the canonical form.**
aFe's JSON-LD Product blocks **omit the ``brand`` field entirely** (every
sample page inspected). Without intervention the shared helper returns
``None`` for ``part_manufacturer`` and the title-heuristic fallback trips
on target vehicles — aFe titles like *"BladeRunner Intake Manifold"*
or model-family names (``Magnum FORCE``, ``Momentum``, ``Mach-Force XP``,
``Scorpion``, ``BladeRunner``, ``Pro Dry S``, ``Pro 5R``) have no aFe
token at all. We pass JSON-LD brand through when it's non-empty (so the
rare resold SKU keeps its real manufacturer if aFe ever adds one), and
coerce to the canonical casing ``"aFe Power"`` when missing, empty, a
car make, or any ``afe`` / ``a.f.e.`` variant.

Variant strategy: **one Part per URL** (Option A from ``VARIANTS.md``).
aFe models every fitment as its own SKU on its own URL; there is no
parent/variant picker on PDPs. Nothing to flatten, nothing is lost.

Discovery — **sitemap is hostile.** Every sitemap path we tried
(``/sitemap.xml``, ``/sitemap_index.xml``, ``/pub/media/sitemap.xml``,
``/sitemaps/sitemap_main.xml``) returns **HTTP 200 with content-type
``image/jpeg`` and a 1692-byte JPEG stub** served from Fastly. That's a
deliberate anti-scrape stub — requests for XML feeds are rewritten to a
tiny blank image rather than 404'd, so naive crawlers don't retry. aFe's
``robots.txt`` advertises no sitemap location either. We do **not** try
to fetch any sitemap path; instead we discover via the catalog-search
endpoint ``/catalogsearch/result/?q=<keyword>&p=<page>`` which returns
clean HTML with ``href="https://afepower.com/afe-power-…"`` anchors for
every product in the search result (~72 unique products per page, with
``&p=2``, ``&p=3`` … pagination honored). A short list of high-signal
seed keywords (``intake``, ``exhaust``, ``filter``, ``tuner``, …)
covers the catalog by product family. The walker caps total fetches at
``MAX_FETCHES = 60`` (same belt as ``delicioustuning``) — at 72 products
per page this is still an ~4k-URL ceiling per run, which comfortably
saturates ``--limit`` for most local tests without hammering the origin.

Override ``CRAWLER_AFEPOWER_START_URLS`` (comma-separated) to skip
discovery entirely and feed a fixed list of PDP URLs.

Tier rationale: Plain Magento through Fastly/Varnish with a normal UA.
No TLS fingerprint block (headers show Fastly, not Cloudflare). No JS
challenge. Tier 0 is correct.

Caveats:
* **Catalog scale** — aFe has a very large, fitment-heavy catalog
  (BMW / Mustang / Challenger / Ram / Tacoma / Jeep / every diesel
  truck platform). ``MAX_FETCHES`` caps discovery work per run so a
  default ``python -m app.crawlers --adapter afepower`` doesn't melt.
  Bump the cap via a code change when you want a full sweep, and pair
  with ``--delay 5`` per the "heavy runs" guidance in
  ``crawlers/README.md``.
* **Sitemap JPEG stub** — documented above; if aFe ever fixes the
  rewrite, swap ``_discover_product_urls_via_search`` for the standard
  sitemap walker used by ``mishimoto``.
* **MAP-protected SKUs** — aFe hides the price on some SKUs (MAP
  policy) with the string "cannot show you the price in catalog…". For
  those pages the JSON-LD Product block omits ``offers`` entirely; we
  return ``price_cents=None`` rather than guessing. Name/SKU/images/
  description are still clean.
* **Brand casing** — aFe styles their name as *"aFe Power"* (lowercase
  ``a``). The canonical string stored in the DB matches that exact
  casing; any variant (``AFE POWER``, ``afe``, ``Advanced Flow
  Engineering``) is collapsed to it.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

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

AFEPOWER_BASE = "https://afepower.com"
BRAND_CANONICAL = "aFe Power"

# Verified live product URLs used as a fallback when discovery yields
# nothing and no env override is provided. Picked across the catalog
# (one Porsche intake, one Dodge diesel manifold) so the first crawl
# exercises the JSON-LD path on meaningfully different fitment rows.
DEFAULT_START_URLS = [
    "https://afepower.com/afe-power-52-12352-c-black-series-cold-air-intake-system",
    "https://afepower.com/afe-power-46-10011-bladerunner-intake-manifold",
]

# Search keywords that cover aFe's catalog by product family. The
# ``/catalogsearch/result/?q=<keyword>`` endpoint returns ~72 unique
# product anchors per page (with pagination via ``&p=N``); these seeds
# hit the major verticals aFe sells (intake, exhaust, filters, tuners,
# suspension, cooling) without double-counting too badly. Dedup in the
# walker keeps the final list clean.
_SEARCH_SEED_KEYWORDS: tuple[str, ...] = (
    "intake",
    "exhaust",
    "filter",
    "manifold",
    "tuner",
    "suspension",
    "intercooler",
    "catch can",
)

# Per-seed pagination cap — each search keyword is walked up to this
# many pages deep. Most seeds exhaust well before page 10.
_MAX_PAGES_PER_SEED = 10

# Global hard cap on search/pagination fetches per discovery run. At 72
# products/page this is a ~4k-URL ceiling, well above typical ``--limit``
# values. Raise in code for a full catalog sweep, paired with
# ``--delay 5``. Mirrors the ``MAX_FETCHES`` belt in ``delicioustuning``.
MAX_FETCHES = 60

# Product URL pattern — Magento rewrites a product at the site root as
# ``/afe-power-<sku>-<slug>``. We match that shape exactly during
# discovery so category pages (``/cars/…``, ``/diesel-trucks/…``) and
# CMS slugs don't leak in.
_PRODUCT_URL_RE = re.compile(r"^/afe-power-[a-z0-9][a-z0-9\-]*$", re.IGNORECASE)

# Tokens that sometimes surface as "brand" via the title heuristic but
# are actually the target vehicle make. aFe covers every major make in
# the US market, plus the Euro performance platforms. Any of these →
# coerce to ``"aFe Power"``.
_CAR_MAKES = frozenset(
    {
        "ford",
        "chevrolet",
        "chevy",
        "gmc",
        "dodge",
        "ram",
        "jeep",
        "chrysler",
        "toyota",
        "nissan",
        "honda",
        "subaru",
        "mazda",
        "mitsubishi",
        "bmw",
        "mercedes",
        "audi",
        "porsche",
        "volkswagen",
        "vw",
        "cadillac",
        "lincoln",
        "buick",
        "hyundai",
        "kia",
        "lexus",
        "infiniti",
        "acura",
        "tesla",
        "land",
        "rover",
    }
)

# aFe product-family / generic words that also leak into title-first-word
# heuristics. None of these are real manufacturers.
_GENERIC_TITLE_TOKENS = frozenset(
    {
        "bladerunner",
        "momentum",
        "magnum",
        "mach-force",
        "machforce",
        "scorpion",
        "pro",
        "rapid",
        "twisted",
        "takeda",
        "sprint",
        "pedal",
        "silver",
        "black",
    }
)

# aFe name variants that should collapse to the canonical ``"aFe Power"``.
_AFE_ALIAS_RE = re.compile(
    r"^(afe|a\.f\.e\.?|advanced\s+flow\s+engineering|afe\s+power|afepower)\b",
    re.IGNORECASE,
)

# Magento image-size query params on ``/media/catalog/product/`` URLs.
# Collapsed for dedupe so the 800x600 hero and the 150x113 thumbnail of
# the same photo don't both end up in the gallery.
_IMAGE_SIZE_PARAMS_RE = re.compile(
    r"[?&](?:width|height|canvas|optimize|fit|bg-color)=[^&]*",
    re.IGNORECASE,
)

# Image URLs that aren't product gallery media (site chrome, logos,
# placeholders). Real gallery URLs live under ``/media/catalog/product/``.
_IMAGE_NOISE_RE = re.compile(
    r"placeholder|logo\.|favicon|sprite|/banner_|mega_?menu|/icon[-_]",
    re.IGNORECASE,
)

_MAX_GALLERY_IMAGES = 12


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk catalog search; fall back to DEFAULT_START_URLS."""
    raw = os.environ.get("CRAWLER_AFEPOWER_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_search()
    return urls if urls else list(DEFAULT_START_URLS)


def _looks_like_product_url(url: str) -> bool:
    """
    True if ``url`` is a first-party afepower.com product page
    (``/afe-power-<sku>-<slug>`` at the site root). Rejects category
    pages (``/cars/…``, ``/diesel-trucks/…``), CMS slugs, and anchor
    fragments.
    """
    if not url or "#" in url:
        # We split on '#' in the walker before calling here, but guard
        # anyway so internal callers don't mis-use the helper.
        url = url.split("#", 1)[0]
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host not in {"afepower.com", "www.afepower.com"}:
        return False
    return bool(_PRODUCT_URL_RE.match(parsed.path))


def _search_url(keyword: str, page: int) -> str:
    """Build a Magento catalog-search URL. Page 1 omits ``&p=``; page >= 2 appends it."""
    base = f"{AFEPOWER_BASE}/catalogsearch/result/?q={keyword.replace(' ', '+')}"
    if page <= 1:
        return base
    return f"{base}&p={page}"


def _extract_product_urls_from_listing(html_text: str) -> List[str]:
    """
    Harvest first-party ``/afe-power-…`` product anchors from a search
    result or category listing page. Returns deduplicated list
    (preserving first-seen order), query and fragment stripped.
    """
    seen: set[str] = set()
    ordered: List[str] = []
    # The listing page duplicates each anchor across image / title / review
    # links, so regex is both simpler and faster than a full BS4 walk.
    for match in re.finditer(r'href="(https://(?:www\.)?afepower\.com/[^"#]+)"', html_text, re.IGNORECASE):
        raw = match.group(1).split("#", 1)[0].split("?", 1)[0]
        if not _looks_like_product_url(raw):
            continue
        if raw in seen:
            continue
        seen.add(raw)
        ordered.append(raw)
    return ordered


def _discover_product_urls_via_search() -> List[str]:
    """
    Walk ``/catalogsearch/result/?q=<seed>&p=<page>`` for each seed
    keyword, harvesting product URLs. Caps at ``MAX_FETCHES`` total
    page fetches across all seeds (shared budget) and
    ``_MAX_PAGES_PER_SEED`` depth per seed. A jittered delay is
    applied between every fetch after the first to stay within
    polite-crawler norms on a large catalog walk.

    Returns a deduplicated list (empty on total failure — caller
    falls back to ``DEFAULT_START_URLS``).
    """
    seen_products: set[str] = set()
    product_urls: List[str] = []
    fetched = 0

    for keyword in _SEARCH_SEED_KEYWORDS:
        if fetched >= MAX_FETCHES:
            break
        # Track whether this seed yielded any new products on a given
        # page — if a page returns zero unseen URLs we've exhausted
        # this seed and stop paginating early.
        for page in range(1, _MAX_PAGES_PER_SEED + 1):
            if fetched >= MAX_FETCHES:
                break
            if fetched > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            fetched += 1
            try:
                html_text = fetch_page(_search_url(keyword, page), timeout=20)
            except Exception:
                # A single failed page shouldn't abort the whole walk —
                # advance to the next seed instead.
                break
            page_urls = _extract_product_urls_from_listing(html_text)
            new_on_page = 0
            for u in page_urls:
                if u in seen_products:
                    continue
                seen_products.add(u)
                product_urls.append(u)
                new_on_page += 1
            # Zero new products on this page means we've either hit
            # the end of results for this seed or the same set is
            # echoing — either way, stop paginating this seed.
            if new_on_page == 0:
                break

    return product_urls


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> str:
    """
    House-brand normalisation for aFe Power.

    * Non-empty JSON-LD / title-derived brand that is not a car make,
      not a generic aFe product-family word, and not an aFe alias →
      pass through (reserved for the rare resell SKU — aFe almost
      never carries third-party parts, but we don't want to nuke a
      real third-party brand if they ever do).
    * Any aFe alias (``AFE``, ``afe power``, ``afepower``, ``A.F.E.``,
      ``Advanced Flow Engineering``) → coerce to canonical
      ``"aFe Power"`` with the correct casing.
    * Empty / car make / generic title token → coerce to
      ``"aFe Power"`` (single-brand storefront default).

    ``product_name`` unused today but retained in the signature so
    future title-level overrides don't require a call-site change.
    """
    _ = product_name
    raw = (part_manufacturer or "").strip()
    if not raw:
        return BRAND_CANONICAL
    low = raw.lower()
    if _AFE_ALIAS_RE.match(low):
        return BRAND_CANONICAL
    if low in _CAR_MAKES or low in _GENERIC_TITLE_TOKENS:
        return BRAND_CANONICAL
    return raw


def _normalize_image_url(raw: str) -> Optional[str]:
    """Upgrade protocol-relative / site-root URLs to absolute https. Reject data: / empty."""
    s = (raw or "").strip()
    if not s or s.startswith("data:"):
        return None
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return AFEPOWER_BASE + s
    if s.startswith("http://"):
        return "https://" + s[len("http://") :]
    if not s.startswith("http"):
        return None
    return s


def _is_valid_product_image(url: str) -> bool:
    """Only Magento product media; reject site chrome and placeholders."""
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
    Identity key for an aFe product photo — the ``/media/catalog/product/``
    path with all size query params stripped so the 800x600 hero and
    the 150x113 thumb of the same photo collapse to one bucket.
    """
    base = url.split("?", 1)[0]
    base = _IMAGE_SIZE_PARAMS_RE.sub("", base)
    return base.lower()


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Walk rendered ``<img>`` tags and collect ``/media/catalog/product/``
    URLs, deduped by size-agnostic key and capped at
    ``_MAX_GALLERY_IMAGES``. Drops the Magento ``width/height/canvas``
    query params from the retained URLs so stored images aren't locked
    to the thumbnail dimensions.
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
        # Strip size query params from the stored URL so consumers get
        # the full-resolution Magento asset.
        stripped = _IMAGE_SIZE_PARAMS_RE.sub("", normalized)
        stripped = stripped.replace("?&", "?").rstrip("?&")
        ordered.append(stripped)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content)

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


class AfePowerAdapter(RetailerCrawlerAdapter):
    """
    aFe Power adapter. Magento 2 storefront at ``afepower.com`` served
    via Fastly/Varnish, plain HTTP suffices. Discovery: catalog-search
    walk with pagination — ``/sitemap.xml`` is stubbed with a 1692-byte
    JPEG by Fastly, so we bypass it entirely and use
    ``/catalogsearch/result/?q=<seed>&p=<page>`` instead. Parsing:
    JSON-LD ``Product`` first (every PDP emits it, with clean ``sku``
    and ``offers.price``); DOM/og fallback otherwise. Brand is always
    coerced to ``"aFe Power"`` — the JSON-LD omits the ``brand`` field
    on every page inspected and the title heuristic would otherwise
    pick up car makes or product-family words. Variants: one Part per
    URL (aFe models every fitment as its own SKU).
    """

    ADAPTER_NAME: ClassVar[str] = "afepower"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered via ``/catalogsearch/result/``
        pagination across a set of seed keywords. Set
        ``CRAWLER_AFEPOWER_START_URLS`` (comma-separated) to override
        with a fixed list. Discovery is capped by ``MAX_FETCHES``
        (see module docstring).
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an aFe Power product page into a ``ScrapedPayload``.
        Returns ``None`` when no usable name can be extracted.

        1. JSON-LD ``Product`` (every PDP emits it — name, sku,
           description, offers.price, image). Brand is always forced to
           ``"aFe Power"`` per the module docstring.
        2. DOM / og fallback — h1/og:title, meta description, DOM
           price, SKU via text scan or title candidate. Brand still
           coerced to ``"aFe Power"``.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                # aFe JSON-LD always omits brand; coerce. Left generic
                # so a future third-party resell SKU passes through.
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)

                # JSON-LD image is a single URL; merge DOM gallery so
                # we keep the full product carousel.
                image_urls = list(payload.image_urls or [])
                seen_keys = {_image_dedup_key(u) for u in image_urls}
                for u in dom_images:
                    key = _image_dedup_key(u)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    image_urls.append(u)
                    if len(image_urls) >= _MAX_GALLERY_IMAGES:
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
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = _normalize_part_manufacturer(None, str(name))

        image_urls = dom_images[:_MAX_GALLERY_IMAGES] if dom_images else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=None,
        )
