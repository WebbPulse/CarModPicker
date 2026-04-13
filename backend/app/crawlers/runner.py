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
    CRAWL_HTML_SAVE_DIR: directory path to save full page HTML (always saved for every URL crawled).
"""

import argparse
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.crawlers.adapters import ADAPTER_REGISTRY, get_adapter
from app.crawlers.base import (
    DEFAULT_REQUEST_DELAY_SEC,
    DEFAULT_USER_AGENT,
    apply_delay_jitter,
    can_fetch_url,
    canonicalize_url,
    crawl_html_fingerprint,
    fetch_page,
    get_crawl_delay_sec,
    ingest_payload,
    save_crawl_page_html,
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
    Return the crawler service account (is_service_account=True).
    Falls back to CRAWLER_USER_ID env var for backwards compatibility with local/CLI usage.
    Raises CrawlerConfigError when neither resolves (API-safe; does not sys.exit).
    """
    user = db.query(DBUser).filter(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False)).first()
    if user:
        return user

    # Fallback: legacy env-var path (CLI / local dev before service account is seeded)
    raw = os.environ.get("CRAWLER_USER_ID")
    if raw:
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

    raise CrawlerConfigError(
        "No crawler service account found and CRAWLER_USER_ID is not set. "
        "Ensure the app has run its startup initialisation (which creates the service account)."
    )


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


def _upsert_crawled_page(
    db: Session,
    *,
    url: str,
    source: str,
    storage_key: Optional[str],
    part_id: Optional[int],
    html_sha256: Optional[str] = None,
) -> None:
    """
    Create or update a CrawledPage record for the given URL.
    storage_key is an S3 key (no leading "/") or an absolute local path (starts with "/").
    part_id, when provided, marks the parse as successful.
    Calls db.flush() — caller is responsible for the surrounding commit.
    """
    now = datetime.now(timezone.utc)

    html_s3_key: Optional[str] = None
    html_local_path: Optional[str] = None
    if storage_key:
        if storage_key.startswith("/"):
            html_local_path = storage_key
        else:
            html_s3_key = storage_key

    insert_values: dict = {
        "url": url,
        "source": source,
        "crawled_at": now,
        "parse_status": "pending",
        "html_s3_key": html_s3_key,
        "html_local_path": html_local_path,
        "global_part_id": part_id,
    }
    if part_id is not None:
        insert_values["parse_status"] = "parsed"
        insert_values["last_parsed_at"] = now
    if html_sha256 is not None:
        insert_values["html_sha256"] = html_sha256

    update_values: dict = {"crawled_at": now}
    if html_s3_key is not None:
        update_values["html_s3_key"] = html_s3_key
    if html_local_path is not None:
        update_values["html_local_path"] = html_local_path
    if part_id is not None:
        update_values["global_part_id"] = part_id
        update_values["parse_status"] = "parsed"
        update_values["last_parsed_at"] = now
    if html_sha256 is not None:
        update_values["html_sha256"] = html_sha256

    stmt = (
        pg_insert(DBCrawledPage)
        .values(**insert_values)
        .on_conflict_do_update(index_elements=["url"], set_=update_values)
    )
    db.execute(stmt)
    db.flush()


def run_crawler(
    adapter_name: str,
    *,
    limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    user_id: Optional[int] = None,
    default_category_id: Optional[int] = None,
    crawl_html_save_dir: Optional[str] = None,
    stop_event: Optional[threading.Event] = None,
    skip_known_urls: bool = False,
) -> dict:
    """
    Run one adapter: discover URLs, fetch, parse, ingest. Optionally cap at `limit` URLs.
    If user_id or default_category_id are provided, use them; otherwise fall back to env vars.
    Saves full page HTML to the archive for every URL crawled (new and previously-seen).
    If stop_event is provided and set, the loop exits early (cooperative cancellation).
    If skip_known_urls is True, URLs already in crawled_pages with parse_status='parsed' are
    filtered out before the limit is applied — useful for successive test runs against the same site.
    Returns a dict: {"adapter": name, "ingested": int, "skipped": int, "errors": int, "total": int}.
    Raises CrawlerConfigError or KeyError (unknown adapter) on setup failure.
    """
    db: Session = SessionLocal()
    try:
        user = _resolve_crawler_user(db, user_id)
        cat_id = _resolve_default_category_id(db, default_category_id)
        adapter = get_adapter(adapter_name)

        urls = list(adapter.discover_product_urls())
        if skip_known_urls and urls:
            canonical_urls = [canonicalize_url(u) for u in urls]
            already_parsed = {
                row.url
                for row in db.query(DBCrawledPage.url)
                .filter(
                    DBCrawledPage.url.in_(canonical_urls),
                    DBCrawledPage.parse_status == "parsed",
                )
                .all()
            }
            before = len(urls)
            urls = [u for u in urls if canonicalize_url(u) not in already_parsed]
            logger.info(
                "Adapter %s: skipped %s already-parsed URL(s), %s remaining.",
                adapter_name,
                before - len(urls),
                len(urls),
            )
        if limit is not None:
            urls = urls[:limit]
        total = len(urls)
        logger.info("Adapter %s: %s URL(s) to process.", adapter_name, total)

        ingested = 0
        skipped = 0
        errors = 0

        for i, url in enumerate(urls, 1):
            if stop_event is not None and stop_event.is_set():
                logger.info("Adapter %s: stop requested, exiting after %s/%s URLs.", adapter_name, i - 1, total)
                break
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
                arch_url = canonicalize_url(url)
                html_utf8, _, html_sha = crawl_html_fingerprint(html)
                existing = db.query(DBCrawledPage).filter(DBCrawledPage.url == arch_url).first()
                storage_key: Optional[str]
                if existing and existing.html_sha256 == html_sha and (existing.html_s3_key or existing.html_local_path):
                    storage_key = existing.html_s3_key or existing.html_local_path
                else:
                    storage_key = save_crawl_page_html(
                        adapter_name,
                        arch_url,
                        html,
                        "",
                        html_utf8=html_utf8,
                        logger_instance=logger,
                    )
                part = ingest_payload(
                    db,
                    payload,
                    current_user=user,
                    default_category_id=cat_id,
                    logger=logger,
                    source="scraped",
                )
                _upsert_crawled_page(
                    db,
                    url=arch_url,
                    source=adapter_name,
                    storage_key=storage_key,
                    part_id=part.id,
                    html_sha256=html_sha,
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
    stop_event: Optional[threading.Event] = None,
    skip_known_urls: bool = False,
) -> dict:
    """
    Run one or more adapters. If multiple adapters, runs them in parallel threads by default.

    Args:
        adapter_names: List of adapter names (e.g. ["a90shop", "example"]).
        limits: Per-adapter limits: {"a90shop": 10, "example": 5}. Overrides global_limit when set.
        global_limit: Limit applied to all adapters when no per-adapter limit is set.
        delay_sec: Delay between requests per crawler.
        parallel: If True and len(adapter_names) > 1, run in parallel threads.
        crawl_html_save_dir: Kept for backward compatibility; HTML is always archived for every URL.
        stop_event: Optional threading.Event for cooperative cancellation across all adapters.
        skip_known_urls: If True, URLs already archived with parse_status='parsed' are filtered out
            before the limit is applied.

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
                stop_event=stop_event,
                skip_known_urls=skip_known_urls,
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
    parser.add_argument(
        "--skip-known",
        action="store_true",
        default=False,
        help="Skip URLs already in crawled_pages with parse_status='parsed'.",
    )
    args = parser.parse_args()

    try:
        run_crawler(args.adapter, limit=args.limit, delay_sec=args.delay, skip_known_urls=args.skip_known)
    except CrawlerConfigError as e:
        logger.error("%s", e)
        sys.exit(1)
    except KeyError as e:
        logger.error("Unknown adapter: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
