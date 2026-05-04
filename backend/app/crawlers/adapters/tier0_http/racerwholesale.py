"""
Racer Wholesale (racerwholesale.com) crawler adapter — **stub, site offline**.

Status as of 2026-04-21 recon: there is no live retailer at either of the
candidate hosts listed in the backlog.

  * ``racerwholesale.com`` — resolves (A ``2.57.91.91``) but HTTPS returns
    ``TLSv1.3 alert internal error (592)`` on handshake. Plain HTTP on :80
    serves ``200 OK`` from a Hostinger-branded "Parked Domain name on
    Hostinger DNS system" page (``Server: hcdn``, ``Content-Type: text/html``,
    ``Cache-Control: no-store``, ``alt-svc: h3=":443"``). No cart, no
    products, no sitemap, no ``/robots.txt`` — just a placeholder template
    with ``<meta name="robots" content="noindex, nofollow, noarchive,
    nosnippet">``.
  * ``racerwholesale.net`` — **NXDOMAIN**; the name isn't registered at all.
  * ``www.racerwholesale.com`` — CNAME to ``racerwholesale.com`` (same parked
    destination).
  * Wayback CDX shows the origin returning ``403 Forbidden`` (openresty) for
    every archived visit from 2023-04-06 through 2025-09-03 and the current
    Hostinger parked page from 2025-12-12 onward — so the storefront has not
    been reachable through normal crawling in at least three years. Older
    snapshots from the late-1990s era exist but are from a prior registrant
    and don't describe the modern safety-reseller business the backlog entry
    (Batch 2C #29, "Seats/harnesses") referenced.
  * WebSearch for "Racer Wholesale" safety reseller surfaces unrelated
    retailers (OG Racing, Racer Direct, Racing Seats USA, Racetech USA,
    Behrent's, Demon Tweeks, etc.) but nothing currently operating under the
    Racer Wholesale name.

**Platform:** unknown — there is no live storefront to fingerprint.
**JSON-LD shape:** unknown — no product page to inspect.
**Variant axis:** presumed size (seats/harnesses), unverified.
**Brand rule:** multi-brand safety reseller → pass through when JSON-LD
brand is populated; fall back to "Racer Wholesale" only when missing
(documented here so the next author has the decision; code path is
unreachable until discovery works).
**Robots / CF / TLS:** Hostinger parked origin; TLS handshake currently
broken on :443 and plain HTTP serves a parked page. If the domain is ever
resold and relaunched, re-run recon from scratch — any prior assumption
about platform is obsolete.

Tier rationale: defaults to ``FETCHER_TIER = "http"`` because the stored
decision is "plain HTTP works fine" once a storefront exists. No point
promoting to Tier 1/2 for a site that doesn't answer at all today; a future
relaunch on Cloudflare can bump the tier at that time.

**Caveats / what the next author should do:**

1. Re-run the probe commands in the module-level recon section above. If
   ``racerwholesale.com`` returns a real e-commerce HTML page (Shopify /
   BigCommerce / Magento / WooCommerce banner in the source or JSON-LD), fill
   in ``discover_product_urls`` against its sitemap and flesh out
   ``parse_product_page`` using the matching template (``grimmspeed.py`` for
   Shopify resell, ``ind.py`` for multi-brand pass-through, ``xph.py`` for
   BigCommerce without JSON-LD, etc.).
2. If a different host emerges (e.g. the business moved to
   ``theracerwholesale.com`` or a Shopify-hosted subdomain), update
   ``HOST_CANDIDATES`` below and the adapter-registry entry. None of the
   alternate TLDs I probed (``.net``, ``.us``, ``.co``, ``.biz``, ``.shop``,
   ``.store``; ``racer-wholesale.com``; ``theracerwholesale.com``) were
   registered as of recon.
3. Until either of the above, the adapter is a safe no-op: discovery yields
   nothing and parsing runs the shared JSON-LD / DOM fallback on any HTML
   that happens to arrive via the Chrome extension capture path, so if a
   user does manually scrape the parked page we still fail cleanly (no
   ``name`` → ``None``, logged as a parse miss rather than a crash).

The ``CRAWLER_RACERWHOLESALE_START_URLS`` env override is still honored —
if an operator knows a working storefront URL (e.g. a Wayback-archived
product page from the pre-2022 era, or a new host) they can feed it in
without editing this file — but the default behaviour is to stay out of
the way.
"""

import os
from typing import ClassVar, Iterator, List, Optional

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

# Candidate hosts documented in the backlog. Kept as a constant rather than
# wired into discovery because neither is currently a working storefront —
# see module docstring. Update this list (and the registry in
# ``adapters/__init__.py``) if the business relaunches on a different TLD.
HOST_CANDIDATES: List[str] = ["racerwholesale.com", "racerwholesale.net"]

# Canonical brand label applied only when JSON-LD brand and all heuristic
# fallbacks return nothing. Racer Wholesale is a reseller of third-party
# safety gear (Sparco, OMP, Racetech, Schroth, …); on a working PDP the
# manufacturer should come from JSON-LD brand and be passed through
# unchanged. This fallback exists so we never emit ``None`` downstream.
RACER_WHOLESALE_BRAND = "Racer Wholesale"


def _resolve_start_urls() -> List[str]:
    """
    Env override is the only way to produce URLs while the site is offline.
    ``CRAWLER_RACERWHOLESALE_START_URLS`` is a comma-separated list; returns
    ``[]`` otherwise so the runner skips the adapter cleanly.
    """
    raw = os.environ.get("CRAWLER_RACERWHOLESALE_START_URLS", "").strip()
    if not raw:
        return []
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Platform-agnostic image gather: ``og:image`` first, then any absolute /
    same-origin ``<img src>``. We don't know the future platform, so no
    theme-specific selectors — the ingest pipeline caps at 12 anyway.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or u in seen:
            return
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
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


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> str:
    """
    Pass JSON-LD brand through unchanged (Sparco / OMP / Racetech / Schroth
    / Cobra / etc.). Fall back to ``"Racer Wholesale"`` only when nothing
    else yielded a value, mirroring the multi-brand-reseller rule used by
    ``ind.py`` except that we keep a non-None fallback rather than dropping
    to ``None`` — the catalog would otherwise end up with unlabelled parts
    if a scraped page's JSON-LD is thin.
    """
    if part_manufacturer:
        brand = part_manufacturer.strip()
        if brand:
            return brand
    return RACER_WHOLESALE_BRAND


class RacerWholesaleAdapter(RetailerCrawlerAdapter):
    """
    Racer Wholesale adapter — **stub while the site is offline**.

    Discovery is env-override-only (``CRAWLER_RACERWHOLESALE_START_URLS``);
    the default yields nothing because the primary host serves a Hostinger
    parked page and the secondary host doesn't exist. Parsing is kept
    generic (JSON-LD first, OG / DOM fallback) so the adapter can still
    process HTML that arrives via the Chrome-extension capture path or the
    archive rescrape pipeline — no harm in having a parser ready for the
    day the storefront returns. See module docstring for the recon log and
    the revival checklist.
    """

    ADAPTER_NAME: ClassVar[str] = "racerwholesale"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield URLs from ``CRAWLER_RACERWHOLESALE_START_URLS`` (comma-
        separated) if set; otherwise yield nothing. No sitemap walk is
        attempted because the primary host returns a parked-domain page and
        the secondary host doesn't resolve — blindly fetching either would
        burn a request for no gain and could mask a future relaunch
        (a working sitemap would look identical to a parked HTML blob at
        the discovery layer).
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a product page. JSON-LD ``Product`` first (the normal path on
        Shopify / WooCommerce / BigCommerce / Magento — whichever platform
        the future storefront lands on), then OG / meta / DOM heuristics.
        Returns ``None`` when no usable name can be extracted — including
        the current reality of the Hostinger parked page, which has no
        ``<h1>`` product title and will correctly fail as a non-product
        page rather than pollute the DB with "Parked Domain" rows.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_dom_images(soup)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD Product — the path most modern e-com platforms expose.
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                part_number = normalize_part_number(payload.part_number) if payload.part_number else None

                # Multi-brand pass-through: prefer JSON-LD brand; heuristics
                # only when JSON-LD is empty. Fallback to "Racer Wholesale"
                # if everything else misses.
                part_manufacturer = payload.part_manufacturer
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_from_title(payload.name)
                if not part_manufacturer and payload.description:
                    part_manufacturer = part_manufacturer_from_description(
                        payload.description, product_name=payload.name
                    )
                if not part_manufacturer:
                    part_manufacturer = part_manufacturer_fallback_from_title(payload.name)
                part_manufacturer = _normalize_part_manufacturer(part_manufacturer)

                image_urls = payload.image_urls or (dom_images if dom_images else None)
                return ScrapedPayload(
                    name=payload.name,
                    product_url=url,
                    description=payload.description,
                    price_cents=price_cents,
                    part_manufacturer=part_manufacturer,
                    part_number=part_number,
                    image_urls=image_urls[:12] if image_urls else None,
                    gtin=payload.gtin,
                )

        # 2. DOM / og fallback: og:title → h1.
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
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer)

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description,
            price_cents=dom_price,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=dom_images[:12] if dom_images else None,
        )
