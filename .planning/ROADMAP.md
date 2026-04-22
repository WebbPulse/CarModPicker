# Roadmap: CarModPicker — Tech-Debt Audit + Fix-All Milestone

## Overview

This milestone pays down eight areas of structural and operational debt across a brownfield FastAPI + React + crawler platform before it sees real traffic. The sequence is driven by three safety principles: safety nets before structural changes, observability before anything that could silently break, and data integrity hardening before high-regression-risk router splits. Every area gets fully resolved — no half-refactors.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Safety Nets & CI Hardening** - Lock in coverage floors, characterization tests, and migration guards before touching anything structural
- [ ] **Phase 2: Observability** - Add Sentry, CloudWatch crawler metrics, and alarms — additive-only, zero regression risk
- [ ] **Phase 3: Non-Breaking Internal Improvements** - Crawler hardening, adapter auto-discovery, Pydantic v1 sweep, car-data lazy-load
- [ ] **Phase 4: DB & Parts Hardening** - N+1 fix, part-link concurrency, FK index audit, session API migration, build-log eager creation
- [ ] **Phase 5: Structural Router Splits** - admin.py → admin/ package, then auth.py → auth/ package; PyJWT migration
- [ ] **Phase 6: Frontend Cleanup & Final CI Gates** - ESLint rules, type-safety, Tailwind v4 patterns, error boundaries, bandit/dep upgrades

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
- [ ] 01-01-PLAN.md — SAFE-09: apply `MetaData(naming_convention=...)` to declarative Base + unit test pinning the 5 convention keys
- [ ] 01-02-PLAN.md — SAFE-08: repair three `op.drop_constraint(None, ...)` migrations (prod-state checkpoint + in-place or forward-only repair)
- [ ] 01-03-PLAN.md — SAFE-04: migration DROP-guard script, unit tests, CI step in backend-ci.yml
- [ ] 01-04-PLAN.md — SAFE-01/02/03: measure coverage baselines (checkpoint) + `--cov-fail-under` + vitest thresholds + frontend `Run tests` CI step
- [ ] 01-05-PLAN.md — SAFE-05: OpenAPI schema snapshot test + committed fixture
- [ ] 01-06-PLAN.md — SAFE-06: 7 auth characterization tests (VCR cassettes + WebAuthn mocks) + secret-audit guardrail
- [ ] 01-07-PLAN.md — SAFE-07: 5 crawler adapter characterization tests against archived HTML fixtures (2× tier0_http + 2× tier2_browser + 1× tier1_tls)
- [ ] 01-08-PLAN.md — SAFE-10: `.github/dependabot.yml` (weekly Monday, pip + npm multi-dir + github-actions, minor+patch grouping, no ignore block)

### Phase 2: Observability
**Goal**: Production errors are visible in Sentry, per-adapter crawler metrics flow into CloudWatch, and a parse-failure alarm fires automatically — all without changing any URL, schema, or external contract
**Depends on**: Phase 1
**Requirements**: OBS-01, OBS-02, OBS-03, OBS-04, OBS-05
**Success Criteria** (what must be TRUE):
  1. Unhandled exceptions in the FastAPI app appear in Sentry with request ID, user ID, and SQLAlchemy query context attached
  2. After a crawler run, CloudWatch shows per-adapter `Ingested`, `ParseFailures`, and `ElapsedSeconds` metrics in the `CarModPicker/Crawlers` namespace
  3. A CloudWatch alarm triggers an SNS → SES email when any adapter's parse-failure rate exceeds 50%
  4. Frontend runtime errors appear in Sentry (or equivalent) via an `ErrorBoundary` integration
**Plans**: TBD
**Note**: Phase 2 is additive-only (no URL/model/schema changes). It may execute concurrently with Phase 3 — both are low regression risk after Phase 1 completes.

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
**Plans**: TBD
**Note**: Phase 3 may execute concurrently with Phase 2. Internal ordering within this phase: CRAWL-01/02/03 (auto-discovery + validation) must complete and count-assert green before CRAWL-05 (parallelization) lands.

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
**Plans**: TBD

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
**Plans**: TBD
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
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases 1 → (2 and 3 in parallel) → 4 → 5 → 6. Phase 2 and Phase 3 may run concurrently after Phase 1 completes. Phase 4 must complete before Phase 5 begins.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Safety Nets & CI Hardening | 0/8 | Not started | - |
| 2. Observability | 0/TBD | Not started | - |
| 3. Non-Breaking Internal Improvements | 0/TBD | Not started | - |
| 4. DB & Parts Hardening | 0/TBD | Not started | - |
| 5. Structural Router Splits | 0/TBD | Not started | - |
| 6. Frontend Cleanup & Final CI Gates | 0/TBD | Not started | - |
