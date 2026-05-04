"""
Injector Dynamics (injectordynamics.com) crawler adapter.

Fuel-injector specialist out of Fort Worth, Texas. **Manufacturer**, not a
storefront: Injector Dynamics partners with Bosch Motorsport to produce the
X-Series (XDS) motorsport injectors — ID725, ID1050-XDS, ID1300-XDS,
ID1700x, ID2000, ID2600-XDS — plus the ID1750-XDS, ID F-series inline fuel
filters (``F750 / F750i / F1250``), the ID BPC100 programmable boost
controller, and a line of UTV fuel-delivery modules. Anchors the fuel
vertical alongside ``radium`` (surge tanks / fittings) and ``deatschwerks``
(injectors / pumps sold direct).

Platform: **WordPress** (Alyeska / Theme Blvd child theme on Apache/2.4).
**No WooCommerce, no e-commerce of any kind.** Injector Dynamics sells
exclusively through authorized dealers (``/order/dealers/``, T1 Race
Development, etc.); ``injectordynamics.com`` is a marketing + spec site, so
every structured-commerce seam you would normally hit on a fuel-shop
retailer — JSON-LD ``Product``, ``og:price:amount``, WooCommerce
``product-type`` meta, a ``/products/<handle>`` URL shape — is absent by
design. What the pages *do* carry is rich: model name (``<title>``), a
long-form "Basic Specifications" block (flow rate / fuel-pressure limits /
electrical connector / dynamic-flow-match data), a per-car "Fitment by
Make & Model" table with application-specific part numbers, and a gallery
of CAD-rendered dimensional drawings. That's what this adapter captures.

Host: ``injectordynamics.com`` (no ``www`` redirect observed). Apache sets
``server: Apache/2.4`` and a ``link: <https://injectordynamics.com/wp-json/>``
header that exposes the WP REST API — which is load-bearing for discovery
(see below).

TLS chain quirk: the origin serves its leaf cert but omits the GlobalSign
GCC R3 DV TLS CA 2020 intermediate. Browsers fetch the intermediate via
AIA but Python's ``ssl`` module doesn't, so plain ``requests`` fails with
``CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate``.
Same pattern + same fix as ``hrewheels.py``: this adapter builds a
session with a combined CA bundle (certifi + the embedded GlobalSign
intermediate PEM) and hands it to the ``HttpFetcher``. Intermediate is
valid until 2029-03-18; see ``_build_trust_session`` below.

Discovery: **there is no ``sitemap.xml`` or ``sitemap_index.xml`` on this
origin** (both 404). WordPress's core sitemap feature (introduced in 5.5)
appears to be disabled or plugin-overridden; no Yoast / Rank Math / All in
One SEO sitemap is advertised either. The workable feed is the WP REST
API — ``/wp-json/wp/v2/pages?per_page=100`` returns every published Page,
and every product on this site is modelled as a WP Page (there is no
custom post type: ``/wp-json/wp/v2/types`` lists only the default
``page / post / attachment / wp_block``). Two URL shapes hold products:

1. ``/injectors/<slug>/`` — children of the ``Injectors`` parent page
   (id=53). Currently: ``id1050-xds``, ``id1300-xds``, ``id2600-xds``.
2. ``/id-<slug>/`` — root-level pages. Currently: ``id-1750-xds``,
   ``id-bpc100``, ``id-f1250-high-flow-inline-filter``,
   ``id-f750-fuel-filter``, ``id-f750i-inline-fuel-filter``.

Discovery walks the REST API and emits URLs matching either shape. The
``/injector-selector/``, ``/order/...``, ``/company-overview/``,
``/service/``, UTV category index pages (``polaris-utv-products`` etc.),
and install-instructions slugs are filtered out — they're CMS pages, not
product spec pages. Override with ``CRAWLER_INJECTORDYNAMICS_START_URLS``
(comma-separated) for targeted smoke tests; fallback to a verified
hard-coded list of the ~8 current PDPs when the REST API is unreachable.

Robots: ``robots.txt`` is permissive — ``User-agent: *`` with
``Disallow: /wp-admin/`` and ``Allow: /wp-admin/admin-ajax.php`` only.
Every product URL is allowed. No ``Crawl-delay`` declared.

Parse strategy — **no JSON-LD** ("JSON_LD_SHAPE: none"). The shared
``extract_json_ld_product`` and ``scraped_payload_from_json_ld`` helpers
return nothing here; they are not called. Fields are derived from:

- **name**: ``<title>`` strips the ``" | Injector Dynamics"`` suffix, then
  falls back to the first ``<h1>``. Titles already ship in the canonical
  model form (``ID1050-XDS``, ``ID BPC100``, ``ID F1250 Inline Filter``)
  so no further normalization is needed.
- **description**: WP REST API ``excerpt.rendered`` when we're seeding
  from it (the cheap path — no second fetch). Otherwise, ``<meta
  name="description">`` is absent on every PDP we checked, so we fall
  back to the ``.entry-content`` block's first paragraph of narrative
  text, stripped to plain text via ``normalize_description_text``.
- **price_cents**: **always None.** No commerce on this site.
- **part_number**: **always None at the top level.** The fitment table
  on each PDP lists ~20-40 per-car application-specific MPNs (e.g.
  ``ID1050-XDS`` has ``1050.48.11.14B.4`` for one Evo X variant and
  ``1050.48.14.WRX.4`` for a 4-cyl Subaru — connector orientation, length
  code, and injector count are all encoded in the MPN). The PDP itself
  has no single canonical SKU — the model name (``ID1050-XDS``) is the
  family identifier, not a MPN. Setting a placeholder here would block
  dedupe, exactly the failure mode ``radium`` documents. Cross-retailer
  dedupe falls back to ``retailer + product_url``.
- **part_manufacturer**: **always forced to canonical ``"Injector Dynamics"``.**
  This is the poster-child house-brand case.
- **image_urls**: DOM sweep of ``wp-content/uploads/`` image URLs inside
  ``.entry-content`` — the WordPress uploads directory is the authoritative
  media store and every gallery image is served from there. Protocol is
  upgraded to https (site mixes ``http://`` and ``https://`` origins on
  legacy uploads from 2016; all paths resolve either way). Capped at 12.

**Variant rule (VARIANTS.md §5 — the poster-child multi-variant case,
lossy by design).** Fuel injectors are the canonical §5 "yes / yes / yes"
example: variants differ by **flow rate** (ID725 / ID1050-XDS / ID1300-XDS
/ ID1700x / ID2000 / ID2600-XDS — hundreds of cc/min apart, different
physical bodies), by **electrical connector** (USCAR vs JETRONIC /
Minitimer — wholly different wire harnesses), by **injector length** (34mm
/ 48mm / 60mm to match rail spacing), by **O-ring style**, and by **set
count** (4 / 6 / 8 injectors matched for a specific engine). Every one of
those combinations has its own MPN, its own price at dealers, and its own
fitment. Injector Dynamics partially shards that axis across URLs — the
flow-rate axis gets a distinct PDP per grade (``/injectors/id1050-xds/``,
``/injectors/id1300-xds/``, ``/injectors/id2600-xds/``), which mirrors how
``texasspeed`` handles piston oversizes (parent page per family). But the
**connector / length / set-count sub-axes live inside a single PDP as a
fitment table**: the ``ID1050-XDS`` page alone documents dozens of
per-car MPNs, each a real SKU the customer would order. We capture **none
of those**. The known-loss summary per VARIANTS.md §3 is:

    URL shape:     parent PDP, one per flow-rate grade
    Strategy:      scrape the flow-rate family page; store the model name
                   and spec copy; leave part_number=None
    What's lost:   every per-fitment MPN (dozens per PDP), every
                   per-connector / per-length / per-set-count variant,
                   every price (there is no price on this site anyway).

This is intentional and documented; the fix is Option D ("first-class
Variant model", VARIANTS.md §6) and is out of scope here. Even if we
harvested the fitment MPNs we have no price/offer to attach them to, so
catalog value per row would be low; better to leave it for the variant
schema work to surface them properly once that lands.

Platform firsts: **pure WordPress with no commerce plugin** — none of the
prior 55 adapters targets a site that publishes product pages as plain
WP Pages. The ``/wp-json/wp/v2/pages`` discovery path is new and should
become the reference pattern for future marketing-only manufacturer sites
(Haltech, Link, several aero shops on Batch 2D are candidates).

Caveats:

- No price, no SKU, no brand in structured form — all three are
  derivations, not extractions.
- ``featured_media`` is ``0`` on every product page we checked, so the
  REST API doesn't give us a hero image cheaply; we fetch the full HTML
  and sweep for uploads URLs.
- Image URLs embedded in content are frequently ``http://`` (2013-era
  uploads); we upgrade to ``https://`` on ingest.
- The ``/injectors/`` parent page itself (id=53) is a category landing,
  not a product — filtered out by slug check.
"""

import html as html_mod
import os
import re
import tempfile
import threading
from typing import ClassVar, Iterator, List, Optional

import certifi
import requests
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import DEFAULT_USER_AGENT, ScrapedPayload
from app.crawlers.fetchers import Fetcher, HttpFetcher
from app.crawlers.parsing import meta_content, normalize_description_text

INJECTORDYNAMICS_BASE = "https://injectordynamics.com"
WP_PAGES_URL = f"{INJECTORDYNAMICS_BASE}/wp-json/wp/v2/pages"

# Canonical house-brand name — matches the title suffix
# ("... | Injector Dynamics") and the logo on the site. Used verbatim for
# every scraped part so the manufacturer table never grows car-make rows
# (some fitment copy leads with "Subaru" / "Mitsubishi") or product-word
# rows ("Injector" alone).
INJECTORDYNAMICS_BRAND = "Injector Dynamics"

# Product pages live at two URL shapes (see module docstring):
#   /injectors/<slug>/   — flow-rate PDPs under the "Injectors" parent
#   /id-<slug>/          — root-level ID-branded hardware (filters, BPC100,
#                          ID1750-XDS which shipped outside the /injectors/
#                          parent tree for historical reasons)
_PRODUCT_PATH_RE = re.compile(
    r"^/(?:injectors/[a-z0-9][a-z0-9\-]*|id-[a-z0-9][a-z0-9\-]*)/?$",
    re.IGNORECASE,
)

# Non-product pages that live under the same URL roots we scan. These are
# CMS landing pages / install guides / dealer-map pages and must not be
# treated as scrapable products.
_NON_PRODUCT_SLUGS = frozenset(
    {
        # /injectors/ parent landing page (id=53) — a category index.
        "injectors",
        # BPC100 user guide, not the product page itself.
        "id-bpc100-guide",
        # "Product Test and Evaluation" — marketing page, not a product.
        "id-product-test-evaluation-amp",
    }
)

# Minimum number of REST-API pages we accept before trusting the feed.
# If the WP REST API is broken (plugin conflict, auth wall, 500), the list
# will be tiny and we fall back to the hard-coded defaults instead of
# emitting a crippled URL set.
_MIN_REST_PAGES = 4

# Verified live product URLs — fallback when the WP REST API is unreachable
# and no env override is provided. Covers both path shapes so the first
# crawl exercises the full parse path end to end (flow-rate PDPs +
# root-level ID-hardware PDPs).
DEFAULT_START_URLS = [
    # Flow-rate family PDPs under /injectors/.
    "https://injectordynamics.com/injectors/id1050-xds/",
    "https://injectordynamics.com/injectors/id1300-xds/",
    "https://injectordynamics.com/injectors/id2600-xds/",
    # Root-level ID-branded hardware.
    "https://injectordynamics.com/id-1750-xds/",
    "https://injectordynamics.com/id-bpc100/",
    "https://injectordynamics.com/id-f1250-high-flow-inline-filter/",
    "https://injectordynamics.com/id-f750-fuel-filter/",
    "https://injectordynamics.com/id-f750i-inline-fuel-filter/",
]

# wp-content/uploads URL pattern. Both ``http://`` and ``https://`` forms
# appear in the DOM on this site (2013-era uploads use http; modern ones
# use https — both resolve either way; we normalize on ingest).
_UPLOADS_IMG_RE = re.compile(
    r"https?://injectordynamics\.com/wp-content/uploads/" r"[^\s\"'<>()]+?\.(?:jpg|jpeg|png|webp|gif)",
    re.IGNORECASE,
)

# Image filename fragments that are site chrome (logo, banner, theme skin)
# rather than product photography. Very small — the Alyeska theme uses
# /wp-content/themes/ for its own assets, so /uploads/ images are almost
# always catalog content. Kept for the rare banner image pulled into a PDP.
_IMAGE_NOISE_RE = re.compile(
    r"/IDLogo|/logo[-_]?|/banner[-_]?|/header[-_]?|/footer[-_]?|/favicon|/sprite|/icon[-_]",
    re.IGNORECASE,
)


# GlobalSign GCC R3 DV TLS CA 2020 — the issuing intermediate the origin
# omits from its TLS handshake. Browsers fetch it via AIA; Python's ssl
# module doesn't, so plain requests fails with CERTIFICATE_VERIFY_FAILED.
# PEM fetched from http://secure.globalsign.com/cacert/gsgccr3dvtlsca2020.crt
# (the AIA URL embedded in the leaf cert). Chains to the GlobalSign Root
# CA - R3 already in certifi. Valid until 2029-03-18; if injectordynamics
# switches CAs the symptom is the same SSLError and the fix is to swap
# this PEM for the new issuer's intermediate.
_GLOBALSIGN_GCC_R3_DV_TLS_CA_2020_PEM = """\
-----BEGIN CERTIFICATE-----
MIIEsDCCA5igAwIBAgIQd70OB0LV2enQSdd00CpvmjANBgkqhkiG9w0BAQsFADBM
MSAwHgYDVQQLExdHbG9iYWxTaWduIFJvb3QgQ0EgLSBSMzETMBEGA1UEChMKR2xv
YmFsU2lnbjETMBEGA1UEAxMKR2xvYmFsU2lnbjAeFw0yMDA3MjgwMDAwMDBaFw0y
OTAzMTgwMDAwMDBaMFMxCzAJBgNVBAYTAkJFMRkwFwYDVQQKExBHbG9iYWxTaWdu
IG52LXNhMSkwJwYDVQQDEyBHbG9iYWxTaWduIEdDQyBSMyBEViBUTFMgQ0EgMjAy
MDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKxnlJV/de+OpwyvCXAJ
IcxPCqkFPh1lttW2oljS3oUqPKq8qX6m7K0OVKaKG3GXi4CJ4fHVUgZYE6HRdjqj
hhnuHY6EBCBegcUFgPG0scB12Wi8BHm9zKjWxo3Y2bwhO8Fvr8R42pW0eINc6OTb
QXC0VWFCMVzpcqgz6X49KMZowAMFV6XqtItcG0cMS//9dOJs4oBlpuqX9INxMTGp
6EASAF9cnlAGy/RXkVS9nOLCCa7pCYV+WgDKLTF+OK2Vxw3RUJ/p8009lQeUARv2
UCcNNPCifYX1xIspvarkdjzLwzOdLahDdQbJON58zN4V+lMj0msg+c0KnywPIRp3
BMkCAwEAAaOCAYUwggGBMA4GA1UdDwEB/wQEAwIBhjAdBgNVHSUEFjAUBggrBgEF
BQcDAQYIKwYBBQUHAwIwEgYDVR0TAQH/BAgwBgEB/wIBADAdBgNVHQ4EFgQUDZjA
c3+rvb3ZR0tJrQpKDKw+x3wwHwYDVR0jBBgwFoAUj/BLf6guRSSuTVD6Y5qL3uLd
G7wwewYIKwYBBQUHAQEEbzBtMC4GCCsGAQUFBzABhiJodHRwOi8vb2NzcDIuZ2xv
YmFsc2lnbi5jb20vcm9vdHIzMDsGCCsGAQUFBzAChi9odHRwOi8vc2VjdXJlLmds
b2JhbHNpZ24uY29tL2NhY2VydC9yb290LXIzLmNydDA2BgNVHR8ELzAtMCugKaAn
hiVodHRwOi8vY3JsLmdsb2JhbHNpZ24uY29tL3Jvb3QtcjMuY3JsMEcGA1UdIARA
MD4wPAYEVR0gADA0MDIGCCsGAQUFBwIBFiZodHRwczovL3d3dy5nbG9iYWxzaWdu
LmNvbS9yZXBvc2l0b3J5LzANBgkqhkiG9w0BAQsFAAOCAQEAy8j/c550ea86oCkf
r2W+ptTCYe6iVzvo7H0V1vUEADJOWelTv07Obf+YkEatdN1Jg09ctgSNv2h+LMTk
KRZdAXmsE3N5ve+z1Oa9kuiu7284LjeS09zHJQB4DJJJkvtIbjL/ylMK1fbMHhAW
i0O194TWvH3XWZGXZ6ByxTUIv1+kAIql/Mt29PmKraTT5jrzcVzQ5A9jw16yysuR
XRrLODlkS1hyBjsfyTNZrmL1h117IFgntBA5SQNVl9ckedq5r4RSAU85jV8XK5UL
REjRZt2I6M9Po9QL7guFLu4sPFJpwR1sPJvubS2THeo7SxYoNDtdyBHs7euaGcMa
D/fayQ==
-----END CERTIFICATE-----
"""


_BUNDLE_PATH_LOCK = threading.Lock()
_BUNDLE_PATH: Optional[str] = None


def _build_trust_bundle_path() -> str:
    """
    Return a filesystem path to a CA bundle that includes certifi's roots
    plus the GlobalSign GCC R3 DV TLS CA 2020 intermediate. Cached
    per-process; generated into a temp file on first call. Safe to call
    from multiple threads.
    """
    global _BUNDLE_PATH
    if _BUNDLE_PATH is not None and os.path.exists(_BUNDLE_PATH):
        return _BUNDLE_PATH
    with _BUNDLE_PATH_LOCK:
        if _BUNDLE_PATH is not None and os.path.exists(_BUNDLE_PATH):
            return _BUNDLE_PATH
        fd, path = tempfile.mkstemp(prefix="injectordynamics-ca-bundle-", suffix=".pem")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(_GLOBALSIGN_GCC_R3_DV_TLS_CA_2020_PEM)
                with open(certifi.where(), "r", encoding="utf-8") as src:
                    out.write(src.read())
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        _BUNDLE_PATH = path
        return _BUNDLE_PATH


def _build_trust_session() -> requests.Session:
    """Build a requests session that verifies against the augmented CA bundle."""
    session = requests.Session()
    session.verify = _build_trust_bundle_path()
    return session


def _resolve_start_urls(session: Optional[requests.Session] = None) -> List[str]:
    """Env override wins; else discover via WP REST; else hard-coded defaults."""
    raw = os.environ.get("CRAWLER_INJECTORDYNAMICS_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_wp_rest(session=session)
    return urls if urls else list(DEFAULT_START_URLS)


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is an Injector Dynamics product PDP — either a
    ``/injectors/<slug>/`` flow-rate family page or a root-level
    ``/id-<slug>/`` hardware page, and the slug is not on the
    non-product deny list.
    """
    if not url:
        return False
    # Require our origin; ignore off-site outbound links (dealers, etc.).
    if "//injectordynamics.com/" not in url and "//www.injectordynamics.com/" not in url:
        return False
    # Strip scheme/host to the path for the regex check.
    m = re.search(r"https?://(?:www\.)?injectordynamics\.com(/[^?#]*)", url)
    if not m:
        return False
    path = m.group(1)
    if not _PRODUCT_PATH_RE.match(path):
        return False
    # Deny list on the trailing slug (last non-empty path segment).
    slug = path.strip("/").rsplit("/", 1)[-1].lower()
    if slug in _NON_PRODUCT_SLUGS:
        return False
    return True


def _discover_product_urls_via_wp_rest(session: Optional[requests.Session] = None) -> List[str]:
    """
    Walk the WP REST API (``/wp-json/wp/v2/pages?per_page=100``) and
    return every product-looking page URL. Returns ``[]`` on any failure
    (HTTP error, JSON parse error, feed shorter than the confidence
    threshold) so the caller falls back to hard-coded defaults.

    We call ``requests`` directly here rather than ``self.fetcher`` because
    discovery runs before the runner injects a fetcher in some paths
    (smoke tests, ad-hoc reruns) and the REST endpoint is Tier-0-trivial —
    plain HTTP with the crawler UA returns JSON on first try, no
    Cloudflare, no TLS fingerprinting.

    ``session`` should be the adapter's trust-bundle session; without it,
    the origin's broken TLS chain causes verification to fail.
    """
    getter = session.get if session is not None else requests.get
    try:
        resp = getter(
            WP_PAGES_URL,
            params={"per_page": "100", "_fields": "id,slug,link,parent"},
            headers={"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        pages = resp.json()
    except (requests.RequestException, ValueError):
        return []

    if not isinstance(pages, list) or len(pages) < _MIN_REST_PAGES:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        link = page.get("link")
        if not isinstance(link, str) or not link:
            continue
        if not _is_product_url(link):
            continue
        base = link.split("?", 1)[0]
        # Force https (REST sometimes returns http for legacy pages).
        if base.startswith("http://"):
            base = "https://" + base[len("http://") :]
        # Normalize trailing slash so two variants of the same URL don't
        # both pass the de-dupe set.
        if not base.endswith("/"):
            base = base + "/"
        if base in seen:
            continue
        seen.add(base)
        product_urls.append(base)
    return product_urls


def _normalize_image_url(url: str) -> str:
    """Upgrade http → https and scheme-relative → https for uploads URLs."""
    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    return u


def _is_valid_product_image(url: str) -> bool:
    """Accept ``/wp-content/uploads/`` URLs only; reject theme chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/wp-content/uploads/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _extract_images(raw_html: str, soup: BeautifulSoup) -> List[str]:
    """
    Collect product-gallery images. There is no JSON-LD and no og:image on
    this site (verified across every PDP), so the DOM sweep inside
    ``.entry-content`` is the single source. We also do a raw regex sweep
    of the full HTML as a belt-and-suspenders backup — some theme variants
    render images through shortcodes that bs4 parses awkwardly. Dedupe on
    the absolute URL (no Shopify-style size-suffix to strip here; the
    Alyeska theme serves the original upload at its real filename).
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
        if u in seen:
            return
        seen.add(u)
        ordered.append(u)

    # Prefer images inside .entry-content (the WordPress post body).
    content_scope = soup.select_one(".entry-content") or soup
    for img in content_scope.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-original"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val)
                break

    # Regex sweep of the full HTML — catches lazy-load data URLs and
    # shortcodes that didn't round-trip through bs4.
    if len(ordered) < 12:
        for match in _UPLOADS_IMG_RE.finditer(raw_html):
            add(match.group(0))
            if len(ordered) >= 12:
                break

    return ordered


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract the product model name from ``<title>`` (format
    ``"<MODEL> | Injector Dynamics"``) stripped of the brand suffix, with
    an ``<h1>`` fallback. Titles are the only structured name source on
    this site — there is no og:title, no JSON-LD name.
    """
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        raw = title_tag.get_text(strip=True)
        if raw:
            # Strip " | Injector Dynamics" (with and without the pipe's
            # surrounding whitespace, case-insensitive).
            cleaned = re.sub(
                r"\s*[\|\-–]\s*Injector\s+Dynamics\s*$",
                "",
                raw,
                flags=re.IGNORECASE,
            ).strip()
            cleaned = html_mod.unescape(cleaned)
            if cleaned and cleaned.lower() != "page not found":
                return cleaned

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return html_mod.unescape(text)
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract a usable description. ``<meta name="description">`` and
    ``og:description`` are absent on every PDP checked, so we walk the
    ``.entry-content`` block's direct children and take the first chunk
    with enough narrative prose to be useful. The Alyeska theme wraps the
    intro copy in a ``<div class="column grid_6">`` (not a ``<p>``), so a
    ``<p>``-only scan misses it — we accept any block-level element whose
    text content is ≥ 120 chars. The ``to learn more... follow this link``
    one-liner that appears before the spec tables is intentionally
    shorter than the threshold so it doesn't win over the real copy.
    """
    for selector in (
        ("meta", {"property": "og:description"}),
        ("meta", {"name": "description"}),
    ):
        tag = soup.find(*selector)
        if isinstance(tag, Tag):
            content = meta_content(tag)
            if content and content.strip():
                return normalize_description_text(content, max_len=2000)

    content_scope = soup.select_one(".entry-content")
    if isinstance(content_scope, Tag):
        best: Optional[str] = None
        for node in content_scope.find_all(["div", "p"]):
            if not isinstance(node, Tag):
                continue
            text = node.get_text(" ", strip=True)
            if not text or len(text) < 120:
                continue
            # First sufficiently-long block wins — the theme renders the
            # narrative copy before the "Basic Specifications" table, so
            # document order matches what a catalog reader expects.
            best = text
            break
        if best:
            return normalize_description_text(best, max_len=2000)
    return None


class InjectorDynamicsAdapter(RetailerCrawlerAdapter):
    """
    Injector Dynamics adapter. WordPress + Alyeska theme, **no commerce
    platform** — manufacturer marketing site that sells through dealers.

    Discovery: ``/wp-json/wp/v2/pages?per_page=100`` filtered to the
    product URL shapes (``/injectors/<slug>/`` and ``/id-<slug>/``), with
    a hard-coded fallback list of the current ~8 PDPs for when the REST
    API is unreachable. Env override ``CRAWLER_INJECTORDYNAMICS_START_URLS``
    (comma-separated) supersedes both.

    Parsing: no JSON-LD, no og, no microdata — pure DOM. Name from
    ``<title>`` (brand suffix stripped); description from the first
    ``.entry-content`` paragraph; images swept from ``/wp-content/uploads/``
    URLs inside the post body. ``price_cents``, ``part_number`` are both
    always ``None`` by design — this site has no prices and no single
    canonical SKU per PDP (see module docstring on the variant rule and
    VARIANTS.md §5). Brand is always forced to ``"Injector Dynamics"``.
    """

    ADAPTER_NAME: ClassVar[str] = "injectordynamics"
    FETCHER_TIER = "http"

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        # injectordynamics.com serves only its leaf cert and omits the
        # GlobalSign GCC R3 DV TLS CA 2020 intermediate from the handshake,
        # so plain requests fails with CERTIFICATE_VERIFY_FAILED. Same
        # pattern as hrewheels — replace the runner's stock HttpFetcher
        # with one backed by an augmented requests.Session.
        if fetcher is None or isinstance(fetcher, HttpFetcher):
            self._trust_session: Optional[requests.Session] = _build_trust_session()
            fetcher = HttpFetcher(session=self._trust_session)
        else:
            self._trust_session = None
        super().__init__(fetcher=fetcher)

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs discovered via the WP REST API, falling back to
        a verified default list when the API is unreachable. Override the
        feed with ``CRAWLER_INJECTORDYNAMICS_START_URLS`` (comma-separated)
        for targeted re-crawls.
        """
        for url in _resolve_start_urls(session=self._trust_session):
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an Injector Dynamics product page into a ``ScrapedPayload``.

        Returns ``None`` when no usable name can be extracted (the WP 404
        template shares DOM shape with a real page; the title-based name
        extractor rejects ``"Page not found"`` so those short-circuit
        here).

        ``price_cents`` and ``part_number`` are intentionally ``None`` —
        there is no price on this site (no commerce) and no canonical SKU
        per PDP (the fitment table lists dozens of per-car MPNs; picking
        one would be arbitrary). Cross-retailer dedupe uses ``retailer +
        product_url`` per the ``radium`` precedent.
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)
        images = _extract_images(html, soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=None,  # no commerce on this site; dealer-only
            part_manufacturer=INJECTORDYNAMICS_BRAND,
            part_number=None,  # fitment-table catalog; no canonical PDP SKU
            image_urls=images if images else None,
        )
