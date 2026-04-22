"""
EcuTek (ecutek.com) crawler adapter.

EcuTek Technologies Ltd is a Uxbridge, UK-based ECU-tuning-software house
whose catalog is best known for the **ProECU** reprogramming suites, the
**RaceROM** feature pack, the **ECU Connect / PhoneFlash** Bluetooth
dongle, and the wired **ProECU USB Programming Kit**. The product range
covers Subaru (classic WRX/STI, BRZ/86 Gen 1 + Gen 2, WRX DIT/Levorg),
Nissan (GT-R R35, 370Z/G37, Juke/Pulsar DIG-T, Q50/Q60 VR30, Z VR30),
Toyota (Supra A90/A91, Yaris GR / Corolla GR), Mazda (MX-5 NC + ND,
DISI 2.3T), Mitsubishi (Evo 5-9/X, L200/Shogun/Pajero), Ford (EcoBoost),
BMW (F-series N55/S55, F/G-series B58/B48, S58), VAG (EA855.3 2.5T), and
Honda (Civic Type R FN2).

**Host:** ``www.ecutek.com`` (canonical; bare ``ecutek.com`` 301s to www
on Apache/2.4). ``ecutektuning.com`` returns 405 on ``/`` and is not this
site — it's a third-party dealer-adjacent domain; only ``ecutek.com`` is
covered here. ``hennesseymotorsports.com``-style host-map expansion is
not needed.

**Platform:** pure **WordPress** (``generator: WordPress 6.4.8``) with
the **All in One SEO (AIOSEO)** plugin handling structured data
(``generator: All in One SEO (AIOSEO) 4.9.1.1``). **No WooCommerce, no
e-commerce plugin of any kind.** EcuTek sells software licenses and the
programming hardware **exclusively through authorized Master Tuner
dealers** (see ``/find-a-tuner/``); every "product" page on
``ecutek.com`` is a marketing/spec post describing what the dealer will
install. This mirrors ``injectordynamics`` and ``hennessey`` — the three
form a cohort of manufacturer-brochure WP sites with no prices and no
canonical per-page SKU.

**Discovery.** ``sitemap.xml`` is the AIOSEO-generated root index with
four children: ``post-sitemap.xml``, ``page-sitemap.xml``,
``category-sitemap.xml``, ``post_tag-sitemap.xml``. There is **no
product-sitemap** — product-like pages are WordPress *posts*, all
tagged with the **Products** category (``taxonomy=category, id=3,
slug="products"``). Discovery walks the WP REST API
(``/wp-json/wp/v2/posts?categories=3&per_page=100``) to enumerate them
— currently ~40 posts covering every tuning suite, the programming
kits, PhoneFlash, RaceROM, and the ECU-Connect dashboards. Two
post-category IDs are *not* walked:

* ``20`` / ``ecutek-dealer`` and ``21`` / ``tuning-suites`` — child
  sub-categories of Dealer. Their posts are already covered under
  "Products" (``3``). Avoids double-scraping via duplicate post IDs.
* All vehicle makes (``bmw``, ``toyota``) and the blog are content, not
  products.

Why REST not sitemap: the sitemap mixes CMS pages
(``about-us``, ``privacy``, ``find-a-tuner``) with product posts under
the same flat namespace, and there is no URL-shape selector (every URL
is ``/{slug}/`` at the site root — no ``/products/`` prefix, no
``/vehicles/`` prefix). The REST API lets us filter by category without
having to hand-maintain a slug allow-list.

Override with ``CRAWLER_ECUTEK_START_URLS`` (comma-separated) for
targeted smoke tests; fixed fallback list kicks in when the REST API
is unreachable.

**JSON-LD shape.** AIOSEO emits a top-level ``@graph`` per page mixing
``BreadcrumbList``, ``Organization``, ``Person`` (author),
``WebPage``, ``WebSite``, and — on product-category posts — a
``BlogPosting``. **No ``Product`` block, no ``Offers``, no ``price``,
no ``sku``, no ``gtin``.** The shared ``extract_json_ld_product``
therefore returns nothing; we parse the ``@graph`` ourselves and pull:

* ``name`` from ``BlogPosting.name`` (or ``WebPage.name`` fallback),
  stripping the trailing ``" - EcuTek"`` site suffix that AIOSEO glues
  on every title.
* ``description`` from ``WebPage.description``
  (``BlogPosting.description`` is empty on this site).
* Hero image from ``BlogPosting.image.url`` — typically a
  ``/content/uploads/<date>/<slug>-featured-image*.jpg`` banner.

**Variant rule (VARIANTS.md §5 — a close cousin of
``injectordynamics`` / ``hennessey``).** Each EcuTek PDP is a *family
of dealer-installable options* (e.g. ProECU Subaru Tuning Suites covers
multiple regions + engine generations with distinct license SKUs behind
the dealer wall). There is no picker on the page, no hasVariant block,
no per-option URL — the variant axis lives entirely on the dealer side.
The adapter stores the family name and leaves ``part_number=None``, so
cross-retailer dedupe falls back to ``(retailer, product_url)`` per the
``radium`` / ``injectordynamics`` / ``hennessey`` precedent.

**Tier rationale.** Tier 0 (``http``) — plain Apache/2.4, no Cloudflare,
no TLS fingerprint gate, 200 on every endpoint with the default crawler
UA. If the origin later adopts a CF challenge the adapter should be
promoted to ``tls`` first (mirrors ``hennessey``).

**Robots.** ``/robots.txt`` is permissive: ``User-agent: *`` with
``Disallow: /wp-admin/`` (+ ``/app_themes/``, ``/cmsmessages/``,
``/home/``) and a public sitemap reference. Every product URL is
allowed. No ``Crawl-delay`` declared.

**Brand rule (VARIANTS.md cross-reference).** House brand is always
forced to the canonical string ``"EcuTek"``. JSON-LD ``Organization.name``
on this site is ``"EcuTek Technologies Ltd"``; we shorten that to match
what KTuner / COBB / Hondata adapters already emit for peer brands in
the ECU-tuning vertical. The shared title heuristic would otherwise
pick up car makes (``Subaru``, ``BMW``, ``Toyota``, ``Nissan``, ``Ford``,
``Mazda``, ``Mitsubishi``, ``Honda``, ``VW``) — every EcuTek product
title leads with the target vehicle (``"Toyota Supra A90 & A91 …"``,
``"Subaru BRZ Gen 2/Toyota GR-86"``) — so the heuristic is intentionally
**not** used here; the house brand is the correct default for every
page.

**Platform firsts:** none — this is the third WordPress-marketing-brochure
adapter (after ``injectordynamics`` and ``hennessey``) and the first that
uses the **AIOSEO** plugin for JSON-LD. The WP REST API discovery
pattern first introduced by ``injectordynamics`` is reused with a
category-filter twist (``?categories=3``).

**Caveats — critical to remember during smoke-test:**

* **Dealer-only, brochure site.** ``price_cents`` and ``part_number``
  are ``None`` on every payload by design; the public pages carry
  neither. Cross-retailer dedupe falls back to ``(retailer, url)``,
  same as ``radium`` / ``injectordynamics`` / ``hennessey``.
* **No ``Product`` JSON-LD.** Every field is derived from
  ``BlogPosting`` / ``WebPage`` nodes inside AIOSEO's ``@graph``.
* **Uploads live at ``/content/uploads/``, not ``/wp-content/uploads/``.**
  This site has a customized uploads path; the image-sweep regex below
  matches ``/content/uploads/`` explicitly.
* **Some Products-category posts are not product pages.** The
  ``regulatory`` (EU Declaration of Conformity) post, OEM-services
  marketing pages, and the ``come-and-work-for-us`` careers post all
  appear under ``categories=3`` historically; the deny list below
  filters them out at discovery.
* **Trailing-slash inconsistency.** The WP REST API returns some
  ``link`` values without a trailing slash (``/nissan-z``,
  ``/vag-ea-855-3``). We normalize by appending ``/`` before emitting
  the URL so de-dupe sees a single canonical form.
* **OG image is the site logo, not the product.** AIOSEO sets
  ``og:image`` to the EcuTek company logo on every PDP we sampled.
  Don't trust ``og:image`` here — use ``BlogPosting.image`` from the
  JSON-LD instead, then sweep ``.main-info`` for body images.
"""

import html as html_mod
import json
import os
import re
from typing import Any, Iterator, List, Optional, cast

import requests
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import DEFAULT_USER_AGENT, ScrapedPayload
from app.crawlers.parsing import normalize_description_text

ECUTEK_BASE = "https://www.ecutek.com"
# WP REST API posts endpoint. Category 3 = "Products" (the parent taxonomy
# that every catalog page is tagged with). Covers tuning suites, hardware
# kits, PhoneFlash, RaceROM, ECU Connect dashboards — ~40 posts.
WP_POSTS_URL = f"{ECUTEK_BASE}/wp-json/wp/v2/posts"
WP_PRODUCTS_CATEGORY_ID = 3

# Canonical house-brand name. JSON-LD ``Organization.name`` is
# ``"EcuTek Technologies Ltd"``; we shorten so rows align with the peer
# ECU-tuning-house-brand adapters (hondata → ``"Hondata"``, ktuner →
# ``"KTuner"``, cobbtuning emits ``"COBB Tuning"``).
ECUTEK_BRAND = "EcuTek"

# AIOSEO appends ``" - EcuTek"`` to every ``<title>`` and JSON-LD
# ``name``; strip before returning the product name.
_TITLE_SUFFIX_RE = re.compile(r"\s*[\|\-–]\s*EcuTek\s*$", re.IGNORECASE)

# Slugs on the Products-category post list that are *not* actual
# product PDPs and must be filtered out at discovery. WordPress's loose
# taxonomy means regulatory/OEM/careers copy ends up tagged with the
# same category as the tuning suites; each listed here was verified
# during recon (2026-04-21) to be a non-product page.
_NON_PRODUCT_SLUGS = frozenset(
    {
        # EU Declaration of Conformity — regulatory, not a product.
        "regulatory",
        # OEM / enterprise services — B2B copy, not a catalog SKU.
        "oem-services-for-vehicle-manufacturers-importers",
        "oem-services-for-hard-parts-manufacturers",
        # Careers page that somehow got tagged Products.
        "come-and-work-for-us",
        # Dealer onboarding / admin-facing content.
        "apply-to-become-an-ecutek-dealer",
        "tuner-support",
        "tuning-with-ecutek",
        "reverse-engineer",
        "phone-flash-tuner-set-up",
        "proecu-programming-kit-supported-ecus",
        "ecu-connect-feature-compatibility",
        "what-are-racerom-special-features",
        "ecuconnect-download",
        # Injector fitment catalog — no price / SKU, duplicate of what
        # dealer hardware pages cover.
        "injectors",
    }
)

# Minimum count of posts we accept from the REST API before trusting
# the feed. If the API is broken (plugin conflict, auth wall, 500) the
# list will be tiny — fall back to the hard-coded defaults rather than
# emitting a crippled URL set. Same pattern as ``injectordynamics``.
_MIN_REST_POSTS = 4

# Verified-live fallback URL list. Used when the REST API is
# unreachable and no env override is set. Covers the three shape
# classes: a hardware kit, a feature-branded product, a platform-tuning
# suite.
DEFAULT_START_URLS = [
    f"{ECUTEK_BASE}/proecu-usb-programming-kit/",
    f"{ECUTEK_BASE}/phone-flash/",
    f"{ECUTEK_BASE}/proecu-tuning-suites/",
    f"{ECUTEK_BASE}/proecu-subaru-tuning-suites/",
    f"{ECUTEK_BASE}/proecu-nissan-tuning-suites/",
    f"{ECUTEK_BASE}/toyota-supra-a90-a91-3-0-and-2-0-litre-engines/",
]

# EcuTek uses a customized uploads path (``/content/uploads/`` without
# the ``wp-`` prefix). All product photography lives under this path;
# non-product chrome (social-media icons, cookie banner logo) lives
# under ``/content/plugins/`` or ``/content/static/``. Matching on the
# uploads path narrowly is the cleanest gate.
_UPLOADS_IMG_RE = re.compile(
    r"https?://(?:www\.)?ecutek\.com/content/uploads/" r"[^\s\"'<>()]+?\.(?:jpg|jpeg|png|webp|gif)",
    re.IGNORECASE,
)

# Filenames that are EcuTek chrome rather than product photography.
# Kept narrow: Facebook/Twitter/Instagram/YouTube share icons +
# the standalone logo + cropped favicons. The social-media PNGs live
# under ``/content/uploads/2019/12/`` so the uploads-path gate alone
# doesn't exclude them.
_IMAGE_NOISE_RE = re.compile(
    r"/ecutek_logo|/Facebook\.|/Twitter\.|/Instagram\.|/Youtube\.|/logo-|"
    r"/cropped-ecutek-icon|/favicon|/sprite|/icon[-_]|/cookieyes",
    re.IGNORECASE,
)

# WordPress auto-generates thumbnail variants of every uploaded image
# at fixed sizes (``<name>-300x84.jpg``, ``<name>-1024x288.jpg``,
# ``<name>-768x216.jpg``, ``<name>-1536x432.jpg``, …). We dedup against
# the unsuffixed original so one upload doesn't produce 5 payload-image
# rows pointing at the same photograph at different resolutions.
_WP_SIZE_SUFFIX_RE = re.compile(r"-\d{2,5}x\d{2,5}(?=\.[a-z]+$)", re.IGNORECASE)


def _strip_brand_suffix(raw: str) -> str:
    """Strip AIOSEO's trailing ``" - EcuTek"`` / ``" | EcuTek"`` suffix."""
    cleaned = _TITLE_SUFFIX_RE.sub("", raw).strip()
    return cleaned


def _normalize_rest_link(link: str) -> Optional[str]:
    """
    Normalize a WP REST ``link`` value to the canonical product URL we
    want to emit:

    * force https scheme (REST occasionally returns http for legacy posts)
    * drop query/fragment
    * ensure a trailing slash so ``nissan-z`` → ``nissan-z/`` de-dupes
      against the sitemap form
    * keep only URLs on the ecutek.com host
    """
    if not link or not isinstance(link, str):
        return None
    base = link.strip().split("?", 1)[0].split("#", 1)[0]
    if not base:
        return None
    if base.startswith("http://"):
        base = "https://" + base[len("http://") :]
    if not base.startswith("https://www.ecutek.com/") and not base.startswith("https://ecutek.com/"):
        return None
    # Force the www form so product URLs match the canonical host in the
    # host map; same shape the sitemap emits.
    if base.startswith("https://ecutek.com/"):
        base = "https://www.ecutek.com/" + base[len("https://ecutek.com/") :]
    if not base.endswith("/"):
        base = base + "/"
    return base


def _slug_from_url(url: str) -> Optional[str]:
    """
    Trailing path segment of an ecutek.com URL, lowercased. Used by the
    discovery deny list to filter non-product posts under the Products
    category.
    """
    m = re.match(r"^https?://(?:www\.)?ecutek\.com/([^/?#]+)/?", url, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower()


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is a plausible EcuTek product-post URL — on the
    ecutek.com host, single-segment root-level path, and the slug isn't
    on the non-product deny list.
    """
    slug = _slug_from_url(url)
    if not slug:
        return False
    if slug in _NON_PRODUCT_SLUGS:
        return False
    # Only accept root-level single-segment slugs (``/<slug>/``). Deeper
    # paths (``/about-us/test/``, ``/category/<slug>/``) are CMS content,
    # not product posts.
    m = re.match(r"^https?://(?:www\.)?ecutek\.com/([^/?#]+)/?$", url, re.IGNORECASE)
    if not m:
        return False
    seg = m.group(1).lower()
    # Deny-list category/tag URL shapes by prefix just in case a future
    # post is accidentally emitted with that leading segment.
    if seg in ("category", "tag", "author", "wp-admin", "wp-json", "feed"):
        return False
    return True


def _discover_product_urls_via_wp_rest() -> List[str]:
    """
    Fetch WP REST posts under the Products category and return every
    URL that passes ``_is_product_url``. Returns ``[]`` on any failure
    so the caller falls back to the hard-coded defaults.

    ``per_page=100`` comfortably covers the current ~40 posts; if the
    catalog ever grows past 100 this needs pagination, but that's a
    long way off for a dealer-only ECU brand.
    """
    try:
        resp = requests.get(
            WP_POSTS_URL,
            params={
                "categories": str(WP_PRODUCTS_CATEGORY_ID),
                "per_page": "100",
                "_fields": "id,slug,link",
            },
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        posts = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(posts, list) or len(posts) < _MIN_REST_POSTS:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []
    for post in posts:
        if not isinstance(post, dict):
            continue
        link = post.get("link")
        if not isinstance(link, str):
            continue
        normalized = _normalize_rest_link(link)
        if not normalized or not _is_product_url(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        product_urls.append(normalized)
    return product_urls


def _resolve_start_urls() -> List[str]:
    """Env override wins; else WP REST discovery; else hard-coded defaults."""
    raw = os.environ.get("CRAWLER_ECUTEK_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_wp_rest()
    return urls if urls else list(DEFAULT_START_URLS)


def _iter_graph_items(html: str) -> Iterator[dict[str, Any]]:
    """
    Yield each dict inside an AIOSEO JSON-LD ``@graph``. AIOSEO emits
    one ``<script type="application/ld+json" class="aioseo-schema">`` per
    page wrapping an array under ``@graph`` — the shared
    ``extract_json_ld_product`` skips it because none of the items are
    ``@type: Product``, so we parse it directly.
    """
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", {"type": "application/ld+json"}):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict):
                        yield cast(dict[str, Any], item)
            else:
                # Some AIOSEO plugin variants emit a single node at the
                # root (observed on a few test pages).
                yield cast(dict[str, Any], data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield cast(dict[str, Any], item)


def _graph_find(html: str, wanted_types: tuple[str, ...]) -> Optional[dict[str, Any]]:
    """First ``@graph`` item whose ``@type`` matches one of ``wanted_types``."""
    for item in _iter_graph_items(html):
        t = item.get("@type")
        if isinstance(t, str) and t in wanted_types:
            return item
        if isinstance(t, list) and any(w in t for w in wanted_types):
            return item
    return None


def _extract_name(html: str, soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer ``BlogPosting.name`` / ``WebPage.name`` from the AIOSEO
    graph (both already omit the HTML entity noise that raw ``<title>``
    contains), then fall back to ``<title>`` with the EcuTek suffix
    stripped, and finally ``<h1>``.
    """
    for node_type in (("BlogPosting",), ("WebPage",)):
        item = _graph_find(html, node_type)
        if item is None:
            continue
        name_val = item.get("name") or item.get("headline")
        if isinstance(name_val, str) and name_val.strip():
            cleaned = _strip_brand_suffix(html_mod.unescape(name_val))
            if cleaned and len(cleaned) >= 3:
                return cleaned

    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        raw = title_tag.get_text(strip=True)
        if raw:
            cleaned = _strip_brand_suffix(html_mod.unescape(raw))
            if cleaned and cleaned.lower() != "page not found" and len(cleaned) >= 3:
                return cleaned

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text and len(text) >= 3:
            return html_mod.unescape(text)
    return None


def _extract_description(html: str, soup: BeautifulSoup) -> Optional[str]:
    """
    ``WebPage.description`` in the AIOSEO graph is the meta-description
    AIOSEO assembles for the page — the first real narrative text of
    the post, usually 200-400 chars. ``BlogPosting.description`` is
    empty on every page we sampled, so skip it. Fall back to the
    ``.main-info`` container's text (the WP post body — no ``<p>`` or
    ``article`` wrappers, just plain divs) when the graph is missing.
    """
    webpage = _graph_find(html, ("WebPage", "ItemPage"))
    if webpage is not None:
        desc = webpage.get("description")
        if isinstance(desc, str) and desc.strip():
            normalized = normalize_description_text(desc, max_len=2000)
            if normalized:
                return normalized

    main = soup.select_one(".main-info")
    if isinstance(main, Tag):
        text = main.get_text(" ", strip=True)
        if text and len(text) >= 80:
            return normalize_description_text(text, max_len=2000)
    return None


def _normalize_image_url(url: str) -> str:
    """Force https and resolve scheme-relative URLs."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


def _is_valid_product_image(url: str) -> bool:
    """Accept ``/content/uploads/`` URLs; reject chrome (logo/social/favicon)."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/content/uploads/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _extract_images(html: str, soup: BeautifulSoup) -> List[str]:
    """
    Collect product images. Start with the ``BlogPosting.image`` from
    the AIOSEO graph (the hero / featured image — almost always a
    per-product banner). Then sweep the ``.main-info`` post body for
    additional ``<img>`` tags. Finish with a regex sweep of the raw
    HTML for any ``/content/uploads/`` URLs we missed (covers lazy-load
    attributes and shortcode output that ``bs4`` can't parse cleanly).
    Cap at 12 per the ``ScrapedPayload`` convention. Dedup on absolute
    URL.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("https://"):
            return
        if not _is_valid_product_image(u):
            return
        # Dedup on the size-suffix-stripped form so thumbnail variants
        # (``name-300x84.jpg``, ``name-1024x288.jpg``) collapse onto the
        # same slot as the unsuffixed original.
        key = _WP_SIZE_SUFFIX_RE.sub("", u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    # 1. BlogPosting hero image (featured_media). Most reliable source.
    post = _graph_find(html, ("BlogPosting", "Article"))
    if post is not None:
        img_val = post.get("image")
        if isinstance(img_val, str):
            add(img_val)
        elif isinstance(img_val, dict):
            url = img_val.get("url") or img_val.get("@id")
            if isinstance(url, str):
                add(url)
        elif isinstance(img_val, list):
            for i in img_val:
                if isinstance(i, str):
                    add(i)
                elif isinstance(i, dict):
                    url = i.get("url") or i.get("@id")
                    if isinstance(url, str):
                        add(url)

    # 2. Body images inside the WP post content container.
    content_scope = soup.select_one(".main-info") or soup
    for img in content_scope.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val)
                break

    # 3. Raw-HTML regex fallback — picks up shortcode-embedded uploads
    # that didn't round-trip through bs4 (rare on this theme but free).
    if len(ordered) < 12:
        for match in _UPLOADS_IMG_RE.finditer(html):
            add(match.group(0))
            if len(ordered) >= 12:
                break

    return ordered


class EcuTekAdapter(RetailerCrawlerAdapter):
    """
    EcuTek adapter.

    WordPress + AIOSEO storefront; plain-HTTP fetches. Discovery walks
    the WP REST API (``/wp-json/wp/v2/posts?categories=3``) for posts
    under the **Products** taxonomy, filtered against a non-product
    deny list (regulatory / careers / OEM-services / tuner-onboarding
    slugs). Parsing reads AIOSEO's ``@graph`` for the product name
    (``BlogPosting.name``), the description
    (``WebPage.description``), and the hero image
    (``BlogPosting.image.url``); body images are harvested from the
    ``.main-info`` post body.

    Brand is always forced to the canonical ``"EcuTek"`` — every page
    on this site is first-party; the title heuristic would otherwise
    pick up car makes (every PDP title leads with the target vehicle).

    Caveat — dealer-only brochure site. ``price_cents`` and
    ``part_number`` are ``None`` by design; cross-retailer dedupe falls
    back to ``(retailer, url)`` per the ``radium`` /
    ``injectordynamics`` / ``hennessey`` precedent.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered via the WP REST API, falling back
        to a verified default list when the API is unreachable. Override
        via ``CRAWLER_ECUTEK_START_URLS`` (comma-separated).
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an EcuTek ``/{slug}/`` product post into a
        ``ScrapedPayload``. Returns ``None`` when no usable name can be
        extracted (non-product page — category index, author archive,
        etc.).

        ``price_cents`` and ``part_number`` are always ``None``: the
        public site carries neither — licenses and programming kits are
        sold exclusively via Master Tuner dealers.
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(html, soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(html, soup)
        images = _extract_images(html, soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=None,  # no commerce on this site; dealer-only
            part_manufacturer=ECUTEK_BRAND,
            part_number=None,  # family pages — no canonical per-PDP SKU
            image_urls=images if images else None,
        )
