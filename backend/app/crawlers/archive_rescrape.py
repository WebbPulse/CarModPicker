"""
Re-parse archived HTML: full ingest (part create/update, inference, listing, price history).

Used by admin batch "rescrape archives" and by POST /crawled-pages/{id}/re-parse.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Optional
from uuid import UUID

from sqlalchemy import or_, select
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

# Cap on the per-URL failure list returned to callers. A job over a 50k-page
# archive that fails on half its rows would produce a multi-megabyte JSON blob
# and bloat both the DB row and the job-report email. 200 is enough for an
# operator to eyeball the failure shape.
MAX_REPORTED_FAILURES = 200
# Backwards-compat alias for older imports.
_MAX_REPORTED_FAILURES = MAX_REPORTED_FAILURES

# How often the driver fires progress_callback while work is in flight. Too
# fast and the admin job-row UPDATE storm shows up on RDS; too slow and the
# progress bar stalls. 2 s matches the crawler UI poll cadence headroom.
_PROGRESS_CALLBACK_INTERVAL_SEC = 2.0

# (processed, total, counts_snapshot) — invoked from the driver thread under a
# lock, so callbacks don't need their own synchronisation.
ProgressCallback = Callable[[int, int, dict[str, int]], None]

# Default cap on rescrape threads when no operator override is set.
#
# The DB pool budget can be huge in dev (DB_POOL_SIZE+OVERFLOW-RESERVE = 144
# with the local-dev settings), but the rescrape worker is GIL-bound: each
# page's parse_product_page / variant ingest
# spends most of its wall time in pure-Python BeautifulSoup + regex work.
# Throwing 144 threads at a single GIL just adds context-switch overhead and
# parks ~120 connections idle-in-transaction (observed in pg_stat_activity:
# active=1, idle_in_txn=~120, sustained for minutes). 16 is the empirical
# sweet spot — enough to overlap S3 GETs with parsing on a different worker,
# few enough that the GIL ping-pong tax is small. Operators can still raise
# it via CRAWLER_RESCRAPE_MAX_WORKERS for I/O-heavy or process-sharded runs.
_DEFAULT_RESCRAPE_WORKERS = 16


def _compute_rescrape_workers(num_pages: int) -> int:
    """
    Decide how many per-URL rescrape threads may run in parallel.

    Each worker checks out one ``SessionLocal`` for the duration of a single
    page, so concurrency is bounded by the DB pool budget left over after
    reserving live traffic: ``DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE``.

    Within that hard ceiling we apply :data:`_DEFAULT_RESCRAPE_WORKERS` as an
    implicit soft cap because the per-page workload is GIL-bound — see the
    constant's docstring.

    ``CRAWLER_RESCRAPE_MAX_WORKERS`` (int env var) is an operator cap for
    throttling against RDS ``max_connections`` or S3 GET concurrency without
    bouncing the process. It can also be used to *raise* the soft cap above
    :data:`_DEFAULT_RESCRAPE_WORKERS` (still bounded by the DB pool).
    """
    worker_budget = max(1, DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE)

    override_raw = os.environ.get("CRAWLER_RESCRAPE_MAX_WORKERS")
    if override_raw:
        try:
            override = int(override_raw)
            if override > 0:
                # Operator override replaces the GIL-aware default and is
                # still clamped to the DB-pool budget below.
                soft_cap = override
            else:
                soft_cap = _DEFAULT_RESCRAPE_WORKERS
        except ValueError:
            # IN-08: mirror runner.py's _compute_adapter_workers behavior —
            # surface a bad env value in the logs instead of silently falling
            # back to the DB-pool-sized default. CRAWLER_RESCRAPE_MAX_WORKERS=8x
            # used to disappear without a trace; now operators see the typo.
            logging.getLogger(__name__).warning("Ignoring non-integer CRAWLER_RESCRAPE_MAX_WORKERS=%r", override_raw)
            soft_cap = _DEFAULT_RESCRAPE_WORKERS
    else:
        soft_cap = _DEFAULT_RESCRAPE_WORKERS

    max_workers = min(num_pages, worker_budget, soft_cap)
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
    return adapter_name_for_product_url(page.url)


def rescrape_crawled_page_from_archive(
    db: Session,
    page: DBCrawledPage,
    *,
    crawler_user: DBUser,
    default_category_id: UUID,
    log: logging.Logger,
    prefetched_html: Optional[str] = None,
) -> tuple[RescrapeOutcome, Optional[UUID], Optional[str]]:
    """
    Fetch archived HTML, parse with the right adapter, ingest (including price history).

    Returns (outcome, part_id if parsed_ok else None, error detail for ingest failures).
    Commits on each terminal path (same as legacy re-parse + ingest_payload commits).

    ``prefetched_html`` lets bulk callers load HTML before checking out a DB
    session, so the (potentially multi-second) S3 GET doesn't sit
    idle-in-transaction holding a connection slot. When omitted, behavior is
    identical to the legacy single-page path.
    """
    adapter_key = resolve_parse_adapter_name(page)
    html = prefetched_html if prefetched_html is not None else load_archived_html(page, log)
    if not html:
        return "skipped_no_html", None, "No archived HTML available (S3 key missing or unreadable)"

    html_utf8, _, html_sha = crawl_html_fingerprint(html)

    adapter = get_adapter(adapter_key)
    payload = adapter.parse_product_page(html, page.url)
    now = datetime.now(timezone.utc)

    if payload is None:
        page.parse_status = "failed"
        page.last_parsed_at = now
        db.commit()
        return "parse_failed", None, f"Parser '{adapter_key}' returned no payload"

    # Pin url/id to locals before ingest_payload — if it raises mid-flush the
    # session is rolled back and any lazy load on ``page`` would then raise
    # PendingRollbackError, crashing the worker before parse_status is marked.
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
            adapter_name=adapter_key,
            adapter=adapter,
        )
    except Exception as e:
        db.rollback()
        log.warning("Archive rescrape: ingest failed for %s (adapter=%s): %s", page_url, adapter_key, e)
        row = db.get(DBCrawledPage, page_id)
        if row is not None:
            row.parse_status = "failed"
            row.last_parsed_at = now
            db.commit()
        return "ingest_failed", None, str(e)

    db.refresh(page)

    # Only re-save HTML when the page was loaded from local disk (migrate to
    # S3) or has no key at all. Skip the put_object round-trip when the HTML
    # was just fetched from html_s3_key — it's already there and writing the
    # same bytes back wastes S3 PUT quota.
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

    # Variant ingest (mirrors runner.py): adapters that bundle multiple priced
    # SKUs under one URL (Wix / Shopify multi-variant pages) emit extras via
    # ``extract_variants``. Each lands as its own Part. Per-variant failures
    # don't roll back the base part — that already committed above.
    try:
        variant_payloads = adapter.extract_variants(html, page.url, payload)
    except Exception as ev:
        log.warning("Archive rescrape: extract_variants raised on %s: %s", page.url, ev)
        variant_payloads = []
    for variant_payload in variant_payloads:
        try:
            ingest_payload(
                db,
                variant_payload,
                current_user=crawler_user,
                default_category_id=default_category_id,
                logger=log,
                source="archive_rescrape",
                adapter_name=adapter_key,
                adapter=adapter,
            )
        except Exception as ev:
            db.rollback()
            log.warning(
                "Archive rescrape: variant ingest failed for %s (variant_url=%s): %s",
                page.url,
                getattr(variant_payload, "product_url", "?"),
                ev,
            )

    return "parsed_ok", part.id, None


def run_rescrape_all_archived_pages(
    db: Session,
    *,
    crawler_user: DBUser,
    default_category_id: UUID,
    log: logging.Logger,
    stop_event: Optional[threading.Event] = None,
    source: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
    shards: int = 1,
    shard_index: int = 0,
) -> dict[str, Any]:
    """
    Re-parse every crawled page that has archived HTML, in parallel.

    Dispatch is URL-level: each worker opens its own ``SessionLocal`` and runs
    one page through :func:`rescrape_crawled_page_from_archive`. Worker count
    scales with DB-pool capacity (see :func:`_compute_rescrape_workers`) and
    can be capped via ``CRAWLER_RESCRAPE_MAX_WORKERS``.

    If ``stop_event`` is set, pending workers short-circuit on entry and
    in-flight pages are allowed to finish. Cancelled workers don't appear in
    ``counts`` — they simply aren't counted.

    Pass ``source`` (e.g. ``"adro"``) to re-parse only one adapter's archive.

    ``progress_callback`` is invoked with ``(processed, total, counts_snapshot)``
    roughly every :data:`_PROGRESS_CALLBACK_INTERVAL_SEC` seconds and once more
    at completion. Calls are serialised under the driver's progress lock, so
    callbacks don't need their own synchronisation. Exceptions from the
    callback are logged and swallowed so a flaky writer can't abort the job.

    ``shards``/``shard_index`` (local-dev sharding): split the candidate page
    set across ``shards`` independent processes by ``int(page.id) % shards ==
    shard_index``. Each process runs its own ThreadPoolExecutor against its
    slice, escaping the GIL on parsing-heavy work. Disjoint partitioning
    means no two processes touch the same row. Default ``shards=1`` is the
    pre-sharding behavior.

    Returns a dict merging aggregate counts with ``failures`` (bounded list),
    ``failures_total``, ``failures_truncated``, and ``processed``/``total`` so
    the admin UI can render a live progress bar from
    ``BackgroundJob.result_summary`` alone.
    """
    if shards < 1:
        raise ValueError(f"shards must be >= 1, got {shards}")
    if not (0 <= shard_index < shards):
        raise ValueError(f"shard_index must be in [0, {shards}), got {shard_index}")
    counts: dict[str, int] = {
        "parsed_ok": 0,
        "parse_failed": 0,
        "ingest_failed": 0,
        "skipped_no_adapter": 0,
        "skipped_no_html": 0,
    }
    failures: list[dict[str, Any]] = []
    total_failures = 0

    stmt = (
        select(
            DBCrawledPage.id,
            DBCrawledPage.url,
            DBCrawledPage.source,
            DBCrawledPage.html_s3_key,
            DBCrawledPage.html_local_path,
        )
        .where(
            or_(
                DBCrawledPage.html_s3_key.isnot(None),
                DBCrawledPage.html_local_path.isnot(None),
            )
        )
        .order_by(DBCrawledPage.id)
    )
    if source is not None:
        stmt = stmt.where(DBCrawledPage.source == source)
    # Materialize into plain tuples then drop the driver session's transaction.
    # The original code held this SELECT's transaction open for the entire job
    # (~9 min observed in pg_stat_activity), pinning a connection slot
    # idle-in-transaction for no reason — we don't touch ``db`` again until
    # the function returns.
    rows = [
        (r.id, r.url, r.source, r.html_s3_key, r.html_local_path) for r in db.execute(stmt).all()
    ]
    db.commit()
    if shards > 1:
        # int(uuid) is the same on every process for a given row, so this
        # gives a deterministic disjoint partition. Doing the filter in Python
        # avoids a Postgres-vs-SQLite UUID-modulo dialect dance.
        rows = [r for r in rows if int(r[0]) % shards == shard_index]
        log.info(
            "Archive rescrape: shard %d/%d selected — %d page(s) in this slice.",
            shard_index,
            shards,
            len(rows),
        )
    total = len(rows)

    def _build_result(processed_: int) -> dict[str, Any]:
        result: dict[str, Any] = dict(counts)
        result["failures"] = failures
        result["failures_total"] = total_failures
        result["failures_truncated"] = total_failures > len(failures)
        result["processed"] = processed_
        result["total"] = total
        return result

    def _fire_progress(processed_: int) -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(processed_, total, dict(counts))
        except Exception:
            log.exception("Archive rescrape: progress_callback raised; continuing")

    if total == 0:
        log.info("Archive rescrape: no archived pages match the filter; nothing to do.")
        _fire_progress(0)
        return _build_result(0)

    max_workers = _compute_rescrape_workers(total)
    log.info(
        "Archive rescrape: %d page(s) to process with %d parallel worker(s).",
        total,
        max_workers,
    )
    _fire_progress(0)

    def _load_html_no_session(
        page_id: UUID, html_s3_key: Optional[str], html_local_path: Optional[str]
    ) -> Optional[str]:
        # Mirrors load_archived_html() but works off the row tuple rather than
        # an ORM-attached page, so we can fetch HTML before checking out a
        # SessionLocal. Keeps the ~hundred-millisecond S3 GET out of the DB
        # connection's open-transaction window.
        html: Optional[str] = None
        if html_s3_key:
            s3_client, bucket_name = get_crawl_s3_client()
            if s3_client is not None and bucket_name is not None:
                try:
                    obj = s3_client.get_object(Bucket=bucket_name, Key=html_s3_key)
                    html = obj["Body"].read().decode("utf-8", errors="replace")
                except Exception as e:
                    log.warning("Could not fetch HTML from S3 key %s (page=%s): %s", html_s3_key, page_id, e)
        if html is None and html_local_path:
            try:
                html = Path(html_local_path).read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                log.warning("Could not read local HTML %s (page=%s): %s", html_local_path, page_id, e)
        return html

    def _worker(
        idx: int,
        page_id: UUID,
        page_url: str,
        page_source: str,
        html_s3_key: Optional[str],
        html_local_path: Optional[str],
    ) -> Optional[tuple[str, str, str, Optional[str]]]:
        # Pending workers that haven't started when cancellation is requested
        # short-circuit on entry — the parallel analog of the old per-iteration
        # stop_event check.
        if stop_event is not None and stop_event.is_set():
            return None
        # Per-URL line is debug-only — at 7k+ URLs/run it dominates
        # CloudWatch and ops only need the every-2s aggregate progress
        # line below. ``idx`` is the URL's dispatch position (sort order
        # by id), NOT the completed-count, so phrase it as a sequence
        # number to avoid being mistaken for a [done/total] fraction.
        log.debug(
            "Archive rescrape: processing #%d of %d — %s (source=%s)",
            idx,
            total,
            page_url,
            page_source,
        )
        # Fetch HTML BEFORE opening a DB session. The original ordering opened
        # the session first, then issued an S3 GetObject while the connection
        # sat idle-in-transaction; under the GIL with ~120 workers in flight,
        # only one could execute SQL at a time and the rest were just hoarding
        # connections. Loading HTML first frees that slot for other workers.
        prefetched_html = _load_html_no_session(page_id, html_s3_key, html_local_path)
        if prefetched_html is None:
            return (
                "skipped_no_html",
                page_url,
                page_source,
                "No archived HTML available (S3 key missing or unreadable)",
            )

        worker_db = SessionLocal()
        try:
            page_row = worker_db.get(DBCrawledPage, page_id)
            if page_row is None:
                return ("skipped_no_html", page_url, page_source, "CrawledPage deleted between query and rescrape")
            # Reuse the pre-fetched user via merge() instead of re-SELECTing
            # the users row on every page (28k+ wasted lookups per job — the
            # dominant query in pg_stat_activity samples). merge() with
            # load=False attaches the existing object to this session without
            # a SELECT, which is safe because the crawler user identity does
            # not change for the duration of the job.
            worker_user = worker_db.merge(crawler_user, load=False)
            outcome, _, err_detail = rescrape_crawled_page_from_archive(
                worker_db,
                page_row,
                crawler_user=worker_user,
                default_category_id=default_category_id,
                log=log,
                prefetched_html=prefetched_html,
            )
            return (outcome, page_url, page_source, err_detail)
        except Exception as e:
            # rescrape_crawled_page_from_archive commits on every terminal path,
            # but a bug that escapes it (or a cross-thread SQLAlchemy issue)
            # would otherwise orphan the session mid-transaction.
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

    processed = 0
    last_callback_at = time.monotonic()
    progress_lock = threading.Lock()
    cancelled_logged = False

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rescrape") as executor:
        futures = [
            executor.submit(_worker, i + 1, page_id, page_url, page_source, html_s3_key, html_local_path)
            for i, (page_id, page_url, page_source, html_s3_key, html_local_path) in enumerate(rows)
        ]
        try:
            for future in as_completed(futures):
                if stop_event is not None and stop_event.is_set() and not cancelled_logged:
                    log.info("Archive rescrape: stop requested; draining in-flight workers.")
                    cancelled_logged = True
                try:
                    outcome_tuple = future.result()
                except CancelledError:
                    continue
                if outcome_tuple is None:
                    continue
                _record(*outcome_tuple)
                with progress_lock:
                    processed += 1
                    now = time.monotonic()
                    due_by_time = (now - last_callback_at) >= _PROGRESS_CALLBACK_INTERVAL_SEC
                    due_by_end = processed == total
                    if due_by_time or due_by_end:
                        last_callback_at = now
                        pct = int(round((processed / total) * 100)) if total else 0
                        log.info(
                            "Archive rescrape progress: [%d/%d] %d%% (ok=%d, parse_fail=%d, ingest_fail=%d, no_html=%d)",
                            processed,
                            total,
                            pct,
                            counts["parsed_ok"],
                            counts["parse_failed"],
                            counts["ingest_failed"],
                            counts["skipped_no_html"],
                        )
                        _fire_progress(processed)
        except BaseException:
            # Propagate KeyboardInterrupt/SystemExit but first unblock workers.
            if stop_event is not None:
                stop_event.set()
            raise

    return _build_result(processed)
