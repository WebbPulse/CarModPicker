"""
Modern Muscle Xtreme (modernmusclextreme.com) crawler adapter.

Live domain: ``https://www.modernmusclextreme.com``. Platform is
**AbleCommerce** — a .NET / ``.aspx`` storefront, not Shopify, BigCommerce,
or Magento — so none of our JSON-LD-first adapters apply directly. Product
URLs follow the shape ``/p-<id>-<slug>.aspx`` (e.g.
``/p-1570-57-vvt-hemi-performance-camshaft-kit-na-no-tune-required-non-mds-by-mmx.aspx``).

MMX is a Mopar / SRT specialist (Challenger, Charger, Hellcat, Jeep SRT,
Durango SRT) but acts as a **multi-brand reseller** — their catalog mixes the
house "Modern Muscle Xtreme" / "MMX" line with Diablosport, HPTuners, Kooks,
Borla, Borla Exhaust, MagnaFlow, Corsa, Stainless Works, JLT, Mopar OEM,
Z Automotive, TBA Machine, and several others. Parsing follows the
``ind.py`` / ``maperformance.py`` philosophy: **brand passes through from
the page unchanged**. Do NOT coerce every part to a single house brand; that
wipes the useful manufacturer information. When the title heuristic instead
picks a car make (Dodge / Jeep / Chrysler / SRT / Hellcat …), we drop it and
let downstream heuristics try — we prefer an honest ``Unknown`` over a wrong
car-make-as-brand.

SKU format is retailer-prefixed for many third parties (e.g.
``STW-SHM64HDRCAT`` for Stainless Works, ``BOR-140642`` for Borla), with
house items using readable codes (``MM-NTR-NSR-NONMDS``). We store it
as-is; cross-retailer dedupe will not always match, but within MMX the SKU
is stable.

Page structure (AbleCommerce) — **no JSON-LD**, but the product page emits
``schema.org/Product`` as microdata inside the main
``<div itemscope itemtype="https://schema.org/Product">`` block:

- Brand: ``<span itemprop="manufacturer" itemscope ...><meta itemprop="name" content="Borla Exhaust">``
- Name: ``<h1 class="product-page-header" itemprop="name">...</h1>``
- SKU: ``<meta itemprop="sku" content="BOR-140642">`` + a visible ``<dt>SKU:</dt><dd>...</dd>``
- Price: ``<meta itemprop="price" content="2032.9900"> <meta itemprop="priceCurrency" content="USD">``
- Description: ``<div itemprop="description">...HTML paragraphs...</div>``
- Main image: ``<meta itemprop="image" content="https://.../images/product/large/<id>.jpg">``
- Gallery thumbs: ``.product-gallery-items .product-gallery-item img src="/images/product/micro/<id>_<N>.jpg"``
  The page's own jQuery rewrites each thumb to a large image at
  ``/images/product/large/<id>_<N>_.jpg`` (note trailing underscore). We do
  the same URL transform so we can archive the gallery without executing JS.

The page ALSO contains related-product `<li>` cards that carry their own
``itemtype="https://schema.org/Product"`` microdata; we must scope to the
**outer** product block (class ``product-page``) so related-item brand/SKU
don't overwrite the real values.

Fetcher tier: ``http`` (default). ``/robots.txt`` and product pages return
HTTP 200 with a plain ``User-Agent: Mozilla/...`` request and no Cloudflare
interstitial; only a stock ASP.NET ``Server``/``X-AspNet-Version`` header
set. No TLS fingerprint or JS-challenge gymnastics required.

Discovery: there is no XML sitemap at ``/sitemap.xml`` (404). AbleCommerce
ships a single HTML sitemap at ``/sitemap.aspx`` (~460 KB) that links every
product via ``/p-<id>-<slug>.aspx`` — we scrape ``href`` values out of that
page. Set ``CRAWLER_MMX_START_URLS`` (comma-separated) to override with a
fixed list for ad-hoc runs or local smoke tests.
"""

import os
import re
from typing import ClassVar, Iterator, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload, fetch_page
from app.crawlers.parsing import (
    extract_dom_price,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

MMX_BASE = "https://www.modernmusclextreme.com"
PRODUCT_URL_RE = re.compile(r"^/p-\d+-[^/]+\.aspx$", re.IGNORECASE)
SITEMAP_PATH = "/sitemap.aspx"

DEFAULT_START_URLS = [
    # House brand (MMX) camshaft kit — exercises the "MMX" manufacturer pass-through.
    "https://www.modernmusclextreme.com/p-1570-57-vvt-hemi-performance-camshaft-kit-na-no-tune-required-non-mds-by-mmx.aspx",
    # Third-party brand (Stainless Works headers) — exercises multi-brand pass-through.
    "https://www.modernmusclextreme.com/p-697-2005-2023-challenger-charger-magnum-300-hemi-57616462-headers-power-series-by-stainless-works.aspx",
]

# Car-make tokens that the title heuristic sometimes picks as part_manufacturer when a
# title leads with the vehicle ("2015+ Challenger Hellcat S-Type …"). MMX is multi-
# brand, so unlike ADRO we do NOT collapse these to a house brand — we drop the
# value and let description / fallback heuristics try. Covers the whole SRT / Mopar
# family that shows up in MMX titles, plus a handful of generic makes that could
# appear in cross-platform kits.
_TITLE_CAR_MAKES = frozenset(
    {
        "challenger",
        "charger",
        "hellcat",
        "demon",
        "redeye",
        "trackhawk",
        "durango",
        "magnum",
        "ram",
        "dodge",
        "chrysler",
        "jeep",
        "srt",
        "srt8",
        "srt10",
        "grand",  # "Grand Cherokee …"
        "mopar",  # Mopar appears as a real OEM brand in JSON-LD/microdata (kept there);
        # but when a title leads with "Mopar …" and no real manufacturer
        # follows, we'd rather fall through to description.
        "hemi",
        "viper",
        "300",
        "300c",
    }
)


def _normalize_part_manufacturer(part_manufacturer: Optional[str]) -> Optional[str]:
    """
    Trim whitespace; drop car-make tokens the title heuristic may have picked.
    Returns None rather than coercing to a house brand so downstream heuristics
    can try — microdata manufacturer (the primary path) always wins before we
    reach here, so legitimate ``Mopar`` / ``MMX`` values are untouched.
    """
    if not part_manufacturer:
        return part_manufacturer
    brand = part_manufacturer.strip()
    if not brand:
        return None
    if brand.lower() in _TITLE_CAR_MAKES:
        return None
    return brand


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_MMX_START_URLS is set, return that list. Else discover via /sitemap.aspx."""
    raw = os.environ.get("CRAWLER_MMX_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch ``/sitemap.aspx`` (AbleCommerce's HTML site map — there is no XML
    sitemap on MMX) and collect every ``/p-<id>-<slug>.aspx`` href. Returns a
    deduplicated list of absolute URLs; empty on network / parse failure.
    """
    try:
        html_text = fetch_page(MMX_BASE + SITEMAP_PATH, timeout=20)
    except Exception:
        return []
    soup = BeautifulSoup(html_text, "html.parser")
    seen: set[str] = set()
    out: List[str] = []
    for a in soup.find_all("a", href=True):
        if not isinstance(a, Tag):
            continue
        href = a.get("href")
        if not isinstance(href, str):
            continue
        href = href.strip()
        if not href:
            continue
        # /sitemap.aspx uses relative paths like "/p-1570-...aspx"
        if not PRODUCT_URL_RE.match(href):
            # Also accept absolute URLs on the same host.
            if href.startswith("http"):
                # Normalize to path for the regex check.
                if not href.startswith(MMX_BASE) and not href.startswith("https://modernmusclextreme.com"):
                    continue
                path = "/" + href.split("/", 3)[3] if href.count("/") >= 3 else ""
                if not PRODUCT_URL_RE.match(path):
                    continue
            else:
                continue
        absolute = urljoin(MMX_BASE + "/", href.lstrip("/"))
        # Dedupe on path only (query strings are noise for AbleCommerce product pages).
        key = absolute.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(absolute)
    return out


def _find_main_product_scope(soup: BeautifulSoup) -> Optional[Tag]:
    """
    Return the outer ``<div class="... product-page ..." itemscope
    itemtype="https://schema.org/Product">`` container. MMX also emits
    ``schema.org/Product`` microdata on related-product ``<li>`` cards
    lower in the page, so we cannot just grab the first match by itemtype
    alone — we specifically want the page-level wrapper whose class list
    includes ``product-page``.
    """
    for div in soup.find_all("div", attrs={"itemtype": re.compile(r"schema\.org/Product$", re.IGNORECASE)}):
        if not isinstance(div, Tag):
            continue
        classes = div.get("class")
        if not isinstance(classes, list):
            continue
        if "product-page" in classes:
            return div
    # Fallback: first schema.org/Product on the page that isn't an <li> (related card).
    for node in soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Product$", re.IGNORECASE)}):
        if isinstance(node, Tag) and node.name != "li":
            return node
    return None


def _microdata_value(scope: Tag, prop: str) -> Optional[str]:
    """
    Return the first ``content`` value for ``itemprop="<prop>"`` within ``scope``
    that does NOT live inside a nested ``itemscope`` sub-block. MMX nests
    ``itemprop="manufacturer"`` and ``itemprop="offers"`` as their own
    ``itemscope`` subtrees that carry their own ``name``/``price`` children, so
    a naive ``scope.find`` for ``itemprop="name"`` would pick the manufacturer
    name instead of the product name on pages where h1 is not a ``<meta>``.
    """
    for tag in scope.find_all(attrs={"itemprop": prop}):
        if not isinstance(tag, Tag):
            continue
        # Skip if an ancestor (inside scope) is itself an itemscope block —
        # that means this value belongs to a sub-entity (manufacturer, offers,
        # related product), not the main Product.
        nested = False
        parent = tag.parent
        while parent is not None and parent is not scope:
            if isinstance(parent, Tag) and parent.has_attr("itemscope"):
                nested = True
                break
            parent = parent.parent
        if nested:
            continue
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        # <h1 itemprop="name">Text</h1> style — no content attr, just text.
        text = tag.get_text(strip=True)
        if text:
            return text
    return None


def _manufacturer_name_from_scope(scope: Tag) -> Optional[str]:
    """
    Read the nested ``<span itemprop="manufacturer" itemscope ...>``'s
    ``<meta itemprop="name">`` — the field that carries the real third-party
    brand (Borla Exhaust / Stainless Works / MOPAR / Modern Muscle Xtreme).
    """
    mfr = scope.find(attrs={"itemprop": "manufacturer"})
    if not isinstance(mfr, Tag):
        return None
    name_tag = mfr.find(attrs={"itemprop": "name"})
    if not isinstance(name_tag, Tag):
        return None
    content = name_tag.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    text = name_tag.get_text(strip=True)
    return text if text else None


def _price_from_scope(scope: Tag) -> Optional[int]:
    """
    First plausible ``itemprop="price"`` under the main Product scope.

    AbleCommerce wraps the real price in a nested
    ``<span itemprop="offers" itemscope itemtype=".../Offer">`` (so the naive
    "reject any nested-itemscope" rule we use for other props would drop every
    price candidate). The outer scope on pages without a ``product-page`` class
    also contains related-product ``<li itemtype=".../Product">`` blocks with
    their own Offer children, so we can't just grab the first nested price
    either — that's how we used to pick ``99.99`` from a related-product card.

    Policy: walk the ``itemprop="price"`` candidates in document order and
    accept the first one that does NOT have a ``schema.org/Product`` ancestor
    between itself and the main scope. That keeps the real product's Offer
    value and skips every related-product Offer. Zero / negative values (used
    as placeholders on "call for availability" items) are skipped.
    """
    for tag in scope.find_all(attrs={"itemprop": "price"}):
        if not isinstance(tag, Tag):
            continue
        blocked = False
        parent = tag.parent
        while parent is not None and parent is not scope:
            if isinstance(parent, Tag):
                itemtype = parent.get("itemtype")
                if isinstance(itemtype, str) and itemtype.lower().endswith("/product") and parent is not scope:
                    blocked = True
                    break
            parent = parent.parent
        if blocked:
            continue
        raw = tag.get("content")
        if not isinstance(raw, str) or not raw.strip():
            raw = tag.get_text(strip=True)
        if not raw:
            continue
        cents = parse_price_cents(raw)
        if cents is None or cents <= 0:
            continue
        return cents
    return None


def _description_from_scope(soup: BeautifulSoup, scope: Tag) -> Optional[str]:
    """
    The real description lives in ``<div id="productDescription" itemprop="description">``
    which sits OUTSIDE the outer Product wrapper on some layouts but is still
    the authoritative product copy. Prefer that by id; fall back to an in-scope
    ``itemprop="description"`` if the layout collapses them together.
    """
    by_id = soup.find("div", id="productDescription")
    if isinstance(by_id, Tag):
        text = by_id.get_text(separator=" ", strip=True)
        if text and len(text) > 30:
            return normalize_description_text(text, max_len=2000)
    desc = scope.find(attrs={"itemprop": "description"})
    if isinstance(desc, Tag):
        text = desc.get_text(separator=" ", strip=True)
        if text and len(text) > 30:
            return normalize_description_text(text, max_len=2000)
    return None


def _collect_gallery_images(soup: BeautifulSoup, primary_large: Optional[str]) -> List[str]:
    """
    Collect product gallery image URLs.

    Primary image is the ``itemprop="image"`` microdata value (already a
    ``/images/product/large/<id>.jpg`` URL). Additional gallery shots live on
    the page only as ``<img class="product-gallery-image" src="/images/product/micro/<id>_<N>.jpg">``
    thumbnails; the site's own jQuery rewrites those at render time to
    ``/images/product/large/<id>_<N>_.jpg`` (note trailing underscore before
    ``.jpg``). We perform the same transform so we archive the full gallery
    without executing JS. Capped at 12 images.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(u: str) -> None:
        if not u or len(urls) >= 12:
            return
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = MMX_BASE + u
        elif u.startswith("http://"):
            u = "https://" + u[len("http://") :]
        if not u.startswith("http"):
            return
        if u in seen:
            return
        seen.add(u)
        urls.append(u)

    if primary_large:
        add(primary_large.strip())

    for img in soup.select(".product-gallery-items .product-gallery-item img[src]"):
        if not isinstance(img, Tag) or len(urls) >= 12:
            break
        src = img.get("src")
        if not isinstance(src, str) or not src.strip():
            continue
        src = src.strip()
        # micro → large with trailing underscore (per site JS transform).
        # Covers "/images/product/micro/1570_1.jpg" → "/images/product/large/1570_1_.jpg".
        large = re.sub(
            r"/images/product/(?:micro|icon|medium)/([^/?#]+?)\.(jpg|jpeg|png|webp)",
            r"/images/product/large/\1_.\2",
            src,
            flags=re.IGNORECASE,
        )
        add(large)

    return urls[:12]


class ModernMuscleXtremeAdapter(RetailerCrawlerAdapter):
    """
    Modern Muscle Xtreme (MMX) adapter. Discovery: HTML ``/sitemap.aspx`` (no
    XML sitemap exists on AbleCommerce here) or ``CRAWLER_MMX_START_URLS``.
    Parsing: schema.org **microdata** first — the page has no JSON-LD — scoped
    to the outer ``<div class="product-page" itemscope itemtype=".../Product">``
    so related-product cards don't leak in. Manufacturer passes through
    unchanged; only car-make tokens that the title fallback picks are dropped.
    """

    # Plain requests works; MMX is ASP.NET / AbleCommerce, no Cloudflare.
    ADAPTER_NAME: ClassVar[str] = "modernmusclextreme"
    category_targets: ClassVar[list[str]] = ["universal"]
    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs from ``/sitemap.aspx``. Set ``CRAWLER_MMX_START_URLS``
        (comma-separated) to override with a fixed list for smoke tests.
        """
        for url in _resolve_start_urls():
            yield url

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse an MMX product page. Microdata first (the only structured data
        the page emits), with DOM/title/description fallbacks for any field the
        microdata block leaves blank. Returns ``None`` if the page doesn't look
        like a product page (no Product microdata block and no h1).
        """
        soup = BeautifulSoup(html, "html.parser")
        scope = _find_main_product_scope(soup)

        # Name — prefer the h1 inside the main scope; fall back to a scoped
        # itemprop="name" (which dodges the manufacturer sub-block via
        # _microdata_value), then to og:title, then to the first h1 anywhere.
        name: Optional[str] = None
        if scope is not None:
            h1 = scope.find("h1", attrs={"itemprop": "name"}) or scope.find("h1")
            if isinstance(h1, Tag):
                text = h1.get_text(strip=True)
                if text:
                    name = text
            if not name:
                name = _microdata_value(scope, "name")
        if not name:
            og_title = soup.find("meta", property="og:title")
            if isinstance(og_title, Tag):
                content = meta_content(og_title)
                if content and content.strip():
                    name = content.strip()
        if not name:
            h1_any = soup.find("h1")
            if isinstance(h1_any, Tag):
                text = h1_any.get_text(strip=True)
                if text:
                    name = text
        if not name or len(name) < 3:
            return None

        # Price / SKU / brand / image from the outer microdata scope when present.
        price_cents: Optional[int] = None
        part_number: Optional[str] = None
        part_manufacturer: Optional[str] = None
        primary_image: Optional[str] = None

        if scope is not None:
            price_cents = _price_from_scope(scope)
            sku_raw = (
                _microdata_value(scope, "sku") or _microdata_value(scope, "mpn") or _microdata_value(scope, "productID")
            )
            part_number = normalize_part_number(sku_raw) if sku_raw else None
            part_manufacturer = _manufacturer_name_from_scope(scope)
            # <meta itemprop="image" content="https://.../images/product/large/<id>.jpg">
            primary_image = _microdata_value(scope, "image")

        # Fallbacks when microdata missed a field.
        if price_cents is None:
            price_cents = extract_dom_price(soup)

        description = _description_from_scope(soup, scope) if scope is not None else None
        if not description:
            og_desc = soup.find("meta", property="og:description")
            if isinstance(og_desc, Tag):
                d = meta_content(og_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000) or d.strip()[:2000]
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = normalize_description_text(d, max_len=2000) or d.strip()[:2000]

        if not part_number:
            # Visible "<dt>SKU:</dt><dd>X</dd>" pair on the product page.
            for dt in soup.find_all("dt"):
                if not isinstance(dt, Tag):
                    continue
                label = dt.get_text(strip=True).lower().rstrip(":")
                if label not in ("sku", "part #", "part number", "item #"):
                    continue
                dd = dt.find_next_sibling("dd")
                if isinstance(dd, Tag):
                    candidate = normalize_part_number(dd.get_text(strip=True))
                    if candidate:
                        part_number = candidate
                        break
        if not part_number:
            candidate = extract_sku_from_text(soup.get_text())
            if candidate:
                part_number = candidate
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        # Brand cascade: microdata manufacturer is authoritative when present
        # (carries the real third-party brand). Otherwise try title heuristic,
        # then description, then known-pattern fallback — dropping car makes
        # along the way so we don't mis-tag a Stainless Works exhaust as "Dodge".
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))
        part_manufacturer = _normalize_part_manufacturer(part_manufacturer)

        image_urls = _collect_gallery_images(soup, primary_image) or None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
        )
