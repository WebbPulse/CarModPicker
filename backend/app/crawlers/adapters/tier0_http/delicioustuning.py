"""
Delicious Tuning (delicioustuning.com) crawler adapter.

Platform: **Drupal 7 + Ubercart** (``X-Powered-By: PleskLin``,
``X-Drupal-Cache``, Ubercart ``uc-*`` CSS classes all over product DOM). The
apex ``delicioustuning.com`` 301s to ``www.delicioustuning.com``; all
canonical URLs and menu hrefs use the ``www.`` form. Plain ``requests``
returns fully-rendered HTML — no Cloudflare / JS-challenge layer — so
``FETCHER_TIER`` stays at the default ``"http"``.

Product URLs: Ubercart nodes exposed both as Drupal path-aliases
(``/86AOS``, ``/flexfuel``, ``/V3_FlexFuel_Kit``) and as raw node paths
(``/node/958``). The page-level ``<link rel="canonical">`` always points at
the path-alias when one exists, so we store whichever URL we were asked
to parse.

**No JSON-LD, no OG meta.** Unlike every Shopify / Magento / WooCommerce
adapter in the tree, this site emits zero schema.org markup on product
pages — no ``application/ld+json`` script, no ``og:title`` /
``og:description``, no ``product:price:amount``. That is the key
platform-first for this adapter: parsing is **pure Ubercart DOM**.

DOM contract we rely on (verified live 2026-04-21):

* Title — ``<h1 class="title" id="page-title">``.
* SKU — ``<div class="product-info model"> … <span
  class="product-info-value">DT_XXX_YYY</span>``. Own-brand parts use a
  ``DT_`` prefix (``DT_BRZ1_AOS_V010``, ``DT_SUB1_COIL_R650``); the small
  number of resold SKUs keep their native code. Both shapes go through
  ``normalize_part_number`` unchanged.
* Price — the *sell* price sits in ``<div class="product-info
  sell-price"><span class="uc-price">$X.XX</span>``. There is frequently
  also a ``<div class="product-info list-price">`` block (MSRP); we
  ignore it and take the sell-price block. Fallback: first ``.uc-price``
  anywhere in the product-info region.
* Description — ``<div class="field field-name-body">`` — HTML-rich; we
  feed it through ``normalize_description_text`` which unwraps tags and
  caps length.
* Images — ``<div class="field field-name-uc-product-image"> …
  <li><img src="…/sites/default/files/styles/medium__200x200_/public/…">``.
  The ``styles/<style>/public/`` path segment is Drupal's on-the-fly
  image-style derivative; the full-resolution original lives at
  ``/sites/default/files/<basename>`` (drop the ``styles/<style>/public/``
  prefix and the ``?itok=…`` query). We canonicalise to that full-res
  URL so recrawls dedupe and so downstream consumers aren't locked to a
  Drupal thumbnail size.

Discovery: no sitemap.xml (``/sitemap.xml``, ``/sitemap``, and
``/sitemap.xml.gz`` all 404). Instead, we walk the leaf catalog categories
advertised by the main-menu structure (``/catalog/<NNN>`` under Infiniti
/ Mazda / Mitsubishi / Nissan / Scion / Subaru / Toyota / Apparel).
Some catalog pages are pure subcategory landings (``/catalog/42`` shows
"Complete Packages / Parts & Accessories / Tunes & Services" cards), so
the discovery walker recurses one level: it scrapes product anchors off
a page *and* follows inner ``/catalog/<NNN>`` links for a second pass.
Product anchors are identified as ``<h3>``-wrapped links that sit next
to a ``<span class="uc-price">`` row — that's the Views ``uc_catalog``
grid shape — so subcategory card anchors (which have no price) don't
leak in. Set ``CRAWLER_DELICIOUSTUNING_START_URLS`` (comma-separated) to
override discovery with a fixed product-URL list.

Brand rule: Delicious Tuning is a **house brand** (own-design AOS, flex
fuel kits, coil packs, CAN-bus hardware). Titles routinely lead with a
chassis/model token ("BRZ/FRS/86 - Air / Oil Separator", "Delicious
OEM+ (4) Coil Packs - MY13-14 (Red)") rather than the brand itself, so
the shared title heuristic trips on car makes. Following the
``VARIANTS.md`` house-brand pattern (same shape as GrimmSpeed): pass
JSON-LD brand through unchanged when non-empty (reserved for any future
resell SKUs), coerce empty / car-make / self-variant values to the
canonical ``"Delicious Tuning"``. The car-make blocklist includes the
chassis families this site targets — Subaru, Toyota, Scion, Mazda,
Mitsubishi, Nissan, Infiniti, BMW.

Variant strategy: one ``ScrapedPayload`` per product URL (Option A in
``VARIANTS.md``). A few DT pages do offer picker-driven variants (e.g.
coil-pack colour), but each variant keeps the same DT-prefixed SKU on
the DOM — the picker drives an ``uc_product_adjustments`` ajax call, not
a separate canonical URL — so per-URL scraping captures the listed SKU
regardless of picker state.

Tier rationale: plain HTTP works first-try (``curl -sI`` returns 200 with
a fully rendered product page). No Cloudflare, no JS challenge, no TLS
fingerprint block. Robots.txt advertises ``Crawl-delay: 10`` — the
shared runner honors that automatically via the larger-of(``--delay``,
robots ``Crawl-delay``) rule, so per-request pacing stays polite without
extra adapter work.

Caveats:
* **Stack age.** The server advertises ``X-Powered-By: PHP/5.6.40`` and
  serves Drupal 7 with the jQuery 1.7.2 bundle. This site has not been
  re-platformed in ~a decade. The DOM shape is stable *because* nothing
  has touched it; a future migration to Shopify (several of the company's
  peers have gone this route) would invalidate every selector below.
* **No schema.org, no product feed.** There is no JSON-LD to cross-check
  against; the DOM is the authoritative source. Any Ubercart theme
  customisation that drops the ``uc-*`` class hooks (unusual on stock
  themes, but possible) would leave prices and SKUs empty — the adapter
  returns ``None`` for the ones it can't find rather than emitting a
  bogus payload.
* **Deep navigation.** The leaf-category tree is three levels deep
  (``Store → Subaru → 15-21 WRX DIT → Parts & Accessories``); the
  initial discovery pass walks the ~40 ``catalog/<NNN>`` IDs that appear
  in the top-level site menu, plus one child level of any subcategory
  grid. Deeper pockets (a 4th-level split on a specific chassis) would
  be missed. Use ``CRAWLER_DELICIOUSTUNING_START_URLS`` to target those
  directly.
"""

import os
import re
import time
from typing import Iterator, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
    fetch_page,
)
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
)

DELICIOUSTUNING_BASE = "https://www.delicioustuning.com"
CATALOG_PATH_PREFIX = "/catalog/"
CATALOG_ID_RE = re.compile(r"^/catalog/\d+/?$")

# Verified live product URLs used as a fallback when env override is absent
# and catalog discovery fails. Picked off /catalog/334 (12-20 GT86 → Parts
# & Accessories) so the first smoke crawl exercises the Ubercart DOM path
# end-to-end — both a path-aliased URL and a raw /node/<id> URL so the
# adapter's canonical/URL handling is covered.
DEFAULT_START_URLS = [
    "https://www.delicioustuning.com/86AOS",
    "https://www.delicioustuning.com/V3_FlexFuel_Kit",
]

# Seed catalog categories — the top-level makes from the main-menu tree.
# Each one is a subcategory-landing page; the discovery walker recurses
# into the inner catalog/<NNN> cards they link to. Hard-coding the make
# roots (rather than every leaf) means we don't ship a 50-URL list that
# silently rots when the site adds another chassis.
CATALOG_SEED_URLS = [
    DELICIOUSTUNING_BASE + "/catalog/213",  # Infiniti
    DELICIOUSTUNING_BASE + "/catalog/78",  # Mazda
    DELICIOUSTUNING_BASE + "/catalog/77",  # Mitsubishi
    DELICIOUSTUNING_BASE + "/catalog/22",  # Nissan
    DELICIOUSTUNING_BASE + "/catalog/27",  # Scion
    DELICIOUSTUNING_BASE + "/catalog/20",  # Subaru
    DELICIOUSTUNING_BASE + "/catalog/32",  # Toyota
    DELICIOUSTUNING_BASE + "/catalog/316",  # Apparel (root of non-vehicle SKUs)
]

# Tokens that would otherwise end up as ``brand`` via the title heuristic
# on this house-brand catalog. Keep in sync with ``VARIANTS.md`` + the
# ``grimmspeed`` shape: every chassis family DT targets lives here.
_CAR_MAKES = frozenset(
    {
        "subaru",
        "toyota",
        "scion",
        "mazda",
        "mitsubishi",
        "nissan",
        "infiniti",
        "bmw",
        "honda",
        "ford",
    }
)

# Canonical brand value — every payload either passes a third-party
# brand through (future-proofing for resells) or is coerced to this.
BRAND_CANONICAL = "Delicious Tuning"

# Ubercart/Drupal derivative image prefix — we want the full-res original.
_IMAGE_STYLE_PREFIX_RE = re.compile(r"/sites/default/files/styles/[^/]+/public/", re.IGNORECASE)

# File-path segments that indicate site chrome rather than product media.
_IMAGE_NOISE_RE = re.compile(
    r"description[-_]tab|line[-_]tab|logo|favicon|placeholder|header[-_]|footer[-_]|sprite|icon[-_]",
    re.IGNORECASE,
)

# DT's Drupal theme sometimes inlines decorative PNGs inside the rich-text
# body (``001_line-tab_0.png``, ``000_description-tab.png``). They live at
# the site root — not under ``styles/`` — but they're not product media.
# The noise regex above catches the filenames; we also require the
# product-image scope below so body-inlined PNGs never enter the gallery.


def _resolve_start_urls() -> List[str]:
    """Env override wins; otherwise walk the catalog tree, then hard-coded default."""
    raw = os.environ.get("CRAWLER_DELICIOUSTUNING_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_catalog()
    return urls if urls else list(DEFAULT_START_URLS)


def _is_same_host(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return False
    return host in ("", "www.delicioustuning.com", "delicioustuning.com")


def _absolutize(href: str) -> Optional[str]:
    """Resolve a (possibly relative) href against the DT base; None on invalid input."""
    if not href or not href.strip():
        return None
    h = href.strip()
    # Drupal's legacy ``?q=node/<id>`` shape is a valid route but we prefer
    # the modern ``/node/<id>`` / path-alias form that the canonical link
    # uses. Rewrite ``?q=node/<id>`` → ``/node/<id>`` so dedupe works.
    if h.startswith("?q=node/"):
        return DELICIOUSTUNING_BASE + "/" + h.split("?q=", 1)[1]
    if h.startswith("http://") or h.startswith("https://"):
        if not _is_same_host(h):
            return None
        return h
    if h.startswith("/"):
        return DELICIOUSTUNING_BASE + h
    return urljoin(DELICIOUSTUNING_BASE + "/", h)


def _is_catalog_category_url(url: str) -> bool:
    """True for ``/catalog/<NNN>`` — a category / subcategory landing page."""
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return False
    return bool(CATALOG_ID_RE.match(path))


def _is_plausible_product_url(url: str) -> bool:
    """
    Reject non-product routes. A DT product lives either at ``/<path-alias>``
    (one path segment, no dot, no query-string node wrapper) or at
    ``/node/<numeric id>``. Category pages, cart, search, user, admin, and
    ``?q=…`` alternate routes are excluded.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    path = (parsed.path or "").rstrip("/")
    if not path:
        return False
    # Category/cart/user/admin/search → not a product.
    if _is_catalog_category_url(url):
        return False
    lower = path.lower()
    if any(
        lower.startswith(p)
        for p in (
            "/cart",
            "/user",
            "/admin",
            "/search",
            "/contact",
            "/about",
            "/news",
            "/portfolio",
            "/map",
            "/info",
            "/bmw_ecutek_unlock",
        )
    ):
        return False
    # Accept /node/<numeric id>.
    if lower.startswith("/node/"):
        tail = lower[len("/node/") :]
        return tail.isdigit() and len(tail) > 0
    # Accept single-segment path-aliases (``/86AOS``, ``/flexfuel``).
    # A slash inside the path means it's nested (``/catalog/XXX``, already
    # rejected above) or a sub-resource we don't want to treat as product.
    segments = [seg for seg in path.split("/") if seg]
    if len(segments) != 1:
        return False
    seg = segments[0]
    if "." in seg:
        return False
    return True


def _product_urls_from_catalog_page(html: str) -> List[str]:
    """
    Extract product URLs from a Ubercart uc_catalog grid. A product card on
    this theme is an ``<h3>`` (title) + ``<span class="uc-price">`` pair
    inside the ``view-uc-catalog`` view; subcategory cards use ``<h1
    class="field-content">`` + no price. Filter for anchors that sit in a
    table row alongside a ``.uc-price`` span so subcategory anchors (which
    share the same anchor shape) don't leak in.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[str] = []
    seen: set[str] = set()

    # The Ubercart catalog grid wraps each card in a <td>. Anchors that
    # accompany a price span → product. Anything else → nav/subcategory.
    catalog_view = soup.select_one("div.view-uc-catalog") or soup
    for cell in catalog_view.find_all("td"):
        if not isinstance(cell, Tag):
            continue
        if not cell.find(class_="uc-price"):
            continue
        for a in cell.find_all("a"):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if not isinstance(href, str):
                continue
            absolute = _absolutize(href)
            if not absolute:
                continue
            if not _is_plausible_product_url(absolute):
                continue
            base = absolute.split("?")[0].split("#")[0]
            if base in seen:
                continue
            seen.add(base)
            results.append(base)
    return results


def _subcategory_urls_from_catalog_page(html: str) -> List[str]:
    """Collect inner ``/catalog/<NNN>`` anchors from the uc_catalog_terms view (subcategory cards)."""
    soup = BeautifulSoup(html, "html.parser")
    results: List[str] = []
    seen: set[str] = set()
    terms_view = soup.select_one("div.view-uc-catalog-terms") or soup
    for a in terms_view.find_all("a"):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str):
            continue
        absolute = _absolutize(href)
        if not absolute or not _is_catalog_category_url(absolute):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        results.append(absolute)
    return results


def _discover_product_urls_via_catalog() -> List[str]:
    """
    Walk the seed-catalog tree one level deep: fetch each make root, harvest
    product anchors, and recurse into any subcategory cards it advertises.
    Returns a deduplicated list; empty on failure.
    """
    seen_products: set[str] = set()
    seen_categories: set[str] = set()
    product_urls: List[str] = []

    # Queue is (url, depth). Depth 0 = seed root, cap recursion at depth 2
    # — deeper than that and we're usually hitting a per-year leaf that
    # also shows products, which is where we want to stop walking anyway.
    queue: List[tuple[str, int]] = [(u, 0) for u in CATALOG_SEED_URLS]
    fetched = 0
    MAX_FETCHES = 60  # belt on walk depth; ~8 roots * 3 subcategories each is well under this

    while queue and fetched < MAX_FETCHES:
        url, depth = queue.pop(0)
        if url in seen_categories:
            continue
        seen_categories.add(url)
        if fetched > 0:
            time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
        fetched += 1
        try:
            html = fetch_page(url, timeout=20)
        except Exception:
            continue
        for product_url in _product_urls_from_catalog_page(html):
            if product_url in seen_products:
                continue
            seen_products.add(product_url)
            product_urls.append(product_url)
        if depth < 2:
            for sub in _subcategory_urls_from_catalog_page(html):
                if sub not in seen_categories:
                    queue.append((sub, depth + 1))

    return product_urls


def _normalize_part_manufacturer(part_manufacturer: Optional[str], product_name: str) -> str:
    """
    House-brand normalisation, same rule as the GrimmSpeed adapter:

    * Empty / car-make / "Delicious"-variant → coerce to canonical
      ``"Delicious Tuning"``.
    * Anything else (meaningful third-party brand text, should only show
      up on the rare resell SKU) → pass through unchanged.

    ``product_name`` unused today but retained in the signature so future
    title-level overrides don't require a call-site change.
    """
    _ = product_name
    raw = (part_manufacturer or "").strip()
    if not raw:
        return BRAND_CANONICAL
    low = raw.lower()
    if low in _CAR_MAKES:
        return BRAND_CANONICAL
    # Collapse "Delicious", "Delicious Tuning Inc", "delicioustuning", etc.
    if (
        low == "delicious"
        or low == "delicious tuning"
        or low == "delicioustuning"
        or low.startswith("delicious tuning ")
        or low.startswith("delicious-tuning")
    ):
        return BRAND_CANONICAL
    return raw


def _normalize_image_url(url: str) -> str:
    """
    Resolve scheme-relative / relative URLs against the DT base and strip the
    Drupal image-style prefix so ``styles/medium__200x200_/public/FOO.jpg``
    collapses to the full-resolution ``/sites/default/files/FOO.jpg``.
    Also drops the ``?itok=…`` image-derivative token (it's only meaningful
    for the thumbnail path we just removed).
    """
    u = url.strip()
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("http://"):
        u = "https://" + u[len("http://") :]
    elif u.startswith("/"):
        u = DELICIOUSTUNING_BASE + u
    # Full-res collapse.
    u = _IMAGE_STYLE_PREFIX_RE.sub("/sites/default/files/", u)
    # Drop itok query param only (keep anything else in case DT ever
    # introduces versioning we'd want to preserve).
    if "?" in u:
        base, qs = u.split("?", 1)
        kept = [kv for kv in qs.split("&") if kv and not kv.lower().startswith("itok=")]
        u = base + ("?" + "&".join(kept) if kept else "")
    return u


def _is_valid_product_image(url: str) -> bool:
    """Only DT-hosted ``/sites/default/files/`` images; reject chrome/decoration."""
    if not url or len(url) < 20:
        return False
    low = url.lower()
    if low.startswith("data:"):
        return False
    if "/sites/default/files/" not in low:
        return False
    if _IMAGE_NOISE_RE.search(low):
        return False
    return True


def _canonical_image_key(url: str) -> str:
    """Drop the itok query param + Drupal style prefix so size variants collapse."""
    key = _IMAGE_STYLE_PREFIX_RE.sub("/sites/default/files/", url)
    key = re.sub(r"[?&]itok=[^&]+", "", key)
    key = key.replace("?&", "?").rstrip("?&")
    return key


def _extract_dom_images(soup: BeautifulSoup) -> List[str]:
    """
    Gather product gallery URLs (Drupal-hosted, full-res) deduped + capped at 12.

    Scope is the Ubercart product-image field (``field-name-uc-product-image``);
    body-inlined PNG decorations ("description-tab", "line-tab") therefore
    never enter the gallery, even before the noise regex runs.
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

    scope: Optional[Tag] = None
    for selector in (
        "div.field-name-uc-product-image",
        "div.field-name-field-image",
        "div.uc-product-image",
    ):
        candidate = soup.select_one(selector)
        if isinstance(candidate, Tag):
            scope = candidate
            break

    if scope is None:
        return ordered

    for img in scope.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-original"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add(val.strip())
                break

    return ordered[:12]


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    h1 = soup.find("h1", id="page-title")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text
    # Fallback: <title>…</title> minus the " | Delicious Tuning" tail that
    # the theme appends on every page.
    title_tag = soup.find("title")
    if isinstance(title_tag, Tag):
        text = title_tag.get_text(strip=True)
        if text:
            text = re.sub(r"\s*\|\s*Delicious Tuning\s*$", "", text).strip()
            if text:
                return text
    return None


def _extract_sku(soup: BeautifulSoup) -> Optional[str]:
    """
    SKU lives in ``<div class="product-info model">`` on Ubercart —
    specifically the ``<span class="product-info-value">`` child. Some
    themes also expose a separate ``product-info sku`` block; we try both.
    """
    for selector in ("div.product-info.model", "div.product-info.sku"):
        block = soup.select_one(selector)
        if isinstance(block, Tag):
            value = block.find(class_="product-info-value")
            if isinstance(value, Tag):
                text = value.get_text(strip=True)
                if text:
                    return normalize_part_number(text)
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """
    Prefer the **sell-price** block so we don't store MSRP when both are
    present. Fall back to the first ``.uc-price`` anywhere in the document.
    """
    sell = soup.select_one("div.product-info.sell-price span.uc-price")
    if isinstance(sell, Tag):
        cents = parse_price_cents(sell.get_text(strip=True))
        if cents is not None:
            return cents
    any_price = soup.select_one("span.uc-price")
    if isinstance(any_price, Tag):
        cents = parse_price_cents(any_price.get_text(strip=True))
        if cents is not None:
            return cents
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """Pull the Drupal body field; fall back to <meta name=description>."""
    body = soup.select_one("div.field-name-body")
    if isinstance(body, Tag):
        text = body.get_text(separator=" ", strip=True)
        if text and len(text) > 10:
            return normalize_description_text(text, max_len=2000)
    meta = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta, Tag):
        content = meta.get("content")
        if isinstance(content, str) and content.strip():
            return normalize_description_text(content, max_len=2000)
    return None


class DeliciousTuningAdapter(RetailerCrawlerAdapter):
    """
    Delicious Tuning adapter. Discovery: walk the seed catalog tree
    (``/catalog/<NNN>`` roots per vehicle make) one level deep and harvest
    product anchors from each ``view-uc-catalog`` grid. Parsing: pure
    Ubercart DOM — title from ``h1#page-title``, SKU from
    ``product-info.model``, sell-price from ``product-info.sell-price``,
    description from ``field-name-body``, gallery from
    ``field-name-uc-product-image`` (collapsed to full-resolution URLs).
    Brand is passed through when a real manufacturer somehow shows up
    (reserved for resells) and otherwise coerced to ``"Delicious Tuning"``.
    """

    # Default Tier 0 — plain HTTP is enough (no Cloudflare, no JS challenge).
    # Left explicit so the choice is documented on the class itself.
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from the catalog walk (env override → catalog
        discovery → verified fallback). A jittered delay is applied between
        catalog fetches inside ``_discover_product_urls_via_catalog``.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Delicious Tuning product page.

        Pure DOM — there is no JSON-LD / OG meta / product:price:amount
        on this Drupal+Ubercart stack. Missing title means the URL isn't
        a product page (or Ubercart is misconfigured); we return ``None``
        so the runner skips ingest.
        """
        soup = BeautifulSoup(html, "html.parser")

        name = _extract_title(soup)
        if not name or len(name) < 3:
            return None

        part_number = _extract_sku(soup)
        price_cents = _extract_price_cents(soup)
        description = _extract_description(soup)
        image_urls = _extract_dom_images(soup)

        # JSON-LD brand is never present on this site; pass an empty
        # placeholder through the normaliser so the car-make / self-variant
        # rules still run (and so future resell SKUs with real brand text
        # in, say, a description block can be wired through here without
        # the call shape changing).
        part_manufacturer = _normalize_part_manufacturer(None, name)

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls if image_urls else None,
        )
