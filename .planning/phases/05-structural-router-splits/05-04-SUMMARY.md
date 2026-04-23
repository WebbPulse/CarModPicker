---
phase: 05-structural-router-splits
plan: 04
subsystem: auth
tags: [fastapi, auth, jwt, pyjwt, oauth, webauthn, totp, router-split, openapi, parametrized-tests]

# Dependency graph
requires:
  - phase: 05-01-admin-split
    provides: Sub-package split template + leaf _helpers pattern + parametrized 401 coverage test shape
  - phase: 05-02-pyjwt-migration
    provides: PyJWT 2.12.1 library swap + settings.JWT_ALGORITHM hoist — split lands on modernized library from day one
  - phase: 05-03-api-contract-generator
    provides: chrome-extension/API_CONTRACT.md + drift-guard test — independent reviewer sanity for extension contract
  - phase: 01-safety-nets-ci-hardening
    provides: OpenAPI snapshot test + auth characterization tests (D-43 guardrail) + Phase 3/4 regression guards
provides:
  - auth/ sub-package with 4 sub-routers (core, two_factor, webauthn, oauth)
  - auth/_helpers.py leaf module (_issue_login_response, _maybe_2fa_challenge)
  - Parametrized 401 drift guard over every /api/auth route with PUBLIC_ROUTES allow-list (D-31)
  - OpenAPI snapshot regenerated with 4 Google OAuth URL moves (D-10) + /api/auth/logout security
  - Deletion of 1,193-line auth.py (CONCERNS.md oversized-file paydown)
  - Frontend Api.ts migrated to post-split Google OAuth paths (D-13)
  - /api/auth/logout newly auth-gated (D-31/AUTH-03 post-split truth)
affects: [06-dependency-cleanup, future-auth-evolution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auth sub-package split: core/two_factor/webauthn/oauth + leaf _helpers.py (mirrors admin template)"
    - "PUBLIC_ROUTES allow-list in test_auth_auth_coverage.py — explicit review-gated public route set"
    - "Constant duplication at leaf module (OAUTH_2FA_PURPOSE, GOOGLE_PROVIDER in _helpers.py + oauth.py) to avoid circular imports"
    - "mock.patch path migration: auth module-top imports -> auth.{webauthn,oauth} sub-module-top imports"

key-files:
  created:
    - backend/app/api/endpoints/auth/__init__.py
    - backend/app/api/endpoints/auth/_helpers.py
    - backend/app/api/endpoints/auth/core.py
    - backend/app/api/endpoints/auth/two_factor.py
    - backend/app/api/endpoints/auth/webauthn.py
    - backend/app/api/endpoints/auth/oauth.py
    - backend/tests/test_auth_auth_coverage.py
  modified:
    - backend/app/main.py
    - backend/tests/fixtures/openapi_snapshot.json
    - backend/tests/api/endpoints/test_auth.py
    - backend/tests/api/endpoints/test_google_oauth.py
    - backend/tests/api/endpoints/test_webauthn.py
    - backend/tests/auth/test_characterization_oauth_link.py
    - backend/tests/auth/test_characterization_oauth_signin.py
    - backend/tests/auth/test_characterization_webauthn.py
    - frontend/src/services/Api.ts
  deleted:
    - backend/app/api/endpoints/auth.py (1193 lines)

key-decisions:
  - "D-10 aggressive URL moves applied: /auth/google/* routes re-rooted under /auth/oauth/google/* (4 paths)"
  - "D-18 cross-module helpers moved to auth/_helpers.py: _issue_login_response, _maybe_2fa_challenge"
  - "D-19 WebAuthn-local helpers stay in auth/webauthn.py: _b64url_{encode,decode}, _build/_decode_challenge_token"
  - "D-20 Google-specific helpers stay in auth/oauth.py: _ensure_google_enabled, _verify_google_or_400, _suggest_username, _decode_purpose_token"
  - "D-31 public-route allow-list codified as PUBLIC_ROUTES set in coverage test (12 entries) — drift detector"
  - "AUTH-03/D-31 logout added Depends(get_current_user) — post-split coverage truth requires 401 on unauthenticated (was 200 pre-split)"
  - "PATTERNS.md §9 Open Question resolved option (a): OAUTH_2FA_PURPOSE + GOOGLE_PROVIDER duplicated in _helpers.py (leaf-module-only; source-of-truth in oauth.py)"
  - "D-14 Chrome extension untouched — extension does not call Google OAuth paths; JWT still decodable under PyJWT 2.12.1 (Plan 02 parity proof)"
  - "mock.patch migration: test_webauthn / test_google_oauth / test_characterization_webauthn updated from app.api.endpoints.auth.X -> app.api.endpoints.auth.{webauthn,oauth}.X"
  - "test_auth.py logout tests updated: test_logout_success now sends Authorization bearer; test_logout_without_login now expects 401 (was 200)"

patterns-established:
  - "Sub-package 401 coverage template: parametrize over app.routes filtered by prefix, subtract PUBLIC_ROUTES allow-list"
  - "Public-route dual guard: (a) protected routes return 401 without auth, (b) public routes return non-401 without auth (auth-leak detector)"
  - "Count-at-or-above drift guard: fails if a parametrized test is disabled or a route silently deleted"
  - "Test mock patch paths anchored on sub-module imports: forces future refactors to update patches explicitly"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03]

# Metrics
duration: 12min
completed: 2026-04-23
---

# Phase 05 Plan 04: Auth Router Split Summary

**Decomposed 1,193-line auth.py into a 4-file auth/ sub-package with leaf _helpers.py, deleted the original file, registered 4 sub-routers in main.py, moved the 4 Google OAuth paths under /auth/oauth/google/* (D-10), added auth-gating to /auth/logout, migrated frontend Api.ts Google OAuth literals, created a parametrized 401 drift guard with 12-entry PUBLIC_ROUTES allow-list, and regenerated the OpenAPI snapshot.**

## Performance

- **Duration:** ~12 min (first commit 09:23:52Z, last commit 09:35:22Z)
- **Started:** 2026-04-23T09:23:52-07:00
- **Completed:** 2026-04-23T09:35:22-07:00
- **Tasks:** 3
- **Files modified:** 17 (7 created, 9 modified, 1 deleted)

## Accomplishments

- 24 auth routes extracted and distributed across 4 focused sub-router files (core=7, two_factor=3, webauthn=7, oauth=7 — exactly matches PLAN.md Finding 2 table)
- `backend/app/api/endpoints/auth.py` deleted (1,193 lines; CONCERNS.md structural-debt entry closed)
- `backend/app/main.py` now registers 4 sub-routers instead of 1 monolithic auth.router
- Parametrized `test_auth_auth_coverage.py` drives 14 assertions (12 parametrized 401 + 1 count guard + 1 public-routes-non-401 sweep)
- OpenAPI snapshot regenerated; diff reflects (a) the 4 Google OAuth path moves `/auth/google/*` → `/auth/oauth/google/*`, (b) new OAuth2PasswordBearer security requirement on `/api/auth/logout`, and (c) operationId string shifts that follow the path changes
- `frontend/src/services/Api.ts` migrated: 4 Google OAuth URL literals updated; type-check clean; vitest 32/32 green
- Chrome extension untouched — confirms D-14 / RESEARCH Finding 3 (extension never calls Google OAuth paths, only /auth/token + authenticated endpoints)
- Phase 1 auth characterization guardrail stayed green (5 passed, 2 skipped — the 2 skipped are pre-existing OAuth cassette deferrals from Phase 01, not introduced here)

## Task Commits

Each task committed atomically:

1. **Task 1: Scaffold auth sub-package + 401 coverage test** — `6d03154` (test)
2. **Task 2: Extract 24 auth routes + wire main.py + delete auth.py + regenerate snapshot** — `ff951d5` (feat)
3. **Task 3: Migrate frontend Google OAuth URL literals** — `211f0dd` (feat)

_Note: Task 1 is the TDD RED scaffold (empty sub-routers + failing 12-count guard); Task 2 is the GREEN gate (routes wired, guard passes); Task 3 is the parallel frontend migration that keeps the full stack consistent._

## Files Created/Modified

**Created (backend):**
- `backend/app/api/endpoints/auth/__init__.py` — single-line docstring package init (D-08)
- `backend/app/api/endpoints/auth/_helpers.py` — cross-module helpers `_issue_login_response` + `_maybe_2fa_challenge` (D-18 leaf module) + duplicated `OAUTH_2FA_PURPOSE` / `GOOGLE_PROVIDER` constants per PATTERNS.md §9
- `backend/app/api/endpoints/auth/core.py` — 7 routes: /token, /token/2fa, /verify-email, /verify-email/confirm, /reset-password, /reset-password/confirm, /logout (AUTH-GATED per D-31)
- `backend/app/api/endpoints/auth/two_factor.py` — 3 routes at prefix /auth/2fa: /setup, /verify, /disable
- `backend/app/api/endpoints/auth/webauthn.py` — 7 routes at prefix /auth/webauthn + D-19 local helpers (WEBAUTHN_REGISTER/LOGIN_PURPOSE, _b64url_encode/_decode, _build/_decode_challenge_token)
- `backend/app/api/endpoints/auth/oauth.py` — 7 routes at prefix /auth/oauth + D-20 local helpers (GOOGLE_LINK/SIGNUP/PROVIDER/OAUTH_2FA_PURPOSE constants, _ensure_google_enabled, _verify_google_or_400, _suggest_username, _decode_purpose_token) + cross-module import of _issue_login_response/_maybe_2fa_challenge
- `backend/tests/test_auth_auth_coverage.py` — parametrized drift guard over `app.routes` filtered by `/api/auth` with 12-entry PUBLIC_ROUTES allow-list

**Modified:**
- `backend/app/main.py` — Removed `auth` from `from .api.endpoints import (...)` tuple; added `from .api.endpoints.auth import (core as auth_core, oauth as auth_oauth, two_factor as auth_2fa, webauthn as auth_webauthn)`; replaced the single `auth.router` registration with 4 sub-router registrations at prefixes `/auth`, `/auth/2fa`, `/auth/webauthn`, `/auth/oauth`
- `backend/tests/fixtures/openapi_snapshot.json` — regenerated; diff shows 4 Google OAuth URL moves + /api/auth/logout security block + derivative operationId shifts
- `backend/tests/api/endpoints/test_auth.py` — `test_logout_success` now passes Authorization bearer; `test_logout_without_login` now expects 401 (was 200) — deviation Rule 3 "blocking" behavior shift from AUTH-03 plan truth
- `backend/tests/api/endpoints/test_webauthn.py` — 4 `mock.patch("app.api.endpoints.auth.verify_{registration,authentication}_response")` retargeted to `auth.webauthn.*`
- `backend/tests/api/endpoints/test_google_oauth.py` — 18 `mock.patch("app.api.endpoints.auth.verify_google_id_token")` retargeted to `auth.oauth.verify_google_id_token`; 4 path constants (GOOGLE_PATH/LINK_PATH/SIGNUP_PATH/CONNECT_PATH) moved to `/auth/oauth/google*`
- `backend/tests/auth/test_characterization_oauth_link.py` — 2 URL literals moved: `/auth/google` → `/auth/oauth/google` and `/auth/google/link` → `/auth/oauth/google/link`
- `backend/tests/auth/test_characterization_oauth_signin.py` — 1 URL literal moved: `/auth/google` → `/auth/oauth/google`
- `backend/tests/auth/test_characterization_webauthn.py` — 4 `mock.patch("app.api.endpoints.auth.{generate,verify}_{registration,authentication}_{options,response}")` retargeted to `auth.webauthn.*`
- `frontend/src/services/Api.ts` — 4 URL literal updates: `/auth/google*` → `/auth/oauth/google*`

**Deleted:**
- `backend/app/api/endpoints/auth.py` (1193 lines)

## URL Moves (OpenAPI snapshot diff)

| Old path | New path |
|---|---|
| `POST /api/auth/google` | `POST /api/auth/oauth/google` |
| `POST /api/auth/google/link` | `POST /api/auth/oauth/google/link` |
| `POST /api/auth/google/signup` | `POST /api/auth/oauth/google/signup` |
| `POST /api/auth/google/connect` | `POST /api/auth/oauth/google/connect` |

Preserved unchanged (per D-10 + D-14):
- `POST /api/auth/token`, `POST /api/auth/token/2fa`
- `POST /api/auth/verify-email`, `GET /api/auth/verify-email/confirm`
- `POST /api/auth/reset-password`, `POST /api/auth/reset-password/confirm`
- `POST /api/auth/logout` (path unchanged; security now requires OAuth2PasswordBearer — NEW)
- `POST /api/auth/2fa/setup`, `POST /api/auth/2fa/verify`, `POST /api/auth/2fa/disable`
- All 7 `POST/GET/PATCH/DELETE /api/auth/webauthn/*` routes
- `POST /api/auth/oauth/2fa`, `GET /api/auth/oauth`, `DELETE /api/auth/oauth/{account_id}`

## Decisions Made

- **OAUTH_2FA_PURPOSE + GOOGLE_PROVIDER duplicated in `auth/_helpers.py`** (PATTERNS.md §9 Open Question option (a)): `_helpers.py` must remain a leaf module (Risk 4 mitigation) — importing these constants from `auth/oauth.py` would create a sibling sub-module edge. Two-line string-literal duplication is a small, low-churn cost; source-of-truth remains in `auth/oauth.py`.
- **Logout auth-gating (AUTH-03 / D-31):** The plan's `must_haves.truths` explicitly requires `/api/auth/logout` to return 401 without auth and succeed with valid JWT. The original `auth.py` logout had no `Depends(get_current_user)`; the new core.py version adds it. This is a Rule 2 (auto-add missing critical functionality) deviation, made explicit in the plan frontmatter — not a scope change invented during execution. Two pre-existing `test_auth.py` tests (`test_logout_success`, `test_logout_without_login`) were updated to match the new behavior (Rule 3 blocking deviation).
- **`@router.get("")` vs `@router.get("/")` for list endpoint:** FastAPI yields `/api/auth/oauth/` (trailing slash) when combining prefix `/auth/oauth` with path `/`, which drifts from the original `/api/auth/oauth` (no slash). Switched to `@router.get("")` for exact parity with pre-split path.
- **Test patch path migration as forcing function:** Per `test_characterization_webauthn.py` comment block, the patches explicitly pin the import boundary so a router refactor that moves imports causes explicit patch failures rather than silent stub misses. This plan validated that intent — all 22 patch targets across 3 test files were updated deliberately.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added Depends(get_current_user) to `/auth/logout`**
- **Found during:** Task 2 verification (test_auth_auth_coverage.py failure on /api/auth/logout without auth)
- **Issue:** Original auth.py:344 `async def logout()` had no auth dependency, so unauthenticated calls returned 200. The plan's `must_haves.truths` entry explicitly requires auth-gating, AND the PUBLIC_ROUTES allow-list in the plan deliberately omits `/api/auth/logout`. Without this fix, `test_auth_route_requires_token[POST-/api/auth/logout]` would fail (expects 401, got 200).
- **Fix:** Added `current_user: DBUser = Depends(get_current_user)` to the logout handler signature + imported `get_current_user` in core.py.
- **Files modified:** `backend/app/api/endpoints/auth/core.py`
- **Verification:** `pytest tests/test_auth_auth_coverage.py` 14/14 pass.
- **Committed in:** `ff951d5` (Task 2 commit).

**2. [Rule 3 - Blocking] Updated `test_auth.py` logout tests to reflect auth-gated behavior**
- **Found during:** Task 2 final pytest sweep (full backend suite)
- **Issue:** `test_logout_success` sent an unauthenticated POST to `/auth/logout` and expected 200; after the logout gate was added, it got 401. `test_logout_without_login` also expected 200 but now should expect 401.
- **Fix:** `test_logout_success` now extracts the access_token from login response and sends `Authorization: Bearer <token>`; `test_logout_without_login` now asserts 401 (post-split coverage truth).
- **Files modified:** `backend/tests/api/endpoints/test_auth.py`
- **Verification:** test_auth.py 27/27 pass; full backend suite 2364 passed, 8 skipped.
- **Committed in:** `ff951d5` (Task 2 commit).

**3. [Rule 3 - Blocking] Updated 22 `mock.patch` targets across 3 test files + 4 test path constants**
- **Found during:** Task 2 pytest sweep — patches targeted `app.api.endpoints.auth.verify_google_id_token` etc. which no longer exists after auth.py deletion.
- **Issue:** `mock.patch` targets pinned the pre-split module path. After the split, those names live in sub-modules (`auth.webauthn`, `auth.oauth`).
- **Fix:** Migrated all 22 patch targets: `app.api.endpoints.auth.X` → `app.api.endpoints.auth.{webauthn,oauth}.X`. Also migrated 4 path constants in `test_google_oauth.py` (`GOOGLE_PATH`, `LINK_PATH`, `SIGNUP_PATH`, `CONNECT_PATH`) and 3 URL literals in characterization tests to the new `/auth/oauth/google*` paths.
- **Files modified:**
  - `backend/tests/api/endpoints/test_webauthn.py` (4 patches)
  - `backend/tests/api/endpoints/test_google_oauth.py` (18 patches + 4 path constants)
  - `backend/tests/auth/test_characterization_webauthn.py` (4 patches — note: the module docstring preserves the original import targets as historical commentary, new patches take effect)
  - `backend/tests/auth/test_characterization_oauth_link.py` (2 URL literals)
  - `backend/tests/auth/test_characterization_oauth_signin.py` (1 URL literal)
- **Verification:** test_webauthn.py 26/26 pass, test_google_oauth.py 20/20 pass, Phase 1 characterization 5 pass (2 pre-existing skip).
- **Committed in:** `ff951d5` (Task 2 commit).

---

**Total deviations:** 3 auto-fixed (1 missing-critical, 2 blocking)
**Impact on plan:** All three were foreshadowed: deviation #1 is spelled out verbatim in plan `must_haves.truths` (so technically a plan-mandated add rather than invented scope); #2 is the natural downstream fallout of #1; #3 is called out in plan Task 2 Step D ("Audit test imports per Risk 5"). No scope creep — all changes confined to files the plan already lists in its `files_modified` block or transitive test-file fallout explicitly anticipated.

## Issues Encountered

- **FastAPI trailing-slash drift on `/api/auth/oauth` list endpoint:** initial implementation used `@router.get("/")` which yielded `/api/auth/oauth/` (with slash) — a silent path change from the original `/api/auth/oauth` (no slash). Caught by manual route enumeration after Task 2 implementation. Fixed by switching to `@router.get("")`.
- **Hook reminders fired spuriously on `Write`/`Edit` tool calls** after files had already been read in the session. The hook's "READ-BEFORE-EDIT" guard appears to not persist Read-tool usage across certain tool invocations in my session. The tool calls still succeeded (file updates were applied per tool responses), and I re-read files when prompted out of an abundance of caution. Does not affect correctness.

## Test Evidence

```
pytest -n auto backend/tests/test_auth_auth_coverage.py
  14 passed (12 parametrized 401 + count guard + public-routes-non-401)

pytest -n auto backend/tests/test_openapi_snapshot.py
  1 passed (snapshot equality after regeneration)

pytest -n auto backend/tests/test_ext_api_contract_up_to_date.py
  1 passed (API_CONTRACT.md unchanged — extension paths untouched, D-14)

pytest -n auto backend/tests/test_pyjwt_migration.py backend/tests/test_jwt_algorithm_regression.py
  3 passed (AUTH-04 guards preserved across split)

pytest -n auto backend/tests/test_session_query_regression.py
        backend/tests/test_logger_migration_regression.py
        backend/tests/test_pydantic_v1_regression.py
  4 passed (Phase 3/4 inherited guards)

pytest -n auto -k "auth and characterization"
  5 passed, 2 skipped (Phase 1 D-43 guardrail; 2 skips are pre-existing OAuth cassette deferrals from Phase 01)

pytest -n auto --cov=app --cov-fail-under=51
  2364 passed, 8 skipped; Total coverage 51.33% (above 51% gate)

cd frontend && npm run type-check
  clean

cd frontend && npm test -- --run
  32 passed
```

## User Setup Required

None - no external service configuration required.

## Post-Deploy Action Required (AUTH-05 UAT)

Once this plan's commits land on `main` and deploy to staging, execute the 5-step AUTH-05 UAT checklist in `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md`. The checklist was created in Plan 05-03 and validates:

1. Web email/password login — `/api/auth/token` still works under split
2. Google OAuth sign-in — new `/api/auth/oauth/google` path works end-to-end
3. Google link flow — new `/api/auth/oauth/google/link` path works end-to-end
4. Chrome extension — existing bearer tokens decode correctly under split; extension continues calling its (unchanged) endpoints
5. WebAuthn passkey registration + login — new `/api/auth/webauthn/*` paths work end-to-end

Only after all 5 steps pass on staging does the Phase 5 gate close.

## Chrome Extension Untouched (D-14)

Grep verification confirmed:

```
grep -rnE "/auth/(google|oauth)" chrome-extension/src/    # -> empty (exit 1)
```

The Chrome extension does not call Google OAuth paths directly — it receives an already-issued bearer token from the web app via `chrome.runtime.sendMessage`. Zero extension changes were made, preserving D-14. The PyJWT parity proof from Plan 05-02 (`test_pyjwt_migration.py`) guarantees that extension-held jose-encoded tokens decode correctly under PyJWT 2.12.1, so in-flight sessions survive deploy without re-auth.

## Next Phase Readiness

- **AUTH-01, AUTH-02, AUTH-03 closed.** 1,193-line auth.py decomposed; 24 routes served from 4 sub-routers; parametrized 401 coverage test in CI.
- **Phase 5 auth-split deliverable complete.** Only post-deploy UAT (AUTH-05 in 05-HUMAN-UAT.md) remains to close the phase gate.
- **Phase 6 dependency cleanup seeded:** the auth split lands on modernized PyJWT (Plan 02) + the parametrized-test pattern is transferable to any future sub-package work; python-jose removal remains deferred per Plan 02 rationale.
- **No blockers for downstream phases.**

## Self-Check: PASSED

Verified post-creation:

- [x] Sub-package files present: `__init__.py`, `_helpers.py`, `core.py`, `two_factor.py`, `webauthn.py`, `oauth.py` (all at `backend/app/api/endpoints/auth/`)
- [x] Test scaffold present: `backend/tests/test_auth_auth_coverage.py`
- [x] Old `backend/app/api/endpoints/auth.py` deleted (verified via `test ! -f`)
- [x] 24 auth sub-package routes served (verified via `app.routes` enumeration; 7/3/7/7 = 24)
- [x] Commits present in git log: `6d03154`, `ff951d5`, `211f0dd`
- [x] OpenAPI snapshot test passes against regenerated fixture
- [x] Phase 1/2/3/4 regression guards pass (pyjwt, jwt algorithm, session-query, logger-migration, pydantic-v1, openapi-snapshot, ext API contract drift guard)
- [x] Phase 1 D-43 end-to-end guardrail green (5 auth characterization tests pass; 2 pre-existing cassette skips)
- [x] Frontend type-check + vitest green; no stray old-path literals in `frontend/src/`
- [x] Chrome extension zero Google/OAuth paths (D-14 preserved)
- [x] Coverage 51.33% above 51% gate
- [x] NotImplementedError placeholder absent in `_helpers.py` (function body copied verbatim, not stubbed)

---

*Phase: 05-structural-router-splits*
*Completed: 2026-04-23*
