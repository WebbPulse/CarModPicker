"""
Z1 Motorsports (z1motorsports.com) crawler adapter — Tier 1 (TLS-impersonating fetcher).

Product URLs: ``https://www.z1motorsports.com/<category-path>/<slug>-p-<digits>.html``

Z1 is behind Cloudflare with a client-fingerprint block (see
``site_problem_notes/z1motorsports.md``): plain ``requests`` / ``curl`` with a
Chrome UA return a ``cf-mitigated: challenge`` 403, but ``curl_cffi`` with
Chrome impersonation passes. Same situation as Vivid Racing. This adapter sets
``FETCHER_TIER = "tls"`` so the runner hands it a ``TlsFetcher``.

Parsing is microdata-driven — the site is a custom osCommerce-style storefront
and does **not** emit a JSON-LD ``Product`` block (only Organization + WebSite).
The product page exposes Schema.org itemprops directly:

- ``<span itemprop="name">`` — authoritative product name.
- ``<a itemprop="brand">Z1 Motorsports</a>`` — authoritative brand (most house
  items are "Z1 Motorsports"; third-party brands are linked the same way).
- ``<meta itemprop="sku" content=" 43428">`` — **Z1's internal product id**,
  matches the ``-p-<digits>`` portion of the URL. NOT a manufacturer part
  number; never written as ``part_number`` (same rule as vividracing).
- ``<span itemprop="price" content="1649.99">`` — current price (sale price
  when applicable — sits inside ``sp-newPrice``; the pre-sale ``sp-oldPrice``
  has no itemprop, so we don't accidentally pick it up).
- ``<div itemprop="description">`` — nested product HTML; normalized.
- Images: the primary product photo appears multiple times:
  - ``<meta itemprop="image" content="ss26_43428.jpg">`` (filename only).
  - ``<figure data-orig-img="https://cdn.z1motorsports.com/images/ss26_43428.jpg">``
    inside ``.product-img-gal-display``.
  - Gallery thumbnails under ``.product-img-gal-sel`` expose ``data-display-img``
    / ``data-zoom-img`` / ``data-small-img`` (all ``cdn.z1motorsports.com`` webp
    variants like ``thumbs/1200x900_<base>.webp``).
  Thumbnail filenames collapse to the same photo by stripping the ``<W>x<H>_``
  size prefix and the extension, so multi-resolution duplicates dedupe to one
  entry.

Discovery: ``/sitemap.xml`` is a flat urlset (no sitemap index). It mixes
category URLs (``-c-<digits>[_<digits>]*.html``) with a small set of product
URLs (``-p-<digits>.html``). We filter to the product suffix. The sitemap
contains a relatively small set of featured products (roughly 20s at time of
writing); category pages render their product grids client-side via JS and are
not walkable with a plain TLS fetcher, so full catalog discovery requires
either a browser or a supplementary source. For now the adapter ships what the
sitemap exposes and accepts a ``CRAWLER_Z1MOTORSPORTS_START_URLS``
(comma-separated) override for ad-hoc runs.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse, urlunparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    extract_part_number_candidate_from_title,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

Z1_BASE = "https://www.z1motorsports.com"
Z1_CDN_BASE = "https://cdn.z1motorsports.com"
SITEMAP_URL = Z1_BASE + "/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical product URL suffix: the last path segment is ``<slug>-p-<digits>.html``.
# The preceding path may be one or more category segments; we don't constrain it.
_PRODUCT_SUFFIX_RE = re.compile(r"/[a-z0-9][a-z0-9\-]*-p-(\d+)\.html$", re.IGNORECASE)

# Image URL filename tail: ``[<W>x<H>_]<base>.<ext>``. We dedupe by <base>
# so ``thumbs/200x150_ss26_46168.webp``, ``thumbs/1200x900_ss26_46168.webp``
# and ``images/ss26_46168.jpg`` collapse to the same photo identity.
_IMAGE_SIZE_PREFIX_RE = re.compile(r"^\d+x\d+_", re.IGNORECASE)

# Safe default so a fresh run can exercise parsing against a known product
# page even when sitemap discovery comes back empty. Override via
# ``CRAWLER_Z1MOTORSPORTS_START_URLS`` for ad-hoc runs.
DEFAULT_START_URLS = [
    "https://www.z1motorsports.com/big-brake-upgrades/z1-motorsports/z1-350z-g35-forged-street-big-brake-upgrade-front-and-rear-p-43428.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` has a ``.../<slug>-p-<digits>.html`` product suffix on the Z1 host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not host.endswith("z1motorsports.com"):
        return False
    path = parsed.path or ""
    return bool(_PRODUCT_SUFFIX_RE.search(path))


def _canonicalize_product_url(url: str) -> Optional[str]:
    """
    Normalize Z1 URLs to the canonical ``https://www.z1motorsports.com/...`` form
    (sitemap mixes ``http://z1motorsports.com`` and ``https://www.z1motorsports.com``
    prefixes). Drops the query string — product pages never take one on Z1.
    Returns None if the URL is not a Z1 product URL.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if not host.endswith("z1motorsports.com"):
        return None
    path = parsed.path or ""
    if not _PRODUCT_SUFFIX_RE.search(path):
        return None
    return urlunparse(("https", "www.z1motorsports.com", path, "", "", ""))


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_Z1MOTORSPORTS_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_Z1MOTORSPORTS_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _normalize_image_url(raw: str) -> Optional[str]:
    """
    Resolve a Z1 image URL to absolute form. The microdata ``itemprop="image"``
    value is often filename-only (``ss26_43428.jpg``) — we anchor those against
    the CDN base. Already-absolute ``https://cdn.z1motorsports.com/...`` URLs
    pass through unchanged.
    """
    s = raw.strip()
    if not s:
        return None
    if s.startswith("//"):
        return "https:" + s
    if s.startswith("http"):
        return s
    # Filename-only or a relative path — assume it lives under the CDN /images/ root.
    return f"{Z1_CDN_BASE}/images/{s.lstrip('/')}"


def _image_dedup_key(url: str) -> str:
    """
    Collapse multi-size variants of the same Z1 photo to one dedup key.

    Strips query string, drops a leading ``thumbs/`` path segment, removes the
    leading ``<W>x<H>_`` filename prefix, and drops the extension — so
    ``ss26_46168.jpg``, ``thumbs/200x150_ss26_46168.webp`` and
    ``thumbs/1200x900_ss26_46168.webp`` all key to ``ss26_46168``.
    """
    base = url.split("?", 1)[0]
    tail = base.rsplit("/", 1)[-1]
    tail = _IMAGE_SIZE_PREFIX_RE.sub("", tail)
    dot = tail.rfind(".")
    if dot > 0:
        tail = tail[:dot]
    return tail.lower()


def _is_noise_image(url: str) -> bool:
    """Reject logos, icons, banners, stock promo artwork that leak into the DOM."""
    low = url.lower()
    return bool(
        re.search(
            r"/logos?/|/icons?/|/models/|/modal/|/badges?/|logo|favicon|placeholder|-banner",
            low,
        )
    )


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    Collect product gallery URLs. Priority order, each deduped by photo identity:

    1. ``<meta itemprop="image">`` (filename-only; anchored to the CDN).
    2. ``.product-img-gal-display`` → ``<figure data-orig-img>`` (highest-quality jpg).
    3. ``.product-img-gal-sel`` thumbnails → ``data-zoom-img`` / ``data-display-img``
       / ``data-small-img`` (webp variants at successive resolutions).
    """
    ordered: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        normalized = _normalize_image_url(raw)
        if not normalized or _is_noise_image(normalized):
            return
        key = _image_dedup_key(normalized)
        if key in seen:
            return
        seen.add(key)
        ordered.append(normalized)

    meta_img = soup.find("meta", attrs={"itemprop": "image"})
    if isinstance(meta_img, Tag):
        content = meta_img.get("content")
        if isinstance(content, str):
            add(content)

    display = soup.find(class_=re.compile(r"product-img-gal-display"))
    if isinstance(display, Tag):
        for figure in display.find_all("figure"):
            if not isinstance(figure, Tag):
                continue
            for attr in ("data-orig-img", "data-zoom-img", "data-display-img"):
                v = figure.get(attr)
                if isinstance(v, str) and v.strip():
                    add(v)

    selector = soup.find(class_=re.compile(r"product-img-gal-sel"))
    if isinstance(selector, Tag):
        for figure in selector.find_all("figure"):
            if not isinstance(figure, Tag):
                continue
            for attr in ("data-zoom-img", "data-display-img", "data-small-img"):
                v = figure.get(attr)
                if isinstance(v, str) and v.strip():
                    add(v)
                    break

    return ordered[:12]


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """
    ``<span itemprop="name">`` inside the ``<h1>`` is authoritative; the
    ``<title itemprop="name">`` carries the same prose plus site chrome, so we
    prefer the span. No og:title is emitted on this theme.
    """
    span = soup.find("span", attrs={"itemprop": "name"})
    if isinstance(span, Tag):
        text = span.get_text(strip=True)
        if text:
            return text

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    return None


def _extract_brand(soup: BeautifulSoup) -> Optional[str]:
    """Read ``<a itemprop="brand">…</a>`` — Z1 tags the brand as a linked anchor."""
    tag = soup.find(attrs={"itemprop": "brand"})
    if not isinstance(tag, Tag):
        return None
    text = tag.get_text(strip=True)
    return text or None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    Read ``<span itemprop="price" content="1649.99">`` → 164999 cents. Only
    the current (sale-aware) ``sp-newPrice`` carries ``itemprop="price"`` —
    ``sp-oldPrice`` has no itemprop, so we won't accidentally pick up the
    strike-through figure.
    """
    tag = soup.find(attrs={"itemprop": "price"})
    if not isinstance(tag, Tag):
        return None
    content = tag.get("content")
    if isinstance(content, str) and content.strip():
        cents = parse_price_cents(content)
        if cents is not None:
            return cents
    text = tag.get_text(strip=True)
    return parse_price_cents(text) if text else None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Normalize the ``<div itemprop="description">`` body text (inline HTML preserved as plain text)."""
    block = soup.find(attrs={"itemprop": "description"})
    if not isinstance(block, Tag):
        return None
    text = block.get_text(separator=" ", strip=True)
    return normalize_description_text(text, max_len=2000)


class Z1MotorsportsAdapter(RetailerCrawlerAdapter):
    """
    Z1 Motorsports adapter.

    Fetcher tier: ``tls`` — Z1's Cloudflare posture blocks plain requests at
    the TLS handshake (``cf-mitigated: challenge``) but lets curl_cffi's
    Chrome impersonation through. See ``site_problem_notes/z1motorsports.md``.

    Discovery: ``CRAWLER_Z1MOTORSPORTS_START_URLS`` env var wins. Otherwise we
    walk ``/sitemap.xml`` via ``self.fetcher`` (so it goes through the TLS
    fetcher), keep URLs that match ``/<slug>-p-<digits>.html``, canonicalize
    them to the ``https://www.z1motorsports.com`` host, and fall back to
    ``DEFAULT_START_URLS`` when the sitemap returns nothing usable. The Z1
    sitemap is a flat urlset (no index) and exposes only a small featured-
    product subset — full catalog discovery is currently JS-gated and out of
    scope for a TLS-only fetcher.

    Parsing: microdata only (no JSON-LD Product block). We extract name, brand,
    price, description, and images from ``itemprop=*`` tags; the
    ``itemprop="sku"`` value is Z1's internal product id (matches the
    ``-p-<digits>`` in the URL) and is deliberately not emitted as
    ``part_number`` — same rule as Vivid Racing. A title-based part-number
    candidate is tried as a fallback.
    """

    ADAPTER_NAME: ClassVar[str] = "z1motorsports"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield canonical product URLs; env override wins when set."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                canonical = _canonicalize_product_url(url)
                if canonical:
                    yield canonical
            return

        for url in self._discover_via_sitemap() or list(DEFAULT_START_URLS):
            canonical = _canonicalize_product_url(url)
            if canonical:
                yield canonical

    def _discover_via_sitemap(self) -> List[str]:
        """
        Fetch ``/sitemap.xml`` via the adapter's fetcher and collect every
        ``/<slug>-p-<digits>.html`` URL. Returns [] on any failure (caller
        falls back to ``DEFAULT_START_URLS``). The sitemap is flat (urlset,
        not a sitemapindex).
        """
        seen: set[str] = set()
        product_urls: List[str] = []

        try:
            xml_text = self.fetcher.fetch(SITEMAP_URL, timeout=15)
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        for loc in _loc_elements(root):
            if not loc.text:
                continue
            raw = loc.text.strip()
            canonical = _canonicalize_product_url(raw)
            if not canonical:
                continue
            if canonical in seen:
                continue
            seen.add(canonical)
            product_urls.append(canonical)

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Z1 product page into a ``ScrapedPayload``. Returns ``None``
        when the URL isn't a Z1 product page or no name can be recovered.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        part_manufacturer = _extract_brand(soup)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(name)

        description = _extract_description(soup)
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=name)
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(name)

        # Z1's itemprop="sku" is the internal product id (matches -p-<N>.html),
        # not an MPN. Never write it as part_number. Fall back to a title-derived
        # candidate; leave part_number unset when no credible code is found.
        part_number = normalize_part_number(extract_part_number_candidate_from_title(name))

        price_cents = _extract_price_cents(soup)
        image_urls = _extract_images(soup)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
