"""
A90 Shop (a90shop.com) crawler adapter.

Uses JSON-LD first (like the chrome-extension), then A90/Wix-specific DOM:
h1 title, "SKU: ...", "From $...", og:meta, and product description.

Discovery: sitemap.xml (and child sitemaps) to find all /product-page/ URLs.
Override with CRAWLER_A90SHOP_START_URLS (comma-separated) to use a fixed list.

Variant splitting (``extract_variants``): Wix product pages embed an
``"options":[{...selections:[...]}]`` JSON block in the inline product data.
Many A90 Shop selections carry a ``+$NN`` price delta in the label
(``"Matte +$22"``, ``"JB4PRO +$300 (fuel options)"``) or are *categorically*
different products (turbo choice / brake pad position / drive type). Any such
selection beyond the default is emitted as its own derived ``ScrapedPayload``
so the catalog stops collapsing eight $200–$1500 SKUs into one row at one
price. See ``_a90_extract_variant_payloads`` for the deduction rules.
"""

import json
import os
import re
import time
from typing import ClassVar, Iterator, List, Optional
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    ScrapedPayload,
    apply_delay_jitter,
    fetch_page,
)
from app.crawlers.parsing import (
    extract_dom_price,
    extract_json_ld_product,
    extract_part_number_candidate_from_title,
    extract_sku_from_text,
    meta_content,
    normalize_part_number,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
    scraped_payload_from_json_ld,
)

# Default start URL for PoC; used only when sitemap discovery fails
A90SHOP_BASE = "https://www.a90shop.com"
DEFAULT_START_URLS = [
    "https://www.a90shop.com/product-page/rays-gram-lights-57cr-a90-supra-wheels-bronze",
]

# Sitemap protocol namespace (Wix and standard sitemaps)
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
PRODUCT_PAGE_PATH = "/product-page/"


def _resolve_start_urls() -> List[str]:
    """If CRAWLER_A90SHOP_START_URLS is set, return that list. Else discover via sitemap (or fallback)."""
    raw = os.environ.get("CRAWLER_A90SHOP_START_URLS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    urls = _discover_product_urls_via_sitemap()
    return urls if urls else list(DEFAULT_START_URLS)


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap (urlset or sitemap index)."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _discover_product_urls_via_sitemap() -> List[str]:
    """
    Fetch sitemap.xml (and child sitemaps if index), collect all <loc> URLs
    that contain /product-page/. Returns deduplicated list; empty on failure.
    """

    def add_product_url(url: str, seen: set[str], out: List[str]) -> None:
        url = (url or "").strip()
        if not url or PRODUCT_PAGE_PATH not in url or url in seen:
            return
        seen.add(url)
        out.append(url)

    def parse_urlset_locs(xml_text: str, seen: set[str], out: List[str]) -> None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return
        for loc in _loc_elements(root):
            if loc.text:
                add_product_url(loc.text, seen, out)

    seen: set[str] = set()
    product_urls: List[str] = []

    try:
        index_url = A90SHOP_BASE + "/sitemap.xml"
        index_text = fetch_page(index_url, timeout=15)
        root = ET.fromstring(index_text)
        tag = root.tag
        if tag == f"{{{SITEMAP_NS}}}sitemapindex" or "sitemapindex" in tag:
            child_sitemap_urls = [loc.text.strip() for loc in _loc_elements(root) if loc.text and loc.text.strip()]
            for i, child_url in enumerate(child_sitemap_urls):
                if i > 0:
                    time.sleep(apply_delay_jitter(DEFAULT_REQUEST_DELAY_SEC))
                try:
                    child_text = fetch_page(child_url, timeout=15)
                    parse_urlset_locs(child_text, seen, product_urls)
                except Exception:
                    continue
        else:
            parse_urlset_locs(index_text, seen, product_urls)
    except Exception:
        return []

    return product_urls


# Wix image URL pattern: only product media from wixstatic (excludes tracking, placeholders)
_WIX_MEDIA_URL_RE = re.compile(
    r"https?://static\.wixstatic\.com/media/[^\s\"'<>]+",
    re.IGNORECASE,
)

# Path segments that indicate promo/logo/banner, not product gallery
_WIX_NON_PRODUCT_PATH = re.compile(
    r"top-promotion|/logo|banner|affirm|icon\.(png|jpg|webp|gif)|1x1|pixel\.gif",
    re.IGNORECASE,
)

# Known A90 Shop non-product media ids (Wix file id after prefix, before ~ or %7E)
# Add ids here when we find logo/site assets that appear before "Related Products"
_A90_NON_PRODUCT_MEDIA_IDS = frozenset(
    {
        "d186b081cecb49fe8cb18f7792c8f0f1",  # A90 shop logo
        "6e48084c31ac47b6bccb899c400fa622",  # "S" / small site icon
    }
)


def _wix_url_to_base(url: str) -> str:
    """Strip /v1/fill/ or /v1/fit/... from Wix URL to get full-size base image."""
    for suffix in ("/v1/fill/", "/v1/fit/"):
        if suffix in url:
            return url.split(suffix)[0]
    return url


def _wix_media_file_id(url: str) -> str:
    """Extract Wix media file id (e.g. ad9611cdf1fd45229cca26cfc549c419) from .../media/0f8225_xxx~mv2.webp."""
    if "/media/" not in url:
        return ""
    segment = url.split("/media/")[-1]
    # 0f8225_xxx~mv2.webp or 0f8225_xxx%7Emv2.png
    if "_" in segment:
        rest = segment.split("_", 1)[1]
        for sep in ("~", "%7e", "%7E"):
            if sep in rest:
                return rest.split(sep)[0].lower()
        return rest.split(".")[0].lower() if "." in rest else rest.lower()
    return ""


def _is_valid_wix_product_image(url: str) -> bool:
    """
    Only allow Wix product media URLs. Reject tracking, data: placeholders,
    bucket URLs, and known promo/logo paths.
    """
    if not url or len(url) < 30:
        return False
    lower = url.lower()
    # Reject non-Wix: tracking, analytics, data: placeholder, bucket
    if lower.startswith("data:"):
        return False
    if "base64" in lower or "clickcease" in lower or "monitor." in lower:
        return False
    if "storageapi.dev" in lower or "stats.aspx" in lower:
        return False
    # Only accept Wix media
    if "static.wixstatic.com/media/" not in lower:
        return False
    # Reject promo/logo/banner paths
    if _WIX_NON_PRODUCT_PATH.search(url):
        return False
    # Reject known A90 Shop logo/site assets (not product gallery)
    if _wix_media_file_id(url) in _A90_NON_PRODUCT_MEDIA_IDS:
        return False
    return True


def _extract_a90_images(soup: BeautifulSoup, raw_html: str) -> List[str]:
    """
    Extract product gallery image URLs for A90 Shop (Wix). Only Wix product media;
    excludes tracking, placeholders, bucket URLs, logos, promo.
    Restricts to HTML before "Related Products" or the comments section so we
    don't include related-product images or comment user avatars.
    """
    # Cut at the earliest of: "Related Products", Wix comments widget, or comment prompts.
    # Comment section profile pictures are also Wix media URLs and would otherwise be included.
    _SECTION_CUTOFFS = [
        "related products",
        "wix-comments",
        'data-hook="comments',
        "add a comment",
        "leave a comment",
        "be the first to comment",
        "comments section",
    ]
    raw_lower = raw_html.lower()
    cut_pos = len(raw_html)
    for marker in _SECTION_CUTOFFS:
        pos = raw_lower.find(marker)
        if pos >= 0:
            cut_pos = min(cut_pos, pos)
    main_html = raw_html[:cut_pos]

    seen_bases: set[str] = set()
    ordered: List[str] = []

    def add_url(src: str, only_if_in_main: bool = False) -> None:
        if not _is_valid_wix_product_image(src):
            return
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = A90SHOP_BASE + src
        src = _wix_url_to_base(src)
        if src in seen_bases:
            return
        if only_if_in_main:
            # URL in HTML often has /v1/fill/...; check if this media file id appears in main area
            if "/media/" in src:
                segment = src.split("/media/")[-1]
                if segment not in main_html:
                    return
            elif src not in main_html:
                return
        seen_bases.add(src)
        ordered.append(src)

    # 1. og:image (in head, always before related)
    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        content = meta_content(og_img)
        if content and content.strip():
            add_url(content.strip())

    # 2. img src / data-src: only add if this URL appears in main_html (before Related Products or comments)
    for img in soup.find_all("img"):
        if not isinstance(img, Tag):
            continue
        for attr in ("src", "data-src", "data-image"):
            val = img.get(attr)
            if isinstance(val, str) and val.strip():
                add_url(val.strip(), only_if_in_main=True)
                break
        else:
            val = img.get("data-srcset")
            if isinstance(val, str) and val.strip():
                first = val.split(",")[0].strip().split()
                if first:
                    add_url(first[0], only_if_in_main=True)

    # 3. Regex on main_html only (so we only get URLs from product area)
    for match in _WIX_MEDIA_URL_RE.findall(main_html):
        add_url(match)
        if len(ordered) >= 12:
            break

    return ordered[:12]


# Wix product pages embed an ``"options":[{...}]`` JSON array in inline
# storefront data. Each entry is one user-facing dropdown (``"Clear Coat
# Finish"``, ``"Turbo Choice"``, ``"Side"``); each entry's ``selections``
# array lists the choosable values. The label often encodes a price delta
# (``"Matte +$22"``, ``"JB4PRO +$300 (fuel options)"``) — Wix does not expose
# per-variant SKUs in this block, so the delta is the only structured price
# signal available without scraping the live storefront API.
_WIX_OPTIONS_KEY_RE = re.compile(r'"options"\s*:\s*\[')

# Match ``+$22``, ``+$300``, ``+ $1,200``, ``$22``, ``$1,004.99`` inside a
# selection label. Capture the numeric portion. We look for the first
# dollar-anchored token; non-dollar numbers in the label (``"V2"``, ``"288 /
# 288 Stage 3"``) are NOT prices and must not be treated as deltas.
_PRICE_DELTA_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")

# Conservative cap on how many variants we emit per page. A turbo-kit page
# with 6 turbo choices × 5 yes/no add-ons is 7 categorically-distinct extras
# at most under our per-option (no-cross-product) split — clamp to 12 so a
# pathological page can't fan out to dozens of part rows.
_MAX_VARIANTS_PER_PAGE = 12

# Minimum dollar delta to treat a numeric ``+$NN`` selection as a distinct
# variant. Smaller deltas are usually rounding / minor finish differences
# we'd rather collapse into the canonical part. Categorical-axis selections
# (Side, Position, Drive Type, Turbo Choice, etc.) bypass this floor — they
# are different products even at $0 delta.
_VARIANT_PRICE_DELTA_MIN_CENTS = 500

# When the Wix ``options[].title`` matches one of these keywords (case-
# insensitive), all non-default selections on that option are split into
# distinct variants regardless of price delta — these axes describe genuinely
# different products (turbo type, brake-pad position, drive-side LHD/RHD).
_CATEGORICAL_OPTION_TOKENS = (
    "turbo",
    "position",
    "side",
    "option",
    "version",
    "configuration",
    "type",
    "pad",
    "kit",
    "drive type",
)


def _slugify_variant(value: str) -> str:
    """Lowercase + collapse non-alphanumerics to a single hyphen.

    The slug feeds two distinct keys: the ``?variant=<slug>`` query param
    (must be URL-safe and stable across re-crawls) and the synthetic part
    number suffix (``<base_pn>-<slug>``). Keep it short — labels include
    promotional text (``"+$22"``, ``"(fuel options)"``) we want to drop.
    """
    cleaned = re.sub(r"\$\s*[\d,]+(?:\.\d{1,2})?", "", value)
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-")
    return cleaned[:40] if cleaned else "variant"


def _extract_wix_options_block(html: str) -> List[dict]:
    """Locate the first ``"options":[...]`` array in inline Wix storefront data.

    Wix embeds the product object as inline JSON; there's no canonical
    ``application/json`` script tag we can latch onto, so we anchor on the
    literal key and walk brackets in string-aware mode (escapes + quoted
    bracket characters in selection labels). Returns ``[]`` when the page
    has no Wix options block, when the JSON is malformed, or when the array
    contains no dict entries with a ``selections`` field — never raises.
    """
    match = _WIX_OPTIONS_KEY_RE.search(html)
    if not match:
        return []
    start = match.end() - 1  # the ``[`` itself
    depth = 0
    in_str = False
    esc = False
    end = -1
    limit = min(start + 200_000, len(html))
    for k in range(start, limit):
        c = html[k]
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
        arr = json.loads(html[start:end])
    except (ValueError, json.JSONDecodeError):
        return []
    if not isinstance(arr, list):
        return []
    return [o for o in arr if isinstance(o, dict) and isinstance(o.get("selections"), list)]


def _parse_price_delta_cents(label: str) -> Optional[int]:
    """Pull the first ``$NN`` dollar amount out of a Wix selection label.

    Handles ``"+$22"``, ``"Matte +$22"``, ``"JB4PRO +$300 (fuel options)"``,
    ``"Yes $1,004.99"``. Returns ``None`` when no dollar-anchored amount is
    present (color/finish toggles like ``"Gloss"`` / ``"Black"`` carry no
    delta and stay collapsed under their categorical-or-price filter).
    """
    if not label:
        return None
    match = _PRICE_DELTA_RE.search(label)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        dollars = float(raw)
    except ValueError:
        return None
    if dollars <= 0:
        return None
    return int(round(dollars * 100))


def _is_categorical_option(option_title: str) -> bool:
    """True if the option title names a categorical axis (vs. a finish toggle)."""
    title = (option_title or "").strip().lower()
    if not title:
        return False
    return any(tok in title for tok in _CATEGORICAL_OPTION_TOKENS)


def _label_without_price(label: str) -> str:
    """Strip the trailing ``+$NN`` / ``$NN`` token so we get a clean variant name."""
    cleaned = re.sub(r"\s*\+?\s*\$\s*[\d,]+(?:\.\d{1,2})?\s*", " ", label or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _build_variant_payload(
    base: ScrapedPayload,
    *,
    option_title: str,
    selection_label: str,
    delta_cents: Optional[int],
) -> Optional[ScrapedPayload]:
    """Derive a per-variant ``ScrapedPayload`` from the base part + one Wix selection.

    Returns ``None`` when the selection is the implicit default (label
    matches the base name) or when the slug would be empty. The returned
    payload differs from ``base`` only in:

      * ``name`` — appended ``" (<option> · <selection>)"``.
      * ``product_url`` — base URL + ``?variant=<slug>``.
      * ``part_number`` — base + ``-<slug>`` (when base has one); else ``None``.
      * ``price_cents`` — base + delta (when base price is known and delta
        is set); else inherits base.
    """
    label_clean = _label_without_price(selection_label)
    if not label_clean:
        return None
    slug = _slugify_variant(selection_label)
    if not slug:
        return None

    sep = "&" if "?" in base.product_url else "?"
    variant_url = f"{base.product_url}{sep}variant={slug}"

    label_for_name = label_clean
    title_for_name = (option_title or "").strip()
    if title_for_name:
        variant_name_suffix = f" ({title_for_name}: {label_for_name})"
    else:
        variant_name_suffix = f" ({label_for_name})"
    variant_name = (base.name or "") + variant_name_suffix

    variant_part_number: Optional[str] = None
    if base.part_number:
        variant_part_number = f"{base.part_number}-{slug}"

    if base.price_cents is not None and delta_cents:
        variant_price_cents: Optional[int] = base.price_cents + delta_cents
    else:
        variant_price_cents = base.price_cents

    return ScrapedPayload(
        name=variant_name,
        product_url=variant_url,
        description=base.description,
        price_cents=variant_price_cents,
        part_manufacturer=base.part_manufacturer,
        part_number=variant_part_number,
        image_urls=base.image_urls,
        gtin=None,  # variant SKUs do not share the base GTIN; safer to omit
    )


def _a90_extract_variant_payloads(html: str, base: ScrapedPayload) -> List[ScrapedPayload]:
    """Top-level variant extractor for an A90 Shop product page.

    For each Wix option block on the page, treat the FIRST selection as the
    base/default (already represented by ``base``) and emit additional
    payloads for the remaining selections that pass the
    delta-or-categorical filter. We deliberately do NOT cross-product
    multi-axis options — A90 Shop labels carry per-option deltas only, so a
    cross-product would generate combinatorial variants without correct
    per-combo prices. Per-axis splits give the catalog distinct rows for
    the "interesting" selections (turbo type, JB4 vs JB4PRO, brake pad
    position) without inventing prices we can't verify.
    """
    if not base or not base.product_url or not base.name:
        return []
    options = _extract_wix_options_block(html)
    if not options:
        return []

    out: List[ScrapedPayload] = []
    seen_urls: set[str] = set()
    seen_urls.add(base.product_url)
    for opt in options:
        title = str(opt.get("title") or opt.get("key") or "").strip()
        selections = opt.get("selections") or []
        if not isinstance(selections, list) or len(selections) < 2:
            continue
        categorical = _is_categorical_option(title)
        # First selection is the implicit default — base payload covers it.
        for sel in selections[1:]:
            if not isinstance(sel, dict):
                continue
            label = str(sel.get("value") or sel.get("description") or "").strip()
            if not label:
                continue
            delta = _parse_price_delta_cents(label)
            if delta is None and not categorical:
                continue
            if delta is not None and delta < _VARIANT_PRICE_DELTA_MIN_CENTS and not categorical:
                continue
            variant = _build_variant_payload(
                base,
                option_title=title,
                selection_label=label,
                delta_cents=delta,
            )
            if variant is None:
                continue
            if variant.product_url in seen_urls:
                continue
            seen_urls.add(variant.product_url)
            out.append(variant)
            if len(out) >= _MAX_VARIANTS_PER_PAGE:
                return out
    return out


class A90ShopAdapter(RetailerCrawlerAdapter):
    """
    A90 Shop adapter. Discovery: start URLs from env or default list.
    Parsing: JSON-LD first, then Wix-style DOM (h1, SKU:, From $..., og:meta).
    """

    ADAPTER_NAME: ClassVar[str] = "a90shop"
    category_targets: ClassVar[list[str]] = ["universal"]

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Uses sitemap.xml (and child sitemaps) to find all
        /product-page/ URLs. Set CRAWLER_A90SHOP_START_URLS (comma-separated) to
        override with a fixed list. Runner applies --limit to cap how many are processed.
        """
        for url in _resolve_start_urls():
            yield url

    def extract_variants(
        self,
        html: str,
        url: str,
        base_payload: ScrapedPayload,
    ) -> List[ScrapedPayload]:
        """Split Wix multi-variant product pages into one ScrapedPayload per SKU.

        Delegates to ``_a90_extract_variant_payloads``; see that helper for
        the per-axis split rules. Returns ``[]`` when the page has no
        multi-variant options block, when every selection is the default,
        or when no selection passes the delta-or-categorical filter — the
        common case for single-SKU A90 Shop pages.
        """
        _ = url  # base_payload.product_url already encodes the page URL
        return _a90_extract_variant_payloads(html, base_payload)

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse A90 Shop product page. JSON-LD first, then A90-specific selectors.
        We always run DOM image extraction (Wix often omits images from JSON-LD)
        and merge images into the payload before returning.
        """
        soup = BeautifulSoup(html, "html.parser")
        dom_images = _extract_a90_images(soup, html)
        dom_price = extract_dom_price(soup)

        # 1. JSON-LD (same strategy as chrome-extension)
        item = extract_json_ld_product(html, product_url=url)
        if item:
            payload = scraped_payload_from_json_ld(item, url)
            if payload and payload.name:
                # Merge DOM images and price when JSON-LD omits them (common on Wix)
                price_cents = payload.price_cents if payload.price_cents is not None else dom_price
                if dom_images or price_cents is not None:
                    payload = ScrapedPayload(
                        name=payload.name,
                        product_url=payload.product_url,
                        description=payload.description,
                        price_cents=price_cents,
                        part_manufacturer=payload.part_manufacturer,
                        part_number=payload.part_number,
                        image_urls=dom_images[:12] if dom_images else payload.image_urls,
                        gtin=payload.gtin,
                    )
                return payload

        # 2. DOM fallback: og:meta, h1, SKU, price, description
        name = None
        og_title = soup.find("meta", property="og:title")
        content_title = meta_content(og_title) if isinstance(og_title, Tag) else None
        if content_title and content_title.strip():
            name = content_title.strip()
        if not name:
            h1 = soup.find("h1")
            if h1:
                h1_text = h1.get_text(strip=True)
                if h1_text:
                    name = h1_text
        if not name or len(name) < 3:
            return None

        description = None
        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag):
            d = meta_content(og_desc)
            if d and d.strip():
                description = d.strip()[:2000]
        if not description:
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if isinstance(meta_desc, Tag):
                d = meta_content(meta_desc)
                if d and d.strip():
                    description = d.strip()[:2000]
        if not description:
            # First long paragraph in main content
            for p in soup.find_all("p"):
                t = p.get_text(strip=True)
                if t and len(t) > 80 and "related" not in t.lower()[:50]:
                    description = t[:2000]
                    break

        price_cents = extract_dom_price(soup)

        part_number = None
        sku_elem = soup.find(class_=re.compile(r"sku", re.I)) or soup.find(id=re.compile(r"sku", re.I))
        if sku_elem:
            part_number = normalize_part_number(sku_elem.get_text(strip=True))
        if not part_number:
            part_number = extract_sku_from_text(soup.get_text())
        if not part_number:
            part_number = normalize_part_number(extract_part_number_candidate_from_title(str(name)))

        part_manufacturer = part_manufacturer_from_title(str(name))
        if not part_manufacturer and description:
            part_manufacturer = part_manufacturer_from_description(description, product_name=str(name))
        if not part_manufacturer:
            part_manufacturer = part_manufacturer_fallback_from_title(str(name))

        image_urls = dom_images[:12] if dom_images else None

        return ScrapedPayload(
            name=str(name),
            product_url=url,
            description=description if description else None,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=image_urls,
        )
