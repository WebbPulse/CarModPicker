---
id: T02
parent: S04
milestone: M002
key_files:
  - backend/app/api/endpoints/admin/extraction_health.py
  - backend/app/main.py
  - backend/tests/api/endpoints/test_admin_extraction_health.py
  - .gsd/DECISIONS.md
key_decisions:
  - Failure-rate signal sourced from crawled_pages.parse_status (DB) over rolling 7-day window, not CloudWatch EMF (D009 — slice plan said D008 but that ID was taken; rationale unchanged).
  - Dialect-aware JSON-extract helper lives inside extraction_health.py rather than as a shared utility — keeps the slice scope tight; fan-out can come later if a second consumer materializes.
  - Empty-specs detection inlines the three-shape match (SQL NULL / JSON 'null' / '{}') from MEM041 instead of importing _empty_specs_filter from app.crawlers.backfill — keeps the FastAPI request path free of crawler-runtime imports.
  - Tests resolve adapter slugs dynamically via _classify_tier(ADAPTER_REGISTRY[slug]) rather than hard-coding 'a90shop' — survives future adapter renames.
duration: 
verification_result: passed
completed_at: 2026-04-25T05:36:46.212Z
blocker_discovered: false
---

# T02: Add GET /api/admin/extraction-health: DB-derived compliance + per-tier coverage gradient + 7d failure-rate (no CloudWatch dep)

**Add GET /api/admin/extraction-health: DB-derived compliance + per-tier coverage gradient + 7d failure-rate (no CloudWatch dep)**

## What Happened

Stood up `backend/app/api/endpoints/admin/extraction_health.py` as a new admin sub-router with a single GET endpoint that returns a structured ExtractionHealthResponse: compliance counts (108/108 per MEM037, with per-tier `<n>/<n>` strings to match the audit stdout shape), per-tier coverage gradient (parts_with_specs / parts_total + per-field presence ratio across UNIVERSAL_FIELD_NAMES), and a 7-day failure-rate block grouped by source. All three sections derive from authoritative DB state — no CloudWatch round-trip, no shell-out to the audit script — by reusing `_classify_tier`, `_is_compliant`, and `ADAPTER_REGISTRY` directly.

Coverage uses a dialect-aware JSON-extract helper `_field_present_count` that branches on `db.bind.dialect.name`: SQLite path uses `func.json_extract(spec, '$.<field>').isnot(None)`, PostgreSQL path uses the `Part.specifications[field].isnot(None)` subscript accessor. Field names come from the immutable `UNIVERSAL_FIELD_NAMES` frozenset (never user input), but values flow through SQLAlchemy parameterization as defense in depth. The empty-specs match handles the three on-disk shapes documented in MEM041 (SQL NULL, JSON 'null' literal, JSON '{}') so coverage doesn't miscount JSON-null parts as having specs.

Failure-rate groups `crawled_pages` by source for parsed/failed counts where `last_parsed_at >= now - 7d`, drops rows whose source isn't in `ADAPTER_REGISTRY` (defensive — a removed adapter shouldn't surface), and computes `failed/(failed+parsed)` defensively (0.0 when denominator is zero). Window is exposed in the response under `window` (days=7, since=ISO8601) so the frontend doesn't have to assume.

Wired into main.py with `extraction_health as admin_extraction_health` in the admin import block and a `register_endpoint(..., prefix='/admin/extraction-health', ...)` call alongside the other admin sub-routers. Captured the EMF-vs-DB choice as D009 via `gsd_save_decision` (the slice plan called for D008, but D008 was already taken — D009 is the next free ID).

Tests cover the 7 cases the plan called out: unauthorized → 401, non-admin → 403, compliance block shape with `<n>/<n>` per-tier strings, coverage seeding (1 part + 1 crawled_page → weight_grams presence ratio ≥ 1/parts_total), failure-rate window with rate=0.5 from 1 failed + 1 parsed, old failure (now-30d) excluded from window, unknown adapter source skipped, and window metadata round-trip via `datetime.fromisoformat`. Tests pick adapter slugs dynamically by tier rather than hard-coding 'a90shop' so a future adapter rename doesn't break the suite.

## Verification

Ran the slice-plan verification command: `TESTING=true pytest backend/tests/api/endpoints/test_admin_extraction_health.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend -q --no-cov`. Result: 11 passed in 8.63s (7 new extraction-health tests + 4 existing compliance-audit tests, no regressions). Each new test exercises a distinct contract bucket from the plan's Negative Tests + happy-path matrix.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest backend/tests/api/endpoints/test_admin_extraction_health.py backend/tests/crawlers/test_compliance_audit.py -n auto --rootdir=backend -q --no-cov` | 0 | ✅ pass | 8630ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/app/api/endpoints/admin/extraction_health.py`
- `backend/app/main.py`
- `backend/tests/api/endpoints/test_admin_extraction_health.py`
- `.gsd/DECISIONS.md`
