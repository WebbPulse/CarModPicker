# Requirements: CarModPicker — Tech-Debt Audit + Fix-All Milestone

**Defined:** 2026-04-21
**Core Value:** A single, coherent place to discover, price, and plan car modifications across fragmented retailer and enthusiast sources.
**Milestone goal:** Pay down structural/operational debt across 8 areas while the platform is in low-traffic production, so the next milestone (data enrichment + user-facing planner tooling) builds on a sound foundation.
**Approach:** Audit + fix-all. Every area gets inventoried; every issue identified gets resolved before phase close. No half-refactors.

## v1 Requirements

Requirements for this milestone. Each maps to exactly one roadmap phase (see Traceability).

### Safety Nets & CI Gates

- [x] **SAFE-01
**: Backend `pytest.ini` enforces `--cov-fail-under=<measured baseline>` so coverage cannot silently drop
- [x] **SAFE-02
**: `frontend-ci.yml` runs `npm test -- --run` on every PR (currently absent)
- [ ] **SAFE-03**: Vitest config enforces a coverage threshold (`lines: 60`) for frontend
- [x] **SAFE-04
**: CI step fails any PR whose migration contains `drop_column`, `drop_table`, or `drop_constraint` without an explicit `# SAFE: <reason>` annotation
- [ ] **SAFE-05**: OpenAPI schema snapshot test catches unintended route/schema drift
- [ ] **SAFE-06**: Auth characterization tests cover signup, verify-email, login, 2FA-TOTP, WebAuthn, OAuth, password-reset happy paths via `pytest-recording` before the auth refactor starts
- [x] **SAFE-07
**: Crawler adapter VCR-style tests cover ≥5 representative adapters against archived S3 HTML before crawler refactor starts
- [x] **SAFE-08
**: Three migrations containing `op.drop_constraint(None, ...)` (`097024200e60`, `172d1c205fb3`, `6eae6b1393c5`) are surgically repaired
- [ ] **SAFE-09**: SQLAlchemy `MetaData` uses an explicit `naming_convention` so future autogen produces named constraints
- [x] **SAFE-10
**: Dependabot or equivalent configured for weekly dependency PRs on backend + frontend + extension

### Observability

- [ ] **OBS-01**: Sentry SDK initialized in `backend/app/main.py` with `FastApiIntegration` + `SqlalchemyIntegration`, `traces_sample_rate=0.05`, `send_default_pii=False`
- [ ] **OBS-02**: Per-adapter CloudWatch custom metrics emitted in `CarModPicker/Crawlers` namespace (`Ingested`, `ParseFailures`, `ElapsedSeconds`)
- [ ] **OBS-03**: CloudWatch alarm on per-adapter `ParseFailures` rate > 50% with SNS → SES notification
- [ ] **OBS-04**: Request-ID propagation audit — every log line produced during a request includes the request_id and user_id
- [ ] **OBS-05**: Frontend errors captured by Sentry (or equivalent) via `@sentry/react` wired into `ErrorBoundary`

### Crawler System Hardening

- [ ] **CRAWL-01**: Adapter auto-discovery via `importlib` + `pkgutil.iter_modules` replaces the hand-maintained `adapters/__init__.py` registry
- [ ] **CRAWL-02**: `ADAPTER_NAME: ClassVar[str]` enforced on every `RetailerCrawlerAdapter` subclass; CI asserts discovered count equals expected
- [ ] **CRAWL-03**: Adapter import errors are caught, logged at ERROR, and fail CI rather than silently dropping adapters
- [ ] **CRAWL-04**: Rate-limit circuit breaker replaced with `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)`; 429/503 status triggers immediate bail
- [ ] **CRAWL-05**: Per-adapter `run_crawler` execution runs under a bounded `ThreadPoolExecutor` sized to `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE`, each worker with its own `SessionLocal()`
- [ ] **CRAWL-06**: Per-adapter pre-crawl health check (fetch `robots.txt` with 5s timeout) skips and emits metric on 4xx/5xx/timeout
- [ ] **CRAWL-07**: Parse-failure reporting bubbles into the job report email with per-adapter failure counts and retailer URL samples

### Database, Migrations & Performance

- [x] **DATA-01
**: N+1 query in `backend/app/api/endpoints/build_logs.py:119` (`DBUser` fetch inside post loop) replaced with `selectinload(Post.author)` batch fetch
- [x] **DATA-02
**: A query-count regression test asserts the N+1 fix stays fixed
- [x] **DATA-03
**: Part-linking endpoints use `.with_for_update()` (pessimistic row lock) to eliminate race conditions on canonical linking/unlinking
- [x] **DATA-04
**: Concurrency test (10-thread `ThreadPoolExecutor`) simulates simultaneous part link/unlink and asserts no orphaned / circular canonical references
- [x] **DATA-05
**: FK index audit across all 22+ models — missing indexes on join keys added via `Index()` declarations
- [x] **DATA-06
**: `session.query()` legacy API calls replaced with `select()` + `session.scalars()` across the codebase
- [x] **DATA-07
**: Production DB pool config: `DB_POOL_SIZE=50`, `pool_pre_ping=True`, `pool_recycle=1800`; `API_CONNECTION_RESERVE` sized for parallel crawlers
- [x] **DATA-08
**: Build-log creation moved from lazy (auto-create mid-request in `build_logs.py:87-98`) to eager (created alongside the parent build list); inconsistent-state branch eliminated
- [ ] **DATA-09**: Alembic migration workflow documented in CONVENTIONS.md to require downgrade testing against a Postgres Docker instance before merge
- [ ] **DATA-10**: `lazy="raise"` applied to relationships known to trigger silent N+1s; every refactor-phase test run is green under that constraint

### Parts & Canonical Dedup Consolidation

- [x] **PARTS-01**: Part-linking race condition eliminated (covered by DATA-03
/DATA-04; cross-referenced here for traceability)
- [ ] **PARTS-02**: `car_inference.py` ambiguity resolution reviewed — `AMBIGUOUS_STANDALONE_CODES` set is documented + a regression test pins current behavior; no new ML logic this milestone, just maintainability
- [ ] **PARTS-03**: Canonical-part flow (create, link, unlink, merge) has integration test coverage matching PROJECT.md's Validated behavior

### Auth Refactor

- [ ] **AUTH-01**: `backend/app/api/endpoints/auth.py` (1,195 lines) decomposed into an `auth/` package (`core.py`, `two_factor.py`, `webauthn.py`, `oauth.py`, `_helpers.py`); old file deleted in the same PR
- [ ] **AUTH-02**: URL prefix `/api/auth/*` routes remain identical after split (Chrome extension critical path)
- [ ] **AUTH-03**: Each sub-router route explicitly redeclares its `Depends(get_current_user)` or equivalent auth dependency; no implicit auth loss
- [ ] **AUTH-04**: `python-jose` replaced with `PyJWT 2.12.1`; `JWTError` → `InvalidTokenError`; algorithm explicitly specified on every decode call
- [ ] **AUTH-05**: Chrome extension end-to-end auth flow validated post-refactor (login, token handoff, logout)
- [ ] **AUTH-06**: `chrome-extension/API_CONTRACT.md` documents every endpoint the extension calls, including request/response shapes

### Admin Module Split

- [ ] **ADMIN-01**: `backend/app/api/endpoints/admin.py` (2,055 lines) decomposed into `admin/` package (`stats.py`, `jobs.py`, `crawlers.py`, `db_ops.py`, `parts.py`); old file deleted in same PR
- [ ] **ADMIN-02**: Every admin sub-router route has explicit `Depends(get_current_admin_user)` or superuser variant; 401/403 integration test per route
- [ ] **ADMIN-03**: EventBridge contract `/api/cron/run-crawler-schedule` route stays on the same path (lives in `admin/crawlers.py`)
- [ ] **ADMIN-04**: Service-level coupling reduced — admin sub-routers inject specific services via `Depends()`, not a single god-service

### Frontend Structure & Quality

- [ ] **FE-01**: `eslint` configured with `@typescript-eslint/no-explicit-any: error` and `no-unsafe-*` rules; existing violations fixed or explicitly allow-listed with rationale
- [ ] **FE-02**: `import.meta.env.VITE_*` audit — any lingering `process.env` references removed
- [ ] **FE-03**: Route-level error boundaries on every lazy-loaded page component
- [ ] **FE-04**: API client types narrowed — `any`-cast audit on response types with either strict typing or `unknown` + runtime validation
- [ ] **FE-05**: Tailwind v3 class sweep — `bg-gradient-to-*` → `bg-linear-to-*`, any surviving `@tailwind base/components/utilities` → `@import "tailwindcss"`, default border/divide color regression caught
- [ ] **FE-06**: `madge --circular` check runs before and after module restructures; no new circular imports introduced
- [ ] **FE-07**: Opportunistic UX polish on any page refactored this milestone; parts catalog explicitly in scope when its frontend touches land

### General Code-Quality Sweep

- [ ] **QUAL-01**: `car_generations_data.py` (8,412-line Python literal) replaced with a JSON file + `@functools.lru_cache(maxsize=1)` loader; uvicorn `--reload` startup latency measurably improves
- [ ] **QUAL-02**: Pydantic v1 pattern sweep — `@validator` → `@field_validator`, `class Config:` → `model_config`, `.dict()` → `model_dump()`, `.parse_obj()` → `model_validate()`; zero v1 deprecation warnings in test run
- [ ] **QUAL-03**: `@app.on_event()` decorator audit — any residual decorators removed in favor of the existing `lifespan` hook
- [ ] **QUAL-04**: `bandit -l -i` gated in CI; HIGH-severity findings fail the build
- [ ] **QUAL-05**: Stack patch upgrades applied in a dedicated dependency-upgrade step: FastAPI 0.136, Uvicorn 0.45, SQLAlchemy 2.0.49, Alembic 1.18, Pydantic 2.13
- [ ] **QUAL-06**: FastAPI 0.136 strict-Content-Type upgrade compatibility: Chrome extension POSTs audited for `Content-Type: application/json` headers before upgrade merged
- [ ] **QUAL-07**: `logger` usage migrated from `Depends()` injection to module-level `logging.getLogger(__name__)` where found
- [ ] **QUAL-08**: S3 lifecycle policy on `carmodpicker-prod-user-images` (or the crawl-archive bucket) transitions old HTML snapshots to Glacier after 90 days

## v2 Requirements

Deferred to the next milestone (data enrichment + user-facing planner tooling).

### Data Enrichment
- **ENRICH-01**: Rich structured extraction from scraped pages (specs, attributes, compatibility hints) beyond bare descriptions
- **ENRICH-02**: Per-adapter schema contract for structured fields extracted
- **ENRICH-03**: Price-history derivation from repeated scrapes of the same product
- **ENRICH-04**: Transformative-use positioning — derived comparative data as the user-facing output

### LLM-Assisted User Tools (post-enrichment)
- **LLM-01**: Build helper — LLM suggests parts that fit the user's car + compatibility + budget
- **LLM-02**: Build planner — LLM decomposes a goal (e.g., "daily driver → track car") into a phased parts list
- **LLM-03**: Part-page summarization for research

### Observability Deepening
- **OBS-V2-01**: Distributed tracing via OpenTelemetry (X-Ray compatible) — deferred; CloudWatch Logs Insights + Sentry covers 90% at current traffic
- **OBS-V2-02**: Synthetic monitoring / canary crawler runs on one "most stable" adapter

### Parts Data Model Deepening
- **PARTS-V2-01**: `car_inference` ML-assisted disambiguation (keyword embeddings) to replace the hand-maintained ambiguity set
- **PARTS-V2-02**: Admin UI for part-curation-time ambiguity resolution
- **PARTS-V2-03**: Optimistic concurrency (`version_id_col`) if `SELECT FOR UPDATE` proves insufficient at higher traffic

### Performance
- **PERF-V2-01**: Query-result caching (Redis or in-memory) for slow-moving reference data (cars, categories, part manufacturers)
- **PERF-V2-02**: Read replicas for report/stat queries if admin dashboard pressure grows
- **PERF-V2-03**: Async SQLAlchemy migration (deferred until traffic demands it)

### UX
- **UX-V2-01**: Full parts-catalog UX redesign (beyond opportunistic polish)
- **UX-V2-02**: Social / build-log expansion (intentionally thin in v1 per PROJECT.md)

## Out of Scope

Explicitly excluded from this milestone. Documented here to prevent scope creep.

| Feature | Reason |
|---------|--------|
| LLM-based scraping/extraction pipeline | Cost-prohibitive until business model proves; user-facing LLM tools are v2 |
| Deep security hardening (SOC2, pen-testing, compliance arc) | Target attainable 90%; not a B2B SaaS |
| New user-facing features | Cleanup arc — no new product surface this milestone |
| Microservices split for crawler subsystem | App Runner + ECS Fargate already provides isolation |
| Kubernetes migration | App Runner is fit-for-purpose |
| Prometheus + Grafana stack | CloudWatch covers the need at zero ops cost |
| LaunchDarkly / Flagsmith | DB-table feature flags sufficient for near-term |
| OpenAPI Pact contract tests | pyright + TS-generated API client already serves as contract in a monorepo |
| Error-budget-based deploys | No SLO baseline yet; instrument first |
| Mobile app | Web + extension only this milestone |
| WebSocket crawler progress | Crawler is async batch; progress via CloudWatch, not WebSocket |
| SBOM generation | Defer until compliance-driven |
| Async SQLAlchemy migration | Major refactor; premature at current traffic |
| React Router framework/SSR mode | Vite SPA is correct architecture |
| Full parts-catalog UX redesign | Opportunistic only this milestone; dedicated UX milestone later |
| Payment / subscription tier rework | Current system stands as-is |
| Full canonical parts redesign | Recent refactor is the direction; consolidate, don't rebuild |

## Traceability

Populated during roadmap creation (2026-04-21).

| Requirement | Phase | Status |
|-------------|-------|--------|
| SAFE-01 | Phase 1 | Pending |
| SAFE-02 | Phase 1 | Pending |
| SAFE-03 | Phase 1 | Pending |
| SAFE-04 | Phase 1 | Pending |
| SAFE-05 | Phase 1 | Pending |
| SAFE-06 | Phase 1 | Pending |
| SAFE-07 | Phase 1 | Pending |
| SAFE-08 | Phase 1 | Pending |
| SAFE-09 | Phase 1 | Pending |
| SAFE-10 | Phase 1 | Pending |
| OBS-01 | Phase 2 | Pending |
| OBS-02 | Phase 2 | Pending |
| OBS-03 | Phase 2 | Pending |
| OBS-04 | Phase 2 | Pending |
| OBS-05 | Phase 2 | Pending |
| CRAWL-01 | Phase 3 | Pending |
| CRAWL-02 | Phase 3 | Pending |
| CRAWL-03 | Phase 3 | Pending |
| CRAWL-04 | Phase 3 | Pending |
| CRAWL-05 | Phase 3 | Pending |
| CRAWL-06 | Phase 3 | Pending |
| CRAWL-07 | Phase 3 | Pending |
| QUAL-01 | Phase 3 | Pending |
| QUAL-02 | Phase 3 | Pending |
| QUAL-03 | Phase 3 | Pending |
| QUAL-07 | Phase 3 | Pending |
| DATA-01 | Phase 4 | Pending |
| DATA-02 | Phase 4 | Pending |
| DATA-03 | Phase 4 | Pending |
| DATA-04 | Phase 4 | Pending |
| DATA-05 | Phase 4 | Pending |
| DATA-06 | Phase 4 | Pending |
| DATA-07 | Phase 4 | Pending |
| DATA-08 | Phase 4 | Pending |
| DATA-09 | Phase 4 | Pending |
| DATA-10 | Phase 4 | Pending |
| PARTS-01 | Phase 4 | Pending |
| PARTS-02 | Phase 4 | Pending |
| PARTS-03 | Phase 4 | Pending |
| ADMIN-01 | Phase 5 | Pending |
| ADMIN-02 | Phase 5 | Pending |
| ADMIN-03 | Phase 5 | Pending |
| ADMIN-04 | Phase 5 | Pending |
| AUTH-01 | Phase 5 | Pending |
| AUTH-02 | Phase 5 | Pending |
| AUTH-03 | Phase 5 | Pending |
| AUTH-04 | Phase 5 | Pending |
| AUTH-05 | Phase 5 | Pending |
| AUTH-06 | Phase 5 | Pending |
| FE-01 | Phase 6 | Pending |
| FE-02 | Phase 6 | Pending |
| FE-03 | Phase 6 | Pending |
| FE-04 | Phase 6 | Pending |
| FE-05 | Phase 6 | Pending |
| FE-06 | Phase 6 | Pending |
| FE-07 | Phase 6 | Pending |
| QUAL-04 | Phase 6 | Pending |
| QUAL-05 | Phase 6 | Pending |
| QUAL-06 | Phase 6 | Pending |
| QUAL-08 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 60 actual (REQUIREMENTS.md header stated 56 — count error in header; all requirements present are mapped)
- Mapped to phases: 60/60
- Unmapped: 0

**Coverage map by phase:**
- Phase 1 (Safety Nets): SAFE-01…SAFE-10 — 10 requirements
- Phase 2 (Observability): OBS-01…OBS-05 — 5 requirements
- Phase 3 (Non-Breaking Internal): CRAWL-01…CRAWL-07, QUAL-01, QUAL-02, QUAL-03, QUAL-07 — 11 requirements
- Phase 4 (DB & Parts): DATA-01…DATA-10, PARTS-01…PARTS-03 — 13 requirements
- Phase 5 (Router Splits): ADMIN-01…ADMIN-04, AUTH-01…AUTH-06 — 10 requirements
- Phase 6 (Frontend + Final CI): FE-01…FE-07, QUAL-04, QUAL-05, QUAL-06, QUAL-08 — 11 requirements

---
*Requirements defined: 2026-04-21*
*Last updated: 2026-04-21 — traceability table populated by roadmapper*
