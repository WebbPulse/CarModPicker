"""Sample Vote creator."""

import random
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.car_generation import CarGeneration  # pyright: ignore[reportMissingImports]
from app.api.models.part import Part  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]
from app.api.models.vote import Vote  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


def create_sample_votes(
    db: Session,
    users: list[User],
    cars: Optional[list[CarGeneration]],
    build_lists: Optional[list[BuildList]],
    global_parts: list[Part],
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
