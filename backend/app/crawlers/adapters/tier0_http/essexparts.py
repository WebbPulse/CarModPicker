"""
Essex Parts Services (essexparts.com) crawler adapter.

Essex is the US authorized distributor for AP Racing — reference pricing for
the track/HPDE brake vertical (Radi-CAL and Competition BBKs, pads, rotors,
fluids). Custom Laravel storefront: no JSON-LD Product, no Schema.org
microdata. Product pages are marked by ``<meta property="og:type"
content="product">`` and a ``<h2 class="product-price">`` block; everything
else (name, brand, Part #, description, images) lives in a ``.detail-section``
container with predictable markup.

Discovery: flat ``/sitemap.xml`` urlset (no sitemap index). The sitemap mixes
products with CMS/category/news pages, so we filter by path prefix and strip
category pagination (``?page=N``). Anything that slips through is rejected at
parse time by the ``og:type=product`` guard.

Product URL shape: root-slug, e.g.
``https://www.essexparts.com/ap-racing-by-essex-radi-cal-competition-brake-kit-front-cp9668390mm-r35gtr``.

Override the discovered list with ``CRAWLER_ESSEXPARTS_START_URLS``
(comma-separated).
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urljoin, urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

ESSEXPARTS_BASE = "https://www.essexparts.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.essexparts.com/ap-racing-by-essex-radi-cal-competition-brake-kit-front-9668390mm-r35-nissan-gt-r",
]

# Site-name suffix appended to <title>/og:title on every page.
_TITLE_SITE_SUFFIX_RE = re.compile(r"\s*\|\s*Essex Parts Services,?\s*Inc\.?\s*$", re.IGNORECASE)

# First-path segments that are never products (CMS, account, navigation, categories
# known to have their own paginated listing pages rather than direct products).
_NON_PRODUCT_PATH_PREFIXES = frozenset(
    {
        "aftermarket-products",
        "apracing-factory-big-brake-kits",
        "big-brake-kits",
        "brake-calipers",
        "brake-cooling-hoses-and-temperature-indicators",
        "brake-discs",
        "brake-fluid",
        "brake-hydraulics",
        "brake-lines",
        "brake-pads",
        "brake-bundles-pads-lines-fluid-discs",
        "brake-caliper-stud-kits",
        "cart",
        "checkout",
        "clearance-products",
        "company-information",
        "connectors-and-clips",
        "contact-us",
        "customer",
        "dealer-locator",
        "essex-designed-apracing-competition-brake-kits",
        # Pluralized "radical" category sibling of the above — both are
        # paginated category listings, not product pages.
        "essex-designed-apracing-radical-competition-brake-kits",
        "featured-products",
        "formula-sae",
        "home-page",
        "manufacturer",
        "master-cylinders",
        "media-center",
        "new-products",
        "news-blog",
        "our-team",
        "privacy-policy",
        "pro-race-series",
        "pro-race-services",
        "professional-racing-products",
        "promotion-and-apparel",
        "spieger-custom-ss-lines",
        "sitemap",
        "storage",
        "support",
        "suspension",
        "temperature-indication-and-protection-products",
        "terms-and-conditions",
        "versodeck-flooring",
        "wheels",
    }
)

# Image path prefix for all real product photos (excludes nav/banner/logo assets).
_PRODUCT_IMAGE_PATH_PART = "/imagecache/"

# Part manufacturer aliases: the "Brand:" field is sometimes co-branded with
# Essex; normalize to the upstream manufacturer so cross-retailer dedupe on
# (manufacturer, part_number) still matches against Girodisc / Summit / etc.
_BRAND_ALIASES: dict[str, str] = {
    "essex & ap racing": "AP Racing",
    "essex and ap racing": "AP Racing",
    "essex parts": "AP Racing",
}


def _is_product_url(url: str) -> bool:
    """
    True iff ``url`` looks like an Essex product page (essexparts.com host,
    single root-slug path, not matching any known non-product prefix, no
    pagination query). This is a cheap pre-parse filter; parse_product_page
    remains the final authority via ``og:type=product``.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host != "essexparts.com" and host != "www.essexparts.com":
        return False
    # Reject category pagination (?page=2) — real products don't carry one.
    if "page=" in (parsed.query or ""):
        return False
    path = parsed.path.strip("/")
    if not path:
        return False
    first = path.split("/", 1)[0].lower()
    if first in _NON_PRODUCT_PATH_PREFIXES:
        return False
    # Very short single-word slugs at the root are almost always navigation
    # (e.g. /support, /cart). Real product slugs are descriptive.
    if "/" not in path and len(first) < 8:
        return False
    return True


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, falling back to the sample URL."""
    raw = os.environ.get("CRAWLER_ESSEXPARTS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (a flat urlset, no index) and return all URLs that
    pass ``_is_product_url``. Deduplicated by full URL; empty on failure.
    """
    seen: set[str] = set()
    product_urls: List[str] = []
    try:
        xml_text = fetch_page(ESSEXPARTS_BASE + "/sitemap.xml", timeout=15)
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        u = loc.text.strip()
        if not _is_product_url(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        product_urls.append(u)
    return product_urls


def _normalize_part_manufacturer(brand: Optional[str]) -> Optional[str]:
    """
    Apply co-brand aliases (``Essex & AP Racing`` → ``AP Racing``). Unknown
    brands pass through unchanged so multi-brand listings (Ferodo, Öhlins,
    Hyperco, Spiegler, Mintex, ...) keep their upstream name.
    """
    if not brand:
        return brand
    b = brand.strip()
    return _BRAND_ALIASES.get(b.lower(), b)


def _is_product_page(soup: BeautifulSoup) -> bool:
    """
    Essex tags category pages with ``og:type=website`` and product pages with
    ``og:type=product``. When og:type is set explicitly, trust it. Only fall
    back to the ``<h2 class="product-price">`` marker when og:type is missing.
    """
    og_type = soup.find("meta", property="og:type")
    if isinstance(og_type, Tag):
        value = (meta_content(og_type) or "").strip().lower()
        if value:
            return value == "product"
    return soup.find("h2", class_="product-price") is not None


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Product name from ``.detail-section > h3`` (preferred — plain name), then
    ``og:title`` / ``<title>`` with the ``" | Essex Parts Services, Inc."``
    suffix stripped, finally ``<h1>``.
    """
    detail = soup.find("div", class_="detail-section")
    if isinstance(detail, Tag):
        h3 = detail.find("h3")
        if isinstance(h3, Tag):
            text = h3.get_text(strip=True)
            if text:
                return text

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content:
            cleaned = _TITLE_SITE_SUFFIX_RE.sub("", content).strip()
            if cleaned:
                return cleaned

    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        text = _TITLE_SITE_SUFFIX_RE.sub("", title_tag.get_text(strip=True)).strip()
        if text:
            return text

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_detail_field(soup: BeautifulSoup, label: str) -> Optional[str]:
    """
    Pull the trailing value from a ``<p><strong>{label}:</strong> value</p>``
    row inside ``.detail-section``. Label match is case-insensitive and allows
    trailing whitespace; returns the stripped value or None.
    """
    detail = soup.find("div", class_="detail-section")
    if not isinstance(detail, Tag):
        return None
    target = label.rstrip(":").lower()
    for p in detail.find_all("p"):
        if not isinstance(p, Tag):
            continue
        strong = p.find("strong")
        if not isinstance(strong, Tag):
            continue
        key = strong.get_text(strip=True).rstrip(":").lower()
        if key != target:
            continue
        # Value is everything in <p> after the <strong> tag.
        full_text = p.get_text(" ", strip=True)
        stripped = re.sub(rf"^{re.escape(strong.get_text(strip=True))}\s*", "", full_text).strip()
        return stripped or None
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    Read the main product price from ``<h2 class="product-price"><span
    class="price">$X.XX</span>``. We must NOT fall back to the first ``$`` in
    body text, because product-option <select>s (``Add Brake Pads + $250.00``)
    render before the main price block and would win a naive scan.
    """
    container = soup.find("h2", class_="product-price")
    if isinstance(container, Tag):
        span = container.find("span", class_="price")
        if isinstance(span, Tag):
            cents = parse_price_cents(span.get_text(strip=True))
            if cents is not None:
                return cents
        # Fall through: grab any text inside the container if the span class changed.
        cents = parse_price_cents(container.get_text(" ", strip=True))
        if cents is not None:
            return cents
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer the in-DOM ``.product-summary`` block (full feature bullet list,
    preserves bullet text as space-joined prose). Fall back to og:description
    / meta description — both are generic category boilerplate on this site,
    but better than nothing for SKUs without a summary block.
    """
    summary = soup.find("div", class_="product-summary")
    if isinstance(summary, Tag):
        text = summary.get_text(" ", strip=True)
        normalized = normalize_description_text(text, max_len=2000)
        if normalized:
            return normalized

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        v = meta_content(og_desc)
        if v:
            normalized = normalize_description_text(v, max_len=2000)
            if normalized:
                return normalized

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        v = meta_content(meta_desc)
        if v:
            normalized = normalize_description_text(v, max_len=2000)
            if normalized:
                return normalized
    return None


def _extract_images(soup: BeautifulSoup, page_url: str) -> List[str]:
    """
    Collect product image URLs. Priority: ``<img itemprop="image">`` (hero) →
    every ``.thumb-swap[data-image]`` in gallery order → ``og:image``.
    Non-``/imagecache/`` assets (site logos, banners) are dropped; relative
    paths are resolved against ``page_url``.
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
        if _PRODUCT_IMAGE_PATH_PART not in u.lower():
            return
        if u in seen:
            return
        seen.add(u)
        ordered.append(u)

    hero = soup.find("img", attrs={"itemprop": "image"})
    if isinstance(hero, Tag):
        src = hero.get("src")
        if isinstance(src, str):
            add(src)

    for a in soup.find_all("a", class_="thumb-swap"):
        if not isinstance(a, Tag) or len(ordered) >= 12:
            break
        data_image = a.get("data-image")
        if isinstance(data_image, str):
            add(data_image)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    return ordered[:12]


class EssexPartsAdapter(RetailerCrawlerAdapter):
    """
    Essex Parts Services adapter. Discovery: flat ``/sitemap.xml`` urlset
    filtered to root-slug product URLs. Parsing: custom Laravel storefront —
    ``og:type=product`` guard, then ``.detail-section`` for name/brand/part,
    ``.product-price .price`` for price, ``.product-summary`` for description,
    and ``itemprop=image`` + ``.thumb-swap`` for images.
    """

    ADAPTER_NAME: ClassVar[str] = "essexparts"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Essex product page. Returns ``None`` for category/CMS pages
        (no ``og:type=product``) or when the product name cannot be recovered.
        """
        if not _is_product_url(url):
            return None
        soup = BeautifulSoup(html, "html.parser")
        if not _is_product_page(soup):
            return None

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        part_number = normalize_part_number(_extract_detail_field(soup, "Part #"))
        brand_raw = _extract_detail_field(soup, "Brand")
        part_manufacturer = _normalize_part_manufacturer(brand_raw)
        price_cents = _extract_price_cents(soup)
        description = _extract_description(soup)

        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(name)
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(name)

        image_urls = _extract_images(soup, url)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
        )
