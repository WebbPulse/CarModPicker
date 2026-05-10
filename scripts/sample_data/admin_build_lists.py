"""Admin BuildList creator (also seeds parts into a single huge build list)."""

import random
import time

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.build_list_part import (  # pyright: ignore[reportMissingImports]
    BuildListPart,
)
from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.part import Part  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


def create_admin_build_lists(
    db: Session,
    users: list[User],
    cars: list[CarGeneration],
    global_parts: list[Part],
    num_build_lists: int = 100,
    parts_per_regular_list: int = 5,
    parts_per_large_list: int = 200,
    num_build_lists_for_car: int = 50,
    target_car_make: str | None = None,
    target_car_model: str | None = None,
    target_car_generation: str | None = None,
) -> tuple[list[BuildList], BuildList, CarGeneration | None]:
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
