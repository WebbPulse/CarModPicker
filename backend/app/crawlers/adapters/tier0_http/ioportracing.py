"""
I/O Port Racing Supplies (ioportracing.com) crawler adapter.

Platform: **PinnacleCart** (a legacy PHP 5.6 shopping cart — the footer proudly
links to pinnaclecart.com, and the server banner is ``Server: Apache`` +
``X-Powered-By: PHP/5.6.40``). Not Shopify, BigCommerce, Magento, or
WooCommerce. Apex ``ioportracing.com`` **301s to** ``www.ioportracing.com`` —
that canonical host is what the whole site (including the single sitemap
entry) uses. The sibling candidate host ``ioport.com`` does **not** resolve
(curl returns no output / connection refused); we do **not** attempt it.

Product URLs follow the shape ``/<category-slug>/<product-slug>/`` — a
two-segment pretty-URL where both segments are the category's and product's
human-readable slugs (e.g. ``/schroth-latchnlink-harnesses/latchnlink-ii-harness-schroth/``,
``/bell-sa2020-composite-helmets/br8-forced-air-helmet-bell/``,
``/cobra-fia-rated-seats/sebring-pro-ultralite-seat-cobra/``). Every observed
product title ends with a trailing ``, <Brand>`` — that convention is the
single most reliable brand signal this site emits.

JSON-LD shape: **none.** There is no ``application/ld+json`` script, no
schema.org microdata (``itemscope`` / ``itemtype``), no OpenGraph
``product:*`` properties — nothing structured on the PDP at all. The only
machine-readable signals are the standard ``<title>``, ``<h1>``,
``<meta name="description">``, and ``<meta property="og:image">``. Everything
else — price, description body, brand, gallery image — is extracted from
PinnacleCart's class-prefixed DOM (``.product-title``, ``.product-description``,
``.product-image``, ``.price-amount``, ``.product-bread-crumbs``). Closest
existing analog in the repo is ``modernmusclextreme.py`` (another legacy
non-JSON-LD storefront) — this adapter mirrors its "DOM-scoped, guard against
related-product leakage, take title heuristic last" pattern.

Brand rule (**multi-brand reseller → pass-through**): I/O Port is a West-Coast
safety / motorsport equipment *reseller*. Their own manufacturer-filter
dropdown on every catalog page enumerates the third-party lines they carry —
Allstar, Apex Wheels, ATL Fuel Cells, Autopower, Bell Helmets, ChatterBox,
Cobra Seats, Cool Shirt, CTEK, ESS Fire Systems, Fuel Safe, Hama, HANS, HJC,
Holley, Joes, Kirkey, Longacre, MagLock, Molecule, MyLaps (AMB), NecksGen,
OMP, Paragon Pro, Pyrotect, RaceCom, Racetech, Recaro, Red Line Lubricants,
Safecraft, **Schroth**, SFE Radios, Simpson, Sytec Switches, Wilwood Brakes —
alongside their own ``I/O Port Racing Supplies`` house line. We therefore
**pass brand through unchanged** whenever we can extract one, matching the
``ind`` / ``ogracing`` / ``modernmusclextreme`` playbook rather than the
house-brand ADRO / 034 playbook.

Brand extraction cascade, in order:

1. **Trailing ``", <Brand>"`` suffix on the H1.** Every PDP we sampled uses
   the ``"<Product Name>, <Brand>"`` format (``"BR8 Forced Air Helmet, Bell"``,
   ``"Sebring Pro Ultralite Seat, Cobra"``, ``"Latch'n'Link II Harness,
   Schroth"``). This is the primary signal. We match against a known-brand
   allowlist to guard against titles where the last comma-separated token is
   a size/color rather than a brand.
2. **Breadcrumb second-to-last segment** — the breadcrumb is
   ``Home > For The Car > Harnesses > Schroth Competition Harnesses > Schroth Latch'n'Link Harnesses``;
   the brand name is usually a prefix of one of those crumbs. Used only when
   the title-suffix match fails (often because the title lacks a comma).
3. **Shared ``part_manufacturer_from_title`` heuristic** — the usual fallback
   for "BrandName ProductWords…" titles.
4. **``part_manufacturer_from_description`` / ``part_manufacturer_fallback_from_title``**
   — last-ditch pattern matching.

Car-make tokens the title heuristic may accidentally land on (BMW / Porsche /
Toyota / Honda / Nissan / …) are dropped so the catalog doesn't grow a phantom
``"BMW"`` manufacturer from titles like ``"BMW E46 Seat Bracket, Sparco"``.
When every step fails we fall back to ``"I/O Port Racing Supplies"`` — the
honest answer for unbranded house items (fire extinguisher mounts, trailer
accessories, custom brackets) rather than leaving the field empty.

Variant rule (per ``adapters/VARIANTS.md`` §5): safety gear is the canonical
case where variants matter. Every PDP with a configurator emits one or more
``<select>`` dropdowns for **size axes** — helmet shell size (S / M / L / XL),
shoe size, seat shell size, harness adjuster type (``5-point with Adjuster``
/ ``6-point V-style``), side-pull direction, shoulder strap width (``2"`` /
``3"``), certification rating (SFI 16.1 / 16.5 / 16.6, FIA 8853-2016). These
are **add-on options on the same URL** — the site has no ``?variant=<id>``
deep-link shape — so there is no per-variant URL to crawl. Per the
cross-adapter pattern documented in VARIANTS.md §3 we take the **base
price** (the ``.price-amount`` value shown before any option add-ons) and
**document the constraint**. The stored ``name`` / ``price_cents`` /
``image_urls`` describe the base SKU; a user shopping a specific size must
click through to ioportracing.com. Until first-class variant support lands
(Option D in VARIANTS.md), this is the documented rule for this site.

There is no SKU / part-number field on any observed PDP. PinnacleCart has a
``product_id`` in its URL query strings but never surfaces it on the page
body, and the site never prints a visible ``SKU:`` / ``Part #:`` label. We
therefore leave ``part_number=None`` and let cross-retailer dedupe fall back
to ``retailer + url`` (same graceful degradation as the ``radium`` adapter,
which has the same "no real SKU on the page" problem for different reasons).

Discovery: ``/sitemap.xml`` exists and returns 200, but it lists **only**
static pages (home, login, signup, cart, testimonials, site_map) — zero
product URLs. (The file's comment even names itself ``"Free Online Sitemap
Generator www.xml-sitemaps.com"`` — it was built from the public pages, not
wired to the catalog.) The HTML ``/site-map.html`` fares no better: it
enumerates the category tree down to leaf categories but stops there. The
only way to find product URLs is to **walk the category listings with
``?p=catalog&mode=catalog&pg=N&pagesize=54``** pagination and scrape the
``class="catalog-product"`` anchor blocks. Because the full catalog is in
the thousands of items across dozens of leaf categories, we do **not** walk
the whole tree at crawl time — we seed discovery from a curated list of
**brand-scoped leaf categories** (``/schroth/``, ``/bell-helmets/``,
``/hans/``, ``/cobra-seats-41/``, ``/omp/`` …) and paginate each until no new
URL appears. Set ``CRAWLER_IOPORTRACING_START_URLS`` (comma-separated product
URLs) to override discovery entirely for ad-hoc runs or smoke tests. When
the walk returns nothing — network error, layout change — the adapter falls
back to a small hard-coded ``DEFAULT_START_URLS`` picking three distinct
brands so the first crawl still exercises the multi-brand pass-through path.

Tier rationale: Plain HTTP works end-to-end — ``/robots.txt`` returns 200
(``User-agent: * Allow: /``), category pages and PDPs both render full HTML
on first curl, and there is no Cloudflare / bot-management fingerprint gate
in front of the Apache origin. ``FETCHER_TIER`` stays at the default
``"http"``. Promote to Tier 1 only if the origin ever starts TLS-fingerprint
gating (unlikely on a plain Apache / PHP 5.6 install).

Robots: ``https://www.ioportracing.com/robots.txt`` is ``User-agent: *
Allow: /`` with a single ``Sitemap:`` directive — fully permissive. No
Crawl-delay declared; the runner's configured ``--delay`` applies.

Caveats:

- **No SKU.** ``part_number`` is always ``None``. Cross-retailer dedupe for
  I/O Port parts works on ``retailer + url``. Same as ``radium``.
- **Variant silently collapsed.** Single stored row per URL even when the
  PDP lists N purchasable size / certification / strap-width permutations.
  Take any "call us for pricing on size X" complaint as a variant-axis
  escalation signal (VARIANTS.md §7).
- **Price may read as ``Call for price``** on back-ordered items; parsing
  returns ``None`` in that case and the runner stores a price-less part.
- **Apex host quirk.** ``ioportracing.com`` 301s to ``www.ioportracing.com``;
  the adapter emits URLs on the www canonical so we never spend a request
  on the redirect hop. ``ioport.com`` does not resolve — not supported.
- **Double-slash in built URLs.** PinnacleCart templates emit absolute URLs
  like ``https://www.ioportracing.com//images/products/br8.jpg`` (note the
  double slash after the host) — browsers and ``requests`` both tolerate
  these, but our image-normalization helper collapses them to a single
  slash so stored URLs are tidy.
- **``og:image`` duplicates the product-image anchor.** We de-dup across
  both sources rather than concatenate them.
- **Related-product cards** appear lower on the PDP as ``<img src="images/products/thumbs/<slug>.jpg">``
  — we explicitly skip any image path containing ``/thumbs/`` in the image
  sweep so those don't leak into the gallery.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urljoin

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
    meta_content,
    normalize_description_text,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

IOPORTRACING_BASE = "https://www.ioportracing.com"

# Curated seed list of **brand-scoped leaf categories** — walking these with
# paged ``?p=catalog&mode=catalog&pg=N&pagesize=54`` pagination yields a
# representative cross-section of the safety catalog without asking the
# runner to walk all ~40 brand directories + every vehicle-specific
# harness category every time. Add or remove slugs to expand coverage.
# (Exact paths confirmed by recon — each returns HTTP 200 and renders
# ``class="catalog-product"`` grid cells on page 1.)
_SEED_CATEGORY_SLUGS: tuple[str, ...] = (
    "schroth",
    "schroth-sfi-16.1-competition-harnesses",
    "schroth-sfi-16.5-competition-harnesses",
    "schroth-sfi-16.6-competition-harnesses",
    "schroth-latchnlink-harnesses",
    "bell-helmets",
    "bell-sa2020-composite-helmets",
    "bell-driving-suits",
    "bell-driving-gloves",
    "hans",
    "hans-head-and-neck-restraints",
    "necksgen",
    "cobra-seats-41",
    "cobra-fia-rated-seats",
    "recaro-seats-24",
    "racetech-seats-23",
    "kirkey-seats",
    "omp",
    "sparco",
    "simpson",
    "pyrotect",
    "autopower",
    "hjc-helmets",
    "molecule-performance-products",
    "safecraft-fire-systems",
    "ess-fire-systems-13",
    "atl-fuel-cells-7",
    "fuel-safe",
    "wilwood-brakes",
    "longacre",
)

# Hard-coded fallback when the category walk returns nothing (network blip,
# layout change) and no env override is set. Three distinct brands so the
# first crawl exercises the multi-brand pass-through path end-to-end rather
# than a single manufacturer's title shape.
DEFAULT_START_URLS = (
    "https://www.ioportracing.com/schroth-latchnlink-harnesses/latchnlink-ii-harness-schroth/",
    "https://www.ioportracing.com/bell-sa2020-composite-helmets/br8-forced-air-helmet-bell/",
    "https://www.ioportracing.com/cobra-fia-rated-seats/sebring-pro-ultralite-seat-cobra/",
)

# Safety cap on pagination per category — the largest observed (Bell helmet
# replacement parts) is ~59 pages at ``pagesize=54``; set the cap comfortably
# above that so we don't silently truncate a high-volume category. Each walk
# respects the runner's jittered delay between requests.
_MAX_PAGES_PER_CATEGORY = 80

# PinnacleCart emits product grid cells as ``<div class="catalog-product">``
# with a ``<a href="<abs-url>">`` linking to the PDP. We match the href on
# the two-segment product URL pattern ``/<cat>/<product>/`` where both
# segments are non-empty slug characters; this guards against the paginator
# / sort-by / view-mode links that share the same scope.
_PRODUCT_URL_RE = re.compile(
    r"^https?://(?:www\.)?ioportracing\.com/+([a-z0-9][a-z0-9\-\./]*?)/+([a-z0-9][a-z0-9\-\./]*?)/?$",
    re.IGNORECASE,
)

# Category-only URLs are single-segment (``/<cat-slug>/``) on this site. The
# paginator emits URLs that bring back a ``?p=catalog...`` query string; the
# product regex above rejects those implicitly because the path doesn't
# survive the ``/`` anchor check. We also never let discovery yield a URL
# on the sitemap's own static pages, which always route through
# ``/index.php?p=...``.

# Brand allowlist for the title-suffix heuristic. Order doesn't matter (we
# do case-insensitive exact match on the trailing ``, <X>`` token). These are
# the brands that appear in the site's own manufacturer-filter dropdown; we
# extend it with a few common spellings and multi-word compound names.
_KNOWN_BRAND_SUFFIXES: frozenset[str] = frozenset(
    s.lower()
    for s in (
        "Allstar",
        "Apex Wheels",
        "ATL Fuel Cells",
        "ATL",
        "Autopower",
        "Bell",
        "Bell Helmets",
        "ChatterBox",
        "ChatterBox Intercoms",
        "Cobra",
        "Cobra Seats",
        "Cool Shirt",
        "CTEK",
        "ESS",
        "ESS Fire Systems",
        "Fuel Safe",
        "Hama",
        "HANS",
        "HJC",
        "HJC Helmets",
        "Holley",
        "I/O Port",
        "I/O Port Racing Supplies",
        "Joes",
        "Kirkey",
        "Kirkey Seats",
        "Longacre",
        "MagLock",
        "Molecule",
        "MyLaps",
        "NecksGen",
        "OMP",
        "Paragon Pro",
        "Pyrotect",
        "RaceCom",
        "Racetech",
        "Racetech Seats",
        "Recaro",
        "Recaro Seats",
        "Red Line",
        "Red Line Lubricants",
        "Safecraft",
        "Schroth",
        "SFE",
        "SFE Radios",
        "Simpson",
        "Sparco",
        "Stilo",
        "Sytec",
        "Sytec Switches",
        "Wilwood",
        "Wilwood Brakes",
        "Alpinestars",
        "AIM",
        "3M",
    )
)

# Canonical brand labels (title-case consumers expect) keyed by the lowercased
# token the heuristics may return. Used after extraction so stored values
# read consistently — e.g. ``"HANS"`` stays uppercase, ``"I/O Port"`` keeps
# its slashes, ``"McLaren"``-style caps are preserved — rather than whatever
# raw case happened to win.
_BRAND_CANONICAL: dict[str, str] = {
    "allstar": "Allstar",
    "apex wheels": "Apex Wheels",
    "atl": "ATL",
    "atl fuel cells": "ATL Fuel Cells",
    "autopower": "Autopower",
    "bell": "Bell",
    "bell helmets": "Bell Helmets",
    "chatterbox": "ChatterBox",
    "chatterbox intercoms": "ChatterBox Intercoms",
    "cobra": "Cobra",
    "cobra seats": "Cobra Seats",
    "cool shirt": "Cool Shirt",
    "ctek": "CTEK",
    "ess": "ESS",
    "ess fire systems": "ESS Fire Systems",
    "fuel safe": "Fuel Safe",
    "hama": "Hama",
    "hans": "HANS",
    "hjc": "HJC",
    "hjc helmets": "HJC Helmets",
    "holley": "Holley",
    "i/o port": "I/O Port Racing Supplies",
    "i/o port racing supplies": "I/O Port Racing Supplies",
    "joes": "Joes",
    "kirkey": "Kirkey",
    "kirkey seats": "Kirkey Seats",
    "longacre": "Longacre",
    "maglock": "MagLock",
    "molecule": "Molecule",
    "mylaps": "MyLaps",
    "necksgen": "NecksGen",
    "omp": "OMP",
    "paragon pro": "Paragon Pro",
    "pyrotect": "Pyrotect",
    "racecom": "RaceCom",
    "racetech": "Racetech",
    "racetech seats": "Racetech Seats",
    "recaro": "Recaro",
    "recaro seats": "Recaro Seats",
    "red line": "Red Line",
    "red line lubricants": "Red Line Lubricants",
    "safecraft": "Safecraft",
    "schroth": "Schroth",
    "sfe": "SFE",
    "sfe radios": "SFE Radios",
    "simpson": "Simpson",
    "sparco": "Sparco",
    "stilo": "Stilo",
    "sytec": "Sytec",
    "sytec switches": "Sytec Switches",
    "wilwood": "Wilwood",
    "wilwood brakes": "Wilwood Brakes",
    "alpinestars": "Alpinestars",
    "aim": "AIM",
    "3m": "3M",
}

# Car-make tokens the title heuristic sometimes picks when a product title
# leads with a vehicle ("BMW E46 Harness Bar, Schroth"). I/O Port is a
# multi-brand reseller; unlike the house-brand adapters we do NOT coerce to a
# house brand here — we drop the token and let downstream heuristics try.
# The trailing-comma-suffix path usually saves us because most titles still
# end with ``, <Brand>``.
_TITLE_CAR_MAKES: frozenset[str] = frozenset(
    {
        "bmw",
        "porsche",
        "toyota",
        "honda",
        "lexus",
        "subaru",
        "nissan",
        "audi",
        "mercedes",
        "mercedes-benz",
        "ford",
        "chevrolet",
        "chevy",
        "tesla",
        "hyundai",
        "kia",
        "genesis",
        "mini",
        "vw",
        "volkswagen",
        "mazda",
        "mitsubishi",
        "scion",
        "dodge",
        "chrysler",
        "jeep",
        "acura",
        "infiniti",
    }
)

# Tokens sometimes picked by the first-token title heuristic that are not
# manufacturer names.
_BRAND_REJECT_TOKENS: frozenset[str] = frozenset({"the", "new", "oem", "racing"})

# Default brand when nothing else works — the honest answer for unbranded
# house items (custom brackets, trailer accessories, shop rags) rather than
# leaving the manufacturer empty.
_DEFAULT_HOUSE_BRAND = "I/O Port Racing Supplies"


def _resolve_start_urls() -> List[str]:
    """Env override wins; else walk the seed categories; else fall back."""
    raw = os.environ.get("CRAWLER_IOPORTRACING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_category_walk()
    return urls if urls else list(DEFAULT_START_URLS)


def _is_product_url(href: str) -> bool:
    """True if ``href`` matches the canonical ``/<cat>/<prod>/`` product URL
    shape on ``www.ioportracing.com``. Rejects category pages, paginator
    links, sort-by / view-mode permutations, and ``/index.php?...`` static
    pages implicitly via the two-segment path anchor."""
    if not href or "?" in href:
        return False
    return bool(_PRODUCT_URL_RE.match(href.strip()))


def _extract_product_urls_from_category(html_text: str) -> List[str]:
    """Return ordered, deduplicated product URLs from a PinnacleCart catalog
    grid page. Scopes to ``<div class="catalog-product">`` cells so the
    breadcrumb / global-nav anchors that share the category-URL shape don't
    leak in."""
    soup = BeautifulSoup(html_text, "html.parser")
    out: List[str] = []
    seen: set[str] = set()
    for cell in soup.find_all("div", class_=re.compile(r"\bcatalog-product\b", re.IGNORECASE)):
        if not isinstance(cell, Tag):
            continue
        # Title anchor inside each cell; we take the first matching href
        # rather than iterate every <a> (image + title both point at the
        # same PDP so dedup by URL anyway, but this avoids wasted work).
        for a in cell.find_all("a", href=True):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if not isinstance(href, str):
                continue
            href = href.strip()
            if not href:
                continue
            # Normalize protocol-relative and relative hrefs against the base.
            absolute = urljoin(IOPORTRACING_BASE + "/", href)
            # Collapse any `//` in the path (PinnacleCart templates emit
            # these; the product URL regex expects a clean path).
            absolute = re.sub(r"(?<!:)//+", "/", absolute)
            if not _is_product_url(absolute):
                continue
            key = absolute.rstrip("/")
            if key in seen:
                continue
            seen.add(key)
            out.append(absolute)
            break
    return out


def _discover_product_urls_via_category_walk() -> List[str]:
    """Walk each seed category with ``?p=catalog&mode=catalog&pg=N&pagesize=54``
    pagination, collecting every product URL. Stops each category as soon as
    a page yields zero *new* URLs (natural end-of-list signal — the paginator
    is a ``Last`` link so we don't know page-count up front). Delays between
    fetches inherit the runner's jittered ``DEFAULT_REQUEST_DELAY_SEC``."""
    seen: set[str] = set()
    out: List[str] = []
    fetched = 0
    for slug in _SEED_CATEGORY_SLUGS:
        base = f"{IOPORTRACING_BASE}/{slug}/"
        for pg in range(1, _MAX_PAGES_PER_CATEGORY + 1):
            if fetched > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            fetched += 1
            cat_url = f"{base}?p=catalog&mode=catalog&pg={pg}&pagesize=54"
            try:
                html_text = fetch_page(cat_url, timeout=20)
            except Exception:
                break
            urls = _extract_product_urls_from_category(html_text)
            added = 0
            for u in urls:
                key = u.rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                out.append(u)
                added += 1
            # End of list when a page adds no new URLs — PinnacleCart
            # happily serves empty grids past the last real page.
            if added == 0:
                break
    return out


def _normalize_image_url(raw: str) -> str:
    """Collapse the ``//`` that PinnacleCart templates emit after the host;
    resolve relative paths against the base; upgrade http to https."""
    u = raw.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        u = "https://" + u[len("http://") :]
    if u.startswith("/"):
        u = IOPORTRACING_BASE + u
    elif not u.startswith("http"):
        # Page-relative (``images/products/xyz.jpg``) — resolve to base.
        u = urljoin(IOPORTRACING_BASE + "/", u.lstrip("./"))
    # Collapse repeated slashes in the path (but not after scheme).
    scheme, sep, rest = u.partition("://")
    if sep:
        rest = re.sub(r"/+", "/", rest)
        u = f"{scheme}://{rest}"
    return u


def _is_related_thumb(url: str) -> bool:
    """Related-product thumbnails live at ``/images/products/thumbs/<slug>.jpg``
    and appear on every PDP below the main gallery. They are not part of the
    product being viewed, so we skip them. The sibling ``/preview/`` path
    is a lower-resolution copy of the main image (used as the ``<img>`` src
    inside the MagicThumb anchor) — also excluded so the gallery doesn't
    double-list the cover shot at two resolutions."""
    low = url.lower()
    return "/images/products/thumbs/" in low or "/images/products/preview/" in low or "/content/cache/skins/" in low


def _extract_product_images(soup: BeautifulSoup, og_image: Optional[str]) -> List[str]:
    """Return the main product image (and any same-PDP gallery shots),
    deduped and capped at 12. PinnacleCart's PDPs have one MagicThumb anchor
    at ``.product-image a`` pointing at the full-size image; og:image is a
    duplicate of that. Related-product thumbs are skipped via
    ``_is_related_thumb``."""
    seen: set[str] = set()
    out: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(out) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http"):
            return
        if _is_related_thumb(u):
            return
        if u in seen:
            return
        seen.add(u)
        out.append(u)

    # Primary: ``<a>`` href inside ``<div class="product-image">`` points at
    # the full-resolution image.
    for scope in soup.find_all("div", class_=re.compile(r"\bproduct-image\b", re.IGNORECASE)):
        if not isinstance(scope, Tag):
            continue
        for a in scope.find_all("a", href=True):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if isinstance(href, str) and href.strip():
                add(href.strip())
        # Inline ``<img src>`` fallback (preview size) if the anchor missed.
        for img in scope.find_all("img", src=True):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str) and src.strip():
                add(src.strip())
        break  # only the first main product-image block

    # og:image is a duplicate but worth checking when the DOM scope came up dry.
    if og_image and og_image.strip():
        add(og_image.strip())

    return out[:12]


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """The product blurb lives in ``<div class="product-description
    product-page-block">``. PinnacleCart wraps it with a ``<div
    class="product-page-block-header">Description</div>`` sibling we need to
    skip — we take the ``product-page-block-content`` child instead. Falls
    back to ``<meta name="description">`` / ``<meta property="og:description">``."""
    for block in soup.find_all("div", class_=re.compile(r"\bproduct-description\b", re.IGNORECASE)):
        if not isinstance(block, Tag):
            continue
        content = block.find("div", class_=re.compile(r"\bproduct-page-block-content\b", re.IGNORECASE))
        target: Optional[Tag] = content if isinstance(content, Tag) else block
        text = target.get_text(separator=" ", strip=True)
        if text and len(text) > 30:
            # Strip the literal leading "Description" that PinnacleCart
            # sometimes inlines into the content block on certain templates.
            cleaned = re.sub(r"^\s*Description\s*", "", text, flags=re.IGNORECASE)
            return normalize_description_text(cleaned, max_len=2000)

    og_desc = soup.find("meta", property="og:description")
    if isinstance(og_desc, Tag):
        d = meta_content(og_desc)
        if d and d.strip():
            return normalize_description_text(d, max_len=2000) or d.strip()[:2000]
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        d = meta_content(meta_desc)
        if d and d.strip():
            return normalize_description_text(d, max_len=2000) or d.strip()[:2000]
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """PinnacleCart renders the active price in ``<span id="product_price"
    class="price-amount">$249.95</span>`` inside the ``<div
    class="product-price">`` block. On "call for price" items the span is
    either empty or reads ``"Call for price"`` — we return ``None`` in both
    cases so the runner stores a price-less part rather than a zero."""
    scope = soup.find("div", class_=re.compile(r"\bproduct-price\b", re.IGNORECASE))
    if isinstance(scope, Tag):
        amt = scope.find(class_=re.compile(r"\bprice-amount\b", re.IGNORECASE))
        if isinstance(amt, Tag):
            text = amt.get_text(strip=True)
            if text and "call" not in text.lower():
                cents = parse_price_cents(text)
                if cents is not None and cents > 0:
                    return cents
    # Page-wide fallback (picks up DOM meta tags if present).
    dom = extract_dom_price(soup)
    return dom if (dom is not None and dom > 0) else None


def _brand_from_title_suffix(name: str) -> Optional[str]:
    """If the title is ``"<Product Name>, <Brand>"`` and ``<Brand>`` matches
    the known-brand allowlist (case-insensitive), return it in canonical
    form. Otherwise ``None`` — the title may have a trailing color / size /
    chassis-code rather than a brand."""
    if not name or "," not in name:
        return None
    tail = name.rsplit(",", 1)[1].strip()
    if not tail:
        return None
    key = tail.lower()
    if key in _KNOWN_BRAND_SUFFIXES:
        return _BRAND_CANONICAL.get(key, tail)
    # Two-word brand may appear suffixed with punctuation (e.g. "Bell.")
    stripped = re.sub(r"[.!?;:]+$", "", key).strip()
    if stripped in _KNOWN_BRAND_SUFFIXES:
        return _BRAND_CANONICAL.get(stripped, tail)
    return None


def _brand_from_breadcrumb(soup: BeautifulSoup) -> Optional[str]:
    """Scan the ``class="product-bread-crumbs"`` block for a known brand
    token. The breadcrumb usually reads ``Home > For The Car > Harnesses >
    Schroth Competition Harnesses > …`` — the second-to-last crumb often
    contains the brand as a prefix."""
    bc = soup.find(class_=re.compile(r"\bproduct-bread-crumbs\b", re.IGNORECASE))
    if not isinstance(bc, Tag):
        return None
    text = bc.get_text(separator=" ", strip=True)
    if not text:
        return None
    # Score each known brand by whether the breadcrumb mentions it as a
    # standalone word (case-insensitive). Prefer longer matches first so
    # "ESS Fire Systems" wins over plain "ESS".
    low = text.lower()
    for key in sorted(_KNOWN_BRAND_SUFFIXES, key=len, reverse=True):
        if not key:
            continue
        pattern = r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, low):
            return _BRAND_CANONICAL.get(key, key.title())
    return None


def _normalize_part_manufacturer(
    part_manufacturer: Optional[str],
) -> Optional[str]:
    """Trim whitespace; drop car-make / reject tokens; canonicalize casing
    against ``_BRAND_CANONICAL`` when we recognize the key. Returns ``None``
    rather than a coerced fallback so callers can try the next step in the
    cascade."""
    if not part_manufacturer:
        return None
    brand = part_manufacturer.strip().rstrip(",.;:")
    if not brand:
        return None
    low = brand.lower()
    if low in _TITLE_CAR_MAKES:
        return None
    if low in _BRAND_REJECT_TOKENS:
        return None
    if low in _BRAND_CANONICAL:
        return _BRAND_CANONICAL[low]
    return brand


def _strip_brand_suffix_from_name(name: str, brand: Optional[str]) -> str:
    """When the title ends with ``, <Brand>`` and we've extracted ``brand``,
    drop the suffix so the stored name reads cleanly ("Latch'n'Link II
    Harness" rather than "Latch'n'Link II Harness, Schroth"). Keeps the
    original name unchanged when the suffix doesn't match ``brand`` (some
    products have a trailing size / color instead)."""
    if not brand or not name or "," not in name:
        return name
    head, _, tail = name.rpartition(",")
    tail_clean = re.sub(r"[.!?;:]+$", "", tail.strip()).strip()
    if tail_clean.lower() == brand.lower() or tail_clean.lower() in _KNOWN_BRAND_SUFFIXES:
        return head.strip()
    return name


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """Prefer ``<div class="product-title">`` (the visible H1-like heading
    PinnacleCart emits), then ``<h1>``, then ``<meta property="og:title">``,
    then ``<title>`` with the site-name suffix stripped. Falls back to
    ``None`` when no usable name is found."""
    title_el = soup.find(class_=re.compile(r"\bproduct-title\b", re.IGNORECASE))
    if isinstance(title_el, Tag):
        text = title_el.get_text(strip=True)
        if text:
            return text
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    og = soup.find("meta", property="og:title")
    if isinstance(og, Tag):
        text = meta_content(og)
        if text and text.strip():
            return text.strip()
    title = soup.find("title")
    if isinstance(title, Tag):
        text = title.get_text(strip=True)
        if text:
            # Strip the site-name suffix (" at I/O Port Racing Supplies").
            return re.sub(r"\s+at\s+I/O\s+Port\s+Racing\s+Supplies\s*$", "", text, flags=re.IGNORECASE).strip()
    return None


class IOPortRacingAdapter(RetailerCrawlerAdapter):
    """I/O Port Racing Supplies adapter. Discovery: paginated walk over a
    curated list of brand-scoped leaf categories (sitemap.xml hosts no
    products). Parsing: DOM-only — there is no JSON-LD or schema.org
    microdata on this PinnacleCart storefront. Brand is extracted via a
    cascade (title-suffix allowlist → breadcrumb → shared heuristics →
    house brand as a last resort) and **passed through** to preserve the
    real third-party manufacturer on every reseller SKU. ``part_number`` is
    always ``None`` (no SKU printed on the PDP). Variant axes (size,
    certification, strap width) are silently collapsed to the base SKU;
    see VARIANTS.md §5.
    """

    # Plain HTTP is enough; Apache / PHP 5.6 origin, no Cloudflare gate.
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs — from ``CRAWLER_IOPORTRACING_START_URLS`` when
        set, otherwise a paginated walk of ``_SEED_CATEGORY_SLUGS``. A
        jittered delay is applied between category fetches inside
        ``_discover_product_urls_via_category_walk``."""
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse an I/O Port Racing PDP. DOM-only — no JSON-LD / microdata.
        Returns ``None`` when no usable name can be extracted (e.g. the URL
        no longer resolves to a product page)."""
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        # Brand cascade.
        part_manufacturer: Optional[str] = _brand_from_title_suffix(name)
        if not part_manufacturer:
            part_manufacturer = _brand_from_breadcrumb(soup)
        description: Optional[str] = _extract_description(soup)
        if not part_manufacturer:
            heuristic = part_manufacturer_from_title(name)
            part_manufacturer = _normalize_part_manufacturer(heuristic)
        if not part_manufacturer and description:
            heuristic = part_manufacturer_from_description(description, product_name=name)
            part_manufacturer = _normalize_part_manufacturer(heuristic)
        if not part_manufacturer:
            heuristic = part_manufacturer_fallback_from_title(name)
            part_manufacturer = _normalize_part_manufacturer(heuristic)
        if not part_manufacturer:
            # Last resort — honest house-brand answer for unbranded items
            # rather than leaving the manufacturer empty.
            part_manufacturer = _DEFAULT_HOUSE_BRAND

        # Strip the ", <Brand>" trailing suffix from the stored name so
        # it reads cleanly in build lists.
        clean_name = _strip_brand_suffix_from_name(name, part_manufacturer)

        # Price (optional).
        price_cents = _extract_price_cents(soup)

        # Images (og:image duplicates the product-image anchor; merge both
        # through the shared add() dedupe).
        og_img_tag = soup.find("meta", property="og:image")
        og_image = meta_content(og_img_tag) if isinstance(og_img_tag, Tag) else None
        image_urls = _extract_product_images(soup, og_image)

        return ScrapedPayload(
            name=clean_name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            # No SKU is surfaced on PDPs — leave part_number unset so
            # cross-retailer dedupe falls back to retailer+url. Matches
            # radium's intentional behavior.
            part_number=None,
            image_urls=image_urls if image_urls else None,
        )
