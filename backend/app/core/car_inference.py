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
        # Cross-make chassis-code collisions — require explicit model+code alias to fire.
        "C8",  # Chevrolet Corvette C8 ↔ Audi A6/RS6/A7/RS7/S6/S7 C8
        "G60",  # BMW i5 M60 G60 ↔ VW Corrado G60 (G-Lader 1.8L)
        "970",  # Porsche Panamera 970 — "970%" in hyperbolic marketing copy triggers it
        # BMW G-codes that collide with Genesis model names. Require make+model or model+code
        # disambiguating aliases ("m3 g80", "bmw i7", "genesis g80", etc.).
        "G70",  # BMW i7 M70 G70 ↔ Genesis G70 (sedan model)
        "G80",  # BMW M3 G80 ↔ Genesis G80 (sedan model)
        "G87",  # BMW M2 G87 — safer to require "m2 g87" / "g87 m2" context
        # Tesla trim name shared across models. Require "model s plaid" / "model x plaid" context.
        "Plaid",
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
    # Toyota GR86 (ZN8, MY 2022+) — distinct model from the original Toyota 86 (ZN6).
    # Product text uses "GR 86", "GR86", "2022+ GR86" etc. The ZN6-era Toyota 86 is
    # not matched by these aliases; for that, use "Toyota 86" full phrase triples.
    ("toyota gr 86", "Toyota", "GR86", "ZN8"),
    ("gr 86", "Toyota", "GR86", "ZN8"),
    ("gr86", "Toyota", "GR86", "ZN8"),
    ("toyota gr86", "Toyota", "GR86", "ZN8"),
    # Toyota GR86 / Subaru BRZ (product text: "Toyota GR86 - BRZ/GR86", "BRZ/GR86")
    ("brz/gr86", "Toyota", "GR86", "ZN8"),
    ("brz/gr86", "Subaru", "BRZ", "ZD8"),
    ("gr86 - brz", "Toyota", "GR86", "ZN8"),
    ("gr86 - brz", "Subaru", "BRZ", "ZD8"),
    # BMW i4 M50 G26
    ("i4 m50", "BMW", "i4 M50", "G26"),
    ("i4 g26", "BMW", "i4 M50", "G26"),
    ("bmw i4 m50", "BMW", "i4 M50", "G26"),
    ("bmw i4 g26", "BMW", "i4 M50", "G26"),
    # Toyota Supra A80 friendly forms (engineering "a80" is auto-built via PHRASE_TRIPLES)
    ("mk4 supra", "Toyota", "Supra", "A80"),
    ("mkiv supra", "Toyota", "Supra", "A80"),
    ("mkiv toyota supra", "Toyota", "Supra", "A80"),
    ("toyota supra mk4", "Toyota", "Supra", "A80"),
    ("supra mk4", "Toyota", "Supra", "A80"),
    ("a80 supra", "Toyota", "Supra", "A80"),
    ("supra a80", "Toyota", "Supra", "A80"),
    # Mazda Miata NA
    ("miata na", "Mazda", "Miata", "NA"),
    ("na miata", "Mazda", "Miata", "NA"),
    ("mx-5 na", "Mazda", "Miata", "NA"),
    ("mx5 na", "Mazda", "Miata", "NA"),
    ("mk1 miata", "Mazda", "Miata", "NA"),
    ("miata mk1", "Mazda", "Miata", "NA"),
    # Mazda Miata NB/NC/ND
    ("miata nb", "Mazda", "Miata", "NB"),
    ("nb miata", "Mazda", "Miata", "NB"),
    ("mx-5 nb", "Mazda", "Miata", "NB"),
    ("mx5 nb", "Mazda", "Miata", "NB"),
    ("mk2 miata", "Mazda", "Miata", "NB"),
    ("miata mk2", "Mazda", "Miata", "NB"),
    ("miata nc", "Mazda", "Miata", "NC"),
    ("nc miata", "Mazda", "Miata", "NC"),
    ("mx-5 nc", "Mazda", "Miata", "NC"),
    ("mx5 nc", "Mazda", "Miata", "NC"),
    ("mk3 miata", "Mazda", "Miata", "NC"),
    ("miata mk3", "Mazda", "Miata", "NC"),
    ("miata nd", "Mazda", "Miata", "ND"),
    ("nd miata", "Mazda", "Miata", "ND"),
    ("mx-5 nd", "Mazda", "Miata", "ND"),
    ("mx5 nd", "Mazda", "Miata", "ND"),
    ("mk4 miata", "Mazda", "Miata", "ND"),
    ("miata mk4", "Mazda", "Miata", "ND"),
    # Mazda RX-7 (SA/FB has a slash so PHRASE_TRIPLES skips the standalone alias for it)
    ("fb rx-7", "Mazda", "RX-7", "SA/FB"),
    ("rx-7 fb", "Mazda", "RX-7", "SA/FB"),
    ("fb rx7", "Mazda", "RX-7", "SA/FB"),
    ("rx7 fb", "Mazda", "RX-7", "SA/FB"),
    ("sa22c rx-7", "Mazda", "RX-7", "SA/FB"),
    ("1st gen rx-7", "Mazda", "RX-7", "SA/FB"),
    ("1st gen rx7", "Mazda", "RX-7", "SA/FB"),
    ("2nd gen rx-7", "Mazda", "RX-7", "FC"),
    ("2nd gen rx7", "Mazda", "RX-7", "FC"),
    ("3rd gen rx-7", "Mazda", "RX-7", "FD"),
    ("3rd gen rx7", "Mazda", "RX-7", "FD"),
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
    # Genesis G70 / G80 — model names collide with BMW chassis codes (G70=i7 M70, G80=M3).
    # AMBIGUOUS_STANDALONE_CODES blocks the bare BMW chassis match; require "genesis" context here.
    ("genesis g70", "Genesis", "G70", "RG"),
    ("genesis g70 fl", "Genesis", "G70", "RG"),
    ("genesis g80", "Genesis", "G80", "RG3"),
    # BMW i7 M70 (electric M-performance flagship; generation_name="G70" collides with Genesis G70)
    ("i7 m70", "BMW", "i7 M70", "G70"),
    ("bmw i7 m70", "BMW", "i7 M70", "G70"),
    # BMW M3 G80 / M4 G82 reverse form (chassis-first ordering seen in titles like "G80 M3").
    # Needed because G80/G82/G87 are in AMBIGUOUS_STANDALONE_CODES to block Genesis collisions.
    ("g80 m3", "BMW", "M3", "G80"),
    ("bmw g80 m3", "BMW", "M3", "G80"),
    # Product copy commonly writes "M3 (G80)" and "M4 (G82)" with the chassis in parens —
    # the plain "m3 g80" phrase won't match because the parens break the space separator.
    ("m3 (g80)", "BMW", "M3", "G80"),
    ("m4 (g82)", "BMW", "M4", "G82/G83"),
    ("m4 (g83)", "BMW", "M4", "G82/G83"),
    ("m2 (g87)", "BMW", "M2", "G87"),
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
    # BMW F8X = shared chassis code for F80 M3 + F82/F83 M4. Titles commonly read
    # "F8X M3/M4 …"; without these aliases the phrase doesn't resolve to either gen.
    ("f8x m3", "BMW", "M3", "F80"),
    ("f8x m4", "BMW", "M4", "F82/F83"),
    ("bmw f8x", "BMW", "M4", "F82/F83"),
    ("f8x m3/m4", "BMW", "M3", "F80"),
    ("f8x m3/m4", "BMW", "M4", "F82/F83"),
    ("f8x m2c", "BMW", "M2", "F87"),  # "M2 Competition" F87
    ("f8x m3 / m4", "BMW", "M3", "F80"),
    ("f8x m3 / m4", "BMW", "M4", "F82/F83"),
    # BMW X3 M (F97) / X4 M (F98)
    ("f97 x3m", "BMW", "X3 M", "F97"),
    ("x3m f97", "BMW", "X3 M", "F97"),
    ("bmw f97", "BMW", "X3 M", "F97"),
    ("bmw x3m", "BMW", "X3 M", "F97"),
    ("x3 m f97", "BMW", "X3 M", "F97"),
    ("f98 x4m", "BMW", "X4 M", "F98"),
    ("bmw x4m", "BMW", "X4 M", "F98"),
    # BMW X5M / X6M / XM (F9X platform; titles like "F9X X3M/X4M" are short-hand)
    ("f9x x3m", "BMW", "X3 M", "F97"),
    ("f9x x4m", "BMW", "X4 M", "F98"),
    ("f95 x5m", "BMW", "X5 M", "F95"),
    ("f96 x6m", "BMW", "X6 M", "F96"),
    ("bmw f95", "BMW", "X5 M", "F95"),
    ("x5m / x6m / xm", "BMW", "X5 M", "F95"),
    ("x5m / x6m / xm", "BMW", "X6 M", "F96"),
    ("x5m / x6m / xm", "BMW", "XM", "F95"),
    ("x5m/x6m/xm", "BMW", "X5 M", "F95"),
    ("x5m/x6m/xm", "BMW", "X6 M", "F96"),
    ("x5m/x6m/xm", "BMW", "XM", "F95"),
    ("bmw xm", "BMW", "XM", "F95"),
    # BMW M5 G90/G99 (current gen). ADRO pages say "BMW G90 M5" or "G9X M5".
    ("g90 m5", "BMW", "M5", "G90/G99"),
    ("m5 g90", "BMW", "M5", "G90/G99"),
    ("g99 m5", "BMW", "M5", "G90/G99"),
    ("m5 g99", "BMW", "M5", "G90/G99"),
    ("g9x m5", "BMW", "M5", "G90/G99"),
    ("m5 g9x", "BMW", "M5", "G90/G99"),
    ("bmw g90", "BMW", "M5", "G90/G99"),
    ("bmw g99", "BMW", "M5", "G90/G99"),
    # BMW F9X = F95 X5M / F96 X6M / F91/F92/F93 M8; for ADRO we mostly need X5M.
    ("f9x m5", "BMW", "M5", "F90"),
    ("f9x m5/m8", "BMW", "M5", "F90"),
    # BMW F1X M5/M6 — F10/F11/F12/F13 era.
    ("f1x m5", "BMW", "M5", "F10"),
    ("f1x m5/m6", "BMW", "M5", "F10"),
    ("f1x m5/m6", "BMW", "M6", "F12/F13/F06"),
    # Corvette C8 — disambiguate from Audi C8 platform
    ("corvette c8", "Chevrolet", "Corvette", "C8"),
    ("c8 corvette", "Chevrolet", "Corvette", "C8"),
    ("chevrolet corvette c8", "Chevrolet", "Corvette", "C8"),
    ("chevy corvette c8", "Chevrolet", "Corvette", "C8"),
    # Audi C8 (RS6/RS7/S6/S7) — only fires with explicit Audi model names
    ("rs6 c8", "Audi", "RS6 Avant", "C8"),
    ("audi rs6 c8", "Audi", "RS6 Avant", "C8"),
    ("c8 rs6", "Audi", "RS6 Avant", "C8"),
    ("rs7 c8", "Audi", "RS7 Sportback", "C8"),
    ("audi rs7 c8", "Audi", "RS7 Sportback", "C8"),
    ("c8 rs7", "Audi", "RS7 Sportback", "C8"),
    ("s6 c8", "Audi", "S6", "C8"),
    ("audi s6 c8", "Audi", "S6", "C8"),
    ("s7 c8", "Audi", "S7 Sportback", "C8"),
    ("audi s7 c8", "Audi", "S7 Sportback", "C8"),
    # Porsche Panamera 970 — require "panamera" in text
    ("panamera 970", "Porsche", "Panamera", "970"),
    ("970 panamera", "Porsche", "Panamera", "970"),
    ("porsche panamera 970", "Porsche", "Panamera", "970"),
    # BMW i5 M60 / Corrado G60 — require model name
    ("i5 m60", "BMW", "i5 M60", "G60"),
    ("bmw i5", "BMW", "i5 M60", "G60"),
    ("m60 i5", "BMW", "i5 M60", "G60"),
    ("bmw g60", "BMW", "i5 M60", "G60"),  # BMW G60 = i5 chassis; without "BMW" don't guess
    ("g60 m5", "BMW", "i5 M60", "G60"),  # occasional "G60 5-Series" from ADRO
    ("g60 5-series", "BMW", "i5 M60", "G60"),
    ("corrado g60", "Volkswagen", "Corrado", "G60"),
    ("vw corrado", "Volkswagen", "Corrado", "G60"),
    ("volkswagen corrado", "Volkswagen", "Corrado", "G60"),
    # Porsche 911 992 / 992.1 (GT3 is a 992 variant — product text says "992 GT3" / "992.1 GT3")
    ("992 gt3", "Porsche", "911", "992"),
    ("992.1 gt3", "Porsche", "911", "992"),
    ("992.2 gt3", "Porsche", "911", "992"),
    ("porsche 992", "Porsche", "911", "992"),
    ("porsche 991", "Porsche", "911", "991"),
    ("991 gt3", "Porsche", "911", "991"),
    ("991.1 gt3", "Porsche", "911", "991"),
    ("991.2 gt3", "Porsche", "911", "991"),
    ("991 turbo", "Porsche", "911", "991"),
    # Porsche 718 (982 chassis; ADRO titles: "PORSCHE 718 PREPREG ...")
    ("porsche 718", "Porsche", "718", "982"),
    ("718 boxster", "Porsche", "718", "982"),
    ("718 cayman", "Porsche", "718", "982"),
    ("718 gt4", "Porsche", "718", "982"),
    ("718 spyder", "Porsche", "718", "982"),
    # Tesla Model 3 (Highland = 2024+ facelift)
    ("tesla model 3", "Tesla", "Model 3", "Pre-Highland"),
    ("model 3 highland", "Tesla", "Model 3", "Highland"),
    ("tesla model 3 highland", "Tesla", "Model 3", "Highland"),
    ("model 3 performance", "Tesla", "Model 3", "Highland"),  # marketing "Performance" = Highland era
    ("model 3 highland performance", "Tesla", "Model 3", "Highland"),
    # Tesla Model Y (Juniper = 2025+ facelift)
    ("tesla model y", "Tesla", "Model Y", "1st Gen"),
    ("model y juniper", "Tesla", "Model Y", "Juniper"),
    ("tesla model y juniper", "Tesla", "Model Y", "Juniper"),
    ("model y performance", "Tesla", "Model Y", "1st Gen"),
    # Tesla Model S / X (Plaid = 2021+ refresh)
    ("tesla model s", "Tesla", "Model S", "Pre-Refresh"),
    ("model s plaid", "Tesla", "Model S", "Plaid"),
    ("tesla model s plaid", "Tesla", "Model S", "Plaid"),
    ("tesla model x", "Tesla", "Model X", "Pre-Refresh"),
    ("model x plaid", "Tesla", "Model X", "Plaid"),
    # Kia Stinger (CK; ADRO has many Stinger body kits)
    ("kia stinger", "Kia", "Stinger", "CK"),
    ("stinger gt", "Kia", "Stinger", "CK"),
    ("stinger ck", "Kia", "Stinger", "CK"),
    # Toyota GR Yaris (1st Gen = 2020-2023 GXPA16; 2nd Gen = 2024+ facelift on same chassis)
    # Plain "gr yaris" maps to 1st Gen. 2nd Gen aliases fire in addition when explicit refresh
    # language is present, so "GR Yaris (Gen 1 & 2)" titles end up linked to both rows.
    ("gr yaris", "Toyota", "GR Yaris", "1st Gen"),
    ("toyota gr yaris", "Toyota", "GR Yaris", "1st Gen"),
    ("yaris gr", "Toyota", "GR Yaris", "1st Gen"),
    ("gen 2 gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("2nd gen gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris gen 2", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris 2nd gen", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris (gen 2)", "Toyota", "GR Yaris", "2nd Gen"),
    ("2024 gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("2025 gr yaris", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris (gen 1 & 2)", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris gen 1 & 2", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris (gen 1 and 2)", "Toyota", "GR Yaris", "2nd Gen"),
    ("gr yaris gen 1 and 2", "Toyota", "GR Yaris", "2nd Gen"),
    # Subaru BRZ (ZD8 gen 2 common in ADRO text as "22+ GR86/BRZ")
    ("subaru brz", "Subaru", "BRZ", "ZD8"),
    ("brz zd8", "Subaru", "BRZ", "ZD8"),
    ("zd8 brz", "Subaru", "BRZ", "ZD8"),
    ("22+ brz", "Subaru", "BRZ", "ZD8"),
    ("22+ gr86", "Toyota", "GR86", "ZN8"),
    # BMW G87 M2 additional spellings (titles like "2023+ G87 BMW M2")
    ("2023+ g87", "BMW", "M2", "G87"),
    # Honda Civic Type R (FL5 newest, FK8 previous) — plain text in ADRO titles
    ("fl5 civic type r", "Honda", "Civic Type R", "FL5"),
    ("honda fl5", "Honda", "Civic Type R", "FL5"),
    ("fk8 civic type r", "Honda", "Civic Type R", "FK8"),
    # Hyundai Elantra N (only one gen CN7, including "PE" facelift trim)
    ("elantra n", "Hyundai", "Elantra N", "CN7"),
    ("hyundai elantra n", "Hyundai", "Elantra N", "CN7"),
    ("elantra n pe", "Hyundai", "Elantra N", "CN7"),
    # Hyundai Veloster N — performance trim of the JS-generation Veloster (2019-2022)
    ("veloster n", "Hyundai", "Veloster", "JS"),
    ("hyundai veloster n", "Hyundai", "Veloster", "JS"),
    # Genesis GV70 (only one gen JK1)
    ("genesis gv70", "Genesis", "GV70", "JK1"),
    ("gv70", "Genesis", "GV70", "JK1"),
    # Ford Mustang chassis codes (ADRO titles say "FORD MUSTANG", desc names S550/S650)
    ("s550", "Ford", "Mustang", "6th Gen"),
    ("mustang s550", "Ford", "Mustang", "6th Gen"),
    ("s650", "Ford", "Mustang", "7th Gen"),
    ("mustang s650", "Ford", "Mustang", "7th Gen"),
    ("s197", "Ford", "Mustang", "5th Gen"),
]

# Word-boundary for short codes so "A90" doesn't match inside "BA90", and "nd" not inside "random"
_SHORT_PHRASE_MAX_LEN = 8

# Aliases that need extra context so we don't match numbers/units: "42" in 0.42 Mu, "lb" in ft-lb / lug bolt
_AUDI_R8_42_PHRASES = ("r8 42", "42 r8", "r8 type 42", "audi r8 42", "audi r8 type 42")
_CHARGER_LB_PHRASES = ("charger lb", "dodge charger lb")


# Units / suffixes that turn a bare numeric phrase into a measurement rather than a chassis code.
# "970% downforce", "992 kph", "718 nm", "911 hp" are not car-generation references.
_NUMERIC_UNIT_SUFFIXES = (
    "%",
    "mm",
    "cm",
    "kph",
    "mph",
    "kw",
    "hp",
    "bhp",
    "whp",
    "nm",
    "lb",
    "lbs",
    "lb-ft",
    "ft-lb",
    "ft/lb",
)


def _is_numeric_measurement_context(text_lower: str, phrase_lower: str) -> bool:
    """
    True if a bare-numeric phrase (e.g. "970", "992") appears only as "<number><unit>"
    or "<number> <unit>" in the text — i.e. it's describing a measurement, not a chassis.
    Checks every occurrence; if any is not a measurement, inference can still fire.
    """
    if not phrase_lower.isdigit():
        return False
    pattern = re.compile(r"\b" + re.escape(phrase_lower) + r"\b\s*([A-Za-z%\-/]+)?")
    any_match = False
    for m in pattern.finditer(text_lower):
        any_match = True
        suffix = (m.group(1) or "").lower()
        if not suffix.startswith(_NUMERIC_UNIT_SUFFIXES):
            return False
    return any_match


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
        if not re.search(r"\b" + re.escape(phrase_lower.replace("/", r"/")) + r"\b", lower):
            return False
        # Bare numeric codes (e.g. "970", "992") that appear only in unit-suffixed contexts
        # ("970%", "992 kph") are measurements, not chassis references.
        if phrase_lower.isdigit() and _is_numeric_measurement_context(lower, phrase_lower):
            return False
        return True
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
    # URL slugs use '-'/'_' as word separators ("tesla-model-s-plaid"). Normalize those to
    # spaces so multi-word aliases like "tesla model s plaid" can match the URL portion.
    url_normalized = re.sub(r"[-_/]+", " ", url)
    combined = f"{name} {description} {url_normalized}".strip()
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
