"""
Multiprocess driver for archive rescrape (local-dev fast path).

The single-process ThreadPoolExecutor version of
:func:`run_rescrape_all_archived_pages` is GIL-bound on parsing-heavy work
(BeautifulSoup + regex extraction across ~28k pages). pg_stat_activity shows
``active=1, idle_in_txn=N`` even with N parallel threads — only one Python
worker holds the GIL at a time, so adding threads past ~16 stops scaling.

This module fans the job out across N worker processes, each running one shard
of the existing sharded driver. Each child has its own GIL and its own
SQLAlchemy engine (we do NOT inherit a forked engine — see
``_child_main``); the parent only aggregates progress and final counts.

Used by the in-process (``ECS_RESCRAPE_TASK_DEFINITION_ARN`` unset) admin
endpoint. Production runs on Fargate where each ECS task is its own process,
so this code path is dev-only.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import threading
import time
from queue import Empty
from typing import Any, Callable, Optional
from uuid import UUID

logger = logging.getLogger(__name__)

# Default child-process count for the local-dev path. 4 matches a typical dev
# laptop's physical core count; each child still runs its own internal
# ThreadPoolExecutor (default 16, capped by CRAWLER_RESCRAPE_MAX_WORKERS) so
# threads-per-process * processes can briefly exceed core count without harm.
# Override with CRAWLER_RESCRAPE_PROCESSES.
_DEFAULT_RESCRAPE_PROCESSES = 4

# How often the parent merges per-shard progress into the unified progress
# callback. Matches the in-process driver's _PROGRESS_CALLBACK_INTERVAL_SEC
# headroom — fast enough to feel live, slow enough not to thrash the admin
# job-row UPDATE.
_AGGREGATE_INTERVAL_SEC = 2.0

ProgressCallback = Callable[[int, int, dict[str, int]], None]


def resolve_process_count() -> int:
    """Honor CRAWLER_RESCRAPE_PROCESSES env override; fall back to default."""
    raw = os.environ.get("CRAWLER_RESCRAPE_PROCESSES")
    if raw:
        try:
            override = int(raw)
            if override > 0:
                return override
        except ValueError:
            logger.warning("Ignoring non-integer CRAWLER_RESCRAPE_PROCESSES=%r", raw)
    return _DEFAULT_RESCRAPE_PROCESSES


def _child_main(
    shard_index: int,
    shards: int,
    crawler_user_id: UUID,
    default_category_id: UUID,
    source: Optional[str],
    progress_queue: "mp.Queue[tuple[int, int, int, dict[str, int]]]",
    stop_flag: Any,  # multiprocessing.Event
    result_queue: "mp.Queue[tuple[int, dict[str, Any]]]",
) -> None:
    """
    Run one shard inside a child process.

    Builds its own SessionLocal/engine (the parent's engine MUST NOT be
    inherited — SQLAlchemy connection pools are not fork-safe). Posts
    ``(shard_index, processed, total, counts)`` snapshots to the parent's
    progress queue, and a final ``(shard_index, result_dict)`` to the result
    queue.
    """
    # IMPORTANT: import inside the child so the engine is created fresh in the
    # child process. Top-level imports would (under fork) carry the parent's
    # pool — when the child made its first query it would corrupt the shared
    # FD or block on a connection that's "owned" by another process.
    from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
    from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id
    from app.db.session import SessionLocal

    # Each child gets a thread-local Event derived from the parent's process
    # event. The inner driver expects threading.Event; we tick it from a tiny
    # bridge thread that polls the multiprocessing flag.
    inner_stop = threading.Event()

    def _stop_bridge() -> None:
        while not inner_stop.is_set():
            if stop_flag.is_set():
                inner_stop.set()
                return
            time.sleep(0.5)

    bridge = threading.Thread(target=_stop_bridge, name=f"rescrape-stopbridge-{shard_index}", daemon=True)
    bridge.start()

    child_log = logging.getLogger(f"app.crawlers.archive_rescrape.shard{shard_index}")

    def _progress(processed: int, total: int, counts: dict[str, int]) -> None:
        # Best-effort — if the queue is full or closed, drop the update; the
        # final result_queue post is the source of truth for counts.
        try:
            progress_queue.put_nowait((shard_index, processed, total, counts))
        except Exception:
            pass

    db = SessionLocal()
    try:
        crawler_user = resolve_crawler_user(db, crawler_user_id)
        cat_id = resolve_default_category_id(db, default_category_id)
        result = run_rescrape_all_archived_pages(
            db,
            crawler_user=crawler_user,
            default_category_id=cat_id,
            log=child_log,
            stop_event=inner_stop,
            source=source,
            progress_callback=_progress,
            shards=shards,
            shard_index=shard_index,
        )
        result_queue.put((shard_index, result))
    except Exception as e:
        child_log.exception("Rescrape shard %d crashed: %s", shard_index, e)
        # Send a sentinel result so the parent doesn't hang forever waiting
        # for a result that's never coming.
        result_queue.put(
            (
                shard_index,
                {
                    "parsed_ok": 0,
                    "parse_failed": 0,
                    "ingest_failed": 0,
                    "skipped_no_adapter": 0,
                    "skipped_no_html": 0,
                    "failures": [
                        {
                            "url": f"<shard {shard_index}>",
                            "source": "internal",
                            "outcome": "ingest_failed",
                            "error": f"shard crashed: {e}",
                        }
                    ],
                    "failures_total": 1,
                    "failures_truncated": False,
                    "processed": 0,
                    "total": 0,
                },
            )
        )
    finally:
        inner_stop.set()
        db.close()


def run_rescrape_all_archived_pages_mp(
    *,
    crawler_user_id: UUID,
    default_category_id: UUID,
    log: logging.Logger,
    stop_event: Optional[threading.Event] = None,
    source: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
    num_processes: Optional[int] = None,
) -> dict[str, Any]:
    """
    Multiprocess fan-out for archive rescrape. Returns the same result-dict
    shape as :func:`run_rescrape_all_archived_pages` (single-process).

    Each child process picks up a deterministic disjoint slice of the
    candidate page set (``int(page.id) % shards == shard_index``) so we never
    double-process a row. Children commit independently; the parent only
    accumulates progress + final counts.

    ``stop_event`` (a ``threading.Event`` from the parent) is mirrored into a
    ``multiprocessing.Event`` so children can observe cancellation.
    """
    n = num_processes if num_processes is not None else resolve_process_count()
    n = max(1, n)

    log.info("Archive rescrape (multiprocess): spawning %d shard process(es).", n)

    # Use 'spawn' to avoid inheriting any engine state, threading locks, or
    # FastAPI/uvloop globals from the parent. Forking a process that already
    # initialized SQLAlchemy is a known footgun (parent's connection pool
    # ends up shared and corrupts).
    ctx = mp.get_context("spawn")
    progress_queue: "mp.Queue[tuple[int, int, int, dict[str, int]]]" = ctx.Queue(maxsize=4096)
    result_queue: "mp.Queue[tuple[int, dict[str, Any]]]" = ctx.Queue()
    stop_flag = ctx.Event()

    # Bridge the parent's threading.Event onto the multiprocessing.Event so
    # the existing cancellation contract still holds. Same trick the children
    # use in reverse.
    parent_stop_thread: Optional[threading.Thread] = None
    if stop_event is not None:
        parent_stop_done = threading.Event()

        def _parent_stop_bridge() -> None:
            while not parent_stop_done.is_set():
                if stop_event.is_set():
                    stop_flag.set()
                    return
                time.sleep(0.5)

        parent_stop_thread = threading.Thread(
            target=_parent_stop_bridge, name="rescrape-mp-parent-stop", daemon=True
        )
        parent_stop_thread.start()
    else:
        parent_stop_done = None

    children: list[Any] = []  # SpawnProcess; declared as Any to avoid Process/SpawnProcess type mismatch
    for shard_index in range(n):
        p = ctx.Process(
            target=_child_main,
            name=f"rescrape-shard-{shard_index}",
            args=(
                shard_index,
                n,
                crawler_user_id,
                default_category_id,
                source,
                progress_queue,
                stop_flag,
                result_queue,
            ),
            daemon=False,
        )
        p.start()
        children.append(p)

    # Per-shard progress state, used to compute aggregate progress for the
    # parent's progress_callback without relying on every shard reporting on
    # the same tick.
    shard_processed: dict[int, int] = {i: 0 for i in range(n)}
    shard_total: dict[int, int] = {i: 0 for i in range(n)}
    shard_counts: dict[int, dict[str, int]] = {
        i: {
            "parsed_ok": 0,
            "parse_failed": 0,
            "ingest_failed": 0,
            "skipped_no_adapter": 0,
            "skipped_no_html": 0,
        }
        for i in range(n)
    }
    last_aggregate_at = time.monotonic()

    def _emit_aggregate() -> None:
        if progress_callback is None:
            return
        agg_processed = sum(shard_processed.values())
        agg_total = sum(shard_total.values())
        agg_counts: dict[str, int] = {
            "parsed_ok": 0,
            "parse_failed": 0,
            "ingest_failed": 0,
            "skipped_no_adapter": 0,
            "skipped_no_html": 0,
        }
        for c in shard_counts.values():
            for k, v in c.items():
                agg_counts[k] = agg_counts.get(k, 0) + v
        try:
            progress_callback(agg_processed, agg_total, agg_counts)
        except Exception:
            log.exception("Archive rescrape (mp): progress_callback raised; continuing")

    # Drain the progress queue while children run. Stop when all results are
    # collected. We treat the result queue as the authoritative completion
    # signal — once we've heard from every shard we're done, even if the
    # progress queue has stragglers.
    results: dict[int, dict[str, Any]] = {}
    while len(results) < n:
        try:
            shard_index, processed, shard_tot, counts = progress_queue.get(timeout=0.5)
            shard_processed[shard_index] = processed
            shard_total[shard_index] = shard_tot
            shard_counts[shard_index] = counts
        except Empty:
            pass

        # Drain any completed results without blocking.
        while True:
            try:
                shard_index, result = result_queue.get_nowait()
                results[shard_index] = result
                # Pin shard's final processed/total/counts to the authoritative
                # values from the result so aggregate end-state is exact even
                # if the last progress message was lost.
                shard_processed[shard_index] = result.get("processed", shard_processed[shard_index])
                shard_total[shard_index] = result.get("total", shard_total[shard_index])
                shard_counts[shard_index] = {
                    k: result.get(k, 0)
                    for k in (
                        "parsed_ok",
                        "parse_failed",
                        "ingest_failed",
                        "skipped_no_adapter",
                        "skipped_no_html",
                    )
                }
            except Empty:
                break

        now = time.monotonic()
        if (now - last_aggregate_at) >= _AGGREGATE_INTERVAL_SEC:
            last_aggregate_at = now
            _emit_aggregate()

    for p in children:
        p.join(timeout=30)
        if p.is_alive():
            log.warning("Rescrape shard %s did not exit cleanly; terminating.", p.name)
            p.terminate()
            p.join(timeout=5)

    if parent_stop_thread is not None and parent_stop_done is not None:
        parent_stop_done.set()

    # Final aggregate emission so the admin UI shows 100%.
    _emit_aggregate()

    # Merge results.
    merged: dict[str, Any] = {
        "parsed_ok": 0,
        "parse_failed": 0,
        "ingest_failed": 0,
        "skipped_no_adapter": 0,
        "skipped_no_html": 0,
    }
    merged_failures: list[dict[str, Any]] = []
    merged_failures_total = 0
    merged_processed = 0
    merged_total = 0
    for shard_index in range(n):
        r = results.get(shard_index)
        if r is None:
            log.warning("Archive rescrape (mp): shard %d returned no result.", shard_index)
            continue
        for k in ("parsed_ok", "parse_failed", "ingest_failed", "skipped_no_adapter", "skipped_no_html"):
            merged[k] += r.get(k, 0)
        merged_failures.extend(r.get("failures", []))
        merged_failures_total += r.get("failures_total", 0)
        merged_processed += r.get("processed", 0)
        merged_total += r.get("total", 0)

    # Apply the same per-job failure cap the single-process driver honors so
    # result_summary doesn't bloat the BackgroundJob row when multiple shards
    # each had near-cap failure lists.
    from app.crawlers.archive_rescrape import MAX_REPORTED_FAILURES

    if len(merged_failures) > MAX_REPORTED_FAILURES:
        merged_failures = merged_failures[:MAX_REPORTED_FAILURES]

    merged["failures"] = merged_failures
    merged["failures_total"] = merged_failures_total
    merged["failures_truncated"] = merged_failures_total > len(merged_failures)
    merged["processed"] = merged_processed
    merged["total"] = merged_total
    return merged
