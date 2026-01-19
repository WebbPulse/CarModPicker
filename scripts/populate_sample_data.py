#!/usr/bin/env python3
"""
Script to populate all database tables with sample data for localhost testing.

Usage:
    cd backend
    python ../scripts/populate_sample_data.py
"""

import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Optional

# Add backend directory to path so we can import app modules
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# Load .env file from backend directory before importing app modules
# This ensures DATABASE_URL and other settings are loaded correctly
from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
    print(f"Loaded .env file from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

from sqlalchemy.orm import Session

from app.api.dependencies.auth import (  # pyright: ignore[reportMissingImports]
    get_password_hash,
)
from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.build_list_part import (  # pyright: ignore[reportMissingImports]
    BuildListPart,
)  # pyright: ignore[reportMissingImports]
from app.api.models.car import Car  # pyright: ignore[reportMissingImports]
from app.api.models.category import Category  # pyright: ignore[reportMissingImports]
from app.api.models.global_part import (  # pyright: ignore[reportMissingImports]
    GlobalPart,
)  # pyright: ignore[reportMissingImports]
from app.api.models.report import Report  # pyright: ignore[reportMissingImports]
from app.api.models.subscription import (  # pyright: ignore[reportMissingImports]
    Subscription,
)  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]
from app.api.models.vote import Vote  # pyright: ignore[reportMissingImports]
from app.core.car_generations_data import (  # pyright: ignore[reportMissingImports]
    get_all_car_generations,
)
from app.db.base import (  # pyright: ignore[reportMissingImports]
    Base,
)  # Import Base to ensure all models are registered  # pyright: ignore[reportMissingImports]
from app.db.session import SessionLocal, engine  # pyright: ignore[reportMissingImports]


def create_sample_users(db: Session) -> list[User]:
    """Create sample users including admin and superuser."""
    print("Creating sample users...")

    # Initial special users
    users_data = [
        {
            "username": "admin",
            "email": "admin@carmodpicker.com",
            "hashed_password": get_password_hash("admin123"),
            "email_verified": True,
            "is_admin": True,
            "is_superuser": True,
            "subscription_tier": "premium",
            "subscription_status": "active",
        },
        {
            "username": "john_doe",
            "email": "john@example.com",
            "hashed_password": get_password_hash("password123"),
            "email_verified": True,
            "subscription_tier": "premium",
            "subscription_status": "active",
        },
        {
            "username": "jane_smith",
            "email": "jane@example.com",
            "hashed_password": get_password_hash("password123"),
            "email_verified": True,
            "subscription_tier": "free",
            "subscription_status": "active",
        },
        {
            "username": "car_enthusiast",
            "email": "enthusiast@example.com",
            "hashed_password": get_password_hash("password123"),
            "email_verified": True,
            "subscription_tier": "premium",
            "subscription_status": "active",
        },
        {
            "username": "modder_pro",
            "email": "modder@example.com",
            "hashed_password": get_password_hash("password123"),
            "email_verified": True,
            "subscription_tier": "free",
            "subscription_status": "active",
        },
    ]

    # Generate additional users to reach 50 total
    first_names = [
        "Alex",
        "Chris",
        "Jordan",
        "Taylor",
        "Morgan",
        "Casey",
        "Riley",
        "Quinn",
        "Avery",
        "Cameron",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
    ]
    prefixes = [
        "speed",
        "drive",
        "auto",
        "car",
        "mod",
        "tune",
        "race",
        "build",
        "custom",
        "pro",
    ]
    suffixes = [
        "fan",
        "lover",
        "racer",
        "builder",
        "tuner",
        "pro",
        "expert",
        "master",
        "guru",
        "ace",
    ]

    for i in range(45):  # 45 more to reach 50 total
        if i < 20:
            # Use first_name_last_name format
            first = random.choice(first_names).lower()
            last = random.choice(last_names).lower()
            username = f"{first}_{last}_{i}"
            email = f"{first}.{last}.{i}@example.com"
        else:
            # Use prefix_suffix format
            prefix = random.choice(prefixes)
            suffix = random.choice(suffixes)
            username = f"{prefix}_{suffix}_{i}"
            email = f"{prefix}{suffix}{i}@example.com"

        users_data.append(
            {
                "username": username,
                "email": email,
                "hashed_password": get_password_hash("password123"),
                "email_verified": random.choice(
                    [True, True, True, False]
                ),  # 75% verified
                "subscription_tier": random.choice(
                    ["free", "free", "premium"]
                ),  # More free users
                "subscription_status": random.choice(
                    ["active", "active", "active", "inactive"]
                ),
            }
        )

    users = []
    created_count = 0
    for user_data in users_data:
        # Check if user already exists
        existing = (
            db.query(User)
            .filter(
                (User.username == user_data["username"])
                | (User.email == user_data["email"])
            )
            .first()
        )
        if existing:
            users.append(existing)
        else:
            user = User(**user_data)
            db.add(user)
            users.append(user)
            created_count += 1

    db.commit()
    for user in users:
        db.refresh(user)

    print(f"Created {created_count} new users, {len(users)} total")
    return users


def create_sample_categories(db: Session) -> list[Category]:
    """Create sample categories."""
    print("Creating sample categories...")

    categories_data = [
        {
            "name": "exhaust",
            "display_name": "Exhaust Systems",
            "description": "Exhaust systems, mufflers, headers, and related components",
            "icon": "🔧",
            "sort_order": 1,
        },
        {
            "name": "suspension",
            "display_name": "Suspension",
            "description": "Coilovers, springs, struts, and suspension components",
            "icon": "⚙️",
            "sort_order": 2,
        },
        {
            "name": "engine",
            "display_name": "Engine Performance",
            "description": "Turbochargers, superchargers, intakes, and engine mods",
            "icon": "🚗",
            "sort_order": 3,
        },
        {
            "name": "wheels",
            "display_name": "Wheels & Tires",
            "description": "Wheels, rims, tires, and wheel accessories",
            "icon": "⭕",
            "sort_order": 4,
        },
        {
            "name": "body",
            "display_name": "Body & Aero",
            "description": "Body kits, spoilers, splitters, and aerodynamic components",
            "icon": "🏎️",
            "sort_order": 5,
        },
        {
            "name": "interior",
            "display_name": "Interior",
            "description": "Seats, steering wheels, shift knobs, and interior mods",
            "icon": "🪑",
            "sort_order": 6,
        },
        {
            "name": "brakes",
            "display_name": "Brakes",
            "description": "Brake pads, rotors, calipers, and brake systems",
            "icon": "🛑",
            "sort_order": 7,
        },
    ]

    categories = []
    created_count = 0
    for cat_data in categories_data:
        # Check if category already exists
        existing = db.query(Category).filter(Category.name == cat_data["name"]).first()
        if existing:
            categories.append(existing)
        else:
            category = Category(**cat_data)
            db.add(category)
            categories.append(category)
            created_count += 1

    db.commit()
    for category in categories:
        db.refresh(category)

    print(f"Created {created_count} new categories, {len(categories)} total")
    return categories


def create_sample_cars(db: Session) -> list[Car]:
    """Create sample centrally managed car generations using the canonical data source."""
    print("Creating sample car generations...")

    # Use the same method as the application initialization
    # This ensures consistency with the canonical car_generations_data.py
    cars_data = get_all_car_generations()

    cars = []
    created_count = 0
    skipped_count = 0

    for car_data in cars_data:
        # Check if car generation already exists
        existing = (
            db.query(Car)
            .filter(
                Car.make == car_data["make"],
                Car.model == car_data["model"],
                Car.generation_name == car_data["generation_name"],
            )
            .first()
        )
        if existing:
            # Skip existing cars to preserve manual edits (same behavior as init_car_generations)
            cars.append(existing)
            skipped_count += 1
        else:
            car = Car(**car_data)
            db.add(car)
            cars.append(car)
            created_count += 1

    db.commit()
    for car in cars:
        db.refresh(car)

    print(
        f"Created {created_count} new car generations, skipped {skipped_count} existing, {len(cars)} total"
    )
    return cars


def create_sample_global_parts(
    db: Session, users: list[User], categories: list[Category]
) -> list[GlobalPart]:
    """Create sample global parts."""
    print("Creating sample global parts...")

    # Initial parts
    initial_parts = [
        {
            "name": "AWE Touring Exhaust System",
            "description": "High-quality cat-back exhaust system with deep, aggressive tone",
            "price": 1299,
            "category_id": categories[0].id,  # exhaust
            "user_id": users[1].id,  # john_doe
            "brand": "AWE",
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
            "price": 2499,
            "category_id": categories[1].id,  # suspension
            "user_id": users[2].id,  # jane_smith
            "brand": "KW",
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
            "price": 1899,
            "category_id": categories[2].id,  # engine
            "user_id": users[3].id,  # car_enthusiast
            "brand": "Garrett",
            "part_number": "GAR-TUR-001",
            "specifications": {"max_boost": "25psi", "compressor": "dual_ball_bearing"},
            "is_verified": True,
        },
        {
            "name": "Volk TE37 Wheels",
            "description": "Lightweight forged wheels, 18x9.5 +22",
            "price": 3200,
            "category_id": categories[3].id,  # wheels
            "user_id": users[1].id,  # john_doe
            "brand": "Rays",
            "part_number": "VOLK-TE37-001",
            "specifications": {"size": "18x9.5", "offset": "+22", "weight": "18.5lbs"},
            "is_verified": True,
        },
        {
            "name": "APR Carbon Fiber Wing",
            "description": "Large carbon fiber rear wing for downforce",
            "price": 899,
            "category_id": categories[4].id,  # body
            "user_id": users[4].id,  # modder_pro
            "brand": "APR",
            "part_number": "APR-AERO-001",
            "specifications": {"material": "carbon_fiber", "adjustable": True},
            "is_verified": False,
        },
        {
            "name": "Recaro Sportster CS Seats",
            "description": "Premium sport seats with heating",
            "price": 1599,
            "category_id": categories[5].id,  # interior
            "user_id": users[2].id,  # jane_smith
            "brand": "Recaro",
            "part_number": "REC-INT-001",
            "specifications": {"heated": True, "adjustable": True},
            "is_verified": True,
        },
        {
            "name": "Brembo GT Big Brake Kit",
            "description": "6-piston front brake kit with slotted rotors",
            "price": 3499,
            "category_id": categories[6].id,  # brakes
            "user_id": users[3].id,  # car_enthusiast
            "brand": "Brembo",
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
            "price": 399,
            "category_id": categories[2].id,  # engine
            "user_id": users[1].id,  # john_doe
            "brand": "Injen",
            "part_number": "INJ-INT-001",
            "specifications": {"filter_type": "dry", "material": "aluminum"},
            "is_verified": True,
        },
        {
            "name": "HKS Hi-Power Exhaust",
            "description": "JDM-style exhaust with titanium tips",
            "price": 1099,
            "category_id": categories[0].id,  # exhaust
            "user_id": users[4].id,  # modder_pro
            "brand": "HKS",
            "part_number": "HKS-EXH-001",
            "specifications": {"material": "titanium", "tips": 2},
            "is_verified": True,
        },
        {
            "name": "Ohlins Road & Track Coilovers",
            "description": "Premium Swedish coilover system",
            "price": 2999,
            "category_id": categories[1].id,  # suspension
            "user_id": users[1].id,  # john_doe
            "brand": "Ohlins",
            "part_number": "OHL-SUS-001",
            "specifications": {"adjustable": True, "damping": "dual_flow_valve"},
            "is_verified": True,
        },
    ]

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
            "brands": [
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
            "brands": [
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
            "brands": ["Garrett", "Injen", "Cobb", "HKS", "Blitz", "Greddy", "APR"],
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
            "brands": ["Rays", "Work", "Enkei", "Volk", "WedsSport", "Rota", "Konig"],
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
            "brands": ["APR", "Seibon", "VIS", "Carbon Creations", "Verus", "Aeroflow"],
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
            "brands": ["Recaro", "Sparco", "Bride", "MOMO", "NRG", "Takata"],
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
            "brands": ["Brembo", "StopTech", "Wilwood", "EBC", "Hawk", "Carbotech"],
            "descriptions": [
                "High-performance brake system",
                "Track-tested brake components",
                "Street performance brake upgrade",
                "Maximum stopping power",
            ],
            "price_range": (199, 4999),
        },
    }

    parts_data = initial_parts.copy()

    # Generate additional parts to reach 50 total
    for i in range(40):  # 40 more to reach 50 total
        category = random.choice(categories)
        category_name = category.name
        template = part_templates.get(category_name, part_templates["exhaust"])

        name_base = random.choice(template["names"])
        brand = random.choice(template["brands"])
        name = (
            f"{brand} {name_base} {i+1}"
            if i < 30
            else f"{name_base} {brand} Edition {i+1}"
        )
        description = random.choice(template["descriptions"])
        price = random.randint(*template["price_range"])
        user = random.choice(users)
        is_verified = random.choice([True, True, True, False])  # 75% verified

        part_number = f"{brand[:3].upper()}-{category_name[:3].upper()}-{i+100:03d}"

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
                "price": price,
                "category_id": category.id,
                "user_id": user.id,
                "brand": brand,
                "part_number": part_number,
                "specifications": specs,
                "is_verified": is_verified,
            }
        )

    parts = []
    for part_data in parts_data:
        part = GlobalPart(**part_data)
        db.add(part)
        parts.append(part)

    db.commit()
    for part in parts:
        db.refresh(part)

    print(f"Created {len(parts)} global parts")
    return parts


def create_sample_build_lists(
    db: Session, users: list[User], cars: list[Car]
) -> list[BuildList]:
    """Create sample build lists."""
    print("Creating sample build lists...")

    # Initial build lists - find cars by make/model to ensure correct references
    # Helper to find a car by make and model
    def find_car(
        make: str, model: str, generation_name: str | None = None
    ) -> Car | None:
        for car in cars:
            if car.make == make and car.model == model:
                if generation_name is None or car.generation_name == generation_name:
                    return car
        return cars[0] if cars else None  # Fallback to first car

    civic = find_car("Honda", "Civic", "10th Gen") or cars[0]
    supra = find_car("Toyota", "Supra") or cars[2] if len(cars) > 2 else cars[0]
    wrx = find_car("Subaru", "WRX", "VA") or cars[3] if len(cars) > 3 else cars[0]
    gtr = find_car("Nissan", "GT-R") or cars[5] if len(cars) > 5 else cars[0]
    miata = find_car("Mazda", "Miata") or cars[6] if len(cars) > 6 else cars[0]
    mustang = (
        find_car("Ford", "Mustang", "S550") or cars[7] if len(cars) > 7 else cars[0]
    )

    initial_build_lists = [
        {
            "name": "My Daily Driver Build",
            "description": "Comfortable daily driver with some performance upgrades",
            "car_id": civic.id,
            "user_id": users[1].id,  # john_doe
        },
        {
            "name": "Track Day Monster",
            "description": "Full track build for maximum performance",
            "car_id": supra.id,
            "user_id": users[1].id,  # john_doe
        },
        {
            "name": "Rally Build",
            "description": "Rally-inspired build for the WRX",
            "car_id": wrx.id,
            "user_id": users[2].id,  # jane_smith
        },
        {
            "name": "GT-R Dream Build",
            "description": "Ultimate performance build for the GT-R",
            "car_id": gtr.id,
            "user_id": users[3].id,  # car_enthusiast
        },
        {
            "name": "Miata Weekend Warrior",
            "description": "Lightweight mods for the perfect weekend car",
            "car_id": miata.id,
            "user_id": users[3].id,  # car_enthusiast
        },
        {
            "name": "Mustang Drag Build",
            "description": "Straight-line speed focused build",
            "car_id": mustang.id,
            "user_id": users[4].id,  # modder_pro
        },
    ]

    # Build list name templates
    build_types = [
        "Daily Driver",
        "Track Build",
        "Street Build",
        "Show Build",
        "Drag Build",
        "Drift Build",
        "Rally Build",
        "Weekend Warrior",
        "Project Car",
        "Dream Build",
        "Race Build",
        "Time Attack",
        "Street Fighter",
        "Sleeper Build",
        "Stance Build",
        "Restoration",
        "Restomod",
        "Classic Build",
        "Modern Classic",
        "Budget Build",
    ]
    descriptions = [
        "Full build for maximum performance",
        "Comfortable daily driver with upgrades",
        "Track-focused modifications",
        "Show car with aesthetic mods",
        "Straight-line speed build",
        "Lightweight performance mods",
        "Balanced street/track setup",
        "Agressive performance build",
        "Budget-friendly modifications",
        "Ultimate performance build",
    ]

    build_lists_data = initial_build_lists.copy()

    # Generate additional build lists to reach 50 total
    for i in range(44):  # 44 more to reach 50 total
        car = random.choice(cars)
        user = random.choice(users)
        build_type = random.choice(build_types)
        description = random.choice(descriptions)

        # Make build list name specific to car
        build_name = f"{car.make} {car.model} {build_type}"
        if i > 30:
            build_name = f"My {build_type}"

        build_lists_data.append(
            {
                "name": build_name,
                "description": description,
                "car_id": car.id,
                "user_id": user.id,
            }
        )

    build_lists = []
    for bl_data in build_lists_data:
        build_list = BuildList(**bl_data)
        db.add(build_list)
        build_lists.append(build_list)

    db.commit()
    for build_list in build_lists:
        db.refresh(build_list)

    print(f"Created {len(build_lists)} build lists")
    return build_lists


def create_sample_build_list_parts(
    db: Session,
    build_lists: list[BuildList],
    global_parts: list[GlobalPart],
    users: list[User],
) -> list[BuildListPart]:
    """Create sample build list parts."""
    print("Creating sample build list parts...")

    # Initial build list parts (for the first few build lists)
    initial_parts = [
        # Daily Driver Build (Civic)
        {
            "build_list_id": build_lists[0].id,
            "global_part_id": global_parts[7].id,  # Injen Cold Air Intake
            "added_by": users[1].id,
            "quantity": 1,
            "notes": "Great for daily driving, easy install",
        },
        {
            "build_list_id": build_lists[0].id,
            "global_part_id": global_parts[1].id,  # KW V3 Coilovers
            "added_by": users[1].id,
            "quantity": 1,
            "notes": "Comfortable yet sporty",
        },
        # Track Day Monster (Supra)
        {
            "build_list_id": build_lists[1].id,
            "global_part_id": global_parts[2].id,  # Garrett Turbo
            "added_by": users[1].id,
            "quantity": 1,
            "notes": "For maximum power",
        },
        {
            "build_list_id": build_lists[1].id,
            "global_part_id": global_parts[6].id,  # Brembo Brakes
            "added_by": users[1].id,
            "quantity": 1,
            "notes": "Essential for track safety",
        },
        {
            "build_list_id": build_lists[1].id,
            "global_part_id": global_parts[3].id,  # Volk TE37 Wheels
            "added_by": users[1].id,
            "quantity": 4,
            "notes": "Lightweight for better handling",
        },
        # Rally Build (WRX)
        {
            "build_list_id": build_lists[2].id,
            "global_part_id": global_parts[1].id,  # KW V3 Coilovers
            "added_by": users[2].id,
            "quantity": 1,
            "notes": "Rally-tuned suspension",
        },
        {
            "build_list_id": build_lists[2].id,
            "global_part_id": global_parts[0].id,  # AWE Exhaust
            "added_by": users[2].id,
            "quantity": 1,
            "notes": "Aggressive rally sound",
        },
        # GT-R Dream Build
        {
            "build_list_id": build_lists[3].id,
            "global_part_id": global_parts[2].id,  # Garrett Turbo
            "added_by": users[3].id,
            "quantity": 2,
            "notes": "Twin turbo upgrade",
        },
        {
            "build_list_id": build_lists[3].id,
            "global_part_id": global_parts[6].id,  # Brembo Brakes
            "added_by": users[3].id,
            "quantity": 1,
            "notes": "Need to stop all that power",
        },
        {
            "build_list_id": build_lists[3].id,
            "global_part_id": global_parts[4].id,  # APR Wing
            "added_by": users[3].id,
            "quantity": 1,
            "notes": "Maximum downforce",
        },
        # Miata Weekend Warrior
        {
            "build_list_id": build_lists[4].id,
            "global_part_id": global_parts[9].id,  # Ohlins Coilovers
            "added_by": users[3].id,
            "quantity": 1,
            "notes": "Perfect for canyon runs",
        },
        {
            "build_list_id": build_lists[4].id,
            "global_part_id": global_parts[3].id,  # Volk TE37 Wheels
            "added_by": users[3].id,
            "quantity": 4,
            "notes": "Lightweight wheels for the Miata",
        },
        # Mustang Drag Build
        {
            "build_list_id": build_lists[5].id,
            "global_part_id": global_parts[8].id,  # HKS Exhaust
            "added_by": users[4].id,
            "quantity": 1,
            "notes": "Lightweight exhaust for drag racing",
        },
    ]

    notes_templates = [
        "Great addition to the build",
        "Essential component",
        "High-quality part",
        "Perfect for this application",
        "Easy installation",
        "Recommended by many builders",
        "Excellent value",
        "Performance tested",
        "Looks great",
        "Worth the money",
    ]

    build_list_parts_data = initial_parts.copy()
    used_combinations = set()

    # Track used combinations to avoid duplicate parts in same build list
    for part in initial_parts:
        key = (part["build_list_id"], part["global_part_id"])
        used_combinations.add(key)

    # Generate additional build list parts - target 150 total
    for i in range(137):  # 137 more to reach 150 total
        build_list = random.choice(build_lists)
        part = random.choice(global_parts)
        user = random.choice(users)
        quantity = random.choice(
            [1, 1, 1, 2, 4]
        )  # Mostly 1, sometimes 2 or 4 (for wheels)
        notes = random.choice(notes_templates)

        # Check if this combination already exists
        key = (build_list.id, part.id)
        if key not in used_combinations:
            build_list_parts_data.append(
                {
                    "build_list_id": build_list.id,
                    "global_part_id": part.id,
                    "added_by": user.id,
                    "quantity": quantity,
                    "notes": notes,
                }
            )
            used_combinations.add(key)

    build_list_parts = []
    for blp_data in build_list_parts_data:
        build_list_part = BuildListPart(**blp_data)
        db.add(build_list_part)
        build_list_parts.append(build_list_part)

    db.commit()
    for build_list_part in build_list_parts:
        db.refresh(build_list_part)

    print(f"Created {len(build_list_parts)} build list parts")
    return build_list_parts


def create_sample_votes(
    db: Session,
    users: list[User],
    cars: Optional[list[Car]],
    build_lists: Optional[list[BuildList]],
    global_parts: list[GlobalPart],
) -> list[Vote]:
    """Create sample votes."""
    print("Creating sample votes...")

    # Only vote on global parts if cars/build_lists are not available
    if cars is None or build_lists is None:
        print("  Skipping votes on cars and build lists (not available)")
        entity_types = ["global_part"]
    else:
        entity_types = ["car", "build_list", "global_part"]

    # Initial votes - only on global parts if cars/build_lists unavailable
    initial_votes = [
        # Votes on global parts
        {
            "user_id": users[1].id,
            "vote_type": "upvote",
            "entity_type": "global_part",
            "entity_id": (
                global_parts[2].id if len(global_parts) > 2 else global_parts[0].id
            ),
        },  # Garrett Turbo or first part
        {
            "user_id": users[2].id,
            "vote_type": "upvote",
            "entity_type": "global_part",
            "entity_id": (
                global_parts[2].id if len(global_parts) > 2 else global_parts[0].id
            ),
        },
        {
            "user_id": users[3].id,
            "vote_type": "upvote",
            "entity_type": "global_part",
            "entity_id": (
                global_parts[3].id if len(global_parts) > 3 else global_parts[0].id
            ),
        },  # Volk TE37 or first part
        {
            "user_id": users[4].id if len(users) > 4 else users[0].id,
            "vote_type": "upvote",
            "entity_type": "global_part",
            "entity_id": (
                global_parts[6].id if len(global_parts) > 6 else global_parts[0].id
            ),
        },  # Brembo Brakes or first part
        {
            "user_id": users[1].id,
            "vote_type": "downvote",
            "entity_type": "global_part",
            "entity_id": (
                global_parts[4].id if len(global_parts) > 4 else global_parts[0].id
            ),
        },  # APR Wing (downvote) or first part
    ]

    # Add car and build_list votes only if available
    if cars is not None and len(cars) > 0:
        initial_votes.extend(
            [
                {
                    "user_id": users[1].id,
                    "vote_type": "upvote",
                    "entity_type": "car",
                    "entity_id": cars[3].id if len(cars) > 3 else cars[0].id,
                },
                {
                    "user_id": users[2].id,
                    "vote_type": "upvote",
                    "entity_type": "car",
                    "entity_id": cars[3].id if len(cars) > 3 else cars[0].id,
                },
            ]
        )

    if build_lists is not None and len(build_lists) > 0:
        initial_votes.extend(
            [
                {
                    "user_id": users[2].id,
                    "vote_type": "upvote",
                    "entity_type": "build_list",
                    "entity_id": (
                        build_lists[1].id if len(build_lists) > 1 else build_lists[0].id
                    ),
                },
                {
                    "user_id": users[3].id,
                    "vote_type": "upvote",
                    "entity_type": "build_list",
                    "entity_id": (
                        build_lists[1].id if len(build_lists) > 1 else build_lists[0].id
                    ),
                },
            ]
        )

    votes_data = initial_votes.copy()
    used_combinations = set()

    # Track used combinations to avoid duplicate votes (same user voting on same entity)
    for vote in initial_votes:
        key = (vote["user_id"], vote["entity_type"], vote["entity_id"])
        used_combinations.add(key)

    # Generate additional votes - target 150 total
    vote_types = ["upvote", "upvote", "upvote", "downvote"]  # Mostly upvotes

    for i in range(136):  # 136 more to reach 150 total
        user = random.choice(users)
        entity_type = random.choice(entity_types)
        vote_type = random.choice(vote_types)

        # Choose entity based on type
        if entity_type == "car" and cars is not None and len(cars) > 0:
            entity_id = random.choice(cars).id
        elif (
            entity_type == "build_list"
            and build_lists is not None
            and len(build_lists) > 0
        ):
            entity_id = random.choice(build_lists).id
        elif entity_type == "global_part":
            entity_id = random.choice(global_parts).id
        else:
            # Skip if entity type not available
            continue

        # Check if this combination already exists
        key = (user.id, entity_type, entity_id)
        if key not in used_combinations:
            votes_data.append(
                {
                    "user_id": user.id,
                    "vote_type": vote_type,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                }
            )
            used_combinations.add(key)

    votes = []
    for vote_data in votes_data:
        vote = Vote(**vote_data)
        db.add(vote)
        votes.append(vote)

    db.commit()
    for vote in votes:
        db.refresh(vote)

    print(f"Created {len(votes)} votes")
    return votes


def create_sample_subscriptions(db: Session, users: list[User]) -> list[Subscription]:
    """Create sample subscriptions."""
    print("Creating sample subscriptions...")

    # Initial subscriptions
    subscriptions_data = [
        {
            "user_id": users[1].id,  # john_doe
            "tier": "premium",
            "status": "active",
            "expires_at": datetime.now(UTC) + timedelta(days=365),
        },
        {
            "user_id": users[3].id,  # car_enthusiast
            "tier": "premium",
            "status": "active",
            "expires_at": datetime.now(UTC) + timedelta(days=180),
        },
        {
            "user_id": users[2].id,  # jane_smith
            "tier": "free",
            "status": "active",
            "expires_at": None,
        },
    ]

    used_user_ids = {sub["user_id"] for sub in subscriptions_data}

    # Generate additional subscriptions for more users - target 50 total
    tiers = ["free", "free", "free", "premium"]  # More free than premium
    statuses = ["active", "active", "active", "inactive", "expired"]

    for i in range(47):  # 47 more to reach 50 total
        # Choose a user that doesn't already have a subscription
        available_users = [u for u in users if u.id not in used_user_ids]
        if not available_users:
            # If all users have subscriptions, just pick any user
            available_users = users

        user = random.choice(available_users)
        tier = random.choice(tiers)
        status = random.choice(statuses)

        # Set expiration based on tier and status
        expires_at = None
        if tier == "premium" and status == "active":
            expires_at = datetime.now(UTC) + timedelta(days=random.randint(30, 365))
        elif tier == "premium" and status == "expired":
            expires_at = datetime.now(UTC) - timedelta(days=random.randint(1, 90))
        elif tier == "free":
            expires_at = None  # Free subscriptions don't expire

        subscriptions_data.append(
            {
                "user_id": user.id,
                "tier": tier,
                "status": status,
                "expires_at": expires_at,
            }
        )
        used_user_ids.add(user.id)

    subscriptions = []
    for sub_data in subscriptions_data:
        subscription = Subscription(**sub_data)
        db.add(subscription)
        subscriptions.append(subscription)

    db.commit()
    for subscription in subscriptions:
        db.refresh(subscription)

    print(f"Created {len(subscriptions)} subscriptions")
    return subscriptions


def create_sample_reports(
    db: Session, users: list[User], global_parts: list[GlobalPart]
) -> list[Report]:
    """Create sample reports."""
    print("Creating sample reports...")

    # Get admin user
    admin_user = next((u for u in users if u.is_admin), users[0])

    # Initial reports
    reports_data = [
        {
            "user_id": users[1].id,
            "entity_type": "global_part",
            "entity_id": global_parts[4].id,  # APR Wing
            "reason": "inaccurate",
            "description": "Price seems incorrect, should be higher",
            "status": "pending",
        },
        {
            "user_id": users[2].id,
            "entity_type": "global_part",
            "entity_id": global_parts[4].id,  # APR Wing
            "reason": "spam",
            "description": "Duplicate listing",
            "status": "reviewed",
            "reviewed_by": admin_user.id,
            "reviewed_at": datetime.now(UTC) - timedelta(days=1),
            "admin_notes": "Verified, not a duplicate",
        },
    ]

    reasons = ["inaccurate", "spam", "inappropriate", "duplicate", "other"]
    statuses = ["pending", "pending", "pending", "reviewed", "resolved", "dismissed"]
    descriptions = [
        "Price seems incorrect",
        "Duplicate listing found",
        "Inappropriate content",
        "Misleading information",
        "Wrong category",
        "Fake product",
        "Spam content",
        "Copyright violation",
    ]
    admin_notes = [
        "Verified, not a duplicate",
        "Issue resolved",
        "Report dismissed - false alarm",
        "Content reviewed and approved",
        "User contacted for clarification",
    ]

    # Generate additional reports - target 50 total
    for i in range(48):  # 48 more to reach 50 total
        user = random.choice(users)
        part = random.choice(global_parts)
        reason = random.choice(reasons)
        status = random.choice(statuses)
        description = random.choice(descriptions)

        report_data = {
            "user_id": user.id,
            "entity_type": "global_part",
            "entity_id": part.id,
            "reason": reason,
            "description": description,
            "status": status,
        }

        # If reviewed/resolved/dismissed, add review information
        if status in ["reviewed", "resolved", "dismissed"]:
            report_data["reviewed_by"] = admin_user.id
            report_data["reviewed_at"] = datetime.now(UTC) - timedelta(
                days=random.randint(1, 30)
            )
            report_data["admin_notes"] = random.choice(admin_notes)

        reports_data.append(report_data)

    reports = []
    for report_data in reports_data:
        report = Report(**report_data)
        db.add(report)
        reports.append(report)

    db.commit()
    for report in reports:
        db.refresh(report)

    print(f"Created {len(reports)} reports")
    return reports


def main() -> None:
    """Main function to populate all tables."""
    print("=" * 60)
    print("Populating database with sample data...")
    print("=" * 60)

    # Create all tables if they don't exist
    print("Creating database tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print("Database tables ready.")

    db: Session = SessionLocal()

    try:
        # Create all sample data
        users = create_sample_users(db)
        categories = create_sample_categories(db)
        # Cars are now centrally managed (car generations, not user-owned)
        cars = create_sample_cars(db)
        global_parts = create_sample_global_parts(db, users, categories)
        # Build lists require a car_id (now mandatory)
        build_lists = create_sample_build_lists(db, users, cars)
        build_list_parts = create_sample_build_list_parts(
            db, build_lists, global_parts, users
        )
        votes = create_sample_votes(db, users, cars, build_lists, global_parts)
        subscriptions = create_sample_subscriptions(db, users)
        reports = create_sample_reports(db, users, global_parts)

        print("=" * 60)
        print("Sample data population complete!")
        print("=" * 60)
        print("\nSummary:")
        print(f"  Users: {len(users)}")
        print(f"  Categories: {len(categories)}")
        print(f"  Car Generations: {len(cars)}")
        print(f"  Global Parts: {len(global_parts)}")
        print(f"  Build Lists: {len(build_lists)}")
        print(f"  Build List Parts: {len(build_list_parts)}")
        print(f"  Votes: {len(votes)}")
        print(f"  Subscriptions: {len(subscriptions)}")
        print(f"  Reports: {len(reports)}")
        print("\nTest credentials:")
        print("  Admin: admin / admin123")
        print("  User: john_doe / password123")
        print("  User: jane_smith / password123")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"Error populating database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
