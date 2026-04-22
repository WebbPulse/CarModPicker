"""
Voltex USA (voltexracing.com) crawler adapter.

Voltex is the Japan-based track/time-attack aero specialist — GT wings
(Type 12B/H2/5/7/etc.), circuit and street body kits, front bumpers,
canards, under-wings, diffusers, rear spoilers, wet-carbon / FRP — famous
for the Cyber Evo time-attack car. The US storefront catalog covers
Mitsubishi Evo 7-9 / Evo X, Subaru WRX/STI (GD and later), Honda S2000,
Honda Civic (FD/FK8), Nissan 350Z / Skyline GT-R, Toyota GR86 / GT86 /
Corolla, Subaru BRZ, plus a couple of merch SKUs (pins, license-plate
frames). **House brand only** — every SKU is Voltex's own part.

Host — the two candidates listed in the task brief (``voltexusa.com``,
``voltex-motorsports.com``) are both dead at crawl time (2026-04-22):

- ``voltexusa.com`` → SERVFAIL from the authoritative NS.
- ``voltex-motorsports.com`` → NXDOMAIN.

The live US storefront is ``voltexracing.com`` ("VOLTEX Racing North
America" per the JSON-LD ``Organization`` block). Apex serves 200 OK;
``www.voltexracing.com`` 301s back to the apex. That's the canonical host
for this adapter. A ``voltexusa.myshopify.com`` Shopify handle resolves
but returns HTTP 404 on every path — almost certainly a legacy/squatted
Shopify store from before the WordPress migration; we ignore it.

Platform: **WordPress + WooCommerce** on the Enfold theme, fronted by
Cloudflare (no JS challenge, no TLS fingerprint block — plain ``requests``
with the default UA gets a complete HTML product page on first try).
Yoast SEO emits ``/sitemap_index.xml`` → ``/product-sitemap.xml`` with
~118 ``/product/<slug>/`` URLs at last count. Generator meta advertises
Site Kit by Google (Yoast itself doesn't set one), but the WooCommerce /
WordPress fingerprints are unmistakable.

Tier rationale: **Tier 0 — plain HTTP.** Verified end-to-end — robots,
sitemap index, product sitemap, and product pages all return 200 OK with
complete HTML on first try. Cloudflare is on caching duty only; the
origin is SiteGround WordPress.

Discovery: sitemap index → ``/product-sitemap.xml`` → filter to
``/product/<slug>/`` URLs. Drops the ``/shop/`` landing that Yoast also
lists in the product sitemap (it's a category/archive, not a product).
Override with ``CRAWLER_VOLTEXUSA_START_URLS`` (comma-separated) for
ad-hoc runs.

JSON-LD shape — **only Yoast SEO WebPage / ImageObject / BreadcrumbList /
WebSite / Organization.** There is **NO ``@type: Product`` block on any
product page** (confirmed against three diverse PDPs spanning a simple
merch SKU, a track-aero body kit, and a GT wing). ``extract_json_ld_product``
therefore always returns ``None`` for this retailer — the adapter has to
parse the WooCommerce DOM directly. Sources used:

- **name** — ``<h1 class="product_title entry-title">`` inside
  ``<div class="summary entry-summary">``. Falls through to ``og:title``
  stripped of the ``" | Voltex Racing North America"`` site suffix that
  Yoast appends.
- **description** — ``<div id="tab-description" ... class="… entry-content
  …">`` (the full product-info tab with feature bullets and fitment).
  Falls through to ``og:description`` and then ``<meta name=description>``.
- **part_number (SKU)** — ``<span class="sku">...</span>`` inside
  ``<span class="sku_wrapper">``. Voltex's SKU shape is
  ``VOL-<MODEL>`` or a descriptive family code like ``C-COMPLETE-CP``
  (Circuit-Complete-CarbonPackage), ``VOL-TYPE12B``, ``VOL-LZ-001``
  (license-plate frame). Passed through ``normalize_part_number``.
- **price_cents** — Voltex runs WooCommerce in **catalog mode**; the
  ``<p class="price">`` element is always empty and no ``offers`` /
  ``product:price:amount`` / ``$NNN`` appears anywhere in the HTML on any
  product we probed. The adapter leaves ``price_cents = None`` on every
  page. The site's business model is contact-for-quote / dealer-ordering,
  which is typical for low-volume JDM track aero. Do not treat a missing
  price as a parse failure.
- **images** — ``<div class="woocommerce-product-gallery__wrapper">`` is
  the Enfold-flattened WooCommerce gallery: hero ``<a href>`` + a
  ``.thumbnails`` sub-div of additional ``<a href>`` entries, each
  pointing at the full-res WordPress upload. The inner ``<img src>`` is
  a resized thumbnail (``-450x347.jpg``) and is ignored — the ``href``
  on the anchor is the real asset. Falls back to ``og:image`` when the
  gallery wrapper is absent.

Variant rule (per VARIANTS.md §3): every Voltex product page is
``product-type-simple`` (confirmed on body kits, wings, bumpers, and
merch). **No ``hasVariant`` / WooCommerce ``variations_form`` / ``?variant=``
query-string variants exist.** Chord-length / material choices (FRP vs.
wet-carbon, Circuit vs. Street version, wing profile number) are each
modelled as their own top-level product URL on this store rather than as
variants of a parent — e.g. the Evo 7-9 Street bumper FRP and Carbon
versions are two separate ``/product/…-frp-frp/`` and ``/product/…-frp-carbon/``
URLs. This is Option B from VARIANTS.md, applied at the storefront level
by Voltex themselves — one ``ScrapedPayload`` per URL is exactly right
here; nothing is being collapsed.

Brand rule — **force canonical manufacturer to ``"Voltex"``.** Every SKU
in the catalog is a first-party Voltex part (the North America entity
resells no third-party manufacturers). There is no JSON-LD brand and no
``<meta property="product:brand">``, so nothing authoritative exists to
pass through. Product titles bake in the target vehicle make and model
("Voltex Racing EVO 9 Circuit Body Kit", "Voltex Racing 350Z Z33 Front
Bumper", "Voltex Racing 06-07 WRX STI Widebody Kit", "Voltex Racing
S2000 Front Bumper Street Version"), so the shared
``part_manufacturer_from_title`` heuristic would otherwise latch onto
"Voltex" for the "Voltex" prefixed titles — OK — but onto a car make
for anything that leads with the chassis. Applying the canonical form
unconditionally (as ADRO and Verus Engineering do, same reason) is the
safest and simplest policy.

The car makes / chassis Voltex builds aero for — all of which would be
wrong as ``part_manufacturer`` if the heuristic ever picked one — form
the blocklist: **Mitsubishi, Evo, Lancer, GTR, GT-R, Nissan, Honda,
Civic, Toyota, GR86, GT86, BRZ, Subaru, WRX, STI, S2000, 350Z**.
Unconditional canonicalization covers all of these.

Host / canonicalization: product URLs normalize ``www.voltexracing.com``
→ ``voltexracing.com`` (the 301 target and the sitemap-advertised host)
so extension captures from either alias hit the same Part row. Scheme
and trailing slash are preserved as WooCommerce serves them.

Caveats:

1. **No prices — ever.** Every ScrapedPayload has ``price_cents=None``.
   This is by design, not a parse bug; the PartListing row will record
   the URL + availability snapshot without a price. Cross-retailer
   dedupe on this catalog therefore leans on ``retailer + url`` the same
   way ``radium`` does (Radium's sku/price are ``NULL/$0``; Voltex's are
   simply absent from the DOM).
2. **Small catalog.** ~118 product URLs at the last sitemap read. The
   ``--limit`` flag is effectively unnecessary on full runs; a polite
   2.5s delay finishes the whole store in ~5 minutes.
3. **Description length varies.** Merch SKUs (lapel pins, plate frames)
   have one-sentence descriptions that fall below the 40-char threshold
   for the tab-description node; the og:description fallback covers
   them without losing the record.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
)

VOLTEXUSA_BASE = "https://voltexracing.com"
SITEMAP_INDEX_URL = f"{VOLTEXUSA_BASE}/sitemap_index.xml"
PRODUCT_SITEMAP_URL = f"{VOLTEXUSA_BASE}/product-sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# WooCommerce product permalink shape on this install: /product/<slug>/.
_PRODUCT_PATH_PREFIX = "/product/"

# Canonical manufacturer for every Voltex product page. See module docstring
# for the rationale (house-brand-only catalog; titles lead with car make /
# chassis code; no JSON-LD brand and no meta:brand tag). Modeled on ADRO /
# Verus Engineering, which apply the same rule for the same reason.
CANONICAL_BRAND = "Voltex"

# Yoast appends " | Voltex Racing North America" to every og:title so search
# snippets show the brand. When we fall back to og:title for the product
# name, we strip the suffix so the stored name matches the in-page <h1>.
_OG_TITLE_SITE_SUFFIX_RE = re.compile(
    r"\s*[|\-–]\s*Voltex\s+Racing(?:\s+North\s+America)?\s*$",
    re.IGNORECASE,
)

DEFAULT_START_URLS = [
    # Verified 200 OK with full WooCommerce product markup 2026-04-22.
    "https://voltexracing.com/product/voltex-racing-evo-9-circuit-body-kit/",
    "https://voltexracing.com/product/voltex-racing-type-12b-gt-wing-wet-carbon/",
]


def _is_product_url(url: str) -> bool:
    """
    True iff ``url`` is a voltexracing.com product page — scheme http(s),
    host is ``voltexracing.com`` (or its ``www.`` alias), and path is
    ``/product/<slug>/`` with exactly one non-empty slug segment.

    Rejects the ``/shop/`` landing that Yoast also emits into
    ``/product-sitemap.xml``, plus category archives (``/product-category/...``)
    and nested permalink variations (``/product/<a>/<b>/``) that aren't
    real WooCommerce product permalinks on this install.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host not in ("voltexracing.com", "www.voltexracing.com"):
        return False
    path = parsed.path or ""
    if not path.startswith(_PRODUCT_PATH_PREFIX):
        return False
    trimmed = path[len(_PRODUCT_PATH_PREFIX) :].strip("/")
    if not trimmed or "/" in trimmed:
        return False
    return True


def _canonical_product_url(url: str) -> str:
    """
    Normalize to the canonical scheme / host / trailing slash. The apex
    301s ``www.voltexracing.com`` → ``voltexracing.com`` and adds a
    trailing slash on product permalinks — fold both here so an extension
    capture on either alias lands on the same Part row. Query and fragment
    are stripped (WooCommerce product URLs never carry meaningful query
    args on this site — ``?add-to-cart=`` is a POST target, not a canonical).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    host = (parsed.hostname or "").lower()
    if host == "www.voltexracing.com":
        host = "voltexracing.com"
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = path + "/"
    scheme = parsed.scheme or "https"
    return f"{scheme}://{host}{path}"


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_VOLTEXUSA_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_VOLTEXUSA_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap_index.xml`` → ``/product-sitemap.xml`` and collect every
    ``/product/<slug>/`` URL. Mirrors the hasport adapter's pattern: fetch
    the index, pick the ``product-sitemap`` child, then enumerate its locs.
    Falls through to a direct ``/product-sitemap.xml`` fetch when the index
    can't be parsed — the child path is stable on Yoast installs, so a
    single xml-stylesheet-processing-instruction hiccup shouldn't lose
    discovery. Returns ``[]`` only on total failure.
    """
    child_urls: List[str] = []
    try:
        index_text = fetch_page(SITEMAP_INDEX_URL, timeout=30)
    except Exception:
        index_text = ""

    if index_text:
        try:
            root = ET.fromstring(index_text)
        except ET.ParseError:
            root = None
        if root is not None:
            tag = root.tag
            if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
                for loc in _loc_elements(root):
                    if loc.text and "product-sitemap" in loc.text:
                        child_urls.append(loc.text.strip())

    if not child_urls:
        child_urls.append(PRODUCT_SITEMAP_URL)

    seen: set[str] = set()
    product_urls: List[str] = []
    for child_url in child_urls:
        try:
            child_text = fetch_page(child_url, timeout=30)
        except Exception:
            continue
        try:
            child_root = ET.fromstring(child_text)
        except ET.ParseError:
            continue
        for loc in _loc_elements(child_root):
            if not loc.text:
                continue
            url = _canonical_product_url(loc.text.strip())
            if not _is_product_url(url) or url in seen:
                continue
            seen.add(url)
            product_urls.append(url)

    return product_urls


def _strip_site_suffix(text: str) -> str:
    """Drop the Yoast " | Voltex Racing North America" suffix from og:title strings."""
    return _OG_TITLE_SITE_SUFFIX_RE.sub("", text).strip()


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Product name: prefer ``<h1 class="product_title entry-title">`` (the
    in-page WooCommerce title — never includes the site suffix). Fall back
    to ``og:title`` with the Yoast site suffix stripped, and to a bare
    ``<h1>`` only as a last resort.
    """
    h1 = soup.find("h1", attrs={"class": re.compile(r"\bproduct_title\b", re.IGNORECASE)})
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            cleaned = _strip_site_suffix(content.strip())
            if cleaned:
                return cleaned

    any_h1 = soup.find("h1")
    if isinstance(any_h1, Tag):
        text = any_h1.get_text(strip=True)
        if text:
            return _strip_site_suffix(text) or text

    return None


def _extract_sku(soup: BeautifulSoup) -> Optional[str]:
    """
    WooCommerce renders the SKU inside ``<span class="sku_wrapper">SKU:
    <span class="sku">...</span></span>``. The inner span is the real SKU;
    match on class to avoid accidentally grabbing the "SKU: " label.

    Returns ``None`` when the SKU node is empty (catalog-mode pages can
    still have SKUs since Voltex always sets them, but be defensive).
    """
    node = soup.find("span", attrs={"class": re.compile(r"(?:^|\s)sku(?:\s|$)", re.IGNORECASE)})
    if not isinstance(node, Tag):
        return None
    text = node.get_text(strip=True)
    if not text:
        return None
    # WooCommerce uses the literal string "N/A" when a SKU is unset.
    if text.strip().lower() in ("n/a", "na"):
        return None
    return normalize_part_number(text)


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull the product description, preferring the WooCommerce description
    tab (``#tab-description``, which on Enfold is also the ``.entry-content``
    panel). Fall back to ``og:description`` and then
    ``<meta name="description">``.

    Descriptions shorter than 40 chars are discarded from the tab panel
    specifically — the tab opens with an ``<h2>Description</h2>`` and a
    one-line body on merch products, which gets inflated to "Description
    <body>" by ``get_text`` and is less useful than the og:description
    one-liner Yoast emits.
    """
    tab = soup.find(id="tab-description")
    if isinstance(tab, Tag):
        # Drop the leading <h2>Description</h2> heading before
        # extracting text so it doesn't wind up as the first word of
        # the stored description.
        for heading in tab.find_all(["h2"], limit=1):
            if isinstance(heading, Tag) and heading.get_text(strip=True).lower() == "description":
                heading.decompose()
        text = tab.get_text(" ", strip=True)
        normalized = normalize_description_text(text, max_len=2000)
        if normalized and len(normalized) >= 40:
            return normalized

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        v = meta_content(og_desc)
        if v and v.strip():
            normalized = normalize_description_text(v, max_len=2000)
            if normalized:
                return normalized

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        v = meta_content(meta_desc)
        if v and v.strip():
            normalized = normalize_description_text(v, max_len=2000)
            if normalized:
                return normalized

    return None


def _is_valid_image_url(url: str) -> bool:
    """
    Accept ``https?://…/wp-content/uploads/…`` image URLs only. Rejects
    data: URIs, the Enfold logo asset, and prettyPhoto preview overlays.
    """
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if not low.startswith("http"):
        return False
    if "/wp-content/uploads/" not in low:
        return False
    if re.search(r"/voltex-racing-logo|/favicon|/placeholder|/icon[-_]", low, re.IGNORECASE):
        return False
    return True


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect full-resolution product images in display order. Voltex's
    Enfold-themed WooCommerce gallery flattens to
    ``<div class="woocommerce-product-gallery__wrapper">`` containing a
    hero ``<a href>`` and a nested ``<div class="thumbnails">`` with
    additional ``<a href>`` anchors — each href is the original
    ``/wp-content/uploads/…`` upload (the inner ``<img>`` is a theme
    thumbnail like ``*-450x347.jpg`` and is ignored).

    Falls back to ``og:image`` when the gallery wrapper is absent
    (shouldn't happen on a real product page, but cheap insurance).
    Dedupes by exact URL and caps at 12.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = raw.strip()
        if not _is_valid_image_url(u):
            return
        if u in seen:
            return
        seen.add(u)
        ordered.append(u)

    wrapper = soup.find(class_="woocommerce-product-gallery__wrapper")
    if isinstance(wrapper, Tag):
        for anchor in wrapper.find_all("a", href=True):
            if not isinstance(anchor, Tag) or len(ordered) >= 12:
                break
            href = anchor.get("href")
            if isinstance(href, str):
                add(href)

    if not ordered:
        og_img = soup.find("meta", property="og:image")
        if isinstance(og_img, Tag):
            add(meta_content(og_img))

    return ordered[:12]


def _is_product_page(soup: BeautifulSoup) -> bool:
    """
    Body-class guard: WooCommerce always stamps ``product-type-simple`` /
    ``product-type-variable`` / ``product-type-grouped`` onto the
    ``<body>`` of a real product page, and ``post-type-product`` on top of
    that. The shop landing (``/shop/``) and product-category archives
    carry neither. Falls back to looking for the WooCommerce summary /
    gallery nodes when the body class is unusual.
    """
    body = soup.find("body")
    if isinstance(body, Tag):
        cls = body.get("class")
        if isinstance(cls, list) and any(c.startswith("product-type-") for c in cls):
            return True
        if isinstance(cls, list) and "post-type-product" in cls:
            return True
    if soup.find(class_="woocommerce-product-gallery__wrapper") is not None:
        return True
    if soup.find("h1", attrs={"class": re.compile(r"\bproduct_title\b", re.IGNORECASE)}) is not None:
        return True
    return False


class VoltexUsaAdapter(RetailerCrawlerAdapter):
    """
    Voltex USA adapter. WordPress + WooCommerce (Enfold theme) on
    ``voltexracing.com``; Yoast SEO sitemap but **no JSON-LD Product
    block** — parsing is DOM-only. Discovery walks
    ``/sitemap_index.xml`` → ``/product-sitemap.xml`` and filters to
    ``/product/<slug>/`` URLs. Every product page is ``product-type-simple``
    (material / version choices are modelled as separate product URLs on
    this store, not WooCommerce variations), so one ``ScrapedPayload``
    per URL is the correct mapping.

    Pricing is never available — Voltex runs WooCommerce in catalog /
    contact-for-quote mode, so ``price_cents`` is always ``None``. Brand
    is forced to ``"Voltex"`` on every part (house-brand-only catalog;
    titles lead with the target vehicle make / chassis code, so the
    shared ``part_manufacturer_from_title`` heuristic can't be used
    safely — Mitsubishi / Evo / Lancer / GT-R / Nissan / Honda / Civic
    / Toyota / GR86 / GT86 / BRZ / Subaru / WRX / STI / S2000 / 350Z
    would all be wrong as ``part_manufacturer``).
    """

    ADAPTER_NAME: ClassVar[str] = "voltexusa"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. ``CRAWLER_VOLTEXUSA_START_URLS`` (comma-separated)
        wins when set. Otherwise walk the Yoast sitemap; fall back to the
        hard-coded defaults only if both the sitemap index and the direct
        product-sitemap fetch fail.
        """
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                canonical = _canonical_product_url(url)
                if _is_product_url(canonical):
                    yield canonical
            return

        discovered = _discover_via_sitemap()
        if not discovered:
            discovered = list(DEFAULT_START_URLS)
        for url in discovered:
            canonical = _canonical_product_url(url)
            if _is_product_url(canonical):
                yield canonical

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Voltex USA product page. Returns ``None`` when the URL
        isn't product-shaped, when the page isn't a WooCommerce product
        (shop landing / category archive / blog post slipped through
        discovery), or when the product name can't be recovered.

        No JSON-LD Product is emitted on this site — everything comes
        from the DOM. Price is always ``None`` (see module docstring).
        """
        canonical_url = _canonical_product_url(url)
        if not _is_product_url(canonical_url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        if not _is_product_page(soup):
            return None

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        part_number = _extract_sku(soup)
        description = _extract_description(soup)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=canonical_url,
            description=description,
            # Catalog-mode storefront: Voltex hides prices site-wide. Not a
            # parse failure — PartListing records the URL + availability
            # without a price and cross-retailer dedupe falls back to
            # retailer + url (same pattern as the radium adapter's NULL SKU
            # + $0 price case).
            price_cents=None,
            # House-brand-only catalog; titles lead with car make / chassis
            # code, and no JSON-LD or meta:brand exists on any PDP. Force
            # the canonical "Voltex" on every part. See module docstring.
            part_manufacturer=CANONICAL_BRAND,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
