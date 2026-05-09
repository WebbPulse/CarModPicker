"""Sample User creator."""

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.api.dependencies.auth import (  # pyright: ignore[reportMissingImports]
    get_password_hash,
)
from app.api.models.user import User  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


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
