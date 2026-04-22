"""
Hennessey Performance (hennesseyperformance.com) crawler adapter.

Hennessey is the Sealy, Texas house brand for high-horsepower Ford / Dodge /
GM turn-key packages — VelociRaptor Bronco/F-150/Ranger, Mammoth TRX, H650
Escalade/Yukon/Tahoe, H1000 CT5-V Blackwing, supercharged Mustang /
Challenger / Hellcat builds, and so on. Closest spiritual analogue in the
Phase 1/2 adapter set is Lingenfelter — a specialty-vertical, first-party,
"complete vehicle or installed package" storefront rather than a parts
catalog. Unlike Lingenfelter, Hennessey does **not** publish a priced
Miva-style PDP per SKU; the public site is a marketing brochure.

Platform: WordPress 6.9 + Elementor Pro, Rank Math SEO plugin
(``<meta name="generator" content="WordPress 6.9.4" />``). Host canonicalizes
302→https://www.hennesseyperformance.com/. The sister domains are
``hennesseymotorsports.com`` (405s — parked / ops-only) and ``hennessey.com``
(separate WP Engine + Cloudflare site, the Venom F5 hypercar brand — not
covered here; see caveats).

Discovery: ``/sitemap_index.xml`` (Rank Math-generated index) points at six
children — ``post-sitemap.xml``, ``page-sitemap.xml``, ``category-sitemap.xml``,
``news-sitemap.xml``, ``video-sitemap.xml``, ``local-sitemap.xml``. There is
**no product-sitemap**. Upgrade-package pages live at ``/vehicles/<slug>/``
inside ``page-sitemap.xml`` (e.g. ``velociraptor-500-bronco-raptor-upgrade``,
``h1000-cadillac-ct5-v-blackwing``, ``mammoth-1000-trx-upgrades``). The
adapter walks ``page-sitemap.xml`` and keeps only ``/vehicles/<slug>/``
entries whose slug is **not** one of the reserved non-package paths (the
index ``/vehicles/``, ``/vehicles/vehicles-for-sale/`` and its ``sold/``
child, and the individual ``/vehicles/vehicles-for-sale/<used-car>-for-sale/``
listings — those are one-off used cars, not a reproducible
upgrade/package product). Override with ``CRAWLER_HENNESSEY_START_URLS``
(comma-separated).

JSON-LD shape: Rank Math emits a top-level ``@graph`` per page mixing
``AutomotiveBusiness``, ``WebSite``, ``WebPage``/``ItemPage``,
``ImageObject``, ``Place``, and — **inconsistently** — a single ``Product``
block (``@type: "Product"``) with ``name`` + ``description`` + ``brand``
(``{"@type":"Brand","name":"Hennessey VelociRaptor"}``) + ``image``. The
Product block carries **no** ``offers``, ``price``, ``sku``, or ``gtin`` —
these are marketing pages, not e-commerce PDPs. Roughly half the
``/vehicles/`` pages we sampled omit the Product block entirely. The
shared ``extract_json_ld_product`` + ``scraped_payload_from_json_ld``
handle the happy path; when no Product block is present the adapter
falls back to ``<title>`` + ``meta[property=og:description]`` +
``meta[property=og:image]`` so we still emit a payload that serves as a
catalog stub for the package.

Variant axis: **none.** The ``/vehicles/<slug>/`` pages are per-package
marketing wrappers (one upgrade tier per URL — e.g. "VelociRaptor 500" vs.
"VelociRaptor 600" get separate slugs). There is no picker, no child
variants, and no per-option SKU on the page, so the "one Part per URL"
contract is a natural fit. See ``VARIANTS.md`` for the cross-adapter
survey; Hennessey falls into the same bucket as a parent-only Shopify
page with no ``hasVariant`` descent needed.

Tier rationale: ``http`` — ``/robots.txt`` returns 200 with
``Disallow: /wp-admin/`` (plus ``/wp-content/uploads/wpforms/``) and a
sitemap reference; product pages return 200 to a plain ``curl`` with no
Cloudflare interstitial. The site runs behind a "tt-server" header
(NitroPack cache + Apache origin); no TLS fingerprint block observed. If
the origin later adds a CF challenge the adapter should be promoted to
``tls`` first.

Brand rule: house brand is canonicalized to **"Hennessey Performance"**.
The JSON-LD ``brand.name`` varies by sub-marque ("Hennessey VelociRaptor",
"Hennessey Mammoth", "Hennessey H650"); we collapse anything starting with
``"hennessey"`` to the single canonical name to protect cross-manufacturer
dedupe. Car makes and model names that the shared title heuristic would
otherwise pick (Ford / Dodge / Chevy / Ram / Cadillac / GMC / Mustang /
Raptor / Bronco / Camaro / Corvette / Challenger / Charger / Hellcat / F-150 /
TRX / Tahoe / Yukon / Suburban / Escalade) are in the blocklist — every
Hennessey title leads with the target vehicle ("Ford Bronco VelociRaptor
500") and the heuristic would otherwise leak the car make as the
manufacturer.

Caveats — critical to remember during smoke-test:

* **Complete-vehicle storefront, not a parts catalog.** Every Part row
  created by this adapter will have ``price_cents=None`` and
  ``part_number=None`` — not because of a site bug but because the public
  pages carry neither. Cross-retailer dedupe therefore falls back to
  ``(retailer, url)`` rather than ``(manufacturer, part_number)``. This is
  the same contract as the ``radium`` adapter (MAP-enforced null SKU / $0
  price on every PDP) and the UI already tolerates it.
* **Inconsistent Product JSON-LD.** Roughly half the ``/vehicles/`` pages
  sampled during recon emit a ``Product`` JSON-LD block; the rest emit only
  ``WebPage`` / ``AutomotiveBusiness`` / ``ImageObject``. The fallback
  parser (``<title>`` / OG meta) handles the no-Product case so we still
  get a row per package.
* **"Vehicles for sale" subtree is excluded.** ``/vehicles/vehicles-for-sale/…``
  URLs (e.g. ``/vehicles/vehicles-for-sale/2022-white-ram-trx-for-sale/``)
  are one-off used-car listings — wrong model for a reproducible catalog.
  These are filtered out at discovery.
* **hennessey.com and hennesseymotorsports.com are not this adapter.**
  ``hennessey.com`` is the Venom F5 hypercar brand (separate WP Engine +
  Cloudflare stack, different catalog scope) and ``hennesseymotorsports.com``
  405s on ``/``. If a future task wants to ingest Venom F5 / grand-tourer
  brochure pages, a second adapter (or an explicit host-map expansion) is
  the right move — the sitemap and page shapes differ.
"""

import os
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urljoin, urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_json_ld_product,
    meta_content,
    normalize_description_text,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

HENNESSEY_BASE = "https://www.hennesseyperformance.com"
SITEMAP_INDEX_URL = f"{HENNESSEY_BASE}/sitemap_index.xml"
PAGE_SITEMAP_URL = f"{HENNESSEY_BASE}/page-sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical first-party brand. JSON-LD ``brand.name`` varies by sub-marque
# ("Hennessey VelociRaptor", "Hennessey Mammoth", "Hennessey H650"); we
# collapse every ``"hennessey ..."`` variant onto this single canonical
# string so a VelociRaptor package and a Mammoth package don't split the
# house brand into two PartManufacturer rows.
HENNESSEY_BRAND = "Hennessey Performance"

# Slugs inside ``/vehicles/`` that are NOT upgrade-package pages and must
# be skipped at discovery. ``vehicles-for-sale`` (and its ``sold`` child
# + ``<used-car>-for-sale`` listings) is Hennessey's used-car inventory —
# one-off listings, not a reproducible catalog product.
_NON_PACKAGE_VEHICLES_SLUGS = frozenset(
    {
        "",  # index page /vehicles/
        "vehicles-for-sale",
    }
)

# Car makes / models / platform names that frequently appear as the first
# token of a Hennessey product title ("Ford Bronco VelociRaptor 500",
# "Cadillac CT5-V Blackwing Upgrade", "Ram TRX Mammoth 1000 Upgrade").
# ``part_manufacturer_from_title`` would otherwise return the car make as
# the part manufacturer; short-circuit here so the house-brand default
# wins instead. Intentionally narrow to Hennessey's actual platform
# coverage — adding unrelated makes (BMW / Porsche / Subaru) here is
# both unnecessary and a footgun if a Hennessey product ever carries a
# third-party brand we want to preserve.
_HENNESSEY_CAR_MODEL_TOKENS = frozenset(
    {
        # Makes
        "ford",
        "dodge",
        "chevy",
        "chevrolet",
        "ram",
        "cadillac",
        "gmc",
        "lincoln",
        # Mustang / Ford performance lineage
        "mustang",
        "shelby",
        "gt350",
        "gt500",
        "raptor",
        "bronco",
        "ranger",
        "f-150",
        "f150",
        "f-250",
        # GM / Cadillac performance lineage
        "camaro",
        "corvette",
        "ct5",
        "ct5-v",
        "ct6",
        "ct6-v",
        "ats",
        "ats-v",
        "cts",
        "cts-v",
        "escalade",
        "tahoe",
        "suburban",
        "yukon",
        "sierra",
        "silverado",
        "zl1",
        "zr1",
        "z06",
        "blackwing",
        # Mopar lineage
        "challenger",
        "charger",
        "hellcat",
        "durango",
        "trx",
        # Sub-marque words that precede a model number
        "velociraptor",
        "mammoth",
        "venom",
        "goliath",
    }
)

# Fixed fallback so the adapter still yields something if the sitemap is
# temporarily unreachable. Both slugs are known-good Product-JSON-LD pages
# (verified during recon).
DEFAULT_START_URLS = [
    f"{HENNESSEY_BASE}/vehicles/velociraptor-500-bronco-raptor-upgrade/",
    f"{HENNESSEY_BASE}/vehicles/cadillac-escalade-v-upgrade/",
    f"{HENNESSEY_BASE}/vehicles/ram-trx-upgrades/",
]


def _is_package_url(url: str) -> bool:
    """
    True if ``url`` is a ``/vehicles/<slug>/`` upgrade-package page on the
    Hennessey Performance host. Rejects the ``/vehicles/`` index, the
    ``vehicles-for-sale`` subtree (used-car inventory, one-off listings),
    and any non-Hennessey host.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "hennesseyperformance.com" or host.endswith(".hennesseyperformance.com")):
        return False
    path = parsed.path or ""
    if not path.startswith("/vehicles/"):
        return False
    remainder = path[len("/vehicles/") :].strip("/")
    # Index page or an obvious non-package route.
    if not remainder:
        return False
    first_seg = remainder.split("/", 1)[0].lower()
    if first_seg in _NON_PACKAGE_VEHICLES_SLUGS:
        return False
    # Single-segment slug only (``/vehicles/<slug>/``). Deeper paths are
    # nested subpages we don't recognize and would rather skip than misparse.
    if "/" in remainder.rstrip("/"):
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_HENNESSEY_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_HENNESSEY_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap() -> List[str]:
    """
    Walk the Rank Math sitemap index → ``page-sitemap.xml`` and return every
    ``/vehicles/<slug>/`` entry that passes ``_is_package_url``. Deduplicated
    by absolute URL; empty list on fetch/parse failure.

    We fetch ``page-sitemap.xml`` directly rather than iterating through the
    full index — the other Rank Math children (``post-sitemap``,
    ``news-sitemap``, ``video-sitemap``, etc.) carry blog posts and video
    landing pages, none of which host the package PDPs.
    """
    try:
        xml_text = fetch_page(PAGE_SITEMAP_URL, timeout=30)
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    seen: set[str] = set()
    package_urls: List[str] = []

    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        url = loc.text.strip().split("?", 1)[0].split("#", 1)[0]
        if not url:
            continue
        if not _is_package_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        package_urls.append(url)

    return package_urls


def _normalize_brand(raw_brand: Optional[str]) -> Optional[str]:
    """
    Collapse every ``"hennessey ..."`` variant onto the canonical
    ``"Hennessey Performance"`` brand. Other values (none expected in
    practice — this is a first-party storefront) pass through unchanged.
    """
    if not raw_brand:
        return None
    cleaned = raw_brand.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith("hennessey"):
        return HENNESSEY_BRAND
    return cleaned


def _resolve_brand(name: Optional[str], json_ld_brand: Optional[str]) -> str:
    """
    Prefer JSON-LD brand (normalized) when present; otherwise try the title
    heuristic but reject car makes / models / platform nameplates via
    ``_HENNESSEY_CAR_MODEL_TOKENS``. Fall back to the house brand — every
    Hennessey ``/vehicles/`` page is a first-party upgrade, so that is the
    correct default when no explicit brand is available.
    """
    normalized = _normalize_brand(json_ld_brand)
    if normalized:
        return normalized
    if name:
        heuristic = part_manufacturer_from_title(name)
        if heuristic:
            if heuristic.strip().lower() in _HENNESSEY_CAR_MODEL_TOKENS:
                heuristic = None
        normalized = _normalize_brand(heuristic)
        if normalized:
            return normalized
    return HENNESSEY_BRAND


def _fallback_payload_from_dom(html: str, url: str) -> Optional[ScrapedPayload]:
    """
    Build a minimal ``ScrapedPayload`` from ``<title>`` + OpenGraph meta
    when no JSON-LD ``Product`` block is present. About half the
    ``/vehicles/`` pages sampled during recon omit the Product block —
    this path keeps us from silently dropping those packages.

    No price / SKU is available on any Hennessey page, so those stay
    ``None``. The brand is set to the house brand.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Prefer og:title over <title> — the raw <title> is suffixed with
    # " - Hennessey Performance", which the OG value already strips on some
    # pages. Fall back to <title> with the suffix removed.
    og_title = meta_content(soup.find("meta", property="og:title"))
    name: Optional[str] = None
    if og_title and og_title.strip():
        name = og_title.strip()
    else:
        title_tag = soup.find("title")
        if isinstance(title_tag, Tag):
            raw_title = title_tag.get_text(strip=True)
            if raw_title:
                # Strip the " - Hennessey Performance" / " | Hennessey Performance"
                # suffix that WP prepends to the <title>.
                for sep in (" - Hennessey Performance", " | Hennessey Performance"):
                    if raw_title.endswith(sep):
                        raw_title = raw_title[: -len(sep)].strip()
                        break
                name = raw_title or None
    if not name or len(name) < 3:
        return None

    og_desc = meta_content(soup.find("meta", property="og:description"))
    description = normalize_description_text(og_desc, max_len=2000) if og_desc else None

    og_image = meta_content(soup.find("meta", property="og:image"))
    images: List[str] = []
    if og_image and og_image.strip():
        images.append(urljoin(url, og_image.strip()))

    return ScrapedPayload(
        name=name,
        product_url=url,
        description=description,
        price_cents=None,
        part_manufacturer=HENNESSEY_BRAND,
        part_number=None,
        image_urls=images or None,
    )


class HennesseyAdapter(RetailerCrawlerAdapter):
    """
    Hennessey Performance adapter.

    WordPress / Elementor storefront; plain-HTTP fetches. Discovery walks the
    Rank Math ``page-sitemap.xml`` for ``/vehicles/<slug>/`` upgrade-package
    pages (used-car ``vehicles-for-sale`` subtree excluded). Parsing prefers
    the inconsistently-emitted JSON-LD ``Product`` block (name / description /
    brand / image — **no price, no sku**); falls back to ``<title>`` + OG
    meta when the block is absent. Brand is normalized to
    ``"Hennessey Performance"`` for every sub-marque (VelociRaptor / Mammoth /
    H650 / H1000 / Venom / Goliath).

    Caveat — this is a complete-vehicle marketing storefront rather than a
    parts catalog. ``price_cents`` and ``part_number`` are ``None`` by
    design; cross-retailer dedupe falls back to ``(retailer, url)``.
    """

    ADAPTER_NAME: ClassVar[str] = "hennessey"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield package-page URLs. Env override wins; sitemap next; fixed fallback last."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_package_url(url):
                    yield url
            return

        discovered = _discover_via_sitemap()
        if discovered:
            for url in discovered:
                yield url
            return

        for url in DEFAULT_START_URLS:
            if _is_package_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Hennessey ``/vehicles/<slug>/`` upgrade-package page into a
        ``ScrapedPayload``. Returns ``None`` when the URL is not package-shaped
        or when neither the JSON-LD ``Product`` block nor the OpenGraph
        fallback yields a usable name.
        """
        if not _is_package_url(url):
            return None

        # Prefer the Rank Math-emitted JSON-LD Product block. Passing
        # ``product_url`` lets the shared extractor reject a Product whose
        # declared URL points at a different slug (belt-and-suspenders; not
        # observed on Hennessey, but cheap).
        product_item = extract_json_ld_product(html, product_url=url)
        if product_item is not None:
            payload = scraped_payload_from_json_ld(product_item, url)
            if payload is not None:
                # Hennessey Product JSON-LD carries no offers / sku / price.
                # ``scraped_payload_from_json_ld`` already returns ``None`` for
                # those fields; enforce our brand canonicalization on top.
                brand = _resolve_brand(payload.name, payload.part_manufacturer)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=None,
                    part_manufacturer=brand,
                    part_number=None,
                    image_urls=payload.image_urls,
                )

        # Fallback: no Product JSON-LD block on this page (~50% of
        # ``/vehicles/`` pages in recon). Pull what we can from
        # ``<title>`` + OpenGraph meta.
        return _fallback_payload_from_dom(html, url)
