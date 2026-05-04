"""
Tein (www.tein.com) crawler adapter — Tier 0 (plain HTTP).

Tein Inc. is the Japanese coilover and damper house brand (FLEX Z, MONO SPORT,
SUPER RACING, EnduraPro, S.TECH, HIGH.TECH, EDFC, …). They are a
Subaru-of-Japan-style OEM-adjacent supplier to nearly every enthusiast chassis
— coilover-vertical-completion in the upper tier alongside KW, Ohlins, and
Fortune Auto. See ``adapters/RETAILER_BACKLOG.md`` Batch 2C #30.

Hosts / storefront split
------------------------
Tein runs **one global catalog** at ``www.tein.com``. The page metadata and
the homepage ``<meta name="description">`` both self-identify the site as
"TEIN USA", so despite the apex ``tein.com`` (and ``.jp`` parent) belonging
to the Japanese HQ, ``www.tein.com`` is the US-facing catalog. Candidate
hosts that do *not* exist:

- ``us.tein.com`` — NXDOMAIN (never existed, or retired long ago).
- ``tein-usa.com`` — NXDOMAIN.
- ``tein.com`` (apex) — no A record; connections time out.

Only ``www.tein.com`` resolves and responds. We accept the apex
``tein.com`` and the US-Japanese ``www.tein.co.jp`` cousin in the host
guard too, in case the extension ever captures a page from those origins
and the archive replay path needs a canonical adapter — every product URL
on Tein shares the same ``/products/<slug>.html`` shape across the brand's
sites.

Platform
--------
Static Apache — hand-written ``.html`` files under ``/products/<slug>.html``.
Server header literally reads ``Server: Apache`` with no CDN, no Cloudflare,
no WAF; both a browser UA and a ``python-requests/2.32`` UA return 200 on the
first try. No bot protection of any kind; **Tier 0 is correct**.

Catalog shape
-------------
Tein is **product-line-shaped, not per-SKU-shaped** — closely mirroring
Fortune Auto. Each series has its own page:

- ``flex_z.html``, ``flex_a.html``, ``flex_avs.html`` (FLEX family — street)
- ``mono_sport.html``, ``mono_racing.html`` (MONO family — track)
- ``super_drift.html``, ``super_racing.html``, ``n1.html``, ``ht.html`` (circuit)
- ``gr-n.html``, ``gravel.html``, ``hg.html``, ``4x4_sport.html`` (rally / off-road)
- ``s_tech.html``, ``high_tech.html``, ``oetech.html`` (lowering springs)
- ``endurapro.html``, ``endurapro_hc.html``, ``endurapro_basic.html`` (OE-shape dampers)
- ``edfc5.html``, ``edfc_active_pro.html`` (electronic damping-force controllers)
- ``sblink_rod.html``, ``lateral_rod.html``, ``upper_mount.html``,
  ``standard_spring.html``, ``racing_spring.html``, ``other_parts.html``
  (accessories / repair parts)

Each line is built-to-fitment — one series page represents thousands of
orderable SKUs keyed by chassis + year. The actual fitment look-up lives
behind the in-page ``/srch/us_search.php?maker=…&carmodel=…&item=…`` form;
those PHP responses would be the per-SKU layer if we ever needed it, but
they are form-driven and not discoverable from a flat URL list. Mirror
Fortune Auto / HRE / Wheels Boutique posture: one Part per product-line page,
``part_number`` left ``None``, ``price_cents`` left ``None``.

Variant strategy (per VARIANTS.md §5)
-------------------------------------
Known loss — **spring-rate and fitment-per-chassis axes are collapsed into
the series page**. MPN differs per (chassis × year × spring-rate), prices
differ too (the fitment-aware search form yields different MSRPs per
application), and fitment differs by definition because the entire axis
is "which car". All three triage questions in §5 are "yes", so this is
exactly the parent-only bias that doc calls out: the DB row captures
"FLEX Z coilover series" rather than "VSF74-D1SS1 for 2016 BRZ". Without
a site-side sitemap of per-SKU URLs or a scrapable per-SKU JSON feed,
lifting this adapter to one-row-per-variant would require synthesizing
URLs against the ``us_search.php`` form — Option C territory in VARIANTS.md,
and not justified until the rest of the per-SKU infrastructure (Variant
table, extension round-trip) is in place.

Parse
-----
No JSON-LD, no schema.org microdata, no OpenGraph meta tags — the HTML is
literally hand-written table-based layout from the mid-2010s. We read:

- **Name**: the ``<title>`` tag, stripped of the ``"TEIN.com:"`` prefix and
  the ``" - PRODUCTS"`` suffix so a page titled
  ``"TEIN.com: FLEX Z - PRODUCTS"`` stores as ``"FLEX Z"``. The product
  line name is then prefixed with ``"Tein "`` so it reads well in lists
  alongside other coilover brands (``"Tein FLEX Z"``).
- **Description**: the tagline inside the green header banner,
  ``<div class="box fourcorners">``. E.g. FLEX Z → "High-End Top-Quality
  Ride Height Adjustable Shock Absorber at Amazingly Low Price!". Falls
  back to ``<meta name="description">`` from the homepage template when
  that div is missing.
- **Image**: the hero ``<img>`` with filename matching ``*_products.(jpg|png)``
  — Tein's consistent naming convention for the main product photo
  (e.g. ``img/flz/flz_products.jpg``). Absolutized against
  ``/products/``.
- **part_number** / **price_cents**: always ``None``. Built-to-fitment,
  quote-or-search driven.
- **part_manufacturer**: constant ``"Tein"``. Every SKU on ``tein.com``
  is Tein's house brand; there is no multi-brand retail on this site.

Brand blocklist
---------------
Tein's product line names lead with the series (``FLEX Z``, ``MONO SPORT``,
``EDFC5``, ``RX1``) — never a car make — so the generic title heuristic
wouldn't trip up here anyway. But the site's dealer / application literature
mentions every Japanese sports car nameplate in running text (Honda, Toyota,
Subaru, Nissan, Mazda, Mitsubishi, Suzuki, Lexus, Infiniti, Acura, …),
so we hard-pin ``part_manufacturer = "Tein"`` and never read it from the
DOM. Belt-and-suspenders for the edge case where a future page template
change pushes Honda/Toyota/etc. into a would-be brand field.

Discovery
---------
No sitemap — ``/sitemap.xml`` returns a soft 404 ("The page cannot be
found."), ``/robots.txt`` allows the whole catalog except four CMS paths
(``/dojo/``, ``/tein_information/``, ``/TEIN_Information/``, ``/ti/``),
with explicit blocks only for NaverBot / Yeti. The authoritative list of
product lines lives in the homepage / ``/products/index.html`` nav, which
is hand-coded. Rather than scrape and re-parse the navigation on every
run, the adapter ships a **static list** of the ~30 product-line slugs
that appear in the index. That is brittle in exchange for predictability;
new product lines ship once every year or two and are added by hand.

Override ``CRAWLER_TEIN_START_URLS`` (comma-separated absolute URLs) for
ad-hoc runs against a subset or an unlisted series.

Robots
------
Plain ``User-Agent: *`` with disallows for CMS paths only. Product pages
are unrestricted. Crawl-delay is unset; the runner's default polite delay
applies.

Caveats
-------
- **Japanese HQ vs. US storefront**: ``www.tein.com`` titles its pages
  "TEIN.com" but serves the US catalog; ``www.tein.co.jp`` is the Japanese
  sister site with different product slugs and Japanese-language copy.
  We only claim ``tein.com`` / ``tein-usa.com`` in the host guard — the
  ``.co.jp`` storefront would need its own discovery list and is out of
  scope for this adapter.
- **No prices, no SKUs** — Tein enforces dealer pricing and fitment-aware
  configuration; both fields are always ``None``. Cross-retailer dedupe
  falls back to ``retailer + url``, same as Fortune Auto and HRE Wheels.
- **iso-8859-1 charset**: pages declare ``charset=iso-8859-1`` even though
  they contain plain ASCII. BeautifulSoup handles the decode; no special
  handling needed for the latin-1 taglines we've observed.
- **Static site → slug drift risk**: Tein rarely renames pages, but they
  occasionally re-org (``edfc_active.html`` → ``edfc_active_pro.html``).
  When the start-URL list goes stale, individual 404s just skip the page;
  the run keeps going.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import normalize_description_text

TEIN_BASE = "https://www.tein.com"
TEIN_PRODUCT_PREFIX = "/products/"

# Every SKU on the Tein catalog is Tein-branded. Hard-pin to sidestep the
# risk that a future template change surfaces a Japanese car make name (see
# module docstring: Honda/Toyota/Subaru/Nissan/Mazda/Mitsubishi/etc. all
# appear in fitment literature on this site) into a would-be brand field.
TEIN_BRAND = "Tein"

# "TEIN.com: " prefix and " - PRODUCTS" suffix appear on every product-line
# page. Stripping both yields the bare series name (e.g. ``FLEX Z``).
_TITLE_PREFIX_RE = re.compile(r"^\s*TEIN\.com\s*:\s*", re.IGNORECASE)
_TITLE_SUFFIX_RE = re.compile(r"\s*-\s*PRODUCTS\s*$", re.IGNORECASE)

# ``/products/<slug>.html`` — canonical product-line URL shape. Slug
# contains lowercase letters, digits, hyphens, and underscores (``flex_z``,
# ``gr-n``, ``4x4_sport``). The bare ``/products/index.html`` root and
# anything outside ``/products/`` is rejected.
_PRODUCT_PATH_RE = re.compile(r"^/products/([a-z0-9][a-z0-9_\-]*)\.html$", re.IGNORECASE)

# Any slug here is rejected — the index / reseller / landing pages under
# ``/products/`` that aren't individual product lines.
_NON_PRODUCT_SLUGS = frozenset({"index"})

# Hero image filename pattern on Tein pages — the consistent
# ``*_products.(jpg|png)`` naming convention for the main product photo.
_HERO_IMAGE_RE = re.compile(r"[a-z0-9_\-]+_products\.(?:jpg|jpeg|png)$", re.IGNORECASE)


# Tein publishes ~30 product lines under ``/products/<slug>.html``. The
# list comes from the homepage / products-index nav (which is hand-coded);
# re-scraping it every run costs a request per crawl for content that
# changes once every year or two. Baking it in keeps discovery predictable
# and lets us unit-test without live HTTP. A slug that 404s just skips —
# the run keeps going.
_PRODUCT_LINE_SLUGS: tuple[str, ...] = (
    # Lowering springs
    "s_tech",
    "high_tech",
    "oetech",
    # OE-shape dampers
    "endurapro",
    "endurapro_hc",
    "endurapro_basic",
    # Street coilovers
    "street_advance_basis_z",
    "street_advance_z4",
    "flex_z",
    "flex_a",
    "flex_avs",
    "rx1",
    "fs2",
    # Track / circuit coilovers
    "mono_sport",
    "mono_racing",
    "super_drift",
    "super_racing",
    "n1",
    "ht",
    # Rally / gravel
    "gr-n",
    "gr-n_frs",
    "gravel",
    "hg",
    # 4x4 / off-road
    "4x4_sport",
    # Custom / motorsport
    "specialized_damper",
    # EDFC electronic controllers
    "edfc5",
    "edfc_active_pro",
    # Accessories / fitment parts
    "sblink_rod",
    "lateral_rod",
    "motor_ext_kit",
    "flexible_controller",
    "upper_mount",
    "standard_spring",
    "racing_spring",
    "other_parts",
    "shockab_protector",
)

DEFAULT_START_URLS: tuple[str, ...] = tuple(
    f"{TEIN_BASE}{TEIN_PRODUCT_PREFIX}{slug}.html" for slug in _PRODUCT_LINE_SLUGS
)


def _is_tein_host(host: str) -> bool:
    """True if ``host`` is one of the Tein-accepted hostnames."""
    host = (host or "").lower()
    if not host:
        return False
    # Canonical live host.
    if host == "www.tein.com" or host == "tein.com":
        return True
    # NXDOMAIN today but historically referenced — accept so any archive
    # replay or extension capture with these origins still routes here.
    if host == "www.tein-usa.com" or host == "tein-usa.com":
        return True
    if host == "us.tein.com":
        return True
    return False


def _is_product_url(url: str) -> bool:
    """True if ``url`` is a Tein ``/products/<slug>.html`` page (not the index)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if not _is_tein_host(parsed.hostname or ""):
        return False
    match = _PRODUCT_PATH_RE.match(parsed.path or "")
    if not match:
        return False
    slug = match.group(1).lower()
    if slug in _NON_PRODUCT_SLUGS:
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_TEIN_START_URLS`` (comma-separated) if set, else ``None``."""
    raw = os.environ.get("CRAWLER_TEIN_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _clean_title(raw: str) -> str:
    """Strip ``"TEIN.com: "`` prefix and ``" - PRODUCTS"`` suffix from a page title."""
    cleaned = _TITLE_PREFIX_RE.sub("", raw).strip()
    cleaned = _TITLE_SUFFIX_RE.sub("", cleaned).strip()
    return cleaned or raw.strip()


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """Parse the product-line name from ``<title>``, prefixed with ``"Tein "``.

    Tein's own title text is the series string (``"FLEX Z"``, ``"MONO SPORT"``).
    Prefixing with the brand makes the catalog row read correctly in lists
    alongside other manufacturers' coilovers (``"Tein FLEX Z"`` vs. the bare
    ``"FLEX Z"`` which collides with unrelated products).
    """
    title_tag = soup.find("title")
    if not isinstance(title_tag, Tag):
        return None
    raw = title_tag.get_text(strip=True)
    if not raw:
        return None
    series = _clean_title(raw)
    if not series or len(series) < 2:
        return None
    # Already prefixed? ``TEIN.com: TEIN RX1 - PRODUCTS`` would collapse to
    # ``TEIN RX1``; don't double-prefix.
    if series.lower().startswith("tein "):
        return series[:5] + series[5:].strip()
    return f"Tein {series}"


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Pull the green banner tagline from ``<div class="box fourcorners">``.

    Falls back to ``<meta name="description">`` (the homepage template's
    default, which every page inherits unless they override it). Lines
    without a tagline div and without a meta description return ``None``.
    """
    box = soup.find("div", class_="box")
    if isinstance(box, Tag):
        classes = box.get("class") or []
        if isinstance(classes, list) and "fourcorners" in classes:
            text = box.get_text(separator=" ", strip=True)
            if text:
                normalized = normalize_description_text(text, max_len=2000)
                if normalized:
                    return normalized

    meta = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta, Tag):
        content = meta.get("content")
        if isinstance(content, str) and content.strip():
            return normalize_description_text(content, max_len=2000)
    return None


def _absolutize(url: str, page_url: str) -> Optional[str]:
    """Resolve a relative image path against the product-line page URL."""
    if not url or not url.strip():
        return None
    u = url.strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("//"):
        return "https:" + u
    try:
        parsed = urlparse(page_url)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.hostname:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if u.startswith("/"):
        return origin + u
    # Relative to the product-line page's directory (``/products/``).
    path = parsed.path or "/"
    directory = path.rsplit("/", 1)[0] + "/"
    return origin + directory + u


def _extract_images(soup: BeautifulSoup, page_url: str) -> List[str]:
    """Return a single-element list with the hero image, or ``[]``.

    Tein's template uses ``*_products.(jpg|png)`` for the primary product
    photo (``img/flz/flz_products.jpg``, ``mono_sport/mnsa_products.jpg``).
    Multiple pages also render a small ``edfc_active_products.jpg`` thumbnail
    inside a "Compatible Products" / "Also See" strip further down the page,
    so matching every ``_products.*`` filename yields sibling links. We only
    keep the **first** match in document order — Tein consistently places
    the main hero above the related-product strips.
    """
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        src = img.get("src")
        if not isinstance(src, str):
            continue
        if not _HERO_IMAGE_RE.search(src.rsplit("/", 1)[-1]):
            continue
        absolute = _absolutize(src, page_url)
        if not absolute:
            continue
        return [absolute]
    return []


class TeinAdapter(RetailerCrawlerAdapter):
    """
    Tein USA (www.tein.com) adapter — Tier 0.

    Discovery: static list of ~30 product-line slugs under ``/products/<slug>.html``
    (the site has no sitemap). ``CRAWLER_TEIN_START_URLS`` env var
    (comma-separated) overrides for ad-hoc runs.

    Parsing: DOM-only (no JSON-LD, no microdata, no OpenGraph). Name from
    ``<title>`` with the ``TEIN.com:`` / `` - PRODUCTS`` chrome stripped and
    the brand prefixed; description from the green banner tagline
    (``div.box.fourcorners``); hero image from ``*_products.(jpg|png)``
    filenames. ``part_number`` and ``price_cents`` are always ``None`` —
    Tein is built-to-fitment and the per-SKU pricing lives behind the
    ``us_search.php`` form rather than on a scrapable URL.
    ``part_manufacturer`` is the constant ``"Tein"``.
    """

    ADAPTER_NAME: ClassVar[str] = "tein"
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product-line URLs. Env override wins; otherwise the baked-in list."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in DEFAULT_START_URLS:
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse a Tein product-line page into a ``ScrapedPayload``.

        Returns ``None`` when the URL is not a product-line page or the
        ``<title>`` is missing / empty (soft 404 or a CMS page that slipped
        through discovery).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)
        images = _extract_images(soup, url)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=None,
            part_manufacturer=TEIN_BRAND,
            part_number=None,
            image_urls=images if images else None,
        )
