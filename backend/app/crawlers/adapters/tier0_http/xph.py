"""
Extreme Power House (x-ph.com) crawler adapter.

BigCommerce Stencil storefront (see ``<meta name="platform" content="bigcommerce.stencil">``).
No JSON-LD ``Product`` block — product-page data instead lives in three places:

- **``BCData`` JS blob** (``var BCData = {...}``) with ``product_attributes``:
  ``sku``, ``upc``, ``mpn``, ``gtin``, ``weight``, ``price.without_tax.{value,currency}``.
  Authoritative for SKU/price on this theme.
- **Schema.org microdata** on the price section: ``itemprop="price"`` +
  ``itemprop="priceCurrency"`` (fallback when BCData isn't parseable).
- **og:/product: meta tags**: ``og:title`` / ``og:image`` / ``product:price:amount``.

Brand is not exposed in BCData, so we lean on the shared title heuristic
(``part_manufacturer_from_title``), then a description/fallback pass — which
picks up cleanly-named brands like "BBS" that lead the product title.

Titles include the SKU as a trailing token (e.g. ``"... PFS/Clip Req. bbsCH106NE"``);
we strip it when it matches the BCData SKU so the stored ``name`` reads cleanly.

Discovery: ``/xmlsitemap.php`` (a sitemap index) → ``xmlsitemap.php?type=products&page=N``
children. BigCommerce product URLs have no path prefix — every slug is at the
site root, so discovery filters by the child sitemap ``type=`` query rather
than a ``/products/``-style path check. Override with
``CRAWLER_XPH_START_URLS`` (comma-separated) for a fixed list.
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

XPH_BASE = "https://x-ph.com"
SITEMAP_INDEX_URL = XPH_BASE + "/xmlsitemap.php"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://x-ph.com/bbs-ch-r-nurburgring-edition-19x9-5-5x120-et35-satin-black-red-lip-wheel-82mm-pfs-clip-req-bbsch106ne/",
]

# The BCData blob is emitted inline on every product page:
#   var BCData = {"product_attributes":{...}};
# It's the cleanest source for SKU / price / weight on a BigCommerce Stencil
# theme, since the site doesn't ship a JSON-LD Product schema.
_BCDATA_RE = re.compile(r"var\s+BCData\s*=\s*(\{.*?\})\s*;", re.DOTALL)

# Junk image URLs on the storefront that occasionally leak into the gallery
# DOM region (loading spinner, BigCommerce chrome, brand defaults).
_IMAGE_NOISE_RE = re.compile(
    r"loading\.svg|/stencil/[^/]+/img/|/assets/img/|/images/stencil/original/image-manager/|placeholder|logo|favicon",
    re.IGNORECASE,
)

# BigCommerce serves the same photo at many sizes under
#   /images/stencil/<WIDTHxHEIGHT>/products/<id>/<batch>/<hash>.jpg?c=<v>
#   /images/stencil/original/products/<id>/<batch>/<hash>.jpg
#   /products/<id>/images/<batch>/<hash>.<W>.<H>.jpg?c=<v>
# We dedupe by the underlying photo identity — the last two path segments
# (batch dir + filename) plus the base filename stripped of trailing `.W.H`
# dimensions — so identical photos at different sizes collapse to one entry.
_STENCIL_SIZE_SUFFIX_RE = re.compile(r"\.\d+\.\d+(\.[A-Za-z0-9]+)$")


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via xmlsitemap.php, then default."""
    raw = os.environ.get("CRAWLER_XPH_START_URLS", "").strip()
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
    child urlset and collect every product URL. Returns deduplicated list
    (keyed by path, query stripped); empty on failure.

    BigCommerce product URLs live at the site root (no ``/products/`` prefix),
    so the filter is on the **child sitemap** ``type`` query param, not on
    the product URL path.
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
            # Single urlset served directly — uncommon on BigCommerce but handle it.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


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
    attrs = bcdata.get("product_attributes")
    return attrs if isinstance(attrs, dict) else {}


def _sku_from_bcdata(attrs: Dict[str, Any]) -> Optional[str]:
    """Prefer MPN (clean manufacturer code) over SKU when BigCommerce populates it."""
    for key in ("mpn", "sku"):
        raw = attrs.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _gtin_from_bcdata(attrs: Dict[str, Any]) -> Optional[str]:
    """Return a GTIN-like value from the BCData ``gtin``/``upc`` fields; None otherwise."""
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


def _price_cents_from_microdata(soup: BeautifulSoup) -> Optional[int]:
    """Read ``<meta itemprop="price" content="875">`` inside the offer scope."""
    tag = soup.find(attrs={"itemprop": "price"})
    if not isinstance(tag, Tag):
        return None
    content = tag.get("content")
    if isinstance(content, str) and content.strip():
        return parse_price_cents(content)
    text = tag.get_text(strip=True)
    return parse_price_cents(text) if text else None


def _price_cents_from_og(soup: BeautifulSoup) -> Optional[int]:
    """Read ``<meta property="product:price:amount" content="875">``."""
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta_content(meta)
            if content:
                cents = parse_price_cents(content)
                if cents is not None:
                    return cents
    return None


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """``<h1 itemprop="name">`` → og:title → first ``<h1>``."""
    h1 = soup.find("h1", attrs={"itemprop": "name"})
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


def _strip_trailing_sku(name: str, sku: Optional[str]) -> str:
    """Drop a trailing SKU token from the title (case-insensitive) if present."""
    if not sku:
        return name
    trimmed = name.rstrip()
    sku_clean = sku.strip()
    if not sku_clean:
        return name
    if trimmed.lower().endswith(sku_clean.lower()):
        # Keep trailing period — it may close an abbreviation in the title
        # (e.g. "Req.") that precedes the SKU token.
        trimmed = trimmed[: -len(sku_clean)].rstrip(" -\u2013\u2014,;:")
    return trimmed or name


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Read the ``<article class="productView-description" itemprop="description">``
    block. The outer article also contains a "Description" heading (as a
    ``productView-title`` paragraph) which we drop before normalizing.
    """
    article = soup.find("article", attrs={"itemprop": "description"})
    if not isinstance(article, Tag):
        return None

    for heading in article.find_all("p", class_=re.compile(r"productView-title")):
        if not isinstance(heading, Tag):
            continue
        if heading.get_text(strip=True).lower().startswith("description"):
            heading.decompose()

    text = article.get_text(separator=" ", strip=True)
    return normalize_description_text(text, max_len=2000)


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
    Reduce a BigCommerce CDN URL to a size-agnostic identity so the same photo
    at different resolutions collapses to one dedup entry.
    """
    base = url.split("?", 1)[0]
    base = _STENCIL_SIZE_SUFFIX_RE.sub(r"\1", base)
    parts = base.rstrip("/").split("/")
    # Last two segments are the ``<batch>/<filename>`` pair, which is the same
    # across the ``.../images/stencil/<size>/...`` and ``.../<id>/images/...``
    # URL forms BigCommerce emits for the same photo.
    return "/".join(parts[-2:]) if len(parts) >= 2 else base


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs. Start with each
    ``productView-image[data-zoom-image]`` (the largest stencil-resized URL),
    then fall back to the ``<img data-src>`` thumbnails and og:image. Dedupe
    by photo identity (see ``_image_dedup_key``) so width variants collapse.
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

    og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content)

    return ordered[:12]


class XPHAdapter(RetailerCrawlerAdapter):
    """
    Extreme Power House adapter. Discovery via ``/xmlsitemap.php`` sitemap index
    (filter children to ``type=products``). Parsing uses the BCData JS blob
    (authoritative SKU + price + GTIN), microdata / og: meta for fallbacks,
    and a DOM sweep of the ``productView-images`` gallery for images.
    """

    ADAPTER_NAME: ClassVar[str] = "xph"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an x-ph.com product page into a ``ScrapedPayload``. Returns
        ``None`` when no product name can be recovered — the page isn't a
        product page (or BigCommerce is serving a soft 404).
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        bcdata = _extract_bcdata(html) or {}
        attrs = _bcdata_product_attributes(bcdata)

        sku_raw = _sku_from_bcdata(attrs)
        part_number = normalize_part_number(sku_raw) if sku_raw else None

        clean_name = _strip_trailing_sku(name, sku_raw)

        price_cents = _price_cents_from_bcdata(attrs) or _price_cents_from_microdata(soup) or _price_cents_from_og(soup)

        description = _extract_description(soup)

        part_manufacturer = part_manufacturer_from_title(clean_name)
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=clean_name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(clean_name)

        image_urls = _extract_images(soup)
        gtin = _gtin_from_bcdata(attrs)

        return ScrapedPayload(
            name=clean_name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
            gtin=gtin,
        )
