---
phase: 01-safety-nets-ci-hardening
plan: 05
subsystem: testing
tags: [openapi, snapshot, fastapi, characterization, pytest]

# Dependency graph
requires:
  - phase: 01-safety-nets-ci-hardening plan 04
    provides: coverage gates live — new test file adds coverage, not removes it
provides:
  - SAFE-05: OpenAPI schema snapshot test pinning all 158 registered routes
  - backend/tests/fixtures/openapi_snapshot.json (466 KB, formatted JSON baseline)
  - backend/tests/test_openapi_snapshot.py (function-scope app import, string equality assertion)
affects:
  - 01-06 (auth characterization): adding new routes or middleware will cause snapshot drift — plan accordingly
  - 01-07 (crawler adapter characterization): same note — parse_product_page tests don't register routes, so no drift expected
  - any future plan that changes endpoint signatures, adds routers, or modifies Pydantic schemas

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OpenAPI snapshot via app.openapi() + json.dumps(indent=2, sort_keys=True) — formatted JSON diff IS the review artifact"
    - "Pitfall 8 compliance: function-scope import of app so conftest.py env-var setup runs first"
    - "Snapshot generation: TESTING=true ENABLE_RATE_LIMITING=false only — no extra overrides (conftest imports app at module scope using Settings defaults)"

key-files:
  created:
    - backend/tests/test_openapi_snapshot.py
    - backend/tests/fixtures/openapi_snapshot.json
    - backend/tests/fixtures/.gitkeep
  modified: []

key-decisions:
  - "Snapshot regeneration command uses sys.stdout.write (not print) to avoid trailing newline mismatch between generation and json.dumps comparison"
  - "Minimal env vars (TESTING=true ENABLE_RATE_LIMITING=false) only — PROJECT_NAME and other settings must use defaults because conftest.py imports app at module scope before test env vars can override Settings"
  - "D-27 enforced: formatted JSON (not hash) so PR diff on openapi_snapshot.json is the human-readable schema-change review artifact"

patterns-established:
  - "Pitfall 8: always import app at function scope in test files that must not influence schema generation before conftest env setup"
  - "Snapshot files live under backend/tests/fixtures/ with a .gitkeep directory marker"

requirements-completed:
  - SAFE-05

# Metrics
duration: 12min
completed: 2026-04-22
---

# Phase 01 Plan 05: OpenAPI Schema Snapshot Test Summary

**SAFE-05: committed 466 KB formatted-JSON OpenAPI snapshot (158 paths) with function-scope app import test that detects any route/schema drift**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-04-22T08:18:00Z
- **Completed:** 2026-04-22T08:29:59Z
- **Tasks:** 2
- **Files modified:** 3 (created)

## Accomplishments
- Created `backend/tests/fixtures/openapi_snapshot.json` — 466,651 bytes, 158 paths, formatted with `indent=2, sort_keys=True`, no trailing newline
- Created `backend/tests/test_openapi_snapshot.py` — imports `app` at function scope (Pitfall 8 compliant), asserts string equality against committed snapshot, failure message contains verbatim regeneration command
- Created `backend/tests/fixtures/.gitkeep` — directory marker so git tracks the fixtures dir if snapshot is temporarily deleted during regeneration
- Full backend suite: 2148 passed, 1 skipped — coverage floor maintained

## Task Commits

1. **Task 1: Create fixtures directory + generate initial openapi_snapshot.json** - `4e72a1b` (feat)
2. **Task 2: Write backend/tests/test_openapi_snapshot.py** - `d32462e` (feat)

## Files Created/Modified
- `backend/tests/test_openapi_snapshot.py` - SAFE-05 snapshot test; function-scope `from app.main import app` at line 39
- `backend/tests/fixtures/openapi_snapshot.json` - 466 KB baseline snapshot (158 paths, sorted keys, 2-space indent)
- `backend/tests/fixtures/.gitkeep` - directory marker

## Regeneration Command (verbatim — for Plan 06/07 and beyond)

```bash
cd backend
TESTING=true ENABLE_RATE_LIMITING=false \
  python -c "import json, sys; from app.main import app; sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True))" \
  > tests/fixtures/openapi_snapshot.json
```

**Critical:** Use ONLY those two env vars. conftest.py imports `app` at module scope, so Settings is already initialized with defaults (e.g., `PROJECT_NAME="CarModPicker"`) before any test-specific env overrides could take effect. Extra vars like `PROJECT_NAME="CarModPicker API"` cause title drift and make the test fail.

## Snapshot Metrics (for Plan 06/07 planning)

| Metric | Value |
|--------|-------|
| File size | 466,651 bytes (~456 KB) |
| Path count | 158 |
| Top-level keys (sorted) | components, info, openapi, paths |
| Serialization | json.dumps(indent=2, sort_keys=True) |

## Decisions Made
- Used `sys.stdout.write` instead of `print` in regeneration command to avoid trailing newline mismatch (json.dumps produces no trailing newline; `print` adds one)
- Minimal env vars only — discovered via debugging that `PROJECT_NAME` override conflicts with Settings already initialized by conftest.py's module-scope `from app.main import app as fastapi_app`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected snapshot generation command to avoid env var conflict with conftest.py**
- **Found during:** Task 2 (running `pytest -n auto tests/test_openapi_snapshot.py`)
- **Issue:** Plan's generation command used `PROJECT_NAME="CarModPicker API"`, but conftest.py imports `app` at module scope (line 28: `from app.main import app as fastapi_app`), which initializes Settings with defaults (`PROJECT_NAME="CarModPicker"`) before any test-level env overrides. This caused a title mismatch in the snapshot at character 152076.
- **Fix:** Regenerated snapshot with minimal env vars (`TESTING=true ENABLE_RATE_LIMITING=false` only). Updated both the module docstring and failure message in `test_openapi_snapshot.py` to document the correct command.
- **Fix also:** Switched from `print(...)` to `sys.stdout.write(...)` in the regeneration command to avoid trailing `\n` that `print` appends but `json.dumps` does not produce.
- **Files modified:** `backend/tests/test_openapi_snapshot.py`, `backend/tests/fixtures/openapi_snapshot.json`
- **Verification:** `pytest -n auto tests/test_openapi_snapshot.py --no-cov` → 1 passed
- **Committed in:** `d32462e` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential for correctness — plan's command would have generated a snapshot that always diverges from what the test sees at CI run time. No scope creep.

## Issues Encountered
- Conftest.py imports app at module scope (`from app.main import app as fastapi_app` on line 28), which runs Settings initialization before any test-level env vars. This is an existing pattern in the test infrastructure; the snapshot generation must match it.

## Handoff Note for Plans 06 and 07

- **Route registration:** Any new characterization test that registers new routes (e.g., adds a router to the FastAPI app) WILL cause `openapi_snapshot.json` to diverge. Run the regeneration command above and commit the updated snapshot alongside the new router code.
- **Most characterization tests don't register routes** — they call service layer or adapter methods directly. VCR cassette tests (SAFE-06) and parse_product_page tests (SAFE-07) are read-only against the app schema, so no snapshot churn is expected from those plans.
- **Middleware injection:** Adding new middleware that adds response headers or changes OpenAPI schema generation would also cause drift. Check the snapshot test after any middleware change.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- SAFE-05 complete; snapshot baseline committed; test is green in CI
- Plans 06 and 07 (auth + crawler characterization) can proceed without touching the snapshot as long as they don't register new routes

## Threat Flags
None — no new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries introduced. The snapshot itself is read-only in the test and contains only the same schema FastAPI already serves publicly at `/api/openapi.json`.

## Self-Check

- [x] `backend/tests/test_openapi_snapshot.py` exists: FOUND
- [x] `backend/tests/fixtures/openapi_snapshot.json` exists: FOUND
- [x] `backend/tests/fixtures/.gitkeep` exists: FOUND
- [x] Commit `4e72a1b` exists (Task 1)
- [x] Commit `d32462e` exists (Task 2)
- [x] `pytest -n auto tests/test_openapi_snapshot.py --no-cov`: 1 passed
- [x] `pytest -n auto -x`: 2148 passed, 1 skipped
- [x] `pyright tests/test_openapi_snapshot.py`: 0 errors
- [x] `black --check tests/test_openapi_snapshot.py`: unchanged

## Self-Check: PASSED
