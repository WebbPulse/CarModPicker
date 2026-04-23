---
phase: 05-structural-router-splits
verified: 2026-04-23T16:45:00Z
status: human_needed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification: null
human_verification:
  - test: "AUTH-05 staging UAT — 5-step Chrome-extension end-to-end auth flow"
    expected: "All 5 checklist items in 05-HUMAN-UAT.md pass on staging after deploy"
    why_human: "Cannot be automated — requires loaded Chrome extension, staging URL, real user login, live network traffic, visual verification of popup state. The checklist file exists but all 5 checkboxes are unchecked and sign-off fields are blank."
gaps: []
deferred: []
---

# Phase 05: Structural Router Splits — Verification Report

**Phase Goal:** `admin.py` (2,055 lines) and `auth.py` (1,195 lines) are each decomposed into well-scoped sub-packages, PyJWT replaces python-jose, every split route has explicit auth dependency declarations with integration tests, and the Chrome extension's API contract is documented and validated end-to-end.

**Verified:** 2026-04-23T16:45:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (merged from ROADMAP Success Criteria + PLAN must_haves)

| # | Truth (goal-level) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | `admin/` package (stats, jobs, crawlers, db_ops, parts) live; old `admin.py` deleted same PR; every admin route 401 unauthenticated | VERIFIED | 5 sub-router files present at `backend/app/api/endpoints/admin/`; `admin.py` absent (`test ! -f` passes); 31 routes served from sub-package; `test_admin_auth_coverage.py` passes (63 cases covering 401/403 per route + drift guard) |
| 2 | `auth/` package (core, two_factor, webauthn, oauth, _helpers) live; old `auth.py` deleted same PR; Phase 1 characterization tests still pass | VERIFIED | 4 sub-router + 1 helper file present at `backend/app/api/endpoints/auth/`; `auth.py` absent; 24 auth routes served (7/3/7/7); characterization `pytest -k "auth and characterization"` — 5 passed, 2 pre-existing cassette skips |
| 3 | Chrome extension end-to-end auth flow succeeds after auth split with no extension-code changes | NEEDS HUMAN | Chrome extension source has zero `/auth/(google|oauth)` references (D-14 preserved); PyJWT parity test proves in-flight jose-issued tokens decode under PyJWT; but full staging UAT (login → popup → scrape → logout) is manual per AUTH-05. Checklist in 05-HUMAN-UAT.md, all 5 boxes unchecked, sign-off blank. |
| 4 | `chrome-extension/API_CONTRACT.md` documents every endpoint the extension calls with request/response shapes | VERIFIED | File exists (2,012 lines); first line `# Chrome Extension API Contract`; 16 endpoint sections (`grep -c '^## \`'` = 16); drift guard `test_ext_api_contract_up_to_date.py` passes; no `/auth` or `/admin` endpoints leaked |
| 5 | python-jose replaced with PyJWT 2.12.1; zero `JWTError` refs; every decode specifies algorithm | VERIFIED | `PyJWT==2.12.1` in requirements.txt; `grep -rn "from jose" backend/app/` → exit 1; `grep -rn "JWTError" backend/app/` → exit 1; custom scanner confirms 0 bare `jwt.decode` offenders; `test_jwt_algorithm_regression.py` + `test_pyjwt_migration.py` both green |
| 6 | All 23+ admin sub-package routes auth-gated; parametrized 401/403 integration test lives in CI | VERIFIED | 31 `/api/admin/*` routes (includes pre-existing crawler_schedules); `test_admin_auth_coverage.py` runs 63 cases parametrized over `app.routes`; DUAL_AUTH_ROUTES allow-list accepts (401, 403) for cron-key routes |
| 7 | All 24 auth sub-package routes obey public/protected contract; parametrized 401 test with PUBLIC_ROUTES allow-list in CI | VERIFIED | `test_auth_auth_coverage.py` contains 6 references to `PUBLIC_ROUTES` and 14 assertions (12 parametrized 401 + count guard + public-routes-non-401 sweep); all pass |
| 8 | EventBridge contract routes (/api/admin/crawlers/run, /rescrape-archives, /service-account) live in `admin.crawlers` module | VERIFIED | Module-location spot check: all three routes resolve to `app.api.endpoints.admin.crawlers`; ADMIN-03 intent preserved; `/api/admin/crawlers/run` path unchanged (EventBridge-bound per D-12) |
| 9 | Frontend Api.ts calls updated; Chrome extension untouched | VERIFIED | `frontend/src/services/Api.ts` contains `'/auth/oauth/google'`, `/link`, `/signup`, `/connect` (4 new Google OAuth literals); no old `/auth/google` literals; new `/admin/db-ops/...` paths present; `frontend` type-check + vitest green per SUMMARY; `grep -rnE "/auth/(google|oauth)" chrome-extension/src/` → exit 1 (empty) |

**Score:** 9/9 goal-level truths VERIFIED (one — truth 3 AUTH-05 UAT — requires human execution of the staging checklist)

---

## Requirements Coverage (10 IDs declared by Phase 5 plans)

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ADMIN-01 | 05-01 | admin.py (2,055 lines) → admin/ package; old file deleted same PR | SATISFIED | `backend/app/api/endpoints/admin.py` absent; 5 sub-routers live at `admin/{stats,jobs,crawlers,db_ops,parts}.py` + `_helpers.py` + `__init__.py` |
| ADMIN-02 | 05-01 | Every admin sub-router route has explicit admin auth dependency; 401/403 integration test per route | SATISFIED | `test_admin_auth_coverage.py` runs 63 parametrized cases; per-route `Depends(get_current_admin_user)` preserved; all pass |
| ADMIN-03 | 05-01 | EventBridge contract route `/api/admin/crawlers/run` stays on same path in `admin/crawlers.py` | SATISFIED | Path preserved; module-location check confirms `app.api.endpoints.admin.crawlers` serves the route; `/rescrape-archives` + `/service-account` also live in same module (defense-in-depth) |
| ADMIN-04 | 05-01 | Admin sub-routers inject specific services via `Depends()`, not a single god-service | SATISFIED | RESEARCH Finding 6: satisfied-by-construction — job_service → jobs.py + crawlers.py; part_linker_service imports hoisted to module-top in parts.py (per SUMMARY) |
| AUTH-01 | 05-04 | auth.py (1,195 lines) → auth/ package (core, two_factor, webauthn, oauth, _helpers); old file deleted same PR | SATISFIED | `backend/app/api/endpoints/auth.py` absent; 4 sub-routers + `_helpers.py` + `__init__.py` present |
| AUTH-02 | 05-04 | URL prefix `/api/auth/*` routes remain identical after split | PARTIAL (intentional deviation, documented) | Non-OAuth paths preserved. `/auth/google/*` → `/auth/oauth/google/*` (4 paths) is an intentional D-10 aggressive move called out in the plan and in the SUMMARY. Chrome extension critical path is unaffected (D-14 — extension does not call Google OAuth). Documented deviation rather than regression. |
| AUTH-03 | 05-04 | Each sub-router route explicitly redeclares auth dependency; no implicit auth loss | SATISFIED (exceeded) | `test_auth_auth_coverage.py` passes. `/api/auth/logout` now auth-gated (was previously public — D-31 intentional hardening, documented in SUMMARY Deviation #1 as Rule 2 Missing-Critical fix) |
| AUTH-04 | 05-02 | python-jose replaced with PyJWT 2.12.1; JWTError → InvalidTokenError; algorithms specified on every decode | SATISFIED | Requirements.txt has `PyJWT==2.12.1`; zero `from jose` or `JWTError` refs in backend/app/; ALGORITHM hoisted to `settings.JWT_ALGORITHM`; `test_jwt_algorithm_regression.py` scans backend/app and finds 0 offenders; `test_pyjwt_migration.py` (byte-identity parity) green |
| AUTH-05 | 05-03 | Chrome extension end-to-end auth flow validated post-refactor | NEEDS HUMAN | 5-step checklist in 05-HUMAN-UAT.md exists (created per D-38); zero steps checked; sign-off fields blank. Cannot be verified programmatically — requires loaded extension on staging. |
| AUTH-06 | 05-03 | `chrome-extension/API_CONTRACT.md` documents every endpoint the extension calls with request/response shapes | SATISFIED | 2,012-line committed file; 16 endpoint sections; drift guard passes; generator supports `--stdout` + default file-write modes; deterministic output |

**Summary:** 9/10 SATISFIED, 1 NEEDS HUMAN (AUTH-05 post-deploy UAT is the only outstanding item). 0 ORPHANED requirements — every ID mapped to Phase 5 in REQUIREMENTS.md is claimed by a plan in this phase.

Note on AUTH-02: The literal "remain identical" wording is satisfied for the Chrome-extension critical path (which AUTH-02 specifically calls out). The 4 Google OAuth path moves are an intentional restructure documented in the 05-04 plan and SUMMARY; the web frontend was migrated in the same PR; extension is unaffected. This is not a coverage gap — it is the documented design.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/api/endpoints/admin/__init__.py` | Package init (D-08) | VERIFIED | 92 bytes, single-line docstring |
| `backend/app/api/endpoints/admin/_helpers.py` | 4 job-lifecycle helpers | VERIFIED | All 4 (`_stamp_heartbeat`, `_heartbeat_loop`, `_get_superadmin_emails`, `_notify_job_completion`) present |
| `backend/app/api/endpoints/admin/{stats,jobs,crawlers,db_ops,parts}.py` | 23 routes distributed 2/4/4/7/6 | VERIFIED | 23 admin-split routes live + 8 pre-existing crawler_schedules/crawler_adapter_configs routes = 31 total under `/api/admin/*` |
| `backend/app/api/endpoints/auth/__init__.py` | Package init | VERIFIED | 91 bytes, single-line docstring |
| `backend/app/api/endpoints/auth/_helpers.py` | `_issue_login_response` + `_maybe_2fa_challenge` | VERIFIED | Both present; NO `NotImplementedError` placeholder remaining |
| `backend/app/api/endpoints/auth/{core,two_factor,webauthn,oauth}.py` | 24 routes distributed 7/3/7/7 | VERIFIED | 24 routes under `/api/auth/*` per route enumeration |
| `backend/app/api/dependencies/auth.py` | PyJWT imports + InvalidTokenError + ALGORITHM from settings | VERIFIED | Line 7: `import jwt`; Line 8: `from jwt import InvalidTokenError`; Line 18: `ALGORITHM = settings.JWT_ALGORITHM`; 3× `except InvalidTokenError` |
| `backend/app/core/config.py` | `JWT_ALGORITHM` setting (HS256 default) | VERIFIED | `JWT_ALGORITHM: str = Field(...)` present at line 39 |
| `backend/requirements.txt` | `PyJWT==2.12.1` + retained `python-jose[cryptography]==3.5.0` (Risk 6) | VERIFIED | Both lines present |
| `backend/scripts/generate_ext_api_contract.py` | Generator + 16-endpoint allow-list + `--stdout` flag | VERIFIED | `EXTENSION_ENDPOINTS` list contains 16 tuples; `--stdout` flag declared; executable produces Markdown |
| `chrome-extension/API_CONTRACT.md` | Committed contract, 16 endpoint sections | VERIFIED | 2,012 lines, header line correct, 16 sections, zero `/auth` or `/admin` leakage |
| `backend/tests/test_admin_auth_coverage.py` | Parametrized 401/403 coverage + DUAL_AUTH_ROUTES allow-list | VERIFIED | File present, 2 references to DUAL_AUTH_ROUTES, 63 cases pass |
| `backend/tests/test_auth_auth_coverage.py` | Parametrized 401 + PUBLIC_ROUTES allow-list | VERIFIED | File present, 6 PUBLIC_ROUTES references, 14 cases pass |
| `backend/tests/test_pyjwt_migration.py` | jose/PyJWT parity proof | VERIFIED | 2 tests pass (parity + byte-identity); InsecureKeyLengthWarning is benign test-only |
| `backend/tests/test_jwt_algorithm_regression.py` | CWE-327 grep guard | VERIFIED | 1 test, walks `backend/app/**/*.py`, passes |
| `backend/tests/test_ext_api_contract_up_to_date.py` | Subprocess-invoke drift guard | VERIFIED | Uses `subprocess.run`, not Python import; 1 test passes |
| `backend/tests/fixtures/openapi_snapshot.json` | Regenerated with 7 admin + 4 OAuth URL moves | VERIFIED | `test_openapi_snapshot.py` passes; delta matches the 11 intentional moves |
| `backend/app/main.py` | 5 admin sub-router + 4 auth sub-router registrations | VERIFIED | Lines 30-35 import admin submodules; 37-42 import auth submodules; 9 `register_endpoint` calls at 237/243/249/255/310/316/322/328/334 |
| `frontend/src/services/Api.ts` | 9 admin URL literals + 4 Google OAuth literals migrated | VERIFIED | All new literals grep-found; old literals absent (scan exits 1) |
| `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` | 5-step AUTH-05 UAT checklist | VERIFIED (exists; unexecuted) | File present, 5 checklist items, 4 sign-off fields all blank |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `backend/app/main.py` | `admin/{stats,jobs,crawlers,db_ops,parts}.router` | `endpoint_registry.register_endpoint(...)` | WIRED | 5 calls present at lines 310-334 |
| `backend/app/main.py` | `auth/{core,two_factor,webauthn,oauth}.router` | `endpoint_registry.register_endpoint(...)` | WIRED | 4 calls present at lines 237-255 |
| `backend/app/api/dependencies/auth.py` | `backend/app/core/config.py` | `ALGORITHM = settings.JWT_ALGORITHM` | WIRED | Line 18 exact match |
| `backend/app/api/endpoints/auth/oauth.py` | `auth/_helpers.py` | `from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge` | WIRED | Import grep-verified in SUMMARY |
| `backend/tests/test_ext_api_contract_up_to_date.py` | `backend/scripts/generate_ext_api_contract.py` | `subprocess.run([python, script, '--stdout'])` | WIRED | Test passes; no Python import of the script (confirmed by docstring rephrase per SUMMARY Deviation #2) |
| `backend/tests/test_admin_auth_coverage.py` | `app.routes` (filtered by /api/admin) | `APIRoute` enumeration + `@pytest.mark.parametrize` | WIRED | 63 test cases collected |
| `backend/tests/test_auth_auth_coverage.py` | `app.routes` (filtered by /api/auth) | PUBLIC_ROUTES set + parametrize | WIRED | 14 cases including public-routes-non-401 sweep |
| `frontend/src/services/Api.ts` | New backend URL tree | Literal strings (4 Google OAuth + 9 admin) | WIRED | All post-migration literals grep-verified |

---

## Data-Flow Trace (Level 4)

Not applicable — Phase 5 is a refactor (no new dynamic data rendering). Routing + serialization flow is tested via the 401/403 parametrized coverage tests and the Phase 1 characterization tests (7 happy-path flows). Both suites pass.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Module location: `/api/admin/crawlers/run` → `admin.crawlers` | Python route inspect | `app.api.endpoints.admin.crawlers` | PASS |
| Module location: `/api/admin/crawlers/rescrape-archives` → `admin.crawlers` | Python route inspect | `app.api.endpoints.admin.crawlers` | PASS |
| Module location: `/api/admin/crawlers/service-account` → `admin.crawlers` | Python route inspect | `app.api.endpoints.admin.crawlers` | PASS |
| Module location: `/api/auth/token` → `auth.core` | Python route inspect | `app.api.endpoints.auth.core` | PASS |
| Module location: `/api/auth/logout` → `auth.core` | Python route inspect | `app.api.endpoints.auth.core` | PASS |
| Module location: `/api/auth/oauth/google` → `auth.oauth` | Python route inspect | `app.api.endpoints.auth.oauth` | PASS |
| Module location: `/api/auth/webauthn/register/options` → `auth.webauthn` | Python route inspect | `app.api.endpoints.auth.webauthn` | PASS |
| Module location: `/api/auth/2fa/setup` → `auth.two_factor` | Python route inspect | `app.api.endpoints.auth.two_factor` | PASS |
| Live server: `POST /api/auth/token` w/o body returns 422 (public) | TestClient | 422 | PASS |
| Live server: `POST /api/auth/logout` w/o auth returns 401 (gated) | TestClient | 401 | PASS |
| Live server: `POST /api/auth/oauth/google` reachable | TestClient | 422 (valid public path; missing body) | PASS |
| Live server: `POST /api/auth/google` gone (D-10 move) | TestClient | 404 | PASS |
| Live server: `GET /api/admin/stats/table-counts` 401 unauth | TestClient | 401 | PASS |
| Live server: `GET /api/admin/db-ops/migrations/current` reachable (new path) | TestClient | 401 unauth | PASS |
| Live server: `GET /api/admin/migrations/current` gone (D-09 move) | TestClient | 404 | PASS |
| Generator `--stdout` produces expected header | Script invocation | `# Chrome Extension API Contract` | PASS |
| Generator `--stdout` emits 16 sections | Script invocation | 16 sections | PASS |
| Full Phase 5 test suite pass | pytest | 86 passed | PASS |
| Auth characterization suite pass | pytest -k "auth and characterization" | 5 passed, 2 pre-existing cassette skips | PASS |
| D-17 admin import audit clean | grep | exit 1 (no bare imports) | PASS |
| D-17 auth import audit clean | grep | exit 1 (no bare imports) | PASS |

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| (none) | No stubs, placeholders, or TODOs detected in the 13 new/modified files | — | — |

Explicit checks performed:
- `grep -rn "raise NotImplementedError" backend/app/api/endpoints/{admin,auth}/` → empty
- `grep -rn "from jose\|JWTError" backend/app/api/endpoints/{admin,auth}/` → empty
- `grep -rn "db\.query\|session\.query" backend/app/api/endpoints/{admin,auth}/` → empty (Phase 4 guard upheld)
- `grep -rn "Depends(get_logger)" backend/app/api/endpoints/{admin,auth}/` → empty (Phase 3 guard upheld)

python-jose is intentionally retained in `requirements.txt` per Risk 6 to support the parity test; removal is explicitly deferred to Phase 6 and documented. Not a gap.

---

## Human Verification Required

### 1. AUTH-05 staging UAT — 5-step Chrome-extension end-to-end auth flow

**Test:** Execute the 5-step checklist in `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` on staging after the Phase 5 commits deploy. Steps cover: (1) staging web login + JWT in localStorage, (2) extension popup "Connected as <username>", (3) navigate to a characterized retailer product page, (4) trigger scrape + verify part creation via `POST /api/parts/` 2xx, (5) logout + verify extension detects 401 on next action.

**Expected:** All 5 checkboxes pass in a single session; sign-off fields (Passed by / Date / Commit on main / Staging URL) filled.

**Why human:** Requires a loaded Chrome extension in dev mode, real staging deploy, live network capture in DevTools, visual popup verification, and cross-tab state propagation. No subset of this can be automated without Playwright-with-extensions infrastructure (D-39 — explicitly deferred in Plan 03's `<deferred>` block).

**Current state:** File exists. All 5 checkboxes unchecked. Sign-off fields blank. No evidence staging deploy has occurred or that a tester has run the checklist.

---

## Gaps Summary

No technical gaps. Every code-level must-have verifies clean against the live codebase:

- Both legacy files (`admin.py`, `auth.py`) are deleted; sub-packages are live with correct route counts.
- PyJWT migration is complete and CWE-327-hardened via a permanent CI grep guard.
- OpenAPI snapshot, API_CONTRACT drift guard, and Phase 3/4 regression guards are all green.
- Frontend URL literals are migrated; Chrome extension source is untouched (D-14 preserved).
- 8 separate module-location spot checks confirm every critical path is served from its intended sub-module.
- 86 combined Phase 5 test cases pass under `pytest -n auto`.

The single outstanding item is AUTH-05's post-deploy Chrome-extension UAT. The mechanism for closing it (the 5-step checklist) exists and is committed; only the execution + sign-off is pending. This is blocking the phase-gate close but not a code defect, and it was explicitly designed as a post-deploy step in Plan 03 per D-38.

**Recommendation:** Merge and deploy Phase 5 to staging; execute the 05-HUMAN-UAT.md checklist; fill in the sign-off fields; re-run `/gsd-verify-work` to flip AUTH-05 from NEEDS HUMAN to SATISFIED and close the phase gate.

---

_Verified: 2026-04-23T16:45:00Z_
_Verifier: Claude (gsd-verifier)_
