---
phase: 03-non-breaking-internal-improvements
plan: 05
subsystem: backend/app/api + backend/tests
tags: [quality, regression-guards, pydantic, on-event, logger-migration, ci, mechanical-sweep]
requires:
  - "backend/pytest.ini --disable-warnings (Pitfall QU-01 — drove the catch_warnings approach)"
  - "backend/tests/fixtures/openapi_snapshot.json (the A6 drift baseline)"
  - "backend/app/core/logging.py::get_logger (D-36 — preserved through Phase 5)"
provides:
  - "CI guard: grep regression for Pydantic v1 patterns (@validator, @root_validator, class Config, .parse_obj, .dict())"
  - "CI guard: Pydantic v2 round-trip under warnings.catch_warnings() with PydanticDeprecatedSince20 as error"
  - "CI guard: grep regression for @*.on_event( (lifespan is the one true pattern)"
  - "CI guard: grep regression for Depends(get_logger) (D-37)"
  - "Clean module-level-logger convention across 10 files (ready for D-35 Phase 5 inheritance)"
affects:
  - "Every future PR that touches backend/app/**/*.py (the guards run on every CI invocation)"
  - "Phase 5 auth.py split: the module-level logger pattern is now canonical to copy into each new submodule"
tech-stack:
  added: []
  patterns:
    - "Module-level `logger = logging.getLogger(__name__)` as the canonical endpoint/util logger idiom"
    - "Grep-based CI regression guards via Path.rglob + regex scan (analog: test_openapi_snapshot.py)"
    - "Pydantic v2 deprecation-as-error via warnings.catch_warnings() (works around pytest.ini --disable-warnings)"
key-files:
  created:
    - backend/tests/test_pydantic_v1_regression.py
    - backend/tests/test_on_event_regression.py
    - backend/tests/test_logger_migration_regression.py
  modified:
    - backend/app/api/endpoints/auth.py
    - backend/app/api/endpoints/users.py
    - backend/app/api/endpoints/votes.py
    - backend/app/api/endpoints/reports.py
    - backend/app/api/endpoints/bug_reports.py
    - backend/app/api/utils/base_endpoint_router.py
    - backend/app/api/utils/base_vote_router.py
    - backend/app/api/utils/base_report_router.py
    - backend/app/api/utils/common_patterns.py
    - backend/app/api/utils/admin_endpoint_patterns.py
decisions:
  - "common_patterns.py dead-code helpers (get_standard_endpoint_dependencies, get_common_dependencies, get_admin_dependencies): removed the `logger` dict entry rather than deleting the helpers (verified zero callers repo-wide, but preserved the factories for minimal blast radius). Docstrings updated to direct future callers to the module-level logger."
  - "OpenAPI snapshot unchanged — A6 verification confirmed: FastAPI excludes `Depends()` params from the emitted schema, so removing 68 `logger: Depends(get_logger)` parameters produced zero schema drift."
  - "get_logger export retained in backend/app/core/logging.py per D-36 — removal deferred to late Phase 5 / early Phase 6. The regression guard asserts absence of the CALL SITE pattern, not the export."
metrics:
  duration_minutes: 18
  completed_date: "2026-04-22"
  tasks_completed: 2
  files_changed: 13
---

# Phase 03 Plan 05: Regression Guards + Logger Migration Sweep Summary

**One-liner:** Landed three grep-based CI regression guards (Pydantic v1 patterns, `@app.on_event`, `Depends(get_logger)`) plus a Pydantic v2 schema round-trip under `warnings.catch_warnings()`, then executed the mechanical 68-site `Depends(get_logger)` → module-level `logger = logging.getLogger(__name__)` sweep across 10 files with OpenAPI snapshot unchanged.

## What was built

### Task 1: Three regression-guard test files — commit `253eae8`

- `backend/tests/test_pydantic_v1_regression.py` (QUAL-02)
  - `test_no_forbidden_patterns_in_app`: walks `backend/app/**/*.py` via `Path.rglob`; fails on any non-comment line matching `@validator\b`, `@root_validator\b`, `^\s*class\s+Config\s*:`, `\.parse_obj\(`, or `\b\w+\.dict\(\)` (with an empty `DICT_ALLOWLIST` for future false positives).
  - `test_no_pydantic_v1_deprecation_warnings_on_roundtrip`: Pitfall QU-01 workaround — `backend/pytest.ini` has `--disable-warnings`, which makes CLI `-W error::DeprecationWarning` filters a no-op. The test installs the filter locally via `warnings.catch_warnings(): warnings.simplefilter("error", pydantic.PydanticDeprecatedSince20)` around a `UserRead.model_validate(...).model_dump()` round-trip.
  - **Payload required fields verified against `UserRead.model_fields`**: `id` (UUID), `username`, `email` (EmailStr), `disabled`, `email_verified`, `is_superuser`, `is_admin`, `subscription_tier`, `subscription_status`. Test uses `uuid4()` for `id` and synthetic strings for text fields — no real PII (see threat T-03-05-05).
- `backend/tests/test_on_event_regression.py` (QUAL-03)
  - Scans for `@\w+\.on_event\(`; fails if reintroduced (lifespan context manager at `main.py:70` is the canonical pattern).
- `backend/tests/test_logger_migration_regression.py` (QUAL-07 / D-37)
  - Scans for `Depends\(\s*get_logger\s*\)`; fails if reintroduced. Error message documents the canonical `logger = logging.getLogger(__name__)` fix to nudge committers toward the right replacement.

All three files follow the analog pattern from `test_openapi_snapshot.py` (Path.rglob + regex scan + file:line offender list).

On the baseline tree, `test_pydantic_v1_regression.py` and `test_on_event_regression.py` were GREEN (D-30 verified zero anti-patterns); `test_logger_migration_regression.py` was RED (68 sites present) — the RED state is Task 2's RED gate.

### Task 2: 68-site Depends(get_logger) sweep — commit `8db4297`

Mechanical transformation across 10 files per 03-CONTEXT §D-34:

**Before:**
```python
from app.core.logging import get_logger
...
async def handler(
    ...,
    logger: logging.Logger = Depends(get_logger),
):
    logger.info(...)
```

**After (matches canonical analogs `crawlers/runner.py:55` and `db/session.py:12`):**
```python
import logging
...

logger = logging.getLogger(__name__)
...

async def handler(...):
    logger.info(...)  # resolves via module closure
```

## Per-file Depends(get_logger) BEFORE / AFTER counts (target: 68 → 0)

| File                                               | Before | After |
| -------------------------------------------------- | -----: | ----: |
| `backend/app/api/endpoints/auth.py`                |     21 |     0 |
| `backend/app/api/endpoints/users.py`               |     11 |     0 |
| `backend/app/api/utils/base_endpoint_router.py`    |      8 |     0 |
| `backend/app/api/utils/base_report_router.py`      |      6 |     0 |
| `backend/app/api/endpoints/reports.py`             |      5 |     0 |
| `backend/app/api/utils/common_patterns.py`         |      4 |     0 |
| `backend/app/api/utils/base_vote_router.py`        |      4 |     0 |
| `backend/app/api/endpoints/bug_reports.py`         |      4 |     0 |
| `backend/app/api/utils/admin_endpoint_patterns.py` |      3 |     0 |
| `backend/app/api/endpoints/votes.py`               |      2 |     0 |
| **Total**                                          | **68** | **0** |

Each file also has:
- `from app.core.logging import get_logger` removed (verified via `grep -c` returns 0).
- `logger = logging.getLogger(__name__)` at module-top, after imports (verified via `grep -c "^logger = logging.getLogger(__name__)"` returns 1 per file).

## Special-case handling

### common_patterns.py — dead-code helper factories

Three helper functions in `backend/app/api/utils/common_patterns.py` returned dict literals containing `"logger": Depends(get_logger)`:

- `get_standard_endpoint_dependencies()` (line 111-115)
- `get_common_dependencies()` (line 568-578)
- `get_admin_dependencies()` (line 582-593)

Repo-wide search for callers returned zero hits (verified via `grep -rn "get_standard_endpoint_dependencies\|get_common_dependencies\|get_admin_dependencies" backend/`). They are dead code.

**Decision:** preserve the factories for minimal blast radius but remove the `"logger"` key from the returned dicts, with a docstring note directing any future caller to use the module-level logger pattern. Alternative (delete the helpers outright) had the same end-state but larger diff.

### common_patterns.py — get_standard_public_endpoint_dependencies (LIVE — 13+ callers)

This helper (`line 118-130` in new tree) is heavily used — `bug_reports.py`, `votes.py`, `build_list_parts.py`, `build_list_phases.py`, `reports.py`, etc. all do:

```python
deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies)
db = deps["db"]
logger = deps["logger"]
```

The helper previously took `logger: logging.Logger = Depends(get_logger)` as a parameter and forwarded it into the returned dict. After the sweep:

- Removed the `logger: logging.Logger = Depends(get_logger)` parameter.
- `return {"db": db, "logger": logger}` still references `logger` — but it now resolves to the module-level `logger = logging.getLogger(__name__)` in `common_patterns.py` (semantically equivalent for every caller — they all use `deps["logger"]` for generic request-context logging, not for per-endpoint-module attribution).

Callers' behavior is preserved: `deps["logger"]` returns a `logging.Logger` instance; `RequestContextFilter` continues to decorate LogRecords with `request_id`/`user_id` regardless of which module's `__name__` the logger was named with.

### base_endpoint_router.py — Pitfall QU-07 (closure-scoped nested defs)

Per 03-RESEARCH Pitfall QU-07, eight of the 68 sites in `base_endpoint_router.py` were `Depends(get_logger)` inside nested function definitions declared within `__init__`. Verified post-sweep:

- The `logger` name in those nested functions now resolves to the module-level `logger = logging.getLogger(__name__)` via closure.
- Downstream service calls like `self.service.count_all(db=db, logger=logger)` still work (the `logger` name binds at the same scope; service kwargs unchanged).
- No regression in any test.

## DICT_ALLOWLIST entries added

**None.** `DICT_PATTERN` in `test_pydantic_v1_regression.py` returned zero matches on the current tree — no `foo.dict()` calls were found anywhere in `backend/app/**/*.py` that triggered the pattern. The allowlist is the empty set; future entries must include a rationale comment.

## OpenAPI snapshot state

**Unchanged.** A6 verified: `pytest tests/test_openapi_snapshot.py` passed GREEN after the sweep without regenerating `backend/tests/fixtures/openapi_snapshot.json`. FastAPI correctly excludes `Depends()` params from the emitted OpenAPI schema, so removing 68 `logger: Depends(get_logger)` parameters produced zero route / schema drift.

No snapshot regeneration required. No SAFE-05 workflow invoked.

## D-36 confirmation: get_logger export preserved

`grep -c "def get_logger" backend/app/core/logging.py` returns `1`. The function remains exported:

```python
# backend/app/core/logging.py
def get_logger(...) -> logging.Logger:
    ...
```

Per 03-CONTEXT §D-36, removal of this export is deferred to late Phase 5 / early Phase 6. The `test_logger_migration_regression.py` guard asserts absence of the CALL SITE pattern (`Depends(get_logger)`), not absence of the export itself — so this preservation is compatible with the guard.

## Phase 5 handoff (D-35)

Phase 5's `auth.py` router split now has a clean module-level-logger pattern to copy verbatim into each new submodule:

```python
import logging
# ... imports ...
logger = logging.getLogger(__name__)
```

No "regime mix" (some files via DI, some via module-level) exists in the touched surface. Phase 5 can inherit the convention mechanically.

## Verification run (pre-commit)

```
cd backend && pytest -n auto tests/test_logger_migration_regression.py \
                              tests/test_openapi_snapshot.py \
                              tests/test_pydantic_v1_regression.py \
                              tests/test_on_event_regression.py \
                              --no-cov
# Result: 5 passed in 3.61s

cd backend && pytest -n auto
# Result: 2164 passed, 5 skipped in 48.31s
#   (5 skipped = pre-existing OAuth cassette-absent tests per STATE.md deferred items)
```

## Deviations from Plan

### Rule 3 — Missing dependency: installed `uuid6` package

- **Found during:** Task 1 setup (`python -c "from app.api.schemas.user import UserRead"` to verify required fields)
- **Issue:** `ModuleNotFoundError: No module named 'uuid6'` — the module is imported by `backend/app/api/models/background_job.py:7` (`from uuid6 import uuid7`) but was not installed in the active Python environment.
- **Fix:** `pip install uuid6` (environment-only; `requirements.txt` already lists it — this was a local-env gap, not a tree gap).
- **Files modified:** none (environment setup only)
- **Commit:** none

### Dead-code helper cleanup (see Special-case handling above)

Three helper factories in `common_patterns.py` had `"logger": Depends(get_logger)` dict entries with zero callers repo-wide. Per Rule 2 / Rule 3, these would have broken at import time after the `get_logger` import removal. Minimal-blast-radius fix: removed the `"logger"` key from each helper's returned dict rather than deleting the helpers. Documented in each helper's docstring.

### Pre-existing coverage drift (out of scope)

- **Finding:** `--cov-fail-under=51` fails at 50.53% on the baseline commit `aabcdeed22f8ad8cf8ee70ca4baef616d6bb5035` — BEFORE any of this plan's changes. Verified by running `pytest --cov=app --cov-fail-under=51` on a clean checkout at that commit: same 50.53% / FAIL result.
- **Scope disposition:** pre-existing drift, NOT caused by this plan's sweep. Per the executor's scope boundary rule, "Only auto-fix issues DIRECTLY caused by the current task's changes."
- **Deferred-items recommendation:** add to `deferred-items.md` — investigate which Phase 01/02 plan drift moved coverage from the 51% floor down to 50.53%. Restore floor (either by raising test coverage on drifted files or by lowering floor to 50 with a comment). Candidate suspects per the coverage report: `app/api/endpoints/admin.py` (which has a large untested surface around background-job rescrape per the logging I/O error observed during the test run).

## Known Stubs

None. All code paths wire real data — no placeholder values, no hardcoded empty returns.

## Threat Flags

None. The sweep neither introduces new network endpoints nor changes any trust boundary. STRIDE analysis in the plan's `<threat_model>` block is fully satisfied: the three CI guards (T-03-05-01/02/03) now exist and are green; threats T-03-05-04/05/06 remain in the "accept" disposition with no change.

## Key Links

- Task 1 commit: `253eae8` — `test(03-05): add CI regression guards for QUAL-02, QUAL-03, QUAL-07`
- Task 2 commit: `8db4297` — `refactor(03-05): sweep 68 Depends(get_logger) sites to module-level logger (QUAL-07)`

## Self-Check: PASSED

- Files created (verified via `[ -f path ] && echo FOUND`):
  - `backend/tests/test_pydantic_v1_regression.py` — FOUND
  - `backend/tests/test_on_event_regression.py` — FOUND
  - `backend/tests/test_logger_migration_regression.py` — FOUND
- Commits present (verified via `git log --oneline | grep <hash>`):
  - `253eae8` — FOUND
  - `8db4297` — FOUND
- Acceptance criteria verified:
  - `grep -rn "Depends(get_logger)" backend/app/ | wc -l` returns `0`
  - `grep -c "def get_logger" backend/app/core/logging.py` returns `1` (D-36 preserved)
  - Module-level `logger = logging.getLogger(__name__)` present in all 10 swept files (verified via `grep -c "^logger = logging.getLogger(__name__)"` returns `1` per file)
  - `from app.core.logging import get_logger` absent from all 10 swept files (verified via `grep -c` returns `0` per file)
  - All 4 regression guards + OpenAPI snapshot test GREEN (`5 passed in 3.61s`)
  - Full test suite GREEN (`2164 passed, 5 skipped in 48.31s`)
