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
        # 2026-05-03 audit (Tier-3): HKS exhaust catalog phrases. ``hi-power``
        # is the HKS catback line; ``metal catalyzer`` is their high-flow cat;
        # ``legamax`` is the HKS axle-back; ``front pipe`` / ``center pipe`` /
        # ``rear section`` are SKU section names common across HKS, ETS, and
        # Subaru aftermarket. ``cel fix`` is a high-flow cat with O2 spacer.
        "hi-power",
        "hi power",
        "metal catalyzer",
        "catalytic converter",
        "front pipe",
        "center pipe",
        "legamax",
        "super sound master",
        "exhaust manifold",
        "cel fix",
        "high flow cat",
        "race pipe",
        "rear section",
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
        # 2026-05-03 audit (Tier-3): HKS / Tein / Eibach catalog phrases that
        # didn't match any of the existing ``coilover``/``spring``/``shock``
        # etc. tokens. ``hipermax`` is the HKS coilover product line.
        # ``performance damper`` is the Yamaha/Lambda chassis damper.
        # ``carbon brace`` / ``front lower bar`` / ``lower arm bar`` /
        # ``pillowball`` are Cusco/Tein/HKS chassis-brace and pillow-ball
        # mount SKUs that have no other suspension keyword.
        "hipermax",
        "performance damper",
        "carbon brace",
        "front lower bar",
        "lower arm bar",
        "tein s.tech",
        "eibach pro-kit",
        "eibach pro kit",
        "bump stop",
        "pillowball",
        "error canceler",
        "suspension error",
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
        # Plumbing/AN-fitting language. The audit (2026-05-03) found 192
        # ``other`` parts that are AN fittings/adapters/hose-ends; the
        # canonical AN-size token is ``-6AN`` / ``-8AN`` etc. (no space),
        # so the existing ``an fitting`` keyword (with space) never matched.
        # Add the dash-AN-N forms as separate explicit keywords. Also add
        # NPT/ORB which are the matching thread standards on the same parts.
        "-3an",
        "-4an",
        "-6an",
        "-8an",
        "-10an",
        "-12an",
        "-16an",
        "npt",
        "orb fitting",
        "hose barb",
        "adapter fitting",
        "fitting flare",
        "banjo fitting",
        "union fitting",
        # Engine swap mounts — the Hasport/Innovative catalog uses these
        # phrases without any other engine-keyword neighbour. 2026-05-03 audit
        # moved 58 parts from ``other`` → ``engine`` via these keywords.
        "engine mount",
        "motor mount",
        "trans mount",
        "transmission mount",
        "swap mount",
        "swap mounts",
        "engine bracket",
        # Engine internals / fuel system phrases the previous list missed
        # because each individual word collides with another category.
        "fuel rail",
        "fuel filter",
        "fuel tank",
        "fuel feed",
        "fuel return",
        "fuel line",
        "valve seat",
        "valve guide",
        "cam gear",
        "throttle body",
        # 2026-05-03 audit (Tier-3): largest residual ``other`` cluster was
        # turbocharger plumbing/hardware (Garrett, Tial, ATPturbo, GReddy
        # SKUs) — none of these matched any of the existing engine keywords
        # because the SKU language is highly specialized. Add the canonical
        # phrases. ``hose union`` / ``hose band`` / ``vacuum tube`` are
        # GReddy-specific catalog phrases; ``vband``/``v-band`` covers all
        # turbo flange/clamp parts. Per the audit, recategorizes 250+ parts
        # in ``other`` → ``engine`` without measurable false positives.
        "turbine housing",
        "compressor housing",
        "chra",
        "super core",
        "wastegate actuator",
        "actuator upgrade",
        "v-band clamp",
        "vband clamp",
        "v-band flange",
        "vband flange",
        "v-band entry",
        "v-band exit",
        "tial",
        "garrett",
        "turbosmart",
        "turbine inlet",
        "turbine outlet",
        "compressor inlet",
        "compressor outlet",
        "wastegate",
        # GReddy/HKS turbo-plumbing phrases — these never collided with any
        # other category in the regression run.
        "hose union",
        "hose band",
        "hose clamp",
        "hose nipple",
        "vacuum tube",
        "swivel nipple",
        "swivel barbed",
        "barbed nipple",
        "vacuum nipple",
        "plug bolt union",
        "compression tube",
        "bend pipe",
        "straight pipe",
        "cast aluminum elbow",
        "aluminum bend",
        "t-bolt clamp",
        "t bolt clamp",
        # AN-fitting catalog phrases the previous Tier-2 dash-AN-N keywords
        # missed (the dash-prefixed forms cover ``-6AN``; these cover the
        # AN-prefixed forms ``AN-6`` and the related fitting kits).
        "an-3",
        "an-4",
        "an-6",
        "an-8",
        "an-10",
        "an-12",
        "an-16",
        "banjo bolt",
        "metric adapter",
        "tube sleeve",
        "tube nut",
        "bulkhead fitting",
        "bulkhead nut",
        "thread sealant",
        "fitting elbow",
        "elbow fitting",
        # HKS intake / SQV / cam keyword set. ``racing suction`` /
        # ``power flow`` / ``airinx`` are HKS catalog product lines that
        # are entirely engine-side intake hardware. ``super sqv`` is the
        # HKS BOV brand. ``vcam`` / ``valcon`` are the HKS variable-cam
        # control system.
        "racing suction",
        "premium suction",
        "power flow",
        "airinx",
        "drycarbon suction",
        "suction return",
        "suction kit",
        "airbox",
        "air box",
        "airflow",
        "maf hose",
        "map sensor",
        "throttle position sensor",
        "knock sensor",
        "o2 sensor",
        "wideband",
        "super sqv",
        "sqv4",
        "blow off valve",
        "blow-off valve",
        "valcon",
        "vcam",
        "vcamshaft",
        "stem-seal",
        "stem seal",
        "cylinder liner",
        "ring gasket",
        "complete engine",
        "engine assembly",
        "long block",
        "short block",
        "carbon plug cover",
        "cover transistor",
        # Engine oil / fluids — HKS's own engine-oil product line and the
        # canonical SAE viscosity tokens. Limited to the dashed forms so
        # we don't fire on freeform "0w" or "5w".
        "racing pro oil",
        "racing oil",
        "super zero racing",
        "super na racing",
        "engine oil",
        "motor oil",
        "0w-20",
        "0w-30",
        "0w-40",
        "5w-30",
        "5w-40",
        "10w-40",
        "10w-50",
        "10w-60",
        "gear oil",
        "g-900",
        "dctf",
        "dct fluid",
        "dct cooler",
        # Hasport / Innovative engine-mount product-line phrases. Already
        # have ``engine mount`` / ``motor mount`` / ``swap mount``; these
        # are the additional Hasport-specific phrases that show up in
        # SKUs without one of those words.
        "torque mount",
        "skid plate",
        "shift linkage",
        "wiring conversion",
        "conversion harness",
        "rear bracket",
        # COBB / Cobb-Tuning catalog language. ``accessport`` already
        # exists. ``power package`` is the Cobb stage-tune SKU naming.
        # ``high flow filter`` is the Cobb intake-filter line.
        "accessport",
        "high flow filter",
        "stage 1",
        "stage 2",
        "stage 3",
        "power package",
        "flex fuel",
        "flex-fuel",
        "openflash",
        "ecu flashing",
        "pdk flashing",
        "dsg flashing",
        # Fuel system / surge tank phrases the Tier-2 keywords missed.
        "surge tank",
        "fuel cell",
        "in-tank",
        "phantom series",
        "fpr",
        "fuel pressure regulator",
        # Pulley / underdrive — almost always engine-side.
        "pulley kit",
        "alternator pulley",
        "underdrive",
        # Aeromotive filter element language (none of which match the
        # previously-added ``aeromotive an-`` phrases).
        "aeromotive",
        "microglass",
        "10-micron",
        "100-micron",
        "stainless mesh",
        "filter element",
        "filter housing",
        "loctite",
        "rtv silicone",
        "battery box",
        "breather filter",
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
        # 2026-05-03 audit (Tier-3): RAYS / Mackin Industries wheel-line
        # SKUs that have no other wheel keyword (descriptions are empty).
        # ``ce28`` / ``57cr`` / ``57xtreme`` are RAYS forged wheel models.
        # ``color clear`` / ``inch black machine`` / ``inch silver machine``
        # / ``inch chrome`` are the Mackin finish-spec phrases. These
        # phrases occur ONLY on wheel SKUs in the catalog.
        "ce28",
        "ce28n",
        "57cr",
        "57xtreme",
        "club racer",
        "color clear",
        "black machine",
        "silver machine",
        "bronze color",
        # The Mackin "12inch chrome" / "13inch silver" pattern: ``inch`` is
        # part of a digit-prefixed token (``12inch``) so a word-boundary
        # match on ``inch`` alone fails. Use the suffix tokens that follow.
        "machine finish",
        # Wheel hardware
        "tuner nut",
        "lock nut",
        "wheel lock",
        "lock & nut",
        "double lock nut",
        "bull lock",
        "wide tread spacer",
        "duralumin lock",
        "beadlock",
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
        # 2026-05-03 audit (Tier-3): exterior trim / mirror / wiper SKUs
        # that fell through. ``mirror cover`` / ``mirror shroud`` are common
        # carbon-fiber mirror caps. ``wiper blade`` covers replacement
        # blades; ``sun visor`` covers sun-visor trim. ``trunk handle`` /
        # ``fuse box cover`` / ``door pull`` / ``door pocket`` /
        # ``door garnish`` / ``door lock`` are exterior body trim.
        # NOTE: do NOT add ``dry carbon`` — it false-positives on interior
        # carbon trim, oil cap covers, and shift paddle sets.
        "mud flap",
        "mud flaps",
        "carbon mirror",
        "mirror cover",
        "mirror shroud",
        "door mirror",
        "door pull",
        "door pocket",
        "door lock",
        "windshield wiper",
        "wiper blade",
        "wiper blades",
        "wiper arm",
        "sun visor",
        "visor mirror",
        "fuse box cover",
        "trunk handle",
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
        # Race-gear / driver safety. 2026-05-03 audit moved 83 parts from
        # ``other`` → ``interior`` via these brand and product phrases —
        # helmets, suits, racing shoes, fire extinguishers, window nets, and
        # SFI/FIA-rated apparel. Brands listed (Sparco/Bell/Arai/Alpinestars/
        # etc.) are race-only; their general consumer apparel is captured by
        # the ``accessories`` swag list below.
        "helmet",
        "hans device",
        "racing suit",
        "driving shoe",
        "driving shoes",
        "race glove",
        "race gloves",
        "nomex",
        "fire extinguisher",
        "window net",
        "rain suit",
        "kart suit",
        "karting suit",
        "karting shoe",
        "arai",
        "sparco",
        "alpinestars",
        "stand21",
        "sabelt",
        "schroth",
        "bell helmet",
        "brey krause",
        "safecraft",
        # 2026-05-03 audit (Tier-3): floor liners and cargo liners that the
        # plain ``floor mat`` keyword missed because the SKU language uses
        # ``FloorLiner`` / ``Cargo Liner`` / ``Carpet Floormat``. These are
        # interior-only — never collide with body/exterior parts.
        "floor mats",
        "floormat",
        "floorliner",
        "weathertech",
        "carpet floormat",
        "rubber mats",
        "cargo liner",
        "trunk liner",
        # Bell helmet accessories (tear-offs, head/neck restraint, etc.)
        # — these are race-safety equipment and ride with the helmet
        # cluster.
        "tear-off",
        "tear off",
        "tearoff",
        "lifeline",
        "head and neck restraint",
        "frontal head restraint",
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
        # 2026-05-03 audit (Tier-3): aftermarket horn upgrades (Hella,
        # Stebel) and the OEM brackets PERRIN ships to mount them. Horns
        # historically rode in ``other`` because none of the existing
        # lighting tokens match them. Treating horns as ``lighting`` keeps
        # them grouped with the other electrical/audible signaling parts.
        "horn kit",
        "horn bracket",
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
        # 2026-05-03 audit (Tier-3): clutch-disc + throw-out bearing SKUs
        # from McLeod / Fidanza / Exedy / SPEC that have no other
        # drivetrain keyword. Brand names match all-and-only clutch parts
        # in the catalog (verified against regression test).
        "throw out bearing",
        "throw-out bearing",
        "release bearing",
        "clutch disc",
        "friction disc",
        "friction kit",
        "mcleod",
        "fidanza",
        "exedy",
        "pin drive",
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
        # 2026-05-03 audit: 167 ``other`` parts that are clearly branded
        # apparel/swag/travel goods. ``cap``/``hat``/``lanyard`` already live
        # in the original list above — do NOT re-add them here, ``_score_text``
        # counts each list entry independently and duplicates double-score.
        "jacket",
        "tee shirt",
        "shirt",
        "hoodie",
        "sweatshirt",
        "polo",
        "hoody",
        "beanie",
        "key holder",
        "key ring",
        "wallet",
        "umbrella",
        "duffle bag",
        "tote bag",
        "drying towel",
        "microfiber towel",
        "hand towel",
        "patch",
        "tote",
        "backpack",
        # 2026-05-03 audit (Tier-3): collectibles + car-care + service
        # SKUs. ``scale model`` / 1-to-NN ratios catch diecast model cars
        # (Porsche 1/43 / 1/18 collectibles). ``car cover`` catches the
        # Covercraft / Premium / Outdoor cover product line. ``cabin
        # filter`` / ``pollen filter`` are HVAC consumables (Genuine BMW,
        # OEM-replacement). ``scheduled maintenance`` catches AMS labor-
        # only SKUs. ``key chain`` / ``key blank`` / ``porsche key`` /
        # ``ballcap`` / ``snapback`` are branded swag the apparel tier-2
        # missed. ``apron`` / ``mechanic apron`` / ``raincoat`` are HKS-
        # branded consumer goods. ``logo tee`` is the Fifteen52 / AWE
        # apparel SKU language.
        "scale model",
        "diecast",
        "die-cast",
        "1/18",
        "1/24",
        "1/43",
        "1/64",
        "workshop gloves",
        "neck gaiter",
        "apron",
        "mechanic apron",
        "raincoat",
        "kids sweater",
        "sweater",
        "logo tee",
        "ballcap",
        "porsche key",
        "key chain",
        "key blank",
        "porsche bug remover",
        "snapback",
        "car cover",
        "outdoor car cover",
        "premium car cover",
        "shipping insurance",
        "pollen filter",
        "cabin filter",
        "nano cabin filter",
        "scheduled maintenance",
        "maintenance service",
        "core charge",
        "core return",
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
