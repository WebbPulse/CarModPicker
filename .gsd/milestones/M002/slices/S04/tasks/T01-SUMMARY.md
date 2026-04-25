---
id: T01
parent: S04
milestone: M002
key_files:
  - backend/app/crawlers/backfill.py
  - backend/tests/crawlers/test_backfill.py
  - .gitignore
key_decisions:
  - Empty-specs filter matches three on-disk shapes (SQL NULL, JSON 'null', JSON '{}') because Part.specifications uses default JSON column without none_as_null=True
  - Single-threaded sequential per-batch (no ThreadPoolExecutor) — backfill is a one-shot bulk operation; parallel rescrape stays in archive_rescrape.py
  - Cursor advances past every attempted part (failure-included) so a bad part can't loop forever on re-runs
  - Added --state-dir CLI flag (default .crawler-state) so tests can land cursor under tmp_path; matches operator convention for runtime caches
duration: 
verification_result: passed
completed_at: 2026-04-25T05:31:06.628Z
blocker_discovered: false
---

# T01: Add app/crawlers/backfill.py: chunked, idempotent, resumable re-extraction CLI for Part.specifications

**Add app/crawlers/backfill.py: chunked, idempotent, resumable re-extraction CLI for Part.specifications**

## What Happened

Stood up `backend/app/crawlers/backfill.py` as a CLI module (`python -m app.crawlers.backfill`) that selects parts whose `specifications` is unset (NULL, JSON `null`, or `'{}'`) joined to a `crawled_pages` row, and re-runs the per-page parse + ingest path via `archive_rescrape.rescrape_crawled_page_from_archive` so universal extraction (MEM026) and ingest-time spec validation (MEM009) flow through unchanged.

CLI shape: `--batch-size N` (positive int, default 100), `--limit N` (non-negative, 0=unlimited), `--source <adapter>` (optional source filter), `--resume` (opt-in cursor read), `--dry-run` (count-only, no writes), `--max-failure-rate FLOAT` ([0.0, 1.0], default 0.5), `--state-dir DIR` (cursor location, default `.crawler-state`). Single-threaded sequential per-batch — bulk one-shot operation that should be conservative on RDS / S3 quota; the parallel rescrape path stays in `archive_rescrape`.

Each batch opens its own `SessionLocal()`, selects up to `--batch-size` candidate part IDs (joined with crawled_pages), invokes the rescrape helper per part, advances the in-memory cursor past every attempted part (failure-included so a bad part doesn't loop forever), and persists the cursor at `<state-dir>/backfill_cursor.json` after the batch. Per-batch INFO log line `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns` plus a final summary line. Exit 0 on success, 1 on unexpected exception, 2 when failure_rate exceeds threshold (only enforced when processed > 0).

Failure modes handled per Q5 of the task plan: rescrape exceptions caught and counted as ingest_failed (cursor advances); cursor-write failures are best-effort WARN; KeyboardInterrupt logs and exits 1; bootstrap session always closes in a `finally`.

Two notable findings during implementation (captured to memory store): (1) MEM041 — SQLAlchemy `JSON` columns without `none_as_null=True` serialize Python None as the literal string `'null'`, so the empty-specs filter has to match SQL NULL, JSON `null`, and JSON `{}`. The first test run failed because `cast(specs, String) == '{}'` only caught one of those shapes. (2) MEM042 — testing CLIs that open their own `SessionLocal()` per batch requires patching `module.SessionLocal` with a sessionmaker bound to `db_session.connection()` and `join_transaction_mode='create_savepoint'` so the CLI's commits become SAVEPOINT releases inside the test's outer transaction.

Test suite (8 listed in the plan + 1 added negative-batch-size case = 9 tests): selection filter, dry-run no-writes, idempotent second run, resume-from-cursor, above-threshold-failure-rate-exits-2, --source restriction, and three argparse rejection tests. All patch `app.crawlers.backfill.rescrape_crawled_page_from_archive` at the import site per MEM011/MEM017. Added `.crawler-state/` to `.gitignore` since the runtime cursor file should not be committed.

Slice-level verification (per S04-PLAN.md): only the backfill CLI's verification command is in scope for this task. The admin extraction-health endpoint signals are deferred to T02; the cursor file inspection surface and exit-code semantics from this task contribute to the slice's failure-visibility checks and were exercised by the test suite.

## Verification

Ran the task plan's verification command directly: `TESTING=true pytest backend/tests/crawlers/test_backfill.py -n auto --rootdir=backend -q --no-cov` — 9 passed in 8.58s. Tests cover selection filter (NULL + JSON null + empty-dict matches; populated specs excluded), dry-run no-writes (rescrape never invoked, no Part / CrawledPage row mutated, no cursor file written), idempotent second run (run 1 populates specs, run 2 invokes rescrape 0 times), resume-from-cursor (cursor at id1 means only id2 + id3 processed in id-sorted order), above-threshold failure rate (all-failures stub → exit 2), --source filter (only the matching adapter's pages touched), and argparse rejection of --batch-size 0, --batch-size -1, and --max-failure-rate 1.5 (each SystemExit code 2). Discovered and fixed the JSON-null filter gap during the first test run before re-running.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest backend/tests/crawlers/test_backfill.py -n auto --rootdir=backend -q --no-cov` | 0 | ✅ pass | 8580ms |

## Deviations

Added a `--state-dir` argument beyond what the task plan listed. The plan asked for the cursor at `backend/.crawler-state/backfill_cursor.json` (relative to operator CWD); making the directory configurable lets tests use `tmp_path` cleanly and gives operators an escape hatch without changing the default behavior. Default is `.crawler-state` so the operator-facing semantics are unchanged. Added one extra negative test (`test_argparse_rejects_negative_batch_size`) alongside the listed 8; the plan only specified the `--batch-size 0` case, but the description text called out -1 as a rejection target so I covered both.

## Known Issues

none

## Files Created/Modified

- `backend/app/crawlers/backfill.py`
- `backend/tests/crawlers/test_backfill.py`
- `.gitignore`
