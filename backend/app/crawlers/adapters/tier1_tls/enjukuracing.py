"""
Enjuku Racing (enjukuracing.com) crawler adapter — Tier 1 (TLS-impersonating fetcher).

Product URLs: ``https://www.enjukuracing.com/products/<slug>.html``. BigCommerce
Stencil storefront (CDN host ``cdn11.bigcommerce.com/s-79xyvl/...``). Unlike
Extreme Power House (``xph.py``), Enjuku's theme **does** emit a full JSON-LD
``Product`` block — name, sku, mpn, brand.name, description, image, and
offers.price are all authoritative — so parsing reuses
``extract_json_ld_product`` / ``scraped_payload_from_json_ld`` the same way the
AMS Performance adapter does. BCData + og: meta are kept as fallbacks only.

Fetcher tier: ``tls`` — the backlog entry estimated Tier-0 ("pattern matches
xph.py") but Cloudflare serves a client-fingerprint challenge on this origin
(``cf-mitigated: challenge`` 403 to plain ``requests``/``curl`` with a Chrome
UA). Same block pattern as Z1 Motorsports / Vivid Racing; ``curl_cffi`` with
Chrome impersonation passes. See ``site_problem_notes/enjukuracing.md``.

Discovery: ``/xmlsitemap.php`` is a sitemap index; children are
``xmlsitemap.php?type={pages,products,categories,brands,news}&page=N``. Only
``type=products`` children are walked. Product URLs in those child urlsets
live under ``/products/<slug>.html`` — the path prefix is the positive filter,
unlike xph where every product slug is at the site root. Override with
``CRAWLER_ENJUKURACING_START_URLS`` (comma-separated) for a fixed list.

Brand policy: Enjuku is a pure reseller carrying third-party lines (ISR
Performance, Brian Crower, Apexi, Tein, Buddy Club, …); there is no
"Enjuku"-branded SKU set. JSON-LD ``brand.name`` covers the entire catalog,
so no static default manufacturer is needed — we fall back only to the shared
title heuristic when a page happens to ship without JSON-LD brand.
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

ENJUKU_BASE = "https://www.enjukuracing.com"
SITEMAP_INDEX_URL = ENJUKU_BASE + "/xmlsitemap.php"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Product URL shape: ``/products/<slug>.html`` on the Enjuku host. BigCommerce
# Stencil lets retailers configure a path prefix; Enjuku uses ``/products/``
# (xph does not — so its discovery keys on the sitemap ``type`` query instead).
_PRODUCT_PATH_RE = re.compile(r"^/products/[a-z0-9][a-z0-9\-]*\.html$", re.IGNORECASE)

# BCData price fallback: ``var BCData = {..."product_attributes":{"price":{"without_tax":{"value":73.15}}}...};``
# Same blob shape as xph — carried here only as a price fallback for the rare
# page where JSON-LD offers are missing or malformed.
_BCDATA_PRICE_RE = re.compile(
    r'"without_tax"\s*:\s*\{[^}]*?"value"\s*:\s*"?(?P<v>-?\d+(?:\.\d+)?)"?',
    re.DOTALL,
)

DEFAULT_START_URLS = [
    "https://www.enjukuracing.com/products/isr-performance-inner-tie-rods-nissan-240sx.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` has a ``/products/<slug>.html`` path on the Enjuku host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "enjukuracing.com" or host.endswith(".enjukuracing.com")):
        return False
    path = parsed.path or ""
    return bool(_PRODUCT_PATH_RE.match(path))


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
    """Return ``CRAWLER_ENJUKURACING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_ENJUKURACING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


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
    """Read ``<meta property="product:price:amount" content="73.15">``."""
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
    no site suffix on this theme), then ``<h1 class="et-productView-title">``
    (custom theme prefix — the xph-style ``itemprop="name"`` is not emitted here).
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


class EnjukuRacingAdapter(RetailerCrawlerAdapter):
    """
    Enjuku Racing adapter.

    Fetcher tier: ``tls`` — Cloudflare ``cf-mitigated: challenge`` on plain
    ``requests``/``curl``, curl_cffi Chrome impersonation passes. Same posture
    as Z1 Motorsports.

    Discovery: ``CRAWLER_ENJUKURACING_START_URLS`` env var wins. Otherwise we
    walk ``/xmlsitemap.php`` (BigCommerce Stencil sitemap index) via
    ``self.fetcher``, keep only ``type=products&page=N`` child sitemaps, and
    collect every ``/products/<slug>.html`` URL they point at. Falls back to
    ``DEFAULT_START_URLS`` when discovery returns nothing.

    Parsing: JSON-LD Product first (the Stencil theme here emits name, sku,
    mpn, brand.name, description, image, and offers.price directly). BCData
    and og: meta are fallbacks for the rare page where JSON-LD is incomplete.
    No site-name suffix or trailing-SKU cleanup is needed — JSON-LD names on
    this theme are already clean.
    """

    ADAPTER_NAME: ClassVar[str] = "enjukuracing"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins when set."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in self._discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def _discover_via_sitemap(self) -> List[str]:
        """
        Fetch ``/xmlsitemap.php`` via the TLS fetcher, walk each
        ``type=products&page=N`` child urlset, and collect every
        ``/products/<slug>.html`` URL. Returns [] on any failure.
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
            index_text = self.fetcher.fetch(SITEMAP_INDEX_URL, timeout=15)
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
                        child_text = self.fetcher.fetch(child_url, timeout=15)
                        parse_urlset_locs(child_text)
                    except Exception:
                        continue
            else:
                # Single urlset served directly — unexpected for this host, but handle it.
                parse_urlset_locs(index_text)
        except Exception:
            return []

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Enjuku Racing product page into a ``ScrapedPayload``. Returns
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
