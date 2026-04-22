"""
OpenFlash Performance / OFT (openflashtablet.com) crawler adapter.

Platform: **WordPress + WooCommerce** (Rhodes theme, Shield WP security
plugin). The marketing URL ``openflashperformance.com`` 302s to
``openflashtablet.com`` — that is the only live host; the originally-probed
candidates ``openflashtuning.com`` and ``theoftshop.com`` are NXDOMAIN at
the time of writing. Apex ``openflashtablet.com`` serves complete HTML on
first request (``requests`` with a plain UA works); no Cloudflare challenge
and no TLS fingerprint block, so ``FETCHER_TIER`` stays at the default
``"http"``.

Product URLs: ``https://openflashtablet.com/shop/<slug>/``

Discovery: ``/wp-sitemap.xml`` is a standard WordPress 5.5+ sitemap **index**
pointing at ``wp-sitemap-posts-product-1.xml`` (products), plus
``wp-sitemap-posts-post-*`` / ``wp-sitemap-posts-page-*`` /
``wp-sitemap-taxonomies-*`` / ``wp-sitemap-users-*`` siblings — only the
``wp-sitemap-posts-product-*`` children host real product URLs, the rest
are skipped. Override with ``CRAWLER_OPENFLASHPERFORMANCE_START_URLS``
(comma-separated) for a fixed list.

JSON-LD shape: Yoast-style ``@graph`` with a ``BreadcrumbList`` and a
``Product`` node. The shared ``extract_json_ld_product`` helper unwraps
``@graph`` and returns the ``Product``. Two WooCommerce/Yoast quirks:

- **Price lives in ``offers[0].priceSpecification[0].price``** instead of
  ``offers[0].price``. Shared ``_price_from_json_ld`` doesn't recurse into
  that nested shape, so we pull the value out explicitly when the shared
  reader returns ``None``. (Same pattern as the ``driveshaftshop`` adapter.)
- **No ``brand`` field** on any Product node — brand is implicit from
  ``offers[0].seller.name`` (``"OpenFlash Performance"``) or missing
  entirely. We therefore ignore the title-heuristic fallback (which would
  always pick the target car make — "Mazda", "Subaru", "Ducati") and hard-
  code the manufacturer to ``"OpenFlash Performance"`` for empty/car-make
  brand slots. The JSON-LD brand is passed through **only** when it's a
  real non-empty, non-car-make string — OFT doesn't resell third-party
  manufacturers today, but the pass-through guards against future catalog
  growth.

Variant rule: OFT's catalog is **not variant-heavy** — each vehicle
platform is its own URL (e.g. ``openflash-tablet-for-mazda-mx5-2019-nd2``
vs ``openflash-tablet-for-mazda-mx5-2006-to-2015``). Where a product does
offer variants (custom e-tuning credit tiers), WooCommerce still emits one
flattened ``Product`` JSON-LD — so the per-URL ``ScrapedPayload`` model
works cleanly. No ``ProductGroup`` extractor needed.

SKU format: First-party codes like ``OFT-ND2``, ``OFTUNIV``, ``OFT-V3-86``,
plus connector-cable ``OBD2-*`` / ``APRILIA-*`` SKUs. All go through
``normalize_part_number`` unchanged.

Images: WooCommerce gallery at ``.woocommerce-product-gallery__image`` with
each item wrapping a full-res ``<a href="...wp-content/uploads/...-scaled.jpg">``
around a resized ``<img src="...-560x420.jpg">``. We prefer the anchor
``href`` (full-res upload) and dedupe WordPress size-suffix variants
(``-600x450``, ``-1200x900``, etc.) so width-variants of the same asset
collapse to one URL.

Tier rationale: WordPress + Shield WP responds to plain ``requests`` with a
full server-rendered page. No JS challenge (Shield's anti-bot cookie
``icwp-wpsf-notbot`` is issued without interaction), no TLS fingerprint
block. Tier 0 is sufficient.

Caveats:

- ``openflashperformance.com`` is the marketing alias — it 302s to
  ``openflashtablet.com``. The host map should route **both** apex hosts
  here so archive replay / Chrome-extension captures of the marketing
  domain also match.
- ``openflashtuning.com`` and ``theoftshop.com`` (suggested during recon)
  are NXDOMAIN. Do not add them to the host map — if OFT stands them up
  later, they can be added then.
- Yoast appends the site name ``" - OpenFlash Performance"`` to
  ``BreadcrumbList`` / ``WebPage`` titles on some pages; ``Product.name``
  is usually clean, but we strip the suffix defensively.
- Robots.txt (Shield WP + Yoast) allows catalog crawling; only
  ``/wp-admin/``, the Shield honeypot, and ``?add-to-cart=`` query URLs
  are disallowed — none of which we hit.
"""

import os
import re
import time
from typing import Any, ClassVar, Iterator, List, Optional, cast
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
    extract_json_ld_product,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

OFT_BASE = "https://openflashtablet.com"
SITEMAP_INDEX_URL = OFT_BASE + "/wp-sitemap.xml"
PRODUCT_PAGE_PATH = "/shop/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Verified live product URLs used as a last-resort fallback when both the
# env override and sitemap discovery fail. Picked across the catalog (Subaru/
# 86 platform + Mazda Miata) so the first crawl exercises the JSON-LD path
# on two distinct vehicle families.
DEFAULT_START_URLS = [
    "https://openflashtablet.com/shop/openflash-tablet_v3-for-gt86-scion-fr-s-subaru-brz-toyota-gt86-2012-to-2020/",
    "https://openflashtablet.com/shop/openflash-tablet-for-mazda-mx5-2019-nd2/",
]

# Only WordPress sitemap children named ``wp-sitemap-posts-product-N.xml``
# host product URLs. Skip post/page/taxonomy/user siblings.
_PRODUCT_SITEMAP_RE = re.compile(r"/wp-sitemap-posts-product-\d+\.xml$", re.IGNORECASE)

# Yoast appends the site name as a title suffix on WebPage nodes. Product
# JSON-LD is usually clean, but strip defensively in case a page leaks it in.
_NAME_SITE_SUFFIX_RE = re.compile(
    r"\s*[-–—|]\s*OpenFlash\s+Performance\s*$",
    re.IGNORECASE,
)

# WordPress upload size-suffix (e.g. ``-600x450.jpg``, ``-1200x900.webp``).
# Rejected so we keep full-resolution gallery media over theme thumbnails and
# so ``_canonical_image_key`` can collapse width-variants of the same asset.
_WP_SIZE_SUFFIX_RE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.[a-z]{2,5}(?:$|\?))", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"/OpenFlash[- ]Performance[- ]Logo|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]|banner",
    re.IGNORECASE,
)

# Canonical house-brand label for the part_manufacturer column. The JSON-LD
# emits no ``brand`` field, so nearly every page falls through to this
# default unless a third-party reseller SKU surfaces later.
_OFT_DEFAULT_BRAND = "OpenFlash Performance"

# Tokens a title-heuristic fallback could pull from OFT product names
# (``OpenFlash Tablet for Mazda MX5 2019+``, ``Bench Flash for Lamborghini
# Urus``, ``ECU Flash for BMW1000``). These are the target vehicle, never
# the manufacturer — coerce to the canonical ``"OpenFlash Performance"``.
_CAR_MAKES = frozenset(
    {
        "subaru",
        "toyota",
        "scion",
        "mazda",
        "nissan",
        "bmw",
        "mercedes",
        "ferrari",
        "porsche",
        "lamborghini",
        "fiat",
        "abarth",
        "ducati",
        "aprilia",
        "ktm",
        "honda",
    }
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via wp-sitemap.xml, then fallback."""
    raw = os.environ.get("CRAWLER_OPENFLASHPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a ``wp-sitemap-posts-product-N.xml`` urlset."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return bool(_PRODUCT_SITEMAP_RE.search(path))


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/wp-sitemap.xml`` → each ``wp-sitemap-posts-product-N.xml`` urlset
    and collect every ``/shop/<slug>/`` URL. Returns deduplicated list
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
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _strip_site_suffix(name: str) -> str:
    """Drop the trailing ``" - OpenFlash Performance"`` suffix if Yoast appended it."""
    stripped = _NAME_SITE_SUFFIX_RE.sub("", name).strip()
    return stripped or name


def _price_cents_from_price_specification(item: dict[str, Any]) -> Optional[int]:
    """
    Read price from ``offers[0].priceSpecification[0].price`` — the shape
    WooCommerce/Yoast uses on OFT. Returns ``None`` when no usable number
    is found. Mirrors the same-named helper on the ``driveshaftshop`` adapter
    (identical Yoast-WooCommerce JSON-LD shape).
    """
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = cast(dict[str, Any], offers[0])
    elif isinstance(offers, dict):
        offer = offers
    else:
        return None
    specs = offer.get("priceSpecification")
    if isinstance(specs, list) and specs:
        spec = cast(dict[str, Any], specs[0])
    elif isinstance(specs, dict):
        spec = specs
    else:
        return None
    price = spec.get("price")
    if price is None:
        return None
    try:
        num = float(str(price).replace(",", ""))
    except (ValueError, TypeError):
        return None
    if not (num > 0):
        return None
    return int(round(num * 100))


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Return the canonical manufacturer for an OFT product page.

    - Empty / missing → coerce to canonical ``"OpenFlash Performance"``
      (the common case — JSON-LD emits no ``brand`` field).
    - Car-make strings (``"Mazda"``, ``"Subaru"``, ``"Ducati"``, …) →
      coerce to the canonical house brand. Title-heuristic fallbacks
      would otherwise grab these from names like "Openflash Tablet for
      Mazda MX5…" and pollute the catalog with phantom car-make
      manufacturers.
    - Any ``"OpenFlash …"`` / ``"OFT …"`` / ``"Openflashtablet"`` variant →
      collapse to the canonical ``"OpenFlash Performance"`` spelling
      regardless of case / trailing qualifier.
    - Anything else (a real third-party manufacturer, if OFT ever resells
      one) → pass through unchanged.
    """
    brand = (part_manufacturer or "").strip()
    if not brand:
        return _OFT_DEFAULT_BRAND
    low = brand.lower()
    if low in _CAR_MAKES:
        return _OFT_DEFAULT_BRAND
    if (
        low == "openflash performance"
        or low == "openflashperformance"
        or low.startswith("openflash ")
        or low.startswith("openflash-")
        or low == "openflashtablet"
        or low.startswith("openflashtablet")
        or low == "oft"
        or low.startswith("oft ")
        or low.startswith("oft-")
    ):
        return _OFT_DEFAULT_BRAND
    return brand


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against OFT."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return OFT_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only WordPress uploads under openflashtablet.com; reject chrome images."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/wp-content/uploads/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """
    Drop WordPress ``-WxH`` size suffixes so width variants of the same
    asset collapse. ``oft3-pic-560x420.jpg`` and ``oft3-pic-scaled.jpg``
    hash to different keys (different basenames), but ``oft3-pic-560x420``
    and ``oft3-pic-1200x900`` collapse to the same key — they are just
    thumbnail variants of the same upload.
    """
    stripped = _WP_SIZE_SUFFIX_RE.sub("", url)
    # Also strip WordPress cache-busting ``?ver=`` / ``?v=`` query params.
    stripped = re.sub(r"[?&](ver|v|fit|resize)=[^&]+", "", stripped)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_gallery_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect every ``<a href>`` inside a ``.woocommerce-product-gallery__image``
    block. The ``href`` points at the full-res WordPress upload; the inner
    ``<img src>`` is a resized thumbnail we don't want. Returns unique,
    document-ordered URLs capped at 12 with size-variant dedupe.
    """
    seen_keys: set[str] = set()
    out: List[str] = []
    for container in soup.select(".woocommerce-product-gallery__image"):
        if not isinstance(container, Tag):
            continue
        anchor = container.find("a", href=True)
        if not isinstance(anchor, Tag):
            continue
        href_val = anchor.get("href")
        if not isinstance(href_val, str):
            continue
        href = _normalize_image_url(href_val)
        if not href.startswith("http") or not _is_valid_product_image(href):
            continue
        key = _canonical_image_key(href)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        out.append(href)
        if len(out) >= 12:
            break
    return out


class OpenFlashPerformanceAdapter(RetailerCrawlerAdapter):
    """
    OpenFlash Performance (OFT) adapter. Discovery: WordPress sitemap index →
    ``wp-sitemap-posts-product-N.xml`` children. Parsing: Yoast-style JSON-LD
    ``Product`` (inside ``@graph`` alongside ``BreadcrumbList`` — the shared
    extractor unwraps ``@graph``), with a WooCommerce/Yoast
    ``priceSpecification`` price fallback, a full-res WooCommerce gallery
    sweep, and a hard-coded ``"OpenFlash Performance"`` default manufacturer
    (JSON-LD emits no ``brand`` field).
    """

    # Default Tier 0 — plain HTTP is enough. Shield WP security plugin serves
    # a notbot cookie without interaction and does not challenge requests.
    ADAPTER_NAME: ClassVar[str] = "openflashperformance"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``wp-sitemap.xml`` (minus non-product
        children). Set ``CRAWLER_OPENFLASHPERFORMANCE_START_URLS``
        (comma-separated) to override with a fixed list. A jittered delay is
        applied between sitemap-child fetches inside
        ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an OpenFlash product page into a ``ScrapedPayload``.

        JSON-LD ``Product`` is authoritative (WordPress + Yoast + WooCommerce).
        Returns ``None`` when no usable Product block is present (soft-404 or
        non-product landing page).
        """
        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        clean_name = _strip_site_suffix(payload.name)

        # Yoast/WooCommerce nests price inside offers[0].priceSpecification[0];
        # the shared reader sees offers[0].price and bails.
        price_cents = payload.price_cents
        if price_cents is None:
            price_cents = _price_cents_from_price_specification(item)

        part_number = normalize_part_number(payload.part_number) if payload.part_number else None
        part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)

        # JSON-LD ``image`` is typically a single full-res URL. Merge the
        # WooCommerce gallery so we keep the full carousel, deduped against
        # the JSON-LD cover by size-variant key.
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_gallery_images(soup)

        image_urls: List[str] = []
        seen_keys: set[str] = set()
        for raw in list(payload.image_urls or []):
            u = _normalize_image_url(raw)
            if not u.startswith("http") or not _is_valid_product_image(u):
                continue
            key = _canonical_image_key(u)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            image_urls.append(u)
        for u in dom_images:
            key = _canonical_image_key(u)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            image_urls.append(u)
            if len(image_urls) >= 12:
                break

        return ScrapedPayload(
            name=clean_name,
            product_url=url,
            description=payload.description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )
