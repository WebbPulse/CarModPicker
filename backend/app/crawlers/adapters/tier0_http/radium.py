"""
Radium Engineering (radiumauto.com) crawler adapter.

High-end fuel and oil system specialist based out of Portland, OR. Anchors
the fuel-delivery vertical in the catalog: fuel surge tanks (FST), dual /
triple-pump hanger assemblies, fuel pressure regulators (FPR / DMR), direct
mount regulators, oil catch cans, and supporting AN/NPT fittings. Strictly
cross-platform — every product is Radium house-brand, every chassis from
S2000 / Evo X / GR Supra / BRZ-GR86 / Lotus Elise-Exige / B-series Civic
through modern turbo platforms.

Platform: **Shopify** (Dawn-family theme). Standard Shopify sitemap index at
``/sitemap.xml`` → ``sitemap_products_1.xml`` urlset; product URLs live under
``/products/<handle>``. ``robots.txt`` only disallows ``/collections/all``
(the default aggregator page); individual product pages are allowed.

Fetcher tier: ``http`` — plain ``requests`` with the default UA clears the
Shopify origin cleanly; no Cloudflare interstitial, no TLS fingerprinting,
no bot-management JS challenge observed.

Parsing: JSON-LD ``Product`` first (present on every PDP), with a DOM / og
fallback. Three site-specific quirks drive the adapter:

1. **Top-level ``sku`` field is the literal string ``"NULL"``** on every
   product. Shopify supports product-level SKUs, but Radium stores real SKUs
   only at the variant level (see quirk 2). Any top-level ``sku`` / ``mpn``
   that normalizes to ``"NULL"`` is discarded so it can't leak into
   ``part_number``.
2. **Multi-variant products are the rule**, not the exception. A single PDP
   (e.g. ``/products/dmr-ra-direct-mount-regulator``) bundles 6-8 variant
   SKUs (``20-1623-00``, ``20-1623-01``, ``20-0624``, ``14-0706``, …) that
   differ by chassis / size / port configuration. There is no single
   canonical SKU for the URL, so we leave ``part_number`` unset rather than
   picking a representative variant at random — cross-retailer dedupe relies
   on ``retailer + product_url`` for this shop. Simple fittings with one
   variant still resolve naturally through the image-filename heuristic.
3. **Prices are always ``$0.00`` in JSON-LD** — Radium enforces MAP so the
   public PDPs never expose a dollar figure. We pass ``None`` rather than
   storing a fake zero.

Brand policy: house-brand only. JSON-LD ``brand.name`` is reliably
``"Radium Engineering"`` on every PDP, but when JSON-LD is missing we fall
back to DOM. The shared ``part_manufacturer_from_title`` heuristic trips on
this catalog because many titles lead with a chassis or model token —
``"S2000 Catch Can Kits RHD"``, ``"Evo X Fuel Rail Kit"``, ``"Lotus Elise …"``
— which would pollute the manufacturer table with car-make entries. We
therefore **always force the house brand** to the canonical
``"Radium Engineering"`` regardless of what the title heuristic returns; the
site is strictly a first-party manufacturer catalog.

SKU format (reference only, not stored): ``<prefix>-<number>[-<variant>]``
where prefix is ``20`` (fuel/oil system hardware), ``14`` (fittings / small
parts), or ``18`` (install kits / wiring). Examples: ``20-1195`` (FST),
``20-1623-00`` (DMR base), ``14-0148-08`` (AN-08 fitting). The SKU frequently
appears as a prefix on product image filenames (``20-1195_1200px_wide.jpg``);
downstream tooling can recover it from there if needed.

Images: Shopify emits a single ``image`` in JSON-LD (the hero). Real galleries
live in the Dawn ``product__media`` section and render ``cdn.shopify.com`` /
``/cdn/shop/files/...`` URLs. We sweep the raw HTML for those, strip
``?width=...`` / ``_{size}x.`` responsive-size qualifiers for dedupe, and
drop theme chrome (``pending-patent.png``, dimension-diagram PNGs that aren't
product photography are kept — Radium uses them intentionally as spec art).

Discovery: Shopify sitemap index → ``sitemap_products_1.xml`` (single child
urlset for this store; small enough catalog that Shopify doesn't split it).
Category (``sitemap_collections_1.xml``) and CMS (``sitemap_pages_1.xml``)
children are skipped. Override with ``CRAWLER_RADIUM_START_URLS``
(comma-separated) to use a fixed list.
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
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

RADIUM_BASE = "https://www.radiumauto.com"
SITEMAP_INDEX_URL = f"{RADIUM_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical form matches the JSON-LD ``brand.name`` and the ``vendor`` meta
# key on every Radium PDP. Also the spelling in
# ``parsing.py::part_manufacturer_from_title`` / ``_from_description``, so
# repeated extraction stays consistent with the rest of the codebase.
RADIUM_BRAND = "Radium Engineering"

# Shopify stuffs "NULL" (literal string) into the top-level product sku field
# when there's no store-wide SKU (Radium stores SKUs only on variants). We
# must discard it; otherwise normalize_part_number happily returns "NULL" and
# the ingest layer saves it as a fake part_number that blocks dedupe.
_SKU_PLACEHOLDER_VALUES = frozenset({"null", "none", "n/a", "na", "-", "--"})

DEFAULT_START_URLS = [
    # Fuel Surge Tank for External Pumps — single-SKU flagship FST (20-1195).
    "https://www.radiumauto.com/products/fuel-surge-tank-for-external-pumps",
    # DMR, Direct Mount Regulator — multi-variant regulator family (20-1623-*).
    "https://www.radiumauto.com/products/dmr-ra-direct-mount-regulator",
]

# Only the ``sitemap_products_*.xml`` children list product URLs; pages and
# collections children are CMS / category noise.
_PRODUCT_CHILD_SITEMAP_RE = re.compile(r"/sitemap_products_\d+\.xml", re.IGNORECASE)

# Shopify CDN hosts for radiumauto.com images. The Dawn theme emits
# ``cdn.shopify.com/s/files/...`` on some pages and the newer per-store
# ``www.radiumauto.com/cdn/shop/files/...`` on others; both point at the
# same asset backend.
_SHOPIFY_CDN_IMG_RE = re.compile(
    r"https?://(?:www\.radiumauto\.com/cdn/shop|cdn\.shopify\.com/s)/"
    r"(?:files|products)/[^\s\"'<>()]+?\.(?:jpg|jpeg|png|webp|gif)"
    r"(?:\?[^\s\"'<>()]*)?",
    re.IGNORECASE,
)

# Shopify responsive-size qualifier — ``_1200x.jpg``, ``_480x480.png``, etc.
# Strip before dedupe so the same asset at different sizes collapses to one.
_SHOPIFY_SIZE_SUFFIX_RE = re.compile(r"_\d+x\d*(?=\.(?:jpg|jpeg|png|webp|gif))", re.IGNORECASE)

# Site-chrome filenames that match _SHOPIFY_CDN_IMG_RE but are NOT product
# media. ``List.png`` is a "size-chart / fitment list" UI badge that the Dawn
# theme renders on every product page; it leaked onto 241 parts via the
# whole-HTML regex sweep before this filter.
_RADIUM_CHROME_FILENAME_RE = re.compile(
    r"/(?:files|products)/(?:List|Logo|Banner|Header|Footer|Placeholder|Favicon|Sprite|Icon|Prop65|Warranty)(?:[-_].*)?\.(?:png|jpg|jpeg|webp|gif)",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk the Shopify sitemap index."""
    raw = os.environ.get("CRAWLER_RADIUM_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a Radium ``/products/<handle>`` PDP."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host not in ("radiumauto.com", "www.radiumauto.com"):
        return False
    path = parsed.path or ""
    if not path.startswith("/products/"):
        return False
    handle = path[len("/products/") :].strip("/")
    # Reject the collection-nested shape ``/products/<collection>/<handle>`` if
    # it ever appears — Shopify allows it but Radium doesn't use it, so any
    # multi-segment path is most likely malformed.
    return bool(handle) and "/" not in handle


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → ``sitemap_products_*.xml`` children and collect
    every ``/products/<handle>`` URL. Skips pages / collections / blogs
    children. Returns a deduplicated list (keyed by bare URL, query stripped);
    empty on failure.
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
        index_text = fetch_page(SITEMAP_INDEX_URL, timeout=20)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_urls:
                if not _PRODUCT_CHILD_SITEMAP_RE.search(child_url):
                    continue
                if fetched > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                fetched += 1
                try:
                    child_text = fetch_page(child_url, timeout=20)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _is_placeholder_sku(value: Optional[str]) -> bool:
    """
    True if ``value`` is Radium's ``"NULL"`` placeholder (or any equivalent
    non-value) rather than a real SKU. Case- and whitespace-insensitive.
    """
    if not value:
        return True
    return value.strip().lower() in _SKU_PLACEHOLDER_VALUES


def _clean_part_number(raw: Optional[str]) -> Optional[str]:
    """
    Normalize a candidate part number, rejecting Radium's ``"NULL"`` sentinel
    so it never reaches the DB. Any other short / junk value is handled
    downstream by ``is_junk_part_number`` in the ingest layer.
    """
    if _is_placeholder_sku(raw):
        return None
    return normalize_part_number(raw)


def _canonical_image_key(url: str) -> str:
    """
    Build a stable dedupe key for a Shopify CDN image URL: strip the
    ``?width=...`` query string and any ``_NNNx[NNN]`` responsive-size
    qualifier from the filename so that the same asset at different sizes
    collapses to one entry.
    """
    no_query = url.split("?", 1)[0]
    return _SHOPIFY_SIZE_SUFFIX_RE.sub("", no_query).lower()


def _normalize_image_url(url: str) -> str:
    """Upgrade protocol-relative and http URLs to https; leave the rest alone."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


def _extract_images(html: str, soup: BeautifulSoup) -> List[str]:
    """
    Collect product-gallery images. JSON-LD gives us at most the hero, so we
    sweep the full HTML for Shopify CDN URLs and dedupe by canonical key.
    og:image leads (same order Shopify renders) and sweeps fill in the rest.
    Deliberately inclusive — Radium uses dimension diagrams and installation
    shots as part of the gallery and those are useful catalog content.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("https://"):
            return
        if not _SHOPIFY_CDN_IMG_RE.match(u):
            return
        if _RADIUM_CHROME_FILENAME_RE.search(u):
            return
        key = _canonical_image_key(u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    for prop in ("og:image:secure_url", "og:image"):
        og = soup.find("meta", property=prop)
        if isinstance(og, Tag):
            add(meta_content(og))

    for match in _SHOPIFY_CDN_IMG_RE.finditer(html):
        add(match.group(0))
        if len(ordered) >= 12:
            break

    return ordered


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Fall back for when JSON-LD has no description. Prefer ``og:description``;
    the bare ``<meta name="description">`` is the last-ditch source.
    """
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


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    """Prefer ``og:title``; fall back to the first ``<h1>``."""
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


class RadiumAdapter(RetailerCrawlerAdapter):
    """
    Radium Engineering adapter. Shopify storefront, plain-HTTP fetcher tier.
    Discovery: ``/sitemap.xml`` index → ``sitemap_products_*.xml`` children.
    Parsing: JSON-LD ``Product`` (with ``"NULL"`` SKU stripped and ``$0.00``
    MAP prices dropped), og / DOM fallback, Shopify CDN gallery sweep.
    Brand is always forced to the canonical ``"Radium Engineering"`` — the
    title heuristic would otherwise assign car-make tokens (S2000, Evo, Lotus,
    …) from chassis-led product names, and this shop is strictly first-party.
    """

    ADAPTER_NAME: ClassVar[str] = "radium"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from the Shopify sitemap index. Set
        ``CRAWLER_RADIUM_START_URLS`` (comma-separated) to override with a
        fixed list for targeted re-crawls or smoke tests.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Radium product page into a ``ScrapedPayload``. JSON-LD first
        (clean on every PDP); og / DOM fallback for any future page that
        loses the Product block. Returns ``None`` when no title can be
        extracted (non-product URLs that slipped through discovery).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_images(html, soup)

        # 1. JSON-LD Product path — present on every current PDP.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                # Drop the "NULL" placeholder that Radium stuffs into sku.
                part_number = _clean_part_number(payload.part_number)
                # Shopify JSON-LD images → just the hero. Use the DOM sweep
                # when available; otherwise keep whatever JSON-LD returned.
                image_urls = dom_images[:12] if dom_images else payload.image_urls
                # Drop the MAP-forced $0.00 — a real zero price is meaningless
                # for catalog/price-history tracking. Use whatever DOM exposes
                # on the off chance a future theme surfaces a real number.
                price_cents = payload.price_cents if payload.price_cents else extract_dom_price(soup)
                if price_cents == 0:
                    price_cents = None
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=RADIUM_BRAND,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                )

        # 2. DOM / og fallback. Rarely taken but keeps the adapter honest if
        # Shopify flips the theme and stops emitting JSON-LD on some PDPs.
        name = _extract_title(soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)
        price_cents = extract_dom_price(soup)
        if price_cents == 0:
            price_cents = None

        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=RADIUM_BRAND,
            part_number=None,  # variant-heavy catalog; no canonical PDP SKU
            image_urls=image_urls,
        )
