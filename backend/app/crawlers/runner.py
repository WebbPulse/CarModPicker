"""
Crawler runner: discover URLs from an adapter, fetch, parse, and ingest.

Run from backend directory:
    python -m app.crawlers --adapter example
    python -m app.crawlers --adapter example --limit 5

Requires env:
    CRAWLER_USER_ID: user ID to attribute created parts to (must have create permission).
    CRAWLER_DEFAULT_CATEGORY_ID: category ID for new parts (optional if CRAWLER_DEFAULT_CATEGORY_NAME set).
    CRAWLER_DEFAULT_CATEGORY_NAME: category name (e.g. exhaust) for new parts (used if category_id not set).
"""

import argparse
import logging
import os
import sys
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    DEFAULT_USER_AGENT,
    can_fetch_url,
    fetch_page,
    get_crawl_delay_sec,
    ingest_payload,
)
from app.crawlers.adapters import ADAPTER_REGISTRY, get_adapter
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _get_crawler_user(db: Session) -> DBUser:
    """Load crawler user by CRAWLER_USER_ID. Exits with message if not set or not found."""
    raw = os.environ.get("CRAWLER_USER_ID")
    if not raw:
        logger.error(
            "CRAWLER_USER_ID is not set. Set it to the user ID that should own crawler-created parts."
        )
        sys.exit(1)
    try:
        user_id = int(raw)
    except ValueError:
        logger.error("CRAWLER_USER_ID must be an integer.")
        sys.exit(1)
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        logger.error("CRAWLER_USER_ID=%s: no user found.", user_id)
        sys.exit(1)
    if user.disabled:
        logger.error("CRAWLER_USER_ID=%s: user is disabled.", user_id)
        sys.exit(1)
    return user


def _get_default_category_id(db: Session) -> int:
    """Resolve default category from CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME."""
    raw_id = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
    if raw_id:
        try:
            cat_id = int(raw_id)
        except ValueError:
            pass
        else:
            cat = db.query(DBCategory).filter(DBCategory.id == cat_id).first()
            if cat and cat.is_active:
                return cat.id
            logger.warning("CRAWLER_DEFAULT_CATEGORY_ID=%s: category not found or inactive.", raw_id)

    name = os.environ.get("CRAWLER_DEFAULT_CATEGORY_NAME", "").strip()
    if name:
        cat = db.query(DBCategory).filter(DBCategory.name == name, DBCategory.is_active).first()
        if cat:
            return cat.id
        logger.warning("CRAWLER_DEFAULT_CATEGORY_NAME=%r: category not found or inactive.", name)

    # Fallback: first active category
    first = db.query(DBCategory).filter(DBCategory.is_active).order_by(DBCategory.sort_order).first()
    if first:
        logger.info("Using first active category: id=%s name=%s", first.id, first.name)
        return first.id

    logger.error(
        "No default category. Set CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME, "
        "or ensure categories are seeded."
    )
    sys.exit(1)


def run_crawler(
    adapter_name: str,
    *,
    limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
) -> None:
    """
    Run one adapter: discover URLs, fetch, parse, ingest. Optionally cap at `limit` URLs.
    """
    db: Session = SessionLocal()
    try:
        user = _get_crawler_user(db)
        default_category_id = _get_default_category_id(db)
        adapter = get_adapter(adapter_name)

        urls = list(adapter.discover_product_urls())
        if limit is not None:
            urls = urls[:limit]
        total = len(urls)
        logger.info("Adapter %s: %s URL(s) to process.", adapter_name, total)

        ingested = 0
        skipped = 0
        errors = 0

        for i, url in enumerate(urls, 1):
            try:
                if i > 1:
                    # Honor robots.txt Crawl-delay if set; use the larger of --delay and directive
                    crawl_delay = get_crawl_delay_sec(url, DEFAULT_USER_AGENT)
                    actual_delay = max(delay_sec, crawl_delay or 0)
                    time.sleep(actual_delay)
                if not can_fetch_url(url, DEFAULT_USER_AGENT):
                    skipped += 1
                    logger.info(
                        "[%s/%s] Skipped (robots.txt disallows): %s",
                        i,
                        total,
                        url,
                    )
                    continue
                html = fetch_page(url)
                payload = adapter.parse_product_page(html, url)
                if payload is None:
                    skipped += 1
                    logger.info(
                        "[%s/%s] Skipped (not a product page or parse failed): %s",
                        i,
                        total,
                        url,
                    )
                    continue
                ingest_payload(
                    db,
                    payload,
                    current_user=user,
                    default_category_id=default_category_id,
                    logger=logger,
                    source="scraped",
                )
                ingested += 1
                logger.info("[%s/%s] Ingested: %s", i, total, url)
            except Exception as e:
                errors += 1
                logger.exception("Error processing %s: %s", url, e)
                db.rollback()

        logger.info(
            "Done. Ingested=%s skipped=%s errors=%s",
            ingested,
            skipped,
            errors,
        )
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a retailer crawler adapter (discover URLs, fetch, parse, ingest).",
    )
    parser.add_argument(
        "--adapter",
        required=True,
        choices=list(ADAPTER_REGISTRY.keys()),
        help="Adapter name to run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of product URLs to process (default: no limit).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SEC,
        help=f"Seconds to wait between requests (default: {DEFAULT_REQUEST_DELAY_SEC}).",
    )
    args = parser.parse_args()

    run_crawler(args.adapter, limit=args.limit, delay_sec=args.delay)


if __name__ == "__main__":
    main()
