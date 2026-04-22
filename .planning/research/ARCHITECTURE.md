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
