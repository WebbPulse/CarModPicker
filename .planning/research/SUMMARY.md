# Project Research Summary

**Project:** CarModPicker
**Domain:** Tech-debt audit + refactor milestone on a mature brownfield FastAPI + React + Python crawler platform
**Researched:** 2026-04-21
**Confidence:** HIGH

## Executive Summary

CarModPicker is a production-deployed, brownfield platform at a critical inflection point: low external traffic means this is the last safe window to pay down structural debt before the codebase sees real load. The stack is architecturally sound — FastAPI, SQLAlchemy 2.0, React 19, PostgreSQL 16, AWS App Runner — and current or one upgrade cycle behind at worst. The debt is organizational and operational, not foundational: files have grown beyond maintainable size (`admin.py` 2,055 lines, `auth.py` 1,195 lines, `car_generations_data.py` 8,412 lines), critical observability is absent (no Sentry, no crawler metrics, no CloudWatch alarms), CI has gaps (no frontend tests, no coverage floor), and three Alembic migrations contain `op.drop_constraint(None, ...)` — latent prod failures on any `downgrade`.

The recommended approach is surgical and sequenced: safety nets first (CI coverage gates, characterization tests, OpenAPI snapshot tests), then additive observability (Sentry + CloudWatch), then non-breaking internal improvements (lazy-load JSON, circuit breaker swap, adapter auto-discovery), and finally the highest-regression-risk structural changes (auth and admin router splits). Every structural change must be preceded by characterization tests; every migration must be validated against real Postgres, not just SQLite. The three existing unnamed constraints must be fixed before any new migration work begins.

The primary execution risks are: a refactor death spiral (eight things half-done), double-maintenance trap (old and new code coexisting), and SQLite/PostgreSQL divergence (tests green, prod broken). All three are preventable with rigid phase discipline: binary done-states, old code deleted in the same PR that adds new code, and migration validation against a Postgres Docker instance. The milestone does not introduce new product features — it is a cleanup arc that prepares the foundation for the next milestone's data enrichment and LLM build-helper work.

## Key Findings

### Recommended Stack

The existing stack is appropriate and should not change this milestone. See `STACK.md` for the full catalog of current idioms, anti-patterns to sweep, and version targets.

**Must-upgrade (non-optional):**
- **FastAPI 0.128 → 0.136** — strict `Content-Type` checking on JSON POSTs introduced in 0.136. Chrome extension must be audited for `Content-Type: application/json` on every POST before upgrading.
- **python-jose → PyJWT 2.12.1** — python-jose unmaintained since 2021; FastAPI docs officially recommend PyJWT. CVE-2024-33663 affects python-jose when `algorithms` isn't specified. Migration is find-replace: `JWTError` → `InvalidTokenError`.

**Should-upgrade (patch-level, safe):** Uvicorn 0.34→0.45, SQLAlchemy 2.0.41→2.0.49, Alembic 1.16→1.18, Pydantic 2.11→2.13.

**Do-not-touch this milestone:** Sync SQLAlchemy + psycopg2 (async migration is premature at current traffic), React Router mode (Vite SPA is correct), axios.

**Anti-patterns to sweep during refactor:**
- `session.query()` legacy API → `select()` + `session.scalars()`
- Pydantic v1 patterns: `@validator`, `class Config:`, `.dict()`, `.parse_obj()` → v2 equivalents
- `logger` via `Depends()` → module-level `logging.getLogger(__name__)`
- Tailwind v3 `bg-gradient-to-*` → v4 `bg-linear-to-*`
- `process.env` in frontend → `import.meta.env.VITE_*`

### Expected Features (Quality Capabilities)

See `FEATURES.md` for full catalog with complexity ratings and debt-area mapping.

**Table stakes (all S/M complexity, all trace to CONCERNS.md gaps):**
- Sentry SDK integration (S) — ends flying blind in production
- Frontend tests in CI (S) — currently missing from `frontend-ci.yml`
- Backend `--cov-fail-under=70` (S) — no coverage floor today
- Migration DROP guard CI step (S) — catches `drop_constraint`/`drop_column` without annotation
- Fix 3 unnamed-constraint migrations (S) — `097024200e60`, `172d1c205fb3`, `6eae6b1393c5`
- Add `naming_convention` to SQLAlchemy `MetaData` (S) — prevents future unnamed constraints
- Per-adapter CloudWatch metrics (M) — `Ingested`, `ParseFailures`, `ElapsedSeconds` in `CarModPicker/Crawlers`
- CloudWatch parse-failure alarm (S) — SNS → SES when failure rate > 50%
- Pre-crawl health check (S) — `robots.txt` fetch before hammering rate-limited retailers
- Circuit breaker threshold 5 → 2–3 via `pybreaker` (S)
- N+1 fix + regression gate (M) — `selectinload` + query-count assertion, same PR
- Concurrency test for part linking (M) — 10-thread ThreadPoolExecutor simulating simultaneous link/unlink
- Adapter auto-discovery (M) — `importlib` + `pkgutil.iter_modules`, CI asserts count == 114
- FK index audit across 22+ models (M)
- DB pool resize for parallel crawlers (S) — `DB_POOL_SIZE=50`, `pool_pre_ping=True`

**Differentiators (selective):**
- Optimistic concurrency on parts (P2, deferred — architecture research recommends `SELECT FOR UPDATE` instead)
- S3 lifecycle policy on crawl archive (30-min Terraform task)
- `pytest-capquery` N+1 regression gate

**Anti-features / Out of Scope (do NOT build):**
- Prometheus + Grafana (CloudWatch is equivalent at zero ops cost)
- Microservices split for crawler (App Runner + ECS Fargate already isolates)
- Kubernetes migration
- LLM-based scraping
- New user-facing features
- Deep security hardening / SOC2 / pen-testing
- Mobile app, WebSocket crawler progress, SBOM, Pact contract tests, LaunchDarkly, error-budget deploys, OpenAPI Pact
- Full catalog UX redesign (opportunistic UX only)
- Payment / subscription tier rework

### Architecture Approach

See `ARCHITECTURE.md` for the full refactor pattern catalog with code sketches.

Targeted surgery on five debt clusters within the existing N-tier shape. The `BaseEndpointRouter` / `BaseCRUDService` / `EndpointRegistry` abstractions are preserved and extended. No deployment changes.

**Major module changes:**
1. `auth.py` (1,195 lines) → `auth/` package (`core.py`, `two_factor.py`, `webauthn.py`, `oauth.py` + `_helpers.py`). URL prefix stays in `main.py`; zero external route changes.
2. `admin.py` (2,055 lines) → `admin/` package (`stats.py`, `jobs.py`, `crawlers.py`, `db_ops.py`, `parts.py`). Service deps injected via `Depends()`.
3. `car_generations_data.py` (8,412-line Python literal) → JSON + `@functools.lru_cache(maxsize=1)` loader.
4. `adapters/__init__.py` (114 manual imports) → directory-scan auto-discovery; `ADAPTER_NAME: ClassVar[str]` on base.
5. Crawler parallelism: bounded `ThreadPoolExecutor` per-adapter session; `pybreaker` circuit breaker.
6. Observability: Sentry SDK + CloudWatch custom metrics namespace.
7. Part-link concurrency: `SELECT ... FOR UPDATE` via `.with_for_update()` (pessimistic; correct for low-frequency admin op).

**Integration contracts that must NOT break:**
- Chrome extension auth flow → `/api/auth/*` URL paths unchanged after split
- EventBridge → `/api/cron/run-crawler-schedule` — stays in `admin/crawlers.py`

### Critical Pitfalls

See `PITFALLS.md` for full catalog with warning signs, prevention strategies, and debt-area mapping. Top 7, all HIGH severity:

1. **Refactor death spiral** — Binary done-states required: old code deleted, CI green, coverage maintained. No "mostly done." Applies to every phase.
2. **Three unnamed Alembic constraints** — `097024200e60`, `172d1c205fb3`, `6eae6b1393c5` all have `op.drop_constraint(None, ...)` — latent prod failures on downgrade. Fix before any new migration work.
3. **Characterization tests must precede structural splits** — VCR + OpenAPI snapshot test before touching `auth.py` or `admin.py`. Auth is the Chrome extension critical path.
4. **SQLite/Postgres divergence** — CI uses SQLite; prod is PG16. `pg_insert` already in `runner.py`. Any upsert/`ON CONFLICT`/`RETURNING` must be tested against Postgres Docker.
5. **Adapter auto-discovery dropout** — Silent drops on `ImportError`. Mitigation: catch + log + CI asserts count.
6. **N+1 reintroduction without regression gate** — `selectinload` fix alone is insufficient; query-count assertion must land in same PR.
7. **FastAPI `Depends()` auth loss during router split** — Every admin sub-router route must explicitly redeclare `Depends(get_current_admin_user)`. Test 401/403 per route.

**Divergence between researchers (resolved):** ARCHITECTURE.md recommends `SELECT FOR UPDATE` (pessimistic); FEATURES.md lists optimistic `version_id_col` as P2. **Decision: use `SELECT FOR UPDATE` — simpler, no migration, correct for actual access pattern.**

## Implications for Roadmap

All three research dimensions (architecture, features, pitfalls) converge on the same six-phase structure. Sequence is driven by three safety principles:

1. **Observability + tests before structural changes** (coverage gates live before code moves; Sentry live before structural work).
2. **Data safety before structural splits** (DB phase before router splits; avoid concurrent migration + split windows).
3. **Metrics before alarms before canary** (CloudWatch metrics unlock alarms unlock future canary work).

### Phase 1: Safety Nets + CI Hardening

**Rationale:** Nothing downstream is safe without this. All items are S-complexity. Zero regression risk. Unlocks every other phase.

**Delivers:**
- `--cov-fail-under=70` in `pytest.ini` (measure baseline first, set floor at baseline)
- `npm test -- --run` in `frontend-ci.yml`
- Migration DROP guard CI step (grep-based)
- OpenAPI schema snapshot test
- Auth characterization tests (5+ flows via `pytest-recording`)
- Crawler adapter VCR tests (5+ adapters against S3 archive HTML)
- Fix three `op.drop_constraint(None, ...)` migrations
- Add `naming_convention` to SQLAlchemy `MetaData`
- Dependabot configuration

**Addresses:** CONCERNS.md test coverage gaps; PITFALLS.md Pitfalls 1, 2, 3, 10.
**Gate:** Must complete before Phase 5 starts.

### Phase 2: Observability + Quick Configuration Wins

**Rationale:** Additive-only — no URL changes, no model changes, zero regression risk. Gets production visibility live before structural work.

**Delivers:**
- Sentry SDK in `main.py`
- CloudWatch custom metrics per adapter (`CarModPicker/Crawlers` namespace)
- CloudWatch alarm on parse-failure rate > 50%
- `pybreaker` circuit breaker (`fail_max=3`, `reset_timeout=120`)
- `DB_POOL_SIZE=50`, `pool_pre_ping=True`, `pool_recycle=1800`
- Pre-crawl health check (robots.txt, 5s timeout)

**Addresses:** CONCERNS.md observability gaps; FEATURES.md table stakes.
**Uses:** `sentry-sdk[fastapi]`, boto3 `put_metric_data`, `pybreaker`.

### Phase 3: Non-Breaking Internal Improvements

**Rationale:** Internal behavior changes without touching URLs, schemas, or external contracts. Auto-discovery must be validated before parallelization.

**Delivers:**
- `car_generations_data.py` → JSON + `lru_cache` loader
- Adapter auto-discovery (CI asserts count == 114)
- Semaphore-bounded parallel adapter execution
- `@app.on_event()` removal audit
- Pydantic v1 anti-pattern sweep (`@validator` → `field_validator`, `.dict()` → `model_dump()`, etc.)

**Ordering within phase:** Auto-discovery → validate count → enable parallelization.

### Phase 4: DB + Parts Hardening

**Rationale:** Schema work is highest-risk for data integrity. Depends on Phase 1 safety nets. N+1 fix + regression gate must land same PR.

**Delivers:**
- N+1 fix in `build_logs.py:119` with query-count regression assertion
- `SELECT FOR UPDATE` on part-link endpoints
- Concurrency test for part linking (10-thread race simulation)
- FK index audit + `Index()` declarations across 22+ models
- Migration downgrade testing against Postgres Docker (new CONVENTIONS.md rule)
- `session.query()` → `select()` + `session.scalars()` sweep
- Build log auto-creation moved from lazy → eager (on build-list creation)

**Addresses:** CONCERNS.md N+1 bug, fragile part-linking races, index gaps; PITFALLS.md Pitfalls 4, 6.

### Phase 5: Structural Router Splits (admin then auth)

**Rationale:** Highest regression risk. Requires Phase 1 characterization tests green. Admin split first (not in Chrome extension critical path), validate, then auth split.

**Delivers:**
- `admin/` package (5 sub-routers); old `admin.py` deleted in same PR
- `auth/` package (4 sub-routers); old `auth.py` deleted in same PR
- 401/403 integration tests for every new admin sub-router route
- `chrome-extension/API_CONTRACT.md` documented
- Chrome extension auth flow validated end-to-end
- python-jose → PyJWT 2.12.1 migration (paired with auth split)

**Ordering:** D1 (admin) → validate in CI → D2 (auth) → validate extension.

### Phase 6: Frontend Cleanup + Test Coverage

**Rationale:** Largely independent of backend phases. Benefits from Sentry being live for FE exceptions. Deferred until backend structural work stabilizes.

**Delivers:**
- Vitest coverage threshold (`lines: 60`)
- eslint `no-explicit-any: error` + `no-unsafe-*` rules
- `import.meta.env` audit (remove `process.env` leftovers)
- `bandit -l -i` threshold (HIGH severity fails CI)
- Route-level error boundaries on all lazy-loaded pages
- `madge --circular` check before/after module restructures
- Tailwind v3 pattern cleanup
- API response `any`-cast audit
- Opportunistic UX polish on touched pages (parts catalog is the known rough spot)

### Phase Ordering Rationale

- **Phase 1 before Phase 5** (HARD dependency): characterization tests must be CI-green before auth/admin splits. All three pitfall-class researchers independently concluded this.
- **Phase 4 before Phase 5**: avoid concurrent migration + router split change windows.
- **Phase 2 additive-only** (no URL/model changes): can land anytime after Phase 1 with low risk.
- **Phase 3 before Phase 5**: auto-discovery validated before adapter parallelization; lazy-load JSON unblocks dev-speed improvements.
- **Admin split before auth split** (within Phase 5): admin is not in Chrome extension critical path; validate split pattern before highest-stakes refactor.
- **Quick-win clustering**: Sentry + `--cov-fail-under` + frontend CI tests + migration DROP guard are all S-complexity and cluster in Phases 1–2 so every subsequent phase has a safety net.

### Research Flags

**No phase requires a dedicated `/gsd-research-phase` cycle.** All patterns are implementation-ready with concrete code examples in the research files.

- Phase 1: Standard patterns (`pytest-recording`, CI scripting, OpenAPI snapshot)
- Phase 2: Standard patterns (Sentry FastAPI integration is turnkey; CloudWatch `PutMetricData` is standard boto3)
- Phase 3: Standard patterns (`lru_cache`, `pkgutil.iter_modules`, `pybreaker` all documented)
- Phase 4: Standard patterns (SQLAlchemy `selectinload`/`with_for_update`/Alembic naming conventions)
- Phase 5: Standard patterns (FastAPI `include_router` sub-package structure is documented)
- Phase 6: Standard patterns (ESLint config, Vitest coverage, Tailwind v4)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified via PyPI/npm live fetch; idioms verified via official docs via Context7. FastAPI 0.136 breaking change and PyJWT migration confirmed. |
| Features | HIGH | All P1 items trace to CONCERNS.md gaps. Complexity estimates grounded in actual codebase. |
| Architecture | HIGH | Patterns verified vs. FastAPI + SQLAlchemy 2.0 docs. File paths and line numbers from actual codebase. |
| Pitfalls | HIGH | All critical pitfalls trace to specific files/line numbers. Three unnamed constraints confirmed by direct inspection. Frontend CI gap confirmed against actual `frontend-ci.yml`. |

**Overall confidence:** HIGH

### Gaps to Address During Planning

- **Postgres Docker test environment** — Phase 4 needs a `docker-compose` step for migration-specific CI. Decide at Phase 4 planning time.
- **`lazy="raise"` scope** — Full audit of all `relationship()` declarations across 22+ models to scope at Phase 4 planning.
- **`chrome-extension/API_CONTRACT.md` content** — Assembled from reading `chrome-extension/src/background.ts`; one-session task during Phase 5.
- **Backend coverage baseline** — Must be measured (`pytest --cov=app`) before Phase 1 sets `--cov-fail-under`. Set floor at measured baseline, raise incrementally.
- **Canary adapter selection** — Which retailer adapter is "most stable" is best determined from Phase 2 CloudWatch metrics data, not decided in advance.

## Top 5 Roadmap Implications

1. **Phase 1 is a strict prerequisite for Phase 5.** Hard dependency: characterization tests must be CI-green before auth/admin splits begin. Not a soft recommendation — three pitfall-class researchers independently concluded this.
2. **Three migrations need surgical repair before Phase 4 begins.** `op.drop_constraint(None, ...)` in `097024200e60`, `172d1c205fb3`, `6eae6b1393c5` will fail on real `alembic downgrade`. Fix them in Phase 1.
3. **Admin split before auth split, always.** Admin is not in the Chrome extension critical path. Auth is. D1 before D2 uses admin as the dry-run for the split pattern.
4. **Quick wins cluster in Phases 1–2.** Sentry, `--cov-fail-under`, migration DROP guard, frontend tests in CI — all S-complexity, all unlock downstream safety.
5. **Adapter parallelization gated on auto-discovery count validation.** If the registry silently drops adapters due to import errors, running them in parallel makes diagnosis harder. CI count assertion must be green before parallelization lands.

## Sources

### Primary (HIGH confidence)
- PyPI live version data (FastAPI, PyJWT, Uvicorn, SQLAlchemy, Pydantic, Alembic) — version currency
- Context7: FastAPI official docs — `include_router`, `lifespan`, dependency injection, router composition
- Context7: SQLAlchemy 2.0 docs — `select()`, `selectinload`, `with_for_update`, `naming_convention`, `Mapped[]`
- Context7: Pydantic v2 docs — migration anti-patterns
- Context7: Tailwind v4 migration guide — v3 class renames
- `.planning/codebase/CONCERNS.md` — direct file inspection (3 migrations, auth.py, admin.py, car_generations_data.py, build_logs.py:119)
- `.planning/codebase/ARCHITECTURE.md`, `STRUCTURE.md`, `STACK.md`, `CONVENTIONS.md`, `INTEGRATIONS.md`, `TESTING.md` — current-state references

### Secondary (MEDIUM confidence)
- AWS App Runner + RDS operational best practices (WebSearch + AWS docs, not direct Terraform inspection)
- `pybreaker` integration patterns (library docs, not production-battle-tested here)
- ThreadPoolExecutor sizing heuristics for crawler parallelization

---
*Research completed: 2026-04-21*
*Ready for roadmap: yes*
