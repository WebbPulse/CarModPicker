"""Sample global Part creator + retailer/price-history seeding for the debug part."""

import random
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.models.category import Category  # pyright: ignore[reportMissingImports]
from app.api.models.part import Part  # pyright: ignore[reportMissingImports]
from app.api.models.part_price_history import (  # pyright: ignore[reportMissingImports]
    PartPriceHistory,
)
from app.api.models.retailer import Retailer  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]
from app.api.services.part_listing_service import (  # pyright: ignore[reportMissingImports]
    create_or_update_listing_and_price,
    get_or_create_curated_part_manufacturer,
    get_or_create_retailer,
)

from ._logging import log_info, log_progress, log_section


def _ensure_sample_retailers(db: Session) -> list[Retailer]:
    """Ensure fake retailers exist for sample data; return list of retailers."""
    fake_retailers = [
        {
            "name": "Summit Racing",
            "domain": "summitracing.com",
            "base_url": "https://www.summitracing.com",
        },
        {
            "name": "A90Shop",
            "domain": "a90shop.com",
            "base_url": "https://www.a90shop.com",
        },
        {
            "name": "Tire Rack",
            "domain": "tirerack.com",
            "base_url": "https://www.tirerack.com",
        },
        {
            "name": "RockAuto",
            "domain": "rockauto.com",
            "base_url": "https://www.rockauto.com",
        },
        {
            "name": "AutoZone",
            "domain": "autozone.com",
            "base_url": "https://www.autozone.com",
        },
        {
            "name": "Advance Auto Parts",
            "domain": "advanceautoparts.com",
            "base_url": "https://www.advanceautoparts.com",
        },
        {"name": "JEGS", "domain": "jegs.com", "base_url": "https://www.jegs.com"},
        {
            "name": "ECS Tuning",
            "domain": "ecstuning.com",
            "base_url": "https://www.ecstuning.com",
        },
        {
            "name": "FCP Euro",
            "domain": "fcpeuro.com",
            "base_url": "https://www.fcpeuro.com",
        },
        {
            "name": "ModAuto",
            "domain": "modauto.com",
            "base_url": "https://www.modauto.com",
        },
    ]
    retailers = []
    for r in fake_retailers:
        retailer = get_or_create_retailer(
            db, r["name"], domain=r.get("domain"), base_url=r.get("base_url")
        )
        retailers.append(retailer)
    db.commit()
    for retailer in retailers:
        db.refresh(retailer)
    return retailers


def create_sample_global_parts(
    db: Session, users: list[User], categories: list[Category]
) -> list[Part]:
    """Create sample global parts (refactored: part_manufacturer_id, no price; prices via PartListing)."""
    start_time = time.time()
    log_section("Creating sample global parts...")

    # Collect all part_manufacturer names we use, then get-or-create part_manufacturers and build part_manufacturer_id map
    initial_part_manufacturer_names = [
        "AWE",
        "KW",
        "Garrett",
        "Rays",
        "APR",
        "Recaro",
        "Brembo",
        "Injen",
        "HKS",
        "Ohlins",
    ]
    part_manufacturer_map: dict[str, int] = {}
    for name in initial_part_manufacturer_names:
        part_manufacturer = get_or_create_curated_part_manufacturer(db, name)
        if part_manufacturer:
            part_manufacturer_map[name] = part_manufacturer.id
    db.commit()

    # Initial parts: use part_manufacturer_id, no price/part_manufacturer (price comes from PartListing later)
    initial_parts_raw = [
        {
            "name": "AWE Touring Exhaust System",
            "description": "High-quality cat-back exhaust system with deep, aggressive tone",
            "category_id": categories[0].id,
            "user_id": users[1].id,
            "part_manufacturer": "AWE",
            "part_number": "AWE-EXH-001",
            "specifications": {
                "material": "stainless_steel",
                "tips": 4,
                "sound_level": "moderate",
            },
            "is_verified": True,
        },
        {
            "name": "KW V3 Coilover Kit",
            "description": "Premium adjustable coilover suspension system",
            "category_id": categories[1].id,
            "user_id": users[2].id,
            "part_manufacturer": "KW",
            "part_number": "KW-SUS-001",
            "specifications": {
                "adjustable": True,
                "damping": "adjustable",
                "lowering": "30-50mm",
            },
            "is_verified": True,
        },
        {
            "name": "Garrett GT2860RS Turbocharger",
            "description": "High-performance turbocharger for increased power",
            "category_id": categories[2].id,
            "user_id": users[3].id,
            "part_manufacturer": "Garrett",
            "part_number": "GAR-TUR-001",
            "specifications": {"max_boost": "25psi", "compressor": "dual_ball_bearing"},
            "is_verified": True,
        },
        {
            "name": "Volk TE37 Wheels",
            "description": "Lightweight forged wheels, 18x9.5 +22",
            "category_id": categories[3].id,
            "user_id": users[1].id,
            "part_manufacturer": "Rays",
            "part_number": "VOLK-TE37-001",
            "specifications": {"size": "18x9.5", "offset": "+22", "weight": "18.5lbs"},
            "is_verified": True,
        },
        {
            "name": "APR Carbon Fiber Wing",
            "description": "Large carbon fiber rear wing for downforce",
            "category_id": categories[4].id,
            "user_id": users[4].id,
            "part_manufacturer": "APR",
            "part_number": "APR-AERO-001",
            "specifications": {"material": "carbon_fiber", "adjustable": True},
            "is_verified": False,
        },
        {
            "name": "Recaro Sportster CS Seats",
            "description": "Premium sport seats with heating",
            "category_id": categories[5].id,
            "user_id": users[2].id,
            "part_manufacturer": "Recaro",
            "part_number": "REC-INT-001",
            "specifications": {"heated": True, "adjustable": True},
            "is_verified": True,
        },
        {
            "name": "Brembo GT Big Brake Kit",
            "description": "6-piston front brake kit with slotted rotors",
            "category_id": categories[6].id,
            "user_id": users[3].id,
            "part_manufacturer": "Brembo",
            "part_number": "BRE-BRK-001",
            "specifications": {
                "pistons": 6,
                "rotor_size": "380mm",
                "caliper_color": "red",
            },
            "is_verified": True,
        },
        {
            "name": "Injen Cold Air Intake",
            "description": "High-flow cold air intake system",
            "category_id": categories[2].id,
            "user_id": users[1].id,
            "part_manufacturer": "Injen",
            "part_number": "INJ-INT-001",
            "specifications": {"filter_type": "dry", "material": "aluminum"},
            "is_verified": True,
        },
        {
            "name": "HKS Hi-Power Exhaust",
            "description": "JDM-style exhaust with titanium tips",
            "category_id": categories[0].id,
            "user_id": users[4].id,
            "part_manufacturer": "HKS",
            "part_number": "HKS-EXH-001",
            "specifications": {"material": "titanium", "tips": 2},
            "is_verified": True,
        },
        {
            "name": "Ohlins Road & Track Coilovers",
            "description": "Premium Swedish coilover system",
            "category_id": categories[1].id,
            "user_id": users[1].id,
            "part_manufacturer": "Ohlins",
            "part_number": "OHL-SUS-001",
            "specifications": {"adjustable": True, "damping": "dual_flow_valve"},
            "is_verified": True,
        },
    ]
    initial_parts = []
    for p in initial_parts_raw:
        part_manufacturer_id = part_manufacturer_map.get(p["part_manufacturer"])
        if part_manufacturer_id is None:
            b = get_or_create_curated_part_manufacturer(db, p["part_manufacturer"])
            if b:
                part_manufacturer_map[p["part_manufacturer"]] = b.id
                part_manufacturer_id = b.id
        if part_manufacturer_id is not None:
            part_data = {k: v for k, v in p.items() if k != "part_manufacturer"}
            part_data["part_manufacturer_id"] = part_manufacturer_id
            initial_parts.append(part_data)

    # Part templates for each category
    part_templates = {
        "exhaust": {
            "names": [
                "Exhaust System",
                "Cat-Back Exhaust",
                "Axle-Back Exhaust",
                "Headers",
                "Downpipe",
                "Muffler",
            ],
            "part_manufacturers": [
                "AWE",
                "HKS",
                "Invidia",
                "Borla",
                "Magnaflow",
                "Greddy",
                "Tanabe",
            ],
            "descriptions": [
                "High-performance exhaust system with aggressive tone",
                "Stainless steel exhaust for durability",
                "Lightweight titanium exhaust system",
                "Race-inspired exhaust with maximum flow",
            ],
            "price_range": (299, 2499),
        },
        "suspension": {
            "names": [
                "Coilover Kit",
                "Lowering Springs",
                "Strut Bar",
                "Sway Bar",
                "Shock Absorbers",
                "Control Arms",
            ],
            "part_manufacturers": [
                "KW",
                "Ohlins",
                "Bilstein",
                "Eibach",
                "Tein",
                "BC Racing",
                "Fortune Auto",
            ],
            "descriptions": [
                "Premium adjustable suspension system",
                "Track-tuned suspension components",
                "Street performance suspension upgrade",
                "Rally-tested suspension parts",
            ],
            "price_range": (199, 3999),
        },
        "engine": {
            "names": [
                "Turbocharger",
                "Cold Air Intake",
                "Intercooler",
                "ECU Tune",
                "Supercharger",
                "Throttle Body",
            ],
            "part_manufacturers": ["Garrett", "Injen", "Cobb", "HKS", "Blitz", "Greddy", "APR"],
            "descriptions": [
                "High-performance engine upgrade",
                "Maximum power enhancement",
                "Reliable engine modification",
                "Race-proven engine component",
            ],
            "price_range": (299, 4999),
        },
        "wheels": {
            "names": [
                "Forged Wheels",
                "Alloy Wheels",
                "Track Wheels",
                "Street Wheels",
                "Racing Wheels",
            ],
            "part_manufacturers": ["Rays", "Work", "Enkei", "Volk", "WedsSport", "Rota", "Konig"],
            "descriptions": [
                "Lightweight forged wheel set",
                "Premium alloy wheels",
                "Track-focused wheel design",
                "Street performance wheels",
            ],
            "price_range": (799, 5499),
        },
        "body": {
            "names": [
                "Carbon Fiber Wing",
                "Front Splitter",
                "Side Skirts",
                "Rear Diffuser",
                "Hood",
                "Fenders",
            ],
            "part_manufacturers": ["APR", "Seibon", "VIS", "Carbon Creations", "Verus", "Aeroflow"],
            "descriptions": [
                "Aerodynamic carbon fiber component",
                "Lightweight body modification",
                "Track-inspired aerodynamic part",
                "Street performance body upgrade",
            ],
            "price_range": (199, 2999),
        },
        "interior": {
            "names": [
                "Sport Seats",
                "Steering Wheel",
                "Shift Knob",
                "Pedals",
                "Gauges",
                "Harness",
            ],
            "part_manufacturers": ["Recaro", "Sparco", "Bride", "MOMO", "NRG", "Takata"],
            "descriptions": [
                "Premium sport interior component",
                "Race-inspired interior upgrade",
                "Comfortable performance interior",
                "Lightweight interior modification",
            ],
            "price_range": (99, 2999),
        },
        "brakes": {
            "names": [
                "Big Brake Kit",
                "Brake Pads",
                "Rotted Rotors",
                "Brake Lines",
                "Caliper Upgrade",
            ],
            "part_manufacturers": ["Brembo", "StopTech", "Wilwood", "EBC", "Hawk", "Carbotech"],
            "descriptions": [
                "High-performance brake system",
                "Track-tested brake components",
                "Street performance brake upgrade",
                "Maximum stopping power",
            ],
            "price_range": (199, 4999),
        },
    }

    # Ensure all template part_manufacturers exist for generated parts
    all_template_part_manufacturers = set()
    for template in part_templates.values():
        all_template_part_manufacturers.update(template["part_manufacturers"])
    for name in all_template_part_manufacturers:
        if name not in part_manufacturer_map:
            b = get_or_create_curated_part_manufacturer(db, name)
            if b:
                part_manufacturer_map[name] = b.id
    db.commit()

    parts_data = initial_parts.copy()

    # Generate additional parts to reach 2500 total (to test pagination with limit=1000)
    for i in range(2490):  # 2490 more to reach 2500 total
        category = random.choice(categories)
        category_name = category.name
        template = part_templates.get(category_name, part_templates["exhaust"])

        name_base = random.choice(template["names"])
        part_manufacturer_name = random.choice(template["part_manufacturers"])
        part_manufacturer_id = part_manufacturer_map.get(part_manufacturer_name)
        if part_manufacturer_id is None:
            b = get_or_create_curated_part_manufacturer(db, part_manufacturer_name)
            if b:
                part_manufacturer_map[part_manufacturer_name] = b.id
                part_manufacturer_id = b.id
        if part_manufacturer_id is None:
            continue

        name = (
            f"{part_manufacturer_name} {name_base} {i+1}"
            if i < 30
            else f"{name_base} {part_manufacturer_name} Edition {i+1}"
        )
        description = random.choice(template["descriptions"])
        user = random.choice(users)
        is_verified = random.choice([True, True, True, False])  # 75% verified

        part_number = (
            f"{part_manufacturer_name[:3].upper()}-{category_name[:3].upper()}-{i+100:03d}"
        )

        # Generate specifications based on category
        specs = {}
        if category_name == "exhaust":
            specs = {
                "material": random.choice(["stainless_steel", "titanium", "aluminum"]),
                "tips": random.randint(1, 4),
            }
        elif category_name == "suspension":
            specs = {
                "adjustable": random.choice([True, False]),
                "lowering": f"{random.randint(20, 60)}mm",
            }
        elif category_name == "engine":
            specs = (
                {"power_gain": f"{random.randint(10, 100)}hp"}
                if random.choice([True, False])
                else {}
            )
        elif category_name == "wheels":
            size = random.choice(["17x8", "18x9", "18x9.5", "19x10", "20x11"])
            specs = {
                "size": size,
                "offset": f"+{random.randint(15, 35)}",
                "weight": f"{random.randint(15, 25)}lbs",
            }
        elif category_name == "body":
            specs = {
                "material": random.choice(
                    ["carbon_fiber", "fiberglass", "polyurethane"]
                ),
                "adjustable": random.choice([True, False]),
            }
        elif category_name == "interior":
            specs = {"adjustable": random.choice([True, False])}
        elif category_name == "brakes":
            specs = {
                "pistons": random.choice([4, 6, 8]),
                "rotor_size": f"{random.randint(330, 400)}mm",
            }

        parts_data.append(
            {
                "name": name,
                "description": description,
                "category_id": category.id,
                "user_id": user.id,
                "part_manufacturer_id": part_manufacturer_id,
                "part_number": part_number,
                "specifications": specs,
                "is_verified": is_verified,
            }
        )

    parts = []
    batch_size = 500
    total = len(parts_data)

    log_info(f"Processing {total:,} global parts in batches of {batch_size}...")

    for i, part_data in enumerate(parts_data):
        part = Part(**part_data)
        db.add(part)
        parts.append(part)

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Global Parts")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} parts)...")

    db.commit()
    for part in parts:
        db.refresh(part)

    elapsed = time.time() - start_time
    log_info(f"✓ Created {len(parts):,} global parts (took {elapsed:.1f}s)")

    # Ensure fake retailers exist, then add many retailers + price history to one part for UI debugging
    retailers = _ensure_sample_retailers(db)
    debug_part = parts[0]  # First part: "AWE Touring Exhaust System"
    base_price_cents = 129900  # $1299.00
    num_price_history_per_listing = 25
    days_back = 90

    log_info(
        f"Adding {len(retailers):,} retailers and price history to debug part (ID: {debug_part.id}, Name: {debug_part.name})..."
    )
    for retailer in retailers:
        listing = create_or_update_listing_and_price(
            db,
            debug_part.id,
            retailer.id,
            product_url=f"https://{retailer.domain or 'example.com'}/parts/{debug_part.part_number or debug_part.id}",
            price_cents=base_price_cents
            + random.randint(-5000, 8000),  # vary by retailer
            observed_at=datetime.now(UTC),
        )
        # Add multiple price history entries (time series over past days_back days)
        for j in range(num_price_history_per_listing - 1):
            days_ago = random.randint(1, days_back)
            observed_at = datetime.now(UTC) - timedelta(days=days_ago)
            price_cents = base_price_cents + random.randint(-8000, 10000)
            hist = PartPriceHistory(
                part_listing_id=listing.id,
                price_cents=max(100, price_cents),
                observed_at=observed_at,
            )
            db.add(hist)
    db.commit()

    log_info("")
    log_info("=" * 60)
    log_info("DEBUG PART FOR RETAILERS & PRICE HISTORY UI")
    log_info("=" * 60)
    log_info(
        f"  Use this global part to test retailer listings and price history charts:"
    )
    log_info(f"  Global Part ID:   {debug_part.id}")
    log_info(f"  Name:             {debug_part.name}")
    log_info(f"  Retailers:        {len(retailers):,} (PartListings)")
    log_info(
        f"  Price history:    ~{len(retailers) * num_price_history_per_listing:,} entries total"
    )
    log_info("=" * 60)
    log_info("")

    return parts
