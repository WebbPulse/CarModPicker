"""
Stance Suspension USA (stance-usa.com) crawler adapter.

Platform: **WordPress + WooCommerce** (Enfold / Avia theme, Yoast SEO) on
an nginx front with no Cloudflare. The apex host is ``stance-usa.com``;
``www.stance-usa.com`` 301s to apex, ``stanceusa.com`` is an unrelated
domain-parking page, and ``stancesuspension.com`` returns Apache 406 with
no live WordPress behind it. Only ``stance-usa.com`` (and the ``www.``
subdomain, for archive-replay completeness) should be host-gated here.

Product URLs: ``https://stance-usa.com/shop/<slug>/``

Discovery: ``/wp-sitemap.xml`` is the standard WordPress 5.5+ sitemap
**index** pointing at ``wp-sitemap-posts-product-1.xml`` (products), plus
post / page / portfolio / taxonomy siblings. Only the
``wp-sitemap-posts-product-N.xml`` children host real product URLs — the
rest are marketing / CMS noise and are skipped. The pre-WP5.5 URL that
``robots.txt`` still advertises (``/main/sitemap.xml``) 404s against the
WordPress rewrite rules, so discovery uses the modern index directly.
Override with ``CRAWLER_STANCEUSA_START_URLS`` (comma-separated) for
ad-hoc runs.

JSON-LD shape: WooCommerce emits a single top-level ``@type: Product``
node (no Yoast ``@graph`` wrapper on this storefront, no Breadcrumb /
WebPage siblings that could trip the URL-aware extractor). The block
carries ``name``, ``@id``, ``url``, ``description``, ``image``, ``sku``,
and ``offers`` — but **no** ``brand`` field. Two WooCommerce shape quirks
matter:

- **Price lives at ``offers[0].priceSpecification[0].price``** with a
  ``UnitPriceSpecification`` wrapper (same Yoast-WooCommerce shape as
  ``openflashperformance`` and ``driveshaftshop``). The shared
  ``_price_from_json_ld`` reader only inspects ``offers[0].price`` /
  ``lowPrice`` / ``highPrice``, so we pull the ``priceSpecification``
  value out explicitly when the shared reader returns ``None``.
- **No OpenGraph meta tags.** The Enfold theme ships no ``og:title`` /
  ``og:description`` / ``og:image`` on PDP — any fallback has to read
  ``<title>`` / ``<h1>`` / ``<meta name="description">`` directly.

Brand rule: the storefront is first-party. Every SKU on the site is a
Stance Suspension product (coilovers, springs, bushings, top hats, hats,
shirts). Per VARIANTS.md §5, the site advertises itself as "STANCE
SUSPENSION" (all-caps) in the ``<title>`` suffix and the JSON-LD
``offers[0].seller.name`` — so the canonical part_manufacturer is
**"Stance Suspension"**, not "Stance USA". Any vendor spelling that
appears in the wild (``"STANCE SUSPENSION"`` all-caps, ``"Stance"``,
``"Stance USA"``, ``"stance-usa"``) collapses to the canonical spelling
so cross-retailer dedupe on (manufacturer, part_number) matches
consistently. The JSON-LD emits no ``brand`` field today, so the
coercion is mostly defensive — but it also guards the handful of third-
party accessories (Swift springs, etc.) from being coerced away. Known
third-party vendors (Swift Springs, Aurora Bearings) pass through with
a title-prefix check so their real manufacturer is preserved.

Variant rule (VARIANTS.md §5 — known loss): several product families are
WooCommerce variable products with spring-rate, chassis-application, or
weather-cover-size variants — e.g. ``stance-coilover-springs-200mm``
exposes an ``attribute_rate`` picker (``8k``, ``10k``, ``12k``, …). The
WooCommerce ``variations`` blob in the DOM carries the per-variant
``display_price`` and a SKU stub for each rate. The JSON-LD, by contrast,
only emits one top-level ``Product`` with the parent SKU (``ST-200``) and
the floor price. We follow the cross-adapter convention: parent SKU /
floor price / parent name win per URL, and the variant axis is a
documented loss. Most coilover PDPs (``/shop/bmw-m3-e46/`` etc.) are
single-SKU fitment pages and unaffected.

Tier rationale: ``Tier 0`` (``FETCHER_TIER = "http"``). Plain ``requests``
returns full HTML on first hit; nginx serves without a WAF or JS
challenge, and the host-header comment / ``x-cache-enabled`` headers hint
at a simple full-page cache rather than a bot-management proxy. No TLS
fingerprint block observed.

robots.txt: ``Disallow`` only targets ``/wp-admin``, ``/wp-includes``,
``/wp-content/{plugins,cache,themes}``, ``/cgi-bin``, ``/trackback``,
``/comments``, and the ``wp-*.php`` admin endpoints — all wildcarded for
``User-agent: *``. Catalog paths (``/shop/<slug>/``, ``/wp-sitemap*.xml``)
are allowed. A ``Crawl-delay: 10`` directive is advertised; the shared
runner's robots cache will pick that up and lift the per-request delay to
10s for this origin (larger of ``--delay`` and the advertised value).
Expect slow but uninterrupted crawls.

Caveats:

- The WooCommerce DOM includes ``.woocommerce-Price-amount`` spans with
  values for the current variant *and* the MSRP (``<del>`` / ``<ins>``
  pair on sale pages). The JSON-LD priceSpecification carries the current
  price in all cases observed, so we don't need a DOM-price fallback —
  but any future DOM-price reader must prefer the ``<ins>`` side.
- Product descriptions on coilover pages are a flattened spec table
  (``Part #\\nST-E46-XR1\\nChassis\\nE46\\nYear\\n00-05\\n...``) rather
  than prose. ``normalize_description_text`` collapses the whitespace
  into a single line; the original layout is lost but the SKU and
  fitment data are preserved in reading order. No downstream logic
  relies on the table layout.
- A small number of apparel / merch SKUs live alongside the suspension
  catalog (``stance-suspension-hats``, ``stance-suspension-trucker-hat``,
  ``stance-suspension-fall-2025-hoodie``). They parse cleanly as
  ``Product`` nodes and are flagged to the default ``suspension``
  category by the runner — acceptable miscategorization at current
  volume, not worth a per-slug override.
- The site advertises a pre-WP5.5 ``/main/sitemap.xml`` in robots.txt
  that 404s behind the current WordPress rewrite rules. Discovery goes
  straight to ``/wp-sitemap.xml`` instead; if WordPress ever reverts to
  the legacy path, add a fallback probe here.
"""

import os
import re
import time
from typing import Any, ClassVar, Iterator, List, Optional, cast
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
    extract_json_ld_product,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

STANCEUSA_BASE = "https://stance-usa.com"
SITEMAP_INDEX_URL = STANCEUSA_BASE + "/wp-sitemap.xml"
PRODUCT_PAGE_PATH = "/shop/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical house brand — the site brands itself "STANCE SUSPENSION" in
# the <title> suffix and the JSON-LD seller.name. "Stance USA" is the
# domain slug, not the vendor name — do not use it as the canonical
# manufacturer label.
STANCEUSA_BRAND = "Stance Suspension"

# Self-spellings that should all collapse to ``STANCEUSA_BRAND``. Anything
# outside this set (e.g. "Swift", "Aurora") is a resold component and
# passes through as-is so the real manufacturer is preserved.
_STANCEUSA_BRAND_VARIANTS = frozenset(
    {
        "stance",
        "stance usa",
        "stance-usa",
        "stanceusa",
        "stance suspension",
        "stancesuspension",
        "stance-suspension",
        "stance suspension usa",
    }
)

# Third-party vendors whose products appear on the storefront and must NOT
# be coerced to the house brand. The lookup is a prefix match on the
# lowercased, whitespace-normalized title so "Swift Springs 60mm ID" and
# "Aurora Lower Control Arm Bearing" resolve to the right manufacturer
# even though the JSON-LD emits no ``brand`` field.
_TITLE_BRAND_PREFIXES: tuple[tuple[str, str], ...] = (
    ("swift springs", "Swift Springs"),
    ("swift ", "Swift Springs"),
    ("aurora ", "Aurora Bearings"),
)

# Verified live product URLs for the fallback path (env override off +
# sitemap discovery down). Picked across catalog families (coilovers +
# springs) so the first run exercises the JSON-LD path on two shapes.
DEFAULT_START_URLS = [
    "https://stance-usa.com/shop/bmw-m3-e46/",
    "https://stance-usa.com/shop/mazda-miata-nd/",
]

# Only WordPress sitemap children named ``wp-sitemap-posts-product-N.xml``
# host product URLs. Skip post/page/portfolio/taxonomy siblings.
_PRODUCT_SITEMAP_RE = re.compile(r"/wp-sitemap-posts-product-\d+\.xml$", re.IGNORECASE)

# WordPress / Yoast appends the site name as a trailing title suffix —
# ``" – STANCE SUSPENSION"`` or ``" - STANCE SUSPENSION"``. The JSON-LD
# ``name`` is clean (``"BMW M3 E46"``) but <title>/<h1> fallbacks pick up
# the suffix and we strip it defensively. Dash / em-dash / en-dash all
# covered; the suffix itself is case-insensitive.
_NAME_SITE_SUFFIX_RE = re.compile(
    r"\s*[-–—|]\s*STANCE\s+SUSPENSION\s*$",
    re.IGNORECASE,
)

# WordPress upload size-suffix (``-600x400.jpg``, ``-1200x800.webp``, …).
# Used by ``_canonical_image_key`` so thumbnail size-variants of the same
# upload collapse to a single row in the gallery.
_WP_SIZE_SUFFIX_RE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.[a-z]{2,5}(?:$|\?))", re.IGNORECASE)


def _is_product_url(url: str) -> bool:
    """True if ``url`` points at a ``/shop/<slug>/`` page on a Stance host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "stance-usa.com" or host.endswith(".stance-usa.com")):
        return False
    return PRODUCT_PAGE_PATH in (parsed.path or "")


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is a ``wp-sitemap-posts-product-N.xml`` urlset."""
    try:
        path = urlparse(url).path
    except ValueError:
        return False
    return bool(_PRODUCT_SITEMAP_RE.search(path))


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via wp-sitemap.xml, then fallback."""
    raw = os.environ.get("CRAWLER_STANCEUSA_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/wp-sitemap.xml`` → each ``wp-sitemap-posts-product-N.xml``
    urlset and collect every ``/shop/<slug>/`` URL. Returns deduplicated
    list (by URL with query stripped); empty on failure so the caller can
    fall back to ``DEFAULT_START_URLS``.
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
            # Urlset served directly — uncommon on WordPress but handle it.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _strip_site_suffix(name: str) -> str:
    """Drop the trailing ``" – STANCE SUSPENSION"`` suffix if WordPress leaked it in."""
    stripped = _NAME_SITE_SUFFIX_RE.sub("", name).strip()
    return stripped or name


def _price_cents_from_price_specification(item: dict[str, Any]) -> Optional[int]:
    """
    Read price from ``offers[0].priceSpecification[0].price`` — the Yoast /
    WooCommerce shape used on Stance. Mirrors the same-named helper on
    ``openflashperformance`` and ``driveshaftshop``; the three adapters all
    hit this nested shape and the shared ``_price_from_json_ld`` doesn't
    recurse into it. Returns ``None`` when no usable number is found.
    """
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = cast(dict[str, Any], offers[0])
    elif isinstance(offers, dict):
        offer = offers
    else:
        return None
    specs = offer.get("priceSpecification")
    if isinstance(specs, list) and specs:
        spec = cast(dict[str, Any], specs[0])
    elif isinstance(specs, dict):
        spec = specs
    else:
        return None
    price = spec.get("price")
    if price is None:
        return None
    try:
        num = float(str(price).replace(",", ""))
    except (ValueError, TypeError):
        return None
    if not (num > 0):
        return None
    return int(round(num * 100))


def _brand_from_title_prefix(name: Optional[str]) -> Optional[str]:
    """
    Return a third-party manufacturer when the product title starts with a
    known reseller prefix (``Swift Springs …``, ``Aurora …``). Returns
    ``None`` otherwise — the caller coerces to the house brand.
    """
    if not name or not name.strip():
        return None
    low = name.strip().lower()
    for prefix, brand in _TITLE_BRAND_PREFIXES:
        if low.startswith(prefix):
            return brand
    return None


def _normalize_part_manufacturer(raw: Optional[str], product_name: Optional[str]) -> str:
    """
    Collapse every Stance-self vendor spelling (``"STANCE SUSPENSION"``,
    ``"Stance"``, ``"Stance USA"``, ``"stance-usa"``, …) to the canonical
    ``"Stance Suspension"``. Empty / missing falls back to the same
    default via a title-prefix check so known third-party vendors (Swift
    Springs, Aurora Bearings) keep their real name even when JSON-LD omits
    the brand field. Non-empty values outside the self-spelling set pass
    through unchanged.
    """
    cleaned = (raw or "").strip()
    if cleaned:
        if cleaned.lower() in _STANCEUSA_BRAND_VARIANTS:
            return STANCEUSA_BRAND
        return cleaned
    # No explicit brand — use the title prefix first (third-party resells),
    # then fall back to the canonical house brand.
    title_brand = _brand_from_title_prefix(product_name)
    if title_brand:
        return title_brand
    return STANCEUSA_BRAND


def _name_from_dom_fallback(soup: BeautifulSoup) -> Optional[str]:
    """
    Recover a product name when JSON-LD is absent. Enfold ships no OG
    meta on PDP, so we try the ``<h1 class="product_title">`` (clean) and
    then ``<title>`` (site-suffixed) with the suffix stripped.
    """
    h1 = soup.find("h1", class_="product_title")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    h1_generic = soup.find("h1")
    if isinstance(h1_generic, Tag):
        text = h1_generic.get_text(strip=True)
        if text:
            return text
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        text = title_tag.get_text(strip=True)
        if text:
            return _strip_site_suffix(text)
    return None


def _description_from_dom(soup: BeautifulSoup) -> Optional[str]:
    """``<meta name="description">`` fallback; Enfold ships no OG description."""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        content = meta_content(meta_desc)
        if content and content.strip():
            return normalize_description_text(content, max_len=2000)
    return None


def _canonical_image_key(url: str) -> str:
    """Drop WordPress ``-WxH`` size suffix + cache-buster params for dedupe."""
    stripped = _WP_SIZE_SUFFIX_RE.sub("", url)
    stripped = re.sub(r"[?&](ver|v|fit|resize)=[^&]+", "", stripped)
    return stripped.replace("?&", "?").rstrip("?&")


class StanceUsaAdapter(RetailerCrawlerAdapter):
    """
    Stance Suspension USA adapter — WordPress + WooCommerce on nginx.

    Discovery: ``/wp-sitemap.xml`` (WordPress 5.5+ sitemap index) →
    ``wp-sitemap-posts-product-N.xml`` children, collecting every
    ``/shop/<slug>/`` URL. ``CRAWLER_STANCEUSA_START_URLS`` (comma-
    separated) overrides with a fixed list. Falls back to
    ``DEFAULT_START_URLS`` when discovery returns nothing.

    Parsing: JSON-LD ``Product`` first (name, sku, description, image,
    offers), with the Yoast/WooCommerce
    ``offers[0].priceSpecification[0].price`` pulled out when the shared
    reader sees no flat ``offers[0].price``. No OG meta on PDP, so DOM
    fallbacks read ``<h1 class="product_title">`` / ``<title>`` / ``<meta
    name="description">`` directly. Brand is coerced to ``"Stance
    Suspension"`` for the house catalog; known third-party prefixes
    (Swift Springs, Aurora Bearings) pass through so resold components
    keep their real manufacturer.

    Variant axis (spring-rate / fitment, VARIANTS.md §5) is a documented
    loss: WooCommerce variable products collapse to the parent SKU and
    floor price the JSON-LD exposes.
    """

    ADAPTER_NAME: ClassVar[str] = "stanceusa"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Stance Suspension product page into a ``ScrapedPayload``.
        Returns ``None`` when the URL isn't product-shaped or when neither
        JSON-LD nor the DOM fallback yields a usable name.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                clean_name = _strip_site_suffix(payload.name)

                # Yoast/WooCommerce nests price inside
                # offers[0].priceSpecification[0]; the shared reader sees
                # offers[0].price and bails.
                price_cents = payload.price_cents
                if price_cents is None:
                    price_cents = _price_cents_from_price_specification(item)

                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, clean_name)

                # JSON-LD image is typically a single full-res URL; dedupe
                # against WordPress size-variants in case a future theme
                # change inlines multiple gallery shots.
                image_urls: Optional[List[str]] = None
                if payload.image_urls:
                    seen_keys: set[str] = set()
                    cleaned: List[str] = []
                    for raw in payload.image_urls:
                        key = _canonical_image_key(raw)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        cleaned.append(raw)
                        if len(cleaned) >= 12:
                            break
                    image_urls = cleaned or None

                return ScrapedPayload(
                    name=clean_name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # Fallback: no JSON-LD Product block. Recover at least a name (+
        # description, when the <meta name="description"> tag carries one)
        # so extension captures and archive rescrapes still store something
        # useful. Enfold ships no OG meta here, so DOM selectors are the
        # only option.
        name = _name_from_dom_fallback(soup)
        if not name or len(name) < 3:
            return None

        clean_name = _strip_site_suffix(name)
        description = _description_from_dom(soup)
        part_manufacturer = _normalize_part_manufacturer(None, clean_name)

        return ScrapedPayload(
            name=clean_name,
            product_url=url,
            description=description,
            price_cents=None,
            part_manufacturer=part_manufacturer,
            part_number=None,
            image_urls=None,
        )
