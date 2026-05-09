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

The per-entity creators live in scripts/sample_data/. This file is just the
CLI shell + section-skip orchestration.
"""

import argparse
import sys
import time
from pathlib import Path

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

from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.build_list_part import (  # pyright: ignore[reportMissingImports]
    BuildListPart,
)
from app.api.models.build_log import BuildLog  # pyright: ignore[reportMissingImports]
from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.category import Category  # pyright: ignore[reportMissingImports]
from app.api.models.part import Part  # pyright: ignore[reportMissingImports]
from app.api.models.report import Report  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]
from app.api.models.vote import Vote  # pyright: ignore[reportMissingImports]
from app.db.base import (  # pyright: ignore[reportMissingImports]
    Base,
)  # Import Base to ensure all models are registered
from app.db.session import SessionLocal, engine  # pyright: ignore[reportMissingImports]

from sample_data import (
    create_admin_build_lists,
    create_sample_build_list_parts,
    create_sample_build_lists,
    create_sample_build_logs,
    create_sample_cars,
    create_sample_categories,
    create_sample_global_parts,
    create_sample_reports,
    create_sample_users,
    create_sample_votes,
    log_info,
    log_section,
)


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
            count = db.query(CarGeneration).count()
            return count >= min_count
        elif section_name == "global_parts":
            count = db.query(Part).count()
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

            cars = db.query(CarGeneration).all()
            if not cars:
                raise ValueError(
                    "No cars found. Please run the main script first to create cars."
                )

            global_parts = db.query(Part).all()
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
                log_info(f"  Make: {target_car.car_make_name}")
                log_info(f"  Model: {target_car.car_model_name}")
                log_info(f"  Generation: {target_car.generation_name or 'N/A'}")
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
            cars = db.query(CarGeneration).all()

        # Global Parts
        if "global_parts" not in skip_list and not (
            args.skip_complete and check_section_complete(db, "global_parts", 2500)
        ):
            global_parts = create_sample_global_parts(db, users, categories)
        else:
            log_section("Skipping global_parts (already complete or skipped)")
            global_parts = db.query(Part).all()

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
