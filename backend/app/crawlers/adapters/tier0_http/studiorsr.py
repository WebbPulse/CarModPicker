"""
Studio RSR (studiorsr.com) crawler adapter.

Product URLs: https://studiorsr.com/products/<handle>?...
Uses JSON-LD first (Shopify often exposes Product schema), then shared DOM fallbacks:
og:meta, h1, extract_dom_price, part_manufacturer_from_title, og:image.

Discovery: sitemap.xml (and child sitemaps) to find all /products/ URLs.
Override with CRAWLER_STUDIORSR_START_URLS (comma-separated) to use a fixed list.
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

STUDIORSR_BASE = "https://studiorsr.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

DEFAULT_START_URLS = [
    "https://studiorsr.com/products/studiorsr-gr86-roll-cage-roll-bar",
]


def _is_product_url(url: str) -> bool:
    """True only for canonical Shopify ``/products/<handle>`` pages.

    StudioRSR's Shopify storefront also serves ``/collections/<vendor>``
    landing pages (Lamborghini, Mercedes-Benz, Porsche). Those pages render an
    og:title of just the vendor name (``"Lamborghini"``) and a "Recently
    viewed" widget that gets picked up as a SKU — so when they leak through
    into the parser they end up as nonsense rows like ``name="Lamborghini"
    part_number="Recently"``. Gate strictly on ``/products/<handle>`` to keep
    them out of the catalog. Collection pages with a nested
    ``/collections/<vendor>/products/<handle>`` shape stay accepted because
    Shopify renders the same product data on either path.
    """
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return False
    return PRODUCT_PAGE_PATH in path


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> Optional[str]:
    """
    Normalize retailer-specific part_manufacturer shorthand to full name (e.g. JSON-LD may give "Rogue").
    """
    if not part_manufacturer:
        return part_manufacturer
    b = part_manufacturer.strip()
    if b == "Rogue" or (b.lower() == "rogue" and re.search(r"\bRogue\s+Engineering\b", product_name, re.IGNORECASE)):
        return "Rogue Engineering"
    if b == "Radium" or (b.lower() == "radium" and re.search(r"\bRadium\s+Engineering\b", product_name, re.IGNORECASE)):
        return "Radium Engineering"
    return part_manufacturer


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_STUDIORSR_START_URLS is set, return that list. Else discover via sitemap (or fallback)."""
    raw = os.environ.get("CRAWLER_STUDIORSR_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


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
        index_url = STUDIORSR_BASE + "/sitemap.xml"
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


# Leading boilerplate on StudioRSR product pages (shipping promo, contact CTA) to strip from descriptions.
_STUDIORSR_DESCRIPTION_BOILERPLATE = re.compile(
    r"^(?:\s*FREE\s+GROUND\s+SHIPPING\s*"
    r"ORDER\s+NOW\s+and\s+get\s+FREE\s+Ground\s+shipping[\s\S]*?\.\s*"
    r"(?:Contact\s+us\s+Directly\s+for\s+NEWEST\s+and\s+BEST\s+PRICING\.?\s*)?"
    r"(?:Chat\s+Below\s*)?"
    r"(?:email:\s*info@studiorsr\.com\s*)?"
    r"(?:call:\s*1-657-549-0195\s*)?\s*)+",
    re.IGNORECASE | re.DOTALL,
)


def _strip_studiorsr_boilerplate(description: Optional[str]) -> Optional[str]:
    """Remove leading StudioRSR promo/contact boilerplate from description text."""
    if not description or not description.strip():
        return description
    s = _STUDIORSR_DESCRIPTION_BOILERPLATE.sub("", description.strip(), count=1)
    return s.strip() or description.strip()


def _extract_full_description_from_dom(soup: BeautifulSoup, max_len: int = 2000) -> Optional[str]:
    """
    Prefer main product description from DOM (Shopify: product form description, .rte, etc.)
    over meta/og which are often truncated. Returns plain text, normalized and length-capped.
    """
    # Shopify themes: product description is often in a div with class containing description/rte
    candidates: List[str] = []
    for selector in (
        "[class*='product__description']",
        "[class*='product-single__description']",
        ".product-description",
        "#product-description",
        "[class*='rte']",
    ):
        for elem in soup.select(selector):
            if not isinstance(elem, Tag):
                continue
            text = elem.get_text(separator=" ", strip=True)
            if text and len(text) > 150:
                candidates.append(text)
    # Also first long paragraph(s) in main content
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main:
        for p in main.find_all("p") if isinstance(main, Tag) else []:
            if not isinstance(p, Tag):
                continue
            t = p.get_text(strip=True)
            if t and len(t) > 150:
                candidates.append(t)
    if not candidates:
        return None
    # Prefer longest reasonable block (full description)
    best = max(candidates, key=len)
    normalized = normalize_description_text(best, max_len=max_len)
    return _strip_studiorsr_boilerplate(normalized) if normalized else None


# Shopify lazy-loader theme assets and brand chrome that should NEVER be
# treated as product images. The theme leaves ``<img src=...>`` pointing at a
# spinner SVG (``loading.svg``) until the lazy-loader hydrates the real
# product image into ``data-src``/``data-srcset`` — so reading ``src`` first
# was capturing the spinner placeholder. Header/footer assets under
# ``/cdn/shop/t/<theme-id>/assets/`` (logos, icons, etc.) are also chrome.
#
# Also deny well-known footer/badge filenames under ``/cdn/shop/files/``:
# - ``security-N.png`` and ``payment-N.png`` (trust badges; previously appeared
#   on 500-780 distinct parts each, since they're rendered in the footer of
#   every product page and pass the "studiorsr.com host + /cdn/shop/files/"
#   filter)
# - ``socialshare_*`` (open-graph share asset)
# - ``logo-studiorsr*``, ``studiorsr_dark*`` (storefront logos)
# - ``header_N_*``, ``sidebar*`` (theme banners)
_STUDIORSR_IMAGE_DENY_RE = re.compile(
    r"/cdn/shop/t/[^/]+/assets/|loading\.svg|\.svg(?:$|\?)"
    r"|/cdn/shop/files/(?:security-|payment-[0-9]|socialshare_|studiorsr_dark|logo-studiorsr|header_[0-9]|sidebar)",
    re.IGNORECASE,
)

# Real product images live on the Shopify CDN under
# ``/cdn/shop/products/`` or ``/cdn/shop/files/`` on the studiorsr.com host.
_STUDIORSR_PRODUCT_IMAGE_PATH_RE = re.compile(
    r"/cdn/shop/(?:products|files)/",
    re.IGNORECASE,
)


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product image URLs from the Shopify-themed product page.

    Read order: ``data-src`` then ``data-srcset`` then ``src``. Shopify's lazy-
    loader leaves ``src`` set to a spinner SVG (``loading.svg``) until the
    real image is hydrated into ``data-src`` — so reading ``src`` first
    captured ~790 spinner placeholders as "product images" across the
    catalog.

    Filters: deny theme/asset paths (``/cdn/shop/t/.*/assets/``), logo
    chrome (``studiorsr_dark``, ``loading.svg``), and any ``.svg``
    extension. Constrain to ``studiorsr.com`` paths matching
    ``/cdn/shop/(products|files)/`` so anything else is dropped.
    Force ``https://`` (rewrite ``http://`` and drop bare ``http://``
    on non-studiorsr hosts that slipped through).
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u:
            return
        u = u.strip()
        if not u:
            return
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = STUDIORSR_BASE + u
        elif u.startswith("http://"):
            u = "https://" + u[len("http://") :]
        if not u.startswith("https://"):
            return
        if _STUDIORSR_IMAGE_DENY_RE.search(u):
            return
        try:
            parsed = urlparse(u)
        except ValueError:
            return
        host = (parsed.hostname or "").lower()
        # Restrict to first-party Shopify CDN paths on studiorsr.com.
        if not (host == "studiorsr.com" or host.endswith(".studiorsr.com")):
            return
        if not _STUDIORSR_PRODUCT_IMAGE_PATH_RE.search(parsed.path or ""):
            return
        if u in seen:
            return
        seen.add(u)
        urls.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(urls) >= 12:
            break
        # Prefer data-src / data-srcset (the real image URL after the
        # lazy-loader hydrates) over ``src`` (the spinner placeholder).
        for attr in ("data-src", "data-srcset", "src"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                # data-srcset is a comma-separated list of "<url> <density>";
                # take the first URL.
                first = val.strip().split(",")[0].strip().split(" ")[0]
                if first:
                    add(first)
                    break
    return urls[:12]


class StudioRSRAdapter(RetailerCrawlerAdapter):
    """
    Studio RSR adapter. Discovery: start URLs from env or sitemap.
    Parsing: JSON-LD first (Shopify), then shared DOM helpers (og:meta, h1, price, part_manufacturer, images).
    """

    ADAPTER_NAME: ClassVar[str] = "studiorsr"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Uses sitemap.xml (and child sitemaps) to find all
        /products/ URLs. Set CRAWLER_STUDIORSR_START_URLS (comma-separated) to
        override with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse Studio RSR product page. JSON-LD first, then DOM fallback using
        shared parsing helpers (meta_content, extract_dom_price, part_manufacturer_from_title).

        Returns ``None`` for non-``/products/`` URLs (e.g. ``/collections/<vendor>``
        landing pages). Without this gate, an extension capture or rescrape of
        ``/collections/lamborghini`` parses as a "product" with name="Lamborghini"
        and part_number="Recently" pulled from the storefront's "Recently viewed"
        widget — pure noise in the catalog.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD (Shopify typically exposes Product schema)
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                # Prefer longer DOM description when JSON-LD/meta is truncated; strip boilerplate
                dom_desc = _extract_full_description_from_dom(soup)
                if dom_desc and (not payload.description or len(dom_desc) > len(payload.description)):
                    description = dom_desc
                else:
                    description = _strip_studiorsr_boilerplate(payload.description) if payload.description else None
                # Reject car model codes (e.g. Z4M) as part_number
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                if dom_images or price_cents is not None:
                    part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)
                    payload = ScrapedPayload(
                        name=payload.name,
                        product_url=payload.product_url,
                        description=description,
                        price_cents=price_cents,
                        part_manufacturer=part_manufacturer,
                        part_number=part_number,
                        image_urls=dom_images[:12] if dom_images else payload.image_urls,
                        gtin=payload.gtin,
                    )
                return payload

        # 2. DOM fallback: og:meta, h1, description, price, part_manufacturer, images
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

        description = None
        dom_full = _extract_full_description_from_dom(soup)
        if dom_full:
            description = dom_full
        if not description:
            og_desc = soup.find("meta", property="og:description")
            if isinstance(og_desc, Tag):
                d = meta_content(og_desc)
                if d and d.strip():
                    description = _strip_studiorsr_boilerplate(
                        normalize_description_text(d, max_len=2000) or d.strip()[:2000]
                    )
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = _strip_studiorsr_boilerplate(
                        normalize_description_text(d, max_len=2000) or d.strip()[:2000]
                    )
        if not description:
            for p in soup.find_all("p"):
                t = p.get_text(strip=True)
                if t and len(t) > 80:
                    description = _strip_studiorsr_boilerplate(normalize_description_text(t, max_len=2000))
                    break

        price_cents = extract_dom_price(soup)
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
            if sku_elem:
                part_number = normalize_part_number(sku_elem.get_text(strip=True))
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
