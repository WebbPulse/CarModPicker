"""
Haltech Engine Management (haltech.com) crawler adapter.

Haltech is the Australian standalone ECU house — Nexus R5, Elite 2500 / 2000 /
1500 / 550, Platinum Sport, Plug'n'Play harnesses, plus apparel and a growing
line of third-party engine internals they resell (Boostline connecting rods,
Wiseco pistons). The storefront lives at ``https://www.haltech.com``
(``haltech.com`` 301s there); ``haltechusa.com`` is a placeholder (HTTP 405)
and *not* a separate catalog — only ``www.haltech.com`` is mapped. The site
runs WooCommerce on WordPress (Yoast SEO + a custom ``theme-haltech`` skin);
catalog pages are served behind Cloudflare but return fully rendered HTML on
first request, so ``FETCHER_TIER`` stays at the default ``"http"``.

**Tier rationale.** Plain ``curl`` returns HTTP 200 with product HTML on every
PDP sampled (Elite 1500, Boostline, Wiseco). No JS challenge, no TLS
fingerprint block observed. No reason to pay the Tier 1 / Tier 2 cost.

**Discovery.** Yoast ships a sitemap **index** at ``/sitemap_index.xml``
(``/sitemap.xml`` 301s to it). The index points at four product urlsets —
``product-sitemap.xml`` through ``product-sitemap4.xml`` — alongside
non-product children (posts, pages, dealers, home sliders, news, authors) that
we skip. Each product urlset is a flat list of ``/product/<slug>/`` URLs. The
adapter walks the index, fetches only the ``product-sitemap*.xml`` children,
and yields every ``/product/`` URL it finds. A jittered delay is applied
between child-sitemap fetches so we don't burst.

Override with ``CRAWLER_HALTECH_START_URLS`` (comma-separated) for ad-hoc runs.

**JSON-LD shape.** Yoast emits a ``@graph`` block with ``WebPage``,
``BreadcrumbList``, ``WebSite``, and ``Organization`` — **no Product schema**.
The canonical per-product data is a GA4 ``dataLayer.push({"event":"view_item",
"ecommerce":{"items":[{…}]}})`` block in the ``<head>``. We parse that directly
— ``item_id`` is the MPN (``HT-150960``, ``BLP-CH6200-927``, ``WPC-K702M88``),
``item_name`` the canonical product name, ``price`` the USD amount, and
``image_url`` the first gallery image. The DOM otherwise has no ``<h1>``, no
``og:price:amount``, no ``itemprop`` microdata — the custom theme renders
price and gallery from JS, so static parsing has to lean on this block.

Fallbacks for when the dataLayer push is absent (older catalog pages, partial
renders):

- **Name**: ``og:title`` with the trailing ``" - Haltech"`` site-name suffix
  stripped.
- **Price**: none — the DOM has no price markup. We accept ``None`` and let
  downstream recrawl pick it up once the page does emit the dataLayer push.
- **Image**: ``.product_single-carousel_item`` ``<img src>`` is the first
  carousel slide on both ECU and Boostline pages.

**Brand rule (house brand).** Per the retailer backlog, Haltech is treated as
a single-brand catalog. The dataLayer always reports ``item_brand: "Haltech"``
even on resold Boostline (``BLP-…``) and Wiseco (``WPC-…``) SKUs, so there is
no extractable per-SKU manufacturer signal on this storefront. The adapter
coerces ``part_manufacturer`` to the canonical ``"Haltech"`` unconditionally —
empty, car-make ("Honda", "Subaru" — the target-vehicle words that dominate
ECU-kit titles), or anything else that would otherwise leak out of the title
heuristic. This matches the house-brand pattern used by Hondata and KTuner.

**Variant rule.** Haltech's PDPs are **one variant per URL** across the
catalog: every ECU / vehicle combo (``HT-150942 Elite 1500 Mitsubishi Galant
VR4``, ``HT-150960 Elite 1500 Honda Civic EP3``, …) is its own slug, every
Boostline bore size is its own slug, every Wiseco oversize is its own slug.
The product sitemap's 4k+ URLs are the authoritative variant list; no
``ProductGroup`` / ``hasVariant`` picker to descend. This is the canonical
"Option B" behavior described in ``VARIANTS.md`` — each variant already has
its own URL, so the crawler's one-Part-per-URL contract matches 1:1 and
nothing is silently dropped. No per-adapter variant logic needed.

**SKU format.** Prefix encodes the real upstream manufacturer:
- ``HT-`` → Haltech's own SKUs (ECUs, harnesses, sensors, apparel).
- ``BLP-`` → Boostline connecting rods (resold).
- ``WPC-`` → Wiseco pistons (resold).
- ``ARP-`` → ARP hardware (occasional).
We store the full prefix-bearing ID as the part number so cross-retailer
dedupe against Boostline / Wiseco's own storefronts can match on MPN.

**Price caveat.** The dataLayer emits ``price: 99999`` as a sentinel on
``Call-to-Order`` / ``MAP-enforced`` SKUs (observed across the Boostline and
Wiseco lines). Any price ≥ ``_PRICE_SENTINEL_USD`` is dropped to ``None``
rather than stored as ``$999.99``.

**Image caveat.** Haltech fronts product imagery through Cloudflare's image
resizer (``/cdn-cgi/image/width=<N>,format=auto/…``) *and* through Cloudflare
Images (``https://imagedelivery.net/IaKGQXu3HHhBuEAF7BOmlg/<uuid>/public``).
The width-clamp proxy is stripped so we store the full-resolution underlying
URL; Cloudflare Images URLs are kept verbatim (they already serve the
"public" variant). Related-product thumbnails sit under ``260x260`` width
clamps alongside the main ``800x`` hero; we dedupe by the unwrapped
``wp-content/uploads/webstore/images/<SKU>_NN.JPG`` suffix so the same SKU's
thumb + hero don't double-count.

**Robots.** Haltech's robots.txt allows the WooCommerce product tree under
``/product/`` for ``User-agent: *``; it only disallows WP admin, WooCommerce
search, and some internal ``/sub/`` + ``/reports/`` trees. A few aggregator
bots (``dotbot``, ``AhrefsBot``, ``BLEXBot``, ``CCBot``, ``SemrushBot``) are
blanket-disallowed; our crawler's UA is not in that list so discovery is
allowed. No ``Crawl-delay`` is declared.
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
)

HALTECH_BASE = "https://www.haltech.com"
SITEMAP_INDEX_URL = f"{HALTECH_BASE}/sitemap_index.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
PRODUCT_PATH_PREFIX = "/product/"

# House brand — the catalog reports ``item_brand:"Haltech"`` on every SKU
# regardless of the upstream manufacturer of the physical part (Boostline /
# Wiseco resells still read "Haltech" in the dataLayer). Coerce to this
# canonical spelling so cross-retailer dedupe groups Haltech's rows together.
HALTECH_BRAND = "Haltech"

# Price sentinel used by the storefront for Call-to-Order / MAP-enforced SKUs.
# Observed on Boostline and Wiseco product pages at 2026-04-21 recon.
# Anything at or above this value is treated as "no price" so we don't store
# $999.99 as a real price.
_PRICE_SENTINEL_USD = 99999

# Default fallback URLs used when sitemap discovery fails and no env override
# is provided. One ECU (Haltech-branded) + one resold engine internal so the
# first crawl exercises both brand paths end to end.
DEFAULT_START_URLS = [
    "https://www.haltech.com/product/ht-150960-elite-1500-honda-civic-ep3/",
    "https://www.haltech.com/product/blp-hn5394-827-honda-b18a-137mm-boostline-kit-arp2000/",
]

# Cloudflare Image Resizer prefix. Product gallery URLs on this site look like
# ``/cdn-cgi/image/width=800,format=auto/wp-content/uploads/webstore/images/HT-150960_00.JPG``.
# Stripping the prefix yields the full-resolution underlying asset; we keep
# that one to avoid locking stored image URLs to a specific display width.
_CF_IMAGE_RESIZER_RE = re.compile(
    r"^/cdn-cgi/image/[^/]+/",
    re.IGNORECASE,
)

# Max images kept per payload (matches ScrapedPayload image cap used elsewhere).
_MAX_IMAGES = 12

# ``dataLayer.push({...})`` block emitted by the theme. A single-line JSON
# object on every product page (pretty-printed in this regex for clarity —
# DOTALL handles any embedded newlines the theme might add later).
_DATALAYER_PUSH_RE = re.compile(
    r"window\.dataLayer\.push\(\s*(\{[^;]*?\})\s*\)\s*;",
    re.DOTALL,
)

# Strip trailing site-name suffix from ``og:title`` (Yoast emits
# ``"<PRODUCT NAME> - Haltech"`` on every PDP). The dash is ASCII on this
# theme; add en/em dashes defensively in case Yoast is reconfigured later.
_TITLE_SUFFIX_RE = re.compile(
    r"\s*[\-–—]\s*Haltech\s*$",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk the Yoast sitemap index; else hardcoded default."""
    raw = os.environ.get("CRAWLER_HALTECH_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """
    True if ``url`` is one of Yoast's ``product-sitemap*.xml`` children.

    Yoast names the first child ``product-sitemap.xml`` and subsequent ones
    ``product-sitemap2.xml``, ``product-sitemap3.xml``, ... The substring
    ``/product-sitemap`` matches all of them and is tight enough to reject
    sibling children like ``post-sitemap.xml`` / ``category-sitemap.xml``.
    """
    return "/product-sitemap" in url


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a Haltech product page (``/product/<slug>/``)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "haltech.com" or host.endswith(".haltech.com")):
        return False
    path = parsed.path or ""
    if not path.startswith(PRODUCT_PATH_PREFIX):
        return False
    # Reject the bare ``/products/`` category landing (different path prefix,
    # but belt-and-suspenders) and the empty ``/product/`` root that the
    # sitemap sometimes emits.
    trimmed = path.rstrip("/")
    return trimmed != PRODUCT_PATH_PREFIX.rstrip("/")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap_index.xml`` → each ``product-sitemap*.xml`` child urlset and
    collect every ``/product/<slug>/`` URL. Returns a deduplicated list (query
    stripped); empty on failure so the caller can fall back to defaults.
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
            if not _is_product_url(u):
                continue
            base = u.split("?")[0]
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
                if not _is_product_child_sitemap(child_url):
                    continue
                if fetched > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                fetched += 1
                try:
                    child_text = fetch_page(child_url, timeout=20)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            # Defensive: if Yoast ever stops emitting an index and flips to a
            # flat urlset, treat the root as the urlset itself.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_datalayer_item(html: str) -> Optional[Dict[str, Any]]:
    """
    Parse the theme's GA4 ``view_item`` dataLayer push and return the first
    ``ecommerce.items[0]`` dict, or ``None`` when absent / malformed.

    The theme emits exactly one push per PDP; we grab the first match and
    reject pushes whose event isn't ``view_item`` (guards against checkout
    / cart pushes that share the same ``window.dataLayer.push(...)`` shape
    but carry different ``items`` semantics).
    """
    for match in _DATALAYER_PUSH_RE.finditer(html):
        raw = match.group(1)
        try:
            blob = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(blob, dict):
            continue
        if blob.get("event") != "view_item":
            continue
        ecommerce = blob.get("ecommerce")
        if not isinstance(ecommerce, dict):
            continue
        items = ecommerce.get("items")
        if not isinstance(items, list) or not items:
            continue
        first = items[0]
        if isinstance(first, dict):
            return first
    return None


def _clean_title(title: str) -> str:
    """
    Strip the trailing ``" - Haltech"`` site-name suffix Yoast tacks onto
    ``og:title`` and the HTML ``<title>``. Leaves the product name alone
    otherwise.
    """
    if not title:
        return title
    return _TITLE_SUFFIX_RE.sub("", title).strip()


def _price_from_datalayer(item: Dict[str, Any]) -> Optional[int]:
    """
    Return ``price_cents`` from the dataLayer's ``price`` field (USD dollars).
    Rejects the ``99999`` Call-to-Order sentinel and any non-positive / non-
    numeric value. Mirrors ``parsing.parse_price_cents`` rounding.
    """
    raw = item.get("price")
    if raw is None:
        return None
    try:
        dollars = float(raw)
    except (TypeError, ValueError):
        return None
    if not (dollars > 0):
        return None
    if dollars >= _PRICE_SENTINEL_USD:
        return None
    return int(round(dollars * 100))


def _normalize_image_url(src: str) -> Optional[str]:
    """
    Produce a storable image URL from a gallery ``<img src>``.

    - Protocol-relative (``//...``) → ``https:``.
    - Absolute paths (``/cdn-cgi/image/width=.../format=auto/...``) get the
      width/format proxy prefix stripped and the site origin attached so we
      store the full-resolution underlying asset instead of a width-clamped
      variant.
    - Bare absolute paths (no proxy prefix) get the site origin attached.
    - Absolute ``imagedelivery.net`` / ``cdn.haltech.com`` URLs pass through
      unchanged — Cloudflare Images already serves the ``public`` variant.
    - Haltech's dataLayer ``image_url`` for Boostline / Wiseco resold SKUs
      wraps an absolute Cloudflare-Images URL inside the
      ``wp-content/uploads/webstore/images/`` path (observed 2026-04-21),
      producing a broken
      ``https://www.haltech.com//wp-content/uploads/webstore/images/https://imagedelivery.net/...``
      URL that doesn't resolve. We unwrap to the inner absolute URL so the
      stored asset is the real one.
    - Duplicated-slash host portions (``https://www.haltech.com//wp-content``)
      are collapsed so dedupe against a clean DOM URL for the same asset
      works.

    Returns ``None`` for anything that doesn't resolve to an ``http(s)`` URL
    (data URIs, empty values, JS handlers).
    """
    if not src:
        return None
    s = src.strip()
    if not s or s.lower().startswith("data:") or s.startswith("#"):
        return None

    # Unwrap the nested ``.../webstore/images/https://imagedelivery.net/...``
    # shape the dataLayer produces for resold SKUs. When the string contains
    # a second ``http(s)://`` after the first, trust the *inner* URL — that's
    # the real Cloudflare Images asset. The outer wrapper is a 404.
    nested_match = re.search(r"https?://.+?(https?://[^\s\"']+)", s)
    if nested_match:
        s = nested_match.group(1)

    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        stripped = _CF_IMAGE_RESIZER_RE.sub("/", s)
        s = HALTECH_BASE + stripped
    else:
        # Absolute http(s) URL — collapse any accidental ``//path`` after the
        # host (``https://www.haltech.com//wp-content/...``) which would make
        # the dedupe key differ from the DOM form of the same asset.
        s = re.sub(r"(https?://[^/]+)//+", r"\1/", s)

    if not s.lower().startswith("http"):
        return None
    return s


def _image_dedupe_key(url: str) -> str:
    """
    Normalize a Haltech image URL down to a dedupe key. Drops the Cloudflare
    Image Resizer ``/cdn-cgi/image/width=.../format=auto/`` prefix and any
    trailing query string, so the same underlying asset served at 260x260
    (related-product thumb) and 800x (hero carousel) collapses to one row.
    """
    key = _CF_IMAGE_RESIZER_RE.sub("/", url)
    # Strip query on imagedelivery.net URLs — Haltech appends a human-readable
    # ``?BL-ConnectingRod-...-FRO.jpeg`` filename hint that isn't part of the
    # asset identity.
    q = key.find("?")
    if q >= 0:
        key = key[:q]
    return key.lower()


def _extract_gallery_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect up to ``_MAX_IMAGES`` product gallery URLs from the DOM.

    Primary source: ``<img class="product_single-carousel_item ...">`` inside
    ``#product_images-carousel`` — the Bootstrap carousel that the custom
    theme renders for every PDP. Ordered by DOM order so the first slide
    (``style="display: inline-block"``) comes first.

    Falls back to a broad ``<img>`` sweep scoped to a ``webstore/images/``
    path pattern on the rare page where the carousel wrapper is missing; the
    dedupe key collapses resizer-variant duplicates from the related-product
    rail.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if len(ordered) >= _MAX_IMAGES:
            return
        url = _normalize_image_url(raw)
        if not url:
            return
        key = _image_dedupe_key(url)
        if key in seen:
            return
        seen.add(key)
        ordered.append(url)

    carousel = soup.find(id="product_images-carousel")
    scope: Optional[Tag] = carousel if isinstance(carousel, Tag) else None

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str):
                add(src)

    if not ordered:
        # Fallback: look at every ``webstore/images`` img on the page. The
        # related-product rail also uses ``webstore/images`` but at width=260;
        # the resizer-prefix-stripping dedupe key collapses any duplicates
        # against the hero so we never emit the same asset twice.
        for img in soup.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= _MAX_IMAGES:
                break
            src = img.get("src")
            if not isinstance(src, str):
                continue
            if "webstore/images" not in src and "imagedelivery.net" not in src:
                continue
            add(src)

    return ordered


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull the long-form overview text from the custom theme's ``#overview_content``
    tab panel. That's the ``"ECU OVERVIEW"`` / product blurb section on ECU
    pages and the corresponding ``"OVERVIEW"`` block on Boostline / Wiseco
    pages. Falls back to the ``og:description`` meta content when the tab panel
    is absent or empty.
    """
    overview = soup.find(id="overview_content")
    if isinstance(overview, Tag):
        text = overview.get_text(separator=" ", strip=True)
        if text and len(text) > 40:
            normalized = normalize_description_text(text, max_len=2000)
            if normalized:
                return normalized

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        content = meta_content(og_desc)
        if content and content.strip():
            normalized = normalize_description_text(content, max_len=2000)
            if normalized:
                return normalized

    return None


def _extract_og_title(soup: BeautifulSoup) -> Optional[str]:
    """Return the cleaned ``og:title`` content (Haltech site-name suffix stripped)."""
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            cleaned = _clean_title(content.strip())
            if cleaned:
                return cleaned
    return None


class HaltechAdapter(RetailerCrawlerAdapter):
    """
    Haltech adapter. Discovery: Yoast sitemap index → ``product-sitemap*.xml``
    children. Parsing: GA4 ``view_item`` dataLayer push (authoritative on this
    site since Yoast emits no Product JSON-LD), with ``og:title`` +
    ``#overview_content`` tab + carousel DOM fallbacks.
    """

    # Plain HTTP is sufficient — Cloudflare on this origin does not challenge
    # ``requests`` for the product tree, and ``/robots.txt`` / ``/sitemap_index.xml``
    # both return 200 on first try. Left explicit so the choice is documented
    # on the class itself, not only in the module docstring.
    ADAPTER_NAME: ClassVar[str] = "haltech"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield every ``/product/<slug>/`` URL from the Yoast sitemap index's
        ``product-sitemap*.xml`` children. Set ``CRAWLER_HALTECH_START_URLS``
        (comma-separated) to override with a fixed list. A jittered delay is
        applied between child-sitemap fetches inside
        ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Haltech product page into a ``ScrapedPayload``.

        1. Pull the GA4 ``view_item`` dataLayer push — canonical source for
           ``item_id`` (MPN), ``item_name``, ``price``, ``image_url``.
        2. Augment with DOM: carousel gallery (dataLayer has only the hero
           image), overview-tab long-form description, ``og:title`` if the
           dataLayer name is missing.
        3. Coerce ``part_manufacturer`` to ``"Haltech"`` unconditionally —
           house-brand rule.

        Returns ``None`` when neither the dataLayer nor ``og:title`` yields a
        usable product name (non-product pages, older Yoast revisions before
        the GA4 push was wired in).
        """
        soup = BeautifulSoup(html, "html.parser")
        datalayer = _extract_datalayer_item(html)

        dl_name: Optional[str] = None
        dl_part_number: Optional[str] = None
        dl_price_cents: Optional[int] = None
        dl_image: Optional[str] = None
        if datalayer is not None:
            raw_name = datalayer.get("item_name")
            if isinstance(raw_name, str) and raw_name.strip():
                dl_name = raw_name.strip()
            raw_id = datalayer.get("item_id")
            if isinstance(raw_id, str) and raw_id.strip():
                dl_part_number = normalize_part_number(raw_id)
            dl_price_cents = _price_from_datalayer(datalayer)
            raw_img = datalayer.get("image_url")
            if isinstance(raw_img, str) and raw_img.strip():
                dl_image = _normalize_image_url(raw_img)

        name = dl_name or _extract_og_title(soup)
        if not name or len(name) < 3:
            return None

        # Gallery: DOM carousel is always richer than the dataLayer's single
        # ``image_url`` (Boostline PDPs ship 5 slides). Start with the carousel
        # order, then merge the dataLayer hero in case the carousel is empty
        # or the theme drifts.
        gallery = _extract_gallery_images(soup)
        if dl_image:
            key = _image_dedupe_key(dl_image)
            if not any(_image_dedupe_key(u) == key for u in gallery):
                gallery.insert(0, dl_image)

        description = _extract_description(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=dl_price_cents,
            part_manufacturer=HALTECH_BRAND,
            part_number=dl_part_number,
            image_urls=gallery[:_MAX_IMAGES] if gallery else None,
        )
