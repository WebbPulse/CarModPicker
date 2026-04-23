---
phase: 5
slug: structural-router-splits
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
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

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {populated by planner} | — | — | — | — | — | — | — | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Planner: fill this table per task in each PLAN.md and mirror here.*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_admin_auth_coverage.py` — stubs for ADMIN-02 (parametrized 401/403 per route).
- [ ] `backend/tests/test_auth_auth_coverage.py` — stubs for AUTH-03 (parametrized 401 per protected route, with public-route allow-list).
- [ ] `backend/tests/test_pyjwt_migration.py` — jose↔PyJWT parity test (AUTH-04 / D-05).
- [ ] `backend/tests/test_jwt_algorithm_regression.py` — grep guard for bare `jwt.decode` without `algorithms=[...]` (D-04).
- [ ] `backend/tests/test_ext_api_contract_up_to_date.py` — drift guard: regenerated contract equals committed `chrome-extension/API_CONTRACT.md` (D-36).
- [ ] `backend/scripts/generate_ext_api_contract.py` — OpenAPI-driven contract generator (D-34/D-35).
- [ ] Fixture reuse: `create_and_login_user` and `test_admin_user` already exist in `backend/tests/conftest.py` (Phase 1 + Phase 4 lineage) — no new fixtures required beyond what RESEARCH.md surfaced.

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
- [ ] `nyquist_compliant: true` set in frontmatter after plan-checker confirms coverage

**Approval:** pending
