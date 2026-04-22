"""
OG Racing (ogracing.com) crawler adapter.

Platform: **Shopify** (Online Store 2.0 theme, served behind Cloudflare — no JS
challenge on product pages, plain ``requests`` returns fully rendered HTML on
first try). Apex ``ogracing.com`` 301s to the canonical ``www.ogracing.com``;
the sibling ``oogracing.com`` is not a Shopify alias (returns an unrelated
lander redirect) and is intentionally not supported here. Plain HTTP is
enough, so ``FETCHER_TIER`` stays at the default ``"http"``.

Product URLs: ``https://www.ogracing.com/products/<handle>``

Discovery: ``/sitemap.xml`` is a standard Shopify sitemap **index** pointing at
``sitemap_products_N.xml?from=…&to=…`` children (plus pages / collections /
blogs siblings we skip). OG Racing also advertises ``en-ca`` locale-prefixed
copies of the same children in the index — those are filtered out to avoid
double-crawling the catalog. Override with ``CRAWLER_OGRACING_START_URLS``
(comma-separated) for a fixed list.

JSON-LD shape: ``@type: Product`` embedded directly (not wrapped in ``@graph``)
with ``brand.name`` populated with the *real* manufacturer, ``offers`` as an
array of ``Offer`` objects — one per purchasable variant — plus top-level
``sku`` / ``gtin`` / ``image`` fields. The shared ``extract_json_ld_product``
returns the Product dict, and ``scraped_payload_from_json_ld`` calls
``_price_from_json_ld`` which reads ``offers[0]`` on arrays — so the first
variant wins on multi-SKU pages (see Variant rule below).

Brand rule (**multi-brand reseller — pass-through**): OG Racing is a safety /
motorsport equipment *reseller*; its catalog is Sparco, OMP, Schroth, Stilo,
Recaro, Bell, Simpson, Alpinestars, AIM, 3M, HANS, and many more third-party
manufacturers. The Shopify JSON-LD carries the real brand on every product
page observed during recon (e.g. ``"Sparco"`` on steering wheels,
``"Simpson"`` on racing shoes, ``"3M"`` on ear plugs). We therefore **pass
JSON-LD brand through unchanged whenever it is non-empty**. We only fall
back to the canonical ``"OG Racing"`` when JSON-LD brand is missing/empty
*and* the shared title / description heuristics also come up dry — matching
the IND / MAPerformance playbook rather than the house-brand ADRO / 034
playbook. Car-make values picked by the title heuristic (BMW / Porsche /
Toyota / Subaru / …) are rejected so the catalog doesn't grow phantom
manufacturer rows from titles like "Sparco BMW Fitment Kit".

Variant rule (per ``adapters/VARIANTS.md`` §5): safety gear is *the* canonical
case where variants matter — helmets come in shell sizes (S / M / L / XL),
shoes in half sizes (6 / 6.5 / 7 / …), racing suits in chest/height sizes,
harnesses in strap width + certification rating (SFI 16.1, FIA 8853-2016),
seats in shell size + HANS/non-HANS variants. Every OG Racing PDP with more
than one purchasable SKU emits an ``offers: []`` array with one ``Offer``
per variant and a per-variant URL ``?variant=<id>``. Per the cross-adapter
pattern documented in VARIANTS.md §3, we **take the first offer** — same
"one Part per URL" contract as every other Shopify adapter. Consequences
carried forward: the stored ``part_number`` / ``price_cents`` / ``gtin``
are the first listed variant's (usually the smallest size in stock), not
an aggregate. Until first-class variant support lands (Option D), this is
the documented rule for this site — users shopping a specific size should
click through to ogracing.com. Different brands' SKU conventions are
preserved verbatim via ``normalize_part_number``; Simpson ships SKUs with
padded internal whitespace (``"SIMT      600 BLK"``) which we leave
unchanged rather than silently rewriting a manufacturer's part number.

Tier rationale: Product HTML returns 200 with full JSON-LD on plain curl
(Cloudflare on this origin does not challenge ``requests``), so Tier 0.
Promote to Tier 1 only if CF ever starts gating the storefront.

Caveats:
- ``gtin`` is present on every offer but the shared
  ``scraped_payload_from_json_ld`` doesn't plumb it into ``ScrapedPayload.gtin``
  today — same as every other Shopify-JSON-LD adapter. Left as-is rather
  than forking the helper; fix in ``parsing.py`` when a dedupe path needs it.
- Top-level ``sku`` / ``gtin`` on multi-variant pages match ``offers[0]``
  (verified on Simpson Midtop shoes) — no risk of variant-mismatch from
  reading the top-level fields instead of descending into offers.
- Locale-prefixed sitemap children (``/en-ca/sitemap_products_*.xml``) list
  the same products as the primary children with localized pricing; we
  discard them to avoid crawling every SKU twice.
"""

import os
import re
import time
from typing import Iterator, List, Optional
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

OGRACING_BASE = "https://www.ogracing.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Verified live product URLs used as a fallback when sitemap discovery fails
# and no env override is provided. Spans three distinct brands so the first
# crawl exercises the multi-brand pass-through path end-to-end rather than
# a single manufacturer's JSON-LD shape.
DEFAULT_START_URLS = [
    "https://www.ogracing.com/products/sparco-215-competition-steering-wheel-1",
    "https://www.ogracing.com/products/simpson-midtop-racing-shoes",
    "https://www.ogracing.com/products/3m-ear-plugs",
]

# Car makes that the title heuristic sometimes picks when a product title
# leads with the target vehicle ("Sparco BMW M3 Harness Kit"). OG Racing
# resells from dozens of third-party manufacturers, so — like IND — we drop
# the car-make value rather than coerce to a house brand; JSON-LD brand (the
# primary path) always wins before we reach this guard.
_TITLE_CAR_MAKES = frozenset(
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
        "mini",
        "vw",
        "volkswagen",
        "mazda",
        "mitsubishi",
        "scion",
    }
)

# Tokens the title heuristic occasionally picks that are generic product
# nouns, not manufacturer names.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem", "racing"})

# Shopify CDN thumbnail size suffix (e.g. file_300x300.jpg). Rejected so the
# full-resolution gallery media wins over theme thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap.xml, then hard-coded default."""
    raw = os.environ.get("CRAWLER_OGRACING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """
    True if ``url`` is a primary ``sitemap_products_N.xml`` child. Excludes
    OG Racing's ``/en-ca/sitemap_products_*.xml`` locale mirrors, which list
    the same products under localized URLs — crawling both would double-count
    every SKU.
    """
    if "/sitemap_products_" not in url:
        return False
    # Reject locale-prefixed mirrors (en-ca, en-gb, etc.).
    # Primary children live at the site root: /sitemap_products_1.xml.
    # Locale mirrors live under /<locale>/sitemap_products_1.xml.
    tail = url.split("://", 1)[-1]
    path = tail.split("/", 1)[1] if "/" in tail else ""
    # path looks like "sitemap_products_1.xml?..." (primary) or
    # "en-ca/sitemap_products_1.xml?..." (locale mirror). Anything with a
    # leading path segment before "sitemap_products_" is a locale mirror.
    first_segment = path.split("/", 1)[0] if "/" in path else path
    return first_segment.startswith("sitemap_products_")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → each primary
    ``sitemap_products_N.xml`` child urlset and collect every
    ``/products/<handle>`` URL. Skips the pages / collections / blogs
    siblings and the ``en-ca`` locale mirrors. Returns a deduplicated list
    (by URL with query stripped); empty on failure.
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
            # Skip locale-prefixed product URLs — Shopify emits
            # ``/en-ca/products/<handle>`` entries in the locale mirror
            # sitemaps; we only want the primary storefront copy.
            if "/en-ca/products/" in u:
                continue
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = OGRACING_BASE + "/sitemap.xml"
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


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> Optional[str]:
    """
    Trim whitespace; drop car-make / reject-token values. Returns ``None``
    rather than coercing to a house brand because OG Racing is a multi-brand
    reseller — the honest answer when JSON-LD and all heuristics come up dry
    is "unknown", not "OG Racing" attached to somebody else's harness.

    JSON-LD brand (the primary path) always wins before we reach here, so
    pass-through for Sparco / Simpson / Stilo / OMP / Bell / Schroth / etc.
    happens upstream of this normalizer.
    """
    if not part_manufacturer:
        return part_manufacturer
    brand = part_manufacturer.strip()
    if not brand:
        return None
    low = brand.lower()
    if low in _TITLE_CAR_MAKES:
        return None
    if low in _BRAND_REJECT_TOKENS:
        return None
    return brand


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against ogracing.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return OGRACING_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only Shopify CDN product media (storefront proxy or bare cdn.shopify.com); reject chrome and thumbnails."""
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
    """
    Gather product gallery image URLs from the DOM (Shopify CDN only),
    deduped and capped at 12. Tries modern ``<media-gallery>`` first, then
    Dawn/OS 2.0 theme wrappers, then a bounded sweep of all ``<img>`` tags
    as a last resort.
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

    og_img = soup.find("meta", property="og:image:secure_url") or soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add(content.strip())

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
        for img in soup.find_all("img", src=True):
            if not isinstance(img, Tag) or len(ordered) >= 12:
                break
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())

    return ordered[:12]


def _extract_full_description_from_dom(soup: BeautifulSoup, max_len: int = 2000) -> Optional[str]:
    """
    DOM description fallback when JSON-LD description is missing/short. Scans
    Shopify theme selectors and long ``<p>`` tags inside ``<main>``. Takes
    the longest candidate.
    """
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
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main and isinstance(main, Tag):
        for p in main.find_all("p"):
            if not isinstance(p, Tag):
                continue
            t = p.get_text(strip=True)
            if t and len(t) > 150:
                candidates.append(t)
    if not candidates:
        return None
    best = max(candidates, key=len)
    return normalize_description_text(best, max_len=max_len)


class OGRacingAdapter(RetailerCrawlerAdapter):
    """
    OG Racing adapter. Discovery: Shopify sitemap index → primary
    ``sitemap_products_N.xml`` children (locale mirrors skipped). Parsing:
    JSON-LD ``Product`` first (authoritative on this storefront — brand /
    sku / price / description / image all populated), with DOM + og fallbacks
    for the rare page that ships no JSON-LD.

    Brand is **passed through** whenever JSON-LD gives a non-empty value
    (Sparco / Simpson / Stilo / OMP / Schroth / Bell / Recaro / 3M / …). When
    JSON-LD brand is missing and every heuristic fails, we return ``None``
    rather than coerce to "OG Racing" — the site is a reseller, so the honest
    unknown is better than a phantom manufacturer row. On multi-variant
    pages the first offer wins (VARIANTS.md §3); other sizes / ratings /
    colors are silently dropped until first-class variant support lands.
    """

    # Default Tier 0 — plain HTTP is enough (Cloudflare on this origin does
    # not challenge ``requests``). Left explicit so the choice is documented
    # on the class itself rather than only in the module docstring.
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``sitemap.xml`` (primary
        ``sitemap_products_*`` children only; locale mirrors filtered out).
        Set ``CRAWLER_OGRACING_START_URLS`` (comma-separated) to override
        with a fixed list. A jittered delay is applied between
        sitemap-child fetches inside ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an OG Racing product page.

        1. JSON-LD ``Product`` (authoritative) — name, description, brand,
           sku, price (first offer on multi-variant pages), cover image.
           Merge DOM gallery images on top of the single-URL JSON-LD cover
           so we keep the full carousel.
        2. DOM / og fallback — h1/og:title, meta description, DOM price,
           SKU via text scan, brand via shared title/description heuristics.

        Returns ``None`` when no usable name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (authoritative on Shopify).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                description = payload.description
                if not description or len(description) < 50:
                    dom_desc = _extract_full_description_from_dom(soup)
                    if dom_desc and len(dom_desc) > len(description or ""):
                        description = dom_desc
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)

                # JSON-LD image is typically a single ImageObject; merge
                # DOM-discovered gallery so we get the full carousel.
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
                    description=description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback.
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
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer)

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
