#!/usr/bin/env python3
"""
Script to populate all database tables with copious amounts of sample data for testing pagination.

This script generates large amounts of entities to push pagination limits and expose
where pagination might be missing or improper:
- Users: 2500+ (tests pagination with limit=1000)
- Global Parts: 2500+ (tests pagination with limit=1000)
- Build Lists: 2500+ (tests pagination with limit=1000)
- Build List Parts: 5000+ (tests pagination)
- Votes: 5000+ (tests pagination)
- Reports: 2500+ (tests pagination)
- Build Logs: One per build list
- Build Log Posts: 200-300 per build log (tests pagination with limit=100)

Note: Categories and Cars are NOT modified by this script.

Usage:
    cd backend
    python ../scripts/populate_sample_data.py
"""

import argparse
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from app.api.models.build_log import (  # pyright: ignore[reportMissingImports]
    BuildLog,
    BuildLogPost,
)  # pyright: ignore[reportMissingImports]
from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.car_model import CarModel  # pyright: ignore[reportMissingImports]
from app.api.models.category import Category  # pyright: ignore[reportMissingImports]
from app.api.models.car_make import CarMake  # pyright: ignore[reportMissingImports]
from app.api.models.global_part import (  # pyright: ignore[reportMissingImports]
    GlobalPart,
)  # pyright: ignore[reportMissingImports]
from app.api.models.part_listing import (
    PartListing,
)  # pyright: ignore[reportMissingImports]
from app.api.models.part_price_history import (  # pyright: ignore[reportMissingImports]
    PartPriceHistory,
)  # pyright: ignore[reportMissingImports]
from app.api.models.report import Report  # pyright: ignore[reportMissingImports]
from app.api.models.retailer import Retailer  # pyright: ignore[reportMissingImports]
from app.api.services.part_listing_service import (  # pyright: ignore[reportMissingImports]
    create_or_update_listing_and_price,
    get_or_create_part_manufacturer_by_name,
    get_or_create_retailer,
)  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]
from app.api.models.vote import Vote  # pyright: ignore[reportMissingImports]
from app.core.car_generations_data import (  # pyright: ignore[reportMissingImports]
    get_all_car_generations,
)
from app.core.part_categories_data import (  # pyright: ignore[reportMissingImports]
    get_all_part_categories,
)
from app.db.base import (  # pyright: ignore[reportMissingImports]
    Base,
)  # Import Base to ensure all models are registered  # pyright: ignore[reportMissingImports]
from app.db.session import SessionLocal, engine  # pyright: ignore[reportMissingImports]


# Logging utilities
def log_info(message: str) -> None:
    """Log an info message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def log_progress(current: int, total: int, entity_name: str) -> None:
    """Log progress for entity creation."""
    percentage = (current / total * 100) if total > 0 else 0
    log_info(f"  {entity_name}: {current:,}/{total:,} ({percentage:.1f}%)")


def log_section(message: str) -> None:
    """Log a section header."""
    print()
    log_info("=" * 60)
    log_info(message)
    log_info("=" * 60)


def create_sample_users(db: Session) -> list[User]:
    """Create sample users including admin and superuser."""
    start_time = time.time()
    log_section("Creating sample users...")

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

    # Generate additional users to reach 2500 total (to test pagination with limit=1000)
    log_info("Generating user data...")
    user_data_list = []
    for i in range(2495):  # 2495 more to reach 2500 total
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

        user_data_list.append(
            {
                "username": username,
                "email": email,
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

    # Hash passwords in parallel (CPU-intensive operation)
    log_info(f"Hashing passwords for {len(user_data_list):,} users in parallel...")
    password_hash_start = time.time()
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all password hashing tasks
        future_to_index = {
            executor.submit(get_password_hash, "password123"): i
            for i in range(len(user_data_list))
        }
        # Collect results as they complete
        password_hashes = {}
        completed = 0
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                password_hashes[index] = future.result()
                completed += 1
                if completed % 500 == 0:
                    log_progress(completed, len(user_data_list), "Password Hashing")
            except Exception as e:
                log_info(f"  Error hashing password for user {index}: {e}")
                password_hashes[index] = get_password_hash("password123")  # Fallback

    password_hash_elapsed = time.time() - password_hash_start
    log_info(
        f"✓ Hashed {len(password_hashes):,} passwords in {password_hash_elapsed:.1f}s"
    )

    # Combine user data with hashed passwords
    for i, user_data in enumerate(user_data_list):
        user_data["hashed_password"] = password_hashes[i]
        users_data.append(user_data)

    users = []
    created_count = 0
    batch_size = 500
    total = len(users_data)

    log_info(f"Processing {total:,} users in batches of {batch_size}...")

    for i, user_data in enumerate(users_data):
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

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Users")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} users)...")

    db.commit()
    for user in users:
        db.refresh(user)

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {created_count:,} new users, {len(users):,} total (took {elapsed:.1f}s)"
    )
    return users


def create_sample_categories(db: Session) -> list[Category]:
    """Create sample categories from canonical part_categories_data (same as init_categories)."""
    start_time = time.time()
    log_section("Creating sample categories...")

    categories_data = get_all_part_categories()
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

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {created_count:,} new categories, {len(categories):,} total (took {elapsed:.1f}s)"
    )
    return categories


def create_sample_cars(db: Session) -> list[Car]:
    """Create sample centrally managed car generations using the canonical data source.
    Uses Make and CarModel entities; same logic as init_car_generations.
    """
    start_time = time.time()
    log_section("Creating sample car generations...")

    cars_data = get_all_car_generations()
    cars: list[Car] = []
    created_count = 0
    skipped_count = 0

    for car_data in cars_data:
        make_name = car_data["make"]
        model_name = car_data["model"]

        # Get or create Make
        make_entity = db.query(Make).filter(Make.name == make_name).first()
        if make_entity is None:
            make_entity = Make(name=make_name)
            db.add(make_entity)
            db.flush()

        # Get or create CarModel
        car_model_entity = (
            db.query(CarModel)
            .filter(CarModel.car_make_id == make_entity.id, CarModel.name == model_name)
            .first()
        )
        if car_model_entity is None:
            car_model_entity = CarModel(car_make_id=make_entity.id, name=model_name)
            db.add(car_model_entity)
            db.flush()

        # Check if car generation already exists
        existing = (
            db.query(Car)
            .filter(
                Car.car_model_id == car_model_entity.id,
                Car.generation_name == car_data["generation_name"],
            )
            .first()
        )
        if existing:
            cars.append(existing)
            skipped_count += 1
        else:
            car = Car(
                car_model_id=car_model_entity.id,
                generation_name=car_data["generation_name"],
                start_year=car_data["start_year"],
                end_year=car_data.get("end_year"),
                description=car_data.get("description"),
            )
            db.add(car)
            cars.append(car)
            created_count += 1

    db.commit()
    for car in cars:
        db.refresh(car)

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {created_count:,} new car generations, skipped {skipped_count:,} existing, {len(cars):,} total (took {elapsed:.1f}s)"
    )
    return cars


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
) -> list[GlobalPart]:
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
        part_manufacturer = get_or_create_part_manufacturer_by_name(db, name)
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
            b = get_or_create_part_manufacturer_by_name(db, p["part_manufacturer"])
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
            b = get_or_create_part_manufacturer_by_name(db, name)
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
            b = get_or_create_part_manufacturer_by_name(db, part_manufacturer_name)
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
        part = GlobalPart(**part_data)
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


def create_sample_build_lists(
    db: Session, users: list[User], cars: list[Car]
) -> list[BuildList]:
    """Create sample build lists."""
    start_time = time.time()
    log_section("Creating sample build lists...")

    # Initial build lists - find cars by make/model to ensure correct references
    # Helper to find a car by make and model
    def find_car(
        make: str, model: str, generation_name: str | None = None
    ) -> Car | None:
        for car in cars:
            if car.car_make_name == make and car.model == model:
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

    # Generate additional build lists to reach 2500 total (to test pagination with limit=1000)
    for i in range(2494):  # 2494 more to reach 2500 total
        car = random.choice(cars)
        user = random.choice(users)
        build_type = random.choice(build_types)
        description = random.choice(descriptions)

        # Make build list name specific to car
        build_name = f"{car.car_make_name} {car.car_model_name} {build_type}"
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
    batch_size = 500
    total = len(build_lists_data)

    log_info(f"Processing {total:,} build lists in batches of {batch_size}...")

    for i, bl_data in enumerate(build_lists_data):
        build_list = BuildList(**bl_data)
        db.add(build_list)
        build_lists.append(build_list)

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Build Lists")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} build lists)...")

    db.commit()
    for build_list in build_lists:
        db.refresh(build_list)

    elapsed = time.time() - start_time
    log_info(f"✓ Created {len(build_lists):,} build lists (took {elapsed:.1f}s)")
    return build_lists


def create_sample_build_list_parts(
    db: Session,
    build_lists: list[BuildList],
    global_parts: list[GlobalPart],
    users: list[User],
) -> list[BuildListPart]:
    """Create sample build list parts."""
    start_time = time.time()
    log_section("Creating sample build list parts...")

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

    # Generate additional build list parts - target 5000 total (to test pagination)
    for i in range(4987):  # 4987 more to reach 5000 total
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
    batch_size = 500
    total = len(build_list_parts_data)

    log_info(f"Processing {total:,} build list parts in batches of {batch_size}...")

    for i, blp_data in enumerate(build_list_parts_data):
        build_list_part = BuildListPart(**blp_data)
        db.add(build_list_part)
        build_list_parts.append(build_list_part)

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Build List Parts")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} parts)...")

    db.commit()
    for build_list_part in build_list_parts:
        db.refresh(build_list_part)

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {len(build_list_parts):,} build list parts (took {elapsed:.1f}s)"
    )
    return build_list_parts


def create_admin_build_lists(
    db: Session,
    users: list[User],
    cars: list[Car],
    global_parts: list[GlobalPart],
    num_build_lists: int = 100,
    parts_per_regular_list: int = 5,
    parts_per_large_list: int = 200,
    num_build_lists_for_car: int = 50,
    target_car_make: str | None = None,
    target_car_model: str | None = None,
    target_car_generation: str | None = None,
) -> tuple[list[BuildList], BuildList, Car | None]:
    """
    Create many build lists for the admin user, with one build list having many parts.
    Also creates many build lists for a specific car generation.

    Args:
        db: Database session
        users: List of users (will find admin user)
        cars: List of cars to assign to build lists
        global_parts: List of global parts to add to build lists
        num_build_lists: Number of build lists to create (default: 100)
        parts_per_regular_list: Number of parts per regular build list (default: 5)
        parts_per_large_list: Number of parts for the large build list (default: 200)
        num_build_lists_for_car: Number of build lists to create for the target car (default: 50)
        target_car_make: Make of the target car generation (optional, will auto-select if not provided)
        target_car_model: Model of the target car generation (optional)
        target_car_generation: Generation name of the target car (optional)

    Returns:
        Tuple of (list of all created build lists, the build list with many parts, target car or None)
    """
    start_time = time.time()
    log_section("Creating admin build lists...")

    # Find admin user
    admin_user = next((u for u in users if u.username == "admin"), None)
    if not admin_user:
        # Try to find by is_admin flag
        admin_user = next((u for u in users if u.is_admin), None)

    if not admin_user:
        raise ValueError("Admin user not found. Please ensure admin user exists.")

    log_info(f"Found admin user: {admin_user.username} (ID: {admin_user.id})")

    if not cars:
        raise ValueError("No cars available. Please ensure cars exist in database.")

    if not global_parts:
        raise ValueError(
            "No global parts available. Please ensure global parts exist in database."
        )

    # Find or select target car generation
    target_car = None
    if num_build_lists_for_car > 0:
        if target_car_make and target_car_model:
            # Try to find the specific car
            for car in cars:
                if (
                    car.car_make_name.lower() == target_car_make.lower()
                    and car.model.lower() == target_car_model.lower()
                ):
                    if target_car_generation:
                        if (
                            car.generation_name
                            and car.generation_name.lower()
                            == target_car_generation.lower()
                        ):
                            target_car = car
                            break
                    else:
                        target_car = car
                        break

        # If not found or not specified, auto-select a popular car
        if not target_car:
            # Try to find common cars first
            popular_cars = ["Honda", "Toyota", "Subaru", "Nissan", "Mazda", "Ford"]
            for make in popular_cars:
                for car in cars:
                    if car.car_make_name == make:
                        target_car = car
                        break
                if target_car:
                    break

            # Fallback to first car
            if not target_car:
                target_car = cars[0]

        log_info(f"\n{'='*60}")
        log_info(f"TARGET CAR GENERATION FOR MULTIPLE BUILD LISTS:")
        log_info(f"  Make: {target_car.car_make_name}")
        log_info(f"  Model: {target_car.car_model_name}")
        log_info(f"  Generation: {target_car.generation_name or 'N/A'}")
        log_info(f"  Car ID: {target_car.id}")
        log_info(f"  Will create {num_build_lists_for_car:,} build lists for this car")
        log_info(f"{'='*60}\n")

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
        "Aggressive performance build",
        "Budget-friendly modifications",
        "Ultimate performance build",
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

    # Create build lists
    build_lists_data = []
    build_lists = []

    # The first build list will be the one with many parts
    large_build_list_car = target_car if target_car else random.choice(cars)
    large_build_list_name = f"Admin's Ultimate {large_build_list_car.car_make_name} {large_build_list_car.car_model_name} Build"

    total_build_lists_to_create = num_build_lists + num_build_lists_for_car
    log_info(f"Creating {total_build_lists_to_create:,} build lists for admin user...")
    log_info(f"  - {num_build_lists:,} general build lists")
    if num_build_lists_for_car > 0:
        log_info(
            f"  - {num_build_lists_for_car:,} build lists for {target_car.car_make_name} {target_car.car_model_name}"
        )

    build_list_counter = 0

    # First, create the build list with many parts (always first)
    build_lists_data.append(
        {
            "name": large_build_list_name,
            "description": "Ultimate performance build with extensive modifications",
            "car_id": large_build_list_car.id,
            "user_id": admin_user.id,
        }
    )
    build_list_counter += 1

    # Create build lists for the target car generation
    if num_build_lists_for_car > 0 and target_car:
        log_info(
            f"Creating {num_build_lists_for_car:,} build lists for {target_car.car_make_name} {target_car.car_model_name}..."
        )
        for i in range(num_build_lists_for_car):
            build_type = random.choice(build_types)
            description = random.choice(descriptions)
            build_name = (
                f"Admin's {target_car.car_make_name} {target_car.car_model_name} {build_type} #{i+1}"
            )

            build_lists_data.append(
                {
                    "name": build_name,
                    "description": description,
                    "car_id": target_car.id,
                    "user_id": admin_user.id,
                }
            )
            build_list_counter += 1

    # Create remaining general build lists
    remaining_lists = (
        num_build_lists - 1
    )  # Subtract 1 because we already created the large one
    for i in range(remaining_lists):
        car = random.choice(cars)
        build_type = random.choice(build_types)
        description = random.choice(descriptions)
        build_name = f"Admin's {car.car_make_name} {car.car_model_name} {build_type}"

        build_lists_data.append(
            {
                "name": build_name,
                "description": description,
                "car_id": car.id,
                "user_id": admin_user.id,
            }
        )
        build_list_counter += 1

    # Create build lists in database
    batch_size = 50
    total = len(build_lists_data)

    log_info(f"Processing {total:,} build lists in batches of {batch_size}...")

    for i, bl_data in enumerate(build_lists_data):
        build_list = BuildList(**bl_data)
        db.add(build_list)
        build_lists.append(build_list)

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Build Lists")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} build lists)...")

    db.commit()
    for build_list in build_lists:
        db.refresh(build_list)

    # Identify the large build list (first one)
    large_build_list = build_lists[0]

    log_info(
        f"✓ Created {len(build_lists):,} build lists (took {time.time() - start_time:.1f}s)"
    )
    log_info(f"\n{'='*60}")
    log_info(f"LARGE BUILD LIST IDENTIFIED:")
    log_info(f"  Name: {large_build_list.name}")
    log_info(f"  ID: {large_build_list.id}")
    log_info(f"  Car: {large_build_list_car.car_make_name} {large_build_list_car.car_model_name}")
    log_info(f"{'='*60}\n")

    # Now create build list parts
    log_section("Adding parts to admin build lists...")
    parts_start_time = time.time()

    build_list_parts = []
    used_combinations = set()

    # First, add many parts to the large build list
    log_info(
        f"Adding {parts_per_large_list:,} parts to large build list (ID: {large_build_list.id})..."
    )

    # Shuffle global parts to get variety
    available_parts = global_parts.copy()
    random.shuffle(available_parts)

    parts_added_to_large = 0
    for i, part in enumerate(available_parts):
        if parts_added_to_large >= parts_per_large_list:
            break

        key = (large_build_list.id, part.id)
        if key not in used_combinations:
            quantity = random.choice([1, 1, 1, 2, 4])  # Mostly 1, sometimes 2 or 4
            notes = random.choice(notes_templates)

            build_list_part = BuildListPart(
                build_list_id=large_build_list.id,
                global_part_id=part.id,
                added_by=admin_user.id,
                quantity=quantity,
                notes=notes,
            )
            db.add(build_list_part)
            build_list_parts.append(build_list_part)
            used_combinations.add(key)
            parts_added_to_large += 1

    log_info(f"✓ Added {parts_added_to_large:,} parts to large build list")

    # Now add parts to regular build lists
    log_info(
        f"Adding {parts_per_regular_list:,} parts to each of the remaining {num_build_lists - 1:,} build lists..."
    )

    total_parts_added = parts_added_to_large
    for build_list in build_lists[1:]:  # Skip the first (large) one
        parts_added = 0
        random.shuffle(available_parts)

        for part in available_parts:
            if parts_added >= parts_per_regular_list:
                break

            key = (build_list.id, part.id)
            if key not in used_combinations:
                quantity = random.choice([1, 1, 1, 2, 4])
                notes = random.choice(notes_templates)

                build_list_part = BuildListPart(
                    build_list_id=build_list.id,
                    global_part_id=part.id,
                    added_by=admin_user.id,
                    quantity=quantity,
                    notes=notes,
                )
                db.add(build_list_part)
                build_list_parts.append(build_list_part)
                used_combinations.add(key)
                parts_added += 1
                total_parts_added += 1

        if (total_parts_added - parts_added_to_large) % 500 == 0:
            db.commit()
            log_progress(
                total_parts_added - parts_added_to_large,
                (num_build_lists - 1) * parts_per_regular_list,
                "Build List Parts",
            )

    db.commit()
    for build_list_part in build_list_parts:
        db.refresh(build_list_part)

    parts_elapsed = time.time() - parts_start_time
    log_info(
        f"✓ Added {len(build_list_parts):,} total build list parts (took {parts_elapsed:.1f}s)"
    )

    # Final summary
    log_info(f"\n{'='*60}")
    log_info("ADMIN BUILD LISTS SUMMARY:")
    log_info(f"  Total build lists created: {len(build_lists):,}")
    log_info(f"  Total build list parts created: {len(build_list_parts):,}")
    log_info(f"\n  LARGE BUILD LIST:")
    log_info(f"    Name: {large_build_list.name}")
    log_info(f"    ID: {large_build_list.id}")
    log_info(f"    Parts count: {parts_added_to_large:,}")
    if target_car and num_build_lists_for_car > 0:
        # Count build lists for target car
        target_car_build_lists = [
            bl for bl in build_lists if bl.car_id == target_car.id
        ]
        log_info(f"\n  TARGET CAR GENERATION ({target_car.car_make_name} {target_car.car_model_name}):")
        log_info(f"    Car ID: {target_car.id}")
        log_info(f"    Generation: {target_car.generation_name or 'N/A'}")
        log_info(f"    Build lists count: {len(target_car_build_lists):,}")
        log_info(
            f"    Build list IDs: {[bl.id for bl in target_car_build_lists[:10]]}{'...' if len(target_car_build_lists) > 10 else ''}"
        )
    log_info(f"{'='*60}\n")

    elapsed = time.time() - start_time
    log_info(f"✓ Completed admin build lists creation (took {elapsed:.1f}s)")

    return build_lists, large_build_list, target_car


def create_sample_votes(
    db: Session,
    users: list[User],
    cars: Optional[list[Car]],
    build_lists: Optional[list[BuildList]],
    global_parts: list[GlobalPart],
) -> list[Vote]:
    """Create sample votes."""
    start_time = time.time()
    log_section("Creating sample votes...")

    # Query existing votes from database to avoid duplicates
    log_info("Checking for existing votes in database...")
    existing_votes = db.query(Vote).all()
    existing_vote_keys = {
        (vote.user_id, vote.entity_type, vote.entity_id) for vote in existing_votes
    }
    log_info(f"Found {len(existing_vote_keys):,} existing votes in database")

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

    votes_data = []
    used_combinations = set()

    # Start with existing vote keys to avoid duplicates
    used_combinations.update(existing_vote_keys)

    # Filter initial votes to only include new ones
    for vote in initial_votes:
        key = (vote["user_id"], vote["entity_type"], vote["entity_id"])
        if key not in used_combinations:
            votes_data.append(vote)
            used_combinations.add(key)

    # Generate additional votes - target 5000 total (to test pagination)
    vote_types = ["upvote", "upvote", "upvote", "downvote"]  # Mostly upvotes

    for i in range(4986):  # 4986 more to reach 5000 total
        user = random.choice(users)
        entity_type = random.choice(entity_types)
        vote_type = random.choice(vote_types)

        # Choose entity based on type
        if entity_type == "car_generation" and cars is not None and len(cars) > 0:
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

        # Check if this combination already exists (in memory or database)
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

    # If no new votes to create, return existing votes
    if not votes_data:
        log_info("No new votes to create, all votes already exist")
        return existing_votes

    votes = []
    batch_size = 500
    total = len(votes_data)

    log_info(f"Processing {total:,} new votes in batches of {batch_size}...")

    for i, vote_data in enumerate(votes_data):
        vote = Vote(**vote_data)
        db.add(vote)
        votes.append(vote)

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Votes")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} votes)...")

    db.commit()
    for vote in votes:
        db.refresh(vote)

    # Combine new votes with existing ones for return
    all_votes = list(existing_votes) + votes

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {len(votes):,} new votes, {len(all_votes):,} total (took {elapsed:.1f}s)"
    )
    return all_votes


def create_sample_reports(
    db: Session, users: list[User], global_parts: list[GlobalPart]
) -> list[Report]:
    """Create sample reports."""
    start_time = time.time()
    log_section("Creating sample reports...")

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

    # Generate additional reports - target 2500 total (to test pagination)
    for i in range(2498):  # 2498 more to reach 2500 total
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
    batch_size = 500
    total = len(reports_data)

    log_info(f"Processing {total:,} reports in batches of {batch_size}...")

    for i, report_data in enumerate(reports_data):
        report = Report(**report_data)
        db.add(report)
        reports.append(report)

        # Commit in batches for better performance
        if (i + 1) % batch_size == 0:
            db.commit()
            batch_num = i // batch_size + 1
            log_progress(min(i + 1, total), total, "Reports")
            log_info(f"  Committed batch {batch_num} ({batch_size:,} reports)...")

    db.commit()
    for report in reports:
        db.refresh(report)

    elapsed = time.time() - start_time
    log_info(f"✓ Created {len(reports):,} reports (took {elapsed:.1f}s)")
    return reports


def create_sample_build_logs(
    db: Session, build_lists: list[BuildList], users: list[User]
) -> tuple[list[BuildLog], list[BuildLogPost]]:
    """Create sample build logs and build log posts."""
    start_time = time.time()
    log_section("Creating sample build logs and posts...")

    build_logs = []
    build_log_posts = []

    # Post content templates
    post_templates = [
        "Just installed this part today! Initial impressions are great.",
        "Update: After 1000 miles, this part is holding up well.",
        "Had some issues with installation, but got it sorted out.",
        "This mod completely transformed the car's performance!",
        "Worth every penny. Highly recommend to others.",
        "Took it to the track this weekend and it performed flawlessly.",
        "Minor issue with fitment, but nothing a little adjustment couldn't fix.",
        "The sound improvement alone makes this worth it.",
        "Great quality build, very impressed with the craftsmanship.",
        "Update: Still going strong after 6 months of daily driving.",
        "This is exactly what I was looking for. Perfect fit!",
        "Had to make some custom modifications, but it works great now.",
        "The performance gains are noticeable, especially on the highway.",
        "Installation was straightforward, took about 2 hours.",
        "Love the look and feel of this upgrade.",
        "Wish I had done this mod sooner!",
        "Great value for the money.",
        "No complaints so far, everything working as expected.",
        "This part exceeded my expectations.",
        "Would definitely buy again if I had another car.",
        "The difference is night and day compared to stock.",
        "Perfect for my build goals.",
        "Quality is top-notch, no regrets here.",
        "This mod really completes the build.",
        "Highly satisfied with this purchase.",
    ]

    # Create a build log for each build list
    build_logs_to_create = []
    for build_list in build_lists:
        # Check if build log already exists
        existing_log = (
            db.query(BuildLog).filter(BuildLog.build_list_id == build_list.id).first()
        )
        if existing_log:
            build_logs.append(existing_log)
            continue

        # Create build log with a title based on the build list
        build_log = BuildLog(
            build_list_id=build_list.id,
            title=f"{build_list.name} - Build Log",
        )
        db.add(build_log)
        build_logs_to_create.append((build_log, build_list))

    # Commit all build logs first
    db.commit()
    log_info(f"✓ Created {len(build_logs_to_create):,} build logs")

    # Refresh build logs to get IDs
    for build_log, _ in build_logs_to_create:
        db.refresh(build_log)
        build_logs.append(build_log)

    # Create posts for each build log
    total_posts_created = 0
    batch_size = 500
    total_build_logs = len(build_logs_to_create)

    # Estimate total posts (200-300 per build log)
    estimated_posts = total_build_logs * 250
    log_info(
        f"Creating posts for {total_build_logs:,} build logs (estimated {estimated_posts:,} posts)..."
    )

    for log_idx, (build_log, build_list) in enumerate(build_logs_to_create):
        # Create 200+ posts per build log to test pagination (limit=100)
        # This ensures we need at least 2 pages
        num_posts = random.randint(200, 300)  # 200-300 posts per build log

        for i in range(num_posts):
            user = random.choice(users)
            content = random.choice(post_templates)
            # Add some variation to posts
            if i > 0 and random.random() < 0.3:  # 30% chance to reference previous post
                content = f"Following up on the previous discussion: {content}"

            # Create posts with varying timestamps to test ordering
            post_time = datetime.now(UTC) - timedelta(
                days=random.randint(0, 365), hours=random.randint(0, 23)
            )

            post = BuildLogPost(
                build_log_id=build_log.id,
                user_id=user.id,
                content=content,
                created_at=post_time,
                updated_at=post_time,
            )
            db.add(post)
            build_log_posts.append(post)
            total_posts_created += 1

            # Commit in batches to avoid memory issues
            if total_posts_created % batch_size == 0:
                db.commit()
                batch_num = total_posts_created // batch_size
                log_progress(total_posts_created, estimated_posts, "Build Log Posts")
                log_info(
                    f"  Committed batch {batch_num} ({batch_size:,} posts, {total_posts_created:,} total)..."
                )

        # Log progress every 100 build logs
        if (log_idx + 1) % 100 == 0:
            log_info(
                f"  Processed {log_idx + 1:,}/{total_build_logs:,} build logs ({total_posts_created:,} posts created so far)..."
            )

    # Final commit for any remaining posts
    db.commit()

    # Refresh all build logs
    for build_log in build_logs:
        db.refresh(build_log)

    elapsed = time.time() - start_time
    log_info(
        f"✓ Created {len(build_logs):,} build logs with {len(build_log_posts):,} total posts (took {elapsed:.1f}s)"
    )
    return build_logs, build_log_posts


def check_section_complete(db: Session, section_name: str, min_count: int) -> bool:
    """Check if a section has already been populated with sufficient data."""
    try:
        if section_name == "users":
            count = db.query(User).count()
            return count >= min_count
        elif section_name == "categories":
            count = db.query(Category).count()
            return count >= min_count
        elif section_name == "cars":
            count = db.query(Car).count()
            return count >= min_count
        elif section_name == "global_parts":
            count = db.query(GlobalPart).count()
            return count >= min_count
        elif section_name == "build_lists":
            count = db.query(BuildList).count()
            return count >= min_count
        elif section_name == "build_list_parts":
            count = db.query(BuildListPart).count()
            return count >= min_count
        elif section_name == "votes":
            count = db.query(Vote).count()
            return count >= min_count
        elif section_name == "reports":
            count = db.query(Report).count()
            return count >= min_count
        elif section_name == "build_logs":
            count = db.query(BuildLog).count()
            return count >= min_count
        return False
    except Exception:
        return False


def main() -> None:
    """Main function to populate all tables."""
    parser = argparse.ArgumentParser(
        description="Populate database with sample data for testing pagination"
    )
    parser.add_argument(
        "--skip-complete",
        action="store_true",
        help="Skip sections that are already complete (have sufficient data)",
    )
    parser.add_argument(
        "--skip",
        nargs="+",
        choices=[
            "users",
            "categories",
            "cars",
            "global_parts",
            "build_lists",
            "build_list_parts",
            "votes",
            "reports",
            "build_logs",
        ],
        help="Skip specific sections",
    )
    parser.add_argument(
        "--admin-build-lists",
        action="store_true",
        help="Create many build lists for admin user with one having many parts (runs separately)",
    )
    parser.add_argument(
        "--num-admin-build-lists",
        type=int,
        default=100,
        help="Number of admin build lists to create (default: 100)",
    )
    parser.add_argument(
        "--parts-per-large-list",
        type=int,
        default=200,
        help="Number of parts for the large build list (default: 200)",
    )
    parser.add_argument(
        "--parts-per-regular-list",
        type=int,
        default=5,
        help="Number of parts per regular build list (default: 5)",
    )
    parser.add_argument(
        "--num-build-lists-for-car",
        type=int,
        default=50,
        help="Number of build lists to create for a specific car generation (default: 50)",
    )
    parser.add_argument(
        "--target-car-make",
        type=str,
        default=None,
        help="Make of the target car generation (e.g., 'Honda')",
    )
    parser.add_argument(
        "--target-car-model",
        type=str,
        default=None,
        help="Model of the target car generation (e.g., 'Civic')",
    )
    parser.add_argument(
        "--target-car-generation",
        type=str,
        default=None,
        help="Generation name of the target car (e.g., '10th Gen')",
    )
    args = parser.parse_args()

    # Create all tables if they don't exist
    print("Creating database tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print("Database tables ready.")

    db: Session = SessionLocal()
    script_start_time = time.time()

    try:
        # Handle admin build lists separately
        if args.admin_build_lists:
            print("=" * 60)
            print("Creating admin build lists...")
            print("=" * 60)

            # Load required data
            users = db.query(User).all()
            if not users:
                raise ValueError(
                    "No users found. Please run the main script first to create users."
                )

            cars = db.query(Car).all()
            if not cars:
                raise ValueError(
                    "No cars found. Please run the main script first to create cars."
                )

            global_parts = db.query(GlobalPart).all()
            if not global_parts:
                raise ValueError(
                    "No global parts found. Please run the main script first to create global parts."
                )

            # Create admin build lists
            build_lists, large_build_list, target_car = create_admin_build_lists(
                db=db,
                users=users,
                cars=cars,
                global_parts=global_parts,
                num_build_lists=args.num_admin_build_lists,
                parts_per_regular_list=args.parts_per_regular_list,
                parts_per_large_list=args.parts_per_large_list,
                num_build_lists_for_car=args.num_build_lists_for_car,
                target_car_make=args.target_car_make,
                target_car_model=args.target_car_model,
                target_car_generation=args.target_car_generation,
            )

            total_elapsed = time.time() - script_start_time
            log_section("Admin build lists creation complete!")
            log_info(
                f"\nTotal time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)"
            )
            log_info(f"\n{'='*60}")
            log_info("IMPORTANT: Large build list for testing")
            log_info(f"{'='*60}")
            log_info(f"  Build List ID: {large_build_list.id}")
            log_info(f"  Build List Name: {large_build_list.name}")
            log_info(f"  User: admin")
            log_info(f"{'='*60}\n")
            if target_car and args.num_build_lists_for_car > 0:
                target_car_build_lists = [
                    bl for bl in build_lists if bl.car_id == target_car.id
                ]
                log_info(f"\n{'='*60}")
                log_info("IMPORTANT: Target car generation with many build lists")
                log_info(f"{'='*60}")
                log_info(f"  Car Make: {target_car.car_make_name}")
                log_info(f"  Car Model: {target_car.car_model_name}")
                log_info(f"  Car Generation: {target_car.generation_name or 'N/A'}")
                log_info(f"  Car ID: {target_car.id}")
                log_info(f"  Build Lists Count: {len(target_car_build_lists):,}")
                log_info(f"  User: admin")
                log_info(f"{'='*60}\n")
            return

        print("=" * 60)
        print("Populating database with sample data...")
        print("=" * 60)
        # Track what we've created
        users = None
        categories = None
        cars = None
        global_parts = None
        build_lists = None
        build_list_parts = None
        votes = None
        reports = None
        build_logs = None
        build_log_posts = None

        # Create all sample data with skip logic
        skip_list = set(args.skip or [])

        # Users
        if "users" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "users", 2500)
        ):
            users = create_sample_users(db)
        else:
            log_section("Skipping users (already complete or skipped)")
            users = db.query(User).all()

        # Categories
        if "categories" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "categories", 7)
        ):
            categories = create_sample_categories(db)
        else:
            log_section("Skipping categories (already complete or skipped)")
            categories = db.query(Category).all()

        # Cars are now centrally managed (car generations, not user-owned)
        if "cars" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "cars", 700)
        ):
            cars = create_sample_cars(db)
        else:
            log_section("Skipping cars (already complete or skipped)")
            cars = db.query(Car).all()

        # Global Parts
        if "global_parts" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "global_parts", 2500)
        ):
            global_parts = create_sample_global_parts(db, users, categories)
        else:
            log_section("Skipping global_parts (already complete or skipped)")
            global_parts = db.query(GlobalPart).all()

        # Build lists require a car_id (now mandatory)
        if "build_lists" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "build_lists", 2500)
        ):
            build_lists = create_sample_build_lists(db, users, cars)
        else:
            log_section("Skipping build_lists (already complete or skipped)")
            build_lists = db.query(BuildList).all()

        # Build List Parts
        if "build_list_parts" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "build_list_parts", 4000)
        ):
            build_list_parts = create_sample_build_list_parts(
                db, build_lists, global_parts, users
            )
        else:
            log_section("Skipping build_list_parts (already complete or skipped)")
            build_list_parts = db.query(BuildListPart).all()

        # Votes
        if "votes" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "votes", 4000)
        ):
            votes = create_sample_votes(db, users, cars, build_lists, global_parts)
        else:
            log_section("Skipping votes (already complete or skipped)")
            votes = db.query(Vote).all()

        # Reports
        if "reports" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "reports", 2000)
        ):
            reports = create_sample_reports(db, users, global_parts)
        else:
            log_section("Skipping reports (already complete or skipped)")
            reports = db.query(Report).all()

        # Build Logs
        if "build_logs" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "build_logs", 2000)
        ):
            build_logs, build_log_posts = create_sample_build_logs(
                db, build_lists, users
            )
        else:
            log_section("Skipping build_logs (already complete or skipped)")
            build_logs = db.query(BuildLog).all()
            build_log_posts = []

        total_elapsed = time.time() - script_start_time
        log_section("Sample data population complete!")
        log_info("\nSummary:")
        log_info(f"  Users: {len(users) if users else 0:,}")
        log_info(f"  Categories: {len(categories) if categories else 0:,}")
        log_info(f"  Car Generations: {len(cars) if cars else 0:,}")
        log_info(f"  Global Parts: {len(global_parts) if global_parts else 0:,}")
        log_info(f"  Build Lists: {len(build_lists) if build_lists else 0:,}")
        log_info(
            f"  Build List Parts: {len(build_list_parts) if build_list_parts else 0:,}"
        )
        log_info(f"  Votes: {len(votes) if votes else 0:,}")
        log_info(f"  Reports: {len(reports) if reports else 0:,}")
        log_info(f"  Build Logs: {len(build_logs) if build_logs else 0:,}")
        log_info(
            f"  Build Log Posts: {len(build_log_posts) if build_log_posts else 0:,}"
        )
        log_info(f"\nTotal time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
        log_info("\nTest credentials:")
        log_info("  Admin: admin / admin123")
        log_info("  User: john_doe / password123")
        log_info("  User: jane_smith / password123")
        log_section("Done!")

    except Exception as e:
        db.rollback()
        log_info(f"❌ Error populating database: {e}")
        import traceback

        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
