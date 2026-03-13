"""
Crawler runner: discover URLs from an adapter, fetch, parse, and ingest.

Run from backend directory:
    python -m app.crawlers --adapter example
    python -m app.crawlers --adapter example --limit 5

Requires env:
    CRAWLER_USER_ID: user ID to attribute created parts to (must have create permission).
    CRAWLER_DEFAULT_CATEGORY_ID: category ID for new parts (optional if CRAWLER_DEFAULT_CATEGORY_NAME set).
    CRAWLER_DEFAULT_CATEGORY_NAME: category name (e.g. exhaust) for new parts (used if category_id not set).

Optional (full-page archive for post-processing):
    CRAWL_HTML_SAVE_DIR: directory path to save full page HTML (new URLs only unless CRAWL_HTML_SAVE_ON_RECRAWL=1).
    CRAWL_HTML_SAVE_ON_RECRAWL: set to 1/true/yes to also overwrite saved HTML when recrawling known URLs.
"""

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.crawlers.adapters import ADAPTER_REGISTRY, get_adapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    DEFAULT_USER_AGENT,
    apply_delay_jitter,
    can_fetch_url,
    fetch_page,
    get_crawl_delay_sec,
    ingest_payload,
    save_crawl_page_html,
    url_is_known,
)
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class CrawlerConfigError(ValueError):
    """Raised when crawler env/config is invalid (CRAWLER_USER_ID, category, etc)."""

    pass


def _get_crawler_user(db: Session) -> DBUser:
    """
    Load crawler user by CRAWLER_USER_ID.
    Raises CrawlerConfigError if not set or not found (API-safe; does not sys.exit).
    """
    raw = os.environ.get("CRAWLER_USER_ID")
    if not raw:
        raise CrawlerConfigError(
            "CRAWLER_USER_ID is not set. Set it to the user ID that should own crawler-created parts."
        )
    try:
        user_id = int(raw)
    except ValueError:
        raise CrawlerConfigError("CRAWLER_USER_ID must be an integer.")
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not user:
        raise CrawlerConfigError(f"CRAWLER_USER_ID={user_id}: no user found.")
    if user.disabled:
        raise CrawlerConfigError(f"CRAWLER_USER_ID={user_id}: user is disabled.")
    return user


def _resolve_crawler_user(db: Session, user_id_override: Optional[int] = None) -> DBUser:
    """
    Resolve crawler user. Uses user_id_override if provided, else CRAWLER_USER_ID env.
    """
    if user_id_override is not None:
        user = db.query(DBUser).filter(DBUser.id == user_id_override).first()
        if not user:
            raise CrawlerConfigError(f"Crawler user_id={user_id_override}: no user found.")
        if user.disabled:
            raise CrawlerConfigError(f"Crawler user_id={user_id_override}: user is disabled.")
        return user
    return _get_crawler_user(db)


def _resolve_default_category_id(db: Session, category_id_override: Optional[int] = None) -> int:
    """
    Resolve default category. Uses category_id_override if provided, else env vars.
    """
    if category_id_override is not None:
        cat = db.query(DBCategory).filter(DBCategory.id == category_id_override).first()
        if not cat or not cat.is_active:
            raise CrawlerConfigError(f"Default category_id={category_id_override}: not found or inactive.")
        return cat.id
    return _get_default_category_id(db)


def _get_default_category_id(db: Session) -> int:
    """
    Resolve default category from CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME.
    Raises CrawlerConfigError if no category can be resolved (API-safe; does not sys.exit).
    """
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

    raise CrawlerConfigError(
        "No default category. Set CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME, "
        "or ensure categories are seeded."
    )


def run_crawler(
    adapter_name: str,
    *,
    limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    user_id: Optional[int] = None,
    default_category_id: Optional[int] = None,
    crawl_html_save_dir: Optional[str] = None,
    crawl_html_save_on_recrawl: Optional[bool] = None,
) -> dict:
    """
    Run one adapter: discover URLs, fetch, parse, ingest. Optionally cap at `limit` URLs.
    If user_id or default_category_id are provided, use them; otherwise fall back to env vars.
    When crawl_html_save_dir is set (or CRAWL_HTML_SAVE_DIR env), saves full page HTML for new URLs
    (or all URLs if crawl_html_save_on_recrawl / CRAWL_HTML_SAVE_ON_RECRAWL is True).
    Returns a dict: {"adapter": name, "ingested": int, "skipped": int, "errors": int, "total": int}.
    Raises CrawlerConfigError or KeyError (unknown adapter) on setup failure.
    """
    db: Session = SessionLocal()
    try:
        user = _resolve_crawler_user(db, user_id)
        cat_id = _resolve_default_category_id(db, default_category_id)
        adapter = get_adapter(adapter_name)

        urls = list(adapter.discover_product_urls())
        if limit is not None:
            urls = urls[:limit]
        total = len(urls)
        logger.info("Adapter %s: %s URL(s) to process.", adapter_name, total)

        ingested = 0
        skipped = 0
        errors = 0

        # Optional: save full page HTML for new URLs (or all if save_on_recrawl)
        save_dir_str = (crawl_html_save_dir or "").strip() or os.environ.get("CRAWL_HTML_SAVE_DIR", "").strip()
        save_on_recrawl = crawl_html_save_on_recrawl
        if save_on_recrawl is None:
            save_on_recrawl = os.environ.get("CRAWL_HTML_SAVE_ON_RECRAWL", "0").strip().lower() in (
                "1",
                "true",
                "yes",
            )
        save_dir: Optional[Path] = Path(save_dir_str) if save_dir_str else None
        if save_dir is not None:
            logger.info(
                "Saving full page HTML (prefix: %s; overwrite on recrawl: %s)",
                save_dir_str,
                save_on_recrawl,
            )
        else:
            logger.debug("Crawl HTML save disabled (no directory/prefix set)")

        for i, url in enumerate(urls, 1):
            try:
                if i > 1:
                    # Honor robots.txt Crawl-delay if set; use the larger of --delay and directive
                    crawl_delay = get_crawl_delay_sec(url, DEFAULT_USER_AGENT)
                    base_delay = max(delay_sec, crawl_delay or 0)
                    actual_delay = apply_delay_jitter(base_delay)
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
                url_known = url_is_known(db, url)
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
                # Save full page copy for new URLs, or for all if save_on_recrawl is set
                if save_dir and (not url_known or save_on_recrawl):
                    save_crawl_page_html(
                        adapter_name,
                        url,
                        html,
                        save_dir,
                        logger_instance=logger,
                    )
                ingest_payload(
                    db,
                    payload,
                    current_user=user,
                    default_category_id=cat_id,
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
        return {
            "adapter": adapter_name,
            "ingested": ingested,
            "skipped": skipped,
            "errors": errors,
            "total": total,
        }
    finally:
        db.close()


def run_crawlers(
    adapter_names: list[str],
    *,
    limits: Optional[dict[str, int]] = None,
    global_limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    parallel: bool = True,
    user_id: Optional[int] = None,
    default_category_id: Optional[int] = None,
    crawl_html_save_dir: Optional[str] = None,
    crawl_html_save_on_recrawl: Optional[bool] = None,
) -> dict:
    """
    Run one or more adapters. If multiple adapters, runs them in parallel threads by default.

    Args:
        adapter_names: List of adapter names (e.g. ["a90shop", "example"]).
        limits: Per-adapter limits: {"a90shop": 10, "example": 5}. Overrides global_limit when set.
        global_limit: Limit applied to all adapters when no per-adapter limit is set.
        delay_sec: Delay between requests per crawler.
        parallel: If True and len(adapter_names) > 1, run in parallel threads.
        crawl_html_save_dir: If set, save full page HTML (new URLs only unless crawl_html_save_on_recrawl).
        crawl_html_save_on_recrawl: If True and crawl_html_save_dir set, also overwrite HTML on recrawl.

    Returns:
        {
            "results": [{"adapter": str, "ingested": int, "skipped": int, "errors": int, "total": int}, ...],
            "summary": {"total_ingested": int, "total_skipped": int, "total_errors": int},
            "failed": [{"adapter": str, "error": str}, ...],
        }
    """
    limits = limits or {}
    results: list[dict] = []
    failed: list[dict] = []

    def run_one(name: str) -> dict | None:
        limit = limits.get(name)
        if limit is None and global_limit is not None:
            limit = global_limit
        try:
            return run_crawler(
                name,
                limit=limit,
                delay_sec=delay_sec,
                user_id=user_id,
                default_category_id=default_category_id,
                crawl_html_save_dir=crawl_html_save_dir,
                crawl_html_save_on_recrawl=crawl_html_save_on_recrawl,
            )
        except (CrawlerConfigError, KeyError) as e:
            return {"_error": str(e), "_adapter": name}
        except Exception as e:
            logger.exception("Crawler %s failed: %s", name, e)
            return {"_error": str(e), "_adapter": name}

    if len(adapter_names) > 1 and parallel:
        with ThreadPoolExecutor(max_workers=len(adapter_names)) as executor:
            futures = {executor.submit(run_one, name): name for name in adapter_names}
            for future in as_completed(futures):
                r = future.result()
                if r is None:
                    continue
                if "_error" in r:
                    failed.append({"adapter": r["_adapter"], "error": r["_error"]})
                else:
                    results.append(r)
    else:
        for name in adapter_names:
            r = run_one(name)
            if r is None:
                continue
            if "_error" in r:
                failed.append({"adapter": r["_adapter"], "error": r["_error"]})
            else:
                results.append(r)

    total_ingested = sum(r.get("ingested", 0) for r in results)
    total_skipped = sum(r.get("skipped", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)

    return {
        "results": results,
        "summary": {
            "total_ingested": total_ingested,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
        },
        "failed": failed,
    }


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

    try:
        run_crawler(args.adapter, limit=args.limit, delay_sec=args.delay)
    except CrawlerConfigError as e:
        logger.error("%s", e)
        sys.exit(1)
    except KeyError as e:
        logger.error("Unknown adapter: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
