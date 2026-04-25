"""
Road Race Engineering (RRE — roadraceengineering.com) crawler adapter —
**stub, pending data-model change.**

RRE is a long-established (1990s) Evo / DSM / 4G Eclipse specialist that
sells a mix of house-brand hardware ("RRE EVO X Downpipe", "RRE
Lightweight Crank Pulley") and resold third-party parts (AEM, Cobb,
Turbosmart, K&N, …). Unlike every other retailer in the adapter tree,
**RRE has no e-commerce storefront** — the site's catalog is a collection
of long WordPress pages, each enumerating *many* distinct products with
inline PayPal "Add to Cart" forms. The 1-payload-per-URL contract that
``ScrapedPayload`` enforces cannot honestly represent this shape, so the
adapter is registered as a parse-only stub until the variant / multi-SKU
data model lands (VARIANTS.md §6, Options C or D).

Live recon (2026-04-21):

* ``roadraceengineering.com`` (apex) and ``www.roadraceengineering.com``
  both HTTP-302 the root to ``/blog`` — the only live surface on this
  host is the WordPress install at ``/blog/``.
* ``/mall/`` and ``/Merchant2/`` — checked because those are the classic
  Miva / Merchant2 storefront paths RRE ran in the early 2000s — both
  return 404. There is no current storefront subpath.
* ``/robots.txt`` returns a 1995-era FrontPage placeholder HTML page
  (``<meta name="GENERATOR" content="Microsoft FrontPage 4.0">``), not
  a robots.txt. ``/sitemap.xml`` returns 404. The shared robots parser
  treats an unparseable robots.txt as "allow", so this does not block
  fetches, but it's worth noting: RRE advertises no crawl policy at all.
* ``/blog/robots.txt`` returns 404; ``/blog/wp-sitemap.xml`` returns a
  valid WordPress sitemap index with **~16 page URLs** and a posts list
  (news posts, not products). The page URLs are the per-chassis parts
  catalogs (``/blog/2008-2015-evo-x-rre-parts-catalog/evo-x-intake-upgrades/``,
  ``…/evo-x-exhaust-parts/``, ``…/rre-evo-x-engine-upgrades/``, …).
* Platform: **WordPress 5.6.17** (``<meta name="generator" content="WordPress 5.6.17">``)
  on PHP/Apache, theme ``modularity-lite``. Commerce is bolted on via
  the ``paypal-wp-button-manager`` plugin (``[paypal_wp_button_manager id=NNNN]``
  shortcodes) — each product on a catalog page has a PayPal form POSTing
  to ``paypal.com/cgi-bin/webscr`` with no per-product URL on the RRE
  side. The only per-item URLs are WordPress image-attachment wrappers
  (``…/evo-x-intake-upgrades/aem-28-20392/``), which are just a single
  ``<img>`` in a blog-post template — not a product page.
* **No JSON-LD, no OG:product, no schema.org markup** of any kind on the
  catalog pages. The shared ``extract_json_ld_product`` finds nothing.

**Why this is a stub, not a working adapter.**

Each catalog page ships **5–15 distinct SKUs inline**. Typical shape (from
``/blog/2008-2015-evo-x-rre-parts-catalog/evo-x-intake-upgrades/``):

    <h2>AEM Panel Filter</h2>
    [paypal_wp_button_manager id=6857]
    <form target="paypal" action="…/cgi-bin/webscr" method="post">…</form>
    <p>Price of $45 includes standard ground shipping…</p>
    <ul><li>Drop-in Design</li>…</ul>
    <p>The reusable AEM Dryflow air filter 28-20392…</p>
    <hr />
    <h2>AEM Cold Air Intake For The EVO X  21-678C (2008-2015)</h2>
    [paypal_wp_button_manager id=6686]
    <form target="paypal" …>…</form>
    <p>Price of $304.99 includes Standard Ground shipping…</p>
    …

``ScrapedPayload`` represents one Part per ``product_url``. Emitting one
payload per catalog URL would collapse 5–15 different parts (AEM panel
filter, AEM CAI, K&N, ETS, RRE-branded) into a single row — factually
wrong for every field except (maybe) the page title. Emitting one
payload per ``<h2>``/``<form>`` block requires the 1:N change sketched
as Options C and D in ``adapters/VARIANTS.md``: the runner contract
needs to accept a list of payloads per URL, each payload needs a
stable synthetic URL (probably ``<page>#<paypal_button_id>``) for
dedupe, and the ingest path needs to stop treating ``product_url`` as
the unique key.

Until that work lands this adapter is **parse-only and non-yielding**:

* ``discover_product_urls()`` yields nothing. There are no per-product
  URLs to crawl, and yielding catalog URLs would produce wrong data.
  Env override ``CRAWLER_ROADRACEENGINEERING_START_URLS`` is still
  honored — someone explicitly pointing the crawler at a URL *knows*
  what they're asking for — but with the expectation that the parser
  will return ``None`` (see below).
* ``parse_product_page()`` returns ``None`` unconditionally. This
  keeps the adapter registered so that (a) the Chrome extension's
  ``/crawled-pages/scrape`` endpoint and the archive rescrape path can
  both map RRE URLs to this adapter via
  ``adapter_name_for_product_url()`` rather than the generic fallback,
  and (b) when someone lands here to implement Options C/D, the file
  and its live-recon notes are already in the tree.

**Brand rule** (documented here so the next author inherits the decision,
not so the stub enforces it): RRE's canonical self-reference on the site
is ``"RRE"`` in product names (``"RRE EVO X Downpipe"``, ``"RRE
Lightweight Crank Pulley"``, ``"RRE Gear and Apparel"``) and
``"Road Race Engineering"`` in the site header / menu (``<h4><a …>Road
/// Race Engineering</a></h4>``, ``"Contact Road Race Engineering"``).
When the multi-SKU path is implemented, **pass JSON-LD / OG brand
through** when present (reserved for resold third-party AEM / Cobb /
Turbosmart items — though given the lack of schema.org markup on this
site, this branch may never fire); otherwise, coerce house-brand items
to the canonical long-form ``"Road Race Engineering"`` (matches how
other long-name specialists like ``"Delicious Tuning"`` and
``"Verus Engineering"`` are stored — the storefront-displayed short
code goes in the SKU, the full brand name goes in the manufacturer
row).

**Variant strategy** (per VARIANTS.md): this adapter cannot use Option
A (parent-only) because the "parent" page is actually many distinct
products, not one product with variants. It needs Option C (synthetic
per-block URLs) or Option D (first-class variant model) before it can
usefully emit any payloads. Noted here so the next author doesn't
retry Option A and re-discover the problem.

**Tier rationale.** Plain HTTP works first-try (Apache returns 200 for
every product-bearing URL with the crawler UA, no Cloudflare, no JS
challenge, no TLS fingerprint block). ``FETCHER_TIER`` stays at the
default ``"http"`` — if and when the stub becomes a real adapter, no
fetcher upgrade is needed.

**Caveats:**

* **Stack age.** WordPress 5.6.17 was released 2020-12; WordPress 5.6 is
  an EOL major. The theme (``modularity-lite``), plugin set
  (``paypal-wp-button-manager``, ``events-calendar``, ``instagram-feed``,
  ``social-buttons-pack``), and the PayPal-form integration are frozen
  in time. The site is effectively write-once from 2010-ish with price
  edits trickled in. Any future RRE re-platform (onto Shopify, for
  instance — a path several of their peers have taken) would obsolete
  every selector this file documents.
* **No schema.org, no OG:product, no ``price:amount`` meta.** When a
  future author implements Options C/D, the parser will have to derive
  name / price / SKU from pure DOM structure: h2-as-name, "Price of
  $X.XX" regex in the following ``<p>``, PayPal ``item_number`` hidden
  input as SKU, first following ``<img>`` as hero image, ``<hr />`` as
  the block separator. There is no machine-readable fallback to verify
  against.
* **PayPal ``item_number`` as the stable identifier.** The PayPal form
  embeds ``<input type="hidden" name="item_number" value="…">`` and a
  shortcode ``[paypal_wp_button_manager id=NNNN]``; either can serve
  as the per-block SKU / synthetic-URL anchor when Options C/D land.
  Prefer ``item_number`` because it's the merchant-facing code and
  more likely to cross-match RRE's internal records than the plugin's
  numeric post ID.
* **Attachment URLs are not product URLs.** Links like
  ``…/evo-x-intake-upgrades/aem-28-20392/`` resolve to WordPress *image*
  attachment pages (``wp/v2/media/6858``), not product pages — they
  contain only a single image and a nav template. Do not accept them as
  candidate product URLs when implementing discovery.
"""

import os
from typing import ClassVar, Iterator, List, Optional

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload

ROADRACEENGINEERING_BASE = "http://roadraceengineering.com"


def _resolve_start_urls() -> List[str]:
    """Env override → list; otherwise empty (no discovery yet)."""
    raw = os.environ.get("CRAWLER_ROADRACEENGINEERING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return []


class RoadRaceEngineeringAdapter(RetailerCrawlerAdapter):
    """
    Road Race Engineering adapter — **stub, parse-only, non-yielding.**

    Registered so RRE URLs captured via the Chrome extension or the
    archive rescrape pipeline map to this adapter (and therefore this
    docstring) rather than the generic fallback; the parser itself
    returns ``None`` until the multi-SKU data-model change in
    ``adapters/VARIANTS.md`` §6 (Option C / D) lands and this file is
    replaced with a real implementation.

    Discovery yields nothing because RRE has no per-product URLs:
    the catalog is a set of long WordPress pages each carrying 5–15
    distinct SKUs inline via PayPal ``[paypal_wp_button_manager]``
    shortcodes. Yielding those catalog URLs would produce one
    misleading payload per page (all fields truncated / wrong for every
    product beyond the first one parsed). See the module docstring for
    the full recon and design rationale.

    Env override ``CRAWLER_ROADRACEENGINEERING_START_URLS`` is honored for
    explicit testing; the parser will still return ``None`` for each one
    until Option C/D lands.
    """

    # Default Tier 0 — plain HTTP is enough (no Cloudflare, no JS
    # challenge). Left explicit so the choice is documented on the class.
    ADAPTER_NAME: ClassVar[str] = "roadraceengineering"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. RRE has no per-product URL shape, so this
        returns whatever ``CRAWLER_ROADRACEENGINEERING_START_URLS``
        contains (explicit caller opt-in) and nothing otherwise. The
        parser is a no-op until VARIANTS.md Option C/D is implemented.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Road Race Engineering catalog page.

        Returns ``None`` unconditionally — the site's WordPress + PayPal
        catalog shape packs many distinct SKUs onto one URL, which the
        1-payload-per-URL ``ScrapedPayload`` contract cannot honestly
        represent. When the variant / multi-SKU model from
        ``adapters/VARIANTS.md`` §6 lands, replace this body with a real
        parser that walks ``<h2>`` ... ``<hr />`` blocks, reads the
        following ``Price of $X.XX`` text, pulls SKU from the PayPal
        ``item_number`` hidden input, and emits one payload per block
        with a synthetic URL of the form
        ``<page>#<paypal_item_number>``.
        """
        _ = html
        _ = url
        return None
