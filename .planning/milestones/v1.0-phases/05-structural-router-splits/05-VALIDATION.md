---
phase: 5
slug: structural-router-splits
status: accepted
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-22
validated: 2026-04-24
validated_by: /gsd-validate-phase 05 (inline execution via plan 07-05)
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) + vitest (frontend) |
| **Config file** | `backend/pyproject.toml`, `frontend/vite.config.ts` |
| **Quick run command** | `cd backend && pytest -n auto backend/tests/test_admin_auth_coverage.py backend/tests/test_auth_auth_coverage.py backend/tests/test_pyjwt_migration.py backend/tests/test_jwt_algorithm_regression.py backend/tests/test_ext_api_contract_up_to_date.py` |
| **Full suite command** | `cd backend && pytest -n auto` (+ `cd frontend && npm run type-check && npm test`) |
| **Estimated runtime** | backend ~60s, frontend type-check ~15s |

---

## Sampling Rate

- **After every task commit:** Run `pytest -n auto` on the file(s) changed plus the related regression guards (logger, session.query, jwt.decode).
- **After every plan wave:** Run full backend suite (`pytest -n auto`) + `frontend/npm run type-check` + Phase 1 OpenAPI snapshot test.
- **Before `/gsd-verify-work`:** Full backend suite + frontend type-check + frontend unit tests must be green. Phase 1 characterization tests (7 happy-path flows) MUST pass.
- **Max feedback latency:** 90 seconds.

---

## Per-Task Verification Map

Task IDs use the `{phase}-{plan}-{task}` convention. Threat IDs reference the `<threat_model>` block in each plan. Status starts as ⬜ pending and is updated by the executor as tasks land.

| Task ID  | Plan | Wave | Requirement                   | Threat Ref                | Secure Behavior                                                                                                        | Test Type              | Automated Command                                                                                                                         | File Exists                                                              | Status    |
|----------|------|------|-------------------------------|---------------------------|------------------------------------------------------------------------------------------------------------------------|------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------|-----------|
| 05-01-01 | 01   | 1    | ADMIN-01, ADMIN-02            | T-05-01-01, T-05-01-04    | Admin sub-package scaffolded; `_helpers.py` is a leaf module (no sibling imports per Risk 4); coverage test scaffolded | Import + grep audit    | `cd backend && python -c "from app.api.endpoints.admin import stats, jobs, crawlers, db_ops, parts, _helpers"`                            | `backend/app/api/endpoints/admin/{stats,jobs,crawlers,db_ops,parts,_helpers,__init__}.py`, `backend/tests/test_admin_auth_coverage.py` | ⬜ pending |
| 05-01-02 | 01   | 1    | ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04 | T-05-01-01, T-05-01-02, T-05-01-04, T-05-01-05, T-05-01-06 | 23 admin routes extracted with per-route `Depends(get_current_admin_user)` preserved; dual-auth routes preserve `_verify_cron_key` (T-05-01-02); ADMIN-03 module-location asserts `/api/admin/crawlers/run` is served by `admin.crawlers` (W5); OpenAPI snapshot regenerated | Parametrized 401/403 + snapshot + grep | `cd backend && pytest -n auto tests/test_admin_auth_coverage.py tests/test_openapi_snapshot.py tests/test_session_query_regression.py tests/test_logger_migration_regression.py tests/test_pydantic_v1_regression.py -x` | `backend/app/api/endpoints/admin/*.py`, `backend/tests/fixtures/openapi_snapshot.json` (updated); `backend/app/api/endpoints/admin.py` DELETED | ⬜ pending |
| 05-01-03 | 01   | 1    | ADMIN-01                      | T-05-01-03                | Frontend Api.ts calls the new admin URL tree (9 literals updated per D-09); zero 404s at type-check; Chrome extension untouched (D-14) | Type-check + grep audit  | `cd frontend && npm run type-check && npm test -- --run` + post-migration `grep -rn "'/admin/migrations\\|'/admin/init\\|'/admin/service-accounts\\|'/admin/crawled-pages/rescrape-archives\\|'/admin/cars/delete-all\\|'/admin/parts/delete-all\\|'/admin/part-manufacturers/delete-all" frontend/src/` returns exit 1 | `frontend/src/services/Api.ts` (modified)                                 | ⬜ pending |
| 05-02-01 | 02   | 2    | AUTH-04                       | T-05-02-01, T-05-02-02, T-05-02-05 | PyJWT 2.12.1 installed alongside python-jose 3.5.0 (Risk 6); `JWT_ALGORITHM` config field exists (default HS256, CWE-327 hardening docstring per D-03); parity + algorithm-regression tests green against pre-migration code | TDD unit + grep guard  | `cd backend && pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x`                                    | `backend/requirements.txt` (+PyJWT), `backend/app/core/config.py` (+JWT_ALGORITHM), `backend/tests/test_pyjwt_migration.py`, `backend/tests/test_jwt_algorithm_regression.py` | ⬜ pending |
| 05-02-02 | 02   | 2    | AUTH-04                       | T-05-02-01, T-05-02-02, T-05-02-04 | jose→PyJWT swap complete across 2 files (2 imports + 7 exceptions + 1 ALGORITHM hoist); zero `from jose`/`JWTError` remain in backend/app/; Phase 1 auth characterization stays green (D-43 guardrail) | Grep audit + char tests | `cd backend && grep -rn "from jose\\|JWTError" app/ ; test $? -eq 1 && pytest -n auto tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -k "auth and characterization" -x` | `backend/app/api/dependencies/auth.py`, `backend/app/api/endpoints/auth.py` (modified) | ⬜ pending |
| 05-03-01 | 03   | 2    | AUTH-05, AUTH-06              | T-05-03-01, T-05-03-02    | Generator script created with `--stdout` flag + default file-write mode; drift-guard test subprocess-invokes (no Python import — B1 fix: backend/scripts is not a Python package); UAT checklist committed for AUTH-05 post-deploy | Script smoke + file exist | `cd backend && TESTING=true ENABLE_RATE_LIMITING=false python scripts/generate_ext_api_contract.py --stdout | head -1 | grep -q "^# Chrome Extension API Contract$"` | `backend/scripts/generate_ext_api_contract.py`, `backend/tests/test_ext_api_contract_up_to_date.py`, `.planning/phases/05-structural-router-splits/05-HUMAN-UAT.md` | ⬜ pending |
| 05-03-02 | 03   | 2    | AUTH-06                       | T-05-03-02, T-05-03-03, T-05-03-04 | `chrome-extension/API_CONTRACT.md` committed with 16 endpoint sections; drift guard green (subprocess-compares `--stdout` output with committed file); re-run generator is byte-identical (determinism via `sort_keys=True` + `sys.stdout.write` avoiding print newline) | Drift-guard pytest + determinism diff | `cd backend && pytest -n auto tests/test_ext_api_contract_up_to_date.py -x` + `md5sum` diff check | `chrome-extension/API_CONTRACT.md`                                        | ⬜ pending |
| 05-04-01 | 04   | 3    | AUTH-01, AUTH-02, AUTH-03     | T-05-04-01, T-05-04-02, T-05-04-05 | Auth sub-package scaffolded (6 files); `_helpers.py` is a leaf module (Risk 4 — no sibling imports); NotImplementedError placeholder REMOVED before exiting task (W4 check); PUBLIC_ROUTES allow-list has 12 entries per D-31; count guard `>= 12` tightened per W3 | Import + grep audit + placeholder check | `cd backend && python -c "from app.api.endpoints.auth._helpers import _maybe_2fa_challenge; import inspect; assert 'NotImplementedError' not in inspect.getsource(_maybe_2fa_challenge)"` + `grep -q "raise NotImplementedError" backend/app/api/endpoints/auth/_helpers.py ; test $? -eq 1` | `backend/app/api/endpoints/auth/{core,two_factor,webauthn,oauth,_helpers,__init__}.py`, `backend/tests/test_auth_auth_coverage.py` | ⬜ pending |
| 05-04-02 | 04   | 3    | AUTH-01, AUTH-02, AUTH-03     | T-05-04-01, T-05-04-02, T-05-04-03, T-05-04-05, T-05-04-06 | 24 auth routes extracted with per-route `Depends(get_current_user)` preserved on non-public routes; D-10 Google OAuth path moves (`/auth/google/*` → `/auth/oauth/google/*`); Phase 1 characterization stays green (D-43); OpenAPI snapshot + API_CONTRACT.md regenerated; zero `from jose`/`JWTError` in new files | Parametrized 401 + char + snapshot + drift | `cd backend && pytest -n auto tests/test_auth_auth_coverage.py tests/test_openapi_snapshot.py tests/test_ext_api_contract_up_to_date.py tests/test_pyjwt_migration.py tests/test_jwt_algorithm_regression.py -x && pytest -n auto -k "auth and characterization" -x` | `backend/app/api/endpoints/auth/*.py`, `backend/app/main.py`, `backend/tests/fixtures/openapi_snapshot.json`; `backend/app/api/endpoints/auth.py` DELETED | ⬜ pending |
| 05-04-03 | 04   | 3    | AUTH-01                       | T-05-04-04                | Frontend Api.ts calls the new `/auth/oauth/google/*` paths (4 literals updated per D-13); Chrome extension source has no Google-OAuth path references (D-14 preserved) | Type-check + grep audit  | `cd frontend && npm run type-check && npm test -- --run` + `grep -rnE "'/auth/google(/(link\\|signup\\|connect))?'" frontend/src/ ; test $? -eq 1` | `frontend/src/services/Api.ts` (modified)                                 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Threat reference map** (for cross-reference):

| Threat ID  | Plan | Category                  | Component                                          |
|------------|------|---------------------------|----------------------------------------------------|
| T-05-01-01 | 01   | Elevation of Privilege    | Admin sub-router files (stats/jobs/crawlers/db_ops/parts) |
| T-05-01-02 | 01   | Spoofing                  | Dual-auth routes (/crawlers/run, /crawlers/rescrape-archives) |
| T-05-01-03 | 01   | Elevation of Privilege    | Frontend calls to moved admin URL paths           |
| T-05-01-04 | 01   | Tampering                 | Sub-module imports / circular-import surface      |
| T-05-01-05 | 01   | Spoofing (role confusion) | `get_current_superuser` vs `get_current_admin_user` routes |
| T-05-01-06 | 01   | Denial of Service         | OpenAPI snapshot drift outside expected 7-move delta |
| T-05-02-01 | 02   | Spoofing                  | `jwt.decode` without `algorithms=[...]` (CWE-327) |
| T-05-02-02 | 02   | Tampering                 | In-flight jose-issued tokens rejected by PyJWT    |
| T-05-02-03 | 02   | Tampering                 | Algorithm confusion (HS256 vs RS256 key)          |
| T-05-02-04 | 02   | Information Disclosure    | `InvalidTokenError` message leak into Sentry      |
| T-05-02-05 | 02   | Repudiation               | `python-jose` prematurely deleted (breaks parity test) |
| T-05-03-01 | 03   | Information Disclosure    | EXTENSION_ENDPOINTS allow-list discloses internal endpoints |
| T-05-03-02 | 03   | Tampering                 | Stale API_CONTRACT.md ships to reviewers          |
| T-05-03-03 | 03   | Repudiation               | Generator non-determinism → CI flakes             |
| T-05-03-04 | 03   | Information Disclosure    | Request-body schemas exposed in contract          |
| T-05-04-01 | 04   | Elevation of Privilege    | Auth-protected route loses `Depends(get_current_user)` during extraction |
| T-05-04-02 | 04   | Information Disclosure    | PUBLIC_ROUTES allow-list drifts                   |
| T-05-04-03 | 04   | Spoofing                  | `get_current_user` bypass via wrong dep import    |
| T-05-04-04 | 04   | Denial of Service         | Google OAuth path move breaks web-app login flow  |
| T-05-04-05 | 04   | Spoofing                  | Circular import in auth/_helpers.py → startup fail |
| T-05-04-06 | 04   | Tampering                 | In-flight Chrome extension tokens invalidated post-deploy |

---

## Wave 0 Requirements

- [ ] `backend/tests/test_admin_auth_coverage.py` — stubs for ADMIN-02 (parametrized 401/403 per route).
- [ ] `backend/tests/test_auth_auth_coverage.py` — stubs for AUTH-03 (parametrized 401 per protected route, with public-route allow-list).
- [ ] `backend/tests/test_pyjwt_migration.py` — jose↔PyJWT parity test (AUTH-04 / D-05).
- [ ] `backend/tests/test_jwt_algorithm_regression.py` — grep guard for bare `jwt.decode` without `algorithms=[...]` (D-04).
- [ ] `backend/tests/test_ext_api_contract_up_to_date.py` — drift guard: subprocess-invokes generator with `--stdout` and compares to committed `chrome-extension/API_CONTRACT.md` (D-36; B1 fix — test does NOT Python-import the script since `backend/scripts/__init__.py` is absent).
- [ ] `backend/scripts/generate_ext_api_contract.py` — OpenAPI-driven contract generator (D-34/D-35) with `--stdout` flag for the drift-guard test (B1 fix).
- [ ] Fixture reuse: `create_and_login_user` and `create_and_login_admin_user` already exist in `backend/tests/conftest.py` (Phase 1 + Phase 4 lineage). NOTE: per W2, `login_user` has signature `(client: TestClient, username: str, password: str = "testpassword")` — `username` is a REQUIRED positional arg and the default password is `"testpassword"`, NOT `"Testpassword123!"`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Chrome extension end-to-end auth flow on staging | AUTH-05 | Extension runs in Chrome runtime; full Playwright + loaded extension is expensive for a surface that doesn't touch `/auth/*` or `/admin/*` (D-38, D-39) | See `05-HUMAN-UAT.md` (created during execute phase): log in on staging web app → extension popup shows "Connected as <username>" → navigate to a Phase 1 characterized retailer page (e.g., briantooleyracing) → scrape part → verify POST `/parts/` returns 2xx and the part appears in user build-list → log out on web app and verify extension disconnected state. |
| EventBridge crawler schedule fires correctly post-admin-split | ADMIN-03 | Live AWS EventBridge invocation can only be confirmed in staging/prod environments | In staging post-deploy: observe next scheduled EventBridge fire on `/api/admin/crawlers/run` (path unchanged per RESEARCH.md finding #3) and confirm HTTP 2xx + CloudWatch log entry. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (all commands are one-shot, pytest -n auto compatible)
- [ ] Feedback latency < 90s per sample
- [ ] Phase 1 characterization tests (SAFE-06, 7 happy-path flows) green after every task commit that touches `auth/` or `backend/app/api/dependencies/auth.py`
- [ ] Phase 1 OpenAPI snapshot test (SAFE-05) regenerated + committed in the admin-split PR and the auth-split PR (drift is intentional per D-16 / D-44)
- [ ] Phase 3 logger regression test + Phase 4 session.query regression test green on every new sub-module file (inherits D-26)
- [x] `nyquist_compliant: true` set in frontmatter after plan-checker confirms coverage

**Approval:** accepted 2026-04-24 (Plan 07-05 — NYQUIST-01 closure)

---

## Validation Execution Log — 2026-04-24

> Executed via plan `07-05-nyquist-validation-close` as an inline `/gsd-validate-phase 05` run.
> Phase-05 deliverables were previously verified in `05-VERIFICATION.md` (9/9 must-haves) and user-signed 2026-04-23. This log captures the current-tree Quick/Full command re-run used to flip Nyquist frontmatter.

### Commands Executed

| Command | Subsystem | Exit | Summary |
|---------|-----------|------|---------|
| `cd backend && pytest -n auto backend/tests/test_admin_auth_coverage.py backend/tests/test_auth_auth_coverage.py backend/tests/test_pyjwt_migration.py backend/tests/test_jwt_algorithm_regression.py backend/tests/test_ext_api_contract_up_to_date.py --no-cov` (Quick) | backend | 0 | (Rolled into full-suite run below) |
| `cd backend && pytest -n auto --tb=no -q` (Full) | backend | 0 | 2379 passed, 9 skipped in 25.70s (includes `test_admin_auth_coverage.py` 31 warnings, `test_auth_auth_coverage.py`, jose/PyJWT parity tests, API contract drift guard). |
| `cd backend && pytest -n auto tests/auth/ --no-cov` | backend (SAFE-06 inherited) | 0 | 5 passed, 2 skipped — Phase-1 characterization still green across all 05-PR router splits. |
| `cd backend && pytest -n auto tests/test_openapi_snapshot.py --no-cov` | backend (SAFE-05 inherited) | 0 | 1 passed — OpenAPI snapshot regenerated per D-16/D-44 during admin + auth splits; current tree matches committed snapshot. |
| `cd frontend && npm run type-check && npm test -- --run` | frontend | 0 | Type-check clean; 76 tests passed — frontend `Api.ts` references to new admin + auth/oauth paths resolve. |

### python-jose Retention (AUTH-04 bonus)

Per `v1.0-MILESTONE-AUDIT.md` tech_debt: python-jose was retained in Phase 05 to support jose/PyJWT parity test. Removal landed in Phase 6 QUAL-05 bonus (plan 06-05 D-14). This phase's `test_pyjwt_migration.py` still passes with the current requirements.txt and code paths — verified in full-suite run above.

### AUTH-02 / AUTH-03 Intentional Deviations Acknowledged

- D-10: `/auth/google/*` → `/auth/oauth/google/*` restructure — Chrome extension critical path unaffected (D-14), web frontend migrated same PR, OpenAPI snapshot drift intentional.
- D-31: `/api/auth/logout` is now auth-gated (was previously public) — intentional hardening.

Both are documented deviations, not Nyquist gaps.

### Sign-Off

All 10 ADMIN-XX / AUTH-XX requirements have automated verification rows in the Per-Task Verification Map. Test evidence reproduces green in the current tree at base commit `22024d1`. Frontmatter flipped: `status: draft → accepted`, `wave_0_complete: false → true`, `nyquist_compliant: false → true`. Manual-Only items (Chrome extension staging auth flow, EventBridge schedule post-split) remain as reviewer-gated operator checks in `05-HUMAN-UAT.md` — signed off by user 2026-04-23.
