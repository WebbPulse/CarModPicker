"""
Infer part category from name and description using keyword scoring.

Used by the crawler (and can be used by the API) to assign a category when
one isn't explicitly provided. Returns a category name from PART_CATEGORIES;
low confidence falls back to "other".
"""

import re
from typing import Optional

# Keywords per category (lowercase). Word-boundary match so "pad" matches "brake pad" not "padding".
# Order of categories here does not affect result; best score wins.
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "exhaust": [
        "exhaust",
        "muffler",
        "header",
        "headers",
        "downpipe",
        "down pipe",
        "cat-back",
        "catback",
        "axle-back",
        "axle back",
        "midpipe",
        "mid pipe",
        "tip",
        "exhaust tip",
        "resonator",
        "resonated",
        "non-resonated",
        "y-pipe",
        "x-pipe",
        "turbo back",
        "touring edition",
        "track edition",
        "conversion kit",
    ],
    "suspension": [
        "coilover",
        "coilovers",
        "coil over",
        "coil-over",
        "spring",
        "springs",
        "strut",
        "struts",
        "shock",
        "shocks",
        "sway bar",
        "swaybar",
        "stabilizer",
        "control arm",
        "camber",
        "lowering",
        "lowered",
        "bushing",
        "bushings",
        "end link",
        "tie rod",
        "tie rods",
        "trailing arm",
        "rear trailing arm",
        "chassis brace",
        "power brace",
        "brace bar",
        "underbody",
        "subframe brace",
        "chassis",
        "front brace",
        "rear brace",
        "damping",
        "damping delete",
        "electronic damping",
        "electronic damping delete",
        "error canceller",
    ],
    "engine": [
        "turbo",
        "turbocharger",
        "supercharger",
        "intake",
        "cold air",
        "cai",
        "air filter",
        "intercooler",
        "blow-off",
        "bov",
        "wastegate",
        "tune",
        "ecu",
        "piggyback",
        "obd",
        "obd2",
        "obdii",
        "flash adapter",
        "flash tuning",
        "downpipe",
        "header",
        "injector",
        "injectors",
        "fuel injector",
        "fuel pump",
        "fuel line",
        "lpfp",
        "oil cooler",
        "oil cap",
        "fluid cap",
        "reservoir cap",
        "radiator",
        "charge pipe",
        "chargepipe",
        "catch can",
        "coolant",
        "auxiliary radiator",
        "engine cover",
        "valve cover",
        "rocker cover",
        "dme",
        "fuel pressure",
        "fuel pressure gauge",
        "ignition coil",
        "coil pack",
        "spark plug",
        "boost tap",
        "vacuum line",
        "vacuum tubing",
        "tubing kit",
        "charge air",
        "trans cooler",
        "dct cooler",
        "transmission cooler",
        "throttle booster",
        "engine bay",
        "oil change",
        "oil change kit",
        "pre-filter",
        "prefilters",
        "filter replacement",
        "intake muffler",
        "intake resonator",
        "connecting rod",
        "rod set",
        "washer fluid",
        "washer fluid cap",
        "retaining kit",
    ],
    "wheels": [
        "wheel",
        "wheels",
        "rim",
        "rims",
        "tire",
        "tires",
        "tyre",
        "tyres",
        "lug",
        "lug nut",
        "lug bolt",
        "lug bolts",
        "stud",
        "stud conversion",
        "stud conversion kit",
        "hub",
        "hubcentric",
        "spacer",
        "center cap",
        "gram lights",
        "volk",
        "te37",
        "work",
        "enkei",
        "bbs",
        "rotiform",
    ],
    "body": [
        "body kit",
        "bodykit",
        "spoiler",
        "wing",
        "splitter",
        "lip",
        "diffuser",
        "bumper",
        "fender",
        "hood",
        "aero",
        "aerodynamic",
        "side skirt",
        "widebody",
        "wide body",
        "grille",
        "grill",
        "carbon fiber",
        "cf ",
        "door garnish",
        "garnish",
        "decal",
        "decals",
        "tow hook",
        "license plate",
        "relocate bracket",
        "roof spoiler",
        "dive plane",
        "canard",
        "canards",
        "wind buffeting",
        "buffeting",
        "badge",
        "rock guard",
        "rock guards",
        "rocker",
        "rocker extension",
        "side rocker",
    ],
    "interior": [
        "seat",
        "seats",
        "steering wheel",
        "steering wheels",
        "shift knob",
        "shifter",
        "shift paddle",
        "shift paddles",
        "paddle shift",
        "harness",
        "harness bar",
        "roll bar",
        "rollbar",
        "cage",
        "floor mat",
        "pedal",
        "gauge",
        "cluster",
        "interior",
        "trim",
        "alcantara",
        "bucket seat",
        "switch panel",
        "door switch panel",
        "storage compartment",
        "compartment cover",
        "console lid",
        "armrest",
        "door sill",
        "sill cover",
        "center console",
        "speaker cover",
    ],
    "brakes": [
        "brake",
        "brakes",
        "pad",
        "pads",
        "rotor",
        "rotors",
        "caliper",
        "calipers",
        "brake line",
        "brakeline",
        "brake fluid",
        "bbk",
        "big brake",
        "slotted",
        "drilled",
        "stainless line",
        "brake kit",
    ],
    "lighting": [
        "headlight",
        "headlights",
        "headlamp",
        "taillight",
        "taillights",
        "tail light",
        "tail lamp",
        "reverse light",
        "fog light",
        "fog lights",
        "fog lamp",
        "drl",
        "daytime running",
        "led",
        "hid",
        "light bar",
        "lightbar",
        "turn signal",
        "marker light",
        "lighting",
        "lamp",
        "bulb",
        "halo",
        "angel eye",
        "grille light",
        "reflector",
        "reflectors",
        "light cover",
        "light covers",
    ],
    "drivetrain": [
        "differential",
        "diff",
        "diffs",
        "driveshaft",
        "drive shaft",
        "axle",
        "axles",
        "clutch",
        "flywheel",
        "transmission",
        "trans",
        "shaft",
        "cv joint",
        "driveline",
        "prop shaft",
        "half shaft",
        "lsd",
        "locker",
        "short shift",
        "short shift kit",
        "shift kit",
    ],
}

# Minimum total score to return a category; else return "other"
MIN_SCORE = 1

# Weight for matches in the part name (description weight is 1)
NAME_WEIGHT = 2

# When text contains "steering wheel(s)", don't count "wheel"/"wheels" toward wheels category
STEERING_WHEEL_PHRASES = ("steering wheel", "steering wheels")
WHEELS_AMBIGUOUS_KEYWORDS = frozenset({"wheel", "wheels"})


def _score_text(text: str, keywords: list[str]) -> int:
    """Count keyword matches (word-boundary) in text. Each keyword counts at most once."""
    if not text or not keywords:
        return 0
    lower = text.lower()
    count = 0
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", lower):
            count += 1
    return count


def _score_text_wheels_aware(text: str, keywords: list[str], context: str) -> int:
    """
    Score for wheels category: exclude 'wheel'/'wheels' when context (e.g. name+description)
    clearly refers to steering wheel (e.g. "steering wheels shift paddles") so those go to interior.
    """
    if not text and not context:
        return _score_text(text, keywords)
    lower_context = (context or "").lower()
    if any(phrase in lower_context for phrase in STEERING_WHEEL_PHRASES):
        keywords = [kw for kw in keywords if kw not in WHEELS_AMBIGUOUS_KEYWORDS]
    return _score_text(text, keywords)


def infer_category(
    name: Optional[str],
    description: Optional[str],
) -> Optional[str]:
    """
    Infer part category from name and description using keyword scoring.

    Returns a category name (e.g. "wheels", "exhaust") when confidence is high enough,
    or "other" when the best score is below MIN_SCORE. Returns None only when both
    name and description are empty/missing (caller should use default category).
    """
    name = (name or "").strip()
    description = (description or "").strip()
    if not name and not description:
        return None

    best_name: Optional[str] = None
    best_score = -1
    combined = f"{name} {description}"

    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == "wheels":
            name_score = _score_text_wheels_aware(name, keywords, combined) * NAME_WEIGHT
            desc_score = _score_text_wheels_aware(description, keywords, combined)
        else:
            name_score = _score_text(name, keywords) * NAME_WEIGHT
            desc_score = _score_text(description, keywords)
        total = name_score + desc_score
        if total > best_score:
            best_score = total
            best_name = category

    if best_name is None or best_score < MIN_SCORE:
        return "other"
    return best_name
