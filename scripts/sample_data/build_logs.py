"""Sample BuildLog + BuildLogPost creator."""

import random
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList  # pyright: ignore[reportMissingImports]
from app.api.models.build_log import (  # pyright: ignore[reportMissingImports]
    BuildLog,
    BuildLogPost,
)
from app.api.models.user import User  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


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
