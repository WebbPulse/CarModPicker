"""
Skunk2 Racing (skunk2.com) crawler adapter.

Iconic Honda / Acura performance brand (camshafts, intake manifolds, coilovers,
throttle bodies, intercoolers, headers). Direct-to-consumer Magento 2 storefront
— evidence: ``/media/catalog/product/cache/<hash>/`` image paths,
``/catalogsearch/result/`` search URLs, standard Magento ``customer/account``
forms. No Cloudflare / WAF interstitial; plain ``requests`` HTTP works fine, so
this is a **Tier 0 (``"http"``) adapter**.

Product URLs: primarily ``https://www.skunk2.com/shop/<slug>.html`` (as linked
from category pages like ``/shop/engine.html``). The same SKU pages also answer
under the slug at the site root (``https://www.skunk2.com/<slug>.html``) because
Magento URL rewrites expose both, so the adapter accepts either shape.

Discovery is the hard part on this site:

- There is no XML sitemap at ``/sitemap.xml``, ``/sitemap_index.xml``,
  ``/pub/sitemap.xml``, ``/catalog/seo_sitemap/product/``, or the Magento
  default ``/media/sitemaps/sitemap.xml``. Every common path returns 404 (or
  redirects to an empty search results page).
- ``/robots.txt`` exists but is a blanket ``Disallow: /`` for every user-agent.
  Our polite runner (``can_fetch_url`` in ``base.py``) honors this, so in
  practice **every product fetch will be skipped** when the crawler is pointed
  at this adapter without intervention. This adapter is therefore primarily
  useful for:
    1. Parsing Chrome-extension-captured pages (``POST /crawled-pages/scrape``)
       where the user's browser already performed the fetch.
    2. Archive rescrape runs against previously-captured HTML.
    3. Explicit operator opt-in via ``CRAWLER_SKUNK2_START_URLS`` on an
       environment where robots.txt enforcement has been relaxed for a short
       authorized window.

For the discovery path we nonetheless implement a category walker: fetch the
``/shop.html`` landing page, collect first-party links that look like product
pages (``/shop/<slug>.html`` or ``/<slug>.html`` ending in a recognisable
SKU-shaped segment), with a polite inter-request delay. Subcategory pages like
``/shop/engine.html`` are also crawled one level deep. The walker stays on host
and filters out cart / account / CMS URLs.

Parsing:

- **No JSON-LD Product block** is emitted — the Magento theme here ships
  without the SEO JSON-LD module (verified against multiple product pages
  2026-04-20). ``extract_json_ld_product`` is still called first as a cheap
  guard in case the site enables it later, but the DOM path is the real
  worker.
- DOM extraction: ``<h1>`` for name, ``"PN: <sku>"`` / ``itemprop="sku"`` style
  text for part number (fallback: extract from image filenames — Skunk2 stores
  each product's SKU in its ``/media/catalog/product/*/<sku>_N.jpg`` asset
  name, which is a reliable signal), ``$N,NNN.NN`` regex for price,
  ``/media/catalog/product/cache/<hash>/...`` gallery images (Magento cache
  variants are deduped on the un-cached key).

Brand canonicalization:

- The site's own product labelling consistently uses ``"Skunk2"`` (the full
  corporate name is "Skunk2 Racing", used in the ``<title>`` chrome and the
  ``@skunk2racing`` social handle, but on-product the brand is simply
  ``Skunk2``). We pick ``"Skunk2"`` as the canonical form so the global
  part-manufacturer table stays consistent with how they market themselves on
  the part itself.
- Because product H1s like ``"Intercooler Kit - 2016-2021 Honda Civic 1.5T"``
  or ``"Pro ST Coilovers - '06-'11 Civic"`` lead with the product type, the
  generic title heuristic would pick up ``Honda`` / ``Acura`` (car makes) or
  common product words as the manufacturer. All of those are coerced to the
  canonical ``"Skunk2"``. Third-party brands are not expected here — every SKU
  on skunk2.com is manufactured by Skunk2.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urljoin, urlparse
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

SKUNK2_BASE = "https://www.skunk2.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
BRAND_CANONICAL = "Skunk2"

# Seed category pages that the discovery walker pulls product links from.
# ``/shop.html`` is the root "all products" page (advertises 661 items in
# 2026-04-20 recon); the top-level category pages below are linked from the
# shop header and give a deep, predictable frontier without needing pagination
# handling.
_CATEGORY_SEED_PATHS = (
    "/shop.html",
    "/shop/engine.html",
    "/shop/induction.html",
    "/shop/exhaust-headers.html",
    "/shop/cooling.html",
    "/shop/suspension.html",
    "/shop/drivetrain.html",
    "/shop/fuel-delivery.html",
    "/shop/hardware.html",
)

# Default product URLs used only when both env override and category-walk
# discovery fail. These are verified live product pages as of 2026-04-20.
DEFAULT_START_URLS = [
    "https://www.skunk2.com/shop/pro-st-coilover-2006-2011-civic-541-05-8750.html",
    "https://www.skunk2.com/shop/intercooler-kit-2016-2021-honda-civic-1-5t.html",
]

# Slug tokens that are emphatically not product pages. Matched as substrings
# against the full URL path.
_NON_PRODUCT_SLUGS = (
    "/customer/",
    "/checkout",
    "/cart",
    "/wishlist",
    "/catalogsearch/",
    "/account",
    "/contact",
    "/about",
    "/blog",
    "/news",
    "/privacy",
    "/terms",
    "/warranty",
    "/dealer",
    "/careers",
    "/team-skunk2",
    "/stay-in-the-loop",
)

# Shop landing pages and category index pages share the ``/shop/*.html`` path
# shape with product detail pages. To keep them out of the product frontier we
# maintain a small deny-list of category slugs; anything else ending in
# ``.html`` under ``/shop/`` (or at the site root) is treated as a product.
_CATEGORY_PRODUCT_BLACKLIST = frozenset(
    {
        "shop",
        "engine",
        "induction",
        "exhaust-headers",
        "cooling",
        "suspension",
        "drivetrain",
        "fuel-delivery",
        "hardware",
        "apparel",
        "accessories",
        "coilovers",
        "springs",
        "camshafts",
        "intake-manifolds",
        "throttle-bodies",
        "headers",
        "exhaust-systems",
        "intercoolers",
        "radiators",
        "oil-pans",
        "oil-coolers",
        "valve-covers",
        "valvetrain",
    }
)

# Skunk2 SKUs are three-dash-separated groups of digits, e.g. 305-05-7010,
# 541-05-8750, 345-05-0100. Useful both for extracting the part number from
# page text / URL slug / image filenames and for recognising product URLs.
_SKU_PATTERN = re.compile(r"\b(\d{3}-\d{2}-\d{3,4})\b")

# Magento cache-hash segment in image URLs
# (``/media/catalog/product/cache/6bad69a7.../3/0/305-05-7010_1.jpg``).
_MAGENTO_CACHE_SEGMENT_RE = re.compile(r"/cache/[a-f0-9]+/", re.IGNORECASE)

# Site-chrome image patterns we refuse to store as product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"/logo|logo\.|favicon|placeholder|sprite|icon[-_]|/banner|banner[-_]|/cms/",
    re.IGNORECASE,
)

# Car makes that Skunk2 builds for. When the generic title-first-word heuristic
# picks one of these, it's a false positive (Skunk2 H1s lead with the product
# type, e.g. "Intercooler Kit - 2016-2021 Honda Civic 1.5T") — coerce to the
# canonical house brand.
_CAR_MAKE_BRANDS = frozenset({"honda", "acura"})

# Every plausible spelling / casing of the house brand collapses to the
# canonical ``"Skunk2"``. ``"Skunk2 Racing"`` is the corporate name used in the
# page ``<title>`` and social handles, but the product brand on every SKU is
# simply ``"Skunk2"`` — keeping one row in the global part-manufacturer table
# means manual edits in the app apply to the whole catalog.
_SKUNK2_BRAND_VARIANTS = frozenset(
    {
        "skunk2",
        "skunk 2",
        "skunk-2",
        "skunk2 racing",
        "skunk 2 racing",
        "skunk-2 racing",
        "skunk2 alpha",
        "skunk2 racing alpha",
        "group a engineering",  # parent LLC; sometimes in scraped footers
    }
)


def _is_skunk2_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of Skunk2's own brand-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _SKUNK2_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Collapse brand variants and car-make false positives to the canonical
    ``"Skunk2"``. Third-party brands (exceptionally rare on this site) pass
    through unchanged so ``get_or_create_part_manufacturer_by_name`` can route
    them to the correct global row.
    """
    brand = (part_manufacturer or "").strip()
    if not brand:
        return BRAND_CANONICAL
    if _is_skunk2_brand_variant(brand):
        return BRAND_CANONICAL
    if brand.lower() in _CAR_MAKE_BRANDS:
        return BRAND_CANONICAL
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk ``/shop.html`` + categories, fall back to defaults."""
    raw = os.environ.get("CRAWLER_SKUNK2_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    if urls:
        return urls
    return _discover_product_urls_via_categories()


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Try the handful of sitemap paths a Magento 2 install might expose. Skunk2
    did not serve a usable sitemap at any of them as of 2026-04-20, but we
    still probe — if the site enables the Magento SEO sitemap module later,
    discovery will pick it up automatically with no code change.

    Returns the deduplicated list of product URLs on success, or an empty
    list if every candidate fails.
    """
    candidates = (
        f"{SKUNK2_BASE}/sitemap.xml",
        f"{SKUNK2_BASE}/pub/sitemap.xml",
        f"{SKUNK2_BASE}/media/sitemaps/sitemap.xml",
        f"{SKUNK2_BASE}/sitemap_index.xml",
    )

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
            if not _looks_like_product_url(u):
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    for candidate in candidates:
        try:
            text = fetch_page(candidate, timeout=15)
        except Exception:
            continue
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            continue
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_urls):
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                try:
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
            if product_urls:
                return product_urls
        else:
            parse_urlset_locs(text)
            if product_urls:
                return product_urls

    return []


def _discover_product_urls_via_categories() -> List[str]:
    """
    Fallback discovery: walk the known seed category pages and collect links
    that look like product detail URLs. Applies a polite inter-request delay
    between category fetches (the runner handles delays between product
    fetches downstream). Returns ``DEFAULT_START_URLS`` if every seed fails.
    """
    seen: set[str] = set()
    product_urls: List[str] = []

    for i, path in enumerate(_CATEGORY_SEED_PATHS):
        if i > 0:
            time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
        try:
            html_text = fetch_page(SKUNK2_BASE + path, timeout=20)
        except Exception:
            continue
        for link in _extract_product_links(html_text):
            if link in seen:
                continue
            seen.add(link)
            product_urls.append(link)

    return product_urls if product_urls else list(DEFAULT_START_URLS)


def _extract_product_links(html_text: str) -> List[str]:
    """
    Pull first-party product links out of a Skunk2 category / landing page.
    Yields URLs in document order. Skips category / CMS pages by slug allowlist
    and by the shared ``_looks_like_product_url`` check.
    """
    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception:
        return []

    hits: List[str] = []
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str) or not href.strip():
            continue
        absolute = urljoin(SKUNK2_BASE, href.strip())
        if not _same_host(absolute):
            continue
        if not _looks_like_product_url(absolute):
            continue
        base = absolute.split("?")[0].split("#")[0]
        hits.append(base)
    return hits


def _same_host(url: str) -> bool:
    """True when ``url`` is on skunk2.com (with or without ``www``)."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return host == "skunk2.com" or host == "www.skunk2.com"


def _looks_like_product_url(url: str) -> bool:
    """
    Product pages end in ``.html`` and sit under ``/shop/<slug>.html`` or at
    the site root as ``/<slug>.html``. Deny-list filters out CMS pages and
    category index pages that share the ``.html`` shape.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    path = (parsed.path or "").lower()
    if not path.endswith(".html"):
        return False
    # Magento index/CMS handles never look like products.
    if any(bad in path for bad in _NON_PRODUCT_SLUGS):
        return False
    # Strip leading /shop/ so both URL shapes share the same tail test.
    tail = path
    if tail.startswith("/shop/"):
        tail = tail[len("/shop/") :]
    else:
        tail = tail.lstrip("/")
    # Reject category index pages (``engine.html``, ``shop/suspension/coilovers.html``
    # — anything whose slug is on the category blacklist or contains a sub-path).
    slug = tail[: -len(".html")] if tail.endswith(".html") else tail
    # Nested category like ``suspension/coilovers.html``
    if "/" in slug:
        return False
    if slug in _CATEGORY_PRODUCT_BLACKLIST:
        return False
    # Product slugs are always descriptive (typically 15+ chars, including the
    # SKU suffix); raise the bar a bit to filter drive-by CMS pages.
    return len(slug) >= 8


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against the site."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return SKUNK2_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Magento product media; reject site chrome and data-URIs."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/media/catalog/product/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """
    Collapse Magento cache-hash variants so the same physical asset rendered
    at several cache keys (``/cache/6bad.../``, ``/cache/98fb.../``, …) dedupes
    down to one entry in the final gallery.
    """
    return _MAGENTO_CACHE_SEGMENT_RE.sub("/", url.strip())


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery images from ``/media/catalog/product/`` paths.
    Deduped on the cache-hash-stripped key so repeated cache-variant renders of
    the same photo count once. Capped at 12 to match the ingest contract.

    We intentionally do not try ``og:image`` here — this storefront doesn't
    emit og meta, so falling back to it would only ever pick up the site logo.
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

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src", "data-original", "data-lazy"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break

    return ordered[:12]


def _extract_sku_from_images(image_urls: List[str]) -> Optional[str]:
    """
    Skunk2 stores every product's SKU in its image filename
    (``/cache/<hash>/3/0/305-05-7010_1.jpg``). When the in-page
    ``PN: <sku>`` text is missing or hidden behind a script-rendered block,
    the first image URL that matches ``NNN-NN-NNN(N)`` is a reliable signal —
    and it's the same SKU the visible PN label would show.
    """
    for url in image_urls:
        match = _SKU_PATTERN.search(url)
        if match:
            return match.group(1)
    return None


def _extract_sku_from_url(url: str) -> Optional[str]:
    """
    Many Skunk2 product slugs suffix the SKU (e.g.
    ``pro-st-coilover-2006-2011-civic-541-05-8750.html``). When neither page
    text nor image filenames yield a SKU, mine it from the URL.
    """
    match = _SKU_PATTERN.search(url)
    return match.group(1) if match else None


class Skunk2Adapter(RetailerCrawlerAdapter):
    """
    Skunk2 Racing adapter. Magento 2 storefront, plain HTTP fetch is enough
    (no Cloudflare on the front door as of 2026-04-20), so ``FETCHER_TIER``
    stays at the default ``"http"``.

    Discovery: ``CRAWLER_SKUNK2_START_URLS`` env var wins. Otherwise probes
    the common Magento sitemap paths (all 404 at time of writing but we try
    anyway so this adapter self-heals if the site ever publishes a sitemap),
    then falls back to a category-page walker rooted at ``/shop.html`` plus
    the top-level engine / induction / suspension / … index pages.

    Parsing: no JSON-LD Product block on this theme, so the adapter runs the
    DOM path directly — ``<h1>`` for name, ``PN:`` text + URL slug + image
    filename as layered SKU sources, ``$...`` regex for price, Magento
    ``/media/catalog/product/...`` URLs for the gallery. Manufacturer is
    always coerced to the canonical ``"Skunk2"`` (the on-product brand label),
    rescuing the car-make false positive the generic title heuristic would
    otherwise produce on titles like
    ``"Intercooler Kit - 2016-2021 Honda Civic 1.5T"``.

    Note on robots.txt: Skunk2 serves a blanket ``Disallow: /`` to all
    user-agents. The shared crawler runner respects this, so in a standard
    run every URL will be skipped. This adapter is therefore most useful for
    parsing extension-captured pages and archive rescrapes; operators can
    opt into an active crawl by setting ``CRAWLER_SKUNK2_START_URLS`` in an
    authorized window.
    """

    ADAPTER_NAME: ClassVar[str] = "skunk2"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from env override, sitemap probe, or category walker."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Skunk2 product page. JSON-LD is tried first as a no-op guard
        (the theme doesn't emit it today, but if that changes the shared
        helper will pick it up for free); on any miss the DOM fallback is
        authoritative. Returns ``None`` when the URL is not product-shaped
        or when neither path yields a usable name.
        """
        if not _looks_like_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (currently absent on this theme; cheap guard).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                if not part_number:
                    part_number = _extract_sku_from_images(dom_images) or _extract_sku_from_url(url)
                    part_number = normalize_part_number(part_number) if part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM fallback (the real parser on this site).
        name: Optional[str] = None
        h1 = soup.find("h1")
        if isinstance(h1, Tag):
            h1_text = h1.get_text(strip=True)
            if h1_text:
                name = h1_text
        if not name:
            og_title = soup.find("meta", property="og:title")
            content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
            if content_title and content_title.strip():
                name = content_title.strip()
        if not name or len(name) < 3:
            return None

        description: Optional[str] = None
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if isinstance(meta_desc, Tag):
            d = meta_content(meta_desc)
            if d and d.strip():
                description = normalize_description_text(d, max_len=2000)
        if not description:
            og_desc = soup.find("meta", property="og:description")
            if isinstance(og_desc, Tag):
                d = meta_content(og_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000)
        if not description:
            # Magento themes often render the copy inside
            # ``.product.attribute.description`` or ``#description``; grab the
            # first long text block we find under either.
            desc_block = soup.find(attrs={"class": re.compile(r"product[-.\s]attribute[-.\s]description", re.I)})
            if not isinstance(desc_block, Tag):
                desc_block = soup.find(id=re.compile(r"description", re.I))
            if isinstance(desc_block, Tag):
                text = desc_block.get_text(separator=" ", strip=True)
                if text and len(text) > 40:
                    description = normalize_description_text(text, max_len=2000)

        # SKU resolution order: explicit "PN:/SKU:" call-out → itemprop/class
        # hook → image filename → URL slug → title code. This is the
        # best-to-worst signal chain on a site that doesn't emit JSON-LD.
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = (
                soup.find(attrs={"itemprop": "sku"})
                or soup.find(class_=re.compile(r"\bsku\b", re.I))
                or soup.find(id=re.compile(r"\bsku\b", re.I))
            )
            if isinstance(sku_elem, Tag):
                raw = sku_elem.get_text(strip=True)
                if raw:
                    # Some Magento themes render as "SKU 305-05-7010"; strip the label.
                    cleaned = re.sub(r"^(sku|pn|part\s*#?)\s*[:\-]?\s*", "", raw, flags=re.IGNORECASE).strip()
                    part_number = normalize_part_number(cleaned)
        if not part_number:
            sku_from_img = _extract_sku_from_images(dom_images)
            if sku_from_img:
                part_number = normalize_part_number(sku_from_img)
        if not part_number:
            sku_from_url = _extract_sku_from_url(url)
            if sku_from_url:
                part_number = normalize_part_number(sku_from_url)
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # Skunk2's catalog is 100% first-party. Skip the generic title /
        # description heuristics (which trip on "Honda" / "Acura" in titles
        # like "Intercooler Kit - 2016-2021 Honda Civic 1.5T") and pin the
        # brand to the canonical house name directly.
        part_manufacturer = BRAND_CANONICAL

        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
        )
