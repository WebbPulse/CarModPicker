# Roadmap: CarModPicker — Tech-Debt Audit + Fix-All Milestone

## Overview

This milestone pays down eight areas of structural and operational debt across a brownfield FastAPI + React + crawler platform before it sees real traffic. The sequence is driven by three safety principles: safety nets before structural changes, observability before anything that could silently break, and data integrity hardening before high-regression-risk router splits. Every area gets fully resolved — no half-refactors.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Safety Nets & CI Hardening** - Lock in coverage floors, characterization tests, and migration guards before touching anything structural
- [x] **Phase 2: Observability** - Add Sentry, CloudWatch crawler metrics, and alarms — additive-only, zero regression risk
- [x] **Phase 3: Non-Breaking Internal Improvements** - Crawler hardening, adapter auto-discovery, Pydantic v1 sweep, car-data lazy-load
- [x] **Phase 4: DB & Parts Hardening** - N+1 fix, part-link concurrency, FK index audit, session API migration, build-log eager creation
- [x] **Phase 5: Structural Router Splits** - admin.py → admin/ package, then auth.py → auth/ package; PyJWT migration
- [x] **Phase 6: Frontend Cleanup & Final CI Gates** - ESLint rules, type-safety, Tailwind v4 patterns, error boundaries, bandit/dep upgrades
- [ ] **Phase 7: v1.0 Residue Cleanup & Audit-Drift Sync** - Operational bugs, code-review residue, dead code, integration advisory A-01, Nyquist Wave 0 close, REQUIREMENTS/ROADMAP doc sync
- [ ] **Phase 8: Frontend Coverage Expansion (SAFE-03)** - Lift frontend test coverage from 0.43% baseline to D-06 targets (60/50/50/60) and enforce thresholds in CI

## Phase Details

### Phase 1: Safety Nets & CI Hardening
**Goal**: CI enforces coverage floors, characterization tests pin current behavior, and migration DROP guard + broken constraint repairs prevent any future phase from shipping a regression silently
**Depends on**: Nothing (first phase)
**Requirements**: SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-06, SAFE-07, SAFE-08, SAFE-09, SAFE-10
**Success Criteria** (what must be TRUE):
  1. A PR that drops backend test coverage below the measured baseline fails CI automatically via `--cov-fail-under`
  2. Every PR runs `npm test -- --run` in CI and frontend coverage threshold is enforced
  3. Any migration containing `drop_column`, `drop_table`, or `drop_constraint` without a `# SAFE:` annotation fails the CI lint step
  4. Auth characterization tests cover all 7+ happy-path flows (signup, verify-email, login, 2FA-TOTP, WebAuthn, OAuth, password-reset) and are CI-green
  5. The three `op.drop_constraint(None, ...)` migrations are repaired and `MetaData` uses an explicit `naming_convention`
**Plans:** 8 plans
- [x] 01-01-PLAN.md — SAFE-09: apply `MetaData(naming_convention=...)` to declarative Base + unit test pinning the 5 convention keys
- [x] 01-02-PLAN.md — SAFE-08: repair three `op.drop_constraint(None, ...)` migrations (prod-state checkpoint + in-place or forward-only repair)
- [x] 01-03-PLAN.md — SAFE-04: migration DROP-guard script, unit tests, CI step in backend-ci.yml
- [x] 01-04-PLAN.md — SAFE-01/02/03: measure coverage baselines (checkpoint) + `--cov-fail-under` + vitest thresholds + frontend `Run tests` CI step
- [x] 01-05-PLAN.md — SAFE-05: OpenAPI schema snapshot test + committed fixture
- [x] 01-06-PLAN.md — SAFE-06: 7 auth characterization tests (VCR cassettes + WebAuthn mocks) + secret-audit guardrail
- [x] 01-07-PLAN.md — SAFE-07: 5 crawler adapter characterization tests against archived HTML fixtures (2× tier0_http + 2× tier2_browser + 1× tier1_tls)
- [x] 01-08-PLAN.md — SAFE-10: `.github/dependabot.yml` (weekly Monday, pip + npm multi-dir + github-actions, minor+patch grouping, no ignore block)

### Phase 2: Observability
**Goal**: Production errors are visible in Sentry, per-adapter crawler metrics flow into CloudWatch, and a parse-failure alarm fires automatically — all without changing any URL, schema, or external contract
**Depends on**: Phase 1
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04, OBS-05
**Success Criteria** (what must be TRUE):
  1. Unhandled exceptions in the FastAPI app appear in Sentry with request ID, user ID, and SQLAlchemy query context attached
  2. After a crawler run, CloudWatch shows per-adapter `Ingested`, `ParseFailures`, and `ElapsedSeconds` metrics in the `CarModPicker/Crawlers` namespace
  3. A CloudWatch alarm triggers an SNS → SES email when any adapter's parse-failure rate exceeds 50%
  4. Frontend runtime errors appear in Sentry (or equivalent) via an `ErrorBoundary` integration
**Plans:** 5 plans
- [x] 02-01-PLAN.md — OBS-04: request_id/user_id propagation audit + bg_log_context + CLI context + pytest regression guard
- [x] 02-02-PLAN.md — OBS-01: Sentry Python SDK 2.x init (FastAPI + Starlette + SQLAlchemy + Logging integrations) + before_send scope processor + Secrets Manager DSN + App Runner/ECS IAM grants
- [x] 02-03-PLAN.md — OBS-02: CloudWatch EMF per-adapter metrics (Ingested / ParseFailures / ElapsedSeconds in CarModPicker/Crawlers namespace) emitted from runner.py BEFORE summary log; rescrape runs emit RunType=rescrape
- [x] 02-04-PLAN.md — OBS-05: @sentry/react + Session Replay on-error + ErrorBoundary captureException + AuthContext setUser + CI-only vite-plugin sourcemap upload + beforeErrorSampling auth-route gate
- [x] 02-05-PLAN.md — OBS-03: Terraform composite parse-failure alarm (metric-math, NaN-via-0 suppression, RunType=live filter, TODO marker for Phase 3 per-adapter for_each) + Crawler Drift Runbook in CONCERNS.md + 02-HUMAN-UAT.md
**Note**: Phase 2 is additive-only (no URL/model/schema changes). It may execute concurrently with Phase 3 — both are low regression risk after Phase 1 completes. Internal wave structure: Wave 1 → [02-01]; Wave 2 → [02-02, 02-04]; Wave 3 → [02-03]; Wave 4 → [02-05]. 02-05 is `autonomous: false` — prod terraform apply gates on 24h staging bake + 7-item HUMAN-UAT checklist per D-58.

### Phase 3: Non-Breaking Internal Improvements
**Goal**: The crawler subsystem is hardened end-to-end (auto-discovery, circuit breaker, parallelization, pre-crawl health check, parse-failure reporting), startup latency improves, and Pydantic v1 anti-patterns are eliminated — without touching any external API contract
**Depends on**: Phase 1
**Requirements**: CRAWL-01, CRAWL-02, CRAWL-03, CRAWL-04, CRAWL-05, CRAWL-06, CRAWL-07, QUAL-01, QUAL-02, QUAL-03, QUAL-07
**Success Criteria** (what must be TRUE):
  1. `ADAPTER_REGISTRY` is populated by directory-scan auto-discovery; CI asserts the discovered count equals the expected baseline; import errors surface as ERROR logs and fail CI rather than silently dropping adapters
  2. The `pybreaker` circuit breaker opens after 3 consecutive failures (down from 5) and backs off for 120 seconds; 429/503 triggers immediate bail
  3. Per-adapter crawler execution runs in a bounded `ThreadPoolExecutor` (workers sized to `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE`); each adapter worker holds its own `SessionLocal`
  4. `uvicorn --reload` startup latency is measurably reduced after `car_generations_data.py` is replaced with a JSON + `lru_cache` loader
  5. `pytest` run produces zero Pydantic v1 deprecation warnings
**Plans:** 5 plans
- [x] 03-01-PLAN.md — CRAWL-01/02/03: adapter auto-discovery (base-class + ADAPTER_NAME/IS_FALLBACK/HEALTH_PROBE_URL ClassVars + __init_subclass__ guard) + 108-adapter sweep via committed helper script + pkgutil.iter_modules scan in __init__.py + test_adapter_discovery.py (count=108, _IMPORT_ERRORS==[]) + 5 characterization tests re-keyed by ADAPTER_REGISTRY[name]
- [x] 03-02-PLAN.md — CRAWL-04/05/06: pybreaker==1.4.1 per-adapter-name registry (fail_max=3, reset_timeout=120) replacing custom counter block; terminal 429/503 pre-trip via breaker.open(); check_health() probe (HEALTH_PROBE_URL=None opt-in default); verify existing ThreadPoolExecutor + CRAWLER_MAX_ADAPTER_WORKERS + per-worker SessionLocal
- [x] 03-03-PLAN.md — CRAWL-07: extend runner result dict with parse_failures, sample_failure_urls (first-5), elapsed_seconds; extend _render_crawler_result_html in email.py with ParseFailures block; URL truncation for >160-char samples
- [x] 03-04-PLAN.md — QUAL-01: lazy JSON loader (car_generations.py with @lru_cache(maxsize=1) + importlib.resources.files) + car_generations_data.json asset + thin-shim car_generations_data.py preserving slugify/CarGenerationData/CAR_GENERATIONS/get_all_car_generations + one-shot export script + uvicorn startup latency measurement (D-28)
- [x] 03-05-PLAN.md — QUAL-02/03/07: three CI regression guards (Pydantic v1 grep + catch_warnings roundtrip; @app.on_event grep; Depends(get_logger) grep) + 68-site logger sweep across 10 files (auth=21, users=11, base_endpoint_router=8, base_report_router=6, reports=5, common_patterns=4, base_vote_router=4, bug_reports=4, admin_endpoint_patterns=3, votes=2)
**Note**: Phase 3 may execute concurrently with Phase 2. Internal ordering within this phase: CRAWL-01/02/03 (auto-discovery + validation) must complete and count-assert green before CRAWL-05 (parallelization) lands. Dependency graph: Plans 01, 04, 05 in wave 1 (parallel); Plan 02 in wave 2 (depends on 01); Plan 03 in wave 3 (depends on 02).

### Phase 4: DB & Parts Hardening
**Goal**: The N+1 query in build logs is fixed and regression-gated, part-link operations are transactional with concurrency tests, all FK join keys have indexes, and the `session.query()` legacy API is eliminated — the database layer is clean and production-pool-sized before any structural router work begins
**Depends on**: Phase 1
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09, DATA-10, PARTS-01, PARTS-02, PARTS-03
**Success Criteria** (what must be TRUE):
  1. `GET /build-logs/build-list/{id}` with 10+ posts issues exactly 2 SQL queries (one for posts, one for authors via `selectinload`), and a query-count assertion in CI prevents regression
  2. Simultaneous part link/unlink from 10 concurrent threads produces zero orphaned or circular canonical references, verified by a concurrency test
  3. All FK join keys across 22+ models have `Index()` declarations; no full-table-scan warnings appear on the FK columns in RDS Performance Insights for common queries
  4. Zero `session.query()` calls remain in the codebase; all queries use `select()` + `session.scalars()`
  5. Build log creation is eager (alongside build list creation) — the inconsistent mid-request auto-create branch in `build_logs.py:87-98` is eliminated
**Plans:** 6 plans
- [x] 04-01-PLAN.md — DATA-05/07: FK index audit across 22 models + autogenerated index-only migration + pool_recycle 3600 → 1800 + regression tests for index presence and pool config (Wave 1, parallel-safe)
- [x] 04-02-PLAN.md — DATA-08: Alembic data-migration backfill of build_logs for legacy build_lists (gen_random_uuid + WHERE NOT EXISTS idempotent; no-op downgrade with SAFE annotation) + delete lazy auto-create branches in build_logs.py :86-98 and :191-201 + orphan-guard invariant test (Wave 2)
- [x] 04-03-PLAN.md — DATA-01/02: N+1 fix in build_logs.py via selectinload(DBBuildLogPost.author) + count query modernization + query_counter fixture using event.listen(engine, before_cursor_execute) with finally-event.remove + self-test + 2-query regression test (Wave 3)
- [x] 04-04-PLAN.md — DATA-06: single-PR mechanical sweep of ~304 db.query / session.query / self.db.query sites across ~37 files per D-08 file-priority order (utils → services → endpoints → crawlers) + grep-based regression guard test_session_query_regression.py + OpenAPI snapshot preservation (Wave 4)
- [x] 04-05-PLAN.md — DATA-03/04/PARTS-01: with_for_update() row-lock insertion in link_new_part/reelect_canonical/unlink_part + pytest `postgres` marker + postgres_engine fixture with PYTEST_XDIST_WORKER per-worker DB suffix + docker-compose.test.yml + backend-ci.yml postgres-tests job (postgres:16 side-car) + 10-thread ThreadPoolExecutor concurrency test asserting exactly-one-canonical/no-cycles/no-orphans invariants (Wave 5)
- [x] 04-06-PLAN.md — DATA-09/10/PARTS-02/PARTS-03: lazy="raise" on BuildLogPost.author + BuildList.build_list_parts + BuildList.build_list_phases with callers audit + car_inference AMBIGUOUS_STANDALONE_CODES docstring + ≥20 parametrized ambiguity vectors pinning current behavior + 5 canonical-flow SQLite integration scenarios + CONVENTIONS.md "Alembic downgrade testing" subsection + test_migration_round_trip.sh reviewer-gated script (Wave 6)
**Note**: Wave structure: Wave 1 → [04-01]; Wave 2 → [04-02]; Wave 3 → [04-03]; Wave 4 → [04-04]; Wave 5 → [04-05]; Wave 6 → [04-06]. Serialized by design per D-42/D-43 and by file-overlap avoidance (build_logs.py touched by plans 02/03/04; part_linker_service.py touched by plans 04/05/06; models touched by plans 01/06). Plan 04-05 introduces a new @pytest.mark.postgres opt-in CI job alongside the existing SQLite default — pytest -n auto local runs remain unchanged.

### Phase 5: Structural Router Splits
**Goal**: `admin.py` (2,055 lines) and `auth.py` (1,195 lines) are each decomposed into well-scoped sub-packages, PyJWT replaces python-jose, every split route has explicit auth dependency declarations with integration tests, and the Chrome extension's API contract is documented and validated end-to-end
**Depends on**: Phase 1, Phase 4
**Requirements**: ADMIN-01, ADMIN-02, ADMIN-03, ADMIN-04, AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06
**Success Criteria** (what must be TRUE):
  1. `admin/` package (stats.py, jobs.py, crawlers.py, db_ops.py, parts.py) is live; old `admin.py` is deleted in the same PR; every sub-router route returns 401 for unauthenticated requests (integration tested)
  2. `auth/` package (core.py, two_factor.py, webauthn.py, oauth.py, _helpers.py) is live; old `auth.py` is deleted in the same PR; all `/api/auth/*` characterization tests from Phase 1 still pass
  3. Chrome extension end-to-end auth flow (login, token handoff, logout) succeeds after the auth split with no changes to extension code
  4. `chrome-extension/API_CONTRACT.md` documents every endpoint the extension calls with request/response shapes
  5. `python-jose` is replaced with `PyJWT 2.12.1`; zero `JWTError` references remain; algorithm is explicitly specified on every decode call
**Plans:** 4 plans
- [x] 05-01-admin-split-PLAN.md — ADMIN-01/02/03/04: decompose admin.py into admin/ sub-package (5 sub-routers + _helpers), regenerate OpenAPI snapshot, migrate frontend admin URLs, parametrized 401/403 coverage test
- [x] 05-02-pyjwt-migration-PLAN.md — AUTH-04: swap python-jose for PyJWT 2.12.1 with JWT_ALGORITHM config hoist, 7 JWTError → InvalidTokenError rewrites, jose/PyJWT parity test, bare-jwt.decode grep guard
- [x] 05-03-api-contract-generator-PLAN.md — AUTH-05/06: OpenAPI-driven chrome-extension/API_CONTRACT.md generator + drift-guard pytest + 05-HUMAN-UAT.md staging checklist
- [x] 05-04-auth-split-PLAN.md — AUTH-01/02/03: decompose auth.py into auth/ sub-package (4 sub-routers + _helpers), aggressive /auth/google/* → /auth/oauth/google/* restructure, parametrized 401 coverage test with public-route allow-list
**Note**: Within Phase 5, admin split (ADMIN-01—04) must precede auth split (AUTH-01—06). Admin is not in the Chrome extension critical path; use it as a dry run for the split pattern before the highest-stakes refactor.

### Phase 6: Frontend Cleanup & Final CI Gates
**Goal**: The frontend has enforced type-safety rules, no legacy env-var patterns, error boundaries on every lazy-loaded page, a clean Tailwind v4 class set, and no circular imports; bandit and dependency upgrades close the remaining CI and security gaps; opportunistic UX polish lands on every page touched
**Depends on**: Phase 2, Phase 5
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07, QUAL-04, QUAL-05, QUAL-06, QUAL-08
**Success Criteria** (what must be TRUE):
  1. `eslint` fails any PR introducing `@typescript-eslint/no-explicit-any` or `no-unsafe-*` violations; existing violations are fixed or allow-listed with rationale
  2. Every lazy-loaded page component has a route-level error boundary; a simulated component throw shows a degraded-but-functional UI rather than a blank page
  3. `madge --circular src/` reports zero circular imports after any module restructure
  4. `bandit -l -i` HIGH-severity findings fail CI; all current HIGH findings are resolved
  5. Stack patch upgrades (FastAPI 0.136, Uvicorn 0.45, SQLAlchemy 2.0.49, Alembic 1.18, Pydantic 2.13) are applied and all tests pass
**Plans:** 6 plans
- [x] 06-01-wave0-infra-parallel-small-PLAN.md — FE-01/FE-02/FE-05/FE-06/QUAL-04/QUAL-08: eslint rule flip + lint baseline, 3 vitest grep guards (FE-02/FE-05/QUAL-06-Content-Type), Tailwind v3→v4 gradient codemod, madge devDep + CI step, bandit HIGH regression test, Terraform Glacier lifecycle on crawl-data bucket (DEEP_ARCHIVE @ 90d)
- [x] 06-02-PLAN.md — FE-01/FE-04: lazyWithReload `any`→`unknown` fix, directory-chunked lint fix sweep, D-22 split `services/Api.ts` (1520 lines) into `frontend/src/api/*.ts` per backend domain (17+ modules + shared `client.ts`) with co-located response types (D-04) and unknown+narrowing (D-03)
- [x] 06-03-PLAN.md — FE-03: RouteGroupBoundary component (Sentry.ErrorBoundary + FallbackRender with eventId + Retry + Go Home) + unit test + App.tsx wiring of 4 route-group wrappers (admin/authentication/builder/public, D-07) + App.coverage.test.tsx parametrized RTL coverage with drift guard (D-10, D-24)
- [x] 06-04-PLAN.md — QUAL-05/QUAL-06 (PR-A): bump fastapi 0.128→0.136.1 + pydantic 2.11→2.13.3 in requirements.txt; rides existing guards (Phase 3 Pydantic-v1 catch_warnings + Phase 1 OpenAPI snapshot + SAFE-06 auth characterization); seed 06-HUMAN-UAT.md with QUAL-06 extension smoke-test + route-group Sentry UAT
- [x] 06-05-PLAN.md — QUAL-05 (PR-B) + D-14/D-23: bump sqlalchemy 2.0.41→2.0.49 + alembic 1.16→1.18.4 + uvicorn 0.34→0.45.0; remove python-jose from requirements.txt; delete test_pyjwt_migration.py; migrate test_auth_utils.py to PyJWT; Alembic 1.18 round-trip canary (plan 04-06)
- [x] 06-06-PLAN.md — FE-07: opportunistic polish on touched files from Plans 06-01..05 + bounded parts-catalog pass on `pages/parts/*` + `components/parts/*` ONLY (D-17); expand 06-HUMAN-UAT.md Section 4 with 5-step checklist; operator visual sign-off
**UI hint**: yes

### Phase 7: v1.0 Residue Cleanup & Audit-Drift Sync
**Goal**: Close the 22 tracked tech-debt items from the v1.0 milestone audit — operational bugs, code-review residue, dead code, integration advisory A-01, the six draft Nyquist Wave 0 validation docs, and REQUIREMENTS/ROADMAP documentation drift — before `/gsd-complete-milestone v1.0`.
**Depends on**: Phase 6
**Requirements**: None (closes `tech_debt` items from .planning/v1.0-MILESTONE-AUDIT.md, not formal REQ-IDs)
**Success Criteria** (what must be TRUE):
  1. `backend/app/core/init_service_accounts.py:53,57` uses `%s` (not `%d`) for the UUID log fields; unit test asserts cold-start service-account creation does not raise TypeError (WR-04)
  2. `backend/app/crawlers/runner.py:117-122` CRAWLER_USER_ID fallback handles UUID strings correctly; regression test covers the env-var-fallback path (WR-03)
  3. `part_linker_service.py::reelect_canonical` applies deterministic row-lock ordering (sort by id before `WHERE IN`); a multi-threaded concurrency test proves no deadlock across link_new_part / reelect_canonical / unlink_part (WR-02)
  4. `backend/pytest.ini testpaths` points at a valid directory (or is removed); `pytest -n auto` still collects the full 2154-test suite (WR-01)
  5. `build_lists.py` with-votes filter duplication (lines 153-169 / 183-198) consolidated into a shared helper (IN-01); free-tier build-list cap enforced in `copy_build_list` with a regression test (IN-02)
  6. Dead-code cleanup: `test_runner_circuit_breaker.py` stub removed; `common_patterns.py` dead helpers deleted (zero repo-wide callers); 8 legacy `db.query(...)` sites in `backend/tests/conftest.py` migrated to `select()` + `session.scalars()`
  7. Integration advisory A-01 closed: lifespan orphan-job sweep in `main.py:102-132` uses `bg_log_context`; `terraform/monitoring.tf:216` TODO resolved via per-adapter `for_each` parse-failure alarm
  8. All 6 phase `VALIDATION.md` files have `wave_0_complete: true` and `nyquist_compliant: true` (via `/gsd-validate-phase 01..06`)
  9. `REQUIREMENTS.md` traceability table: 59 rows flipped `Pending` → `Satisfied`; checkboxes `[ ]` → `[x]` for all 59 satisfied requirements (SAFE-03 remains Pending as it moves to Phase 8). `ROADMAP.md` Progress table: Phase 1/2/5/6 rows updated from "Not started" to "Complete" with actual completion dates
**Plans:** 6 plans
- [x] 07-01-operational-bug-verification-PLAN.md — WR-01/WR-02/WR-03/WR-04/IN-02 regression tests pinning already-landed Phase 4 code-review fixes (init_service_accounts %s, CRAWLER_USER_ID UUID, reelect_canonical concurrency, copy_build_list free-tier cap)
- [x] 07-02-code-review-residue-PLAN.md — IN-01 static regression for build_lists.py `_apply_build_list_filters` helper consolidation
- [x] 07-03-dead-code-cleanup-PLAN.md — delete test_runner_circuit_breaker.py stub, remove 11 common_patterns.py dead helpers (zero callers), migrate 6 legacy db.query sites in tests/conftest.py to SQLAlchemy 2.0 select()
- [x] 07-04-integration-advisory-A01-PLAN.md — wrap main.py lifespan orphan sweeps in bg_log_context + convert terraform composite alarm to per-adapter for_each (adapter_names.txt seed)
- [x] 07-05-nyquist-validation-close-PLAN.md — run `/gsd-validate-phase 01..06` and flip wave_0_complete + nyquist_compliant to true across all 6 phase VALIDATION.md files
- [x] 07-06-documentation-drift-sync-PLAN.md — flip 59 REQUIREMENTS.md traceability rows (Pending → Satisfied) and checkboxes ([ ] → [x]); update ROADMAP.md Progress table with actual Phase 1/2/4/5/6 completion dates
**Note**: Force-created by `/gsd-plan-milestone-gaps` from the `tech_debt` block of `.planning/v1.0-MILESTONE-AUDIT.md` despite the audit's empty `gaps[]` array. Scope intentionally excludes documented intentional deviations (DATA-07 pool override, AUTH-02 OAuth restructure, AUTH-03 logout gating), already-signed UAT items, and the Alembic round-trip CI automation deferred per Plan 04 D-31. SAFE-03 split to Phase 8.

### Phase 8: Frontend Coverage Expansion (SAFE-03)
**Goal**: Lift frontend test coverage from the 2026-04-22 baseline (lines 0.43% / functions 10.52% / branches 18.43% / statements 0.43%) to the D-06 targets (lines 60 / functions 50 / branches 50 / statements 60) and enforce the thresholds in `frontend/vitest.config.ts` so SAFE-03 is CI-gated.
**Depends on**: Phase 7
**Requirements**: SAFE-03
**Success Criteria** (what must be TRUE):
  1. `npm run test:coverage` in `frontend/` reports lines ≥60, functions ≥50, branches ≥50, statements ≥60
  2. The `thresholds` block in `frontend/vitest.config.ts` is uncommented and enforcing (D-06 values removed from staged-comment status)
  3. `frontend-ci.yml` fails any PR that drops coverage below the thresholds
  4. Shared test infrastructure exists for the common mock surface (axios client, AuthContext, React Router wrapper) — documented in `frontend/src/test/setup.ts` or a sibling helpers file
  5. Any files excluded from coverage via vitest `exclude` have an inline rationale comment (pure types, third-party shims)
**Note**: Reopens SAFE-03 from Phase 1 (explicitly deferred at plan 01-04 checkpoint — Option C). Frontend has 170 source files and 9 existing tests — scope is a breadth-focused test-writing pass prioritized by: (a) API client modules in `frontend/src/api/` (17+ files, high-leverage), (b) contexts and custom hooks (small surface, high branch coverage impact), (c) lazy-loaded pages (render smoke + one error path), (d) components as needed to hit thresholds. Plan count TBD during `/gsd-plan-phase 8`.

## Progress

**Execution Order:**
Phases 1 → (2 and 3 in parallel) → 4 → 5 → 6. Phase 2 and Phase 3 may run concurrently after Phase 1 completes. Phase 4 must complete before Phase 5 begins.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Safety Nets & CI Hardening | 8/8 | Complete | 2026-04-23 |
| 2. Observability | 5/5 | Complete | 2026-04-23 |
| 3. Non-Breaking Internal Improvements | 5/5 | Complete | 2026-04-22 |
| 4. DB & Parts Hardening | 6/6 | Complete | 2026-04-23 |
| 5. Structural Router Splits | 4/4 | Complete | 2026-04-23 |
| 6. Frontend Cleanup & Final CI Gates | 6/6 | Complete | 2026-04-23 |
| 7. v1.0 Residue Cleanup & Audit-Drift Sync | 6/6 | In progress | - |
| 8. Frontend Coverage Expansion (SAFE-03) | 0/TBD | Not started | - |
