"""
Infer car make / model / generation from part name and description using phrase matching.

Used by the crawler to set car_ids when scraping so parts are associated with the
right car generations (e.g. "MKV Supra A90" -> Toyota Supra A90).

Returns a list of (make, model, generation_name) triples; caller resolves to car IDs
via resolve_car_triples_to_ids().
"""

import re
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from app.core.car_generations_data import CAR_GENERATIONS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# Generation codes that must NOT match when they appear alone - too ambiguous.
# Examples: "GR" matches both Subaru WRX GR and Toyota GR Supra; "Mk5" matches VW and Supra;
# "B5" matches Audi platform and product codes; "D2" is D2 Racing brand; "8S" matches "8s" (quarter-mile);
# "B4" is Bilstein B4 product line, not Audi RS2 B4; "EVO" is Bilstein EVO, not Huracán EVO;
# "P1" appears in product codes (AT-P1), not just McLaren P1; "V10" in Rexpeed V10 is model, not Camry V10;
# "HI" in HKS Hi Power, not Genesis G90 HI; "Mk4" alone can appear near Supra MKV; "NA" in CTEK MXS 5.0 NA battery charger, not Miata NA; "S", "I", etc. match everywhere.
AMBIGUOUS_STANDALONE_CODES: frozenset[str] = frozenset(
    {
        "GR",
        "Mk5",
        "Mk4",  # VW Mk4; require "golf mk4" / "jetta mk4" to avoid Supra MKV confusion
        "B5",
        "B4",  # Bilstein B4 OE; require "rs2" / "avant" for Audi RS2 B4
        "EVO",  # Bilstein EVO; require "huracan" for Lamborghini Huracán EVO
        "P1",  # ADRO AT-P1 etc.; require "mclaren" for McLaren P1
        "V10",  # Rexpeed V10; require "camry" for Toyota Camry V10
        "HI",  # HKS Hi Power; require "g90" / "genesis" for Genesis G90 1st Gen
        "NA",  # CTEK MXS 5.0 NA battery charger etc.; require "miata" / "mx-5" for Mazda Miata NA
        "E90",  # Toyota Corolla E90 vs BMW E90 M3; require "m3" / "bmw" or "corolla" for disambiguation
        "E92",
        "E93",
        "E9x",
        "E46",  # BMW E46 shared by M3, 3 Series, 330i; require "e46 m3" / "e46 3 series" / "e46 330i"
        "E36",  # BMW E36 shared by M3, 3 Series, 330i; require "e36 m3" / "e36 3 series" / "e36 330i"
        "S",
        "D2",
        "8S",  # Subaru WRX, VW Golf, Audi A4/S4, D2 Racing, Audi TT 8S vs "8s"
        "I",
        "II",
        "III",
        "IV",
        "V",
        "VI",
        "VII",
        "VIII",
        "IX",  # Lancer Evolution Roman numerals
    }
)


def _build_phrase_triples() -> list[tuple[str, str, str, str]]:
    """
    Build (phrase, make, model, generation_name) from canonical data.
    Phrase is normalized (lowercase, single spaces) for matching.
    Skips standalone generation codes that are highly ambiguous (e.g. GR, Mk5, B5).
    """
    triples: list[tuple[str, str, str, str]] = []
    for make, models in CAR_GENERATIONS.items():
        for model_data in models:
            model = model_data["model"]
            for gen in model_data["generations"]:
                gen_name = gen["generation_name"]
                # Full phrase: "Toyota Supra A90"
                full = f"{make} {model} {gen_name}".lower()
                triples.append((full, make, model, gen_name))
                # Model + generation: "Supra A90", "M4 G82/G83"
                model_gen = f"{model} {gen_name}".lower()
                triples.append((model_gen, make, model, gen_name))
                # Generation only for short codes - skip ambiguous ones to avoid false positives
                if len(gen_name) <= 6 and "/" not in gen_name and gen_name not in AMBIGUOUS_STANDALONE_CODES:
                    triples.append((gen_name.lower(), make, model, gen_name))
    return triples


# Built once at import; sort by phrase length descending so longer matches win.
PHRASE_TRIPLES: list[tuple[str, str, str, str]] = sorted(_build_phrase_triples(), key=lambda x: -len(x[0]))


# Aliases: phrase -> (make, model, generation_name). Used when product text uses
# nicknames (MKV Supra, GR Supra, G82, etc.). Order: longer phrases first for specificity.
CAR_ALIASES: list[tuple[str, str, str, str]] = [
    # Toyota Supra A90
    ("mkv supra", "Toyota", "Supra", "A90"),
    ("mk5 supra", "Toyota", "Supra", "A90"),
    ("gr supra", "Toyota", "Supra", "A90"),
    ("supra gr a90", "Toyota", "Supra", "A90"),
    ("supra gr a91", "Toyota", "Supra", "A90"),
    ("supra gr 2020+", "Toyota", "Supra", "A90"),
    ("2020+ supra", "Toyota", "Supra", "A90"),
    ("2020+ toyota supra", "Toyota", "Supra", "A90"),
    ("2020 supra", "Toyota", "Supra", "A90"),
    ("supra 2020", "Toyota", "Supra", "A90"),
    ("2020 toyota supra", "Toyota", "Supra", "A90"),
    ("toyota supra 2020", "Toyota", "Supra", "A90"),
    ("a90/a91", "Toyota", "Supra", "A90"),
    ("a90 supra", "Toyota", "Supra", "A90"),
    ("a91 supra", "Toyota", "Supra", "A90"),
    ("mkv toyota supra", "Toyota", "Supra", "A90"),
    ("mkv supra gr", "Toyota", "Supra", "A90"),
    ("supra gr", "Toyota", "Supra", "A90"),  # "Oracle 20-21 Supra GR", "Supra GR RGB+A"
    ("20-21 toyota supra", "Toyota", "Supra", "A90"),
    ("2020-2021 toyota supra", "Toyota", "Supra", "A90"),
    ("off your supra", "Toyota", "Supra", "A90"),  # "shaves weight off your Supra"
    # BMW M4 G82/G83
    ("g82 m4", "BMW", "M4", "G82/G83"),
    ("g83 m4", "BMW", "M4", "G82/G83"),
    ("bmw g82", "BMW", "M4", "G82/G83"),
    ("m4 g82", "BMW", "M4", "G82/G83"),
    ("m4 g83", "BMW", "M4", "G82/G83"),
    # BMW G8X (M3 G80 / M4 G82/G83) - common in product titles
    ("g8x m3", "BMW", "M3", "G80"),
    ("g8x m4", "BMW", "M4", "G82/G83"),
    ("bmw g8x", "BMW", "M4", "G82/G83"),  # G8X often used for M4 grilles/body; M3 G80 also possible
    ("m3 g80", "BMW", "M3", "G80"),
    ("m4 g8x", "BMW", "M4", "G82/G83"),
    ("m3 g8x", "BMW", "M3", "G80"),
    # BMW M3 E90/E92/E93 (E9x) — product text: "E9x M3", "BMW E90 M3"; avoid matching Toyota Corolla E90
    ("e9x m3", "BMW", "M3", "E90/E92/E93"),
    ("e90 m3", "BMW", "M3", "E90/E92/E93"),
    ("e92 m3", "BMW", "M3", "E90/E92/E93"),
    ("e93 m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e9x m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e90 m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e92 m3", "BMW", "M3", "E90/E92/E93"),
    ("bmw e93 m3", "BMW", "M3", "E90/E92/E93"),
    ("e90/e92/e93 m3", "BMW", "M3", "E90/E92/E93"),
    ("m3 e9x", "BMW", "M3", "E90/E92/E93"),
    ("m3 e90", "BMW", "M3", "E90/E92/E93"),
    ("m3 e92", "BMW", "M3", "E90/E92/E93"),
    ("m3 e93", "BMW", "M3", "E90/E92/E93"),
    # BMW 3 Series E90/E91/E92/E93 (E91 = wagon/touring)
    ("e91 3 series", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("bmw e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e91 3 series xi", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("3 series e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    # BMW M2 G87 (S58; product text often groups "M2, M3, M4 G8X S58")
    ("bmw m2 g87", "BMW", "M2", "G87"),
    ("m2 g87", "BMW", "M2", "G87"),
    ("g87 m2", "BMW", "M2", "G87"),
    ("m2 g8x", "BMW", "M2", "G87"),
    ("bmw m2", "BMW", "M2", "G87"),  # "BMW M2, M3, M4" list context
    ("m3, m4 g8x", "BMW", "M3", "G80"),  # "M2, M3, M4 G8X" list context
    # BMW M3/M4 G8X (product text: "BMW M3/M4 S58 (G8X)", "2021+ BMW M3/M4")
    ("m3/m4 g8x", "BMW", "M3", "G80"),
    ("m3/m4 g8x", "BMW", "M4", "G82/G83"),
    ("bmw m3/m4", "BMW", "M3", "G80"),
    ("bmw m3/m4", "BMW", "M4", "G82/G83"),
    # BMW Z4 G29 (current gen; if not in CAR_GENERATIONS, resolve will return no ID)
    ("z4 g29", "BMW", "Z4", "G29"),
    ("bmw z4 g29", "BMW", "Z4", "G29"),
    ("g29 z4", "BMW", "Z4", "G29"),
    # Honda Civic 10th Gen
    ("10th gen civic", "Honda", "Civic", "10th Gen"),
    ("civic 10th gen", "Honda", "Civic", "10th Gen"),
    ("10th gen", "Honda", "Civic", "10th Gen"),  # ambiguous; often Civic in product titles
    # Civic Type R
    ("fk8", "Honda", "Civic Type R", "FK8"),
    ("fk8 civic", "Honda", "Civic Type R", "FK8"),
    ("fl5", "Honda", "Civic Type R", "FL5"),
    ("fl5 civic", "Honda", "Civic Type R", "FL5"),
    # Toyota GR Corolla 1st Gen (E210 chassis; product text may say "E210")
    ("gr corolla", "Toyota", "GR Corolla", "1st Gen"),
    ("corolla gr", "Toyota", "GR Corolla", "1st Gen"),
    ("gr corolla e210", "Toyota", "GR Corolla", "1st Gen"),
    ("toyota gr corolla", "Toyota", "GR Corolla", "1st Gen"),
    # Toyota GR 86 / 86 ZN8 (product text: "GR Supra/GR 86/GR Corolla" etc.)
    ("toyota gr 86", "Toyota", "86", "ZN8"),
    ("gr 86", "Toyota", "86", "ZN8"),
    ("gr86", "Toyota", "86", "ZN8"),
    # Toyota GR86 / Subaru BRZ (product text: "Toyota GR86 - BRZ/GR86", "BRZ/GR86")
    ("brz/gr86", "Toyota", "86", "ZN8"),
    ("brz/gr86", "Subaru", "BRZ", "ZD8"),
    ("gr86 - brz", "Toyota", "86", "ZN8"),
    ("gr86 - brz", "Subaru", "BRZ", "ZD8"),
    # BMW i4 M50 G26
    ("i4 m50", "BMW", "i4 M50", "G26"),
    ("i4 g26", "BMW", "i4 M50", "G26"),
    ("bmw i4 m50", "BMW", "i4 M50", "G26"),
    ("bmw i4 g26", "BMW", "i4 M50", "G26"),
    # Mazda Miata NA
    ("miata na", "Mazda", "Miata", "NA"),
    ("na miata", "Mazda", "Miata", "NA"),
    ("mx-5 na", "Mazda", "Miata", "NA"),
    ("mx5 na", "Mazda", "Miata", "NA"),
    # Dodge Charger 2024+
    ("charger lb", "Dodge", "Charger", "2024+"),
    ("dodge charger lb", "Dodge", "Charger", "2024+"),
    # Lamborghini Huracán EVO
    ("huracan evo", "Lamborghini", "Huracán", "EVO"),
    ("huracán evo", "Lamborghini", "Huracán", "EVO"),
    # Genesis G90 (1st Gen = HI, 2nd Gen = RS4 chassis; product text may use old codes)
    ("genesis g90", "Genesis", "G90", "1st Gen"),
    ("g90 genesis", "Genesis", "G90", "1st Gen"),
    ("g90 hi", "Genesis", "G90", "1st Gen"),
    ("genesis g90 hi", "Genesis", "G90", "1st Gen"),
    ("g90 rs4", "Genesis", "G90", "2nd Gen"),
    ("genesis g90 rs4", "Genesis", "G90", "2nd Gen"),
    # VW Mk4 platform (Golf, Jetta, R32) - product titles often say "Mk4" or "MK4"
    ("golf mk4", "Volkswagen", "Golf", "Mk4"),
    ("jetta mk4", "Volkswagen", "Jetta", "Mk4"),
    ("r32 mk4", "Volkswagen", "R32", "Mk4"),
    ("vw golf mk4", "Volkswagen", "Golf", "Mk4"),
    ("vw jetta mk4", "Volkswagen", "Jetta", "Mk4"),
    # BMW B58 engine cars (multiple; we match "B58" only when Supra/M340i/Z4 etc. in text)
    ("b58 supra", "Toyota", "Supra", "A90"),
    ("supra b58", "Toyota", "Supra", "A90"),
    ("b58 m340", "BMW", "M340i", "G20/G21"),
    ("b58 m440", "BMW", "M440i", "G22/G23/G26"),
    ("b58 z4", "BMW", "Z4", "G29"),
    ("z4 b58", "BMW", "Z4", "G29"),
    # BMW Gen 2 B58 (product text: "G Chassis Gen 2 2019+ B58 BMW", Burger catch can)
    ("gen 2 b58 bmw", "BMW", "M340i", "G20/G21"),
    ("g chassis gen 2 b58", "BMW", "M340i", "G20/G21"),
    # BMW M340i / M440i (B58 variants; specific model names in product titles)
    ("m340i", "BMW", "M340i", "G20/G21"),
    ("m340 i", "BMW", "M340i", "G20/G21"),  # common typo/spacing in product titles
    ("m340i b58", "BMW", "M340i", "G20/G21"),
    ("m440i", "BMW", "M440i", "G22/G23/G26"),
    ("m440 i", "BMW", "M440i", "G22/G23/G26"),
    ("m440i b58", "BMW", "M440i", "G22/G23/G26"),
    # BMW M240i G42 (B58; product text: "M340i, M440i, and 2022+ M240i")
    ("bmw m240i", "BMW", "M240i", "G42"),
    ("m240i", "BMW", "M240i", "G42"),
    ("m240 i", "BMW", "M240i", "G42"),
    # BMW 3/4 Series chassis codes (product text: "BMW (G20 G21 G22 G23 G26 G42)")
    ("bmw (g20", "BMW", "3 Series", "G20/G21"),
    ("bmw (g21", "BMW", "3 Series", "G20/G21"),
    ("g21 g22", "BMW", "4 Series", "G22/G23/G26"),  # "G20 G21 G22 G23" list context
    ("bmw (g22", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw (g23", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw g20", "BMW", "3 Series", "G20/G21"),
    ("bmw g21", "BMW", "3 Series", "G20/G21"),
    ("bmw g22", "BMW", "4 Series", "G22/G23/G26"),
    ("bmw g23", "BMW", "4 Series", "G22/G23/G26"),
    # Audi R8 (Mk1 = type 42, Mk2 = 4S; product text may use old codes)
    ("r8 42", "Audi", "R8", "Mk1"),
    ("r8 type 42", "Audi", "R8", "Mk1"),
    ("audi r8 42", "Audi", "R8", "Mk1"),
    ("audi r8 type 42", "Audi", "R8", "Mk1"),
    ("42 r8", "Audi", "R8", "Mk1"),
    ("r8 4s", "Audi", "R8", "Mk2"),
    ("audi r8 4s", "Audi", "R8", "Mk2"),
    # Audi RS2 Avant (B4 chassis)
    ("rs2 avant b4", "Audi", "RS2 Avant", "1st Gen"),
    ("audi rs2 b4", "Audi", "RS2 Avant", "1st Gen"),
    # Toyota Camry (V10/V20 chassis codes in product text)
    ("camry v10", "Toyota", "Camry", "1st Gen"),
    ("v10 camry", "Toyota", "Camry", "1st Gen"),
    ("camry v20", "Toyota", "Camry", "2nd Gen"),
    ("v20 camry", "Toyota", "Camry", "2nd Gen"),
    # Ferrari FF, McLaren P1 (model name = gen code; product text says "Ferrari FF", "McLaren P1")
    ("ferrari ff", "Ferrari", "FF", "1st Gen"),
    ("ff ferrari", "Ferrari", "FF", "1st Gen"),
    ("mclaren p1", "McLaren", "P1", "1st Gen"),
    ("p1 mclaren", "McLaren", "P1", "1st Gen"),
    # BMW M6 F12/F13/F06 (product titles: "BMW F12 M6", "Brake Lines - BMW F12 M6")
    ("bmw f12 m6", "BMW", "M6", "F12/F13/F06"),
    ("f12 m6", "BMW", "M6", "F12/F13/F06"),
    ("m6 f12", "BMW", "M6", "F12/F13/F06"),
    ("f13 m6", "BMW", "M6", "F12/F13/F06"),
    ("m6 f13", "BMW", "M6", "F12/F13/F06"),
    # BMW M3 E90/E92/E93 when in parentheses (e.g. "BMW M3 ( E90 / E92 )")
    ("m3 ( e90 / e92", "BMW", "M3", "E90/E92/E93"),
    ("m3 ( e90", "BMW", "M3", "E90/E92/E93"),
    ("m3 ( e92", "BMW", "M3", "E90/E92/E93"),
    ("m3 ( e93", "BMW", "M3", "E90/E92/E93"),
    # BMW E46 / E36 (ambiguous standalone; require chassis+model so we don't match all three models)
    ("e46 m3", "BMW", "M3", "E46"),
    ("m3 e46", "BMW", "M3", "E46"),
    ("e46 3 series", "BMW", "3 Series", "E46"),
    ("3 series e46", "BMW", "3 Series", "E46"),
    ("e46 330i", "BMW", "330i", "E46"),
    ("330i e46", "BMW", "330i", "E46"),
    ("e36 m3", "BMW", "M3", "E36"),
    ("m3 e36", "BMW", "M3", "E36"),
    ("e36 3 series", "BMW", "3 Series", "E36"),
    ("3 series e36", "BMW", "3 Series", "E36"),
    ("e36 330i", "BMW", "330i", "E36"),
    ("330i e36", "BMW", "330i", "E36"),
    # BMW Z4 M E85/E86 (product titles: "E46 M3 / E8x Z4M"; E8x is retailer typo for E85)
    ("e8x z4m", "BMW", "Z4 M", "E85/E86"),
    ("e8x z4 m", "BMW", "Z4 M", "E85/E86"),
    ("e85 z4m", "BMW", "Z4 M", "E85/E86"),
    ("e86 z4m", "BMW", "Z4 M", "E85/E86"),
    ("e85 z4 m", "BMW", "Z4 M", "E85/E86"),
    ("e86 z4 m", "BMW", "Z4 M", "E85/E86"),
    ("z4m e85", "BMW", "Z4 M", "E85/E86"),
    ("z4m e86", "BMW", "Z4 M", "E85/E86"),
    ("z4 m e85", "BMW", "Z4 M", "E85/E86"),
    ("z4 m e86", "BMW", "Z4 M", "E85/E86"),
    ("bmw z4m", "BMW", "Z4 M", "E85/E86"),
    # BMW M6 E63/E64 (product titles: "E60 M5 / E6x M6", "BMW M6 E63")
    ("e6x m6", "BMW", "M6", "E63/E64"),
    ("m6 e63", "BMW", "M6", "E63/E64"),
    ("m6 e64", "BMW", "M6", "E63/E64"),
    ("e63 m6", "BMW", "M6", "E63/E64"),
    ("e64 m6", "BMW", "M6", "E63/E64"),
    ("bmw m6 e63", "BMW", "M6", "E63/E64"),
    # BMW M6 F12/F13/F06 when in parentheses (e.g. "M5 / M6 (F10 / F12 / F13)")
    ("m6 (f10 / f12", "BMW", "M6", "F12/F13/F06"),
    ("m6 (f10 / f13", "BMW", "M6", "F12/F13/F06"),
    # BMW M3 F80 / M4 F82 (product titles: "F80 M3 / F82 M4")
    ("f80 m3", "BMW", "M3", "F80"),
    ("m3 f80", "BMW", "M3", "F80"),
    ("bmw f80 m3", "BMW", "M3", "F80"),
    ("f82 m4", "BMW", "M4", "F82/F83"),
    ("m4 f82", "BMW", "M4", "F82/F83"),
    ("bmw f82 m4", "BMW", "M4", "F82/F83"),
    ("m3 f80 / f82 m4", "BMW", "M3", "F80"),
    ("m3 f80 / f82 m4", "BMW", "M4", "F82/F83"),
]

# Word-boundary for short codes so "A90" doesn't match inside "BA90", and "nd" not inside "random"
_SHORT_PHRASE_MAX_LEN = 8

# Aliases that need extra context so we don't match numbers/units: "42" in 0.42 Mu, "lb" in ft-lb / lug bolt
_AUDI_R8_42_PHRASES = ("r8 42", "42 r8", "r8 type 42", "audi r8 42", "audi r8 type 42")
_CHARGER_LB_PHRASES = ("charger lb", "dodge charger lb")


def _phrase_matches(text: str, phrase: str) -> bool:
    """Return True if phrase appears in text (case-insensitive). Word boundaries for short alphanumeric phrases."""
    if not text or not phrase:
        return False
    lower = text.lower()
    phrase_lower = phrase.lower()
    if phrase_lower not in lower:
        return False
    # For short alphanumeric codes (e.g. A90, G82, ND), require word boundary to avoid false positives
    if len(phrase) <= _SHORT_PHRASE_MAX_LEN and phrase.replace("/", "").replace(" ", "").isalnum():
        return bool(re.search(r"\b" + re.escape(phrase_lower.replace("/", r"/")) + r"\b", lower))
    return True


def _reject_audi_r8_42_false_positive(text: str) -> bool:
    """Return True if text likely has '42' from decimals/measurements (0.42 Mu, 4.2L) not Audi R8 type 42."""
    lower = text.lower()
    # "42" as part of decimal (0.42, 4.2) or measurement (42mm, 42%) -> reject R8 42 match
    if re.search(r"[0-9.]\s*42\s*(?:mu|mm|%|whp|nm|lb)", lower):
        return True
    if re.search(r"\b0\.42\b", lower) or re.search(r"\b4\.2\s*(?:l|liter)", lower):
        return True
    return False


def _reject_charger_lb_false_positive(text: str) -> bool:
    """Return True if 'lb' is from ft-lb or lug bolt(s), not Dodge Charger LB."""
    lower = text.lower()
    if "ft-lb" in lower or "ft lb" in lower or "lug bolt" in lower or "lug bolts" in lower:
        return True
    return False


def _alias_phrase_matches(combined: str, phrase: str) -> bool:
    """Like _phrase_matches but with extra guards for known false-positive aliases."""
    if not _phrase_matches(combined, phrase):
        return False
    phrase_lower = phrase.lower()
    if phrase_lower in _AUDI_R8_42_PHRASES and _reject_audi_r8_42_false_positive(combined):
        return False
    if phrase_lower in _CHARGER_LB_PHRASES and _reject_charger_lb_false_positive(combined):
        return False
    return True


def infer_car_generations(
    name: Optional[str],
    description: Optional[str],
    product_url: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """
    Infer (make, model, generation_name) triples from part name, description, and optional URL.

    Returns unique list of triples that can be resolved to car IDs via resolve_car_triples_to_ids().
    Order: aliases first (more specific), then phrase triples from canonical data.
    """
    name = (name or "").strip()
    description = (description or "").strip()
    url = (product_url or "").strip()
    combined = f"{name} {description} {url}".strip()
    if not combined:
        return []

    seen: set[tuple[str, str, str]] = set()
    result: list[tuple[str, str, str]] = []

    # Check aliases first (specific nicknames); use alias-aware matching for R8 42 / Charger LB
    for phrase, make, model, gen_name in CAR_ALIASES:
        if (make, model, gen_name) in seen:
            continue
        if _alias_phrase_matches(combined, phrase):
            seen.add((make, model, gen_name))
            result.append((make, model, gen_name))

    # Then canonical phrases (from CAR_GENERATIONS); prefer longer matches (PHRASE_TRIPLES is pre-sorted)
    for phrase, make, model, gen_name in PHRASE_TRIPLES:
        if (make, model, gen_name) in seen:
            continue
        if _phrase_matches(combined, phrase):
            seen.add((make, model, gen_name))
            result.append((make, model, gen_name))

    return result


def resolve_car_triples_to_ids(
    db: "Session",
    triples: list[tuple[str, str, str]],
) -> list[UUID]:
    """
    Resolve (car_make_name, car_model_name, generation_name) triples to car_generation IDs.

    Only returns IDs for car_generations that exist (CarMake + CarModel + CarGeneration with that generation_name).
    """
    if not triples:
        return []
    from app.api.models.car_generation import CarGeneration
    from app.api.models.car_make import CarMake
    from app.api.models.car_model import CarModel

    ids: list[UUID] = []
    seen_ids: set[UUID] = set()
    for car_make_name, car_model_name, gen_name in triples:
        car_make = db.query(CarMake).filter(CarMake.name == car_make_name).first()
        if not car_make:
            continue
        car_model = (
            db.query(CarModel).filter(CarModel.car_make_id == car_make.id, CarModel.name == car_model_name).first()
        )
        if not car_model:
            continue
        car_generation = (
            db.query(CarGeneration)
            .filter(
                CarGeneration.car_model_id == car_model.id,
                CarGeneration.generation_name == gen_name,
            )
            .first()
        )
        if car_generation and car_generation.id not in seen_ids:
            seen_ids.add(car_generation.id)
            ids.append(car_generation.id)
    return ids
