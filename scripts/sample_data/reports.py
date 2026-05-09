"""Sample Report creator."""

import random
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.models.part import Part  # pyright: ignore[reportMissingImports]
from app.api.models.report import Report  # pyright: ignore[reportMissingImports]
from app.api.models.user import User  # pyright: ignore[reportMissingImports]

from ._logging import log_info, log_progress, log_section


def create_sample_reports(
    db: Session, users: list[User], global_parts: list[Part]
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
