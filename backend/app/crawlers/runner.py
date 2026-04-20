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
from uuid import UUID

import requests
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
    get_crawl_delay_sec,
    ingest_payload,
    save_crawl_page_html,
)
from app.crawlers.fetchers import get_fetcher
from app.db.session import API_CONNECTION_RESERVE, DB_MAX_OVERFLOW, DB_POOL_SIZE, SessionLocal

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


def resolve_crawler_user(db: Session, user_id_override: Optional[UUID] = None) -> DBUser:
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


def resolve_default_category_id(db: Session, category_id_override: Optional[UUID] = None) -> UUID:
    """
    Resolve default category. Uses category_id_override if provided, else env vars.
    """
    if category_id_override is not None:
        cat = db.query(DBCategory).filter(DBCategory.id == category_id_override).first()
        if not cat or not cat.is_active:
            raise CrawlerConfigError(f"Default category_id={category_id_override}: not found or inactive.")
        return cat.id
    return _get_default_category_id(db)


def _get_default_category_id(db: Session) -> UUID:
    """
    Resolve default category from CRAWLER_DEFAULT_CATEGORY_ID or CRAWLER_DEFAULT_CATEGORY_NAME.
    Raises CrawlerConfigError if no category can be resolved (API-safe; does not sys.exit).
    """
    raw_id = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
    if raw_id:
        try:
            cat_id = UUID(raw_id)
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
    part_id: Optional[UUID],
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
        "part_id": part_id,
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
        update_values["part_id"] = part_id
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
    user_id: Optional[UUID] = None,
    default_category_id: Optional[UUID] = None,
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
    # Fetcher is constructed inside the try block (after we know the adapter
    # exists); bound here at None so the finally block's cleanup pass is safe
    # even when we fail before construction.
    fetcher = None
    try:
        # Bail before we spend time on discovery (which itself does network
        # I/O for sitemaps and can sit in retry-backoff loops).
        if stop_event is not None and stop_event.is_set():
            logger.info("Adapter %s: cancelled before discovery.", adapter_name)
            return {"adapter": adapter_name, "ingested": 0, "skipped": 0, "errors": 0, "total": 0, "cancelled": True}
        user = resolve_crawler_user(db, user_id)
        cat_id = resolve_default_category_id(db, default_category_id)
        # Construct the fetcher matching this adapter's declared tier before the
        # adapter itself, so the adapter's discover_product_urls() (which may
        # need the upgraded fetcher for sitemap calls on Tier 1/2 sites) can
        # use self.fetcher. Existing Tier 0 adapters that call module-level
        # fetch_page() directly are unaffected — they get an HttpFetcher they
        # simply don't touch.
        adapter_cls = ADAPTER_REGISTRY[adapter_name] if adapter_name in ADAPTER_REGISTRY else None
        tier = adapter_cls.FETCHER_TIER if adapter_cls is not None else "http"
        fetcher = get_fetcher(tier)
        logger.info("Adapter %s: using fetcher tier %r (%s)", adapter_name, tier, fetcher.__class__.__name__)
        adapter = get_adapter(adapter_name, fetcher=fetcher)

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
        if total == 0:
            # Discovery returning zero is almost always a broken sitemap or a
            # silently-swallowed exception inside the adapter's discover path,
            # not a genuinely empty catalog. WARNING so it stands out in logs.
            logger.warning(
                "Adapter %s: discovered 0 URLs — likely broken sitemap or discovery path.",
                adapter_name,
            )
        else:
            logger.info("Adapter %s: %s URL(s) to process.", adapter_name, total)

        ingested = 0
        skipped_robots = 0
        skipped_not_product = 0
        skipped_gone = 0
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
                    skipped_robots += 1
                    logger.info(
                        "[%s/%s] Skipped (robots.txt disallows): %s",
                        i,
                        total,
                        url,
                    )
                    continue
                html = adapter.fetcher.fetch(url)
                payload = adapter.parse_product_page(html, url)
                if payload is None:
                    skipped_not_product += 1
                    # Per-URL log stays at INFO: a single miss is usually a
                    # non-product URL in the sitemap (category/blog/etc).
                    # The end-of-run summary escalates if the rate is high.
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
            except requests.exceptions.HTTPError as e:
                # 404 / 410 are routine on retailer sitemaps — the product has
                # been removed but the sitemap still lists the URL. Count as a
                # skip so one stale entry doesn't show up as a scary traceback
                # alongside 49 healthy pages.
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in (404, 410):
                    skipped_gone += 1
                    logger.warning("[%s/%s] Skipped (HTTP %s gone): %s", i, total, status, url)
                    db.rollback()
                else:
                    errors += 1
                    logger.exception("Error processing %s: %s", url, e)
                    db.rollback()
            except Exception as e:
                errors += 1
                logger.exception("Error processing %s: %s", url, e)
                db.rollback()

        skipped = skipped_robots + skipped_not_product + skipped_gone
        # Pick the summary log level based on how healthy the run looks. A
        # retailer that discovered pages but ingested zero is almost always a
        # broken parser (or sitewide 4xx) — surface it at ERROR so it isn't
        # buried in the INFO stream alongside healthy adapters. High but
        # non-total miss rates (>50% parse-None on at least 10 URLs) are a
        # softer signal of drift and go to WARNING.
        summary_level = logging.INFO
        summary_reason = ""
        if total > 0 and ingested == 0:
            summary_level = logging.ERROR
            summary_reason = " — 0 ingested from %s URLs, adapter likely broken" % total
        elif total >= 10 and skipped_not_product > total * 0.5:
            summary_level = logging.WARNING
            summary_reason = " — >50%% of pages failed to parse as products, adapter may be drifting"
        elif errors > 0 and errors >= max(1, total // 4):
            summary_level = logging.WARNING
            summary_reason = " — %s error(s) on %s URLs" % (errors, total)
        logger.log(
            summary_level,
            "Adapter %s done. Ingested=%s skipped=%s (robots=%s not_product=%s gone=%s) errors=%s total=%s%s",
            adapter_name,
            ingested,
            skipped,
            skipped_robots,
            skipped_not_product,
            skipped_gone,
            errors,
            total,
            summary_reason,
        )
        return {
            "adapter": adapter_name,
            "ingested": ingested,
            "skipped": skipped,
            "skipped_robots": skipped_robots,
            "skipped_not_product": skipped_not_product,
            "skipped_gone": skipped_gone,
            "errors": errors,
            "total": total,
        }
    finally:
        # Close the fetcher if we got far enough to create one. FlareSolverr
        # in particular holds a server-side browser session we want to destroy
        # cleanly so we don't pile up orphaned Chromium instances in its pool.
        if fetcher is not None:
            try:
                fetcher.close()
            except Exception as e:
                logger.warning("Fetcher cleanup failed: %s", e)
        db.close()


def _compute_adapter_workers(num_adapters: int) -> int:
    """
    Decide how many adapter threads may run in parallel.

    Scales up to ``num_adapters`` by default but never beyond what the DB pool
    can sustain while still reserving ``API_CONNECTION_RESERVE`` connections
    for live API traffic. Each running adapter holds exactly one SessionLocal
    for its full run, so the ceiling is
    ``DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE``.

    ``CRAWLER_MAX_ADAPTER_WORKERS`` (int env var) is an operator override that
    caps worker count regardless of pool size — useful for throttling against
    external constraints (RDS max_connections, FlareSolverr pool, upstream
    retailer rate limits) without bouncing the process.
    """
    worker_budget = max(1, DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE)
    max_workers = min(num_adapters, worker_budget)

    override_raw = os.environ.get("CRAWLER_MAX_ADAPTER_WORKERS")
    if override_raw:
        try:
            override = int(override_raw)
            if override > 0:
                max_workers = min(max_workers, override)
        except ValueError:
            logger.warning("Ignoring non-integer CRAWLER_MAX_ADAPTER_WORKERS=%r", override_raw)

    return max(1, max_workers)


def run_crawlers(
    adapter_names: list[str],
    *,
    limits: Optional[dict[str, int]] = None,
    global_limit: Optional[int] = None,
    delay_sec: float = DEFAULT_REQUEST_DELAY_SEC,
    delays: Optional[dict[str, float]] = None,
    parallel: bool = True,
    user_id: Optional[UUID] = None,
    default_category_id: Optional[UUID] = None,
    default_category_ids: Optional[dict[str, UUID]] = None,
    crawl_html_save_dir: Optional[str] = None,
    stop_event: Optional[threading.Event] = None,
    skip_known_urls: bool = False,
    skip_known_urls_by_adapter: Optional[dict[str, bool]] = None,
) -> dict:
    """
    Run one or more adapters. If multiple adapters, runs them in parallel threads by default.

    Args:
        adapter_names: List of adapter names (e.g. ["a90shop", "example"]).
        limits: Per-adapter limits: {"a90shop": 10, "example": 5}. Overrides global_limit when set.
        global_limit: Limit applied to all adapters when no per-adapter limit is set.
        delay_sec: Default delay between requests per crawler when no per-adapter override is set.
        delays: Per-adapter delay override: {"a90shop": 7.5}. Falls back to ``delay_sec``.
        parallel: If True and len(adapter_names) > 1, run in parallel threads.
        default_category_id: Default category used when no per-adapter override is set.
        default_category_ids: Per-adapter category override: {"a90shop": <uuid>}.
            Falls back to ``default_category_id``.
        crawl_html_save_dir: Kept for backward compatibility; HTML is always archived for every URL.
        stop_event: Optional threading.Event for cooperative cancellation across all adapters.
        skip_known_urls: Default skip flag when no per-adapter override is set.
        skip_known_urls_by_adapter: Per-adapter override: {"a90shop": True}.

    Returns:
        {
            "results": [{"adapter": str, "ingested": int, "skipped": int, "errors": int, "total": int}, ...],
            "summary": {"total_ingested": int, "total_skipped": int, "total_errors": int},
            "failed": [{"adapter": str, "error": str}, ...],
        }
    """
    limits = limits or {}
    delays = delays or {}
    default_category_ids = default_category_ids or {}
    skip_known_urls_by_adapter = skip_known_urls_by_adapter or {}
    results: list[dict] = []
    failed: list[dict] = []

    def run_one(name: str) -> dict | None:
        # Skip work entirely if cancellation was requested before this future
        # was pulled off the queue. Otherwise queued adapters still spin up a
        # DB session, build a fetcher, and run sitemap discovery (with its own
        # retries) before they get to the per-URL stop-event check — which is
        # exactly what makes a 50-adapter cancel feel like it "isn't working."
        if stop_event is not None and stop_event.is_set():
            logger.info("Adapter %s: cancelled before start.", name)
            return {"adapter": name, "ingested": 0, "skipped": 0, "errors": 0, "total": 0, "cancelled": True}
        limit = limits.get(name)
        if limit is None and global_limit is not None:
            limit = global_limit
        adapter_delay = delays.get(name, delay_sec)
        adapter_skip = skip_known_urls_by_adapter.get(name, skip_known_urls)
        adapter_category = default_category_ids.get(name, default_category_id)
        try:
            return run_crawler(
                name,
                limit=limit,
                delay_sec=adapter_delay,
                user_id=user_id,
                default_category_id=adapter_category,
                crawl_html_save_dir=crawl_html_save_dir,
                stop_event=stop_event,
                skip_known_urls=adapter_skip,
            )
        except (CrawlerConfigError, KeyError) as e:
            return {"_error": str(e), "_adapter": name}
        except Exception as e:
            logger.exception("Crawler %s failed: %s", name, e)
            return {"_error": str(e), "_adapter": name}

    if len(adapter_names) > 1 and parallel:
        max_workers = _compute_adapter_workers(len(adapter_names))
        if max_workers < len(adapter_names):
            logger.info(
                "Capping adapter parallelism at %s (requested %s). Set CRAWLER_MAX_ADAPTER_WORKERS to override.",
                max_workers,
                len(adapter_names),
            )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
