"""
Ensure one ``adapter_schedules`` row exists per registered crawler adapter.

Called from the FastAPI lifespan on startup. Newly-added adapters appear here
automatically — disabled, with conservative defaults — so the admin UI can see
them without a Terraform or migration change.
"""

import logging

from sqlalchemy.orm import Session

from app.api.models.adapter_schedule import AdapterSchedule
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC
from app.crawlers.runner import CrawlerConfigError, resolve_default_category_id

logger = logging.getLogger(__name__)


def init_adapter_schedules(db: Session) -> None:
    """
    Insert a row for every registered adapter that doesn't already have one.

    Idempotent — existing rows are left untouched so admin edits persist. If the
    default category cannot be resolved (fresh DB, categories not yet seeded),
    skip seeding and log; a subsequent startup will fill the rows once the
    category table is populated.
    """
    existing = {
        name
        for (name,) in db.query(AdapterSchedule.adapter_name).filter(
            AdapterSchedule.adapter_name.in_(list(ADAPTER_REGISTRY.keys()))
        )
    }
    missing = [name for name in ADAPTER_REGISTRY.keys() if name not in existing]
    if not missing:
        return

    try:
        default_category_id = resolve_default_category_id(db)
    except CrawlerConfigError as e:
        logger.warning("Skipping adapter_schedules seeding: %s", e)
        return

    for name in missing:
        db.add(
            AdapterSchedule(
                adapter_name=name,
                enabled=False,
                schedule_expression="cron(0 2 1 * ? *)",
                delay_sec=DEFAULT_REQUEST_DELAY_SEC,
                per_run_limit=None,
                skip_known_urls=False,
                default_category_id=default_category_id,
            )
        )
    db.commit()
    logger.info("Seeded %d adapter schedule row(s): %s", len(missing), ", ".join(missing))
