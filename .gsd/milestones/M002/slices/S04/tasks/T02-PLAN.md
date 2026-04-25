---
estimated_steps: 62
estimated_files: 4
skills_used: []
---

# T02: Add `GET /api/admin/extraction-health` endpoint backed by compliance + DB-derived coverage and failure-rate

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

## Inputs

- ``backend/app/crawlers/compliance_audit.py` — `ADAPTER_REGISTRY`, `_classify_tier`, `_is_compliant` for compliance counts (108/108 per MEM037)`
- ``backend/app/crawlers/adapters/base.py` — `UNIVERSAL_FIELD_NAMES` frozenset for the per-field coverage heatmap`
- ``backend/app/crawlers/adapters/__init__.py` — `ADAPTER_REGISTRY` mapping (adapter_name → class) for tier classification`
- ``backend/app/api/models/crawled_page.py` — `CrawledPage.parse_status`, `.source`, `.last_parsed_at`, `.part_id` for failure-rate window queries`
- ``backend/app/api/models/part.py` — `Part.specifications` JSON column for coverage computation`
- ``backend/app/api/dependencies/auth.py` — `get_current_admin_user` for the route gate`
- ``backend/app/api/utils/endpoint_registry.py` — `EndpointRegistry.register_endpoint` for the main.py wiring`
- ``backend/app/api/endpoints/admin/crawlers.py` — pattern reference: APIRouter() + Depends(get_current_admin_user) + standard_responses`
- ``backend/tests/api/endpoints/test_admin.py` — pattern reference: `create_and_login_admin_user` + `create_and_login_user` helpers`

## Expected Output

- ``backend/app/api/endpoints/admin/extraction_health.py` — new admin sub-router with `GET /` endpoint returning the full ExtractionHealthResponse schema; ~150 lines including Pydantic models, dialect-aware JSON-extract helper `_field_present_count`, and three derivation functions (`_compute_compliance`, `_compute_coverage`, `_compute_failure_rate_7d`)`
- ``backend/app/main.py` — import added to `from .api.endpoints.admin import (...)` block (line ~30); new `register_endpoint` call alongside other admin sub-routers (around line 342) under `/admin/extraction-health``
- ``backend/tests/api/endpoints/test_admin_extraction_health.py` — pytest module with the 7 tests listed in description; reuses `create_and_login_admin_user`/`create_and_login_user` from `tests.api.endpoints.test_admin``
- ``.gsd/DECISIONS.md` — new D008 row appended via `gsd_decision_save`: 'Admin extraction-health failure-rate sourced from crawled_pages.parse_status (DB), not CloudWatch EMF — authoritative state, no IAM/network dependency, works in dev'`

## Verification

TESTING=true pytest backend/tests/api/endpoints/test_admin_extraction_health.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend -q --no-cov

## Observability Impact

- Signals added/changed: standard FastAPI access log per request; no new metrics emitted (the endpoint is read-only); the existing `ExtractionFailureRate` EMF metric remains the production stream — this endpoint just exposes the same underlying signal via the DB path so dev + tests see it too
- How a future agent inspects this: `curl -H 'Authorization: Bearer <admin-token>' http://localhost:8000/api/admin/extraction-health | jq` returns the live JSON; for shell debugging, `select source, parse_status, count(*) from crawled_pages where last_parsed_at >= now() - interval '7 days' group by source, parse_status` reproduces the failure-rate computation
- Failure state exposed: when an adapter's failure rate is high, it surfaces as a row in `failure_rate_7d` with `rate > 0`; when an adapter's coverage is low (most parts have no `specifications`), it surfaces in `coverage.per_tier.<tier>.per_field` as a near-zero presence ratio across the 5 universal fields
