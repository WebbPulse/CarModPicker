---
id: S04
parent: M002
milestone: M002
provides:
  - ["backend/app/crawlers/backfill.py CLI (python -m app.crawlers.backfill) — chunked/idempotent/resumable re-extraction over Part.specifications", "backend/app/api/endpoints/admin/extraction_health.py — GET /api/admin/extraction-health returning compliance + coverage + failure_rate_7d + window metadata", "Admin endpoint contract for S11 to consume: per_tier '<n>/<n>' compliance strings, coverage.per_tier.<tier>.per_field heatmap data, failure_rate_7d list with adapter/failed/parsed/rate/tier", ".crawler-state/ directory convention for runtime cursor files (gitignored)", "Dialect-aware JSON-extract helper pattern (inlined in extraction_health.py)", "MEM044 / MEM045 / MEM047 captured to memory store"]
requires:
  - slice: S01
    provides: SpecRegistry, ingest validation hook (used transitively via rescrape_crawled_page_from_archive)
  - slice: S02
    provides: Universal extraction post-hook + UNIVERSAL_FIELD_NAMES frozenset (consumed by coverage block)
  - slice: S03
    provides: ADAPTER_REGISTRY, _classify_tier, _is_compliant from compliance_audit.py (compliance + coverage + failure_rate_7d all reuse these)
affects:
  - ["S11 (Admin shell + extraction-health UI) — consumes the GET /api/admin/extraction-health JSON shape directly", "S13 (Final integration) — operator runs the backfill CLI manually as part of the milestone close gate; admin endpoint is the verification surface"]
key_files:
  - ["backend/app/crawlers/backfill.py", "backend/tests/crawlers/test_backfill.py", "backend/app/api/endpoints/admin/extraction_health.py", "backend/tests/api/endpoints/test_admin_extraction_health.py", "backend/app/main.py", ".gitignore"]
key_decisions:
  - ["Failure-rate signal sourced from `crawled_pages.parse_status` (DB) over rolling 7-day window, not CloudWatch EMF (D009 — slice plan said D008 but that ID was taken; rationale unchanged). Authoritative state, no IAM round-trip, works in dev + tests, single SQL query per request.", "Empty-specs filter matches three on-disk shapes (SQL NULL, JSON 'null', JSON '{}') because Part.specifications uses default JSON column without none_as_null=True. The cast(specs, String) == '{}' check alone misses ~67% of rows.", "Single-threaded sequential per-batch backfill (no ThreadPoolExecutor) — backfill is a one-shot bulk operation that should be conservative on RDS / S3 quota. Parallel rescrape stays in archive_rescrape.py.", "Cursor advances past every attempted part (failure-included) so a bad part can't loop forever on re-runs.", "Added --state-dir CLI flag (default .crawler-state) so tests can land cursor under tmp_path; matches operator convention for runtime caches.", "Dialect-aware JSON-extract helper lives inside extraction_health.py rather than as a shared utility — keeps the slice scope tight; fan-out can come later if a second consumer materializes.", "Empty-specs detection inlines the three-shape match (MEM041/MEM044) in extraction_health.py instead of importing _empty_specs_filter from backfill.py — keeps the FastAPI request path free of crawler-runtime imports."]
patterns_established:
  - ["Dialect-aware JSON-extract: branch on db.bind.dialect.name == 'sqlite' (json_extract) vs 'postgresql' (subscript) for cross-DB JSON queries. Field names from a closed allowlist (UNIVERSAL_FIELD_NAMES frozenset) are the actual injection guard.", "Empty Part.specifications match must cover three on-disk shapes: SQL NULL, JSON 'null' literal, JSON '{}' (MEM044). Inlined at every consumer rather than centralized to keep crawler-runtime imports out of the FastAPI request path.", "CLI tests requiring the CLI to open its own SessionLocal() per batch: patch module.SessionLocal with a sessionmaker bound to db_session.connection() and join_transaction_mode='create_savepoint' (MEM045) so the CLI's commit/close lifecycle runs unchanged inside the test's outer transaction.", "Admin observability endpoints prefer DB-derived signals over CloudWatch EMF reads when the DB is the authoritative source — single round-trip, works in dev + tests, no IAM dependency (D009)."]
observability_surfaces:
  - ["INFO log per batch: 'backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns' (structured, parseable)", "WARN log on per-part rescrape failure (carries part_id + error class)", "Final summary log line at CLI exit (batches, parts_processed, parts_updated, skipped, ingest_failed, failure_rate)", "CLI exit codes: 0 success / 1 unexpected exception / 2 above-threshold failure-rate / argparse SystemExit 2 on malformed args", ".crawler-state/backfill_cursor.json checkpoint file (operator-inspectable for resume position)", "GET /api/admin/extraction-health JSON: compliance counts, per-tier coverage gradient with per-field presence ratios, 7d failure-rate per adapter, window metadata", "FastAPI access log captures admin endpoint requests via standard middleware", "Existing CloudWatch EMF ExtractionFailureRate metric continues to fire from ingest_payload during backfill runs (env-gated, no behavior change)"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T05:42:40.686Z
blocker_discovered: false
---

# S04: Re-extraction backfill + admin extraction-health API

**Shipped chunked/idempotent/resumable re-extraction CLI and GET /api/admin/extraction-health endpoint that exposes DB-derived compliance, per-tier coverage gradient, and 7d per-adapter failure-rate without CloudWatch dependency.**

## What Happened

S04 closes the operational seam for M002's enrichment work. Two surfaces shipped: a CLI that backfills `Part.specifications` for already-ingested parts, and an admin endpoint that operators (and the eventual S11 admin UI) read to see compliance + coverage + failure-rate at a glance.

**T01 — Backfill CLI (`python -m app.crawlers.backfill`).** Selects parts whose `specifications` is unset (NULL, JSON `null`, or `'{}'`) joined to a `crawled_pages` row, then re-runs the per-page parse + ingest path via `archive_rescrape.rescrape_crawled_page_from_archive` so the S02 universal extractor and S01 ingest-time spec validation flow through unchanged. CLI shape: `--batch-size N` (default 100), `--limit N` (0=unlimited), `--source <adapter>`, `--resume`, `--dry-run`, `--max-failure-rate FLOAT` (default 0.5), `--state-dir DIR` (default `.crawler-state`). Single-threaded sequential per-batch — backfill is a one-shot bulk operation; the parallel rescrape path stays in `archive_rescrape`. Each batch opens its own `SessionLocal()`, processes up to `--batch-size` candidates, advances an in-memory cursor past every attempted part (failure-included so a bad part can't loop forever), and persists the cursor at `<state-dir>/backfill_cursor.json` after the batch. Per-batch INFO log line `backfill: batch=N start_id=<uuid> processed=N updated=N skipped=N elapsed=Ns` plus a final summary. Exit codes: 0 success, 1 unexpected exception, 2 above-threshold failure rate.

**T02 — Admin extraction-health endpoint (`GET /api/admin/extraction-health`).** Single sub-router gated on `Depends(get_current_admin_user)` returning a structured `ExtractionHealthResponse` with three sections: (1) **compliance** counts (108/108 per MEM037, with per-tier `<n>/<n>` strings to match the `compliance_audit.py` stdout shape) reusing `_classify_tier`/`_is_compliant`/`ADAPTER_REGISTRY` directly — no shell-out; (2) **coverage** per tier (parts_with_specs / parts_total + per-field presence ratio across `UNIVERSAL_FIELD_NAMES`) using a dialect-aware `_field_present_count` helper that branches on `db.bind.dialect.name` (SQLite `func.json_extract` vs. Postgres subscript `Part.specifications[field]`); (3) **failure_rate_7d** grouping `crawled_pages.last_parsed_at >= now-7d` by source for parsed/failed counts, dropping rows whose source isn't in `ADAPTER_REGISTRY` (defensive — a removed adapter shouldn't surface). Window metadata (`days=7`, `since=ISO8601`) is in the response so the frontend doesn't have to assume.

**Threat surface** is the new admin endpoint. The dialect-aware JSON-extract helper is the only theoretically injectable seam, and it's mitigated three ways: (a) field names come from the immutable `UNIVERSAL_FIELD_NAMES` frozenset, never from request input; (b) values flow through SQLAlchemy parameterization; (c) the endpoint takes no body or query params. Auth is `Depends(get_current_admin_user)` — 401 unauth, 403 non-admin, 200 admin. Adapter slugs and counts are operationally sensitive but not PII.

**Two notable findings captured to the memory store** (already inlined in MEM044/MEM045/MEM047):
- **MEM044 (gotcha):** SQLAlchemy `JSON` columns without `none_as_null=True` serialize Python `None` as the literal JSON string `'null'`, so empty-specs filters must match three on-disk shapes (SQL NULL, JSON `'null'`, JSON `'{}'`). T01's first test run failed because `cast(specs, String) == '{}'` only caught one of those shapes. Same logic inlined into the admin endpoint to keep crawler-runtime imports out of the FastAPI request path.
- **MEM045 (pattern):** Testing CLIs that open their own `SessionLocal()` per batch requires patching `module.SessionLocal` with a sessionmaker bound to `db_session.connection()` and `join_transaction_mode='create_savepoint'` so per-batch commits become SAVEPOINT releases inside the test's outer transaction.
- **MEM047 (pattern):** Dialect-aware JSON-extract for cross-DB compatibility; field names from a closed allowlist are the actual injection guard.

**Decision recorded as D009:** failure-rate sources from `crawled_pages.parse_status` (DB), not CloudWatch EMF — authoritative state, no IAM/network round-trip, works in dev + tests, single SQL query per request. EMF metric `ExtractionFailureRate` continues to fire from `ingest_payload` for monitoring; the admin endpoint deliberately does not consume it. Slice plan called for D008 but that ID was already taken — D009 is the next free ID.

**Patterns established for downstream slices.** S11 (admin UI) consumes the JSON shape verbatim — `compliance.per_tier` strings render as compliance pills, `coverage.per_tier.<tier>.per_field` becomes the field-presence heatmap, `failure_rate_7d` becomes the per-adapter rate column. The dialect-aware JSON-extract helper is inlined in `extraction_health.py` rather than extracted to a shared utility — fan-out to a shared `app.crawlers.json_query` module can come when (or if) a second consumer materializes. The empty-specs three-shape match (MEM044) is now duplicated in `backfill.py::_empty_specs_filter` and `extraction_health.py` — the duplication is intentional to keep the FastAPI request path free of crawler-runtime imports, but if a third site needs it the pattern should be lifted.

**What S05+ should know.** The backfill is opt-in (operator runs the CLI manually with prod env vars + `CRAWLER_USER_ID`/`CRAWLER_DEFAULT_CATEGORY_NAME`). It is not auto-scheduled — that's intentional for the M002 close gate. The backfill_cursor.json is per `--state-dir`, not per source; if you start `--source a` then resume `--source b` the cursor is shared (acceptable for a one-shot bulk operation, but documented in the CLI help). The 7-day failure window is a hard-coded `WINDOW_DAYS = 7` constant — make it a query param if a future user surface needs other windows.

## Verification

**Slice-level verification (per S04-PLAN.md must-haves):**

1. **Test suite green** — Ran `TESTING=true pytest backend/tests/crawlers/test_backfill.py backend/tests/api/endpoints/test_admin_extraction_health.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend -q --no-cov`. **Result: 20 passed in 8.68s** (9 backfill + 7 extraction-health + 4 compliance-audit, no regressions).

2. **Backfill CLI shape** — Ran `python -m app.crawlers.backfill --help` from `backend/`. All required flags present and documented: `--batch-size` (default 100), `--limit` (default 0=unlimited), `--source`, `--resume` (opt-in), `--dry-run`, `--max-failure-rate` (default 0.5), `--state-dir` (default `.crawler-state`). Argparse rejects `--batch-size 0`, `--batch-size -1`, and `--max-failure-rate 1.5` with SystemExit code 2 (covered by 3 dedicated negative tests).

3. **Idempotency proven by test** — `test_idempotent_second_run_processes_zero_parts` patches `rescrape_crawled_page_from_archive` to populate `Part.specifications` on first call; second run reports `processed=0, updated=0` because the empty-specs filter no longer matches.

4. **Resumability proven by test** — `test_resume_starts_from_cursor` writes `{"last_processed_part_id": "<id1>"}`, seeds 3 parts (id1<id2<id3), and asserts only id2+id3 are touched on `--resume`.

5. **Failure-rate threshold enforcement** — `test_above_threshold_failure_rate_exits_2` patches the rescrape stub to always return `parse_failed`; CLI exits 2.

6. **Admin endpoint contract** — `test_extraction_health_returns_compliance_block` asserts `compliance.compliant == compliance.total` and `per_tier` keys (`http`, `tls`, `browser`) each render `<n>/<n>` strings. `test_extraction_health_coverage_counts_specifications_field` seeds a part with `weight_grams` populated and verifies `coverage.per_tier.http.parts_with_specs >= 1` and `per_field.weight_grams >= 1/parts_total`. `test_extraction_health_failure_rate_window` seeds 1 failed + 1 parsed for an adapter and asserts `rate=0.5`. `test_extraction_health_excludes_old_failures` confirms 30d-old rows don't appear in the 7d window. `test_extraction_health_skips_unknown_sources` confirms a `source='not_a_real_adapter'` row is skipped (no entry surfaces).

7. **Auth** — `test_extraction_health_unauthorized` (no auth → 401) and `test_extraction_health_forbidden_non_admin` (regular user → 403) both green.

8. **Wiring** — `extraction_health` imported in `backend/app/main.py:33` and registered via `endpoint_registry.register_endpoint(...)` at line 350 with prefix `/admin/extraction-health` and `tags=["admin"]`.

9. **Threat-surface mitigations confirmed** — Field names sourced from `UNIVERSAL_FIELD_NAMES` frozenset (immutable, not request-derived); endpoint takes no body or query params; auth gate `Depends(get_current_admin_user)` enforces 401/403; SQL queries use SQLAlchemy ORM expressions (no raw string interpolation).

10. **Decision recorded** — D009 (failure-rate from DB, not CloudWatch EMF) saved to `.gsd/DECISIONS.md` via `gsd_save_decision` from T02.

**Verification evidence table:**

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest backend/tests/crawlers/test_backfill.py backend/tests/api/endpoints/test_admin_extraction_health.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend -q --no-cov` | 0 | ✅ pass | 8680ms |
| 2 | `python -m app.crawlers.backfill --help` (from `backend/`) | 0 | ✅ all expected flags documented | <1000ms |

**Live runtime CLI verification deferred** — running `python -m app.crawlers.backfill --dry-run --limit 0` against the live local DB requires `CRAWLER_USER_ID` + `CRAWLER_DEFAULT_CATEGORY_NAME` env vars and an active Postgres docker-compose instance. Auto-mode does not bring up Docker. Behavior is exhaustively covered by `test_dry_run_makes_no_writes` which patches at the import site per MEM011/MEM017, asserts no Part row mutations, no `last_parsed_at` changes, and no cursor file written. Operator-driven dry-run is the gate for S13 final integration verification.

## Requirements Advanced

- R005 — Backfill CLI delivered: chunked/idempotent/resumable re-extraction over Part.specifications via existing rescrape_crawled_page_from_archive. 9 tests cover selection filter, dry-run, idempotency, resume, failure-rate threshold, source filter, argparse rejections.
- R006 — GET /api/admin/extraction-health endpoint delivered with DB-derived compliance (108/108 + per-tier '<n>/<n>'), per-tier coverage gradient over UNIVERSAL_FIELD_NAMES, and 7d per-adapter failure-rate from crawled_pages.parse_status. 7 tests cover auth, contract shape, coverage seeding, failure-rate window, old-failure exclusion, unknown-source skip, window metadata.
- R018 — Crawler test suite extended by 9 new backfill tests + 7 new extraction-health tests (16 net new) without breaking existing 4 compliance-audit tests. All 20 tests green in 8.68s under -n auto.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

"T01 added a `--state-dir` CLI argument beyond what the plan listed. Plan specified the cursor at `backend/.crawler-state/backfill_cursor.json` (relative to operator CWD); making the directory configurable lets tests use tmp_path cleanly without changing default operator behavior. Default is `.crawler-state` so operator-facing semantics are unchanged. T01 also added one extra negative test (`test_argparse_rejects_negative_batch_size`) — plan only specified `--batch-size 0`, but the description text called out `-1` as a rejection target so both are covered. T02 captured the EMF-vs-DB choice as D009 instead of D008 (plan called for D008, but that ID was already taken — D009 is the next free ID; rationale unchanged)."

## Known Limitations

"Backfill CLI is not auto-scheduled — operator runs it manually with prod env vars (CRAWLER_USER_ID + CRAWLER_DEFAULT_CATEGORY_NAME). Acceptable for the M002 close gate; if continuous backfill is needed later it should move to an EventBridge-scheduled ECS task. WINDOW_DAYS=7 is a hard-coded constant in extraction_health.py; the response exposes it under window.days so the consumer can render the actual window, but the API has no parameter to vary the window. Empty-specs three-shape match is duplicated in backfill.py and extraction_health.py — intentional to keep crawler-runtime imports out of the FastAPI request path; if a third consumer needs it, lift to a shared utility."

## Follow-ups

"Add Alembic-autogenerated index `(source, last_parsed_at)` and `(source, parse_status)` on crawled_pages if not already present (slice plan flagged this as a follow-up — verify via `\\d crawled_pages` in psql). Live-runtime backfill verification (`python -m app.crawlers.backfill --dry-run --limit 0` against the populated local DB) deferred to S13 final integration verification — auto-mode does not bring up Docker. Operator-driven dry-run is exhaustively covered by test_dry_run_makes_no_writes which patches at the import site."

## Files Created/Modified

- `backend/app/crawlers/backfill.py` — New CLI module: chunked/idempotent/resumable re-extraction over Part.specifications via rescrape_crawled_page_from_archive. argparse with --batch-size/--limit/--source/--resume/--dry-run/--max-failure-rate/--state-dir. Per-batch INFO log, per-batch SessionLocal, cursor checkpoint.
- `backend/tests/crawlers/test_backfill.py` — 9 tests: empty-specs filter, dry-run no-writes, idempotent second run, resume-from-cursor, above-threshold failure rate, --source restriction, 3 argparse rejection tests.
- `backend/app/api/endpoints/admin/extraction_health.py` — New admin sub-router. GET /api/admin/extraction-health returns ExtractionHealthResponse with compliance, coverage, failure_rate_7d, window. Dialect-aware JSON-extract helper inlined.
- `backend/tests/api/endpoints/test_admin_extraction_health.py` — 7 tests: 401 unauth, 403 non-admin, compliance block shape, coverage seeded counts, failure-rate window, old-failure exclusion, unknown-source skip, window metadata.
- `backend/app/main.py` — Imported extraction_health as admin_extraction_health (line 33); registered router at /admin/extraction-health prefix with admin tags (line 350).
- `.gitignore` — Added .crawler-state/ as runtime cache directory (cursor file lives here, not committed).
