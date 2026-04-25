"""
Dinan (dinancars.com) crawler adapter.

Product URLs: ``https://www.dinancars.com/...`` — the root host ``dinancars.com``
301s to ``www.dinancars.com``. Dinan is BMW's longest-running US performance-
parts house-brand (software flashes, Dinantronics piggybacks, cat-back exhausts,
brake kits, suspension kits) and ships parts across the full BMW chassis
catalog — E/F/G-class 3-series/5-series/X-chassis coverage plus some MINI.

**Fetch blocker: Cloudflare managed JS challenge.** Every surface we probed on
2026-04-21 — the homepage, ``/robots.txt``, ``/sitemap.xml``,
``/sitemap_index.xml``, ``/products.json`` — returned HTTP 403 with
``cf-mitigated: challenge`` and a "Just a moment..." interstitial requiring JS
execution and cookie round-trips. Plain ``requests`` (Tier 0) and TLS
impersonation via ``curl_cffi`` (Tier 1) cannot reach product HTML because the
challenge requires JS. Hence ``FETCHER_TIER = "browser"`` — the runner swaps in
FlareSolverr (Tier 2) once ``FLARESOLVERR_URL`` is configured.

**Current scope: parse-only.** Pages arrive via the Chrome extension
(``POST /crawled-pages/scrape``) or the archive rescrape pipeline; both route
through ``adapter_name_for_product_url`` so registering ``dinancars.com`` there
gives captured pages a site-specific parser instead of the generic fallback.
``discover_product_urls`` is a stub until Tier 2 is wired up. Once it is, the
sitemap walker probably needs to follow ``/sitemap.xml`` (shape unconfirmed —
Dinan is described in the retailer backlog as "Shopify or BigCommerce"; we
won't know which until a post-challenge HTML sample is captured).

**Platform:** unconfirmed. The retailer backlog (entry Batch 2A #10) notes
"Shopify or BigCommerce". Behind the CF challenge we can't inspect response
headers (``powered-by``, ``X-AspNet-Version``, ``BCData`` vs Shopify cookies)
or JSON-LD shape directly. The adapter is defensive: it tries ``ProductGroup``
JSON-LD first (the Shopify SEO-app / WooCommerce shape), then falls back to
plain ``Product`` JSON-LD (the Shopify default and BigCommerce-with-schema
shape), and finally to DOM / OG meta heuristics. If the platform turns out to
be BigCommerce without JSON-LD, the DOM fallback will still yield a usable
``name`` / ``price`` / ``description`` via og:title / og:price:amount /
og:description. If we later confirm BigCommerce, this adapter can grow a
``BCData`` extractor like ``xph`` does.

**JSON-LD shape (expected, unverified):** ``ProductGroup`` with
``hasVariant: [Product, ...]`` is the most common pattern on BMW-vertical
storefronts (``burgermotorsports``, ``maperformance``). If that's what Dinan
emits, the first variant wins per ``VARIANTS.md`` §3 row 1 — name / brand /
description come from the group root; sku / price / image come from
``hasVariant[0]``. Other variants (different BMW chassis fitments, different
tune stages) silently drop. This is consistent with every other adapter at
time of writing — each ProductGroup emits exactly one ``ScrapedPayload``.

**Variant strategy:** first-variant-wins when JSON-LD is ``ProductGroup``;
top-level fields as-is when JSON-LD is plain ``Product`` (already flattened
by Shopify). Per ``VARIANTS.md`` §4, the ProductGroup extractor is duplicated
here (fourth/fifth adapter to need it, after ``maperformance``, ``ets``,
``burgermotorsports``, ``texasspeed``). **This task deliberately does not
refactor ``parsing.py``** — promoting ``_extract_product_group_from_json_ld``
to the shared module is a separate piece of work tracked in
``RETAILER_BACKLOG.md`` and ``VARIANTS.md`` §4; until then, the per-adapter
copy documents the exact ProductGroup shape seen on each site.

**Brand canonicalization:** Dinan is a house-brand storefront. Every product
is Dinan-branded, with the occasional partner/co-branded item (e.g. Dinan by
Hartge historical pieces). The JSON-LD ``brand.name`` is the authoritative
source when present. We:

- Pass through the JSON-LD brand value when it's plausible (non-empty, not
  a car make, not a Dinan-name alias).
- Coerce to ``"Dinan"`` when the brand is empty, a car make leaked from a
  title like "BMW F30 335i Tune" (the title heuristic's first-token fallback
  often picks the make on Dinan product pages), or a known Dinan alias.
- ``_CAR_MAKES`` explicitly includes ``"bmw"`` — this is the main coercion
  target on a BMW-vertical retailer. ``"mini"`` is also included for the MINI
  catalog Dinan occasionally carries.

**Caveats:**

- This adapter has never seen a live Dinan product page (Cloudflare blocks
  direct fetches from AWS egress). Selectors and JSON-LD assumptions are
  inferred from the retailer-backlog template (``burgermotorsports``) and
  from how BMW-vertical storefronts usually emit schema.org. First real
  capture via the Chrome extension may reveal theme-specific quirks — in
  particular the image-CDN host (Shopify ``/cdn/shop/`` vs BigCommerce
  ``cdn11.bigcommerce.com``) and whether Dinan surfaces a ``sku`` / ``mpn``
  in JSON-LD or only in the DOM.
- BMW-as-brand guard is load-bearing. Dinan titles lead with the target
  chassis/model (e.g. "BMW F30 335i Dinantronics Sport Tuner"); without the
  coerce, ``part_manufacturer_from_title`` would return ``"BMW"`` and cross-
  retailer dedupe would conflate Dinan parts with OEM BMW parts from ECS /
  Turner / FCP Euro.
- Once a post-challenge HTML sample lands, revisit:
  (a) real JSON-LD shape (Product vs ProductGroup — this adapter handles
  both, but we should document which Dinan actually emits),
  (b) image-CDN allowlist (filter out site chrome / mega-menu banners),
  (c) whether the sitemap is ``/sitemap.xml`` (Shopify/BigCommerce default)
  or a custom shape that needs its own discovery path.

Override live-crawl start URLs (once Tier 2 is live) via
``CRAWLER_DINAN_START_URLS`` (comma-separated).
"""

import json
from typing import Any, ClassVar, Dict, Iterator, List, Optional, cast

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
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

DINAN_BASE = "https://www.dinancars.com"

# Canonical house brand — every Dinan-branded SKU converges on this single
# manufacturer row so we don't split the catalog across "Dinan" / "Dinan Inc" /
# "Dinan Engineering" / car-make leak.
DINAN_BRAND = "Dinan"

# Brand values that should be rewritten to DINAN_BRAND. Car makes leak in when
# the title heuristic picks the first token of a vehicle-targeted title like
# "BMW F30 335i Dinantronics Sport Tuner". BMW and MINI are the main coercion
# targets on this BMW-vertical storefront; keep the list broad enough that the
# occasional non-BMW co-branded item (Dinan by Audi historical pieces) doesn't
# slip through as the car make.
_CAR_MAKES = frozenset(
    {
        "bmw",
        "mini",
        "mercedes",
        "mercedes-benz",
        "audi",
        "porsche",
        "volkswagen",
        "vw",
        "toyota",
        "honda",
        "nissan",
        "infiniti",
        "subaru",
        "lexus",
        "acura",
        "ford",
        "chevrolet",
        "chevy",
    }
)

# Dinan name variants we might see in the JSON-LD brand field or from the
# Shopify / BigCommerce Organization schema. All collapse to DINAN_BRAND.
_DINAN_BRAND_ALIASES = frozenset(
    {
        "dinan",
        "dinan cars",
        "dinancars",
        "dinan engineering",
        "dinan, inc",
        "dinan, inc.",
        "dinan inc",
        "dinan inc.",
        "dinan performance",
    }
)


def _canonical_brand(brand: Optional[str]) -> Optional[str]:
    """
    Apply Dinan-specific brand canonicalization:

    - Empty -> DINAN_BRAND.
    - Car-make values ("BMW", "MINI", ...) -> DINAN_BRAND. BMW is the main
      coercion target: titles like "BMW F30 335i Dinantronics Sport Tuner"
      make the generic title heuristic pick "BMW" as the first plausible
      token, which would wrongly attribute Dinan SKUs to BMW.
    - Dinan name variants ("Dinan Engineering", "Dinan, Inc.", ...) ->
      DINAN_BRAND.
    - Anything else is passed through unchanged so the occasional
      co-branded / partner item keeps its real manufacturer name.
    """
    if not brand or not brand.strip():
        return DINAN_BRAND
    low = brand.strip().lower()
    if low in _CAR_MAKES:
        return DINAN_BRAND
    if low in _DINAN_BRAND_ALIASES:
        return DINAN_BRAND
    return brand.strip()


def _extract_product_group_from_json_ld(html_text: str) -> Optional[Dict[str, Any]]:
    """
    Return the first ``ProductGroup`` JSON-LD block on the page.

    NOTE: duplicated from ``maperformance`` / ``burgermotorsports`` /
    ``ets`` / ``texasspeed``. Per VARIANTS.md §4, the ProductGroup extractor
    is deliberately kept per-adapter until a refactor lifts it into
    ``parsing.py``. Do not merge here — each adapter's copy documents the
    exact shape seen on that site.

    The shared ``extract_json_ld_product`` helper only matches ``@type == "Product"``
    and would skip the ``ProductGroup`` root even when it's what the page
    emits, so we look it up directly here.
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
    """Flatten a variant ``image`` field (string | list[str|{url}]) into a list of URLs."""
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
    Build a ScrapedPayload from a ProductGroup JSON-LD block. Reads name /
    brand / description from the group root and sku / mpn / price / image from
    the first variant (VARIANTS.md §3 row 1: "first variant wins"). Returns
    None if the group has no name.

    Brand canonicalization is deferred to the caller so the raw JSON-LD value
    is preserved here — ``parse_product_page`` applies ``_canonical_brand``
    after merging with DOM fallbacks.
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

    gtin_val = variant.get("gtin13") or variant.get("gtin12") or variant.get("gtin")
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


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery image URLs from the DOM. Without a confirmed-live
    Dinan page we don't know the exact theme selectors (Shopify ``.product__media``
    vs BigCommerce ``.productView-images``), so take a permissive approach:
    og:image first, then any ``<img src>``, capped at 12 and deduped.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or u in seen:
            return
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = DINAN_BASE + u
        if not u.startswith("http"):
            return
        seen.add(u)
        urls.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

    for img in soup.find_all("img", src=True):
        if not isinstance(img, Tag) or len(urls) >= 12:
            break
        src = img.get("src")
        if isinstance(src, str) and src.strip():
            add(src.strip())

    return urls[:12]


class DinanAdapter(RetailerCrawlerAdapter):
    """
    Dinan adapter. Tier 2 (Cloudflare managed JS challenge on every surface).

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``).
    Until then, this adapter is used only for HTML captured through the
    Chrome extension or replayed from the archive. ``discover_product_urls``
    is a stub.

    Parsing: ``ProductGroup`` JSON-LD first (first-variant-wins per
    VARIANTS.md §3 row 1), then plain ``Product`` JSON-LD, then a DOM / og
    fallback. Brand is canonicalized to ``"Dinan"`` when empty, a car make
    ("BMW" / "MINI" — the common title-heuristic leak on this BMW-vertical
    site), or a known Dinan alias; otherwise the JSON-LD value is passed
    through unchanged.
    """

    ADAPTER_NAME: ClassVar[str] = "dinan"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Stub: live crawling requires FlareSolverr. The extension-capture path
        does not go through discovery, so returning an empty iterator is safe
        and keeps the runner from throwing when an operator accidentally kicks
        this adapter off before Tier 2 is deployed.

        When Tier 2 is wired up: honor ``CRAWLER_DINAN_START_URLS`` if set;
        otherwise walk ``/sitemap.xml`` (shape unconfirmed — Shopify sitemap
        index vs BigCommerce ``xmlsitemap.php`` index, depending on which
        platform Dinan runs). First capture via the Chrome extension should
        disambiguate.
        """
        return iter(())

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Dinan product page. Tries ProductGroup JSON-LD first (the
        common schema on BMW-vertical Shopify storefronts), then plain
        Product JSON-LD, then a DOM / og fallback. Returns None when no
        name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. ProductGroup JSON-LD (the shape BMW-vertical Shopify stores
        #    typically emit; first variant wins per VARIANTS.md §3).
        group = _extract_product_group_from_json_ld(html)
        if group:
            payload = _payload_from_product_group(group, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                part_manufacturer = _canonical_brand(payload.part_manufacturer)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=payload.part_number,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 2. Plain Product JSON-LD (the default Shopify / with-schema
        #    BigCommerce shape; variant[0] fields already flattened).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                image_urls = payload.image_urls or (dom_images[:12] if dom_images else None)
                part_manufacturer = _canonical_brand(payload.part_manufacturer)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=normalize_part_number(payload.part_number) if payload.part_number else None,
                    image_urls=image_urls,
                    gtin=payload.gtin,
                )

        # 3. DOM / og fallback — covers BigCommerce-without-schema themes and
        #    any page that doesn't surface JSON-LD late enough for capture.
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

        part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _canonical_brand(part_manufacturer)

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
