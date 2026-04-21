"""
Re-parse archived HTML: full ingest (part create/update, inference, listing, price history).

Used by admin batch "rescrape archives" and by POST /crawled-pages/{id}/re-parse.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional  # Optional still used for load_archived_html return
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.crawlers.adapters import ADAPTER_REGISTRY, adapter_name_for_product_url, get_adapter
from app.crawlers.base import (
    crawl_html_fingerprint,
    get_crawl_s3_client,
    ingest_payload,
    save_crawl_page_html,
)
from app.db.session import API_CONNECTION_RESERVE, DB_MAX_OVERFLOW, DB_POOL_SIZE, SessionLocal

RescrapeOutcome = Literal[
    "parsed_ok",
    "parse_failed",
    "ingest_failed",
    "skipped_no_adapter",
    "skipped_no_html",
]

# Cap on the per-URL failure list returned in the result_summary. Without a
# cap, a job that parses 50k pages and fails on half of them would produce a
# multi-megabyte JSON blob and bloat the DB + email. 200 is enough for an
# operator to see the shape of the failure while keeping the payload small.
_MAX_REPORTED_FAILURES = 200


def _compute_rescrape_workers(num_pages: int) -> int:
    """
    Decide how many per-URL rescrape threads may run in parallel.

    Scales with DB-pool capacity the same way as the crawler runner: each worker
    checks out one ``SessionLocal`` for the duration of a single page rescrape,
    so total concurrency must fit
    ``DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE``.

    ``CRAWLER_RESCRAPE_MAX_WORKERS`` (int env var) is an operator cap for
    throttling against RDS ``max_connections`` or S3 GET concurrency without
    bouncing the process.
    """
    worker_budget = max(1, DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE)
    max_workers = min(num_pages, worker_budget)

    override_raw = os.environ.get("CRAWLER_RESCRAPE_MAX_WORKERS")
    if override_raw:
        try:
            override = int(override_raw)
            if override > 0:
                max_workers = min(max_workers, override)
        except ValueError:
            # Silent fallback — mirror the runner.py behavior so a typo doesn't block the job.
            pass

    return max(1, max_workers)


def load_archived_html(page: DBCrawledPage, log: logging.Logger) -> Optional[str]:
    """Load raw HTML for a crawled page from S3 or local path."""
    html: Optional[str] = None
    if page.html_s3_key:
        s3_client, bucket_name = get_crawl_s3_client()
        if s3_client is not None and bucket_name is not None:
            try:
                obj = s3_client.get_object(Bucket=bucket_name, Key=page.html_s3_key)
                html = obj["Body"].read().decode("utf-8", errors="replace")
            except Exception as e:
                log.warning("Could not fetch HTML from S3 key %s: %s", page.html_s3_key, e)
    if html is None and page.html_local_path:
        try:
            html = Path(page.html_local_path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            log.warning("Could not read local HTML %s: %s", page.html_local_path, e)
    return html


def resolve_parse_adapter_name(page: DBCrawledPage) -> str:
    """
    Adapter key to parse this page's HTML.

    Returns a site-specific adapter when one is registered for the source or URL,
    otherwise falls back to ``"generic"`` so every archived page can be re-parsed.
    """
    if page.source in ADAPTER_REGISTRY:
        return page.source
    # For chrome_extension and any other source, pick by URL (always returns a key)
    return adapter_name_for_product_url(page.url)


def rescrape_crawled_page_from_archive(
    db: Session,
    page: DBCrawledPage,
    *,
    crawler_user: DBUser,
    default_category_id: UUID,
    log: logging.Logger,
) -> tuple[RescrapeOutcome, Optional[UUID], Optional[str]]:
    """
    Fetch archived HTML, parse with the right adapter, ingest (including price history).

    Returns (outcome, part_id if parsed_ok else None, error detail for ingest failures).
    Commits on each terminal path (same as legacy re-parse + ingest_payload commits).
    """
    adapter_key = resolve_parse_adapter_name(page)
    html = load_archived_html(page, log)
    if not html:
        # Every archived page is expected to have HTML in S3 or on disk;
        # missing HTML means the archival step failed or the object was
        # deleted. Operators want to know which pages are orphaned.
        log.warning(
            "Archive rescrape: no HTML for %s (source=%s, page_id=%s)",
            page.url,
            page.source,
            page.id,
        )
        return "skipped_no_html", None, "No archived HTML available (S3 key missing or unreadable)"

    html_utf8, _, html_sha = crawl_html_fingerprint(html)

    adapter = get_adapter(adapter_key)
    payload = adapter.parse_product_page(html, page.url)
    now = datetime.now(timezone.utc)

    if payload is None:
        # Every row we rescrape was parseable the first time, so a None
        # payload here points at parser drift or corrupt HTML — worth a
        # warning so the failure shows up in default log configs.
        log.warning(
            "Archive rescrape: parse failed for %s (adapter=%s)",
            page.url,
            adapter_key,
        )
        page.parse_status = "failed"
        page.last_parsed_at = now
        db.commit()
        return "parse_failed", None, f"Parser '{adapter_key}' returned no payload"

    # Capture identifiers before the try/except — if ingest_payload raises mid-flush,
    # the session is in a rolled-back state and any lazy load on `page` (e.g. page.url
    # for logging) would raise PendingRollbackError and escape this handler, crashing
    # the worker before parse_status gets marked.
    page_url = page.url
    page_id = page.id
    try:
        part = ingest_payload(
            db,
            payload,
            current_user=crawler_user,
            default_category_id=default_category_id,
            logger=log,
            source="archive_rescrape",
        )
    except Exception as e:
        db.rollback()
        log.warning(
            "Archive rescrape: ingest failed for %s (adapter=%s): %s",
            page_url,
            adapter_key,
            e,
        )
        row = db.get(DBCrawledPage, page_id)
        if row is not None:
            row.parse_status = "failed"
            row.last_parsed_at = now
            db.commit()
        return "ingest_failed", None, str(e)

    db.refresh(page)

    # Only re-save HTML when the page was loaded from local disk (migrate to S3) or has no key at
    # all. Skip the put_object round-trip when the HTML was just fetched from html_s3_key — it is
    # already there and writing the same bytes back wastes S3 PUT quota.
    if not page.html_s3_key:
        storage_key = save_crawl_page_html(
            adapter_key,
            page.url,
            html,
            "",
            html_utf8=html_utf8,
            logger_instance=log,
        )
        if storage_key:
            if storage_key.startswith("/"):
                page.html_local_path = storage_key
                page.html_s3_key = None
            else:
                page.html_s3_key = storage_key
                page.html_local_path = None

    page.html_sha256 = html_sha
    page.part_id = part.id
    page.parse_status = "parsed"
    page.last_parsed_at = now
    db.commit()
    return "parsed_ok", part.id, None


def run_rescrape_all_archived_pages(
    db: Session,
    *,
    crawler_user: DBUser,
    default_category_id: UUID,
    log: logging.Logger,
    stop_event: Optional[threading.Event] = None,
    source: Optional[str] = None,
) -> dict[str, Any]:
    """
    Re-parse every crawled page that has archived HTML (S3 or local), in parallel.

    ``ingest_payload`` records listing and price history when the parsed payload includes a price.
    Dispatch is URL-level: each worker opens its own ``SessionLocal`` and runs one page through
    :func:`rescrape_crawled_page_from_archive`. Worker count scales with DB-pool capacity and
    can be capped via ``CRAWLER_RESCRAPE_MAX_WORKERS`` — see :func:`_compute_rescrape_workers`.

    If stop_event is provided and set, pending workers short-circuit on entry (returning a
    cancellation sentinel) and in-flight pages are allowed to finish. Cancelled pages do not
    appear in the counts — they simply aren't counted, matching the pre-parallel behavior
    where cancelled iterations were never counted either.

    Pass ``source`` (e.g. ``"adro"``) to re-parse only one adapter's archive — useful after
    adapter-specific parsing fixes so other retailers' data isn't touched.

    Returns a dict combining aggregate counts (``parsed_ok``, ``parse_failed``, …) with a
    bounded ``failures`` list describing up to ``_MAX_REPORTED_FAILURES`` individual
    failures so the admin UI and job-report email can show *which* URLs failed, not just
    how many. ``failures_truncated`` reports whether the cap was hit.
    """
    counts: dict[str, int] = {
        "parsed_ok": 0,
        "parse_failed": 0,
        "ingest_failed": 0,
        "skipped_no_adapter": 0,
        "skipped_no_html": 0,
    }
    failures: list[dict[str, Any]] = []
    total_failures = 0

    q = (
        db.query(DBCrawledPage.id, DBCrawledPage.url, DBCrawledPage.source)
        .filter(
            or_(
                DBCrawledPage.html_s3_key.isnot(None),
                DBCrawledPage.html_local_path.isnot(None),
            )
        )
        .order_by(DBCrawledPage.id)
    )
    if source is not None:
        q = q.filter(DBCrawledPage.source == source)
    rows = q.all()

    if not rows:
        result: dict[str, Any] = dict(counts)
        result["failures"] = failures
        result["failures_total"] = total_failures
        result["failures_truncated"] = False
        return result

    max_workers = _compute_rescrape_workers(len(rows))
    log.info(
        "Archive rescrape: %s page(s) to process with %s parallel worker(s).",
        len(rows),
        max_workers,
    )

    # Grab the primitive ids before crossing threads — each worker loads its own
    # ORM instances against its private Session.
    crawler_user_id: UUID = crawler_user.id

    def _worker(page_id: UUID, page_url: str, page_source: str) -> Optional[tuple[str, str, str, Optional[str]]]:
        # Pending futures that haven't been picked up yet can short-circuit on
        # entry when cancellation is requested — this is the parallel analog of
        # the original loop's per-iteration stop_event check.
        if stop_event is not None and stop_event.is_set():
            return None
        worker_db = SessionLocal()
        try:
            page_row = worker_db.get(DBCrawledPage, page_id)
            if page_row is None:
                return ("skipped_no_html", page_url, page_source, "CrawledPage deleted between query and rescrape")
            worker_user = worker_db.get(DBUser, crawler_user_id)
            if worker_user is None:
                return ("ingest_failed", page_url, page_source, "Crawler user not found in worker session")
            outcome, _, err_detail = rescrape_crawled_page_from_archive(
                worker_db,
                page_row,
                crawler_user=worker_user,
                default_category_id=default_category_id,
                log=log,
            )
            return (outcome, page_url, page_source, err_detail)
        except Exception as e:
            # rescrape_crawled_page_from_archive commits on every terminal path,
            # but a bug that escapes it (or a cross-thread SQLAlchemy issue) would
            # otherwise orphan the session mid-transaction.
            log.exception("Archive rescrape worker crashed on %s: %s", page_url, e)
            try:
                worker_db.rollback()
            except Exception:
                pass
            return ("ingest_failed", page_url, page_source, f"worker exception: {e}")
        finally:
            worker_db.close()

    def _record(outcome: str, page_url: str, page_source: str, err_detail: Optional[str]) -> None:
        nonlocal total_failures
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome == "parsed_ok":
            return
        total_failures += 1
        if len(failures) < _MAX_REPORTED_FAILURES:
            failures.append(
                {
                    "url": page_url,
                    "source": page_source,
                    "outcome": outcome,
                    "error": err_detail,
                }
            )

    cancelled_logged = False
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rescrape") as executor:
        futures = [executor.submit(_worker, r.id, r.url, r.source) for r in rows]
        try:
            for future in as_completed(futures):
                if stop_event is not None and stop_event.is_set() and not cancelled_logged:
                    log.info("Archive rescrape: stop requested, draining in-flight workers and cancelling the rest.")
                    cancelled_logged = True
                    # Cancel any futures the pool hasn't started yet. Running
                    # futures ignore .cancel() (they'll short-circuit via the
                    # stop_event check inside the worker instead).
                    for pending in futures:
                        pending.cancel()
                try:
                    outcome_tuple = future.result()
                except CancelledError:
                    continue
                if outcome_tuple is None:
                    continue  # worker short-circuited on stop_event
                _record(*outcome_tuple)
        except BaseException:
            if stop_event is not None:
                stop_event.set()
            raise

    result = dict(counts)
    result["failures"] = failures
    result["failures_total"] = total_failures
    result["failures_truncated"] = total_failures > len(failures)
    return result
