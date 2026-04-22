"""
Steeda (steeda.com) crawler adapter.

BigCommerce Stencil storefront — same sitemap shape as Tick Performance /
XPH, but Steeda also runs the "Website Advantage Rich Snippets" app which
emits a clean ``Product`` JSON-LD block on every product page. That gives
us a richer primary parse source (name, description, brand, image[], offers,
gtin) than the ``BCData`` JS blob alone. ``BCData`` is still kept as a
backup for the small set of products where the JSON-LD block is missing
or stripped by a future theme change.

Product URLs live at the site root (no ``/products/`` prefix), e.g.
``https://www.steeda.com/mishimoto-mmts-mus-86a-mustang-thermostat`` or
``https://www.steeda.com/ford-racing-mustang-5.0l-coyote-air-conditioning-kit-...m50ac.html``.
Since category and brand landing pages also live at root, the adapter
does not try to reject URLs by shape — the JSON-LD ``Product`` check at
parse time is the gate, and sitemap discovery is restricted to the
``type=products`` children so non-product URLs never enter the crawler
queue in the first place.

Fetcher tier: ``http`` — Cloudflare fronts the origin but does not
challenge non-browser clients with a plain UA. Sitemap and product pages
all return 200 to the crawler. If ``cf-mitigated: challenge`` appears in
logs, promote ``FETCHER_TIER`` to ``"tls"``.

Parsing quirks:

- **SKU vs MPN:** the BigCommerce-emitted ``sku`` is a BC variant-id prefix
  + space + the real part number (``"075 MMTS-MUS-86A"``, ``"161 M-7553-E302"``).
  The MPN field on both JSON-LD and BCData is the clean manufacturer code
  (``"MMTS-MUS-86A"``). For Steeda's own SKUs the divergence is a dash vs.
  space (``"555-4044"`` MPN vs. ``"555 4044"`` SKU). We always prefer MPN
  so cross-retailer dedup on the clean MPN works.
- **Brand:** JSON-LD ``brand.name`` is populated by the Rich Snippets app
  from the BigCommerce Brand field, which is retailer-curated. Steeda is a
  multi-brand reseller (Mishimoto, Ford Performance, MBRP, Alpharex, K&N,
  Russell, …) so the brand pass-through is the right default. Steeda's own
  hardware emits ``"Steeda Autosports"`` consistently, but we collapse bare
  ``"Steeda"`` / ``"Steeda Autosports"`` variants to the canonical
  ``"Steeda Autosports"`` to protect against one house brand splitting
  across two manufacturer rows.
- **Images:** JSON-LD ``image`` is an array of size variants of the single
  hero photo (``/stencil/original/``, ``/stencil/1280w/``, ``/stencil/1280x1280/``,
  ``/stencil/500x659/``) — all of the same file. Multi-image products keep
  the extra photos only in the DOM gallery. We merge JSON-LD images with a
  sweep of ``.productView-image[data-zoom-image]`` and the thumbnail rail,
  deduping by a BC-aware key (the ``/products/<id>/<batch>/<file>`` suffix)
  so size variants collapse.

Discovery: ``/xmlsitemap.php`` sitemap index → ``type=products&page=N``
children (Steeda currently exposes two product pages). Pages / categories /
brands children are skipped — none of those host product pages. Override
with ``CRAWLER_STEEDA_START_URLS`` (comma-separated) for a fixed list.
"""

import json
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

STEEDA_BASE = "https://www.steeda.com"
SITEMAP_INDEX_URL = STEEDA_BASE + "/xmlsitemap.php"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.steeda.com/mishimoto-mmts-mus-86a-mustang-thermostat",
]

# Canonical house-brand name. Steeda's Rich Snippets app emits
# ``"Steeda Autosports"`` for first-party SKUs, but theme / BC Brand field
# changes could surface bare ``"Steeda"`` as well — collapse both to one
# canonical spelling so the global part-manufacturer table doesn't split
# the house brand across two rows.
_STEEDA_CANONICAL_BRAND = "Steeda Autosports"
_STEEDA_BRAND_VARIANTS = frozenset({"steeda", "steeda autosports", "steeda autosports llc", "steeda autosports, llc"})

# Inline on every product page:
#   var BCData = {"product_attributes":{...}};
# Backup source for SKU / MPN / price when JSON-LD is missing (rare — the
# Rich Snippets app ships JSON-LD on every product today).
_BCDATA_RE = re.compile(r"var\s+BCData\s*=\s*(\{.*?\})\s*;", re.DOTALL)

# Reject storefront chrome that occasionally slips into the gallery region
# (Steeda logos, PCI / BBB badges, theme assets).
_IMAGE_NOISE_RE = re.compile(
    r"loading\.svg|/stencil/[^/]+/img/|/assets/img/|/images/stencil/original/image-manager/|placeholder|logo|favicon|bbb\.png|pci_dss",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via xmlsitemap.php, then default."""
    raw = os.environ.get("CRAWLER_STEEDA_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
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
    child urlset and collect every product URL. Returns a deduplicated list
    (keyed by path, query stripped); empty on failure.
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


def _is_steeda_brand_variant(value: Optional[str]) -> bool:
    """True if ``value`` is one of Steeda's own house-brand spellings."""
    if not value:
        return False
    return value.strip().lower() in _STEEDA_BRAND_VARIANTS


def _normalize_part_manufacturer(raw: Optional[str]) -> Optional[str]:
    """
    Collapse Steeda house-brand variants to the canonical spelling; pass
    third-party brands (Mishimoto, Ford Performance, MBRP, …) through
    unchanged so the catalog keeps per-manufacturer rows for them.
    """
    brand = (raw or "").strip()
    if not brand:
        return None
    if _is_steeda_brand_variant(brand):
        return _STEEDA_CANONICAL_BRAND
    return brand


def _mpn_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """
    Prefer the clean ``mpn`` over ``sku`` on Steeda.

    BigCommerce emits ``sku`` as ``"<BC-variant-id> <real-MPN>"`` (e.g.
    ``"075 MMTS-MUS-86A"``, ``"161 M-7553-E302"``). For Steeda's own SKUs
    the divergence is dash-vs-space (``"555-4044"`` MPN vs. ``"555 4044"``
    SKU). The ``mpn`` field is always the clean manufacturer code, so we
    pull it first and only fall back to stripping the BC-id prefix off
    ``sku`` when ``mpn`` is missing.
    """
    raw_mpn = item.get("mpn")
    if isinstance(raw_mpn, str) and raw_mpn.strip():
        return raw_mpn.strip()
    raw_sku = item.get("sku")
    if isinstance(raw_sku, str) and raw_sku.strip():
        stripped = re.sub(r"^\d+\s+", "", raw_sku.strip())
        return stripped or raw_sku.strip()
    return None


def _gtin_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    """Read ``gtin`` / ``gtin13`` / ``gtin12`` / ``gtin8`` / ``gtin14`` off the product."""
    for key in ("gtin", "gtin13", "gtin12", "gtin8", "gtin14"):
        raw = item.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _extract_bcdata(html: str) -> Optional[Dict[str, Any]]:
    """Parse the ``var BCData = {...}`` JSON blob; return None on any failure."""
    match = _BCDATA_RE.search(html)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _bcdata_product_attributes(bcdata: Dict[str, Any]) -> Dict[str, Any]:
    """Return ``product_attributes`` sub-dict, or ``{}`` if not present."""
    attrs = bcdata.get("product_attributes")
    return attrs if isinstance(attrs, dict) else {}


def _part_number_from_bcdata(attrs: Dict[str, Any]) -> Optional[str]:
    """Prefer MPN over SKU on BCData (same logic as the JSON-LD path)."""
    for key in ("mpn", "sku"):
        raw = attrs.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _gtin_from_bcdata(attrs: Dict[str, Any]) -> Optional[str]:
    """Return GTIN/UPC from BCData ``product_attributes``."""
    for key in ("gtin", "upc"):
        raw = attrs.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _price_cents_from_bcdata(attrs: Dict[str, Any]) -> Optional[int]:
    """Read ``product_attributes.price.without_tax.value`` (dollars) → cents."""
    price = attrs.get("price")
    if not isinstance(price, dict):
        return None
    without_tax = price.get("without_tax")
    if not isinstance(without_tax, dict):
        return None
    value = without_tax.get("value")
    if value is None:
        return None
    try:
        dollars = float(value)
    except (TypeError, ValueError):
        return None
    if dollars <= 0:
        return None
    return int(round(dollars * 100))


def _price_cents_from_og(soup: BeautifulSoup) -> Optional[int]:
    """Read ``<meta property="product:price:amount">`` / ``og:price:amount``."""
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta_content(meta)
            if content:
                cents = parse_price_cents(content)
                if cents is not None:
                    return cents
    return None


def _extract_name_dom(soup: BeautifulSoup) -> Optional[str]:
    """``<h1 class="productView-title">`` → og:title → first ``<h1>``."""
    h1 = soup.find("h1", class_=re.compile(r"\bproductView-title\b"))
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    plain_h1 = soup.find("h1")
    if isinstance(plain_h1, Tag):
        text = plain_h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description_dom(soup: BeautifulSoup) -> Optional[str]:
    """Read ``.productView-description`` (Stencil's standard description wrapper)."""
    article = soup.find(class_=re.compile(r"\bproductView-description\b"))
    if isinstance(article, Tag):
        text = article.get_text(" ", strip=True)
        normalized = normalize_description_text(text, max_len=2000)
        if normalized and len(normalized) >= 20:
            return normalized
    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        d = meta_content(og_desc)
        if d and d.strip():
            return normalize_description_text(d, max_len=2000)
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        d = meta_content(meta_desc)
        if d and d.strip():
            return normalize_description_text(d, max_len=2000)
    return None


def _is_valid_product_image(url: str) -> bool:
    """Keep BigCommerce product CDN paths; reject theme chrome and loading spinners."""
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
    """Expand protocol-relative URLs; reject non-HTTP values."""
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
    photo at different resolutions (``/stencil/original/``,
    ``/stencil/1280w/``, ``/stencil/500x659/``, …) collapses to one dedup
    entry. Key is the last two path segments (``<batch>/<file>``) with the
    query and any trailing ``.W.H`` dimensions stripped.
    """
    base = url.split("?", 1)[0]
    base = re.sub(r"\.\d+\.\d+(\.[A-Za-z0-9]+)$", r"\1", base)
    parts = base.rstrip("/").split("/")
    return "/".join(parts[-2:]) if len(parts) >= 2 else base


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather gallery image URLs from the DOM. Walks each
    ``.productView-image[data-zoom-image]`` (the largest stencil-resized
    URL the theme pre-renders) and the thumbnail rail for multi-image
    products where only one zoom image is emitted server-side. Deduped by
    photo identity so size variants collapse.
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
        for thumb in gallery.find_all("a", class_=re.compile(r"productView-thumbnail-link")):
            if not isinstance(thumb, Tag):
                continue
            for attr in ("data-zoom-image", "href"):
                v = thumb.get(attr)
                if isinstance(v, str) and v.strip():
                    add(v)
                    break

    og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content)

    return ordered[:12]


def _merge_image_urls(primary: List[str], secondary: List[str]) -> List[str]:
    """Union two image lists preserving order, deduped by photo identity."""
    ordered: List[str] = []
    seen: set[str] = set()
    for url in list(primary) + list(secondary):
        if not url:
            continue
        key = _image_dedup_key(url)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(url)
        if len(ordered) >= 12:
            break
    return ordered


class SteedaAdapter(RetailerCrawlerAdapter):
    """
    Steeda (steeda.com) adapter.

    BigCommerce Stencil storefront running the Website Advantage Rich
    Snippets app, so every product page ships a ``Product`` JSON-LD block
    alongside the standard ``BCData`` JS blob.

    Discovery: ``/xmlsitemap.php`` sitemap index → ``type=products&page=N``
    children only. Non-product child sitemaps (pages, categories, brands)
    are skipped.

    Parsing: JSON-LD ``Product`` is the primary source (name, description,
    image[], offers.price, brand.name, gtin). BCData is the backup for the
    rare page without JSON-LD. We prefer the ``mpn`` field over ``sku`` on
    both sources because BigCommerce prefixes ``sku`` with the internal
    variant id (``"075 MMTS-MUS-86A"``) while ``mpn`` is the clean
    manufacturer code (``"MMTS-MUS-86A"``) used for cross-retailer dedup.
    """

    ADAPTER_NAME: ClassVar[str] = "steeda"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a steeda.com product page into a ``ScrapedPayload``.

        Returns ``None`` when neither a JSON-LD Product block nor a BCData
        blob with a usable name is found — category / brand landing pages
        that share the root URL namespace land here and are correctly
        rejected.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)

        # 1. JSON-LD Product — the authoritative source on every real
        # product page today.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                raw_mpn = _mpn_from_json_ld(item)
                part_number = normalize_part_number(raw_mpn) if raw_mpn else None

                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)

                json_ld_images = list(payload.image_urls or [])
                image_urls = _merge_image_urls(json_ld_images, dom_images)

                gtin = _gtin_from_json_ld(item) or payload.gtin

                price_cents = payload.price_cents
                if price_cents is None:
                    bcdata = _extract_bcdata(html) or {}
                    price_cents = _price_cents_from_bcdata(_bcdata_product_attributes(bcdata)) or _price_cents_from_og(
                        soup
                    )

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=gtin,
                )

        # 2. BCData / DOM fallback — rare path (JSON-LD-producing app is
        # installed site-wide today), but keeps the adapter resilient if a
        # theme migration drops the Rich Snippets integration.
        #
        # Gate the fallback on BCData ``product_attributes`` carrying at
        # least one real product signal (SKU/MPN or price). Without this
        # gate, category/brand landing pages — which share the site-root
        # URL namespace on BC Stencil and also render an ``<h1>`` — would
        # parse as fake products.
        bcdata = _extract_bcdata(html) or {}
        attrs = _bcdata_product_attributes(bcdata)
        if not _part_number_from_bcdata(attrs) and _price_cents_from_bcdata(attrs) is None:
            return None

        name = _extract_name_dom(soup)
        if not name or len(name) < 3:
            return None

        raw_part_number = _part_number_from_bcdata(attrs)
        part_number = normalize_part_number(raw_part_number) if raw_part_number else None

        description = _extract_description_dom(soup)

        price_cents = _price_cents_from_bcdata(attrs) or _price_cents_from_og(soup)

        part_manufacturer = _normalize_part_manufacturer(part_manufacturer_from_title(name))
        if not part_manufacturer and description:
            part_manufacturer = _normalize_part_manufacturer(
                part_manufacturer_from_description(description, product_name=name)
            )
        if not part_manufacturer:
            part_manufacturer = _normalize_part_manufacturer(part_manufacturer_fallback_from_title(name))

        gtin = _gtin_from_bcdata(attrs)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images if dom_images else None,
            gtin=gtin,
        )
