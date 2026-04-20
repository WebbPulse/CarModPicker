"""
Full-Race Motorsports (full-race.com) crawler adapter.

Forced-induction specialist — turbo manifolds (bottom-mount K-series, Ecoboost),
drop-in turbo upgrades, wastegates, BOVs, and supporting hardware for Honda
K/L, Ford Ecoboost/Mustang, GM, and Mopar platforms. Anchors the FI vertical
in the catalog — their manifold pricing is the reference point for
bottom-mount builds.

Platform: Magento 2 (Staylime theme). Product URLs are root-level slugs
(``/tial-mvs-38mm-external-wastegate``,
``/garrett-gen-2-gtx3071r-evo-x-bolt-on-twin-scroll-turbo``) — not the
``/products/<handle>`` Shopify shape the rest of the adapters key off.
Category pages live under ``/store/...``.

Fetcher tier: ``http`` — plain ``requests`` with a Chrome UA clears nginx /
CloudFront cleanly; no TLS fingerprint or JS challenge.

Parsing: no JSON-LD on product pages. The parser keys off the Magento
``og:title`` / ``og:description`` / ``og:image`` / ``product:price:amount``
meta tags (emitted on every PDP) plus ``form[data-product-sku]`` for the
manufacturer MPN. Pages are sanity-checked for the ``catalog-product-view``
body class — CMS / category / landing URLs that slip through sitemap
discovery return None rather than polluting the catalog.

Images: the Staylime theme renders the product gallery client-side by
injecting ``<img>`` strings inside a ``$(...).html('<img …>')`` call, so
BeautifulSoup's ``<img>`` sweep only sees the hero (og:image) plus
related-product thumbs. We regex the raw HTML for
``/media/catalog/product/cache/<32-hex>/<path>`` URLs and dedup by the path
*after* the cache hash — Magento renders each responsive size at a distinct
hash, so the same asset appears 5–10 times otherwise. Brand-logo assets
(``_brand.(jpg|png)``) and related-product images outside the PDP scope are
filtered.

Brand: Full-Race resells multi-brand (TiAL, Garrett, BorgWarner-EFR, Precision,
MHI, AEM) alongside their own house-brand manifolds / flanges / vacuum kits.
No structured brand field — ``part_manufacturer_from_title`` picks up reseller
brands from the first token, and titles that lead with ``Full-Race`` /
``Full Race`` canonicalize to ``Full-Race`` so in-house SKUs don't orphan.

Discovery: ``/sitemap.xml`` is a single flat ``urlset`` (not a sitemap index).
Product URLs have a single-segment path and don't start with ``/store/``
(which is reserved for categories / sub-categories). The filter drops the
homepage, ``/store/*`` categories, multi-segment CMS / account / checkout
paths, and obvious non-product slugs (``about``, ``contact``, ``blog``, …);
the parser's body-class check catches anything that still slips through.
Override with ``CRAWLER_FULLRACE_START_URLS`` (comma-separated).
"""

import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_dom_price,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

FULLRACE_BASE = "https://www.full-race.com"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://www.full-race.com/tial-mvs-38mm-external-wastegate",
]

FULLRACE_HOUSE_BRAND = "Full-Race"

# Path prefixes that are definitionally not product pages. ``/store/`` is the
# category tree; the rest are Magento CMS / account / checkout surfaces that
# may show up in the sitemap alongside the flat root-level product slugs.
_NON_PRODUCT_PATH_PREFIXES = (
    "/store/",
    "/customer/",
    "/account/",
    "/checkout/",
    "/cart/",
    "/wishlist/",
    "/catalogsearch/",
    "/search/",
    "/contact/",
    "/contact-us",
    "/sales/",
    "/cms/",
    "/media/",
    "/pub/",
    "/static/",
    "/privacy",
    "/terms",
    "/returns",
    "/shipping",
    "/warranty",
    "/faq",
)

# Single-segment slugs that are CMS pages rather than products. Extend as the
# sitemap surfaces new ones; unknown CMS slugs that leak through still get
# rejected by the body-class check in ``parse_product_page``.
_NON_PRODUCT_EXACT_SLUGS = frozenset(
    {
        "about",
        "about-us",
        "brands",
        "bundles",
        "buttons",
        "catalog",
        "contact",
        "contact-us",
        "blog",
        "news",
        "press",
        "careers",
        "jobs",
        "team",
        "dealer-locator",
        "dealers",
        "fitment",
        "resources",
        "select-your-vehicle",
        "store",
        "support",
        "help",
        "faq",
        "faqs",
        "typography",
        "warranty",
        "returns",
        "shipping",
        "privacy",
        "privacy-policy",
        "terms",
        "terms-of-service",
        "sitemap",
    }
)

# Magento cache path — filename is ``/media/catalog/product/cache/<32-hex>/<asset-path>``.
# The 32-hex token is a size/fit cache key; the asset path is stable per image.
_MAGENTO_CACHE_IMG_RE = re.compile(
    r"https?://(?:www\.)?full-race\.com/media/catalog/product/cache/"
    r"(?P<hash>[a-f0-9]{16,64})/"
    r"(?P<path>[^\s\"'<>()]+?\.(?:jpg|jpeg|png|webp|gif))",
    re.IGNORECASE,
)

# Gallery-scoped image extraction: the Staylime theme renders the main
# product carousel by injecting ``<img class="default-picture">`` /
# ``class="large-picture"`` / ``class="product-gallery__midget"`` elements
# inside a ``<script>`` string literal. Related-product / recently-viewed
# carousels on the same page use ``class="product-image-photo"``, so a naive
# sweep of every catalog cache URL picks up T-shirt thumbs and other
# cross-sell assets. Matching ``class="..."`` + ``data-src="..."`` in the
# same tag keeps us scoped to the actual gallery.
_GALLERY_IMG_TAG_RE = re.compile(
    r"class=[\"']\s*(?:default-picture|large-picture|product-gallery__midget)\b"
    r"[^\"']*[\"'][^>]*?data-src=[\"'](?P<url>[^\"'<>\s]+)[\"']",
    re.IGNORECASE,
)

# Assets in the catalog cache that are still not product photography —
# brand-badge tiles and placeholders render into the main gallery but
# shouldn't end up in the catalog gallery.
_NON_PRODUCT_IMAGE_RE = re.compile(
    r"_brand\.|/brand[_/]|brand_logo|placeholder|/related[_/]|_thumb\.",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then default."""
    raw = os.environ.get("CRAWLER_FULLRACE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap urlset."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` looks like a Full-Race product page.

    Product URLs are root-level single-segment slugs
    (``/garrett-gt3582r``). Category URLs sit under ``/store/...``; CMS pages
    either share one of the ``_NON_PRODUCT_PATH_PREFIXES`` or match a known
    exact slug.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not host.endswith("full-race.com"):
        return False
    path = parsed.path or ""
    if not path or path == "/":
        return False
    for prefix in _NON_PRODUCT_PATH_PREFIXES:
        if path.startswith(prefix):
            return False
    trimmed = path.strip("/")
    if not trimmed or "/" in trimmed:
        return False
    if trimmed.lower() in _NON_PRODUCT_EXACT_SLUGS:
        return False
    return True


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (single urlset — Full-Race does not emit an index)
    and collect every product-shaped URL. Returns a deduplicated list
    keyed by path, or empty on failure.
    """
    seen: set[str] = set()
    product_urls: List[str] = []
    try:
        sitemap_text = fetch_page(FULLRACE_BASE + "/sitemap.xml", timeout=30)
        root = ET.fromstring(sitemap_text)
    except Exception:
        return []
    for loc in _loc_elements(root):
        if not loc.text:
            continue
        url = loc.text.strip()
        if not url or not _is_product_url(url):
            continue
        base = url.split("?")[0]
        if base in seen:
            continue
        seen.add(base)
        product_urls.append(base)
    return product_urls


def _canonical_image_path(url: str) -> Optional[str]:
    """
    Return the stable post-cache-hash portion of a Magento cache URL, or None
    when the URL isn't a product image or matches the non-product noise list.
    Used as a dedupe key so different responsive sizes of the same asset
    collapse to one entry.
    """
    match = _MAGENTO_CACHE_IMG_RE.search(url)
    if not match:
        return None
    asset_path = match.group("path")
    if _NON_PRODUCT_IMAGE_RE.search(asset_path):
        return None
    return asset_path.lower()


def _extract_gallery_images(html: str, soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery URLs scoped to the main product carousel.

    Main gallery images are injected inside a ``<script>`` string literal as
    ``<img class="(default|large)-picture" data-src="…">`` /
    ``class="product-gallery__midget"`` tags — BS4 doesn't see them since
    they're script text. Related-product and recently-viewed widgets on the
    same page also render ``/media/catalog/product/cache/…`` URLs but use a
    different class (``product-image-photo``), so we match ``class="…" +
    data-src="…"`` pairs rather than sweeping every cache URL. og:image is
    added first so the hero leads regardless of gallery class order.
    """
    ordered: List[str] = []
    seen_paths: set[str] = set()

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        canonical = _canonical_image_path(raw)
        if canonical is None or canonical in seen_paths:
            return
        seen_paths.add(canonical)
        normalized = raw.strip()
        if normalized.startswith("//"):
            normalized = "https:" + normalized
        elif normalized.startswith("http://"):
            normalized = "https://" + normalized[len("http://") :]
        ordered.append(normalized)

    og = soup.find("meta", property="og:image") or soup.find("meta", property="og:image:secure_url")
    if isinstance(og, Tag):
        content = meta_content(og)
        if content:
            add(content.strip())

    for match in _GALLERY_IMG_TAG_RE.finditer(html):
        add(match.group("url"))
        if len(ordered) >= 12:
            break

    return ordered


def _is_product_page(soup: BeautifulSoup) -> bool:
    """
    Sanity check that we're looking at an actual PDP. Magento emits
    ``catalog-product-view`` on the body tag of every product page; CMS /
    category / account pages don't.
    """
    for element_name in ("body", "html"):
        tag = soup.find(element_name)
        if not isinstance(tag, Tag):
            continue
        classes = tag.get("class")
        if isinstance(classes, list) and "catalog-product-view" in classes:
            return True
        if isinstance(classes, str) and "catalog-product-view" in classes.split():
            return True
    return False


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Prefer ``og:title``; fall back to ``h1.page-title > span.base``."""
    og = soup.find("meta", property="og:title")
    if isinstance(og, Tag):
        content = meta_content(og)
        if content and content.strip():
            return content.strip()
    span = soup.select_one("h1.page-title span.base")
    if isinstance(span, Tag):
        text = span.get_text(strip=True)
        if text:
            return text
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Full product description lives under ``#details`` on the Staylime theme;
    short description sits in ``.product__short-description``; og:description
    and the bare ``<meta name="description">`` are last-ditch fallbacks.
    """
    details = soup.find(id="details")
    if isinstance(details, Tag):
        text = details.get_text(" ", strip=True)
        if text and len(text) >= 20:
            return normalize_description_text(text, max_len=2000)

    short = soup.select_one(".product__short-description")
    if isinstance(short, Tag):
        text = short.get_text(" ", strip=True)
        if text and len(text) >= 10:
            return normalize_description_text(text, max_len=2000)

    for selector in (
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "description"}),
    ):
        tag = soup.find(*selector)
        if isinstance(tag, Tag):
            content = meta_content(tag)
            if content and content.strip():
                return normalize_description_text(content, max_len=2000)
    return None


def _extract_sku(soup: BeautifulSoup) -> Optional[str]:
    """
    Manufacturer MPN lives in ``form[data-product-sku]`` (the add-to-cart
    form) and is mirrored in the ``.hero__sku`` label. The form attribute is
    the cleanest source — no "SKU  " prefix to strip.
    """
    form = soup.find("form", attrs={"data-product-sku": True})
    if isinstance(form, Tag):
        sku = form.get("data-product-sku")
        if isinstance(sku, str) and sku.strip():
            return normalize_part_number(sku)
    hero = soup.select_one(".hero__sku")
    if isinstance(hero, Tag):
        text = hero.get_text(" ", strip=True)
        if text:
            cleaned = re.sub(r"^\s*SKU\s*:?\s*", "", text, flags=re.IGNORECASE)
            if cleaned:
                return normalize_part_number(cleaned)
    return None


def _resolve_part_manufacturer(title: str, description: Optional[str]) -> Optional[str]:
    """
    Pick the part manufacturer from title tokens, with description fallback,
    and canonicalize Full-Race's house brand. Reseller SKUs (TiAL, Garrett,
    BorgWarner, Precision, MHI, AEM) keep their own identity via the shared
    first-token heuristic.
    """
    if re.match(r"^\s*full[\s-]race\b", title, re.IGNORECASE):
        return FULLRACE_HOUSE_BRAND
    brand = part_manufacturer_from_title(title)
    if brand and brand.lower().rstrip("-").startswith("full"):
        # "Full" alone or "Full-Race" → canonical house brand.
        if re.match(r"^full[\s-]?race$", brand, re.IGNORECASE) or brand.lower() == "full":
            return FULLRACE_HOUSE_BRAND
    if brand:
        return brand
    if description:
        brand = part_manufacturer_from_description(description, product_name=title)
        if brand:
            return brand
    return part_manufacturer_fallback_from_title(title)


class FullRaceAdapter(RetailerCrawlerAdapter):
    """
    Full-Race Motorsports adapter. Discovery via the flat ``/sitemap.xml``
    urlset (Magento's single-level sitemap, not a Shopify-style index).
    Parsing keys off og: + product: meta tags, the ``form[data-product-sku]``
    MPN attribute, and the ``#details`` description block; the gallery is
    regex-swept out of the raw HTML because the Staylime theme builds the
    carousel client-side.
    """

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Full-Race product page into a ``ScrapedPayload``. Returns
        ``None`` when the page is missing the Magento product body class
        (CMS / category / account pages the sitemap filter may let through)
        or when no title can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        if not _is_product_page(soup):
            return None

        title = _extract_title(soup)
        if not title or len(title) < 3:
            return None

        description = _extract_description(soup)
        price_cents = extract_dom_price(soup)
        part_number = _extract_sku(soup)
        part_manufacturer = _resolve_part_manufacturer(title, description)
        image_urls = _extract_gallery_images(html, soup)

        return ScrapedPayload(
            name=title,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
