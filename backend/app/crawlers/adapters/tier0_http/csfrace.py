"""
CSF Race (csfrace.com) crawler adapter.

**Platform — Shopify.** The response carries ``powered-by: Shopify`` and the
full set of Shopify cookies (``_shopify_y`` / ``_shopify_s`` /
``_shopify_essential``). Apex ``csfrace.com`` is the canonical host; ``www.``
issues a 301 to the apex (``x-redirect-reason: canonical_host_redirection``).
The historical ``csf-radiators.com`` domain does not resolve and is not used
here. Plain ``requests`` (Tier 0) pulls fully rendered HTML with JSON-LD on
the first try — Cloudflare sits in front but does not challenge.

**Sitemap shape.** ``/robots.txt`` does not advertise ``Sitemap:`` lines, but
the standard Shopify ``/sitemap.xml`` is a sitemap **index** with the usual
four siblings:

- ``sitemap_products_1.xml?from=...&to=...`` (product URLs — what we want)
- ``sitemap_pages_1.xml`` (CMS)
- ``sitemap_collections_1.xml`` (category listings)
- ``sitemap_blogs_1.xml`` (articles)

Only the ``sitemap_products_*`` children host product URLs, so the
discovery filter is the same "contains ``/products/`` and came from a
products child sitemap" rule used by ``grimmspeed`` / ``radium`` / every
other Shopify adapter.

**JSON-LD shape.** Every PDP emits a clean ``@type: Product`` block with
``name`` / ``sku`` / ``gtin`` / ``brand.name`` / ``offers.price`` /
``description`` / ``image``. The shared ``extract_json_ld_product`` +
``scraped_payload_from_json_ld`` helpers handle it directly. No
``ProductGroup`` wrapper — Shopify's default theme flattens the first
variant into the top-level ``Product``, which is the common Shopify shape
described in ``VARIANTS.md``.

**Brand handling — coerce blank / car-make → "CSF" (matching existing
canonical).** This is the load-bearing part for cross-retailer dedupe:

- ``part_manufacturer_from_description`` in ``parsing.py`` explicitly maps
  the phrase ``"CSF Radiators"`` to the canonical string ``"CSF"`` (see
  the ``(r"\\bCSF\\s+Radiators?\\b", "CSF")`` entry). The PartManufacturer
  table already carries a row for ``"CSF"``. We must emit the *same*
  canonical — **not** ``"CSF Race"``, ``"CSF Racing"``, or
  ``"CSF Radiators"`` — or ingest will create a duplicate row and split
  history across two manufacturers.
- CSF Race also carries *genuine third-party* brands: Rywire (custom
  radiators), Cicio Performance (oil coolers), A/C Solutions
  (BMW E30 A/C kits), and collabs like "CSF x Jackson Racing" show up in
  the Shopify ``vendor`` field. JSON-LD ``brand.name`` is trustworthy on
  this store for the real manufacturer, so we pass it through whenever
  it's non-empty and isn't a car make.
- Product titles lead with the target vehicle ("BMW E46 M3 / E39 M5
  Race-Spec Dual-Pass Oil Cooler", "Toyota GR Corolla Stepped-Core
  Intercooler"), so the title heuristic would trip on BMW / Toyota / etc.
  if it ever ran as a fallback. We coerce car-make brands to ``"CSF"``.
- Anything matching ``"CSF"`` / ``"CSF Race"`` / ``"CSF Racing"`` /
  ``"CSF Radiators"`` / ``"CSF x <partner>"`` collapses to the canonical
  ``"CSF"``.

Same pattern as ``grimmspeed``: pass through real third-party brands
(COBB, CSF, ACT in GrimmSpeed's case; Rywire, Cicio, A/C Solutions here),
coerce empty/car-make/house-brand-variant to the canonical form.

**Variant rule.** Radiators, oil coolers, and intercoolers on this store
are one PDP per chassis fitment — the "variant" users care about is
*which car it fits*, and CSF splits fitments across distinct products
(e.g. ``8285`` silver vs ``8285b`` black — two URLs, two SKUs, two PDPs).
Shopify variants (``variants[]``) on a single PDP tend to be trivial
axes (color) where price and SKU may differ but the fitment does not.
Per ``VARIANTS.md``, that's the "parent-only" case — take the first
variant's ``sku`` / ``price`` as flattened in the top-level JSON-LD and
don't descend. Good enough for the cooling vertical.

**SKU format.** CSF house parts are a short numeric code
(``8032``, ``7058``, ``3081``, ``8021``); collabs and resold lines keep
the partner's native SKU (``ACS-SC-30``, ``ACS-30-24V``). Both shapes go
through ``normalize_part_number`` unchanged.

**GTIN.** Every product ships a ``gtin`` in JSON-LD (e.g. ``710353080320``).
Passed through.

**Images.** JSON-LD ``image`` is a single URL. Shopify stores the full
gallery under ``//csfrace.com/cdn/shop/files/...``; we merge the DOM
gallery on top of the JSON-LD cover, size-dedup on Shopify
``?v=...&width=...`` params, and cap at 12 (matches other Shopify
adapters).

**Discovery override.** ``CRAWLER_CSFRACE_START_URLS`` (comma-separated)
skips sitemap discovery; falls back to ``DEFAULT_START_URLS`` if the
sitemap walk errors.

**Fetcher tier — plain HTTP.** ``curl`` with a normal desktop UA returns
200 and the full HTML with JSON-LD. No ``cf-mitigated``, no Just-a-moment
interstitial. ``FETCHER_TIER`` stays at the default ``"http"``.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
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

CSFRACE_BASE = "https://csfrace.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical PartManufacturer value. MUST match the existing DB row that
# ``parsing.py::part_manufacturer_from_description`` maps ``"CSF Radiators"``
# to — see the ``(r"\bCSF\s+Radiators?\b", "CSF")`` pattern. Any other
# string ("CSF Race", "CSF Racing", "CSF Radiators") would create a
# duplicate manufacturer and split cross-retailer history.
BRAND_CANONICAL = "CSF"

# Verified live URLs — a mix of house-brand (``CSF``) and collab
# (``CSF x Cicio``, ``A/C Solutions``) PDPs so the first crawl exercises
# both the pass-through and the coerce-to-canonical branches.
DEFAULT_START_URLS = [
    "https://csfrace.com/products/8032-bmw-e46-m3-e39-m5-race-spec-dual-pass-oil-cooler",
    "https://csfrace.com/products/8285-toyota-gr-corolla-stepped-core-intercooler-silver",
]

# Car makes the title heuristic sometimes surfaces as "brand" because CSF
# Race titles lead with the target vehicle ("BMW E46 M3 ...",
# "Toyota GR Corolla ..."). Any of these → coerce to BRAND_CANONICAL.
_CAR_MAKES = frozenset(
    {
        "acura",
        "audi",
        "bmw",
        "chevrolet",
        "chevy",
        "chrysler",
        "dodge",
        "ford",
        "honda",
        "hyundai",
        "infiniti",
        "jeep",
        "kia",
        "lexus",
        "mazda",
        "mercedes",
        "mercedes-benz",
        "mini",
        "mitsubishi",
        "nissan",
        "plymouth",
        "pontiac",
        "porsche",
        "ram",
        "saab",
        "scion",
        "subaru",
        "toyota",
        "volkswagen",
        "vw",
        "yamaha",  # CSF sells motorcycle radiators too (e.g. Yamaha R1)
    }
)

# Generic words occasionally picked by the first-token title heuristic.
_BRAND_REJECT_TOKENS = frozenset({"the", "new", "oem", "race", "racing"})

# CSF canonical variants. Any of these → collapse to BRAND_CANONICAL.
# Order: longest/most specific first so prefix matches don't swallow short
# forms.
_CSF_CANONICAL_PREFIXES = (
    "csf radiators",
    "csf radiator",
    "csf racing",
    "csf race",
    "csf x ",  # "CSF x Jackson Racing", "CSF x Cicio Performance" etc.
    "csf ",
)

# Shopify CDN thumbnail size suffix (e.g. ``file_300x300.jpg``). Rejected so
# we keep full-resolution gallery media over theme thumbnails.
_SHOPIFY_THUMBNAIL_RE = re.compile(r"_\d{2,4}x\d{2,4}\.\w{2,5}(?:$|\?)", re.IGNORECASE)

# Image URL patterns that are site chrome rather than product gallery media.
_IMAGE_NOISE_RE = re.compile(
    r"mega_?menu|/banner_|_banner|/logo|logo_|header_|footer_|placeholder|favicon|sprite|icon[-_]",
    re.IGNORECASE,
)


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk sitemap.xml; fall back to DEFAULT_START_URLS."""
    raw = os.environ.get("CRAWLER_CSFRACE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_products_child_sitemap(url: str) -> bool:
    """True if ``url`` is a Shopify ``sitemap_products_N.xml`` child sitemap."""
    return "/sitemap_products_" in url


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → each ``sitemap_products_N.xml``
    child urlset and collect every ``/products/<handle>`` URL. Skips
    ``sitemap_pages_*`` / ``sitemap_collections_*`` / ``sitemap_blogs_*``
    siblings — none host product pages. Returns a deduplicated list
    (query stripped); empty on failure.

    Shopify's products sitemap lists the root URL first
    (``https://csfrace.com/``) — that one gets filtered out by the
    ``/products/`` substring check along with the non-product children.
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
        index_url = CSFRACE_BASE + "/sitemap.xml"
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


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> str:
    """
    Return the canonical manufacturer for a CSF Race product page.

    - Empty, whitespace, car-make, or reject-token → coerce to
      ``BRAND_CANONICAL`` (``"CSF"``).
    - Any CSF-house variant (``"CSF"``, ``"CSF Race"``, ``"CSF Racing"``,
      ``"CSF Radiators"``, ``"CSF x <partner>"``) → collapse to
      ``BRAND_CANONICAL``. This is the dedupe-critical branch: the DB
      already has a ``"CSF"`` manufacturer row and ``parsing.py``
      rewrites ``"CSF Radiators"`` to ``"CSF"`` in the description
      heuristic. Everything has to agree.
    - Real third-party brands (Rywire, Cicio Performance, A/C Solutions,
      Jackson Racing, etc.) pass through unchanged.

    ``product_name`` is unused today but kept in the signature for
    symmetry with ``grimmspeed._normalize_part_manufacturer`` and in
    case a future title-level override is needed.
    """
    _ = product_name
    brand = (part_manufacturer or "").strip()
    if not brand:
        return BRAND_CANONICAL
    low = brand.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return BRAND_CANONICAL
    # Collapse any CSF-house variant to canonical. Done with a startswith
    # check so "CSF x Jackson Racing" / "CSF Radiators Inc." / etc. all
    # fold in. Plain "CSF" matches the first prefix ("csf ") only via the
    # literal check below — startswith("csf ") wouldn't match bare "csf".
    if low == "csf":
        return BRAND_CANONICAL
    for prefix in _CSF_CANONICAL_PREFIXES:
        if low.startswith(prefix):
            return BRAND_CANONICAL
    return brand


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against csfrace.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return CSFRACE_BASE + u
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
    """Drop Shopify ``v`` / ``width`` / ``height`` / ``crop`` params so size variants of the same asset collapse."""
    stripped = re.sub(r"[?&](v|width|height|crop)=[^&]+", "", url)
    stripped = stripped.replace("?&", "?").rstrip("?&")
    return stripped


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs from the DOM (Shopify CDN only),
    deduped and capped at 12. CSF Race's theme uses a ``media-gallery``
    custom element (``media-gallery.js`` is loaded per-PDP). Fall back
    through the common legacy selectors for safety.
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
                    # data-srcset is a comma-separated list; take the first URL.
                    first = val.strip().split(",")[0].strip().split(" ")[0]
                    if first:
                        add(first)
                        break

    return ordered[:12]


class CSFRaceAdapter(RetailerCrawlerAdapter):
    """
    CSF Race adapter. Shopify storefront, plain HTTP fetcher tier.

    - **Discovery:** sitemap index at ``/sitemap.xml`` →
      ``sitemap_products_1.xml?from=&to=`` child urlset. Query string is
      preserved on the fetch (Shopify requires it).
    - **Parsing:** JSON-LD ``@type: Product`` is authoritative on every
      PDP (name, sku, gtin, brand, price, description, cover image).
      DOM gallery is merged on top of the single-URL JSON-LD image.
    - **Brand:** pass through when JSON-LD gives a real manufacturer
      (Rywire, Cicio Performance, A/C Solutions, …); coerce empty,
      car-make, or ``CSF`` / ``CSF Race`` / ``CSF Racing`` /
      ``CSF Radiators`` / ``CSF x <partner>`` to the canonical
      ``"CSF"`` so ingest reuses the existing PartManufacturer row.
    - **Variant rule:** radiator/cooler catalog has 1 PDP per chassis
      fitment (color splits get their own URLs, e.g. ``-silver`` vs
      ``-black``). Shopify ``variants[]`` stays flattened in the
      top-level JSON-LD — take variant[0]; don't descend. See
      ``VARIANTS.md``.
    """

    ADAPTER_NAME: ClassVar[str] = "csfrace"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from ``/sitemap.xml`` (sitemap index →
        ``sitemap_products_N.xml`` children). Set
        ``CRAWLER_CSFRACE_START_URLS`` (comma-separated) to override
        with a fixed list.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a CSF Race product page into a ``ScrapedPayload``.

        1. JSON-LD ``Product`` (every real PDP emits a clean block with
           name / sku / gtin / brand / offers / description / image).
           Merge DOM gallery on top of the single-URL cover image.
        2. DOM / og fallback — only reached for pages where JSON-LD is
           missing or doesn't parse.

        Returns ``None`` when no usable name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (authoritative).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)

                # JSON-LD image is typically a single-URL cover; merge the
                # DOM gallery on top so we get the full carousel.
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

        # 2. DOM / og fallback — only reached when JSON-LD is absent/unparseable.
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
