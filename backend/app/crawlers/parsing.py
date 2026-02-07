"""
Shared parsing helpers used by multiple crawler adapters.

Mirrors the high-level logic from the chrome-extension content script:
JSON-LD Product schema first, then price/SKU regex and DOM fallbacks.
Adapters can use these and add retailer-specific selectors.
"""

import json
import re
from typing import Any, Dict, List, Optional, cast

from bs4 import BeautifulSoup

from app.crawlers.base import ScrapedPayload


def extract_json_ld_product(html: str) -> Optional[Dict[str, Any]]:
    """
    Extract the first Product from JSON-LD script(s). Returns a dict with
    name, description, brand, sku, price (from offers), image(s).
    """
    soup = BeautifulSoup(html, "html.parser")
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
            return item
    return None


def _brand_from_json_ld(item: Dict[str, Any]) -> Optional[str]:
    brand = item.get("brand")
    if isinstance(brand, str) and brand.strip():
        return brand.strip()
    if isinstance(brand, dict):
        name = brand.get("name")
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
    """
    name_val = item.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    if not name:
        return None
    desc = item.get("description")
    description = None
    if isinstance(desc, str) and len(desc.strip()) > 10:
        description = desc.strip()[:2000]
    brand = _brand_from_json_ld(item)
    sku_val = item.get("sku") or item.get("mpn")
    part_number: Optional[str] = None
    if isinstance(sku_val, str) and sku_val.strip():
        part_number = normalize_part_number(sku_val)
    price_cents = _price_from_json_ld(item)
    images = _images_from_json_ld(item)
    image_url = images[0] if images else None
    return ScrapedPayload(
        name=name,
        product_url=product_url,
        description=description,
        price_cents=price_cents,
        brand=brand,
        part_number=part_number,
        image_url=image_url,
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


def normalize_part_number(raw: Optional[str]) -> Optional[str]:
    """
    Strip common prefixes (SKU:, Part #:, etc.) so we store the actual code.
    """
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    for pattern in _PART_NUMBER_PREFIXES:
        s = re.sub(pattern, "", s, flags=re.IGNORECASE)
    s = s.strip()
    return s if s else None


def extract_sku_from_text(text: str) -> Optional[str]:
    """
    Find SKU/part number from body text. Tries "SKU: X", "SKU: X - Y", "Part #: X".
    """
    if not text:
        return None
    # "SKU: WGCR425MA2 - WGCR635MA2" -> take full value or first segment
    match = re.search(
        r"(?:SKU|Part\s*#?|Item\s*#?|P/N)\s*:?\s*([A-Za-z0-9\-\.]+(?:\s*-\s*[A-Za-z0-9\-\.]+)*)",
        text,
        re.IGNORECASE,
    )
    if match:
        candidate = normalize_part_number(match.group(1))
        if candidate and len(candidate) >= 2:
            return candidate
    return None
