"""
Lingenfelter Performance Engineering (lingenfelter.com) crawler adapter.

Lingenfelter is the reference-price storefront for LS/LT built engines and
Magnuson/ProCharger supercharger packages on the Camaro/Corvette/Cadillac-V
and Hellcat side — the GM analogue of AMS Performance for R35 or IAG for
Subaru. The built-engine and installed-SC packages sit in the $15k–$40k
tier that Texas Speed / Tick / BTR don't cover at the same product level.

Platform: Miva Merchant. Product pages do **not** emit JSON-LD ``Product``
— catalog data lives in schema.org microdata
(``<div itemscope itemtype="http://schema.org/Product">`` with ``<meta
itemprop="..." content="...">`` children for name, sku, mpn, description,
brand, category, and a nested ``schema.org/Offer`` scope for
``priceCurrency`` / ``price`` / ``availability``).

Fetcher tier: ``http`` — plain ``requests`` returns HTTP 200 on
``/robots.txt``, ``/sitemap.xml``, and product pages with no Cloudflare
interstitial. (The RETAILER_BACKLOG entry guessed Tier-0/1 conservatively.)

Discovery: ``/sitemap.xml`` is a **flat urlset** that mixes product URLs
in two equivalent forms — SEO-friendly ``/product/<code>.html`` and the
Miva-native ``/mm5/merchant.mvc?Screen=PROD&Product_Code=<code>``. We keep
only the ``/product/<code>.html`` form (canonical user-facing URL) and drop
``/category/<name>.html`` / ``Screen=CTGY`` entries. The sitemap was last
regenerated in 2020 (per ``<lastmod>``), so a non-trivial share (~35% in a
20-URL sample) of the legacy Lingenfelter-internal ``L…`` SKUs now 404 on
the current catalog — runner handles 404s gracefully, the remaining 65%
still gives us ~900 live products to seed the Lingenfelter retailer.
Override with ``CRAWLER_LINGENFELTER_START_URLS`` (comma-separated).

Parsing: microdata ``itemprop="name" / "mpn" / "sku" / "description" /
"price"`` is the authoritative source. Price ``content`` is dollars (integer
or decimal — e.g. ``"13999"`` → $13,999.00, ``"5444.99"`` → $5,444.99), same
convention as the DOM ``#js-price-value[data-base-price]``. ``itemprop="mpn"``
and ``itemprop="sku"`` are populated per-SKU and usually identical; we prefer
``mpn`` over ``sku`` to match cross-retailer dedupe (Summit / Jegs / BTR).

Brand policy: ``itemprop="brand"`` is **always** ``"Lingenfelter Performance
Engineering"`` — even on third-party SKUs like ``BORLA … Exhaust`` or
``Magnuson … Supercharger``. Unlike BTR (which populates per-SKU
``brand.name``), Lingenfelter's microdata is a useless co-brand signal. We
recover the real manufacturer from the title (``part_manufacturer_from_title``
picks up ``"BORLA"`` / ``"Magnuson"`` / ``"Lingenfelter"`` as the first
token) and normalize any ``"Lingenfelter"`` variant to the canonical
``"Lingenfelter Performance Engineering"``. Falls back to that same default
when the title starts with a chassis/model code (``"CTS-V LSA Supercharged
Engine Package …"``) so first-party LPE engine packages still resolve to
Lingenfelter rather than leaking "CTS-V" as a brand.

Images: the real gallery is in a ``var image_data<NNNN> = [...]`` JS blob,
not the microdata ``itemprop="image"`` meta (which is sometimes a ``/mm5/``
stub on newer SKUs). Each entry has shape ``{"type_code": "main" | "",
"image_data": [thumb_540, thumb_100, full]}``. We take the last URL in
``image_data`` (full size), order entries so ``type_code == "main"`` wins
the hero position, and resolve relative ``graphics/...`` paths against
the ``<base href="https://www.lingenfelter.com/mm5/">`` declared on every
product page.
"""

import json
import os
import re
from typing import Iterator, List, Optional
from urllib.parse import urljoin, urlparse

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_from_title,
)

LINGENFELTER_BASE = "https://www.lingenfelter.com"
SITEMAP_URL = f"{LINGENFELTER_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
IMAGE_BASE = f"{LINGENFELTER_BASE}/mm5/"

# Canonical first-party brand. Lingenfelter's itemprop=brand always reads
# this exact string, and so does the storefront header/footer — matching it
# verbatim keeps cross-retailer dedupe on (manufacturer, part_number) stable
# for LPE-branded SKUs shared with Summit / Jegs / ECS.
LPE_BRAND = "Lingenfelter Performance Engineering"

# GM / Cadillac / Hellcat car-model tokens that often appear as the first
# word of a Lingenfelter product title on their own in-house SKUs — e.g.
# ``"CTS-V LSA Supercharged Engine Package …"``, ``"ZL1 Camaro …"``.
# ``part_manufacturer_from_title`` doesn't recognize these as chassis/model
# codes (its regex targets BMW-style ``E46`` / ``F80`` letter+digits shapes),
# so we short-circuit here and fall through to the LPE first-party default
# rather than leaking "CTS-V" / "ZL1" as a manufacturer. Storefront scope
# is narrow enough that a small hand-curated list is cheaper than adding
# generic vehicle-token detection to the shared parsing helpers.
_LPE_CAR_MODEL_TOKENS = frozenset(
    {
        "cts",
        "cts-v",
        "ats",
        "ats-v",
        "ct5",
        "ct5-v",
        "ct6",
        "ct6-v",
        "camaro",
        "corvette",
        "silverado",
        "sierra",
        "escalade",
        "trailblazer",
        "gto",
        "ssr",
        "zl1",
        "z06",
        "zr1",
        "lsa",
        "lt4",
        "lt2",
        "lt1",
        "ls3",
        "ls7",
        "ls9",
        "hellcat",
        "challenger",
        "charger",
    }
)

DEFAULT_START_URLS = [
    "https://www.lingenfelter.com/product/L010086509.html",
]

# ``var image_data<NNNN> = [ ... ]`` — the Miva ImageMachine gallery array
# emitted on every product page. The suffix digits are the internal product
# row id (different per SKU); we anchor on the ``image_data`` prefix + ``[``
# and walk bracket depth to the matching ``]`` (same approach as the BTR
# ``mage/gallery/gallery`` parser).
_IMAGE_DATA_OPEN_RE = re.compile(r"image_data\d+\s*=\s*\[")


def _is_product_url(url: str) -> bool:
    """
    True if ``url`` points to a ``/product/<slug>`` page on the Lingenfelter
    host. Accepts both the canonical ``.html`` form and the SEO-friendly
    ``/product/<pretty-slug>`` form the storefront serves in the nav —
    chrome-extension captures can arrive in either shape. Rejects category
    (``/category/...``) and Miva native (``/mm5/merchant.mvc?Screen=CTGY``)
    URLs; product-page detection for ``Screen=PROD`` is redundant because
    those never leave the sitemap in practice (the SEO URL is the
    user-facing copy).
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and not (host == "lingenfelter.com" or host.endswith(".lingenfelter.com")):
        return False
    path = parsed.path or ""
    # ``/product/<something>`` — slug may or may not end in ``.html``.
    if not path.startswith("/product/"):
        return False
    remainder = path[len("/product/") :].strip("/")
    if not remainder:
        return False
    # Filter out obvious non-product slugs like ``/product/VIN_LookUp.html``
    # which appears in the header nav as a feature page, not a catalog entry.
    # The lookup page has no itemprop microdata so parse would return None,
    # but rejecting at the URL level keeps discovery counts honest.
    first_seg = remainder.split("/", 1)[0]
    if first_seg.lower() in {"vin_lookup.html", "vin_lookup"}:
        return False
    return True


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_LINGENFELTER_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_LINGENFELTER_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _discover_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.xml`` (a flat urlset — no sitemap index) and return every
    ``/product/<slug>.html`` entry. Deduplicated by path; empty list on
    fetch/parse failure. The sitemap also lists the equivalent Miva-native
    ``/mm5/merchant.mvc?Screen=PROD&Product_Code=<code>`` URL for each SKU —
    dropping those avoids double-crawling the same product twice per run.
    """
    try:
        xml_text = fetch_page(SITEMAP_URL, timeout=30)
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
        url = loc.text.strip().split("?", 1)[0]
        if not url:
            continue
        if not _is_product_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        product_urls.append(url)

    return product_urls


def _product_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Return the ``<div itemscope itemtype="http://schema.org/Product">``
    wrapper that contains all microdata for the product. Returns None when
    the page is not a product (CMS pages / VIN lookup / category pages have
    no Product scope).
    """
    for tag in soup.find_all(attrs={"itemscope": True}):
        if not isinstance(tag, Tag):
            continue
        itemtype = tag.get("itemtype")
        if isinstance(itemtype, str) and "schema.org/Product" in itemtype:
            return tag
    return None


def _itemprop_content(scope: Tag, name: str) -> Optional[str]:
    """
    Read ``<meta itemprop="{name}" content="...">`` from within a scope.
    Only scans direct ``<meta>`` / ``<link>`` descendants — nested scopes
    (``itemprop=offers`` → ``itemprop=price``) are handled by a second call
    that passes the offer scope in directly, avoiding ambiguity when the
    same ``itemprop`` name could appear at two nesting levels.
    """
    for tag in scope.find_all(["meta", "link"]):
        if not isinstance(tag, Tag):
            continue
        if tag.get("itemprop") != name:
            continue
        content = tag.get("content") or tag.get("href")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _offer_scope(product_scope: Tag) -> Optional[Tag]:
    """
    Return the nested ``<div itemprop="offers" itemscope itemtype="schema.org/Offer">``
    child, if present. Offer fields (``priceCurrency``, ``price``,
    ``availability``) live inside this inner scope — not at the top level of
    the Product scope.
    """
    for tag in product_scope.find_all(attrs={"itemscope": True}):
        if not isinstance(tag, Tag):
            continue
        if tag.get("itemprop") != "offers":
            continue
        return tag
    return None


def _extract_price_cents(product_scope: Tag) -> Optional[int]:
    """
    Price in cents from the microdata ``<meta itemprop="price" content="...">``
    inside the Offer scope. Value is always dollars — integer (``"13999"``
    → $13,999.00) or decimal (``"5444.99"`` → $5,444.99). Falls back to the
    ``#js-price-value[data-base-price]`` DOM attribute on the parent
    document (same value, different surface) when the microdata is absent.
    """
    offer = _offer_scope(product_scope)
    if offer is not None:
        raw = _itemprop_content(offer, "price")
        if raw:
            cents = parse_price_cents(raw)
            if cents is not None:
                return cents

    # DOM fallback: the ``<div id="js-price-value" data-base-price="...">``
    # lives outside the Product scope but inside the same page; climb to the
    # document root to find it.
    root = product_scope
    while root.parent is not None:
        root = root.parent
    price_div = root.find(id="js-price-value") if isinstance(root, Tag) else None
    if isinstance(price_div, Tag):
        raw = price_div.get("data-base-price")
        if isinstance(raw, str) and raw.strip():
            cents = parse_price_cents(raw)
            if cents is not None:
                return cents
    return None


def _extract_name(product_scope: Tag) -> Optional[str]:
    """
    Product name from ``itemprop="name"`` meta first (authoritative — emitted
    on every page). Falls back to the ``<h1 class="nm"><span class="normal">``
    heading for the rare page where microdata is missing but the DOM heading
    still renders. Both sources yield identical text in practice.
    """
    raw = _itemprop_content(product_scope, "name")
    if raw:
        return raw

    root = product_scope
    while root.parent is not None:
        root = root.parent
    if isinstance(root, Tag):
        h1 = root.find("h1", class_="nm")
        if isinstance(h1, Tag):
            text = h1.get_text(" ", strip=True)
            if text:
                return text
    return None


def _extract_part_number(product_scope: Tag) -> Optional[str]:
    """
    Prefer ``mpn`` (manufacturer part number) over ``sku`` when both exist
    and differ. On LPE they're usually identical (same row echoed into both
    meta tags), but for resold brands like Borla / Manley a future catalog
    change could split them — keep the MPN preference so cross-retailer
    dedupe on (manufacturer, part_number) stays stable with Summit / Jegs.
    """
    mpn = _itemprop_content(product_scope, "mpn")
    if mpn:
        return mpn
    return _itemprop_content(product_scope, "sku")


def _extract_description(product_scope: Tag) -> Optional[str]:
    """
    Read ``itemprop="description"`` — contains the full product copy
    inline-encoded with HTML entities (``&nbsp;``, ``&#40;``) and the
    occasional stray ``<br>``. ``normalize_description_text`` handles both.
    """
    raw = _itemprop_content(product_scope, "description")
    if not raw:
        return None
    return normalize_description_text(raw, max_len=2000)


def _normalize_brand(raw_brand: Optional[str]) -> Optional[str]:
    """
    Map any ``"lingenfelter …"`` variant (bare ``"Lingenfelter"`` from the
    title heuristic, ``"Lingenfelter Performance"``, or the canonical
    ``"Lingenfelter Performance Engineering"`` itself) to the single canonical
    form. Other values pass through unchanged so third-party brands
    (``"BORLA"``, ``"Magnuson"``) aren't mutated.
    """
    if not raw_brand:
        return None
    cleaned = raw_brand.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith("lingenfelter"):
        return LPE_BRAND
    return cleaned


def _resolve_brand(name: str, itemprop_brand: Optional[str]) -> str:
    """
    Title heuristic first (``part_manufacturer_from_title`` picks up
    ``"BORLA"`` / ``"Magnuson"`` / ``"Lingenfelter"`` as first token).
    ``itemprop=brand`` is always LPE regardless of the actual manufacturer,
    so we only use it as a last-resort default when the title offers no
    brand signal. Normalize any Lingenfelter variant to the canonical name,
    and reject GM/Cadillac/Hellcat car-model tokens the shared heuristic
    doesn't know to skip (``"CTS-V"``, ``"ZL1"``, ``"Corvette"``).
    """
    heuristic = part_manufacturer_from_title(name)
    if heuristic and heuristic.strip().lower() in _LPE_CAR_MODEL_TOKENS:
        heuristic = None
    normalized = _normalize_brand(heuristic)
    if normalized:
        return normalized
    # Title didn't yield a brand (chassis-first titles like "CTS-V LSA
    # Supercharged Engine Package …" fall through). Default to LPE — the
    # storefront is first-party, so when no third-party brand is indicated,
    # the product is LPE's own.
    fallback = _normalize_brand(itemprop_brand) or LPE_BRAND
    return fallback


def _extract_image_gallery(html_text: str) -> List[str]:
    """
    Pull the ``image_data<N>`` JS array and return full-size image URLs,
    ``type_code == "main"`` first (hero), others in declaration order. Each
    entry's ``image_data`` is ``[thumb_540, thumb_100, full]`` — we always
    take the last element. Relative ``graphics/...`` paths are resolved
    against the ``/mm5/`` base declared on every product page.

    Returns [] on any parse failure — callers should fall back to the
    ``itemprop="image"`` meta (which may itself be a ``/mm5/`` stub).
    """
    match = _IMAGE_DATA_OPEN_RE.search(html_text)
    if not match:
        return []
    start = match.end() - 1  # position of the opening '['
    depth = 0
    end = -1
    in_str = False
    esc = False
    limit = min(start + 500_000, len(html_text))
    for k in range(start, limit):
        c = html_text[k]
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    if end < 0:
        return []

    try:
        data = json.loads(html_text[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []

    mains: List[str] = []
    others: List[str] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        images = entry.get("image_data")
        if not isinstance(images, list) or not images:
            continue
        full = images[-1]
        if not isinstance(full, str) or not full.strip():
            continue
        absolute = urljoin(IMAGE_BASE, full.strip())
        type_code = entry.get("type_code")
        if isinstance(type_code, str) and type_code.strip().lower() == "main":
            mains.append(absolute)
        else:
            others.append(absolute)

    seen: set[str] = set()
    ordered: List[str] = []
    for u in mains + others:
        key = u.split("?", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        ordered.append(u)
    return ordered[:12]


def _fallback_image_from_itemprop(product_scope: Tag) -> Optional[str]:
    """
    Read ``<meta itemprop="image" content="...">`` when the ``image_data``
    JS gallery is absent. Note: on newer SKUs this field is populated with
    a ``https://www.lingenfelter.com/mm5/`` stub that doesn't resolve to an
    actual image — the caller must still treat an empty gallery list as
    authoritative and skip this path when the URL ends at ``/mm5/``.
    """
    raw = _itemprop_content(product_scope, "image")
    if not raw:
        return None
    cleaned = raw.strip()
    # Drop the ``/mm5/`` stub (trailing-slash URL points at the Miva store
    # root, not an image).
    if cleaned.rstrip("/").endswith("/mm5"):
        return None
    return cleaned


class LingenfelterAdapter(RetailerCrawlerAdapter):
    """
    Lingenfelter Performance Engineering adapter.

    Miva Merchant storefront; plain-HTTP fetches. Discovery via flat
    ``/sitemap.xml`` filtered to ``/product/*.html`` entries (Miva-native
    ``Screen=PROD`` duplicates dropped). Parsing uses schema.org microdata
    (``itemprop="name" / "mpn" / "sku" / "description"`` + nested
    ``itemprop="offers"`` scope for ``price``), the ``image_data<N>`` JS
    array for the gallery, and the title heuristic for true manufacturer —
    microdata ``brand`` is always LPE regardless of the actual brand.
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """Yield product URLs. Env override wins; sitemap next; fixed fallback last."""
        env_urls = _resolve_start_urls_env()
        if env_urls is not None:
            for url in env_urls:
                if _is_product_url(url):
                    yield url
            return

        for url in _discover_via_sitemap() or list(DEFAULT_START_URLS):
            if _is_product_url(url):
                yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Lingenfelter product page into a ``ScrapedPayload``. Returns
        ``None`` when the URL is not product-shaped, when the schema.org
        Product microdata scope is absent (CMS / 404 landing), or when no
        name can be recovered.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")
        product_scope = _product_scope(soup)
        if product_scope is None:
            return None

        name = _extract_name(product_scope)
        if not name or len(name) < 3:
            return None

        part_number_raw = _extract_part_number(product_scope)
        part_number = normalize_part_number(part_number_raw) if part_number_raw else None

        description = _extract_description(product_scope)
        price_cents = _extract_price_cents(product_scope)

        itemprop_brand = _itemprop_content(product_scope, "brand")
        part_manufacturer = _resolve_brand(name, itemprop_brand)

        gallery = _extract_image_gallery(html)
        if not gallery:
            fallback = _fallback_image_from_itemprop(product_scope)
            if fallback:
                gallery = [fallback]

        return ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=gallery[:12] if gallery else None,
        )
