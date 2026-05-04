"""
Brian Tooley Racing (briantooleyracing.com) crawler adapter.

BTR is the reference-price retailer for LS / LT / Gen-III HEMI valvetrain
(cams, springs, rockers, pushrods). The RETAILER_BACKLOG entry guessed
BigCommerce; the live site is actually **Magento** — robots.txt lists the
``/catalog/product/view/`` and ``/catalogsearch/`` paths, and the product
pages emit the standard ``page-title-wrapper`` / ``product attribute
description`` / ``mage/gallery/gallery`` markup.

Fetcher tier: ``http`` — plain ``requests`` returns HTTP 200 on
``/robots.txt``, ``/sitemap.xml``, and product pages without any Cloudflare
interstitial.

Discovery: ``/sitemap.xml`` is a **flat urlset** (no index). It mixes
homepages, categories, CMS pages, and products in a single document and
distinguishes them via the ``<priority>`` tag:

- ``1.0`` — products (and the site root). ~5.8k URLs.
- ``0.5`` — categories and brand landing pages. ~400 URLs.
- ``0.2`` — CMS / policy pages. ~30 URLs.

A handful of ``<priority>1.0</priority>`` entries point at the legacy Magento
``/catalog/product/view/id/<N>`` URL shape, which ``robots.txt`` disallows.
We filter discovery to ``<priority>1.0</priority>`` entries whose path ends
in ``.html`` and is not the site root — that set is all products and nothing
else. Override with ``CRAWLER_BRIANTOOLEYRACING_START_URLS`` (comma-separated)
for ad-hoc runs.

Parsing: JSON-LD ``Product`` is authoritative (name, brand.name, sku, mpn,
offers.price, image). ``brand.name`` is populated per-SKU — ``"Brian Tooley
Racing"`` on house SKUs, ``"Procharger"`` / ``"Mopar"`` / ``"ARP"`` etc. on
the resold brands — so no static default manufacturer is needed.

Two augmentations on top of the shared JSON-LD helper:

- **Multi-image gallery.** The JSON-LD ``image`` field is a single URL; the
  real gallery lives in the Magento ``x-magento-init`` block keyed on
  ``"mage/gallery/gallery"`` with a ``"data":[{thumb,img,full,position,
  isMain,type}, ...]`` array. Same shape as the Hyva theme gallery that the
  Texas Speed adapter handles; we parse it locally and order by ``position``.
- **Description.** JSON-LD ``description`` is almost always empty on BTR;
  the product copy lives under ``<div class="product attribute description">
  <div class="value">...</div></div>``.

Title cleanup: BTR listing titles routinely carry a trailing ``" - <MPN>"``
token (``"03-08 5.7 HEMI CAM BOLT - MOPAR 06504429"``,
``"BTR LS6 BEEHIVE SPRING - .560 LIFT - 16 PC KIT - SP011-16"``). We strip
the suffix only when it exactly matches the JSON-LD MPN, so cross-retailer
display reads cleanly without guessing at a split.
"""

import json
import logging
import os
import re
from typing import ClassVar, Iterator, List, Optional, Tuple
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_json_ld_product,
    normalize_description_text,
    normalize_part_number,
    scraped_payload_from_json_ld,
)

BTR_BASE = "https://briantooleyracing.com"
SITEMAP_URL = f"{BTR_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://briantooleyracing.com/btr-560-beehive-valve-spring-set-sp011-16.html",
]

# Trailing ``" - <token>"`` (or ``" – "`` / ``" — "`` / ``": "`` /
# ``", "``) suffix on a BTR title. We only strip when ``<token>`` exactly
# matches the JSON-LD MPN, so titles like ``"Gen V LT - Camshaft"`` stay
# intact (the trailing ``"Camshaft"`` is not an MPN).
_TRAILING_MPN_RE = re.compile(
    r"[\s,;:\-\u2013\u2014]+([A-Za-z0-9][A-Za-z0-9._/\-]*)\s*$",
)


# BP Automotive house catalog ships 3-char alphanumeric SKUs ("A12", "E01",
# "A99") that contain a digit (so they pass ``is_junk_part_number``) but
# strip to <4 chars and fail the canonical 4-char floor. Scoped to the
# specific brand string so resold lines (ARP, Texas Speed, Comp Cams, \u2026)
# keep their vendor-issued identifiers. Modeled on
# ``tier0_http/roadsportsupply.py:_compose_rss_part_number``.
_BP_AUTOMOTIVE_BRAND_TOKENS = frozenset({"bp automotive"})
_BP_AUTOMOTIVE_PN_PREFIX = "BPA"
_BP_AUTOMOTIVE_SHORT_SKU_RE = re.compile(r"^[A-Za-z]\d{1,3}$")


def _brand_prefix_bp_automotive(
    part_number: Optional[str], part_manufacturer: Optional[str]
) -> Optional[str]:
    """
    Promote BP Automotive's bare 3-char letter+digit SKUs ("A12") to the
    prefixed form ("BPA-A12") so they survive the downstream canonical
    4-char floor without losing the original code. Returns the input
    unchanged for any other shape or non-BP-Automotive brand.
    """
    if not part_number or not part_manufacturer:
        return part_number
    sku = part_number.strip()
    if not sku or not _BP_AUTOMOTIVE_SHORT_SKU_RE.match(sku):
        return part_number
    brand_key = part_manufacturer.strip().lower()
    if brand_key not in _BP_AUTOMOTIVE_BRAND_TOKENS:
        return part_number
    return f"{_BP_AUTOMOTIVE_PN_PREFIX}-{sku}"


def _is_product_url(url: str) -> bool:
    """True if ``url`` looks like a BTR product page (``/<slug>.html`` at root)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "briantooleyracing.com" or host.endswith(".briantooleyracing.com")):
        return False
    path = parsed.path or ""
    if not path.endswith(".html"):
        return False
    # Root-slug only — reject nested category URLs like
    # ``/camshafts-lifters-pushrods/camshafts/ls3-naturally-aspirated-cams.html``.
    trimmed = path.strip("/")
    if "/" in trimmed:
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_BRIANTOOLEYRACING_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_BRIANTOOLEYRACING_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap() -> List[str]:
    """
    Walk the flat ``/sitemap.xml`` urlset and return every ``<priority>1.0</priority>``
    entry whose path ends in ``.html`` at the site root — i.e. products, not
    categories (0.5), CMS pages (0.2), or the ``<priority>1.0</priority>`` site
    root. Empty list on failure.
    """
    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=30)
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []

    url_tag = f"{{{SITEMAP_NS}}}url"
    loc_tag = f"{{{SITEMAP_NS}}}loc"
    priority_tag = f"{{{SITEMAP_NS}}}priority"
    for url_el in root.findall(url_tag):
        priority_el = url_el.find(priority_tag)
        if priority_el is None or not priority_el.text:
            continue
        try:
            priority = float(priority_el.text.strip())
        except ValueError:
            continue
        # 1.0 is the products bucket on BTR (homepage also 1.0 but fails
        # _is_product_url because its path is "/").
        if priority < 0.99:
            continue
        loc_el = url_el.find(loc_tag)
        if loc_el is None or not loc_el.text:
            continue
        url = loc_el.text.strip().split("?", 1)[0]
        if not _is_product_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        product_urls.append(url)

    return product_urls


# ``<script type="text/x-magento-init">{...}</script>`` on BTR products holds
# the gallery config under ``"mage/gallery/gallery"."data"``. Structure:
#   {"[data-gallery-role=gallery-placeholder]":{"mage/gallery/gallery":{
#     "data":[{"thumb":...,"img":...,"full":...,"position":"1","isMain":true,
#              "type":"image","videoUrl":null}, ...]
#   }}}
# We find the ``"mage/gallery/gallery"`` marker, then walk bracket depth to the
# closing ``]`` of its ``"data"`` array. Same approach as the Texas Speed Hyva
# gallery parser, but keyed on a different marker.
_GALLERY_MARKER = '"mage/gallery/gallery"'
_GALLERY_DATA_RE = re.compile(r'"data"\s*:\s*\[')


def _extract_gallery_full_urls(html: str) -> List[str]:
    """
    Extract ``full`` URLs from the Magento ``mage/gallery/gallery`` data array,
    ordered by ``position`` and deduplicated by the un-querystringed URL.

    Returns [] when the gallery JSON is absent or malformed — callers should
    then fall back to the single JSON-LD ``image``.
    """
    marker_idx = html.find(_GALLERY_MARKER)
    if marker_idx < 0:
        return []
    data_match = _GALLERY_DATA_RE.search(html, marker_idx)
    if not data_match:
        return []
    start = data_match.end() - 1  # position of the opening '['
    depth = 0
    end = start
    in_str = False
    esc = False
    for k in range(start, min(start + 500_000, len(html))):
        c = html[k]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    else:
        return []

    try:
        data = json.loads(html[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    entries: list[tuple[int, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("type") and item.get("type") != "image":
            continue
        full = item.get("full") or item.get("img")
        if not isinstance(full, str) or not full.strip():
            continue
        try:
            position = int(item.get("position") or 0)
        except (TypeError, ValueError):
            position = 0
        entries.append((position, full.strip()))

    entries.sort(key=lambda e: e[0])
    seen: set[str] = set()
    out: List[str] = []
    for _, u in entries:
        base = u.split("?", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        out.append(u)
    return out[:12]


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Read the Magento ``<div class="product attribute description">
    <div class="value">...</div></div>`` block. JSON-LD ``description`` is
    almost always empty on BTR so this is the primary source.
    """
    container = soup.find("div", class_=re.compile(r"\bproduct attribute description\b"))
    if not isinstance(container, Tag):
        return None
    value = container.find("div", class_=re.compile(r"\bvalue\b"))
    target = value if isinstance(value, Tag) else container
    text = target.get_text(" ", strip=True)
    if not text:
        return None
    return normalize_description_text(text, max_len=2000)


def _strip_trailing_mpn(name: str, mpn: Optional[str]) -> str:
    """
    Drop a trailing ``" - <mpn>"`` (or comma/en-dash/em-dash separator) from
    the title when the token is exactly the JSON-LD MPN. Keeps the suffix
    intact when the trailing token isn't the real MPN — we don't guess at
    which of several dashes separates the product name from the SKU.
    """
    if not mpn:
        return name
    match = _TRAILING_MPN_RE.search(name)
    if not match:
        return name
    candidate = match.group(1).strip()
    if candidate.lower() != mpn.strip().lower():
        return name
    trimmed = name[: match.start()].rstrip(" ,;:-\u2013\u2014")
    return trimmed or name


# ---------------------------------------------------------------------------
# Engine-family fitment extraction (Tier-2)
# ---------------------------------------------------------------------------
#
# BTR product pages render a Magento additional-attributes spec table:
#
#     <table class="data table additional-attributes">
#       <tr><th class="col label">Engine Type</th><td class="col data">Gen V LT</td></tr>
#       ...
#     </table>
#
# The ``Engine Type`` row carries the engine-family classification BTR uses
# across its catalog. Two values cover ~all BTR fitment that maps cleanly to
# CarMods's ``car_generations`` rows:
#
#   * ``Gen III/Gen IV LS`` (and the rarer ``Gen III/IV LS``) — LS-platform
#     valvetrain. Fits the F-body Camaro 4th Gen, Camaro 5th Gen, C5/C6
#     Corvette, CTS-V Gen 1/2, GTO 2004-2006 (DB row "Holden"), and Pontiac
#     Firebird (Trans Am trim ships under the Firebird car_model row).
#   * ``Gen V LT`` — LT-platform valvetrain. Fits Camaro 6th Gen, C7 + C8
#     Corvette, CTS-V Gen 3.
#
# Other ``Engine Type`` values seen in production (``LSA``, ``LS3``, etc.) are
# narrower than a single car_generation and would over-attribute on a naive
# fan-out — we leave those to the universal phrase-triple pipeline. Be
# conservative; never silently universal-flag.
#
# The override stashes the engine family on the payload via setattr so it
# survives ``apply_universal_extraction`` without flowing through
# specifications (which would fail Pydantic ``extra='forbid'`` validation
# under the universal CategorySpec).

_ENGINE_TYPE_LABEL_RE = re.compile(r"^\s*engine\s*type\s*$", re.IGNORECASE)
# Tolerate both ``Gen III/Gen IV LS`` and ``Gen III/IV LS`` spellings; case-insensitive.
_GEN_III_IV_LS_RE = re.compile(
    r"\bgen\s*iii(?:\s*/\s*(?:gen\s*)?iv)?\s*ls\b",
    re.IGNORECASE,
)
_GEN_V_LT_RE = re.compile(r"\bgen\s*v\s*lt\b", re.IGNORECASE)

_ENGINE_GEN_III_IV_LS = "GEN_III_IV_LS"
_ENGINE_GEN_V_LT = "GEN_V_LT"

# Engine-family → list of (Make, Model, Generation) triples. Names MUST match
# car_generations / car_models / car_makes rows verbatim — verified against
# the live local DB before commit.
_ENGINE_FAMILY_TRIPLES: dict[str, list[Tuple[str, str, str]]] = {
    _ENGINE_GEN_III_IV_LS: [
        ("Chevrolet", "Camaro", "4th Gen"),
        ("Chevrolet", "Camaro", "5th Gen"),
        ("Chevrolet", "Corvette", "C5"),
        ("Chevrolet", "Corvette", "C6"),
        ("Cadillac", "CTS-V", "1st Gen"),
        ("Cadillac", "CTS-V", "2nd Gen"),
        # GTO 2004-2006 lives in the DB as ``Pontiac | GTO | Holden`` (the
        # Holden Monaro-derived chassis); no separate "2004-2006" row exists.
        ("Pontiac", "GTO", "Holden"),
        # Pontiac Trans Am is a Firebird trim — the 4th-gen Firebird
        # (1993-2002) is the LS-era car. Earlier gens are pre-LS.
        ("Pontiac", "Firebird", "4th Gen"),
    ],
    _ENGINE_GEN_V_LT: [
        ("Chevrolet", "Camaro", "6th Gen"),
        ("Chevrolet", "Corvette", "C7"),
        ("Chevrolet", "Corvette", "C8"),
        ("Cadillac", "CTS-V", "3rd Gen"),
        # Camaro ZL1 and Z/28 are 6th-gen trims, not separate car_models —
        # they're already covered by the Camaro 6th Gen row above.
    ],
}


def _extract_engine_type(soup: BeautifulSoup) -> Optional[str]:
    """
    Return the ``Engine Type`` cell value from the BTR additional-attributes
    table, or ``None`` when absent.
    """
    table = soup.find("table", class_=lambda c: bool(c) and "additional-attributes" in (c if isinstance(c, list) else [c]))
    if not isinstance(table, Tag):
        return None
    for tr in table.find_all("tr"):
        th = tr.find("th")
        if not isinstance(th, Tag):
            continue
        if not _ENGINE_TYPE_LABEL_RE.match(th.get_text(" ", strip=True)):
            continue
        td = tr.find("td")
        if not isinstance(td, Tag):
            continue
        value = td.get_text(" ", strip=True)
        return value or None
    return None


def _classify_engine_family(engine_type: Optional[str]) -> Optional[str]:
    """Map a free-text ``Engine Type`` cell to a normalised family key. Conservative."""
    if not engine_type:
        return None
    if _GEN_V_LT_RE.search(engine_type):
        return _ENGINE_GEN_V_LT
    if _GEN_III_IV_LS_RE.search(engine_type):
        return _ENGINE_GEN_III_IV_LS
    return None


class BrianTooleyRacingAdapter(RetailerCrawlerAdapter):
    """
    Brian Tooley Racing adapter. Magento storefront; plain HTTP fetches.

    Discovery: env override wins. Otherwise walk the flat ``/sitemap.xml`` and
    keep ``<priority>1.0</priority>`` root-slug ``.html`` entries (products).

    Parsing: JSON-LD ``Product`` for name/brand/sku/mpn/price; Magento
    ``mage/gallery/gallery`` ``"data"`` array for the image gallery; the
    ``product attribute description`` DOM block for the description.
    """

    ADAPTER_NAME: ClassVar[str] = "briantooleyracing"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def infer_category_for_part(self, parsed: ScrapedPayload) -> Optional[str]:
        """Pin category to ``engine`` unless a more-specific keyword fires.

        BTR's catalog is exclusively LS / LT engine internals (camshafts,
        valve springs, head studs, rod sets, oil pumps, timing kits) —
        the universal keyword scorer was sending a chunk of them to
        ``other`` because product titles often lead with the platform
        ("LS3 Stage 3", "Gen V LT1") and the description mentions the
        engine series rather than the part class. Tier-2 audit
        (2026-05-02): pin the default here, and let the universal
        scorer override only when a more-specific category clearly
        applies (e.g. an LS swap clutch fork → drivetrain).
        """
        from app.core.category_inference import infer_category

        inferred = infer_category(parsed.name, parsed.description)
        # Only defer to the universal scorer when it picked a non-default,
        # non-engine slug — anything else (other / engine) falls through
        # to our pinned default.
        if inferred and inferred not in ("other", "engine"):
            return inferred
        return "engine"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; sitemap next; fixed fallback last."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in _discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a BTR product page. JSON-LD Product is authoritative; returns
        None when the URL is not product-shaped, when JSON-LD is missing, or
        when no name can be recovered (typical Magento soft-404).
        """
        if not _is_product_url(url):
            return None

        # BTR 301s retired slugs (e.g. ``/ac-delco-oil-filter-pf46-19210283-...``
        # → ``/ac-delco-oil-filter-pf46-12731172.html``) to the canonical product
        # page; the fetcher follows, and the JSON-LD on the landed page declares
        # the canonical URL, not the requested one. The URL-strict helper then
        # rejects it. Retry without URL-matching and accept the result only when
        # it declares a same-host URL — that still excludes the Wix/a90shop
        # cross-product JSON-LD footgun (different host / unrelated product).
        item = extract_json_ld_product(html, product_url=url)
        if not item:
            fallback = extract_json_ld_product(html)
            if fallback:
                declared = fallback.get("url")
                if isinstance(declared, str) and _is_product_url(declared):
                    item = fallback
        if not item:
            return None

        payload = scraped_payload_from_json_ld(item, url)
        if not payload or not payload.name:
            return None

        # Prefer mpn (clean manufacturer PN) over sku when both are present
        # and differ — mirrors the Texas Speed preference so cross-retailer
        # dedupe lines up on the same key.
        mpn_val = item.get("mpn") if isinstance(item, dict) else None
        mpn_str: Optional[str] = None
        if isinstance(mpn_val, str) and mpn_val.strip():
            mpn_str = mpn_val.strip()

        part_number = normalize_part_number(mpn_str) if mpn_str else None
        if not part_number:
            part_number = normalize_part_number(payload.part_number) if payload.part_number else None

        # BP Automotive ships 3-char alphanumeric SKUs ("A12", "E01") that
        # contain a digit so they pass ``is_junk_part_number`` but strip to
        # <4 chars and fail the canonical 4-char floor. Brand-prefix them
        # to ``BPA-<sku>`` (mirrors RSS / Forgeline) so the canonical
        # dedup key keeps the original code while clearing the floor.
        # Scoped to this manufacturer string so resold brands (ARP, Texas
        # Speed, Comp Cams, …) keep their vendor-issued identifiers.
        part_number = _brand_prefix_bp_automotive(
            part_number, payload.part_manufacturer
        )

        clean_name = _strip_trailing_mpn(payload.name, mpn_str)

        soup = BeautifulSoup(html, "html.parser")
        description = payload.description or _extract_description(soup)

        gallery_images = _extract_gallery_full_urls(html)
        image_urls = gallery_images or (payload.image_urls or None)

        out = ScrapedPayload(
            name=clean_name,
            product_url=url,
            description=description,
            price_cents=payload.price_cents,
            part_manufacturer=payload.part_manufacturer,
            part_number=part_number,
            image_urls=image_urls[:12] if image_urls else None,
            gtin=payload.gtin,
        )

        # Stash engine-family hint on the payload so the
        # ``infer_car_for_part`` override can resolve it without re-parsing
        # the HTML. setattr on the dataclass is safe — it isn't frozen and
        # ingest_payload only reads declared fields. Spec validation never
        # sees this attribute (would fail ``extra='forbid'`` if it did).
        family = _classify_engine_family(_extract_engine_type(soup))
        if family is not None:
            out._btr_engine_family = family  # type: ignore[attr-defined]
        return out

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Adapter-wins car-inference for BTR (S04 T04).

        Reads the engine-family hint stashed by ``parse_product_page`` and
        fans out to the LS-platform or LT-platform car_generation set.
        Conservative: narrower ``Engine Type`` values (``LSA``, ``LS3``,
        ``LS6`` ...) hand off to the universal phrase-triple pipeline rather
        than over-attributing.
        """
        family = getattr(parsed, "_btr_engine_family", None)
        if not family:
            return None
        triples = _ENGINE_FAMILY_TRIPLES.get(family)
        if not triples:
            logger.warning(
                "briantooleyracing: unknown engine family %r url=%s",
                family,
                parsed.product_url,
            )
            return None
        return list(triples)
