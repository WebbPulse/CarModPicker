"""
Road Sport Supply / RSS Manufacturing (roadsportsupply.com) crawler adapter.

RSS Manufacturing ("Road Sport Supply") is a Porsche suspension manufacturer in
Costa Mesa, CA. The RETAILER_BACKLOG entry listed ``rss-mfg.com`` as the domain,
but that hostname does not resolve — the manufacturer's actual storefront is
``roadsportsupply.com``. Same company; the adapter is keyed on the live domain.

Product URLs: ``https://roadsportsupply.com/<slug>/`` (root-slug with trailing
slash, BigCommerce Stencil default — no ``/products/`` prefix). Matches the
xph.com URL shape rather than the enjukuracing ``/products/<slug>.html`` shape.

Fetcher tier: ``http`` — plain ``requests`` with a Chrome UA returns HTTP 200
on the homepage, sitemap, and product pages. Cloudflare is in front but does
not challenge non-browser clients the way it does on Z1 / Vivid / Enjuku.

Parsing: Stencil theme emits a full JSON-LD ``Product`` block (name, sku,
brand.name, description, image, offers.price). JSON-LD is authoritative; BCData
``product_attributes.price.without_tax.value`` is the price fallback for the
rare page with an empty offers block. og:title / ``<h1>`` cover the DOM fallback
when JSON-LD is absent entirely.

Brand policy: Road Sport Supply is both an RSS-direct store AND a reseller of
third-party Porsche performance lines (Sharkwerks, Cargraphic, Racetech,
Girodisc, …). JSON-LD ``brand.name`` is populated per-SKU and covers the full
catalog, so no static default manufacturer is needed — the shared title /
description heuristics handle the rare un-branded page.

Discovery: ``/xmlsitemap.php`` is a sitemap index; children partition by
``type={pages,products,categories,brands,news}``. Only ``type=products``
children are walked. Override with ``CRAWLER_ROADSPORTSUPPLY_START_URLS``
(comma-separated) for ad-hoc runs.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
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
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

ROADSPORTSUPPLY_BASE = "https://roadsportsupply.com"
SITEMAP_INDEX_URL = ROADSPORTSUPPLY_BASE + "/xmlsitemap.php"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Product URLs are root-slug with a trailing slash (``/<slug>/``). Category,
# brand, and CMS pages share the prefix space, so the sitemap ``type=products``
# query is the real positive filter — this regex only rejects obvious non-slug
# shapes (empty path, nested paths, query-only URLs).
_PRODUCT_PATH_RE = re.compile(r"^/[a-z0-9][a-z0-9\-]*/?$", re.IGNORECASE)

# Non-product root paths served under the same ``/<slug>/`` shape. These leak
# into discovery if the sitemap is ever misconfigured; the filter stays cheap
# because the sitemap ``type`` partitioning already rejects them upstream.
_NON_PRODUCT_SLUGS = frozenset(
    {
        "cart",
        "checkout",
        "login",
        "account",
        "search",
        "contact-us",
        "about-us",
        "privacy",
        "privacy-policy",
        "terms",
        "shipping",
        "returns",
        "brands",
        "categories",
        "rss",
        "blog",
    }
)

# BCData price fallback: ``var BCData = {..."product_attributes":{"price":
# {"without_tax":{"value":290}}}...};``. Same blob shape as xph / enjukuracing;
# kept permissive so it survives minor Stencil theme variations.
_BCDATA_PRICE_RE = re.compile(
    r'"without_tax"\s*:\s*\{[^}]*?"value"\s*:\s*"?(?P<v>-?\d+(?:\.\d+)?)"?',
    re.DOTALL,
)

DEFAULT_START_URLS = [
    "https://roadsportsupply.com/323-thrust-arm-bushing-puck-non-castor-adjustable-front-axle/",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` has a single-segment root-slug path on the roadsportsupply host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "roadsportsupply.com" or host.endswith(".roadsportsupply.com")):
        return False
    path = parsed.path or ""
    if not _PRODUCT_PATH_RE.match(path):
        return False
    slug = path.strip("/").lower()
    return slug not in _NON_PRODUCT_SLUGS


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a ``xmlsitemap.php?type=products&page=N`` child sitemap."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if not parsed.path.endswith("/xmlsitemap.php"):
        return False
    return parse_qs(parsed.query).get("type", [""])[0] == "products"


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_ROADSPORTSUPPLY_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_ROADSPORTSUPPLY_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/xmlsitemap.php`` (sitemap index) → each ``type=products&page=N``
    child urlset and collect every product URL. Returns deduplicated list
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
            raw = loc.text.strip()
            if not raw or not _is_product_url(raw):
                continue
            base = raw.split("?", 1)[0]
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


def _price_cents_from_bcdata(html: str) -> Optional[int]:
    """
    Parse ``BCData.product_attributes.price.without_tax.value`` (dollars) → cents
    via a targeted regex. Kept permissive (matches on the nested ``without_tax``
    dict anywhere in the inline blob) so it survives minor theme variations.
    """
    match = _BCDATA_PRICE_RE.search(html)
    if not match:
        return None
    try:
        dollars = float(match.group("v"))
    except ValueError:
        return None
    if dollars <= 0:
        return None
    return int(round(dollars * 100))


def _price_cents_from_og(soup: BeautifulSoup) -> Optional[int]:
    """Read ``<meta property="product:price:amount" content="290">``."""
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if not isinstance(meta, Tag):
            continue
        content = meta_content(meta)
        if not content:
            continue
        cents = parse_price_cents(content)
        if cents is not None:
            return cents
    return None


def _name_from_dom_fallback(soup: BeautifulSoup) -> Optional[str]:
    """
    Recover a product name when JSON-LD is missing. ``og:title`` first (cleanest,
    no site suffix on this theme), then any bare ``<h1>``.
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip():
            return content.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    return None


class RoadSportSupplyAdapter(RetailerCrawlerAdapter):
    """
    Road Sport Supply (RSS Manufacturing) adapter.

    Fetcher tier: ``http`` — Cloudflare is passive on this origin; plain
    ``fetch_page`` returns full HTML on the homepage, sitemap, and product
    pages.

    Discovery: ``CRAWLER_ROADSPORTSUPPLY_START_URLS`` env var wins. Otherwise
    we walk ``/xmlsitemap.php`` (BigCommerce Stencil sitemap index), keep only
    ``type=products&page=N`` child sitemaps, and collect every product URL.
    Falls back to ``DEFAULT_START_URLS`` when discovery returns nothing.

    Parsing: JSON-LD Product first (name, sku, brand.name, description, image,
    offers.price). BCData and og: meta are fallbacks for the rare page where
    JSON-LD is incomplete.
    """

    ADAPTER_NAME: ClassVar[str] = "roadsportsupply"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins when set."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in _discover_product_urls_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Road Sport Supply product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL isn't product-shaped or when neither JSON-LD nor
        the DOM fallback yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents
                if price_cents is None:
                    price_cents = _price_cents_from_bcdata(html) or _price_cents_from_og(soup)

                part_manufacturer = (payload.part_manufacturer or "").strip() or None
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_from_title(payload.name)
                if not part_manufacturer and payload.description:
                    part_manufacturer = part_manufacturer_from_description(
                        payload.description, product_name=payload.name
                    )
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_fallback_from_title(payload.name)

                part_number = normalize_part_number(payload.part_number) if payload.part_number else None

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=payload.image_urls,
                    gtin=payload.gtin,
                )

        # Fallback: no JSON-LD Product. Recover at least a name from og:title / <h1>
        # so downstream archive rescrapes still capture something usable.
        name = _name_from_dom_fallback(soup)
        if not name or len(name) < 3:
            return None

        part_manufacturer = part_manufacturer_from_title(name) or part_manufacturer_fallback_from_title(name)

        price_cents = _price_cents_from_bcdata(html) or _price_cents_from_og(soup)

        og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
        image_urls: Optional[List[str]] = None
        if isinstance(og_img, Tag):
            content = meta_content(og_img)
            if content and content.strip():
                image_urls = [content.strip()]

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=None,
            image_urls=image_urls,
        )
