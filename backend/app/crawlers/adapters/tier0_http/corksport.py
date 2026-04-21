"""
CorkSport Mazda Performance (corksport.com) crawler adapter — Tier 0 (plain HTTP).

CorkSport is a Mazda specialist (Mazdaspeed 3/6, 2014+ Mazda 3, CX-5, RX-8,
Protege) that sells its own house-brand hardware *and* resells a long list of
third-party Mazda-oriented manufacturers. Platform: **CS-Cart** — the classic
telltales are the sitemap shape (``/products_1.xml`` + ``/categories_1.xml`` +
``/pages_1.xml`` children under a ``sitemapindex``), the product URLs (flat at
the site root, ``.html`` suffix, no ``/products/`` prefix), the ``ty-*``
classed DOM (``.ty-price``, ``.ty-product-img``, ``.ty-product-detail``), and
the ``data-cpga-*`` product-tracking attributes used by CS-Cart's Google
Analytics addon. Cloudflare is *not* fronting the origin — plain ``requests``
with the crawler UA returns HTTP 200 on robots.txt, sitemap, and product pages.

Every product page emits a ``<script type="application/ld+json">`` block with
``@type: "Product"`` carrying ``name``, ``sku``, ``description``, ``image``,
and an ``offers`` object keyed ``@type: "AggregateOffer"`` (price /
lowPrice / highPrice / offerCount). The shared JSON-LD helpers
(``scraped_payload_from_json_ld``, ``_price_from_json_ld``) handle all of that
including AggregateOffer pricing. Three CorkSport-specific quirks drive the
adapter-local logic:

- **Brand is never populated in JSON-LD.** CorkSport's CS-Cart theme does not
  emit ``brand`` on the Product schema — not for own-brand items
  (``"CorkSport Power Series ... Intake"``) and *not* for third-party resale
  (``"Tial Mazdaspeed ... Wastegate"``, ``"Mazdaspeed NGK 1-Step Colder Spark
  Plugs"``, ``"COBB AccessPort"``). The ``data-cpga-brand`` tracking attribute
  is always empty too. There is genuinely no machine-readable brand on the
  page. We therefore lean on the title heuristic (``part_manufacturer_from_title``)
  and then coerce to the canonical house-brand name **only** when the title
  leads with one of CorkSport's house-brand markers (``"CorkSport"``) — this
  is the multi-brand-reseller pattern from ``ind.py`` and ``maperformance.py``,
  not the single-brand-coerce pattern from ``adro.py``. Third-party
  manufacturers (Cobb, Tial, NGK, AEM, Garrett, Whiteline, Turbosmart, K&N,
  Mishimoto, BC Racing, Eibach, Koni, …) propagate through unchanged.
- **The title heuristic often picks a car make** (titles regularly start with
  ``"Mazdaspeed"`` / ``"Mazda"``) or a chassis token (``"MZR"``, ``"DISI"``).
  Those are not part manufacturers. We drop them so the honest answer is
  "unknown" and ingest falls back to ``"Unknown"`` rather than creating a
  ``"Mazdaspeed"`` manufacturer row alongside real brands.
- **SKUs are retailer-internal, never the manufacturer MPN.** CorkSport emits
  SKU values like ``"Axl-6-276-63130"`` (own-brand intake), ``"GEN-6-715"``
  (Tial wastegate), ``"GEN-6-147-11"`` (NGK spark plugs). There is no ``mpn``
  field. We keep the SKU because it is a stable per-retailer identifier and
  supports intra-retailer dedupe, but it will not cross-match with any other
  retailer's listing of the same physical part.

Canonical house-brand form: ``"CorkSport"``. The storefront signs offers as
``"CorkSport Performance"`` (full legal name) but the brand as commonly
written on product pages, marketing, and packaging is ``"CorkSport"`` — one
word, PascalCase. We use ``"CorkSport"`` so the part-manufacturer list stays
consistent with how the brand is referenced elsewhere.

Notable third-party brands CorkSport resells (not exhaustive): COBB Tuning,
Tial, NGK, AEM, Garrett, K&N, Mishimoto, BC Racing, Eibach, Koni, Whiteline,
Turbosmart, ACT, Perrin, DBA, Hawk, StopTech, Öhlins.

Discovery: ``/sitemap.xml`` (sitemapindex) → ``/products_1.xml`` urlset. The
children sitemap index exposes ``categories_1.xml``, ``pages_1.xml``,
``custom_links_1.xml``, ``product_images_1.xml`` — we only want products.
The products urlset includes base URLs *and* ``?variation_id=<id>`` variant
URLs that point at the same product page; we dedupe on the path so the same
product isn't crawled once per variant. Override with
``CRAWLER_CORKSPORT_START_URLS`` (comma-separated) for ad-hoc runs.

Image gallery: JSON-LD only ships the hero image. The CS-Cart gallery DOM
uses ``<a class="cm-image-previewer" href="...">`` anchors inside
``.ty-product-img`` pointing at the full-size ``/images/detailed/<id>/<file>``
WebP. We walk those first, then fall back to the JSON-LD hero.
"""

import os
import re
import time
from typing import Iterator, List, Optional
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
    normalize_description_text,
    normalize_part_number,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

CORKSPORT_BASE = "https://corksport.com"
SITEMAP_INDEX_URL = CORKSPORT_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Default: one own-brand product (CorkSport Power Series intake) and one
# third-party resale (Tial MV-R wastegate). Keeps smoke tests honest about the
# multi-brand pass-through path.
DEFAULT_START_URLS = [
    "https://corksport.com/corksport-power-series-2007-2013-mazdaspeed-3-big-maf-3-intake.html",
    "https://corksport.com/tial-mazdaspeed-3-and-mazdaspeed-6-mv-r-wastegate.html",
]

# Canonical house-brand form. Kept separate from the variant set so the name
# we commit is always spelled ``CorkSport`` even when the title leads with
# ``Corksport`` / ``CORKSPORT`` / etc.
_CORKSPORT_CANONICAL_BRAND = "CorkSport"
_CORKSPORT_BRAND_VARIANTS = frozenset(
    {
        "corksport",
        "cork sport",
        "cork-sport",
        "corksport performance",
    }
)

# Car-make / chassis / platform tokens the title heuristic regularly picks on
# a Mazda specialist. ``part_manufacturer_from_title`` returns the first non-
# generic word, and CorkSport titles lead with the target vehicle ("Mazdaspeed
# 3 Short Ram Intake", "Mazda 32mm Coolant Temperature Adapter Port") or an
# engine-platform code ("DISI MZR Fuel Rail O-Ring Kit"). None of these are
# part manufacturers; drop them rather than commit a fake row. The shared
# chassis/part-code filters in ``parsing.py`` are BMW-centric (E46, VF570,
# etc.) and don't catch these Mazda-specific tokens.
_TITLE_NON_BRAND_TOKENS = frozenset(
    {
        # Car makes the title heuristic may surface
        "mazda",
        "mazdaspeed",
        "mazdaspeeed",  # common typo, cheap to guard against
        # Engine platform codes used as title leaders on this storefront
        "disi",
        "mzr",
        "skyactiv",
        "skyactiv-g",
        "skyactiv-d",
        "rotary",
        # Generic/non-brand leaders that slip past the shared generic-word set
        "vacuum",
        "rear",
        "front",
        "replacement",
        "universal",
    }
)

# CorkSport-brand detector: the title leads with ``CorkSport`` (case-insensitive,
# optional space/hyphen). Used to *upgrade* the title-heuristic's None result to
# the canonical house-brand name when the product is clearly CorkSport-made.
_HOUSE_BRAND_TITLE_RE = re.compile(r"^\s*cork\s*-?\s*sport\b", re.IGNORECASE)

# URL-slug signal: the product URL itself leads with a ``corksport-`` slug on
# every own-brand product we've sampled (``corksport-radiator-cap.html``,
# ``corksport-power-series-...html``, ``corksport-13-big-brake-kit-...html``).
# Used to coerce to the house brand when the title happens to lead with the
# target vehicle (``"Mazdaspeed 3, 3 inch Power Series Intake"`` on a URL
# whose slug is ``corksport-power-series-...``).
_HOUSE_BRAND_URL_SLUG_RE = re.compile(r"/corksport-[a-z0-9]", re.IGNORECASE)


def _strip_leading_non_brand_tokens(title: str) -> str:
    """
    Drop leading tokens that are car makes / chassis / platform codes on a
    Mazda specialist (``"Mazdaspeed"``, ``"Mazda"``, ``"DISI"``, ``"MZR"``,
    …). Titles like ``"Mazdaspeed NGK 1-Step Colder Spark Plugs"`` or
    ``"Mazdaspeed 3 Cobb AccessPort"`` lead with the target vehicle but the
    real brand is token 2 or 3; after this trim, the shared
    ``part_manufacturer_from_title`` heuristic returns ``"NGK"`` / ``"Cobb"``
    instead of ``"Mazdaspeed"``. Short numeric / punctuation / model-code
    tokens that follow a make (``"3"``, ``"6"``, ``"/"``, ``","``, ``"CX-5"``,
    ``"RX-8"``) are stripped too so a title like ``"MAZDASPEED 3 / MAZDASPEED 6
    COBB AccessPort"`` lands on ``"COBB AccessPort"``.

    Returns the title unchanged when no leading non-brand token is present,
    so titles like ``"Cobb Tuning ..."`` are left alone.
    """
    if not title:
        return title
    tokens = title.strip().split()
    stripped = 0
    for tok in tokens:
        low = tok.lower().strip(",.:;!?/\\()[]\"'")
        if not low:
            # Pure punctuation token — drop only once we've already stripped a
            # make, so titles like ``"/-foo"`` don't eat their leading bracket.
            if stripped > 0:
                stripped += 1
                continue
            break
        if low in _TITLE_NON_BRAND_TOKENS:
            stripped += 1
            continue
        # Strip short numeric / model-code tokens only *after* we've already
        # stripped a make token — we want to keep numeric leaders on titles
        # that happen to start with a model code (rare on this storefront)
        # rather than the "Mazdaspeed 3 ..." shape.
        if stripped > 0 and (low.isdigit() or re.match(r"^cx-?\d$|^rx-?\d$", low)):
            stripped += 1
            continue
        break
    if stripped == 0:
        return title
    return " ".join(tokens[stripped:])


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> Optional[str]:
    """
    Collapse CorkSport's self-spellings (``"CorkSport"``, ``"CorkSport
    Performance"``, ``"Cork Sport"``) to the canonical ``"CorkSport"`` row.
    Drop values that are actually a car make or chassis code; return ``None``
    so the caller can fall through to a house-brand coercion check. Third-
    party vendor strings (``"Cobb"``, ``"Tial"``, ``"NGK"``, ``"AEM"``, …)
    pass through unchanged so re-sold hardware lands on the real manufacturer
    in the global part-manufacturer list.
    """
    if not part_manufacturer:
        return part_manufacturer
    brand = part_manufacturer.strip()
    if not brand:
        return None
    low = brand.lower()
    if low in _CORKSPORT_BRAND_VARIANTS:
        return _CORKSPORT_CANONICAL_BRAND
    if low in _TITLE_NON_BRAND_TOKENS:
        return None
    return brand


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise discover via sitemap, then default."""
    raw = os.environ.get("CRAWLER_CORKSPORT_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all ``<loc>`` elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _is_product_child_sitemap(url: str) -> bool:
    """True if ``url`` is the CorkSport products sitemap (``/products_<N>.xml``)."""
    try:
        path = urlparse(url).path.lower()
    except ValueError:
        return False
    # Skip categories/pages/custom_links/product_images children — only walk products.
    return bool(re.match(r"^/products_\d+\.xml$", path))


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` (sitemap index) → each ``/products_<N>.xml`` child
    urlset and collect every product URL. Dedupe on the URL path so the
    ``?variation_id=<id>`` variant entries that CS-Cart emits collapse onto
    their base product URL. Returns an empty list on failure.
    """
    seen_paths: set[str] = set()
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
            if not u:
                continue
            try:
                parsed = urlparse(u)
            except ValueError:
                continue
            path = parsed.path
            if not path.endswith(".html"):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            # Drop variant query params — the base URL is the canonical product page.
            base = u.split("?", 1)[0]
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
            # Unexpected: sitemap.xml served as a flat urlset. Parse defensively.
            parse_urlset_locs(index_text)
    except Exception:
        return []

    return product_urls


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is a CorkSport product page — on the corksport.com host,
    with a non-empty ``.html`` path that isn't a known non-product page.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "corksport.com" and not host.endswith(".corksport.com"):
        return False
    path = (parsed.path or "").strip("/")
    if not path or not path.endswith(".html"):
        return False
    # Reject CS-Cart storefront chrome that also lives at site root with .html.
    lower = path.lower()
    if lower in {
        "store_closed.html",
        "contact-us.html",
        "about-us.html",
        "shipping.html",
        "returns.html",
        "privacy.html",
        "terms.html",
    }:
        return False
    return True


def _normalize_image_url(raw: str) -> Optional[str]:
    """Expand protocol-relative URLs and resolve bare paths against CORKSPORT_BASE."""
    s = raw.strip()
    if not s:
        return None
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return CORKSPORT_BASE + s
    if s.startswith("http://"):
        return "https://" + s[len("http://") :]
    if not s.startswith("http"):
        return None
    return s


def _is_valid_product_image(url: str) -> bool:
    """Keep ``/images/detailed/`` and ``/images/thumbnails/`` product shots; reject chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/images/" not in low:
        return False
    if re.search(r"logo|favicon|placeholder|sprite|pixel\.(gif|png)|/design/themes/", low):
        return False
    return True


def _image_dedup_key(url: str) -> str:
    """
    Collapse the same photo served at different sizes. CS-Cart serves both the
    full-size ``/images/detailed/<id>/<file>`` and ``/images/thumbnails/<w>/<h>/detailed/<id>/<file>``
    — same file name, different prefix. Key on the last ``/detailed/<id>/<file>``
    segment so width variants dedupe onto the full-size hit.
    """
    base = url.split("?", 1)[0]
    # Strip query; normalize .webp / .jpg suffix swaps so the same image at two
    # formats still collapses.
    m = re.search(r"/detailed/\d+/([^/]+)$", base)
    if m:
        stem = re.sub(r"\.(webp|jpg|jpeg|png|gif)$", "", m.group(1), flags=re.IGNORECASE)
        return stem.lower()
    return base.lower()


def _extract_gallery_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery image URLs from the CS-Cart
    ``<a class="cm-image-previewer">`` anchors. Each anchor's ``href`` points
    at the full-size ``/images/detailed/...`` asset; the nested ``<img>``
    is the lower-res thumbnail. We keep full-size hrefs and dedupe on photo
    identity so width variants collapse. Capped at 12.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or not _is_valid_product_image(normalized):
            return
        key = _image_dedup_key(normalized)
        if key in seen:
            return
        seen.add(key)
        ordered.append(normalized)

    # Primary: CS-Cart image-previewer anchors (full-size hrefs).
    for anchor in soup.select("a.cm-image-previewer"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if isinstance(href, str):
            add(href)

    # Fallback: any ``.ty-product-img img[src]`` in case the previewer class
    # is themed out on a given page.
    if not ordered:
        for img in soup.select(".ty-product-img img"):
            if not isinstance(img, Tag):
                continue
            for attr in ("data-src", "src"):
                v = img.get(attr)
                if isinstance(v, str) and v.strip():
                    add(v)
                    break

    return ordered[:12]


class CorkSportAdapter(RetailerCrawlerAdapter):
    """
    CorkSport Mazda Performance adapter. CS-Cart storefront, plain HTTP is
    sufficient (no Cloudflare challenge). Discovery via ``/sitemap.xml`` →
    ``/products_<N>.xml`` children, deduped on path to collapse
    ``?variation_id=<id>`` variant entries onto their base product URL.

    Parsing uses the JSON-LD ``Product`` block as the primary source
    (CS-Cart emits name, sku, description, image, offers as ``AggregateOffer``
    on every product page). Adapter-local rules:

    - Brand is never present in JSON-LD (empty for both own-brand and resale),
      so we lean on the title heuristic and then coerce to ``"CorkSport"``
      only when the title actually leads with ``"CorkSport"``. Third-party
      manufacturers (Cobb, Tial, NGK, AEM, …) pass through unchanged.
    - Drop car-make / chassis / platform tokens (``"Mazda"``, ``"Mazdaspeed"``,
      ``"MZR"``, ``"DISI"``) that the title heuristic picks on a Mazda
      specialist — they are not part manufacturers.
    - The JSON-LD ``sku`` is a CorkSport-internal inventory code (``Axl-…``,
      ``GEN-…``) and there is no ``mpn``. We keep it for intra-retailer dedupe
      but it will not cross-match against other retailers' listings.
    - Expand past the JSON-LD hero image by walking the CS-Cart
      ``a.cm-image-previewer`` gallery.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs from the sitemap; env override wins when set."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a CorkSport product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL isn't product-shaped or the page has no JSON-LD
        Product block (category / info / checkout page).
        """
        if not _is_product_url(url):
            return None

        item = extract_json_ld_product(html, product_url=url)
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # --- Brand resolution ----------------------------------------------------
        # JSON-LD brand is essentially always absent on this storefront (verified
        # across own-brand and multiple resale pages), so lean on the title
        # heuristic. Two passes: first on the raw title, then — if the result is
        # a dropped car-make token — on the title with the leading non-brand
        # tokens stripped. That second pass converts "Mazdaspeed NGK ..." and
        # "Mazdaspeed 3 Cobb AccessPort" into the real third-party brand.
        part_manufacturer = _normalize_part_manufacturer(payload.part_manufacturer)
        if not part_manufacturer:
            part_manufacturer = _normalize_part_manufacturer(part_manufacturer_from_title(payload.name))
        if not part_manufacturer:
            # Iterate the strip so a title like "MAZDASPEED 3 / MAZDASPEED 6
            # COBB AccessPort" trims one make, then the "/" + second make,
            # before the heuristic runs on "COBB AccessPort".
            trimmed = payload.name
            for _ in range(3):
                next_trim = _strip_leading_non_brand_tokens(trimmed)
                if not next_trim or next_trim == trimmed:
                    break
                trimmed = next_trim
            if trimmed and trimmed != payload.name:
                part_manufacturer = _normalize_part_manufacturer(part_manufacturer_from_title(trimmed))
        # House-brand coercion: title leads with "CorkSport" OR the product URL
        # slug starts with "corksport-" (covers the case where the title leads
        # with the target vehicle — e.g. "Mazdaspeed 3, 3 inch Power Series
        # Intake" at /corksport-power-series-...). We do not apply a blanket
        # "default to CorkSport when missing" because that would falsely label
        # Cobb AccessPorts and Tial wastegates as CorkSport-made.
        if _HOUSE_BRAND_TITLE_RE.match(payload.name or "") or _HOUSE_BRAND_URL_SLUG_RE.search(url or ""):
            part_manufacturer = _CORKSPORT_CANONICAL_BRAND

        # --- Part number ---------------------------------------------------------
        # JSON-LD SKU is the CorkSport internal code. No mpn field. Keep it for
        # intra-retailer dedupe; ingest's junk-filter handles the degenerate case
        # where the SKU equals the manufacturer name.
        part_number = normalize_part_number(payload.part_number) if payload.part_number else None

        # --- Description --------------------------------------------------------
        # JSON-LD description is already the primary editorial copy on this
        # storefront; just run the standard length/normalization helper.
        description = normalize_description_text(payload.description, max_len=2000) if payload.description else None

        # --- Price --------------------------------------------------------------
        # JSON-LD AggregateOffer.price → _price_from_json_ld handles that path.
        # DOM fallback covers the rare page without JSON-LD offers populated.
        price_cents = payload.price_cents
        if price_cents is None:
            price_cents = extract_dom_price(soup)

        # --- Images -------------------------------------------------------------
        dom_images = _extract_gallery_images(soup)
        image_urls = dom_images if dom_images else payload.image_urls

        return ScrapedPayload(
            name=payload.name,
            product_url=payload.product_url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
            gtin=payload.gtin,
        )
