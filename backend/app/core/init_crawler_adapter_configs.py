"""
Ensure one ``crawler_adapter_configs`` row exists per registered crawler
adapter.

Called from the FastAPI lifespan on startup. Newly-added adapters appear here
automatically (disabled, with conservative defaults). Rows are NEVER removed —
tuning learned for a retailer is preserved across restarts and even across
adapter removals so re-adding a retailer reuses the known-good delay.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.crawler_adapter_config import CrawlerAdapterConfig
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC
from app.crawlers.runner import CrawlerConfigError, resolve_default_category_id

logger = logging.getLogger(__name__)


def init_crawler_adapter_configs(db: Session) -> None:
    """Insert a row for every registered adapter that doesn't already have one."""
    existing = set(
        db.scalars(
            select(CrawlerAdapterConfig.adapter_name).where(
                CrawlerAdapterConfig.adapter_name.in_(list(ADAPTER_REGISTRY.keys()))
            )
        ).all()
    )
    missing = [name for name in ADAPTER_REGISTRY.keys() if name not in existing]
    if not missing:
        return

    try:
        default_category_id = resolve_default_category_id(db)
    except CrawlerConfigError as e:
        logger.warning("Skipping crawler_adapter_configs seeding: %s", e)
        return

    for name in missing:
        db.add(
            CrawlerAdapterConfig(
                adapter_name=name,
                delay_sec=DEFAULT_REQUEST_DELAY_SEC,
                per_run_limit=None,
                skip_known_urls=False,
                default_category_id=default_category_id,
            )
        )
    db.commit()
    logger.info("Seeded %d crawler adapter config row(s): %s", len(missing), ", ".join(missing))
