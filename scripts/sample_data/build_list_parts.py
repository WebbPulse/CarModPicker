"""Sample BuildListPart creator."""

import random
import time

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.build_list_part import (  # pyright: ignore[reportMissingImports]
    BuildListPart,
)
from app.api.models.part import Part  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


def create_sample_build_list_parts(
    db: Session,
    build_lists: list[BuildList],
    global_parts: list[Part],
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
