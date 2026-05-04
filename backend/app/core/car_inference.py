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

from sqlalchemy import select

from app.core.car_generations_data import CAR_GENERATIONS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


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
        # Dodge Charger "2024+" LB gen collides with BMW G-chassis "(2024+)" year suffixes.
        "2024+",
        # Ferrari/Porsche numeric model names that collide with BMW part numbers, bore-size text,
        # and dash-list chassis fragments. Require make/model context.
        "308",  # Ferrari 308 ↔ E24 635CSi, bore fragments
        "328",  # Ferrari 328 ↔ BMW 328i trim, E46 325/328/330i list context
        "348",  # Ferrari 348 ↔ dash-list like "F32 F33 F34 F36"
        "356",  # Porsche 356 ↔ BMW part-number digits "… 356"
        "928",  # Porsche 928 ↔ BMW E46 Parking Brake Boot digits
        "930",  # Porsche 911 930 ↔ "4.930\"" LS valve length, 930 CV joint name
        "944",  # Porsche 944 ↔ BMW E34 Door Handle part numbers
        "992",  # Porsche 911 992 ↔ "3.992\"" bore text
        "997",  # Porsche 911 997 ↔ "3.997\"" LS head-gasket bore text
        # Displacement / forced-induction codes that collide with Audi/VW chassis letters.
        "7L",  # VW Touareg 7L ↔ "2.7L"/"6.7L"/"7.0L" displacement
        "8L",  # Audi A3/S3 8L ↔ "1.8L"/"3.8L"/"4.8L" displacement
        "8T",  # Audi A5/S5/RS5 8T ↔ "1.8T"/"2.0T"/"2.7T" forced induction
        # Two-letter/short chassis codes with known mass false positives.
        "A5",  # VW Beetle A5 ↔ Audi A5 model name in "A4/A5" product titles
        "A35",  # Nissan Maxima A35 ↔ Mercedes-AMG A35 hatchback
        "AD",  # Hyundai Elantra AD ↔ "LHD"/"RHD"/"ADaptive" fragments
        "AE86",  # Seeded AE86 gen ↔ other Corolla-era products; require "corolla ae86" / "toyota ae86"
        "B2",  # Audi 80/90 B2 ↔ ECU connector labels ("B2" pin)
        "B6",  # Audi A4/S4 B6 ↔ Bilstein B6 Performance, Miata B6 engine code
        "B8",  # Audi A4/S4 B8 ↔ Bilstein B8 5100/5160/6112 shock product line
        "B16",  # Nissan Sentra B16 ↔ Bilstein B16 PSS9 + Honda B16 engine code
        "B18",  # Nissan Sentra B18 ↔ Honda B18 engine code
        "BC",  # Subaru Legacy BC ↔ product SKUs / BC Racing brand
        "BD",  # Subaru Legacy BD ↔ Kia Forte GT BD
        "BF",  # Subaru Legacy BF ↔ Mazda 323 GTX BF
        "BG",  # Subaru Legacy BG ↔ BC Racing fitment text
        "BJ",  # Subaru Legacy BJ ↔ Mazdaspeed Protegé BJ
        "BL",  # Subaru Legacy/Outback BL ↔ Mazda3 BL
        "BM",  # Subaru Legacy BM ↔ "BMW" substring, Mazda3 BM
        "BN",  # Subaru Legacy BN short-year forms
        "BR",  # Subaru Legacy BR / Outback BR
        "BS",  # Subaru Legacy BS short-year forms
        "BT",  # Subaru Baja BT gen
        "CE",  # Mitsubishi Lancer CE gen
        "CT",  # Mitsubishi Lancer CT / CT9A Evo
        "DA",  # Acura DA Integra (2nd Gen)
        "E30",  # BMW 3 Series / M3 E30 ↔ Ford Bronco Raptor part codes
        "E60",  # BMW M5 E60 ↔ "E60-E85" ethanol fuel labels in RS3 Stage tunes
        "EG",  # Honda Civic EG chassis — generic English letter pair
        "EK",  # Honda Civic EK chassis — same
        "F15",  # BMW X5 F15 ↔ Nissan Juke F15
        "F16",  # BMW X6 F16 ↔ Nissan Juke F16
        "GD",  # Mazda MX-6 GD ↔ Subaru WRX GD
        "GE",  # Mazda MX-6 GE ↔ "4A-GE", "2JZ-GE", "1ZZ-GE", "4U-GSE" engine codes
        "J1",  # Porsche Taycan J1 ↔ SKUs like "HP-EGJ1AX"
        "LD",  # Dodge Charger LD ↔ CORSA Silverado/Sierra exhaust copy
        "L30",  # Nissan Altima L30 ↔ bolt-length labels ("M8 P1.25 L30")
        "Mk1",  # Multi-make (Focus / R8 / Golf / Rabbit / Scirocco Mk1)
        "Mk2",  # Multi-make (Focus / R8 / Scirocco Mk2)
        "Mk3",  # Multi-make (Focus / Golf / Scirocco Mk3) ↔ "Toyota Supra (MK3)"
        "P10",  # Infiniti G20 P10 ↔ URL slugs "/p10" and "P1.0" bolt-pitch labels
        "P11",  # Infiniti G20 P11 ↔ forgeline URL trailing IDs ("/p11")
        "R32",  # Nissan GT-R R32 / Nissan Skyline R32 ↔ VW Golf R32 / VR6 3.2L
        "RA",  # Honda Odyssey RA — preemptive; require "odyssey ra"
        "RD",  # Honda CR-V RD ↔ "RD" in part SKUs / "Ford" substring contexts
        "RE",  # Honda CR-V RE ↔ "re-torque", "re-install", "you're", contraction word-boundaries (largest FP cluster)
        "RM",  # Honda CR-V RM ↔ BC Racing "RM Series" coilovers
        "S14",  # BMW M3 E30 S14 engine code ↔ Nissan 240SX S14
        "S50",  # BMW S50 engine code ↔ Infiniti FX35/FX45 S50 gen
        "M30",  # BMW M30 engine code ↔ Infiniti M30 model
        "VE",  # Pontiac G8 VE / Holden VE ↔ "we've", "automotive", "Verus"
        "VF",  # Holden VF / Chevy SS VF ↔ "automotiVE" fragments
        "VR6",  # VW Corrado VR6 ↔ VR6 engine family on Golf/Jetta/Passat/R32
        "T6",  # Ford Ranger T6 ↔ "6061-T6" aircraft aluminum tempering spec
        # --- Tier-1 audit (2026-05) FALSE-POSITIVE PURGE ---------------------
        # Whole-gen-name slash-split offenders. Worst absolute offenders found in
        # the live DB audit (62% of attributed parts had at least one FP). Adding
        # the WHOLE gen_name suppresses the per-component standalone emission
        # entirely; rely on "make model gen_name" / "model gen_name" full phrases
        # plus CAR_ALIASES for legitimate matches.
        "Turbo/Shelby",  # Dodge Daytona — components "turbo"/"shelby" hit ~2,900 parts
        "R/T Turbo",  # Dodge Stealth — component "r" / "t turbo" too generic (~2,080 parts)
        "BE/BH",  # Subaru Legacy / Legacy GT — "be"/"bh" hit ~6,448 parts
        "E36/7",  # BMW Z3 M — bare "7" hit ~3,000 parts
        "E36/8",  # BMW Z3 M — bare "8" same lineage
        "E36/7 E36/8",  # BMW Z3 (combined gen_name) — splits to "7 E36"/"8"
        "V1",  # Volvo S40 / V40 — bare "v1" hit ~456 parts
        # English-word-shaped components from the slash-splits above.
        "Turbo",
        "Shelby",
        "BE",
        "BH",
        "R",  # Dodge Stealth R/T Turbo component — single-letter, must never fire
        "T",  # Dodge Stealth R/T Turbo component — single-letter, must never fire
        "7",  # BMW Z3 E36/7 component — single-digit, must never fire
        "8",  # BMW Z3 E36/8 component — single-digit, must never fire
        # Audit-flagged 2-3 char alpha codes shared with brand SKU prefixes,
        # English words, or other common product-text fragments. Each requires
        # a "make model" or "model gen_name" full phrase to fire.
        "DB5",  # Aston Martin DB5
        "DB6",  # Aston Martin DB6
        "DB7",  # Aston Martin DB7
        "DB9",  # Aston Martin DB9
        "DBS",  # Aston Martin DBS — collides with "ABS" / "DBS" wheel SKU prefixes
        "GLH",  # Dodge Omni GLH — collides with brand SKUs
        "GTB",  # Ferrari 296/488 GTB — collides with retailer SKU "GTB-XXX"
        "ZRC",  # Lexus RC / RC F — collides with retailer SKU prefix
        "CXD",  # Subaru SVX
        "FY",  # Audi SQ5 FY — 2-char code, frequent SKU/brand collision
        "RG",  # Genesis G70 RG
        "DH",  # Genesis G80 DH
        "RW",  # Honda CR-V RW
        "YH",  # Honda Element YH
        "GK",  # Hyundai Tiburon GK
        "XD",  # Hyundai Elantra XD
        "JS",  # Hyundai Veloster JS — also "JS Performance" / JavaScript fragments
        "NE",  # Hyundai Ioniq 5 N NE — 2-char prefix collision
        "CK",  # Kia Stinger CK
        "TF",  # Kia Optima SX TF
        "JF",  # Kia Optima SX JF
        "VT",  # Lamborghini Diablo VT — collides with "VTec", "VT" brand
        "SV",  # Lamborghini Diablo SV — collides with "SV" trims, "Land Rover SV"
        "NB",  # Mazda Miata NB — 2-char alpha
        "NC",  # Mazda Miata NC
        "ND",  # Mazda Miata ND — collides with "and", "second", "Found"
        "SA",  # Mazda RX-7 SA
        "FB",  # Mazda RX-7 FB — collides with "FB" SKU codes
        "FC",  # Mazda RX-7 FC
        "FD",  # Mazda RX-7 FD
        "JC",  # Mazda Cosmo JC
        "GG",  # Mazda6 GG/GY component
        "GY",  # Mazda6 GG/GY component
        "GH",  # Mazda6 GH component
        "GJ",  # Mazda6 GJ/GL / Subaru Impreza GP/GJ
        "GL",  # Mazda6 GL component
        "CS",  # Mitsubishi Lancer CS — collides with "CS" trims, "carbon stainless"
        "CJ",  # Mitsubishi Lancer CJ
        "VA",  # Subaru WRX VA — collides with state abbrev / "VA" SKU
        "VB",  # Subaru WRX VB
        "GF",  # Subaru Impreza GC/GF component
        "GP",  # Subaru Impreza GP/GJ component
        "SF",  # Subaru Forester SF
        "SG",  # Subaru Forester SG
        "SJ",  # Subaru Forester SJ
    }
)
"""Generation codes that must NOT fire on their own because they collide with
other tokens in scraped catalog data.

Purpose:
    Codes in this set require an adjacent make+model phrase (see PHRASE_TRIPLES
    and CAR_ALIASES in this module) to disambiguate. Bare standalone matches
    are suppressed by ``_build_phrase_triples`` to avoid false positives like
    "HI" in "HKS Hi Power" incorrectly matching Genesis G90 HI, or "NA" in
    "CTEK MXS 5.0 NA" incorrectly matching Miata NA.

Criterion for adding a code:
    - It matches a real product-name token (brand, SKU suffix, marketing phrase,
      engine code, bore/displacement figure) that creates repeated false
      positives in scraped catalog data, AND/OR
    - It is shared across multiple make/model lineages and cannot disambiguate
      without the paired make/model string.

Criterion for removing a code:
    - The colliding brand/product is retired or absent from the current retailer
      catalog, AND
    - No remaining collisions exist in representative scraped samples, AND
    - Removing the entry provably improves recall without introducing new false
      positives (verify against ``test_car_inference.py`` +
      ``test_car_inference_ambiguity.py``).

Known counterexamples:
    See ``backend/tests/test_car_inference_ambiguity.py`` for ~20+ pinned
    behaviors. Those tests assert CURRENT behavior, not CORRECTNESS. The
    ML-based rewrite (PARTS-V2-01) is explicitly deferred to v2 per
    ``.planning/REQUIREMENTS.md``.
"""


def _is_too_short_to_dispatch(component: str) -> bool:
    """
    Generic length-based filter for slash-split gen-name components.

    Tier-1 audit (2026-05) found that splitting gen_names like ``Turbo/Shelby``,
    ``R/T Turbo``, ``E36/7 E36/8`` and ``BE/BH`` produced 1-2 char and 1-2 digit
    standalone phrases that matched English words and SKU fragments inside
    product titles, attributing ~62% of parts to false-positive generations.

    Rules (mirrors the audit prescription):
        * Pure-digit single chars (``"7"``, ``"8"``) — ALWAYS too short.
        * Pure-digit components shorter than 3 chars — too short.
        * Pure-alphabetic components shorter than 4 chars — too short
          (catches ``"R"``, ``"T"``, ``"BE"``, ``"BH"`` etc.).

    Mixed alphanumeric components (e.g. ``"V1"``, ``"NA1"``, ``"TB1"``,
    ``"NA2"``, ``"E36"``) are NOT filtered here — those are handled by adding
    to ``AMBIGUOUS_STANDALONE_CODES`` if they cause real-world FPs.
    """
    if not component:
        return True
    if component.isdigit() and len(component) < 3:
        return True
    if component.isalpha() and len(component) < 4:
        return True
    return False


def _build_phrase_triples() -> list[tuple[str, str, str, str]]:
    """
    Build (phrase, make, model, generation_name) from canonical data.
    Phrase is normalized (lowercase, single spaces) for matching.
    Skips standalone generation codes that are highly ambiguous (e.g. GR, Mk5, B5).

    Two-layer filter for individual slash-split components:
        1. ``AMBIGUOUS_STANDALONE_CODES`` — explicit deny-list keyed by exact
           component / gen_name string.
        2. ``_is_too_short_to_dispatch`` — generic length-based filter that
           drops pure-alpha < 4 chars and pure-digit < 3 chars (Tier-1 audit
           false-positive guard).
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
                # Generation only for short codes - skip ambiguous ones to avoid false positives.
                # Slash-gen names (e.g. "F30/F31/F34", "E36/7", "BL/BP") are split into each
                # individual chassis code so they can match as standalone phrases too.
                if gen_name in AMBIGUOUS_STANDALONE_CODES:
                    continue
                components = [c.strip() for c in gen_name.split("/") if c.strip()]
                for component in components:
                    if len(component) > 6:
                        continue
                    if component in AMBIGUOUS_STANDALONE_CODES:
                        continue
                    if _is_too_short_to_dispatch(component):
                        continue
                    triples.append((component.lower(), make, model, gen_name))
    return triples


# Built once at import; sort by phrase length descending so longer matches win.
PHRASE_TRIPLES: list[tuple[str, str, str, str]] = sorted(_build_phrase_triples(), key=lambda x: -len(x[0]))


# Make+model phrase index for extract_fitment_candidates (issue #2). This is a
# narrower index than PHRASE_TRIPLES — it pairs (make, model) without baking in
# a generation, so the helper can return year-range candidates that the resolver
# narrows to the correct gen via generations_for_make_model_year_range.
def _build_make_model_phrases() -> tuple[
    list[tuple[str, str, str]],  # phrases requiring make context: "ford mustang"
    list[tuple[str, str, str]],  # bare-model phrases: "mustang"
]:
    """Build (phrase, make, model) entries.

    Two output lists:
      - ``with_make``: ``"<make> <model>"`` phrases — always safe to match.
      - ``model_only``: ``"<model>"`` phrases — only safe when the caller
        passes ``trusted_makes`` constraining the universe of possible makes.

    Both lists are sorted longest-first so a longer match like
    ``"ram 2500"`` wins over ``"ram"``.
    """
    with_make: list[tuple[str, str, str]] = []
    model_only: list[tuple[str, str, str]] = []
    for make, models in CAR_GENERATIONS.items():
        make_lower = make.lower()
        for model_data in models:
            model = model_data["model"]
            model_lower = model.lower()
            with_make.append((f"{make_lower} {model_lower}", make, model))
            model_only.append((model_lower, make, model))
    with_make.sort(key=lambda x: -len(x[0]))
    model_only.sort(key=lambda x: -len(x[0]))
    return with_make, model_only


_FITMENT_PHRASES_WITH_MAKE, _FITMENT_PHRASES_MODEL_ONLY = _build_make_model_phrases()


# Aliases: phrase -> (make, model, generation_name). Used when product text uses
# nicknames (MKV Supra, GR Supra, G82, etc.). Order: longer phrases first for specificity.
#
# Trim-vs-model decision rule (so adapters don't all reinvent it):
#   - A trim gets its own model row in car_generations_data.json ONLY when it has
#     a genuinely distinct production window from the base model AND retailers
#     consistently treat it as a separate fitment token. Examples that DO get
#     their own model row: Forester XT, Outback XT, GR86, GR Corolla.
#   - Otherwise, the trim is mapped here as alias(es) pointing at the base
#     model's generation(s). Examples: WRX STI -> WRX, GT500 -> Mustang,
#     Boss 302 -> Mustang, SVT Cobra -> Mustang, GT350 -> Mustang.
#   - When a trim spans multiple generations (WRX STI: GD/GR/VA, GT500:
#     5th Gen/6th Gen), emit one alias entry per generation. Adapter hooks layer
#     year-range narrowing on top via narrow_triples_by_year_range.
#   - Single-token chassis-style trim names (just "STI", just "GT500") are
#     intentionally NOT added unless the token is unambiguous in context — see
#     AMBIGUOUS_STANDALONE_CODES and the "STI alone is too short/ambiguous"
#     note on the Subaru block below.
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
    # Toyota GR86 / Subaru BRZ (product text: "Toyota GR86 - BRZ/GR86", "BRZ/GR86").
    # "brz/gr86" fires both gen pairs: 1st gen ZC6+ZN6 (2013-2020) AND 2nd gen ZD8+ZN8 (2022+).
    ("brz/gr86", "Subaru", "BRZ", "ZC6"),
    ("brz/gr86", "Toyota", "86", "ZN6"),
    ("brz/gr86", "Subaru", "BRZ", "ZD8"),
    ("brz/gr86", "Toyota", "GR86", "ZN8"),
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
    ("charger lb", "Dodge", "Charger", "LB"),
    ("dodge charger lb", "Dodge", "Charger", "LB"),
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
    # BMW M240i F22/F23 (2016-2021) + G42 (2022+) — "m240i" alone covers both gens so
    # every F22 M240i product doesn't get mis-tagged as G42-only (fixes ~7 parts in c2).
    ("bmw m240i", "BMW", "M240i", "F22/F23"),
    ("bmw m240i", "BMW", "M240i", "G42"),
    ("m240i", "BMW", "M240i", "F22/F23"),
    ("m240i", "BMW", "M240i", "G42"),
    ("m240 i", "BMW", "M240i", "F22/F23"),
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
    # NOTE: "330i E36" was previously aliased to BMW 330i E36 — but BMW
    # didn't make a 330i in the E36 era (the E36 6-cyl options were 320i /
    # 325i / 328i; the 330i nameplate started with E46 in 2001). Alias
    # removed to fix drift; if a real "E36 330i" title appears it likely
    # refers to a swap or a typo and falls through to the universal pipeline.
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
    # BMW 3 Series F30/F31/F34 slash-gen phrase fills (A1 split now covers the base,
    # but retailer text uses "BMW F30", "F30/F31", "F34 GT" etc. explicitly).
    ("f30 3 series", "BMW", "3 Series", "F30/F31/F34"),
    ("f30 3-series", "BMW", "3 Series", "F30/F31/F34"),
    ("f31 3 series", "BMW", "3 Series", "F30/F31/F34"),
    ("f30/f31", "BMW", "3 Series", "F30/F31/F34"),
    ("f30 / f31", "BMW", "3 Series", "F30/F31/F34"),
    ("bmw f30", "BMW", "3 Series", "F30/F31/F34"),
    ("f34 3 series gt", "BMW", "3 Series", "F30/F31/F34"),
    ("f34 gt", "BMW", "3 Series", "F30/F31/F34"),
    # BMW 4 Series F32/F33/F36
    ("f32 4 series", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 4-series", "BMW", "4 Series", "F32/F33/F36"),
    ("f33 4 series", "BMW", "4 Series", "F32/F33/F36"),
    ("f36 4 series", "BMW", "4 Series", "F32/F33/F36"),
    ("f32/f33", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 / f33", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 / f36", "BMW", "4 Series", "F32/F33/F36"),
    ("f32/f36", "BMW", "4 Series", "F32/F33/F36"),
    ("f32 f33 f36", "BMW", "4 Series", "F32/F33/F36"),
    # BMW 2 Series F22/F23
    ("f22 2 series", "BMW", "2 Series", "F22/F23"),
    ("f22 2-series", "BMW", "2 Series", "F22/F23"),
    ("f23 2 series", "BMW", "2 Series", "F22/F23"),
    ("f22/f23", "BMW", "2 Series", "F22/F23"),
    ("f22 / f23", "BMW", "2 Series", "F22/F23"),
    ("f22 228i", "BMW", "2 Series", "F22/F23"),
    ("f22 m235i", "BMW", "M240i", "F22/F23"),
    ("f22 m240i", "BMW", "M240i", "F22/F23"),
    # BMW 1 Series F20/F21
    ("f20 1 series", "BMW", "1 Series", "F20/F21"),
    ("f20 1-series", "BMW", "1 Series", "F20/F21"),
    ("f20/f21", "BMW", "1 Series", "F20/F21"),
    ("f20 / f21", "BMW", "1 Series", "F20/F21"),
    ("bmw f20", "BMW", "1 Series", "F20/F21"),
    # BMW M6 F12/F13/F06 (extra slash-gen forms beyond the existing "m6 f12" aliases)
    ("f06 6 series", "BMW", "M6", "F12/F13/F06"),
    ("f06 m6", "BMW", "M6", "F12/F13/F06"),
    ("m6 f06", "BMW", "M6", "F12/F13/F06"),
    ("f06/f12/f13", "BMW", "M6", "F12/F13/F06"),
    ("f06 / f12 / f13", "BMW", "M6", "F12/F13/F06"),
    ("f06 / f12", "BMW", "M6", "F12/F13/F06"),
    ("f06 / f13", "BMW", "M6", "F12/F13/F06"),
    # BMW 6 Series F12/F13 (non-M) — seed gen added in C3
    ("f12 6 series", "BMW", "6 Series", "F12/F13/F06"),
    ("f13 6 series", "BMW", "6 Series", "F12/F13/F06"),
    ("f12 / f13", "BMW", "6 Series", "F12/F13/F06"),
    ("f12 640i", "BMW", "6 Series", "F12/F13/F06"),
    # BMW Z4 E85/E86 base (non-M) — "e85 z4" existing entry is for "z4 m"; this is base.
    ("e85 / e86", "BMW", "Z4", "E85/E86"),
    ("e85/e86", "BMW", "Z4", "E85/E86"),
    ("e85 z4", "BMW", "Z4", "E85/E86"),
    ("e86 z4", "BMW", "Z4", "E85/E86"),
    ("bmw z4 e85", "BMW", "Z4", "E85/E86"),
    ("z4 (n52)", "BMW", "Z4", "E85/E86"),
    # BMW 1 Series E81/E82/E87/E88 — E82/E88 are the coupe/convertible (non-1M); common fitment text.
    ("e87 1 series", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e87 1-series", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("bmw e87", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e88 128i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e88 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 128i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 e88 128i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82 e88 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82/e88 135i", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82/e88 1 series", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("e82/e88", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("bmw 1 series e82", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("1 series (e82)", "BMW", "1 Series", "E81/E82/E87/E88"),
    ("1 series (e88)", "BMW", "1 Series", "E81/E82/E87/E88"),
    # BMW 3 Series E90/E91/E92/E93 slash-gen fills + trim variants
    ("e90/e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e90 / e91", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e91 3 series touring", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 328i", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 335i", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 cabrio", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e90/e92/e93 335i", "BMW", "335i", "E90/E91/E92/E93"),
    ("e92 facelift", "BMW", "3 Series", "E90/E91/E92/E93"),
    ("e93 facelift", "BMW", "3 Series", "E90/E91/E92/E93"),
    # BMW 3 Series E36 / E46 trim variants (bare i-less forms, body styles, tool-kit span)
    ("e36 325", "BMW", "3 Series", "E36"),
    ("e36 325i", "BMW", "3 Series", "E36"),
    ("e36 328", "BMW", "3 Series", "E36"),
    ("e36 328i", "BMW", "3 Series", "E36"),
    ("e36 318", "BMW", "3 Series", "E36"),
    ("e36 318i", "BMW", "3 Series", "E36"),
    ("e36 323", "BMW", "3 Series", "E36"),
    ("e36 323i", "BMW", "3 Series", "E36"),
    ("e36 4 door", "BMW", "3 Series", "E36"),
    ("e36 cabrio", "BMW", "3 Series", "E36"),
    ("e46 323", "BMW", "3 Series", "E46"),
    ("e46 323i", "BMW", "3 Series", "E46"),
    ("e46 325i", "BMW", "3 Series", "E46"),
    ("e46 325xi", "BMW", "3 Series", "E46"),
    ("e46 328", "BMW", "3 Series", "E46"),
    ("e46 328i", "BMW", "3 Series", "E46"),
    ("e46 330ci", "BMW", "330i", "E46"),
    ("e46 330xi", "BMW", "330i", "E46"),
    ("e46 cabrio", "BMW", "3 Series", "E46"),
    ("e46 convertible", "BMW", "3 Series", "E46"),
    ("e46 ci", "BMW", "3 Series", "E46"),
    ("e46 3-series", "BMW", "3 Series", "E46"),
    ("e46 coupe", "BMW", "3 Series", "E46"),
    ("e46 touring", "BMW", "3 Series", "E46"),
    ("e46 (not m3)", "BMW", "3 Series", "E46"),
    ("e36/e46", "BMW", "3 Series", "E36"),
    ("e36/e46", "BMW", "3 Series", "E46"),
    # BMW X5 E53/E70/F15/G05 — X-series non-M seeds added in C3
    ("e70 x5", "BMW", "X5", "E70"),
    ("e70 x5 35d", "BMW", "X5", "E70"),
    ("e70 35d", "BMW", "X5", "E70"),
    ("bmw e70 x5", "BMW", "X5", "E70"),
    ("e53 x5", "BMW", "X5", "E53"),
    ("bmw e53", "BMW", "X5", "E53"),
    ("f15 x5", "BMW", "X5", "F15"),  # blocks Juke F15
    ("bmw f15", "BMW", "X5", "F15"),
    ("g05 x5", "BMW", "X5", "G05"),
    ("bmw g05", "BMW", "X5", "G05"),
    # BMW X3 E83/F25/G01
    ("e83 x3", "BMW", "X3", "E83"),
    ("bmw e83", "BMW", "X3", "E83"),
    ("f25 x3", "BMW", "X3", "F25"),
    ("bmw f25", "BMW", "X3", "F25"),
    ("g01 x3", "BMW", "X3", "G01"),
    ("bmw g01", "BMW", "X3", "G01"),
    # BMW X4 F26/G02
    ("f26 x4", "BMW", "X4", "F26"),
    ("bmw f26", "BMW", "X4", "F26"),
    ("g02 x4", "BMW", "X4", "G02"),
    ("bmw g02", "BMW", "X4", "G02"),
    # BMW X6 F16/G06 — F16 blocks Juke F16
    ("f16 x6", "BMW", "X6", "F16"),
    ("bmw f16", "BMW", "X6", "F16"),
    ("g06 x6", "BMW", "X6", "G06"),
    ("f15 x5 / f16 x6", "BMW", "X5", "F15"),
    ("f15 x5 / f16 x6", "BMW", "X6", "F16"),
    # BMW X7 G07
    ("g07 x7", "BMW", "X7", "G07"),
    ("bmw g07", "BMW", "X7", "G07"),
    # BMW X1 E84/F48/U11
    ("e84 x1", "BMW", "X1", "E84"),
    ("bmw e84", "BMW", "X1", "E84"),
    ("f48 x1", "BMW", "X1", "F48"),
    ("bmw f48", "BMW", "X1", "F48"),
    ("u11 x1", "BMW", "X1", "U11"),
    # BMW X2 F39
    ("f39 x2", "BMW", "X2", "F39"),
    ("bmw f39", "BMW", "X2", "F39"),
    # BMW 2 Series Gran Coupe F44
    ("f44 2 series gran coupe", "BMW", "2 Series Gran Coupe", "F44"),
    ("f44 gran coupe", "BMW", "2 Series Gran Coupe", "F44"),
    ("f44 m235i", "BMW", "2 Series Gran Coupe", "F44"),
    # BMW 7 Series — full gen lineup
    ("g11 7 series", "BMW", "7 Series", "G11/G12"),
    ("g12 7 series", "BMW", "7 Series", "G11/G12"),
    ("g11/g12", "BMW", "7 Series", "G11/G12"),
    ("g11 / g12", "BMW", "7 Series", "G11/G12"),
    ("bmw g11", "BMW", "7 Series", "G11/G12"),
    ("bmw g12", "BMW", "7 Series", "G11/G12"),
    ("e38 7 series", "BMW", "7 Series", "E38"),
    ("e38 740i", "BMW", "7 Series", "E38"),
    ("e38 740il", "BMW", "7 Series", "E38"),
    ("e38 750il", "BMW", "7 Series", "E38"),
    ("bmw e38", "BMW", "7 Series", "E38"),
    ("e32 7 series", "BMW", "7 Series", "E32"),
    ("e32 750il", "BMW", "7 Series", "E32"),
    ("e32 735i", "BMW", "7 Series", "E32"),
    ("bmw e32", "BMW", "7 Series", "E32"),
    ("e23 7 series", "BMW", "7 Series", "E23"),
    ("e23 733i", "BMW", "7 Series", "E23"),
    ("e23 735i", "BMW", "7 Series", "E23"),
    ("bmw e23", "BMW", "7 Series", "E23"),
    ("e65/e66", "BMW", "7 Series", "E65/E66"),
    ("e65 / e66", "BMW", "7 Series", "E65/E66"),
    ("e65 745i", "BMW", "7 Series", "E65/E66"),
    ("e65 745li", "BMW", "7 Series", "E65/E66"),
    ("bmw e65", "BMW", "7 Series", "E65/E66"),
    # BMW 8 Series E31 / G14/G15/G16
    ("e31 8 series", "BMW", "8 Series", "E31"),
    ("e31 840", "BMW", "8 Series", "E31"),
    ("e31 840ci", "BMW", "8 Series", "E31"),
    ("e31 850", "BMW", "8 Series", "E31"),
    ("e31 850i", "BMW", "8 Series", "E31"),
    ("e31 850ci", "BMW", "8 Series", "E31"),
    ("bmw e31", "BMW", "8 Series", "E31"),
    ("g15 8 series", "BMW", "8 Series", "G14/G15/G16"),
    ("g15 840i", "BMW", "8 Series", "G14/G15/G16"),
    ("bmw g15", "BMW", "8 Series", "G14/G15/G16"),
    ("g14 8 series", "BMW", "8 Series", "G14/G15/G16"),
    ("g16 8 series", "BMW", "8 Series", "G14/G15/G16"),
    # BMW 5 Series G30/G31 + E28/E34 (new seed) + E39 trim variants
    ("g30 5 series", "BMW", "5 Series", "G30/G31"),
    ("g30 530i", "BMW", "5 Series", "G30/G31"),
    ("g30 540i", "BMW", "5 Series", "G30/G31"),
    ("e28 528e", "BMW", "5 Series", "E28"),
    ("e28 533i", "BMW", "5 Series", "E28"),
    ("e28 535i", "BMW", "5 Series", "E28"),
    ("bmw e28", "BMW", "5 Series", "E28"),
    ("e34 525i", "BMW", "5 Series", "E34"),
    ("e34 530i", "BMW", "5 Series", "E34"),
    ("e34 535i", "BMW", "5 Series", "E34"),
    ("e34 540i", "BMW", "5 Series", "E34"),
    ("e34 touring", "BMW", "5 Series", "E34"),
    ("bmw e34", "BMW", "5 Series", "E34"),
    ("e39 525i", "BMW", "5 Series", "E39"),
    ("e39 528i", "BMW", "5 Series", "E39"),
    ("e39 530i", "BMW", "5 Series", "E39"),
    ("e39 535i", "BMW", "5 Series", "E39"),
    ("e39 540i", "BMW", "5 Series", "E39"),
    ("e39 545i", "BMW", "5 Series", "E39"),
    ("e39 touring", "BMW", "5 Series", "E39"),
    # BMW 6 Series GT G32 (new seed) + E24/E63/E64/F12 (non-M gens)
    ("g32 6 series gt", "BMW", "6 Series GT", "G32"),
    ("g32 640i", "BMW", "6 Series GT", "G32"),
    ("e24 635csi", "BMW", "6 Series", "E24"),
    ("e63 6 series", "BMW", "6 Series", "E63/E64"),
    ("e63 6-series", "BMW", "6 Series", "E63/E64"),
    ("e63 645i", "BMW", "6 Series", "E63/E64"),
    ("e63 650i", "BMW", "6 Series", "E63/E64"),
    ("e64 645ci", "BMW", "6 Series", "E63/E64"),
    ("bmw e63", "BMW", "6 Series", "E63/E64"),
    ("bmw e64", "BMW", "6 Series", "E63/E64"),
    # BMW i3 I01 (electric)
    ("i01 i3", "BMW", "i3", "I01"),
    ("bmw i3", "BMW", "i3", "I01"),
    # BMW M340i / M440i short forms + xDrive variants
    ("m340", "BMW", "M340i", "G20/G21"),
    ("m440", "BMW", "M440i", "G22/G23/G26"),
    ("m240ix", "BMW", "M240i", "G42"),
    ("m340ix", "BMW", "M340i", "G20/G21"),
    # BMW generic chassis shorthand ("f-chassis", "g chassis") — high-risk but common in adapter copy
    ("f-chassis", "BMW", "3 Series", "F30/F31/F34"),
    ("f chassis", "BMW", "3 Series", "F30/F31/F34"),
    ("g chassis", "BMW", "3 Series", "G20/G21"),
    ("g-chassis", "BMW", "3 Series", "G20/G21"),
    # BMW Z3 E36/7 E36/8 (new seed)
    ("bmw z3 e36/7", "BMW", "Z3", "E36/7 E36/8"),
    ("bmw z3 (e36/7)", "BMW", "Z3", "E36/7 E36/8"),
    ("bmw z3", "BMW", "Z3", "E36/7 E36/8"),
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
    # Porsche 918 Spyder + Carrera GT — bare/common forms (gen names same as model)
    ("porsche 918", "Porsche", "918 Spyder", "918 Spyder"),
    ("918 spyder", "Porsche", "918 Spyder", "918 Spyder"),
    ("porsche 918 spyder", "Porsche", "918 Spyder", "918 Spyder"),
    ("carrera gt", "Porsche", "Carrera GT", "Carrera GT"),
    ("porsche carrera gt", "Porsche", "Carrera GT", "Carrera GT"),
    ("cgt", "Porsche", "Carrera GT", "Carrera GT"),
    # Porsche Cayenne sub-chassis codes (955/957 = 9PA 1st gen; 958 = 92A 2nd gen; 9Y0 = PO536 3rd)
    ("cayenne 955", "Porsche", "Cayenne", "9PA"),
    ("cayenne 957", "Porsche", "Cayenne", "9PA"),
    ("955 cayenne", "Porsche", "Cayenne", "9PA"),
    ("957 cayenne", "Porsche", "Cayenne", "9PA"),
    ("cayenne 958", "Porsche", "Cayenne", "92A"),
    ("958 cayenne", "Porsche", "Cayenne", "92A"),
    ("cayenne 9pa", "Porsche", "Cayenne", "9PA"),
    ("porsche 9pa", "Porsche", "Cayenne", "9PA"),
    ("porsche 92a", "Porsche", "Cayenne", "92A"),
    ("cayenne 9y0", "Porsche", "Cayenne", "PO536"),
    ("9y0 cayenne", "Porsche", "Cayenne", "PO536"),
    ("cayenne 2019+", "Porsche", "Cayenne", "PO536"),
    ("porsche cayenne", "Porsche", "Cayenne", "9PA"),
    ("porsche cayenne", "Porsche", "Cayenne", "92A"),
    ("2003-2008 cayenne", "Porsche", "Cayenne", "9PA"),
    # Porsche 911 Turbo glued / 987S short forms
    ("996tt", "Porsche", "911", "996"),
    ("997tt", "Porsche", "911", "997"),
    ("996 turbo", "Porsche", "911", "996"),
    ("997 turbo", "Porsche", "911", "997"),
    ("987s", "Porsche", "Cayman", "987"),
    ("987s", "Porsche", "Boxster", "987"),
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
    # Subaru BRZ — plain "subaru brz" fires BOTH gens (ZC6 2013-2020 + ZD8 2022+).
    # Otherwise every pre-2022 BRZ product gets mis-tagged as ZD8-only (~70 parts fixed).
    ("subaru brz", "Subaru", "BRZ", "ZC6"),
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
    # GT500 spans 2007-2014 (5th Gen / S197) and 2020-2022 (6th Gen / S550).
    # Map both so year-narrowing in adapter hooks resolves to the correct gen;
    # without an explicit year a GT500 part is genuinely ambiguous between the two.
    ("gt500", "Ford", "Mustang", "5th Gen"),
    ("gt500", "Ford", "Mustang", "6th Gen"),
    ("shelby gt500", "Ford", "Mustang", "5th Gen"),
    ("shelby gt500", "Ford", "Mustang", "6th Gen"),
    # Ford Mustang trim names — "dark horse" (S650), GT350 (S550 only), Boss 302 (5th Gen), Bullitt, Mach 1
    ("dark horse", "Ford", "Mustang", "7th Gen"),
    ("boss 302 mustang", "Ford", "Mustang", "5th Gen"),
    ("mustang boss 302", "Ford", "Mustang", "5th Gen"),
    ("bullitt mustang", "Ford", "Mustang", "5th Gen"),
    ("mustang bullitt", "Ford", "Mustang", "5th Gen"),
    ("mach 1 mustang", "Ford", "Mustang", "5th Gen"),
    ("mustang mach 1", "Ford", "Mustang", "5th Gen"),
    ("svt cobra", "Ford", "Mustang", "4th Gen"),
    ("mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("terminator cobra", "Ford", "Mustang", "4th Gen"),
    ("gt350 mustang", "Ford", "Mustang", "6th Gen"),
    ("shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("mustang gt350", "Ford", "Mustang", "6th Gen"),
    ("shelby gt350r", "Ford", "Mustang", "6th Gen"),
    ("gt350r", "Ford", "Mustang", "6th Gen"),
    # Ford Focus SVT (2002-2004, Mk1 only)
    ("focus svt", "Ford", "Focus", "Mk1"),
    ("svt focus", "Ford", "Focus", "Mk1"),
    # Ford Mustang decade-spanning year-range fitment patterns
    ("1979-2004 mustang", "Ford", "Mustang", "3rd Gen"),
    ("1979-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1979-1993 mustang", "Ford", "Mustang", "3rd Gen"),
    ("1994-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1996-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1996-2004 ford mustang", "Ford", "Mustang", "4th Gen"),
    ("1999-2004 mustang", "Ford", "Mustang", "4th Gen"),
    ("1999-2004 ford mustang", "Ford", "Mustang", "4th Gen"),
    ("2001 ford mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("2003-2004 ford mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("2003-2004 mustang cobra", "Ford", "Mustang", "4th Gen"),
    ("2001-2004 ford cobra", "Ford", "Mustang", "4th Gen"),
    ("2002-2004 ford mustang gt", "Ford", "Mustang", "4th Gen"),
    ("2005-2010 mustang", "Ford", "Mustang", "5th Gen"),
    ("2005-2010 ford mustang", "Ford", "Mustang", "5th Gen"),
    ("2005-2014 mustang", "Ford", "Mustang", "5th Gen"),
    ("2010-2014 mustang", "Ford", "Mustang", "5th Gen"),
    ("2011-2014 mustang", "Ford", "Mustang", "5th Gen"),
    ("2011-2014 ford mustang", "Ford", "Mustang", "5th Gen"),
    ("2011-14 mustang", "Ford", "Mustang", "5th Gen"),
    ("2015-2017 mustang", "Ford", "Mustang", "6th Gen"),
    ("2015-2017 ford mustang", "Ford", "Mustang", "6th Gen"),
    ("2015-17 mustang", "Ford", "Mustang", "6th Gen"),
    ("2016+ ford mustang", "Ford", "Mustang", "6th Gen"),
    ("2018-2023 mustang", "Ford", "Mustang", "6th Gen"),
    ("2018+ ford mustang", "Ford", "Mustang", "6th Gen"),
    ("2018 ford mustang gt", "Ford", "Mustang", "6th Gen"),
    ("2015-2017 mustang gt", "Ford", "Mustang", "6th Gen"),
    ("2015-2017 mustang ecoboost", "Ford", "Mustang", "6th Gen"),
    ("2015+ mustang ecoboost", "Ford", "Mustang", "6th Gen"),
    ("2015+ ford mustang shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("2016+ ford mustang shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("mustang shelby gt350", "Ford", "Mustang", "6th Gen"),
    ("new edge mustang", "Ford", "Mustang", "4th Gen"),
    ("new edge", "Ford", "Mustang", "4th Gen"),
    ("s197.1 mustang", "Ford", "Mustang", "5th Gen"),
    ("s197.2 mustang", "Ford", "Mustang", "5th Gen"),
    ("s550.1 mustang", "Ford", "Mustang", "6th Gen"),
    ("s550.2 mustang", "Ford", "Mustang", "6th Gen"),
    # Ford SVT Lightning (F-150 10th Gen)
    ("1999-2004 ford svt lightning", "Ford", "F-150", "10th Gen"),
    ("ford svt lightning", "Ford", "F-150", "10th Gen"),
    # Ford Bronco / Ranger / Maverick / F-150 Raptor / Fiesta ST (needs seed additions in C8)
    ("ford bronco", "Ford", "Bronco", "6th Gen"),
    ("2021+ ford bronco", "Ford", "Bronco", "6th Gen"),
    ("2021-2025 ford bronco", "Ford", "Bronco", "6th Gen"),
    ("bronco raptor", "Ford", "Bronco", "6th Gen"),
    ("ford maverick", "Ford", "Maverick", "1st Gen"),
    ("bronco sport", "Ford", "Bronco Sport", "1st Gen"),
    ("ranger raptor", "Ford", "Ranger Raptor", "1st Gen"),
    ("ford ranger raptor", "Ford", "Ranger Raptor", "1st Gen"),
    ("2024 ford ranger raptor", "Ford", "Ranger Raptor", "1st Gen"),
    # Ford Ranger T6 (2019-2023) — "T6" now in AMBIGUOUS_STANDALONE_CODES due to "6061-T6" aluminum
    # spec collision; require explicit "ranger t6" / "ford ranger t6" context.
    ("ranger t6", "Ford", "Ranger", "T6"),
    ("ford ranger t6", "Ford", "Ranger", "T6"),
    ("ford ranger", "Ford", "Ranger", "T6"),
    ("ford f-150", "Ford", "F-150", "13th Gen"),
    ("ford f-150", "Ford", "F-150", "14th Gen"),
    ("f-150 ecoboost raptor", "Ford", "F-150 Raptor", "3rd Gen"),
    ("f-150 raptor", "Ford", "F-150 Raptor", "3rd Gen"),
    ("fiesta st", "Ford", "Fiesta ST", "Mk7"),
    ("ford fiesta st", "Ford", "Fiesta ST", "Mk7"),
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
    # Evo year-range multi-gen fitments + JDM CDxA/CExA/CNxA/CPxA/CTxA/CZxA chassis codes
    ("2008-2015 mitsubishi evo x", "Mitsubishi", "Lancer Evolution", "X"),
    ("2003-2006 mitsubishi evo 8/9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("2003-2006 mitsubishi evo 8/9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("2003-2015 mitsubishi evo 8/9/x", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("2003-2015 mitsubishi evo 8/9/x", "Mitsubishi", "Lancer Evolution", "IX"),
    ("2003-2015 mitsubishi evo 8/9/x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo 8 9 x", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 8 9 x", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 8 9 x", "Mitsubishi", "Lancer Evolution", "X"),
    ("lancer evolution vii", "Mitsubishi", "Lancer Evolution", "VII"),
    ("lancer evolution viii", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("lancer evolution ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("lancer evolution x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo viii/ix", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo viii/ix", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo ix/x", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo ix/x", "Mitsubishi", "Lancer Evolution", "X"),
    ("evo 8/9", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("evo 8/9", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 9/10", "Mitsubishi", "Lancer Evolution", "IX"),
    ("evo 9/10", "Mitsubishi", "Lancer Evolution", "X"),
    ("cd9a", "Mitsubishi", "Lancer Evolution", "I"),
    ("ce9a", "Mitsubishi", "Lancer Evolution", "II"),
    ("ce9a", "Mitsubishi", "Lancer Evolution", "III"),
    ("cn9a", "Mitsubishi", "Lancer Evolution", "IV"),
    ("cp9a", "Mitsubishi", "Lancer Evolution", "IV"),
    ("cp9a", "Mitsubishi", "Lancer Evolution", "V"),
    ("cp9a", "Mitsubishi", "Lancer Evolution", "VI"),
    ("cp9a/cn9a", "Mitsubishi", "Lancer Evolution", "IV"),
    ("cp9a/cn9a", "Mitsubishi", "Lancer Evolution", "V"),
    ("cp9a/cn9a", "Mitsubishi", "Lancer Evolution", "VI"),
    ("ct9a", "Mitsubishi", "Lancer Evolution", "VII"),
    ("ct9a", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("ct9a", "Mitsubishi", "Lancer Evolution", "IX"),
    ("cz4a", "Mitsubishi", "Lancer Evolution", "X"),
    ("4b11t", "Mitsubishi", "Lancer Evolution", "X"),
    ("4b11 evo", "Mitsubishi", "Lancer Evolution", "X"),
    ("cz4a 4b11", "Mitsubishi", "Lancer Evolution", "X"),
    ("4g63 evo", "Mitsubishi", "Lancer Evolution", "VII"),
    ("4g63 evo", "Mitsubishi", "Lancer Evolution", "VIII"),
    ("4g63 evo", "Mitsubishi", "Lancer Evolution", "IX"),
    # Mitsubishi 3000GT + Dodge Stealth platform twin
    ("mitsubishi 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("mitsubishi 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("mitsubishi 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("3000gt vr-4", "Mitsubishi", "3000GT", "1st Gen"),
    ("3000gt vr-4", "Mitsubishi", "3000GT", "2nd Gen"),
    ("3000gt vr-4", "Mitsubishi", "3000GT", "3rd Gen"),
    ("3000gt vr4", "Mitsubishi", "3000GT", "1st Gen"),
    ("z16a", "Mitsubishi", "3000GT", "1st Gen"),
    ("dodge stealth", "Mitsubishi", "3000GT", "1st Gen"),
    ("91-93 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("1991-1993 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("94-99 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("94-99 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("1994-1999 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("1994-1999 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    ("91-99 mitsubishi 3000gt", "Mitsubishi", "3000GT", "1st Gen"),
    ("91-99 mitsubishi 3000gt", "Mitsubishi", "3000GT", "2nd Gen"),
    ("91-99 mitsubishi 3000gt", "Mitsubishi", "3000GT", "3rd Gen"),
    # Mitsubishi Eclipse DSM / Eagle Talon + year-range multi-gen fitments
    ("2g dsm", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("dsm eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("dsm eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("dsm gsx", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1g dsm", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eclipse gsx", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eclipse gsx", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("eclipse gs-t", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eclipse gs-t", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("eagle talon", "Mitsubishi", "Eclipse", "1st Gen"),
    ("eagle talon", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1996-2000 mitsubishi eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1990-1994 mitsubishi eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1990-1994 eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1990-1994 eclipse / talon", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1990-1994 eclipse/talon", "Mitsubishi", "Eclipse", "1st Gen"),
    ("1995-1999 mitsubishi eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1995-1999 eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("1995-1999 eclipse / talon", "Mitsubishi", "Eclipse", "2nd Gen"),
    ("90-94 mitsubishi eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("89-94 mitsubishi eclipse", "Mitsubishi", "Eclipse", "1st Gen"),
    ("95-99 mitsubishi eclipse", "Mitsubishi", "Eclipse", "2nd Gen"),
    # Mitsubishi Eclipse Cross / Lancer CE (new seeds) + Galant VR-4 + Ralliart
    ("18-24 mitsubishi eclipse cross", "Mitsubishi", "Eclipse Cross", "1st Gen"),
    ("mitsubishi eclipse cross", "Mitsubishi", "Eclipse Cross", "1st Gen"),
    ("96-00 mitsubishi lancer", "Mitsubishi", "Lancer", "CE"),
    ("91-99 mitsubishi galant vr4", "Mitsubishi", "Galant VR-4", "1st Gen"),
    ("galant vr-4", "Mitsubishi", "Galant VR-4", "1st Gen"),
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
    # Nissan GT-R R35 + Skyline R32/R33/R34 (new seed) + JDM chassis codes + engine codes
    ("2009-2018 nissan gt-r", "Nissan", "GT-R", "R35"),
    ("2017-2019 nissan gt-r", "Nissan", "GT-R", "R35"),
    ("nissan gt-r", "Nissan", "GT-R", "R35"),
    ("gt-r r35", "Nissan", "GT-R", "R35"),
    ("r35 gt-r", "Nissan", "GT-R", "R35"),
    ("r35 gtr", "Nissan", "GT-R", "R35"),
    ("nissan gtr", "Nissan", "GT-R", "R35"),
    ("skyline r32", "Nissan", "Skyline", "R32"),
    ("skyline r33", "Nissan", "Skyline", "R33"),
    ("skyline r34", "Nissan", "Skyline", "R34"),
    ("nissan r32", "Nissan", "Skyline", "R32"),
    ("nissan r33", "Nissan", "Skyline", "R33"),
    ("nissan r34", "Nissan", "Skyline", "R34"),
    ("gt-r r32", "Nissan", "GT-R", "R32"),
    ("gt-r r33", "Nissan", "GT-R", "R33"),
    ("gt-r r34", "Nissan", "GT-R", "R34"),
    ("bnr32", "Nissan", "GT-R", "R32"),
    ("hcr32", "Nissan", "GT-R", "R32"),
    ("bcnr33", "Nissan", "GT-R", "R33"),
    ("ecr33", "Nissan", "GT-R", "R33"),
    ("bnr34", "Nissan", "GT-R", "R34"),
    ("er34", "Nissan", "GT-R", "R34"),
    ("bnr32/bcnr33/bnr34", "Nissan", "GT-R", "R32"),
    ("bnr32/bcnr33/bnr34", "Nissan", "GT-R", "R33"),
    ("bnr32/bcnr33/bnr34", "Nissan", "GT-R", "R34"),
    ("bcnr33/bnr34", "Nissan", "GT-R", "R33"),
    ("bcnr33/bnr34", "Nissan", "GT-R", "R34"),
    ("rb26", "Nissan", "GT-R", "R32"),
    ("rb26", "Nissan", "GT-R", "R33"),
    ("rb26", "Nissan", "GT-R", "R34"),
    ("rb26dett", "Nissan", "GT-R", "R32"),
    ("rb26dett", "Nissan", "GT-R", "R33"),
    ("rb26dett", "Nissan", "GT-R", "R34"),
    ("rb26/rb25/rb20", "Nissan", "GT-R", "R32"),
    ("rb26/rb25/rb20", "Nissan", "GT-R", "R33"),
    ("rb26/rb25/rb20", "Nissan", "GT-R", "R34"),
    ("vr38", "Nissan", "GT-R", "R35"),
    ("vr38dett", "Nissan", "GT-R", "R35"),
    # Nissan Altima U13 / Sentra B13/B14 seed + Datsun Z-cars
    ("93-97 nissan altima", "Nissan", "Altima", "U13"),
    ("91-94 nissan sentra", "Nissan", "Sentra", "B13"),
    ("95-99 nissan sentra", "Nissan", "Sentra", "B14"),
    ("69-74 datsun 240z", "Datsun", "240Z", "S30"),
    ("74-78 datsun 260z", "Datsun", "260Z", "S30"),
    ("75-78 datsun 280z", "Datsun", "280Z", "S30"),
    # Chevrolet Camaro year-range patterns
    ("2010-2015 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2010-2015 chevrolet camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2010+ camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro ss 2010", "Chevrolet", "Camaro", "5th Gen"),
    ("2010-14 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2016+ camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("2016-2024 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("2016-2022 camaro", "Chevrolet", "Camaro", "6th Gen"),
    # Chevrolet Camaro G5/G6 Katech shorthand + ZL1/Z28/1LE trim patterns
    ("g5 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("g6 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro g5", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro g6", "Chevrolet", "Camaro", "6th Gen"),
    ("g5 camaro zl1", "Chevrolet", "Camaro", "5th Gen"),
    ("g6 camaro zl1", "Chevrolet", "Camaro", "6th Gen"),
    ("g5 camaro z28", "Chevrolet", "Camaro", "5th Gen"),
    ("camaro zl1", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro 1le", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro z/28", "Chevrolet", "Camaro", "5th Gen"),
    ("z/28 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("10-15 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("10-15 camaro ss", "Chevrolet", "Camaro", "5th Gen"),
    ("16-24 camaro", "Chevrolet", "Camaro", "6th Gen"),
    ("82-02 camaro", "Chevrolet", "Camaro", "3rd Gen"),
    ("82-02 camaro", "Chevrolet", "Camaro", "4th Gen"),
    ("82-92 fbody", "Chevrolet", "Camaro", "3rd Gen"),
    ("2012-2015 camaro", "Chevrolet", "Camaro", "5th Gen"),
    ("2012-2015 camaro zl1", "Chevrolet", "Camaro", "5th Gen"),
    ("2017+ camaro zl1", "Chevrolet", "Camaro", "6th Gen"),
    ("camaro zl1 1le", "Chevrolet", "Camaro", "6th Gen"),
    ("1993-2001 camaro", "Chevrolet", "Camaro", "4th Gen"),
    ("1993-2001 chevrolet camaro", "Chevrolet", "Camaro", "4th Gen"),
    ("chevrolet camaro 1993-2001", "Chevrolet", "Camaro", "4th Gen"),
    # Chevrolet Corvette C5/C6/C7/C8 variants + year-ranges
    ("c8 z06", "Chevrolet", "Corvette", "C8"),
    ("c8 corvette z06", "Chevrolet", "Corvette", "C8"),
    ("c8 e-ray", "Chevrolet", "Corvette", "C8"),
    ("c8 zr1", "Chevrolet", "Corvette", "C8"),
    ("97-04 corvette", "Chevrolet", "Corvette", "C5"),
    ("chevrolet corvette 2001-2004", "Chevrolet", "Corvette", "C5"),
    ("chevrolet corvette 2005-2008", "Chevrolet", "Corvette", "C6"),
    ("chevrolet corvette 2014+", "Chevrolet", "Corvette", "C7"),
    ("2001-2004 corvette c5", "Chevrolet", "Corvette", "C5"),
    ("2005-2008 corvette c6", "Chevrolet", "Corvette", "C6"),
    ("2014+ corvette c7", "Chevrolet", "Corvette", "C7"),
    ("2014+ chevrolet corvette", "Chevrolet", "Corvette", "C7"),
    # Chevrolet SS (VF Commodore-based)
    ("chevy ss", "Chevrolet", "SS", "VF Series"),
    ("chevrolet ss sedan", "Chevrolet", "SS", "VF Series"),
    # Chevrolet/GMC full-size pickups + SUVs — need seed (C5/C6)
    ("silverado 1500", "Chevrolet", "Silverado", "K2"),
    ("silverado ss", "Chevrolet", "Silverado", "GMT800"),
    ("tahoe", "Chevrolet", "Tahoe", "GMT900"),
    ("suburban", "Chevrolet", "Suburban", "GMT800"),
    ("sierra 1500", "GMC", "Sierra", "K2"),
    ("yukon denali", "GMC", "Yukon", "K2"),
    # Cadillac CTS-V, CT5-V Blackwing, CT4-V Blackwing, Escalade — needs seed (C4)
    ("escalade", "Cadillac", "Escalade", "K2"),
    ("cadillac cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("cts-v gen 2", "Cadillac", "CTS-V", "2nd Gen"),
    ("cts-v gen 3", "Cadillac", "CTS-V", "3rd Gen"),
    ("09-15 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("09-14 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("2009-14 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("2009-2015 cts-v", "Cadillac", "CTS-V", "2nd Gen"),
    ("2016-2019 cadillac cts-v", "Cadillac", "CTS-V", "3rd Gen"),
    ("ct5-v blackwing", "Cadillac", "CT5-V Blackwing", "1st Gen"),
    ("ct4-v blackwing", "Cadillac", "CT4-V Blackwing", "1st Gen"),
    # Holden Commodore VE
    ("holden commodore ve", "Holden", "Commodore", "VE"),
    # Pontiac G8 (VE Commodore-based, 2008-2009; Pontiac brand discontinued 2010)
    ("pontiac g8", "Pontiac", "G8", "VE"),
    ("g8 gt", "Pontiac", "G8", "VE"),
    ("g8 gxp", "Pontiac", "G8", "VE"),
    # Pontiac GTO (Holden Monaro generation)
    ("pontiac gto", "Pontiac", "GTO", "Holden"),
    ("04-06 gto", "Pontiac", "GTO", "Holden"),
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
    ("tlx type s", "Acura", "TLX", "2nd Gen"),  # no-hyphen variant
    ("acura tlx type-s", "Acura", "TLX", "2nd Gen"),
    ("2021+ acura tlx", "Acura", "TLX", "2nd Gen"),
    ("2021-25 acura tlx type s", "Acura", "TLX", "2nd Gen"),
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
    # Audi combined A4/S4/RS4 B5 fitments (034 common product-title format)
    ("b5 audi a4/s4/rs4", "Audi", "A4", "B5"),
    ("b5 audi a4/s4/rs4", "Audi", "S4", "B5"),
    ("b5 audi a4/s4/rs4", "Audi", "RS4", "B5"),
    ("b5 a4/s4/rs4", "Audi", "A4", "B5"),
    ("b5 a4/s4/rs4", "Audi", "S4", "B5"),
    ("b5 a4/s4/rs4", "Audi", "RS4", "B5"),
    ("b4/b5 audi a4/s4/rs4", "Audi", "A4", "B5"),
    ("b4/b5 audi a4/s4/rs4", "Audi", "S4", "B5"),
    ("b4/b5 audi a4/s4/rs4", "Audi", "RS4", "B5"),
    # Audi C5 A6/S6/allroad bridging fitments ("B5 S4 & C5 A6" is a 034 pattern)
    ("c5 a6/allroad", "Audi", "S6", "C5"),
    ("b5 s4 & c5 a6", "Audi", "S4", "B5"),
    ("b5 s4 & c5 a6", "Audi", "S6", "C5"),
    # Audi RS3 8V explicit (blocks 8L Audi A3 displacement misfires)
    ("2015-2021 audi rs3", "Audi", "RS3", "8V"),
    ("audi rs3 8v", "Audi", "RS3", "8V"),
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
    # Mazda Miata engine-displacement aliases (BP/B6 engine codes now in AMBIGUOUS, so require miata context)
    ("1.8 miata", "Mazda", "Miata", "NA"),
    ("1.8 miata", "Mazda", "Miata", "NB"),
    ("1.6 miata", "Mazda", "Miata", "NA"),
    ("miata 1.8", "Mazda", "Miata", "NA"),
    ("miata 1.8", "Mazda", "Miata", "NB"),
    ("miata 1.6", "Mazda", "Miata", "NA"),
    ("1.8 bp engine", "Mazda", "Miata", "NB"),
    ("bp engine miata", "Mazda", "Miata", "NB"),
    ("b6 miata engine", "Mazda", "Miata", "NA"),
    ("1.6 b6 engine", "Mazda", "Miata", "NA"),
    ("mazda bp engine", "Mazda", "Miata", "NB"),
    ("1990-97 miata", "Mazda", "Miata", "NA"),
    ("1994-00 miata", "Mazda", "Miata", "NA"),
    ("1994-00 miata", "Mazda", "Miata", "NB"),
    ("2001-05 miata", "Mazda", "Miata", "NB"),
    ("nb2 miata", "Mazda", "Miata", "NB"),
    ("miata nb2", "Mazda", "Miata", "NB"),
    ("nb1 miata", "Mazda", "Miata", "NB"),
    ("miata nb1", "Mazda", "Miata", "NB"),
    ("1989-2005 mazda miata", "Mazda", "Miata", "NA"),
    ("1989-2005 mazda miata", "Mazda", "Miata", "NB"),
    ("1989-2005 miata", "Mazda", "Miata", "NA"),
    ("1989-2005 miata", "Mazda", "Miata", "NB"),
    ("1994-2005 1.8 mx-5 miata", "Mazda", "Miata", "NA"),
    ("1994-2005 1.8 mx-5 miata", "Mazda", "Miata", "NB"),
    # Mazda RX-7 JDM chassis codes + bare model forms
    ("fd3s", "Mazda", "RX-7", "FD"),
    ("rx-7 fd3s", "Mazda", "RX-7", "FD"),
    ("rx7 fd3s", "Mazda", "RX-7", "FD"),
    ("mazda rx-7 fd3s", "Mazda", "RX-7", "FD"),
    ("fd3c", "Mazda", "RX-7", "FD"),
    ("fc3s", "Mazda", "RX-7", "FC"),
    ("rx-7 fc3s", "Mazda", "RX-7", "FC"),
    ("mazda rx-7", "Mazda", "RX-7", "FC"),
    ("mazda rx-7", "Mazda", "RX-7", "FD"),
    ("mazda rx7", "Mazda", "RX-7", "FC"),
    ("mazda rx7", "Mazda", "RX-7", "FD"),
    ("93+ mazda rx-7", "Mazda", "RX-7", "FD"),
    # Mazda RX-8 bare forms
    ("mazda rx-8", "Mazda", "RX-8", "SE3P"),
    ("rx-8", "Mazda", "RX-8", "SE3P"),
    ("rx8", "Mazda", "RX-8", "SE3P"),
    # Mazdaspeed 3 / Mazdaspeed Protegé / Mazdaspeed 6 year variants
    ("mazdaspeed 3", "Mazda", "Mazda3", "BK"),
    ("mazdaspeed3", "Mazda", "Mazda3", "BK"),
    ("mazdaspeed 2.0 fs turbo", "Mazda", "Mazdaspeed Protegé", "BJ"),
    ("mazda b2600", "Mazda", "B-Series Truck", "5th Gen"),
    ("2005-2007 mazdaspeed 6", "Mazda", "Mazda6", "GG/GY"),
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
    ("sti gde", "Subaru", "WRX", "GD"),
    ("sti gdf", "Subaru", "WRX", "GD"),
    ("wrx gh8", "Subaru", "WRX", "GR"),
    ("wrx gh", "Subaru", "WRX", "GR"),
    ("wrx vab", "Subaru", "WRX", "VA"),
    ("wrx vaf", "Subaru", "WRX", "VA"),
    ("sti vab", "Subaru", "WRX", "VA"),
    # Subaru WRX parens-chassis + multi-gen year-range fitments + BRZ/FRS/86 pairings
    ("sti (gde)", "Subaru", "WRX", "GD"),
    ("sti (gdf)", "Subaru", "WRX", "GD"),
    ("sti (grb)", "Subaru", "WRX", "GR"),
    ("sti (gvb)", "Subaru", "WRX", "GR"),
    ("sti (gvf)", "Subaru", "WRX", "GR"),
    ("sti (vab)", "Subaru", "WRX", "VA"),
    ("sti (vaf)", "Subaru", "WRX", "VA"),
    ("sti (vag)", "Subaru", "WRX", "VA"),
    ("gde/gdf", "Subaru", "WRX", "GD"),
    ("gvb/gvf", "Subaru", "WRX", "GR"),
    ("vab/vaf/vag", "Subaru", "WRX", "VA"),
    ("gc6", "Subaru", "WRX", "GC"),
    ("gc6/gc8", "Subaru", "WRX", "GC"),
    # Scion FR-S / Subaru BRZ / Toyota 86 (ZC6 / ZN6 1st-gen pair — seeded existing)
    ("scion fr-s", "Subaru", "BRZ", "ZC6"),
    ("scion fr-s", "Toyota", "86", "ZN6"),
    ("frs/brz", "Subaru", "BRZ", "ZC6"),
    ("frs/brz", "Toyota", "86", "ZN6"),
    ("fr-s/brz", "Subaru", "BRZ", "ZC6"),
    ("fr-s/brz", "Toyota", "86", "ZN6"),
    ("2013-2016 scion fr-s", "Subaru", "BRZ", "ZC6"),
    ("2013-2016 scion fr-s", "Toyota", "86", "ZN6"),
    ("2013-2020 subaru brz", "Subaru", "BRZ", "ZC6"),
    ("2013-2024 subaru brz", "Subaru", "BRZ", "ZC6"),
    ("2013-2024 subaru brz", "Subaru", "BRZ", "ZD8"),
    ("2017-2020 toyota 86", "Toyota", "86", "ZN6"),
    ("2017-2019 toyota 86", "Toyota", "86", "ZN6"),
    ("17-20 toyota 86", "Toyota", "86", "ZN6"),
    ("2022-2024 subaru brz", "Subaru", "BRZ", "ZD8"),
    # Subaru WRX/STI decade-spanning year-range patterns
    ("2002-2014 subaru wrx", "Subaru", "WRX", "GD"),
    ("2002-2014 subaru wrx", "Subaru", "WRX", "GR"),
    ("02-14 wrx", "Subaru", "WRX", "GD"),
    ("02-14 wrx", "Subaru", "WRX", "GR"),
    ("02-14 subaru wrx", "Subaru", "WRX", "GD"),
    ("02-14 subaru wrx", "Subaru", "WRX", "GR"),
    ("2015-2021 subaru wrx", "Subaru", "WRX", "VA"),
    ("2015-2021 subaru wrx / sti", "Subaru", "WRX", "VA"),
    ("2015-2021 subaru wrx/sti", "Subaru", "WRX", "VA"),
    ("2015-2021 wrx/sti", "Subaru", "WRX", "VA"),
    ("2015-2021 wrx", "Subaru", "WRX", "VA"),
    ("2008-2014 subaru wrx/sti", "Subaru", "WRX", "GR"),
    ("2008-2014 subaru wrx / sti", "Subaru", "WRX", "GR"),
    ("2008-2014 wrx/sti", "Subaru", "WRX", "GR"),
    ("2008-2014 subaru wrx", "Subaru", "WRX", "GR"),
    ("2006-2017 subaru wrx", "Subaru", "WRX", "GD"),
    ("2006-2017 subaru wrx", "Subaru", "WRX", "GR"),
    ("2006-2017 subaru wrx", "Subaru", "WRX", "VA"),
    ("02-07 subaru wrx / sti", "Subaru", "WRX", "GD"),
    ("2002-2007 subaru wrx / sti", "Subaru", "WRX", "GD"),
    ("2002-2007 wrx/sti", "Subaru", "WRX", "GD"),
    ("2002-2007 subaru wrx", "Subaru", "WRX", "GD"),
    ("2007-2021 sti", "Subaru", "WRX", "GR"),
    ("2007-2021 sti", "Subaru", "WRX", "VA"),
    ("2002-2014 wrx", "Subaru", "WRX", "GD"),
    ("2002-2014 wrx", "Subaru", "WRX", "GR"),
    ("92-01 subaru impreza wrx", "Subaru", "WRX", "GC"),
    ("92-01 impreza wrx", "Subaru", "WRX", "GC"),
    ("11-14 subaru impreza sti", "Subaru", "WRX", "GR"),
    ("08-14 impreza wrx hatchback", "Subaru", "WRX", "GR"),
    ("06-21 sti", "Subaru", "WRX", "GR"),
    ("06-21 sti", "Subaru", "WRX", "VA"),
    ("06-14 wrx", "Subaru", "WRX", "GD"),
    ("06-14 wrx", "Subaru", "WRX", "GR"),
    # Subaru Forester XT year-range + bare forms
    ("03-08 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("04-07 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2004-2007 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2004-2008 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2004-07 subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("2014-2018 subaru forester", "Subaru", "Forester XT", "SJ"),
    ("2009-2013 subaru forester xt", "Subaru", "Forester XT", "SH"),
    ("04-13 fxt", "Subaru", "Forester XT", "SG"),
    ("04-13 fxt", "Subaru", "Forester XT", "SH"),
    ("04-08 fxt", "Subaru", "Forester XT", "SG"),
    ("09-13 fxt", "Subaru", "Forester XT", "SH"),
    ("subaru forester xt", "Subaru", "Forester XT", "SG"),
    ("subaru forester xt", "Subaru", "Forester XT", "SH"),
    ("forester xt", "Subaru", "Forester XT", "SG"),
    ("forester xt", "Subaru", "Forester XT", "SH"),
    # Subaru Ascent (new seed)
    ("subaru ascent", "Subaru", "Ascent", "1st Gen"),
    # Subaru Legacy parens+slash chassis forms + new BC/BJ/BF seed + BM/BR BN/BS year ranges
    ("05-09 subaru legacy (bl9 / bp)", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bl9", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bp5", "Subaru", "Legacy", "BL/BP"),
    ("95-99 subaru legacy", "Subaru", "Legacy", "BD/BG"),
    ("subaru legacy bd", "Subaru", "Legacy", "BD/BG"),
    ("subaru legacy bg", "Subaru", "Legacy", "BD/BG"),
    ("90-94 subaru legacy", "Subaru", "Legacy", "BC/BJ/BF"),
    ("10-14 subaru legacy", "Subaru", "Legacy", "BM/BR"),
    ("15-19 subaru legacy", "Subaru", "Legacy", "BN/BS"),
    # Subaru Baja (new seed)
    ("03-06 subaru baja", "Subaru", "Baja", "BT"),
    # Subaru Impreza base year-range fitments (pre-existing WRX distinctions)
    ("16-21 subaru impreza", "Subaru", "Impreza", "GP/GJ"),
    ("17-23 subaru impreza sport", "Subaru", "Impreza", "GP/GJ"),
    # Mercedes G63 AMG (W463) + SL-Class R230 SL55 AMG
    ("mercedes g63", "Mercedes", "G63 AMG", "W463"),
    ("mercedes g63 amg", "Mercedes", "G63 AMG", "W463"),
    ("g63 amg", "Mercedes", "G63 AMG", "W463"),
    ("sl55 amg", "Mercedes", "SL-Class", "R230"),
    ("mercedes benz sl55 amg", "Mercedes", "SL-Class", "R230"),
    # Dodge Viper / Charger / Challenger year-range fitments
    ("1996-2000 dodge viper", "Dodge", "Viper", "SR II"),
    ("1996-2000 viper", "Dodge", "Viper", "SR II"),
    ("2003-2006 dodge viper", "Dodge", "Viper", "ZB I"),
    ("2006-2008 charger", "Dodge", "Charger", "LX"),
    ("2006-2008 dodge charger", "Dodge", "Charger", "LX"),
    ("2006-2008 charger/300c/magnum", "Dodge", "Charger", "LX"),
    ("2006-2008 charger/300c", "Dodge", "Charger", "LX"),
    ("2006-2014 charger", "Dodge", "Charger", "LX"),
    ("2006-2014 charger", "Dodge", "Charger", "LD"),
    ("2009-2014 charger", "Dodge", "Charger", "LD"),
    ("2015+ charger", "Dodge", "Charger", "LD"),
    ("2015+ dodge charger", "Dodge", "Charger", "LD"),
    ("2015+ dodge charger hellcat", "Dodge", "Charger", "LD"),
    ("dodge charger hellcat", "Dodge", "Charger", "LD"),
    ("2008 challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2008 dodge challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2008-2014 challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2008-2014 dodge challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2009-2014 challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2015+ challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2015+ dodge challenger", "Dodge", "Challenger", "3rd Gen"),
    ("2015+ challenger hellcat", "Dodge", "Challenger", "3rd Gen"),
    ("challenger hellcat", "Dodge", "Challenger", "3rd Gen"),
    ("challenger demon", "Dodge", "Challenger", "3rd Gen"),
    ("2009-2014 challenger r/t", "Dodge", "Challenger", "3rd Gen"),
    ("2009-2014 challenger srt8", "Dodge", "Challenger", "3rd Gen"),
    # New-make aliases: Alfa Romeo / Land Rover / Jaguar / Saab / Volvo / Smart / Fiat / Pontiac GP / Mini Coupé+Roadster
    ("alfa romeo 4c", "Alfa Romeo", "4C", "960"),
    ("alfa romeo giulia", "Alfa Romeo", "Giulia", "Type 952"),
    ("alfa romeo giulia quadrifoglio", "Alfa Romeo", "Giulia", "Type 952"),
    ("alfa romeo stelvio", "Alfa Romeo", "Stelvio", "Type 949"),
    ("stelvio quadrifoglio", "Alfa Romeo", "Stelvio", "Type 949"),
    ("12-16 range rover evoque", "Land Rover", "Range Rover Evoque", "L538"),
    ("12-19 range rover evoque", "Land Rover", "Range Rover Evoque", "L538"),
    ("13-15 jaguar xf", "Jaguar", "XF", "X250"),
    ("02-04 jaguar x-type", "Jaguar", "X-Type", "CF1"),
    ("saab 9-3", "Saab", "9-3", "YS3F"),
    ("volvo v40", "Volvo", "V40", "V1"),
    ("volvo s40", "Volvo", "S40", "V1"),
    ("2008-2014 smart fortwo", "Smart", "ForTwo", "W451"),
    ("12-19 fiat 500", "Fiat", "500", "312"),
    ("fiat 500 abarth", "Fiat", "500", "312"),
    ("04-08 pontiac grand prix", "Pontiac", "Grand Prix", "8th Gen"),
    ("12-15 mini coupé", "Mini", "Coupé", "R58"),
    ("mini coupé r59", "Mini", "Roadster", "R59"),
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
    ("90-93 toyota celica", "Toyota", "Celica", "5th Gen"),
    ("toyota celica", "Toyota", "Celica", "6th Gen"),  # broad: most parts target 6th/7th gen
    ("toyota celica", "Toyota", "Celica", "7th Gen"),
    # Toyota Supra A90 B48 variant + 2.0/3.0 trim aliases
    ("b48 supra", "Toyota", "Supra", "A90"),
    ("supra 2.0", "Toyota", "Supra", "A90"),
    ("supra 3.0", "Toyota", "Supra", "A90"),
    # Toyota AE86 (Zenki/Kouki) — AE86 is in AMBIGUOUS_STANDALONE_CODES; require context
    ("ae86", "Toyota", "AE86", "Zenki"),
    ("ae86", "Toyota", "AE86", "Kouki"),
    ("corolla ae86", "Toyota", "AE86", "Zenki"),
    ("corolla ae86", "Toyota", "AE86", "Kouki"),
    ("toyota corolla ae86", "Toyota", "AE86", "Zenki"),
    ("toyota corolla ae86", "Toyota", "AE86", "Kouki"),
    ("toyota ae86", "Toyota", "AE86", "Zenki"),
    ("toyota ae86", "Toyota", "AE86", "Kouki"),
    ("ae86 corolla", "Toyota", "AE86", "Zenki"),
    ("ae86 corolla", "Toyota", "AE86", "Kouki"),
    ("corolla gt-s (ae86)", "Toyota", "AE86", "Zenki"),
    ("4a-ge ae86", "Toyota", "AE86", "Zenki"),
    ("84-87 toyota corolla ae86", "Toyota", "AE86", "Zenki"),
    ("84-87 toyota corolla ae86", "Toyota", "AE86", "Kouki"),
    # Toyota Supra A80 JDM / A70 Mk3 chassis codes
    ("jza80", "Toyota", "Supra", "A80"),
    ("jza80 supra", "Toyota", "Supra", "A80"),
    ("supra jza80", "Toyota", "Supra", "A80"),
    ("toyota supra jza80", "Toyota", "Supra", "A80"),
    ("ma70", "Toyota", "Supra", "A70"),
    ("ma70 supra", "Toyota", "Supra", "A70"),
    ("7mgt supra", "Toyota", "Supra", "A70"),
    ("7m-gte", "Toyota", "Supra", "A70"),
    ("86-92 toyota supra", "Toyota", "Supra", "A70"),
    ("mk3 supra", "Toyota", "Supra", "A70"),
    ("supra mk3", "Toyota", "Supra", "A70"),
    ("mkiii supra", "Toyota", "Supra", "A70"),
    ("mk3 toyota supra", "Toyota", "Supra", "A70"),
    ("86-92 supra", "Toyota", "Supra", "A70"),
    ("1986-1992 toyota supra", "Toyota", "Supra", "A70"),
    ("1986-1992 supra", "Toyota", "Supra", "A70"),
    ("1993-1998 toyota supra", "Toyota", "Supra", "A80"),
    ("1993-1998 supra", "Toyota", "Supra", "A80"),
    # Toyota MR2 Spyder (W30) year-range aliases
    ("mr2 spyder", "Toyota", "MR2", "W30"),
    ("toyota mr2 spyder", "Toyota", "MR2", "W30"),
    ("00-05 toyota mr2", "Toyota", "MR2", "W30"),
    ("00-07 toyota mr2", "Toyota", "MR2", "W30"),
    # Toyota MR2 JDM chassis codes (W10 = AW11, W20 = SW20, W30 = ZZW30)
    ("sw20", "Toyota", "MR2", "W20"),
    ("mr2 sw20", "Toyota", "MR2", "W20"),
    ("toyota mr2 sw20", "Toyota", "MR2", "W20"),
    ("sw20 mr2", "Toyota", "MR2", "W20"),
    ("aw11", "Toyota", "MR2", "W10"),
    ("mr2 aw11", "Toyota", "MR2", "W10"),
    ("toyota mr2 aw11", "Toyota", "MR2", "W10"),
    ("aw11 mr2", "Toyota", "MR2", "W10"),
    ("toyota mrs zzw30", "Toyota", "MR2", "W30"),
    ("mrs zzw30", "Toyota", "MR2", "W30"),
    # Toyota Corolla E100 (AE100/AE101/AE111)
    ("93-97 toyota corolla", "Toyota", "Corolla", "E100"),
    ("93-02 toyota corolla", "Toyota", "Corolla", "E100"),
    ("corolla ae101", "Toyota", "Corolla", "E100"),
    ("corolla ae111", "Toyota", "Corolla", "E100"),
    # Toyota Chaser (JZX100) / Cressida (MX83/MX73) engine-code aliases
    ("toyota chaser", "Toyota", "Chaser", "JZX100"),
    ("toyota cressida", "Toyota", "Cressida", "MX83"),
    ("toyota cressida", "Toyota", "Cressida", "MX73"),
    ("cressida 89-92", "Toyota", "Cressida", "MX83"),
    ("cressida mx83", "Toyota", "Cressida", "MX83"),
    ("mx83 cressida", "Toyota", "Cressida", "MX83"),
    ("2jz-gte", "Toyota", "Supra", "A80"),
    ("2jzgte", "Toyota", "Supra", "A80"),
    ("1jz-gte", "Toyota", "Chaser", "JZX100"),
    ("1jzgte", "Toyota", "Chaser", "JZX100"),
    ("1jzgte vvti", "Toyota", "Chaser", "JZX100"),
    ("3s-gte", "Toyota", "MR2", "W20"),
    # 4U-GSE engine on Toyobaru (86/BRZ)
    ("4u-gse", "Subaru", "BRZ", "ZC6"),
    ("4u-gse", "Toyota", "86", "ZN6"),
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
    # Hyundai Genesis Coupe engine-trim aliases (2.0T / 3.8)
    ("genesis 2.0t", "Hyundai", "Genesis Coupe", "BK"),
    ("genesis 2.0t", "Hyundai", "Genesis Coupe", "BK2"),
    ("hyundai genesis coupe 2.0t", "Hyundai", "Genesis Coupe", "BK"),
    ("hyundai genesis coupe 2.0t", "Hyundai", "Genesis Coupe", "BK2"),
    ("hyundai genesis coupe 3.8", "Hyundai", "Genesis Coupe", "BK"),
    ("hyundai genesis coupe 3.8", "Hyundai", "Genesis Coupe", "BK2"),
    # Hyundai Veloster year-range aliases (FS/JS in AMBIGUOUS_STANDALONE_CODES)
    ("12-18 hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("11-17 hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("18-22 hyundai veloster", "Hyundai", "Veloster", "JS"),
    ("hyundai veloster", "Hyundai", "Veloster", "FS"),
    ("hyundai veloster", "Hyundai", "Veloster", "JS"),
    ("veloster turbo", "Hyundai", "Veloster", "FS"),
    # Acura TL year-range aliases
    ("96-98 acura tl", "Acura", "TL", "1st Gen"),
    ("98-01 acura tl", "Acura", "TL", "2nd Gen"),
    ("99-03 acura tl", "Acura", "TL", "2nd Gen"),
    ("04-08 acura tl", "Acura", "TL", "3rd Gen"),
    ("09-14 acura tl", "Acura", "TL", "4th Gen"),
    ("acura tl", "Acura", "TL", "3rd Gen"),
    ("acura tl", "Acura", "TL", "4th Gen"),
    # Acura RDX year-range aliases
    ("07-12 acura rdx", "Acura", "RDX", "TB1/TB2"),
    ("13-18 acura rdx", "Acura", "RDX", "TB3/TB4"),
    ("2019-2021 acura rdx", "Acura", "RDX", "TC1"),
    ("2019+ acura rdx", "Acura", "RDX", "TC1"),
    ("2019 acura rdx", "Acura", "RDX", "TC1"),
    ("acura rdx", "Acura", "RDX", "TB1/TB2"),  # broad: TB1/TB2 turbo most tuning-popular
    ("acura rdx", "Acura", "RDX", "TB3/TB4"),
    # Acura ILX year-range aliases
    ("13-15 acura ilx", "Acura", "ILX", "DE3"),
    ("16-22 acura ilx", "Acura", "ILX", "DE3"),
    ("16-23 acura ilx", "Acura", "ILX", "DE3"),
    ("acura ilx", "Acura", "ILX", "DE3"),
    # Acura Integra/RSX combined product name alias (often listed together in fitment guides)
    ("acura integra / rsx", "Acura", "RSX", "DC5"),
    ("acura integra/rsx", "Acura", "RSX", "DC5"),
    ("02-06 acura integra / rsx", "Acura", "RSX", "DC5"),
    # Acura Integra year-range aliases (gen names "3rd Gen"/"4th Gen" rarely appear in product text)
    ("94-01 acura integra", "Acura", "Integra", "3rd Gen"),
    ("97-01 acura integra", "Acura", "Integra", "3rd Gen"),
    ("02-06 acura integra", "Acura", "Integra", "4th Gen"),
    ("acura integra", "Acura", "Integra", "3rd Gen"),  # broad: 3rd+4th most common
    ("acura integra", "Acura", "Integra", "4th Gen"),
    # Integra Type R is a trim of the 3rd Gen Integra (DC2 chassis), MY1997-2001.
    # Seed has Integra with gens 1st-5th; DC2 = 3rd Gen.
    ("acura integra type-r", "Acura", "Integra", "3rd Gen"),
    ("integra type-r", "Acura", "Integra", "3rd Gen"),
    # Acura Integra 5th Gen (2023+) — 5th Gen exists in seed but "acura integra" alias
    # above broad-fires 3rd+4th; explicit 5th-Gen aliases needed for modern Integra.
    ("2022 acura integra", "Acura", "Integra", "5th Gen"),
    ("2023 acura integra", "Acura", "Integra", "5th Gen"),
    ("2024 acura integra", "Acura", "Integra", "5th Gen"),
    ("2023+ acura integra", "Acura", "Integra", "5th Gen"),
    ("2023+ acura integra type-s", "Acura", "Integra", "5th Gen"),
    ("2024 integra type s", "Acura", "Integra", "5th Gen"),
    ("integra type s", "Acura", "Integra", "5th Gen"),
    # Acura DA Integra 2nd Gen — "DA" is now in AMBIGUOUS_STANDALONE_CODES; require context.
    ("90-93 acura da integra", "Acura", "Integra", "2nd Gen"),
    ("da integra", "Acura", "Integra", "2nd Gen"),
    ("acura da integra", "Acura", "Integra", "2nd Gen"),
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
    # MDX gen mapping: YD1 = 1st Gen (2001-2006), YD2 = 2nd Gen (2007-2013),
    # YD3 = 3rd Gen (2014-2020), YD4 = 4th Gen (2022+). Seed uses 1st/2nd/3rd/4th
    # Gen names; aliases below were previously written against the chassis
    # codes which weren't seed gen_names. Drift fixed.
    ("07-13 acura mdx", "Acura", "MDX", "2nd Gen"),
    ("14-20 acura mdx", "Acura", "MDX", "3rd Gen"),
    ("14-21 acura mdx", "Acura", "MDX", "3rd Gen"),
    ("acura mdx", "Acura", "MDX", "2nd Gen"),  # broad
    ("acura mdx", "Acura", "MDX", "3rd Gen"),
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
    # Honda Civic FE1/FL1/FL2 (11th Gen), FC/FK7 (10th Gen), EM/EJ/EK/EP3/EK9/D16 codes,
    # plus 3rd-7th Gen year-range fitments.
    ("2017-2019 honda civic si", "Honda", "Civic", "10th Gen"),
    ("2017-2020 honda civic type r", "Honda", "Civic Type R", "FK8"),
    ("2017-2020 civic type r", "Honda", "Civic Type R", "FK8"),
    ("2017-2021 honda civic type r", "Honda", "Civic Type R", "FK8"),
    ("2017-2022 honda cr-v", "Honda", "CR-V", "RW"),
    ("2023+ honda cr-v", "Honda", "CR-V", "RW"),
    ("2018-2022 honda accord", "Honda", "Accord", "10th Gen"),
    ("2012-2015 honda civic si", "Honda", "Civic", "9th Gen"),
    ("2017-2021 honda civic si", "Honda", "Civic", "10th Gen"),
    ("civic fe1", "Honda", "Civic", "11th Gen"),
    ("fe1 civic", "Honda", "Civic", "11th Gen"),
    ("honda civic fe1", "Honda", "Civic", "11th Gen"),
    ("civic si fe1", "Honda", "Civic", "11th Gen"),
    ("civic (fe1)", "Honda", "Civic", "11th Gen"),
    ("fl1", "Honda", "Civic", "11th Gen"),
    ("fl2", "Honda", "Civic", "11th Gen"),
    ("civic fc", "Honda", "Civic", "10th Gen"),
    ("civic (fc)", "Honda", "Civic", "10th Gen"),
    ("fc civic", "Honda", "Civic", "10th Gen"),
    ("fk7", "Honda", "Civic", "10th Gen"),
    ("civic fk7", "Honda", "Civic", "10th Gen"),
    ("civic em", "Honda", "Civic", "7th Gen"),
    ("civic (em)", "Honda", "Civic", "7th Gen"),
    ("em1", "Honda", "Civic", "7th Gen"),
    ("em2", "Honda", "Civic", "7th Gen"),
    ("civic ep3", "Honda", "Civic Type R", "EP3"),
    ("ep3 civic", "Honda", "Civic Type R", "EP3"),
    ("ek9", "Honda", "Civic Type R", "EK9"),
    ("ek9 civic", "Honda", "Civic Type R", "EK9"),
    ("d16", "Honda", "Civic", "6th Gen"),
    ("honda civic d16", "Honda", "Civic", "6th Gen"),
    ("ej civic", "Honda", "Civic", "6th Gen"),
    ("ek civic", "Honda", "Civic", "6th Gen"),
    ("civic (ej / ek)", "Honda", "Civic", "6th Gen"),
    ("civic (ej/ek)", "Honda", "Civic", "6th Gen"),
    ("84-87 honda civic", "Honda", "Civic", "3rd Gen"),
    ("88-91 honda civic", "Honda", "Civic", "4th Gen"),
    ("92-95 honda civic", "Honda", "Civic", "5th Gen"),
    ("96-00 honda civic", "Honda", "Civic", "6th Gen"),
    ("eg civic", "Honda", "Civic", "5th Gen"),
    ("honda eg civic", "Honda", "Civic", "5th Gen"),
    ("honda ek civic", "Honda", "Civic", "6th Gen"),
    ("78-79 honda civic", "Honda", "Civic", "1st Gen"),
    ("honda civic cvcc", "Honda", "Civic", "1st Gen"),
    # Honda Prelude / Odyssey RA
    ("92-01 honda prelude", "Honda", "Prelude", "4th Gen"),
    ("92-01 honda prelude", "Honda", "Prelude", "5th Gen"),
    ("94-98 honda odyssey", "Honda", "Odyssey", "RA"),
    ("94-98 honda odyssey (ra1-5)", "Honda", "Odyssey", "RA"),
    ("honda odyssey ra", "Honda", "Odyssey", "RA"),
    # Honda Accord year-range aliases (same issue — trim names interrupt make/model/gen)
    ("03-07 honda accord", "Honda", "Accord", "7th Gen"),
    ("08-12 honda accord", "Honda", "Accord", "8th Gen"),
    ("13-17 honda accord", "Honda", "Accord", "9th Gen"),
    ("18-22 honda accord", "Honda", "Accord", "10th Gen"),
    ("90-97 honda accord", "Honda", "Accord", "4th Gen"),
    ("90-97 honda accord", "Honda", "Accord", "5th Gen"),
    ("98-02 honda accord", "Honda", "Accord", "6th Gen"),
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
    ("97-05 lexus gs400", "Lexus", "GS", "JZS160"),
    ("lexus gs400 jzs161", "Lexus", "GS", "JZS160"),
    ("jzs161", "Lexus", "GS", "JZS160"),
    # Lexus IS JDM chassis codes + is300c + extended year ranges
    ("lexus is300 sxe10", "Lexus", "IS", "XE10"),
    ("is300 sxe10", "Lexus", "IS", "XE10"),
    ("sxe10", "Lexus", "IS", "XE10"),
    ("18-23 lexus is", "Lexus", "IS", "XE30"),
    ("10-15 lexus is250c", "Lexus", "IS", "XE20"),
    ("toyota is300", "Lexus", "IS", "XE10"),
    ("is300 2000-2005", "Lexus", "IS", "XE10"),
    ("2000-2005 is300", "Lexus", "IS", "XE10"),
    ("is300 1998-2005", "Lexus", "IS", "XE10"),
    # Lexus LS UCF10 + LS400 + RX (new seed) + year ranges
    ("95-00 lexus ls400", "Lexus", "LS", "UCF10"),
    ("lexus ls400", "Lexus", "LS", "UCF10"),
    ("04-09 lexus rx330", "Lexus", "RX", "XU30"),
    ("04-09 lexus rx350", "Lexus", "RX", "XU30"),
    # Mitsubishi Eclipse year-range aliases (3G/4G gen tokens don't appear in product text, so anchor on year ranges)
    ("00-05 mitsubishi eclipse", "Mitsubishi", "Eclipse", "3rd Gen"),
    ("06-12 mitsubishi eclipse", "Mitsubishi", "Eclipse", "4th Gen"),
    ("mitsubishi eclipse", "Mitsubishi", "Eclipse", "3rd Gen"),
    ("mitsubishi eclipse", "Mitsubishi", "Eclipse", "4th Gen"),
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
    # VW R32 Mk4/Mk5 explicit forms (VR6 / Golf IV/V R32)
    ("mk5 volkswagen r32", "Volkswagen", "R32", "Mk5"),
    ("mkv volkswagen r32", "Volkswagen", "R32", "Mk5"),
    ("mk4 volkswagen r32", "Volkswagen", "R32", "Mk4"),
    ("mkiv volkswagen r32", "Volkswagen", "R32", "Mk4"),
    ("2004 volkswagen golf iv r32", "Volkswagen", "R32", "Mk4"),
    ("volkswagen golf iv r32", "Volkswagen", "R32", "Mk4"),
    ("golf iv r32 4motion", "Volkswagen", "R32", "Mk4"),
    ("volkswagen golf v r32", "Volkswagen", "R32", "Mk5"),
    ("golf v r32", "Volkswagen", "R32", "Mk5"),
    # VW Passat B5/B6/B7 (new seed) + Passat CC + W8 + Jetta / Golf / GTI multi-gen fitments
    ("06-11 volkswagen passat (b6)", "Volkswagen", "Passat", "B6"),
    ("volkswagen passat b6", "Volkswagen", "Passat", "B6"),
    ("volkswagen passat b7", "Volkswagen", "Passat", "B7"),
    ("09-17 volkswagen passat cc", "Volkswagen", "Passat CC", "B6/B7"),
    ("volkswagen passat cc", "Volkswagen", "Passat CC", "B6/B7"),
    ("02-04 volkswagen passat w8", "Volkswagen", "Passat", "B5/B5.5"),
    ("passat w8", "Volkswagen", "Passat", "B5/B5.5"),
    ("passat 3bs", "Volkswagen", "Passat", "B5/B5.5"),
    # VW classic Golf/GTI/Jetta — seed only covers Golf Mk1+, Jetta Mk4+,
    # GTI Mk5+. Aliases referencing pre-seed gens (Jetta Mk2/Mk3, GTI Mk2/Mk3/Mk4)
    # were drift bugs and have been removed. Surviving entries below cover
    # only the seed-resolvable combinations. If a future seed change adds
    # the missing gens, restore the relevant aliases in the same PR.
    ("84-97 volkswagen golf", "Volkswagen", "Golf", "Mk2"),
    ("84-97 volkswagen golf", "Volkswagen", "Golf", "Mk3"),
    ("1987-1992 vw golf", "Volkswagen", "Golf", "Mk2"),
    ("1993-1998 vw golf", "Volkswagen", "Golf", "Mk3"),
    ("1999-2005 volkswagen golf", "Volkswagen", "Golf", "Mk4"),
    ("1999-2005 vw golf/jetta", "Volkswagen", "Golf", "Mk4"),
    ("1999-2005 vw golf/jetta", "Volkswagen", "Jetta", "Mk4"),
    ("1999-2005 vw golf/jetta/beetle", "Volkswagen", "Golf", "Mk4"),
    ("1999-2005 vw golf/jetta/beetle", "Volkswagen", "Jetta", "Mk4"),
    # Subaru Legacy year-range aliases — generation codes use "/" ("BE/BH") which fails substring
    # matching when product titles space-pad the slash ("Legacy (BE / BH)").
    ("00-04 subaru legacy", "Subaru", "Legacy", "BE/BH"),
    ("subaru legacy be / bh", "Subaru", "Legacy", "BE/BH"),
    ("subaru legacy be/bh", "Subaru", "Legacy", "BE/BH"),
    ("05-09 subaru legacy", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bl / bp", "Subaru", "Legacy", "BL/BP"),
    ("subaru legacy bm9", "Subaru", "Legacy", "BM/BR"),
    ("subaru legacy bm / br", "Subaru", "Legacy", "BM/BR"),
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
    # --- M004/S02 corpus-derived additions (decided_at: 2026-04-27, audit: zero alias decisions) ---
    # The corpus-vote audit (`backend/scripts/m004_taxonomy_audit.py --dry-run`) emitted zero
    # `decision == 'alias'` rows against the local Postgres corpus this milestone targets.
    # No new alias tuples are appended. The frozen-baseline test in
    # `tests/test_car_inference.py::TestM004S02AliasBaseline` pins the resulting
    # `len(CAR_ALIASES)` so a future agent that lands deletions or reorderings here gets
    # a loud failure instead of a silent recall regression.
    # --- M004/S04 corpus-derived additions (decided_at: 2026-04-28, audit: zero-corpus environment per MEM216/MEM221) ---
    # T02 recorded a zero-corpus pre-S04 snapshot (.gsd/milestones/M004/s04-corpus-delta.json)
    # because the auto-mode SQLite fallback has no `crawled_pages` table. Per the T03 plan's
    # zero-corpus branch, two defensible year-range aliases are added below — direct parallels
    # of the existing FK8 year-range entries at lines 2283-2285 and the "2023+ honda cr-v" form
    # at line 2287. FL5 Civic Type R production years are 2023+ (US, debuted MY2023). These
    # close a known retailer-text gap (year-range fitment phrasing) with no ambiguity risk:
    # "civic type r" already routes uniquely to Honda, and the M004/S02 baseline test will
    # bump from 2035 → 2037 in the same commit (TestM004S04AliasBaseline.EXPECTED_BASELINE).
    ("2023+ honda civic type r", "Honda", "Civic Type R", "FL5"),
    ("2023+ civic type r", "Honda", "Civic Type R", "FL5"),
]

# Word-boundary for short codes so "A90" doesn't match inside "BA90", and "nd" not inside "random"
_SHORT_PHRASE_MAX_LEN = 8

# Aliases that need extra context so we don't match numbers/units: "42" in 0.42 Mu, "lb" in ft-lb / lug bolt
_AUDI_R8_42_PHRASES = ("r8 42", "42 r8", "r8 type 42", "audi r8 42", "audi r8 type 42")
_CHARGER_LB_PHRASES = ("charger lb", "dodge charger lb")


# Units / suffixes that turn a bare numeric phrase into a measurement rather than a chassis code.
# "970% downforce", "992 kph", "718 nm", "911 hp" are not car-generation references.
# Also includes displacement ("2.7L"), forced-induction ("1.8T"), bore/length ('3.997"'),
# and imperial linear ("4.930in", "383ci") forms that collide with Porsche/VAG chassis codes.
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
    # Displacement / forced-induction suffix forms
    "l",  # "2.7L", "3.8L" displacement
    "t",  # "1.8T", "2.0T", "2.7T" forced induction
    "tfsi",
    "tsi",
    # Imperial linear
    "in",  # 4.930in
    "ci",  # cubic inches
    "cid",
    "cu",
    "cubic",
)


def _is_numeric_measurement_context(text_lower: str, phrase_lower: str) -> bool:
    """
    True if a bare-numeric phrase (e.g. "970", "992") appears only as "<number><unit>"
    or "<number> <unit>" in the text — i.e. it's describing a measurement, not a chassis.
    Checks every occurrence; if any is not a measurement, inference can still fire.

    Also rejects when the phrase appears as the fractional portion of a decimal value
    (`3.997"`, `4.930in`, `3,8L` Euro-comma) — in every observed case that is a
    bore/displacement figure, never a chassis code.
    """
    if not phrase_lower.isdigit():
        return False
    # Reject decimal-fractional occurrences outright (e.g. "3.997\"", "4.930in", "3,8L").
    if re.search(rf"[0-9][.,]{re.escape(phrase_lower)}\b", text_lower):
        return True
    # Capture a trailing measurement suffix. Allow `"` (inch glyph) in addition to the
    # alphabetic/%/-// characters, since it is not alphabetic but is a valid unit.
    pattern = re.compile(r"\b" + re.escape(phrase_lower) + r'\b\s*(["A-Za-z%\-/]+)?')
    any_match = False
    for m in pattern.finditer(text_lower):
        any_match = True
        suffix = (m.group(1) or "").lower()
        if suffix.startswith('"'):
            continue
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

    Year-range narrowing is applied automatically when the combined text contains exactly one
    coherent fitment span (overlapping/adjacent ranges merge into one span). Multiple disjoint
    spans (multi-fitment titles like "2003-2007 LX, 2009-2014 LD") leave triples unfiltered —
    the title is too ambiguous to safely narrow, since each phrase match could legitimately
    belong to either span. If narrowing would strip every triple (e.g. a single year token like
    "since 2002" that doesn't overlap any matched-model generation), the unnarrowed triples are
    kept rather than falling through to is_universal — the year token in that case is more
    likely an incidental year (release date, spec callout) than a fitment year.
    """
    name = (name or "").strip()
    description = (description or "").strip()
    url = (product_url or "").strip()
    # URL slugs use '-'/'_' as word separators ("tesla-model-s-plaid"). Normalize those to
    # spaces so multi-word aliases like "tesla model s plaid" can match the URL portion.
    url_normalized = re.sub(r"[-_/]+", " ", url)
    # Strip parentheses from product names — fitment titles like "(7th Generation)" or "(FWD / AWD)"
    # would otherwise block substring matching against PHRASE_TRIPLES (which don't contain parens).
    #
    # Known limitation: this strip leaves the parenthesized words inline, so titles where parens
    # appear *between* a make and model token still won't match make+model phrases. Example:
    # "Nissan (ONLY) GT-R" → "Nissan ONLY GT-R" — and "nissan gt-r" is not a substring of that.
    # The adjacency requirement is what keeps PHRASE_TRIPLES precise (e.g. preventing "Honda" +
    # "Civic" tokens scattered across a long fitment list from being treated as one phrase), so
    # we don't try to repair the gap by additional rewriting. Adapters that need parens-broken
    # phrases handled should override infer_car_for_part with their own parser.
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

    if not result:
        return result

    # Year-range narrowing. Forward to a private helper so the policy
    # (single-coherent-span only; preserve triples on empty narrow) lives
    # next to the merge logic. extract_year_ranges and narrow_triples_by_year_range
    # are defined later in the module — late binding makes the references safe.
    return _maybe_narrow_by_combined_year_ranges(result, combined)


# Canonical year-range extractor (issue #5). Replaces the 5 near-duplicate
# _extract_*_year_range helpers that each adapter had to maintain. Handles:
#   - 4-digit year ranges:        "2015-2018", "2015 - 2018"
#   - 2-digit-tail year ranges:   "2015-23", "2003-09" (century-inferred)
#   - 2-digit-pair year ranges:   "92-95", "08-14" (century-inferred from MY rules)
#   - Open-ended:                 "2003+", "(2015+)" (-> end = current_year + 1)
#   - Single year:                "2015", "(2015)" (returned as (Y, Y))
#   - Model-year prefix:          "MY2010", "MY 2010"
#   - Half model years:           "2010.5-2012", "1998.5+"
# Returns a list of (start_year, end_year) tuples in title order. Returns []
# if no plausible range is found. Year validity gate: 1960-current_year+1.
import datetime as _dt

_YEAR_LO: int = 1960
_YEAR_HI_OFFSET: int = 1  # current_year + 1 to allow MY-ahead-of-CY

# Allow en-dash, em-dash, hyphen-minus, and "to" as range separators.
_RANGE_SEP = r"\s*(?:[-–—]|to)\s*"
# YYYY-YYYY (with optional .5 on either side)
_YYYY_YYYY_RE = re.compile(
    rf"\b((?:19|20)\d{{2}})(?:\.5)?{_RANGE_SEP}((?:19|20)\d{{2}})(?:\.5)?\b"
)
# YYYY-YY (4-digit start, 2-digit tail)
_YYYY_YY_RE = re.compile(
    rf"\b((?:19|20)\d{{2}})(?:\.5)?{_RANGE_SEP}(\d{{2}})(?!\d)"
)
# YY-YY (both 2-digit). Constrained: standalone token form to avoid matching
# arbitrary numbers. Requires non-digit-or-dot lookbehind to prevent matching
# inside larger digit sequences or decimal numbers.
_YY_YY_RE = re.compile(
    rf"(?<![\d.])(\d{{2}}){_RANGE_SEP}(\d{{2}})(?!\d)"
)
# Open-ended: YYYY+. Lookbehind allows a "MY" prefix without a word boundary
# (so "MY2015+" matches as well as " 2015+").
_YYYY_PLUS_RE = re.compile(
    r"(?:(?<=\s)|(?<=^)|(?<=\()|(?<=MY))((?:19|20)\d{2})(?:\.5)?\s*\+"
)
# Single year. Conservative: the year must be standalone (not part of a longer
# digit sequence and not part of a word like "2015th"). Includes optional MY
# prefix with an optional space ("MY2010", "MY 2010"). Same-shape lookbehind
# as YYYY_PLUS_RE so a leading "MY" doesn't block the match.
_SINGLE_YEAR_RE = re.compile(
    r"(?:(?<=\s)|(?<=^)|(?<=\()|(?<=MY)|(?<=MY ))((?:19|20)\d{2})(?:\.5)?(?!\d)",
    re.IGNORECASE,
)


def _validate_year_range(y1: int, y2: int) -> Optional[tuple[int, int]]:
    """Return (y1, y2) clamped+ordered if plausible, else None."""
    cy = _dt.datetime.now(_dt.timezone.utc).year
    hi = cy + _YEAR_HI_OFFSET
    if not (_YEAR_LO <= y1 <= hi):
        return None
    if not (_YEAR_LO <= y2 <= hi):
        return None
    if y1 > y2:
        return None
    return (y1, y2)


def _infer_century(start_year: int, two_digit_tail: int) -> int:
    """Convert a 2-digit year tail into a 4-digit year using the start year's century.
    If the inferred year is less than start_year (e.g. start=1995, tail=04 would
    naively give 1904), bump to the next century (-> 2004)."""
    century = (start_year // 100) * 100
    candidate = century + two_digit_tail
    if candidate < start_year:
        candidate += 100
    return candidate


def _infer_yy_yy_century(yy1: int, yy2: int) -> Optional[tuple[int, int]]:
    """A 2-digit-pair like '92-95' or '08-14' needs century inference.
    Heuristic: 60-99 -> 19xx, 00-59 -> 20xx (covers MY 1960 forward; 60+ years
    of cars). Both years must satisfy plausibility individually."""
    def _y(yy: int) -> int:
        return 1900 + yy if 60 <= yy <= 99 else 2000 + yy

    y1, y2 = _y(yy1), _y(yy2)
    return _validate_year_range(y1, y2)


def extract_year_ranges(text: Optional[str]) -> list[tuple[int, int]]:
    """Extract every plausible (start_year, end_year) range from ``text``.

    Single-year tokens come back as ``(Y, Y)``. Open-ended ``YYYY+`` comes
    back as ``(Y, current_year + 1)``. Same-tuple duplicates are de-duped
    while preserving first-seen order; overlapping forms (e.g. a YYYY-YYYY
    range whose start year *also* matches the single-year regex) are
    handled by extracting the longer-form ranges first and then masking
    the matched spans before searching for shorter forms.

    Designed as the single source of truth for year-range parsing across
    adapters. Replaces _extract_steeda_year_range, _extract_hasport_year_ranges,
    _extract_perrin_year_range, _extract_mishimoto_year_range, and
    _extract_leading_year_range (driveshaftshop), each of which had a
    near-duplicate version of this logic.
    """
    if not text:
        return []
    cy = _dt.datetime.now(_dt.timezone.utc).year
    open_ended_hi = cy + _YEAR_HI_OFFSET

    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []

    # We process longer / more-specific forms first and mask the consumed
    # spans before attempting shorter forms, so a YYYY-YYYY range doesn't
    # also yield two single-year matches at its boundaries.
    masked = list(text)

    def _mask(start: int, end: int) -> None:
        for i in range(start, end):
            masked[i] = " "

    def _emit(rng: Optional[tuple[int, int]]) -> None:
        if rng is None:
            return
        if rng in seen:
            return
        seen.add(rng)
        out.append(rng)

    # 1. YYYY-YYYY (longest, most specific)
    for m in _YYYY_YYYY_RE.finditer(text):
        y1, y2 = int(m.group(1)), int(m.group(2))
        _emit(_validate_year_range(y1, y2))
        _mask(m.start(), m.end())

    masked_text = "".join(masked)

    # 2. YYYY-YY
    for m in _YYYY_YY_RE.finditer(masked_text):
        y1 = int(m.group(1))
        tail = int(m.group(2))
        y2 = _infer_century(y1, tail)
        _emit(_validate_year_range(y1, y2))
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    # 3. YY-YY (both 2-digit, century-inferred)
    for m in _YY_YY_RE.finditer(masked_text):
        yy1 = int(m.group(1))
        yy2 = int(m.group(2))
        _emit(_infer_yy_yy_century(yy1, yy2))
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    # 4. YYYY+ (open-ended)
    for m in _YYYY_PLUS_RE.finditer(masked_text):
        y1 = int(m.group(1))
        _emit(_validate_year_range(y1, open_ended_hi))
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    # 5. Single year (returned as (Y, Y))
    for m in _SINGLE_YEAR_RE.finditer(masked_text):
        y = int(m.group(1))
        _emit(_validate_year_range(y, y))

    return out


def _extract_year_ranges_with_spans(
    text: Optional[str],
) -> list[tuple[tuple[int, int], int, int]]:
    """Same as extract_year_ranges, but each entry also carries (span_start,
    span_end) for the matched substring. Used by extract_fitment_candidates
    to pair year-ranges with nearby (make, model) phrase matches by distance.
    """
    if not text:
        return []
    cy = _dt.datetime.now(_dt.timezone.utc).year
    open_ended_hi = cy + _YEAR_HI_OFFSET

    seen: set[tuple[int, int]] = set()
    out: list[tuple[tuple[int, int], int, int]] = []

    masked = list(text)

    def _mask(start: int, end: int) -> None:
        for i in range(start, end):
            masked[i] = " "

    def _emit(rng: Optional[tuple[int, int]], span_start: int, span_end: int) -> None:
        if rng is None or rng in seen:
            return
        seen.add(rng)
        out.append((rng, span_start, span_end))

    for m in _YYYY_YYYY_RE.finditer(text):
        y1, y2 = int(m.group(1)), int(m.group(2))
        _emit(_validate_year_range(y1, y2), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YYYY_YY_RE.finditer(masked_text):
        y1 = int(m.group(1))
        tail = int(m.group(2))
        y2 = _infer_century(y1, tail)
        _emit(_validate_year_range(y1, y2), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YY_YY_RE.finditer(masked_text):
        yy1, yy2 = int(m.group(1)), int(m.group(2))
        _emit(_infer_yy_yy_century(yy1, yy2), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _YYYY_PLUS_RE.finditer(masked_text):
        y1 = int(m.group(1))
        _emit(_validate_year_range(y1, open_ended_hi), m.start(), m.end())
        _mask(m.start(), m.end())
    masked_text = "".join(masked)

    for m in _SINGLE_YEAR_RE.finditer(masked_text):
        y = int(m.group(1))
        _emit(_validate_year_range(y, y), m.start(), m.end())

    return out


class FitmentCandidate:
    """A (make, model, year_range) extracted from a product title.

    ``year_range`` is None when no year-range token was found near enough
    to the (make, model) phrase to confidently pair them. Callers can either
    drop None-year candidates or fall back to gen resolution that doesn't
    require year info (e.g. matching all generations of the model).

    Frozen-dataclass-style: equality and hashing for de-duplication.
    """

    __slots__ = ("make", "model", "year_range")

    def __init__(self, make: str, model: str, year_range: Optional[tuple[int, int]]) -> None:
        self.make: str = make
        self.model: str = model
        self.year_range: Optional[tuple[int, int]] = year_range

    def __repr__(self) -> str:
        return f"FitmentCandidate(make={self.make!r}, model={self.model!r}, year_range={self.year_range!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FitmentCandidate):
            return NotImplemented
        return (
            self.make == other.make
            and self.model == other.model
            and self.year_range == other.year_range
        )

    def __hash__(self) -> int:
        return hash((self.make, self.model, self.year_range))


# Maximum character distance between a (make, model) phrase match and a
# year-range token for them to be considered paired. Tuned to cover typical
# title shapes:
#   "Steeda Mustang (2015-2023) Cold Air Intake"          ~22 chars between
#   "2009-2014 Charger SRT8 Driveshaft"                   ~10 chars between
#   "Subaru WRX/STI 2015-2018 Strut Bar"                  ~12 chars between
# Anything beyond ~50 chars usually means the year and the model belong to
# different fitment fragments (e.g. a cross-fitment list).
_FITMENT_PAIR_DISTANCE: int = 50


def extract_fitment_candidates(
    title: Optional[str],
    *,
    trusted_makes: Optional[set[str]] = None,
) -> list[FitmentCandidate]:
    """Extract (make, model, year_range) candidates from a product title.

    Walks ``CAR_GENERATIONS`` (via _FITMENT_PHRASES_WITH_MAKE) for "<make>
    <model>" matches; if ``trusted_makes`` is given, also walks bare-model
    phrases scoped to that make set. For each (make, model) match, looks
    for a nearby year-range via ``extract_year_ranges`` and pairs them
    by character distance (within _FITMENT_PAIR_DISTANCE).

    Designed to replace per-adapter ``_<ADAPTER>_MODEL_PATTERNS``
    dictionaries. Adapter ``infer_car_for_part`` hooks collapse to::

        candidates = extract_fitment_candidates(parsed.name, trusted_makes={"Ford"})
        triples = [
            t
            for c in candidates
            if c.year_range is not None
            for t in generations_for_make_model_year_range(c.make, c.model, c.year_range)
        ]
        return triples or None

    Returns candidates in title order with duplicates removed. A candidate
    with ``year_range=None`` is emitted when a (make, model) phrase matched
    but no nearby year-range token was found — callers decide whether to
    drop it or use it without year-narrowing.
    """
    if not title:
        return []
    title_lower = title.lower()

    # Pre-extract year ranges WITH character spans so we can pair by distance.
    year_spans = _extract_year_ranges_with_spans(title)

    # Find (make, model) matches and pair with closest year-range by distance.
    candidates: list[FitmentCandidate] = []
    seen_keys: set[tuple[str, str, Optional[tuple[int, int]]]] = set()
    matched_spans: list[tuple[int, int]] = []  # avoid double-emitting overlapping matches

    def _try_match(phrases: list[tuple[str, str, str]]) -> None:
        for phrase, make, model in phrases:
            if trusted_makes is not None and make not in trusted_makes:
                continue
            start = title_lower.find(phrase)
            if start == -1:
                continue
            end = start + len(phrase)
            # Skip matches that overlap a longer prior match on the same span.
            if any(ms <= start < me or ms < end <= me for ms, me in matched_spans):
                continue
            matched_spans.append((start, end))

            # Pair with closest year-range within distance budget.
            paired_range: Optional[tuple[int, int]] = None
            best_dist = _FITMENT_PAIR_DISTANCE + 1
            for (rng, ys, ye) in year_spans:
                if ye <= start:
                    dist = start - ye
                elif ys >= end:
                    dist = ys - end
                else:
                    dist = 0
                if dist <= _FITMENT_PAIR_DISTANCE and dist < best_dist:
                    best_dist = dist
                    paired_range = rng

            key = (make, model, paired_range)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            candidates.append(FitmentCandidate(make, model, paired_range))

    _try_match(_FITMENT_PHRASES_WITH_MAKE)
    if trusted_makes is not None:
        _try_match(_FITMENT_PHRASES_MODEL_ONLY)

    # Sort by first-occurrence position in title for stable, intuitive output.
    candidates.sort(key=lambda c: title_lower.find(c.model.lower()))
    return candidates


def generations_for_make_model_year_range(
    make: str,
    model: str,
    year_range: tuple[int, int],
) -> list[tuple[str, str, str]]:
    """
    Return ``(make, model, generation_name)`` triples whose US production
    window overlaps ``year_range``. Reads ``CAR_GENERATIONS`` (the static
    declarative data) so this function is DB-free and safe to call from
    adapters at parse time. ``year_range`` is ``(start_year, end_year)``;
    use ``9999`` as ``end_year`` for open-ended ranges (``2021+``).

    Stable ordering matches the declarative sequence in
    ``car_generations_data`` so test diffs are predictable. Returns an
    empty list when the make/model is unknown, when no generation window
    overlaps, or when ``year_range`` is implausible (start > end).

    Used by adapter ``infer_car_for_part`` hooks for retailers whose
    titles encode fitment as a model token + parenthesized year range
    (Steeda's ``"Mustang ... (2015-2023)"``, Driveshaftshop's ``"2009-2014
    Dodge Charger ..."``) — the universal pipeline only matches phrases
    like ``"Mustang 6th Gen"`` and so misses these titles entirely.
    """
    y1, y2 = year_range
    if y1 > y2:
        return []
    models = CAR_GENERATIONS.get(make)
    if not models:
        return []
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for model_data in models:
        if model_data["model"] != model:
            continue
        for gen in model_data["generations"]:
            gs = gen["start_year"]
            ge = gen["end_year"] if gen["end_year"] is not None else 9999
            if y1 <= ge and y2 >= gs:
                gen_name = gen["generation_name"]
                if gen_name not in seen:
                    seen.add(gen_name)
                    out.append((make, model, gen_name))
    return out


def narrow_triples_by_year_range(
    triples: list[tuple[str, str, str]],
    year_range: tuple[int, int],
) -> list[tuple[str, str, str]]:
    """
    Filter ``triples`` to those whose generation window in ``CAR_GENERATIONS``
    overlaps ``year_range``. ``year_range`` is ``(start_year, end_year)``;
    use ``9999`` as the upper bound for open-ended ranges.

    Triples whose (make, model, generation) is unknown to ``CAR_GENERATIONS``
    are dropped — without a year window we can't decide overlap, and an
    unknown triple is also unlikely to resolve in ``resolve_car_triples_to_ids``
    against the DB anyway.

    Used by adapter ``infer_car_for_part`` hooks to layer year-range
    intelligence on top of ``infer_car_generations``: the universal
    pipeline matches model phrases like ``"Mitsubishi Eclipse"`` and
    returns *every* generation of that model; narrowing to the title's
    year range trims the match set down to the actually-fitted generations.
    Returns the filtered list (possibly empty); the adapter is responsible
    for converting an empty list to ``None`` to fall through.
    """
    y1, y2 = year_range
    if y1 > y2 or not triples:
        return []

    out: list[tuple[str, str, str]] = []
    for make, model, gen_name in triples:
        models = CAR_GENERATIONS.get(make)
        if not models:
            continue
        for model_data in models:
            if model_data["model"] != model:
                continue
            for gen in model_data["generations"]:
                if gen["generation_name"] != gen_name:
                    continue
                gs = gen["start_year"]
                ge = gen["end_year"] if gen["end_year"] is not None else 9999
                if y1 <= ge and y2 >= gs:
                    out.append((make, model, gen_name))
                break
            break
    return out


def _merge_year_ranges(
    ranges: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent year-ranges into disjoint spans.

    Two ranges merge when they overlap OR sit within one year of each other
    (so 2010-2014 and 2015-2018 become 2010-2018 — a single coherent fitment
    block, not two disjoint mentions). Returns the merged spans sorted by
    start year. Used by ``_maybe_narrow_by_combined_year_ranges`` to decide
    whether a title carries one fitment span (narrow) or several (skip).
    """
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        # Adjacent (gap of 1 year) and overlapping ranges are the same fitment span.
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _maybe_narrow_by_combined_year_ranges(
    triples: list[tuple[str, str, str]],
    combined_text: str,
) -> list[tuple[str, str, str]]:
    """Narrow ``triples`` by the year-range(s) found in ``combined_text``, if safe.

    Policy:
    1. Extract every (start, end) year range from the text via the canonical helper.
    2. Merge overlapping/adjacent ranges. A single merged span = a coherent fitment
       window (even if expressed as "2012, 2013, 2014, 2015" or "2012-2014 / 2015").
    3. With exactly one merged span, narrow triples to those that overlap it.
    4. With two-or-more disjoint spans, skip narrowing — the title carries multiple
       fitment windows and we can't tell which triples belong to which.
    5. If narrowing would empty the result, return the unnarrowed triples instead.
       The year token is then more likely incidental (release year, spec callout,
       "since 2002") than a fitment year. This costs some over-attribution but
       avoids regressing parts that the universal pipeline got right pre-narrowing.

    The 5 adapters with their own infer_car_for_part hooks (Steeda, Hasport,
    Perrin, Mishimoto, Driveshaftshop) bypass this entirely because they
    short-circuit infer_car_generations at the call site in crawlers/base.py.
    """
    ranges = extract_year_ranges(combined_text)
    if not ranges:
        return triples
    merged = _merge_year_ranges(ranges)
    if len(merged) != 1:
        return triples
    narrowed = narrow_triples_by_year_range(triples, merged[0])
    return narrowed if narrowed else triples


def _load_engine_platforms() -> dict:
    """Load engine_platforms_data.json and validate every fitment against CAR_GENERATIONS.

    Each fitment's (make, model, gen_name) must exist in the seed; otherwise
    the engine platform would resolve to no car_generation IDs at runtime
    and the part would fall through to is_universal=True silently. Failing
    loudly at import time is the correct trade-off — the data file is
    in-tree and any breakage means a seed/engine-data mismatch that needs
    fixing in the same PR.
    """
    import json as _json
    from importlib.resources import files as _files

    raw = _json.loads(
        _files("app.core").joinpath("engine_platforms_data.json").read_text(encoding="utf-8")
    )
    for engine_name, payload in raw.items():
        for fitment in payload.get("fitments", []):
            make = fitment["make"]
            model = fitment["model"]
            gen_name = fitment["gen_name"]
            models = CAR_GENERATIONS.get(make)
            if not models:
                raise RuntimeError(
                    f"engine_platforms[{engine_name!r}] references unknown make {make!r}"
                )
            model_entry = next((m for m in models if m["model"] == model), None)
            if model_entry is None:
                raise RuntimeError(
                    f"engine_platforms[{engine_name!r}] references unknown "
                    f"({make!r}, {model!r}) — model not in seed"
                )
            if not any(g["generation_name"] == gen_name for g in model_entry["generations"]):
                raise RuntimeError(
                    f"engine_platforms[{engine_name!r}] references unknown "
                    f"({make!r}, {model!r}, {gen_name!r}) — generation not in seed"
                )
    return raw


# Module-level: built once at import. Each entry is engine_name -> {family, displacement,
# description, phrases (list[str]), fitments (list[{make, model, gen_name}])}.
ENGINE_PLATFORMS: dict = _load_engine_platforms()

# Phrase -> engine_name lookup, sorted longest-first so "5.9l cummins" wins over "cummins".
# Phrases are all lowercase per the loader's convention.
_ENGINE_PHRASE_INDEX: list[tuple[str, str]] = sorted(
    [
        (phrase.lower(), engine_name)
        for engine_name, payload in ENGINE_PLATFORMS.items()
        for phrase in payload.get("phrases", [])
    ],
    key=lambda x: -len(x[0]),
)


def infer_car_generations_via_engine(
    name: Optional[str],
    description: Optional[str] = None,
) -> list[tuple[str, str, str]]:
    """Return car triples for parts that reference an engine platform by name.

    A title like "6.7L Cummins Boost Pipe" with no make/model token still
    has a deterministic fitment: the cars that came with that engine.
    Walks ENGINE_PLATFORMS, matches phrases against the combined
    name+description (lowercased), and returns the union of every matched
    engine's fitment list as (make, model, gen_name) triples — same shape
    that ``infer_car_generations`` returns, so callers can treat the two
    interchangeably.

    Designed as a fallback after ``infer_car_generations`` returns []. If
    a title contains both an engine name AND a make/model token (e.g.
    "Ram 2500 6.7L Cummins"), the universal pipeline already resolves it
    and this function is not consulted.
    """
    if not name and not description:
        return []
    combined = re.sub(r"\s{2,}", " ", f"{name or ''} {description or ''}".lower()).strip()
    if not combined:
        return []
    matched_engines: set[str] = set()
    for phrase, engine_name in _ENGINE_PHRASE_INDEX:
        if phrase in combined:
            matched_engines.add(engine_name)
    if not matched_engines:
        return []
    seen: set[tuple[str, str, str]] = set()
    triples: list[tuple[str, str, str]] = []
    for engine_name in matched_engines:
        for fitment in ENGINE_PLATFORMS[engine_name].get("fitments", []):
            triple = (fitment["make"], fitment["model"], fitment["gen_name"])
            if triple in seen:
                continue
            seen.add(triple)
            triples.append(triple)
    return triples


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
        car_make = db.scalars(select(CarMake).where(CarMake.name == car_make_name)).first()
        if not car_make:
            continue
        car_model = db.scalars(
            select(CarModel).where(
                CarModel.car_make_id == car_make.id,
                CarModel.name == car_model_name,
            )
        ).first()
        if not car_model:
            continue
        car_generation = db.scalars(
            select(CarGeneration).where(
                CarGeneration.car_model_id == car_model.id,
                CarGeneration.generation_name == gen_name,
            )
        ).first()
        if car_generation and car_generation.id not in seen_ids:
            seen_ids.add(car_generation.id)
            ids.append(car_generation.id)
    return ids
