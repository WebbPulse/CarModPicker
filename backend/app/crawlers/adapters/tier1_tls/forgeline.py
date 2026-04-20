"""
Forgeline (forgeline.com) crawler adapter — Tier 1 (TLS).

Forgeline is the US-forged wheel reference for high-end track/street builds
(C7/C8 Corvette, GT3, Viper, GT500, R35). $3k–$8k wheel sets put it on the
same domestic-forged shelf as HRE, complementing Mackin's JDM-forged coverage
(RAYS, Advan). See ``adapters/RETAILER_BACKLOG.md`` for backlog placement.

Product URLs: ``https://www.forgeline.com/<slug>/p<id>``. The slug is the
model code (``al304``, ``cf202``, ``ga1r``) for wheels and a
descriptive name for accessories (``3-ear-billet-push-in-cap``,
``beadlock-ring``, ``anthracite``). Categories live at ``/<slug>/c<id>``
and are skipped. The slug is **not** authoritative — at least one URL
(``/ga1r/p3``) renders a different model's page (CF206), so trust the
parsed page content over the URL slug.

Fetcher tier: Cloudflare 403s plain HTTP at the TLS handshake (``Attention
Required! | Cloudflare`` interstitial). curl_cffi Chrome impersonation
clears both the sitemap and product fetches, same posture as Vivid Racing /
Cobb Tuning / Mackin. ``FETCHER_TIER = "tls"``.

Parsing: no JSON-LD ``Product`` block — the site is a custom CMS that emits
only OpenGraph + a marketing template. Strategy:

- **name** — ``og:title`` (clean "MODEL | Description" form, e.g.
  ``"AL304 | Three Piece Forged Wheel"``). Falls back to
  ``h1.product_title`` (the model code alone, e.g. ``"AL304"``) when
  og:title is missing.
- **description** — ``og:description`` / meta description, normalized.
- **price_cents** — first ``<h1 class="total_price">`` in the DOM. Wheel
  pages render a "From $X" prefix because per-wheel pricing varies by
  finish; accessories render a flat ``$X``. Both parse cleanly through
  ``parse_price_cents`` which strips the prefix.
- **part_number** — explicit ``Part # XXX`` text on the page (accessories
  always carry it embedded in the heading) wins. Otherwise the
  ``h1.product_title`` model code is used when it looks like an actual SKU
  (uppercase alphanumeric, no whitespace) — for wheels this gives the
  industry-standard model code (AL304, CF202, GA1R) which IS how Forgeline
  itself refers to the part.
- **part_manufacturer** — always ``Forgeline``. Direct manufacturer site,
  no resold lines.
- **image_urls** — ``og:image`` first, then ``<img src>`` under
  ``/product_images/forgeline/``. Filenames containing ``-title-`` are
  category/series banners (``monoblock-title-1869-v2.webp``) and are
  filtered out. Deduped by filename stem with the size suffix
  (``-medium_image-WxH``, ``-large-XXX-vN``) stripped, capped at 12.
"""

import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

FORGELINE_HOST = "www.forgeline.com"
FORGELINE_BASE = f"https://{FORGELINE_HOST}"
SITEMAP_URL = f"{FORGELINE_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Product URLs are ``/<slug>/p<digits>``. Categories are ``/<slug>/c<digits>``
# — the ``c`` shape is rejected here so category landing pages don't enter
# the parse pipeline. Trailing slash is optional; the sitemap emits both.
_PRODUCT_PATH_RE = re.compile(r"^/[a-z0-9][a-z0-9\-]*/p\d+/?$", re.IGNORECASE)

# ``Part # CAP3EAR-POL-ENG-OPTION`` style; match runs of uppercase, digits,
# and dash/underscore/slash so kebab-style SKUs survive intact.
_PART_NUMBER_INLINE_RE = re.compile(
    r"Part\s*#\s*([A-Z0-9][A-Z0-9\-_/]+)",
    re.IGNORECASE,
)

# Forgeline model codes are short alphanumeric tokens (AL304, CF202, GA1R,
# CF1R, ZX3P). Use the h1 product_title as a part_number fallback only when
# it looks like one of these — accessory headings often include marketing
# copy and a "Part #" suffix that the inline-regex above already caught.
_MODEL_CODE_RE = re.compile(r"^[A-Z][A-Z0-9]{1,9}$")

# Category/series banner filename marker. The site reuses a "View other
# series" rail at the bottom of every product page, pulling banner artwork
# named like ``monoblock-title-1869-v2.webp``. The ``-title-`` infix is the
# stable signal — real product images use ``-large-...``, ``-medium_image-WxH``,
# or no suffix at all.
_CATEGORY_BANNER_RE = re.compile(r"-title-\d", re.IGNORECASE)

# Strip Forgeline's CDN size suffixes when computing the dedup key. Two
# patterns cover the live catalog: ``-medium_image-365x365`` (gallery
# thumbs) and ``-large-<seq>-v<n>`` (lightbox originals).
_IMAGE_SIZE_SUFFIX_RE = re.compile(
    r"-(?:medium_image-\d+x\d+|large-\d+-+v\d+)(?=\.[A-Za-z]+$)",
    re.IGNORECASE,
)

# Forgeline product image hosting path. Anything outside this prefix is
# either a category banner inline asset or unrelated theme art.
_PRODUCT_IMAGE_PATH = "/product_images/forgeline/"

# Smoke-test seed: AL304 is a current high-volume forged wheel with a clean
# price ($1830.00 starting) and the standard wheel-template DOM.
DEFAULT_START_URLS = [
    "https://www.forgeline.com/al304/p108",
]


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` is a Forgeline product URL (``/<slug>/p<id>``).

    Accepts both ``www.forgeline.com`` (sitemap canonical) and bare
    ``forgeline.com`` (the bare host serves identical content) so that
    URLs captured via the Chrome extension match regardless of which form
    the user visited.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "forgeline.com" and not host.endswith(".forgeline.com"):
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_FORGELINE_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_FORGELINE_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """``og:title`` (full "MODEL | Description") then ``h1.product_title`` (model only)."""
    og = soup.find("meta", property="og:title")
    if isinstance(og, Tag):
        v = meta_content(og)
        if v and v.strip():
            return v.strip()
    h1 = soup.find("h1", class_="product_title")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """``og:description`` first, then meta description. Both carry the marketing copy."""
    for selector in (("meta", {"property": "og:description"}), ("meta", {"name": "description"})):
        tag_name, attrs = selector
        meta = soup.find(tag_name, attrs=attrs)
        if isinstance(meta, Tag):
            v = meta_content(meta)
            if v and v.strip():
                normalized = normalize_description_text(v, max_len=2000)
                if normalized:
                    return normalized
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    First ``<h1 class="total_price">`` text, parsed through ``parse_price_cents``.
    Wheel pages prefix with ``From `` (per-wheel base price); accessories
    print a flat ``$X``. Both forms parse cleanly. Returns None when the
    page renders no price node — Forgeline does this for finishes and a
    handful of configurator-only options.
    """
    el = soup.select_one("h1.total_price")
    if not isinstance(el, Tag):
        return None
    text = el.get_text(strip=True)
    if not text:
        return None
    return parse_price_cents(text)


def _extract_part_number(soup: BeautifulSoup) -> Optional[str]:
    """
    Explicit ``Part # XXX`` token (accessories embed it in the H1) wins.
    Otherwise fall back to ``h1.product_title`` when it looks like a model
    code (AL304, CF202, GA1R). Wheel pages don't expose a separate SKU
    field, but the model code IS how Forgeline references the part across
    its catalog and printed materials.
    """
    h1 = soup.find("h1", class_="product_title")
    h1_text = h1.get_text(separator=" ", strip=True) if isinstance(h1, Tag) else ""

    match = _PART_NUMBER_INLINE_RE.search(h1_text or "")
    if not match:
        match = _PART_NUMBER_INLINE_RE.search(soup.get_text(separator=" ", strip=False))
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return normalize_part_number(candidate)

    if h1_text:
        # The H1 may contain the embedded "Part # …" we already failed to
        # match (different separator chars); strip that suffix before the
        # model-code check so accessories don't pollute it.
        head = re.split(r"Part\s*#", h1_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if _MODEL_CODE_RE.match(head):
            return normalize_part_number(head)
    return None


def _image_dedup_key(url: str) -> str:
    """
    Collapse Forgeline's CDN size variants. ``foo-large-108--v1.webp``,
    ``foo-medium_image-365x365.png`` and ``foo.png`` all key to ``foo``.
    Query string stripped first.
    """
    base = url.split("?", 1)[0]
    tail = base.rsplit("/", 1)[-1]
    tail = _IMAGE_SIZE_SUFFIX_RE.sub("", tail)
    dot = tail.rfind(".")
    if dot > 0:
        tail = tail[:dot]
    return tail.lower()


def _normalize_image_url(raw: str) -> Optional[str]:
    """Resolve protocol-relative / site-root URLs to absolute https URLs."""
    u = raw.strip()
    if not u:
        return None
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = FORGELINE_BASE + u
    if not u.startswith("http"):
        return None
    return u


def _extract_images(soup: BeautifulSoup) -> List[str]:
    """
    og:image hero first, then any ``<img src>`` under ``/product_images/
    forgeline/`` that isn't a category banner (``-title-`` infix). Deduped
    by filename stem so per-finish thumbnails of the same shot collapse to
    one entry. Capped at 12.
    """
    seen: set[str] = set()
    ordered: List[str] = []

    def add(raw: Optional[str]) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u:
            return
        path_only = urlparse(u).path or ""
        if _PRODUCT_IMAGE_PATH not in path_only:
            return
        if _CATEGORY_BANNER_RE.search(path_only):
            return
        key = _image_dedup_key(u)
        if key in seen:
            return
        seen.add(key)
        ordered.append(u)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    for img in soup.find_all("img"):
        if not isinstance(img, Tag) or len(ordered) >= 12:
            break
        for attr in ("src", "data-src"):
            val = img.get(attr)
            if isinstance(val, str):
                add(val)
                break

    return ordered[:12]


class ForgelineAdapter(RetailerCrawlerAdapter):
    """
    Forgeline adapter.

    Fetcher tier: ``tls`` — Cloudflare blocks plain HTTP at the TLS
    fingerprint check (403 ``Attention Required!``). curl_cffi Chrome
    impersonation clears both sitemap and product page fetches.

    Discovery: walk ``/sitemap.xml`` (a flat urlset, not an index) and keep
    URLs matching ``/<slug>/p<id>``. The sitemap mixes products with blog
    posts, location pages, and category landings; the path regex filters
    cleanly. ``CRAWLER_FORGELINE_START_URLS`` env override available for
    ad-hoc runs.

    Parsing: DOM-only — Forgeline emits no JSON-LD Product block. og:title
    for name, ``h1.total_price`` for price (``From $X`` for wheels, ``$X``
    flat for accessories), explicit ``Part #`` token or model code from
    ``h1.product_title`` for part_number, and og:image plus product_images/
    forgeline/ ``<img>`` sweep with ``-title-`` banner filter for gallery.
    Manufacturer is always Forgeline (direct site).
    """

    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Env override wins, then sitemap walk, then DEFAULT_START_URLS."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in self._discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def _discover_via_sitemap(self) -> List[str]:
        """
        Fetch the flat ``/sitemap.xml`` urlset via the TLS fetcher and return
        every ``<loc>`` whose path matches the product shape. Empty list on
        any fetch/parse failure.
        """
        try:
            xml_text = self.fetcher.fetch(SITEMAP_URL, timeout=30)
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        seen: set[str] = set()
        product_urls: List[str] = []
        for loc in root.findall(f".//{{{SITEMAP_NS}}}loc"):
            if not loc.text:
                continue
            u = loc.text.strip()
            if not _is_product_url(u) or u in seen:
                continue
            seen.add(u)
            product_urls.append(u)
        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Forgeline product page. Returns None when the URL isn't
        product-shaped or no name surfaces (e.g. a category page captured
        by mistake).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 2:
            return None

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=_extract_description(soup),
            price_cents=_extract_price_cents(soup),
            part_manufacturer="Forgeline",
            part_number=_extract_part_number(soup),
            image_urls=_extract_images(soup) or None,
        )
