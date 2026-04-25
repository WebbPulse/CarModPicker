---
estimated_steps: 40
estimated_files: 2
skills_used: []
---

# T01: Add `app/crawlers/backfill.py` chunked/idempotent/resumable re-extraction CLI

Stand up `backend/app/crawlers/backfill.py` as a CLI module (`python -m app.crawlers.backfill`) that selects `CrawledPage` rows whose linked `Part.specifications` is NULL or empty, batches them by `--batch-size N` (default 100), and re-runs the per-page parse+ingest path via the existing `rescrape_crawled_page_from_archive` helper from `archive_rescrape.py` (which already invokes `apply_universal_extraction` between parse and ingest, per MEM026). The CLI must be:

- **Idempotent** — re-running on the same input set produces no spurious DB writes. Achieved by selecting only parts where `specifications IS NULL OR specifications = '{}'` so a second run picks up zero rows once extraction succeeded for each. (For PostgreSQL `JSON` and SQLite `JSON`, treat both `NULL` and the empty-dict literal as 'no specifications'. Use `or_(Part.specifications.is_(None), cast(Part.specifications, String) == '{}')` or equivalent — verify against the SQLite in-memory test DB used by pytest.)
- **Resumable** — write a tiny JSON checkpoint at `backend/.crawler-state/backfill_cursor.json` after every successful batch with `{"last_processed_part_id": "<uuid>", "updated_at": "<iso8601>"}`. On startup, if `--resume` is passed and the file exists, the SELECT starts from `Part.id > <cursor>`. Without `--resume`, it starts from the beginning regardless of the file's presence (resume is opt-in to keep the dev fast-path simple).
- **Chunked** — never load more than `--batch-size` rows into memory; commit per-batch via the existing per-page commits inside `rescrape_crawled_page_from_archive`.
- **Observable** — log one structured INFO line per batch: `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns`, plus a final summary line and exit code (0 = success, 2 = above-threshold failure rate, 1 = unexpected exception).

CLI args (use stdlib `argparse`, mirror `app/crawlers/__main__.py` conventions):
- `--batch-size N` (default 100)
- `--limit N` (default 0 = unlimited; cap on total parts processed)
- `--source <adapter>` (optional; restrict to one adapter's archive — mirrors `archive_rescrape.run_rescrape_all_archived_pages(source=...)`)
- `--resume` (opt-in: read cursor file)
- `--dry-run` (count parts that would be processed; print summary; perform NO writes)
- `--max-failure-rate FLOAT` (default 0.5; CLI exits non-zero if `(parse_failed + ingest_failed) / processed` exceeds this; only enforced when processed > 0)

Do NOT reuse the parallel ThreadPoolExecutor from `archive_rescrape` for V1 — backfill is a one-shot bulk operation that should be conservative on RDS/S3 quota. Single-threaded sequential per-batch is fine for the M002 close gate; the rescrape job remains the parallel path for ad-hoc re-parses.

Use `app.crawlers.runner.resolve_crawler_user(db, None)` and `resolve_default_category_id(db, None)` to source the service-account user and default category, mirroring how `ecs_rescrape_runner.py` boots. Logger setup: `from app.core.logging import configure_root_logging; configure_root_logging()` at the top of `main()` so log lines match the rest of the crawler subsystem.

Guard against `MEM008` (S3 import-time crash): `app.crawlers.*` imports trigger boto3 head_bucket calls at module load; the existing crawler entry points already work under prod env vars. The CLI should NOT set `TESTING=true` itself (that would silence the EMF metric we want firing) — it relies on the operator's environment. Tests, however, MUST run with `TESTING=true` (which conftest.py already sets).

FAILURE MODES (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `rescrape_crawled_page_from_archive` (S3 fetch + parse + ingest) | catch, log WARN, increment failure counter, advance cursor past the failed part_id so re-runs don't loop forever | n/a (S3 client has its own timeouts; failure surfaces as exception) | drop the spec block (handled inside ingest_payload per MEM015), Part still persists |
| `SessionLocal` (per-batch DB session) | rollback + close + re-raise as exit-1 unexpected exception | n/a (sync) | n/a |
| Cursor file write (`backfill_cursor.json`) | log WARN, continue (resume becomes manual the next run) | n/a | n/a |

LOAD PROFILE (Q6):
- Shared resources: SQLAlchemy SessionLocal pool (per-batch checkout); S3 GET budget for archived HTML; CloudWatch EMF stdout (from inherited ingest_payload firing)
- Per-operation cost: 1 S3 GET + 1 parse + 1-3 DB writes (Part + PartListing + PartPriceHistory) per part; ~50ms-500ms per part empirically (S03 backfill rescrape is the closest analog)
- 10x breakpoint: serial per-batch is conservative; the practical cap for M002 close is the 25k-parts catalog; even at 500ms/part that's ~3.5 hours sequential, acceptable for a one-shot M002 close gate. If parallelism is needed later, mirror `archive_rescrape._compute_rescrape_workers` and bound on DB pool budget.

NEGATIVE TESTS (Q7):
- Malformed inputs: `--batch-size 0` should reject with argparse error; `--batch-size -1` should reject; `--max-failure-rate 1.5` should reject (must be in [0, 1])
- Error paths: `rescrape_crawled_page_from_archive` returns `('parse_failed', None, '<msg>')` — counted as failure, doesn't crash; raises arbitrary exception — caught, logged, counted as ingest_failed, advance cursor
- Boundary conditions: empty result set (no parts with NULL specifications) — exit 0 immediately with summary; cursor file missing on `--resume` — silently start from beginning; `--limit` smaller than `--batch-size` — process up to `--limit` and exit

Write tests in `backend/tests/crawlers/test_backfill.py`:
- `test_select_only_parts_with_empty_specifications` — seed 3 Part rows (one with NULL specifications, one with `{}`, one with `{'weight_grams': 100, 'weight_grams_confidence': 'high'}`), assert the SELECT returns exactly the first two part IDs.
- `test_dry_run_makes_no_writes` — seed 2 parts + crawled_pages with archived HTML in the test fixture dir; run the CLI's main() with `argv=['--dry-run']`; assert no Part row had its `specifications` updated and no `last_parsed_at` changed.
- `test_idempotent_second_run_processes_zero_parts` — patch `rescrape_crawled_page_from_archive` (at the import site `app.crawlers.backfill.rescrape_crawled_page_from_archive` per MEM011/MEM017) to a stub that sets `Part.specifications = {'weight_grams': 1.0, 'weight_grams_confidence': 'high'}` on the first call; run main() once (asserts processed=1, updated=1); run again (asserts processed=0).
- `test_resume_starts_from_cursor` — write a cursor file `{"last_processed_part_id": "<id1>"}`, seed 3 parts with id1 < id2 < id3 (sort by Part.id); run with `--resume`; assert only id2 and id3 were touched.
- `test_above_threshold_failure_rate_exits_2` — patch `rescrape_crawled_page_from_archive` to always return `('parse_failed', None, 'stub error')`; assert `main()` returns exit code 2.
- `test_source_filter_restricts_adapter` — seed crawled_pages with two distinct sources; run with `--source <one>`; assert only that adapter's pages were touched.
- `test_argparse_rejects_invalid_batch_size` — `argv=['--batch-size', '0']` should raise SystemExit with code 2.
- `test_argparse_rejects_invalid_failure_rate` — `argv=['--max-failure-rate', '1.5']` should raise SystemExit with code 2.

All tests MUST patch `rescrape_crawled_page_from_archive` at `app.crawlers.backfill.rescrape_crawled_page_from_archive` (import site, per MEM011/MEM017). DO NOT patch the source `app.crawlers.archive_rescrape.rescrape_crawled_page_from_archive`.

The `.gsd/` directory is in `.gitignore` (per the cleanup-prompt context), but `backend/.crawler-state/` is a runtime directory — add it to `.gitignore` instead and create the directory at runtime via `Path('.crawler-state').mkdir(exist_ok=True)` in `main()`. No `.gitkeep` needed if the directory is created at runtime; remove that from Expected Output if so. (Decision: do create at runtime, do NOT commit a placeholder — keeps the repo clean and matches the convention used by other runtime caches.)

## Inputs

- ``backend/app/crawlers/archive_rescrape.py` — reuse `rescrape_crawled_page_from_archive` for per-page parse+ingest (already invokes `apply_universal_extraction` per MEM026)`
- ``backend/app/crawlers/runner.py` — reuse `resolve_crawler_user` and `resolve_default_category_id` for service-account boot (mirrors `ecs_rescrape_runner.py` pattern)`
- ``backend/app/crawlers/__main__.py` — argparse convention reference for the existing crawler CLI`
- ``backend/app/api/models/crawled_page.py` — `CrawledPage.parse_status`, `.source`, `.part_id`, `.html_s3_key`, `.html_local_path`, `.last_parsed_at``
- ``backend/app/api/models/part.py` — `Part.specifications` (Optional[Dict[str, Any]]) is the field to backfill`
- ``backend/app/core/logging.py` — `configure_root_logging` for matching log format`
- ``backend/app/db/session.py` — `SessionLocal` for the per-batch session checkout`

## Expected Output

- ``backend/app/crawlers/backfill.py` — new CLI module with `main(argv=None) -> int`, `argparse` setup with batch-size / limit / source / resume / dry-run / max-failure-rate args, batch loop + cursor write, structured logs, exit-code semantics (0 success / 1 unexpected / 2 above-threshold-failure-rate)`
- ``backend/tests/crawlers/test_backfill.py` — pytest module with the 8 tests listed in description; all patch `rescrape_crawled_page_from_archive` at the import site`

## Verification

TESTING=true pytest backend/tests/crawlers/test_backfill.py -n auto --rootdir=backend -q --no-cov

## Observability Impact

- Signals added/changed: per-batch INFO log line `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns`; final summary line; per-failure WARN propagated from `rescrape_crawled_page_from_archive`; `ExtractionFailureRate` EMF continues to fire from `ingest_payload` per existing wiring (no new emit added in this task)
- How a future agent inspects this: tail the process stdout/stderr; read `backend/.crawler-state/backfill_cursor.json` for last-known progress; query `select count(*) from parts where specifications is null` against the DB for remaining work
- Failure state exposed: non-zero CLI exit code (1 unexpected, 2 above-threshold failure rate); WARN logs name the adapter + URL; cursor file shows where the last successful batch landed before any crash
