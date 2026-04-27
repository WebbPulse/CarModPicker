"""
Re-extraction backfill CLI: repopulate ``Part.specifications`` for parts that
were ingested before the S02 universal-extractor wiring landed.

Run from ``backend/``:

    python -m app.crawlers.backfill --batch-size 100
    python -m app.crawlers.backfill --batch-size 200 --source a90shop --resume
    python -m app.crawlers.backfill --dry-run

Requires the same env vars as the rest of the crawler subsystem
(``CRAWLER_USER_ID``, ``CRAWLER_DEFAULT_CATEGORY_NAME``/``_ID``). The CLI
re-uses :func:`app.crawlers.archive_rescrape.rescrape_crawled_page_from_archive`
for the per-page parse + ingest path so universal extraction (per MEM026) and
ingest-time spec validation (per MEM009) flow through unchanged.

Design notes
------------

* **Idempotent.** The SELECT only returns parts whose ``specifications`` is
  ``NULL`` or the empty-dict literal, so a successful run shrinks the working
  set; a re-run on the same input yields zero rows.
* **Resumable.** After every successful batch the CLI writes a tiny JSON
  cursor at ``<state-dir>/backfill_cursor.json`` with the highest part_id
  processed so far. ``--resume`` opts in to reading that cursor on startup
  (without it the CLI starts from the beginning).
* **Chunked.** Never loads more than ``--batch-size`` rows at a time. Each
  batch closes its session before the next one opens, so a long-running
  backfill doesn't hold a connection from the pool.
* **Single-threaded.** Bulk one-shot operation — keep S3 GET / RDS load
  conservative. The parallel rescrape path lives in ``archive_rescrape``.

Exit codes
----------
* ``0`` — backfill completed (zero or more parts processed) within the
  configured failure threshold.
* ``1`` — unexpected exception escaped the batch loop.
* ``2`` — finished, but ``(parse_failed + ingest_failed) / processed``
  exceeded ``--max-failure-rate``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.part import Part as DBPart
from app.core.logging import configure_root_logging
from app.crawlers.archive_rescrape import rescrape_crawled_page_from_archive
from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Cursor file lives under ``<state-dir>/`` so a Ctrl-C can resume. Default
# state dir is ``.crawler-state`` (relative to the operator's CWD, which is
# ``backend/`` for the documented run command). Tests override via
# ``--state-dir`` to land checkpoints under tmp_path.
DEFAULT_STATE_DIR = Path(".crawler-state")
CURSOR_FILENAME = "backfill_cursor.json"


def _empty_specs_filter():
    """SQLAlchemy clause matching parts with no specifications populated.

    Three distinct on-disk shapes count as 'no specifications':

    * SQL ``NULL`` — the column was never written.
    * JSON ``null`` (the literal string ``'null'``) — Python ``None`` written
      through SQLAlchemy's default ``JSON`` type lands here, NOT as SQL NULL,
      because the column is not declared ``none_as_null=True``.
    * JSON empty dict (``'{}'``) — early ingests that wrote an empty dict
      instead of a real spec block.

    Casting to ``String`` is dialect-portable: SQLite stores JSON as TEXT and
    PostgreSQL's ``JSON`` (not ``JSONB``) accepts a string cast as well.
    """
    cast_specs = cast(DBPart.specifications, String)
    return or_(
        DBPart.specifications.is_(None),
        cast_specs == "{}",
        cast_specs == "null",
    )


def _select_candidate_part_ids(
    db: Session,
    *,
    batch_size: int,
    after_part_id: Optional[UUID],
    source: Optional[str],
    remaining_limit: Optional[int],
) -> list[UUID]:
    """Return the next chunk of part IDs that need their specifications backfilled.

    Joins parts → crawled_pages on ``part_id`` so that we only consider parts
    that actually have an archived page to re-parse. Parts without any
    matching crawled_pages row (e.g. user-created parts) are skipped — there's
    nothing to re-extract from. ``after_part_id`` is the resume cursor; pass
    ``None`` to start from the beginning.
    """
    chunk = batch_size
    if remaining_limit is not None:
        chunk = min(chunk, remaining_limit)
    if chunk <= 0:
        return []

    stmt = select(DBPart.id).join(DBCrawledPage, DBCrawledPage.part_id == DBPart.id).where(_empty_specs_filter())
    if source is not None:
        stmt = stmt.where(DBCrawledPage.source == source)
    if after_part_id is not None:
        stmt = stmt.where(DBPart.id > after_part_id)
    stmt = stmt.order_by(DBPart.id).limit(chunk)
    return list(db.scalars(stmt).all())


def _read_cursor(cursor_path: Path) -> Optional[UUID]:
    """Return the resume cursor's last_processed_part_id, or None if absent/invalid.

    A malformed cursor is treated as missing rather than fatal: a bad file
    shouldn't block a re-run. The WARN log surfaces it so an operator can
    fix the file if they care, but the run keeps going from the beginning.
    """
    if not cursor_path.is_file():
        return None
    try:
        data = json.loads(cursor_path.read_text(encoding="utf-8"))
        raw = data.get("last_processed_part_id")
        if not raw:
            return None
        return UUID(raw)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        logger.warning("backfill: ignoring malformed cursor at %s: %s", cursor_path, e)
        return None


def _write_cursor(cursor_path: Path, last_part_id: UUID) -> None:
    """Persist the resume cursor. Best-effort: a write failure logs WARN and continues."""
    payload = {
        "last_processed_part_id": str(last_part_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        cursor_path.parent.mkdir(parents=True, exist_ok=True)
        cursor_path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as e:
        logger.warning("backfill: failed to write cursor at %s: %s — resume will be manual", cursor_path, e)


def _process_one_part(
    db: Session,
    part_id: UUID,
    *,
    crawler_user,
    default_category_id: UUID,
    source: Optional[str],
) -> tuple[str, bool]:
    """Re-extract one part. Returns (outcome, updated_flag).

    ``outcome`` is one of: ``parsed_ok``, ``parse_failed``, ``ingest_failed``,
    ``skipped_no_html``, ``skipped_no_page``. ``updated_flag`` is True iff the
    part now has populated specifications (used for the per-batch ``updated``
    counter).
    """
    page_stmt = select(DBCrawledPage).where(DBCrawledPage.part_id == part_id)
    if source is not None:
        page_stmt = page_stmt.where(DBCrawledPage.source == source)
    page_stmt = page_stmt.order_by(DBCrawledPage.last_parsed_at.desc().nullslast())
    page = db.scalars(page_stmt).first()
    if page is None:
        return ("skipped_no_page", False)

    try:
        outcome, _new_part_id, _err = rescrape_crawled_page_from_archive(
            db,
            page,
            crawler_user=crawler_user,
            default_category_id=default_category_id,
            log=logger,
        )
    except Exception as e:
        # MEM015: ingest_payload swallows spec-validation errors but a real
        # exception (S3 outage, DB pool exhaustion) needs to be caught here so
        # one bad part doesn't abort the whole batch. Cursor advances past
        # this part on the caller's side so re-runs don't loop forever.
        logger.warning("backfill: rescrape raised for part %s: %s", part_id, e)
        try:
            db.rollback()
        except Exception:
            pass
        return ("ingest_failed", False)

    if outcome != "parsed_ok":
        return (outcome, False)

    # Re-fetch the part to check whether universal extraction populated specs.
    part = db.get(DBPart, part_id)
    updated = bool(part is not None and part.specifications)
    return (outcome, updated)


def _open_session(session_factory) -> Session:
    """Indirection so tests can patch the session factory.

    The default factory is the module-level ``SessionLocal`` import; tests
    monkeypatch ``app.crawlers.backfill.SessionLocal`` to inject the in-memory
    SQLite session bound to the per-test transaction (mirrors the pattern in
    ``test_parallel_session_isolation.py``).
    """
    return session_factory()


def run_backfill(args: argparse.Namespace) -> int:
    """Execute the backfill loop. Returns the CLI exit code.

    Separated from :func:`main` so tests can call it without re-parsing argv.
    Each batch opens its own session via the module-level ``SessionLocal``
    (patchable by tests).
    """
    state_dir = Path(args.state_dir)
    cursor_path = state_dir / CURSOR_FILENAME

    after_part_id: Optional[UUID] = None
    if args.resume:
        after_part_id = _read_cursor(cursor_path)
        if after_part_id is not None:
            logger.info("backfill: resuming from part_id > %s", after_part_id)
        else:
            logger.info("backfill: --resume set but no usable cursor; starting from beginning")

    if not args.dry_run:
        # Create the state dir up front so cursor writes don't fail mid-run.
        # Skipped on dry-run to keep that path read-only.
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("backfill: cannot create state dir %s: %s", state_dir, e)

    # Resolve the crawler service account + default category once. These are
    # derived from env vars (CRAWLER_USER_ID / CRAWLER_DEFAULT_CATEGORY_*); a
    # misconfiguration surfaces as CrawlerConfigError before any batch runs.
    bootstrap_db = _open_session(SessionLocal)
    try:
        crawler_user = resolve_crawler_user(bootstrap_db, None)
        default_category_id = resolve_default_category_id(bootstrap_db, None)
    finally:
        bootstrap_db.close()

    counters = {
        "batches": 0,
        "processed": 0,
        "updated": 0,
        "skipped": 0,
        "parse_failed": 0,
        "ingest_failed": 0,
    }
    overall_start = time.monotonic()
    limit_total: Optional[int] = args.limit if args.limit and args.limit > 0 else None

    while True:
        if limit_total is not None and counters["processed"] >= limit_total:
            break
        remaining = (limit_total - counters["processed"]) if limit_total is not None else None

        batch_db = _open_session(SessionLocal)
        try:
            part_ids = _select_candidate_part_ids(
                batch_db,
                batch_size=args.batch_size,
                after_part_id=after_part_id,
                source=args.source,
                remaining_limit=remaining,
            )
            if not part_ids:
                break

            counters["batches"] += 1
            batch_idx = counters["batches"]
            batch_start = time.monotonic()
            batch_processed = 0
            batch_updated = 0
            batch_skipped = 0
            start_id = part_ids[0]

            if args.dry_run:
                # Counts only; advance cursor so successive dry-run loops don't
                # repeat the same chunk forever.
                batch_processed = len(part_ids)
                counters["processed"] += batch_processed
                after_part_id = part_ids[-1]
                logger.info(
                    "backfill[dry-run]: batch=%d start_id=%s processed=%d updated=0 skipped=0 elapsed=%.2fs",
                    batch_idx,
                    start_id,
                    batch_processed,
                    time.monotonic() - batch_start,
                )
                continue

            for part_id in part_ids:
                outcome, updated = _process_one_part(
                    batch_db,
                    part_id,
                    crawler_user=crawler_user,
                    default_category_id=default_category_id,
                    source=args.source,
                )
                batch_processed += 1
                if outcome == "parsed_ok" and updated:
                    batch_updated += 1
                elif outcome in ("skipped_no_html", "skipped_no_page"):
                    batch_skipped += 1
                elif outcome == "parse_failed":
                    counters["parse_failed"] += 1
                elif outcome == "ingest_failed":
                    counters["ingest_failed"] += 1
                # Advance cursor as we go so a crash mid-batch still resumes
                # past the last attempted part (failure-included), matching
                # the failure-mode contract: a bad part shouldn't loop forever.
                after_part_id = part_id

            counters["processed"] += batch_processed
            counters["updated"] += batch_updated
            counters["skipped"] += batch_skipped

            elapsed = time.monotonic() - batch_start
            logger.info(
                "backfill: batch=%d start_id=%s processed=%d updated=%d skipped=%d elapsed=%.2fs",
                batch_idx,
                start_id,
                batch_processed,
                batch_updated,
                batch_skipped,
                elapsed,
            )

            # Persist cursor after each successful batch. Failure here is
            # non-fatal (logged WARN); resume just becomes manual next run.
            if after_part_id is not None:
                _write_cursor(cursor_path, after_part_id)
        finally:
            batch_db.close()

    total_elapsed = time.monotonic() - overall_start
    failures = counters["parse_failed"] + counters["ingest_failed"]
    failure_rate = (failures / counters["processed"]) if counters["processed"] else 0.0

    logger.info(
        "backfill: done batches=%d processed=%d updated=%d skipped=%d "
        "parse_failed=%d ingest_failed=%d failure_rate=%.3f elapsed=%.2fs%s",
        counters["batches"],
        counters["processed"],
        counters["updated"],
        counters["skipped"],
        counters["parse_failed"],
        counters["ingest_failed"],
        failure_rate,
        total_elapsed,
        " (dry-run)" if args.dry_run else "",
    )

    if counters["processed"] > 0 and failure_rate > args.max_failure_rate:
        logger.error(
            "backfill: failure_rate=%.3f exceeded --max-failure-rate=%.3f; exiting 2",
            failure_rate,
            args.max_failure_rate,
        )
        return 2
    return 0


def _positive_int(raw: str) -> int:
    """argparse type for ``--batch-size`` / ``--limit`` style ints (must be > 0 for batch-size)."""
    try:
        value = int(raw)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected an integer, got {raw!r}") from e
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer (>0), got {value}")
    return value


def _nonneg_int(raw: str) -> int:
    """argparse type for ``--limit`` (0 = unlimited, negative = invalid)."""
    try:
        value = int(raw)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected an integer, got {raw!r}") from e
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be a non-negative integer, got {value}")
    return value


def _failure_rate(raw: str) -> float:
    """argparse type for ``--max-failure-rate`` — must be in [0.0, 1.0]."""
    try:
        value = float(raw)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected a float, got {raw!r}") from e
    if not (0.0 <= value <= 1.0):
        raise argparse.ArgumentTypeError(f"must be in [0.0, 1.0], got {value}")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.crawlers.backfill",
        description="Re-extract Part.specifications for parts whose JSON column is NULL or empty.",
    )
    parser.add_argument(
        "--batch-size",
        type=_positive_int,
        default=100,
        help="Parts per batch (default: 100). Each batch opens its own DB session.",
    )
    parser.add_argument(
        "--limit",
        type=_nonneg_int,
        default=0,
        help="Cap on total parts processed (default: 0 = unlimited).",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Restrict to one adapter's archive (matches crawled_pages.source).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Read the cursor file and start from Part.id > <cursor>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Count parts that would be processed; perform NO writes.",
    )
    parser.add_argument(
        "--max-failure-rate",
        type=_failure_rate,
        default=0.5,
        help="Exit code 2 when (parse_failed+ingest_failed)/processed exceeds this (default: 0.5).",
    )
    parser.add_argument(
        "--state-dir",
        type=str,
        default=str(DEFAULT_STATE_DIR),
        help=f"Directory for the resume cursor file (default: {DEFAULT_STATE_DIR}).",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint. Returns the exit code (callers should ``sys.exit`` on it)."""
    configure_root_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return run_backfill(args)
    except KeyboardInterrupt:
        logger.warning("backfill: interrupted by user; partial progress saved to cursor file.")
        return 1
    except Exception:
        logger.exception("backfill: unexpected failure")
        return 1


if __name__ == "__main__":
    sys.exit(main())
