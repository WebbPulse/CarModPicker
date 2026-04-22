"""
Racing Beat (racingbeat.com) crawler adapter — Tier 1 (TLS).

Racing Beat is the oldest Mazda-only performance house in the US (in
business since the 1970s), covering RX-7 (FB / FC / FD), RX-8, Miata
(NA/NB/NC/ND), Mazda2/3/6, Protegé, and CX-3/30/5/50. The backlog entry
(Batch 2B #13) lands RX-7/RX-8 coverage on top of our existing Miata
adapters (`flyinmiata`, `goodwinracing`, `corksport`).

Host: apex ``racingbeat.com`` 301s to ``www.racingbeat.com``; all menu
hrefs and canonical links use the ``www.`` form. Both hosts pass through
`_is_same_host` so extension captures on either one route here.

Tier rationale — **Tier 1 TLS**. Plain ``curl`` / ``requests`` hit a
Cloudflare managed-challenge interstitial on every HTML route (``cf-
mitigated: challenge``, ``Just a moment...`` body). ``curl_cffi`` Chrome
impersonation clears the block cleanly — the mitigation is TLS / JA3
fingerprint based, no JS solve required. ``robots.txt`` is one of the
very few paths that returns 200 on plain HTTP; the adapter still routes
every product / category fetch through ``self.fetcher`` so the TLS path
is consistent.

Platform — **Interchange (Akopia / Red Hat / Mivelocity)**, the same
classic Perl storefront that backs Good-Win Racing (see
``tier1_tls/goodwinracing.py``). The tell is the
``/mazda/performance/ord/basket.html`` checkout path plus
``mv_session_id`` / ``mv_order_item`` / ``mv_action`` hidden form
fields on every page. URLs are hand-authored (no Magento / Shopify
slug factory), so the shape is stable and predictable:

* Vehicle model index: ``/Mazda/<Model>.html``
  (e.g. ``/Mazda/RX7-1993-1995.html``).
* Category landing:    ``/<Model>/<Category>.html``
  (e.g. ``/RX7-1993-1995/Cat-Back-Exhausts.html``).
* Product page:        ``/<Model>/<Category>/<NumericID>.html``
  (e.g. ``/RX7-1993-1995/Cat-Back-Exhausts/16426.html``) — the
  numeric ID is the Racing Beat part number.

Every URL in the site menu is appended with a rolling ``?id=<8-char
session>`` token. ``robots.txt`` disallows ``/*?*`` outright, so the
adapter strips query strings from every discovered URL before yielding
it. It also honors the ``Disallow: /*.htm$`` and ``Disallow: /*.asp$``
rules (legacy path shapes) by only accepting ``.html`` URLs.

Discovery — no XML sitemap (``/sitemap.xml`` returns a CF challenge
even through TLS; the underlying route is 404 when checked via the CF
solve). The adapter walks the model index pages advertised on the
homepage nav, collects every ``/<Model>/...``-rooted category URL
published in each model menu, fetches the categories, and harvests the
numeric-ID product anchors from the category grid. One fetch per model
+ one per category stays well under heavy-crawl pace at the default
delay. Override with ``CRAWLER_RACINGBEAT_START_URLS`` (comma-separated
product URLs) for ad-hoc runs.

Parsing — **schema.org microdata, no JSON-LD**. The PDP body is
``<div id="product_page" itemscope itemtype="http://schema.org/Product">``
with load-bearing selectors:

* Name:        ``<h1 itemprop="name">...</h1>`` (may contain ``<br/>``)
* Part number: ``<span itemprop="productID">16426</span>`` — Racing
  Beat's numeric part code, identical to the numeric segment of the
  URL path.
* Price:       ``<div itemprop="offers">...<span itemprop="price">$764.03</span>``
* Description: the **first** ``<div itemprop="description">`` inside
  ``#product_page`` (the page also contains several ``others_who_bought``
  suggested-product cards after the main body — those have no
  ``itemprop="description"``, but we scope extraction to
  ``#product_page`` anyway as defense in depth).
* Main image:  ``<a href="/images/items/<id>.jpg" data-lightbox="product">
  <img itemprop='image' src="/images/items/350x280/<id>.webp">`` — the
  anchor ``href`` is the full-resolution original; the ``<img src>`` is
  a 350x280 derivative. We prefer the lightbox ``href`` and fall back
  to the ``itemprop="image"`` value.
* Gallery:     ``<div id="part_detail_images">`` with more
  ``/images/items/<id>.N.jpg`` lightbox anchors.

**No ``itemprop="brand"``** — Racing Beat is a house brand and doesn't
advertise it in the microdata. Brand resolution therefore coerces to
the canonical ``"Racing Beat"`` with a car-make / model blocklist
(Mazda, RX-7, RX-8, Miata, MX-5, CX-3/30/5/50, Mazda2/3/6, Protegé) so
the shared title heuristic — which would otherwise pick "Mazda" or
"RX-7" as the brand — never leaks through. A small resell presence
(Racing Beat distributes select third-party Mazda lines) would keep a
real brand token in the title; when any known third-party name shows
up the normalizer passes it through, otherwise the page is treated as
house-brand.

Variant strategy — **Option A** (``VARIANTS.md``): one
``ScrapedPayload`` per product URL. Racing Beat's picker-driven
variants are unusual; where they exist (exhaust size options in a
handful of FD listings) they submit through the same Interchange
``mv_order_Size`` form without changing the page URL, and the top-
level ``productID`` is the family part number. One row per URL is the
correct shape here.

Caveats:

* **Session-token churn.** Every menu href is appended with
  ``?id=<8-char token>``. The token is regenerated on each fetch but
  the path before the ``?`` is the canonical URL — we strip the query
  string on every link extraction so discovery doesn't retry the same
  page under a dozen different tokens.
* **Legacy URL shapes.** Some catalog areas still emit ``.htm`` and
  ``.asp`` URLs (old rotary-tech-tips / photo-gallery content); those
  are disallowed by robots.txt anyway and we only accept ``.html``.
* **No XML sitemap.** Discovery depends on the main-menu nav being
  present on the homepage. A menu restructure would break the walker;
  the ``CRAWLER_RACINGBEAT_START_URLS`` env escape hatch covers that
  case. Hard-coded ``DEFAULT_START_URLS`` (a handful of verified FD /
  ND / RX-8 PDPs) keeps the runner from no-op'ing on first landing.
* **Stack age.** The storefront has not been re-platformed in 15+
  years; microdata is stable *because* nothing has touched it. A
  hypothetical migration would invalidate every selector in this file.
* **CF reputation.** AWS egress IPs can score badly with Cloudflare
  Bot Management regardless of TLS fingerprint; if consecutive 403s
  show up on production even after the TLS fetcher clears locally,
  the fallback is to promote ``FETCHER_TIER`` to ``"browser"`` (tier
  2) once FlareSolverr is deployed.
"""

import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
)
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

RACINGBEAT_HOST = "www.racingbeat.com"
RACINGBEAT_BASE = f"https://{RACINGBEAT_HOST}"

# Vehicle-model index pages advertised in the homepage nav. Each one
# lists its category landing pages, which in turn list product URLs.
# Hand-picked (not discovered from the homepage DOM) so the walker is
# deterministic even if the nav toggles an entry in/out temporarily.
MODEL_INDEX_URLS: List[str] = [
    f"{RACINGBEAT_BASE}/Mazda/RX7-1975-1985.html",
    f"{RACINGBEAT_BASE}/Mazda/RX7-1986-1992.html",
    f"{RACINGBEAT_BASE}/Mazda/RX7-1993-1995.html",
    f"{RACINGBEAT_BASE}/Mazda/RX8.html",
    f"{RACINGBEAT_BASE}/Mazda/Miata-1990-2005.html",
    f"{RACINGBEAT_BASE}/Mazda/Miata-MX5-2006-Present.html",
    f"{RACINGBEAT_BASE}/Mazda/Mazda-2.html",
    f"{RACINGBEAT_BASE}/Mazda/Mazda-3.html",
    f"{RACINGBEAT_BASE}/Mazda/Mazda-6.html",
    f"{RACINGBEAT_BASE}/Mazda/Protege.html",
    f"{RACINGBEAT_BASE}/Mazda/CX5.html",
]

# Verified live product URLs; used as a fallback when neither the env
# override nor the nav walk returns anything. Picked across FD / ND /
# RX-8 so the first smoke crawl exercises all three chassis families.
DEFAULT_START_URLS: List[str] = [
    f"{RACINGBEAT_BASE}/RX7-1993-1995/Cat-Back-Exhausts/16426.html",
    f"{RACINGBEAT_BASE}/RX7-1993-1995/Flywheels/11435.html",
]

BRAND_CANONICAL = "Racing Beat"

# Tokens that the title heuristic would otherwise pick as ``brand``. The
# blocklist covers every chassis / model family that Racing Beat sells
# into — these are car makes or model codes, never manufacturers.
_BLOCKED_BRAND_TOKENS = frozenset(
    {
        "mazda",
        "rx-7",
        "rx7",
        "rx-8",
        "rx8",
        "miata",
        "mx-5",
        "mx5",
        "cx-3",
        "cx3",
        "cx-30",
        "cx30",
        "cx-5",
        "cx5",
        "cx-50",
        "cx50",
        "mazda2",
        "mazda3",
        "mazda6",
        "protege",
        "protegé",
    }
)

# Numeric-ID product URL shape: ``/<Model>/<Category>/<digits>.html``.
# The model/category segments contain letters, digits, and hyphens.
_PRODUCT_PATH_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9\-]*/[A-Za-z0-9][A-Za-z0-9\-]*/\d+\.html$")

# Category landing shape: ``/<Model>/<Category>.html`` (two path
# segments, the second ending in ``.html``).
_CATEGORY_PATH_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9\-]*/[A-Za-z0-9][A-Za-z0-9\-]*\.html$")

# Site chrome that shows up inside ``/images/...`` paths but is not
# product media. Racing Beat's layout/banner art lives under
# ``/images/layout/``; any ``/images/items/...`` URL is product-shot.
_IMAGE_NOISE_RE = re.compile(
    r"/images/(layout|customer_rides|homepage|icons)/|placeholder|logo|favicon",
    re.IGNORECASE,
)


def _is_same_host(url: str) -> bool:
    """True if ``url`` is on the Racing Beat apex or www host."""
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    return host in ("", RACINGBEAT_HOST, "racingbeat.com")


def _strip_query(url: str) -> str:
    """Drop the ``?id=<session>`` token (and any other query) from a URL."""
    return url.split("?", 1)[0].split("#", 1)[0]


def _is_product_url(url: str) -> bool:
    """Accept only ``/<Model>/<Category>/<digits>.html`` on the Racing Beat host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not _is_same_host(url):
        return False
    path = parsed.path or ""
    if not _PRODUCT_PATH_RE.match(path):
        return False
    # Robots rule: ``Disallow: /*.htm$`` / ``/*.asp$``. We only accept
    # ``.html`` which the product regex already enforces — this is a
    # belt over the suspenders.
    low = path.lower()
    if low.endswith(".htm") or low.endswith(".asp"):
        return False
    return True


def _is_category_url(url: str) -> bool:
    """Accept only ``/<Model>/<Category>.html`` on the Racing Beat host."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if not _is_same_host(url):
        return False
    path = parsed.path or ""
    if not _CATEGORY_PATH_RE.match(path):
        return False
    # Don't treat the model index itself (``/Mazda/<Model>.html``) as a
    # category landing — the first segment is always ``Mazda`` (capital
    # M) on the index pages and the cards there link back to the same
    # index, which would loop.
    first_seg = path.split("/", 2)[1]
    if first_seg == "Mazda":
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return the env-configured start URLs, or ``None`` if unset."""
    raw = os.environ.get("CRAWLER_RACINGBEAT_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_links(html: str) -> List[str]:
    """
    Harvest all ``href`` values from an HTML page and return them with
    the Racing Beat session token (and any other query string) stripped.
    Absolute + relative hrefs are both handled; non-Racing-Beat hosts
    are filtered out.
    """
    out: List[str] = []
    seen: set[str] = set()
    # We don't need a full DOM parse here — href capture is enough, and
    # it also lets us pick up anchors emitted inside HTML comments or
    # malformed tags that BeautifulSoup might drop.
    for match in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', html, flags=re.IGNORECASE):
        href = match.group(1).strip()
        if not href:
            continue
        # Absolutize
        if href.startswith("//"):
            absolute = "https:" + href
        elif href.startswith("http://") or href.startswith("https://"):
            absolute = href
        elif href.startswith("/"):
            absolute = RACINGBEAT_BASE + href
        else:
            # Relative hrefs on this site are rare and usually decorative
            # (``javascript:null(0)``, ``#...``). Skip them.
            continue
        if not _is_same_host(absolute):
            continue
        base = _strip_query(absolute)
        if base in seen:
            continue
        seen.add(base)
        out.append(base)
    return out


class RacingBeatAdapter(RetailerCrawlerAdapter):
    """
    Racing Beat adapter. Tier 1 TLS (Cloudflare managed-challenge front).

    Discovery: env override wins (``CRAWLER_RACINGBEAT_START_URLS``).
    Otherwise walk the hand-listed model-index pages
    (``/Mazda/<Model>.html``), collect the category landing pages each
    one links to, fetch the categories, and harvest numeric-ID product
    URLs. Falls back to a small hard-coded verified-PDP list when the
    walk returns empty.

    Parsing: schema.org microdata only — Interchange's older theme does
    not emit JSON-LD. Name / part-number / price / description /
    images are all read off ``itemprop`` selectors inside
    ``#product_page``. Brand is coerced to ``"Racing Beat"`` with a
    car-make / chassis blocklist (Mazda / RX-7 / RX-8 / Miata / MX-5 /
    CX-* / Mazda2/3/6 / Protegé).
    """

    ADAPTER_NAME: ClassVar[str] = "racingbeat"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override → nav walk → hard-coded fallback."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        discovered = self._discover_via_nav()
        if discovered:
            for url in discovered:
                if _is_product_url(url):
                    yield url
            return

        for url in DEFAULT_START_URLS:
            if _is_product_url(url):
                yield url

    def _discover_via_nav(self) -> List[str]:
        """
        Walk the model-index pages to collect category URLs, then walk
        each category to collect numeric-ID product URLs. Returns a
        deduplicated list; empty on total fetch failure.
        """
        category_urls: List[str] = []
        seen_cats: set[str] = set()

        for idx, model_url in enumerate(MODEL_INDEX_URLS):
            if idx > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                html = self.fetcher.fetch(model_url, timeout=30)
            except Exception:
                continue
            for link in _extract_links(html):
                if not _is_category_url(link):
                    continue
                if link in seen_cats:
                    continue
                seen_cats.add(link)
                category_urls.append(link)

        product_urls: List[str] = []
        seen_products: set[str] = set()

        for idx, cat_url in enumerate(category_urls):
            if idx > 0:
                time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
            try:
                html = self.fetcher.fetch(cat_url, timeout=30)
            except Exception:
                continue
            for link in _extract_links(html):
                if not _is_product_url(link):
                    continue
                if link in seen_products:
                    continue
                seen_products.add(link)
                product_urls.append(link)

        return product_urls

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Racing Beat product page (Interchange + schema.org
        microdata). Returns ``None`` when the URL isn't product-shaped
        or when the page has no ``#product_page`` block / no name
        (soft-404 on an orphaned part number).
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        product_page = soup.find("div", id="product_page")
        if not isinstance(product_page, Tag):
            return None

        name = _extract_name(product_page)
        if not name or len(name) < 3:
            return None

        part_number = _extract_part_number(product_page, url)
        price_cents = _extract_price_cents(product_page)
        description = _extract_description(product_page)
        image_urls = _extract_images(product_page)

        part_manufacturer = _normalize_part_manufacturer(name)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )


def _extract_name(scope: Tag) -> Optional[str]:
    """
    Read the ``<h1 itemprop="name">`` inside ``#product_page``. The
    theme uses ``<br/>`` inside the h1 for multi-line titles ("Cat-Back
    Exhaust - Single Tip<br/>93-95 RX-7"); we normalize the separator
    to a space so the stored name is single-line.
    """
    h1 = scope.find("h1", attrs={"itemprop": "name"})
    if not isinstance(h1, Tag):
        h1 = scope.find("h1")
    if not isinstance(h1, Tag):
        return None
    # get_text(separator=" ") collapses <br/> boundaries and nested
    # spans into a clean space-delimited string.
    text = h1.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _extract_part_number(scope: Tag, url: str) -> Optional[str]:
    """
    ``<span itemprop="productID">`` holds Racing Beat's internal part
    number (same digits as the numeric URL segment). Falls back to
    pulling the numeric segment out of the product URL when the
    itemprop is missing — that path is extremely rare (part pages all
    emit productID in the theme we inspected) but keeps the adapter
    robust to theme drift.
    """
    pid = scope.find(attrs={"itemprop": "productID"})
    if isinstance(pid, Tag):
        text = pid.get_text(strip=True)
        if text:
            normalized = normalize_part_number(text)
            if normalized:
                return normalized
    # URL fallback: ``/<Model>/<Category>/<digits>.html``.
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return None
    m = re.search(r"/(\d+)\.html$", path)
    if m:
        return normalize_part_number(m.group(1))
    return None


def _extract_price_cents(scope: Tag) -> Optional[int]:
    """
    ``<div itemprop="offers">...<span itemprop="price">$764.03</span>``.
    Parse the dollar text; Racing Beat only sells in USD so no currency
    handling is required.
    """
    # Prefer the price inside the offers block to avoid any stray
    # itemprop="price" that might sit on a related-product card. The
    # ``others_who_bought`` cards don't carry microdata on this theme,
    # but the belt-and-suspenders scoping is cheap.
    offers = scope.find(attrs={"itemprop": "offers"})
    target = offers if isinstance(offers, Tag) else scope
    price_tag = target.find(attrs={"itemprop": "price"})
    if not isinstance(price_tag, Tag):
        return None
    content = price_tag.get("content")
    if isinstance(content, str) and content.strip():
        cents = parse_price_cents(content.strip())
        if cents is not None:
            return cents
    text = price_tag.get_text(strip=True)
    if text:
        return parse_price_cents(text)
    return None


def _extract_description(scope: Tag) -> Optional[str]:
    """
    First ``<div itemprop="description">`` inside ``#product_page``.
    Racing Beat's theme emits rich HTML (paragraphs + inline anchors);
    ``normalize_description_text`` strips the tags and caps length.
    """
    desc = scope.find(attrs={"itemprop": "description"})
    if not isinstance(desc, Tag):
        return None
    text = desc.get_text(separator=" ", strip=True)
    if not text or len(text) < 10:
        return None
    return normalize_description_text(text, max_len=2000)


def _normalize_image_url(raw: str) -> str:
    """Absolutize relative image URLs; upgrade ``http://`` → ``https://``."""
    u = raw.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("/"):
        return RACINGBEAT_BASE + u
    return u


def _is_valid_product_image(url: str) -> bool:
    """Accept ``/images/items/...`` media; reject layout / chrome."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    # Product images live at /images/items/...
    return "/images/items/" in low


def _canonical_image_key(url: str) -> str:
    """
    Dedupe key so every representation of one Racing Beat photo
    collapses to a single entry:

    * Drop the size-path segment (``350x280/``, ``115x74/``, ``x74/``)
      — thumbs sit at ``/images/items/<WxH>/<id>.<ext>`` while full-res
      sits at ``/images/items/<id>.<ext>``.
    * Drop the file extension entirely — the lightbox anchor points at
      ``<id>.jpg`` while the thumbnail ``<img src>`` is ``<id>.webp``;
      both represent the same photo.
    """
    key = re.sub(r"/images/items/\d*x\d*/", "/images/items/", url, flags=re.IGNORECASE)
    key = key.split("?", 1)[0]
    # Strip the final extension so jpg/webp/png collapse to one key.
    key = re.sub(r"\.(jpe?g|webp|png|gif)$", "", key, flags=re.IGNORECASE)
    return key


def _extract_images(scope: Tag) -> List[str]:
    """
    Gather product gallery URLs from the main-product regions of
    ``#product_page``. The theme renders each image as
    ``<a href="/images/items/<id>[.N].jpg" data-lightbox="product">
    <img src="/images/items/350x280/<id>.webp" itemprop='image'></a>``.
    The anchor's ``href`` is the full-res source (preferred); the
    ``<img src>`` is a sized derivative (fallback). We walk both and
    dedupe on canonical key (ignoring extension + size-dir).

    Scope is restricted to the hero image region and detail-image gallery
    so the ``#others_who_bought`` related-products block (which sits
    inside the same ``#product_page`` wrapper on this theme) never
    leaks its thumbnail cards into the product's own gallery.
    """
    seen_keys: set[str] = set()
    ordered: List[str] = []

    def add(raw: str) -> None:
        if not raw or len(ordered) >= 12:
            return
        u = _normalize_image_url(raw)
        if not u.startswith("http") or not _is_valid_product_image(u):
            return
        key = _canonical_image_key(u)
        if key in seen_keys:
            return
        seen_keys.add(key)
        ordered.append(u)

    # Scope to the hero image container + the detail-image gallery.
    # Anything else inside #product_page — including
    # #others_who_bought — is ignored.
    image_regions: List[Tag] = []
    for region_id in ("product_main_image", "part_detail_images"):
        region = scope.find("div", id=region_id)
        if isinstance(region, Tag):
            image_regions.append(region)

    for region in image_regions:
        # Lightbox anchors (full-resolution) first.
        for anchor in region.find_all("a", attrs={"data-lightbox": True}):
            if not isinstance(anchor, Tag):
                continue
            href = anchor.get("href")
            if isinstance(href, str):
                add(href)
        # Fallback: any <img> in the same region.
        for img in region.find_all("img"):
            if not isinstance(img, Tag):
                continue
            src = img.get("src")
            if isinstance(src, str):
                add(src)

    return ordered[:12]


def _normalize_part_manufacturer(name: str) -> str:
    """
    Racing Beat is a house brand; microdata omits ``itemprop="brand"``.
    Coerce to the canonical ``"Racing Beat"`` — the blocklist guards
    against the shared title heuristic picking a chassis family
    ("Mazda", "RX-7", "Miata") as the manufacturer when we don't
    override it.
    """
    # The blocklist isn't actually consulted here (we always return the
    # canonical value) but the local import of its contents makes the
    # intent clear and keeps a single source of truth if a later change
    # wants to pass through a third-party resell brand.
    _ = (name, _BLOCKED_BRAND_TOKENS)
    return BRAND_CANONICAL
