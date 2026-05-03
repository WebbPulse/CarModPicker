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
        # Engine internals — Tier-2 audit (2026-05-02). The catch-all
        # ``other`` was 18.6% of the catalog because pistons, gaskets,
        # cams, valve-train, head/main/rod studs, AN fittings, and
        # silicone-hose plumbing fell through the keyword scorer. These
        # belong to the ``engine`` bucket per the catalog audit; if a
        # future ``plumbing`` category is split out, AN fittings + hoses
        # move there.
        "piston",
        "pistons",
        "piston ring",
        "i-beam",
        "h-beam",
        "head gasket",
        "gasket set",
        "oil pump",
        "oil pan",
        "oil drain",
        "oil feed",
        "camshaft",
        "camshafts",
        "cam gear",
        "cam sprocket",
        "timing chain",
        "timing belt",
        "timing kit",
        "tensioner",
        "valve spring",
        "valve springs",
        "valve retainer",
        "valve retainers",
        "valve seat",
        "valve guide",
        "pushrod",
        "lifter",
        "rocker arm",
        "main bearing",
        "rod bearing",
        "cam bearing",
        "crankshaft",
        "crank pulley",
        "cylinder head",
        "block",
        "head stud",
        "head studs",
        "main stud",
        "main studs",
        "rod stud",
        "rod studs",
        "nitrous",
        "water methanol",
        "silicone hose",
        "coupler",
        "t-bolt clamp",
        "an fitting",
        "hose end",
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
        # ``stud`` alone fires on engine head studs, ARP rod studs, exhaust
        # studs, etc. — the catalog audit (2026-05-02) found 42 BTR head-stud
        # SKUs miscategorized as "wheels" via this keyword. Restrict to the
        # wheel-specific phrases.
        "stud conversion",
        "stud conversion kit",
        "wheel stud",
        "wheel studs",
        "extended stud",
        "extended studs",
        # ``hub`` alone matches "supercharger hub", "fan hub", "Bosch ignition
        # hub" — restrict to wheel-context phrases.
        "wheel hub",
        "wheel hubs",
        "hubcentric",
        "hub centric",
        "wheel spacer",
        "wheel spacers",
        # ``spacer`` alone matches engine, suspension, and exhaust spacers —
        # the wheel-prefixed and hub-centric forms above are the unambiguous
        # wheel signal.
        "center cap",
        "centercap",
        "gram lights",
        "volk",
        "te37",
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
    "accessories": [
        # Apparel / branded swag / cosmetic + detailing supplies. Tier-2
        # audit (2026-05-02) split these out of ``other`` so the
        # catch-all reflects truly-uncategorized parts. ``accessories``
        # iterates LAST so existing categories (body, interior, etc.)
        # win on score ties — e.g. ``"GR Badge"`` keeps routing to
        # ``body`` rather than ``accessories`` because both score 3 and
        # ``body`` is encountered first in the loop. Overlap entries
        # (``decal`` / ``badge`` / ``floor mat``) are intentionally
        # duplicated; the body/interior versions still win for parts
        # whose context surfaces additional keywords from those
        # categories (door decals → body via ``door``-adjacent terms).
        "t-shirt",
        "hat",
        "cap",
        "keychain",
        "keyring",
        "lanyard",
        "decal",
        "sticker",
        "emblem",
        "badge",
        "license plate frame",
        "license plate relocator",
        "floor mat",
        "mud flap",
        "wax",
        "polish",
        "cleaner",
        "microfiber",
    ],
}

# Minimum total score to return a category; else return "other"
MIN_SCORE = 1

# Weight for matches in the part name (description weight is 1)
NAME_WEIGHT = 2

# When text contains "steering wheel(s)" or a wheel-detailing accessory phrase
# (``wheel cleaner``/``wheel polish``/``wheel wax``), don't count plain
# ``wheel``/``wheels`` toward the wheels category — the product is interior
# (steering) or accessories (detailing), not a road wheel.
STEERING_WHEEL_PHRASES = (
    "steering wheel",
    "steering wheels",
    "wheel cleaner",
    "wheel polish",
    "wheel wax",
)
WHEELS_AMBIGUOUS_KEYWORDS = frozenset({"wheel", "wheels"})

# Tier-2 audit (2026-05-02): when the engine-specific phrase ``valve spring(s)``
# is present, suppress suspension's plain ``spring``/``springs`` so a valve-train
# product doesn't tie or beat engine on score. Same pattern as the steering-wheel
# guard above.
VALVE_SPRING_PHRASES = ("valve spring", "valve springs")
SUSPENSION_AMBIGUOUS_KEYWORDS = frozenset({"spring", "springs"})

# Tier-2 audit (2026-05-02): when an accessories-specific license-plate phrase
# is present (``license plate frame``/``license plate relocator``), suppress
# body's plain ``license plate`` keyword so an apparel/accessory plate frame
# doesn't tie body on score (body would otherwise win because it iterates first).
LICENSE_PLATE_ACCESSORY_PHRASES = ("license plate frame", "license plate relocator")
BODY_AMBIGUOUS_LICENSE_KEYWORDS = frozenset({"license plate"})


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


def _score_text_suspension_aware(text: str, keywords: list[str], context: str) -> int:
    """
    Score for suspension category: exclude plain ``spring``/``springs`` when context
    contains ``valve spring(s)`` (those are valve-train → engine, not suspension).
    """
    if not text and not context:
        return _score_text(text, keywords)
    lower_context = (context or "").lower()
    if any(phrase in lower_context for phrase in VALVE_SPRING_PHRASES):
        keywords = [kw for kw in keywords if kw not in SUSPENSION_AMBIGUOUS_KEYWORDS]
    return _score_text(text, keywords)


def _score_text_body_aware(text: str, keywords: list[str], context: str) -> int:
    """
    Score for body category: exclude plain ``license plate`` when context contains a
    more-specific accessories phrase (``license plate frame``/``license plate relocator``).
    """
    if not text and not context:
        return _score_text(text, keywords)
    lower_context = (context or "").lower()
    if any(phrase in lower_context for phrase in LICENSE_PLATE_ACCESSORY_PHRASES):
        keywords = [kw for kw in keywords if kw not in BODY_AMBIGUOUS_LICENSE_KEYWORDS]
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
        elif category == "suspension":
            name_score = _score_text_suspension_aware(name, keywords, combined) * NAME_WEIGHT
            desc_score = _score_text_suspension_aware(description, keywords, combined)
        elif category == "body":
            name_score = _score_text_body_aware(name, keywords, combined) * NAME_WEIGHT
            desc_score = _score_text_body_aware(description, keywords, combined)
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
