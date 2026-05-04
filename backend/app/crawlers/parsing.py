"""
Shared parsing helpers used by multiple crawler adapters.

Mirrors the high-level logic from the chrome-extension content script:
JSON-LD Product schema first, then price/SKU regex and DOM fallbacks.
Adapters can use these and add retailer-specific selectors.
"""

import html
import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from app.crawlers.base import ScrapedPayload

if TYPE_CHECKING:
    from app.crawlers.adapters.base import RetailerCrawlerAdapter

logger = logging.getLogger(__name__)


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


# Generic product-type words that must never be used as part_manufacturer.
#
# Three flavors collapsed into one set so the title-token loop can do a single
# lookup:
#
# - Product-category words ("supercharger", "exhaust", "wheel"): a title that
#   leads with the product type rarely names a real manufacturer in that token.
# - Material / finish / shape descriptors ("carbon", "aluminum", "billet",
#   "stainless", "titanium", "silicone", "forged"): observed in production as
#   the assigned manufacturer for studiorsr, atpturbo, etc. when the title
#   reads "Carbon Fiber Trunk Spoiler ..." or "Billet Wastegate Actuator ...".
# - Position / state adjectives ("front", "rear", "complete", "replacement",
#   "universal", "new", "oem"): same shape — these lead the title before any
#   real brand token.
# - Articles / connectors ("the", "for", "and", "with", "to", "of"): observed
#   as ``"for"`` and ``"the"`` getting written as the manufacturer when the
#   title structure is "<part> for <car>".
_GENERIC_PRODUCT_WORDS = frozenset(
    {
        # Product categories.
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
        "thermostat",
        "flange",
        "clamp",
        "gasket",
        "gaskets",
        "sensor",
        "sensors",
        "switch",
        "sender",
        "module",
        "wire",
        "wires",
        "harness",
        "connector",
        "relay",
        "coil",
        "coils",
        "spark",
        "plug",
        "plugs",
        "bolt",
        "bolts",
        "nut",
        "nuts",
        "head",
        "heads",
        "valve",
        "valves",
        "clutch",
        "coilover",
        "coilovers",
        "spring",
        "springs",
        "tank",
        "pump",
        "filter",
        "hose",
        "hoses",
        "spacer",
        "spacers",
        "tool",
        "tools",
        "bushing",
        "bushings",
        "manifold",
        "manifolds",
        "header",
        "headers",
        "downpipe",
        "catback",
        "muffler",
        "rotor",
        "rotors",
        "pad",
        "pads",
        "pulley",
        "pulleys",
        "lip",
        "spoiler",
        "diffuser",
        "fender",
        "hood",
        "trunk",
        "shift",
        "shifter",
        "steering",
        "racing",
        "tuner",
        "challenge",
        "motorsport",
        "motorsports",
        "install",
        # Engine internals / drivetrain pieces that lead Lingenfelter / BTR /
        # Texas Speed titles when the brand is implicit ("LSA Pistons", "C6
        # Driveshaft"). The first-token scan would otherwise persist these as
        # standalone manufacturer rows.
        "piston",
        "pistons",
        "ring",
        "rings",
        "rod",
        "rods",
        "crank",
        "crankshaft",
        "cam",
        "cams",
        "camshaft",
        "camshafts",
        "lifter",
        "lifters",
        "bearing",
        "bearings",
        "block",
        "engine",
        "driveshaft",
        "driveshafts",
        "axle",
        "axles",
        "differential",
        "transmission",
        "flywheel",
        "injector",
        "injectors",
        "throttle",
        "regulator",
        # Catalog / placeholder leakage. The GReddy Shopify storefront emits
        # ``"brand": {"name": "CATALOG"}`` for first-party SKUs; without an
        # explicit reject the title scan promotes "CATALOG" to a manufacturer
        # row of its own.
        "catalog",
        # Generic hardware nouns observed leading multi-brand retailer titles
        # (Lingenfelter, MAPerformance, …) — "Cover Plate", "Output Basket",
        # "Bracket Set", "Mounting Adapter". The leading token never names
        # the maker.
        "cover",
        "covers",
        "output",
        "basket",
        "baskets",
        "shaft",
        "shafts",
        "removal",
        "package",
        "set",
        "sets",
        "assembly",
        "assemblies",
        "adapter",
        "adapters",
        "fitting",
        "fittings",
        # Vehicle subsystem nouns observed leading aftermarket retailer titles
        # ("BMW Accelerator Cable", "VW Brake Hose", "Audi Tie Rod End"). The
        # leading word names the function or part — never the maker.
        "accelerator",
        "bowden",
        "cable",
        "cables",
        "arm",
        "arms",
        "rod",
        "tie",
        "ball",
        "joint",
        "joints",
        "link",
        "links",
        "gas",
        "gear",
        "gears",
        "wiper",
        "wipers",
        "blade",
        "blades",
        "lamp",
        "lamps",
        "light",
        "lights",
        "headlight",
        "headlights",
        "taillight",
        "taillights",
        "mirror",
        "mirrors",
        "panel",
        "panels",
        "door",
        "doors",
        "window",
        "windows",
        "carpet",
        "floormat",
        "floormats",
        "mat",
        "mats",
        "trim",
        "trims",
        "seal",
        "seals",
        "weatherstrip",
        "emblem",
        "emblems",
        "badge",
        "badges",
        # Materials / finishes.
        "carbon",
        "fiber",
        "aluminum",
        "aluminium",
        "stainless",
        "titanium",
        "billet",
        "forged",
        "silicone",
        "rubber",
        "leather",
        "chrome",
        "polished",
        "anodized",
        "ceramic",
        "magnesium",
        "kevlar",
        "composite",
        # Generic part nouns that surface as second-token mfr when the first
        # token is a material we already reject (e.g. "Aluminum Transmission
        # Pan ..." would otherwise yield "Pan" once "Aluminum" is skipped).
        "pan",
        "cover",
        "covers",
        "cap",
        "caps",
        "shield",
        "guard",
        "mount",
        "mounts",
        "bracket",
        "brackets",
        "arm",
        "arms",
        "transmission",
        # Position / state adjectives.
        "front",
        "rear",
        "left",
        "right",
        "upper",
        "lower",
        "complete",
        "replacement",
        "universal",
        "new",
        "oem",
        "aftermarket",
        "heavy",
        "duty",
        "high",
        "low",
        "pure",
        "race",
        "canyon",
        # Connectors / articles — observed as actual stored manufacturer names.
        "the",
        "for",
        "and",
        "with",
        "to",
        "of",
        "or",
        "from",
        "your",
        "our",
        "all",
        # Title-leading qualifiers observed in production as the stored
        # manufacturer for hundreds of parts:
        # - "aka" — ATP Turbo titles like "GTW3684 aka GTW6262 …"
        # - "amazon.com" / "amazon" — Flyin' Miata marketplace titles like
        #   "Amazon.com Brake line union (metric)".
        # - "alternate" / "genuine" — OEM-replacement titles ("Genuine BMW
        #   Pulley") where the real brand is the second token.
        #
        # Compound brands whose first token alone is misleading
        # ("American Racing Headers", "Active Autowerke", "Agency Power",
        # "Alfa Romeo") are NOT rejected via this set — they're matched
        # up-front in ``part_manufacturer_from_title`` via the multi-word
        # brand list so the full brand wins before the first-token loop
        # fires. That keeps "Agency Power Oval Taper" → "Agency Power"
        # rather than losing the brand entirely to "Unknown".
        "aka",
        "amazon.com",
        "amazon",
        "alternate",
        "genuine",
        # Plural and adjective leakage observed downstream of the leading
        # product noun: e.g. "Engine Air Filters - Cayenne 955" lands on
        # "Filters" once "Engine"/"Air" are skipped; "Flange, Oil Drain /
        # Return" lands on "Drain"; "Cat Back Tube" lands on "Cat" / "Back".
        # All of these are descriptor or noun fragments, never brands.
        "filters",
        "drain",
        "tube",
        "tubes",
        "disk",
        "disks",
        "disc",
        "discs",
        "tip",
        "tips",
        "package",
        "packages",
        "set",
        "sets",
        "cat",
        "back",
        "cool",
        "cooling",
        "boost",
        # Use-case descriptors that ride on top of any product noun ("Sport
        # Brakes", "Touring Cat Back", "Track Day Pads"). Never brands on
        # their own. ``race`` is already in the set above; the rest were
        # leaking through.
        "track",
        "street",
        "rally",
        "drag",
        "drift",
        "touring",
        "sport",
        # Size / shape adjectives.
        "long",
        "short",
        "wide",
        "narrow",
        "tall",
        "deep",
        "shallow",
        "soft",
        "hard",
        "round",
        "square",
        "flat",
        "curved",
        "twin",
        "single",
        "triple",
        "dual",
        # State words common in product titles ("Stage 2", "Custom Cage").
        "stage",
        "mode",
        "custom",
        # Standalone product fragments that show up at title start.
        "lift",
        "vacuum",
        # Additional product nouns and material/finish leakage observed
        # post-fix in the title corpus: "Wastegate, Tial 38mm" → "Wastegate";
        # "STAINLESS Steel V-band" → "Steel"; "Flange, Oil Drain / Return" →
        # "Return". Plus connectors / port words on plumbing parts.
        "wastegate",
        "blowoff",
        "steel",
        "iron",
        "brass",
        "alloy",
        "return",
        "inlet",
        "outlet",
        "supply",
        "feed",
        "vent",
        "vents",
        "gauge",
        "gauges",
        "actuator",
        "actuators",
        "bracket",
        "brackets",
        "mount",
        "mounts",
        "adapter",
        "adapters",
        # Car *model* / chassis-name leakage. The first-token reject above
        # covers car *makes*; these are the high-volume *model* names that
        # lead Suncoast / a90shop / studiorsr titles ("Cayenne 955 V8",
        # "Boxster 986", "Supra A90"). They belong to car attribution.
        "cayenne",
        "boxster",
        "macan",
        "panamera",
        "carrera",
        "supra",
        "civic",
        "accord",
        "miata",
        "corvette",
        "camaro",
        "mustang",
        "challenger",
        "charger",
        "hellcat",
        "trackhawk",
        "wrangler",
        "tacoma",
        "tundra",
        "f-150",
        "f150",
        "silverado",
        "sierra",
        "ranger",
        "raptor",
        "wrx",
        "evo",
        "evolution",
        "lancer",
        "skyline",
        "gtr",
        "z06",
        "zr1",
        "ctsv",
        "cts-v",
    }
)


# Tokens that look like manufacturers but are car makes, not parts brands.
# A car make can occasionally be a parts brand (Subaru ships first-party
# accessories), but in the first-token title heuristic, leading with the car
# make almost always means "this part fits a <make>" — not "<make> made this
# part." Reject and let the description fallback or JSON-LD recover the real
# brand. Mirrors the broader ``_CAR_MAKES`` set declared lower in this file
# (used by ``part_manufacturer_universal``); kept as a separate identifier so
# tightening the title heuristic doesn't accidentally narrow the universal
# pipeline's reject list.
_TITLE_REJECT_CAR_MAKES = frozenset(
    {
        "acura",
        "audi",
        "bmw",
        "chevrolet",
        "chevy",
        "chrysler",
        "dodge",
        "ford",
        "honda",
        "hyundai",
        "infiniti",
        "jeep",
        "kia",
        "lexus",
        "mazda",
        "mclaren",
        "mercedes",
        "mercedes-benz",
        "mini",
        "mitsubishi",
        "nissan",
        "plymouth",
        "pontiac",
        "porsche",
        "ram",
        "saab",
        "scion",
        "subaru",
        "toyota",
        "volkswagen",
        "vw",
        "yamaha",
        # Exotic / European car makes that lead studiorsr / a90shop / IND
        # titles ("Maserati JB5", "Lamborghini Huracan ECU tune", "Ferrari
        # 488 ..."). Same shape as the other car makes — leading the title
        # signals fitment, not brand.
        "maserati",
        "lamborghini",
        "ferrari",
        "lotus",
        "bentley",
        "rollsroyce",
        "rolls-royce",
        "aston",
        "alpine",
        "polestar",
        "tesla",
        "rivian",
        "lucid",
    }
)


# Multi-word brands the first-token scan would otherwise split. Each entry is
# a regex matched case-insensitively as a whole-word phrase anywhere in the
# title; the second element is the canonical brand name to return. Order is
# most-specific → least-specific because some prefixes overlap (e.g.
# "American Axle" vs "American Racing Headers").
#
# Add a new entry here when production data shows a brand being chopped at
# the first space — observed losses include "American" (was "American Racing
# Headers"), "Brian" (was "Brian Crower" / "Brian Tooley Racing").
_TITLE_MULTI_WORD_BRANDS: tuple[tuple[str, str], ...] = (
    (r"\bAmerican\s+Racing\s+Headers\b", "American Racing Headers"),
    (r"\bAmerican\s+Axle\b", "American Axle"),
    (r"\bBrian\s+Crower\b", "Brian Crower"),
    (r"\bBrian\s+Tooley\s+Racing\b", "Brian Tooley Racing"),
    (r"\bChevrolet\s+Performance\b", "Chevrolet Performance"),
    # Compound brands whose first token alone names a different (or
    # nonexistent) entity. Without an up-front match the first-token scan
    # would store the leading qualifier as the manufacturer
    # ("Active", "Agency", "Alfa") and we'd lose the real brand.
    (r"\bActive\s+Autowerke\b", "Active Autowerke"),
    (r"\bAgency\s+Power\b", "Agency Power"),
    (r"\bAlfa\s+Romeo\b", "Alfa Romeo"),
)


def part_manufacturer_from_title(title: str) -> Optional[str]:
    """
    Heuristic for part_manufacturer from product title when JSON-LD part_manufacturer is missing.

    1. Prefer explicit " by PartManufacturerName" (e.g. "... by VF-Engineering").
    2. Match curated multi-word brands (``_TITLE_MULTI_WORD_BRANDS``) so brands
       like "American Racing Headers" don't get chopped at the first space.
    3. Otherwise use first word that is not a chassis code (E46, E9x), not a
       part code (VF540, VF620), not a generic product / material word
       (Carbon, Front, Stainless), and not a car make (Toyota, BMW). Trailing
       punctuation is stripped before comparison so "Thermostat," doesn't
       sneak past the generic-word guard.

    Returning ``None`` is a feature — it lets the description fallback and
    the universal-pipeline JSON-LD/microdata layers recover the real brand
    instead of locking in a noise token like "Carbon" or "Front."
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
    # Curated multi-word brands (American Racing Headers, Brian Tooley Racing,
    # Chevrolet Performance, …) — match before the first-token scan would
    # chop them at the first space.
    for pattern, canonical in _TITLE_MULTI_WORD_BRANDS:
        if re.search(pattern, title, re.IGNORECASE):
            return canonical

    # 3. First token that looks like a part_manufacturer (not chassis, not
    # part code, not generic product word, not a car make like "BMW" /
    # "Porsche" / "Ford" — leading with the make almost always means "fits a
    # <make>" rather than "<make> made this part"; let the description /
    # JSON-LD recover the real brand instead).
    parts = title.split()
    for token in parts:
        if not token or len(token) < 3:
            continue
        if _looks_like_chassis_code(token):
            continue
        if _looks_like_part_or_model_code(token):
            continue
        cleaned = token.lower().rstrip(",.;:!?")
        if cleaned in _GENERIC_PRODUCT_WORDS:
            continue
        if cleaned in _TITLE_REJECT_CAR_MAKES:
            continue
        if token[0].isupper() or (len(token) > 1 and token[0].isalpha()):
            return token.rstrip(",.;:!?")
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


# ---------------------------------------------------------------------------
# part_manufacturer_universal — JSON-LD / microdata / OpenGraph ladder (S03 T02)
# ---------------------------------------------------------------------------
#
# Mirrors the brand-precedence ladder used by m004_ground_truth.truth_from_html
# but lives in production code. Per MEM212 the measurement and production
# copies stay separate — same shape, separate ownership — so a measurement
# tweak can't silently move the predictor.

# Reject HTML inputs longer than this (5MB) — short-circuits past HTML-based
# steps. Mirrors the HTML_SIZE_CAP_BYTES in m004_ground_truth.
MANUFACTURER_HTML_SIZE_CAP_BYTES: int = 5 * 1024 * 1024


# Shared reject-token sets used by ``part_manufacturer_universal`` when an
# adapter declares ``MANUFACTURER_SELECTORS`` with a canonical-coerce
# mapping. Extracted as module-level frozensets (S03 T03) from the
# pre-existing per-adapter copies in csfrace.py / grimmspeed.py so the
# universal pipeline can apply the same reject logic without each adapter
# re-declaring them. Existing per-adapter constants stay in place — ripping
# them out is S04+ scope and would touch the adapter-local
# ``_normalize_part_manufacturer`` helpers, which is out of S03 lift scope.
#
# Adapters MAY supplement these via tuple-form selector mappings:
# ``MANUFACTURER_SELECTORS = {".brand": ("CSF", "wheels", "exhaust")}``.
# Tokens are compared case-insensitively after trimming.
_BRAND_REJECT_TOKENS: frozenset[str] = frozenset(
    {"the", "new", "oem", "race", "racing"}
)

_CAR_MAKES: frozenset[str] = frozenset(
    {
        "acura",
        "audi",
        "bmw",
        "chevrolet",
        "chevy",
        "chrysler",
        "dodge",
        "ford",
        "honda",
        "hyundai",
        "infiniti",
        "jeep",
        "kia",
        "lexus",
        "mazda",
        "mercedes",
        "mercedes-benz",
        "mini",
        "mitsubishi",
        "nissan",
        "plymouth",
        "pontiac",
        "porsche",
        "ram",
        "saab",
        "scion",
        "subaru",
        "toyota",
        "volkswagen",
        "vw",
        "yamaha",
    }
)


def _brand_from_jsonld_item(
    item: Dict[str, Any],
) -> Optional[Tuple[str, str]]:
    """Return (value, source) where source ∈ {'jsonld_brand', 'jsonld_manufacturer'} or None.

    JSON-LD ``brand`` may be a str, dict.name, or list[str | dict.name]. When
    ``brand`` is missing or empty we fall through to ``manufacturer`` (same
    shape) so a ``Product.manufacturer.name`` payload still wins over
    microdata/OG. Empty/whitespace strings are treated as None at every layer.
    """

    def _read(value: Any) -> Optional[str]:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str):
                stripped = name.strip()
                return stripped or None
            return None
        if isinstance(value, list):
            for entry in value:
                resolved = _read(entry)
                if resolved:
                    return resolved
        return None

    brand = _read(item.get("brand"))
    if brand:
        return (brand, "jsonld_brand")
    manufacturer = _read(item.get("manufacturer"))
    if manufacturer:
        return (manufacturer, "jsonld_manufacturer")
    return None


def _stringify_microdata_value(tag: Tag) -> Optional[str]:
    """Pull a sane string out of an itemprop element.

    Handles three element shapes: ``<meta itemprop='x' content='...'>``,
    nested ``<span itemprop='name'>`` (canonical schema.org Brand shape), and
    plain text content. Returns ``None`` for empty values so callers can fall
    through to the next layer. Mirrors the helper in
    ``m004_ground_truth._stringify_microdata_value`` deliberately — production
    and measurement copies stay separate per MEM212.
    """
    if not isinstance(tag, Tag):
        return None

    if tag.name == "meta":
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None

    name_child = tag.find(attrs={"itemprop": "name"})
    if isinstance(name_child, Tag) and name_child is not tag:
        inner_meta = name_child.get("content") if name_child.name == "meta" else None
        if isinstance(inner_meta, str) and inner_meta.strip():
            return inner_meta.strip()
        inner_text = name_child.get_text(separator=" ", strip=True)
        if inner_text:
            return inner_text

    text = tag.get_text(separator=" ", strip=True)
    if text:
        return text
    return None


_MANUFACTURER_OG_PROPS: Tuple[str, ...] = (
    "og:brand",
    "product:brand",
    "og:product:brand",
)


def _adapter_name(adapter: "Optional[RetailerCrawlerAdapter]") -> str:
    """Return a stable adapter identifier for log lines, or 'none'."""
    if adapter is None:
        return "none"
    name = getattr(adapter, "name", None)
    if isinstance(name, str) and name:
        return name
    return type(adapter).__name__ or "none"


def _selector_text(tag: Tag) -> Optional[str]:
    """Extract a sane string from a CSS-selector match.

    ``meta`` tags expose value via ``content``; everything else uses the
    stripped text content. Returns ``None`` for empty values so
    ``_resolve_from_adapter_selectors`` can fall through to the next entry.
    """
    if not isinstance(tag, Tag):
        return None
    if tag.name == "meta":
        content = tag.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None
    text = tag.get_text(strip=True)
    return text or None


def _resolve_from_adapter_selectors(
    html_text: str,
    adapter: "Optional[RetailerCrawlerAdapter]",
) -> Optional[str]:
    """Consult ``adapter.MANUFACTURER_SELECTORS`` for a retailer-specific brand.

    Iterates the dict in declaration order — first non-rejected value wins.
    Each value is either:

    * A canonical-string mapping ``"CSF"`` — the resolved selector string is
      checked against the shared ``_BRAND_REJECT_TOKENS | _CAR_MAKES`` reject
      set; reject matches coerce to the canonical string, non-rejects pass
      through unchanged.
    * A tuple ``("CSF", "wheels", "exhaust")`` — first entry is the canonical
      string, remaining entries are *additional* reject tokens supplementing
      the shared set. Same coercion rules apply.

    Defensive: every BeautifulSoup selector call is wrapped — a malformed
    selector or a parser failure logs ``manufacturer_universal_failed`` and
    falls through to the next entry. The function never raises.
    """
    if adapter is None:
        return None
    selectors = getattr(type(adapter), "MANUFACTURER_SELECTORS", None)
    if not isinstance(selectors, dict) or not selectors:
        return None

    try:
        soup = BeautifulSoup(html_text, "html.parser")
    except Exception as exc:  # noqa: BLE001 — defensive boundary
        logger.debug(
            "manufacturer_universal_failed",
            extra={"source": "adapter_selectors", "error": repr(exc)},
        )
        return None

    for selector, mapping in selectors.items():
        if not isinstance(selector, str) or not selector.strip():
            continue
        try:
            tag = soup.select_one(selector)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "manufacturer_universal_failed",
                extra={"source": "adapter_selectors", "error": repr(exc)},
            )
            continue
        if tag is None:
            continue

        try:
            value = _selector_text(tag)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "manufacturer_universal_failed",
                extra={"source": "adapter_selectors", "error": repr(exc)},
            )
            continue
        if not value:
            continue

        # Decode the mapping shape into (canonical, extra_rejects).
        canonical: Optional[str] = None
        extra_rejects: frozenset[str] = frozenset()
        if isinstance(mapping, str):
            canonical = mapping
        elif isinstance(mapping, tuple) and mapping:
            head = mapping[0]
            if isinstance(head, str):
                canonical = head
            extra_rejects = frozenset(
                t.lower().strip()
                for t in mapping[1:]
                if isinstance(t, str) and t.strip()
            )

        low = value.lower().strip()
        if (
            low in _BRAND_REJECT_TOKENS
            or low in _CAR_MAKES
            or low in extra_rejects
        ):
            if canonical:
                return canonical
            continue
        return value

    return None


def part_manufacturer_universal(
    name: str,
    description: Optional[str],
    html: Optional[str],
    *,
    product_url: Optional[str] = None,
    adapter: "Optional[RetailerCrawlerAdapter]" = None,
) -> Optional[str]:
    """Resolve a part manufacturer using the universal brand-precedence ladder.

    Resolution order, first hit wins:

      1. JSON-LD ``Product.brand`` (str / dict.name / list[str | dict.name]),
         then JSON-LD ``Product.manufacturer`` as a same-block fallback.
      2. Microdata: ``itemprop="brand"`` then ``itemprop="manufacturer"``.
      3. OpenGraph / product meta tags: ``og:brand`` → ``product:brand`` →
         ``og:product:brand``.
      4. ``part_manufacturer_from_title(name)``.
      5. ``part_manufacturer_from_description(description, product_name=name)``.
      6. ``part_manufacturer_fallback_from_title(name)``.

    Defensive contract:

    * Never raises. Every BeautifulSoup/JSON parse is wrapped in
      ``try/except Exception`` (per MEM212 / m004_ground_truth pattern); on
      failure the function emits ``manufacturer_universal_failed`` at debug
      and falls through to the next layer.
    * ``html is None`` or whitespace-only short-circuits past steps 1–3 to the
      title/description/fallback ladder so HTML-less callers still work.
    * Inputs over ``MANUFACTURER_HTML_SIZE_CAP_BYTES`` (5MB) short-circuit past
      HTML-based steps — mirrors ``HTML_SIZE_CAP_BYTES`` in the measurement
      module.
    * Empty/whitespace strings from any source are treated as None.

    On each successful resolution emits a ``manufacturer_universal_resolved``
    debug log line with ``source`` ∈ ``{'adapter_selectors', 'jsonld_brand',
    'jsonld_manufacturer', 'microdata', 'opengraph', 'title', 'description',
    'fallback', 'none'}``, ``adapter`` (adapter name or ``'none'``), and
    ``value`` so a future agent can grep crawler logs to localize regressions
    by source.

    Adapter consultation (S03 T03):

    * When ``adapter is not None`` and the adapter declares a non-empty
      ``MANUFACTURER_SELECTORS`` ClassVar, this function consults those CSS
      selectors FIRST — ahead of JSON-LD/microdata/OG — because a retailer-
      specific selector is cheaper and more accurate than guessing from
      generic schema markup.
    * After all HTML-based layers + title/description/fallback have run, the
      ``infer_manufacturer_for_part`` inheritance hook is reserved for a
      future ingest call site that has access to a parsed ``ScrapedPayload``.
      ``part_manufacturer_universal`` does NOT call ``infer_manufacturer_for_part``
      in S03 because no current caller (the harness ``_predict_manufacturer``
      and any future ingest call site) passes a ``parsed`` object — the slot
      is declared on the base for forward compatibility with S07's backfill.
    """
    adapter_label = _adapter_name(adapter)

    # Steps 1–3 require a non-trivial, in-cap HTML payload.
    has_html = bool(html and html.strip())
    if has_html and len(html or "") > MANUFACTURER_HTML_SIZE_CAP_BYTES:
        logger.debug(
            "manufacturer_universal_failed",
            extra={
                "source": "html_size_cap",
                "error": "html exceeds MANUFACTURER_HTML_SIZE_CAP_BYTES",
            },
        )
        has_html = False

    if has_html:
        assert html is not None  # for type narrowing — has_html guard above
        # 0. Adapter-declared MANUFACTURER_SELECTORS (cheap retailer-specific
        # layer; S03 T03). Runs ahead of JSON-LD because a retailer's CSS
        # selector is more authoritative than schema.org markup that may
        # carry a car-make leakage from the title.
        adapter_hit = _resolve_from_adapter_selectors(html, adapter)
        if adapter_hit is not None:
            logger.debug(
                "manufacturer_universal_resolved",
                extra={
                    "source": "adapter_selectors",
                    "adapter": adapter_label,
                    "value": adapter_hit,
                },
            )
            return adapter_hit

        # 1. JSON-LD Product.brand → Product.manufacturer fallback
        try:
            item = extract_json_ld_product(html, product_url=product_url)
        except Exception as exc:  # noqa: BLE001 — defensive boundary
            logger.debug(
                "manufacturer_universal_failed",
                extra={"source": "jsonld", "error": repr(exc)},
            )
            item = None
        if isinstance(item, dict):
            try:
                brand_hit = _brand_from_jsonld_item(item)
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "manufacturer_universal_failed",
                    extra={"source": "jsonld", "error": repr(exc)},
                )
                brand_hit = None
            if brand_hit is not None:
                value, source = brand_hit
                logger.debug(
                    "manufacturer_universal_resolved",
                    extra={
                        "source": source,
                        "adapter": adapter_label,
                        "value": value,
                    },
                )
                return value

        # 2. Microdata: itemprop=brand → itemprop=manufacturer
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "manufacturer_universal_failed",
                extra={"source": "microdata", "error": repr(exc)},
            )
            soup = None
        if soup is not None:
            for prop in ("brand", "manufacturer"):
                try:
                    candidate = soup.find(attrs={"itemprop": prop})
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "manufacturer_universal_failed",
                        extra={"source": "microdata", "error": repr(exc)},
                    )
                    candidate = None
                if isinstance(candidate, Tag):
                    try:
                        value = _stringify_microdata_value(candidate)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(
                            "manufacturer_universal_failed",
                            extra={"source": "microdata", "error": repr(exc)},
                        )
                        value = None
                    if value:
                        logger.debug(
                            "manufacturer_universal_resolved",
                            extra={
                                "source": "microdata",
                                "adapter": adapter_label,
                                "value": value,
                            },
                        )
                        return value

            # 3. OpenGraph / product:* meta tags
            for prop in _MANUFACTURER_OG_PROPS:
                try:
                    meta = soup.find("meta", property=prop)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "manufacturer_universal_failed",
                        extra={"source": "opengraph", "error": repr(exc)},
                    )
                    meta = None
                if isinstance(meta, Tag):
                    content = meta.get("content")
                    if isinstance(content, str) and content.strip():
                        value = content.strip()
                        logger.debug(
                            "manufacturer_universal_resolved",
                            extra={
                                "source": "opengraph",
                                "adapter": adapter_label,
                                "value": value,
                            },
                        )
                        return value

    # 4. Title heuristic
    try:
        title_hit = part_manufacturer_from_title(name) if name else None
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "manufacturer_universal_failed",
            extra={"source": "title", "error": repr(exc)},
        )
        title_hit = None
    if title_hit:
        logger.debug(
            "manufacturer_universal_resolved",
            extra={
                "source": "title",
                "adapter": adapter_label,
                "value": title_hit,
            },
        )
        return title_hit

    # 5. Description heuristic
    try:
        description_hit = part_manufacturer_from_description(
            description, product_name=name
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "manufacturer_universal_failed",
            extra={"source": "description", "error": repr(exc)},
        )
        description_hit = None
    if description_hit:
        logger.debug(
            "manufacturer_universal_resolved",
            extra={
                "source": "description",
                "adapter": adapter_label,
                "value": description_hit,
            },
        )
        return description_hit

    # 6. Fallback regex on title
    try:
        fallback_hit = part_manufacturer_fallback_from_title(name) if name else None
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "manufacturer_universal_failed",
            extra={"source": "fallback", "error": repr(exc)},
        )
        fallback_hit = None
    if fallback_hit:
        logger.debug(
            "manufacturer_universal_resolved",
            extra={
                "source": "fallback",
                "adapter": adapter_label,
                "value": fallback_hit,
            },
        )
        return fallback_hit

    logger.debug(
        "manufacturer_universal_resolved",
        extra={"source": "none", "adapter": adapter_label, "value": None},
    )
    return None


def _canonical_url_key(url: Optional[str]) -> Optional[str]:
    """
    Normalize a URL for equality comparison: collapse http/https to a single
    key, lowercase host, strip a trailing slash from the path, drop
    query/fragment. Used to decide whether a JSON-LD Product's declared URL
    refers to the page we're actually parsing. Returns None when the input
    isn't a parseable absolute URL.

    Why http and https collapse: legacy storefronts (vividracing.com, plus
    other older catalogs) emit JSON-LD with ``url`` set to ``http://...`` even
    though the canonical page is served over https. A strict scheme match
    would reject every Product block on those sites, the adapter would fall
    through to the DOM/og fallback, and chassis tokens from the title (IS300,
    AE86, JZA80) would land in ``part_number`` via the title-shape heuristic.
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
    scheme = parsed.scheme.lower()
    if scheme in ("http", "https"):
        scheme = "http"
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return f"{scheme}://{parsed.netloc.lower()}{path}"


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


def _escape_json_control_chars(raw: str) -> str:
    """
    Escape raw control characters (newline, tab, etc.) that appear inside
    JSON *string values*. Some Shopify themes (studiorsr.com) embed
    multi-line product descriptions directly into the JSON-LD payload
    without escaping the newlines/tabs, so strict ``json.loads`` rejects
    the document and the adapter silently loses sku/brand.

    Walks the document character by character, tracking whether we're
    inside a quoted string, and replaces any control byte (0x00–0x1F)
    *inside* a string with its ``\\uXXXX`` form. Control bytes between
    tokens (formatting whitespace) are preserved as-is — JSON allows them
    structurally — so the rewrite never changes the document's shape.
    """
    out: List[str] = []
    in_str = False
    esc = False
    for ch in raw:
        cp = ord(ch)
        if in_str:
            if esc:
                esc = False
                out.append(ch)
                continue
            if ch == "\\":
                esc = True
                out.append(ch)
                continue
            if ch == '"':
                in_str = False
                out.append(ch)
                continue
            if cp <= 0x1F:
                out.append(f"\\u{cp:04x}")
                continue
            out.append(ch)
            continue
        if ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


def _json_ld_type_is_product(t: Any) -> bool:
    """schema.org @type matcher for Product, case-insensitive.

    Some storefronts (notably Shopify themes on studiorsr.com) emit
    `"@type": "product"` in lowercase, which a strict equality check would skip
    and silently fall through to the adapter's DOM fallback — losing
    JSON-LD-only fields like `sku` and `brand.name`.
    """
    if isinstance(t, str):
        return t.strip().lower() == "product"
    if isinstance(t, list):
        return any(isinstance(x, str) and x.strip().lower() == "product" for x in t)
    return False


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
            # Some Shopify themes (e.g. studiorsr.com) emit JSON-LD with
            # unescaped raw newlines / tabs inside string values from a
            # multi-line description, which strict JSON rejects. Retry with
            # control chars escaped so we still recover sku/brand instead of
            # silently falling through to a weaker DOM path.
            try:
                data = json.loads(_escape_json_control_chars(raw))
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
            if not _json_ld_type_is_product(t):
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
        return html.unescape(part_manufacturer.strip())
    if isinstance(part_manufacturer, dict):
        name = part_manufacturer.get("name")
        if isinstance(name, str) and name.strip():
            return html.unescape(name.strip())
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
    # Normalize to a list of items. Schema.org allows ``image`` to be:
    # - a string URL
    # - an ``ImageObject`` dict (e.g. Shopify OS 2.0: ``{"@type":"ImageObject","url":..., ...}``)
    # - a list of either of the above
    # Previously the ``else img`` fallback iterated over a dict's KEYS
    # (yielding ``"@type"``, ``"url"``, ``"image"``, ``"name"``, ``"width"``,
    # ``"height"`` as "image URLs"); seen on every ogracing JSON-LD, polluted
    # 251 parts.
    if isinstance(img, str):
        candidates: List[Any] = [img]
    elif isinstance(img, dict):
        candidates = [img]
    elif isinstance(img, list):
        candidates = img
    else:
        return []
    urls: List[str] = []
    for i in candidates:
        if isinstance(i, str) and i.strip():
            urls.append(i.strip())
        elif isinstance(i, dict):
            # Prefer ``url``; fall back to ``contentUrl`` (also valid on
            # ImageObject) and a string-typed nested ``image``.
            for key in ("url", "contentUrl", "image"):
                v = i.get(key)
                if isinstance(v, str) and v.strip():
                    urls.append(v.strip())
                    break
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


def part_number_canonical(raw: Optional[str]) -> Optional[str]:
    """
    Build the canonical dedup key for a part number: strip prefixes, drop every
    non-alphanumeric character, and uppercase the result. Returns ``None`` for
    empty input, results shorter than 4 characters, or values that match the
    car/model blacklist.

    The raw ``parts.part_number`` column keeps the human-readable form (the
    return value of ``normalize_part_number``); this canonical form is stored
    in ``part_number_normalized`` and used for equality matching so that
    styling drift (``"AEM-30-2400"`` vs ``"AEM 30/2400"``) collapses into a
    single dedup key.
    """
    normalized = normalize_part_number(raw)
    if not normalized:
        return None
    canonical = re.sub(r"[^A-Za-z0-9]", "", normalized).upper()
    if not canonical or len(canonical) < 4:
        return None
    if canonical.lower() in _PART_NUMBER_CAR_MODEL_BLACKLIST:
        return None
    return canonical


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


# Pure-alpha words observed leaking into SKU slots from variant/option labels
# on retailer pages whose ``SKU:`` field is empty. The page-wide text scan
# would otherwise pick up the next-line dropdown label ("Fuel:", "Size:",
# "Turbo:") and write it as a SKU — see sheepeyrace and mackin-ind for
# concrete cases. Match is case-insensitive on the normalized (whitespace-
# stripped) value. Real SKUs that happen to be one of these words are rare
# enough that the false-positive cost is negligible — anything carrying a
# digit, hyphen, or longer compound form bypasses this list.
_ALPHA_OPTION_LABEL_DENYLIST = frozenset(
    {
        "fuel",
        "turbo",
        "core",
        "size",
        "color",
        "colour",
        "product",
        "option",
        "options",
        "style",
        "type",
    }
)


# Car-make tokens that leak into synthesized part numbers (chassis-leakage:
# ``"Toyota-Supra-A91-Pure800"``, ``"Subaru-WRX-STi-Tune"``). When any of these
# tokens appears as a whole word inside the candidate, the value is almost
# certainly a title-shape concatenation rather than a real SKU. Match is
# case-insensitive and word-boundary-scoped on the original (non-collapsed)
# value so legitimate codes that happen to embed these substrings as part of
# a longer alphanumeric run (``"TOYO225"``, ``"INFINITRONIC"``) survive.
_PART_NUMBER_MAKE_TOKEN_DENYLIST = frozenset(
    {
        "toyota",
        "subaru",
        "honda",
        "nissan",
        "ford",
        "chevrolet",
        "chevy",
        "mazda",
        "bmw",
        "audi",
        "porsche",
        "mitsubishi",
        "lexus",
        "infiniti",
        "acura",
        "volkswagen",
        "vw",
        "hyundai",
        "kia",
        "genesis",
        "tesla",
    }
)

_PART_NUMBER_MAKE_TOKEN_RE = re.compile(
    r"\b(?:" + "|".join(sorted(_PART_NUMBER_MAKE_TOKEN_DENYLIST, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

# Price-shape: a bare decimal with two trailing digits (``"15109.14"``,
# ``"99.95"``). The crawler occasionally writes a stringified price into the
# SKU slot when JSON-LD ``offers.price`` is mis-mapped onto ``sku``.
_PART_NUMBER_PRICE_SHAPE_RE = re.compile(r"^\d+\.\d{2}$")

# Suspicious-length cap for SKU-shaped values. Real SKUs almost never run past
# 40 chars; the worst offenders we've seen are bundle-list concatenations
# ("Item1+Item2+Item3" from a multi-product variant string).
_PART_NUMBER_LENGTH_CAP = 40

# Pure-numeric GTIN (UPC/EAN) shapes. UPC-A is 12 digits, EAN-13 is 13. When a
# candidate matches one of these and the part has no GTIN yet, the value is
# moved to the gtin column instead of dropped — see ``gtin_candidate_for_pn``.
_PART_NUMBER_GTIN_RE = re.compile(r"^\d{12,13}$")


def is_junk_part_number(part_number: Optional[str], part_manufacturer: Optional[str]) -> bool:
    """
    Reject part numbers that are almost certainly scraper noise rather than a real SKU:
    empty, equal to the manufacturer name (case/space-insensitive), a short
    alphabetic-only token (≤3 chars containing no digits — almost always a brand
    acronym mistakenly written into the SKU slot like "CSF"), or a pure-alpha
    option-label word like "FUEL"/"SIZE"/"TURBO" leaked from a Wix/Shopify
    variant dropdown when the page's SKU field was empty.

    Numeric or alphanumeric short codes (e.g. "326", "608", "30074", "B1") are
    NOT junk — Road Sport Supply, Girodisc, and other manufacturers ship real
    catalog SKUs in this shape. Those would never collide with a brand name.

    Suspicious-pattern guards (added with the canonical-PN refactor):

    - **Bundle/list concatenations** — > 40 chars containing whitespace or ``+``
      almost always come from a mis-mapped variant string (``"Item A + Item B
      + Item C"``). Real SKUs that long don't carry separators.
    - **Price-shape** — bare ``\\d+\\.\\d{{2}}`` is a stringified price, never
      a SKU.
    - **GTIN-shape** — pure 12/13-digit values are UPC/EAN codes; ingest
      promotes them to the ``gtin`` column instead of writing them as a part
      number. The dedicated promotion helper handles that hand-off; this
      function still rejects them as part-number junk.
    - **Make tokens** — title-shape synthesized SKUs (``"Toyota-Supra-A91-
      Pure800"``) are dropped when any of the make tokens appears as a whole
      word.

    Used as a last-mile guard in ingest so a JSON-LD sku of "CSF" on a CSF-branded
    page doesn't become the part's part_number and cause spurious cross-URL dedupe.
    """
    if not part_number or not part_number.strip():
        return True
    raw = part_number.strip()
    normalized = re.sub(r"\s+", "", raw).lower()
    # Short purely alphabetic tokens (no digits) are almost always brand acronyms
    # leaking into the SKU slot. Anything containing a digit (or longer than 3
    # chars) is allowed through — manufacturer-equality check below still catches
    # full-name collisions like "ADRO" → manufacturer "Adro".
    if len(normalized) < 4 and not any(c.isdigit() for c in normalized):
        return True
    # Generic option-label words observed leaking from dropdown selectors. Only
    # rejects pure-alpha matches; anything with a digit or hyphen is allowed
    # through (real SKUs like "TURBO-2" or "CORE-450" pass the filter).
    if normalized.isalpha() and normalized in _ALPHA_OPTION_LABEL_DENYLIST:
        return True
    if part_manufacturer:
        manufacturer_key = re.sub(r"\s+", "", part_manufacturer).lower()
        if manufacturer_key and normalized == manufacturer_key:
            return True
    # Bundle/list leakage: a long string carrying whitespace or ``+`` is the
    # signature of a multi-product concatenation, not a real SKU.
    if len(raw) > _PART_NUMBER_LENGTH_CAP and (
        any(c.isspace() for c in raw) or "+" in raw
    ):
        return True
    # Price-shape (``"15109.14"``).
    if _PART_NUMBER_PRICE_SHAPE_RE.match(raw):
        return True
    # GTIN-shape (12/13 digit pure numeric). Belongs in ``gtin``, not
    # ``part_number``. Caller is expected to first attempt GTIN promotion via
    # ``gtin_candidate_for_pn``; the rejection here is the no-op fallback when
    # the gtin slot is already populated.
    if _PART_NUMBER_GTIN_RE.match(raw):
        return True
    # Make-token leakage (``"Toyota-Supra-A91-Pure800"`` and friends).
    if _PART_NUMBER_MAKE_TOKEN_RE.search(raw):
        return True
    return False


def gtin_candidate_for_pn(part_number: Optional[str]) -> Optional[str]:
    """
    Return a normalized GTIN string when ``part_number`` looks like a 12- or
    13-digit pure-numeric value (UPC-A / EAN-13), otherwise ``None``. Caller
    promotes the result into the ``gtin`` column when that slot is empty.
    Whitespace is stripped; non-digit characters disqualify the candidate.
    """
    if not part_number or not part_number.strip():
        return None
    raw = part_number.strip()
    if _PART_NUMBER_GTIN_RE.match(raw):
        return raw
    return None

