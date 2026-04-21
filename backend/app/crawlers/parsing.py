"""
Shared parsing helpers used by multiple crawler adapters.

Mirrors the high-level logic from the chrome-extension content script:
JSON-LD Product schema first, then price/SKU regex and DOM fallbacks.
Adapters can use these and add retailer-specific selectors.
"""

import html
import json
import re
from typing import Any, Dict, List, Optional, cast
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
