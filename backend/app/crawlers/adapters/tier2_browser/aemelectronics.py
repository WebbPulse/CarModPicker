"""
AEM Performance Electronics (aemelectronics.com) crawler adapter.

**Not to be confused with AEM Intakes.** The "AEM" brand split years ago.
The intake / cold-air-intake line ("AEM Induction") is now under Holley and
lives at ``aemintakes.com`` — a separate catalog with separate SKUs.
*This* adapter is for the **AEM Performance Electronics** business — ECUs
(Infinity, Infinity-6, Series 2 EMS), wideband UEGO controllers, digital
gauges (X-Series), boost controllers, CD-5 / CD-7 dashes, and the fuel /
injector hardware that ships with those kits. If the target URL is on
``aemintakes.com``, that's a different retailer and this adapter is wrong
for it.

Platform: **Drupal 7** (generator meta ``Drupal 7``; node-type
``aem-product-sections``; AdvAgg JS aggregator at
``/sites/default/files/advagg_js/``). Custom Drupal product type — not
Commerce Kickstart, not Ubercart's canonical theme — so there is **no
JSON-LD ``Product``** on the page. The only structured-data signal is a
bare ``itemprop="offers"`` microdata wrapper; the rest of the DOM is
custom templating. Parsing is DOM-driven:

- Product name: ``<h1>`` inside the product section (Drupal's default
  node title). OG ``og:title`` / ``<title>`` are reliable fallbacks.
- Part number: the catalog prints ``Part Number: NN-NNNN`` (e.g.
  ``30-4350`` for the X-Series wideband gauge, ``30-0352`` for the
  Infinity-6 EMS). Extract via the ``Part Number:`` label.
- Price: ``itemprop="price"`` inside the ``offers`` wrapper, with a
  ``$NNN.NN`` text fallback for the few pages that render price outside
  the microdata block.
- Description: Drupal field ``field-name-body`` / ``field-type-text-long``
  panel; fall back to ``meta name="description"``.
- Images: product-page ``<img>`` tags whose src contains
  ``/sites/default/files/`` (Drupal's public files directory).

Discovery: the site is **entirely behind a Cloudflare *managed JS
challenge*** — every path (``/``, ``/robots.txt``, ``/sitemap.xml``,
product pages) returns HTTP 403 with ``cf-mitigated: challenge`` to
plain ``requests``. TLS impersonation alone will not clear the challenge
because JS execution is required. Hence ``FETCHER_TIER = "browser"`` —
live discovery and fetches are gated on a configured FlareSolverr service
(``FLARESOLVERR_URL``). Until that is wired in for this origin,
``discover_product_urls`` is a **stub** that yields nothing. Product
HTML arriving via the Chrome extension (``POST /crawled-pages/scrape``)
or archive rescrape still routes through this adapter for per-site
parsing (the next author should register the
``aemelectronics.com`` / ``aem-usa.com`` / ``aempower.com`` hosts in
``adapter_name_for_product_url`` when the registry is touched).

Host disposition:

- ``aemelectronics.com`` (apex) → 301s to ``www.aemelectronics.com``.
- ``www.aemelectronics.com`` — canonical catalog; Cloudflare challenged.
- ``aempower.com`` — 301s to ``www.aemelectronics.com`` (legacy brand
  domain kept alive for inbound links).
- ``aem-usa.com`` — **different company** (AEM Components — aerospace /
  mil-spec passive electronics, ferrite chips, tin-whisker mitigation).
  Do **not** route aem-usa.com to this adapter; unrelated catalog.

Brand rule: canonical part_manufacturer is ``"AEM Performance Electronics"``.
The DOM never advertises a "brand" row (first-party storefront), so the
shared title heuristic will pick off car makes that appear in plug-and-play
fit tables ("Infinity-8 Plug-N-Play EMS for Mitsubishi Evo X"). Every
platform AEM's Infinity / Infinity-6 / Series-2 EMS fits gets listed in
the blocklist below — Subaru / Honda / Acura / Nissan / Infiniti / Toyota
/ Lexus / Mazda / Mitsubishi / BMW / Porsche / Audi / Volkswagen / Ford
/ Chevrolet / Dodge / Mercedes / Hyundai — so the title heuristic never
mints a phantom car-make manufacturer. Empty / car-make / generic-word
results all coerce to ``"AEM Performance Electronics"``.

Variant rule: per ``VARIANTS.md`` §3, one ``ScrapedPayload`` per URL.
AEM's catalog skews single-SKU-per-page; variation axes that do exist
(gauge bezel color, harness length) each live on their own URL in the
Drupal taxonomy, so no ``hasVariant`` descent is needed. Matches the
"most Shopify adapters" row of the survey table — top-level fields win,
other variants are silently out of scope.

Tier rationale: Tier 2 (``FETCHER_TIER = "browser"``). Live probe against
``www.aemelectronics.com`` returned HTTP 403 with
``cf-mitigated: challenge`` on every path tested, including
``/robots.txt`` and ``/sitemap.xml``. Tier 1 (TLS impersonation) will not
help because this is a JS challenge, not a JA3 block. FlareSolverr is the
only viable fetcher.

Caveats:

- **AEM Electronics vs AEM Intakes** — the single most important thing to
  double-check on any URL routed here. The intake catalog is on a
  different host (``aemintakes.com``) and under Holley's corporate
  umbrella now. Parts overlap in name (both have "AEM"-branded SKUs) but
  not in numbering; misrouting would cross-contaminate the
  PartManufacturer dedupe.
- **No JSON-LD** — do not wire in ``extract_json_ld_product``; the page
  has none and a fallback ``Product`` in a shared menu blob would
  overwrite the real data. Parsing is DOM-only.
- **Challenge on /robots.txt** — the shared robots fetch in ``base.py``
  treats 403/401 as "allow all" specifically to handle this case
  (documented there alongside the bimmerworld / amsperformance
  observation). Good; no special handling needed here.
- **Discovery stub** — when Tier 2 is live, discovery can walk the
  top-level category pages (``/products/programmable-engine-management-systems``,
  ``/products/wideband-uego-air-fuel-controllers``,
  ``/products/gauges``, ``/products/boost-controllers``,
  ``/products/cd-digital-dash-displays-adapter-harnesses``,
  ``/products/fuel-delivery``) and follow ``href`` links with the
  ``/products/`` prefix. Drupal's ``/sitemap.xml`` exists but is
  behind the same challenge.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    extract_dom_price,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

AEM_ELECTRONICS_BASE = "https://www.aemelectronics.com"
AEM_ELECTRONICS_BRAND = "AEM Performance Electronics"

# Car makes whose names appear in AEM product titles because the Infinity /
# Infinity-6 / Series-2 EMS line is sold as plug-and-play kits per chassis.
# Any of these → coerce to the canonical "AEM Performance Electronics" brand
# so we don't grow phantom car-make manufacturers from the title heuristic.
_CAR_MAKES = frozenset(
    {
        "subaru",
        "honda",
        "acura",
        "nissan",
        "infiniti",
        "toyota",
        "lexus",
        "mazda",
        "mitsubishi",
        "bmw",
        "porsche",
        "audi",
        "volkswagen",
        "vw",
        "ford",
        "chevrolet",
        "chevy",
        "gm",
        "dodge",
        "mopar",
        "mercedes",
        "mercedes-benz",
        "hyundai",
        "kia",
        "scion",
    }
)

# Generic tokens that occasionally win the first-token title heuristic on
# this catalog ("Infinity", "Series", "Wideband", "UEGO" — AEM product-line
# names that are not brand names). Coerced to canonical too.
_BRAND_REJECT_TOKENS = frozenset(
    {
        "infinity",
        "infinity-6",
        "series",
        "wideband",
        "uego",
        "x-series",
        "cd-5",
        "cd-7",
        "tru-boost",
        "aemnet",
        "ems",
    }
)

# AEM printed part numbers are the classic 30-series SKUs: NN-NNNN (e.g.
# 30-0352, 30-4350, 84-2322, 23-0046). Used as a fallback when the "Part
# Number:" label isn't present — narrow enough that it won't match random
# dates or telephone numbers in the page body.
_AEM_PART_NUMBER_RE = re.compile(r"\b(\d{2}-\d{3,5})\b")

# Drupal's public files directory — product imagery lives here. Filters out
# site chrome (header logo, footer icons, payment-method sprites) which live
# under ``/sites/default/files/logo.png`` or ``/misc/`` outside the ``files``
# subtree of the theme.
_IMAGE_FILES_PATH = "/sites/default/files/"

# Same noise patterns other Drupal / Shopify adapters filter out — match
# against the URL lowercased.
_IMAGE_NOISE_RE = re.compile(
    r"logo|favicon|sprite|placeholder|payment|header|footer|icon[-_]|banner",
    re.IGNORECASE,
)

DEFAULT_START_URLS: List[str] = [
    # Verified product URLs captured from 2023 archive snapshots; kept for
    # parse-test use by the archive-replay pipeline. Live crawling is gated
    # on FlareSolverr — see module docstring.
    "https://www.aemelectronics.com/products/boost-controllers/tru-boostx-controller-gauge",
    "https://www.aemelectronics.com/products/wideband-uego-air-fuel-controllers",
]


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise empty (discovery is stubbed for now)."""
    raw = os.environ.get("CRAWLER_AEMELECTRONICS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return []


def _normalize_image_url(src: str) -> Optional[str]:
    """Scheme-relative / root-relative → absolute URL on aemelectronics.com."""
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("/"):
        return AEM_ELECTRONICS_BASE + s
    if s.startswith("http://"):
        return "https://" + s[len("http://") :]
    if s.startswith("https://"):
        return s
    return None


def _is_valid_product_image(url: str) -> bool:
    """True for ``/sites/default/files/`` images that aren't site chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if _IMAGE_FILES_PATH not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """Gather product-gallery image URLs from the DOM, deduped, capped at 12."""
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        absolute = _normalize_image_url(raw)
        if not absolute or not _is_valid_product_image(absolute):
            return
        if absolute in seen:
            return
        seen.add(absolute)
        ordered.append(absolute)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content)

    for img in soup.find_all("img", src=True):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        src = img.get("src")
        if isinstance(src, str):
            add(src)

    return ordered[:12]


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """Product name: ``<h1>`` → ``og:title`` → ``<title>``."""
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text and len(text) >= 3:
            return text

    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        content = meta_content(og_title)
        if content and content.strip() and len(content.strip()) >= 3:
            # Drupal's OG title often ends with "| AEM" — strip trailing site.
            return re.sub(r"\s*\|\s*AEM.*$", "", content.strip())

    title = soup.find("title")
    if isinstance(title, Tag):
        text = title.get_text(strip=True)
        if text:
            return re.sub(r"\s*\|\s*AEM.*$", "", text) or None
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Description: Drupal body field → meta description."""
    for selector in (
        ".field-name-body",
        ".field-type-text-long",
        ".node-aem-product-sections .field-name-body",
        "#block-system-main .field-type-text-with-summary",
    ):
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            text = node.get_text(separator=" ", strip=True)
            if text and len(text) > 40:
                normalized = normalize_description_text(text, max_len=2000)
                if normalized:
                    return normalized

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        content = meta_content(meta_desc)
        if content and content.strip():
            return normalize_description_text(content, max_len=2000)
    return None


def _extract_part_number(soup: BeautifulSoup) -> Optional[str]:
    """Prefer ``Part Number: NN-NNNN`` label; fall back to bare NN-NNNN regex."""
    body_text = soup.get_text(separator=" ", strip=True)
    # Strip trailing punctuation from the capture so "Part Number: 30-0300." on
    # the end of a sentence produces "30-0300", not "30-0300." — matches the
    # shared ``extract_sku_from_text`` behavior for the same edge case.
    label_match = re.search(
        r"Part\s*Number\s*:\s*([A-Za-z0-9][A-Za-z0-9\-\/]{2,})",
        body_text,
        re.IGNORECASE,
    )
    if label_match:
        raw = label_match.group(1).rstrip(".")
        candidate = normalize_part_number(raw)
        if candidate:
            return candidate

    sku_via_shared = extract_sku_from_text(body_text)
    if sku_via_shared:
        return sku_via_shared

    pn_match = _AEM_PART_NUMBER_RE.search(body_text)
    if pn_match:
        return normalize_part_number(pn_match.group(1))
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """Price: ``itemprop="price"`` → shared DOM scanner."""
    price_elem = soup.find(attrs={"itemprop": "price"})
    if isinstance(price_elem, Tag):
        # ``content`` attr (microdata canonical form) wins over inner text.
        content = price_elem.get("content")
        if isinstance(content, str) and content.strip():
            cents = parse_price_cents(content)
            if cents is not None:
                return cents
        text = price_elem.get_text(strip=True)
        if text:
            cents = parse_price_cents(text)
            if cents is not None:
                return cents
    return extract_dom_price(soup)


def _normalize_part_manufacturer(raw: Optional[str]) -> str:
    """
    Coerce to canonical ``"AEM Performance Electronics"`` for:
    empty, car-make (full platform list — see module docstring), generic AEM
    product-line token, or any ``"AEM ..."`` variant. Anything else passes
    through unchanged in case a co-branded SKU surfaces (none observed so far
    on this first-party storefront, but preserves the pattern used elsewhere).
    """
    value = (raw or "").strip()
    if not value:
        return AEM_ELECTRONICS_BRAND
    low = value.lower()
    if low in _CAR_MAKES or low in _BRAND_REJECT_TOKENS:
        return AEM_ELECTRONICS_BRAND
    # Collapse "AEM", "AEM Electronics", "AEM Performance", "AEM Performance
    # Electronics" (and case variants) into the canonical label.
    if low == "aem" or low.startswith("aem ") or low.startswith("aem-"):
        return AEM_ELECTRONICS_BRAND
    return value


class AEMElectronicsAdapter(RetailerCrawlerAdapter):
    """
    AEM Performance Electronics adapter.

    Live crawling is gated on FlareSolverr (``FETCHER_TIER = "browser"``) —
    every path on ``www.aemelectronics.com`` is behind a Cloudflare managed
    JS challenge. Until Tier 2 is wired up for this origin, this adapter is
    used only for HTML captured through the Chrome extension or replayed
    from the archive. ``discover_product_urls`` honors the
    ``CRAWLER_AEMELECTRONICS_START_URLS`` env override for one-off parse
    tests; otherwise it returns an empty iterator.

    Parsing is **DOM-only** — the storefront emits no JSON-LD ``Product``.
    Brand is always forced to the canonical ``"AEM Performance
    Electronics"``; the DOM has no brand field and the shared title
    heuristic's first-token pass would otherwise pick up car makes from
    plug-and-play fitment strings.
    """

    ADAPTER_NAME: ClassVar[str] = "aemelectronics"
    FETCHER_TIER = "browser"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Stub: live crawling requires FlareSolverr (JS challenge on every
        path including ``/robots.txt`` and ``/sitemap.xml``). Yields URLs
        from ``CRAWLER_AEMELECTRONICS_START_URLS`` when set, otherwise an
        empty iterator — the chrome-extension / archive-replay paths do
        not call this.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an AEM Performance Electronics product page. DOM-driven
        because this storefront (Drupal 7, ``aem-product-sections`` node
        type) does not emit JSON-LD. Returns ``None`` when no name can
        be extracted — that's a non-product page (category listing,
        search, account).
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name:
            return None

        part_number = _extract_part_number(soup)
        description = _extract_description(soup)
        price_cents = _extract_price_cents(soup)
        image_urls = _extract_dom_images(soup)
        part_manufacturer = _normalize_part_manufacturer(None)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
