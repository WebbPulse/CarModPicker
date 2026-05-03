"""
Cobb Tuning (cobbtuning.com) crawler adapter — Tier 1 (TLS-impersonating fetcher).

Product URLs: ``https://www.cobbtuning.com/products/<category>/<slug>`` (most
products live under a category), with a smaller set of "featured" SKUs at
``/products/<slug>`` directly. Cobb rebuilt the storefront on top of a Magento 2
frontend themed as a SPA-ish catalog: category pages render a server-side grid
of product anchors, but price / SKU / inventory are hydrated client-side and
do NOT appear in the initial HTML. JSON-LD Product is no longer emitted.

Cobb is behind Cloudflare-style bot protection: plain ``requests.get`` and
``curl`` with a full current-Chrome header set both return 403 against every
path except ``/robots.txt``, while real-browser access from the same network
loads fine. That profile matches Vivid Racing's TLS/JA3 fingerprint block (see
``site_problem_notes/vividracing.md`` and ``cobbtuning.md``), so this adapter
sets ``FETCHER_TIER = "tls"`` to route discovery *and* product fetches through
curl_cffi's Chrome impersonation.

Notes:

- ``/sitemap.xml`` is a Yoast-style index of page/post/brand/category/landing
  sitemaps — none of which list actual products. Discovery walks category pages
  instead: fetch ``/``, collect ``/products/<slug>`` anchors (candidate
  categories + featured products), fetch each, and collect every
  ``/products/*/*`` URL the category grid advertises.
- ``robots.txt`` bans ``/*?`` — any URL with a query string is off limits.
  ``canonicalize_url()`` strips known tracking params; ``_is_product_url``
  drops anything with a remaining query string on top of that.
- The post-migration product pages emit no JSON-LD. ``parse_product_page``
  uses og:title / og:description / og:image / ``<h1>`` to recover the name,
  description, and primary image; price and part number are normally absent
  from the initial HTML (hydrated client-side) and come back as ``None``.
- Cobb's catalog is overwhelmingly their own hardware — AccessPort, SF
  intakes, Stage packages, NexGen exhausts. When no brand is surfaceable and
  no title heuristic fires, the adapter defaults ``part_manufacturer`` to
  ``"COBB Tuning"``; the title-first-word heuristic would otherwise pick up
  product words like "Accessport" or "Stage" and write garbage.
"""

import logging
import os
import re
import time
from typing import ClassVar, Iterator, List, Optional, Set
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

COBBTUNING_BASE = "https://www.cobbtuning.com"

logger = logging.getLogger(__name__)

# Default manufacturer when nothing else surfaces a brand. Cobb's catalog is
# overwhelmingly their own hardware (AccessPort, SF intakes, Stage packages,
# NexGen exhausts), so assigning "COBB Tuning" unconditionally on the fallback
# path is strictly better than the shared title-first-word heuristic, which
# would pick up product words like "Accessport" or "Stage" as a "manufacturer".
_DEFAULT_MANUFACTURER = "COBB Tuning"

# Post-migration product URLs live at ``/products/<category>/<slug>`` (two-level)
# or ``/products/<slug>`` (one-level for featured SKUs). Paths are lowercase
# with hyphens; no trailing ``.html``. This shape guard accepts both depths;
# discovery decides which 1-level URLs are category indexes (fetched and
# expanded) vs direct products.
_PRODUCT_PATH_RE = re.compile(r"^/products/[a-zA-Z0-9][a-zA-Z0-9\-]*(?:/[a-zA-Z0-9][a-zA-Z0-9\-]*)?/?$")

# CMS / account / checkout / informational paths. The ``/products/`` guard
# above already filters most of these out, but we also reject a few legacy
# Magento 2 ``.html`` paths so archive-rescrape doesn't replay them.
_NON_PRODUCT_PATH_RE = re.compile(
    r"^/("
    r"customer|checkout|cart|wishlist|onestepcheckout|catalogsearch|review|"
    r"tag|blog|news|press|events|about|about-us|contact|contact-us|support|"
    r"warranty|dealer|dealers|shipping|returns|terms|privacy|cookie|sitemap|"
    r"rss|store|stores|help|faq|careers|media|legal|tuning-support|"
    r"accessport-support"
    r")(/|$|\.html)",
    re.IGNORECASE,
)

# Pages under /products/ that are NOT products themselves (category or listing
# pages only). ``/products`` (no sub-slug) is the catalog root; these named
# slugs are always categories regardless of whether the URL is 1-level or
# 2-level. We do NOT treat these as products even when discovery surfaces them.
_CATEGORY_ONLY_1LEVEL_SLUGS: frozenset[str] = frozenset()

# Per category page, cap how many product anchors we accept. Cobb's largest
# category (accessport) surfaces ~120 products in one page; 300 gives headroom
# without letting a runaway page list blow up discovery.
_MAX_PRODUCTS_PER_CATEGORY = 300

# Per-discovery cap so a misconfigured / hijacked homepage can't cause unbounded
# crawling. ~1500 is well above the actual catalog size.
_MAX_DISCOVERY_URLS = 1500

# Default candidate categories used when the homepage doesn't surface any.
# Matches the top-level nav on cobbtuning.com as of the WordPress/Magento
# migration. Override via ``CRAWLER_COBBTUNING_START_URLS`` when testing.
_SEED_CATEGORIES: tuple[str, ...] = (
    "/products/accessport",
    "/products/accessport-accessories",
    "/products/air-induction",
    "/products/apparel",
    "/products/brakes",
    "/products/cooling",
    "/products/drivetrain",
    "/products/engine-dress-up",
    "/products/exhaust",
    "/products/exterior",
    "/products/fuel-system",
    "/products/interior",
    "/products/maintenance-items",
    "/products/short-ram-intakes",
    "/products/software",
    "/products/stage-package",
    "/products/suspension",
    "/products/turbo",
    "/products/wheels",
)

# Safe default so a fresh run exercises parsing against a known URL even when
# category discovery comes back empty (e.g. if the homepage layout is changed
# in a way that breaks anchor extraction). Override via
# CRAWLER_COBBTUNING_START_URLS. This flagship SKU is a natural smoke test.
DEFAULT_START_URLS = [
    "https://www.cobbtuning.com/products/accessport/accessport-for-subaru-wrx-sti-2008-2014",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a plausible Cobb Tuning product page URL."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.query:
        # robots.txt disallows /*? — any URL with a query string is off limits.
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "cobbtuning.com" or host.endswith(".cobbtuning.com")):
        return False
    path = (parsed.path or "").rstrip("/")
    if not _PRODUCT_PATH_RE.match(path + "/"):
        # _PRODUCT_PATH_RE accepts an optional trailing slash; normalise here
        # so both ``/products/exhaust`` and ``/products/exhaust/`` match.
        if not _PRODUCT_PATH_RE.match(path):
            return False
    if _NON_PRODUCT_PATH_RE.match(path):
        return False
    # Bare catalog root and known category-only 1-level slugs are filtered
    # regardless of shape match above.
    if path in ("/products", ""):
        return False
    segments = [s for s in path.split("/") if s]
    if len(segments) == 2 and segments[0] == "products" and segments[1].lower() in _CATEGORY_ONLY_1LEVEL_SLUGS:
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_COBBTUNING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_COBBTUNING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_products_href(html: str) -> List[str]:
    """Extract every ``/products/...`` anchor href from an HTML blob, preserving order."""
    hrefs: List[str] = []
    seen: Set[str] = set()
    for m in re.finditer(r'href="([^"#?]+)"', html):
        h = m.group(1)
        # Normalise to an absolute URL on the cobbtuning.com origin.
        if h.startswith("/products/"):
            full = COBBTUNING_BASE + h
        elif h.startswith(COBBTUNING_BASE + "/products/"):
            full = h
        else:
            continue
        # Strip trailing slash for dedupe.
        canon = full.rstrip("/")
        if canon in seen:
            continue
        seen.add(canon)
        hrefs.append(canon)
    return hrefs


# Hostnames used by analytics/tracking pixels that show up in <img src>
# tags — must be excluded from the product image list.
_IMAGE_TRACKER_HOSTS: frozenset[str] = frozenset(
    {
        "facebook.com",
        "www.facebook.com",
        "connect.facebook.net",
        "google-analytics.com",
        "www.google-analytics.com",
        "googletagmanager.com",
        "www.googletagmanager.com",
        "googleadservices.com",
        "doubleclick.net",
        "bat.bing.com",
        "t.co",
        "ct.pinterest.com",
        "analytics.tiktok.com",
    }
)

# Matches the Cobb media filename convention ``<SKU>_main.jpg`` /
# ``<SKU>_main.png`` inside the ``/media/catalog/products/`` path. SKUs are
# 4–16 uppercase alphanumerics; this is specific enough to skip the tracking
# pixels and branding images that also live under /media/.
_IMAGE_SKU_RE = re.compile(
    r"/media/catalog/products/(?:[^/]+/)*([A-Z0-9][A-Z0-9\-_]{2,15})_main\.(?:jpg|jpeg|png|webp)",
    re.IGNORECASE,
)

# Cobb's product names embed the SKU as the trailing parenthesised token —
# every Accessport variant lands in the catalog with its name suffixed
# ``... (AP3-MIT-002)`` / ``... (AP3-AU-SUB-006)``. JSON-LD is gone
# post-migration and the image-filename convention only fires for products
# whose hero image is named after the SKU; this regex picks up the rest.
#
# Shape: opening paren, one upper letter, then upper alphanumeric, then at
# least one ``-``/``_``/``/``-separated alphanumeric segment, closing paren.
# The segment requirement filters chassis-style codes like ``(Mk7)`` /
# ``(8V)`` / ``(B58)`` (no separator) and bare numerics like ``(2024)``,
# while still catching multi-segment SKUs ``(AP3-AU-SUB-006)``.
_NAME_SKU_PARENS_RE = re.compile(
    r"\(([A-Z][A-Z0-9]*(?:[-_/][A-Z0-9]+){1,5})\)"
)


# Generic AccessPort beauty-shot filenames that COBB inlines as marketing
# imagery on a wide set of unrelated category pages (intakes, exhausts,
# stage packages). The hero image often points at one of these — leaking
# the AccessPort glamour shot onto ~417 non-AP3 product rows. We deny these
# UNLESS the page's SKU starts with ``AP3-`` (the AccessPort SKU prefix),
# in which case the beauty shot IS the product photo.
_COBB_ACCESSPORT_IMAGE_RE = re.compile(
    r"accessport_v3_(?:extra|main|subaru|ford|bmw|volkswagen|mazda)",
    re.IGNORECASE,
)


def _is_accessport_marketing_image(url: str, *, page_sku: Optional[str]) -> bool:
    """
    True when ``url`` is one of the generic AccessPort marketing beauty shots
    AND the page's SKU is not part of the AP3 family.
    """
    if not _COBB_ACCESSPORT_IMAGE_RE.search(url):
        return False
    if page_sku and page_sku.upper().startswith("AP3-"):
        return False
    return True


def _extract_dom_images(soup: BeautifulSoup, *, page_sku: Optional[str] = None) -> List[str]:
    """
    Collect product image URLs: og:image first, then <img> tags. Normalizes
    protocol-relative and site-root paths to absolute https URLs. Drops
    analytics/tracking-pixel hosts, plus any cobbtuning.com image that isn't
    under ``/media/catalog/products/`` (site logos, theme icons, etc.).
    Also denies generic AccessPort beauty shots
    (``accessport_v3_(extra|main|subaru|ford|bmw|volkswagen|mazda)``) when the
    page's SKU is NOT in the AP3 family — those marketing photos otherwise
    leak across hundreds of unrelated parts. Capped at 12.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        if not raw or len(urls) >= 12:
            return
        u = raw.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = COBBTUNING_BASE + u
        if not u.startswith("http"):
            return
        if u in seen:
            return
        try:
            parsed = urlparse(u)
            host = (parsed.hostname or "").lower()
        except ValueError:
            return
        if host in _IMAGE_TRACKER_HOSTS:
            return
        # On cobbtuning.com, product images live under /media/catalog/products/;
        # anything else (logos, theme SVGs, favicons) is site chrome and would
        # pollute the ScrapedPayload.image_urls list.
        if host == "cobbtuning.com" or host.endswith(".cobbtuning.com"):
            if "/media/catalog/products/" not in (parsed.path or ""):
                return
        if _is_accessport_marketing_image(u, page_sku=page_sku):
            return
        seen.add(u)
        urls.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img", src=True):
        if not isinstance(img, Tag) or len(urls) >= 12:
            break
        src = img.get("src")
        if isinstance(src, str) and src.strip():
            add(src.strip())
    return urls[:12]


def _extract_sku_from_image_urls(image_urls: List[str]) -> Optional[str]:
    """
    Cobb's catalog images follow ``/media/catalog/products/.../<SKU>_main.ext``
    — a reliable way to recover the SKU when the product page's HTML no longer
    emits JSON-LD (post-migration the price/SKU are hydrated client-side).
    """
    for url in image_urls:
        m = _IMAGE_SKU_RE.search(url)
        if m:
            return m.group(1).upper()
    return None


def _extract_sku_from_name_parens(name: Optional[str]) -> Optional[str]:
    """
    Pull a Cobb SKU out of the trailing parenthesised token in a product name
    (``"... Accessport V3 (AP3-MIT-002)"`` → ``"AP3-MIT-002"``).

    Used as a last-resort SKU recovery after the page-text, sku-class element
    and image-filename paths have all missed. The regex requires at least one
    ``-``/``_``/``/``-separated segment so chassis tokens like ``(Mk7)`` or
    ``(B58)`` and year/displacement parens like ``(2024)`` don't get adopted
    as part numbers.
    """
    if not name:
        return None
    m = _NAME_SKU_PARENS_RE.search(name)
    if not m:
        return None
    return m.group(1)


def _strip_site_prefix(title: str) -> str:
    """
    Strip the ``"COBB Tuning - "`` / ``"COBB Tuning | "`` boilerplate prefix
    from an og:title so the product name isn't dominated by the site name.
    """
    stripped = title.strip()
    for sep in (" - ", " – ", " | ", " : "):
        prefix = "COBB Tuning" + sep
        if stripped.lower().startswith(prefix.lower()):
            return stripped[len(prefix) :].strip()
    return stripped


class CobbTuningAdapter(RetailerCrawlerAdapter):
    """
    Cobb Tuning adapter.

    Fetcher tier: ``tls`` — Cobb returns 403 to plain requests and to curl with
    a full current-Chrome header set, while real browsers from the same network
    load fine. curl_cffi's Chrome TLS impersonation is the first thing to try;
    if Cloudflare also starts issuing a JS challenge, the adapter needs to be
    promoted to the ``browser`` (FlareSolverr) tier.

    Discovery: ``CRAWLER_COBBTUNING_START_URLS`` env var wins. Otherwise we
    walk ``/sitemap.xml`` via ``self.fetcher`` (so requests go through the TLS
    fetcher, not plain ``fetch_page`` which Cloudflare 403s here), collect any
    product-shaped URLs, and fall back to ``DEFAULT_START_URLS`` if discovery
    comes back empty.

    Parsing: JSON-LD Product first (Magento 2 emits schema.org by default),
    then DOM/og fallback. Defaults ``part_manufacturer`` to ``COBB Tuning``
    when nothing else surfaces — most of the catalog is COBB-branded, and the
    title-first-word heuristic otherwise picks product words like
    "Accessport" or "Stage" as manufacturers.
    """

    ADAPTER_NAME: ClassVar[str] = "cobbtuning"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Env override (``CRAWLER_COBBTUNING_START_URLS``)
        wins; otherwise walks the catalog via category pages. Falls back to
        ``DEFAULT_START_URLS`` when discovery fails or returns nothing.
        """
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in self._discover_via_categories() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def _discover_via_categories(self) -> List[str]:
        """
        Walk ``/`` then each ``/products/<category>`` page to collect every
        product-shaped URL the server-rendered catalog grid advertises.

        Returns [] on any failure; the caller decides the fallback. Output is
        deduped and capped at ``_MAX_DISCOVERY_URLS``.
        """
        seen: Set[str] = set()
        products: List[str] = []

        # 1. Pull candidate categories from the homepage. Falls back to the
        #    seed list when the homepage anchor extraction yields nothing —
        #    a homepage layout change shouldn't flatline discovery entirely.
        category_urls: List[str] = []
        try:
            home_html = self.fetcher.fetch(COBBTUNING_BASE + "/", timeout=15)
            for url in _extract_products_href(home_html):
                path = urlparse(url).path.rstrip("/")
                segments = [s for s in path.split("/") if s]
                # 1-level /products/<slug> candidates are treated as categories
                # and expanded. Direct-product 1-level slugs that happen to sit
                # in the homepage get captured in step 3 below.
                if len(segments) == 2 and segments[0] == "products":
                    if url not in seen:
                        seen.add(url)
                        category_urls.append(url)
        except Exception as e:
            logger.warning("cobbtuning: homepage fetch failed: %s", e)

        if not category_urls:
            category_urls = [COBBTUNING_BASE + p for p in _SEED_CATEGORIES]

        # 2. For each category, fetch and collect every 2-level product URL.
        for i, cat_url in enumerate(category_urls):
            if len(products) >= _MAX_DISCOVERY_URLS:
                break
            if i > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                cat_html = self.fetcher.fetch(cat_url, timeout=20)
            except Exception as e:
                logger.warning("cobbtuning: category fetch failed (%s): %s", cat_url, e)
                continue
            added_from_cat = 0
            for href in _extract_products_href(cat_html):
                path = urlparse(href).path.rstrip("/")
                segments = [s for s in path.split("/") if s]
                if len(segments) != 3 or segments[0] != "products":
                    # Skip sub-category links and the "back to /products" root;
                    # only 2-level product URLs are yielded here.
                    continue
                if href in seen:
                    continue
                if not _is_product_url(href):
                    continue
                seen.add(href)
                products.append(href)
                added_from_cat += 1
                if added_from_cat >= _MAX_PRODUCTS_PER_CATEGORY:
                    break
                if len(products) >= _MAX_DISCOVERY_URLS:
                    break

            # 3. If a 1-level URL's page surfaced no 2-level children, it's
            #    almost certainly a direct product page (a featured SKU the
            #    homepage linked to), not a category. Yield the URL itself.
            #    cat_url is already in ``seen`` from step 1 but not in
            #    ``products`` until we add it here.
            if added_from_cat == 0 and _is_product_url(cat_url) and cat_url not in products:
                products.append(cat_url)

        return products

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Cobb Tuning product page. JSON-LD Product first (Magento 2
        emits it by default with name / brand / sku / offers), then a DOM /
        og fallback. Returns None when the URL is not product-shaped or when
        neither JSON-LD nor the DOM yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Magento 2 default SEO output).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                description = payload.description
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = payload.part_manufacturer or _DEFAULT_MANUFACTURER
                # Filter DOM images using the JSON-LD SKU so generic Accessport
                # beauty-shots are denied on non-AP3 SKUs.
                dom_images = _extract_dom_images(soup, page_sku=part_number)
                # JSON-LD image lists are also vulnerable to the same generic
                # accessport_v3_*.jpg leak — apply the deny filter post-hoc.
                jsonld_images = [
                    u
                    for u in (payload.image_urls or [])
                    if not _is_accessport_marketing_image(u, page_sku=part_number)
                ]
                image_urls = jsonld_images or (dom_images[:12] if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback. Prefer the product-heading <h1> (clean name)
        #    over og:title on the new layout, since og:title is uniformly
        #    prefixed with "COBB Tuning - " and the page template also emits
        #    a generic ``<h1 class="page-title">COBB Tuning - Products</h1>``
        #    site header. The product-specific h1 carries
        #    ``class="product--heading"`` — check that first, then fall back
        #    to any h1 whose text isn't obviously the site header.
        name: Optional[str] = None
        product_h1 = soup.find("h1", class_=re.compile(r"product", re.I))
        if isinstance(product_h1, Tag):
            h1_text = product_h1.get_text(strip=True)
            if h1_text and len(h1_text) >= 3:
                name = h1_text
        if not name:
            for h1 in soup.find_all("h1"):
                if not isinstance(h1, Tag):
                    continue
                h1_text = h1.get_text(strip=True)
                if not h1_text or len(h1_text) < 3:
                    continue
                # Skip the generic site-header h1 ("COBB Tuning - Products").
                if h1_text.lower().startswith("cobb tuning"):
                    continue
                name = h1_text
                break
        if not name:
            og_title = soup.find("meta", property="og:title")
            content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
            if content_title and content_title.strip():
                name = _strip_site_prefix(content_title)
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

        # SKU recovery. Order: explicit SKU text on the page → SKU-classed
        # element → Cobb's ``<SKU>_main.jpg`` image filename convention
        # (reliable post-migration since price/SKU are hydrated client-side
        # and the image URL is the only server-rendered carrier) → trailing
        # parenthesised SKU token in the product name (``... (AP3-MIT-002)``)
        # which Cobb uses on every Accessport variant. We skip the
        # title-first-word heuristic entirely — the new h1 tends to start
        # with model-year tokens ("Redline", "Gen2", "Subaru") that produce
        # garbage part numbers.
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if isinstance(sku_elem, Tag):
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            # Image-filename SKU recovery has to happen on the unfiltered DOM
            # images so we can still extract an AP3 SKU when only the generic
            # accessport_v3_main.jpg image is present. Pull a temporary list
            # without the SKU-aware deny filter, mine it for SKUs, then re-run
            # extraction with the recovered SKU to filter properly.
            unfiltered = _extract_dom_images(soup, page_sku="AP3-PROBE")
            image_sku = _extract_sku_from_image_urls(unfiltered)
            if image_sku:
                part_number = normalize_part_number(image_sku)
        if not part_number:
            name_sku = _extract_sku_from_name_parens(str(name))
            if name_sku:
                part_number = normalize_part_number(name_sku)

        # No JSON-LD brand available. Skip the title-first-word heuristic
        # (which picks "Accessport" / "Stage" / "SF" as manufacturers on this
        # catalog) and use the COBB Tuning default directly.
        part_manufacturer = _DEFAULT_MANUFACTURER

        # Filter the gallery using the recovered SKU so AccessPort beauty
        # shots are dropped from non-AP3 product pages but kept for AP3 SKUs.
        dom_images = _extract_dom_images(soup, page_sku=part_number)

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
