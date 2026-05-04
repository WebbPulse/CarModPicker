"""
StopTech crawler adapter — **stub, no independent storefront.**

StopTech was the track/HPDE sub-brand of Centric Parts (originally founded
in 1999 by James Walker Jr. as a balanced-brake-system kit maker, then
acquired by Centric Parts / Brakes Inc. in 2007). Centric Parts was in turn
rolled up into **Power Stop, LLC** in the 2020–2024 consolidation of the
aftermarket brake-hardware space. As of 2026-04-21 **no first-party
direct-to-consumer StopTech storefront exists on any candidate host** —
the brand is sold exclusively as a product line inside the corporate
parent's Magento 2 catalog (``centricparts.com``), which is a distinct
retailer with its own platform, URL shape, and brand-filter problem.

Live recon (2026-04-21):

* ``stoptech.com`` and ``www.stoptech.com`` — **HTTP/2 301** to
  ``https://www.centricparts.com/stop-tech``. The apex still resolves
  (``209.126.30.141``, nginx), but the SSL cert served is for
  ``3aa074a4dd.nxcli.net`` (a Nexcess/Liquid Web shared hosting
  placeholder) — a plain ``requests`` fetch fails with
  ``SSL: CERTIFICATE_VERIFY_FAILED`` at the TLS layer, before any
  redirect is followed. Every path we probed (``/``, ``/robots.txt``,
  ``/sitemap.xml``) returns the same 301 once SSL is bypassed; no
  product URLs exist on this host.
* ``stopech.com`` — **NXDOMAIN** (a plausible typo-catcher candidate
  from the backlog header; not serving).
* ``www.centricparts.com/stop-tech`` — the 301 target. **Magento 2**
  (Gamma/Brakes theme, ``categorypath-stop-tech`` body class), but it is
  a pure marketing / brand-landing page. The only outbound links are
  ``/partFinder/page/index`` (a vehicle-fitment lookup, not a product
  catalog), ``/wheretobuy`` (dealer locator), and ``/sponsorship-stoptech-racing``.
  No ``/product/`` or ``/stop-tech/<sku>`` URLs, no embedded product
  grid, no JSON-LD ``Product`` block, no StopTech-only sitemap
  fragment.
* ``www.centricparts.com/catalogsearch/result/?q=stoptech`` — returns
  mixed-brand rotors at URLs like ``/disc-brake-rotor-7375617``. These
  are real Centric Parts PDPs, but the URL shape is shared with every
  other Brakes-Inc / Centric / StopTech / PowerStop SKU in the catalog;
  there is no host-level way to constrain crawling to the StopTech
  sub-line. Treating centricparts.com as the scope would mean building
  a **centricparts** adapter (a different retailer in the schema), not
  a StopTech adapter — out of scope for this file, and not currently
  on the backlog.

Platform / discovery / JSON-LD: **N/A** — there is no first-party
StopTech storefront to probe. The recon above is the complete negative
result; no platform generator tag, no StopTech-scoped sitemap, no
schema.org ``Product`` addressable under a StopTech-branded host.

Robots: ``stoptech.com/robots.txt`` returns the 301 HTML body
(``The document has moved here``) rather than a real robots file;
shared ``_get_robots_parser`` treats a non-200/-404 on robots.txt as
"allow" so the polite runner wouldn't block — but the adapter yields
nothing, so it never gets that far. ``centricparts.com/robots.txt``
is a stock Magento allowlist (``Disallow: /index.php/``,
``/checkout/``, ``/customer/``, ``/catalog/``, query-string paths) —
relevant only if a future **centricparts** adapter is ever built.

Brand rule (documented here so the next author inherits the decision,
not because the stub enforces it): if / when a first-party StopTech
storefront returns, the canonical part_manufacturer string must be
stored as ``"StopTech"`` (single word, camelcase). The corporate
variants ``"StopTech by Centric Parts"``, ``"Centric Parts StopTech"``,
``"Power Stop StopTech"``, and plain ``"Stop Tech"`` (two words) are
all co-branding noise from retailer listings; they must collapse to
``"StopTech"`` to protect cross-retailer dedupe on
``(manufacturer, part_number)``. Title-heuristic defenses: StopTech
titles routinely lead with chassis or car-make prefixes
("E46 M3 BBK Front", "Cayman GT4 Front Kit", "Mustang GT500 Caliper
Conversion"), and the first-token fallback in ``parsing.py`` would
otherwise pick the car make as the manufacturer. The car-make /
chassis blocklist needed on this catalog, should a real adapter be
built:

    BMW, Porsche, Audi, Mercedes, Benz, Chevrolet, Chevy, Ford,
    Mustang, Dodge, Cadillac, Corvette, Camaro, Subaru, Nissan,
    GT-R, Toyota, Supra, Lexus, Honda, Civic, Acura, Evo, STI,
    E46, E90, E92, F80, F82, F87, F30, F10, G80, G82, G87, C5,
    C6, C7, C8, FD, FC, RX7, RX8, 370Z, 350Z, 86, BRZ, FRS.

Any of those → coerce to ``"StopTech"``.

Variant rule (per ``adapters/VARIANTS.md``): StopTech BBKs are
**per-chassis PDPs** — each PDP represents a specific caliper + rotor
+ line combination sized for one chassis family (e.g. "ST-40 Front
BBK for E46 M3"), and the purchasable variant axis is the **pad
compound** (Street Performance vs. Track / Race vs. Performance
Street) on some PDPs and the **caliper finish** (anodized red /
silver / black / raw) on others. If / when a live storefront
returns, the realistic posture mirrors the Phase 1 Shopify adapters
(``grimmspeed``, ``radium``, ``ie``) — **Option A territory**:
parent URL, first-variant-wins, take the top-level ``Product``
JSON-LD's ``sku`` / ``price`` / ``image`` and accept that the pad
compound and caliper finish variants collapse to whichever SKU the
site lists first. ``ProductGroup`` descent is only needed if the
returned platform turns out to be Magento 2 configurable (see
``texasspeed`` / ``mishimoto``) rather than plain Shopify.

Tier rationale: **Tier 0** ``"http"``. The legacy ``stoptech.com``
origin runs on nginx with no Cloudflare / JS-challenge markers — the
only failure mode observed is the SSL cert mismatch, which is a
static misconfig, not a bot-management feature. ``centricparts.com``
itself also served plain 200s to a stock ``curl`` request with no
challenge interstitial during recon. No TLS impersonation or headless
browser is anticipated. Revisit only if a future storefront is
observed with ``cf-mitigated: challenge`` or a 403 to plain
``requests``.

**Why this is a stub, not a working adapter.**

``ScrapedPayload`` requires a ``product_url``. There is nothing to
yield:

* ``stoptech.com`` / ``www.stoptech.com`` — every path 301s to
  ``www.centricparts.com/stop-tech``; the TLS layer fails with a cert
  mismatch (``3aa074a4dd.nxcli.net`` on a ``stoptech.com``-named
  request), so even the redirect can't be followed by a stock
  ``requests`` client without verification disabled. No sitemap, no
  product URLs.
* ``stopech.com`` — NXDOMAIN; DNS does not resolve at all.
* ``www.centricparts.com/stop-tech`` — the 301 target, but a pure
  marketing / brand-landing page. Zero product links on the page;
  only ``/partFinder``, ``/wheretobuy``, and a sponsorship sub-page.
  Emitting even one payload from this URL would collapse the entire
  StopTech catalog into a single row with wrong name / price / SKU /
  manufacturer for every downstream field.
* Pulling StopTech parts from ``centricparts.com``'s shared
  ``/disc-brake-rotor-NNNNNNN`` catalog belongs in a future
  **centricparts** adapter (separate retailer, separate brand-filter
  problem), not here — doing it in this file would conflate the
  StopTech brand with every other Brakes-Inc / Centric / PowerStop
  line hosted at the same URL shape.

Caveats — critical for the next author to know:

* **Host map.** If / when a StopTech storefront reappears, all three
  candidate hosts (``stoptech.com``, ``www.stoptech.com``,
  ``stopech.com``) should be registered in
  ``adapter_name_for_product_url()`` so archive-rescrape and
  extension-capture routes land here rather than the generic fallback.
  The current ``__init__.py`` does **not** register any of them — do
  not add them without a real parser, because the generic fallback's
  "do nothing sensible with a 301 HTML body" behavior is strictly
  better than a StopTech-aware stub that also does nothing (noisy
  without signal).
* **Do not merge with a future centricparts adapter.** ``centricparts.com``
  is a multi-brand Magento 2 storefront hosting Centric, StopTech,
  PowerStop, Brakes-Inc house labels, and some third-party lines. Its
  ingest path needs brand-field filtering against the JSON-LD
  ``brand.name`` to emit rows for each sub-line as the correct
  ``part_manufacturer``. A StopTech-only facade over a centricparts
  crawler will silently miss any PDPs whose JSON-LD brand field says
  ``"Centric"`` but whose description still references StopTech
  (catalog mis-tagging is common here). Build centricparts as its own
  adapter when the backlog picks it up, and let brand-coercion upgrade
  the StopTech rows into this retailer's slot only if a distinct
  "manufacturer=StopTech" filter is reliable at ingest time.
* **Env override ``CRAWLER_STOPTECH_START_URLS``** is honored for
  explicit testing (someone pointing the crawler at a URL *knows*
  what they're asking for) but the parser still returns ``None`` — a
  real discovery + parse implementation will land alongside a live
  first-party storefront, not before it.
* **Power Stop ownership / consolidation.** StopTech's corporate
  parent is Centric Parts → Brakes Inc. → Power Stop (in that order
  of rollups). A future first-party storefront is **more likely** to
  reappear at ``powerstop.com``'s catalog (as a StopTech sub-brand
  collection) than at ``stoptech.com``. If that happens, this adapter
  should become a facade over a **powerstop** adapter's brand=StopTech
  filter — not a resurrection of ``stoptech.com``.
* **Wilwood is the natural next step, not StopTech.** Backlog item
  #33 (Wilwood) has a live direct-to-consumer storefront and will
  ship as a real adapter; this file exists so that the backlog's
  "BBK direct" slot is closed with a documented negative result.
"""

import os
from typing import ClassVar, Iterator, List, Optional

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload

# Kept as documentation of the (currently dead) canonical host. Not used
# for any network call — the adapter yields nothing.
STOPTECH_BASE = "https://stoptech.com"


def _resolve_start_urls() -> List[str]:
    """Env override → list; otherwise empty (no live first-party storefront)."""
    raw = os.environ.get("CRAWLER_STOPTECH_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return []


class StoptechAdapter(RetailerCrawlerAdapter):
    """
    StopTech adapter — **stub, parse-only, non-yielding.**

    StopTech has no first-party direct-to-consumer storefront as of
    recon date (2026-04-21). ``stoptech.com`` 301s to
    ``www.centricparts.com/stop-tech`` (a marketing landing page with
    no product URLs), ``stopech.com`` is NXDOMAIN, and pulling StopTech
    rows out of ``centricparts.com``'s shared multi-brand catalog is a
    different retailer's job — see module docstring for the full
    recon and rationale.

    Discovery yields nothing. Env override
    ``CRAWLER_STOPTECH_START_URLS`` is honored for explicit testing;
    the parser will still return ``None`` for each one.
    """

    # Tier 0 — no Cloudflare / JS challenge observed on any candidate
    # host. The only failure mode was a static SSL cert mismatch on
    # stoptech.com; that's not a bot-management artifact and won't be
    # solved by upgrading fetcher tier. Left explicit so the choice is
    # documented on the class as well as the module docstring.
    ADAPTER_NAME: ClassVar[str] = "stoptech"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. There is no current StopTech first-party
        storefront, so this yields only whatever
        ``CRAWLER_STOPTECH_START_URLS`` contains (explicit caller
        opt-in) and nothing otherwise. The parser is a no-op until a
        real storefront returns and this file is replaced with a real
        implementation.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a StopTech product page.

        Returns ``None`` unconditionally — there is no live first-party
        StopTech storefront with product pages to parse. When / if a
        real first-party StopTech storefront reappears (most likely as
        a sub-brand collection on ``powerstop.com`` rather than a
        resurrected ``stoptech.com``), replace this body with a real
        parser and update the module docstring with the live platform,
        SKU shape, and variant strategy. Pulling StopTech items out of
        ``centricparts.com``'s shared multi-brand catalog belongs in a
        future **centricparts** adapter, not here — see the module
        docstring for why.
        """
        _ = html
        _ = url
        return None
