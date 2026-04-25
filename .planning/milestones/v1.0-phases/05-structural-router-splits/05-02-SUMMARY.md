---
phase: 05-structural-router-splits
plan: 02
subsystem: auth
tags: [jwt, pyjwt, python-jose, security, cwe-327, auth, hs256]

# Dependency graph
requires:
  - phase: 05-01-admin-split
    provides: Admin router split landed first per roadmap ordering
  - phase: 01-safety-nets-ci-hardening
    provides: Auth characterization tests (D-43 guardrail) for in-flight token regression detection
provides:
  - PyJWT 2.12.1 primary JWT library (AUTH-04)
  - settings.JWT_ALGORITHM centralized algorithm config (default HS256)
  - backend/tests/test_pyjwt_migration.py — jose/PyJWT HS256 parity proof
  - backend/tests/test_jwt_algorithm_regression.py — CWE-327 grep guard (bare jwt.decode detector)
  - Zero from jose / JWTError references in backend/app/
  - ALGORITHM hoisted from dependencies/auth.py literal to settings.JWT_ALGORITHM
affects: [05-04-auth-split, 06-dependency-cleanup]

# Tech tracking
tech-stack:
  added: [PyJWT==2.12.1]
  patterns: [jwt.InvalidTokenError broad base exception, regression-grep guard (test_*_regression.py shape)]

key-files:
  created:
    - backend/tests/test_pyjwt_migration.py
    - backend/tests/test_jwt_algorithm_regression.py
  modified:
    - backend/requirements.txt
    - backend/app/core/config.py
    - backend/app/api/dependencies/auth.py
    - backend/app/api/endpoints/auth.py

key-decisions:
  - "python-jose retained through Phase 5 for parity test import (Risk 6). Removal deferred to Phase 6 dependency cleanup."
  - "ALGORITHM hoisted from module-level literal to settings.JWT_ALGORITHM (D-07). Sibling code imports ALGORITHM unchanged — no callsite churn."
  - "endpoints/auth.py (still monolithic at Plan 02) receives the library swap in-place. Split into per-feature routers lands in Plan 04 after API_CONTRACT."
  - "No leeway=10 addition was needed — Phase 1 auth characterization stayed green on first run without PyJWT iat/exp tolerance adjustments (Risk 1 non-triggered)."

patterns-established:
  - "Regression-grep guard: scan backend/app/**/*.py for a dangerous-pattern regex with a 3-line window for multi-line statements (shape mirrored from test_session_query_regression.py)."
  - "Library-swap parity test: encode with old library, decode with new library, assert payload identity + byte-identity of encoded token. Deletable once confidence period elapses."

requirements-completed: [AUTH-04]

# Metrics
duration: 3min
completed: 2026-04-23
---

# Phase 05 Plan 02: PyJWT Migration Summary

**Swap python-jose==3.5.0 for PyJWT==2.12.1 across auth.py with CWE-327-hardening grep guard and HS256 parity proof, landing before the auth router split so the split happens on the modernized library from day one.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-23T16:09:00Z
- **Completed:** 2026-04-23T16:12:00Z (approx)
- **Tasks:** 2
- **Files modified:** 4 (+ 2 new test files)

## Accomplishments

- PyJWT 2.12.1 added alongside retained python-jose 3.5.0 (Risk 6 — jose kept for parity test through Phase 5)
- `settings.JWT_ALGORITHM` config field added (default HS256; D-03 + D-07 hoist target)
- 2 import-line rewrites: `from jose import JWTError, jwt` → `import jwt` + `from jwt import InvalidTokenError` (dependencies/auth.py line 7, endpoints/auth.py line 23)
- 7 exception-handler rewrites: `except JWTError[: | as e:]` → `except InvalidTokenError[: | as e:]` (3 in dependencies/auth.py lines 100/132/160, 4 in endpoints/auth.py lines 261/332/515/911)
- `ALGORITHM = "HS256"` literal hoisted to `ALGORITHM = settings.JWT_ALGORITHM` in dependencies/auth.py line 17 (D-07)
- 2 new test files: `test_pyjwt_migration.py` (parity + byte-identity) and `test_jwt_algorithm_regression.py` (CWE-327 grep guard)
- **Parity test result: byte-identical confirmed.** Assumption A2 from plan holds — jose and PyJWT produce the same HS256 token string for identical payload + key + algorithm.
- Phase 1 auth characterization suite green (5 passed, 2 OAuth-cassette-pending skips from Phase 01 deferred item): login happy path, signup/verify, webauthn register/authenticate, TOTP enroll/challenge, password reset request/confirm — all decode in-flight tokens correctly under PyJWT.

## Task Commits

1. **Task 1: Add PyJWT + JWT_ALGORITHM config + parity/regression tests** — `245da69` (feat)
2. **Task 2: Swap jose → PyJWT imports + rewrite exceptions + hoist ALGORITHM** — `e4c595c` (feat)

_Note: Both tasks combined TDD-style test + implementation into single commits because the parity tests (written pre-swap) validate the post-swap behavior directly, and the regression grep stays green across both phases._

## Files Created/Modified

- **Created:** `backend/tests/test_pyjwt_migration.py` — HS256 parity (jose encode → PyJWT decode) + byte-identity across libraries. Delete candidate in Phase 6 when python-jose is removed.
- **Created:** `backend/tests/test_jwt_algorithm_regression.py` — Permanent CI gate: scans `backend/app/**/*.py` for any `jwt.decode(...)` without `algorithms=[...]` within 3 lines. Shapes mirrored from `test_session_query_regression.py` per Phase 3/4 precedent.
- **Modified:** `backend/requirements.txt` — Added `PyJWT==2.12.1` with explanatory comment; kept `python-jose[cryptography]==3.5.0` with deferral comment pointing to Phase 6 cleanup.
- **Modified:** `backend/app/core/config.py` — Added `JWT_ALGORITHM: str = Field(default="HS256", ...)` after `ACCESS_TOKEN_EXPIRE_MINUTES_MAX`. Matches the `Field(default=..., description=...)` pattern used by SECRET_KEY and GOOGLE_CLIENT_ID.
- **Modified:** `backend/app/api/dependencies/auth.py` — Line 7: import swap. Line 17: ALGORITHM hoist. Lines 100/132/160: `except JWTError:` → `except InvalidTokenError:`. `jwt.encode`/`jwt.decode` call-sites unchanged (PyJWT signatures identical to jose).
- **Modified:** `backend/app/api/endpoints/auth.py` — Line 23: import swap. Lines 261/332/515/911: `except JWTError[: | as e:]` → `except InvalidTokenError[: | as e:]`. `jwt.decode` call-sites unchanged (already had `algorithms=[ALGORITHM]` per pre-migration audit). **File remains monolithic — split into per-feature routers lands in Plan 05-04 after API_CONTRACT.**

## Decisions Made

- **python-jose retention (Risk 6):** Kept in requirements.txt with a comment noting Phase 6 deferred removal. Required because `test_pyjwt_migration.py` imports jose to prove parity. Removing jose in the same PR as adding the parity test would cause `ModuleNotFoundError` at test-collection time (T-05-02-05 mitigation).
- **ALGORITHM hoist (D-07):** `ALGORITHM = settings.JWT_ALGORITHM` keeps the module-level `ALGORITHM` name intact. Sibling code that imports or references `ALGORITHM` from `dependencies.auth` needs no changes. The `settings.JWT_ALGORITHM` layer centralizes the algorithm literal for future rotation (out of scope this plan per D-46).
- **No `leeway=10` addition:** Phase 1 auth characterization passed on the first post-swap run, meaning PyJWT 2.x's stricter `iat`/`exp` validation (Risk 1) did not trigger token rejection on any of the 5 characterization flows. Leeway is available as a future mitigation if Sentry reveals a 401 spike post-deploy.
- **Single commit per task (not strict TDD RED/GREEN split):** The test files in Task 1 were written to pass against the existing jose-backed codebase (parity proof + regression grep both green against pre-swap state per plan's `<behavior>` section). Task 2 then applied the library swap while keeping both tests green. This matches the plan's `<action>` ordering exactly; a RED/GREEN commit split would have required writing a test that fails before the swap — which contradicts the parity-test design intent.

## Deviations from Plan

None — plan executed exactly as written. All verification steps passed on first run:

- Two grep audits returned exit 1 (zero `from jose`, zero `JWTError` in `backend/app/`).
- `grep -c "except InvalidTokenError"`: 3 in dependencies/auth.py, 4 in endpoints/auth.py (matches plan's expected counts).
- `grep -q "^ALGORITHM = settings.JWT_ALGORITHM$"`: exit 0.
- `grep -c "^from jwt import InvalidTokenError$"`: 1 in each of the two files.
- `pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py`: 3 passed.
- `pytest -n auto -k "auth and characterization"`: 5 passed, 2 skipped (OAuth cassette-pending — pre-existing Phase 01 deferred item, not caused by this plan).
- `from app.main import app; len(app.routes) == 197`: OK.

## Issues Encountered

None.

## Risk 1 Watch Items (Post-Deploy)

Monitor the following via Sentry after merging this PR to production:

- **Spike in 401 responses on `/api/auth/*` endpoints** in the first 5–15 minutes post-deploy. If observed, root-cause before next Plan (05-03 / 05-04). Expected cause if triggered: PyJWT 2.x's stricter `iat` clock-skew validation rejecting tokens issued moments before deploy with the rolling-worker clock skew (typically <5s, but possible up to ~30s on App Runner).
- **Mitigation if triggered:** Add `leeway=10` (seconds) to each `jwt.decode(...)` call in `dependencies/auth.py` lines 95, 127, 155 AND `endpoints/auth.py` lines 227, 311, 514, 910. Single follow-up PR; does not require rollback.
- **Characterization guard:** `pytest -n auto -k "auth and characterization"` green in this commit proves in-flight-token behavior works at test-SECRET_KEY level. Production SECRET_KEY may expose subtle differences; monitor actively for the first post-deploy hour.

## python-jose Retention Rationale (Risk 6)

python-jose 3.5.0 remains in `requirements.txt` with an explanatory comment:

```
# python-jose — KEPT through Phase 5 only for test_pyjwt_migration.py parity assertion.
# Scheduled for removal in Phase 6 dependency cleanup.
```

**Why kept:** `test_pyjwt_migration.py` imports `from jose import jwt as jose_jwt` to prove byte-identical HS256 tokens between libraries. Deleting jose now would break test collection (T-05-02-05).

**Why deferrable:** jose is no longer imported by any runtime code (`backend/app/**/*.py`), verified by `grep -rn "from jose" backend/app/` returning exit 1. It is a test-only dependency after this plan. The ecdsa transitive-dep CVE remains non-exploitable in HS256-only usage (documented in original comment, preserved).

**Removal plan:** Phase 6 dependency-cleanup plan removes `python-jose[cryptography]==3.5.0` from `requirements.txt`, deletes `test_pyjwt_migration.py` (or converts it to a PyJWT-only self-encode/self-decode sanity test), and re-audits. At that point, ecdsa disappears from the dependency tree entirely.

## Still-Monolithic auth.py Note

`backend/app/api/endpoints/auth.py` remains a single ~900-line module after this plan. The library swap was performed in-place. The per-feature split (email verification, password reset, webauthn, 2FA/TOTP, google OAuth, core login) is scheduled for Plan 05-04 per the phase roadmap. That plan operates on the modernized PyJWT-backed file, benefiting from the clean `InvalidTokenError` exception convention and the `settings.JWT_ALGORITHM` hoist.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- **AUTH-04 closed.** Zero `from jose` / `JWTError` in runtime code. CWE-327 regression grep in CI.
- **Plan 05-04 ready to consume:** can split endpoints/auth.py without worrying about jose→PyJWT drift in the split commits.
- **Phase 6 dependency cleanup seeded:** python-jose removal + `test_pyjwt_migration.py` disposition documented in Deferred Ideas.
- **Production deploy watch:** Sentry 401-spike monitoring for 1 hour post-deploy. Rollback not anticipated.

## Self-Check: PASSED

Verified post-creation:
- `backend/requirements.txt` contains `PyJWT==2.12.1` and `python-jose[cryptography]==3.5.0` — both lines present.
- `backend/app/core/config.py` contains `JWT_ALGORITHM: str = Field(` — field added.
- `backend/app/api/dependencies/auth.py` contains `import jwt`, `from jwt import InvalidTokenError`, `ALGORITHM = settings.JWT_ALGORITHM`, 3 `except InvalidTokenError:` sites.
- `backend/app/api/endpoints/auth.py` contains `import jwt`, `from jwt import InvalidTokenError`, 4 `except InvalidTokenError` sites.
- `backend/tests/test_pyjwt_migration.py` exists and passes (2 tests).
- `backend/tests/test_jwt_algorithm_regression.py` exists and passes (1 test).
- Commits `245da69` (Task 1) and `e4c595c` (Task 2) present in `git log --oneline`.

---
*Phase: 05-structural-router-splits*
*Completed: 2026-04-23*
