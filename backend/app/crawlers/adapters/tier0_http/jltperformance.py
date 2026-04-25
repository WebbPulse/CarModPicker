"""
JLT Performance crawler adapter — **stub, no live storefront.**

JLT Performance was founded by Jay Tucker in 2003 ("JLT" = "Jay's Lethal
Toy", his custom Mustang) and built a multi-platform catalog of cold-air
intakes, oil separators and throttle-body spacers spanning Mustang,
Challenger, Camaro, F-150, Corvette. By 2026 the original brand has been
split apart commercially and **no first-party direct-to-consumer
storefront survives on any of the candidate hosts**.

Live recon (2026-04-21):

* ``jltperformance.com`` — **NXDOMAIN** on both apex and ``www.``.
  Public search cache shows only ``ww5.jltperformance.com``, a classic
  Sedo / parked-domain placeholder ("cold air intakes, performance
  parts, performance exhaust, Volant air intakes"). Not a working
  storefront.
* ``jltruemeaning.com`` — **NXDOMAIN** on both apex and ``www.``. Never
  observed serving product inventory in the wider archive either.
* ``jltcoldairintake.com`` — **resolves and returns 200**, but is a
  WordPress marketing / affiliate site, not e-commerce. ``/sitemap.xml``
  → ``/sitemap_index.xml`` → ``/page-sitemap.xml`` lists exactly three
  URLs: ``/``, ``/privacy-policy/``, ``/contact/``. Every "Buy Now" CTA
  on the homepage redirects to an Amazon affiliate search URL
  (``https://www.amazon.com/s?k=JLT+<product>&tag=autopartsss-20``).
  No ``/product/`` or ``/products/`` path. No JSON-LD ``Product``, no
  WooCommerce shop page, no BigCommerce / Shopify / Magento markers.
* **Oil separator business has spun off** to ``jlosc.com``
  ("J&L Oil Separator Co. — formerly JLT Oil Separators"). That site
  does carry product pages but is branded J&L, not JLT, and should be
  modelled as its own adapter (``jlosc`` / J&L Oil Separator Co.) if
  and when it reaches the backlog — not here.
* **Intakes are now sold through retail partners** only: S&B Filters
  (``sbfilters.com/collections/jlt``), Lethal Performance, CJ Pony
  Parts, Late Model Restoration, Phastek, More Power Tuning, etc. Each
  of those is already (or will be) covered by its own retailer adapter;
  pulling the JLT sub-catalog from any one of them is that adapter's
  job, not this one's.

Platform / discovery / JSON-LD: **N/A** — there is no current JLT
Performance storefront to probe. The recon above is the complete
negative result; no platform generator tag, no sitemap with product
URLs, no schema.org ``Product``. A future author re-running this
investigation only needs to confirm the three hosts above (and any
newly observed jlt-branded successor) before concluding the same.

Robots: ``jltperformance.com`` / ``jltruemeaning.com`` advertise no
robots.txt (domain doesn't resolve). ``jltcoldairintake.com/robots.txt``
times out / is not served in a useful form; the shared robots parser
treats an unreachable robots.txt as "allow". None of this matters
because the adapter yields nothing.

Brand rule (documented here so the next author inherits the decision,
not because the stub enforces it): if and when a storefront reappears,
JLT's house brand should be stored as the canonical ``"JLT
Performance"``. The **car-make blocklist** for coerce-to-house-brand
is substantial on this catalog — JLT's products are almost always
titled by fitment ("2024-2025 Mustang GT Cold Air Intake", "F-150 5.0
Oil Separator", "Corvette C8 Z06 Cold Air Intake") so a first-token
heuristic routinely lands on the vehicle make. The full blocklist:

    Ford, Mustang, Shelby, GT350, GT500, Darkhorse,
    Chevrolet, Chevy, Camaro, Corvette,
    Dodge, Challenger, Charger, Durango, Jeep, Hellcat, Hemi, SRT,
    Cadillac, GMC.

Any of those → coerce to ``"JLT Performance"``. Third-party resell
items inside JLT's own catalog (the occasional S&B-labelled filter,
K&N drop-in, Volant housing) are rare but do happen and should pass
through when JSON-LD / OG brand carries a non-JLT manufacturer.

Variant rule (per ``adapters/VARIANTS.md``): JLT historically used
dropdown variants on the storefront for fitment axes
(driver-vs-passenger side on oil separators, tune-required-vs-no-tune
on intakes, oiled-vs-dry filter element, color finish). If a Shopify
storefront reappears this is **Option A territory — parent URL +
first-variant-wins**, same as most Shopify Phase-1 adapters. If
Magento / Hyva reappears, see ``texasspeed`` / ``mishimoto`` for the
``ProductGroup`` handling.

Tier rationale: **Tier 0** ``"http"``. Nothing observed on any
candidate host uses Cloudflare Bot Management, JS challenges, or a
TLS fingerprint block; the affiliate site at ``jltcoldairintake.com``
fetches plain. No fetcher upgrade will be needed when / if a real
storefront returns — revisit only if recon observes ``cf-mitigated:
challenge`` or a TLS-level 403.

**Why this is a stub, not a working adapter.**

``ScrapedPayload`` requires a ``product_url``. There is nothing to
yield:

* ``jltperformance.com`` / ``jltruemeaning.com`` — DNS does not
  resolve; any fetch raises before a byte of HTML comes back.
* ``jltcoldairintake.com`` — resolves, but has no product URLs. The
  three pages in its sitemap (home, privacy, contact) all describe
  the same product range via prose + Amazon-affiliate CTAs; emitting
  even one payload per page would collapse the catalog into a single
  row with wrong name / price / SKU / manufacturer for every field.
* Pulling JLT parts from retail-partner sites (S&B, LMR, CJ Pony, …)
  is handled by those retailers' own adapters when they exist — doing
  it here would double-emit the same inventory under two different
  retailer rows.

Caveats:

* **Host map.** If / when the JLT storefront returns, all three
  candidate hosts (``jltperformance.com``, ``jltruemeaning.com``,
  ``jltcoldairintake.com``) should be registered in
  ``adapter_name_for_product_url()`` so archive-rescrape and
  extension-capture routes land here rather than the generic fallback
  — even on the affiliate site, the ingest path is better served by
  a JLT-aware stub that refuses to parse marketing pages than by a
  generic parser that might hallucinate a payload.
* **Env override ``CRAWLER_JLTPERFORMANCE_START_URLS``** is honored
  for explicit testing (someone pointing the crawler at a URL *knows*
  what they're asking for) but the parser still returns ``None`` — a
  real discovery + parse implementation will land alongside a live
  storefront, not before it.
* **Do not register jlosc.com here.** J&L Oil Separator Co. is a
  distinct corporate entity post-split; its catalog, branding, and URL
  shape differ and it belongs in its own adapter (``jlosc``) if and
  when the backlog picks it up.
* **Do not merge with retail-partner adapters.** S&B, LMR, CJ Pony
  etc. have their own JSON-LD / sitemap shapes and brand-coercion
  rules; pulling JLT items out of those catalogs is that adapter's
  responsibility, not this file's.
"""

import os
from typing import ClassVar, Iterator, List, Optional

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload

# Kept as documentation of the (currently dead) canonical host. Not used
# for any network call — the adapter yields nothing.
JLTPERFORMANCE_BASE = "https://jltperformance.com"


def _resolve_start_urls() -> List[str]:
    """Env override → list; otherwise empty (no live storefront to discover)."""
    raw = os.environ.get("CRAWLER_JLTPERFORMANCE_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return []


class JLTPerformanceAdapter(RetailerCrawlerAdapter):
    """
    JLT Performance adapter — **stub, parse-only, non-yielding.**

    Registered so that any future JLT Performance URL captured via the
    Chrome extension or the archive rescrape pipeline maps to this
    adapter (and therefore this module's docstring) rather than the
    generic fallback. The parser itself returns ``None`` until a live
    first-party storefront exists to parse; see the module docstring
    for the full recon and rationale.

    Discovery yields nothing because the three candidate hosts
    (``jltperformance.com``, ``jltruemeaning.com``,
    ``jltcoldairintake.com``) are, respectively, NXDOMAIN, NXDOMAIN,
    and a three-page Amazon-affiliate marketing site with no product
    URLs. Env override ``CRAWLER_JLTPERFORMANCE_START_URLS`` is honored
    for explicit testing; the parser will still return ``None`` for
    each one.
    """

    # Tier 0 — nothing observed on any candidate host needs TLS
    # impersonation or a headless browser. Left explicit so the choice
    # is documented on the class rather than only in the docstring.
    ADAPTER_NAME: ClassVar[str] = "jltperformance"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. There is no current JLT Performance
        storefront, so this yields only whatever
        ``CRAWLER_JLTPERFORMANCE_START_URLS`` contains (explicit caller
        opt-in) and nothing otherwise. The parser is a no-op until a
        real storefront returns and this file is replaced with a real
        implementation.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a JLT Performance product page.

        Returns ``None`` unconditionally — there is no live storefront
        with product pages to parse. When / if a real first-party JLT
        storefront reappears, replace this body with a real parser
        (likely JSON-LD ``Product`` first, Shopify / WooCommerce /
        BigCommerce fallbacks per the platform observed during recon)
        and update the module docstring with the live platform, SKU
        shape and variant strategy.
        """
        _ = html
        _ = url
        return None
