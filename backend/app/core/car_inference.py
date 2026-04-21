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
        "IX",
        "X",  # Lancer Evolution Roman numerals; "X" alone fires on "1-7/8 X 3" product copy
        # Corvette C-generation codes collide with Audi C-platform codes (S6/RS6/RS7/S7).
        # Require model context: "corvette c7", "c7 z06", "rs6 c7", etc.
        "C4",  # Chevrolet Corvette C4 ↔ Audi S6 C4 platform
        "C5",  # Chevrolet Corvette C5 ↔ Audi RS6/S6 C5 platform
        "C6",  # Chevrolet Corvette C6 ↔ Audi RS6/S6 C6 platform
        "C7",  # Chevrolet Corvette C7 ↔ Audi RS6/RS7/S6/S7 C7 platform
        # Cross-make chassis-code collisions — require explicit model+code alias to fire.
        "C8",  # Chevrolet Corvette C8 ↔ Audi A6/RS6/A7/RS7/S6/S7 C8
        "E70",  # BMW X5 M E70 ↔ Toyota Corolla E70; require make+model context
        "F40",  # Ferrari F40 (1987-1992) ↔ BMW 1 Series F40 (2019+); require make/model context
        "Mk6",  # VW Golf/GTI/Jetta/Golf R Mk6 ↔ Ford Fiesta Mk6; require model+gen context
        "Mk7",  # VW Golf/GTI/Jetta/Golf R Mk7 ↔ Ford Fiesta Mk7; require model+gen context
        "G60",  # BMW i5 M60 G60 ↔ VW Corrado G60 (G-Lader 1.8L)
        "970",  # Porsche Panamera 970 — "970%" in hyperbolic marketing copy triggers it
        # BMW G-codes that collide with Genesis model names. Require make+model or model+code
        # disambiguating aliases ("m3 g80", "bmw i7", "genesis g80", etc.).
        "G70",  # BMW i7 M70 G70 ↔ Genesis G70 (sedan model)
        "G80",  # BMW M3 G80 ↔ Genesis G80 (sedan model)
        "G87",  # BMW M2 G87 — safer to require "m2 g87" / "g87 m2" context
        # Tesla trim name shared across models. Require "model s plaid" / "model x plaid" context.
        "Plaid",
        # Subaru WRX GC chassis ↔ BMW body-style suffix "Gran Coupe" / "xDrive GC".
        # Require "gc8" / "wrx gc" / "impreza gc" context for the Subaru match.
        "GC",
        # Common two-letter/short codes that appear constantly in product names — mass false positives.
        # Each requires a "model gen" or "make model" phrase (already built by PHRASE_TRIPLES).
        "HD",  # "ACT HD" clutch, "HD Series" wheels — require "elantra hd" for Hyundai Elantra HD
        "CV",  # CV joint / CV axle ubiquitous in driveline parts — require "ev6 gt cv"
        "CV1",  # "CV1" forged monoblock wheel product line — require "ev6 gt cv1"
        "S1",  # ARE "S1" hose identifier, "Series P1-S1xx" — require "rx-3 s1" for Mazda RX-3 S1
        "SH",  # Acura SH-AWD / Cusco product codes — require "forester xt sh" or "forester sh"
        "OS",  # Cusco "Type OS" rear strut bar product line — require "kona n os"
        "FS",  # Mazda FS engine code (FS-DE, FS-ZE) / Ford F-series suffix — require "veloster fs"
        "MD",  # MAGDRAIN "MD-05" magnetic drain bolt brand — require "elantra md"
        "BK",  # Subaru Legacy BK gen code / generic product-code suffix — require "genesis coupe bk"
        "LX",  # Lexus LX model name / luxury trim suffix — require "charger lx" or "dodge lx"
        "BP",  # "BP Automotive" standalone-harness brand — require "mazda3 bp" / "mazda bp"
        "XT",  # "Subaru Forester XT" and "Thule AirScreen XT" — require "subaru xt" for Subaru XT gen
        "CR",  # VW Touareg 3rd gen code — `\bcr\b` fires on "Honda CR-V"; require "touareg cr"
        "RL",  # Honda Odyssey 2nd-gen internal code — conflicts with "Acura RL" luxury sedan
        "RS",  # Audi RS model prefix / "RS coilovers" / "KW RS" — require "hr-v rs" or "honda rs" for HR-V RS gen
        "RU",  # Honda HR-V RU gen code — too short; require "hr-v ru" context
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
    # VW Mk6 platform — standalone "Mk6" blocked (Ford Fiesta Mk6 collision); require model context
    ("golf mk6", "Volkswagen", "Golf", "Mk6"),
    ("golf (mk6)", "Volkswagen", "Golf", "Mk6"),
    ("gti mk6", "Volkswagen", "GTI", "Mk6"),
    ("gti (mk6)", "Volkswagen", "GTI", "Mk6"),
    ("jetta mk6", "Volkswagen", "Jetta", "Mk6"),
    ("jetta (mk6)", "Volkswagen", "Jetta", "Mk6"),
    ("golf r mk6", "Volkswagen", "Golf R", "Mk6"),
    ("vw mk6", "Volkswagen", "Golf", "Mk6"),
    ("vw golf mk6", "Volkswagen", "Golf", "Mk6"),
    ("vw gti mk6", "Volkswagen", "GTI", "Mk6"),
    ("fiesta mk6", "Ford", "Fiesta", "Mk6"),
    ("ford fiesta mk6", "Ford", "Fiesta", "Mk6"),
    # VW Mk7 platform — standalone "Mk7" blocked (Ford Fiesta Mk7 collision); require model context
    ("golf mk7", "Volkswagen", "Golf", "Mk7"),
    ("golf (mk7)", "Volkswagen", "Golf", "Mk7"),
    ("gti mk7", "Volkswagen", "GTI", "Mk7"),
    ("gti (mk7)", "Volkswagen", "GTI", "Mk7"),
    ("jetta mk7", "Volkswagen", "Jetta", "Mk7"),
    ("jetta (mk7)", "Volkswagen", "Jetta", "Mk7"),
    ("golf r mk7", "Volkswagen", "Golf R", "Mk7"),
    ("golf r (mk7)", "Volkswagen", "Golf R", "Mk7"),
    ("golf mk7.5", "Volkswagen", "Golf", "Mk7"),
    ("golf (mk7.5)", "Volkswagen", "Golf", "Mk7"),
    ("gti mk7.5", "Volkswagen", "GTI", "Mk7"),
    ("gti (mk7.5)", "Volkswagen", "GTI", "Mk7"),
    ("golf r mk7.5", "Volkswagen", "Golf R", "Mk7"),
    ("vw mk7", "Volkswagen", "Golf", "Mk7"),
    ("vw golf mk7", "Volkswagen", "Golf", "Mk7"),
    ("vw gti mk7", "Volkswagen", "GTI", "Mk7"),
    ("vw golf r mk7", "Volkswagen", "Golf R", "Mk7"),
    ("fiesta mk7", "Ford", "Fiesta", "Mk7"),
    ("ford fiesta mk7", "Ford", "Fiesta", "Mk7"),
    ("fiesta st mk7", "Ford", "Fiesta ST", "Mk7"),
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
    # Chevrolet Corvette C5 (1997-2004) — disambiguate from Audi C5 platform (RS6/S6)
    ("c5 corvette", "Chevrolet", "Corvette", "C5"),
    ("corvette c5", "Chevrolet", "Corvette", "C5"),
    ("chevy c5", "Chevrolet", "Corvette", "C5"),
    ("chevrolet c5", "Chevrolet", "Corvette", "C5"),
    ("c5 z06", "Chevrolet", "Corvette", "C5"),
    # Audi RS6/S6 C5 platform — "RS6 Avant C5" auto-built; "rs6 c5" shorthand is not
    ("rs6 c5", "Audi", "RS6 Avant", "C5"),
    ("audi rs6 c5", "Audi", "RS6 Avant", "C5"),
    ("c5 rs6", "Audi", "RS6 Avant", "C5"),
    ("s6 c5", "Audi", "S6", "C5"),
    ("audi s6 c5", "Audi", "S6", "C5"),
    ("c5 s6", "Audi", "S6", "C5"),
    # Chevrolet Corvette C6 (2005-2013) — disambiguate from Audi C6 platform (RS6/S6)
    ("c6 corvette", "Chevrolet", "Corvette", "C6"),
    ("corvette c6", "Chevrolet", "Corvette", "C6"),
    ("chevy c6", "Chevrolet", "Corvette", "C6"),
    ("chevrolet c6", "Chevrolet", "Corvette", "C6"),
    ("c6 z06", "Chevrolet", "Corvette", "C6"),
    ("c6 zr1", "Chevrolet", "Corvette", "C6"),
    # Audi RS6/S6 C6 platform
    ("rs6 c6", "Audi", "RS6 Avant", "C6"),
    ("audi rs6 c6", "Audi", "RS6 Avant", "C6"),
    ("c6 rs6", "Audi", "RS6 Avant", "C6"),
    ("s6 c6", "Audi", "S6", "C6"),
    ("audi s6 c6", "Audi", "S6", "C6"),
    ("c6 s6", "Audi", "S6", "C6"),
    # Chevrolet Corvette C7 (2014-2019) — disambiguate from Audi C7 platform (RS6/RS7/S6/S7)
    ("c7 corvette", "Chevrolet", "Corvette", "C7"),
    ("corvette c7", "Chevrolet", "Corvette", "C7"),
    ("chevy c7", "Chevrolet", "Corvette", "C7"),
    ("chevrolet c7", "Chevrolet", "Corvette", "C7"),
    ("c7 z06", "Chevrolet", "Corvette", "C7"),
    ("c7 zo6", "Chevrolet", "Corvette", "C7"),  # common "ZO6" typo in product titles
    ("c7 zr1", "Chevrolet", "Corvette", "C7"),
    ("c7/c7 z06", "Chevrolet", "Corvette", "C7"),  # seen in ARH long-tube header titles
    # Audi RS6/RS7/S6/S7 C7 platform — shorthand "rs6 c7" not auto-built (full form is "rs6 avant c7")
    ("rs6 c7", "Audi", "RS6 Avant", "C7"),
    ("audi rs6 c7", "Audi", "RS6 Avant", "C7"),
    ("c7 rs6", "Audi", "RS6 Avant", "C7"),
    ("rs7 c7", "Audi", "RS7 Sportback", "C7"),
    ("audi rs7 c7", "Audi", "RS7 Sportback", "C7"),
    ("c7 rs7", "Audi", "RS7 Sportback", "C7"),
    ("s6 c7", "Audi", "S6", "C7"),
    ("audi s6 c7", "Audi", "S6", "C7"),
    ("c7 s6", "Audi", "S6", "C7"),
    ("s7 c7", "Audi", "S7 Sportback", "C7"),
    ("audi s7 c7", "Audi", "S7 Sportback", "C7"),
    ("c7 s7", "Audi", "S7 Sportback", "C7"),
    # BMW X5 M E70 / Toyota Corolla E70 — "E70" alone is ambiguous; require make+model context
    ("bmw e70", "BMW", "X5 M", "E70"),
    ("e70 x5m", "BMW", "X5 M", "E70"),
    ("x5m e70", "BMW", "X5 M", "E70"),
    ("e70 x5 m", "BMW", "X5 M", "E70"),
    ("x5 m e70", "BMW", "X5 M", "E70"),
    ("corolla e70", "Toyota", "Corolla", "E70"),
    ("e70 corolla", "Toyota", "Corolla", "E70"),
    ("toyota e70", "Toyota", "Corolla", "E70"),
    # Ferrari F40 (1987-1992) vs BMW 1 Series F40 (2019+) — gen_name="F40" for both
    # "ferrari f40" requires explicit alias since the gen code equals the model name
    ("ferrari f40", "Ferrari", "F40", "F40"),
    ("f40 ferrari", "Ferrari", "F40", "F40"),
    ("bmw f40", "BMW", "1 Series", "F40"),
    ("f40 bmw", "BMW", "1 Series", "F40"),
    ("bmw 1 series f40", "BMW", "1 Series", "F40"),
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
    # Ford Mustang year-range patterns commonly seen in product titles
    ("2015-2023 mustang", "Ford", "Mustang", "6th Gen"),
    ("2015+ mustang", "Ford", "Mustang", "6th Gen"),
    ("2015-2020 mustang", "Ford", "Mustang", "6th Gen"),
    ("2024+ mustang", "Ford", "Mustang", "7th Gen"),
    ("2024 mustang", "Ford", "Mustang", "7th Gen"),
    ("fox body mustang", "Ford", "Mustang", "3rd Gen"),
    ("fox body", "Ford", "Mustang", "3rd Gen"),  # "Fox Body" is almost always Mustang context
    ("sn95 mustang", "Ford", "Mustang", "4th Gen"),
    ("sn95", "Ford", "Mustang", "4th Gen"),
    ("5.0 mustang", "Ford", "Mustang", "6th Gen"),  # Coyote 5.0L era; older 5.0 is "fox body"
    ("gt500", "Ford", "Mustang", "6th Gen"),  # 2007-2014 GT500 = 5th Gen; 2020+ = 6th Gen — default to 6th
    ("shelby gt500", "Ford", "Mustang", "6th Gen"),
    # Ford F-150 year-range patterns (regular truck, not Raptor)
    ("2015-2020 f-150", "Ford", "F-150", "13th Gen"),
    ("2015-2020 ford f-150", "Ford", "F-150", "13th Gen"),
    ("2015+ f-150", "Ford", "F-150", "13th Gen"),
    ("2015-2022 f-150", "Ford", "F-150", "13th Gen"),
    ("2021+ f-150", "Ford", "F-150", "14th Gen"),
    ("2021-2023 f-150", "Ford", "F-150", "14th Gen"),
    ("2009-2014 f-150", "Ford", "F-150", "12th Gen"),
    ("2009-2014 ford f-150", "Ford", "F-150", "12th Gen"),
    ("2015-2020 f150", "Ford", "F-150", "13th Gen"),
    ("2021+ f150", "Ford", "F-150", "14th Gen"),
    # Mitsubishi Lancer Evolution — Roman numerals are in AMBIGUOUS_STANDALONE_CODES; need explicit aliases.
    # Short "evo X" forms (≤8 chars) get word-boundary checking so "evo v" won't match "evo vii".
    # Long "mitsubishi/lancer evo X" forms skip word boundaries — only use when X is NOT a
    # prefix of a higher generation numeral (safe: VIII, IX, X are not prefixes of anything higher).
    # Unsafe long forms omitted: mitsubishi/lancer evo i/ii/iii/iv/v/vi/vii would
    # substring-match higher generations via the long-phrase no-boundary path.
    ("evo i", "Mitsubishi", "Lancer Evolution", "I"),  # 5 chars — word-boundary checked ✓
    ("evo 1", "Mitsubishi", "Lancer Evolution", "I"),
    ("evo ii", "Mitsubishi", "Lancer Evolution", "II"),
    ("evo 2", "Mitsubishi", "Lancer Evolution", "II"),
    ("evo iii", "Mitsubishi", "Lancer Evolution", "III"),
    ("evo 3", "Mitsubishi", "Lancer Evolution", "III"),
    ("evo iv", "Mitsubishi", "Lancer Evolution", "IV"),
    ("evo 4", "Mitsubishi", "Lancer Evolution", "IV"),
    ("evo v", "Mitsubishi", "Lancer Evolution", "V"),  # word boundary: "evo v" ≠ "evo vii" ✓
    ("evo 5", "Mitsubishi", "Lancer Evolution", "V"),
    ("evo vi", "Mitsubishi", "Lancer Evolution", "VI"),
    ("evo 6", "Mitsubishi", "Lancer Evolution", "VI"),
    ("evo vii", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo 7", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 8", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("mitsubishi evo viii", "Mitsubishi", "Lancer Evolution", "VIII"),  # safe: "viii" not prefix of higher
    ("lancer evo viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("mitsubishi evo ix", "Mitsubishi", "Lancer Evolution", "IX"),  # safe: "ix" not prefix of higher
    ("lancer evo ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo 10", "Mitsubishi", "Lancer Evolution", "X"),
    ("evolution x", "Mitsubishi", "Lancer Evolution", "X"),
    ("lancer evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("mitsubishi evo x", "Mitsubishi", "Lancer Evolution", "X"),  # safe: X is the highest
    ("08-16 mitsubishi evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("08-15 mitsubishi evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("2008-2015 evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("2008-2015 mitsubishi evo", "Mitsubishi", "Lancer Evolution", "X"),
    # Evo VII/VIII/IX are all CT9A — product titles sometimes group them together
    ("evo vii / viii / ix", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo vii / viii / ix", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo vii / viii / ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 7/8/9", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo 7/8/9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 7/8/9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 7-9", "Mitsubishi", "Lancer Evolution", "VII"),
    ("evo 7-9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 7-9", "Mitsubishi", "Lancer Evolution", "IX"),
    # Infiniti G35 / G37 — already in DB (V35/V36) but "g35" bare name has no alias
    ("g35", "Infiniti", "G35", "V35"),
    ("infiniti g35", "Infiniti", "G35", "V35"),
    ("g35 coupe", "Infiniti", "G35", "V35"),
    ("g35 sedan", "Infiniti", "G35", "V35"),
    ("g37", "Infiniti", "G37", "V36"),
    ("infiniti g37", "Infiniti", "G37", "V36"),
    ("g37 coupe", "Infiniti", "G37", "V36"),
    ("g37 sedan", "Infiniti", "G37", "V36"),
    ("g37 ipl", "Infiniti", "G37", "V36"),
    # Infiniti Q50 / Q60 (VR30 engine; product titles often list Q50/Q60 together)
    ("q50", "Infiniti", "Q50", "V37"),
    ("infiniti q50", "Infiniti", "Q50", "V37"),
    ("q50 red sport", "Infiniti", "Q50", "V37"),
    ("q50/q60", "Infiniti", "Q50", "V37"),
    ("q50/q60", "Infiniti", "Q60", "V37"),
    ("q60", "Infiniti", "Q60", "V37"),
    ("infiniti q60", "Infiniti", "Q60", "V37"),
    ("q60 red sport", "Infiniti", "Q60", "V37"),
    # Nissan 350Z / 370Z / Z — bare model names don't have generation code in product titles
    ("350z", "Nissan", "350Z", "Z33"),
    ("nissan 350z", "Nissan", "350Z", "Z33"),
    ("370z", "Nissan", "370Z", "Z34"),
    ("nissan 370z", "Nissan", "370Z", "Z34"),
    ("09-20 nissan 370z", "Nissan", "370Z", "Z34"),
    ("nissan z", "Nissan", "Z", "RZ34"),
    ("2023+ nissan z", "Nissan", "Z", "RZ34"),
    ("2023 nissan z", "Nissan", "Z", "RZ34"),
    ("2024 nissan z", "Nissan", "Z", "RZ34"),
    ("rz34", "Nissan", "Z", "RZ34"),
    # Chevrolet Camaro year-range patterns
    ("2010-2015 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2010-2015 chevrolet camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2010+ camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro ss 2010", "Chevrolet", "Camaro", "5th Gen"),
    ("2010-14 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2016+ camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("2016-2024 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("2016-2022 camaro", "Chevrolet", "Camaro", "6th Gen"),
    # Pontiac G8 (VE Commodore-based, 2008-2009; Pontiac brand discontinued 2010)
    ("pontiac g8", "Pontiac", "G8", "VE"),
    ("g8 gt", "Pontiac", "G8", "VE"),
    ("g8 gxp", "Pontiac", "G8", "VE"),
    # Pontiac GTO (Holden Monaro generation)
    ("pontiac gto", "Pontiac", "GTO", "Holden"),
    ("2004-2006 gto", "Pontiac", "GTO", "Holden"),
    ("2004 gto", "Pontiac", "GTO", "Holden"),
    ("2005 gto", "Pontiac", "GTO", "Holden"),
    ("2006 gto", "Pontiac", "GTO", "Holden"),
    # Pontiac Firebird 4th Gen (F-body, LS1)
    ("pontiac firebird", "Pontiac", "Firebird", "4th Gen"),
    ("firebird trans am", "Pontiac", "Firebird", "4th Gen"),
    ("trans am ws6", "Pontiac", "Firebird", "4th Gen"),
    # Subaru WRX GD sub-chassis codes — product text uses GDA/GDB; DB stores simplified "GD".
    # GDA = 2002-2007 WRX sedan, GDB = 2002-2007 WRX wagon/hatch. Both map to WRX GD.
    ("wrx gda", "Subaru", "WRX", "GD"),
    ("wrx gdb", "Subaru", "WRX", "GD"),
    ("gda wrx", "Subaru", "WRX", "GD"),
    ("gdb wrx", "Subaru", "WRX", "GD"),
    ("gda/gdb", "Subaru", "WRX", "GD"),
    ("gda / gdb", "Subaru", "WRX", "GD"),  # product titles often space around slash
    ("gda-gdb", "Subaru", "WRX", "GD"),
    ("impreza wrx gda", "Subaru", "WRX", "GD"),
    ("impreza wrx gdb", "Subaru", "WRX", "GD"),
    ("impreza gda", "Subaru", "Impreza", "GD/GG"),
    ("impreza gdb", "Subaru", "Impreza", "GD/GG"),
    # Subaru WRX GR sub-chassis codes — GRB = 2008-2014 WRX hatch, GRF = WRX sedan. Both = WRX GR.
    ("wrx grb", "Subaru", "WRX", "GR"),
    ("wrx grf", "Subaru", "WRX", "GR"),
    ("grb wrx", "Subaru", "WRX", "GR"),
    ("grf wrx", "Subaru", "WRX", "GR"),
    ("grb/grf", "Subaru", "WRX", "GR"),
    ("impreza grb", "Subaru", "Impreza", "GE/GH"),
    ("impreza gvb", "Subaru", "Impreza", "GE/GH"),
    # Subaru WRX GC — "GC" standalone is blocked (BMW Gran Coupe false positives).
    # Require chassis "GC8" or compound phrases. PHRASE_TRIPLES still covers "wrx gc" / "subaru wrx gc".
    ("gc8", "Subaru", "WRX", "GC"),
    ("gc8 wrx", "Subaru", "WRX", "GC"),
    ("wrx gc8", "Subaru", "WRX", "GC"),
    ("subaru gc8", "Subaru", "WRX", "GC"),
    ("gc wrx", "Subaru", "WRX", "GC"),
    ("impreza gc", "Subaru", "WRX", "GC"),
    ("92-00 subaru wrx", "Subaru", "WRX", "GC"),
    ("1992-2000 subaru wrx", "Subaru", "WRX", "GC"),
    # Subaru WRX STI — "STI" alone is too short/ambiguous; require compound forms.
    # Maps "wrx sti" / "subaru sti" to GD+GR+VA since those eras share most STI aftermarket parts.
    # VB (2022+) dropped the STI; use explicit "vb" / "2022+ wrx" aliases for that gen.
    ("wrx sti", "Subaru", "WRX", "GD"),
    ("wrx sti", "Subaru", "WRX", "GR"),
    ("wrx sti", "Subaru", "WRX", "VA"),
    ("subaru sti", "Subaru", "WRX", "GD"),
    ("subaru sti", "Subaru", "WRX", "GR"),
    ("subaru sti", "Subaru", "WRX", "VA"),
    ("subaru wrx sti", "Subaru", "WRX", "GD"),
    ("subaru wrx sti", "Subaru", "WRX", "GR"),
    ("subaru wrx sti", "Subaru", "WRX", "VA"),
    # Era-specific STI aliases (chassis suffix commonly used in product titles)
    ("sti gd", "Subaru", "WRX", "GD"),
    ("sti gdb", "Subaru", "WRX", "GD"),
    ("sti gr", "Subaru", "WRX", "GR"),
    ("sti grb", "Subaru", "WRX", "GR"),
    ("sti va", "Subaru", "WRX", "VA"),
    ("sti vb", "Subaru", "WRX", "VB"),
    ("2004-2021 subaru sti", "Subaru", "WRX", "GD"),
    ("2004-2021 subaru sti", "Subaru", "WRX", "GR"),
    ("2004-2021 subaru sti", "Subaru", "WRX", "VA"),
    ("2004+ subaru sti", "Subaru", "WRX", "GD"),
    ("2004+ subaru sti", "Subaru", "WRX", "GR"),
    ("2004+ subaru sti", "Subaru", "WRX", "VA"),
    ("2004-2007 subaru sti", "Subaru", "WRX", "GD"),
    ("2004-2007 subaru wrx sti", "Subaru", "WRX", "GD"),
    ("2008-2014 subaru sti", "Subaru", "WRX", "GR"),
    ("2008-2021 subaru sti", "Subaru", "WRX", "GR"),
    ("2008-2021 subaru sti", "Subaru", "WRX", "VA"),
    ("2015-2021 subaru sti", "Subaru", "WRX", "VA"),
    ("2022+ subaru wrx", "Subaru", "WRX", "VB"),
    ("2022-2024 subaru wrx", "Subaru", "WRX", "VB"),
    # Honda S2000 — AP1/AP2 codes exist in PHRASE_TRIPLES but bare "S2000" / "Honda S2000" need aliases
    ("honda s2000", "Honda", "S2000", "AP1"),
    ("honda s2000", "Honda", "S2000", "AP2"),
    ("s2000", "Honda", "S2000", "AP1"),
    ("s2000", "Honda", "S2000", "AP2"),
    ("2000-2003 honda s2000", "Honda", "S2000", "AP1"),
    ("2000-2003 s2000", "Honda", "S2000", "AP1"),
    ("2004-2009 honda s2000", "Honda", "S2000", "AP2"),
    ("2004-2009 s2000", "Honda", "S2000", "AP2"),
    # Honda Civic gen-number aliases — only 10th gen had aliases; extend to 8th/9th/11th
    ("8th gen civic", "Honda", "Civic", "8th Gen"),
    ("civic 8th gen", "Honda", "Civic", "8th Gen"),
    ("8th gen", "Honda", "Civic", "8th Gen"),  # 2006-2011; "8th gen" is common Civic shorthand
    ("9th gen civic", "Honda", "Civic", "9th Gen"),
    ("civic 9th gen", "Honda", "Civic", "9th Gen"),
    ("9th gen", "Honda", "Civic", "9th Gen"),  # 2012-2015
    ("11th gen civic", "Honda", "Civic", "11th Gen"),
    ("civic 11th gen", "Honda", "Civic", "11th Gen"),
    ("11th gen", "Honda", "Civic", "11th Gen"),  # 2022+
    # Honda Civic "Nth Generation" full-word spelling (product titles spell out "Generation" not "Gen")
    ("civic 7th generation", "Honda", "Civic", "7th Gen"),
    ("honda civic 7th generation", "Honda", "Civic", "7th Gen"),
    ("7th generation civic", "Honda", "Civic", "7th Gen"),
    ("civic (7th generation)", "Honda", "Civic", "7th Gen"),
    ("civic 8th generation", "Honda", "Civic", "8th Gen"),
    ("honda civic 8th generation", "Honda", "Civic", "8th Gen"),
    ("8th generation civic", "Honda", "Civic", "8th Gen"),
    ("civic (8th generation)", "Honda", "Civic", "8th Gen"),
    ("civic 9th generation", "Honda", "Civic", "9th Gen"),
    ("honda civic 9th generation", "Honda", "Civic", "9th Gen"),
    ("9th generation civic", "Honda", "Civic", "9th Gen"),
    ("civic (9th generation)", "Honda", "Civic", "9th Gen"),
    ("civic 10th generation", "Honda", "Civic", "10th Gen"),
    ("honda civic 10th generation", "Honda", "Civic", "10th Gen"),
    ("10th generation civic", "Honda", "Civic", "10th Gen"),
    ("civic (10th generation)", "Honda", "Civic", "10th Gen"),
    ("civic 11th generation", "Honda", "Civic", "11th Gen"),
    ("honda civic 11th generation", "Honda", "Civic", "11th Gen"),
    # Honda Civic Si — trim designation (not a separate model); map by era to the correct Civic gen
    ("civic si 2006", "Honda", "Civic", "8th Gen"),
    ("2006-2011 civic si", "Honda", "Civic", "8th Gen"),
    ("2012-2015 civic si", "Honda", "Civic", "9th Gen"),
    ("civic si 2012", "Honda", "Civic", "9th Gen"),
    ("2017-2021 civic si", "Honda", "Civic", "10th Gen"),
    ("2022+ civic si", "Honda", "Civic", "11th Gen"),
    # Honda Civic Hatchback year-specific (Sport/Hatchback = non-Type-R versions)
    ("2017-2021 civic hatchback", "Honda", "Civic", "10th Gen"),
    ("2016-2021 civic hatchback", "Honda", "Civic", "10th Gen"),
    ("civic hatchback 2017", "Honda", "Civic", "10th Gen"),
    # Acura TSX — CL9/CU2 in PHRASE_TRIPLES but bare "Acura TSX" needs aliases
    ("acura tsx", "Acura", "TSX", "CL9"),
    ("acura tsx", "Acura", "TSX", "CU2"),
    ("04-08 acura tsx", "Acura", "TSX", "CL9"),
    ("09-14 acura tsx", "Acura", "TSX", "CU2"),
    # Acura RSX — DC5 only; "Acura RSX" / "Acura Integra RSX" bare forms
    ("acura rsx", "Acura", "RSX", "DC5"),
    ("acura integra rsx", "Acura", "RSX", "DC5"),
    ("02-06 acura rsx", "Acura", "RSX", "DC5"),
    # Acura TLX — "acura tlx" could be 1st or 2nd gen; "type-s" pins to 2nd gen
    ("acura tlx", "Acura", "TLX", "1st Gen"),
    ("acura tlx", "Acura", "TLX", "2nd Gen"),
    ("tlx type-s", "Acura", "TLX", "2nd Gen"),
    ("acura tlx type-s", "Acura", "TLX", "2nd Gen"),
    ("2021+ acura tlx", "Acura", "TLX", "2nd Gen"),
    ("2015-2020 acura tlx", "Acura", "TLX", "1st Gen"),
    # Acura NSX — NA1/NA2 and NC1; "acura nsx" spans both gens without year context
    ("acura nsx", "Acura", "NSX", "NA1/NA2"),
    ("acura nsx", "Acura", "NSX", "NC1"),
    ("nsx na1", "Acura", "NSX", "NA1/NA2"),
    ("nsx nc1", "Acura", "NSX", "NC1"),
    # BMW E46 325 / 330 — product titles sometimes omit the "i" suffix
    ("e46 325", "BMW", "3 Series", "E46"),
    ("bmw e46 325", "BMW", "3 Series", "E46"),
    ("e46 330", "BMW", "330i", "E46"),
    ("bmw e46 330", "BMW", "330i", "E46"),
    # Nissan 240SX S15 / Silvia S15 — sold in Japan only but common in US aftermarket
    ("s15", "Nissan", "240SX", "S15"),
    ("240sx s15", "Nissan", "240SX", "S15"),
    ("nissan s15", "Nissan", "240SX", "S15"),
    ("silvia s15", "Nissan", "240SX", "S15"),
    ("nissan silvia s15", "Nissan", "240SX", "S15"),
    ("99-02 nissan silvia", "Nissan", "240SX", "S15"),
    # Nissan 240SX bare model name (often no S13/S14 suffix in product titles)
    ("nissan 240sx", "Nissan", "240SX", "S13"),
    ("nissan 240sx", "Nissan", "240SX", "S14"),
    # Infiniti G35 grouped with Nissan 350Z in product titles
    ("350z/g35", "Nissan", "350Z", "Z33"),
    ("350z/g35", "Infiniti", "G35", "V35"),
    ("350z / g35", "Nissan", "350Z", "Z33"),
    ("350z / g35", "Infiniti", "G35", "V35"),
    ("350z/g35/g37", "Nissan", "350Z", "Z33"),
    ("350z/g35/g37", "Infiniti", "G35", "V35"),
    ("350z/g35/g37", "Infiniti", "G37", "V36"),
    # Kia EV6 GT — standalone "CV"/"CV1" are now blocked; product text says "EV6 GT" or "Kia EV6"
    ("ev6 gt", "Kia", "EV6 GT", "CV"),
    ("kia ev6 gt", "Kia", "EV6 GT", "CV"),
    ("kia ev6", "Kia", "EV6 GT", "CV"),
    # Hyundai Kona N — standalone "OS" is now blocked; product text often says just "Kona N"
    ("kona n", "Hyundai", "Kona N", "OS"),
    ("hyundai kona n", "Hyundai", "Kona N", "OS"),
    # Dodge Charger LX — standalone "LX" blocked; "dodge lx" seen in driveline product titles
    ("dodge lx", "Dodge", "Charger", "LX"),
    ("dodge lx charger", "Dodge", "Charger", "LX"),
    # Subaru Forester XT SH — parenthetical form "Subaru Forester (SH)" in product titles
    ("forester (sh)", "Subaru", "Forester XT", "SH"),
    ("subaru forester (sh)", "Subaru", "Forester XT", "SH"),
    # Mazda Mazda3 BP — standalone "BP" blocked; "mazda bp" engine-code shorthand still used
    ("mazda bp", "Mazda", "Mazda3", "BP"),
    ("mazda 3 bp", "Mazda", "Mazda3", "BP"),
    # Audi B5 S4/RS4/A4 — B5 is in AMBIGUOUS_STANDALONE_CODES so "b5" alone won't fire.
    # Product titles often say "B5 Audi S4" (B5 before model name) which doesn't match "s4 b5" PHRASE_TRIPLE.
    ("b5 audi s4", "Audi", "S4", "B5"),
    ("b5 audi rs4", "Audi", "RS4", "B5"),
    ("b5 audi a4", "Audi", "A4", "B5"),
    ("b5 audi s4/rs4", "Audi", "S4", "B5"),
    ("b5 audi s4/rs4", "Audi", "RS4", "B5"),
    ("b5 s4/rs4", "Audi", "S4", "B5"),
    ("b5 s4/rs4", "Audi", "RS4", "B5"),
    # Audi UrS4 (C4 platform, 1991-1994) — "UrS4" is a community nickname, not an official model name.
    # The DB model is "S4 (UrS4)" generation "C4". "urs4/urs6" product titles pair with UrS6 = S6 C4.
    ("urs4", "Audi", "S4 (UrS4)", "C4"),
    ("ur-s4", "Audi", "S4 (UrS4)", "C4"),
    ("audi urs4", "Audi", "S4 (UrS4)", "C4"),
    ("audi ur-s4", "Audi", "S4 (UrS4)", "C4"),
    ("urs4/urs6", "Audi", "S4 (UrS4)", "C4"),
    ("urs4/urs6", "Audi", "S6", "C4"),
    ("urs4 urs6", "Audi", "S4 (UrS4)", "C4"),
    ("urs4 urs6", "Audi", "S6", "C4"),
    # Audi UrS6 (C4 platform, 1994-1997) — already in DB as S6/C4.
    ("urs6", "Audi", "S6", "C4"),
    ("ur-s6", "Audi", "S6", "C4"),
    ("audi urs6", "Audi", "S6", "C4"),
    # Audi UrQuattro (Typ 85, 1980-1991) — the original turbocharged quattro coupe.
    ("urquattro", "Audi", "UrQuattro", "Typ 85"),
    ("ur-quattro", "Audi", "UrQuattro", "Typ 85"),
    ("audi urquattro", "Audi", "UrQuattro", "Typ 85"),
    ("audi ur-quattro", "Audi", "UrQuattro", "Typ 85"),
    ("audi urq", "Audi", "UrQuattro", "Typ 85"),
    ("quattro typ 85", "Audi", "UrQuattro", "Typ 85"),
    # Audi 80/90 — B2/B3/B4 small-chassis cars (034Motorsport's vintage Audi catalog).
    # "B3" alone is too ambiguous (Bilstein B3); require "audi" context.
    ("audi 80", "Audi", "80/90", "B3"),  # default to B3 (most common tuning target)
    ("audi 90", "Audi", "80/90", "B3"),
    ("audi b3 80", "Audi", "80/90", "B3"),
    ("audi b3 90", "Audi", "80/90", "B3"),
    ("audi b3 chassis", "Audi", "80/90", "B3"),
    ("audi b2 chassis", "Audi", "80/90", "B2"),
    ("audi b4 chassis", "Audi", "80/90", "B4"),
    ("audi 80/90", "Audi", "80/90", "B3"),
    ("audi coupe quattro", "Audi", "80/90", "B3"),
    ("coupe quattro", "Audi", "80/90", "B3"),
    ("audi small chassis", "Audi", "80/90", "B3"),
    ("audi small chassis", "Audi", "80/90", "B2"),
    ("audi vintage small chassis", "Audi", "80/90", "B2"),
    # Audi 100/200/5000 — C3/C4 cars referenced in 034Motorsport product titles.
    ("audi 200", "Audi", "100/200", "C3"),
    ("audi 200 quattro", "Audi", "100/200", "C3"),
    ("audi 200 20v", "Audi", "100/200", "C3"),
    ("audi 5000", "Audi", "100/200", "C3"),
    ("audi 100", "Audi", "100/200", "C4"),
    ("audi 100 quattro", "Audi", "100/200", "C4"),
    # Pontiac F-Body — "F-body" spans Camaro 3rd/4th Gen and Firebird 3rd/4th Gen.
    # Year context distinguishes 3rd (1982-1992) from 4th (1993-2002).
    ("f-body", "Chevrolet", "Camaro", "3rd Gen"),
    ("f-body", "Chevrolet", "Camaro", "4th Gen"),
    ("f-body", "Pontiac", "Firebird", "3rd Gen"),
    ("f-body", "Pontiac", "Firebird", "4th Gen"),
    ("fbody", "Chevrolet", "Camaro", "3rd Gen"),
    ("fbody", "Chevrolet", "Camaro", "4th Gen"),
    ("fbody", "Pontiac", "Firebird", "3rd Gen"),
    ("fbody", "Pontiac", "Firebird", "4th Gen"),
    ("camaro & firebird", "Chevrolet", "Camaro", "4th Gen"),
    ("camaro & firebird", "Pontiac", "Firebird", "4th Gen"),
    ("camaro and firebird", "Chevrolet", "Camaro", "4th Gen"),
    ("camaro and firebird", "Pontiac", "Firebird", "4th Gen"),
    ("camaro/firebird", "Chevrolet", "Camaro", "4th Gen"),
    ("camaro/firebird", "Pontiac", "Firebird", "4th Gen"),
    # Mazda Miata NA6 / NA8 sub-chassis codes (both are part of the NA generation).
    ("na6 miata", "Mazda", "Miata", "NA"),
    ("miata na6", "Mazda", "Miata", "NA"),
    ("na6 chassis", "Mazda", "Miata", "NA"),
    ("na6", "Mazda", "Miata", "NA"),
    ("na8 miata", "Mazda", "Miata", "NA"),
    ("miata na8", "Mazda", "Miata", "NA"),
    ("na8 chassis", "Mazda", "Miata", "NA"),
    ("na8", "Mazda", "Miata", "NA"),
    # Mazdaspeed Miata / Mazdaspeed MX-5 (NB2 with factory turbo, 2004-2005)
    ("mazdaspeed miata", "Mazda", "Miata", "NB"),
    ("mazdaspeed mx-5", "Mazda", "Miata", "NB"),
    ("mazdaspeed 6 turbo", "Mazda", "Mazda6", "GG/GY"),
    # Audi S2 B4 — often grouped with RS2 in product titles ("S2/RS2", "B4 S2/RS2")
    ("audi s2", "Audi", "S2", "B4"),
    ("s2 coupe audi", "Audi", "S2", "B4"),
    ("b4 s2", "Audi", "S2", "B4"),
    ("s2/rs2", "Audi", "S2", "B4"),
    ("s2/rs2", "Audi", "RS2 Avant", "1st Gen"),
    # Subaru WRX bare model — "subaru wrx" without gen code is very common in product titles.
    # GC is excluded (pre-US; most parts are for GD onward). VB is excluded (separate alias above).
    ("subaru wrx", "Subaru", "WRX", "GD"),
    ("subaru wrx", "Subaru", "WRX", "GR"),
    ("subaru wrx", "Subaru", "WRX", "VA"),
    # VB-specific year phrases that don't include "subaru" adjacent to the year
    ("2022+ wrx", "Subaru", "WRX", "VB"),
    ("2022-2024 wrx", "Subaru", "WRX", "VB"),
    ("2022 wrx", "Subaru", "WRX", "VB"),
    ("2023+ wrx", "Subaru", "WRX", "VB"),
    ("2024 wrx", "Subaru", "WRX", "VB"),
    # Subaru "Impreza WRX" / "Impreza STI" — older naming before WRX was a standalone model.
    # "Impreza WRX" name was used for GC (1992-2000) and GD (2001-2007).
    ("impreza wrx", "Subaru", "WRX", "GC"),
    ("impreza wrx", "Subaru", "WRX", "GD"),
    ("subaru impreza wrx", "Subaru", "WRX", "GC"),
    ("subaru impreza wrx", "Subaru", "WRX", "GD"),
    ("impreza sti", "Subaru", "WRX", "GD"),
    ("impreza sti", "Subaru", "WRX", "GR"),
    ("subaru impreza sti", "Subaru", "WRX", "GD"),
    ("subaru impreza sti", "Subaru", "WRX", "GR"),
    # Subaru WRX/STI year-range patterns (vendor fitment format: "YY-YY Make Model")
    ("02-07 subaru wrx", "Subaru", "WRX", "GD"),
    ("02-07 subaru impreza wrx", "Subaru", "WRX", "GD"),
    ("02-07 wrx", "Subaru", "WRX", "GD"),
    ("05-07 sti", "Subaru", "WRX", "GD"),
    ("05-07 subaru sti", "Subaru", "WRX", "GD"),
    ("05-07 subaru impreza sti", "Subaru", "WRX", "GD"),
    ("08-14 subaru wrx", "Subaru", "WRX", "GR"),
    ("08-14 subaru impreza wrx", "Subaru", "WRX", "GR"),
    ("08-14 wrx", "Subaru", "WRX", "GR"),
    ("08-14 subaru sti", "Subaru", "WRX", "GR"),
    ("08-14 subaru impreza sti", "Subaru", "WRX", "GR"),
    ("08-14 sti", "Subaru", "WRX", "GR"),
    ("08-21 sti", "Subaru", "WRX", "GR"),  # 2008-2021 STI spans GR and VA
    ("08-21 sti", "Subaru", "WRX", "VA"),
    ("08-21 subaru sti", "Subaru", "WRX", "GR"),
    ("08-21 subaru sti", "Subaru", "WRX", "VA"),
    ("15-21 wrx", "Subaru", "WRX", "VA"),
    ("15-21 subaru wrx", "Subaru", "WRX", "VA"),
    ("15-21 sti", "Subaru", "WRX", "VA"),
    ("15-21 subaru sti", "Subaru", "WRX", "VA"),
    ("15-21 subaru impreza sti", "Subaru", "WRX", "VA"),
    ("04-21 sti", "Subaru", "WRX", "GD"),  # multi-gen: GD + GR + VA
    ("04-21 sti", "Subaru", "WRX", "GR"),
    ("04-21 sti", "Subaru", "WRX", "VA"),
    ("04-21 subaru sti", "Subaru", "WRX", "GD"),
    ("04-21 subaru sti", "Subaru", "WRX", "GR"),
    ("04-21 subaru sti", "Subaru", "WRX", "VA"),
    # Subaru WRX/STI sub-chassis codes used in product titles
    ("wrx gda", "Subaru", "WRX", "GD"),
    ("wrx gdb", "Subaru", "WRX", "GD"),
    ("sti gde", "Subaru", "WRX", "GD"),
    ("sti gdf", "Subaru", "WRX", "GD"),
    ("wrx gh8", "Subaru", "WRX", "GR"),
    ("wrx gh", "Subaru", "WRX", "GR"),
    ("sti grb", "Subaru", "WRX", "GR"),
    ("wrx vab", "Subaru", "WRX", "VA"),
    ("wrx vaf", "Subaru", "WRX", "VA"),
    ("sti vab", "Subaru", "WRX", "VA"),
    # Aston Martin Vantage — product titles use "V8 Vantage"/"V12 Vantage" without the make name
    ("v8 vantage", "Aston Martin", "Vantage", "V8 Vantage"),
    ("aston martin v8 vantage", "Aston Martin", "Vantage", "V8 Vantage"),
    ("v12 vantage", "Aston Martin", "Vantage", "V12 Vantage"),
    ("aston martin v12 vantage", "Aston Martin", "Vantage", "V12 Vantage"),
    ("aston martin vantage", "Aston Martin", "Vantage", "V8 Vantage"),
    ("aston martin vantage", "Aston Martin", "Vantage", "V12 Vantage"),
    # Toyota Celica year-range aliases (product names use year ranges, not "7th Gen")
    ("00-05 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("00-06 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("1999-2005 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("2000-2005 toyota celica", "Toyota", "Celica", "7th Gen"),
    ("toyota celica", "Toyota", "Celica", "6th Gen"),  # broad: most parts target 6th/7th gen
    ("toyota celica", "Toyota", "Celica", "7th Gen"),
    # Toyota MR2 Spyder (W30) year-range aliases
    ("mr2 spyder", "Toyota", "MR2", "W30"),
    ("toyota mr2 spyder", "Toyota", "MR2", "W30"),
    ("00-05 toyota mr2", "Toyota", "MR2", "W30"),
    ("00-07 toyota mr2", "Toyota", "MR2", "W30"),
    # Nissan Altima year-range aliases (generation codes L30/L31/L32/L34 rarely appear in product text)
    ("02-06 nissan altima", "Nissan", "Altima", "L30"),
    ("07-12 nissan altima", "Nissan", "Altima", "L31"),
    ("07-18 nissan altima", "Nissan", "Altima", "L31"),
    ("13-18 nissan altima", "Nissan", "Altima", "L32"),
    ("nissan altima", "Nissan", "Altima", "L31"),  # broad: L31 most common tuning target
    ("nissan altima", "Nissan", "Altima", "L32"),
    # Nissan Sentra year-range aliases
    ("00-06 nissan sentra", "Nissan", "Sentra", "B15"),
    ("07-12 nissan sentra", "Nissan", "Sentra", "B16"),
    ("13-19 nissan sentra", "Nissan", "Sentra", "B17"),
    ("nissan sentra", "Nissan", "Sentra", "B15"),  # broad
    ("nissan sentra", "Nissan", "Sentra", "B16"),
    # Nissan Maxima year-range aliases
    ("00-03 nissan maxima", "Nissan", "Maxima", "A33"),
    ("04-08 nissan maxima", "Nissan", "Maxima", "A34"),
    ("09-14 nissan maxima", "Nissan", "Maxima", "A35"),
    ("07-18 nissan altima / 09-23 nissan maxima", "Nissan", "Altima", "L31"),
    ("07-18 nissan altima / 09-23 nissan maxima", "Nissan", "Maxima", "A35"),
    ("02-06 nissan altima / 04-08 nissan maxima", "Nissan", "Altima", "L30"),
    ("02-06 nissan altima / 04-08 nissan maxima", "Nissan", "Maxima", "A34"),
    # Nissan Juke year-range aliases (F15 is the only US-market generation)
    ("nissan juke", "Nissan", "Juke", "F15"),
    ("10-17 nissan juke", "Nissan", "Juke", "F15"),
    ("10-17 juke", "Nissan", "Juke", "F15"),
    # Hyundai Elantra year-range aliases (generation codes HD/MD/AD in AMBIGUOUS_STANDALONE_CODES)
    ("00-06 hyundai elantra", "Hyundai", "Elantra", "XD"),
    ("07-10 hyundai elantra", "Hyundai", "Elantra", "HD"),
    ("11-16 hyundai elantra", "Hyundai", "Elantra", "MD"),
    ("11-15 hyundai elantra", "Hyundai", "Elantra", "MD"),
    ("16-20 hyundai elantra", "Hyundai", "Elantra", "AD"),
    ("21-24 hyundai elantra", "Hyundai", "Elantra", "CN7"),
    ("hyundai elantra", "Hyundai", "Elantra", "MD"),  # broad: MD most common tuning target
    ("hyundai elantra", "Hyundai", "Elantra", "AD"),
    # Hyundai Tiburon year-range aliases
    ("97-99 hyundai tiburon", "Hyundai", "Tiburon", "RD1"),
    ("00-01 hyundai tiburon", "Hyundai", "Tiburon", "RD2"),
    ("03-08 hyundai tiburon", "Hyundai", "Tiburon", "GK"),
    ("hyundai tiburon", "Hyundai", "Tiburon", "GK"),
    # Hyundai Genesis Coupe year-range aliases (BK in AMBIGUOUS_STANDALONE_CODES)
    ("10-12 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("10-16 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("10-16 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("13-16 hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("hyundai genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    ("genesis coupe", "Hyundai", "Genesis Coupe", "BK"),
    ("genesis coupe", "Hyundai", "Genesis Coupe", "BK2"),
    # Hyundai Veloster year-range aliases (FS/JS in AMBIGUOUS_STANDALONE_CODES)
    ("12-18 hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("11-17 hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("18-22 hyundai veloster", "Hyundai", "Veloster", "JS"),
    ("hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("hyundai veloster", "Hyundai", "Veloster", "JS"),
    ("veloster turbo", "Hyundai", "Veloster", "FS"),
    ("veloster n", "Hyundai", "Veloster", "JS"),
    # Acura TL year-range aliases
    ("99-03 acura tl", "Acura", "TL", "2nd Gen"),
    ("04-08 acura tl", "Acura", "TL", "3rd Gen"),
    ("09-14 acura tl", "Acura", "TL", "4th Gen"),
    ("acura tl", "Acura", "TL", "3rd Gen"),
    ("acura tl", "Acura", "TL", "4th Gen"),
    # Acura RDX year-range aliases
    ("07-12 acura rdx", "Acura", "RDX", "TB1/TB2"),
    ("13-18 acura rdx", "Acura", "RDX", "TB3/TB4"),
    ("acura rdx", "Acura", "RDX", "TB1/TB2"),  # broad: TB1/TB2 turbo most tuning-popular
    ("acura rdx", "Acura", "RDX", "TB3/TB4"),
    # Acura ILX year-range aliases
    ("13-15 acura ilx", "Acura", "ILX", "DE3"),
    ("16-22 acura ilx", "Acura", "ILX", "DE3"),
    ("acura ilx", "Acura", "ILX", "DE3"),
    # Acura Integra/RSX combined product name alias (often listed together in fitment guides)
    ("acura integra / rsx", "Acura", "RSX", "DC5"),
    ("acura integra/rsx", "Acura", "RSX", "DC5"),
    ("02-06 acura integra / rsx", "Acura", "RSX", "DC5"),
    ("02-06 acura rsx", "Acura", "RSX", "DC5"),
    # Acura Integra year-range aliases (gen names "3rd Gen"/"4th Gen" rarely appear in product text)
    ("94-01 acura integra", "Acura", "Integra", "3rd Gen"),
    ("97-01 acura integra", "Acura", "Integra", "3rd Gen"),
    ("02-06 acura integra", "Acura", "Integra", "4th Gen"),
    ("acura integra", "Acura", "Integra", "3rd Gen"),  # broad: 3rd+4th most common
    ("acura integra", "Acura", "Integra", "4th Gen"),
    ("acura integra type-r", "Acura", "Integra Type R", "DC2"),
    ("integra type-r", "Acura", "Integra Type R", "DC2"),
    # Honda CR-V year-range aliases
    ("02-06 honda cr-v", "Honda", "CR-V", "RD4/RD5/RD6/RD7"),
    ("07-11 honda cr-v", "Honda", "CR-V", "RE"),
    ("12-16 honda cr-v", "Honda", "CR-V", "RM"),
    ("17-22 honda cr-v", "Honda", "CR-V", "RW"),
    ("honda cr-v", "Honda", "CR-V", "RE"),  # broad: RE most tuning-popular
    ("honda cr-v", "Honda", "CR-V", "RM"),
    # Honda HR-V year-range aliases
    ("16-22 honda hr-v", "Honda", "HR-V", "RU"),
    ("23-24 honda hr-v", "Honda", "HR-V", "RS"),
    ("honda hr-v", "Honda", "HR-V", "RU"),
    # HR-V RS gen — "RS" standalone blocked; need explicit context
    ("hr-v rs", "Honda", "HR-V", "RS"),
    ("honda hr-v rs", "Honda", "HR-V", "RS"),
    # HR-V RU gen — "RU" standalone blocked; need explicit context
    ("hr-v ru", "Honda", "HR-V", "RU"),
    ("honda hr-v ru", "Honda", "HR-V", "RU"),
    # Honda Element year-range aliases
    ("03-11 honda element", "Honda", "Element", "YH"),
    ("honda element", "Honda", "Element", "YH"),
    # Honda Odyssey year-range aliases ("RL" standalone is blocked — conflicts with Acura RL)
    ("99-04 honda odyssey", "Honda", "Odyssey", "RL"),
    ("honda odyssey rl", "Honda", "Odyssey", "RL"),
    ("05-10 honda odyssey", "Honda", "Odyssey", "RL3"),
    ("11-17 honda odyssey", "Honda", "Odyssey", "RL4"),
    ("18-24 honda odyssey", "Honda", "Odyssey", "RL5"),
    ("honda odyssey", "Honda", "Odyssey", "RL3"),  # broad
    ("honda odyssey", "Honda", "Odyssey", "RL4"),
    # Honda Insight year-range aliases
    ("10-14 honda insight", "Honda", "Insight", "2nd Gen"),
    ("honda insight", "Honda", "Insight", "2nd Gen"),
    # Honda Fit year-range aliases (generation names "1st Gen" etc. rarely appear in product text)
    ("07-08 honda fit", "Honda", "Fit", "1st Gen"),
    ("09-13 honda fit", "Honda", "Fit", "2nd Gen"),
    ("15-20 honda fit", "Honda", "Fit", "3rd Gen"),
    ("honda fit", "Honda", "Fit", "2nd Gen"),  # broad
    ("honda fit", "Honda", "Fit", "3rd Gen"),
    # Acura MDX year-range aliases
    ("07-13 acura mdx", "Acura", "MDX", "YD2"),
    ("14-20 acura mdx", "Acura", "MDX", "YD3"),
    ("14-21 acura mdx", "Acura", "MDX", "YD3"),
    ("acura mdx", "Acura", "MDX", "YD2"),  # broad
    ("acura mdx", "Acura", "MDX", "YD3"),
    # Acura RLX year-range aliases
    ("14-20 acura rlx", "Acura", "RLX", "KC2"),
    ("acura rlx", "Acura", "RLX", "KC2"),
    # Acura RL year-range aliases (separate from RLX; "RL" standalone blocked — conflicts with Honda Odyssey gen)
    ("96-04 acura rl", "Acura", "RL", "KA9"),
    ("05-12 acura rl", "Acura", "RL", "KB1"),
    ("acura rl", "Acura", "RL", "KA9"),
    ("acura rl", "Acura", "RL", "KB1"),
    # Honda Civic year-range aliases — product titles often have trim/variant before generation
    # (e.g., "01-05 Honda Civic Base / Si / Type-R") so PHRASE_TRIPLE can't match
    ("01-05 honda civic", "Honda", "Civic", "7th Gen"),
    ("06-11 honda civic", "Honda", "Civic", "8th Gen"),
    ("2006-2011 honda civic", "Honda", "Civic", "8th Gen"),
    ("12-15 honda civic", "Honda", "Civic", "9th Gen"),
    ("2012-2015 honda civic", "Honda", "Civic", "9th Gen"),
    ("16-21 honda civic", "Honda", "Civic", "10th Gen"),
    ("2016-2021 honda civic", "Honda", "Civic", "10th Gen"),
    ("17-21 honda civic", "Honda", "Civic", "10th Gen"),
    ("22-24 honda civic", "Honda", "Civic", "11th Gen"),
    ("honda civic si", "Honda", "Civic", "8th Gen"),  # Si trims across 8th/9th/10th
    ("honda civic si", "Honda", "Civic", "9th Gen"),
    ("honda civic si", "Honda", "Civic", "10th Gen"),
    # Honda Accord year-range aliases (same issue — trim names interrupt make/model/gen)
    ("03-07 honda accord", "Honda", "Accord", "7th Gen"),
    ("08-12 honda accord", "Honda", "Accord", "8th Gen"),
    ("13-17 honda accord", "Honda", "Accord", "9th Gen"),
    ("18-22 honda accord", "Honda", "Accord", "10th Gen"),
    # Toyota Camry year-range aliases (gen codes XV10/XV20/etc. rarely appear in product titles)
    ("97-01 toyota camry", "Toyota", "Camry", "XV20"),
    ("02-06 toyota camry", "Toyota", "Camry", "XV30"),
    ("07-11 toyota camry", "Toyota", "Camry", "XV40"),
    ("12-17 toyota camry", "Toyota", "Camry", "XV50"),
    ("18-24 toyota camry", "Toyota", "Camry", "XV70"),
    ("toyota camry", "Toyota", "Camry", "XV40"),  # broad: most common tuning targets
    ("toyota camry", "Toyota", "Camry", "XV50"),
    ("toyota camry", "Toyota", "Camry", "XV70"),
    # Toyota Corolla year-range aliases
    ("03-08 toyota corolla", "Toyota", "Corolla", "E140"),
    ("09-13 toyota corolla", "Toyota", "Corolla", "E150"),
    ("09-19 toyota corolla", "Toyota", "Corolla", "E150"),  # product titles often span gens
    ("09-19 toyota corolla", "Toyota", "Corolla", "E170"),
    ("14-18 toyota corolla", "Toyota", "Corolla", "E170"),
    ("19-24 toyota corolla", "Toyota", "Corolla", "E210"),
    ("toyota corolla", "Toyota", "Corolla", "E140"),  # broad
    ("toyota corolla", "Toyota", "Corolla", "E150"),
    ("toyota corolla", "Toyota", "Corolla", "E170"),
    # Toyota Prius year-range aliases
    ("00-03 toyota prius", "Toyota", "Prius", "NHW11"),
    ("01-03 toyota prius", "Toyota", "Prius", "NHW11"),
    ("04-09 toyota prius", "Toyota", "Prius", "XW20"),
    ("10-15 toyota prius", "Toyota", "Prius", "ZVW30"),
    ("16-22 toyota prius", "Toyota", "Prius", "ZVW50"),
    ("23-24 toyota prius", "Toyota", "Prius", "ZVW60"),
    ("toyota prius", "Toyota", "Prius", "XW20"),  # broad: XW20 and ZVW30 most common
    ("toyota prius", "Toyota", "Prius", "ZVW30"),
    ("prius zvw30", "Toyota", "Prius", "ZVW30"),
    # Toyota Yaris year-range aliases
    ("06-11 toyota yaris", "Toyota", "Yaris", "XP90"),
    ("07-11 toyota yaris", "Toyota", "Yaris", "XP90"),
    ("12-18 toyota yaris", "Toyota", "Yaris", "XP130"),
    ("12-23 toyota yaris", "Toyota", "Yaris", "XP130"),
    ("toyota yaris", "Toyota", "Yaris", "XP90"),  # broad
    ("toyota yaris", "Toyota", "Yaris", "XP130"),
    # Toyota Echo year-range aliases
    ("00-05 toyota echo", "Toyota", "Echo", "P10"),
    ("toyota echo", "Toyota", "Echo", "P10"),
    # Toyota Venza year-range aliases
    ("09-17 toyota venza", "Toyota", "Venza", "1st Gen"),
    ("toyota venza", "Toyota", "Venza", "1st Gen"),
    ("toyota venza", "Toyota", "Venza", "2nd Gen"),
    # Toyota C-HR year-range aliases
    ("18-24 toyota c-hr", "Toyota", "C-HR", "AX10"),
    ("toyota c-hr", "Toyota", "C-HR", "AX10"),
    # Toyota Matrix year-range aliases
    ("03-08 toyota matrix", "Toyota", "Matrix", "E130"),
    ("09-13 toyota matrix", "Toyota", "Matrix", "E150"),
    ("toyota matrix", "Toyota", "Matrix", "E130"),  # broad
    ("toyota matrix", "Toyota", "Matrix", "E150"),
    ("03-08 toyota corolla / altis / matrix", "Toyota", "Corolla", "E140"),
    ("03-08 toyota corolla / altis / matrix", "Toyota", "Matrix", "E130"),
    # Lexus IS model-number aliases — "IS250"/"IS350" are trim names, not generation codes
    ("lexus is250", "Lexus", "IS", "XE20"),
    ("lexus is250", "Lexus", "IS", "XE30"),
    ("lexus is350", "Lexus", "IS", "XE20"),
    ("lexus is350", "Lexus", "IS", "XE30"),
    ("lexus is300", "Lexus", "IS", "XE10"),
    ("lexus is300", "Lexus", "IS", "XE20"),
    ("lexus is200", "Lexus", "IS", "XE10"),
    ("lexus is-f", "Lexus", "IS F", "XE20"),
    ("lexus isf", "Lexus", "IS F", "XE20"),
    ("06-13 lexus is", "Lexus", "IS", "XE20"),
    ("99-05 lexus is", "Lexus", "IS", "XE10"),
    ("14-20 lexus is", "Lexus", "IS", "XE30"),
    # Lexus GS model-number aliases
    ("lexus gs300", "Lexus", "GS", "JZS160"),
    ("lexus gs400", "Lexus", "GS", "JZS160"),
    ("lexus gs430", "Lexus", "GS", "JZS160"),
    ("lexus gs430", "Lexus", "GS", "GRS190"),
    ("lexus gs350", "Lexus", "GS", "GRS190"),
    ("lexus gs350", "Lexus", "GS", "GRL10"),
    ("lexus gs300", "Lexus", "GS", "GRS190"),
    ("06-11 lexus gs", "Lexus", "GS", "GRS190"),
    ("12-20 lexus gs", "Lexus", "GS", "GRL10"),
    ("98-05 lexus gs", "Lexus", "GS", "JZS160"),
    # Mitsubishi Eclipse year-range aliases (gen names "Third Generation" etc. don't appear in product text)
    ("00-05 mitsubishi eclipse", "Mitsubishi", "Eclipse", "Third Generation"),
    ("06-12 mitsubishi eclipse", "Mitsubishi", "Eclipse", "Fourth Generation"),
    ("mitsubishi eclipse", "Mitsubishi", "Eclipse", "Third Generation"),
    ("mitsubishi eclipse", "Mitsubishi", "Eclipse", "Fourth Generation"),
    # Mitsubishi Lancer (non-Evo) — require make+model to avoid matching "lancer evolution"
    ("mitsubishi lancer", "Mitsubishi", "Lancer", "CJ"),
    ("02-07 mitsubishi lancer", "Mitsubishi", "Lancer", "CS/CT"),
    ("08-17 mitsubishi lancer", "Mitsubishi", "Lancer", "CJ"),
    ("lancer gt", "Mitsubishi", "Lancer", "CJ"),
    ("lancer gts", "Mitsubishi", "Lancer", "CJ"),
    ("lancer se", "Mitsubishi", "Lancer", "CJ"),
    # Mitsubishi Outlander year-range aliases
    ("03-06 mitsubishi outlander", "Mitsubishi", "Outlander", "1st Gen"),
    ("07-13 mitsubishi outlander", "Mitsubishi", "Outlander", "2nd Gen"),
    ("14-21 mitsubishi outlander", "Mitsubishi", "Outlander", "3rd Gen"),
    ("mitsubishi outlander", "Mitsubishi", "Outlander", "2nd Gen"),
    ("mitsubishi outlander", "Mitsubishi", "Outlander", "3rd Gen"),
    ("outlander gt", "Mitsubishi", "Outlander", "3rd Gen"),
    # Mini Cooper chassis-code and year-range aliases
    ("mini cooper r50", "Mini", "Cooper", "R50/R52/R53"),
    ("mini cooper r52", "Mini", "Cooper", "R50/R52/R53"),
    ("mini cooper r53", "Mini", "Cooper", "R50/R52/R53"),
    ("mini r50", "Mini", "Cooper", "R50/R52/R53"),
    ("mini r53", "Mini", "Cooper", "R50/R52/R53"),
    ("02-06 mini cooper", "Mini", "Cooper", "R50/R52/R53"),
    ("mini cooper r56", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("mini cooper r55", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("mini r56", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("07-13 mini cooper", "Mini", "Cooper", "R55/R56/R57/R58/R59"),
    ("mini cooper f56", "Mini", "Cooper", "F55/F56/F57"),
    ("mini cooper f55", "Mini", "Cooper", "F55/F56/F57"),
    ("mini f56", "Mini", "Cooper", "F55/F56/F57"),
    ("14-24 mini cooper", "Mini", "Cooper", "F55/F56/F57"),
    ("14-23 mini cooper", "Mini", "Cooper", "F55/F56/F57"),
    # Mini Countryman chassis-code aliases
    ("mini countryman r60", "Mini", "Countryman", "R60"),
    ("mini r60", "Mini", "Countryman", "R60"),
    ("11-16 mini countryman", "Mini", "Countryman", "R60"),
    ("mini countryman f60", "Mini", "Countryman", "F60"),
    ("mini f60", "Mini", "Countryman", "F60"),
    ("17-23 mini countryman", "Mini", "Countryman", "F60"),
    # VW Touareg year-range aliases
    ("04-10 volkswagen touareg", "Volkswagen", "Touareg", "7L"),
    ("04-10 vw touareg", "Volkswagen", "Touareg", "7L"),
    ("11-18 volkswagen touareg", "Volkswagen", "Touareg", "7P"),
    ("11-18 vw touareg", "Volkswagen", "Touareg", "7P"),
    ("volkswagen touareg", "Volkswagen", "Touareg", "7L"),
    ("volkswagen touareg", "Volkswagen", "Touareg", "7P"),
    ("vw touareg", "Volkswagen", "Touareg", "7L"),
    ("vw touareg", "Volkswagen", "Touareg", "7P"),
    ("touareg", "Volkswagen", "Touareg", "7L"),
    ("touareg", "Volkswagen", "Touareg", "7P"),
    # Subaru Legacy year-range aliases — generation codes use "/" ("BE/BH") which fails substring
    # matching when product titles space-pad the slash ("Legacy (BE / BH)").
    ("00-04 subaru legacy", "Subaru", "Legacy", "BE/BH"),
    ("subaru legacy be / bh", "Subaru", "Legacy", "BE/BH"),
    ("subaru legacy be/bh", "Subaru", "Legacy", "BE/BH"),
    ("05-09 subaru legacy", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bl / bp", "Subaru", "Legacy", "BL/BP"),
    ("10-14 subaru legacy", "Subaru", "Legacy", "BM/BR"),
    ("subaru legacy bm9", "Subaru", "Legacy", "BM/BR"),
    ("subaru legacy bm / br", "Subaru", "Legacy", "BM/BR"),
    ("15-19 subaru legacy", "Subaru", "Legacy", "BN/BS"),
    ("subaru legacy bn9", "Subaru", "Legacy", "BN/BS"),
    ("subaru legacy bn / bs", "Subaru", "Legacy", "BN/BS"),
    # Subaru Impreza base (non-WRX) year-range aliases
    ("17-23 subaru impreza", "Subaru", "Impreza", "GP/GJ"),
    ("subaru impreza sport", "Subaru", "Impreza", "GP/GJ"),
    ("subaru impreza base", "Subaru", "Impreza", "GP/GJ"),
    # Subaru Legacy GT (spec.B / GT) year-range aliases
    ("2006-2009 legacy gt", "Subaru", "Legacy GT", "BL/BP"),
    ("2006-2009 legacy spec b", "Subaru", "Legacy GT", "BL/BP"),
    ("legacy spec b", "Subaru", "Legacy GT", "BL/BP"),
    ("legacy gt spec b", "Subaru", "Legacy GT", "BL/BP"),
    ("subaru legacy gt", "Subaru", "Legacy GT", "BL/BP"),
    # Hyundai Genesis Sedan — separate from Genesis Coupe; not in seed data, map to brand Genesis
    ("09-14 hyundai genesis sedan", "Genesis", "G80", "DH"),
    ("15-16 hyundai genesis sedan", "Genesis", "G80", "DH"),
    ("hyundai genesis sedan", "Genesis", "G80", "DH"),
    # Subaru Outback XT year-range aliases — generation codes use "/" same as Legacy
    ("subaru outback bl / bp", "Subaru", "Outback XT", "BL/BP"),
    ("subaru outback bm / br", "Subaru", "Outback XT", "BM/BR"),
    ("05-09 subaru outback", "Subaru", "Outback XT", "BL/BP"),
    ("10-14 subaru outback", "Subaru", "Outback XT", "BM/BR"),
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
    # Strip parentheses from product names — fitment titles like "(7th Generation)" or "(FWD / AWD)"
    # would otherwise block substring matching against PHRASE_TRIPLES (which don't contain parens).
    name_normalized = re.sub(r"[()]", " ", name)
    desc_normalized = re.sub(r"[()]", " ", description)
    combined = re.sub(r" {2,}", " ", f"{name_normalized} {desc_normalized} {url_normalized}").strip()
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
