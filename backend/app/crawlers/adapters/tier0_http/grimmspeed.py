"""
GrimmSpeed (grimmspeed.com) crawler adapter.

Platform: **Shopify** (served behind Cloudflare, but no JS challenge — plain
``requests`` pulls a fully rendered HTML page; apex ``grimmspeed.com`` 301s to
``www.grimmspeed.com``, which is what the sitemap advertises). No TLS or
browser tier required, so ``FETCHER_TIER`` stays at the default ``"http"``.

Product URLs: ``https://www.grimmspeed.com/products/<handle>``

Discovery: ``/sitemap.xml`` is a standard Shopify sitemap **index** pointing
at ``sitemap_products_1.xml?from=…&to=…`` plus the usual pages / collections
/ blogs siblings — only the ``sitemap_products_*`` children host real
product URLs, the rest are skipped. Override with
``CRAWLER_GRIMMSPEED_START_URLS`` (comma-separated) for a fixed list.

Brand handling: GrimmSpeed is **predominantly a house brand** — most of the
catalog is their own intakes, up-pipes, chassis bracing, EBCS electronics,
etc. JSON-LD emits ``brand.name = "GrimmSpeed"`` for those. **But** they
resell a meaningful number of third-party Subaru parts too: COBB (Accessport
V3), CSF (radiators, cooling bundles), ACT (clutches/flywheels), and the
occasional IAG / Killer B SKU. On those pages the JSON-LD brand is correctly
populated with the real manufacturer (``"Cobb Tuning"``, ``"CSF"``, …), so
**we pass JSON-LD brand through unchanged whenever it's non-empty**.

We only coerce to the canonical ``"GrimmSpeed"`` form when:

1. JSON-LD brand is missing/empty entirely; or
2. The title-heuristic fallback returned a car make (Subaru / Toyota /
   Mitsubishi / Scion / Ford / Honda / Mazda — GrimmSpeed covers all of
   these over the catalog's history) or a generic product word.
3. The JSON-LD brand is itself one of those car makes (belt-and-suspenders
   guard — haven't observed it on GrimmSpeed but the cost is free).

SKU format: Own-brand parts use a ``GRM`` prefix plus 6 digits
(``GRM034001``, ``GRM056001``, ``GRM091019``). Resold parts keep the
manufacturer's native SKU (e.g. COBB's ``COBAP3-SUB-004``). Both shapes go
through ``normalize_part_number`` unchanged — nothing to strip.

Images: JSON-LD ``image`` is a single URL wrapped in a one-element array
pointing at the storefront-proxy CDN
(``www.grimmspeed.com/cdn/shop/products/…``) rather than bare
``cdn.shopify.com``. Gallery media sits inside a legacy Shopify theme
wrapper rather than a ``<media-gallery>`` custom element on this store, so
the DOM sweep looks at ``.product-images`` / ``.product__media-wrapper`` /
``.product-single__media`` to cover both layouts and dedupes against the
JSON-LD cover image. Thumbnail / size-suffix variants
(``_300x300.jpg`` etc.) are rejected to keep full-resolution media.

Tier rationale: Plain Shopify served through Cloudflare with no JS
challenge — ``curl`` returns complete HTML with JSON-LD on first try. No
reason to pay the Tier 1 / Tier 2 cost.
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

GRIMMSPEED_BASE = "https://www.grimmspeed.com"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Verified live product URLs used as a fallback when sitemap discovery fails
# and no env override is provided. Picked across the catalog so the first
# crawl exercises the JSON-LD path end to end.
DEFAULT_START_URLS = [
    "https://www.grimmspeed.com/products/grimmspeed-3-bolt-manifold-up-pipe-gasket-wrx-sti-lgt-fxt",
    "https://www.grimmspeed.com/products/grimmspeed-aos-rebuild-kit",
]

# Tokens that the title heuristic / an empty JSON-LD brand sometimes surface
# as "brand" but are really the target vehicle make. GrimmSpeed covers Subaru
# primarily, with smaller lines for the other makes below. Any of these →
# coerce to "GrimmSpeed" so the catalog doesn't grow a phantom "Subaru"
# part manufacturer from our scrape.
_CAR_MAKES = frozenset(
    {
        "subaru",
        "toyota",
        "scion",
        "mitsubishi",
        "ford",
        "mazda",
        "honda",
        "nissan",
        "chevrolet",
        "chevy",
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
    raw = os.environ.get("CRAWLER_GRIMMSPEED_START_URLS", "").strip()
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
    Walk ``/sitemap.xml`` (sitemap index) → each ``sitemap_products_N.xml``
    child urlset and collect every ``/products/<handle>`` URL. Skips
    ``sitemap_pages_*`` / ``sitemap_collections_*`` / ``sitemap_blogs_*``
    siblings — none host product pages. Returns a deduplicated list
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
            base = u.split("?")[0]
            if base in seen:
                continue
            seen.add(base)
            product_urls.append(base)

    try:
        index_url = GRIMMSPEED_BASE + "/sitemap.xml"
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
    Return the canonical manufacturer for a GrimmSpeed product page.

    - Non-empty JSON-LD / title / description brand that is NOT a car make,
      NOT a reject token, and NOT a GrimmSpeed name variant → pass through
      (this is how "Cobb Tuning", "CSF", "ACT", etc. keep their identity
      when GrimmSpeed resells them).
    - Empty, car-make, reject-token, or a "GrimmSpeed …" variant → coerce to
      canonical ``"GrimmSpeed"``. This catches both the JSON-LD-missing path
      (the fallback heuristic sees "GrimmSpeed 3-Bolt Manifold…" and picks
      "GrimmSpeed" already — the guard is belt-and-suspenders for titles
      that lead with the target vehicle like "WRX STI Short Shifter").

    product_name is unused today but kept in the signature so callers don't
    change when we need title-level overrides later.
    """
    _ = product_name
    brand = (part_manufacturer or "").strip()
    if not brand:
        return "GrimmSpeed"
    low = brand.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return "GrimmSpeed"
    # Collapse "GrimmSpeed Inc", "GrimmSpeed Performance", "Grimmspeed", etc.
    # into the canonical form regardless of case / trailing qualifier.
    if low == "grimmspeed" or low.startswith("grimmspeed ") or low.startswith("grimmspeed-"):
        return "GrimmSpeed"
    return brand


def _normalize_image_url(url: str) -> str:
    """Upgrade scheme-relative / http URLs to https; resolve absolute paths against grimmspeed.com."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return GRIMMSPEED_BASE + u
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
    deduped and capped at 12.

    GrimmSpeed's theme predates ``<media-gallery>``; gallery media is under
    ``.product-images`` / ``.product-single__media`` wrappers depending on
    template version. We try the modern ``<media-gallery>`` first (future-
    proof) and fall back through the legacy selectors before scanning the
    raw ``<img>`` tags.
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


class GrimmSpeedAdapter(RetailerCrawlerAdapter):
    """
    GrimmSpeed adapter. Discovery: Shopify sitemap index → ``sitemap_products_N.xml``
    children. Parsing: JSON-LD ``Product`` (wrapped in ``@graph`` alongside
    BreadcrumbList — the shared extractor unwraps ``@graph``) first, with
    DOM / og fallbacks for the rare page that ships no JSON-LD. Brand is
    passed through when JSON-LD gives us a real manufacturer (including
    third-party resells like COBB, CSF, ACT) and forced to ``"GrimmSpeed"``
    when missing or when the title heuristic lands on a car make.
    """

    # Default Tier 0 — plain HTTP is enough (Cloudflare on this origin does
    # not challenge ``requests``). Left explicit so the choice is documented
    # on the class itself rather than only in the module docstring.
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered from ``sitemap.xml`` (minus non-product
        children). Set ``CRAWLER_GRIMMSPEED_START_URLS`` (comma-separated) to
        override with a fixed list. A jittered delay is applied between
        sitemap-child fetches inside ``_discover_product_urls_via_sitemap``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a GrimmSpeed product page.

        1. JSON-LD ``Product`` (authoritative on Shopify) — name, description,
           brand, sku, price, cover image. Merge DOM gallery images on top of
           the single-URL JSON-LD cover so we keep the full carousel.
        2. DOM / og fallback — h1/og:title, meta description, DOM price,
           SKU via text scan, brand via shared title/description heuristics.

        Returns ``None`` when no usable name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (GrimmSpeed wraps it in @graph — the shared
        #    extractor handles that).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None
                part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer, payload.name)

                # JSON-LD image is typically a single-element array; merge DOM
                # gallery so we get the full product carousel.
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
