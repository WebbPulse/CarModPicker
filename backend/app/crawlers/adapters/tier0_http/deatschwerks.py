"""
DeatschWerks (deatschwerks.com) crawler adapter.

Fuel-system specialist out of Oklahoma City. House brand ``DeatschWerks``
(canonical spelling — camel-case, one word — matches JSON-LD ``brand.name``
and their own logo). Anchors the fuel-injector / fuel-pump slice of the
fuel vertical alongside ``radium`` (which carries surge tanks + fittings):
low / high-impedance injectors in 1000-2200 cc/min grades, DW series
in-tank pumps (DW200 / DW300 / DW400 / DW440 brushless / DW810), staged
surge tanks (2.5L / 3.5L / 5.5L), and fuel-pressure sensors.

Platform: **Shopify** (Dawn-family theme, served through Cloudflare but
plain ``requests`` with a real User-Agent clears on first try — no JS
challenge, no TLS/JA3 block observed 2026-04-22). ``FETCHER_TIER`` stays
at default ``"http"``. Apex ``deatschwerks.com`` is the canonical host;
``www.deatschwerks.com`` 301s to it and is not what the sitemap
advertises.

Discovery: standard Shopify ``/sitemap.xml`` sitemap **index** →
``sitemap_products_1.xml?from=…&to=…`` urlset. The query string must be
preserved on the child fetch (Shopify sitemap children reject a bare path
without the date-range params). Pages / collections / blogs siblings are
skipped; so is the ``/en-ca/`` locale mirror (same SKUs, different prices
in CAD — crawling both would double the row count for no catalog gain).
Override with ``CRAWLER_DEATSCHWERKS_START_URLS`` (comma-separated) for
targeted smoke tests.

Robots: ``robots.txt`` is a vanilla Shopify template — ``/admin``,
``/cart``, ``/checkout``, ``/search``, ``/policies``, sort/filter URLs
are all Disallowed; ``/products/<handle>`` is allowed. A top-of-file
comment asks automated "buy-for-me" checkout agents to go elsewhere; we
only scrape public product data so the polite-crawl path is fine.

JSON-LD shape: plain ``@type: Product`` on every PDP (not ``ProductGroup``).
``brand.name`` is reliably ``"DeatschWerks"``; ``sku`` is the real MPN
(e.g. ``42M-14-1200-4``, ``6-000-55ST``, ``16M-03-1500-8``); ``gtin`` is
populated with the UPC on most products; ``offers.price`` is the real
USD figure (DeatschWerks does not enforce MAP the way Radium does, so we
do **not** null out zeros reflexively — a zero here would be an outage
signal worth keeping an eye on, not a policy).

**Variant rule (VARIANTS.md §3 / §5 — this is the known-loss case).**
Fuel injectors and pumps come in a flow-rate axis (1000 / 1200 / 1500 /
1800 / 2200 cc/min …) and a connector-count / harness axis (sold as
matched sets of 2 / 4 / 6 / 8); these combinations have **distinct MPNs**,
**distinct prices**, and **distinct fitments** (VARIANTS.md §5 tests all
answer yes for fuel injectors). In principle this is the exact axis that
would motivate lifting the one-Part-per-URL constraint (Option D — first-
class Variant model — is what injector catalogs want long-term).

DeatschWerks sidesteps that for now by giving **every variant its own
slug**: ``/products/42m-14-1200-4`` (4-injector set) and
``/products/42m-14-1200-6`` (6-injector set) are separate PDPs with
separate JSON-LD ``Product`` blocks and separate SKUs. That matches the
``summitracing / jegs`` row in VARIANTS.md §3 ("per-variant URL, each
variant is its own page with its own JSON-LD → parse as a plain Product;
nothing is lost at the page level — but the parent concept is gone, so
related variants aren't linked"). **Parallel-row drift is accepted**: the
DB will carry N Part rows for one family (e.g. 42M-14-1200-*) which share
a name-prefix and manufacturer but have no explicit relationship; fixing
that is Option E (``family_mpn``) or Option D work, tracked in
VARIANTS.md §6-§7. This adapter does not attempt variant aggregation.

Brand policy: house-brand only. Force the canonical ``"DeatschWerks"`` on
every payload regardless of what JSON-LD / title heuristics return. The
shared ``part_manufacturer_from_title`` trips on chassis-led titles that
occur on some DW listings ("Toyota Supra 2JZ-GE …"), and the JSON-LD
brand field is reliable, so we prefer to pin the canonical form rather
than sometimes-pass-through. No third-party resell SKUs observed on this
shop.

Images: Shopify JSON-LD emits a single hero ``image``; richer galleries
live in the Dawn ``<media-gallery>`` / ``product__media`` wrappers. We
mirror the Shopify CDN sweep pattern from ``radium.py`` — sweep the raw
HTML for ``cdn.shopify.com`` / ``/cdn/shop/files/`` URLs, strip Shopify's
``_NNNx[NNN]`` responsive-size qualifier plus ``?width=…`` / ``?v=…``
for dedupe, and cap at 12.
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

DEATSCHWERKS_BASE = "https://deatschwerks.com"
SITEMAP_INDEX_URL = f"{DEATSCHWERKS_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical spelling — matches JSON-LD ``brand.name``, the site logo, and
# the company's own marketing materials. Lowercased / altcase variants from
# heuristics or DOM fallbacks are coerced to this form so the part-
# manufacturer table doesn't sprout "deatschwerks" / "Deatschwerks" /
# "DEATSCHWERKS" duplicates of the real entry.
DEATSCHWERKS_BRAND = "DeatschWerks"

# Standard Shopify ``/sitemap_products_*.xml`` child; other siblings host
# CMS / category / blog content.
_PRODUCT_CHILD_SITEMAP_RE = re.compile(r"/sitemap_products_\d+\.xml", re.IGNORECASE)

# Shopify CDN hosts for this store. Mirrors the radium.py regex; covers
# both the storefront-proxy CDN URL and the bare cdn.shopify.com URL.
_SHOPIFY_CDN_IMG_RE = re.compile(
    r"https?://(?:deatschwerks\.com/cdn/shop|cdn\.shopify\.com/s)/"
    r"(?:files|products)/[^\s\"'<>()]+?\.(?:jpg|jpeg|png|webp|gif)"
    r"(?:\?[^\s\"'<>()]*)?",
    re.IGNORECASE,
)

# Shopify responsive-size qualifier (e.g. ``_1200x.jpg``, ``_480x480.png``).
# Strip before dedupe so the same asset at different sizes collapses.
_SHOPIFY_SIZE_SUFFIX_RE = re.compile(r"_\d+x\d*(?=\.(?:jpg|jpeg|png|webp|gif))", re.IGNORECASE)

# Verified product URLs used when sitemap discovery fails and no env
# override is set. Chosen to exercise both of the catalog's main shapes:
# a pump/surge tank (single SKU) and an injector (per-variant URL that
# is really one node of a family).
DEFAULT_START_URLS = [
    # 5.5L Staged Surge Tank — single-SKU flagship FST (6-000-55ST).
    "https://deatschwerks.com/products/6-000-55st",
    # 1200cc/min Low-Z injector, matched set of 4 — per-variant URL in a
    # 4/6/8-connector family (42M-14-1200-4 / -6 / -8).
    "https://deatschwerks.com/products/42m-14-1200-4",
]


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk the Shopify sitemap index."""
    raw = os.environ.get("CRAWLER_DEATSCHWERKS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a DeatschWerks ``/products/<handle>`` PDP on apex."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host not in ("deatschwerks.com", "www.deatschwerks.com"):
        return False
    path = parsed.path or ""
    # Drop the /en-ca/ locale mirror — same SKUs, different currency. Crawling
    # both would double rows without adding catalog coverage.
    if path.startswith("/en-ca/"):
        return False
    if not path.startswith("/products/"):
        return False
    handle = path[len("/products/") :].strip("/")
    # Collection-nested ``/products/<collection>/<handle>`` isn't used on this
    # store; a multi-segment path is almost certainly malformed.
    return bool(handle) and "/" not in handle


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → ``sitemap_products_*.xml``
    children and collect every apex ``/products/<handle>`` URL.

    Shopify serves the child with a ``?from=&to=`` date-range query string;
    we must preserve it verbatim on the fetch (a bare path is rejected).
    Returns a deduplicated list (keyed by bare URL, query stripped); empty
    on failure so the caller can fall back to ``DEFAULT_START_URLS``.
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
                # Skip the /en-ca/ locale mirror child sitemap; same SKUs.
                if "/en-ca/" in child_url:
                    continue
                if fetched > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                fetched += 1
                try:
                    # Shopify sitemap children require the ?from=&to= query;
                    # fetch the URL verbatim (don't strip).
                    child_text = fetch_page(child_url, timeout=20)
                    parse_urlset_locs(child_text)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _canonical_image_key(url: str) -> str:
    """
    Stable dedupe key for a Shopify CDN image URL: strip the query string
    and any ``_NNNx[NNN]`` responsive-size qualifier so the same asset at
    different sizes collapses to one entry.
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
    Collect product-gallery images. JSON-LD gives us at most the hero, so
    sweep the full HTML for Shopify CDN URLs and dedupe by canonical key.
    og:image leads (same order Shopify renders) and the sweep fills in the
    rest. Caps at 12 — plenty for an injector / pump / surge-tank PDP.
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
    Fall back for when JSON-LD has no ``description``. Prefer
    ``og:description``; bare ``<meta name="description">`` is last-ditch.
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


class DeatschwerksAdapter(RetailerCrawlerAdapter):
    """
    DeatschWerks adapter. Shopify storefront, plain-HTTP fetcher tier.

    Discovery: ``/sitemap.xml`` index → ``sitemap_products_1.xml`` children
    (``?from=&to=`` query preserved). Apex ``deatschwerks.com`` only; the
    ``/en-ca/`` locale mirror is excluded.

    Parsing: JSON-LD ``Product`` (present on every PDP — name / description
    / brand / sku / price / gtin / hero image), og / DOM fallback, Shopify
    CDN gallery sweep. Brand is always forced to the canonical
    ``"DeatschWerks"`` — this shop is strictly first-party.

    Variant strategy: **per-variant URL** (VARIANTS.md §3, summitracing /
    jegs row). Each flow-rate × connector-count combination has its own
    slug and SKU — parsed as an independent ``Product``. Parallel-row drift
    is accepted; family aggregation is Option D/E future work.
    """

    ADAPTER_NAME: ClassVar[str] = "deatschwerks"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from the Shopify sitemap index. Set
        ``CRAWLER_DEATSCHWERKS_START_URLS`` (comma-separated) to override
        with a fixed list for targeted re-crawls or smoke tests.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a DeatschWerks product page into a ``ScrapedPayload``.

        1. JSON-LD ``Product`` path — authoritative on every current PDP.
           Merge the DOM gallery sweep on top of the single-URL hero image
           so we keep the full carousel.
        2. DOM / og fallback — kept for robustness if Shopify flips the
           theme and stops emitting JSON-LD on some pages.

        Returns ``None`` when no title can be extracted (non-product URLs
        that slipped through discovery).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_images(html, soup)

        # 1. JSON-LD Product path.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                # Merge DOM gallery on top of the single-URL JSON-LD hero.
                image_urls = list(payload.image_urls or [])
                seen_keys = {_canonical_image_key(u) for u in image_urls}
                for u in dom_images:
                    key = _canonical_image_key(u)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    image_urls.append(u)
                    if len(image_urls) >= 12:
                        break
                # JSON-LD price should be real (no MAP enforcement), but a
                # bare zero is meaningless for price history — fall back to
                # DOM in case the theme briefly surfaces a real number.
                price_cents = payload.price_cents
                if not price_cents:
                    price_cents = extract_dom_price(soup)
                if price_cents == 0:
                    price_cents = None
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=DEATSCHWERKS_BRAND,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback. Rare — kept so a theme flip that drops
        # JSON-LD on some PDPs doesn't silently blank the adapter.
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
            part_manufacturer=DEATSCHWERKS_BRAND,
            part_number=None,  # no reliable PDP SKU without JSON-LD on this store
            image_urls=image_urls,
        )
