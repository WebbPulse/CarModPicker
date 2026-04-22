"""
HRE Performance Wheels (hrewheels.com) crawler adapter — Tier 0 (plain HTTP).

Product URLs: ``/wheels/<series-slug>/<model-slug>`` (e.g.
``/wheels/series-p1/p101``, ``/wheels/classic-series/305m``,
``/wheels/hre-flowform/ff15``). Anything shorter (``/wheels``,
``/wheels/grid``, ``/wheels/<series>``) is a category / landing page and
is rejected.

HRE runs a custom PHP stack on nginx + Plesk — no Shopify, no WooCommerce,
no JSON-LD ``Product`` block. All product facts live in bespoke class
names on a server-rendered page:

- ``h1.WheelName`` — model code (``P101``)
- ``.SeriesName`` — series (``Series P1``)
- ``.MainImage img[src]`` — hero image (422x409 Shopify-style variant)
- ``.WheelAltImages a[href]`` / ``a[data-large]`` — full-resolution
  gallery (same asset at the ``wheel-original`` size variant)
- ``og:title`` — ``Series P1 - P101`` (richer than ``h1`` alone; used as
  the preferred name so the catalog entry shows the series)
- ``og:description`` — always empty on HRE; the description copy is a
  run of direct-child ``<p>`` tags inside ``.MainInformation``

Pages also render a ``.SeriesDisplayPrice`` "Starting at $X USD each"
line for some series. Per the RETAILER_BACKLOG policy this adapter is
catalog-only (wheels are quote-driven and configured per-customer), so
``price_cents`` is always ``None`` — same stance as ``wheelsboutique.py``.
The ingest pipeline records the listing without appending to price
history. See ``site_problem_notes/hrewheels.md``.

Fetcher tier: ``http``. The backlog entry hedged "Tier-1/2"; an AWS
egress probe showed the origin returns 200 to a plain Chrome UA with no
Cloudflare fronting (``server: nginx`` + ``x-powered-by: PHP/7.4`` + no
``cf-ray``). If that changes, promote to ``tier1_tls/``.

TLS chain quirk: the origin serves its leaf cert but omits the Starfield
G2 intermediate. A modern browser fetches the intermediate itself via AIA
but Python's ``ssl`` module doesn't, so plain ``requests`` / ``curl_cffi``
both fail with ``CERTIFICATE_VERIFY_FAILED: unable to get local issuer
certificate``. Rather than disabling verification (which opens the
crawler up to MITM), this adapter builds a session with a combined CA
bundle (certifi + the embedded Starfield G2 intermediate PEM) and hands
it to the ``HttpFetcher``. See ``_build_trust_session`` below.

Discovery: ``/sitemap.xml`` is a single flat ``<urlset>`` (not a
sitemap-index) that mixes product URLs with CMS pages (``/gallery``,
``/news``, ``/corporate/*``, ``/dealers``, etc.), so the filter is the
product URL regex rather than a child-sitemap name. Loc values use the
``http://`` scheme even though the site 301s to ``https://``; the
adapter normalizes to ``https://www.hrewheels.com`` before yielding.
Override with ``CRAWLER_HREWHEELS_START_URLS`` (comma-separated).

Brand: HRE only sells HRE. Unlike Wheels Boutique (multi-brand reseller
where the brand is in the URL's first path segment), every hrewheels.com
product is by definition an HRE wheel, so the adapter returns the
constant ``"HRE"``.

Part numbers: model codes like ``P101`` / ``305M`` / ``FF15`` are
series-level identifiers, not true SKUs — the same model ships in many
diameters, widths, offsets, and finishes, each a distinct part. Leaving
``part_number=None`` matches Wheels Boutique's posture and avoids
collapsing real fitments into a single catalog row downstream.
"""

import os
import re
import tempfile
import threading
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

import certifi
import defusedxml.ElementTree as ET
import requests
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.fetchers import Fetcher, HttpFetcher
from app.crawlers.parsing import meta_content, normalize_description_text

HREWHEELS_BASE = "https://www.hrewheels.com"
SITEMAP_URL = HREWHEELS_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Product paths are ``/wheels/<series>/<model>`` — exactly two segments
# after ``/wheels/``. The ``/wheels`` root and ``/wheels/grid`` index both
# fall one segment short and are rejected by this shape.
_PRODUCT_PATH_RE = re.compile(r"^/wheels/[^/]+/[^/]+/?$", re.IGNORECASE)

DEFAULT_START_URLS = [
    "https://www.hrewheels.com/wheels/series-p1/p101",
]

# HRE's brand is invariant — the whole site is their catalog.
HRE_BRAND = "HRE"

# The Affirm monthly-payment promo renders as a ``<p>`` inside
# ``.MainInformation``. Its copy is always "As low as $X/mo with ... Apply
# now" — strip these before joining description paragraphs so the catalog
# row isn't polluted with financing text.
_AFFIRM_PROMO_RE = re.compile(r"\bas low as\b.*\b(apply now|/mo)\b", re.IGNORECASE)


# Starfield Secure Certificate Authority - G2. The origin omits this from
# its handshake, so we embed the PEM (fetched from
# https://certs.starfieldtech.com/repository/sfig2.crt.pem) and append it
# to the certifi bundle at session-build time. Valid until 2031-05-03; the
# successor bundle would need to be re-embedded if the origin's issuer ever
# changes.
_STARFIELD_G2_INTERMEDIATE_PEM = """\
-----BEGIN CERTIFICATE-----
MIIFADCCA+igAwIBAgIBBzANBgkqhkiG9w0BAQsFADCBjzELMAkGA1UEBhMCVVMx
EDAOBgNVBAgTB0FyaXpvbmExEzARBgNVBAcTClNjb3R0c2RhbGUxJTAjBgNVBAoT
HFN0YXJmaWVsZCBUZWNobm9sb2dpZXMsIEluYy4xMjAwBgNVBAMTKVN0YXJmaWVs
ZCBSb290IENlcnRpZmljYXRlIEF1dGhvcml0eSAtIEcyMB4XDTExMDUwMzA3MDAw
MFoXDTMxMDUwMzA3MDAwMFowgcYxCzAJBgNVBAYTAlVTMRAwDgYDVQQIEwdBcml6
b25hMRMwEQYDVQQHEwpTY290dHNkYWxlMSUwIwYDVQQKExxTdGFyZmllbGQgVGVj
aG5vbG9naWVzLCBJbmMuMTMwMQYDVQQLEypodHRwOi8vY2VydHMuc3RhcmZpZWxk
dGVjaC5jb20vcmVwb3NpdG9yeS8xNDAyBgNVBAMTK1N0YXJmaWVsZCBTZWN1cmUg
Q2VydGlmaWNhdGUgQXV0aG9yaXR5IC0gRzIwggEiMA0GCSqGSIb3DQEBAQUAA4IB
DwAwggEKAoIBAQDlkGZL7PlGcakgg77pbL9KyUhpgXVObST2yxcT+LBxWYR6ayuF
pDS1FuXLzOlBcCykLtb6Mn3hqN6UEKwxwcDYav9ZJ6t21vwLdGu4p64/xFT0tDFE
3ZNWjKRMXpuJyySDm+JXfbfYEh/JhW300YDxUJuHrtQLEAX7J7oobRfpDtZNuTlV
Bv8KJAV+L8YdcmzUiymMV33a2etmGtNPp99/UsQwxaXJDgLFU793OGgGJMNmyDd+
MB5FcSM1/5DYKp2N57CSTTx/KgqT3M0WRmX3YISLdkuRJ3MUkuDq7o8W6o0OPnYX
v32JgIBEQ+ct4EMJddo26K3biTr1XRKOIwSDAgMBAAGjggEsMIIBKDAPBgNVHRMB
Af8EBTADAQH/MA4GA1UdDwEB/wQEAwIBBjAdBgNVHQ4EFgQUJUWBaFAmOD07LSy+
zWrZtj2zZmMwHwYDVR0jBBgwFoAUfAwyH6fZMH/EfWijYqihzqsHWycwOgYIKwYB
BQUHAQEELjAsMCoGCCsGAQUFBzABhh5odHRwOi8vb2NzcC5zdGFyZmllbGR0ZWNo
LmNvbS8wOwYDVR0fBDQwMjAwoC6gLIYqaHR0cDovL2NybC5zdGFyZmllbGR0ZWNo
LmNvbS9zZnJvb3QtZzIuY3JsMEwGA1UdIARFMEMwQQYEVR0gADA5MDcGCCsGAQUF
BwIBFitodHRwczovL2NlcnRzLnN0YXJmaWVsZHRlY2guY29tL3JlcG9zaXRvcnkv
MA0GCSqGSIb3DQEBCwUAA4IBAQBWZcr+8z8KqJOLGMfeQ2kTNCC+Tl94qGuc22pN
QdvBE+zcMQAiXvcAngzgNGU0+bE6TkjIEoGIXFs+CFN69xpk37hQYcxTUUApS8L0
rjpf5MqtJsxOYUPl/VemN3DOQyuwlMOS6eFfqhBJt2nk4NAfZKQrzR9voPiEJBjO
eT2pkb9UGBOJmVQRDVXFJgt5T1ocbvlj2xSApAer+rKluYjdkf5lO6Sjeb6JTeHQ
sPTIFwwKlhR8Cbds4cLYVdQYoKpBaXAko7nv6VrcPuuUSvC33l8Odvr7+2kDRUBQ
7nIMpBKGgc0T0U7EPMpODdIm8QC3tKai4W56gf0wrHofx1l7
-----END CERTIFICATE-----
"""


_BUNDLE_PATH_LOCK = threading.Lock()
_BUNDLE_PATH: Optional[str] = None


def _build_trust_bundle_path() -> str:
    """
    Return a filesystem path to a CA bundle that includes certifi's roots
    plus the Starfield G2 intermediate. Cached per-process; generated into
    a temp file on first call. Safe to call from multiple threads — the
    lock guards the first-write race.
    """
    global _BUNDLE_PATH
    if _BUNDLE_PATH is not None and os.path.exists(_BUNDLE_PATH):
        return _BUNDLE_PATH
    with _BUNDLE_PATH_LOCK:
        if _BUNDLE_PATH is not None and os.path.exists(_BUNDLE_PATH):
            return _BUNDLE_PATH
        fd, path = tempfile.mkstemp(prefix="hrewheels-ca-bundle-", suffix=".pem")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                out.write(_STARFIELD_G2_INTERMEDIATE_PEM)
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


def _is_product_url(url: str) -> bool:
    """True if ``url`` is on hrewheels.com and matches the product path shape."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "hrewheels.com" and not host.endswith(".hrewheels.com"):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _canonicalize_sitemap_url(url: str) -> str:
    """Normalize sitemap loc URLs to ``https://www.hrewheels.com/<path>``.

    Sitemap locs are emitted as ``http://www.hrewheels.com/...`` but the
    origin 301s to the ``https`` + ``www`` pair. Rewriting up-front keeps
    the fetcher from eating a redirect per URL.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip()
    path = parsed.path or "/"
    return f"{HREWHEELS_BASE}{path}"


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_HREWHEELS_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_HREWHEELS_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap(session: Optional[requests.Session] = None) -> List[str]:
    """
    Fetch ``/sitemap.xml`` and filter its flat urlset down to product paths.

    HRE's sitemap is a single ``<urlset>`` (not an index), so there's no
    child-sitemap step — just one fetch, one XML parse, one regex filter.
    Returns an empty list on fetch/parse failure so the caller can fall
    through to ``DEFAULT_START_URLS``.

    ``session`` should be the adapter's trust-bundle session; without it,
    the origin's broken TLS chain causes verification to fail.
    """
    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=30, session=session)
    except Exception:
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    seen: set[str] = set()
    product_urls: List[str] = []
    for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
        if not loc.text:
            continue
        canonical = _canonicalize_sitemap_url(loc.text)
        if not _is_product_url(canonical):
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        product_urls.append(canonical)
    return product_urls


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    Prefer ``og:title`` (``Series P1 - P101``) because it pairs the model
    code with the series; ``h1.WheelName`` alone (``P101``) is ambiguous
    across series once parts land in the global catalog. Fall back to the
    bare model code, then to ``<title>`` as a last resort.
    """
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    wheel_name = soup.select_one("h1.WheelName")
    if isinstance(wheel_name, Tag):
        text = wheel_name.get_text(strip=True)
        if text:
            return text
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        text = title_tag.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Join the prose ``<p>`` tags inside ``.MainInformation``.

    Skip the Affirm financing promo (matched by ``_AFFIRM_PROMO_RE``) and
    the ``.ViewFinishes`` anchor-wrapper ``<p>``. Empty paragraphs and
    ones without real text are dropped. Returns ``None`` when nothing
    meaningful remains rather than returning an empty string so the
    ingest payload stays tidy.
    """
    main_info = soup.select_one(".MainInformation")
    if not isinstance(main_info, Tag):
        return None

    parts: List[str] = []
    for p in main_info.find_all("p", recursive=False):
        if not isinstance(p, Tag):
            continue
        classes = p.get("class")
        if isinstance(classes, list) and "ViewFinishes" in classes:
            continue
        text = p.get_text(separator=" ", strip=True)
        if not text:
            continue
        if _AFFIRM_PROMO_RE.search(text):
            continue
        parts.append(text)

    if not parts:
        return None
    joined = " ".join(parts)
    return normalize_description_text(joined, max_len=2000)


def _normalize_image_url(src: str) -> Optional[str]:
    """Return ``https://<host>/<path>`` for a product image URL, else None.

    HRE hosts images on ``s3.amazonaws.com/cdn.hrewheels.com`` and emits
    them as protocol-relative ``//s3.amazonaws.com/...`` links. Rejects
    anything outside that CDN path so shared theme chrome (logos, PDF
    icons, sponsor badges like ``/img/logo-Brembo.jpg``) doesn't leak in.
    """
    if not src:
        return None
    s = src.strip()
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = HREWHEELS_BASE + s
    if not s.startswith("http"):
        return None
    low = s.lower()
    if "cdn.hrewheels.com" not in low:
        return None
    return s


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect gallery image URLs for the product.

    Preferred source is ``.WheelAltImages a[data-large]`` — those point
    at the ``wheel-original`` (full-resolution) variant of each photo.
    ``a[href]`` on the same anchor is a 422x409 mid-size variant and is
    only used when ``data-large`` is missing. Falls back to the hero
    ``.MainImage img[src]`` and finally the smaller og:image thumbnail
    so a product with no alt gallery still has one image. Deduped and
    capped at 12.
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        ordered.append(normalized)

    alt_scope = soup.select_one(".WheelAltImages")
    if isinstance(alt_scope, Tag):
        for anchor in alt_scope.find_all("a"):
            if not isinstance(anchor, Tag):
                continue
            data_large = anchor.get("data-large")
            href = anchor.get("href")
            if isinstance(data_large, str) and data_large.strip():
                add(data_large.strip())
            elif isinstance(href, str) and href.strip():
                add(href.strip())

    main_scope = soup.select_one(".MainImage")
    if isinstance(main_scope, Tag):
        img = main_scope.find("img")
        if isinstance(img, Tag):
            src = img.get("src")
            if isinstance(src, str):
                add(src.strip())

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content:
            add(content.strip())

    return ordered[:12]


class HREWheelsAdapter(RetailerCrawlerAdapter):
    """
    HRE Performance Wheels adapter — catalog-only, quote-driven pricing.

    Discovery walks ``/sitemap.xml`` (flat urlset, not an index) and
    filters to ``/wheels/<series>/<model>`` paths. Parsing reads bespoke
    class names (``h1.WheelName``, ``.MainInformation``, ``.MainImage``,
    ``.WheelAltImages``) because the custom PHP stack emits no JSON-LD
    Product block.

    Like Wheels Boutique, this adapter leaves ``price_cents=None`` and
    skips part numbers — HRE wheels are configured per-fitment and a
    single page represents many orderable SKUs.
    """

    ADAPTER_NAME: ClassVar[str] = "hrewheels"
    FETCHER_TIER = "http"

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        # HRE's origin omits the Starfield G2 intermediate from its TLS
        # handshake, so plain requests fails with CERTIFICATE_VERIFY_FAILED.
        # The runner hands every Tier-0 adapter a vanilla HttpFetcher that
        # knows nothing about the bundle — so whenever we got either no
        # fetcher or the stock HttpFetcher, replace it with one backed by
        # an augmented requests.Session. Callers that pass a non-HttpFetcher
        # (tests / mocks) are trusted to manage their own transport.
        if fetcher is None or isinstance(fetcher, HttpFetcher):
            self._trust_session: Optional[requests.Session] = _build_trust_session()
            fetcher = HttpFetcher(session=self._trust_session)
        else:
            self._trust_session = None
        super().__init__(fetcher=fetcher)

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs; env override wins, then sitemap, then ``DEFAULT_START_URLS``."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in _discover_via_sitemap(session=self._trust_session) or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """Parse an HRE product page. Returns ``None`` for non-product URLs or when no name is found."""
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)
        images = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=None,
            part_manufacturer=HRE_BRAND,
            part_number=None,
            image_urls=images if images else None,
        )
