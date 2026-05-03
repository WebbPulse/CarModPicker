"""
ADRO (adro.com) crawler adapter.

Product URLs: https://adro.com/products/<handle>
Uses JSON-LD first (Shopify Product schema), then DOM fallbacks for rare pages
that lack it. Image extraction is scoped to the product media gallery; other
images (site nav, mega-menu, related-product thumbnails) are rejected.

Discovery: sitemap.xml (and child sitemaps) to find all /products/ URLs.
`-full-kit` URLs are excluded because they're bundle/category landing pages
(no SKU, price 0.00, a product picker listing individual sub-products).
Override with CRAWLER_ADRO_START_URLS (comma-separated) to use a fixed list.

Brand: ADRO lists itself as vendor for everything (JSON-LD brand = "ADRO USA").
When JSON-LD brand is empty OR the title heuristic picked a car make, we force
"ADRO". The "NOT FOR EVERYBODY" collab is whitelisted to "Not For Everybody".
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
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

ADRO_BASE = "https://adro.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://adro.com/products/bmw-g82-m4-at-r3-swan-neck-wing-with-flat-endplates",
]

# URL handles that are bundle/category landing pages, not real products.
_BUNDLE_HANDLE_SUFFIXES = ("-full-kit",)

# Vendor values (JSON-LD brand or title first-token) that should be replaced
# with "ADRO" because they indicate the target vehicle, not a part manufacturer.
_CAR_MAKES = frozenset(
    {
        "bmw",
        "porsche",
        "toyota",
        "honda",
        "lexus",
        "subaru",
        "nissan",
        "audi",
        "mercedes",
        "mercedes-benz",
        "ford",
        "chevrolet",
        "chevy",
        "tesla",
        "hyundai",
        "kia",
        "genesis",
    }
)

# Tokens that the fallback title heuristic sometimes picks as brand but are not
# manufacturers. "NOT" comes from "NOT FOR EVERYBODY"; "AERO" is ADRO's internal
# aero program name from the "AERO PROGRAM DECAL" title, not a third-party brand.
_BRAND_REJECT_TOKENS = frozenset({"not", "the", "new", "aero"})

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg, file_100x100.webp).
# Stripped / rejected so we prefer full-resolution product media over the
# thumbnails Shopify renders for the sidebar picker and related products.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (not product gallery).
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|adro\.svg|header_|footer_|megamenu|placeholder",
    re.IGNORECASE,
)

# HTML markers where the main product block ends and related-product /
# recommendations / picker content begins. Used to bound DOM scraping and
# image extraction on pages that put picker thumbnails below the gallery.
_HTML_CUTOFF_MARKERS = (
    "learnmore__content",
    "learnmore__product-description",
    "product__learn-more",
    "product-recommendations",
    "product__picker-product",
    "customers also bought",
    "you may also like",
    "related products",
)


def _is_bundle_url(url: str) -> bool:
    """True if the URL path is a known bundle/category landing pattern."""
    try:
        path = urlparse(url).path.lower()
    except ValueError:
        return False
    return any(path.endswith(suffix) for suffix in _BUNDLE_HANDLE_SUFFIXES)


def _is_bundle_page(soup: BeautifulSoup) -> bool:
    """
    DOM-level bundle detection: ADRO's picker renders multiple sub-product
    titles under `product__picker-product__title`. More than one means this
    page is a kit/bundle listing, not a single purchasable part.
    """
    picker_titles = soup.select(".product__picker-product__title")
    return len(picker_titles) >= 2


def _json_ld_offer_price_is_zero(item: dict) -> bool:
    """
    True if the JSON-LD Product's offers block explicitly sets price to 0.

    ``_price_from_json_ld`` collapses 0 and "missing" into the same None, so we inspect
    the raw dict here — a literal 0.00 means Shopify rendered a bundle/picker landing
    page, while an absent price could just be a back-ordered real product we want to keep.
    """
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else None
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = None
    if not isinstance(offer, dict):
        return False
    for key in ("price", "lowPrice"):
        raw = offer.get(key)
        if raw is None:
            continue
        try:
            return float(str(raw).replace(",", "")) == 0.0
        except (ValueError, TypeError):
            continue
    return False


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> str:
    """
    Return the canonical manufacturer for an ADRO product.

    - Empty / car-make / reject-token brands / ADRO name variants -> "ADRO".
    - "NOT FOR EVERYBODY" decals/apparel are ADRO-branded collabs sold under the
      ADRO storefront; they previously got their own "Not For Everybody" row, but
      that just split ADRO into two manufacturers. Collapse to "ADRO".
    - Everything else (CSF, JQ Werks, GoldenWrench, …) is passed through so third
      parties sold through ADRO keep their own identities.

    product_name is unused today but kept in the signature so callers don't change
    when we need title-level overrides again in the future.
    """
    _ = product_name
    brand = (part_manufacturer or "").strip()
    if not brand:
        return "ADRO"
    low = brand.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return "ADRO"
    # ADRO's own vendor string on Shopify has historically been "ADRO", "ADRO US",
    # "ADRO USA" — all the same brand. Collapse any "adro …" prefix.
    if low == "adro" or low.startswith("adro ") or low.startswith("adro-"):
        return "ADRO"
    return brand


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_ADRO_START_URLS is set, return that list. Else discover via sitemap (or fallback)."""
    raw = os.environ.get("CRAWLER_ADRO_START_URLS", "").strip()
    if raw:
        urls = [u.strip() for u in raw.split(",") if u.strip()]
    else:
        urls = _discover_product_urls_via_sitemap() or list(DEFAULT_START_URLS)
    return [u for u in urls if not _is_bundle_url(u)]


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch sitemap.xml (and child sitemaps if index), collect all <loc> URLs
    that contain /products/. Returns deduplicated list (by path); empty on failure.
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
            product_urls.append(u)

    try:
        index_url = ADRO_BASE + "/sitemap.xml"
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


def _cut_html_before_related(raw_html: str) -> str:
    """Truncate HTML at the earliest related-products/picker/learnmore marker."""
    if not raw_html:
        return raw_html
    lower = raw_html.lower()
    cut = len(raw_html)
    for marker in _HTML_CUTOFF_MARKERS:
        pos = lower.find(marker)
        if pos >= 0 and pos < cut:
            cut = pos
    return raw_html[:cut]


def _is_inside_noise_block(tag: Tag) -> bool:
    """True if any ancestor has a class marking it as learnmore/picker/recommendations."""
    for anc in tag.parents:
        if not isinstance(anc, Tag):
            continue
        classes = anc.get("class") or []
        if not isinstance(classes, list):
            classes = [str(classes)]
        joined = " ".join(classes)
        if "learnmore__" in joined or "product__picker" in joined or "product-recommendations" in joined:
            return True
    return False


def _extract_full_description_from_dom(soup: BeautifulSoup, max_len: int = 2000) -> Optional[str]:
    """
    DOM description fallback for the rare page with no JSON-LD description.

    Strict allowlist of selectors (so we don't match `learnmore__product-description`
    via a wildcard), and we reject matches that live inside a learnmore/picker
    block. Takes the FIRST match in DOM order (the main product block is always
    above related content on Shopify themes), not the longest.
    """
    for selector in (
        "div.product__description",
        "div.product-single__description",
        "#product-description",
    ):
        for elem in soup.select(selector):
            if not isinstance(elem, Tag):
                continue
            if _is_inside_noise_block(elem):
                continue
            text = elem.get_text(separator=" ", strip=True)
            if text and len(text) > 80:
                return normalize_description_text(text, max_len=max_len)
    # Fallback: first long <p> before the related-products cutoff.
    for p in soup.find_all("p"):
        if not isinstance(p, Tag) or _is_inside_noise_block(p):
            continue
        t = p.get_text(strip=True)
        if t and len(t) > 150:
            return normalize_description_text(t, max_len=max_len)
    return None


def _canonical_image_key(url: str) -> str:
    """Key for dedupe: drop Shopify's v/width/height/crop params so width variants collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=\w+", "", url)
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
    """Upgrade // or http:// to https://; resolve absolute paths against adro.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return ADRO_BASE + u
    return u


def _extract_adro_images(soup: BeautifulSoup, raw_html: str) -> List[str]:
    """
    Product gallery images only.

    Sources (in order): og:image, <media-gallery>, .product__media-wrapper.
    All candidates run through Shopify-CDN allowlist + noise/thumbnail filter,
    are upgraded to https, and deduped by canonical URL (ignoring v/width query
    params). Capped at 12.
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

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        wrapper = soup.select_one(".product__media-wrapper")
        if isinstance(wrapper, Tag):
            scope = wrapper

    if scope is not None:
        for img in scope.find_all("img", src=True):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())
    else:
        # Very rare: no media-gallery / wrapper. Fall back to any <img> in the
        # HTML before related-product markers; filters still reject noise.
        cut_soup = BeautifulSoup(_cut_html_before_related(raw_html), "html.parser")
        for img in cut_soup.find_all("img", src=True):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())

    return ordered[:12]


class AdroAdapter(RetailerCrawlerAdapter):
    """
    ADRO adapter. Discovery: start URLs from env or sitemap, minus bundles.
    Parsing: JSON-LD first, then DOM fallback. Brand normalized to ADRO /
    Not For Everybody / JSON-LD value. Bundle pages rejected outright.
    """

    ADAPTER_NAME: ClassVar[str] = "adro"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield real product URLs from sitemap.xml (minus bundle pages). Set
        CRAWLER_ADRO_START_URLS (comma-separated) to override with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an ADRO product page. Returns None for bundle/kit pages (detected
        by URL, by the DOM-level product picker, and by a 0-price JSON-LD payload
        which Shopify emits for category-style picker landing pages).
        """
        if _is_bundle_url(url):
            return None
        soup = BeautifulSoup(html, "html.parser")
        if _is_bundle_page(soup):
            return None

        dom_images = _extract_adro_images(soup, html)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD (authoritative on Shopify): name, description, brand, sku, price, image.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            # Shopify emits price=0.00 for picker/bundle landing pages that have no
            # SKU of their own (sub-products are priced). Real ADRO products are all
            # > $0, so a hard 0 in JSON-LD is a bundle flag. We check the raw item
            # because _price_from_json_ld returns None for both 0 and missing.
            if _json_ld_offer_price_is_zero(item) and dom_price in (None, 0):
                return None
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                # Trust JSON-LD description when it's substantive; only fall
                # back to DOM when JSON-LD omits a usable description.
                description = payload.description
                if not description or len(description) < 50:
                    dom_desc = _extract_full_description_from_dom(soup)
                    if dom_desc and len(dom_desc) > len(description or ""):
                        description = dom_desc
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                return ScrapedPayload(
                    name=payload.name,
                    product_url=payload.product_url,
                    description=description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. DOM fallback: og:meta, h1, description, price, SKU, brand, images.
        name = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if h1:
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
        if not name or len(name) < 3:
            return None

        description = _extract_full_description_from_dom(soup)
        if not description:
            og_desc = soup.find("meta", property="og:description")
            if isinstance(og_desc, Tag):
                d = meta_content(og_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000) or d.strip()[:2000]
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000) or d.strip()[:2000]

        price_cents = extract_dom_price(soup)
        part_number = extract_sku_from_text(soup.get_text())
        # Shape guard: ADRO's Shopify template renders ``SKU:`` as a label even
        # for variants whose actual SKU is null. Without a value attached, the
        # body-text scan grabs the next visible token — typically the variant
        # dropdown label ("CHASSIS MODEL" → captured as "CHASSIS"). Reject
        # pure-alpha captures: ADRO's real internal SKUs are alphanumeric
        # mixes ("FXXCCT", "FXXFCC") that always contain digits or hyphens.
        # See MEMORY: feedback_pn_extract_label_leakage.md.
        if part_number and part_number.isalpha():
            part_number = None
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if sku_elem:
                candidate = normalize_part_number(sku_elem.get_text(strip=True))
                # Same shape guard for the sku_elem path: an empty SKU element
                # like ``<p class="product__sku">SKU:</p>`` normalizes to
                # "SKU" — pure-alpha junk per the same reasoning.
                if candidate and not candidate.isalpha():
                    part_number = candidate
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer, str(name))

        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
        )
