"""
Evasive Motorsports (evasivemotorsports.com) crawler adapter.

Product URLs: https://www.evasivemotorsports.com/store/product/<slug>/
Miva Merchant storefront — does **not** expose JSON-LD, but does render a
Schema.org microdata ``Product`` block with name/sku/price/priceCurrency/
description/image, plus a "Specs" table that carries the real brand and MPN.

The ``itemprop="sku"`` value is retailer-prefixed (e.g. ``TOMS-08611-TZW50``)
while the spec-table ``MPN`` is the clean manufacturer code
(``08611-TZW50``). We use MPN as ``part_number`` — same trick as the Summit
Racing adapter — so cross-retailer dedupe on (manufacturer, part_number)
still matches on MPN alone.

Discovery: sitemap index at ``/sitemap.xml`` points at ``/sitemap{N}.xml``
urlsets; we collect every URL whose path contains ``/store/product/``.
Override with ``CRAWLER_EVASIVEMOTORSPORTS_START_URLS`` (comma-separated).
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urljoin
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

EVASIVE_BASE = "https://www.evasivemotorsports.com"
PRODUCT_PAGE_PATH = "/store/product/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.evasivemotorsports.com/store/product/toms-racing-window-visor-toyota-prius-zvw50-16-22/",
]

# Evasive serves images under /mm5/graphics/... Banner / logo / promo assets
# live in the same tree as real product photos, so we filter by filename.
_IMAGE_NOISE_RE = re.compile(
    r"(?:^|/)(?:banner|logo|warning|placeholder|icon|sprite|favicon)" r"|banner|product[_-]?page|affirm|page-banner",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, falling back to the sample URL."""
    raw = os.environ.get("CRAWLER_EVASIVEMOTORSPORTS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (a sitemap index) → each ``/sitemap{N}.xml`` urlset
    and collect every ``/store/product/...`` URL. Returns a deduplicated list
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
            if PRODUCT_PAGE_PATH not in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = EVASIVE_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
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


def _find_product_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """Return the ``schema.org/Product`` itemscope container (if present)."""
    for div in soup.find_all(attrs={"itemscope": True}):
        if not isinstance(div, Tag):
            continue
        itemtype = div.get("itemtype")
        if isinstance(itemtype, str) and "schema.org/Product" in itemtype:
            return div
    return None


def _microdata_content(scope: Tag, prop: str) -> Optional[str]:
    """Read the ``content`` attr of the first ``itemprop=<prop>`` under ``scope``."""
    tag = scope.find(attrs={"itemprop": prop})
    if not isinstance(tag, Tag):
        return None
    content = tag.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    # Fall back to text (itemprop="name">Foo</>) if no content attr
    text = tag.get_text(strip=True)
    return text if text else None


def _specs_table_lookup(soup: BeautifulSoup) -> dict[str, str]:
    """
    Parse the "Specs" tab table (``<div itemprop="spec">``) into a
    lowercased-label → value map, e.g. {"brand": "TOM's Racing", "mpn": "08611-TZW50"}.
    """
    out: dict[str, str] = {}
    spec_div = soup.find(attrs={"itemprop": "spec"})
    if not isinstance(spec_div, Tag):
        return out
    for row in spec_div.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = [c for c in row.find_all("td") if isinstance(c, Tag)]
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).rstrip(":").strip().lower()
        value = cells[1].get_text(strip=True)
        if label and value:
            out[label] = value
    return out


def _extract_description(soup: BeautifulSoup, scope: Optional[Tag]) -> Optional[str]:
    """
    Prefer the DOM "Description" section (captured in the ``product-details``
    block) because it preserves line breaks as readable text; fall back to the
    microdata ``itemprop="description"`` content, which is typically the same
    prose on one line.
    """
    dom_block = soup.find("div", class_=re.compile(r"\bproduct-details\b"))
    if isinstance(dom_block, Tag):
        # Drop the "Description" header before reading the body text.
        for header in dom_block.find_all(["h4", "h3", "h2"]):
            if isinstance(header, Tag) and header.get_text(strip=True).lower().startswith("description"):
                header.decompose()
        text = dom_block.get_text(separator=" ", strip=True)
        normalized = normalize_description_text(text, max_len=2000)
        if normalized and len(normalized) >= 40:
            return normalized

    if scope is not None:
        meta_desc = _microdata_content(scope, "description")
        if meta_desc:
            return normalize_description_text(meta_desc, max_len=2000)

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        v = meta_content(og_desc)
        if v:
            return normalize_description_text(v, max_len=2000)
    return None


def _extract_price_cents(scope: Tag) -> Optional[int]:
    """Read price + currency from the Offer microdata inside ``scope``."""
    price_raw = _microdata_content(scope, "price")
    if not price_raw:
        return None
    return parse_price_cents(price_raw)


def _is_valid_product_image(url: str) -> bool:
    """Keep Miva product images (/mm5/graphics/...) and reject banners/logos/warnings."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/graphics/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _extract_images(soup: BeautifulSoup, scope: Optional[Tag], page_url: str) -> List[str]:
    """
    Collect product image URLs. Start with the microdata / og:image (the hero
    image Miva exposes to search engines), then append anything in the
    thumbnail list container. Relative Miva paths are resolved against the
    page URL so the ``/mm5/`` base element on the document is respected.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = raw.strip()
        if not u:
            return
        if u.startswith("//"):
            u = "https:" + u
        elif not u.startswith("http"):
            u = urljoin(page_url, u)
        if not _is_valid_product_image(u):
            return
        if u in seen:
            return
        seen.add(u)
        ordered.append(u)

    if scope is not None:
        add(_microdata_content(scope, "image"))

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    thumbs = soup.find(class_=re.compile(r"x-product-layout-images__thumbnail-list"))
    if isinstance(thumbs, Tag):
        for img in thumbs.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            for attr in ("src", "data-src", "data-zoom-image"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val)
                    break
        for a in thumbs.find_all("a"):
            if not isinstance(a, Tag) or len(ordered) >= 12:
                break
            for attr in ("href", "data-zoom-image", "data-image"):
                val = a.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val)
                    break

    return ordered[:12]


def _extract_name(soup: BeautifulSoup, scope: Optional[Tag]) -> Optional[str]:
    """Microdata name → og:title → h1. Microdata is authoritative when present."""
    if scope is not None:
        name = _microdata_content(scope, "name")
        if name:
            return name

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    return None


class EvasiveMotorsportsAdapter(RetailerCrawlerAdapter):
    """
    Evasive Motorsports adapter. Discovery via ``/sitemap.xml`` → child urlsets
    (URLs containing ``/store/product/``). Parsing uses the Schema.org
    microdata ``Product`` block for name/price/description/image plus the
    Specs table for brand and MPN (preferred over the retailer-prefixed SKU).
    """

    ADAPTER_NAME: ClassVar[str] = "evasivemotorsports"
    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Evasive Motorsports product page. Returns ``None`` when no
        product name can be recovered (i.e. the page isn't a product page).
        """
        soup = BeautifulSoup(html, "html.parser")
        scope = _find_product_scope(soup)

        name = _extract_name(soup, scope)
        if not name or len(name) < 3:
            return None

        specs = _specs_table_lookup(soup)

        # Part manufacturer: Specs "Brand" wins; else title/description heuristics.
        part_manufacturer: Optional[str] = None
        brand_raw = specs.get("brand")
        if brand_raw:
            part_manufacturer = brand_raw
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(name)

        # Part number: prefer clean MPN over retailer-prefixed SKU.
        part_number: Optional[str] = None
        mpn_raw = specs.get("mpn") or specs.get("manufacturer part number")
        if mpn_raw:
            part_number = normalize_part_number(mpn_raw)
        if not part_number and scope is not None:
            sku_raw = _microdata_content(scope, "sku")
            if sku_raw:
                part_number = normalize_part_number(sku_raw)

        price_cents = _extract_price_cents(scope) if scope is not None else None
        description = _extract_description(soup, scope)

        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(name)

        image_urls = _extract_images(soup, scope, url)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
        )
