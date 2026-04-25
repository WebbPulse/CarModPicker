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

# Architecture Research: Refactor Patterns for CarModPicker Tech-Debt Milestone

**Domain:** Brownfield FastAPI + SQLAlchemy + React platform — hot-spot decomposition, concurrency hardening, crawler architecture, observability
**Researched:** 2026-04-21
**Confidence:** HIGH (patterns verified against official FastAPI docs, SQLAlchemy 2.0 docs, Python packaging docs; specific file analysis done against the actual codebase)

---

## Recommended Refactor Architecture (System Overview)

The milestone is NOT a re-architecture. It is targeted surgery on five independent debt clusters. The diagram below shows post-refactor component boundaries — the existing N-tier layer shape is preserved; only internal module groupings change.

```
┌──────────────────────────────────────────────────────────────────────┐
│                         FastAPI App (main.py)                         │
│   EndpointRegistry registers: auth_*, admin_*, + all existing routers │
└────────────┬────────────────────────────┬────────────────────────────┘
             │                            │
┌────────────▼────────────┐  ┌────────────▼────────────────────────────┐
│   auth sub-routers       │  │        admin sub-routers                │
│   auth_core.py           │  │   admin_stats.py                        │
│   auth_2fa.py            │  │   admin_jobs.py                         │
│   auth_webauthn.py       │  │   admin_crawlers.py                     │
│   auth_oauth.py          │  │   admin_parts.py  (canonical link ops)  │
└──────────┬──────────────┘  └────────────┬────────────────────────────┘
           │  DI: same get_db,             │  DI: per-domain service
           │  get_current_user             │  injected via Depends()
           │  (no change to callers)       │
┌──────────▼──────────────────────────────▼────────────────────────────┐
│                        Service Layer (unchanged)                       │
│  AuthService · UserService · CrawlerScheduleService · JobService ...   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────┐
│                     Database (SQLAlchemy 2.0 / PostgreSQL 16)          │
│  Concurrency: SELECT FOR UPDATE on part-link ops                       │
│  Optimistic: version_id_col on CanonicalPart                          │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       Crawler Subsystem                               │
│                                                                        │
│  AdapterRegistry (auto-discovered, not hand-registered)               │
│      ↓ per-tier sub-packages: tier0_http / tier1_tls / tier2_browser  │
│                                                                        │
│  RunCrawlers (run_crawlers function)                                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐   ... up to N        │
│  │ Adapter A  │  │ Adapter B  │  │ Adapter C  │  (semaphore-limited)  │
│  │ thread     │  │ thread     │  │ thread     │                       │
│  └────────────┘  └────────────┘  └────────────┘                      │
│  Each thread: own SessionLocal, per-adapter CircuitBreaker instance   │
│                                                                        │
│  CarGenerationsData: JSON file, lazy-loaded singleton via lru_cache   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                       Observability Layer                              │
│  Structured JSON logs (python-json-logger) — already in place         │
│  + Sentry SDK (FastAPI integration, traces_sample_rate=0.1)           │
│  + Request ID already propagated via RequestContextFilter             │
│  + Crawler metrics: per-adapter counters emitted to CloudWatch        │
│    (ingested / parse_failures / elapsed_sec per run)                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Refactor Pattern Catalog

Each pattern below maps to one or more CONCERNS.md hot spots.

---

### Pattern 1: Vertical Sub-Router Split (auth.py decomposition)

**Addresses:** `auth.py` (1,195 lines, 18+ route handlers spanning 5 distinct auth domains)

**What:** Extract route handlers into named domain sub-modules under `api/endpoints/auth/`. Each sub-module defines its own `APIRouter`. A thin `auth/__init__.py` assembles them into a single parent router via `include_router`. The URL prefix `"/auth"` stays in `main.py`; nothing changes for callers.

**When to use:** Any single file that mixes 3+ conceptually independent workflows, all sharing the same URL prefix. Here: login+email-verify+reset, TOTP, WebAuthn, Google OAuth are four distinct state machines crammed together.

**Trade-offs:** Zero URL breaking changes. Slightly more import indirection. Dependency injection (Depends) declared at file scope still works — FastAPI resolves at request time, not import time.

**Concrete split for auth.py:**

```
backend/app/api/endpoints/auth/
    __init__.py          # assembles parent router
    core.py              # /token, /token/2fa, /verify-email, /reset-password, /logout
    two_factor.py        # /2fa/setup, /2fa/verify, /2fa/disable
    webauthn.py          # /webauthn/register/*, /webauthn/login/*, /webauthn/credentials
    oauth.py             # /google, /google/link, /google/signup, /oauth/2fa, /google/connect, /oauth
```

**`auth/__init__.py` shape:**

```python
from fastapi import APIRouter
from .core import router as core_router
from .two_factor import router as totp_router
from .webauthn import router as webauthn_router
from .oauth import router as oauth_router

router = APIRouter()
router.include_router(core_router)         # no prefix — all paths relative to /auth
router.include_router(totp_router)
router.include_router(webauthn_router)
router.include_router(oauth_router)
```

**`main.py` stays unchanged** — it still does:
```python
endpoint_registry.register_endpoint(auth.router, prefix="/auth", tags=["authentication"], ...)
```

**Shared helpers** (`_issue_login_response`, `_maybe_2fa_challenge`, `_verify_google_or_400`, etc.) move to `auth/_helpers.py` imported by sub-modules that need them.

**DI unchanged:** `Depends(get_current_user)`, `Depends(get_db)`, and `Depends(get_optional_current_user)` are resolved by FastAPI at request dispatch. Splitting the router does not affect how FastAPI resolves `Depends`.

---

### Pattern 2: Domain-Group Sub-Router Split (admin.py decomposition)

**Addresses:** `admin.py` (2,055 lines spanning jobs, crawlers, stats, DB ops, part-linking)

**What:** Same vertical split, but admin.py mixes five more-distinct domains than auth. Split into five sibling routers, all registering at router level only (no independent prefix — they share `/admin`). A thin `admin/__init__.py` assembles the parent router. Per-domain services are injected via constructor, not imported as module singletons.

**Concrete split:**

```
backend/app/api/endpoints/admin/
    __init__.py          # assembles parent router
    stats.py             # GET table counts, crawl bucket summary, migration revision (~150 lines)
    jobs.py              # list/get/cancel jobs, heartbeat, job progress (~250 lines)
    crawlers.py          # list adapters, run_crawlers endpoint, rescrape (~600 lines)
    db_ops.py            # run_migrations, init_car_generations, init_categories, delete_all_* (~400 lines)
    parts.py             # lookup parts by URL, link group, promote/unlink/link canonical, rescan (~400 lines)
```

**Service injection pattern** (reduces the high coupling CONCERNS.md flags):

```python
# admin/crawlers.py
from fastapi import APIRouter, Depends
from app.api.dependencies.auth import get_current_admin_user
from app.services.job_service import get_job_service   # Depends-injectable factory

router = APIRouter()

@router.post("/run")
async def run_crawlers_endpoint(
    ...,
    job_svc=Depends(get_job_service),   # injected, not module-level import
    current_user=Depends(get_current_admin_user),
):
    ...
```

This makes each sub-router independently testable by overriding the service dependency.

---

### Pattern 3: Lazy-Load JSON Singleton (car_generations_data.py)

**Addresses:** `car_generations_data.py` (8,412-line Python literal imported at crawler init), `car_inference.py` (2,742 lines loading it)

**What:** Move the data structure out of a Python source file into `backend/app/core/car_generations_data.json`. Wrap the load in an `@functools.lru_cache(maxsize=1)` function. First caller pays the I/O cost; all subsequent calls return the cached object. JSON `orjson` loads 8K-line files in ~15ms — negligible vs the Python AST parse time for an equivalent `.py` literal.

**When to use:** Any large data file that is read-only, infrequently refreshed, and imported by a module that incurs startup-path cost (as this does via `car_inference.py` → `car_generations_data.py` on every `uvicorn --reload`).

**Pattern:**

```python
# core/car_data_loader.py
import functools
import json
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "car_generations_data.json"

@functools.lru_cache(maxsize=1)
def get_car_generations() -> dict:
    """Load car data once; subsequent calls return cached dict (thread-safe in CPython)."""
    with _DATA_FILE.open("rb") as f:
        return json.load(f)    # orjson.loads(f.read()) if speed matters
```

```python
# car_inference.py — replace top-level import
# BEFORE:
from app.core.car_generations_data import CAR_GENERATIONS
# AFTER:
from app.core.car_data_loader import get_car_generations

def resolve_car_triples_to_ids(triples, db):
    CAR_GENERATIONS = get_car_generations()   # first call loads; rest are free
    ...
```

**Migration path:** Python `json.dumps()` on the existing `CAR_GENERATIONS` dict generates the JSON file without manual reformatting.

```bash
python -c "
import json
from app.core.car_generations_data import CAR_GENERATIONS
with open('backend/app/core/car_generations_data.json', 'w') as f:
    json.dump(CAR_GENERATIONS, f)
"
```

**Note on `lru_cache` thread-safety:** CPython's GIL makes `lru_cache` safe for concurrent reads from multiple threads (crawler thread pool). The only race is if two threads call it simultaneously before the cache is populated — both compute the value, one wins, both return the same result. Acceptable.

---

### Pattern 4: SELECT FOR UPDATE for Part-Linking Races

**Addresses:** CONCERNS.md — "Part linking logic is not transactional" / race condition leaving orphaned canonical refs.

**What:** Acquire a row-level write lock before mutating the canonical relationship. SQLAlchemy 2.0's `.with_for_update()` maps directly to `SELECT ... FOR UPDATE`. The lock is held for the duration of the transaction and released on commit/rollback.

**When to use:** Any operation that is a read-then-write sequence where another transaction could modify the same row between your read and write. Part link/unlink is exactly this pattern.

**Pattern:**

```python
# parts service — part linking
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.models.part import Part as DBPart

def link_part_to_canonical(db: Session, part_id: UUID, canonical_id: UUID) -> DBPart:
    # Acquire row lock — blocks any concurrent link/unlink on this part
    stmt = (
        select(DBPart)
        .where(DBPart.id == part_id)
        .with_for_update()          # SELECT ... FOR UPDATE
    )
    part = db.execute(stmt).scalar_one_or_none()
    if part is None:
        raise HTTPException(404, "Part not found")
    if part.canonical_part_id is not None and part.canonical_part_id != canonical_id:
        raise HTTPException(409, "Part already linked to a different canonical")

    part.canonical_part_id = canonical_id
    db.commit()
    return part
```

**Advisory locks** (PostgreSQL `pg_advisory_xact_lock`) are overkill here. They are appropriate when locking a logical resource that doesn't map to a single row (e.g., "only one crawler per retailer"). For part-row mutations, `with_for_update()` is simpler and sufficient.

**Optimistic concurrency** (`version_id_col`) is an alternative that avoids blocking but requires retry logic on the caller. For part-link admin ops that run infrequently and tolerate short waits, `SELECT FOR UPDATE` is preferable.

```python
# Only add version_id_col if you need high-throughput conflict detection
# (not needed for low-frequency admin part-link operations)
class CanonicalPart(Base):
    __tablename__ = "canonical_parts"
    ...
    version_id = Column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": version_id}
    # SQLAlchemy auto-increments on UPDATE; raises StaleDataError on conflict
```

---

### Pattern 5: Semaphore-Bounded Parallel Crawler Execution

**Addresses:** CONCERNS.md — "Crawler runner processes adapters sequentially"; "Database connection pool undersized for concurrent crawlers"

**What:** The existing `run_crawlers` function uses `ThreadPoolExecutor` for within-adapter URL parallelism but iterates adapters serially (or in a thread pool via the `parallel=True` path). The fix: run multiple adapters concurrently via `ThreadPoolExecutor` with a semaphore-based concurrency cap tied to the available DB pool budget.

The existing code already has `ThreadPoolExecutor` in `run_crawlers` when `parallel=True`. The key addition is:
1. A `max_parallel_adapters` cap derived from `DB_POOL_SIZE - API_CONNECTION_RESERVE`
2. Per-adapter DB sessions (not shared) — already the case, since each `run_crawler` call creates `SessionLocal()`
3. A per-adapter `CircuitBreaker` instance attached before dispatch

**Pattern:**

```python
# runner.py — run_crawlers enhancement

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def run_crawlers(adapter_names, *, parallel=True, **kwargs) -> dict:
    if not parallel or len(adapter_names) == 1:
        # existing serial path — unchanged
        ...

    # Derived from existing constants already imported in runner.py
    max_workers = _compute_adapter_workers(len(adapter_names))
    # _compute_adapter_workers already exists at line 657 — just ensure it caps at
    # (DB_POOL_SIZE - API_CONNECTION_RESERVE) // URLS_PER_ADAPTER_THREAD
    
    sem = threading.Semaphore(max_workers)

    def run_one_guarded(name):
        sem.acquire()
        try:
            return run_one(name)   # existing inner function
        finally:
            sem.release()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_one_guarded, name): name for name in adapter_names}
        for future in as_completed(futures):
            ...  # existing result aggregation
```

**Note:** The `_compute_adapter_workers` function already exists at line 657. Verify it caps at the DB pool budget — if not, add the cap there.

---

### Pattern 6: Per-Adapter Circuit Breaker (pybreaker)

**Addresses:** CONCERNS.md — "Crawler rate limit circuit breaker threshold is high (5 consecutive failures)" / silent hammering of rate-limited retailers.

**What:** Replace the hand-rolled `RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD` counter with a `pybreaker.CircuitBreaker` instance per adapter. `pybreaker` provides CLOSED / OPEN / HALF_OPEN state machine, reset timeout, and listener hooks for alerting.

**Why pybreaker over aiobreaker:** The crawler runner is synchronous (threads, not asyncio). `pybreaker` is the sync-native library. `aiobreaker` is for async contexts.

**Pattern:**

```python
# base.py or runner.py — one breaker per adapter instance
import pybreaker

def make_circuit_breaker(adapter_name: str) -> pybreaker.CircuitBreaker:
    return pybreaker.CircuitBreaker(
        fail_max=3,                         # open after 3 consecutive failures (down from 5)
        reset_timeout=120,                  # re-attempt after 2 min
        name=adapter_name,
        listeners=[_AlertingListener()],    # see below
    )

class _AlertingListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        if new_state.name == "open":
            logger.warning("Circuit OPEN for adapter %s — retailer rate-limited or down", cb.name)
            # future: emit CloudWatch metric or Sentry event here
```

Usage in `run_crawler`:
```python
breaker = make_circuit_breaker(adapter_name)

@breaker
def _fetch_url(url):
    return fetcher.get(url)

for url in urls:
    try:
        html = _fetch_url(url)
    except pybreaker.CircuitBreakerError:
        logger.warning("Adapter %s: circuit open, skipping remaining %d URLs", adapter_name, len(remaining))
        break   # bail on this adapter, move to next
```

**This replaces** the existing `RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD` integer counter in `runner.py`. Delete the counter and the surrounding if-block; pybreaker manages the state machine.

---

### Pattern 7: Directory-Scan Auto-Discovery for Adapters

**Addresses:** CONCERNS.md — "Loose coupling between crawler adapters and registry" / "silent failures if an adapter's import fails"

**What:** Replace the 100+ manual imports in `adapters/__init__.py` with a directory scan that imports every `.py` file in the tier directories and registers any class that subclasses `RetailerCrawlerAdapter`.

**Why directory-scan over Python entry points:** Entry points require each adapter to be a separate installed package. That's overkill — the adapters live in the same codebase. Directory scan is simpler and provides the same auto-discovery benefit.

**Pattern:**

```python
# adapters/__init__.py — replace manual import block

import importlib
import inspect
import pkgutil
from pathlib import Path
from app.crawlers.adapters.base import RetailerCrawlerAdapter

_TIER_PACKAGES = [
    "app.crawlers.adapters.tier0_http",
    "app.crawlers.adapters.tier1_tls",
    "app.crawlers.adapters.tier2_browser",
]

def _discover_adapters() -> dict[str, type[RetailerCrawlerAdapter]]:
    registry: dict[str, type[RetailerCrawlerAdapter]] = {}
    for pkg_name in _TIER_PACKAGES:
        pkg = importlib.import_module(pkg_name)
        pkg_path = Path(pkg.__file__).parent
        for module_info in pkgutil.iter_modules([str(pkg_path)]):
            module = importlib.import_module(f"{pkg_name}.{module_info.name}")
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, RetailerCrawlerAdapter)
                    and obj is not RetailerCrawlerAdapter
                    and hasattr(obj, "ADAPTER_NAME")
                ):
                    registry[obj.ADAPTER_NAME] = obj
    return registry

ADAPTER_REGISTRY: dict[str, type[RetailerCrawlerAdapter]] = _discover_adapters()
```

**Required change to adapter base class:** Add `ADAPTER_NAME: ClassVar[str]` as an abstract class attribute to `RetailerCrawlerAdapter`. Each adapter sets it (e.g., `ADAPTER_NAME = "a90shop"`). This replaces the current string-key manual registration and makes the name co-located with the adapter.

**Validation:** After discovery, log the count at startup: `logger.info("Discovered %d crawler adapters", len(ADAPTER_REGISTRY))`. If the count is wrong, the import error is surfaced immediately rather than silently at runtime.

---

### Pattern 8: Characterization Tests via VCR Before Structural Refactor

**Addresses:** Test coverage gaps (CONCERNS.md) — particularly for auth flows and crawler adapters.

**What:** Before moving code, record HTTP interactions with `pytest-recording` (VCR.py wrapper). These cassettes lock in the current behavior — if the refactored code produces different HTTP traffic, the test fails. This is a "characterization test": it doesn't assert correctness, it asserts that the refactored code behaves identically to pre-refactor.

**When to use:** Any structural refactor where the behavior is assumed-correct but untested. Auth flows and crawler adapters both qualify.

**Pattern for crawler adapter:**

```python
# tests/crawlers/test_a90shop_vcr.py
import pytest

@pytest.mark.vcr(record_mode="none")  # replay only; fail on new requests
def test_a90shop_discover_and_parse():
    from app.crawlers.adapters.tier0_http.a90shop import A90ShopAdapter
    adapter = A90ShopAdapter()
    urls = adapter.discover_product_urls()
    assert len(urls) > 0
    result = adapter.parse_product_page(SAMPLE_HTML, urls[0])
    assert result is not None
    assert result.name
    assert result.price > 0
```

First run with `--record-mode=once` against the S3 archive (the project already has `carmodpicker-prod-crawl-html`) — replay archived HTML, never hit live retailers.

**Pattern for auth endpoint characterization:**

```python
# tests/api/test_auth_characterization.py
import pytest
from fastapi.testclient import TestClient

def test_login_returns_access_token(client: TestClient, test_user):
    resp = client.post("/api/auth/token", data={"username": test_user.email, "password": "testpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Snapshot the response shape (not the token value)
    assert set(data.keys()) == {"access_token", "token_type", "user"}
```

Run these tests BEFORE touching auth.py. They catch regressions introduced during the split.

---

### Pattern 9: OpenAPI Schema Snapshot Tests (Contract Tests)

**Addresses:** Risk of API drift during router splits.

**What:** Export the FastAPI OpenAPI schema as a JSON file checked into git. A CI test asserts the live schema matches the snapshot. Any URL or shape change surfaces as a diff in the snapshot file, requiring explicit acknowledgment.

**Pattern:**

```python
# tests/test_openapi_snapshot.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

SNAPSHOT_PATH = Path(__file__).parent / "openapi_snapshot.json"

def test_openapi_schema_unchanged():
    client = TestClient(app)
    resp = client.get("/openapi.json")
    current = resp.json()
    if not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2))
        pytest.skip("Snapshot created — run tests again to validate")
    saved = json.loads(SNAPSHOT_PATH.read_text())
    assert current == saved, "OpenAPI schema changed — update snapshot if intentional"
```

Run `pytest --update-snapshot` flag (or delete the file) when intentional changes are made. This creates an explicit, reviewable gate against accidental URL drift during the router splits.

---

### Pattern 10: Structured Observability — Sentry + CloudWatch Crawler Metrics

**Addresses:** CONCERNS.md — "No metrics/observability for crawler performance" / "None" error tracking

**What:** Layer two managed-first observability additions on top of the existing structured logging:

1. **Sentry SDK** — error tracking for exceptions that make it past the error handler middleware. FastAPI integration is automatic.
2. **CloudWatch custom metrics** — per-adapter crawl counters (ingested / parse_failures / elapsed_sec). Emitted as `put_metric_data` calls after each `run_crawler` completes.

**Sentry integration:**

```python
# main.py — add near top, before FastAPI app creation
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

sentry_sdk.init(
    dsn=settings.SENTRY_DSN,         # add to config.py; empty string = disabled
    integrations=[
        FastApiIntegration(transaction_style="endpoint"),
        SqlalchemyIntegration(),      # captures slow/erroring queries
    ],
    traces_sample_rate=0.05,          # 5% trace sampling — low traffic, cheap
    environment=settings.APP_ENVIRONMENT,
    send_default_pii=False,           # do not send user emails/PII
)
```

**CloudWatch crawler metrics:**

```python
# core/metrics.py — thin wrapper
import boto3
from datetime import datetime, timezone

_cw = boto3.client("cloudwatch", region_name=settings.AWS_REGION)

def emit_crawler_run(adapter_name: str, ingested: int, parse_failures: int, elapsed_sec: float):
    if not settings.EMIT_METRICS:      # add flag to config.py; default False in dev
        return
    _cw.put_metric_data(
        Namespace="CarModPicker/Crawlers",
        MetricData=[
            {"MetricName": "Ingested",       "Value": ingested,       "Unit": "Count",   "Dimensions": [{"Name": "Adapter", "Value": adapter_name}]},
            {"MetricName": "ParseFailures",   "Value": parse_failures, "Unit": "Count",   "Dimensions": [{"Name": "Adapter", "Value": adapter_name}]},
            {"MetricName": "ElapsedSeconds",  "Value": elapsed_sec,    "Unit": "Seconds", "Dimensions": [{"Name": "Adapter", "Value": adapter_name}]},
        ],
    )
```

Call `emit_crawler_run(...)` at the end of `run_crawler()` using the result dict already returned. This adds one CloudWatch API call per adapter run — negligible cost.

**Request ID already works** — `RequestContextFilter` in `log_context.py` already injects `request_id` and `user_id`. Sentry picks these up automatically via the FastAPI integration. No additional propagation needed.

---

## Component Boundaries After Refactor

### Auth Sub-Router Shape

```
auth/
├── __init__.py          Assembles: include_router(core, totp, webauthn, oauth)
├── _helpers.py          Shared: _issue_login_response, _maybe_2fa_challenge,
│                                _decode_purpose_token, _suggest_username
├── core.py              Routes: /token, /token/2fa, /verify-email, /verify-email/confirm,
│                                /reset-password, /reset-password/confirm, /logout
├── two_factor.py        Routes: /2fa/setup, /2fa/verify, /2fa/disable
├── webauthn.py          Routes: /webauthn/register/options, /webauthn/register/verify,
│                                /webauthn/login/options, /webauthn/login/verify,
│                                /webauthn/credentials (GET, PATCH, DELETE)
│                        Helpers: _b64url_encode, _b64url_decode, _build_challenge_token,
│                                 _decode_challenge_token (private to this module)
└── oauth.py             Routes: /google, /google/link, /google/signup, /oauth/2fa,
                                 /google/connect, /oauth (GET, DELETE)
                         Helpers: _ensure_google_enabled, _verify_google_or_400
```

Each file imports from `auth._helpers` for shared utilities. Each file independently imports `Depends(get_db)` and `Depends(get_current_user)` — no inter-sub-module DI wiring needed.

### Admin Sub-Router Shape

```
admin/
├── __init__.py          Assembles all five sub-routers; no prefix (all share /admin)
├── stats.py             Routes: GET table-counts, GET crawl-bucket-summary,
│                                GET migration-revision
│                        Deps:   Depends(get_current_admin_user), Depends(get_db)
├── jobs.py              Routes: GET /jobs, GET /jobs/{id}, POST /jobs/{id}/cancel,
│                                GET /crawler-service-account, GET /job-progress/{id}
│                        Deps:   Depends(job_service_dep)
├── crawlers.py          Routes: GET /crawlers, POST /run, POST /rescrape-archived
│                        Deps:   Depends(job_service_dep), Depends(get_current_admin_user)
│                        Keeps:  _launch_ecs_crawler_task, _run_crawlers_in_process (private)
├── db_ops.py            Routes: POST /run-migrations, POST /init-car-generations,
│                                POST /init-categories, DELETE /cars, DELETE /part-manufacturers
│                        Deps:   Depends(get_current_superuser)
│                        Keeps:  _get_alembic_directory (private)
└── parts.py             Routes: GET /part-link-group, GET /parts-by-url,
                                 POST /promote-canonical, POST /unlink-canonical,
                                 POST /link-parts, POST /rescan-canonical
                         Deps:   Depends(get_current_admin_user), Depends(get_db)
                         Note:   Part-link routes should use SELECT FOR UPDATE (Pattern 4)
```

---

## Recommended Build Order (Dependency Graph)

The build order enforces the safety principle: **observability and tests before structural changes, data safety before concurrency**.

```
Phase A: Safety Net (must complete before structural refactors)
├── A1: OpenAPI schema snapshot test (Pattern 9) ─────────────────────┐
├── A2: Auth characterization tests (Pattern 8, auth flows)           │  Gate: CI green
└── A3: Crawler adapter VCR tests (Pattern 8, 5+ adapters)           │  before Phase B

Phase B: Non-breaking improvements (no URL changes, no model changes)
├── B1: car_generations_data.py → JSON lazy load (Pattern 3) ────────┐
│       No model changes, no URL changes, startup latency fix         │
├── B2: Circuit breaker swap pybreaker (Pattern 6) ───────────────────┤  Parallelizable
│       Internal runner change, no external surface                   │
├── B3: Adapter auto-discovery (Pattern 7) ───────────────────────────┘
│       Must validate ADAPTER_REGISTRY count matches current before committing
│
├── B4: Crawler semaphore + worker cap (Pattern 5) ────────────────────  After B2+B3 stable
│       Depends on B3 (auto-discovery must work correctly first)
│       Increase DB_POOL_SIZE in config when enabling parallel adapters

Phase C: Observability (additive, zero regression risk)
├── C1: Sentry SDK integration (Pattern 10) ──────────────────────────┐
└── C2: CloudWatch crawler metrics (Pattern 10) ───────────────────────┘  Parallelizable

Phase D: Structural router splits (highest regression risk — run AFTER Phase A tests pass)
├── D1: admin.py split into admin/ sub-routers (Pattern 2) ──────────┐
│       Lower regression risk than auth (admin endpoints not in Chrome │
│       extension critical path)                                      │  Run D1 first,
├── D2: auth.py split into auth/ sub-routers (Pattern 1) ─────────────┘  validate, then D2
│       Highest regression risk (auth is Chrome extension critical path)
│       Validate: Chrome extension auth flow still works end-to-end

Phase E: Concurrency hardening (requires DB migration — must be last)
└── E1: SELECT FOR UPDATE on part-link endpoints (Pattern 4)
        Requires Alembic migration if adding version_id_col (optimistic path)
        No migration needed if using SELECT FOR UPDATE only (pessimistic path — recommended)
```

**Key dependency rules:**
- Phase A must complete (CI green) before Phase D starts. Router splits without characterization tests are blind refactors.
- B3 (auto-discovery) must be validated before B4 (parallel execution) — a wrong adapter count discovered under parallel load is harder to diagnose.
- D1 before D2 — admin split is lower stakes than auth. Use D1 as a dry run for the split pattern itself.
- E1 is independent of D1/D2 but should not run during D2 (avoid concurrent migration + router split change windows).

---

## Anti-Patterns — Explicit "Don't Do This"

### Anti-Pattern 1: Microservices Split

**What people do:** Separate admin, auth, and crawler into distinct FastAPI services with inter-service HTTP calls.
**Why wrong:** CarModPicker is low traffic. Each service boundary adds network latency, distributed transaction complexity, and operational overhead (separate deployments, health checks, secrets). The coupling problems in admin.py are a code organization problem, not a deployment boundary problem.
**Do this instead:** Vertical sub-router split within the same process (Patterns 1 and 2).

### Anti-Pattern 2: Async SQLAlchemy Migration

**What people do:** Convert all `Session` to `AsyncSession`, all `def` routes to `async def`, to unlock true async DB queries.
**Why wrong:** The existing codebase is synchronous-SQLAlchemy throughout. Migrating to `AsyncSession` requires changing every service and every test fixture. The payoff (non-blocking DB IO) is not meaningful at current traffic. FastAPI already runs sync def routes in a thread pool via anyio — DB calls don't block the event loop.
**Do this instead:** Keep synchronous SQLAlchemy; add `with_for_update()` where needed (Pattern 4). Async SQLAlchemy is a future milestone concern.

### Anti-Pattern 3: Shared Mutable State Across Crawler Threads

**What people do:** Share a single `SessionLocal()` instance across concurrent adapter threads.
**Why wrong:** SQLAlchemy Sessions are not thread-safe. Concurrent access causes `DetachedInstanceError`, stale reads, and transaction corruption. The existing code correctly creates per-adapter sessions (`SessionLocal()` inside `run_crawler`). Don't break this.
**Do this instead:** Maintain the existing pattern — each `run_crawler` invocation creates its own Session from `SessionLocal`.

### Anti-Pattern 4: `lru_cache` on Async Functions for Car Data

**What people do:** Decorate an `async def` function with `@lru_cache` to cache the car data load.
**Why wrong:** `lru_cache` on async functions caches the coroutine object, not the awaited result — every call returns a new coroutine wrapping the cached one, which is subtly broken.
**Do this instead:** Use `@lru_cache` on a synchronous `def` function (Pattern 3). Car data loading is I/O (file read), which is fast enough to do synchronously in a `def` function. If async loading is needed, use `asyncio.get_event_loop().run_in_executor()` with a separate sync loader — but it's not needed here.

### Anti-Pattern 5: Building a Custom Observability Stack

**What people do:** Hand-roll metrics collection, build a custom dashboard, write a bespoke alerting system.
**Why wrong:** CloudWatch already exists (terraform/monitoring.tf), Sentry is one `pip install` and 10 lines away. Custom observability requires ongoing maintenance and is a distraction from product work.
**Do this instead:** Sentry for errors, CloudWatch custom metrics for crawler counters (Pattern 10). Both are managed, both are already part of the AWS account.

### Anti-Pattern 6: Rewriting car_inference.py Ambiguity Logic

**What people do:** During the decomposition milestone, rewrite the AMBIGUOUS_STANDALONE_CODES set or replace phrase matching with embeddings.
**Why wrong:** Car inference correctness is hard to validate without a labelled dataset. Rewriting it during a tech-debt milestone risks breaking the 25K-part existing associations. CONCERNS.md correctly notes this is fragile.
**Do this instead:** Scope is "maintainability only" — move the data to JSON (Pattern 3), leave the matching logic untouched. ML-based inference is a future milestone with its own research phase.

---

## Scaling Considerations

These are the realistic next bottlenecks after the milestone, not targets for this milestone:

| Concern | Post-Milestone State | Next Threshold |
|---------|---------------------|----------------|
| DB connections | Pool at 20 (current); increase to 30-40 when enabling parallel crawlers | ~500 concurrent API users |
| Rate limiting | In-memory per worker; fine for App Runner single-instance | Multi-instance App Runner deployment needs Redis |
| Car data load | JSON file, LRU-cached, ~15ms once per worker | No realistic scaling limit |
| Adapter registry | 114 adapters, in-memory after auto-discovery | ~500+ adapters: consider DB-backed registry |
| Crawler parallelism | Thread-pool capped by DB pool budget | 200+ adapters: consider async SQLAlchemy + asyncio |

---

## Integration Points

### Preserved Integration Contracts

| Integration | Change Risk | Notes |
|-------------|-------------|-------|
| Chrome extension auth flow | HIGH — test explicitly | Auth URL split must not change `/api/auth/*` paths |
| EventBridge → `/api/cron/run-crawler-schedule` | LOW | admin/crawlers.py keeps this route unchanged |
| Extension POST `/api/crawled-pages/*` | NONE | Not in admin split scope |
| Sentry DSN | ADDITIVE | New config var; empty string = disabled (no prod impact) |
| CloudWatch metrics | ADDITIVE | Guarded by `EMIT_METRICS` flag; default False |

### Module Boundary Communication

| Boundary | Communication | Notes |
|----------|---------------|-------|
| auth/* sub-modules | Import from auth._helpers | No circular imports possible (helpers has no router imports) |
| admin/* sub-modules | Independent routers; shared service deps via Depends() | |
| crawler runner → metrics | Direct function call after run_crawler returns | |
| car_data_loader → car_inference | lru_cache singleton; imported as function call | Replaces module-level attribute import |

---

## Sources

- FastAPI official docs — Bigger Applications, include_router: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI safely sharing dependencies across routers (2025): https://dev.turmansolutions.ai/2025/09/15/safely-sharing-fastapi-dependencies-across-multiple-routers/
- SQLAlchemy 2.0 with_for_update: https://testdriven.io/tips/5ce50ece-eaeb-496f-8339-c871c00781c4/
- SQLAlchemy 2.0 versioning / optimistic concurrency: https://docs.sqlalchemy.org/en/20/orm/versioning.html
- SQLAlchemy async session per-task rule: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- pybreaker circuit breaker: https://github.com/danielfm/pybreaker
- Python plugin auto-discovery via directory scan: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/
- pytest-recording (VCR): https://github.com/kiwicom/pytest-recording
- FastAPI observability guide (2025): https://blog.greeden.me/en/2025/10/07/operations-friendly-observability-a-fastapi-implementation-guide-for-logs-metrics-and-traces-request-id-json-logs-prometheus-opentelemetry-and-dashboard-design/
- Sentry FastAPI integration: https://docs.sentry.io/platforms/python/integrations/fastapi/
- asgi-correlation-id + Sentry: https://github.com/snok/asgi-correlation-id
- Strangler fig pattern — OneUptime (Jan 2026): https://oneuptime.com/blog/post/2026-01-24-strangler-fig-migration-pattern/view
- FastAPI LRU cache vs lifespan discussion: https://github.com/fastapi/fastapi/discussions/11987

---

*Architecture research for: CarModPicker tech-debt refactor milestone*
*Researched: 2026-04-21*

# Stack Research: Tech-Debt Refactor Milestone

**Domain:** Mature FastAPI + React + PostgreSQL platform (CarModPicker)
**Researched:** 2026-04-21
**Confidence:** HIGH (versions verified via PyPI/npm; idioms verified via official docs and Context7)

---

## Purpose of This Document

This is NOT a greenfield stack recommendation. CarModPicker already has a working production stack.
This document answers: **for the stack already in use, what does current best-practice look like as of 2026?**

For each library: pinned version → current stable → recommended target → modern idioms to adopt → anti-patterns to eliminate.

---

## Backend Core

### FastAPI

| | |
|--|--|
| **Pinned** | 0.128.0 |
| **Current stable** | 0.136.0 (2026-04-16) |
| **Recommended target** | 0.136.0 |
| **Priority** | MUST upgrade — breaking changes between 0.128 → 0.136 affect this codebase |
| **Confidence** | HIGH |

**What changed 0.128 → 0.136 that matters:**
- 0.135.0: SSE (`EventSourceResponse`) support natively (minor — not used yet)
- 0.135.1: Fixed `TaskGroup` yield handling in request async exit stack (bug fix — relevant if lifespan uses task groups)
- 0.135.2: Raised minimum Pydantic to `>=2.9.0` (already satisfied at 2.11.3)
- 0.136.0: Starlette 1.0.0 support; **strict Content-Type checking for JSON requests** (BREAKING for some API clients — any client that omits `Content-Type: application/json` on POST bodies will now get a 422 by default; set `strict_content_type=False` to disable if needed during migration)

**Lifespan hooks — must adopt:**

The app already uses `lifespan=` context manager in `main.py` (correct). This is the current idiom. Confirm there are zero remaining `@app.on_event("startup")` / `@app.on_event("shutdown")` decorators anywhere in the codebase — these are deprecated and silently skipped when `lifespan=` is also set.

```python
# CORRECT (already in use)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown

app = FastAPI(lifespan=lifespan)

# WRONG — deprecated, silently ignored alongside lifespan=
@app.on_event("startup")
async def startup():
    ...
```

**Dependency injection — current idioms:**

The app's `get_logger` injected via `Depends()` is correct but uncommon; logging is normally module-level (`logger = logging.getLogger(__name__)`). The `Depends()` pattern for logger is harmless but adds needless overhead per request. Module-level loggers are the standard FastAPI pattern.

```python
# CURRENT — logger injected as Depends() (works but unusual)
async def endpoint(logger: logging.Logger = Depends(get_logger)):
    ...

# BETTER — module-level logger (zero overhead, standard pattern)
logger = logging.getLogger(__name__)

async def endpoint():
    logger.info("...")
```

**Async vs sync endpoints — decision rule:**

The codebase uses synchronous SQLAlchemy sessions (`Session`, not `AsyncSession`). Endpoints marked `async def` with a sync `Session` dependency are **not wrong** — FastAPI runs the sync session in a thread pool. But the endpoints must not call other blocking I/O besides the DB. The rule:

- `async def` + sync `Session` dependency: FastAPI threadpools the session, endpoint runs on event loop — fine for this architecture, do not change during refactor
- `async def` + truly blocking CPU work: must offload to thread pool explicitly via `asyncio.run_in_executor`
- `def` (sync) with sync dependencies: also fine; FastAPI threadpools the entire handler

Do NOT mix `async def` with any genuinely blocking library calls without explicit threadpool offload. The codebase's pattern is consistent and should not be changed wholesale — only flag violations found in the audit.

**Middleware — current idioms:**

The custom `BaseHTTPMiddleware` subclasses are correct. One caveat: `BaseHTTPMiddleware` has a known performance overhead (wraps each request in a new coroutine stack). For high-throughput use, Starlette's pure ASGI middleware is faster. At CarModPicker's current traffic level this is not a concern. Keep `BaseHTTPMiddleware` for readability.

**APIRouter composition — current idioms:**

`EndpointRegistry` wrapping `APIRouter` is idiomatic. One thing to verify: all routers use `prefix=` and `tags=` consistently for OpenAPI docs clarity.

---

### Uvicorn

| | |
|--|--|
| **Pinned** | 0.34.0 |
| **Current stable** | 0.45.0 (2026-04-21) |
| **Recommended target** | 0.45.0 |
| **Priority** | SHOULD upgrade — multiple bug fixes and performance improvements across 11 minor versions |
| **Confidence** | HIGH |

No breaking changes expected. Standard `pip install --upgrade uvicorn` upgrade.

---

### SQLAlchemy

| | |
|--|--|
| **Pinned** | 2.0.41 |
| **Current stable** | 2.0.49 (2026-04-03) |
| **Recommended target** | 2.0.49 |
| **Priority** | SHOULD upgrade — patch releases only within the 2.0 series, no breaking changes |
| **Confidence** | HIGH |

**Already correct: 2.0-style ORM usage**

The codebase uses `Mapped[]` typed columns and `mapped_column()` — this is the correct SQLAlchemy 2.0 style. Do NOT revert to the 1.x `Column()` pattern.

```python
# CORRECT — SQLAlchemy 2.0 style (already in use)
class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(nullable=True)

# WRONG — 1.x legacy style (do not use)
class User(Base):
    id = Column(UUID, primary_key=True)
    username = Column(String, unique=True)
```

**Sync vs async session — keep sync for this milestone:**

The codebase uses synchronous `Session` + `psycopg2-binary`. This is the correct choice for the current architecture: sync SQLAlchemy in async FastAPI endpoints runs in FastAPI's threadpool. Migrating to `AsyncSession` + `asyncpg` is a significant refactor (all queries must change, lazy loading breaks silently in async, need `selectinload()` everywhere) and is out of scope for a tech-debt cleanup milestone. **Keep sync session + psycopg2 for this milestone.**

The async session migration is future work if concurrency benchmarks show a bottleneck — at current traffic levels it is premature optimization.

**N+1 prevention — must adopt during refactor:**

The known N+1 in build logs (from CONCERNS.md) must be fixed. The current codebase uses `lazy=select` (default lazy loading). The fix:

```python
# WRONG — N+1: each access to build_list.parts fires a separate query
build_lists = session.scalars(select(BuildList)).all()
for bl in build_lists:
    print(bl.parts)  # fires N queries

# CORRECT — use selectinload for one-to-many collections
from sqlalchemy.orm import selectinload

stmt = select(BuildList).options(selectinload(BuildList.parts))
build_lists = session.scalars(stmt).all()
# fires exactly 2 queries total regardless of result count

# For many-to-one (single object), joinedload is preferred (one JOIN, no extra query)
from sqlalchemy.orm import joinedload

stmt = select(BuildList).options(joinedload(BuildList.owner))
```

Rule of thumb:
- One-to-many collection: `selectinload()` (avoids cartesian explosion)
- Many-to-one single object: `joinedload()` (one JOIN is efficient for single lookups)
- Explicitly set `lazy="raise"` on relationships being fixed to catch regressions in tests

**Query style — 2.0 select() is required:**

```python
# CORRECT — 2.0 style
from sqlalchemy import select
stmt = select(User).where(User.email == email)
user = session.scalars(stmt).first()

# WRONG — 1.x legacy query API (still works in 2.0 but is deprecated path)
user = session.query(User).filter(User.email == email).first()
```

Audit the codebase for any remaining `session.query()` calls and migrate them to `select()` during the refactor. CONVENTIONS.md shows `db.query(DBUser)` usage in `auth.py` — this is the primary target.

---

### Alembic

| | |
|--|--|
| **Pinned** | 1.16.2 |
| **Current stable** | 1.18.4 (2026-02-10) |
| **Recommended target** | 1.18.4 |
| **Priority** | SHOULD upgrade — 1.18.0 added plugin system and improved autogenerate |
| **Confidence** | HIGH |

**Already correct: autogenerate only**

The project correctly uses `alembic revision --autogenerate` only. Never write migration files by hand. This is correct.

**Naming conventions — adopt if not present:**

If the `Base.metadata` doesn't already have a naming convention, add one to prevent Alembic from generating anonymous constraint names (which break on rename/alter):

```python
from sqlalchemy import MetaData

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

**Migration hygiene — column renames:**

Alembic sees a column rename as `DROP + ADD` (data loss). Never rename columns directly in the model and autogenerate — always use explicit `op.alter_column()` in a manual migration step.

---

### Pydantic

| | |
|--|--|
| **Pinned** | 2.11.3 |
| **Current stable** | 2.13.3 (2026-04-20) |
| **Recommended target** | 2.13.3 |
| **Priority** | SHOULD upgrade — minor, patch-level improvements within v2 series |
| **Confidence** | HIGH |

**Already correct: ConfigDict and field_validator**

The codebase uses `ConfigDict(from_attributes=True)` and `@field_validator` with `@classmethod` — these are the correct v2 patterns.

**Computed fields — adopt where properties are used:**

If any schema models use `@property` to expose derived values, replace with `@computed_field` so they appear in serialization automatically:

```python
# WRONG — @property is invisible to Pydantic serialization
class PartRead(BaseModel):
    price_cents: int

    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100

# CORRECT — @computed_field is included in .model_dump() and response JSON
from pydantic import computed_field

class PartRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    price_cents: int

    @computed_field
    @property
    def price_dollars(self) -> float:
        return self.price_cents / 100
```

**Annotated validators — prefer for reusable constraints:**

```python
from typing import Annotated
from pydantic import AfterValidator

def must_be_positive(v: int) -> int:
    if v <= 0:
        raise ValueError("must be positive")
    return v

PositiveInt = Annotated[int, AfterValidator(must_be_positive)]

# Reuse across schemas without copy-pasting @field_validator
class PartCreate(BaseModel):
    price_cents: PositiveInt
    quantity: PositiveInt
```

**model_validator for cross-field validation:**

```python
from pydantic import model_validator

class DateRange(BaseModel):
    start: date
    end: date

    @model_validator(mode='after')
    def check_date_order(self) -> 'DateRange':
        if self.end < self.start:
            raise ValueError('end must be after start')
        return self
```

**v1 patterns to eliminate:**

- `@validator` decorator → replace with `@field_validator` (v1 validator is still imported but emits deprecation warnings in v2)
- `class Config:` nested class → replace with `model_config = ConfigDict(...)`
- `orm_mode = True` → replace with `from_attributes=True` in ConfigDict
- `.dict()` method → replace with `.model_dump()`
- `.parse_obj()` → replace with `.model_validate()`

Audit all schema files for `@validator`, `class Config`, `orm_mode`, `.dict()`, `.parse_obj()`.

---

### Authentication — python-jose → PyJWT

| | |
|--|--|
| **Pinned** | python-jose[cryptography] 3.5.0 |
| **Current stable (PyJWT)** | PyJWT 2.12.1 (2026-03-13) |
| **Recommended target** | PyJWT 2.12.1 |
| **Priority** | SHOULD replace — FastAPI officially updated docs to recommend PyJWT (PR #11589, May 2024) |
| **Confidence** | HIGH |

**Why replace python-jose:**

python-jose is essentially unmaintained (minimal commits since 2021). FastAPI has officially moved its documentation to recommend PyJWT. CVE-2024-33663 (algorithm confusion) affects python-jose when `algorithms` is not explicitly specified to `jwt.decode()`. The codebase comment in `requirements.txt` correctly notes the ecdsa CVE is not exploitable with HS256, but the package being unmaintained is itself a risk.

**Migration is simple — same `encode`/`decode` surface:**

```python
# BEFORE (python-jose)
from jose import JWTError, jwt
payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
token = jwt.encode(data, SECRET_KEY, algorithm="HS256")

# AFTER (PyJWT)
import jwt as pyjwt
from jwt.exceptions import InvalidTokenError

payload = pyjwt.decode(token, SECRET_KEY, algorithms=["HS256"])
token = pyjwt.encode(data, SECRET_KEY, algorithm="HS256")
# Note: PyJWT encode() returns str (not bytes) in v2+
```

The main difference: `JWTError` → `InvalidTokenError` (or `jwt.PyJWTError`). Since the app only uses HS256, the migration is a straight find-replace with one exception rename.

---

### psycopg2-binary

| | |
|--|--|
| **Pinned** | 2.9.10 |
| **Current stable** | 2.9.12 (2026-04-20) |
| **Recommended target** | 2.9.12 (same major) |
| **Priority** | MINOR upgrade — keep psycopg2 for this milestone (see SQLAlchemy note above) |
| **Confidence** | HIGH |

**Longer-term consideration (future milestone):** psycopg3 (`psycopg` package, v3.3.3) is now production stable and provides native async support with SQLAlchemy 2.0. Migration requires switching to `create_async_engine("postgresql+psycopg://...")` + `AsyncSession`. Not for this milestone.

---

### boto3

| | |
|--|--|
| **Pinned** | 1.42.91 |
| **Current stable** | 1.42.93 (2026-04-21) |
| **Recommended target** | 1.42.93 |
| **Priority** | MINOR patch upgrade |
| **Confidence** | HIGH |

**Type stubs — current idiom is correct:**

`boto3-stubs[s3,sesv2]` is the correct approach. The `TYPE_CHECKING` guard prevents importing stubs at runtime:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

def upload_file(client: "S3Client", ...) -> None:
    ...
```

This pattern is already idiomatic and correct. The boto3 stubs approach is the accepted standard for type-safe AWS SDK usage in Python.

---

### Type Checking — mypy vs pyright

| | |
|--|--|
| **mypy pinned** | 1.17.1 |
| **mypy current stable** | 1.20.2 (2026-04-21) |
| **Recommended** | Keep both: pyright in editor (already configured in pyproject.toml), mypy in CI |
| **Confidence** | MEDIUM |

The codebase already runs both mypy and pyright (per CONVENTIONS.md). This is actually a strong pattern:
- pyright catches errors faster in the editor (3-5x faster than mypy, no plugin needed for FastAPI/Pydantic)
- mypy in CI ensures library compatibility via its plugin ecosystem

Upgrade mypy to 1.20.2. Ensure `pyright` is pinned in dev tooling (not just installed via editors). Run `pyright --verifytypes app` to check for missing type annotations in the service layer.

---

### pytest / pytest-asyncio / pytest-xdist

| | |
|--|--|
| **pytest pinned** | 9.0.3 |
| **pytest current stable** | 9.0.3 (confirmed current as of 2026-04-21) |
| **pytest-asyncio pinned** | 1.3.0 |
| **pytest-asyncio current stable** | 1.3.0 (confirmed current) |
| **pytest-xdist pinned** | 3.8.0 |
| **Recommended target** | Keep current versions — all are at current stable |
| **Priority** | NO upgrade needed |
| **Confidence** | HIGH |

**pytest-asyncio 1.3.0 — legacy mode removed:**

Version 1.3.0 removed `legacy` mode. Only `auto` and `strict` modes remain. Ensure `asyncio_mode` is explicitly configured in `pyproject.toml` (or `pytest.ini`):

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # recommended for pure-asyncio projects
# OR
asyncio_mode = "strict"  # requires explicit @pytest.mark.asyncio on each test
```

If the project uses async tests without explicit mode config, add it now to silence deprecation warnings in 1.3.0.

**pytest-xdist with async tests:**

`-n auto` + `asyncio_mode = "auto"` works correctly in pytest-asyncio 1.3.0 — each worker gets its own event loop. The existing `-n auto` convention is correct. Do not use `--dist=loadscope` unless you have shared async fixtures that break across workers (investigate if flaky async tests appear).

**Test isolation pattern — already correct:**

The savepoint/outer-transaction rollback pattern documented in CONVENTIONS.md (`join_transaction_mode="create_savepoint"`) is the correct pattern for fast test isolation without resetting the database between tests. Keep it.

---

## Frontend Core

### React

| | |
|--|--|
| **Pinned** | 19.1.0 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed |

**React 19 hooks to adopt during refactor:**

React 19.1.0 is current. The refactor opportunity is adopting React 19 APIs that may not be in use yet:

`useOptimistic` — for mutations where you want to show instant feedback before the server confirms:

```tsx
// Before React 19: manual state management + rollback on error
const [votes, setVotes] = useState(initialVotes);
const handleVote = async () => {
    setVotes(v => v + 1);  // optimistic
    try { await postVote(); }
    catch { setVotes(v => v - 1); }  // rollback
};

// React 19: useOptimistic handles this cleanly
import { useOptimistic, useTransition } from 'react';
const [optimisticVotes, addOptimisticVote] = useOptimistic(
    serverVotes,
    (current, increment: number) => current + increment
);
const [isPending, startTransition] = useTransition();
const handleVote = () => {
    startTransition(async () => {
        addOptimisticVote(1);
        await postVote();
    });
};
```

`use()` hook — for consuming promises or context mid-render (replaces some `useEffect`+state patterns):

```tsx
// For context, use() can be called conditionally (unlike useContext)
import { use } from 'react';
const user = use(AuthContext);  // simpler than useContext in some cases
```

`useTransition` with async — now supports async functions directly in React 19:

```tsx
const [isPending, startTransition] = useTransition();
startTransition(async () => {
    await someAsyncOperation();  // works in React 19, didn't before
});
```

**What NOT to adopt:**

Server Components and server actions are a Next.js/Remix pattern. CarModPicker is a Vite SPA — these do not apply. Do not attempt to adopt RSC patterns.

**Context usage — current idioms remain correct:**

`AuthContext` and `AppSettingsContext` pattern is idiomatic React. The `useAuth()` hook that throws when used outside provider is the correct guard pattern. No changes needed.

**Error boundaries — ensure coverage:**

React 19 improved error boundary behavior. The root `ErrorBoundary` in `main.tsx` is correct. Ensure route-level error boundaries exist for pages that make async API calls — a single root boundary means the entire app crashes on one page's error.

---

### React Router

| | |
|--|--|
| **Pinned** | 7.6.0 |
| **Confidence** | HIGH — at current stable or near it |
| **Priority** | No upgrade needed |

**SPA mode — correct usage:**

CarModPicker is a Vite SPA. React Router 7 in "library mode" (using `createBrowserRouter` + `RouterProvider`) is correct for this architecture. Do NOT migrate to "framework mode" (which adds SSR complexity appropriate for Remix-style apps, not a Vite SPA with a separate FastAPI backend).

**clientLoader pattern — adopt for data-fetching routes:**

React Router 7 supports `clientLoader` for route-level data fetching. This is cleaner than fetching in `useEffect`:

```tsx
// React Router 7 clientLoader (if using framework/data router mode)
export async function clientLoader({ params }: Route.ClientLoaderArgs) {
    const part = await partsApi.getPart(params.id);
    return { part };
}

export default function PartPage({ loaderData }: Route.ComponentProps) {
    const { part } = loaderData;
    // ...
}
```

Evaluate whether the frontend's current `useEffect`-on-mount data fetching can be migrated to `clientLoader` during page refactors. This is "nice to adopt" for new pages, not a forced migration for existing pages.

---

### TypeScript

| | |
|--|--|
| **Pinned** | ~5.8.3 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed |

**Type-safety gaps to address:**

- Replace any `any` casts that exist in API response types with proper interfaces
- Ensure all `axios` response types use generic `AxiosResponse<T>` not raw `any`
- Use `satisfies` operator (TS 4.9+) for configuration objects that need narrowing:

```typescript
const config = {
    baseURL: '/api',
    timeout: 5000,
} satisfies Partial<AxiosRequestConfig>;
```

- Import types with `import type` consistently (already enforced by ESLint config, verify coverage)

---

### Vite + Build Tools

| | |
|--|--|
| **Vite pinned (frontend)** | 6.3.5 |
| **Vite pinned (extension)** | 6.4.2 |
| **Confidence** | HIGH — at current stable series |
| **Priority** | No upgrade needed |

**Vite 6 patterns — already correct:**

The `@tailwindcss/vite` plugin instead of PostCSS `tailwindcss` plugin is the correct Vite 6 + Tailwind v4 approach. The SWC plugin (`@vitejs/plugin-react-swc`) for fast JSX transpilation is correct.

**Environment variables:**

Vite 6 uses `import.meta.env.VITE_*` — ensure no `process.env` references remain in frontend code.

---

### Vitest

| | |
|--|--|
| **Pinned** | 3.2.4 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed |

**Current idioms to adopt:**

Coverage provider: `@vitest/coverage-v8` is the correct provider (already used). `c8` is the predecessor — ensure no lingering `c8` references.

Test context API (Vitest 3):

```typescript
// Vitest 3: use test.extend for shared context (preferred over beforeEach setup)
const test = base.extend<{ user: User }>({
    user: async ({}, use) => {
        const u = await createTestUser();
        await use(u);
        await cleanup(u);
    }
});
```

**Performance:** Enable `experimental.fsModuleCache` in vitest config for faster incremental re-runs:

```typescript
// vite.config.ts
export default defineConfig({
    test: {
        experimental: {
            fsModuleCache: true,
        }
    }
})
```

---

### Tailwind CSS

| | |
|--|--|
| **Pinned** | 4.1.7 |
| **Confidence** | HIGH — at current stable |
| **Priority** | No upgrade needed; clean up v3 patterns |

**The app is already on v4 (correct).** The cleanup work is removing v3 patterns that may have survived the migration.

**v3 patterns to eliminate during component refactors:**

1. `tailwind.config.js` should no longer exist — config belongs in CSS via `@theme {}`. If a `tailwind.config.js` or `tailwind.config.ts` is still present, migrate those theme values to the CSS file.

2. Three-directive imports:
```css
/* WRONG (v3 pattern) */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* CORRECT (v4) */
@import "tailwindcss";
```

3. Gradient utility renames:
```html
<!-- WRONG (v3 name) -->
<div class="bg-gradient-to-r from-blue-500 to-purple-500">

<!-- CORRECT (v4 name) -->
<div class="bg-linear-to-r from-blue-500 to-purple-500">
```

4. Border and divide color defaults changed from `gray-200` to `currentColor` in v4. Any `border` or `divide-*` class without explicit color now renders differently than in v3. Audit for visual regressions.

5. Arbitrary value overuse: `w-[37px]` style arbitrary values should be replaced with design token values or CSS custom properties registered in `@theme {}`. Keep arbitrary values only when a design token genuinely doesn't cover the case.

6. The `content` array in config is gone in v4 — Tailwind scans automatically. Delete any leftover `content: [...]` configuration.

**v4 idioms to use (not v3):**

```css
/* CSS-first theme definition (v4) */
@import "tailwindcss";

@theme {
    --color-brand: oklch(0.65 0.2 250);
    --font-heading: "Inter", sans-serif;
    --radius-card: 0.75rem;
}
```

```html
<!-- Use CSS vars directly as utilities -->
<div class="bg-(--color-brand) rounded-(--radius-card)">
```

---

## AWS / Infrastructure

### App Runner + RDS PG16 + S3 + SES + EventBridge

| | |
|--|--|
| **Confidence** | MEDIUM — based on official AWS docs and WebSearch |
| **Priority** | Audit-level; no infra swaps this milestone |

**Secrets management — current pattern needs verification:**

If secrets are injected as env vars via Terraform/App Runner config at deploy time (not via Secrets Manager native integration), consider migrating to App Runner's native Secrets Manager integration. This pulls secrets at runtime rather than bake-time:

- App Runner supports native Secrets Manager integration: the service IAM role needs `secretsmanager:GetSecretValue` on the specific secret ARNs
- Benefit: secrets rotation without redeploy; audit trail via CloudWatch
- The IAM role should be scoped to `Resource: arn:aws:secretsmanager:REGION:ACCOUNT:secret:carmodpicker/*` not `*`

**X-Ray tracing:**

App Runner has native AWS X-Ray integration. If not enabled, this is a one-checkbox change in the App Runner service config (or Terraform `observability_configuration_arn`). X-Ray provides distributed tracing across App Runner → RDS → S3 without code changes beyond adding the SDK.

**IAM least privilege — verify:**

The App Runner instance role and any Lambda/ECS crawler roles should follow least-privilege:
- S3: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` scoped to specific bucket ARNs (not `s3:*`)
- SES: `ses:SendEmail`, `ses:SendRawEmail` scoped to specific sender identity
- Secrets Manager: `secretsmanager:GetSecretValue` scoped to specific secret ARNs

**RDS connection pool:**

The default SQLAlchemy connection pool (`pool_size=5, max_overflow=10`) may be too small or too large for App Runner's concurrency model. App Runner can scale to multiple instances; each instance has its own pool. Verify `pool_pre_ping=True` is set (detects stale connections after RDS failover) and `pool_recycle` is set to `<1800` seconds (avoids hitting RDS's idle connection timeout).

```python
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,       # reconnect after RDS failover
    pool_recycle=1800,        # recycle before RDS idle timeout
)
```

---

## Anti-Patterns to Eliminate

| Anti-Pattern | Where | Why Bad | Fix |
|---|---|---|---|
| `session.query()` legacy API | `auth.py`, possibly others | SQLAlchemy 2.0 deprecated path | Migrate to `select()` + `session.scalars()` |
| `@app.on_event()` decorators | Anywhere they persist | Silently no-ops alongside `lifespan=` | Remove (or consolidate into lifespan) |
| `@validator` (Pydantic v1) | Schema files | Emits deprecation warnings in Pydantic v2 | Replace with `@field_validator` |
| `class Config:` (Pydantic v1) | Schema files | Deprecated in v2 | Replace with `model_config = ConfigDict(...)` |
| `.dict()` / `.parse_obj()` | Anywhere | Pydantic v1 method names | Replace with `.model_dump()` / `.model_validate()` |
| python-jose for JWT | `auth.py` | Unmaintained; FastAPI docs recommend PyJWT | Migrate to `PyJWT` |
| Lazy-loaded relationships in list endpoints | Services | N+1 queries | Add `selectinload()` to list queries |
| `process.env` in frontend | Any frontend file | Vite uses `import.meta.env` | Replace with `import.meta.env.VITE_*` |
| `bg-gradient-to-*` | Tailwind CSS | v3 class name, broken in v4 | Replace with `bg-linear-to-*` |
| `@tailwind base/components/utilities` | CSS files | v3 import syntax | Replace with `@import "tailwindcss"` |
| Logger injected via `Depends()` | `auth.py`, others | Overhead per request; non-standard | Replace with module-level `logging.getLogger(__name__)` |

---

## Version Summary Table

| Package | Pinned | Current Stable | Gap | Action |
|---|---|---|---|---|
| FastAPI | 0.128.0 | 0.136.0 | 8 minor | MUST upgrade (strict CT-Type behavior) |
| Uvicorn | 0.34.0 | 0.45.0 | 11 minor | SHOULD upgrade |
| SQLAlchemy | 2.0.41 | 2.0.49 | 8 patch | SHOULD upgrade |
| Alembic | 1.16.2 | 1.18.4 | 2 minor | SHOULD upgrade |
| Pydantic | 2.11.3 | 2.13.3 | 2 minor | SHOULD upgrade |
| python-jose | 3.5.0 | 3.5.0 | — | REPLACE with PyJWT 2.12.1 |
| psycopg2-binary | 2.9.10 | 2.9.12 | 2 patch | MINOR |
| boto3 | 1.42.91 | 1.42.93 | 2 patch | MINOR |
| mypy | 1.17.1 | 1.20.2 | 3 patch | MINOR |
| pytest | 9.0.3 | 9.0.3 | — | Current |
| pytest-asyncio | 1.3.0 | 1.3.0 | — | Current |
| React | 19.1.0 | 19.1.0 | — | Current |
| React Router | 7.6.0 | ~7.6 | — | Current |
| TypeScript | 5.8.3 | ~5.8 | — | Current |
| Vite | 6.3.5 / 6.4.2 | ~6.4 | — | Current |
| Vitest | 3.2.4 | ~3.2 | — | Current |
| Tailwind CSS | 4.1.7 | 4.1.7 | — | Current, clean v3 patterns |

---

## What NOT to Change This Milestone

| Decision | Rationale |
|---|---|
| Keep sync SQLAlchemy session | Migrating to AsyncSession + asyncpg is a major refactor. Not needed at current traffic. Correct to defer. |
| Keep React Router in library mode (not framework mode) | SPA + separate FastAPI backend is the right architecture. Framework mode adds SSR complexity that doesn't fit. |
| Keep psycopg2-binary | Coupled to sync session decision above. |
| Keep BaseHTTPMiddleware | Performance overhead negligible at current traffic. Readable. |
| Keep -n auto parallel pytest | The savepoint isolation pattern works correctly with xdist. No reason to change. |
| Keep axios (not fetch) | Axios intercepts + retry logic is already wired in. Migrating to native fetch is scope creep. |
| No RSC/Server Components | Vite SPA architecture. Server Components are a different deployment model. |
| No LLM APIs in this milestone | Per PROJECT.md — cost-gated until business model proven. |

---

## Sources

- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) — version verification, Starlette 1.0 breaking changes, lifespan idioms
- [FastAPI Lifespan Events Docs](https://fastapi.tiangolo.com/advanced/events/) — current lifespan pattern
- [FastAPI Discussion #11345](https://github.com/fastapi/fastapi/discussions/11345) — python-jose → PyJWT migration confirmation
- [SQLAlchemy 2.0 Async IO Docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — AsyncSession caveats, lazy loading in async
- [SQLAlchemy Relationship Loading](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html) — selectinload vs joinedload
- [Pydantic v2 Validators](https://pydantic.dev/docs/validation/latest/concepts/validators/) — field_validator, model_validator, annotated patterns
- [Tailwind CSS v4.0 Blog Post](https://tailwindcss.com/blog/tailwindcss-v4) — breaking changes from v3
- [PyPI: FastAPI](https://pypi.org/project/fastapi/) — current stable version
- [PyPI: SQLAlchemy](https://pypi.org/project/sqlalchemy/) — current stable version
- [PyPI: Pydantic](https://pypi.org/project/pydantic/) — current stable version
- [PyPI: Alembic](https://pypi.org/project/alembic/) — current stable version
- [PyPI: Uvicorn](https://pypi.org/project/uvicorn/) — current stable version
- [PyPI: PyJWT](https://pypi.org/project/PyJWT/) — recommended JWT replacement
- [PyPI: pytest-asyncio](https://pypi.org/project/pytest-asyncio/) — 1.3.0 confirmed current
- [AWS App Runner Security Best Practices](https://docs.aws.amazon.com/apprunner/latest/dg/security-best-practices.html) — IAM, Secrets Manager native integration
- [React 19 Release Notes](https://react.dev/blog/2024/12/05/react-19) — useOptimistic, useTransition, use()
- [pytest-asyncio 1.3.0 Docs](https://pytest-asyncio.readthedocs.io/en/stable/) — asyncio_mode configuration, legacy removal

---

*Stack research for: CarModPicker tech-debt refactor milestone*
*Researched: 2026-04-21*

# Feature Research: Quality Capabilities

**Domain:** Tech-debt audit milestone — quality/health capabilities for a mature Python + TypeScript + AWS monolith
**Researched:** 2026-04-21
**Confidence:** HIGH (grounded in CONCERNS.md inventory + verified tooling docs)

---

## Framing

This is not a product-feature document. "Features" here means **quality capabilities**: what a healthy production codebase at CarModPicker's shape and stage must have, should have, and must not prematurely build. All entries are anchored to the 8 active debt areas from PROJECT.md and the concrete gaps in CONCERNS.md.

The 8 debt areas:
1. **Auth** — auth.py split, 2FA/WebAuthn/OAuth accretion
2. **Crawler** — adapter auto-discovery, parse-failure alerting, parallelization, retry, health-check
3. **Observability** — structured logs, crawler metrics, request tracing, production monitoring
4. **DB/Migrations** — N+1 fix, indexes, migration hygiene, connection pool
5. **Parts/Dedup** — transactional part linking, inference engine maintainability
6. **Frontend** — page/component organization, API client consistency, type-safety
7. **Tests/CI** — backend + frontend coverage, pyright/eslint/bandit gates, concurrency tests
8. **Code-quality** — admin.py split, car_generations_data.py load, dead code, Base* compliance

---

## Table Stakes

Missing these means the team is flying blind, shipping is risky, or quality regression is invisible.

### Observability

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Error tracking (Sentry) | CONCERNS.md: "None detected — no Sentry, LogRocket". Unhandled exceptions in prod are invisible. Low-traffic window is the time to get baseline — not after launch. | S | `sentry-sdk[fastapi]` — auto-instruments FastAPI via `FastApiIntegration` + `StarletteIntegration`; init before app creation; `traces_sample_rate=0.1` for prod to cap cost | #3 Observability |
| Structured log enrichment: correlation ID on every line | Already uses `python-json-logger` + `RequestContextFilter` with correlation ID + user ID. Gap is ensuring crawler jobs emit the same correlation IDs so a job run is traceable end-to-end. | S | Extend `RequestContextFilter` to propagate job_id into log context for crawler runs | #3 Observability |
| Per-adapter crawler metrics | CONCERNS.md: "Admins must manually inspect job reports." No dashboard for success rate, parse time, or failure trends. | M | Emit CloudWatch `PutMetricData` calls at adapter teardown: `parse_success_count`, `parse_failure_count`, `parse_time_ms`, `urls_discovered`. One CloudWatch namespace per adapter. Costs ~$0.30/1000 custom metrics. | #2 Crawler, #3 Observability |
| CloudWatch alarm on parse-failure rate | Parse failures are currently silent data loss. CONCERNS.md: "auto-email superadmins if failures exceed baseline." | S | CloudWatch Alarm on `parse_failure_count / (parse_success_count + parse_failure_count) > 0.5` per adapter, SNS → SES email. Terraform-managed. | #2 Crawler, #3 Observability |
| RDS Performance Insights (query-level) | Already enabled (7-day retention). Gap: nobody is looking at it. Make it part of the N+1 fix validation workflow. | S | No new infra; wire into DB/Migrations phase as the verification tool. | #4 DB/Migrations |

### Testing

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Backend coverage threshold enforced in CI | TESTING.md: coverage XML generated but no `--cov-fail-under` gate. Coverage can silently drop. | S | Add `--cov-fail-under=70` to `pytest.ini` `addopts`. Start at 70, raise incrementally as debt is paid. | #7 Tests/CI |
| Frontend tests run in CI | TESTING.md: "Tests are NOT run in CI for frontend." Frontend logic has zero regression protection. | S | Add `npm test -- --run` step to `frontend-ci.yml` before the build step. Add `coverage.thresholds` in `vitest.config.ts` (`lines: 60` initially). | #7 Tests/CI |
| N+1 regression gate (build logs) | CONCERNS.md: N+1 query in build log posts is a known bug. After fix, must prevent regression. | S | Use `pytest-capquery` (2025-era tool) or manual SQLAlchemy event listener to assert `SELECT` count on `test_build_log_posts` equals 2 (one for posts, one for authors), not N+1. | #4 DB/Migrations, #7 Tests/CI |
| Concurrency test for part linking | CONCERNS.md: "No concurrency tests for part linking; coverage assumes serial execution." Race → orphaned canonical references. | M | `concurrent.futures.ThreadPoolExecutor` with 10 threads simultaneously calling link/unlink; assert no orphans after join. Runs in SQLite in-memory, no external dep. | #5 Parts/Dedup, #7 Tests/CI |
| Adapter smoke test harness | CONCERNS.md: "no integration test across all adapters." Every adapter has unit tests with mocked HTML but no shape validation. | M | A lightweight pytest parametrize over all registered adapter classes; assert they implement required interface methods, have non-empty `discover_product_urls` patterns, and parse fixtures produce `PartData` with required fields. Not live-site — uses fixture HTML. | #2 Crawler, #7 Tests/CI |

### CI/CD Gates

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| pyright in CI (already present, strengthen) | Already runs `pyright` in CI. Gap: strictness level may be too loose. | S | Add `"strict": true` for new files in `pyrightconfig.json` via per-directory overrides. Do not flip global strict — too noisy on brownfield. | #7 Tests/CI, #8 Code-quality |
| bandit in CI (already present, tune) | Already runs `bandit -r app`. Gap: no severity threshold. High-severity findings must fail the build. | S | Add `-l -i` (high severity, high confidence) or `--exit-zero` removal so bandit fails CI on HIGH severity. | #7 Tests/CI |
| eslint no-unused-vars and type-safety rules enforced | CONCERNS.md flags frontend type-safety gaps. eslint already runs but unclear if `@typescript-eslint/no-explicit-any` is error-level. | S | Audit `frontend/.eslintrc` / `eslint.config.*`: ensure `@typescript-eslint/no-explicit-any: error` and `@typescript-eslint/no-unsafe-*` rules are enabled. | #6 Frontend, #7 Tests/CI |
| Migration safety check: no destructive ops without explicit comment | Alembic autogenerate can silently emit `DROP COLUMN` if a model field is removed. A CI lint catches this before it reaches staging. | S | Add CI step: `grep -E "(drop_column|drop_table|drop_constraint)" alembic/versions/*.py` on changed files; fail if found without a `# SAFE:` annotation comment. Script-level, no new dep. | #4 DB/Migrations |
| pip-audit in CI (already present) | Already runs `pip-audit`. Confirms. Keep as-is; no gap. | — | Existing. Note: `python-dotenv` 1.1.0 → 1.2.2 already fixed. | #7 Tests/CI |

### Migration Hygiene

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Backwards-compatible migration discipline | CONCERNS.md: part linking is not transactional. When adding constraints (e.g., `UNIQUE` on `canonical_part_id`), a naive migration will fail on existing data with dupes. | M | Three-phase pattern: (1) add column nullable, (2) backfill data, (3) add constraint. All three phases as separate Alembic revisions. Document the pattern in CONVENTIONS.md. | #4 DB/Migrations, #5 Parts/Dedup |
| Index audit on all FK columns | CONCERNS.md: "full table scans if indexes are missing on join keys." 25+ models, many FK columns. | M | `alembic revision --autogenerate` will catch missing indexes only if `Index()` is declared in models. Audit: run `SELECT * FROM pg_indexes WHERE tablename = '...'` against local Postgres for all FK columns in all 22+ tables. Add `Index()` declarations to models, then autogenerate. | #4 DB/Migrations |
| Connection pool sizing for concurrent crawlers | CONCERNS.md: `DB_POOL_SIZE=20` exhausts under heavy crawl + API concurrency. | S | Set `DB_POOL_SIZE=50, max_overflow=10` for prod App Runner env. Add a connection pool monitoring CloudWatch metric: `pool_checkedout` from SQLAlchemy pool events. | #4 DB/Migrations |

### Crawler Health

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Adapter auto-discovery | CONCERNS.md: "Easy to forget to register new adapters; silent failures if an adapter's import fails." With 114 adapters this is a real maintenance tax. | M | Python `importlib` + directory scan of `crawlers/adapters/` subdirectories; auto-register classes that subclass `RetailerCrawlerAdapter`. Validate each loads without import error at startup. | #2 Crawler, #8 Code-quality |
| Pre-crawl retailer health check | CONCERNS.md: "Crawler starts on a retailer and hammers it for an hour before discovering the site is down." | S | Before `run_crawler()` per adapter: `GET robots.txt` with 5s timeout. 4xx/5xx or timeout → skip adapter, emit `adapter_skipped` CloudWatch metric, log warning. | #2 Crawler |
| Circuit breaker threshold reduction | CONCERNS.md: `RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5` wastes 62s of backoff on clearly-rate-limited sites. | S | Reduce to 2; add 429/503-specific bail path that skips remaining retries immediately and emits `adapter_rate_limited` CloudWatch event. | #2 Crawler |
| Adapter parallelization (inter-adapter) | CONCERNS.md: "sequential adapter execution" — one slow adapter blocks all subsequent. 100+ adapters × slow retailer = hours. | M | `asyncio.gather()` with a semaphore (e.g., max 10 concurrent adapters) over the adapter list in `run_crawlers()`. Each adapter gets its own DB session (already the case per-adapter). | #2 Crawler |

### Dependency Management

| Capability | Why Table Stakes | Complexity | Tool/Library | Debt Area |
|------------|-----------------|------------|--------------|-----------|
| Automated dependency update PRs | No Renovate or Dependabot configured. `python-dotenv` was updated reactively (CONCERNS.md). | S | Enable GitHub Dependabot (`dependabot.yml`) for `pip` (backend), `npm` (frontend + chrome-extension), and `github-actions`. Weekly cadence. Group patch updates into single PR. | #7 Tests/CI |
| curl_cffi monitoring | CONCERNS.md: "C extension, subject to version-specific memory safety issues." Dependabot won't catch CVEs in C extensions until NVD records them. | S | Add `curl_cffi` to a watched list in `pip-audit` run. Subscribe to `curl_cffi` GitHub releases via watch. No automated fix — just awareness. | #7 Tests/CI |

---

## Differentiators

These raise quality meaningfully above table stakes. Build selectively — each requires justification relative to the current traffic level and team size (solo dev).

| Capability | Value Proposition | Complexity | Tool/Library | Debt Area | Build Trigger |
|------------|-------------------|------------|--------------|-----------|---------------|
| OpenTelemetry request tracing | Correlates a user request across FastAPI → DB → S3 → SES. Reveals latency breakdowns invisible in logs. Real value: when a user says "search is slow" you can see exactly which query took 800ms. | L | `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, ADOT collector → CloudWatch. Significant setup; defer unless CloudWatch Insights isn't enough. | #3 Observability | After Sentry + CloudWatch alarms are live and you have a specific "this is still opaque" problem |
| Database-backed feature flags | CONCERNS.md notes rate-limiter `ENABLE_RATE_LIMITING=false` env-var is a risk in prod. Feature flags let ops toggle per-endpoint rate limiting without a deploy. Also enables dark-launching crawler changes. | L | Flagsmith (self-hosted, PostgreSQL-backed) or a lightweight custom `feature_flags` table + FastAPI `Depends()` helper. Flagsmith adds infra complexity (another service). Custom table is ~2 hours of work and fits the existing pattern. Recommend custom table first. | #1 Auth, #2 Crawler | After crawler parallelization lands and you want safe dark-launch of new adapter behavior |
| Optimistic concurrency on part linking | CONCERNS.md: "Part linking logic is not transactional — race conditions can leave orphaned canonical references." A `version_id` column on `canonical_parts` catches concurrent writes. | S | SQLAlchemy `__mapper_args__ = {"version_id_col": version_id}` on the canonical part model. Raises `StaleDataError` on concurrent write; caller retries. Pairs with the concurrency test above. | #5 Parts/Dedup | Schedule with the transactional part-linking fix |
| Query profiling assertions in CI (pytest-capquery) | Prevents N+1 regressions from being introduced after fixes are made. Once the build-log N+1 is fixed, the fix must not regress. | M | `pytest-capquery` wraps SQLAlchemy engine at driver level; snapshot the expected query count per test; fail on deviation. Requires careful fixture scoping with xdist. | #4 DB/Migrations, #7 Tests/CI | Immediately after the N+1 fix lands |
| Synthetic canary crawler run | Run a known-good adapter against a known-stable retailer on a schedule (e.g., daily) and alert if parse success drops to 0. Catches retailer DOM changes within 24h instead of during the next manual crawl audit. | M | EventBridge rule → Lambda or App Runner task that runs a single "canary" adapter (pick the most stable retailer). Compare against expected part count ± 10%. Emit CloudWatch alarm if diverges. | #2 Crawler, #3 Observability | After per-adapter CloudWatch metrics are live |
| S3 lifecycle policy for crawl archive | CONCERNS.md: "S3 HTML snapshots will add significant volume. No built-in retention policy." | S | Terraform: `aws_s3_bucket_lifecycle_configuration` on `carmodpicker-prod-crawl-html` — transition to Glacier after 90 days, delete after 365 days. 30-minute Terraform task. | #2 Crawler | Alongside any crawler storage work |

---

## Anti-Features

Explicitly deferred. These will be requested, seem reasonable, but create disproportionate complexity at the current scale.

| Anti-Feature | Why Requested | Why Avoid | What to Do Instead | Debt Area |
|--------------|--------------|-----------|-------------------|-----------|
| Custom Prometheus + Grafana stack | Full metric visibility, custom dashboards | Ops burden: another two services to run (Prometheus server + Grafana), alerting pipeline complexity, no native AWS integration. App Runner doesn't expose a scrape endpoint by default. | CloudWatch custom metrics (`PutMetricData`) + CloudWatch dashboards. Same data, managed service, zero new infra. | #3 Observability |
| Microservices split (crawler as separate service) | Crawlers are a distinct subsystem; decoupling seems clean | At 114 adapters and solo-dev velocity, splitting crawler into a separate service adds a deployment pipeline, cross-service auth, and network overhead with zero scaling benefit at current traffic. App Runner + ECS Fargate tasks already give you "run crawlers independently." | Keep crawler in the monolith. The ECS Fargate task path already isolates crawler runs from API traffic. | #2 Crawler |
| K8s migration | Container orchestration, horizontal scaling | App Runner handles auto-scaling with zero ops. K8s adds ~40h of migration and ongoing ops tax. Revisit only if App Runner pricing or limits become a constraint. | Stay on App Runner. Add read replica on RDS if DB becomes the bottleneck. | Infra |
| LaunchDarkly or full Flagsmith hosted | Enterprise feature flags | Overkill for a solo dev / low-traffic platform. LaunchDarkly is $200+/mo. Flagsmith hosted adds a vendor dependency. | Simple `feature_flags` DB table + cache. If complexity grows, self-host Flagsmith later. | #1 Auth |
| OpenAPI contract tests / Pact | API schema drift detection between frontend and backend | Valuable at team scale. At solo dev + monorepo the contract is enforced by pyright (shared types) and the TypeScript API client is the single consumer. Pact adds test infrastructure without solving a real current problem. | Keep TypeScript API client as the contract. Add `tsc --noEmit` on the client types against the OpenAPI schema using `openapi-typescript` if drift becomes a problem. | #6 Frontend |
| Error-budget-based deploys | SRE practice: block deploys if error rate exceeds budget | No SLO exists; traffic is near zero. Without an SLO the error budget is meaningless. Adds process overhead with no signal. | Add Sentry + CloudWatch alarms first. Define an SLO (e.g., 99.5% requests < 500ms) only once you have baseline data. | #3 Observability |
| SBOM generation + supply chain signing | Compliance, SLSA provenance | Not a B2B SaaS; no compliance requirement. pip-audit + npm audit already cover known CVEs. SBOM adds tooling (Syft/Grype) with no actionable output for this context. | Continue pip-audit + npm audit in CI. Revisit when serving enterprise customers or when compliance is a sales requirement. | #7 Tests/CI |
| Real-time WebSocket crawler progress | Live admin dashboard showing crawl progress | High complexity (needs SSE or WebSocket endpoint, state broadcast, reconnect logic). Admin already gets email on job completion. | Background job status polling via existing `GET /api/admin/jobs/{id}` endpoint is sufficient. Polish the admin dashboard UI instead. | #2 Crawler |

---

## Feature Dependencies

```
[Per-adapter CloudWatch metrics]
    └──enables──> [CloudWatch parse-failure alarm]
                      └──enables──> [Canary crawler run]

[N+1 fix (build logs)]
    └──requires──> [N+1 regression gate (pytest-capquery)]

[Adapter parallelization]
    └──requires──> [Pre-crawl health check]  (parallelizing without health checks amplifies hammering)
    └──enables──> [Canary crawler run]  (stable parallel runner makes canary meaningful)

[Optimistic concurrency (part linking)]
    └──requires──> [Concurrency test for part linking]  (gate must exist before the fix to catch regressions)

[Coverage threshold CI gate]
    └──enables──> [Frontend tests in CI]  (threshold only meaningful once tests run in CI)

[Adapter auto-discovery]
    └──enables──> [Adapter smoke test harness]  (harness parametrizes over auto-discovered adapters)
```

---

## Prioritization Matrix

| Capability | Dev Impact | Risk Reduction | Cost (S/M/L) | Priority |
|------------|-----------|---------------|------------|---------|
| Sentry error tracking | HIGH — ends "flying blind" | HIGH | S | P1 |
| Frontend tests in CI | HIGH — closes zero-protection gap | HIGH | S | P1 |
| Backend coverage threshold (--cov-fail-under) | MEDIUM | MEDIUM | S | P1 |
| Migration safety CI check (no DROP without annotation) | MEDIUM | HIGH | S | P1 |
| Per-adapter CloudWatch metrics | HIGH — crawler visibility | HIGH | M | P1 |
| Pre-crawl retailer health check | MEDIUM | MEDIUM | S | P1 |
| Circuit breaker threshold reduction | LOW | MEDIUM | S | P1 |
| N+1 regression gate (pytest-capquery) | MEDIUM | HIGH | M | P1 |
| Concurrency test for part linking | MEDIUM | HIGH | M | P1 |
| Adapter auto-discovery | MEDIUM | MEDIUM | M | P1 |
| CloudWatch parse-failure alarm | HIGH | HIGH | S | P1 |
| Index audit + FK index additions | MEDIUM | MEDIUM | M | P1 |
| Connection pool resize (prod env) | LOW | MEDIUM | S | P1 |
| Dependabot configuration | LOW | MEDIUM | S | P2 |
| Backwards-compatible migration discipline (documented pattern) | MEDIUM | HIGH | S | P2 |
| Optimistic concurrency on part linking | MEDIUM | HIGH | S | P2 |
| Adapter smoke test harness | MEDIUM | MEDIUM | M | P2 |
| bandit severity threshold | LOW | MEDIUM | S | P2 |
| eslint any/unsafe rules to error | MEDIUM | MEDIUM | S | P2 |
| S3 lifecycle policy (crawl archive) | LOW | LOW | S | P2 |
| Adapter parallelization | HIGH — crawl speed | LOW | M | P2 |
| Query profiling assertions in CI | MEDIUM | HIGH | M | P2 |
| Feature flags (custom DB table) | MEDIUM | MEDIUM | M | P3 |
| Canary crawler run | MEDIUM | MEDIUM | M | P3 |
| OpenTelemetry tracing | LOW at current traffic | LOW | L | P3 |

**Priority key:**
- P1: Build this milestone — directly closes a CONCERNS.md gap, low/medium complexity
- P2: Build this milestone if the phase addresses the related debt area — medium complexity, high value
- P3: Defer or build only if adjacent work makes it cheap

---

## Sources

- CONCERNS.md (authoritative debt inventory, 2026-04-22) — all table-stakes items are directly traceable to entries there
- TESTING.md (testing patterns audit, 2026-04-22) — CI gaps, coverage configuration, frontend test absence
- INTEGRATIONS.md (integration audit, 2026-04-22) — observability gaps, CloudWatch setup, no Sentry confirmed
- [Sentry FastAPI integration docs](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [pytest-capquery for N+1 detection](https://dev.to/fmartins/stop-testing-your-code-and-ignoring-your-database-catching-n1-in-pytest-4pd5)
- [Vitest coverage thresholds](https://vitest.dev/guide/coverage)
- [SQLAlchemy optimistic locking](https://oneuptime.com/blog/post/2026-01-25-optimistic-locking-sqlalchemy/view)
- [Flagsmith FastAPI integration](https://medium.com/@r_bilan/integrating-flagsmith-with-fastapi-a-step-by-step-guide-for-ff-f85ac90bc6a3)
- [OpenTelemetry + FastAPI + CloudWatch](https://aws.amazon.com/blogs/mt/introducing-opentelemetry-promql-support-in-amazon-cloudwatch/)
- [Alembic backwards-compatible migrations](https://medium.com/exness-blog/alembic-migrations-without-downtime-a3507d5da24d)
- [Renovate vs Dependabot 2025](https://www.turbostarter.dev/blog/renovate-vs-dependabot-whats-the-best-tool-to-automate-your-dependency-updates)

---
*Feature research for: CarModPicker tech-debt milestone — quality capabilities*
*Researched: 2026-04-21*

# Pitfalls Research

**Domain:** Tech-debt audit + refactor milestone — brownfield FastAPI + React + crawler + Chrome extension
**Researched:** 2026-04-21
**Confidence:** HIGH (grounded in the actual codebase; all claims traceable to specific files)

---

## Critical Pitfalls

### Pitfall 1: Refactor Death Spiral — Enthusiasm Without Momentum Gates

**Severity:** HIGH

**What goes wrong:**
The milestone starts as a focused cleanup. Three weeks in, eight things are half-done: `admin.py` split started but not finished, auth refactor broke something in the TOTP flow, N+1 fix works locally but the query count assertion isn't in CI, and the car-data lazy-load is half-migrated. The 80%-done state is worse than the starting state — the original code at least worked. Momentum collapses.

**Why it happens:**
Debt work has no visible user-facing output. There's no reward loop. Every phase touches fragile code, which means each one can surface unexpected bugs that feel like "scope creep" but are actually just debt being honest. Solo developers with AI-assisted coding move fast in short bursts but can lose thread continuity across sessions.

**How to avoid:**
- Each phase must have a concrete, binary done-state: "CI is green, old code is deleted, coverage didn't drop." No "mostly done."
- Enforce a "kill the old code before calling it done" rule. If `admin.py` is being split, the old monolith must be deleted, not left beside the new files.
- Commit after every logical sub-step. AI sessions lose context; a commit is the handoff artifact.
- Define scope ruthlessly at phase start. If a phase is "split admin.py," it is NOT "also refactor the job service it calls."

**Warning signs:**
- More than one file has both old and new versions simultaneously for more than a single work session
- Git log shows many small commits on different files with no clear "done" commit
- Coverage report shows the same module appearing in uncovered lines across multiple sessions

**Phase to address:**
Every phase — enforce these constraints in the phase definition, not as an afterthought. Especially critical for: Auth refactor (Area 1), Admin.py split (Area 8), Crawler hardening (Area 2).

---

### Pitfall 2: Double-Maintenance Trap — Old and New Code Left in Place

**Severity:** HIGH

**What goes wrong:**
`admin.py` gets split into `admin_jobs.py`, `admin_crawlers.py`, `admin_stats.py`. But the original `admin.py` stays registered in `EndpointRegistry` as a safety net "until we're sure the new ones work." A week later both are running. Bugs get fixed in one place, not the other. A month later nobody knows which version is authoritative.

In this codebase specifically: `adapters/__init__.py` currently has 114 manually-registered imports. During auto-discovery refactor, there's a real risk of running both the old manual registry and the new scan-based one simultaneously.

**Why it happens:**
Fear of breaking prod. Absence of a clear deletion checkpoint.

**How to avoid:**
- Deletion is part of the definition of done. If you haven't deleted the old code, the phase isn't closed.
- For `admin.py` split: `EndpointRegistry` registration of old `admin` router must be removed in the same commit that adds the new routers. No overlap window.
- For adapter auto-discovery: implement the new discovery mechanism, validate it produces the same set as the manual registry, then delete the manual imports list entirely. Use a test that asserts the two sets are identical before the cutover.
- Use git to enforce: the PR that adds new code must also delete old code.

**Warning signs:**
- Two files doing the same job exist simultaneously
- `from app.api.endpoints import admin` still in `main.py` after the split
- Both ADAPTER_REGISTRY and a new auto-discovery mechanism are loaded

**Phase to address:**
Area 8 (admin.py split), Area 2 (crawler adapter auto-discovery)

---

### Pitfall 3: Alembic Autogen Missing Unnamed Constraints — Silent Prod Failure

**Severity:** HIGH

**What goes wrong:**
`alembic revision --autogenerate` produces a migration that looks correct locally, runs against SQLite in CI (which is more permissive), passes CI, and then fails on prod RDS PostgreSQL 16 because a constraint drop references `None` (unnamed constraint). PostgreSQL requires explicit constraint names for `op.drop_constraint()`. SQLite ignores it entirely.

This has already happened: three migrations in the history contain `op.drop_constraint(None, ...)`:
- `097024200e60_add_canonical_part_id_to_parts.py:33`
- `172d1c205fb3_add_build_list_phases.py:45`
- `6eae6b1393c5_add_brand_model.py:48`

These are latent prod migration failures waiting for someone to run `downgrade`.

**Why it happens:**
Autogenerate doesn't always know the constraint name on SQLite-generated schemas. The developer sees the migration file, trusts the tooling, and doesn't spot `None` in the constraint name position.

**How to avoid:**
- Add a pre-commit or CI check: `grep -r "drop_constraint(None" alembic/versions/` fails the build if it finds matches.
- Before any migration is merged, run `alembic downgrade -1 && alembic upgrade head` against a real Postgres instance (local Docker). Not SQLite.
- Fix the three existing `drop_constraint(None, ...)` instances before any new schema work touches those tables.
- Configure `alembic.ini` with `naming_convention` to force all constraints to be named from the start. This is the correct long-term fix.

**Warning signs:**
- Migration file contains `drop_constraint(None, ...)` anywhere
- `alembic downgrade` was never tested locally (only `upgrade head`)
- CI uses only SQLite but prod is Postgres (this codebase's current state — SQLite tests don't catch this)

**Phase to address:**
Area 4 (DB / migrations / perf pass) — fix the existing three, add naming_convention, add CI grep check.

---

### Pitfall 4: SQLite / PostgreSQL Feature Divergence — Tests Green, Prod Broken

**Severity:** HIGH

**What goes wrong:**
Tests use SQLite in-memory. PostgreSQL 16 has features and constraints SQLite doesn't: strict foreign key enforcement by default, real enum types, generated columns, check constraints with names, upsert behavior differences, `ON CONFLICT DO UPDATE` syntax. A refactor that touches parts deduplication (canonical part linking, `pg_insert` upsert) or adds Postgres-specific constructs will pass CI and silently fail or behave differently in prod.

Specifically: `runner.py` already uses `from sqlalchemy.dialects.postgresql import insert as pg_insert`. This import will fail if ever run in a SQLite test context. The test suite currently avoids crawler ingestion paths — that's the only reason this hasn't broken CI.

**Why it happens:**
The SQLite-in-CI decision was made for speed and simplicity (correct tradeoff). The risk is that the test boundary is implicit, not explicit. Developers adding new tests don't know which code paths are Postgres-only.

**How to avoid:**
- Document explicitly which modules are Postgres-only (crawler ingestion, `pg_insert` usage) and mark them with `pytest.mark.skip` or separate them into integration tests that run against a real Postgres Docker instance.
- Add a `conftest.py` check: if `pg_insert` is imported in non-crawler test code, fail with a clear error.
- For the parts dedup consolidation (Area 5): any new upsert/merge logic must be tested against Postgres, not just SQLite. Spin up a local Postgres Docker for these specific tests.
- The existing `check_db_ready()` and `get_db()` session behavior should be validated against Postgres connection pool exhaustion scenarios, not just SQLite.

**Warning signs:**
- New test imports `from sqlalchemy.dialects.postgresql import ...`
- A refactor adds `ON CONFLICT` or `RETURNING` clauses that are Postgres-specific
- Coverage for parts ingestion path is low but tests are "passing"

**Phase to address:**
Area 4 (DB / migrations / perf), Area 5 (parts dedup consolidation)

---

### Pitfall 5: Breaking FastAPI `Depends()` During Router Split — Silent 422s or Auth Bypass

**Severity:** HIGH

**What goes wrong:**
When splitting `admin.py` into sub-routers, each new router must have its own `Depends(get_current_admin_user)` or `Depends(get_current_superuser)` guards. If a route handler is moved to a new file but its dependency is inherited from the old router's include prefix rather than declared on the route itself, the endpoint either loses auth protection (if the router prefix dependency is stripped) or silently 422s on auth parameters (if the dependency is renamed or shadowed).

FastAPI dependency injection scope is a frequent source of subtle bugs during router splits. A missing `Depends()` on an admin endpoint is a security regression, not just a bug.

**Why it happens:**
Developers assume router-level `dependencies=` propagate correctly to all routes. They do — but only if the router is included correctly. During a split, the registration path changes, and assumptions about which `APIRouter` carries which dependencies break.

**How to avoid:**
- Every route in the new admin sub-routers must declare its auth dependency explicitly on the route decorator, not solely at router-include time.
- Write an integration test for each new admin sub-router that verifies: (1) an unauthenticated request returns 401, (2) a regular user returns 403, (3) an admin user succeeds.
- Use the existing `test_admin_user` and `test_superuser_user` fixtures — they exist for exactly this purpose.
- After the split, grep for any admin route that lacks `current_user: DBUser = Depends(get_current_admin_user)` or equivalent.

**Warning signs:**
- A new admin route returns 200 for an unauthenticated request in tests
- `Depends()` appears only in `app.include_router(admin_router, dependencies=[...])` but not on individual route handlers
- CI passes but no test asserts auth behavior for the new routes

**Phase to address:**
Area 8 (admin.py split), Area 1 (auth refactor)

---

### Pitfall 6: N+1 Reintroduction During Refactor

**Severity:** HIGH

**What goes wrong:**
The known N+1 in `build_logs.py:119` gets fixed with `joinedload`. Six months later a refactor of the build-log post listing (to add a new field or paginate differently) iterates over posts again and introduces a new loop query. Without a query-count assertion in the test suite, CI stays green while prod performance silently regresses.

More broadly: the `BaseCRUDService` abstraction means developers don't always see the ORM queries they're generating. A refactor that changes how related data is fetched (e.g., accessing `post.author` inside a loop after a session refactor) can introduce N+1 without any obvious code change.

**Why it happens:**
ORM makes queries invisible. SQLAlchemy's default lazy loading means `post.author` inside a loop fires a query per iteration — no warning, no error, just slow code.

**How to avoid:**
- When fixing the existing N+1, add a `sqlalchemy-query-counter` or equivalent assertion: `assert query_count == 1` (or whatever the expected fixed count is). This becomes the regression guard.
- For any endpoint that returns a list of objects with relationships, use `selectinload` or `joinedload` explicitly in the service layer, never rely on lazy-load defaults.
- Models currently use `lazy="selectin"` for only one relationship (`part.py:65`). Audit all other `relationship()` declarations during Area 4 and set explicit loading strategies.
- Run `SQLALCHEMY_WARN_20=1` locally during development to surface lazy-load warnings.

**Warning signs:**
- An endpoint's response time grows proportionally with the list size
- No query count assertion exists for the fixed N+1 endpoint
- A new field is added to a list endpoint without also checking how it's loaded

**Phase to address:**
Area 4 (DB / migrations / perf pass) for the fix; Area 7 (test coverage) for the regression guard.

---

### Pitfall 7: Crawler Adapter Discovery Breakage — Silent Adapter Dropout

**Severity:** HIGH

**What goes wrong:**
The current `adapters/__init__.py` manually registers 114 adapters with explicit imports. When auto-discovery is implemented (Area 2), a new scan-based registry replaces the manual list. If any adapter has an import error (e.g., its dependencies changed, a circular import was introduced), the new auto-discovery silently skips it. With the manual registry, a broken import crashes startup loudly. With auto-discovery, a broken import means that adapter runs zero pages and nobody notices.

**Why it happens:**
Auto-discovery improves ergonomics (no manual registration) but trades import-time failure for silent runtime dropout. The failure mode is invisible — the crawler runs, ingests from other adapters, and the broken adapter is simply absent from results.

**How to avoid:**
- Auto-discovery must validate imports, not just scan for files. Catch `ImportError` per adapter and emit a startup ERROR log (not just a warning) with the full traceback. Fail the entire crawler run if any adapter fails to load in strict mode.
- Add a CI test that asserts `len(ADAPTER_REGISTRY) == expected_count`. If an adapter silently drops out, the count assertion fails.
- During the transition period: run old and new registry in parallel, assert they produce the same set of adapter names, then delete the old one. Don't delete first.
- Keep the adapter validation test (asserting count) as a permanent CI gate.

**Warning signs:**
- Adapter count in `ADAPTER_REGISTRY` drops between deploys without a corresponding deletion commit
- Crawl job reports show fewer adapters run than expected
- A new adapter file exists in the directory but doesn't appear in job reports

**Phase to address:**
Area 2 (crawler system hardening)

---

### Pitfall 8: Auth Refactor Breaking 2FA / WebAuthn / OAuth Flows — Regression in Non-Happy-Path

**Severity:** HIGH

**What goes wrong:**
`auth.py` is 1,195 lines covering email/password, TOTP 2FA, WebAuthn passkeys, Google OAuth, and JWT session management — all accreted together. During the split, it's easy to correctly extract the happy path but break a non-happy-path: TOTP failure handling, the OAuth account-link flow for existing users, the WebAuthn assertion verification, or the redirect chain after email verification. These flows are rarely exercised in CI because they're hard to test (real TOTP secrets, WebAuthn ceremony, OAuth redirects).

**Why it happens:**
Non-happy-path auth flows are undertested. The existing test suite covers `test_login`, but probably not `test_login_with_totp_then_totp_secret_rotated` or `test_oauth_link_existing_account_already_has_oauth`. When you move code without tests, you can't know what broke.

**How to avoid:**
- Before splitting `auth.py`, write characterization tests for every flow that currently works: TOTP enable/disable, TOTP verify-fail, WebAuthn enroll, WebAuthn assert, Google OAuth new account, Google OAuth link existing account, email verify success, email verify expired token, JWT expiry with configurable TTL. These tests don't need to be perfect — they just need to exercise the code paths and assert the HTTP status codes.
- Split is then safe because tests will catch regressions.
- Never delete code from `auth.py` until the corresponding test passes in the new module.

**Warning signs:**
- Auth refactor PR has no new test files
- Coverage of `auth.py` drops after the split (it should stay the same or increase)
- The TOTP or WebAuthn code paths have zero test coverage before the refactor starts

**Phase to address:**
Area 1 (auth refactor) — tests first, split second.

---

### Pitfall 9: Chrome Extension API Schema Drift — Silent Breaking Change

**Severity:** HIGH

**What goes wrong:**
A backend refactor changes a response schema (renames a field, adds a required field, changes a type) in an endpoint the Chrome extension calls. The extension is not updated. The extension either silently breaks (users can't submit parts) or continues working with stale data. The extension is not in CI for backend changes — CI only triggers on `backend/**` or `frontend/**` path changes, not `chrome-extension/**`. There is no contract test between extension and backend.

This is especially likely during Area 5 (parts dedup consolidation), which touches the parts schema, and Area 1 (auth refactor), which touches auth endpoints the extension uses for its token handoff.

**Why it happens:**
The extension is treated as a separate project. Backend developers don't have a mental model of which API endpoints the extension calls.

**How to avoid:**
- Create and maintain a `chrome-extension/API_CONTRACT.md` that lists every backend endpoint the extension calls, with expected request/response shape.
- When a backend endpoint changes its schema, the PR must include an update to that contract doc and a corresponding extension change.
- Add the extension's endpoint list to a CI check: if `backend/app/api/schemas/parts.py` changes, the CI step warns to verify the extension contract.
- For auth: the extension's `background.ts:156` 10-minute nonce TTL is a known issue — fixing it is part of Area 1.

**Warning signs:**
- A parts schema field is renamed without checking `chrome-extension/src/`
- The extension popup shows errors users don't report (because traffic is low)
- `chrome-extension/API_CONTRACT.md` doesn't exist (currently the case)

**Phase to address:**
Area 1 (auth refactor), Area 5 (parts dedup), Area 6 (frontend cleanup — treat extension as a consumer alongside the web frontend)

---

### Pitfall 10: Refactoring Without a Coverage Baseline — Silent Regression

**Severity:** HIGH

**What goes wrong:**
CI runs tests with coverage, but there's no coverage threshold enforced. Coverage can drop from 70% to 50% across this milestone if refactored code moves into untested paths. CI stays green. Nobody notices until a production bug surfaces in code that "should have been tested."

The frontend CI is worse: tests are not run in CI at all (`frontend-ci.yml` runs lint, type-check, and build — but not `npm test`). Frontend coverage is completely untracked in CI.

**Why it happens:**
Coverage thresholds weren't set initially. Adding them retroactively requires knowing the current baseline first.

**How to avoid:**
- Immediately before the milestone starts: run `pytest --cov=app --cov-report=term-missing` and record the current coverage number as a floor. Configure `pytest.ini` with `--cov-fail-under=<baseline>`.
- Add `npm test` to `frontend-ci.yml`. This should have been there already.
- Coverage must not decrease phase-over-phase. If a refactor drops coverage, either add tests to the refactored code or explicitly justify the drop in the PR description.
- Track coverage as a metric, not just a pass/fail: look at per-module coverage for the modules being changed.

**Warning signs:**
- `pytest.ini` has no `--cov-fail-under` configured (currently the case)
- Frontend tests not in CI (currently the case)
- A PR deletes a test file because "the code was refactored"

**Phase to address:**
Area 7 (test coverage & CI gates) — this should be the first phase or run concurrently with every other phase.

---

## Moderate Pitfalls

### Pitfall 11: `car_generations_data.py` Load Strategy — Startup Latency Regression

**Severity:** MEDIUM

**What goes wrong:**
If `car_generations_data.py` (8,412 lines) is moved to lazy-load (correct fix, per CONCERNS.md) but the refactor is done incorrectly, the lazy-load fires on every import of `car_inference.py` instead of once per process. With `uvicorn --reload` during development, this hits on every reload. In production, App Runner cold starts become noticeably slower.

**How to avoid:**
- Use a module-level singleton with `functools.lru_cache` or a `_cache = None` guard pattern. The data loads once, stays in memory.
- Test the fix with a simple `python -c "import time; t=time.time(); from app.core.car_inference import infer_car_generations; print(time.time()-t)"` before and after.
- Do not move the data to a database query path unless you add an in-process cache — a DB query on every car inference call at crawler scale would be far worse than the current eager import.

**Warning signs:**
- `uvicorn --reload` takes noticeably longer after the refactor
- Crawler initialization time increases

**Phase to address:**
Area 8 (general code-quality sweep)

---

### Pitfall 12: Rate-Limit Circuit Breaker Masking Real Bugs

**Severity:** MEDIUM

**What goes wrong:**
`RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5` in `runner.py:70`. When a retailer's site is broken (not rate-limiting, but returning 503 due to a broken CDN or DNS issue), the circuit breaker fires after 5 retries. The log says "circuit breaker tripped" but the real cause is a parse failure or a structural site change, not rate limiting. Reducing the threshold (correct for rate-limit cases) makes this ambiguity worse.

**How to avoid:**
- Distinguish circuit breaker cause before tripping: log the specific HTTP status codes seen (429 vs. 503 vs. connection timeout). The circuit breaker message should include "5× 429 (rate limited)" vs. "5× 503 (upstream error)" — these require different follow-up actions.
- When hardening the crawler (Area 2), do not just reduce the threshold; fix the signal quality so operators know why it tripped.

**Warning signs:**
- Circuit breaker logs say "rate limited" but manual visit to the retailer site shows it's up
- Multiple adapters trip the circuit breaker on the same day (systemic issue, not rate limiting)

**Phase to address:**
Area 2 (crawler hardening), Area 3 (observability)

---

### Pitfall 13: ThreadPoolExecutor Sizing — Connection Pool Exhaustion During Parallelization

**Severity:** MEDIUM

**What goes wrong:**
`runner.py` currently runs adapters serially. CONCERNS.md flags parallelizing adapter execution as a scaling improvement. If parallelization is implemented naively — e.g., `ThreadPoolExecutor(max_workers=50)` — and each worker holds a `SessionLocal` for its entire run, 50 workers × 1 session = 50 connections. The pool is `DB_POOL_SIZE=25` + `DB_MAX_OVERFLOW=75` = 100 max. This looks fine until you add API traffic reserve (`API_CONNECTION_RESERVE=20`) and realize a full parallel crawl of 114 adapters would exceed the pool.

**How to avoid:**
- The existing code in `session.py` already exports `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, and `API_CONNECTION_RESERVE` for exactly this reason. The crawler runner should compute max parallel workers as `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE`, not hardcode a number.
- Test connection pool exhaustion locally with `max_workers = pool_max + 1` and verify it errors cleanly rather than deadlocking.
- Add a startup log: "Crawler will use N parallel workers (pool capacity: X, API reserve: Y)."

**Warning signs:**
- `QueuePool limit of size X overflow Y reached` in crawler logs
- API endpoints start returning 503 during crawl runs
- Crawler workers hang indefinitely (they're waiting for a connection that never becomes available)

**Phase to address:**
Area 2 (crawler hardening)

---

### Pitfall 14: Context Re-renders Cascading — Frontend Performance Regression During Cleanup

**Severity:** MEDIUM

**What goes wrong:**
The frontend has two contexts: `AuthContext` and `AppSettingsContext`. If the frontend cleanup (Area 6) moves state out of local component state into context, or restructures how context consumers are organized, any state change in `AuthContext` will re-render every component that calls `useAuth()`. This is the canonical React context anti-pattern: a broad context with frequently-changing state causes full re-renders on every change.

At low traffic this is invisible. With React 19's concurrent features, it may produce subtle rendering order issues.

**How to avoid:**
- Do not add new state to existing contexts during cleanup. If new state is needed, create a narrowly-scoped context or use `useState` + prop drilling for localized state.
- After any restructure involving context, use React DevTools Profiler to check which components re-render on auth state changes. If more than 3-4 top-level components re-render on a token refresh, the context is too broad.
- Split `AuthContext` if it currently holds both auth state and user-preference state — these have different update frequencies.

**Warning signs:**
- React DevTools shows "why did this render?" fires on unrelated components after an auth state change
- Page transitions feel sluggish after context restructure
- `useAuth()` is called in deeply-nested leaf components that don't need auth state

**Phase to address:**
Area 6 (frontend structure cleanup)

---

### Pitfall 15: Vite HMR vs. Production Build Divergence

**Severity:** MEDIUM

**What goes wrong:**
During frontend cleanup (Area 6), a component or module works in `npm run dev` (Vite HMR) but fails in `npm run build` (production ESM bundle). Common causes: circular imports that HMR tolerates but bundler tree-shaking rejects, dynamic imports that work with dev server but produce wrong chunk splits in prod, or environment variables accessed at module scope that differ between dev and prod.

The `Api.ts` file is 1,519 lines — a monolith. If it's split during cleanup, the split introduces import order assumptions that HMR masks.

**How to avoid:**
- Run `npm run build` in CI (it already does this — good). Do not merge any frontend cleanup PR without a passing build step.
- If `Api.ts` is split: run `npm run build && npm run preview` and verify the app loads correctly in the production bundle before merging.
- Check for circular imports with `madge --circular src/` before and after any service-layer restructure.

**Warning signs:**
- `npm run dev` works but `npm run build` throws a type error or bundler error
- The production deploy shows a blank page or module not found error
- `madge` finds new circular dependencies after a refactor

**Phase to address:**
Area 6 (frontend structure cleanup)

---

### Pitfall 16: Archive-Replay Drift — Stale HTML Causing False "Fixed" Status

**Severity:** MEDIUM

**What goes wrong:**
The self-archive bucket lets the crawler re-run against stored HTML. During crawler hardening (Area 2), a developer "fixes" a parse failure by tuning the adapter against archived HTML, runs it against the archive, sees green results, and marks the adapter as fixed. But the archived HTML is weeks old. The live retailer page has since changed its DOM again. The fix looks complete but breaks on the next real crawl run.

**Why it happens:**
Archive-replay is fast and offline — it's a natural shortcut. But the archive timestamp is invisible unless you explicitly check it.

**How to avoid:**
- When using archive-replay to fix an adapter, always also run against one live URL from that retailer as a sanity check before closing the fix.
- Add a `--max-archive-age-days` flag to the crawler CLI that rejects archive entries older than N days when used for validation.
- Log the archive entry's crawl date alongside the parse result: "Parsed successfully from archive (crawled: 2026-03-01)."

**Warning signs:**
- An adapter is marked "fixed" but the next real crawl shows the same parse failures
- Archive entries being used for testing are more than 30 days old

**Phase to address:**
Area 2 (crawler hardening)

---

### Pitfall 17: Migration Runs Without Downgrade Test — Unrecoverable Schema State

**Severity:** MEDIUM

**What goes wrong:**
A migration runs `alembic upgrade head` on prod. Something in application code is wrong, and the team needs to roll back. `alembic downgrade -1` runs and fails because the `downgrade()` function wasn't tested, uses `op.drop_constraint(None, ...)` (already present in 3 migrations), or drops a column that application code still references. The database is now in an inconsistent state. Recovery requires manual SQL surgery.

**How to avoid:**
- Every migration must have a tested `downgrade()` function. Test it locally: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`. If downgrade fails, fix it before merging.
- For `op.drop_constraint(None, ...)` — this is a known issue in the codebase. Fix all three instances during Area 4 before adding any new migrations.
- Add `naming_convention` to SQLAlchemy `MetaData` so autogenerate always produces named constraints.

**Warning signs:**
- A migration's `downgrade()` function is a pass or a TODO comment
- `op.drop_constraint(None, ...)` appears in any new migration
- No test of `downgrade` exists in any migration in the history

**Phase to address:**
Area 4 (DB / migrations / perf pass)

---

## Minor Pitfalls

### Pitfall 18: Error Boundary Gaps After Component Split

**Severity:** LOW

**What goes wrong:**
The frontend cleanup splits large page components into smaller sub-components. The original page had no error boundary (there are no error boundaries currently — E2E tests don't exist per TESTING.md). A sub-component that previously was part of a large render tree now throws an unhandled error that bubbles up to the root, showing a blank page instead of a degraded-but-functional UI.

**How to avoid:**
- Any new sub-component that makes an API call should be wrapped in a local error boundary.
- Add a top-level `ErrorBoundary` around each route's lazy-loaded page component in `App.tsx` if one doesn't already exist.
- When in doubt: if a component can throw (async data, missing data, etc.), wrap it.

**Phase to address:**
Area 6 (frontend structure cleanup)

---

### Pitfall 19: `__tablename__` Conflicts After Model File Split

**Severity:** LOW

**What goes wrong:**
If `admin.py`'s embedded logic causes someone to accidentally define a new model class with a duplicate `__tablename__`, SQLAlchemy will raise a mapper conflict at import time. This is loud (import error), not silent, but can block the entire app from starting.

Currently all 26 `__tablename__` values appear unique (verified in this analysis). The risk is low but increases if model files are restructured.

**How to avoid:**
- Add a CI test that imports all models and asserts no duplicate `__tablename__` values exist.
- This is a 5-line test and a permanent guard.

**Phase to address:**
Area 8 (code quality sweep)

---

### Pitfall 20: Build Log Auto-Creation Failure on First Access

**Severity:** LOW

**What goes wrong:**
`build_logs.py:87–98` auto-creates a `DBBuildLog` if missing when a build list is first accessed. This mid-request creation is not wrapped in error handling (per CONCERNS.md). A DB error during auto-creation returns an inconsistent state to the caller. During any refactor of the build-logs endpoint, this fragile path can become worse — especially if the refactor changes session scope or transaction boundaries.

**How to avoid:**
- Fix the root cause during Area 8: create the `DBBuildLog` eagerly when the `BuildList` is created, not lazily on first access.
- If the lazy approach stays, wrap the auto-creation in a proper try/except with a 500 response.
- Add a test for the auto-create failure path before any refactor touches this file.

**Phase to address:**
Area 8 (code quality sweep), also relevant to Area 4 if transaction refactoring touches build logs

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep old code alongside new "just in case" | Feels safe, easy to revert | Double-maintenance, confusion about which is authoritative, never get deleted | Never — use git revert instead |
| Skip downgrade() in migration | Saves 10 minutes | Unrecoverable schema state if rollback needed | Never |
| Trust SQLite tests for Postgres-specific code | CI is fast and simple | Prod failures that passed CI | Acceptable only for code that never uses Postgres-specific SQL |
| Run adapter fixes only against archive | Offline, fast iteration | Archive drift — fix looks done but breaks on live pages | Acceptable for initial diagnosis; never for final validation |
| Not deleting dead code | "Might need it later" | Maintenance burden, confusion, prevents safe refactoring | Never — delete and use git history |
| No coverage threshold | Avoids CI friction | Coverage silently erodes across the milestone | Never for a refactor milestone |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Alembic + PostgreSQL | Using `op.drop_constraint(None, ...)` — works in SQLite, fails on Postgres | Always name constraints; use `naming_convention` in MetaData; test downgrade on real Postgres |
| SQLAlchemy relationships | Accessing `.author` inside a list loop (lazy load fires per item) | Set explicit `lazy="selectin"` or use `joinedload`/`selectinload` in query; assert query count in tests |
| FastAPI `Depends()` during router split | Assuming router-level `dependencies=` propagates; it does, but only if include is correct | Declare auth dependency on each route explicitly; test 401/403 for every admin route |
| Chrome extension + backend schema change | Renaming a response field breaks extension silently | Maintain API_CONTRACT.md; check extension imports when backend schemas change |
| Crawler adapter + auto-discovery | Import errors silently drop adapters from registry | Catch ImportError per adapter, emit ERROR log, assert adapter count in CI |
| AWS RDS + Alembic | Migration that worked locally fails on RDS due to constraint naming or permission differences | Test migrations against a Postgres Docker instance, not just SQLite |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 in list endpoints | Response time grows linearly with list size | `selectinload`/`joinedload` + query count assertion in tests | At ~20+ items in list |
| Sequential crawler adapter execution | Total crawl time grows with each new adapter added | Parallelize with `ThreadPoolExecutor` bounded by connection pool math | At 50+ adapters (currently 114 — already hitting this) |
| `car_generations_data.py` eager import | Startup latency, slow `uvicorn --reload` | Lazy-load singleton with module-level cache | Every restart |
| No cache on reference data endpoints | DB hit on every `/categories/`, `/car-generations/`, `/part-manufacturers/` request | In-memory or Redis cache with TTL invalidation on write | At ~500 concurrent users |
| S3 HTML archive unbounded growth | `ListObjects` pagination slow; S3 costs grow | Lifecycle policy to expire/archive old crawl HTML | At ~100k stored pages |
| Connection pool exhaustion during parallel crawl | API requests return 503 during crawl runs | Cap crawler workers at `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE` | When parallelizing beyond 80 workers |

---

## "Looks Done But Isn't" Checklist

- [ ] **Auth refactor:** Old `auth.py` endpoints still registered? Verify no duplicate routes — FastAPI silently uses first-match routing.
- [ ] **Admin.py split:** Old `admin` router still imported in `main.py`? Verify the old import is deleted and all admin routes return 401 for unauthenticated requests.
- [ ] **N+1 fix:** Is there a query-count assertion in the test? If not, the fix will regress silently.
- [ ] **Crawler adapter auto-discovery:** Does CI assert adapter count matches expected? If not, a silent dropout won't be caught.
- [ ] **Migration safety:** Does every new migration have a tested `downgrade()`? Is `op.drop_constraint(None, ...)` absent from all new migrations?
- [ ] **Coverage threshold:** Is `--cov-fail-under` set in `pytest.ini`? Is `npm test` in `frontend-ci.yml`?
- [ ] **Chrome extension contract:** After any parts schema change — was the extension tested? Does `API_CONTRACT.md` exist and was it updated?
- [ ] **Lazy-load fix for `car_generations_data.py`:** Does the data still load correctly after switching to lazy? Test with a real `infer_car_generations()` call.
- [ ] **Parts dedup transactional fix:** Are concurrent link/unlink operations now safe? Is there a concurrency test?
- [ ] **Build log auto-creation:** Is the fragile mid-request creation replaced or wrapped in proper error handling?

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Refactor death spiral | HIGH | Stop all work. Identify the last working commit. Revert incomplete refactors to that state. Restart with smaller, phase-gated scope. |
| Double-maintenance trap | MEDIUM | Pick one as authoritative. Delete the other. Fix any divergent bug fixes. Document which was chosen and why. |
| Prod migration failure (constraint error) | HIGH | Do NOT run `alembic downgrade` without testing it first (downgrade may also fail). Fix the constraint name manually in SQL, then update the migration file to match. |
| N+1 reintroduced | LOW | Add `selectinload` to the query. Add query-count assertion. Deploy. |
| Adapter dropout | LOW | Add the dropped adapter back to the registry or fix its import. Trigger a manual crawl run to backfill missed pages. |
| Chrome extension API drift | MEDIUM | Identify the schema change that broke compatibility. Update the extension to match the new schema. Test the full scrape-to-submit flow. Publish a new extension version. |
| Coverage regression | LOW | Find which modules lost coverage. Add targeted tests. Do not lower the threshold — fix the coverage. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Refactor death spiral | All phases — enforce done-state definition | Each phase closes with old code deleted and CI green |
| Double-maintenance trap | Area 8 (admin split), Area 2 (crawler discovery) | `grep` for old router imports; verify adapter count |
| Alembic unnamed constraints | Area 4 (DB / migrations) | `grep -r "drop_constraint(None"` returns empty |
| SQLite / Postgres divergence | Area 4, Area 5 | Migrations tested against Postgres Docker; pg-specific tests separated |
| Broken `Depends()` after router split | Area 1 (auth), Area 8 (admin split) | Every admin route has 401/403 test |
| N+1 reintroduction | Area 4 (DB / perf) + Area 7 (tests) | Query-count assertion exists in CI |
| Adapter discovery breakage | Area 2 (crawler hardening) | CI asserts adapter count |
| Auth refactor regression | Area 1 (auth refactor) | Characterization tests written before split begins |
| Chrome extension drift | Area 1, Area 5, Area 6 | `API_CONTRACT.md` exists; extension tests in CI |
| Coverage regression | Area 7 (test coverage) | `--cov-fail-under` set; `npm test` in frontend CI |
| car_generations_data.py latency | Area 8 (code quality) | Startup time measured before/after |
| Circuit breaker signal confusion | Area 2 (crawler) + Area 3 (observability) | Log includes HTTP status breakdown, not just "tripped" |
| ThreadPoolExecutor sizing | Area 2 (crawler) | Worker count = pool math formula; pool exhaustion tested |
| Context re-render cascade | Area 6 (frontend) | React DevTools profiler checked after restructure |
| Vite HMR divergence | Area 6 (frontend) | `npm run build` passes in CI (already does) |
| Archive-replay drift | Area 2 (crawler) | Fixed adapters validated against one live URL |
| Migration without downgrade test | Area 4 (DB / migrations) | downgrade tested in local Postgres Docker |
| Error boundary gaps | Area 6 (frontend) | Error boundaries on all async data-fetching components |
| `__tablename__` conflict | Area 8 (code quality) | CI test imports all models and asserts unique tablenames |
| Build log auto-create | Area 8 (code quality) | Lazy creation replaced with eager; failure path tested |

---

## Sources

- Codebase analysis: `.planning/codebase/CONCERNS.md` (2026-04-22) — primary source for fragile areas and known bugs
- Codebase analysis: `.planning/codebase/TESTING.md` (2026-04-22) — test posture, CI configuration
- Direct code inspection: `backend/alembic/versions/` — unnamed constraint instances found in 3 migrations
- Direct code inspection: `backend/app/crawlers/adapters/__init__.py` — 114 manually-registered adapters
- Direct code inspection: `backend/app/api/endpoints/auth.py` (1,195 lines), `admin.py` (2,055 lines)
- Direct code inspection: `backend/app/db/session.py` — connection pool constants
- Direct code inspection: `.github/workflows/frontend-ci.yml` — frontend tests absent from CI (confirmed)
- Direct code inspection: `backend/app/api/models/*.py` — lazy loading strategy (selectin used in only 1 of 26+ relationships)
- Project context: `.planning/PROJECT.md` — milestone scope and constraints

---

*Pitfalls research for: CarModPicker tech-debt audit + refactor milestone*
*Researched: 2026-04-21*