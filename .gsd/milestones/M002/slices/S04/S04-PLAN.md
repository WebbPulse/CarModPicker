# S04: Re-extraction backfill + admin extraction-health API

**Goal:** Ship a chunked / idempotent / resumable re-extraction backfill CLI that repopulates `Part.specifications` for existing parts using the S02 universal extractor + S01 SpecRegistry validation, and a `GET /api/admin/extraction-health` endpoint that returns binary compliance (108/108 from compliance_audit, NOT 111 — see MEM037), per-tier coverage gradient (T0/T1/T2 field-presence over `Part.specifications`), and per-adapter `extraction_failure_rate` over a rolling 7-day window — all derivable from DB state with no CloudWatch round-trip.
**Demo:** Kick off the backfill: python -m app.crawlers.backfill --batch-size 100. Job is idempotent (re-running on the same parts produces no duplicates), resumable (Ctrl-C and resume picks up where it left off), and logs progress with per-batch counts. Hit GET /api/admin/extraction-health — JSON returns compliance: 111/111, per-tier coverage gradient, per-adapter failure-rate over 7d window.

## Must-Haves

- Run `TESTING=true python -m app.crawlers.backfill --dry-run --limit 0` from `backend/` — exit 0, prints batch counts and the count of parts-with-empty-specifications it would process. Re-run the same command twice without `--dry-run` against the local SQLite test DB (or a sample-fixture loop) — second run reports 0 parts updated (idempotent). Hit `GET /api/admin/extraction-health` as an admin via `pytest tests/api/endpoints/test_admin_extraction_health.py` — JSON returns `{"compliance": {"compliant": 108, "total": 108, "per_tier": {"http": "83/83", "tls": "15/15", "browser": "10/10"}}, "coverage": {"per_tier": {...}}, "failure_rate_7d": [{"adapter": "...", "failed": N, "parsed": N, "rate": 0.xx, "tier": "..."}, ...], "window": {"days": 7, "since": "..."}}`. The full crawler test suite stays green: `pytest backend/tests/crawlers/ -n auto --rootdir=backend --no-cov -q` reports zero new failures.
- THREAT SURFACE — the admin endpoint is the only new attack surface in this slice. Abuse: attacker crafts a `Part.specifications` JSON with malicious keys hoping to inject SQL via the field-presence count helper. Mitigated by: dialect-aware helper uses parameterized queries (SQLAlchemy `text(...).bindparams(...)` or ORM expressions), and field names are sourced from the immutable `UNIVERSAL_FIELD_NAMES` frozenset (not request input). Data exposure: response includes adapter slugs and parts-counts — operationally sensitive but not PII; gated on `Depends(get_current_admin_user)`. Input trust: NONE — endpoint takes no body or query params.
- REQUIREMENT IMPACT — Requirements touched: R005 (backfill — primary), R006 (admin extraction-health — primary), R018 (crawler test coverage extended — supporting). Re-verify: existing `archive_rescrape` integration tests must still pass since backfill reuses `rescrape_crawled_page_from_archive`; existing admin endpoint auth coverage in `test_admin_auth_coverage.py` must include the new `/admin/extraction-health` route (audit auto-discovers from registered routers). Decisions revisited: D004 (price-history aggregation) — none, separate domain; D007 (category bridge) — confirmed: backfill exercises the bridge by virtue of reusing ingest_payload; introduces a new D008 (admin extraction-health failure-rate sourced from DB, not EMF).

## Proof Level

- This slice proves: - This slice proves: integration
- Real runtime required: yes — CLI must actually run against the DB; FastAPI test client must hit the live endpoint
- Human/UAT required: no — both pieces are mechanically verifiable

## Integration Closure

- Upstream surfaces consumed: `app/crawlers/archive_rescrape.py::rescrape_crawled_page_from_archive` (per-page parse+ingest, already wires apply_universal_extraction per MEM026), `app/crawlers/compliance_audit.py::ADAPTER_REGISTRY + _classify_tier + _is_compliant` (T0/T1/T2 totals from live ADAPTER_REGISTRY, MEM037), `app/crawlers/adapters::ADAPTER_REGISTRY` (FETCHER_TIER lookup), `app/crawlers/adapters/base.py::UNIVERSAL_FIELD_NAMES` (frozenset for per-field coverage), `app/api/models/crawled_page.py::CrawledPage` (parse_status + source + last_parsed_at + part_id), `app/api/models/part.py::Part.specifications`, `app/api/dependencies/auth::get_current_admin_user`, `app/api/utils/endpoint_registry::EndpointRegistry`
- New wiring introduced in this slice: new `app/crawlers/backfill.py` CLI module (entry `python -m app.crawlers.backfill`); new `app/api/endpoints/admin/extraction_health.py` sub-router registered in `app/main.py` under `/admin/extraction-health`
- What remains before the milestone is truly usable end-to-end: S05–S12 frontend + price-history work; this slice opens the operational seam only — the admin UI in S11 will consume the JSON returned here

## Verification

- Runtime signals: structured INFO log per batch (`backfill: batch=N start_id=... processed=N updated=N skipped=N elapsed=Ns`); WARN log on per-part ingest failure carries adapter_name + url + error class; admin endpoint logs request count via standard FastAPI access log; existing `ExtractionFailureRate` EMF metric continues to fire from `ingest_payload` during backfill runs (env-gated, no behavior change)
- Inspection surfaces: CLI prints final summary to stdout (batches, parts_processed, parts_updated, skipped_no_html, ingest_failed); admin endpoint returns full structured JSON; backfill writes a `backfill_cursor.json` checkpoint file under `backend/.crawler-state/` after each batch so a Ctrl-C can resume
- Failure visibility: per-batch progress emits a log line; per-failure rows surface in the admin endpoint's `failure_rate_7d` block via `crawled_pages.parse_status='failed'` (authoritative DB state, no CloudWatch dependency); the CLI exit code is non-zero when more than `--max-failure-rate` (default 0.5) of the run failed
- Redaction constraints: none — no secrets touched; admin endpoint requires `get_current_admin_user`

## Tasks

- [x] **T01: Add `app/crawlers/backfill.py` chunked/idempotent/resumable re-extraction CLI** `est:3h`
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
  - Files: `backend/app/crawlers/backfill.py`, `backend/tests/crawlers/test_backfill.py`
  - Verify: TESTING=true pytest backend/tests/crawlers/test_backfill.py -n auto --rootdir=backend -q --no-cov

- [ ] **T02: Add `GET /api/admin/extraction-health` endpoint backed by compliance + DB-derived coverage and failure-rate** `est:3h`
  Stand up `backend/app/api/endpoints/admin/extraction_health.py` as a new admin sub-router registered under `/admin/extraction-health` in `backend/app/main.py`. The endpoint returns a JSON document with three sections — compliance, coverage, failure-rate — all derivable from authoritative DB state (NOT CloudWatch).

Response shape (Pydantic schema lives in this file as `ExtractionHealthResponse`):

```json
{
  "compliance": {
    "compliant": 108,
    "total": 108,
    "per_tier": {"http": "83/83", "tls": "15/15", "browser": "10/10"}
  },
  "coverage": {
    "per_tier": {
      "http": {"parts_with_specs": 1234, "parts_total": 5678, "per_field": {"weight_grams": 0.42, "material": 0.31, "finish": 0.18, "warranty_days": 0.05, "fitment_notes": 0.61}},
      "tls": {...},
      "browser": {...}
    }
  },
  "failure_rate_7d": [
    {"adapter": "a90shop", "failed": 12, "parsed": 188, "rate": 0.06, "tier": "http"},
    ...
  ],
  "window": {"days": 7, "since": "2026-04-17T22:14:08+00:00"}
}
```

Implementation plan (one file, ~150 lines):

1. **Compliance** — import `ADAPTER_REGISTRY`, `_classify_tier`, `_is_compliant` from `app.crawlers.compliance_audit` and count directly. Don't shell out, don't capture stdout, don't fork the logic. The exact same per-tier counting that `audit()` does inline. Per-tier output renders as `"<n_compliant>/<n_total>"` strings to match the audit's stdout shape.

2. **Coverage** — for each tier (http/tls/browser), compute the set of adapter slugs from `{slug for slug, cls in ADAPTER_REGISTRY.items() if _classify_tier(cls) == tier_key}`. Then query parts joined to crawled_pages via `crawled_pages.part_id == parts.id`, filtered by `crawled_pages.source.in_(<tier_slugs>)`. For each tier:
   - `parts_total` = count of distinct part_ids in that join
   - `parts_with_specs` = same count but with `Part.specifications.isnot(None)` and dialect-aware non-empty check
   - `per_field[field]` = ratio of parts whose `specifications` JSON contains the field key, computed via dialect-aware `_field_present_count(db, field_name, tier_adapter_names)`. Iterate over `UNIVERSAL_FIELD_NAMES` from `app.crawlers.adapters.base`.

   Dialect helper: `def _field_present_count(db, field_name, tier_sources): if db.bind.dialect.name == 'sqlite': use func.json_extract(Part.specifications, f'$.{field_name}').isnot(None); elif db.bind.dialect.name == 'postgresql': use Part.specifications[field_name].isnot(None); else: raise NotImplementedError`. SQLite path is exercised by the test suite; postgres path runs in prod. NEVER interpolate `field_name` from request input — it comes from the immutable `UNIVERSAL_FIELD_NAMES` frozenset, so SQL injection isn't reachable, but use parameterized expressions anyway as defense in depth.

3. **Failure rate** — query `crawled_pages` grouped by `source` for `parse_status='failed'` count and `parse_status='parsed'` count over the last 7 days (`last_parsed_at >= now - 7d`). Skip rows whose `last_parsed_at IS NULL` (never parsed = not in window). Join with `ADAPTER_REGISTRY` to attach the tier and skip unknown sources (defensive — a `crawled_pages.source` value referring to a removed adapter shouldn't appear in the response). Compute `rate = failed / (failed + parsed)` defensively (`0.0` if denominator is zero). The 7-day window is a hard-coded constant `WINDOW_DAYS = 7` at module top; expose it in the response under `window` so the frontend doesn't have to assume.

Why DB-derived (not EMF-derived): the EMF metric is fire-and-forget and gated to staging/production (per `cloudwatch_emf.py` D-20). Reading it back requires CloudWatch GetMetricData IAM + a network round-trip. `crawled_pages.parse_status` is the same authoritative signal — `archive_rescrape` and `runner` both write `parse_status='failed'` when ingest fails, so the count is exact. Captured as a new decision (D008) — append to `.gsd/DECISIONS.md` after planning via `gsd_decision_save`.

Auth: gate on `Depends(get_current_admin_user)` exactly like `admin/crawlers.py::list_crawlers`. Returns 200 with the body, 401 unauth, 403 non-admin.

Wiring in `main.py`:
- Add `extraction_health as admin_extraction_health` to the `from .api.endpoints.admin import (...)` block at line 30.
- Add a new `endpoint_registry.register_endpoint(admin_extraction_health.router, prefix="/admin/extraction-health", tags=["admin"], description="Admin extraction health (compliance, coverage, failure-rate)")` block alongside the other admin sub-routers (around line 342).

FAILURE MODES (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Postgres / SQLite (coverage + failure-rate queries) | propagate as 500 (FastAPI default); errors are infra, not user-recoverable | n/a (in-process) | n/a |
| `ADAPTER_REGISTRY` (import-time) | already validated by `RetailerCrawlerAdapter.__init_subclass__`; if it's wrong the app would have failed to start | n/a | n/a |
| `get_current_admin_user` | 401/403 returned by dependency | n/a | n/a |

LOAD PROFILE (Q6):
- Shared resources: read-only DB queries on `parts` + `crawled_pages` tables; one Postgres connection per request via standard FastAPI session dep
- Per-operation cost: ~6 SQL queries per request (3 tiers × (parts_total + parts_with_specs) + 1 per universal field per tier coverage + 1 grouped query for failure-rate). For a 25k-parts catalog with `(source, last_parsed_at)` and `(source, parse_status)` indexes already in place, ~50-100ms total. No N+1 — each per-field query is a single COUNT.
- 10x breakpoint: this endpoint is admin-only and called manually, expected QPS << 1. The 10x scenario is more parts (250k) — still inside budget given indexed queries. Add the index `(source, last_parsed_at)` to `crawled_pages` if not present — verify via `\d crawled_pages` in psql; if missing, add an Alembic autogenerate migration as a follow-up (NOT part of this task, but flag it in the task's Done-when notes).

NEGATIVE TESTS (Q7):
- Malformed inputs: endpoint takes no body or query params — nothing to malform
- Error paths: missing auth → 401; non-admin auth → 403
- Boundary conditions: empty `crawled_pages` table → `failure_rate_7d=[]`, coverage all-zero, compliance still 108/108; `crawled_pages` with all-NULL `last_parsed_at` → `failure_rate_7d=[]`; row with `source` not in `ADAPTER_REGISTRY` → silently skipped (defensive, captured in test)

Write tests in `backend/tests/api/endpoints/test_admin_extraction_health.py`:
- `test_extraction_health_unauthorized` — no auth → 401.
- `test_extraction_health_forbidden_non_admin` — regular user → 403.
- `test_extraction_health_returns_compliance_block` — admin → 200; assert `data['compliance']['compliant'] == data['compliance']['total']`; assert `'http'`, `'tls'`, `'browser'` keys present in `per_tier` and each value is `"<n>/<n>"`-shaped.
- `test_extraction_health_coverage_counts_specifications_field` — seed 1 `Part` with `specifications={'weight_grams': 1.0, 'weight_grams_confidence': 'high'}` linked via `crawled_pages.part_id` to a `crawled_pages` row whose source is one of the registered T0 adapter names; assert the `coverage.per_tier.http.parts_with_specs >= 1` and `per_field.weight_grams >= 1/parts_total`.
- `test_extraction_health_failure_rate_window` — seed 2 `crawled_pages` with `source='a90shop'` (or any registered slug), one `parse_status='failed'` and `last_parsed_at=now`, one `parse_status='parsed'` and `last_parsed_at=now`; assert `failure_rate_7d` contains an entry with `adapter='a90shop'`, `failed=1`, `parsed=1`, `rate=0.5`.
- `test_extraction_health_excludes_old_failures` — seed a `crawled_pages` row with `parse_status='failed'` and `last_parsed_at=now-30d`; assert it does NOT appear in `failure_rate_7d` (or appears with failed=0).
- `test_extraction_health_skips_unknown_sources` — seed a `crawled_pages` row with `source='not_a_real_adapter'`; assert no entry appears for that source in `failure_rate_7d`.
- `test_extraction_health_returns_window_metadata` — assert `data['window']['days'] == 7` and `since` is an ISO8601 string.

Follow the test pattern from `backend/tests/api/endpoints/test_admin.py::TestAdminRescrapeArchives` — `create_and_login_admin_user` + `create_and_login_user` helpers can be imported from `tests.api.endpoints.test_admin` (the file is already there in the test tree).

Must use a JSON-extract helper that detects dialect (`db.bind.dialect.name == 'sqlite'` vs `'postgresql'`) so tests pass under SQLite in-memory and prod uses Postgres `->` accessor. Capture this branch as part of the implementation, not a follow-up. The helper lives inside `extraction_health.py` (no separate utility file — keeps the slice scope tight).

After implementation, append D008 to `.gsd/DECISIONS.md` via `gsd_decision_save`: 'Admin extraction-health failure-rate sourced from `crawled_pages.parse_status` (DB), not CloudWatch EMF — authoritative state, no IAM/network dependency, works in dev + tests, single SQL round-trip per request. Revisable: yes — if multi-region read replicas land we may shift to a CloudWatch read for cross-region aggregation.'
  - Files: `backend/app/api/endpoints/admin/extraction_health.py`, `backend/app/main.py`, `backend/tests/api/endpoints/test_admin_extraction_health.py`, `.gsd/DECISIONS.md`
  - Verify: TESTING=true pytest backend/tests/api/endpoints/test_admin_extraction_health.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend -q --no-cov

## Files Likely Touched

- backend/app/crawlers/backfill.py
- backend/tests/crawlers/test_backfill.py
- backend/app/api/endpoints/admin/extraction_health.py
- backend/app/main.py
- backend/tests/api/endpoints/test_admin_extraction_health.py
- .gsd/DECISIONS.md
