# Phase 3: Non-Breaking Internal Improvements - Research

**Researched:** 2026-04-22
**Domain:** Crawler subsystem hardening (auto-discovery, circuit breaker, parallelization, health check, reporting) + Pydantic v2 regression guards + logger migration + JSON data lazy-load
**Confidence:** HIGH (all claims tool-verified against the live codebase and pybreaker source; three CONTEXT inaccuracies surfaced for the planner)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All D-01 through D-38 are locked. Research may not re-open any of them; research only addresses HOW to execute them. Summary of the binding constraints:

**Adapter auto-discovery (CRAWL-01/02/03):**
- D-01: Replace hand-maintained `ADAPTER_REGISTRY` with `importlib` + `pkgutil.iter_modules` scan of `tier0_http/`, `tier1_tls/`, `tier2_browser/`; keys are each subclass's `ADAPTER_NAME`.
- D-02: Every `RetailerCrawlerAdapter` subclass MUST declare `ADAPTER_NAME: ClassVar[str]`. Base class enforces via `__init_subclass__` raising `TypeError` on missing/empty value. Derivation from class name/module path is forbidden.
- D-03: Introduce `IS_FALLBACK: ClassVar[bool] = False` on the base class. `GenericHtmlParser` sets it to `True`. Discovery scan skips `IS_FALLBACK=True` adapters; baseline count covers crawlable adapters only. `GenericHtmlParser` stays importable directly for URL-host fallback mapping.
- D-04: Expected baseline is a hard-coded integer in `backend/tests/crawlers/test_adapter_discovery.py`. Bumping the number is the PR that adds/removes an adapter. **See ⚠️ below — the CONTEXT number (111) does not match the current tree.**
- D-05: Import failures caught per-module, logged at ERROR with traceback, collected in `_IMPORT_ERRORS: list[tuple[str, BaseException]]`, loader raises `RuntimeError` if list is non-empty OR count < expected. Single enforcement point for pytest and CI.
- D-06: Test asserts: (a) count == baseline, (b) `_IMPORT_ERRORS == []`, (c) every adapter has non-empty `ADAPTER_NAME`, (d) no two adapters share an `ADAPTER_NAME`.

**Circuit breaker (CRAWL-04):**
- D-07: Add `pybreaker` to `requirements.txt`. Delete `RATE_LIMIT_CIRCUIT_BREAKER_*` block in `runner.py` (counter + constants + `consecutive_rate_limited`, `rate_limit_bailout`, `rate_limit_bailout_after`) in the same PR.
- D-08: Per-adapter-name, process-global `_BREAKERS: dict[str, pybreaker.CircuitBreaker]` initialized via `get_breaker(adapter_name)` helper. All worker threads for the same adapter share the same breaker instance.
- D-09: `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)`. REQ literal.
- D-10: Runner wraps per-URL `parse+fetch` call in `breaker.call(...)`. Existing `fetch_with_retries` loop in `backend/app/crawlers/base.py` is unchanged. Fetcher-layer retries absorb transient 429/502/503/504; only an exhausted fetch surface counts as one failure toward `fail_max=3`.
- D-11: On final 429 or 503 surfaced by the fetcher (retry budget spent), runner calls `breaker.open()` directly to pre-trip. One terminal 429/503 opens the breaker for 120s; ordinary errors need 3 consecutive to trip.
- D-12: When breaker is open, `breaker.call(...)` raises `pybreaker.CircuitBreakerError`. Runner catches, terminates per-adapter URL loop, records `{rate_limit_bailout: true, rate_limit_bailout_after: i}` in the result dict (preserves existing schema), continues to next adapter.

**Parallelization (CRAWL-05):**
- D-13: Bounded `concurrent.futures.ThreadPoolExecutor`; each future is `run_crawler(adapter_name)`; results collected via `as_completed`. **See ⚠️ below — parallelization already exists in current tree.**
- D-14: `max_workers = min(DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE, len(ADAPTER_REGISTRY))` = `min(80, N)`; env override `CRAWLER_MAX_WORKERS` takes precedence. **See ⚠️ below — existing env var is `CRAWLER_MAX_ADAPTER_WORKERS`.**
- D-15: Each worker creates its own `SessionLocal()` at start of `run_crawler`, closes in `finally`. No session leakage.
- D-16: Per-URL `time.sleep(actual_delay)` preserved inside each worker. Inter-adapter parallel, intra-adapter serial throttling.
- D-17: Plan-level `depends_on` enforces CRAWL-01/02/03 land (count-assert green) before CRAWL-04/05.

**Pre-crawl health check (CRAWL-06):**
- D-18: Default probe: `{base_url}/robots.txt` with 5s timeout. Adapters override via `HEALTH_PROBE_URL: ClassVar[str | None]`. `None` = skip probe (anti-bot tier2). Base default is empty string = "derive from `BASE_URL` class attribute". **See ⚠️ below — no adapter has `BASE_URL` today.**
- D-19: `check_health(self) -> HealthResult` method on base class. `HealthResult` is `@dataclass(frozen=True)` with `healthy: bool`, `reason: str`, `status_code: int | None`. Uses adapter's own fetcher.
- D-20: Unhealthy = any 4xx, 5xx, timeout, or connection error. Runner logs WARNING, records `{skipped: true, skip_reason: "health_<reason>"}`. 3xx followed; 2xx passes.
- D-21: Breaker-bail and health-skip are distinct `skip_reason` values; report surfaces each as its own section.

**Parse-failure reporting (CRAWL-07):**
- D-22: Extend SES job-report email with per-adapter block showing Ingested / ParseFailures fraction / Elapsed / first-5 sample URLs.
- D-23: First 5 failures (not evenly sampled). Per-worker accumulator merged into final payload.
- D-24: No Phase 2 dependency. `parse_failures` / `sample_failure_urls` keys are schema-compatible with OBS-02 CloudWatch emission.

**car_generations (QUAL-01):**
- D-25: Extract 8,412-line Python literal to `backend/app/core/car_generations_data.json` (package-adjacent). Load via `importlib.resources.files("app.core").joinpath("car_generations_data.json")`.
- D-26: New `backend/app/core/car_generations.py` module with `@functools.lru_cache(maxsize=1)` on `load_car_generations() -> dict`. Lazy: first request pays cost (~hundreds ms), everything after is memoized. `uvicorn --reload` startup does NOT trigger the load.
- D-27: One-shot conversion script `backend/scripts/export_car_generations.py` that imports old `car_generations_data.py`, `json.dump(sort_keys=True, indent=2)`, writes target. Commits JSON; replaces `car_generations_data.py` with stub raising `ImportError` pointing to new module. **See ⚠️ below — stub approach will break 4+ call sites in migrations/models/tests.**
- D-28: Before/after `time uvicorn app.main:app --reload` measurement, 3 runs each, median in PR description. No CI gate.
- D-29: Public API shape matches existing dict structure. No schema redesign.

**Pydantic v1 / on_event guards (QUAL-02, QUAL-03):**
- D-30: Current codebase has zero hits for `@validator`, `@root_validator`, `class Config:`, `.dict()`, `.parse_obj(`, `@app.on_event`. **Verified empirically — see Runtime State Inventory.**
- D-31: Add regression tests:
  - `backend/tests/test_pydantic_v1_regression.py`: uses `warnings.filterwarnings("error", category=pydantic.PydanticDeprecatedSince20)` in a sample schema roundtrip + grep-based scan of `backend/app/**/*.py` for forbidden patterns.
  - `backend/tests/test_on_event_regression.py` (or merged): grep scan for `@app\.on_event\(`, asserts zero matches.
- D-32: If the warnings-as-error probe surfaces hits the grep missed, fix in-phase before marking QUAL-02 complete.

**Logger migration (QUAL-07):**
- D-33: Sweep all files containing `Depends(get_logger)`. File list fixed at 10 files, 65 total sites per CONTEXT. **See ⚠️ below — actual total is 68 sites (not 65); auth.py has 21 sites (not 19).**
- D-34: Mechanical pattern: add module-level `logger = logging.getLogger(__name__)` after imports; delete `from app.core.logging import get_logger`; delete `logger: logging.Logger = Depends(get_logger),` from every signature.
- D-35: Phase 5 auth.py split inherits pattern (each new auth/ module gets own module-level logger). No Phase 3 / Phase 5 ordering coupling.
- D-36: Keep `backend/app/core/logging.py::get_logger` exported through Phase 3; remove in late Phase 5 / early Phase 6 if nothing else imports it.
- D-37: Acceptance: `grep -rn "Depends(get_logger)" backend/app/` returns zero; CI coverage ≥ baseline.

**Phase 2 decoupling:**
- D-38: Every deliverable lands without Phase 2 artifacts (Sentry init, CloudWatch namespace, alarms). CRAWL-07 uses existing SES infrastructure; OBS-02 reads the same result dict later.

### Claude's Discretion

- Exact variable/function names inside `adapters/__init__.py` discovery helpers (`_IMPORT_ERRORS`, `_discover_adapters`, etc.)
- Whether discovery error path uses `RuntimeError` specifically or a more specific custom exception
- JSON indentation / key-ordering for committed `car_generations_data.json` (sort_keys preferred)
- Sample-URL truncation rule when URL is >100 chars in job-report email
- Whether QUAL-02/03 grep test uses Python `re` inside pytest or shell `grep | test $?` CI step
- Whether to bundle grep test into existing `test_openapi_snapshot.py`-style guard tests or create new dedicated test modules

### Deferred Ideas (OUT OF SCOPE)

- Remove `get_logger` export entirely (late Phase 5 / early Phase 6)
- Retroactive rename of all 108 adapter tests to use `ADAPTER_NAME`
- `discover_product_urls()` characterization (deferred from Phase 1, still not in Phase 3)
- Async rewrite of crawler runner
- Observability instrumentation of the breaker itself (listeners → Sentry/CloudWatch = Phase 2)
- S3 lifecycle policy QUAL-08 (Phase 6)
- Pydantic v2 feature-adoption audit (beyond regression-guard scope)
- Rollback plan for pybreaker flakiness (revert = delete wrapper, restore counter)

---

### ⚠️ CONTEXT Discrepancies Requiring Plan-Time Reconciliation

**The planner MUST flag these in the plan, either by adjusting numbers/approach inside D-ranges Claude's-discretion, or by flagging them for a short discuss-phase update before planning commits. Research does not relitigate locked decisions; it surfaces factual drift from the CONTEXT that will cause the plan to fail verification if unaddressed.**

| # | CONTEXT claim | Actual codebase state | Impact |
|---|---------------|----------------------|--------|
| DISC-01 | D-04: "Current count = 111 (84 tier0 + 16 tier1 + 11 tier2)" | 108 adapter subclasses: 83 tier0 + 15 tier1 + 10 tier2, plus 1 fallback (`GenericHtmlParser`). `ADAPTER_REGISTRY` today has 109 keys (108 + `"generic"`). After filtering `IS_FALLBACK=True`, the D-06 baseline is **108**, not 111. | Planner must use 108 as the hard-coded count. Miscount in test = CI red on first run. |
| DISC-02 | D-13: "Replace the currently-serial per-adapter loop" | `runner.py:767-784` already wraps `run_crawler` in `ThreadPoolExecutor(max_workers=_compute_adapter_workers(...))` with `as_completed`. Parallelization is live. `_compute_adapter_workers` at line 657 already implements the D-14 formula. | CRAWL-05 is partially done. The plan scope narrows to: (a) ensure the **breaker** is wired INTO the existing executor correctly, (b) rename env var (see DISC-03), (c) verify per-worker `SessionLocal()` lifecycle (already correct at runner.py:748-ff). |
| DISC-03 | D-14: env var `CRAWLER_MAX_WORKERS` | Existing env var is `CRAWLER_MAX_ADAPTER_WORKERS` (runner.py:675). | Either rename to match D-14, or update D-14 to existing name. The existing name is more descriptive; recommend keeping `CRAWLER_MAX_ADAPTER_WORKERS` (Claude's discretion under D-14 naming). |
| DISC-04 | D-18: "default probe derived from `BASE_URL` class attribute" | **Zero adapters** declare a `BASE_URL` class attribute. Each adapter embeds its host in module-level constants (e.g., `BTR_BASE = "https://briantooleyracing.com"` in briantooleyracing.py). | The planner must pick one of: (a) add `BASE_URL: ClassVar[str]` to every adapter (108-file sweep on top of `ADAPTER_NAME` sweep — doubles D-02's scope), (b) default `HEALTH_PROBE_URL = None` so health check is opt-in per adapter, (c) derive from `adapter_name_for_product_url()` reverse-mapping (fragile). **Recommendation: (b) — opt-in, with explicit per-adapter override wave.** See "Pitfall HC-01" below. |
| DISC-05 | D-27: "Replace `car_generations_data.py` with stub raising `ImportError`" | The file exports 4 public symbols used beyond the dict-literal: `slugify()` (used in `alembic/versions/30e2e2139a2e_*.py`, `models/car_generation.py`, `models/car_model.py`, `tests/test_init_cars_display_name.py`), `CAR_GENERATIONS` dict, `CarGenerationData` TypedDict, `get_all_car_generations()`. Stubbing the module would break Alembic migrations and model imports. | The plan must preserve `slugify()` (move to a dedicated `car_utils.py` or leave in place) and either: keep `car_generations_data.py` as a thin shim that proxies to the new JSON-backed loader, OR split helpers into `car_generations_helpers.py` while the JSON replaces `CAR_GENERATIONS`. **Recommendation: thin-shim approach** — `car_generations_data.py` becomes 20 lines: `slugify`, `CarGenerationData`, and `CAR_GENERATIONS = load_car_generations()` + `get_all_car_generations = ...` delegating to new module. Preserves all call sites. |
| DISC-06 | D-33: "65 total sites, auth.py 19 sites" | Actual: **68 total sites**, **auth.py has 21 sites**. Full per-file count below in Runtime State Inventory. | Cosmetic — update D-33 numbers in the plan and verification. Doesn't change the approach. |
| DISC-07 | CONTEXT §code_context: custom breaker at "`runner.py:64-71, 444-596`" | Actual: constants at lines **64-71**, breaker-state block at **444-582** (reset counter on successful fetch at line 477, accumulator at 569-582). No material code between 583-596 — that's the summary-level-selection logic, which stays. | Minor — just use the actual lines (64-71 for constants, 444-452 for state init, 542-545 for reset, 569-582 for trip). |
| DISC-08 | CONTEXT: `HttpFetcher.fetch()` retry loop at `base.py:548-601` | Actual: the shared retry loop is `fetch_with_retries()` at **base.py:532-603**. The rate-limit branch is 567-585; the timeout branch is 588-601. Per-transport `HttpFetcher.fetch()` at line 118, `TlsFetcher.fetch()` at line 216, `FlareSolverrFetcher.fetch()` at line 365 — they all delegate to `fetch_with_retries()`. | Minor — D-10 says "fetcher-layer retries" and the shared function IS the retry layer. Preserved as D-10 mandates. |
| DISC-09 | CONTEXT lists `test_characterization_texasspeed.py` + 4 siblings as needing `ADAPTER_NAME` switch (per Phase 1 D-23) | Verified: files exist at `backend/tests/crawlers/test_characterization_{briantooleyracing,amsperformance,texasspeed,cobbtuning,subispeed}.py`. All 5 key adapters by class name today, with a docstring noting the switch lands in Phase 3. | Correct — plan must update these 5 in the same PR as D-02 introduction. |

None of these discrepancies require relitigation of decisions; they require accurate numbers and approach adjustments within the Claude's-discretion areas of the locked decisions.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|-------------------------------------|------------------|
| CRAWL-01 | Adapter auto-discovery via `importlib` + `pkgutil.iter_modules` replaces hand-maintained `adapters/__init__.py` registry | `pkgutil.iter_modules` + `importlib.import_module` pattern; per-module try/except; retain `adapter_name_for_product_url` URL-host mapping and `get_adapter()` helpers from current `__init__.py` untouched |
| CRAWL-02 | `ADAPTER_NAME: ClassVar[str]` enforced on every subclass; CI asserts discovered count equals expected | `__init_subclass__` hook on `RetailerCrawlerAdapter` base raises `TypeError` if attribute missing/empty. 108-file sweep to add `ADAPTER_NAME = "<slug>"` matching current registry keys. |
| CRAWL-03 | Adapter import errors caught, logged at ERROR, fail CI (not silently drop) | Per-module try/except around `importlib.import_module`; accumulate in `_IMPORT_ERRORS`; single test fails CI when non-empty. |
| CRAWL-04 | Rate-limit circuit breaker replaced with `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)`; 429/503 triggers immediate bail | `pybreaker 1.4.1` — thread-safe via `threading.RLock()`; `breaker.open()` programmatically trips and DOES fire `state_change` listeners (verified in source). See "Library specifics" below. |
| CRAWL-05 | Per-adapter `run_crawler` runs in bounded `ThreadPoolExecutor` sized to `DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE`, each worker its own `SessionLocal()` | **Already implemented** at `runner.py:767-784` + `_compute_adapter_workers` at line 657. Phase 3 scope: ensure the pybreaker registry (D-08) is thread-safe when read by these workers + align env var naming (DISC-03). |
| CRAWL-06 | Per-adapter pre-crawl health check (fetch `robots.txt` with 5s timeout), skip on 4xx/5xx/timeout | Adapter-level method using the adapter's own fetcher with `timeout=5`. See DISC-04 — default-probe-URL derivation needs alignment. |
| CRAWL-07 | Parse-failure reporting bubbles into job report email with per-adapter counts + retailer URL samples | Existing `_render_crawler_result_html` in `backend/app/core/email.py:221` already renders `error_urls` / `parse_miss_urls` / `rate_limit_bailout`. New work: add `parse_failures` integer + `sample_failure_urls: list[str]` (first 5 URL-only) to result dict; extend email renderer. |
| QUAL-01 | `car_generations_data.py` → JSON + `@lru_cache` loader; `uvicorn --reload` startup latency measurably improves | `importlib.resources.files()` stable API in Py 3.12+ (project on 3.13). Thin-shim approach (DISC-05) preserves `slugify`, `CAR_GENERATIONS`, `get_all_car_generations`, `CarGenerationData`. |
| QUAL-02 | Pydantic v1 pattern sweep: zero v1 deprecation warnings in test run | Current state: zero hits. Regression guard: grep scan + explicit `warnings.catch_warnings()` roundtrip. **Critical:** `pytest.ini` has `--disable-warnings` → must use `warnings.catch_warnings() + simplefilter("error", ...)` context manager, not CLI `-W error`. |
| QUAL-03 | `@app.on_event()` audit; any residual removed in favor of `lifespan` | Current state: zero hits; `main.py:70` uses `async def lifespan(app)`. Regression guard only. |
| QUAL-07 | `logger` migrated from `Depends()` to module-level `logging.getLogger(__name__)` where found | 68 sites across 10 files (DISC-06). Mechanical transformation in D-34. |
</phase_requirements>

---

## Summary

Phase 3 hardens the crawler end-to-end and eliminates residual Pydantic v1 / `Depends(get_logger)` anti-patterns, without touching any external API contract. Five distinct workstreams map to the 11 requirements:

1. **Auto-discovery sweep (CRAWL-01/02/03):** 108-file mechanical sweep adding `ADAPTER_NAME: ClassVar[str]` (and optionally `BASE_URL` if DISC-04 goes path-a); replace hand-maintained `ADAPTER_REGISTRY` with `pkgutil.iter_modules` scan that populates the dict at module-import time; add hard-coded count assertion + `_IMPORT_ERRORS` guard test.
2. **Breaker + health-check integration (CRAWL-04/06):** Replace custom rate-limit counter block with a per-adapter `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)` registry; call `breaker.open()` on terminal 429/503; add `check_health()` method that probes `robots.txt` before crawling. These two land in the same PR (shared per-adapter-name keyed registry).
3. **Parallelization alignment (CRAWL-05):** Codebase already has `ThreadPoolExecutor`-based parallelism. Plan only needs to (a) confirm per-worker `SessionLocal()` is correct (it is), (b) align env var name `CRAWLER_MAX_ADAPTER_WORKERS` vs `CRAWLER_MAX_WORKERS`, (c) ensure the breaker registry is thread-safe when accessed by workers (it is, since `dict` assignment + `pybreaker` internal `RLock` are both safe).
4. **Job-report extension (CRAWL-07):** Extend existing `_render_crawler_result_html` in `email.py` with a `parse_failures: int` + `sample_failure_urls: list[str]` (first-5) block per adapter.
5. **Regression-guard sweep (QUAL-01/02/03/07):** Lazy-load `car_generations_data` via JSON + `@lru_cache` (with thin-shim to preserve `slugify` / `CAR_GENERATIONS` callers); add Pydantic v1 / `on_event` grep-and-roundtrip regression tests; migrate 68 `Depends(get_logger)` sites to module-level loggers.

**Primary recommendation:** Execute in 5 plans ordered by the CONTEXT's dependency constraint (CRAWL-01/02/03 before CRAWL-05; CRAWL-04 + CRAWL-05 same PR). QUAL-01/02/03/07 can parallelize fully.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Adapter discovery & registry | Background worker (crawler subsystem) | — | Pure import-time Python; no request path touched |
| Circuit breaker state | Background worker (in-process registry) | — | Process-global dict keyed by adapter name; shared across ThreadPoolExecutor workers |
| Health-check probe | Background worker (adapter method) | — | Uses adapter's own fetcher; fires on crawl-start, not on API requests |
| Parallel adapter execution | Background worker (ThreadPoolExecutor) | DB connection pool | Scales up to `pool - reserve`; `SessionLocal()` per worker thread |
| Parse-failure reporting | Background worker → SES email | — | End-of-run side effect; existing SES path |
| `car_generations` loading | API / backend (lazy, request-triggered) | — | `@lru_cache` ensures first-call cost, zero startup latency |
| Pydantic v1 regression | CI test runner | — | Pure guard; no runtime impact |
| `on_event` regression | CI test runner | — | Pure guard; no runtime impact |
| Logger migration | API / backend (endpoint functions) | — | Module-level initialization; no request-time cost |

Note: None of these capabilities touch the Browser / Frontend Server / CDN tiers. This is a pure backend-internal phase.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pybreaker` | **1.4.1** | Thread-safe circuit breaker for the crawler's per-adapter rate-limit protection | The canonical Python implementation; ~13 years maintained; thread-safe via internal `threading.RLock()`; supports programmatic `open()` / listeners / exclude callable [VERIFIED: PyPI `pybreaker 1.4.1` released 2025-09-21; source code inspected at `/tmp/pb_pkg/pb_src/pybreaker/__init__.py`] |
| `importlib.resources` | stdlib (Python 3.13) | Package-adjacent JSON loading for `car_generations_data.json` | Stable API since Python 3.12; works in dev, pytest, and App Runner Docker image; replaces fragile `os.path.join(__file__, ...)` pattern [CITED: https://docs.python.org/3.13/library/importlib.resources.html] |
| `functools.lru_cache` | stdlib | Memoize the JSON parse of `car_generations_data.json` | Zero-dep; thread-safe; `maxsize=1` perfectly matches the "load once, reuse" pattern [CITED: Python stdlib] |
| `pkgutil.iter_modules` | stdlib | Walk the three adapter-tier directories at module-import time | `pkgutil` is the standard approach for subpackage discovery in Python; paired with `importlib.import_module` for per-module import with try/except [CITED: https://docs.python.org/3.13/library/pkgutil.html] |
| `concurrent.futures.ThreadPoolExecutor` | stdlib | Bounded parallel adapter execution | Already in use at `runner.py:775` — no change needed; thread-pool is correct transport for SQLAlchemy `SessionLocal()` per worker pattern [VERIFIED: codebase `backend/app/crawlers/runner.py:23,775`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | **2.11.3** (pinned) | Schema validation; regression-guard target | Already installed; QUAL-02 test imports `pydantic.PydanticDeprecatedSince20` warning class [VERIFIED: `backend/requirements.txt`] |
| `pytest` + `pytest-xdist` | existing | Test runner with `-n auto --dist=loadfile` | All new tests must be worker-safe (pure-import assertions are inherently safe) [VERIFIED: `backend/pytest.ini`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pybreaker` | `circuitbreaker` (pip) | Smaller, but less feature-complete; no `exclude_callable`; no `state_change` listener API; CONTEXT locked `pybreaker` per REQ-CRAWL-04 |
| `importlib.resources.files()` | `pathlib.Path(__file__).parent / "car_generations_data.json"` | Works in dev but breaks in zipapp / alternative layouts; CONTEXT locked `importlib.resources` per D-25 |
| `pkgutil.iter_modules` | Manual `os.listdir` | Doesn't handle subpackage `__init__.py` or pyc-only layouts; `pkgutil` handles all Python module types including namespace packages |
| Async rewrite (`asyncio`) | Would obviate thread-safety concerns | Massive refactor; pybreaker 1.4.1 is sync-only (aiobreaker is a fork); CONTEXT D-30-deferred section excludes this |

**Installation:**
```bash
cd backend
pip install 'pybreaker==1.4.1'
# Then append to requirements.txt:
# pybreaker==1.4.1
```

**Version verification (2026-04-22):**
- `pybreaker 1.4.1` — released 2025-09-21, 7 months old, stable. Supports Python ≥ 3.10. CarModPicker runs 3.13 in CI/Docker → fully compatible. [VERIFIED: PyPI release history https://github.com/danielfm/pybreaker/releases]
- Python 3.13 `importlib.resources.files()` — stable API since 3.12, no deprecations in 3.13 or 3.14. [CITED: https://docs.python.org/3.13/library/importlib.resources.html]

---

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────┐
                          │  CLI / Admin endpoint / EventBridge │
                          │  POST /admin/crawlers/run           │
                          └───────────────┬─────────────────────┘
                                          │
                                          ▼
                       ┌──────────────────────────────────┐
                       │  run_crawlers(adapter_names)     │
                       │  backend/app/crawlers/runner.py  │
                       └──────┬───────────────────────────┘
                              │
                              ▼
              ┌─────────────────────────────────────────┐
              │  ThreadPoolExecutor(max_workers=...)    │  ◄── D-14: min(80, N) + env override
              │  _compute_adapter_workers (already live)│
              └──────┬──────────────────────────────────┘
                     │  submit(run_one, adapter_name) for each
                     ▼
            ┌────────────────────────────────────────────┐
            │ Worker thread i                            │
            │                                            │
            │  db = SessionLocal()      ◄── D-15         │
            │                                            │
            │  ┌──────────────────────────┐              │
            │  │ get_breaker(adapter_name)│ ◄── D-08     │
            │  │   per-adapter-name global│              │
            │  │   pybreaker registry     │              │
            │  └──────────────────────────┘              │
            │                                            │
            │  adapter = get_adapter(adapter_name)       │
            │         ◄── D-01 auto-discovered           │
            │                                            │
            │  result = adapter.check_health()  ◄── D-19 │
            │  if not result.healthy:                    │
            │     record skip_reason="health_..."        │
            │     return                                 │
            │                                            │
            │  for url in adapter.discover_product_urls():
            │    try:                                    │
            │      html = breaker.call(                  │
            │         adapter.fetcher.fetch, url)  ◄── D-10
            │      payload = adapter.parse_product_page( │
            │         html, url)                         │
            │      if payload: ingest(db, payload)       │
            │      else: parse_failures += 1             │
            │            sample_failure_urls.append(url) │
            │    except pybreaker.CircuitBreakerError:   │
            │      rate_limit_bailout = True  ◄── D-12   │
            │      break                                 │
            │    except FetcherError as e:               │
            │      if status in (429, 503):              │
            │        breaker.open()   ◄── D-11 terminal  │
            │                                            │
            │  return {adapter: ..., ingested: ...,      │
            │    parse_failures: ..., sample_failure_urls: ...
            │    rate_limit_bailout: ..., skip_reason: ...}
            │                                            │
            │  finally: db.close(), fetcher.close()      │
            └────────────────┬───────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  as_completed(futures)       │
              │  aggregate into summary dict │
              └───────────┬──────────────────┘
                          │
                          ▼
              ┌───────────────────────────────┐
              │ BackgroundJob.result_summary  │
              └───────────┬───────────────────┘
                          │
                          ▼
              ┌────────────────────────────────────┐
              │ send_job_report_email              │
              │ backend/app/core/email.py:72       │
              │ _render_crawler_result_html ◄── D-22
              │   (adds parse_failures + samples)  │
              └────────────────────────────────────┘

SIDE QUEST (unrelated to crawler):
  GET /api/car-generations/...
        │
        ▼
  backend/app/api/endpoints/car_generations.py
        │
        ▼
  backend/app/core/car_generations.py      ◄── D-26 NEW module
        │
        ▼
  @lru_cache(maxsize=1)
  load_car_generations() → dict
        │
        ▼
  importlib.resources.files("app.core")
    .joinpath("car_generations_data.json")
    .read_text()
        │
        ▼
  json.loads(...)
```

### Pattern 1: Auto-discovery via `pkgutil.iter_modules` + per-module try/except

**What:** Walk the three adapter tier packages at import time; accumulate each subclass of `RetailerCrawlerAdapter` (excluding `IS_FALLBACK=True`) into the registry.
**When to use:** Replace the 100+ explicit `from X import Y` lines in `__init__.py` (lines 19-131 today).

```python
# Source: pattern verified against Python stdlib docs https://docs.python.org/3.13/library/pkgutil.html#pkgutil.iter_modules
# and the existing codebase layout (backend/app/crawlers/adapters/tier0_http/*.py)

import importlib
import pkgutil
import logging
from typing import Type

from app.crawlers.adapters.base import RetailerCrawlerAdapter
# generic imported directly — not via scan, not in registry
from app.crawlers.adapters.generic import GenericHtmlParser  # noqa: F401  (used by adapter_name_for_product_url)

logger = logging.getLogger(__name__)

# Module-level — populated at import time
ADAPTER_REGISTRY: dict[str, Type[RetailerCrawlerAdapter]] = {}
_IMPORT_ERRORS: list[tuple[str, BaseException]] = []


def _discover_adapters() -> None:
    """Walk the three tier subpackages, import every module, collect concrete adapters."""
    import app.crawlers.adapters.tier0_http as tier0
    import app.crawlers.adapters.tier1_tls as tier1
    import app.crawlers.adapters.tier2_browser as tier2

    for pkg in (tier0, tier1, tier2):
        for modinfo in pkgutil.iter_modules(pkg.__path__, prefix=f"{pkg.__name__}."):
            try:
                module = importlib.import_module(modinfo.name)
            except BaseException as exc:  # noqa: BLE001 — we want to catch everything, including ImportError subclasses
                logger.error("failed to import adapter %s: %s", modinfo.name, exc, exc_info=True)
                _IMPORT_ERRORS.append((modinfo.name, exc))
                continue
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, RetailerCrawlerAdapter)
                    and attr is not RetailerCrawlerAdapter
                    and not getattr(attr, "IS_FALLBACK", False)
                ):
                    name = attr.ADAPTER_NAME  # set by __init_subclass__ — guaranteed present & non-empty
                    if name in ADAPTER_REGISTRY:
                        _IMPORT_ERRORS.append((modinfo.name, ValueError(
                            f"duplicate ADAPTER_NAME {name!r}: "
                            f"{ADAPTER_REGISTRY[name].__module__} vs {attr.__module__}"
                        )))
                        continue
                    ADAPTER_REGISTRY[name] = attr


_discover_adapters()
```

```python
# backend/app/crawlers/adapters/base.py — __init_subclass__ enforcement

from abc import ABC, abstractmethod
from typing import ClassVar

class RetailerCrawlerAdapter(ABC):
    ADAPTER_NAME: ClassVar[str] = ""           # overridden by each subclass
    IS_FALLBACK: ClassVar[bool] = False        # default; GenericHtmlParser sets True
    HEALTH_PROBE_URL: ClassVar[str | None] = None  # None = skip; otherwise full URL
    FETCHER_TIER: ClassVar[Literal["http", "tls", "browser"]] = "http"  # existing

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Only enforce on concrete subclasses — the Generic fallback is exempt because
        # IS_FALLBACK=True opts it out of the registry (its own ADAPTER_NAME is unused).
        if getattr(cls, "IS_FALLBACK", False):
            return
        # ABCs (which set __abstractmethods__) are also exempt — but every current
        # concrete adapter is not an ABC, so this branch rarely fires.
        if getattr(cls, "__abstractmethods__", None):
            return
        name = getattr(cls, "ADAPTER_NAME", "")
        if not isinstance(name, str) or not name.strip():
            raise TypeError(
                f"{cls.__module__}.{cls.__qualname__} must declare "
                f"ADAPTER_NAME: ClassVar[str] = '<slug>' (non-empty)"
            )
```

### Pattern 2: Per-adapter-name pybreaker registry (D-08)

```python
# Source: pybreaker 1.4.1 usage idioms, verified against
# /tmp/pb_pkg/pb_src/pybreaker/__init__.py (CircuitBreaker class lines 88-304)

import pybreaker
import threading

_BREAKERS: dict[str, pybreaker.CircuitBreaker] = {}
_BREAKERS_LOCK = threading.Lock()  # guards the dict (pybreaker's own RLock guards the breaker)


def get_breaker(adapter_name: str) -> pybreaker.CircuitBreaker:
    """Return the process-global breaker for this adapter, creating on first access."""
    breaker = _BREAKERS.get(adapter_name)
    if breaker is not None:
        return breaker
    with _BREAKERS_LOCK:
        # Double-checked: another thread may have created it while we waited for the lock.
        breaker = _BREAKERS.get(adapter_name)
        if breaker is not None:
            return breaker
        breaker = pybreaker.CircuitBreaker(
            fail_max=3,
            reset_timeout=120,
            name=adapter_name,  # surfaces in CircuitBreakerError repr, useful for logs
        )
        _BREAKERS[adapter_name] = breaker
        return breaker
```

### Pattern 3: Wrapping the fetch call with breaker + pre-trip on 429/503

```python
# Source: pybreaker CircuitBreaker.call + CircuitBreaker.open APIs
# (pb_src/pybreaker/__init__.py lines 239-292) + existing fetch classification
# in backend/app/crawlers/runner.py:_http_status_from_exception

from pybreaker import CircuitBreakerError

breaker = get_breaker(adapter_name)

for i, url in enumerate(urls, 1):
    try:
        html = breaker.call(adapter.fetcher.fetch, url)
    except CircuitBreakerError:
        # D-12: breaker is open; bail the entire adapter URL loop
        logger.error("Adapter %s: breaker OPEN after %s URLs; bailing.", adapter_name, i)
        rate_limit_bailout = True
        rate_limit_bailout_after = i
        break
    except FetcherError as e:
        status = _http_status_from_exception(e)
        # D-11: terminal 429/503 (fetcher exhausted its retry budget) pre-trips the breaker
        if status in (429, 503):
            breaker.open()  # fires state_change listener via internal state.setter
            logger.warning(
                "Adapter %s: terminal %s on URL %s — opened breaker for %ss",
                adapter_name, status, url, 120,
            )
        # fall through to existing error-bucket classification
        ...
```

### Pattern 4: Pre-crawl health check (D-19)

```python
# Source: new code; design cross-references D-18, D-19, D-20, and existing fetcher API
# at backend/app/crawlers/fetchers.py:HttpFetcher.fetch

from dataclasses import dataclass

@dataclass(frozen=True)
class HealthResult:
    healthy: bool
    reason: str                  # "ok", "http_4xx", "http_5xx", "timeout", "connection", "skipped_by_config"
    status_code: int | None      # HTTP status if reason is http_*; else None


# on RetailerCrawlerAdapter base class:
def check_health(self) -> HealthResult:
    probe_url = type(self).HEALTH_PROBE_URL
    if probe_url is None:
        # D-18: explicit opt-out (anti-bot tier2 retailers)
        return HealthResult(healthy=True, reason="skipped_by_config", status_code=None)
    try:
        # Use adapter's own fetcher so tier-specific transport rules apply.
        # 5s timeout per D-18 is short — robots.txt should come back fast.
        html = self.fetcher.fetch(probe_url, timeout=5)
        # Fetcher raised no exception → 2xx. Redirect (3xx) is followed by fetcher transparently.
        return HealthResult(healthy=True, reason="ok", status_code=200)
    except FetcherError as e:
        status = _http_status_from_exception(e)
        if status and 400 <= status < 500:
            return HealthResult(healthy=False, reason="http_4xx", status_code=status)
        if status and 500 <= status < 600:
            return HealthResult(healthy=False, reason="http_5xx", status_code=status)
        # timeout / connection / unknown
        bucket = _classify_fetch_error(e, status)
        return HealthResult(healthy=False, reason=bucket, status_code=status)
```

### Pattern 5: `importlib.resources.files()` lazy JSON loader (D-26)

```python
# Source: https://docs.python.org/3.13/library/importlib.resources.html#importlib.resources.files
# Used by: backend/app/core/car_generations.py (NEW)

from __future__ import annotations

import functools
import json
from importlib.resources import files


@functools.lru_cache(maxsize=1)
def load_car_generations() -> dict:
    """Load and memoize the car-generations dict from JSON.

    First call reads ~8000-line JSON + parses (~100-200ms on a warm SSD).
    Subsequent calls return the cached dict reference.
    """
    resource = files("app.core").joinpath("car_generations_data.json")
    # read_text() handles encoding correctly; works for both filesystem and zipapp layouts.
    return json.loads(resource.read_text(encoding="utf-8"))
```

### Pattern 6: Pydantic v2 regression-guard roundtrip (D-31)

```python
# Source: https://docs.pydantic.dev/latest/migration/ — deprecation classes
# Verified: pydantic.PydanticDeprecatedSince20 exists in pydantic 2.11.3 (backend/requirements.txt)

import warnings
import pytest
import pydantic
from app.api.schemas.user import UserPublic  # pick a representative v2 schema


def test_no_pydantic_v1_deprecation_warnings_on_roundtrip() -> None:
    # pytest.ini has --disable-warnings; we override locally with a context manager.
    with warnings.catch_warnings():
        warnings.simplefilter("error", pydantic.PydanticDeprecatedSince20)
        user = UserPublic(id=1, username="x", email="x@x.com", email_verified=True)
        dumped = user.model_dump()
        reloaded = UserPublic.model_validate(dumped)
        assert reloaded == user
```

### Pattern 7: Forbidden-pattern grep test (D-31)

```python
# Source: new code; replicates the migration DROP-guard idiom from Phase 1 (SAFE-04)

import re
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"

FORBIDDEN_PATTERNS = [
    (re.compile(r"@validator\b"),            "Pydantic v1 @validator — use @field_validator"),
    (re.compile(r"@root_validator\b"),       "Pydantic v1 @root_validator — use @model_validator"),
    (re.compile(r"^\s*class\s+Config\s*:"),  "Pydantic v1 class Config — use model_config = ConfigDict(...)"),
    (re.compile(r"\.parse_obj\("),           "Pydantic v1 .parse_obj() — use .model_validate()"),
    (re.compile(r"@app\.on_event\("),        "Deprecated @app.on_event — use lifespan context manager"),
]

# .dict() is trickier because it hits non-Pydantic dict-like objects; use allow-list if needed
DICT_PATTERN = re.compile(r"\b\w+\.dict\(\)")
# Known-safe .dict() callers (SQLAlchemy row._asdict is a common false positive surface)
DICT_ALLOWLIST: set[str] = set()


def test_no_forbidden_patterns_in_app() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            # strip full-line comments to avoid false positives in migration notes
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pat, label in FORBIDDEN_PATTERNS:
                if pat.search(line):
                    offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno, label))
            # .dict() with allow-list
            if DICT_PATTERN.search(line):
                rel = str(pyfile.relative_to(BACKEND_APP))
                if rel not in DICT_ALLOWLIST:
                    offenders.append((rel, lineno, ".dict() — use .model_dump() (or add to DICT_ALLOWLIST with rationale)"))
    assert not offenders, "Forbidden patterns found:\n" + "\n".join(
        f"  {f}:{n}: {label}" for f, n, label in offenders
    )
```

### Pattern 8: `Depends(get_logger)` → module-level sweep (D-34)

```python
# Source: Python logging best practice + FastAPI dependency-injection docs
# https://docs.python.org/3/library/logging.html#logger-objects

# BEFORE (at top of endpoint file):
from app.core.logging import get_logger
from fastapi import Depends

@router.get("/...")
def foo(
    ...,
    logger: logging.Logger = Depends(get_logger),
):
    logger.info("...")

# AFTER:
import logging
logger = logging.getLogger(__name__)

@router.get("/...")
def foo(...):  # logger param removed; body unchanged
    logger.info("...")
```

### Anti-Patterns to Avoid

- **Don't derive `ADAPTER_NAME` from class name or module path.** D-02 forbids this. A rename must be an explicit, grep-able act. `__init_subclass__` enforces this at import time; the test enforces it at CI time.
- **Don't populate the registry with `GenericHtmlParser`.** D-03: `IS_FALLBACK=True` opts it out. `GenericHtmlParser` is imported directly by `adapter_name_for_product_url()` for URL-host fallback mapping — it never goes through `get_adapter(name)`.
- **Don't wrap `fetch_with_retries()` in the breaker.** D-10: the breaker sits ATOP the retry loop, not inside it. Fetcher-layer retries absorb transient blips; one exhausted retry surface = one breaker failure.
- **Don't swap `pybreaker.call()` for the decorator `@breaker`.** Per-adapter-name dispatch needs the function-object path (D-08 registry), not a decorator applied to a module-level function. Decorator style would bind a single breaker to the fetch function forever.
- **Don't rely on `pytest.ini -W error::PydanticDeprecatedSince20`.** `pytest.ini` has `--disable-warnings`, which suppresses ALL warnings including the filter. Use `warnings.catch_warnings() + simplefilter("error", ...)` inside each regression test instead.
- **Don't remove the entire `car_generations_data.py`.** DISC-05: `slugify()` is used by Alembic migrations, two model files, and a test. The file must remain as a thin shim.
- **Don't assume `lru_cache` on `load_car_generations()` is thread-safe against mutation.** Callers MUST NOT mutate the returned dict — `lru_cache` returns the same object reference every call. Add a module-level comment warning, or `return copy.deepcopy(...)` if mutation is a risk (slower; verify no caller mutates before choosing immutable).
- **Don't use `os.path.join(os.path.dirname(__file__), "car_generations_data.json")`.** D-25: this breaks inside zipapp / some deploy layouts. Use `importlib.resources.files()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circuit breaker state machine | Custom counter + threshold logic | `pybreaker.CircuitBreaker` | Thread-safe state transitions, half-open probing, listener hooks, 13 years of battle-testing — we're DELETING our hand-rolled version (CRAWL-04 / D-07) |
| Parallel adapter execution | Custom thread-management loop | `concurrent.futures.ThreadPoolExecutor` + `as_completed` | Already in use; error isolation per future, clean cancellation via context-manager exit |
| Package-adjacent file loading | `os.path.join(os.path.dirname(__file__), ...)` | `importlib.resources.files(...)` | Zipapp-safe, Docker-safe, pytest-safe, no layout assumptions |
| Memoized JSON parse | Module-level dict + "if not loaded" logic | `@functools.lru_cache(maxsize=1)` | Thread-safe, one line, zero drift risk |
| Adapter discovery | Hand-maintained import list of 108 lines | `pkgutil.iter_modules + importlib.import_module` | Error-isolation per module; CRAWL-01 / D-01 mandates |
| Logger dependency injection | `Depends(get_logger)` on every endpoint | Module-level `logging.getLogger(__name__)` | Python logging is already process-global and request-context-aware via the existing `RequestContextFilter` handler; DI adds zero value |

**Key insight:** Three of the 11 requirements are EXPLICITLY about deleting hand-rolled custom infrastructure in favor of stdlib / widely-adopted library patterns. The phase is a net subtraction of code.

---

## Runtime State Inventory

Phase 3 is mostly non-rename (QUAL-07 is the exception — it renames the `logger` identifier's binding from a parameter to a module global), but three areas touch runtime state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | `car_generations` DB table — seeded from `CAR_GENERATIONS` + `get_all_car_generations()` at app startup (via `init_cars.py`). After QUAL-01 lands, the seeded DB state MUST be bit-identical to pre-change, or the "no external API contract change" invariant breaks. | Plan-level verification: run `init_cars.py` against a fresh SQLite DB before and after QUAL-01; diff the `car_generation` + `car_model` + `car_make` table rows. Must be zero-diff. |
| **Live service config** | None. Crawler runs are triggered by EventBridge → `/api/cron/run-crawler-schedule`; no external registration state keyed on adapter names that changes when the registry goes auto-discovered. | None — the `ADAPTER_NAME` values are preserved exactly as the 108 current registry keys, so EventBridge / admin UI / crawler-run history rows are unchanged. |
| **OS-registered state** | None. No OS-level service names or task-scheduler entries reference `get_logger`, breaker state, or adapter registry. | None. |
| **Secrets / env vars** | `CRAWLER_MAX_ADAPTER_WORKERS` (existing) — see DISC-03. Planner may alias this to `CRAWLER_MAX_WORKERS` for D-14 compatibility, or update D-14. `CRAWLER_USER_ID` (existing, required) unaffected. `CRAWLER_DEFAULT_CATEGORY_NAME` (existing, required) unaffected. | Plan decision: keep `CRAWLER_MAX_ADAPTER_WORKERS` (more descriptive) and record the name in the plan's decision table. |
| **Build artifacts / installed packages** | `backend/requirements.txt` must gain `pybreaker==1.4.1` line. Docker image rebuild required on merge. | CI's pip cache invalidates on `requirements.txt` hash change → auto-resolved. Document in plan's "infrastructure" verification step that the new container image's `pip list` shows pybreaker. |

**Fresh codebase verification performed 2026-04-22:**
- `grep -rnE "@validator\b\|@root_validator\b\|class Config:" backend/app/` → **zero hits** [VERIFIED]
- `grep -rnE "\.dict\(\)\|\.parse_obj\(" backend/app/` → **zero hits** [VERIFIED]
- `grep -rn "@app\.on_event" backend/app/` → **zero hits** [VERIFIED]
- `grep -rn "Depends(get_logger)" backend/app/` → **68 hits across 10 files** (per-file breakdown below) [VERIFIED]

Per-file `Depends(get_logger)` site count (2026-04-22 snapshot):

| File | Sites |
|------|------:|
| `backend/app/api/endpoints/auth.py` | 21 |
| `backend/app/api/endpoints/users.py` | 11 |
| `backend/app/api/utils/base_endpoint_router.py` | 8 |
| `backend/app/api/utils/base_report_router.py` | 6 |
| `backend/app/api/endpoints/reports.py` | 5 |
| `backend/app/api/utils/common_patterns.py` | 4 |
| `backend/app/api/utils/base_vote_router.py` | 4 |
| `backend/app/api/endpoints/bug_reports.py` | 4 |
| `backend/app/api/utils/admin_endpoint_patterns.py` | 3 |
| `backend/app/api/endpoints/votes.py` | 2 |
| **Total** | **68** |

---

## Common Pitfalls

### Pitfall AD-01: `__init_subclass__` fires for every subclass, even via `isinstance`/`issubclass` imports

**What goes wrong:** If `RetailerCrawlerAdapter.__init_subclass__` raises `TypeError` on missing `ADAPTER_NAME`, ANY intermediate abstract or test-helper subclass without `ADAPTER_NAME` blows up at import time — potentially before the test's `pytest.raises` has a chance to catch it.
**Why it happens:** `__init_subclass__` fires when the class body is executed, not when the class is first instantiated.
**How to avoid:** Exempt classes that still have `__abstractmethods__` (still abstract) AND exempt `IS_FALLBACK=True` (per D-03). The `GenericHtmlParser` sets `IS_FALLBACK=True` to clear the check.
**Warning signs:** Any `class X(RetailerCrawlerAdapter)` in a test file without an `ADAPTER_NAME` will blow up. Mitigation: test-only adapters declare `ADAPTER_NAME = "test_x"` + `IS_FALLBACK = True`.

### Pitfall AD-02: `pkgutil.iter_modules` doesn't recurse into subpackages

**What goes wrong:** If someone ever nests a subpackage under `tier0_http/` (e.g., a vendor-specific shim), `pkgutil.iter_modules(pkg.__path__)` won't find it unless we also recurse.
**Why it happens:** `iter_modules` is shallow by design.
**How to avoid:** Current tree has a flat structure (all adapter files are direct children of tier0_http/, tier1_tls/, tier2_browser/). Document the flat-structure invariant in `adapters/__init__.py`. If nesting ever happens, switch to `pkgutil.walk_packages` (but that requires `onerror=` to preserve our per-module error isolation).
**Warning signs:** A new `.py` file at `adapters/tier0_http/somevendor/adapter.py` (under a subfolder) — the test-count assertion would fail because the adapter wouldn't be discovered.

### Pitfall AD-03: Discovery errors during `pytest` collection masquerade as unrelated failures

**What goes wrong:** If `import app.crawlers.adapters` triggers a traceback at module-import time (because an adapter has a syntax error and `_IMPORT_ERRORS` accumulates + discovery raises), every test that does `from app.main import app` fails with the same opaque error, not just the discovery test.
**Why it happens:** Python module-import is once-per-process; the first failure poisons the well.
**How to avoid:** D-05 says "loader raises `RuntimeError` if `_IMPORT_ERRORS` is non-empty OR count < expected" — but that raise happens AT IMPORT TIME, so tests that import `ADAPTER_REGISTRY` get a module-level crash. Better pattern: DON'T raise at import time; only populate `_IMPORT_ERRORS`, and let `test_adapter_discovery.py` assert on it. This way a single targeted test fails, not every test.
**Warning signs:** CI shows 200+ test failures all with the same stack trace. Fix: move the `raise RuntimeError` from the `adapters/__init__.py` loader into the discovery test.

### Pitfall BR-01: pybreaker breaker registry dict mutation under concurrent first-access

**What goes wrong:** Two workers call `get_breaker("foo")` simultaneously on a registry where `"foo"` doesn't yet exist — both construct a new `CircuitBreaker`, both `_BREAKERS["foo"] = ...`, but only one wins. The losing thread's breaker has no listeners attached; its failures don't count anywhere.
**Why it happens:** Dict `__setitem__` is atomic in CPython under the GIL but the "check-then-set" pattern isn't.
**How to avoid:** Module-level `threading.Lock()` around the check-and-set. Double-checked locking is fine here because we're writing to a dict, not a class. See Pattern 2 above.
**Warning signs:** Tests may pass because they rarely race. Load test with 108 workers hitting 108 never-before-seen adapter names simultaneously — if two workers hit the same adapter name in a race, one's breaker orphans.

### Pitfall BR-02: `breaker.open()` doesn't pass the triggering exception

**What goes wrong:** Per pybreaker source (line 281-287), `breaker.open()` is unconditional; it sets the state to OPEN but does NOT record which exception caused it. Subsequent `breaker.call(...)` raises `CircuitBreakerError("Timeout not elapsed yet, circuit breaker still open")` with no cause — the original 429/503 is lost for debugging.
**Why it happens:** `open()` is the "external signal" path, designed for monitoring-system-triggered trips, not for "I saw a bad status myself."
**How to avoid:** LOG the 429/503 cause BEFORE calling `breaker.open()`. The `logger.warning(...)` call (see Pattern 3) captures the URL, status, and reason — the email report reads `rate_limit_bailout_after` to find the last URL processed. Not an "explicit trigger" but debuggable.
**Warning signs:** An operator opens the job report email, sees `rate_limit_bailout=true`, and can't tell from the samples whether it was 429 or 503 that tripped it. Mitigation: add `rate_limit_bailout_status: int | None` to the result dict.

### Pitfall BR-03: `CircuitBreakerError` is NOT a subclass of `FetcherError`

**What goes wrong:** The existing `runner.py` `except Exception as e:` block at line 526 catches EVERYTHING. After adding `breaker.call(...)`, a `CircuitBreakerError` raised by the breaker (when OPEN) falls into that block and gets classified with the general error handler. The D-12 "terminate loop + record bailout" path needs a NARROWER exception handler.
**Why it happens:** The catch-all was written for the old custom-counter design where `CircuitBreakerError` didn't exist.
**How to avoid:** Add an explicit `except pybreaker.CircuitBreakerError:` BEFORE the `except Exception as e:` block. Pattern 3 above shows the correct ordering.
**Warning signs:** The job report shows `errors: 45` and `rate_limit_bailout: false` even though the breaker clearly opened mid-run — the `CircuitBreakerError`s are being counted as ordinary errors.

### Pitfall BR-04: `breaker.call(fn, *args)` unpacks args; fetcher expects kwargs

**What goes wrong:** `breaker.call(adapter.fetcher.fetch, url, timeout=5)` passes `timeout` as a keyword argument through `call(func, *args, **kwargs)` — verify pybreaker 1.4.1 supports kwargs pass-through.
**Why it happens:** Some circuit-breaker libraries accept only positional args.
**How to avoid:** Verified in pybreaker 1.4.1 source: `def call(self, func, *args, **kwargs) -> T` at line 241 [VERIFIED: `/tmp/pb_pkg/pb_src/pybreaker/__init__.py:241`]. Kwargs are passed through to the state's `call()` method untouched.
**Warning signs:** None — this works.

### Pitfall TP-01: SQLAlchemy `Session` is thread-LOCAL, not thread-SAFE

**What goes wrong:** Sharing one `SessionLocal()` across workers causes `InvalidRequestError: This session is already in use`. D-15 specifies per-worker sessions, which avoids this.
**Why it happens:** SQLAlchemy `Session` holds `Connection` state that can't be accessed from another thread safely.
**How to avoid:** D-15 pattern — each worker calls `db = SessionLocal()` inside its `try` block at the top of `run_crawler`, closes in `finally`. Already implemented correctly at `runner.py:run_crawler`.
**Warning signs:** `InvalidRequestError` mid-crawler-run, `TypeError: no such column` from stale cursor — classic thread-sharing symptom.

### Pitfall TP-02: `ThreadPoolExecutor` swallows `future.result()` exceptions until you ask

**What goes wrong:** `executor.submit(run_one, name)` puts the work in a future. If `run_one` raises and nobody ever calls `future.result()`, the exception is silently buried until interpreter exit.
**Why it happens:** `as_completed` DOES yield the future, but if `future.result()` isn't unconditionally called, the exception sits there.
**How to avoid:** The existing `run_one` wraps everything in try/except and returns `{"_error": ..., "_adapter": ...}` — no exception escapes. Preserve this pattern.
**Warning signs:** A broken adapter leaves zero trace in the job report email.

### Pitfall HC-01: `HEALTH_PROBE_URL` default derivation (DISC-04)

**What goes wrong:** D-18 says default probe URL is `{BASE_URL}/robots.txt` — but 108 adapters have zero `BASE_URL` class attribute. If we default `HEALTH_PROBE_URL = ""` and try to derive at runtime, we get `f"{BASE_URL}/robots.txt"` = `"/robots.txt"` which is not a URL.
**Why it happens:** Adapter authors embed host in module-level constants (e.g., `BTR_BASE = "https://briantooleyracing.com"` in briantooleyracing.py), not class attributes.
**How to avoid:** Planner picks ONE of:
- **(Option A) Opt-in explicit URL:** Default `HEALTH_PROBE_URL: ClassVar[str | None] = None` → `check_health()` returns early with `reason="skipped_by_config"`. Adapters that want health checks declare `HEALTH_PROBE_URL = "https://host.com/robots.txt"` explicitly. Simple, non-breaking, but only a fraction of adapters get the probe.
- **(Option B) Full BASE_URL sweep:** Add `BASE_URL: ClassVar[str]` to all 108 adapters in the same sweep that adds `ADAPTER_NAME`. Default probe becomes `f"{BASE_URL.rstrip('/')}/robots.txt"`. Full coverage but doubles the sweep scope.
- **(Option C) Name-to-host reverse lookup:** Use `adapter_name_for_product_url()` in reverse (it maps URL → name; we want name → URL). Fragile — some adapters have multiple hosts (e.g., fortune-auto.com + fortuneauto-na.com).
**Recommendation:** Start with Option A for Phase 3. Option B can be a follow-up once every adapter has an `ADAPTER_NAME` baseline.
**Warning signs:** Plan includes a test that asserts every adapter has a `HEALTH_PROBE_URL` → test fails for the majority.

### Pitfall HC-02: `robots.txt` probes trigger the block on tier2 anti-bot sites

**What goes wrong:** For ecstuning / jegs / tirerack (tier2_browser with Cloudflare), even `GET /robots.txt` triggers the JS challenge. The probe takes 30s+ (FlareSolverr spin-up) and sometimes gets a 403 — which WE report as "unhealthy" when the actual site is fine for our adapter.
**Why it happens:** The block isn't on the content, it's on the TLS fingerprint / cookie state.
**How to avoid:** D-18 explicitly allows `HEALTH_PROBE_URL = None` to skip. All tier2_browser adapters should probably set `None`. Plan should include a deliberate audit of the 10 tier2_browser adapters before landing.
**Warning signs:** First run after CRAWL-06 lands shows all 10 tier2 adapters skipped with `reason="http_4xx"` even though they work.

### Pitfall HC-03: 5s timeout is aggressive for cold DNS on retailer sites

**What goes wrong:** Some retailers take 6-8 seconds for first-byte (no CDN, long TLS handshake, cold cache). 5s default timeout triggers `reason="timeout"` on the first probe of the day.
**Why it happens:** Globally distributed e-commerce sites have variable latencies.
**How to avoid:** Per REQ-CRAWL-06, the timeout is fixed at 5s (locked). Accept the small false-positive rate; an adapter that's routinely >5s on `robots.txt` is genuinely slow and deserves the warning.
**Warning signs:** Job report shows 5-10 "health_timeout" skips per run, but the adapter ran fine last week.

### Pitfall PR-01: Parse-failure sample-URL truncation for long URLs (Claude's-discretion D-22)

**What goes wrong:** Some retailer product URLs are >200 chars (query-string variant selectors). Dumping all 5 verbatim in an email can make the HTML block unreadable.
**How to handle:** Truncate to first 120 chars + `…` + last 40 chars (preserves host + path-head and any fragment/anchor). Show a tooltip via `title=` attribute for the full URL on hover. Claude's-discretion territory.
**Warning signs:** Email rendering test shows a single `<li>` that wraps to 6 lines.

### Pitfall JS-01: `@lru_cache(maxsize=1)` + `uvicorn --reload` dict-mutation hazard

**What goes wrong:** If any downstream code mutates the returned dict (e.g., `load_car_generations()["subaru"].append(...)` in a seed script), the next call returns the mutated version. `lru_cache` returns the SAME dict reference each call.
**Why it happens:** Python's `lru_cache` caches the return value; it doesn't deep-copy on return.
**How to avoid:** Audit callers of `CAR_GENERATIONS` and `get_all_car_generations()`. If any mutate, either (a) wrap returns in `types.MappingProxyType(...)` for read-only, or (b) add a docstring warning + code review discipline. Current callers (`car_inference.py`, `init_cars.py`, models, endpoints) are read-only based on grep audit.
**Warning signs:** A test that runs a mutation on the dict in one test case and reads it in another — one test mutates, the other sees the mutation.

### Pitfall JS-02: `importlib.resources.files()` returns `MultiplexedPath` when multiple site-packages hit

**What goes wrong:** In some venv setups, `files("app.core")` returns a `MultiplexedPath` instead of a concrete `Path`; `joinpath("car_generations_data.json")` works, but `.read_text()` may have weird encoding defaults.
**Why it happens:** Editable installs + namespace packages can interleave.
**How to avoid:** Always pass `encoding="utf-8"` to `read_text()`. Test locally in both `pip install -e .` and `pip install .` modes.
**Warning signs:** Unicode decoding errors on a clean production Docker image but fine in dev.

### Pitfall QU-01: `--disable-warnings` in pytest.ini defeats command-line `-W error`

**What goes wrong:** Adding `-W error::PydanticDeprecatedSince20` to the pytest command line (or even inside addopts) has NO effect because the `--disable-warnings` flag in the existing `pytest.ini` suppresses all warnings after collection.
**Why it happens:** `--disable-warnings` sets `disable-warnings = True` on the pytest config, which bypasses the `-W` filters entirely.
**How to avoid:** Use `warnings.catch_warnings()` + `warnings.simplefilter("error", pydantic.PydanticDeprecatedSince20)` INSIDE the test function body. See Pattern 6.
**Warning signs:** QUAL-02 regression test passes when a `.dict()` is added, even though the deprecation warning is surfacing — because pytest is hiding it.

### Pitfall QU-02: Grep test false positives on `.dict()` for non-Pydantic objects

**What goes wrong:** `.dict()` matches SQLAlchemy `Row._mapping` casts, `Namespace.__dict__`, and other unrelated constructs.
**Why it happens:** Python's `.dict()` is shared across Pydantic, `dataclasses.asdict`-like helpers, and third-party libs.
**How to avoid:** Allow-list pattern (see Pattern 7). OR use a smarter regex that excludes `Row\.dict\(\)`, `\.__dict__`, `namedtuple\._asdict`. OR drop `.dict()` from the grep list and rely solely on the `PydanticDeprecatedSince20` warnings-as-error probe, which is exact.
**Warning signs:** CI fails on an unrelated SQLAlchemy query. Iterate on the allow-list.

### Pitfall QU-03: `main.py` lifespan signature is async; grep must tolerate it

**What goes wrong:** The grep for `@app\.on_event\(` is not fooled by `async def lifespan(app)` — but a maintenance PR adding `@asynccontextmanager @app.on_event(...)` in some weird compat shim could slip past. Extremely unlikely.
**How to avoid:** Two patterns cover it: `@app\.on_event\(` AND `@.*\.on_event\(` (broader). Use the broader pattern to be safe.
**Warning signs:** None likely; this is paranoia-level.

### Pitfall QU-07: 68 `Depends(get_logger)` sites include 10+ in shared util modules

**What goes wrong:** Util modules (`base_endpoint_router.py`, `base_vote_router.py`, etc.) have `Depends(get_logger)` in dependency-injected FUNCTION signatures — removing the parameter doesn't just move the logger, it changes the function's FastAPI route signature (which may affect the OpenAPI schema, failing Phase 1 SAFE-05).
**Why it happens:** FastAPI introspects route function signatures to build OpenAPI. If `Depends(get_logger)` shows up as a route parameter, it's part of the schema.
**How to avoid:** Run `python -c "import json; from app.main import app; print(json.dumps(app.openapi(), sort_keys=True))"` before and after the sweep. Diff. If the OpenAPI changes (it shouldn't, since `Depends()` parameters are excluded from the OpenAPI spec by FastAPI), commit the updated snapshot.
**Warning signs:** SAFE-05 snapshot test fails after QUAL-07 land. Fix: regenerate + review the diff; if legitimate (purely removal of hidden params), commit.

---

## Code Examples

All patterns above (1-8) are verified code examples. Additional real-codebase references:

### Current breaker block to DELETE (D-07)

```python
# backend/app/crawlers/runner.py:64-71 (CONSTANTS)
RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5
RATE_LIMIT_CIRCUIT_BREAKER_STATUSES = frozenset({429, 502, 503, 504})

# backend/app/crawlers/runner.py:444-452 (STATE INIT — delete)
# Circuit-breaker state. `consecutive_rate_limited` counts URLs whose
# retry chain exhausted against 429/502/503/504; reset whenever a fetch
# returns (any HTTP response, including 4xx that prove the origin is
# alive). `rate_limit_bailout` flips to True when the threshold trips
# and is surfaced in the returned result.
consecutive_rate_limited = 0
rate_limit_bailout = False
rate_limit_bailout_after = 0

# backend/app/crawlers/runner.py:475-478 (RESET ON SUCCESS — delete, but preserve comment)
# Fetch returned without raising — origin is responsive. Reset
# the circuit-breaker counter regardless of whether parsing
# succeeds downstream; we only care about upstream health here.
consecutive_rate_limited = 0

# backend/app/crawlers/runner.py:536-545 (COUNT ON FAILURE — delete)
# Circuit-breaker accounting: a status in the rate-limit set
# means the per-URL retry chain fully exhausted against the
# upstream. Any other HTTP status (e.g. 404/410) resets the
# counter because it proves the origin served our request.
# Non-HTTP failures (timeouts/connection errors, status=None)
# are ambiguous and left untouched.
if status in RATE_LIMIT_CIRCUIT_BREAKER_STATUSES:
    consecutive_rate_limited += 1
elif status is not None:
    consecutive_rate_limited = 0

# backend/app/crawlers/runner.py:569-582 (TRIP — replace with CircuitBreakerError catch)
if consecutive_rate_limited >= RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD:
    logger.error(
        "Adapter %s: circuit breaker tripped after %s consecutive rate-limited "
        "fetches (last status %s). Bailing at %s/%s URLs to avoid hammering a "
        "struggling origin.",
        adapter_name, consecutive_rate_limited, status, i, total,
    )
    rate_limit_bailout = True
    rate_limit_bailout_after = i
    break
```

### Result-dict schema preserved (D-12)

The existing result dict at `runner.py:621-644` has `rate_limit_bailout` + `rate_limit_bailout_after` keys already. CRAWL-07 ADDS two new keys without removing any:

```python
return {
    "adapter": adapter_name,
    "ingested": ingested,
    "skipped": skipped,
    "skipped_robots": skipped_robots,
    "skipped_not_product": skipped_not_product,
    "skipped_gone": skipped_gone,
    "errors": errors,
    "total": total,
    "http_errors": http_errors,
    "error_urls": error_urls,
    "error_urls_truncated": errors > len(error_urls),
    "parse_miss_urls": parse_miss_urls,
    "parse_miss_urls_truncated": skipped_not_product > len(parse_miss_urls),
    "rate_limit_bailout": rate_limit_bailout,
    "rate_limit_bailout_after": rate_limit_bailout_after,
    # --- NEW (CRAWL-07) ---
    "parse_failures": skipped_not_product,          # alias; keeps the intent distinct from "errors"
    "sample_failure_urls": [p["url"] for p in parse_miss_urls[:5]],  # first 5, URL-only
    # --- NEW (CRAWL-06) ---
    "health_skipped": False,                        # True when check_health() returned unhealthy
    "health_reason": None,                          # one of the HealthResult.reason values
    "health_status_code": None,                     # HTTP status if applicable
}
```

### Thin-shim replacement for `car_generations_data.py` (DISC-05)

```python
# backend/app/core/car_generations_data.py (post-QUAL-01)
"""Thin shim preserving the public API of the old 8,412-line module.

The huge CAR_GENERATIONS literal now lives in car_generations_data.json and is
loaded lazily via car_generations.load_car_generations(). Callers see no change
in behavior; import paths and symbol shapes are identical.
"""
from __future__ import annotations

import re
from typing import TypedDict
from typing_extensions import NotRequired

from app.core.car_generations import load_car_generations


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


class CarGenerationData(TypedDict):
    generation_name: str
    start_year: int
    end_year: int | None
    description: NotRequired[str]
    display_name: NotRequired[str]
    slug: NotRequired[str]


# Lazily populated; preserves the module-level name used by car_inference.py:15
CAR_GENERATIONS = load_car_generations()  # lru_cached, one-time cost on first call


def get_all_car_generations() -> list[dict[str, str | int | None]]:
    """Unchanged semantics — iterates over CAR_GENERATIONS."""
    generations: list[dict[str, str | int | None]] = []
    for make, models in CAR_GENERATIONS.items():
        for model_data in models:
            model = model_data["model"]
            model_display_name = model_data.get("model_display_name")
            model_slug = model_data.get("slug") or slugify(model)
            for gen in model_data["generations"]:
                gen_dict: dict[str, str | int | None] = {
                    "make": make,
                    "model": model,
                    "model_slug": model_slug,
                    "model_display_name": model_display_name,
                    "generation_name": gen["generation_name"],
                    "generation_slug": gen.get("slug") or slugify(gen["generation_name"]),
                    "display_name": gen.get("display_name"),
                    "start_year": gen["start_year"],
                    "end_year": gen["end_year"],
                }
                if "description" in gen:
                    gen_dict["description"] = gen["description"]
                generations.append(gen_dict)
    return generations
```

This way `from app.core.car_generations_data import slugify` still works in the migration at `backend/alembic/versions/30e2e2139a2e_*.py:24`, in `backend/app/api/models/car_generation.py:11`, `car_model.py:16`, and `tests/test_init_cars_display_name.py:17` — without any of those files changing.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-maintained `ADAPTER_REGISTRY` dict with 100+ `from X import Y` lines | `pkgutil.iter_modules` + `importlib.import_module` with `__init_subclass__` enforcement | Phase 3 (this phase) | New adapters auto-register; CI count-assert catches accidental omissions |
| Custom in-runner counter for rate-limit circuit breaker | `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)` per-adapter registry | Phase 3 (this phase) | Thread-safe; half-open probing; fewer lines of code |
| `Depends(get_logger)` parameter injection | Module-level `logging.getLogger(__name__)` | Phase 3 (this phase) | FastAPI-native; no `Depends` round-trip on every request; request-context preserved via existing `RequestContextFilter` |
| 8,412-line Python literal `CAR_GENERATIONS` | Package-adjacent JSON + `@lru_cache` loader | Phase 3 (this phase) | Eliminates startup parse cost; keeps API shape identical |
| Pydantic v1 `@validator`, `class Config`, `.dict()`, `.parse_obj()` | Pydantic v2 `@field_validator`, `model_config`, `.model_dump()`, `.model_validate()` | Pre-Phase 3 (already complete) | Phase 3 installs regression guards only |
| `@app.on_event("startup"/"shutdown")` | `async def lifespan(app)` context manager | Pre-Phase 3 (already complete; `main.py:70`) | Phase 3 installs regression guard only |
| `python-jose` JWT | `PyJWT 2.12.1` | Phase 5 (future) | Not a Phase 3 concern |

**Deprecated / outdated:**
- `@app.on_event` — FastAPI deprecated in 0.100+ in favor of `lifespan`. Already migrated in CarModPicker.
- Pydantic v1 API (`BaseModel.dict()`, `BaseModel.parse_obj()`, `@validator`, `class Config`) — removed in Pydantic 3.0 (not yet released); deprecation warnings emitted since Pydantic 2.0.
- `python-jose` — still imported but slated for replacement in Phase 5 (AUTH-04). Not a Phase 3 concern.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pybreaker.CircuitBreaker.call(...)` passes kwargs through to the underlying function | Pattern 3 / Pitfall BR-04 | LOW — verified in source, but if the 1.4.1 API ever changes, fetcher's `timeout=5` kwarg silently drops. [VERIFIED against pybreaker 1.4.1 source] |
| A2 | `breaker.open()` programmatic call DOES fire `state_change` listeners | D-11 analysis | LOW — verified: `open()` → `self.state = STATE_OPEN` setter → `_create_new_state(..., notify=True)` → `CircuitOpenState.__init__(notify=True)` → iterates listeners. [VERIFIED: pybreaker 1.4.1 source lines 189-192, 281-287, 829-840] |
| A3 | `@lru_cache(maxsize=1)` on `load_car_generations()` is thread-safe | Pattern 5 | LOW — CPython `lru_cache` is thread-safe; documented in stdlib. [CITED: https://docs.python.org/3/library/functools.html#functools.lru_cache] |
| A4 | Current callers of `CAR_GENERATIONS` / `get_all_car_generations()` don't mutate the dict | Pitfall JS-01 | MEDIUM — grep-based audit of 4 direct callers shows read-only access. Risk is a future caller adds mutation; mitigation is a docstring warning + code review. [VERIFIED by grep audit 2026-04-22] |
| A5 | Python 3.13's `importlib.resources.files()` is stable and works in the App Runner Docker image (python:3.13-slim) | Pattern 5 | LOW — stable API since 3.12; `python:3.13-slim` is the project's deployment base. [CITED: https://docs.python.org/3.13/library/importlib.resources.html; VERIFIED: `backend/Dockerfile` uses `python:3.13-slim`] |
| A6 | FastAPI's OpenAPI schema excludes `Depends()` parameters from route signatures | Pitfall QU-07 | LOW-MEDIUM — FastAPI docs say yes. Verify via the before/after `app.openapi()` diff during the sweep. [ASSUMED from FastAPI docs; VERIFY IN PLAN — "compute openapi-snapshot diff in the QUAL-07 PR; confirm zero-delta"] |
| A7 | `--disable-warnings` in pytest.ini suppresses `-W error::...` CLI flags | Pitfall QU-01 | LOW — documented pytest behavior. Mitigation is the context-manager approach in Pattern 6. [CITED: https://docs.pytest.org/en/stable/how-to/capture-warnings.html] |
| A8 | `pybreaker 1.4.1` works under Python 3.13 | Standard Stack | LOW — pybreaker docs say "Python ≥ 3.10"; 3.13 is covered. Active maintenance (last release 2025-09-21). [VERIFIED: PyPI, GitHub releases] |
| A9 | SES job-report email recipients & template infrastructure are unchanged by CRAWL-07 | Pattern / architecture | LOW — existing `send_job_report_email` in `backend/app/core/email.py:72` takes the result dict and renders HTML; adding new keys to the dict + rendering them in `_render_crawler_result_html` is additive. [VERIFIED: grep inspection of email.py] |
| A10 | The 5 characterization tests (Phase 1 SAFE-07) will pass under the new `ADAPTER_NAME`-keyed pattern | Phase 1 D-23 handoff | LOW — tests key by class name today and switch to `ADAPTER_NAME` (`D-23` deferred to Phase 3). `ADAPTER_NAME` values must match the tier0/1 adapter class name slugs already used in `ADAPTER_REGISTRY` keys. [VERIFIED by reading `test_characterization_briantooleyracing.py` and `adapters/__init__.py:134-248`] |
| A11 | 108 is the correct baseline count for `ADAPTER_REGISTRY` after `IS_FALLBACK` exclusion | DISC-01 | MEDIUM — could drift if `__init_subclass__` logic accidentally registers a helper/base class. Planner should compute the count DURING plan verification by running the discovery scan and recording the actual number. [VERIFIED: counted 83+15+10=108 non-init adapter modules + 1 GenericHtmlParser fallback; grep returned 108 concrete subclasses] |
| A12 | The `__init_subclass__` TypeError approach will NOT fire for test-local adapter subclasses that intentionally don't set `ADAPTER_NAME` | Pitfall AD-01 | MEDIUM — need to ensure `IS_FALLBACK=True` OR `__abstractmethods__` exemption catches every test-helper pattern. Planner should search for `class X(RetailerCrawlerAdapter)` in `backend/tests/` and confirm none would break. [ASSUMED — verify during plan task-breakdown; recommend a pre-plan grep audit] |
| A13 | The existing `CRAWLER_MAX_ADAPTER_WORKERS` env var is read by production / dev ops scripts | DISC-03 | MEDIUM — renaming to `CRAWLER_MAX_WORKERS` per D-14 could break a prod override. Recommendation: keep the existing name (Claude's-discretion under D-14's naming). [ASSUMED — verify by grep of `.github/workflows/`, `terraform/`, and any docs/README] |

---

## Open Questions

1. **Should `HEALTH_PROBE_URL` default to `None` (opt-in) or `f"{BASE_URL}/robots.txt"` with a full `BASE_URL` sweep?** (Pitfall HC-01 / DISC-04)
   - What we know: Zero adapters have `BASE_URL` today; D-18 says default derived from `BASE_URL`.
   - What's unclear: Whether the 108-adapter `BASE_URL` sweep doubles the plan scope or whether `None`-default + explicit opt-in is acceptable coverage.
   - **Recommendation:** Go with Option A (opt-in). The 5 Phase-1 characterization-tested adapters are a natural starting set. Full coverage is a follow-up. Planner to surface this trade-off in the CRAWL-06 plan.

2. **Should pybreaker's `state_change` listener fire a log event for observability, or is that deferred to Phase 2 entirely?** (CONTEXT Deferred Ideas)
   - What we know: CONTEXT says "Observability instrumentation of the breaker itself ... belongs in Phase 2, not Phase 3."
   - What's unclear: Is a simple `logger.warning("Breaker for %s state %s→%s")` inside Phase 3 already "observability instrumentation"? Or just "logging"?
   - **Recommendation:** Phase 3 adds a minimal breaker-state-change LOG line (matches existing `logger.error("Adapter X: circuit breaker tripped...")` pattern). Phase 2 adds CloudWatch emission + Sentry crumbs on top of that same listener. Low risk of scope creep.

3. **Does the OpenAPI schema change when `Depends(get_logger)` parameters are removed from route functions?** (Pitfall QU-07)
   - What we know: FastAPI excludes `Depends()` from OpenAPI — so NO, the schema shouldn't change.
   - What's unclear: Edge cases where a util router module has non-Depends logger parameters mixed in.
   - **Recommendation:** Run `python -c "from app.main import app; print(app.openapi())"` before AND after the QUAL-07 sweep. Diff. Commit the diff (expected: empty). If non-empty, inspect + either update snapshot or revert the bad rename.

4. **How are the `parse_failures` / `sample_failure_urls` keys consumed by Phase 2's CloudWatch code (D-24)?** (CONTEXT §specifics)
   - What we know: OBS-02 in REQUIREMENTS.md says "per-adapter `Ingested`, `ParseFailures`, `ElapsedSeconds` metrics" — maps 1:1 to `ingested`, `parse_failures`, elapsed.
   - What's unclear: Does `ElapsedSeconds` exist in the current result dict? (Grep: no — `elapsed` isn't a current key.)
   - **Recommendation:** Phase 3 adds `elapsed_seconds: float` (time.monotonic() delta around the URL loop) to the result dict. OBS-02 reads it. This is a 3-line addition and is in CRAWL-07 scope ("per-adapter failure counts + timings" is implied by D-22's email template including "Elapsed: {seconds}s").

5. **Does the thin-shim `car_generations_data.py` (DISC-05) cause a cyclic import with `car_generations.py`?** (QUAL-01 edge)
   - What we know: `car_generations.py` has zero imports from `car_generations_data`; the shim imports from it.
   - What's unclear: Whether any OTHER module imports from BOTH at runtime in a specific order that creates a cycle.
   - **Recommendation:** Build an import-order graph with `python -X importtime -c "import app.main"` before + after. If no cycle, proceed.

---

## Environment Availability

Phase 3 touches only Python + installed packages + existing CI. No external services beyond the already-existing SES email path.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All Phase 3 code | ✓ | 3.13 (Dockerfile, CI workflow) | — |
| `pybreaker` | CRAWL-04 | ✗ (to add) | 1.4.1 (target) | — (no fallback; blocking for CRAWL-04) |
| `importlib.resources` | QUAL-01 | ✓ (stdlib 3.13) | — | — |
| `pkgutil` | CRAWL-01 | ✓ (stdlib) | — | — |
| `functools.lru_cache` | QUAL-01 | ✓ (stdlib) | — | — |
| `pydantic` | QUAL-02 regression test | ✓ | 2.11.3 | — |
| SES (AWS) | CRAWL-07 email extension | ✓ (existing) | — | — |
| RDS PostgreSQL | CRAWL-05 per-worker `SessionLocal()` | ✓ (existing) | 16 | — |

**Missing dependencies with no fallback:**
- `pybreaker 1.4.1` — must be added to `backend/requirements.txt` as part of CRAWL-04 plan.

**Missing dependencies with fallback:** None.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest 8.x` + `pytest-xdist` + `pytest-cov` |
| Config file | `backend/pytest.ini` (existing; `--cov-fail-under=51` landed in Phase 1) |
| Quick run command | `pytest -n auto backend/tests/crawlers/test_adapter_discovery.py backend/tests/test_pydantic_v1_regression.py backend/tests/test_on_event_regression.py -x` |
| Full suite command | `pytest -n auto --cov=app --cov-fail-under=51` |

Phase 3 uses the existing test infrastructure untouched. All new tests must be worker-safe (`-n auto --dist=loadfile`).

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRAWL-01 | `ADAPTER_REGISTRY` populated by directory scan | unit | `pytest backend/tests/crawlers/test_adapter_discovery.py -x` | ❌ Wave 0 |
| CRAWL-02 | Every adapter declares non-empty `ADAPTER_NAME`; `__init_subclass__` raises on missing | unit | `pytest backend/tests/crawlers/test_adapter_discovery.py::test_all_adapters_have_name -x` | ❌ Wave 0 |
| CRAWL-02 | Count matches hard-coded baseline (108 per DISC-01) | unit | `pytest backend/tests/crawlers/test_adapter_discovery.py::test_adapter_count_baseline -x` | ❌ Wave 0 |
| CRAWL-03 | `_IMPORT_ERRORS` is empty after discovery; logs at ERROR on failure | unit | `pytest backend/tests/crawlers/test_adapter_discovery.py::test_no_import_errors -x` | ❌ Wave 0 |
| CRAWL-04 | `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)` opens after 3 consecutive failures + terminal 429/503 | unit | `pytest backend/tests/crawlers/test_circuit_breaker.py -x` | ❌ Wave 0 |
| CRAWL-04 | Per-adapter-name registry isolates breakers (breaker for A ≠ breaker for B) | unit | `pytest backend/tests/crawlers/test_circuit_breaker.py::test_breaker_registry_isolation -x` | ❌ Wave 0 |
| CRAWL-04 | `rate_limit_bailout=True` + `rate_limit_bailout_after=N` recorded on open | integration | `pytest backend/tests/crawlers/test_runner_breaker.py -x` | ❌ Wave 0 |
| CRAWL-05 | `ThreadPoolExecutor` worker count = `min(80, N)` with `CRAWLER_MAX_ADAPTER_WORKERS` override | unit | `pytest backend/tests/crawlers/test_compute_adapter_workers.py -x` | ❌ Wave 0 (existing code; tests likely absent) |
| CRAWL-05 | Each worker holds its own `SessionLocal` (no session leakage) | integration | `pytest backend/tests/crawlers/test_parallel_session_isolation.py -x` | ❌ Wave 0 |
| CRAWL-06 | `check_health()` on unhealthy response sets `{skipped: true, skip_reason: "health_..."}` | unit | `pytest backend/tests/crawlers/test_health_check.py -x` | ❌ Wave 0 |
| CRAWL-06 | `HEALTH_PROBE_URL=None` skips probe (returns `healthy=True, reason="skipped_by_config"`) | unit | `pytest backend/tests/crawlers/test_health_check.py::test_none_probe_skips -x` | ❌ Wave 0 |
| CRAWL-07 | Result dict includes `parse_failures` + `sample_failure_urls` (first 5, URL-only) | unit | `pytest backend/tests/crawlers/test_runner_result_dict.py -x` | ❌ Wave 0 |
| CRAWL-07 | Email renderer includes ParseFailures block + sample URL list | unit | `pytest backend/tests/test_email.py::test_crawler_parse_failures_block -x` | ✅ `test_email.py` exists; add test case |
| QUAL-01 | `load_car_generations()` returns the same dict as `CAR_GENERATIONS` | integration | `pytest backend/tests/test_car_generations_loader.py -x` | ❌ Wave 0 |
| QUAL-01 | `@lru_cache(maxsize=1)` memoizes — second call is O(1), no file re-read | unit | `pytest backend/tests/test_car_generations_loader.py::test_lru_cache_single_load -x` | ❌ Wave 0 |
| QUAL-01 | Startup latency measurably improves (manual; before/after median of 3 `time uvicorn app.main:app --reload` runs) | **manual** | N/A — documented in PR description per D-28 | — |
| QUAL-02 | Grep scan of `backend/app/**/*.py` finds zero `@validator`, `@root_validator`, `class Config:`, `.parse_obj(` | unit | `pytest backend/tests/test_pydantic_v1_regression.py -x` | ❌ Wave 0 |
| QUAL-02 | Representative Pydantic v2 schema roundtrip emits zero `PydanticDeprecatedSince20` warnings | unit | `pytest backend/tests/test_pydantic_v1_regression.py::test_no_v1_warnings_on_roundtrip -x` | ❌ Wave 0 |
| QUAL-03 | Grep scan finds zero `@app\.on_event\(` matches | unit | `pytest backend/tests/test_on_event_regression.py -x` (or merged with QUAL-02) | ❌ Wave 0 |
| QUAL-07 | `grep -rn "Depends(get_logger)" backend/app/` returns zero | unit | `pytest backend/tests/test_logger_migration_regression.py -x` | ❌ Wave 0 |
| QUAL-07 | Post-sweep: existing tests still pass; OpenAPI snapshot unchanged | regression | `pytest backend/tests/test_openapi_snapshot.py -x` | ✅ exists |
| — (characterization regression) | All 5 Phase-1 characterization tests still pass after `ADAPTER_NAME` switch | unit | `pytest backend/tests/crawlers/test_characterization_*.py -x` | ✅ exist |

### Sampling Rate

- **Per task commit:** `pytest -n auto backend/tests/crawlers/test_adapter_discovery.py backend/tests/test_pydantic_v1_regression.py backend/tests/test_on_event_regression.py backend/tests/test_logger_migration_regression.py -x` (covers all regression guards, ~5s)
- **Per wave merge:** `pytest -n auto backend/tests/crawlers/ backend/tests/ -x` (full crawler + core suite)
- **Phase gate:** `pytest -n auto --cov=app --cov-fail-under=51` green before `/gsd-verify-work`; OpenAPI snapshot matches; `grep -rn "Depends(get_logger)" backend/app/` returns zero

### Wave 0 Gaps

Test infrastructure exists (`pytest.ini`, `conftest.py`, fixtures). New test files needed:

- [ ] `backend/tests/crawlers/test_adapter_discovery.py` — covers CRAWL-01, CRAWL-02, CRAWL-03 (count assertion + import-errors + unique `ADAPTER_NAME` + non-empty `ADAPTER_NAME`)
- [ ] `backend/tests/crawlers/test_circuit_breaker.py` — covers CRAWL-04 breaker registry + `fail_max`/`reset_timeout` semantics + terminal 429/503 → `breaker.open()`
- [ ] `backend/tests/crawlers/test_runner_breaker.py` — covers CRAWL-04 integration: runner catches `CircuitBreakerError`, records bailout, terminates loop
- [ ] `backend/tests/crawlers/test_compute_adapter_workers.py` — covers CRAWL-05 `_compute_adapter_workers` formula + `CRAWLER_MAX_ADAPTER_WORKERS` override
- [ ] `backend/tests/crawlers/test_parallel_session_isolation.py` — covers CRAWL-05 per-worker `SessionLocal` lifecycle
- [ ] `backend/tests/crawlers/test_health_check.py` — covers CRAWL-06 `check_health()` semantics including `HEALTH_PROBE_URL=None` skip path
- [ ] `backend/tests/crawlers/test_runner_result_dict.py` — covers CRAWL-07 `parse_failures` + `sample_failure_urls` + `elapsed_seconds` (Open Q #4) keys
- [ ] `backend/tests/test_car_generations_loader.py` — covers QUAL-01 JSON loader + `lru_cache` memoization + pre/post-shim equivalence
- [ ] `backend/tests/test_pydantic_v1_regression.py` — covers QUAL-02 grep scan + warnings-as-error roundtrip
- [ ] `backend/tests/test_on_event_regression.py` (or merged with QUAL-02) — covers QUAL-03 grep scan
- [ ] `backend/tests/test_logger_migration_regression.py` — covers QUAL-07 regression grep; `grep -rn "Depends(get_logger)" backend/app/` must return zero
- [ ] Add test case to existing `backend/tests/test_email.py` — covers CRAWL-07 renderer block

No framework install needed; `pytest` + `pytest-xdist` + `pytest-cov` already in the dev stack.

---

## Security Domain

Phase 3 is backend-only hardening with no auth/session/crypto changes. Security enforcement applies principally via QUAL-02 (defense-in-depth: ensure Pydantic input validation stays on v2 with no deprecation-warning-leaking paths).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (no auth changes) |
| V3 Session Management | no | — (no session changes) |
| V4 Access Control | no | — (no authz changes; admin crawler routes keep existing `Depends(get_current_admin_user)`) |
| V5 Input Validation | **yes** | Pydantic v2 schemas (locked by QUAL-02 regression test) |
| V6 Cryptography | no | — (no crypto changes; pybreaker has no crypto surface) |

### Known Threat Patterns for Python/FastAPI Crawler Workloads

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SSRF via user-supplied URLs to `adapter.fetcher.fetch(url)` | Elevation-of-privilege, Information-disclosure | Runner only accepts URLs from `adapter.discover_product_urls()` (sitemap-derived) — not user-supplied. Existing `can_fetch_url` checks robots.txt; existing host allowlist in `adapter_name_for_product_url` bounds hosts. No Phase 3 change. |
| Dependency-pinning supply-chain attack (pybreaker) | Tampering | Pin exact version (`pybreaker==1.4.1`); verify via `pip-audit` on CI (existing SAFE-10 pipeline). |
| Adapter module executing arbitrary code at import time (e.g., a new adapter with `os.system` in its module body) | Elevation-of-privilege | Per-module try/except isolates the import; `_IMPORT_ERRORS` records the failure; CI rejects. New adapter code is reviewed at PR time. |
| SES bill attack via excessive email sends (CRAWL-07 job report) | Denial-of-service (cost) | Existing SES send path already rate-limited; Phase 3 extends content, not frequency. No new attack surface. |
| `car_generations_data.json` tampering (malicious seed data affecting init_cars) | Tampering | Committed to git, reviewed at PR; no runtime fetch from S3/external. SHA256 via Git commit hash. No new attack surface. |

---

## Sources

### Primary (HIGH confidence)

- **pybreaker 1.4.1 source code** (inspected locally from PyPI wheel: `/tmp/pb_pkg/pb_src/pybreaker/__init__.py`) — RLock usage (line 103), `open()` body (281-287), state setter (179-195), `state_change` listener mechanism (800-850)
- **pybreaker GitHub README** — https://github.com/danielfm/pybreaker/blob/main/README.rst (exclude, listeners, thread safety claim)
- **pybreaker CHANGELOG** — https://github.com/danielfm/pybreaker/blob/main/CHANGELOG (v1.4.1 release 2025-09-21, min Python 3.10)
- **Python 3.13 `importlib.resources` docs** — https://docs.python.org/3.13/library/importlib.resources.html
- **Python 3.13 `pkgutil` docs** — https://docs.python.org/3.13/library/pkgutil.html
- **Python `functools.lru_cache` docs** — https://docs.python.org/3/library/functools.html#functools.lru_cache (thread safety)
- **Pydantic 2 deprecation reference** — `pydantic.PydanticDeprecatedSince20` class is the canonical filter target
- **CarModPicker codebase (2026-04-22 snapshot)**:
  - `backend/app/crawlers/runner.py` (custom breaker block lines 64-71, 444-582; ThreadPoolExecutor at 767-784)
  - `backend/app/crawlers/base.py` (retry loop `fetch_with_retries` at 532-603)
  - `backend/app/crawlers/adapters/__init__.py` (hand-maintained registry lines 134-248)
  - `backend/app/crawlers/adapters/base.py` (current base class 1-63)
  - `backend/app/crawlers/adapters/generic.py` (GenericHtmlParser, IS_FALLBACK target)
  - `backend/app/core/car_generations_data.py` (8,412 lines; exports `CAR_GENERATIONS`, `slugify`, `CarGenerationData`, `get_all_car_generations`)
  - `backend/app/db/session.py` (pool constants 27-29, worker-formula inputs)
  - `backend/app/main.py` (lifespan at 70, no on_event)
  - `backend/app/core/email.py` (send_job_report_email at 72; renderer at 221)
  - `backend/app/core/logging.py` (get_logger at 71)
  - `backend/pytest.ini` (--disable-warnings gotcha)
  - `backend/requirements.txt` (pydantic 2.11.3, fastapi 0.128.0, sqlalchemy 2.0.41, no pybreaker)
  - `backend/Dockerfile` (python:3.13-slim base)
  - `backend/tests/crawlers/test_characterization_*.py` (5 characterization tests keyed by class name today)

### Secondary (MEDIUM confidence)

- **FastAPI lifespan migration docs** — referenced by D-30 state; `@app.on_event` deprecation in FastAPI 0.100+
- **PyPI pybreaker listing** — https://pypi.org/project/pybreaker/ (download stats, metadata)
- **PyTutorial guide on `importlib.resources.files()`** — practical usage patterns

### Tertiary (LOW confidence)

- **pybreaker internals not documented externally** — `breaker.open()` firing `state_change` listeners verified directly from source (no docs guarantee). If pybreaker changes this behavior in a future major version, D-11 needs revisiting.

---

## Project Constraints (from CLAUDE.md)

Directives from `CarModPicker/CLAUDE.md` that the planner MUST honor:

1. **`pytest -n auto` always** — Any new test must be worker-safe. Pure-grep and pure-import tests are safe by construction; breaker-state and parallel-session tests must use fixtures that ensure per-worker isolation (no shared mutable module state across tests that run simultaneously in different workers).
2. **SQLite in-memory for tests, no Postgres required** — CRAWL-05 per-worker `SessionLocal()` tests must work against the SQLite-in-memory pool. Verify via the existing `backend/tests/conftest.py` pattern.
3. **Alembic autogenerate-only** — Phase 3 writes NO migrations. If a plan surfaces a schema change, re-examine the phase boundary. `car_generations_data.py` → JSON does NOT change DB schema; `init_cars` still reads the dict.
4. **`ENABLE_RATE_LIMITING=false` in tests** — Existing default; new tests inherit. Breaker tests must NOT conflate API rate limiting with the CRAWL-04 breaker (they are unrelated subsystems).
5. **`TESTING=true` and `ENABLE_RATE_LIMITING=false` set BEFORE `from app.main import app`** — `conftest.py` sets these; new test files must not break the order.
6. **`EndpointRegistry` pattern** — Not affected by Phase 3. QUAL-07 only changes endpoint function signatures (parameter removal), not registration.
7. **`BaseEndpointRouter` + `BaseCRUDService`** — Not affected by Phase 3.
8. **CORS config allows `chrome-extension://` + `null`** — Not affected.

---

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — versions verified on PyPI, pybreaker internals verified in source
- Architecture (auto-discovery, breaker registry, health check): **HIGH** — all three patterns match existing Python idioms; pybreaker source inspected
- Code-level locations + line numbers: **HIGH** — all paths grep-verified against 2026-04-22 codebase snapshot; three CONTEXT inaccuracies surfaced (DISC-01 through DISC-09)
- Pitfalls: **HIGH-MEDIUM** — 15 pitfalls documented with concrete reproduction signals; some (HC-01, HC-02) depend on operational behavior not observable in repo alone
- Assumptions: **LOW-risk** for all 13 assumptions — all verified or tracked with explicit mitigation

**Research date:** 2026-04-22
**Valid until:** 2026-05-22 (30 days — pybreaker is stable, Python 3.13 is stable; revisit if pybreaker 1.5 releases with breaking API changes)

---

## Plan Dependency Graph (advisory, for the planner)

Based on CONTEXT's internal ordering constraint (D-17) and the cross-dependency analysis above, 5 plans map cleanly:

```
Plan P1 — CRAWL-01/02/03: adapter auto-discovery + ADAPTER_NAME sweep
  • Adds ADAPTER_NAME to every subclass (108 files)
  • Adds IS_FALLBACK to base + GenericHtmlParser
  • Replaces ADAPTER_REGISTRY population with pkgutil scan
  • Adds test_adapter_discovery.py with count assertion (108)
  • Updates 5 characterization tests to key by ADAPTER_NAME (Phase 1 D-23 handoff)

Plan P2 — CRAWL-04 + CRAWL-05 + CRAWL-06: breaker + parallelization alignment + health check
  • Requires P1 landed (needs ADAPTER_NAME for breaker registry keying)
  • Adds pybreaker==1.4.1 to requirements.txt
  • Adds _BREAKERS registry + get_breaker() helper
  • Wraps adapter.fetcher.fetch() in breaker.call() with CircuitBreakerError catch
  • Adds breaker.open() on terminal 429/503
  • Deletes RATE_LIMIT_CIRCUIT_BREAKER_* counter block (D-07 "delete before add")
  • Adds HEALTH_PROBE_URL class attribute to base (default None — Option A)
  • Adds check_health() method + HealthResult dataclass
  • Renames/aligns CRAWLER_MAX_ADAPTER_WORKERS vs CRAWLER_MAX_WORKERS (DISC-03)
  • Adds test_circuit_breaker.py, test_runner_breaker.py, test_health_check.py

Plan P3 — CRAWL-07: parse-failure reporting
  • Requires P2 landed (needs parse_failures/sample_failure_urls accumulator)
  • Adds parse_failures + sample_failure_urls (first-5) + elapsed_seconds to result dict
  • Extends _render_crawler_result_html in email.py
  • Adds test case to test_email.py

Plan P4 — QUAL-01: car_generations lazy-load
  • INDEPENDENT — no dependency on P1-P3
  • Creates car_generations.py + JSON file + export script
  • Converts car_generations_data.py to thin shim (DISC-05)
  • Adds test_car_generations_loader.py
  • Measures uvicorn --reload latency (manual evidence in PR)

Plan P5 — QUAL-02 + QUAL-03 + QUAL-07: regression guards + logger migration
  • INDEPENDENT — no dependency on P1-P4
  • Adds test_pydantic_v1_regression.py, test_on_event_regression.py, test_logger_migration_regression.py
  • 68-site logger sweep across 10 files
  • Verifies OpenAPI snapshot unchanged post-sweep (SAFE-05 gate)
```

**Parallelization:** P4 and P5 are fully parallel with P1/P2/P3. The crawler chain (P1 → P2 → P3) is sequential. Five plans total; three parallel tracks possible.

---

*Phase 3 research gathered: 2026-04-22*
*Research by: gsd-researcher*
