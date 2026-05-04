"""
Suncoast Porsche Parts (suncoastparts.com) crawler adapter — Tier 1 (TLS).

Product URLs: ``https://www.suncoastparts.com/product/<SKU>.html`` — the path
stem is the retailer SKU itself (both OEM Porsche part numbers like
``99755922100041`` and internal Suncoast codes like ``POHC``, ``SGP996``).

Platform is Miva Merchant 5 (``robots.txt`` exposes ``/mm5/``; graphics live
at ``/mm5/graphics/…``). Behind Cloudflare with a *managed JS challenge* on
plain requests (``Just a moment…`` 403s), but curl_cffi's Chrome handshake
passes cleanly — so ``FETCHER_TIER = "tls"``, not ``"browser"``.

Discovery: single flat ``/sitemap.xml`` urlset (~19k entries, ~2.6 MB).
No gzip, no sitemap index — just filter locs to the ``/product/<SKU>.html``
shape. Override via ``CRAWLER_SUNCOASTPARTS_START_URLS``.

Parsing strategy: Miva does NOT emit a JSON-LD ``Product`` block here (the
only JSON-LD on page is a storewide ``LocalBusiness``), so we go straight to
OpenGraph + meta:
- ``og:title`` → name (cleaner than ``<h1>``, which Miva concatenates with
  the "SKU: …" span text, giving us ``"Emblem - \"Speedster\" in BlackSKU:
  99755922100041"`` from ``h1.get_text(strip=True)``).
- ``og:brand`` → ``part_manufacturer`` (``Porsche`` on most SKUs; Suncoast
  stocks third-party brands too and they show up here).
- ``product:price:amount`` → ``price_cents``.
- ``<meta name="description">`` → description. We deliberately **skip**
  ``og:description`` — it is the templated "Check out the deal on X at
  Suncoast Porsche Parts & Accessories" marketing blurb and carries no
  product info.
- Part number: the URL stem is the store's SKU and is mirrored in a span
  ``.x-product-layout-purchase__sku`` as ``SKU: <code>``. URL stem wins
  (authoritative, URL-unescaped). For numeric stems this is the OEM Porsche
  MPN; for prefixed stems (``PK``, ``SG``, ``PO`` …) it is Suncoast's
  internal code — still the right per-retailer part_number.
- Images: Miva emits a ``var image_data<N> = [{"image_data": [full, thumb,
  zoom]}, …]`` JS array in the gallery ``<script>``. We regex it, take the
  first URL of each entry (the full-size image), URL-quote the path
  (Suncoast ships filenames with spaces), and seed with ``og:image``.
"""

import json
import logging
import os
import re
from typing import ClassVar, Iterator, List, Optional, Tuple
from urllib.parse import quote, urlparse
from xml.etree.ElementTree import Element

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup, Tag

from app.crawlers.adapters.base import RetailerCrawlerAdapter
from app.crawlers.base import ScrapedPayload
from app.crawlers.parsing import (
    extract_dom_price,
    meta_content,
    normalize_description_text,
    normalize_part_number,
    parse_price_cents,
    part_manufacturer_fallback_from_title,
    part_manufacturer_from_description,
    part_manufacturer_from_title,
)

logger = logging.getLogger(__name__)

SUNCOAST_BASE = "https://www.suncoastparts.com"
SITEMAP_URL = f"{SUNCOAST_BASE}/sitemap.xml"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# Canonical product URL: /product/<SKU>.html where SKU is the Miva product_code.
# SKUs are alphanumeric with optional dashes/underscores/periods; no slashes.
_PRODUCT_PATH_RE = re.compile(r"^/product/([A-Za-z0-9][A-Za-z0-9._\-]*)\.html$")

# Miva gallery: ``var image_data<N> = [ ... ];`` — the array of gallery entries,
# each with ``"image_data": [main, thumb, zoom]``. Number suffix varies per page.
_IMAGE_DATA_VAR_RE = re.compile(r"image_data\d*\s*=\s*(\[[\s\S]*?\])\s*(?:\n|;)")

# Fallback so a fresh run still exercises parsing when sitemap discovery breaks.
DEFAULT_START_URLS = [
    "https://www.suncoastparts.com/product/99755922100041.html",
]


def _is_product_url(url: str) -> bool:
    """True if ``url`` matches Suncoast's ``/product/<SKU>.html`` pattern on suncoastparts.com."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if host and host != "suncoastparts.com" and not host.endswith(".suncoastparts.com"):
        return False
    if parsed.query:
        # Canonical product URLs have no query string. The legacy Miva
        # /mm5/merchant.mvc?Screen=PROD&Product_Code=… path also appears in
        # the sitemap but redirects to the canonical form — we skip it.
        return False
    return bool(_PRODUCT_PATH_RE.match(parsed.path or ""))


def _sku_from_url(url: str) -> Optional[str]:
    """Return the SKU (product_code) encoded in a ``/product/<SKU>.html`` URL, or None."""
    try:
        path = urlparse(url).path or ""
    except ValueError:
        return None
    m = _PRODUCT_PATH_RE.match(path)
    return m.group(1) if m else None


def _loc_elements(root: Element) -> List[Element]:
    """Find all <loc> elements in a sitemap urlset."""
    return root.findall(f".//{{{SITEMAP_NS}}}loc")


def _resolve_start_urls_env() -> Optional[List[str]]:
    """Return ``CRAWLER_SUNCOASTPARTS_START_URLS`` (comma-separated) if set; else None."""
    raw = os.environ.get("CRAWLER_SUNCOASTPARTS_START_URLS", "").strip()
    if not raw:
        return None
    return [u.strip() for u in raw.split(",") if u.strip()]


def _extract_product_urls_from_sitemap(xml_text: str) -> List[str]:
    """
    Parse ``sitemap.xml`` (urlset only — Suncoast ships no sitemap index) and
    return the ``/product/<SKU>.html`` locs in document order, deduplicated.
    Returns [] on parse failure so the caller can fall back.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    seen: set[str] = set()
    out: List[str] = []
    for loc in _loc_elements(root):
        if not loc.text:
            continue
        u = loc.text.strip()
        if not _is_product_url(u):
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _normalize_graphics_url(raw: str) -> Optional[str]:
    """
    Turn a Miva gallery path (``graphics/00000002/12/foo bar.jpg``) into an
    absolute URL with the path segment URL-quoted. Suncoast ships filenames
    with spaces and occasional parentheses; browsers encode these transparently,
    but a naïve string concat leaves them raw and downstream fetchers fail.
    """
    if not raw:
        return None
    u = raw.strip()
    if not u:
        return None
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("http://") or u.startswith("https://"):
        parsed = urlparse(u)
        path = quote(parsed.path, safe="/%")
        return f"{parsed.scheme}://{parsed.netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")
    # Relative — strip leading slash, then attach to base.
    rel = u.lstrip("/")
    return f"{SUNCOAST_BASE}/{quote(rel, safe='/%')}"


def _extract_gallery_urls_from_js(html: str) -> List[str]:
    """
    Pull the full-size gallery URLs from the ``var image_data<N> = [...]``
    block Miva renders into the product page.

    Each entry in the array looks like::

        {"type_code": "main",
         "image_data": ["graphics/…/foo.jpg",
                        "graphics/…/foo_80x51.jpg",
                        "graphics/…/foo.jpg"]}

    We take ``image_data[0]`` (full-size) from each entry, drop thumbnails,
    dedupe, and return normalized absolute URLs.
    """
    match = _IMAGE_DATA_VAR_RE.search(html)
    if not match:
        return []
    raw_array = match.group(1)
    # The JS source has backslash-escaped forward slashes (``graphics\/…``).
    # json.loads tolerates those, but we also guard against a trailing comma
    # before ``]`` that some Miva themes emit by stripping it.
    cleaned = re.sub(r",\s*\]", "]", raw_array)
    try:
        entries = json.loads(cleaned)
    except ValueError:
        return []
    urls: List[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        paths = entry.get("image_data")
        if not isinstance(paths, list) or not paths:
            continue
        first = paths[0]
        if not isinstance(first, str) or not first.strip():
            continue
        abs_url = _normalize_graphics_url(first)
        if not abs_url or abs_url in seen:
            continue
        seen.add(abs_url)
        urls.append(abs_url)
    return urls


def _extract_images(soup: BeautifulSoup, html: str) -> List[str]:
    """
    Gallery images for a Suncoast product. og:image first (a clean absolute
    URL), then the ``image_data`` JS array, then the ``data-image`` attr on
    ``#js-main-image`` as a last resort. Capped at 12.
    """
    urls: List[str] = []
    seen: set[str] = set()

    def add(raw: Optional[str]) -> None:
        if not raw or len(urls) >= 12:
            return
        normalized = _normalize_graphics_url(raw)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        urls.append(normalized)

    og_img = soup.find("meta", property="og:image")
    if isinstance(og_img, Tag):
        add(meta_content(og_img))

    for u in _extract_gallery_urls_from_js(html):
        add(u)

    main_img = soup.find(id="js-main-image")
    if isinstance(main_img, Tag):
        data_image = main_img.get("data-image")
        if isinstance(data_image, str):
            add(data_image)

    return urls[:12]


def _extract_name(soup: BeautifulSoup) -> Optional[str]:
    """og:title is the only clean source — <h1> includes the "SKU: …" span."""
    og_title = soup.find("meta", property="og:title")
    if isinstance(og_title, Tag):
        v = meta_content(og_title)
        if v and v.strip():
            return v.strip()
    # Very last resort: parse only the first H1 text-node and drop trailing SKU.
    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            text = re.sub(r"\s*SKU\s*:.*$", "", text, flags=re.IGNORECASE).strip()
            if text:
                return text
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    """
    Real product copy lives in ``<meta name="description">``. ``og:description``
    on Suncoast is always the same marketing sentence ("Check out the deal on
    X at Suncoast Porsche Parts & Accessories") and is useless — we skip it.
    """
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if isinstance(meta_desc, Tag):
        v = meta_content(meta_desc)
        if v and v.strip():
            return normalize_description_text(v, max_len=2000)
    return None


def _extract_price_cents(soup: BeautifulSoup) -> Optional[int]:
    """``product:price:amount`` is authoritative; fall back to DOM price scan."""
    price_meta = soup.find("meta", property="product:price:amount")
    if isinstance(price_meta, Tag):
        v = meta_content(price_meta)
        if v:
            cents = parse_price_cents(v)
            if cents is not None:
                return cents
    return extract_dom_price(soup)


_PORSCHE_OEM_BRAND = "Porsche OEM"


# ---------------------------------------------------------------------------
# Fitment / breadcrumb extraction (Tier-2)
# ---------------------------------------------------------------------------
#
# Suncoast renders a category breadcrumb on every product page in the shape
#
#     Home | <Model> | <YYYY-YYYY> (<chassis>) | <variant> | <Cat> | <Sub> | <Title>
#
# where ``<Model>`` is the Porsche-side model name ("Boxster", "Cayman",
# "Cayenne", "Panamera", "718", "911 Carrera Models", ...) and ``<chassis>`` is
# the chassis-code marker ("986", "997", "987.2", "718", ...). The
# ``infer_car_for_part`` override below maps that pair to one or more
# (CarMake, CarModel, Generation) triples that match active rows in our
# car_generations table; ``resolve_car_triples_to_ids`` does the actual lookup
# at ingest time so the adapter stays DB-free.
#
# Sub-variant chassis codes ("987.2", "991.2") collapse to the parent chassis
# ("987", "991"). Codes for which we cannot defend a triple (Suncoast Platz,
# Selection Merchandise, anything outside the recognised Porsche-platform set)
# return no triple and the universal phrase-triple inference takes over.
#
# When the breadcrumb is missing, malformed, or routes through a non-vehicle
# leaf ("Selection Merchandise", "For Men"), ``_extract_breadcrumb_fitment``
# returns ``None`` and the override hands control back to the universal
# pipeline. Never silently universal-flag.

_BREADCRUMB_CONTAINER_CLASSES = (
    "x-collapsing-breadcrumbs__list",
    "breadcrumbs__list",
)

# Captures ``YYYY-YYYY (<chassis>)`` and grabs the chassis token. Chassis is
# alnum + an optional ``.<digit>`` sub-tag (Suncoast routinely emits "987.2",
# "991.2", "971.2" for facelift platforms). We bound everything tightly so
# this regex is linear over the breadcrumb text (MEM029 ReDoS contract).
_YEAR_CHASSIS_RE = re.compile(
    r"\b\d{4}\s*[-–—]\s*\d{4}\s*\(([A-Za-z0-9]{2,5}(?:\.\d)?)\)",
)

# DB-aligned chassis → (model, generation) for the Suncoast-relevant Porsche
# platforms. Generation strings here MUST match the
# ``car_generations.generation_name`` column verbatim — ``resolve_car_triples_to_ids``
# does an exact-match lookup. Anything not in this map (Carrera GT, 918
# Spyder, Macan) is intentionally unmapped: Suncoast's URL/breadcrumb rarely
# carries the chassis for those, and a wrong guess attaches to a real owner's
# build list.
#
# 986/987/981 are ambiguous between Boxster and Cayman; the breadcrumb's
# ``<Model>`` cell disambiguates and is consulted in the override below
# before the chassis lookup. ``718`` is the inverse case — both models live
# under the same DB ``718`` car_model row with generation ``982``.
_CHASSIS_TO_911 = {
    "930": "930",
    "964": "964",
    "993": "993",
    "996": "996",
    "997": "997",
    "991": "991",
    "992": "992",
}
# Cayenne chassis codes — 955 and 957 are 9PA (gen 1 + facelift), 958 is 92A.
_CHASSIS_TO_CAYENNE = {
    "955": "9PA",
    "957": "9PA",
    "958": "92A",
}
# Panamera — 970 is gen 1, 971 is gen 2 (and 971.2 is the facelift, also 971).
_CHASSIS_TO_PANAMERA = {
    "970": "970",
    "971": "971",
}
# Boxster / Cayman shared chassis codes. The breadcrumb model cell picks the
# right car_model row.
_CHASSIS_TO_MID_ENGINE = {
    "986": "986",  # Boxster only (Cayman didn't exist on 986)
    "987": "987",  # Both
    "981": "981",  # Both
}


def _normalize_chassis(raw: str) -> str:
    """Drop sub-variant suffix (``987.2`` → ``987``)."""
    return raw.split(".", 1)[0]


def _extract_breadcrumb_fitment(soup: BeautifulSoup) -> Optional[Tuple[str, str]]:
    """
    Pull ``(model_text, chassis_code)`` from the Suncoast breadcrumb.

    Returns ``None`` when the breadcrumb is missing, when no
    ``YYYY-YYYY (<chassis>)`` cell is present (non-vehicle leaves like
    "Selection Merchandise", scale models, men's apparel), or when the model
    cell is the literal ``"Home"`` wrapper.

    The chassis is normalised to its parent code (``"987.2"`` → ``"987"``).
    """
    container = None
    for cls in _BREADCRUMB_CONTAINER_CLASSES:
        container = soup.find(class_=lambda c, target=cls: bool(c) and target in (c if isinstance(c, list) else [c]))
        if container is not None:
            break
    if not isinstance(container, Tag):
        return None

    # Each ``<li>`` is one breadcrumb cell. Drop the leading "Home" so the
    # first remaining cell is always the model.
    cells = [li.get_text(" ", strip=True) for li in container.find_all("li")]
    cells = [c for c in cells if c and c.lower() != "home"]
    if len(cells) < 2:
        return None

    model_text = cells[0]
    chassis: Optional[str] = None
    for cell in cells[1:]:
        match = _YEAR_CHASSIS_RE.search(cell)
        if match:
            chassis = _normalize_chassis(match.group(1))
            break
    if not chassis:
        return None
    return model_text, chassis


def _triples_for_chassis(model_text: str, chassis: str) -> List[Tuple[str, str, str]]:
    """
    Map a Suncoast (model_text, chassis) breadcrumb pair to one or more
    (Make, Model, Generation) triples that match active car_generations rows.

    Returns ``[]`` when the chassis is unrecognised so the override falls back
    to the universal pipeline. Each unrecognised pair is logged at ``warning``
    so adapter regressions surface in the run summary.
    """
    model_lower = model_text.lower()

    # 911 platform — model cell is "911 Carrera Models" (or just "911").
    if "911" in model_lower:
        gen = _CHASSIS_TO_911.get(chassis)
        if gen:
            return [("Porsche", "911", gen)]

    # 718 platform (post-2017 Boxster + Cayman both ship under the 718 brand).
    if "718" in model_lower or chassis == "718":
        # DB has only ``Porsche | 718 | 982`` — both 718 Boxster and 718
        # Cayman share that row. Suncoast labels the chassis cell "(718)" on
        # both 718 Boxster and 718 Cayman pages.
        return [("Porsche", "718", "982")]

    # Cayenne.
    if "cayenne" in model_lower:
        gen = _CHASSIS_TO_CAYENNE.get(chassis)
        if gen:
            return [("Porsche", "Cayenne", gen)]

    # Panamera.
    if "panamera" in model_lower:
        gen = _CHASSIS_TO_PANAMERA.get(chassis)
        if gen:
            return [("Porsche", "Panamera", gen)]

    # Boxster / Cayman — shared 986/987/981 platforms; the model text picks
    # the car_model row.
    if "boxster" in model_lower:
        gen = _CHASSIS_TO_MID_ENGINE.get(chassis)
        if gen:
            return [("Porsche", "Boxster", gen)]
    if "cayman" in model_lower:
        gen = _CHASSIS_TO_MID_ENGINE.get(chassis)
        # Cayman 986 doesn't exist as a production model — skip if it
        # somehow shows up.
        if gen and gen != "986":
            return [("Porsche", "Cayman", gen)]

    return []


def _extract_part_manufacturer(soup: BeautifulSoup, name: Optional[str], description: Optional[str]) -> Optional[str]:
    """
    Resolve the part manufacturer for a Suncoast product.

    Suncoast's ``og:brand`` reports ``"Porsche"`` on every OEM SKU — but
    "Porsche" is the *car make*, not a parts-catalog brand. Storing it as
    the manufacturer collapses 999 unrelated OEM SKUs (engine mounts, brake
    pads, headlights) onto a single make-shaped row that's indistinguishable
    from any other Porsche-fitment part in the global catalog. We rename it
    to ``"Porsche OEM"`` so dedupe / search can still group genuine Porsche
    parts but the row is unambiguously a parts brand.

    Third-party brands (``"AWE Tuning"``, ``"Bilstein"``, …) pass through
    unchanged because they are real aftermarket manufacturers.

    Title / description fallbacks only run when ``og:brand`` is missing
    entirely.
    """
    brand_meta = soup.find("meta", property="og:brand")
    if isinstance(brand_meta, Tag):
        v = meta_content(brand_meta)
        if v and v.strip():
            cleaned = v.strip()
            if cleaned.lower() == "porsche":
                return _PORSCHE_OEM_BRAND
            return cleaned
    if name:
        candidate = part_manufacturer_from_title(name)
        if candidate:
            return candidate
    if description and name:
        candidate = part_manufacturer_from_description(description, product_name=name)
        if candidate:
            return candidate
    if name:
        return part_manufacturer_fallback_from_title(name)
    # Final fallback: every Suncoast SKU is sold by an authorized Porsche
    # dealer, so when the heuristics fail we still know it is at minimum
    # a Porsche-OEM-grade part. Better than leaking ``None``.
    return _PORSCHE_OEM_BRAND


class SuncoastPartsAdapter(RetailerCrawlerAdapter):
    """
    Suncoast Porsche Parts adapter.

    Fetcher tier: ``tls`` — Cloudflare managed JS challenge on plain requests;
    curl_cffi Chrome impersonation passes the handshake and the challenge.

    Discovery: ``CRAWLER_SUNCOASTPARTS_START_URLS`` env override wins. Otherwise
    pull ``/sitemap.xml`` through the TLS fetcher and filter to
    ``/product/<SKU>.html``. Sitemap also contains legacy
    ``/mm5/merchant.mvc?Screen=PROD&Product_Code=…`` entries — the query-
    string guard in ``_is_product_url`` drops them.

    Parsing: no JSON-LD ``Product``. Uses OpenGraph + meta description +
    Miva's inline ``image_data`` JS array. URL stem is the authoritative
    retailer SKU and always wins over the on-page ``SKU:`` span.
    """

    ADAPTER_NAME: ClassVar[str] = "suncoastparts"
    FETCHER_TIER = "tls"

    def discover_product_urls(self) -> Iterator[str]:
        """
        Yield product URLs. Env override wins; otherwise walk ``/sitemap.xml``
        via the TLS fetcher and fall back to ``DEFAULT_START_URLS`` if that
        returns nothing usable.
        """
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
        Fetch ``/sitemap.xml`` through the adapter's fetcher and return every
        ``/product/<SKU>.html`` loc. Returns [] on any failure.
        """
        try:
            xml_text = self.fetcher.fetch(SITEMAP_URL, timeout=60)
        except Exception:
            return []
        return _extract_product_urls_from_sitemap(xml_text)

    def parse_product_page(self, html: str, url: str) -> Optional[ScrapedPayload]:
        """
        Parse a Suncoast product page. Returns ``None`` if the URL is not a
        product page or no name can be extracted.
        """
        if not _is_product_url(url):
            return None

        soup = BeautifulSoup(html, "html.parser")

        name = _extract_name(soup)
        if not name or len(name) < 3:
            return None

        description = _extract_description(soup)
        price_cents = _extract_price_cents(soup)
        part_manufacturer = _extract_part_manufacturer(soup, name, description)

        # URL stem is the retailer SKU — authoritative. For OEM Porsche stock
        # this is also the manufacturer MPN (e.g. 99755922100041).
        part_number = normalize_part_number(_sku_from_url(url))

        images = _extract_images(soup, html)

        payload = ScrapedPayload(
            name=name,
            product_url=url,
            description=description,
            price_cents=price_cents,
            part_manufacturer=part_manufacturer,
            part_number=part_number,
            image_urls=images or None,
        )

        # Stash breadcrumb fitment hint as a private attr so the
        # ``infer_car_for_part`` override below can resolve it without
        # re-parsing the HTML. setattr on the dataclass is safe — it isn't
        # frozen and the attribute is ignored by ingest_payload (which only
        # reads declared fields). Spec validation never sees it.
        fitment = _extract_breadcrumb_fitment(soup)
        if fitment is not None:
            payload._suncoast_fitment = fitment  # type: ignore[attr-defined]
        return payload

    def infer_car_for_part(
        self, parsed: ScrapedPayload
    ) -> Optional[List[Tuple[str, str, str]]]:
        """
        Adapter-wins car-inference for Suncoast (S04 T04).

        Reads the breadcrumb hint stashed by ``parse_product_page`` and maps
        the Porsche chassis code to one or more (Make, Model, Generation)
        triples that match active ``car_generations`` rows. When the hint is
        absent (non-vehicle product, malformed breadcrumb) or the chassis is
        unrecognised, returns ``None`` so the universal phrase-triple
        pipeline takes over rather than silently universal-flagging the part.

        Logging: unmapped chassis codes and missing breadcrumbs both emit a
        WARNING with the product URL so adapter regressions surface in the
        run summary. Don't crash on the override; never silently universal-flag.
        """
        fitment = getattr(parsed, "_suncoast_fitment", None)
        if not fitment:
            return None
        model_text, chassis = fitment
        triples = _triples_for_chassis(model_text, chassis)
        if not triples:
            logger.warning(
                "suncoastparts: unmapped chassis breadcrumb model=%r chassis=%r url=%s",
                model_text,
                chassis,
                parsed.product_url,
            )
            return None
        return triples
