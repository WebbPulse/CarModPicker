"""Sample BuildList creator."""

import random
import time

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


def create_sample_build_lists(
    db: Session, users: list[User], cars: list[CarGeneration]
) -> list[BuildList]:
    """Create sample build lists."""
    start_time = time.time()
    log_section("Creating sample build lists...")

    # Initial build lists - find cars by make/model to ensure correct references
    # Helper to find a car by make and model
    def find_car(
        make: str, model: str, generation_name: str | None = None
    ) -> CarGeneration | None:
        for car in cars:
            if car.car_make_name == make and car.car_model_name == model:
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
