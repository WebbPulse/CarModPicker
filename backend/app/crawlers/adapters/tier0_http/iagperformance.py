"""
IAG Performance (iagperformance.com) crawler adapter.

BigCommerce Stencil storefront — the classic telltales are in ``robots.txt``
(``/account.php``, ``/cart.php``, ``/__socialshop/``) and the sitemap shape
(``/xmlsitemap.php`` index → ``xmlsitemap.php?type=products&page=N`` children).
Product URLs are flat at the site root — ``https://www.iagperformance.com/<slug>/``
— with no ``/products/`` prefix, so discovery filters on the child sitemap
``type=`` query param rather than the product URL path.

Unlike XPH (the other BigCommerce adapter in this tree), IAG's theme emits a
clean JSON-LD ``Product`` block on every product page with name, sku, mpn,
brand.name, description, image, offers.price / priceCurrency, and occasionally
gtin12. That makes parsing straightforward — reuse the shared JSON-LD helpers
and then apply four IAG-specific rules:

- **Part number: prefer ``mpn`` over ``sku``.** BigCommerce dropship items
  emit the SKU as ``ds_<BRAND>_<MPN>`` (e.g. ``ds_BHXS_6240018`` for an ACT
  clutch disc) while the ``mpn`` field has the clean manufacturer code
  (``6240018``). The shared ``scraped_payload_from_json_ld`` helper reads
  ``sku or mpn``, which is the wrong order here, so we override the part
  number from the raw JSON-LD item.
- **Brand canonicalization.** IAG's own catalog emits the brand as
  ``"IAG Performance"``; a handful of older SKUs show ``"IAG"``. Collapse
  both to ``"IAG Performance"`` so the global part-manufacturer list doesn't
  split the same brand across two rows. Third-party vendor names (ACT, Cobb,
  Perrin, GrimmSpeed, Mishimoto, Garrett, …) pass through unchanged.
- **Shogun description cleanup.** IAG uses the Shogun page-builder for its
  house-brand product pages, and the builder leaks inline JSON markers into
  the description string — ``{"__shgImageV2Elements": {"uuid": "<id>"}}``
  chunks between paragraphs. These add nothing to the product description
  and pollute full-text search, so we strip them.
- **GTIN extraction.** IAG emits ``gtin12`` on own-brand SKUs; the shared
  ``scraped_payload_from_json_ld`` doesn't pull gtin, so it's done here.

Image gallery: JSON-LD ships only the hero image. The full Stencil gallery
lives in ``<section class="productView-images">`` with ``data-zoom-image`` on
each ``<figure>`` — we walk that the same way XPH does and dedup by photo
identity so width variants collapse.

Discovery: ``/xmlsitemap.php`` (sitemap index) → ``xmlsitemap.php?type=products&page=N``
children. Two product pages today (~12k SKUs). Override with
``CRAWLER_IAGPERFORMANCE_START_URLS`` (comma-separated) for a fixed list.

Fetcher tier: plain HTTP. Cloudflare fronts the origin but serves sitemap
and product pages to plain ``requests`` with a normal UA. Promote to
``tls`` if ``cf-mitigated: challenge`` ever appears.
"""

import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional
from urllib.parse import parse_qs, urlparse
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
    normalize_description_text,
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

IAG_BASE = "https://www.iagperformance.com"
SITEMAP_INDEX_URL = IAG_BASE + "/xmlsitemap.php"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.iagperformance.com/iag-performance-crest-cnc-stage-x-2-5l-subaru-billet-aluminum-short-block-for-wrx-sti-lgt-fxt/",
]

# Canonical manufacturer name. IAG's own products emit the brand as either
# ``"IAG Performance"`` (modern) or ``"IAG"`` (older). Collapse both to one
# canonical row so ``get_or_create_part_manufacturer_by_name`` doesn't create
# two entries for the same brand.
_IAG_CANONICAL_BRAND = "IAG Performance"
_IAG_BRAND_VARIANTS = frozenset({"iag", "iag performance", "iag-performance", "iagperformance"})

# BigCommerce dropship SKU prefix. When a third-party item ships from a
# distributor, BC emits the SKU as ``ds_<BRAND>_<MPN>`` (e.g.
# ``ds_BHXS_6240018`` for ACT via Behmer/BHXS). The clean ``mpn`` field is
# still populated — we prefer it, and strip the prefix from the SKU as a
# last-ditch fallback.
_DROPSHIP_SKU_PREFIX_RE = re.compile(r"^ds_[A-Z0-9]+_", re.IGNORECASE)

# Shogun page-builder leakage: the builder emits element-anchor JSON blobs
# (``{"__shgImageV2Elements": {"uuid": "s-..."}}``) between paragraphs of the
# product description. These add nothing to the human-readable text and
# pollute full-text search, so we scrub them out before normalization.
_SHOGUN_MARKER_RE = re.compile(
    r"\{\s*\"__shgImageV2Elements\"\s*:\s*\{[^{}]*\}\s*\}",
    re.DOTALL,
)

# Product gallery noise that can slip into a loose DOM sweep on a Stencil
# theme (logos, payment icons, loading spinners). Same filter shape as XPH.
_IMAGE_NOISE_RE = re.compile(
    r"loading\.svg|/stencil/[^/]+/img/|/assets/img/|/images/stencil/original/image-manager/|placeholder|logo|favicon",
    re.IGNORECASE,
)

# BigCommerce serves the same photo at many sizes under
# ``/images/stencil/<WxH>/products/...`` or ``/products/<id>/images/<batch>/...<W>.<H>.jpg``.
# Collapse to a size-agnostic identity so width variants dedupe. Matches the
# XPH regex — same CDN layout.
_STENCIL_SIZE_SUFFIX_RE = re.compile(r"\.\d+\.\d+(\.[A-Za-z0-9]+)$")


def _is_iag_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of IAG's own brand-field spellings."""
    if not value:
        return False
    return value.strip().lower() in _IAG_BRAND_VARIANTS


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> Optional[str]:
    """
    Collapse IAG's self-spellings (``"IAG"``, ``"IAG Performance"``) to the
    single canonical ``"IAG Performance"``. Third-party vendor strings
    (``"ACT"``, ``"Cobb"``, ``"GrimmSpeed"``, …) pass through unchanged so
    re-sold hardware lands on the real manufacturer in the global list.
    Empty input returns ``None`` so callers can fall back to a title heuristic.
    """
    brand = (part_manufacturer or "").strip()
    if not brand:
        return None
    if _is_iag_brand_variant(brand):
        return _IAG_CANONICAL_BRAND
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via xmlsitemap.php, then default."""
    raw = os.environ.get("CRAWLER_IAGPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a ``xmlsitemap.php?type=products&page=N`` child sitemap."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if not parsed.path.endswith("/xmlsitemap.php"):
        return False
    return parse_qs(parsed.query).get("type", [""])[0] == "products"


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/xmlsitemap.php`` (sitemap index) → each ``type=products&page=N``
    child urlset and collect every product URL. Returns deduplicated list
    (keyed by path, query stripped); empty on failure.

    BigCommerce product URLs live at the site root (no ``/products/`` prefix),
    so the filter is on the child sitemap ``type`` query param, not the
    product URL path.
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
            if not u:
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


def _part_number_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """
    Prefer ``mpn`` over ``sku`` — BigCommerce dropship SKUs carry a
    ``ds_<BRAND>_`` prefix that hides the real manufacturer part number.
    As a last-ditch fallback, strip the dropship prefix from ``sku`` so a
    page with an empty ``mpn`` still contributes a clean part number.
    """
    mpn = item.get("mpn")
    if isinstance(mpn, str) and mpn.strip():
        return normalize_part_number(mpn)
    sku = item.get("sku")
    if isinstance(sku, str) and sku.strip():
        stripped = _DROPSHIP_SKU_PREFIX_RE.sub("", sku.strip())
        return normalize_part_number(stripped) if stripped else None
    return None


def _gtin_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """
    Pull a GTIN from the JSON-LD Product. IAG emits ``gtin12`` on its own
    brand SKUs — check the common variants and return the first populated
    one. The shared ``scraped_payload_from_json_ld`` doesn't extract gtin,
    so it's done here.
    """
    for key in ("gtin", "gtin13", "gtin12", "gtin8", "gtin14"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _clean_shogun_markers(description: Optional[str]) -> Optional[str]:
    """
    Scrub Shogun page-builder element anchors from the description. The
    builder emits ``{"__shgImageV2Elements": {"uuid": "s-<id>"}}`` JSON
    blobs between paragraphs; they add nothing to the human-readable text.
    Returns ``None`` if nothing is left after cleanup.
    """
    if not description:
        return description
    cleaned = _SHOGUN_MARKER_RE.sub(" ", description)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on the iagperformance.com host with a non-empty path."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "iagperformance.com" and not host.endswith(".iagperformance.com"):
        return False
    path = (parsed.path or "").strip("/")
    if not path:
        return False
    # Reject BigCommerce chrome paths — these shouldn't get parsed as products.
    if path.endswith(".php") or path.startswith(("admin/", "cart", "checkout", "account", "login")):
        return False
    return True


def _is_valid_product_image(url: str) -> bool:
    """Keep BigCommerce ``cdn11.bigcommerce.com`` product images; reject theme chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/products/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _normalize_image_url(raw: str) -> Optional[str]:
    """Expand protocol-relative URLs and reject non-HTTP values."""
    s = raw.strip()
    if not s:
        return None
    if s.startswith("//"):
        s = "https:" + s
    if not s.startswith("http"):
        return None
    return s


def _image_dedup_key(url: str) -> str:
    """
    Reduce a BigCommerce CDN URL to a size-agnostic identity so the same
    photo at different resolutions collapses to one dedup entry. Matches
    the XPH keying — same CDN layout.
    """
    base = url.split("?", 1)[0]
    base = _STENCIL_SIZE_SUFFIX_RE.sub(r"\1", base)
    parts = base.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else base


def _extract_gallery_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs from the Stencil
    ``<section class="productView-images">`` region. Each ``<figure>`` has a
    ``data-zoom-image`` pointing at the largest stencil-resized URL, plus a
    lower-res ``<img data-src>`` thumbnail. Dedup by photo identity so the
    two collapse to one entry. Capped at 12.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or not _is_valid_product_image(normalized):
            return
        key = _image_dedup_key(normalized)
        if key in seen:
            return
        seen.add(key)
        ordered.append(normalized)

    gallery = soup.find("section", class_=re.compile(r"productView-images"))
    if isinstance(gallery, Tag):
        for figure in gallery.find_all("figure", class_=re.compile(r"productView-image")):
            if not isinstance(figure, Tag):
                continue
            zoom = figure.get("data-zoom-image")
            if isinstance(zoom, str):
                add(zoom)
            for img in figure.find_all("img"):
                if not isinstance(img, Tag):
                    continue
                for attr in ("data-src", "src"):
                    v = img.get(attr)
                    if isinstance(v, str) and v.strip():
                        add(v)
                        break

    return ordered[:12]


class IAGPerformanceAdapter(RetailerCrawlerAdapter):
    """
    IAG Performance adapter. BigCommerce Stencil storefront, plain HTTP is
    sufficient. Discovery via ``/xmlsitemap.php`` → ``type=products&page=N``
    children. Parsing uses the JSON-LD ``Product`` block as the authoritative
    source (Stencil emits it on every product page with name / sku / mpn /
    brand / description / image / offers.price). Adapter-local rules: prefer
    ``mpn`` over ``sku`` (BigCommerce dropship SKUs carry a ``ds_<BRAND>_``
    prefix), collapse IAG's own brand spellings to one canonical row, strip
    Shogun page-builder leakage from descriptions, and expand past the
    single hero image by walking the Stencil gallery DOM.
    """

    ADAPTER_NAME: ClassVar[str] = "iagperformance"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an IAG Performance product page into a ``ScrapedPayload``.
        Returns ``None`` when the URL isn't product-shaped or the page has
        no JSON-LD Product block (soft-404 / category / info page).
        """
        if not _is_product_url(url):
            return None

        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        part_number = _part_number_from_json_ld(item)

        part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(payload.name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(payload.name)

        description = _clean_shogun_markers(payload.description)
        if description is not None:
            description = normalize_description_text(description, max_len=2000)

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_gallery_images(soup)
        image_urls = dom_images if dom_images else payload.image_urls

        gtin = _gtin_from_json_ld(item)

        return ScrapedPayload(
            name=payload.name,
            product_url=payload.product_url,
            description=description,
            price_cents=payload.price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=gtin,
        )
