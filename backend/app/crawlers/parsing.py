"""
Shared parsing helpers used by multiple crawler adapters.

Mirrors the high-level logic from the chrome-extension content script:
JSON-LD Product schema first, then price/SKU regex and DOM fallbacks.
Adapters can use these and add retailer-specific selectors.
"""

import html
import json
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.base import ScrapedPayload


def meta_content(tag: Optional[Tag]) -> Optional[str]:
    """
    Get meta tag content as string. bs4 can return a list for multi-valued attrs;
    this returns a single string or None. Reusable across crawlers (og:title, og:description, etc.).
    """
    if not isinstance(tag, Tag):
        return None
    content = tag.get("content")
    return content if isinstance(content, str) else None


def extract_dom_price(soup: BeautifulSoup) -> Optional[int]:
    """
    Extract first price in cents from DOM: try product:price:amount / og:price:amount
    meta tags, then first $... pattern in body text. Reusable across Shopify/Wix/etc.
    """
    for prop in ("product:price:amount", "og:price:amount"):
        meta = soup.find("meta", property=prop)
        if isinstance(meta, Tag):
            content = meta_content(meta)
            if content:
                cents = parse_price_cents(content)
                if cents is not None:
                    return cents
    body = soup.get_text()
    # First $... or "From $..." in body
    match = re.search(r"(?:From\s*)?\$[\s,]?\d+\.?\d*", body)
    if match:
        return parse_price_cents(match.group(0))
    return None


# Chassis/platform codes that are often the first word of product titles (e.g. "E46 M3 VF570", "E9x M3").
# We should not use these as part_manufacturer names; prefer " by PartManufacturerName" or a later token.
_CHASSIS_LIKE_PATTERN = re.compile(
    r"^[A-Z][0-9]{1,3}x?$|^[A-Z][0-9]{2,}$",  # E46, E9x, E90, F80, G82, etc.
    re.IGNORECASE,
)


def _looks_like_chassis_code(word: str) -> bool:
    """True if word looks like a chassis/platform code (E46, E9x, F80, G82) rather than a part manufacturer."""
    if not word or len(word) < 2:
        return False
    return bool(_CHASSIS_LIKE_PATTERN.match(word.strip()))


# Part/model codes in titles (e.g. VF540, VF620, VF570) — use as part_number, not part_manufacturer.
_PART_CODE_PATTERN = re.compile(
    r"^[A-Za-z]{2,}[0-9]{2,}$|^[A-Za-z]+[0-9]+[A-Za-z]*$",  # VF540, VF620, VF570, or alphanumeric
    re.IGNORECASE,
)


def _looks_like_part_or_model_code(word: str) -> bool:
    """True if word looks like a part/model code (VF540, VF620) rather than a part manufacturer name."""
    if not word or len(word) < 2:
        return False
    w = word.strip()
    if len(w) <= 2:
        return False
    if _looks_like_chassis_code(w):
        return False
    return bool(_PART_CODE_PATTERN.match(w))


# Generic product-type words that must never be used as part_manufacturer (Supercharger, Oil, System, etc.).
_GENERIC_PRODUCT_WORDS = frozenset(
    {
        "supercharger",
        "cooler",
        "oil",
        "system",
        "intake",
        "performance",
        "software",
        "kit",
        "kits",
        "exhaust",
        "radiator",
        "radiators",
        "brake",
        "brakes",
        "wheel",
        "wheels",
        "suspension",
        "turbo",
        "turbocharger",
        "intercooler",
        "cold",
        "air",
        "flash",
        "na",
    }
)


def part_manufacturer_from_title(title: str) -> Optional[str]:
    """
    Heuristic for part_manufacturer from product title when JSON-LD part_manufacturer is missing.

    1. Prefer explicit " by PartManufacturerName" (e.g. "... by VF-Engineering").
    2. Otherwise use first word that is not a chassis code (E46, E9x) and not a part code (VF540, VF620).
       Part codes in the title should go to part_number, not part_manufacturer.
    """
    if not title or len(title) < 2:
        return None
    title = title.strip()

    # 1. Explicit " by PartManufacturerName" or " By PartManufacturerName"
    by_match = re.search(r"\s+by\s+([A-Za-z0-9][A-Za-z0-9\-\.\s&]+?)(?:\s*$|\s+by\s+)", title, re.IGNORECASE)
    if by_match:
        part_manufacturer_candidate = by_match.group(1).strip()
        if part_manufacturer_candidate and len(part_manufacturer_candidate) >= 2:
            return part_manufacturer_candidate

    # 2. Two-word part_manufacturers (title often "PartManufacturer Name Product...")
    if re.search(r"\bAC\s+Schnitzer\b", title, re.IGNORECASE):
        return "AC Schnitzer"
    if re.search(r"\bRogue\s+Engineering\b", title, re.IGNORECASE):
        return "Rogue Engineering"
    if re.search(r"\bRadium\s+Engineering\b", title, re.IGNORECASE):
        return "Radium Engineering"
    # JQ Werks — first-token scan below falls through because "JQ" is 2 chars
    # and gets rejected, leaving "WERKS" as the split-off manufacturer. Match
    # the full brand up front so we don't split JQ Werks steering wheel SKUs
    # across two manufacturer rows.
    if re.search(r"\bJQ\s+Werks\b", title, re.IGNORECASE):
        return "JQ Werks"

    # 3. First token that looks like a part_manufacturer (not chassis, not part code, not generic product word)
    parts = title.split()
    for token in parts:
        if not token or len(token) < 3:
            continue
        if _looks_like_chassis_code(token):
            continue
        if _looks_like_part_or_model_code(token):
            continue
        if token.lower() in _GENERIC_PRODUCT_WORDS:
            continue
        if token[0].isupper() or (len(token) > 1 and token[0].isalpha()):
            return token
        break
    return None


def extract_part_number_candidate_from_title(title: str) -> Optional[str]:
    """
    Extract first token that looks like a part/model code (VF540, VF620, VF570) from the title.
    Excludes chassis codes (E9x, E46) — those are not part numbers.
    """
    if not title or not title.strip():
        return None
    for token in title.strip().split():
        if not token:
            continue
        if _looks_like_chassis_code(token):
            continue
        if _looks_like_part_or_model_code(token):
            return token.strip()
    return None


def part_manufacturer_from_description(
    description: str | None,
    *,
    max_chars: int = 800,
    product_name: str | None = None,
) -> Optional[str]:
    """
    Heuristic for part_manufacturer from product description when title didn't yield a part_manufacturer.
    Looks for common patterns like "VF-Engineering", "CSF Radiators", "Studio RSR".

    Only searches the first max_chars so suggested/related-product boilerplate
    (e.g. "StudioRSR.com offers... CSF Radiators") later on the page doesn't win.
    When product_name contains "VF" (e.g. "VF Oil Cooler"), prefer VF-Engineering
    over CSF so we don't assign CSF from a related-product snippet.
    """
    if not description or not description.strip():
        return None
    text = description.strip()
    # Limit to main product description; avoid suggested-product / footer boilerplate
    search_text = text[:max_chars] if len(text) > max_chars else text
    name_has_vf = bool(product_name and re.search(r"\bVF\b", product_name, re.IGNORECASE))
    # Order: VF-Engineering first so we prefer it when both appear
    patterns = [
        (r"\bVF-?Engineering\b", "VF-Engineering"),
        (r"\bVF\s+Engineering\b", "VF-Engineering"),
        (r"\bAC\s+Schnitzer\b", "AC Schnitzer"),
        (r"\bRogue\s+Engineering\b", "Rogue Engineering"),
        (r"\bRadium\s+Engineering\b", "Radium Engineering"),
        (r"\bCSF\s+Radiators?\b", "CSF"),
        (r"\bStudio\s+RSR\b", "Studio RSR"),
        (r"\bHex\s+Tuning\b", "Hex Tuning"),
    ]
    for pattern, part_manufacturer in patterns:
        if not re.search(pattern, search_text, re.IGNORECASE):
            continue
        # If product name has "VF" (e.g. "E9x M3 VF Oil Cooler"), don't assign CSF from
        # a related-product snippet; prefer VF-Engineering if it appears in main description
        if part_manufacturer == "CSF" and name_has_vf:
            if re.search(r"\bVF-?Engineering\b|\bVF\s+Engineering\b", search_text, re.IGNORECASE):
                return "VF-Engineering"
            return None
        return part_manufacturer
    return None


def part_manufacturer_fallback_from_title(title: str) -> Optional[str]:
    """
    When no part_manufacturer was found from JSON-LD, title heuristic, or description, infer from
    known title patterns. E.g. "E9x M3 VF650 Supercharger" has no standalone "VF" but
    "VF650" is a VF-Engineering part code — match VF as prefix of digits or standalone.
    """
    if not title or not title.strip():
        return None
    # VF-Engineering: "VF" standalone or "VF" + digits (VF650, VF540, VF620, etc.)
    if re.search(r"\bVF(?:\b|\d)", title.strip(), re.IGNORECASE):
        return "VF-Engineering"
    return None


def _canonical_url_key(url: Optional[str]) -> Optional[str]:
    """
    Normalize a URL for equality comparison: lowercase scheme+host, strip a
    trailing slash from the path, drop query/fragment. Used to decide whether
    a JSON-LD Product's declared URL refers to the page we're actually parsing.
    Returns None when the input isn't a parseable absolute URL.
    """
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    try:
        parsed = urlparse(s)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"


def _json_ld_product_urls(item: Dict[str, Any]) -> List[str]:
    """Collect the URL-like fields declared on a Product JSON-LD block."""
    urls: List[str] = []

    def _append(val: Any) -> None:
        if isinstance(val, str) and val.strip():
            urls.append(val.strip())
        elif isinstance(val, list):
            for v in val:
                _append(v)
        elif isinstance(val, dict):
            nested = val.get("url") or val.get("@id")
            _append(nested)

    _append(item.get("url"))
    _append(item.get("@id"))
    _append(item.get("sameAs"))
    offers = item.get("offers") or item.get("Offers")
    if isinstance(offers, dict):
        _append(offers.get("url"))
    elif isinstance(offers, list):
        for off in offers:
            if isinstance(off, dict):
                _append(off.get("url"))
    return urls


def extract_json_ld_product(
    html: str,
    *,
    product_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract a Product from JSON-LD script(s). Returns a dict with name,
    description, part_manufacturer, sku, price (from offers), image(s).

    When ``product_url`` is provided, the selector is URL-aware:
      * A Product whose declared ``url`` / ``@id`` / ``sameAs`` / ``offers[].url``
        canonically matches ``product_url`` is preferred — returned immediately.
      * A Product with declared URLs that *all disagree* with ``product_url``
        is rejected (not returned). Some Wix/CMS pages ship JSON-LD for a
        different product than the page URL resolves to; trusting the first
        Product would overwrite the user's scrape with the wrong part.
      * A Product with no declared URL is treated as a candidate and returned
        when no URL-matching block was found — covers sites whose JSON-LD
        omits the URL entirely.

    When ``product_url`` is omitted (or unparseable as an absolute URL), the
    historical behaviour is preserved: first Product wins.
    """
    want_key = _canonical_url_key(product_url)
    soup = BeautifulSoup(html, "html.parser")
    fallback_no_url: Optional[Dict[str, Any]] = None
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        items: List[Dict[str, Any]] = []
        if isinstance(data, list):
            items = cast(List[Dict[str, Any]], data)
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                items = cast(List[Dict[str, Any]], data["@graph"])
            else:
                items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t != "Product" and (not isinstance(t, list) or "Product" not in t):
                continue
            if want_key is None:
                return item
            declared_urls = _json_ld_product_urls(item)
            declared_keys = [k for k in (_canonical_url_key(u) for u in declared_urls) if k]
            if any(k == want_key for k in declared_keys):
                return item
            if not declared_keys and fallback_no_url is None:
                fallback_no_url = item
            # else: Product declares URLs, none match → skip it entirely
    return fallback_no_url


def _part_manufacturer_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    part_manufacturer = item.get("brand")
    if isinstance(part_manufacturer, str) and part_manufacturer.strip():
        return part_manufacturer.strip()
    if isinstance(part_manufacturer, dict):
        name = part_manufacturer.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def _price_from_json_ld(item: Dict[str, Any]) -> Optional[int]:
    offers = item.get("offers")
    if isinstance(offers, list) and offers:
        offer = cast(Dict[str, Any], offers[0])
    else:
        offer = cast(Optional[Dict[str, Any]], offers)
    if not isinstance(offer, dict):
        return None
    for key in ("price", "lowPrice", "highPrice"):
        val = offer.get(key)
        if val is None:
            continue
        try:
            num = float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if not (num > 0):
            continue
        return int(round(num * 100))
    return None


def _images_from_json_ld(item: Dict[str, Any]) -> List[str]:
    img = item.get("image")
    if not img:
        return []
    urls: List[str] = []
    for i in ([img] if isinstance(img, str) else img) if img else []:
        if isinstance(i, str) and i.strip():
            urls.append(i.strip())
        elif isinstance(i, dict) and i.get("url"):
            urls.append(str(i["url"]).strip())
    return urls


def scraped_payload_from_json_ld(item: Dict[str, Any], product_url: str) -> Optional[ScrapedPayload]:
    """
    Build a ScrapedPayload from a JSON-LD Product item. Returns None if missing name.
    Decodes HTML entities and strips HTML from descriptions.
    """
    name_val = item.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None
    name = html.unescape(name)
    desc = item.get("description")
    description = None
    if isinstance(desc, str) and len(desc.strip()) > 10:
        description = normalize_description_text(desc, max_len=2000)
    part_manufacturer = _part_manufacturer_from_json_ld(item)
    sku_val = item.get("sku") or item.get("mpn")
    part_number: Optional[str] = None
    if isinstance(sku_val, str) and sku_val.strip():
        part_number = normalize_part_number(sku_val)
    price_cents = _price_from_json_ld(item)
    images = _images_from_json_ld(item)
    return ScrapedPayload(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=price_cents,
        part_manufacturer=part_manufacturer,
        part_number=part_number,
        image_urls=images[:12] if images else None,
    )


def parse_price_cents(text: str) -> Optional[int]:
    """
    Extract first price in cents from text (e.g. "From $2,642.46" or "$199.00").
    Mirrors extension extractPriceValue logic.
    """
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"[$,\s]", "", text)
    match = re.search(r"(\d+\.?\d*)", cleaned)
    if match:
        try:
            dollars = float(match.group(1))
            if dollars >= 0:
                return int(round(dollars * 100))
        except ValueError:
            pass
    return None


# Prefixes to strip from part number (extension normalizePartNumber)
_PART_NUMBER_PREFIXES = [
    r"^SKU\s*:\s*",
    r"^Part\s*#\s*:\s*",
    r"^Part\s*Number\s*:\s*",
    r"^Item\s*#\s*:\s*",
    r"^Product\s*Code\s*:\s*",
    r"^Model\s*#?\s*:\s*",
    r"^Code\s*:\s*",
]

# Car/model codes that look like part numbers but should not be stored as SKU (e.g. Z4M, 1M, E8x).
# Check uses space-stripped key so "Z4 M" and "Z4M" both match.
_PART_NUMBER_CAR_MODEL_BLACKLIST = frozenset(
    {
        "z4m",
        "1m",
        "e8x",
        "e9x",
        "e46",
        "e90",
        "e92",
        "e82",
        "e85",
        "e86",
        "f80",
        "f82",
        "f10",
        "f12",
        "e60",
        "e63",
        "e64",
    }
)


def normalize_description_text(raw: Optional[str], max_len: int = 2000) -> Optional[str]:
    """
    Normalize description: decode HTML entities, strip HTML tags to plain text, and cap length.
    """
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    if "<" in s and ">" in s:
        s = BeautifulSoup(s, "html.parser").get_text(separator=" ", strip=True)
    else:
        s = html.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len] if s else None


def normalize_part_number(raw: Optional[str]) -> Optional[str]:
    """
    Strip common prefixes (SKU:, Part #:, etc.) so we store the actual code.
    Rejects known car/model codes that look like part numbers (e.g. Z4M, 1M, E8x, E9x).
    Blacklist check uses space-stripped key so "Z4 M" from JSON-LD is rejected like "Z4M".
    """
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    for pattern in _PART_NUMBER_PREFIXES:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    s = s.strip()
    if not s:
        return None
    key = re.sub(r"\s+", "", s).lower()
    if key in _PART_NUMBER_CAR_MODEL_BLACKLIST:
        return None
    return s


def extract_sku_from_text(text: str) -> Optional[str]:
    """
    Find SKU/part number from body text. Tries "SKU: X", "SKU: X - Y", "Part #: X".

    Cue words are whole-word only so "partners" doesn't bleed into "Part". The bare
    words "Part" and "Item" are not accepted — they are too common; require a "#"
    or the word "Number" so we match explicit callouts like "Part #: X", not a
    random noun. Captured value must be ≥ 4 chars so 3-letter words that happen
    to follow a cue (e.g. "CSF") don't leak in as SKUs.
    """
    if not text:
        return None
    match = re.search(
        r"\b(?:SKU|P/N|(?:Part|Item)\s*(?:#|No\.?|Number))\s*:?\s*"
        r"([A-Za-z0-9][A-Za-z0-9\-\.]{2,}(?:\s*-\s*[A-Za-z0-9\-\.]+)*)",
        text,
        re.IGNORECASE,
    )
    if match:
        # Trim trailing sentence punctuation; "SKU: X." is a sentence, "X" is the value.
        raw = match.group(1).rstrip(".")
        candidate = normalize_part_number(raw)
        if candidate and len(candidate) >= 4:
            return candidate
    return None


def is_junk_part_number(part_number: Optional[str], part_manufacturer: Optional[str]) -> bool:
    """
    Reject part numbers that are almost certainly scraper noise rather than a real SKU:
    empty, shorter than 4 chars, or equal to the manufacturer name (case/space-insensitive).

    Used as a last-mile guard in ingest so a JSON-LD sku of "CSF" on a CSF-branded page
    doesn't become the part's part_number and cause spurious cross-URL dedupe.
    """
    if not part_number or not part_number.strip():
        return True
    normalized = re.sub(r"\s+", "", part_number).lower()
    if len(normalized) < 4:
        return True
    if part_manufacturer:
        manufacturer_key = re.sub(r"\s+", "", part_manufacturer).lower()
        if manufacturer_key and normalized == manufacturer_key:
            return True
    return False


# ---------------------------------------------------------------------------
# Universal-field extractors (S02)
# ---------------------------------------------------------------------------
#
# Five pure-function extractors for fields every part can plausibly carry —
# weight, material, finish, warranty, and fitment notes. Each returns
# ``(value, confidence)`` (confidence ∈ {'high','medium','low'}) or ``None``
# when nothing was found. Functions are deterministic, side-effect-free, and
# import-safe (no DB, no network, no I/O). Confidence levels mirror the
# CategorySpec convention from ``app/crawlers/specs/base.py``.
#
# ReDoS / cost guard: every regex below is linear-time on user-controlled
# text (no nested quantifiers on user-supplied groups). Input scanning is
# capped at the first ``_UNIVERSAL_INPUT_CAP`` chars of the html string —
# well above any real product page — so a 50MB pathological input cannot
# wedge the regex engine.

_UNIVERSAL_INPUT_CAP = 50_000

_Confidence = Literal["high", "medium", "low"]


def _cap_html(html_text: Optional[str]) -> Optional[str]:
    """Return at most the first ``_UNIVERSAL_INPUT_CAP`` chars of html_text, or None."""
    if not html_text or not html_text.strip():
        return None
    if len(html_text) > _UNIVERSAL_INPUT_CAP:
        return html_text[:_UNIVERSAL_INPUT_CAP]
    return html_text


# Sentinel weight bounds (grams). Anything outside is treated as scraper noise.
_WEIGHT_GRAM_MIN = 1.0
_WEIGHT_GRAM_MAX = 500_000.0

# Unit conversions to grams.
_WEIGHT_UNIT_TO_GRAMS: Dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kgs": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "lb": 453.59237,
    "lbs": 453.59237,
    "pound": 453.59237,
    "pounds": 453.59237,
    "oz": 28.3495231,
    "ounce": 28.3495231,
    "ounces": 28.3495231,
}


def _to_grams(value: float, unit: str) -> Optional[float]:
    """Convert ``value`` in ``unit`` to grams; return None if unit unknown or result out of range."""
    factor = _WEIGHT_UNIT_TO_GRAMS.get(unit.lower())
    if factor is None:
        return None
    grams = value * factor
    if grams < _WEIGHT_GRAM_MIN or grams > _WEIGHT_GRAM_MAX:
        return None
    return grams


# Linear-time regex: bounded numeric runs so a 50K-char digit pile cannot
# trigger O(N²) backtracking when the trailing unit token is missing.
# Real weights fit comfortably in {1,8}.{1,4}.
_WEIGHT_VALUE_UNIT_RE = re.compile(
    r"(?<!\d)(\d{1,8}(?:\.\d{1,4})?)\s{0,4}(lbs?|pounds?|kgs?|kilograms?|g|grams?|oz|ounces?)\b",
    re.IGNORECASE,
)
_WEIGHT_LABELED_RE = re.compile(
    r"weight\s{0,4}[:=]?\s{0,4}(\d{1,8}(?:\.\d{1,4})?)\s{0,4}(lbs?|pounds?|kgs?|kilograms?|g|grams?|oz|ounces?)\b",
    re.IGNORECASE,
)


def _weight_from_json_ld(html_text: str) -> Optional[Tuple[float, _Confidence]]:
    """Pull a Product weight from JSON-LD if a numeric value + unit can be resolved."""
    item = extract_json_ld_product(html_text)
    if not item:
        return None
    weight = item.get("weight")
    if weight is None:
        return None
    # Schema.org QuantitativeValue: {"value": "12", "unitCode": "LBR"} or unitText
    if isinstance(weight, dict):
        raw_val = weight.get("value")
        unit = weight.get("unitText") or weight.get("unitCode") or weight.get("unit")
        if raw_val is None or unit is None:
            return None
        try:
            value = float(str(raw_val).replace(",", "").strip())
        except (ValueError, TypeError):
            return None
        unit_str = str(unit).strip()
        # Map common UN/CEFACT unit codes that JSON-LD uses to our table.
        unit_code_map = {
            "LBR": "lb",
            "LB": "lb",
            "KGM": "kg",
            "KG": "kg",
            "GRM": "g",
            "G": "g",
            "ONZ": "oz",
            "OZ": "oz",
        }
        unit_str = unit_code_map.get(unit_str.upper(), unit_str)
        grams = _to_grams(value, unit_str)
        if grams is not None:
            return (grams, "high")
        return None
    if isinstance(weight, str):
        match = _WEIGHT_VALUE_UNIT_RE.search(weight)
        if match:
            try:
                value = float(match.group(1))
            except ValueError:
                return None
            grams = _to_grams(value, match.group(2))
            if grams is not None:
                return (grams, "high")
    return None


# Match shipping-table-ish containers we should *skip* before falling through
# to body text. Linear scan on lowercased html — cheap and good enough.
_SHIPPING_BLOCK_HINTS = (
    'class="shipping',
    "class='shipping",
    "shipping-info",
    "shipping_info",
    "shipping-weight",
)


def _strip_shipping_blocks(html_text: str) -> str:
    """
    Remove obvious shipping-info <table>/<div> blocks before body-text weight
    fallback so a "Shipping Weight: 30 lb" row doesn't beat the real spec row.
    Best-effort — uses BeautifulSoup to drop matching elements.
    """
    lowered = html_text.lower()
    if not any(hint in lowered for hint in _SHIPPING_BLOCK_HINTS):
        return html_text
    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception:  # noqa: BLE001  — defensive: bs4 should never raise here
        return html_text
    for tag in soup.find_all(["table", "div", "section"]):
        if not isinstance(tag, Tag):
            continue
        cls_attr = tag.get("class")
        cls_list: List[str] = []
        if isinstance(cls_attr, list):
            cls_list = [str(c).lower() for c in cls_attr]
        elif isinstance(cls_attr, str):
            cls_list = [cls_attr.lower()]
        id_attr = tag.get("id")
        id_str = str(id_attr).lower() if isinstance(id_attr, str) else ""
        if any("shipping" in c for c in cls_list) or "shipping" in id_str:
            tag.decompose()
    return str(soup)


def extract_weight(html_text: str) -> Optional[Tuple[float, _Confidence]]:
    """
    Extract a product's weight, normalized to grams.

    Confidence tiering (high → low):
      * high: JSON-LD Product ``weight`` with a recognizable unit.
      * medium: labeled spec-row text outside shipping blocks ("Weight: 25 lb").
      * low: first ``<value> <unit>`` match anywhere in body text.

    Returns None when no plausible weight is found, when the converted value
    falls outside ``[1 g, 500_000 g]``, or on malformed input.
    """
    capped = _cap_html(html_text)
    if capped is None:
        return None

    json_ld_hit = _weight_from_json_ld(capped)
    if json_ld_hit is not None:
        return json_ld_hit

    cleaned = _strip_shipping_blocks(capped)
    try:
        soup = BeautifulSoup(cleaned, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)
    except Exception:  # noqa: BLE001
        body_text = cleaned

    labeled = _WEIGHT_LABELED_RE.search(body_text)
    if labeled:
        try:
            value = float(labeled.group(1))
        except ValueError:
            value = 0.0
        grams = _to_grams(value, labeled.group(2))
        if grams is not None:
            return (grams, "medium")

    loose = _WEIGHT_VALUE_UNIT_RE.search(body_text)
    if loose:
        try:
            value = float(loose.group(1))
        except ValueError:
            value = 0.0
        grams = _to_grams(value, loose.group(2))
        if grams is not None:
            return (grams, "low")

    return None


# Material lexicon — order matters for canonicalization (longer/more-specific
# phrases first) so "billet aluminum" wins over plain "aluminum" when both
# patterns could match. Maps regex pattern → canonical output form.
_MATERIAL_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b6061\s+aluminum\b", re.IGNORECASE), "6061 aluminum"),
    (re.compile(r"\b7075\s+aluminum\b", re.IGNORECASE), "7075 aluminum"),
    (re.compile(r"\bbillet\s+aluminum\b", re.IGNORECASE), "billet aluminum"),
    (re.compile(r"\bforged\s+steel\b", re.IGNORECASE), "forged steel"),
    (re.compile(r"\bcast\s+iron\b", re.IGNORECASE), "cast iron"),
    (re.compile(r"\bstainless\s+steel\b", re.IGNORECASE), "stainless steel"),
    (re.compile(r"\bcarbon[\s\-]fiber\b", re.IGNORECASE), "carbon fiber"),
    (re.compile(r"\baluminum\b", re.IGNORECASE), "aluminum"),
    (re.compile(r"\baluminium\b", re.IGNORECASE), "aluminum"),
    (re.compile(r"\btitanium\b", re.IGNORECASE), "titanium"),
    (re.compile(r"\bsteel\b", re.IGNORECASE), "steel"),
    (re.compile(r"\bplastic\b", re.IGNORECASE), "plastic"),
    (re.compile(r"\brubber\b", re.IGNORECASE), "rubber"),
    (re.compile(r"\bsilicone\b", re.IGNORECASE), "silicone"),
    (re.compile(r"\bbrass\b", re.IGNORECASE), "brass"),
    (re.compile(r"\bcopper\b", re.IGNORECASE), "copper"),
    (re.compile(r"\biron\b", re.IGNORECASE), "iron"),
]


def _match_first_material(text: str) -> Optional[str]:
    for pattern, canonical in _MATERIAL_PATTERNS:
        if pattern.search(text):
            return canonical
    return None


_MATERIAL_LABELED_RE = re.compile(r"material\s*[:=]?\s*([^\n<>]{1,80})", re.IGNORECASE)


def extract_material(html_text: str) -> Optional[Tuple[str, _Confidence]]:
    """
    Extract a part's material (aluminum/steel/titanium/...) at confidence high → low.

    high: JSON-LD ``material`` value matches the material lexicon.
    medium: labeled "Material: …" row matches the lexicon.
    low: first body-text or title hit on the lexicon.
    """
    capped = _cap_html(html_text)
    if capped is None:
        return None

    item = extract_json_ld_product(capped)
    if item is not None:
        material_field = item.get("material")
        if isinstance(material_field, str) and material_field.strip():
            canonical = _match_first_material(material_field)
            if canonical is not None:
                return (canonical, "high")
        elif isinstance(material_field, dict):
            name = material_field.get("name")
            if isinstance(name, str) and name.strip():
                canonical = _match_first_material(name)
                if canonical is not None:
                    return (canonical, "high")

    try:
        soup = BeautifulSoup(capped, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)
    except Exception:  # noqa: BLE001
        body_text = capped

    labeled = _MATERIAL_LABELED_RE.search(body_text)
    if labeled:
        canonical = _match_first_material(labeled.group(1))
        if canonical is not None:
            return (canonical, "medium")

    canonical = _match_first_material(body_text)
    if canonical is not None:
        return (canonical, "low")

    return None


# Finish lexicon — split into "treatment-style" finishes and "color-only" so
# we can tag colour-only matches as low confidence.
_FINISH_TREATMENTS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bpowder[\s\-]coated\b", re.IGNORECASE), "powder coated"),
    (re.compile(r"\bclear[\s\-]coat\b", re.IGNORECASE), "clear-coat"),
    (re.compile(r"\banodized\b", re.IGNORECASE), "anodized"),
    (re.compile(r"\bpolished\b", re.IGNORECASE), "polished"),
    (re.compile(r"\bbrushed\b", re.IGNORECASE), "brushed"),
    (re.compile(r"\bpainted\b", re.IGNORECASE), "painted"),
    (re.compile(r"\braw\b", re.IGNORECASE), "raw"),
    (re.compile(r"\bsatin\b", re.IGNORECASE), "satin"),
    (re.compile(r"\bmatte\b", re.IGNORECASE), "matte"),
    (re.compile(r"\bgloss\b", re.IGNORECASE), "gloss"),
    (re.compile(r"\bchrome\b", re.IGNORECASE), "chrome"),
]

_FINISH_COLORS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bblack\b", re.IGNORECASE), "black"),
    (re.compile(r"\bred\b", re.IGNORECASE), "red"),
    (re.compile(r"\bblue\b", re.IGNORECASE), "blue"),
    (re.compile(r"\bsilver\b", re.IGNORECASE), "silver"),
    (re.compile(r"\bgold\b", re.IGNORECASE), "gold"),
]

_FINISH_LABELED_RE = re.compile(r"finish\s*[:=]?\s*([^\n<>]{1,80})", re.IGNORECASE)


def _match_first_finish(text: str) -> Optional[Tuple[str, bool]]:
    """Return (canonical, is_treatment) for the first match, treatments preferred over colours."""
    for pattern, canonical in _FINISH_TREATMENTS:
        if pattern.search(text):
            return (canonical, True)
    for pattern, canonical in _FINISH_COLORS:
        if pattern.search(text):
            return (canonical, False)
    return None


def extract_finish(html_text: str) -> Optional[Tuple[str, _Confidence]]:
    """
    Extract a part's finish (anodized/polished/black/...).

    Treatment finishes (anodized, polished, etc.) score higher than bare colour
    mentions: a labeled treatment is medium, an unlabeled treatment is low,
    and any colour-only match is always low — so a "red anodized" mention
    beats a stray "red" appearing in the body copy.
    """
    capped = _cap_html(html_text)
    if capped is None:
        return None

    item = extract_json_ld_product(capped)
    if item is not None:
        for key in ("color", "colour", "additionalProperty"):
            val = item.get(key)
            text: Optional[str] = None
            if isinstance(val, str):
                text = val
            elif isinstance(val, dict):
                name = val.get("value") or val.get("name")
                if isinstance(name, str):
                    text = name
            if text:
                hit = _match_first_finish(text)
                if hit is not None:
                    canonical, is_treatment = hit
                    return (canonical, "high" if is_treatment else "low")

    try:
        soup = BeautifulSoup(capped, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)
    except Exception:  # noqa: BLE001
        body_text = capped

    labeled = _FINISH_LABELED_RE.search(body_text)
    if labeled:
        hit = _match_first_finish(labeled.group(1))
        if hit is not None:
            canonical, is_treatment = hit
            return (canonical, "medium" if is_treatment else "low")

    hit = _match_first_finish(body_text)
    if hit is not None:
        canonical, _ = hit
        return (canonical, "low")

    return None


# Warranty: convert (n, unit) → number of days for sortable comparison.
_WARRANTY_UNIT_DAYS: Dict[str, float] = {
    "year": 365.25,
    "years": 365.25,
    "yr": 365.25,
    "yrs": 365.25,
    "month": 30.44,
    "months": 30.44,
    "day": 1.0,
    "days": 1.0,
}

_WARRANTY_RE = re.compile(
    r"(?<!\d)(\d{1,4})[\s\-]{0,4}(year|years|yr|yrs|month|months|day|days)\s{0,4}(?:limited\s{1,4})?warranty",
    re.IGNORECASE,
)


def extract_warranty(html_text: str) -> Optional[Tuple[float, _Confidence]]:
    """
    Extract a warranty as a float number-of-days so values are sortable.

    Captures shapes like ``"2 year limited warranty"``, ``"30-day warranty"``,
    ``"6 months warranty"``. Returns None when no warranty phrase is found.
    Confidence tiering: high on JSON-LD ``warranty`` field, medium on body
    text matches.
    """
    capped = _cap_html(html_text)
    if capped is None:
        return None

    item = extract_json_ld_product(capped)
    if item is not None:
        warranty = item.get("warranty")
        text: Optional[str] = None
        if isinstance(warranty, str):
            text = warranty
        elif isinstance(warranty, dict):
            name = warranty.get("value") or warranty.get("name") or warranty.get("description")
            if isinstance(name, str):
                text = name
        if text:
            m = _WARRANTY_RE.search(text)
            if m:
                try:
                    qty = float(m.group(1))
                except ValueError:
                    qty = 0.0
                factor = _WARRANTY_UNIT_DAYS.get(m.group(2).lower())
                if factor is not None and qty > 0:
                    return (qty * factor, "high")

    try:
        soup = BeautifulSoup(capped, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)
    except Exception:  # noqa: BLE001
        body_text = capped

    m = _WARRANTY_RE.search(body_text)
    if m:
        try:
            qty = float(m.group(1))
        except ValueError:
            qty = 0.0
        factor = _WARRANTY_UNIT_DAYS.get(m.group(2).lower())
        if factor is not None and qty > 0:
            return (qty * factor, "medium")

    return None


# Word-bounded chassis-code matcher — same shape as ``_CHASSIS_LIKE_PATTERN``
# (E46, E9x, F80, G82) but anchored at word boundaries rather than start/end of
# string, so we can find chassis mentions inside running prose. Bounded digit
# runs ({1,4}) keep the search linear-time on adversarial input.
_CHASSIS_IN_TEXT_RE = re.compile(
    r"\b([A-Z][0-9]{1,4}x?)\b",
)

# Year ranges like "2008-2013", "2010 to 2015", "'08-'13".
_YEAR_RANGE_RE = re.compile(
    r"'?\d{2,4}\s{0,4}(?:-|–|to)\s{0,4}'?\d{2,4}",
)


def _split_sentences(text: str) -> List[str]:
    """Cheap sentence splitter — good enough for fitment-notes locality checks."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|[\n\r]+", text) if s.strip()]


def extract_fitment_notes(html_text: str) -> Optional[Tuple[str, _Confidence]]:
    """
    Capture the first prose chunk that mentions a chassis code (E46/F80/G82/...) and,
    ideally, a year range. Returned string is capped at 300 chars.

    Confidence tiering:
      * high: chassis + year range in the same sentence.
      * medium: chassis present *or* year range present (not both in one sentence).
      * low: only a loose chassis-like token, no year context.
    """
    capped = _cap_html(html_text)
    if capped is None:
        return None

    try:
        soup = BeautifulSoup(capped, "html.parser")
        body_text = soup.get_text(separator=" ", strip=True)
    except Exception:  # noqa: BLE001
        body_text = capped
    if not body_text:
        return None

    sentences = _split_sentences(body_text)

    best_low: Optional[str] = None
    best_medium: Optional[str] = None
    for sent in sentences:
        chassis_hit = False
        for m in _CHASSIS_IN_TEXT_RE.finditer(sent):
            token = m.group(1)
            if _looks_like_chassis_code(token):
                chassis_hit = True
                break
        year_hit = bool(_YEAR_RANGE_RE.search(sent))
        if chassis_hit and year_hit:
            return (sent[:300], "high")
        if chassis_hit and best_medium is None:
            best_medium = sent[:300]
        elif year_hit and best_medium is None and chassis_hit is False:
            # year-only sentences are weaker context but still better than nothing
            best_low = best_low or sent[:300]
        if not chassis_hit and not year_hit:
            continue
        if best_low is None and chassis_hit:
            best_low = sent[:300]

    if best_medium is not None:
        return (best_medium, "medium")
    if best_low is not None:
        return (best_low, "low")

    # Last-ditch: any standalone chassis-like token anywhere in the text.
    for m in _CHASSIS_IN_TEXT_RE.finditer(body_text):
        token = m.group(1)
        if _looks_like_chassis_code(token):
            # Grab a 200-char window around the hit for context.
            start = max(0, m.start() - 80)
            end = min(len(body_text), m.end() + 120)
            return (body_text[start:end].strip()[:300], "low")

    return None


# Public entry point: run all five extractors and return the non-None hits.
_UNIVERSAL_FIELD_NAMES: Tuple[str, ...] = (
    "weight_grams",
    "material",
    "finish",
    "warranty_days",
    "fitment_notes",
)


def extract_universal_fields(html_text: Optional[str]) -> Dict[str, Tuple[Any, str]]:
    """
    Run all five universal-field extractors and return the non-None results.

    Keys mirror the CategorySpec base field names declared in S02 T02:
    ``weight_grams``, ``material``, ``finish``, ``warranty_days``,
    ``fitment_notes``. Each value is a ``(value, confidence)`` tuple. Returns
    an empty dict when ``html_text`` is None/empty or when nothing extracts.

    This is the call-site that ``RetailerCrawlerAdapter.apply_universal_extraction``
    (T03) consumes — see ``S02-PLAN.md``.
    """
    if not html_text or not html_text.strip():
        return {}

    out: Dict[str, Tuple[Any, str]] = {}

    weight_hit = extract_weight(html_text)
    if weight_hit is not None:
        out["weight_grams"] = weight_hit

    material_hit = extract_material(html_text)
    if material_hit is not None:
        out["material"] = material_hit

    finish_hit = extract_finish(html_text)
    if finish_hit is not None:
        out["finish"] = finish_hit

    warranty_hit = extract_warranty(html_text)
    if warranty_hit is not None:
        out["warranty_days"] = warranty_hit

    fitment_hit = extract_fitment_notes(html_text)
    if fitment_hit is not None:
        out["fitment_notes"] = fitment_hit

    return out
