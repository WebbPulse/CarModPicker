"""
FTP Motorsport (ftpmotorsport.com.tw) crawler adapter.

Product URLs: https://www.ftpmotorsport.com.tw/products/<handle>

Platform: **EasyStore** (Shopify-shaped storefront served by Express + Varnish;
assets from ``store-themes.easystore.co``; product images from
``cdn.store-assets.com``). The shop migrated here from an older Shopline
instance (``ftpmotorsport.shoplineapp.com``) sometime in 2025; the legacy URL
is still linked as "Old Site" on the new homepage. **Platform first** for this
codebase — no other adapter talks to EasyStore yet. The JSON-LD / sitemap
layout is close enough to Shopify that the Shopify templates apply, but the
CDN host and the presence of an explicit ``sitemap_products.xml`` (rather than
Shopify's ``sitemap_products_N.xml`` children) are EasyStore-specific.

**Host candidates.** The task brief listed ``ftpmotorsports.com`` /
``ftp-motorsports.com``; both are NXDOMAIN. The real brand is singular
"Motorsport" and lives at ``ftpmotorsport.com.tw`` (Taipei-based, established
1997 per the site's own copy). ``ftpmotorsport.com`` now 302s to
``ftpmotorsport.com.tw`` so it's included in the host map for archive replay
completeness, but the canonical base we crawl from is the ``.com.tw`` domain.

Tier rationale (Tier 0 / plain HTTP):

- No Cloudflare interstitial on ``robots.txt``, ``/sitemap.xml``, or product
  pages for the crawler UA. Response headers show Varnish + Express, not
  ``cf-mitigated``.
- ``robots.txt`` is a standard Shopify-style allow list: only admin paths
  (``/cart``, ``/checkout``, ``/api``, ``/account``, ``/search``) are
  disallowed, plus per-bot crawl-delays (MJ12bot: 20s, AhrefsBot: 10s, none
  named for ``*``). Our UA is unrestricted.

Discovery: ``/sitemap.xml`` is a parent sitemapindex pointing at
``sitemap_products.xml`` (single urlset, ~1500 lines at probe time) plus
``_pages``, ``_collections``, ``_blogs``. We walk only the ``_products`` child
and collect every ``/products/<handle>`` ``<loc>`` — path has non-ASCII
separators (``｜``, the full-width vertical bar) in some handles, which we
preserve verbatim.

Parsing: plain ``@type: "Product"`` JSON-LD (not ``ProductGroup``; EasyStore
emits one Product block per page even when the page has size/color variants
— the first variant's fields are flattened at top level, matching Shopify's
plain-theme behavior from VARIANTS.md §3 row 1. We take the top-level
``sku``/``price``/``image[]`` as-is; other variants are silently lost, same as
every Shopify-plain adapter today). Shared ``extract_json_ld_product`` handles
the shape; we fall back to DOM/og meta when JSON-LD is missing.

Brand canonicalization (house brand "FTP Motorsport"):

- The JSON-LD on every sampled page has **no ``brand`` field at all**, so the
  title heuristic does the work. Titles follow two shapes:
    1. ``"FTP <model-code> <description>"`` (e.g. "FTP S58 High-Flow intake
       pipe…") — the heuristic picks "FTP" and we coerce to "FTP Motorsport".
    2. ``"【<Partner> 】<description>"`` — FTP resells a handful of
       partner-brand items (MaxCap being the one visible in the sitemap at
       probe time). The leading full-width bracket defeats the whitespace-
       tokenizer in ``part_manufacturer_from_title``, so we strip the
       ``【...】`` envelope before calling it and keep whatever partner brand
       was inside.
- Empty / car-make values (BMW / Mini / Toyota / etc. leaking from titles like
  "BMW S55 Engine Oil Cap…") are coerced to "FTP Motorsport". BMW is in
  ``_CAR_MAKES`` since FTP's catalog is BMW-first.

Caveats:

- **Host fragility.** FTP has already migrated platforms once
  (Shopline → EasyStore). If they move again, `ftpmotorsport.com.tw` is the
  durable anchor; `ftpmotorsport.com` (the plain .com redirect) may follow
  the migration or may not. The env override
  ``CRAWLER_FTPMOTORSPORTS_START_URLS`` is the escape hatch until the sitemap
  shape lands on a new host.
- **Multi-brand storefront.** Same consideration as `ind` / `burgermotorsports`
  — don't hard-coerce every page to the house brand. The MaxCap lineup is
  genuinely third-party; coerce only on car-make leaks and FTP's own aliases.
- **Variant bias.** One Part per URL (VARIANTS.md §3 Option A). EasyStore
  flattens the first variant's SKU/price/image into the top-level Product,
  so the DB row captures one of N option combinations silently. Acceptable
  for this catalog (charge pipes / intakes where variants are mostly fitment
  and a user would navigate per-URL anyway).
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

FTP_BASE = "https://www.ftpmotorsport.com.tw"
PRODUCT_PAGE_PATH = "/products/"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical house brand. FTP ships everything under this name; the Organization
# schema on the site spells it "FTP Motorsport" (singular, matching the host).
FTP_BRAND = "FTP Motorsport"

# Verified-live product URLs (probed 2026-04-21). Used when neither the env
# override nor sitemap discovery returns anything, so a cold-start smoke test
# still exercises the parser end-to-end.
DEFAULT_START_URLS = [
    (
        "https://www.ftpmotorsport.com.tw/products/"
        "ftp-s58-high-flow-intake-pipe-inlet-pipe-lite-version-"
        "f97-x3-m-f98-x4-m-11658089779-11658091579"
    ),
]

# Car makes that must never land in ``part_manufacturer``. FTP's catalog is
# BMW-first; titles like "BMW S55 Engine Oil Cap" will have the heuristic pick
# "BMW" as the first capitalized token, which we then rewrite to FTP_BRAND.
# Mini is on the same platform and gets the same treatment.
_CAR_MAKES = frozenset(
    {
        "bmw",
        "mini",
        "mercedes",
        "mercedes-benz",
        "toyota",
        "supra",
        "volkswagen",
        "vw",
        "audi",
        "porsche",
        "honda",
        "nissan",
        "infiniti",
        "subaru",
        "ford",
        "chevrolet",
        "chevy",
        "dodge",
        "ram",
        "jeep",
    }
)

# FTP's own name shows up in a handful of legal / abbreviated forms. Collapse
# all of them onto FTP_BRAND so we don't fragment the manufacturer table.
_FTP_BRAND_ALIASES = frozenset(
    {
        "ftp",
        "ftp motorsport",
        "ftp motorsports",
        "ftp motorsport inc",
        "ftp motorsport inc.",
        "ftp motorsport, inc.",
        "ftpmotorsport",
        "ftpmotorsports",
    }
)

# Leading full-width-bracket brand envelopes used on reseller listings, e.g.
# "【MaxCap 】BMW S55 Engine Oil Cap…". We peel the bracketed value out as the
# brand candidate and strip it from the title before running the generic
# heuristic (which otherwise chokes on the non-ASCII delimiters).
_BRACKET_BRAND_RE = re.compile(r"^\s*[【\[]\s*([^】\]]+?)\s*[】\]]\s*", re.UNICODE)


def _canonical_brand(brand: Optional[str]) -> Optional[str]:
    """
    FTP-specific brand canonicalization.

    - Empty / whitespace -> FTP_BRAND (every FTP-branded page lands here
      because JSON-LD has no ``brand`` key).
    - Car-make values (``"BMW"``, ``"Mini"``, ...) -> FTP_BRAND. These come
      from the title heuristic picking the first capitalized token on
      vehicle-targeted listings (``"BMW S55 Engine Oil Cap…"``).
    - Known FTP aliases (``"FTP"``, ``"FTPMotorsport"``, "FTP Motorsports" US
      plural variant) -> FTP_BRAND so the manufacturer row stays unified.
    - Anything else is passed through unchanged so partner brands like
      "MaxCap" — which FTP resells alongside its house line — keep their real
      manufacturer and don't get swallowed by the house brand.
    """
    if not brand or not brand.strip():
        return FTP_BRAND
    low = brand.strip().lower()
    if low in _CAR_MAKES:
        return FTP_BRAND
    if low in _FTP_BRAND_ALIASES:
        return FTP_BRAND
    return brand.strip()


def _brand_from_bracketed_title(title: str) -> Optional[str]:
    """
    Extract a partner brand from a leading full-width-bracket envelope.

    Reseller listings on FTP's storefront lead with the actual manufacturer in
    full-width brackets, e.g. ``"【MaxCap 】BMW S55 Engine Oil Cap…"``. The
    generic ``part_manufacturer_from_title`` doesn't handle the CJK
    punctuation, so we match the bracket group here and return its contents
    (trimmed of trailing spaces inside the bracket). Returns None if the title
    doesn't start with a bracket group or the bracket is empty.
    """
    if not title:
        return None
    m = _BRACKET_BRAND_RE.match(title)
    if not m:
        return None
    inside = m.group(1).strip()
    if not inside or len(inside) < 2:
        return None
    return inside


def _strip_bracket_prefix(title: str) -> str:
    """Drop a leading ``【…】`` envelope so downstream heuristics see a clean title."""
    if not title:
        return title
    return _BRACKET_BRAND_RE.sub("", title, count=1).strip()


def _resolve_start_urls() -> List[str]:
    """
    Return the list of product URLs to crawl.

    Precedence:
      1. ``CRAWLER_FTPMOTORSPORTS_START_URLS`` (comma-separated) — explicit override.
      2. Sitemap discovery (``/sitemap.xml`` → ``sitemap_products.xml``).
      3. ``DEFAULT_START_URLS`` — small hand-verified list so a cold smoke
         test still exercises the parser when discovery fails.
    """
    raw = os.environ.get("CRAWLER_FTPMOTORSPORTS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemapindex)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Walk ``/sitemap.xml`` and collect every ``/products/<handle>`` URL.

    FTP's sitemap index lists four children: ``sitemap_products.xml``,
    ``sitemap_pages.xml``, ``sitemap_collections.xml``, ``sitemap_blogs.xml``.
    Only the products child is product URLs — walking the others would cost
    HTTP round-trips with no yield. Returns a deduplicated list (canonical
    path, query stripped); empty on failure so the caller can fall back to
    DEFAULT_START_URLS.
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
        index_url = FTP_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                # Only the ``sitemap_products`` urlset is product URLs.
                if "sitemap_products" not in child_url:
                    continue
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
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


class FTPMotorsportsAdapter(RetailerCrawlerAdapter):
    """
    FTP Motorsport adapter. Tier 0 (plain HTTP is sufficient).

    Discovery: EasyStore sitemap index → ``sitemap_products.xml`` child
    (single flat urlset). ``CRAWLER_FTPMOTORSPORTS_START_URLS`` overrides.

    Parsing: plain ``Product`` JSON-LD first (the shape EasyStore emits; the
    first variant's fields are flattened at the top level per VARIANTS.md §3
    row 1), then a DOM / og-meta fallback. Brand is canonicalized to
    "FTP Motorsport" when JSON-LD has no brand (the norm on this site), when
    the title heuristic returns a car make, or when it returns a known FTP
    alias. Bracket-prefixed reseller titles (``"【MaxCap 】…"``) have their
    partner brand peeled out before the heuristic runs, so third-party items
    keep their real manufacturer.
    """

    ADAPTER_NAME: ClassVar[str] = "ftpmotorsports"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Env override wins, then sitemap, then
        ``DEFAULT_START_URLS``. Runner applies ``--limit`` downstream.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an FTP Motorsport product page.

        Tries JSON-LD ``Product`` first (every sampled page carries one with
        name / description / sku / offers.price / image[]). Falls back to
        DOM + og-meta when JSON-LD is missing or malformed.

        Returns None when no name can be extracted.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product (the common path on this site).
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                name = payload.name
                # JSON-LD has no ``brand`` field on this site; derive from the
                # title. Strip any leading ``【Partner 】`` envelope so the
                # generic heuristic sees clean text, but remember the
                # bracketed value as a partner-brand candidate.
                bracket_brand = _brand_from_bracketed_title(name)
                cleaned_name = _strip_bracket_prefix(name) if bracket_brand else name

                part_manufacturer: Optional[str] = payload.part_manufacturer
                if not part_manufacturer and bracket_brand:
                    part_manufacturer = bracket_brand
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_from_title(cleaned_name)
                if not part_manufacturer and payload.description:
                    part_manufacturer = part_manufacturer_from_description(
                        payload.description, product_name=cleaned_name
                    )
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_fallback_from_title(cleaned_name)
                part_manufacturer = _canonical_brand(part_manufacturer)

                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None

                return ScrapedPayload(
                    name=name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=payload.image_urls,
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
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        bracket_brand = _brand_from_bracketed_title(str(name))
        cleaned_name = _strip_bracket_prefix(str(name)) if bracket_brand else str(name)
        part_manufacturer: Optional[str] = bracket_brand
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(cleaned_name)
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=cleaned_name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(cleaned_name)
        part_manufacturer = _canonical_brand(part_manufacturer)

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=None,
        )
