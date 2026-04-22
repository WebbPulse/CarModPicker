"""
Perrin Performance (perrin.com) crawler adapter.

Platform: **Shopify**. The apex ``perrinperformance.com`` 301s to
``perrin.com`` — that is the live storefront (``www.perrin.com`` also 301s
in). The second candidate, ``perrinperf.com``, is NXDOMAIN as of recon
(2026-04-21) and is not used; kept here only as a documented non-alias so
the next author doesn't chase it. Served behind Cloudflare with no JS
challenge — plain ``requests`` returns a fully rendered HTML page — so
``FETCHER_TIER`` stays at the default ``"http"``.

Product URLs: ``https://perrin.com/products/<handle>``

Discovery: ``/sitemap.xml`` is a standard Shopify sitemap **index** with a
``sitemap_products_1.xml?from=…&to=…`` child plus the usual pages /
collections / blogs siblings — only the ``sitemap_products_*`` child hosts
real product URLs. Override with ``CRAWLER_PERRINPERFORMANCE_START_URLS``
(comma-separated) for a fixed list.

JSON-LD shape: ``@type: ProductGroup`` with a ``hasVariant: [Product, ...]``
array — the same schema MAPerformance emits, **not** the plain ``Product``
that most Shopify stores serve. The shared ``extract_json_ld_product`` only
matches ``@type == "Product"``, so we ship our own ProductGroup-aware
extractor here (mirroring ``maperformance.py`` / ``ets.py`` /
``burgermotorsports.py``).

Brand handling: Perrin is **effectively 100% a house brand** — the catalog
is entirely their own intakes, inlet hoses, chassis braces, shifters,
engine covers, cosmetic kits, etc. JSON-LD ships ``brand.name = "PERRIN"``
(all caps). We pass JSON-LD brand through when it's non-empty and not a
reject value, and coerce empty / car-make / self-variant values to the
canonical ``"Perrin Performance"`` so the catalog doesn't grow both
``PERRIN`` and ``Perrin Performance`` rows, nor a phantom ``Subaru``
manufacturer from the title heuristic falling through on titles like
``"2015 WRX Cold Air Intake"``. Reject tokens + car-makes list lifted from
``grimmspeed`` and trimmed to the Subaru-adjacent platforms Perrin covers
(Subaru, Toyota / Scion — 86/FR-S, Ford — Focus ST/RS, which Perrin had
a small line for).

Variant handling rule (per VARIANTS.md §3 row 1): **parent URL only; first
variant wins** — top-level sku / price / image come from ``hasVariant[0]``.
Perrin's variant axis is typically finish / color (Red / Black / Hyper
Pink) at the same price, so the loss is mostly cosmetic, but it's still
Option A status-quo: all-but-first variants are silently dropped. When
variants become a blocker here, Option B (per-variant URL ingest via
``?variant=<id>``) is the path — every variant does have a deep-link URL
in the Offer entry.

Images: Shopify CDN (``perrin.com/cdn/shop/files/…``). Dedupe via the
shared ``_canonical_image_key`` / ``_normalize_image_url`` /
thumbnail-regex pattern used in grimmspeed and maperformance so width /
v-cachebuster variants of the same asset collapse.

Tier rationale: Plain Shopify served through Cloudflare with no JS
challenge — ``curl`` returns complete HTML with the ProductGroup JSON-LD
on first try. No reason to pay the Tier 1 / Tier 2 cost.
"""

import json
import os
import re
import time
from typing import Any, Dict, Iterator, List, Optional, cast
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

PERRIN_BASE = "https://perrin.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

PERRIN_BRAND = "Perrin Performance"

# Verified live product URLs (recon 2026-04-21). Used as fallback when sitemap
# discovery fails and no env override is provided. Picked across the catalog
# so the first crawl exercises the ProductGroup JSON-LD path end to end.
DEFAULT_START_URLS = [
    "https://perrin.com/products/2008-2015-wrx-sti-cold-air-intake",
    "https://perrin.com/products/turbo-inlet-hose-for-2015-2021-wrx-forester-xt",
]

# Car makes Perrin covers — titles frequently lead with the chassis
# ("2015 WRX Cold Air Intake") so the first-token title heuristic can
# misfire to one of these. Coerce to the canonical Perrin Performance name
# when that happens.
_CAR_MAKES = frozenset(
    {
        "subaru",
        "toyota",
        "scion",
        "ford",
    }
)

# Generic words sometimes picked by the first-token title heuristic.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem"})

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg, file_100x100.webp).
# Rejected so we keep full-resolution gallery media over theme thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap.xml, then hard-coded default."""
    raw = os.environ.get("CRAWLER_PERRINPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` child sitemap."""
    return "/sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` → each ``sitemap_products_N.xml`` child urlset and
    collect every ``/products/<handle>`` URL. Skips ``sitemap_pages_*`` /
    ``sitemap_collections_*`` / ``sitemap_blogs_*`` siblings — none host
    product pages. Returns a deduplicated list (by URL with query stripped);
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
            if PRODUCT_PAGE_PATH not in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = PERRIN_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
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
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Find the first ``ProductGroup`` JSON-LD block. Perrin emits ProductGroup
    at the page level with a ``hasVariant: [Product, ...]`` array; the shared
    extractor only matches plain ``Product`` so we look it up here.
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


def _payload_from_product_group(group: Dict[str, Any], product_url: str) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a ProductGroup JSON-LD block. Reads
    brand/description/name from the group root and sku/price/gtin/image from
    the first variant. Returns None if the group has no name.
    """
    name_val = group.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None

    brand_val = group.get("brand")
    brand: Optional[str] = None
    if isinstance(brand_val, str) and brand_val.strip():
        brand = brand_val.strip()
    elif isinstance(brand_val, dict):
        bn = brand_val.get("name")
        if isinstance(bn, str) and bn.strip():
            brand = bn.strip()

    description: Optional[str] = None
    desc_val = group.get("description")
    if isinstance(desc_val, str) and len(desc_val.strip()) > 10:
        description = normalize_description_text(desc_val, max_len=2000)

    variant = _first_variant(group) or {}
    sku_val = variant.get("sku") or variant.get("mpn") or group.get("productID")
    part_number = normalize_part_number(sku_val) if isinstance(sku_val, str) else None
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


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> str:
    """
    Return the canonical manufacturer for a Perrin product page.

    - Empty / car-make / reject-token / any case-folded "PERRIN"-variant →
      coerce to the canonical ``"Perrin Performance"``. Perrin emits the
      brand in all-caps (``"PERRIN"``) and occasionally as ``"PERRIN
      PERFORMANCE"``; both collapse to the canonical form.
    - Anything else passes through unchanged (belt-and-suspenders — Perrin is
      functionally a single-brand catalog so this path is essentially dead,
      but the cost is zero).
    """
    _ = product_name
    brand = (part_manufacturer or "").strip()
    if not brand:
        return PERRIN_BRAND
    low = brand.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return PERRIN_BRAND
    if low == "perrin" or low.startswith("perrin ") or low.startswith("perrin-"):
        return PERRIN_BRAND
    return brand


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against perrin.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return PERRIN_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify CDN product media; reject chrome and thumbnails."""
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
    """Drop Shopify v/width/height/crop params so width variants of the same asset collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """Collect product gallery image URLs from the DOM (Shopify CDN only), deduped, capped at 12."""
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

    scope: Optional[Tag] = None
    gallery = soup.find("media-gallery")
    if isinstance(gallery, Tag):
        scope = gallery
    else:
        for selector in (
            ".product__media-wrapper",
            ".product-single__media",
            ".product-images",
            ".product-gallery",
        ):
            candidate = soup.select_one(selector)
            if isinstance(candidate, Tag):
                scope = candidate
                break

    if scope is not None:
        for img in scope.find_all("img"):
            if not isinstance(img, Tag):
                continue
            for attr in ("src", "data-src", "data-original", "data-srcset"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    first = val.strip().split(",")[0].strip().split(" ")[0]
                    if first:
                        add(first)
                        break
    else:
        for img in soup.find_all("img"):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            for attr in ("src", "data-src", "data-original"):
                val = img.get(attr)
                if isinstance(val, str) and val.strip():
                    add(val.strip())
                    break

    return ordered[:12]


class PerrinPerformanceAdapter(RetailerCrawlerAdapter):
    """
    Perrin Performance adapter. Discovery: Shopify sitemap index →
    ``sitemap_products_N.xml`` children. Parsing: ProductGroup JSON-LD first
    (the schema Perrin actually emits — variant[0] carries sku/price/image),
    then plain Product JSON-LD as a defensive fallback, then DOM / og. Brand
    is coerced to the canonical ``"Perrin Performance"`` since the catalog
    is effectively house-brand only and JSON-LD ships ``"PERRIN"`` / ``"PERRIN
    PERFORMANCE"`` which would otherwise grow two manufacturer rows.
    """

    # Default Tier 0 — plain HTTP is enough (Cloudflare on this origin does
    # not challenge ``requests``). Left explicit so the choice is documented
    # on the class itself rather than only in the module docstring.
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``sitemap.xml`` (minus non-product
        children). Set ``CRAWLER_PERRINPERFORMANCE_START_URLS`` (comma-separated)
        to override with a fixed list. A jittered delay is applied between
        sitemap-child fetches inside ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Perrin Performance product page.

        1. ProductGroup JSON-LD (the authoritative path on this store) —
           name / description / brand from the group root, sku / price /
           image from ``hasVariant[0]``. Merge DOM gallery on top so we
           don't drop to a single hero image.
        2. Plain Product JSON-LD — defensive fallback for any page where
           Perrin's SEO app doesn't ship the ProductGroup wrapper.
        3. DOM / og fallback — h1/og:title, meta description, DOM price,
           SKU via text scan, brand via shared title/description heuristics.

        Returns ``None`` when no usable name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. ProductGroup JSON-LD (the path that fires on real Perrin pages).
        group = _extract_product_group_from_json_ld(html)
        if group:
            payload = _payload_from_product_group(group, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)

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

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=payload.part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. Plain Product JSON-LD fallback.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)

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

                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 3. DOM / og fallback.
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
