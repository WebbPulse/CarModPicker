"""
fifteen52 (fifteen52.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``https://fifteen52.com/products/<handle>``. The ``www.`` host
301-redirects to the bare apex, so the sitemap and ``DEFAULT_START_URLS`` use
the apex directly.

fifteen52 is a direct-to-consumer rally-style forged wheel brand — Focus RS,
Fiesta ST, GR Corolla, Subaru, R35 GT-R (Project 6GR variants), 52offroad
truck/SUV fitments. RETAILER_BACKLOG lists this as one of the "direct forged
wheels" fills that Tire Rack / Mackin can't cover because those carriers don't
stock fifteen52 fitments.

Shopify modern theme: JSON-LD ``Product`` is emitted with name, description,
brand, sku, offers, and image. Parsing reuses the shared
``extract_json_ld_product`` / ``scraped_payload_from_json_ld`` helpers with one
fifteen52-specific rule:

- **Manufacturer collapse:** the catalog is mostly first-party (fifteen52's own
  forged and cast wheels + the 52offroad truck line + Classic HD accessories).
  JSON-LD ``brand.name`` / Shopify vendor appears as ``"fifteen52"`` (the
  branded all-lowercase spelling), occasionally ``"Fifteen52"`` or
  ``"FIFTEEN52"``. All self-spellings collapse to the single canonical
  ``"fifteen52"`` so the global part-manufacturer table doesn't split one brand
  across rows. Co-branded SKUs with a distinct third-party brand (e.g.
  ``"Project 6GR"`` on the R35 GT-R variants) pass through unchanged.

Discovery: ``/sitemap.xml`` (sitemap index) → ``sitemap_products_*.xml`` child
urlsets only. Pages / collections / blog children are skipped. Override with
``CRAWLER_FIFTEEN52_START_URLS`` (comma-separated).

Fetcher tier: plain HTTP. fifteen52 is Cloudflare-fronted Shopify but serves
``/sitemap.xml`` and product pages to plain ``requests`` with the crawler UA.
Promote to ``tls`` if ``cf-mitigated: challenge`` starts appearing in logs.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
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
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

FIFTEEN52_BASE = "https://fifteen52.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Only the products urlset matters for catalog discovery. Pages / collections /
# blogs children are skipped — those are CMS surfaces (about, dealer locator,
# team / news posts), not product pages.
_PRODUCTS_SITEMAP_RE = re.compile(r"/sitemap_products_\d+\.xml(\?|$)", re.IGNORECASE)

DEFAULT_START_URLS = [
    "https://fifteen52.com/products/107mm-classic-hd-cap-_-asphalt-black",
]

# Canonical manufacturer name. fifteen52's brand styling is all-lowercase; the
# Shopify vendor / JSON-LD brand field usually matches, but occasional products
# use title-case or uppercase. Collapse to one row so the global
# part-manufacturer table doesn't split one brand across multiple entries.
_FIFTEEN52_CANONICAL_BRAND = "fifteen52"
_FIFTEEN52_BRAND_VARIANTS = frozenset(
    {
        "fifteen52",
        "fifteen 52",
        "fifteen-52",
        "fifteen52 wheels",
        "fifteen 52 wheels",
    }
)

# Shopify CDN thumbnail / picker size suffix (file_300x300.jpg, file_64x64.webp)
# — rejected so we keep full-resolution gallery media rather than the picker
# thumbnails the theme renders in the sidebar.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (nav / footer / logos / banners)
# rather than product media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite",
    re.IGNORECASE,
)


def _is_fifteen52_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of fifteen52's own vendor-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _FIFTEEN52_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Collapse fifteen52's self-spellings (``"fifteen52"`` / ``"Fifteen52"`` /
    ``"FIFTEEN52"`` / empty) to the canonical ``"fifteen52"``. Third-party
    vendor strings on co-branded SKUs — e.g. ``"Project 6GR"`` for R35 GT-R
    wheels — pass through unchanged so those rows land on the real brand in
    the global part-manufacturer list.
    """
    brand = (part_manufacturer or "").strip()
    if not brand or _is_fifteen52_brand_variant(brand):
        return _FIFTEEN52_CANONICAL_BRAND
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then fall back to defaults."""
    raw = os.environ.get("CRAWLER_FIFTEEN52_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (sitemap index), then walk only the
    ``sitemap_products_*.xml`` children. Each child urlset's ``<loc>`` entries
    containing ``/products/`` are collected (deduplicated by canonical path).
    Returns an empty list on failure so the caller falls back to defaults.
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
        index_url = FIFTEEN52_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [
                loc.text.strip()
                for loc in _loc_elements(root)
                if loc.text and loc.text.strip() and _PRODUCTS_SITEMAP_RE.search(loc.text)
            ]
            for i, child_url in enumerate(child_sitemap_urls):
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
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


def _canonical_image_key(url: str) -> str:
    """Dedupe key: drop Shopify ``v``/``width``/``height``/``crop`` params so width variants collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _is_valid_shopify_product_image(url: str) -> bool:
    """Only Shopify CDN product media; reject site chrome and picker thumbnails."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/cdn/shop/" not in low and "cdn.shopify.com" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    if _SHOPIFY_THUMBNAIL_RE.search(low):
        return False
    return True


def _normalize_image_url(url: str) -> str:
    """Upgrade ``//`` or ``http://`` to ``https://``; resolve absolute paths against the apex host."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return FIFTEEN52_BASE + u
    return u


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Product gallery images from the DOM (Shopify CDN only), deduped, capped at
    12. Looks at ``<media-gallery>`` first and falls back to
    ``.product__media-wrapper`` — the two patterns Shopify themes use for the
    main product image rail.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_shopify_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        wrapper = soup.select_one(".product__media-wrapper")
        if isinstance(wrapper, Tag):
            scope = wrapper

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            for attr in ("src", "data-src", "data-original"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break

    return ordered[:12]


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a fifteen52.com ``/products/<handle>`` page."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "fifteen52.com" and not host.endswith(".fifteen52.com"):
        return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


class Fifteen52Adapter(RetailerCrawlerAdapter):
    """
    fifteen52 adapter. Shopify storefront, plain HTTP is sufficient.

    Discovery: ``CRAWLER_FIFTEEN52_START_URLS`` env var wins. Otherwise walks
    ``/sitemap.xml`` (sitemap index) and pulls every ``/products/<handle>``
    URL out of the ``sitemap_products_*.xml`` child urlsets only. Falls back
    to ``DEFAULT_START_URLS`` if discovery returns nothing.

    Parsing: JSON-LD Product first (Shopify default — name / brand / sku /
    offers / image), then a DOM / og fallback for the rare page without
    JSON-LD. Manufacturer is collapsed to the canonical ``"fifteen52"`` when
    the vendor field is empty or any self-spelling variant; co-branded
    third-party vendors (Project 6GR, OE hardware) pass through.
    """

    ADAPTER_NAME: ClassVar[str] = "fifteen52"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a fifteen52 product page. JSON-LD Product is the authoritative
        source on Shopify; the DOM / og fallback covers the rare page without
        JSON-LD. Returns ``None`` when the URL is not product-shaped or when
        neither path yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (Shopify default).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
                # JSON-LD image is a single string on fifteen52; merge with DOM
                # gallery so we end up with the full carousel rather than just
                # the hero.
                image_urls = list(payload.image_urls or [])
                seen_keys = {_canonical_image_key(u) for u in image_urls}
                for u in dom_images:
                    key = _canonical_image_key(u)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    image_urls.append(u)
                    if len(image_urls) >= 12:
                        break
                return ScrapedPayload(
                    name=payload.name,
                    product_url=payload.product_url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback — no JSON-LD on the page (rare on Shopify).
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

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # No JSON-LD brand available. fifteen52's catalog is mostly first-party
        # (wheels + accessories), so default directly to the canonical brand
        # rather than running title-first-word heuristics that would match
        # fitment words ("Tarmac", "Turbomac", etc.) as brand names.
        part_manufacturer = _FIFTEEN52_CANONICAL_BRAND

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
