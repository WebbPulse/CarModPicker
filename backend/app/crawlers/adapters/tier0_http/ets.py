"""
Extreme Turbo Systems (extremeturbosystems.com) crawler adapter.

The Evo/DSM/Supra/GTR forced-induction specialist — intercoolers, turbo
manifolds, charge pipe kits, exhaust manifolds, and related hardware. Almost
every SKU is an ETS house-brand product; third-party pass-through inventory
is the rare exception.

Live domain: ``https://www.extremeturbosystems.com`` (the candidate
``ets-racing.com`` serves an expired cert and does not resolve to this
business). Platform: Shopify. Robots.txt is the stock Shopify template;
``/products/<handle>`` URLs are allowed — no custom crawl rules to worry about.

Fetcher tier: ``http`` — plain ``requests`` with the default crawler UA
clears Shopify cleanly; no Cloudflare / JA3 wall, no JS challenge. No reason
to pay the Tier-1 / Tier-2 cost here.

Sitemap shape: ``/sitemap.xml`` is a Shopify *sitemap index* whose ``<loc>``
entries already include the required ``?from=&to=`` range query — loading
those child URLs without the query returns HTTP 400, so we must preserve the
full URL string from the index. Children include ``sitemap_products_1.xml``
(the only one we care about), plus ``sitemap_pages_*``,
``sitemap_collections_*``, ``sitemap_blogs_*``. The index also mirrors every
child under ``/en-ca/...`` which yields duplicate product URLs at a different
locale path; we filter that locale out rather than dedupe after fetch, since
the main-domain list is the canonical one.

Parsing: each product page emits JSON-LD as ``@type: ProductGroup`` with a
``hasVariant: [Product, ...]`` array (36+ variants on a typical intercooler —
size / inlet-outlet / core color / stencil). The shared
``extract_json_ld_product`` only matches plain ``@type: "Product"`` so it
misses ETS entirely; we walk the same script tags looking for ``ProductGroup``
and pull brand/description/name from the group, sku/price/image from the
first variant (MAPerformance uses the exact same pattern — see its adapter
for the rationale on "first variant is representative"). Variant ``name``
fields look like ``"<product title> - <size> - <inlet/outlet> / <color>"``,
so we prefer ``group.name`` for the stored product name.

Brand handling: JSON-LD ``brand.name`` is authoritative and reads
``"Extreme Turbo Systems"`` on every ETS-house product we've sampled — we
pass that through verbatim. When brand is missing or when the generic title
heuristic would pick a target-vehicle token (``Mitsubishi``, ``Evo``,
``Subaru``, ``Toyota``, …) or the retailer acronym (``ETS``) from titles
like ``"ETS 90-94 Mitsubishi Eclipse 1G 7\" Street Intercooler"``, we coerce
to the canonical ``"Extreme Turbo Systems"``. Legitimate third-party brands
(TiAL, Garrett, BorgWarner, Mishimoto, …) slipping through the catalog keep
their own identity via the shared ``part_manufacturer_from_title`` path.

Images: Shopify CDN product media (``cdn.shopify.com/s/files/...`` and
``/cdn/shop/files/...``); we take variant ``image`` first (full resolution,
widthed to 1920) then fall back to DOM sweep within the product media scope,
rejecting site chrome (mega-menu, logos, placeholders) and Shopify responsive
thumbnails. Deduped by canonical URL (dropping ``?v=`` / ``?width=``
variants) and capped at 12.

Discovery: override with ``CRAWLER_ETS_START_URLS`` (comma-separated).
"""

import json
import os
import re
import time
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast
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

ETS_BASE = "https://www.extremeturbosystems.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical form of the house brand on this site. JSON-LD already emits this
# verbatim, so passing brand through works in the common case; the normalizer
# below coerces the handful of misses (missing brand, title heuristic picking
# "ETS" / a car make) onto the same string so we don't split the catalog
# across "ETS" and "Extreme Turbo Systems" rows in the PartManufacturer table.
ETS_HOUSE_BRAND = "Extreme Turbo Systems"

# A single verified product URL for environments where sitemap discovery is
# disabled / blocked. Kept short because the live sitemap carries 300+ real
# product URLs and is the expected source in production.
DEFAULT_START_URLS = [
    "https://www.extremeturbosystems.com/products/ets-90-94-mitsubishi-eclipse-1g-7-street-intercooler",
    "https://www.extremeturbosystems.com/products/ets-95-99-mitsubishi-eclipse-2g-7-street-intercooler-2-5-inout",
]

# Values (JSON-LD brand, or the generic title-first-token heuristic) that
# should be replaced with ETS_HOUSE_BRAND because they name the target
# vehicle or the retailer acronym, not an actual part manufacturer. Kept
# lowercase; compared space-stripped.
_BRAND_COERCE_TOKENS = frozenset(
    {
        # Retailer acronym — title heuristic picks "ETS" as the first word.
        "ets",
        # Vehicle makes ETS targets (every product name leads with one).
        "mitsubishi",
        "subaru",
        "toyota",
        "nissan",
        "honda",
        "mazda",
        "ford",
        "chevrolet",
        "chevy",
        "lexus",
        # Chassis / model short-hands that sometimes trip the heuristic.
        "evo",
        "evox",
        "dsm",
        "supra",
        "wrx",
        "sti",
        "gtr",
        "brz",
    }
)

# Shopify CDN responsive-size suffix (e.g. ``_300x300.jpg``). We skip these
# so the stored gallery is full-resolution product photography, not the
# picker thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome (logos, mega-menu, banners) rather
# than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap index, then default."""
    raw = os.environ.get("CRAWLER_ETS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_main_locale_product_sitemap(url: str) -> bool:
    """
    True if ``url`` is a main-domain ``sitemap_products_*.xml`` child (not an
    ``/en-ca/`` locale mirror, not a pages/collections/blogs child).

    The Shopify index repeats every product URL under ``/en-ca/`` with an
    identical product handle — fetching both just doubles discovery work for
    the same products. Pages / collections / blogs don't carry
    ``/products/<handle>`` URLs so skipping them isn't strictly required, but
    it saves a round-trip per extra child.
    """
    if "/en-ca/" in url:
        return False
    return "sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → main-locale ``sitemap_products_*.xml`` children
    and collect every ``/products/<handle>`` URL. Returns a deduplicated list
    (keyed by canonical path, query stripped); empty on failure.

    Notes:
    - The index's child ``<loc>`` entries include a mandatory ``?from=&to=``
      range query. Fetching the child sitemap without that query returns
      HTTP 400, so we pass the URL through verbatim.
    - Individual product ``<loc>`` entries in the child urlset do not carry
      tracking query params; we still strip any trailing query before dedup
      as a belt-and-braces measure.
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
            # en-ca locale URLs would duplicate the main-domain products; drop
            # them here in case a future sitemap shape inlines them.
            if "/en-ca/" in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = ETS_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            fetched = 0
            for child_url in child_sitemap_urls:
                if not _is_main_locale_product_sitemap(child_url):
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
            # Sitemap is a flat urlset (fallback case — not what Shopify
            # actually emits today, but cheap to handle).
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Find the first ``ProductGroup`` JSON-LD block. ETS's Shopify SEO app emits
    ``ProductGroup`` with ``hasVariant: [Product, ...]``; the shared extractor
    only matches ``@type == "Product"`` so it misses ETS entirely.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            items = cast(List[Dict[str, Any]], data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = cast(List[Dict[str, Any]], data["@graph"])
            else:
                items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "ProductGroup" or (isinstance(t, list) and "ProductGroup" in t):
                return item
    return None


def _first_variant(group: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the first Product entry from a ProductGroup's hasVariant array."""
    variants = group.get("hasVariant")
    if not isinstance(variants, list):
        return None
    for v in variants:
        if isinstance(v, dict):
            return v
    return None


def _offer_price_cents(variant: Dict[str, Any]) -> Optional[int]:
    """Pull the first usable price from a variant's ``offers`` (list or dict)."""
    offers = variant.get("offers")
    if isinstance(offers, list) and offers:
        offer = offers[0] if isinstance(offers[0], dict) else None
    elif isinstance(offers, dict):
        offer = offers
    else:
        offer = None
    if not isinstance(offer, dict):
        return None
    for key in ("price", "lowPrice"):
        raw = offer.get(key)
        if raw is None:
            continue
        try:
            num = float(str(raw).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if num > 0:
            return int(round(num * 100))
    return None


def _images_from_variant(variant: Dict[str, Any]) -> List[str]:
    """Normalize the ``image`` field of a variant into a plain list of URLs."""
    img = variant.get("image")
    if not img:
        return []
    raw_list = [img] if isinstance(img, str) else (img if isinstance(img, list) else [])
    out: List[str] = []
    for entry in raw_list:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
        elif isinstance(entry, dict) and entry.get("url"):
            out.append(str(entry["url"]).strip())
    return out


def _brand_from_group(group: Dict[str, Any]) -> Optional[str]:
    """Extract ``brand.name`` from a ProductGroup (string or ``{name}`` dict)."""
    brand_val = group.get("brand")
    if isinstance(brand_val, str) and brand_val.strip():
        return brand_val.strip()
    if isinstance(brand_val, dict):
        bn = brand_val.get("name")
        if isinstance(bn, str) and bn.strip():
            return bn.strip()
    return None


def _payload_from_product_group(group: Dict[str, Any], product_url: str) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a ProductGroup JSON-LD block. Reads brand /
    description / name from the group root and price / sku / image from the
    first variant. Returns None if the group has no name.

    Why first-variant: ETS variants are all the same physical part at
    different dress-up options (core color, inlet size, stencil). The first
    variant's SKU is the representative MPN; other variants typically just
    append option codes. Pricing is identical across variants in practice.
    """
    name_val = group.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None

    brand = _brand_from_group(group)

    description: Optional[str] = None
    desc_val = group.get("description")
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    variant = _first_variant(group) or {}
    sku_val = variant.get("sku") or variant.get("mpn") or group.get("productID")
    part_number = normalize_part_number(sku_val) if isinstance(sku_val, str) else None
    # Shape guard: ETS's storefront occasionally writes the H1/title into
    # ``variant.sku`` (e.g. ``"ETS Snap Back Hat"`` on merch). That pollutes
    # the canonical key — drop the SKU when it equals the name modulo case
    # and whitespace. Real ETS SKUs are alphanumeric codes ("400-30-1010")
    # that never collide with the rendered name.
    if part_number and name:
        if re.sub(r"\s+", "", part_number).lower() == re.sub(r"\s+", "", name).lower():
            part_number = None
    price_cents = _offer_price_cents(variant) if variant else None

    gtin_val = variant.get("gtin") or variant.get("gtin13") or variant.get("gtin12")
    gtin = gtin_val.strip() if isinstance(gtin_val, str) and gtin_val.strip() else None

    images = _images_from_variant(variant) if variant else []
    if not images:
        group_imgs = group.get("image")
        if isinstance(group_imgs, str) and group_imgs.strip():
            images = [group_imgs.strip()]
        elif isinstance(group_imgs, list):
            images = [str(i).strip() for i in group_imgs if isinstance(i, str) and i.strip()]

    return ScrapedPayload(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=price_cents,
        part_manufacturer=brand,
        part_number=part_number,
        image_urls=images[:12] if images else None,
        gtin=gtin,
    )


def _normalize_part_manufacturer(raw_brand: Optional[str]) -> str:
    """
    Return the canonical manufacturer for an ETS product.

    - JSON-LD brand that is already ``"Extreme Turbo Systems"`` (or any
      lowercase / whitespace / ``"ETS"`` variant) → canonical house brand.
    - Missing brand, car-make brand, retailer-acronym brand → house brand.
    - Everything else (legit third-party vendor) passes through unchanged.

    The token check uses the space-stripped lowercase form so multi-word
    values (``"Extreme Turbo Systems"`` vs ``"ExtremeTurboSystems"``) and
    case variants all collapse correctly.
    """
    if not raw_brand or not raw_brand.strip():
        return ETS_HOUSE_BRAND

    normalized = raw_brand.strip()
    low = normalized.lower()
    stripped = re.sub(r"\s+", "", low)

    # All the house-brand spellings we've observed on ETS pages or that the
    # fallback heuristic could produce. Coerce to the single canonical form.
    if stripped in {"ets", "extremeturbosystems", "extremeturbo", "extreme"}:
        return ETS_HOUSE_BRAND
    if "extremeturbosystems" in stripped:
        return ETS_HOUSE_BRAND

    # Target-vehicle tokens that the generic title heuristic can pick up from
    # "ETS <year> <make> <model> <part>" titles.
    if stripped in _BRAND_COERCE_TOKENS:
        return ETS_HOUSE_BRAND

    return normalized


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against ETS."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return ETS_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify product-CDN images; reject site chrome and thumbnails."""
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


def _canonical_image_key(url: str) -> str:
    """Drop Shopify v/width/height/crop params so responsive variants collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs from the DOM (Shopify CDN only),
    deduped, capped at 12. Used as a fallback when the ProductGroup variant
    doesn't carry an ``image`` field.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    # Prefer og:image first so the hero leads, then sweep <img> tags in the
    # product media scope (Shopify's Dawn-style themes render all gallery
    # images as <img> in the main section).
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src", "data-original"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break

    return ordered[:12]


class ETSAdapter(RetailerCrawlerAdapter):
    """
    Extreme Turbo Systems adapter.

    Tier 0 (``http``) — plain ``requests`` is sufficient; no anti-bot wall.

    Discovery: ``/sitemap.xml`` (Shopify sitemap index) →
    ``sitemap_products_1.xml?from=&to=`` child urlset. ``/en-ca/`` locale
    mirrors and non-product children are skipped. Env override:
    ``CRAWLER_ETS_START_URLS`` (comma-separated).

    Parsing: ``ProductGroup`` JSON-LD first (variant[0] for sku/price/image),
    then plain ``Product`` JSON-LD, then a DOM / og fallback. Brand is
    normalized so ETS / car-make / missing values all resolve to the
    canonical ``"Extreme Turbo Systems"`` manufacturer; third-party brands
    (TiAL, Garrett, …) pass through unchanged.
    """

    ADAPTER_NAME: ClassVar[str] = "ets"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an ETS product page. Tries ProductGroup JSON-LD first (the
        schema ETS actually emits), then plain Product JSON-LD, then a DOM /
        og fallback. Returns ``None`` only when no name can be extracted —
        missing brand / price / SKU are tolerated (brand defaults to the
        house brand, price falls back to DOM ``$...`` pattern).
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. ProductGroup JSON-LD (the real path on every live ETS PDP).
        group = _extract_product_group_from_json_ld(html)
        if group:
            payload = _payload_from_product_group(group, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=_normalize_part_manufacturer(payload.part_manufacturer),
                    part_number=payload.part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. Plain Product JSON-LD (defensive — not observed on ETS today,
        # but cheap to try before falling through to the DOM fallback).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                jsonld_pn = normalize_part_number(payload.part_number) if payload.part_number else None
                # Same shape guard as the ProductGroup path above: drop SKU
                # values that echo the H1/title (storefront leak from empty
                # SKU fields).
                if jsonld_pn and re.sub(r"\s+", "", jsonld_pn).lower() == re.sub(r"\s+", "", payload.name).lower():
                    jsonld_pn = None
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=_normalize_part_manufacturer(payload.part_manufacturer),
                    part_number=jsonld_pn,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 3. DOM / og fallback: og:title, og:description, DOM price, SKU
        # regex, first-token brand heuristic. Almost never reached — the
        # ProductGroup block is always present on live PDPs — but keeps
        # parse-only callers (archive rescrape, extension capture) safe.
        name: Optional[str] = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if isinstance(h1, Tag):
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
        if not name or len(name) < 3:
            return None

        description: Optional[str] = None
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            d = meta_content(og_desc)
            if d and d.strip():
                description = normalize_description_text(d, max_len=2000)
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000)

        price_cents = dom_price
        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        brand_candidate: Optional[str] = part_manufacturer_from_title(str(name))
        if not brand_candidate and description:
            brand_candidate = part_manufacturer_from_description(description, product_name=str(name))
        if not brand_candidate:
            brand_candidate = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _normalize_part_manufacturer(brand_candidate)

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
