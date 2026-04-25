"""
Girodisc (girodisc.com) crawler adapter.

Girodisc is the US manufacturer of two-piece, fully-floating brake rotors — the
reference rotor line for the track/HPDE segment across BMW M, Porsche,
Corvette, GT-R, Evo, STI, GR Supra, and Civic Type R. Pairs with Essex
(AP Racing calipers/pads) to price a full track brake package.

Site platform: **BigCommerce Stencil**. No JSON-LD Product is emitted. Product
pages are tagged with ``<meta property="og:type" content="product">`` and
carry a populated ``window.BCData.product_attributes`` blob; the shared
DOM has predictable ``productView-*`` classes.

Discovery: sitemap index at ``/xmlsitemap.php`` → ``?type=products&page=N``
child urlsets. ``type=pages`` / ``type=categories`` children are skipped —
product URLs live only under ``type=products``. Override with
``CRAWLER_GIRODISC_START_URLS`` (comma-separated) for a fixed list.

Product URL shape: root-slug, e.g.
``https://girodisc.com/corvette-c8-z06-front-rotors/``.

Parsing: ``og:type=product`` guard, then DOM extraction —
``h1.productView-title[itemprop="name"]`` for the name, the
``[data-product-sku]`` DD for the SKU, ``[data-product-price-without-tax]``
for the price, ``div[itemprop="description"]`` for the description, and the
``section.productView-images`` gallery (``data-zoom-image`` + thumbnail
``data-image-gallery-zoom-image-url`` attrs) for the image list. ``og:image``
is a last-ditch hero source.

Brand policy: Girodisc is a single-brand manufacturer shop (every rotor,
caliper rebuild kit, and pad set is their own), so ``part_manufacturer``
always defaults to ``"Girodisc"``.
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

GIRODISC_BASE = "https://girodisc.com"
SITEMAP_INDEX_URL = GIRODISC_BASE + "/xmlsitemap.php"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# First-party manufacturer store — every SKU is branded Girodisc.
GIRODISC_BRAND = "Girodisc"

DEFAULT_START_URLS = [
    "https://girodisc.com/corvette-c8-z06-front-rotors/",
]

# Only the ``type=products`` child sitemaps list product URLs; ``type=pages``
# and ``type=categories`` are CMS / category noise. Matches against the raw
# query-string (no leading ``?``), so ``type`` may be first or later param.
_PRODUCT_SITEMAP_QUERY_RE = re.compile(r"(^|&)type=products\b", re.IGNORECASE)

# BigCommerce Stencil CDN path marker — all real product images live under
# the per-store CDN. Used to drop theme chrome (loading.svg, payment icons,
# shared stencil sprites) that would otherwise leak in from the gallery scope.
_BIGCOMMERCE_PRODUCT_IMAGE_PATH_PART = "/images/stencil/"
_BIGCOMMERCE_PRODUCT_IMAGE_HOST = "cdn11.bigcommerce.com"

# Theme-chrome assets inside the product CDN that must not be mistaken for
# product imagery (loading placeholder, mega-menu icons, favicons).
_NON_PRODUCT_MEDIA_RE = re.compile(
    r"/loading\.svg|/logo[/_-]|favicon|sprite|placeholder",
    re.IGNORECASE,
)

# First-path segments that are definitely not products (cart/admin flow plus
# the BigCommerce collection pages that render category grids at the same
# root-slug level as products).
_NON_PRODUCT_PATH_PREFIXES = frozenset(
    {
        "about-us",
        "big-brake-kit-parts",
        "brake-caliper-rebuild-kits",
        "brake-pads",
        "brakefluid",
        "caliper-rebuild-kits",
        "careers",
        "cart.php",
        "categories",
        "checkout.php",
        "contact-us",
        "dealers",
        "dust-boots",
        "front-rotors",
        "login.php",
        "piston-seals",
        "rear-rotors",
        "replacement-rings",
        "search.php",
        "sitemap",
        "technical-info",
        "titanium-pad-shields",
        "tools",
    }
)


def _is_product_url(url: str) -> bool:
    """
    Cheap pre-parse filter: ``url`` is on the Girodisc host, is a single
    root-slug path (products are all top-level), and doesn't match a known
    non-product first segment. ``parse_product_page`` remains the final
    authority via the ``og:type=product`` guard.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host != "girodisc.com" and host != "www.girodisc.com":
        return False
    path = parsed.path.strip("/").lower()
    if not path:
        return False
    first = path.split("/", 1)[0]
    if first in _NON_PRODUCT_PATH_PREFIXES:
        return False
    if first.endswith(".php"):
        return False
    return True


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then default."""
    raw = os.environ.get("CRAWLER_GIRODISC_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Girodisc ``?type=products`` urlset child."""
    try:
        query = urlparse(url).query or ""
    except ValueError:
        return False
    return bool(_PRODUCT_SITEMAP_QUERY_RE.search(query))


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/xmlsitemap.php`` (sitemap index) → each ``?type=products&page=N``
    urlset and collect every product URL. Skips ``type=pages`` /
    ``type=categories`` children. Returns deduplicated list (keyed by bare
    URL, query stripped); empty on failure.
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
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _is_product_page(soup: BeautifulSoup) -> bool:
    """
    Girodisc tags product pages with ``og:type=product``; category pages omit
    the tag. Presence of ``[data-product-sku]`` is a defensive second check.
    """
    og_type = soup.find("meta", property="og:type")
    if isinstance(og_type, Tag) and (meta_content(og_type) or "").strip().lower() == "product":
        return True
    return soup.find(attrs={"data-product-sku": True}) is not None


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Product name from ``h1.productView-title`` first (the in-page heading), then
    ``og:title`` (site strips ``" - <sku> - GiroDisc"`` suffix on the OG tag,
    so it's clean). Plain ``<h1>`` is the final fallback.
    """
    h1 = soup.select_one("h1.productView-title")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            return content.strip()

    h1_any = soup.find("h1")
    if isinstance(h1_any, Tag):
        text = h1_any.get_text(strip=True)
        if text:
            return text
    return None


def _extract_sku(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull the SKU from ``<dd ... data-product-sku itemprop="sku">A1-319</dd>``.
    """
    node = soup.find(attrs={"data-product-sku": True})
    if isinstance(node, Tag):
        text = node.get_text(strip=True)
        if text:
            return normalize_part_number(text)
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    Read the main product price from
    ``<span data-product-price-without-tax>$1,550.00</span>``. Fall back to
    ``product:price:amount`` meta (BigCommerce emits whole-dollar values
    here, e.g. ``content="1550"`` for $1,550) when the DOM span is absent —
    ``parse_price_cents`` treats the number as dollars regardless.

    We must NOT fall back to the first ``$`` in body text: the BigCommerce
    "Related Products" grid renders full product cards with prices below the
    main block and would beat a naive scan.
    """
    node = soup.find(attrs={"data-product-price-without-tax": True})
    if isinstance(node, Tag):
        cents = parse_price_cents(node.get_text(strip=True))
        if cents is not None:
            return cents

    meta = soup.find("meta", property="product:price:amount")
    if isinstance(meta, Tag):
        content = meta_content(meta)
        if content:
            cents = parse_price_cents(content)
            if cents is not None:
                return cents
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Pull the full product description from ``<div itemprop="description">``
    (scoped to the ``#accordion--description`` body on Girodisc). Fall back to
    ``og:description`` only as a last resort — the OG description is a
    site-wide default ("We design, manufacture, and sell 2-piece, fully-floating
    brake rotors…") and is identical across every product page, so it's
    useless for catalog copy when the itemprop block is present.
    """
    node = soup.find(attrs={"itemprop": "description"})
    if isinstance(node, Tag):
        text = node.get_text(" ", strip=True)
        normalized = normalize_description_text(text, max_len=2000)
        if normalized:
            return normalized

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        content = meta_content(og_desc)
        if content:
            return normalize_description_text(content, max_len=2000)
    return None


def _canonical_image_url(src: str, page_url: str) -> Optional[str]:
    """
    Normalize a product-image URL. Resolves protocol-relative and relative
    paths against ``page_url``, rejects non-BigCommerce hosts, and filters
    theme chrome (loading placeholder, sprite, favicon).
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = urljoin(page_url, s)
    if not s.startswith("http"):
        return None
    try:
        parsed = urlparse(s)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if _BIGCOMMERCE_PRODUCT_IMAGE_HOST not in host:
        return None
    if _BIGCOMMERCE_PRODUCT_IMAGE_PATH_PART not in parsed.path:
        return None
    if _NON_PRODUCT_MEDIA_RE.search(s):
        return None
    return s


def _extract_images(soup: BeautifulSoup, page_url: str) -> List[str]:
    """
    Gather product gallery images. Priority: main figure's ``data-zoom-image``
    (full-res hero) → each thumbnail's ``data-image-gallery-zoom-image-url`` →
    ``og:image`` (hero fallback when the gallery scope is missing). Dedupes by
    URL, caps at 12.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        canonical = _canonical_image_url(raw, page_url)
        if not canonical or canonical in seen:
            return
        seen.add(canonical)
        ordered.append(canonical)

    gallery = soup.select_one("section.productView-images")
    if isinstance(gallery, Tag):
        main = gallery.find("figure", attrs={"data-image-gallery-main": True})
        if isinstance(main, Tag):
            zoom = main.get("data-zoom-image")
            if isinstance(zoom, str):
                add(zoom)

        for thumb in gallery.find_all(attrs={"data-image-gallery-zoom-image-url": True}):
            if not isinstance(thumb, Tag) or len(ordered) >= 12:
                break
            url = thumb.get("data-image-gallery-zoom-image-url")
            if isinstance(url, str):
                add(url)

    if not ordered:
        og_img = soup.find("meta", property="og:image")
        if isinstance(og_img, Tag):
            add(meta_content(og_img))

    return ordered[:12]


class GirodiscAdapter(RetailerCrawlerAdapter):
    """
    Girodisc adapter. Discovery: ``/xmlsitemap.php`` index → ``?type=products``
    urlset children. Parsing: DOM-only (no JSON-LD on this storefront) — name
    from ``h1.productView-title``, SKU from ``[data-product-sku]``, price from
    ``[data-product-price-without-tax]``, description from
    ``[itemprop=description]``, images from ``section.productView-images``.
    Brand is always ``"Girodisc"`` (single-brand manufacturer store).
    """

    ADAPTER_NAME: ClassVar[str] = "girodisc"
    category_targets: ClassVar[list[str]] = ["brake", "universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Girodisc product page. Returns ``None`` for category / CMS
        pages (missing ``og:type=product``) or when the product name cannot
        be recovered.
        """
        soup = BeautifulSoup(html, "html.parser")
        if not _is_product_page(soup):
            return None

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        part_number = _extract_sku(soup)
        price_cents = _extract_price_cents(soup)
        description = _extract_description(soup)
        image_urls = _extract_images(soup, url)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=GIRODISC_BRAND,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
