---
phase: 6
slug: frontend-cleanup-final-ci-gates
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `06-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

### Backend

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 + pytest-xdist 3.8.0 + pytest-cov 6.2.1 + pytest-recording 0.13.4 |
| **Config file** | `backend/pytest.ini` (coverage floor 51 per SAFE-01) |
| **Quick run command** | `cd backend && pytest -n auto -x path/to/test_file.py::test_name` |
| **Full suite command** | `cd backend && pytest -n auto --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~60 seconds full suite (xdist parallel) |

### Frontend

| Property | Value |
|----------|-------|
| **Framework** | vitest 3.2.4 + @testing-library/react 16.1.0 + jsdom 25.0.1 |
| **Config file** | `frontend/vitest.config.ts` |
| **Quick run command** | `cd frontend && npm test -- --run path/to/file.test.ts` |
| **Full suite command** | `cd frontend && npm test -- --run --coverage` |
| **Estimated runtime** | ~30 seconds full suite |

### Static / Lint

| Property | Value |
|----------|-------|
| **Frontend lint** | `cd frontend && npm run lint` (ESLint 9.x with tseslint recommendedTypeChecked) |
| **Frontend circular-import check** | `cd frontend && npx madge --circular --extensions ts,tsx src/` (FE-06, new) |
| **Backend lint** | `cd backend && black --config pyproject.toml . && isort . && pyright` |
| **Backend security scan** | `cd backend && bandit -r app` (QUAL-04 verification path; currently `-ll` gates HIGH) |

### Infrastructure-as-Code

| Property | Value |
|----------|-------|
| **Terraform validate** | `cd terraform && terraform validate` |
| **Terraform plan (Glacier rule only)** | `cd terraform && terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data` |
| **Manual artifact** | `terraform plan` output pasted into PR description (D-20) |

---

## Sampling Rate

- **After every task commit (quick feedback, ≤30s target):**
  - Frontend typing work: `cd frontend && npm run lint`
  - Frontend tests touched: `cd frontend && npm test -- --run <touched test>`
  - Backend upgrade/test work: `cd backend && pytest -n auto -x <touched test>`
- **After every plan wave (wave-merge gate):**
  - Wave 1 (parallel small — FE-02, FE-06 setup, FE-05 codemod, QUAL-04, QUAL-08): frontend lint+test + backend QUAL-04 regression test
  - Wave 2 (FE-01 typing chunks + FE-04 API domain split): frontend lint + frontend full suite
  - Wave 3 (FE-03 route-group wrappers): frontend full suite (new RouteGroupBoundary + App.coverage tests)
  - Wave 4 (PR-A — FastAPI 0.136 + Pydantic 2.13 + QUAL-06 extension audit): backend full pytest + OpenAPI snapshot + auth characterization
  - Wave 5 (PR-B — SQLAlchemy 2.0.49 + Alembic 1.18 + Uvicorn 0.45 + jose removal): backend full pytest + migration round-trip script
  - Wave 6 (FE-07 opportunistic polish + parts-catalog targeted pass): frontend full suite + manual UAT sample
- **Before `/gsd-verify-work`:** All four must be green simultaneously:
  1. `cd backend && pytest -n auto --cov=app --cov-report=term-missing`
  2. `cd frontend && npm test -- --run --coverage`
  3. `cd frontend && npm run lint`
  4. `cd frontend && npx madge --circular --extensions ts,tsx src/`
- **Max feedback latency:** ≤30 seconds for task-commit sample; ≤90 seconds for wave-merge gate.

---

## Per-Requirement Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Wave |
|--------|----------|-----------|-------------------|-------------|------|
| FE-01 | ESLint strict rules gate CI; zero source violations | lint | `cd frontend && npm run lint` | ✅ existing (rule config flip) | 2 |
| FE-01 | `src/test/**` honors strict rules (D-05) | lint | `cd frontend && npm run lint` | ✅ same | 2 |
| FE-02 | No `process.env` in frontend browser source | static guard | `cd frontend && npm test -- --run src/test/no-process-env.test.ts` | ❌ Wave 0 | 1 |
| FE-03 | Every `<Route>` sits under a route-group boundary | integration (RTL) | `cd frontend && npm test -- --run src/App.coverage.test.tsx` | ❌ Wave 0 | 3 |
| FE-03 | RouteGroupBoundary fallback UI renders on child throw | integration (RTL) | `cd frontend && npm test -- --run src/components/common/RouteGroupBoundary.test.tsx` | ❌ Wave 0 | 3 |
| FE-04 | Per-domain `src/api/*.ts` modules exist (D-22) | static | `test -d frontend/src/api && ls frontend/src/api/*.ts` | ❌ created in Wave 2 | 2 |
| FE-04 | API client response handlers narrow via `unknown` not `any` | lint | Covered by FE-01 `no-unsafe-*` rules | ✅ same lint step | 2 |
| FE-05 | No `bg-gradient-to-*` substring anywhere in src/ | static guard | `cd frontend && npm test -- --run src/test/no-legacy-gradient.test.ts` | ❌ Wave 0 | 1 |
| FE-06 | Zero circular imports | static | `cd frontend && npx madge --circular --extensions ts,tsx src/` | ✅ CLI available; CI step new | 1 |
| FE-07 | Opportunistic polish does not regress visual behavior | manual UAT | Human review (06-HUMAN-UAT.md checklist) | ❌ drafted in Wave 6 | 6 |
| QUAL-04 | bandit HIGH-severity subprocess fixture fails CI | integration (subprocess) | `cd backend && pytest -n auto backend/tests/test_bandit_high_gate.py` | ❌ Wave 0 | 1 |
| QUAL-05 | Pydantic 2.13 emits zero V1 deprecations (existing guard) | pytest catch_warnings | `cd backend && pytest -n auto` (plan 03-05 guard fires on any v1 deprecation) | ✅ existing | 4 |
| QUAL-05 | Alembic 1.18 round-trip migrations | script | `cd backend && bash scripts/test_migration_round_trip.sh` | ✅ existing (plan 04-06) | 5 |
| QUAL-05 | FastAPI 0.136 auth characterization green | existing | `cd backend && pytest -n auto -k "auth and characterization"` | ✅ existing (SAFE-06) | 4 |
| QUAL-05 | FastAPI 0.136 OpenAPI snapshot stable | existing | `cd backend && pytest -n auto backend/tests/test_openapi_snapshot.py` | ✅ existing (SAFE-05) | 4 |
| QUAL-06 | Extension POSTs set Content-Type or use FormData | static guard | `cd frontend && npm test -- --run src/test/extension-content-type.test.ts` | ❌ Wave 0 | 4 |
| QUAL-08 | Terraform plan produces DEEP_ARCHIVE transition at 90 days on crawl-data bucket | terraform plan | `cd terraform && terraform plan -target=aws_s3_bucket_lifecycle_configuration.crawl_data` | Manual (PR artifact) | 1 |
| D-14 | python-jose removed from requirements.txt; no source imports `jose` | static | `! grep -rn "from jose\|import jose" backend/` | Manual grep or CI step (Wave 0 or 5) | 5 |
| D-23 | `backend/tests/dependencies/test_auth_utils.py` migrated to PyJWT | static + test | `! grep -n "from jose" backend/tests/dependencies/test_auth_utils.py && cd backend && pytest -n auto backend/tests/dependencies/test_auth_utils.py` | ✅ test file exists; migration edit in Wave 5 | 5 |

*Status column intentionally omitted — gsd-executor tracks per-task status in PLAN.md frontmatter.*

---

## Wave 0 Requirements

Wave 0 (infrastructure before implementation) must install the following before any implementation wave runs. Every item is a Wave-1 prerequisite:

- [ ] `backend/tests/test_bandit_high_gate.py` — QUAL-04 regression test (subprocess runs bandit on synthetic B602 HIGH fixture; asserts exit code ≠ 0). xdist-safe.
- [ ] `frontend/src/test/no-legacy-gradient.test.ts` — FE-05 regression guard (greps `src/**/*.{ts,tsx}`, fails on any `bg-gradient-to-` hit).
- [ ] `frontend/src/test/extension-content-type.test.ts` — QUAL-06 regression guard (greps `chrome-extension/src/**/*.ts` for `fetch(..., { method: 'POST' ... })`, asserts `Content-Type: application/json` header or `FormData` body).
- [ ] `frontend/src/test/no-process-env.test.ts` — FE-02 regression guard (greps `src/` for `process.env`; allow-lists documented exceptions in vite.config.ts / non-browser files).
- [ ] `frontend/src/App.coverage.test.tsx` — FE-03 route-group coverage (parametrized RTL render per route; forces child throw; asserts RouteGroupBoundary fallback).
- [ ] `frontend/src/components/common/RouteGroupBoundary.tsx` — new component implementing D-07/D-08 (Sentry `FallbackRender` with eventId surfacing, Retry button, Go Home link).
- [ ] `frontend/src/components/common/RouteGroupBoundary.test.tsx` — render + fallback + retry-resets-state test.
- [ ] `.github/workflows/frontend-ci.yml` — new `Check circular imports` step after `Run tests`, before `Build application`.
- [ ] `frontend/package.json` — add `madge@^8.0.0` to devDependencies + regenerate `package-lock.json`.
- [ ] `frontend/eslint.config.js` — flip `@typescript-eslint/no-explicit-any`, `no-unsafe-*` from warn to error (FE-01 D-01); drop `src/test/**` override (D-05).
- [ ] `frontend/06-LINT-BASELINE.txt` — committed output of `cd frontend && npm run lint 2>&1 | tee 06-LINT-BASELINE.txt` after the eslint config flip (D-02).

No new test framework installation needed — vitest + pytest already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Parts-catalog polish visual quality | FE-07 | Aesthetic judgement; no headless visual regression harness | `06-HUMAN-UAT.md` checklist: Card variants, spacing, typography match existing patterns on `pages/parts/*` and `components/parts/*` |
| Opportunistic polish on touched pages | FE-07 | Scope is per-PR and subjective | UAT spot-checks on pages visited during waves 1–5 |
| Terraform apply (QUAL-08) | QUAL-08 | Requires AWS SSO; operator-gated | `terraform apply` run by operator after plan review; confirm `aws_s3_bucket_lifecycle_configuration.crawl_data` resource created in state |
| PR-A smoke test against chrome extension | QUAL-06 | Can't exercise `chrome-extension://` origin in headless CI | Load unpacked extension → hit login/crawl endpoints against local backend built on FastAPI 0.136; verify no 400 Content-Type errors |
| Sentry event ID surfaces in prod route-group fallback | FE-03 / OBS-05 | Requires real Sentry project + staging deploy | Trigger a staging error in each of admin/authentication/builder/public route groups; confirm fallback shows event ID and the event is captured with `route_group` tag |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies declared
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references in Per-Requirement Verification Map
- [ ] No watch-mode flags on any command
- [ ] Feedback latency < 30s per task, < 90s per wave
- [ ] Manual-only items are genuinely unautomatable (not just "not yet automated")
- [ ] `nyquist_compliant: true` set in frontmatter after planner confirms coverage

**Approval:** pending
