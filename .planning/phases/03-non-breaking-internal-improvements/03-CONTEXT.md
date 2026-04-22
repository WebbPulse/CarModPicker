# Phase 3: Non-Breaking Internal Improvements - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Harden the crawler subsystem end-to-end — adapter auto-discovery + validation, `pybreaker`-based circuit breaker, bounded `ThreadPoolExecutor` parallelization, per-adapter pre-crawl health check, and parse-failure reporting in the job email — plus eliminate residual Pydantic v1 anti-patterns, `@app.on_event` decorators, and the `Depends(get_logger)` pattern. No external API contract changes; no URL/schema/model drift. May run concurrent with Phase 2 (Observability); must NOT depend on Phase 2 artifacts landing first.

Internal ordering (from ROADMAP): CRAWL-01/02/03 (auto-discovery + count-assert green) must complete before CRAWL-05 (parallelization) lands. CRAWL-04 (breaker) lands in the same PR as CRAWL-05 — the two share a shared-state contract (per-adapter-name breaker registry read by each worker thread).

</domain>

<decisions>
## Implementation Decisions

### Adapter auto-discovery (CRAWL-01, CRAWL-02, CRAWL-03)

- **D-01:** Replace the hand-maintained `ADAPTER_REGISTRY` dict in `backend/app/crawlers/adapters/__init__.py` with an `importlib` + `pkgutil.iter_modules` directory scan over `tier0_http/`, `tier1_tls/`, `tier2_browser/`. The scan populates `ADAPTER_REGISTRY` at module import time; the dict keys are each adapter's `ADAPTER_NAME`.
- **D-02:** Every `RetailerCrawlerAdapter` subclass MUST declare `ADAPTER_NAME: ClassVar[str]` explicitly (e.g., `ADAPTER_NAME = "briantooleyracing"`). Derivation from class name or module path is forbidden — renames must be deliberate, grep-able acts. The base class raises `TypeError` at `__init_subclass__` time if the attribute is missing or empty.
- **D-03:** Introduce `IS_FALLBACK: ClassVar[bool] = False` on `RetailerCrawlerAdapter` base. `GenericHtmlParser` (`adapters/generic.py`) sets `IS_FALLBACK = True`. The discovery scan skips every `IS_FALLBACK=True` adapter — the baseline-count assertion covers crawlable adapters only. Generic stays importable directly (for the URL-host fallback mapping in `adapters/__init__.py`) but is never in `ADAPTER_REGISTRY`.
- **D-04:** The expected baseline count lives as a hard-coded integer inside a new `backend/tests/crawlers/test_adapter_discovery.py`: `assert len(ADAPTER_REGISTRY) == 111`. Bumping the number is the PR that adds/removes an adapter — git diff surfaces every change. Current count = 111 (84 tier0 + 16 tier1 + 11 tier2, minus any non-adapter files in those tiers; planner verifies exact number against current tree).
- **D-05:** Import failures during the scan are caught per-module, logged at `ERROR` with the full traceback (`logger.error("failed to import adapter %s: %s", modname, exc, exc_info=True)`), collected in an `_IMPORT_ERRORS: list[tuple[str, BaseException]]` module-level attribute, and the loader raises `RuntimeError` if the list is non-empty OR if `len(ADAPTER_REGISTRY) < expected`. The new pytest both imports the registry (triggering discovery) AND asserts `_IMPORT_ERRORS == []` — a single enforcement point for both local `pytest` and CI.
- **D-06:** The new test module imports `app.crawlers.adapters` directly and asserts: (a) count equals the hardcoded baseline, (b) `_IMPORT_ERRORS` is empty, (c) every adapter in `ADAPTER_REGISTRY` has a non-empty `ADAPTER_NAME`, (d) no two adapters share an `ADAPTER_NAME`. Fail mode: pytest exits non-zero → existing `backend-ci.yml` already fails CI.

### Circuit breaker via pybreaker (CRAWL-04)

- **D-07:** Add `pybreaker` to `backend/requirements.txt`. Replace the custom `RATE_LIMIT_CIRCUIT_BREAKER_*` counter block in `backend/app/crawlers/runner.py:64-71, 444-596` entirely — delete `consecutive_rate_limited`, `rate_limit_bailout`, `rate_limit_bailout_after`, `RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD`, `RATE_LIMIT_CIRCUIT_BREAKER_STATUSES` as part of the same PR that introduces pybreaker.
- **D-08:** Breaker scope: **per-adapter-name, process-global registry**. A module-level `_BREAKERS: dict[str, pybreaker.CircuitBreaker] = {}` keyed by `adapter_name`, initialized on first access via a helper `get_breaker(adapter_name) -> pybreaker.CircuitBreaker`. All ThreadPoolExecutor workers for the same adapter share the same breaker instance. `pybreaker.CircuitBreaker` is thread-safe internally (`RLock` under the hood).
- **D-09:** Breaker configuration: `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)`. REQ literal.
- **D-10:** Breaker scoping at call sites: the **runner wraps the per-URL `parse+fetch` call** in `breaker.call(...)`; the existing `HttpFetcher.fetch()` retry-with-backoff loop in `backend/app/crawlers/base.py:548-601` is **unchanged**. Rationale: fetcher-layer retries absorb transient 429/502/503/504 blips (Retry-After + exponential backoff); only a fully-exhausted fetch surface counts as one failure towards `fail_max=3`. Preserves transient-vs-systemic separation.
- **D-11:** 429/503 "immediate bail" semantics: when the fetcher surfaces a final 429 or 503 (after its retry budget is spent), the runner calls `breaker.open()` directly (or raises a sentinel `ImmediateBailError` configured in pybreaker's `exclude` / `listeners` to pre-trip). Effect: one terminal 429/503 opens the breaker for 120s; ordinary network errors still need 3 consecutive to trip. Matches REQ intent precisely.
- **D-12:** When a breaker is open, `breaker.call(...)` raises `pybreaker.CircuitBreakerError`. The runner catches it, terminates the per-adapter URL loop, records `{rate_limit_bailout: true, rate_limit_bailout_after: i}` in the adapter's result dict (keeping the existing report schema), and moves to the next adapter. Job report email surfaces breaker-bailed adapters as a distinct failure class.

### Per-adapter parallelization (CRAWL-05)

- **D-13:** Replace the currently-serial per-adapter loop in `backend/app/crawlers/runner.py` with a bounded `concurrent.futures.ThreadPoolExecutor`. Each submitted future is `run_crawler(adapter_name)` for one adapter. Executor context enters the crawler entrypoint; submit futures for all enabled adapters; collect results via `as_completed`.
- **D-14:** Worker count = `min(DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE, len(ADAPTER_REGISTRY))` = `min(80, 111) = 80` today, with env-var override `CRAWLER_MAX_WORKERS` (int) that takes precedence when set. Caps accidental over-subscription if `ADAPTER_REGISTRY` ever shrinks; supports prod tuning / local dev without code edits.
- **D-15:** Each worker thread creates its OWN `SessionLocal()` at the start of its `run_crawler` call and closes it in a `finally` block. No session leakage across adapters. The existing `SessionLocal` pattern in `backend/app/db/session.py` is already configured for this pool size (D-14 formula derives from the existing constants at lines 27-29).
- **D-16:** Per-URL `time.sleep(actual_delay)` (currently `backend/app/crawlers/runner.py:463`) is **preserved inside each worker**. Per-adapter politeness throttling continues to matter under parallelization — workers for DIFFERENT adapters run in parallel, but URLs within one adapter remain serially throttled.
- **D-17:** Internal phase ordering: CRAWL-01/02/03 plans land and count-assert green BEFORE the CRAWL-04/05 plan. Plan-level `depends_on` enforces this in the execute wave graph.

### Pre-crawl health check (CRAWL-06)

- **D-18:** Default probe URL: `{base_url}/robots.txt` with 5s timeout. Adapters override via `HEALTH_PROBE_URL: ClassVar[str | None]` on the subclass. `None` = skip the health check for that adapter (used for anti-bot tier2 retailers where probing `robots.txt` triggers the very block we'd be trying to detect). The base class default is the empty string, meaning "derive `{base_url}/robots.txt` from `BASE_URL` class attribute".
- **D-19:** Probe implementation lives on `RetailerCrawlerAdapter` as `check_health(self) -> HealthResult` where `HealthResult` is a simple `@dataclass(frozen=True)` with `healthy: bool`, `reason: str`, `status_code: int | None`. Uses the adapter's own fetcher (so tier-specific transport rules apply) with a 5s timeout override.
- **D-20:** "Unhealthy" = any 4xx, 5xx, timeout, or connection error. Runner logs `logger.warning("skipping %s: health=%s status=%s", adapter_name, reason, status_code)` and adds `{skipped: true, skip_reason: "health_<reason>"}` to the adapter's result dict (visible in the job report). 200-299 passes; 3xx redirects are followed by the fetcher and pass if the final response is 2xx.
- **D-21:** The breaker-bail result row (D-12) and the health-skip result row (D-20) are distinct `skip_reason` values; the job report surfaces each as its own section so ops can distinguish "site down" from "site shedding load".

### Parse-failure reporting (CRAWL-07)

- **D-22:** Extend the existing crawler job report email (produced after a crawler run, sent via SES). Add a per-adapter block:
  ```
  Adapter: {adapter_name}
    Ingested: {N}
    ParseFailures: {K} / {total_urls} ({pct}%)
    Elapsed: {seconds}s
    SampleFailures:
      - {url_1}
      - {url_2}
      - ... up to 5 URLs (first-N of encountered failures)
  ```
- **D-23:** Sample URLs are the FIRST 5 failures encountered in the run (not evenly sampled). Rationale: the start of a failure cascade usually exposes the root cause; later failures repeat it. Sample collection lives in the per-worker result accumulator; the runner merges per-adapter accumulators into the final job-report payload.
- **D-24:** Phase 3 does NOT depend on Phase 2 CloudWatch metrics (OBS-02) landing. The same failure-counting infrastructure introduced here (per-adapter result dict with `parse_failures`, `sample_failure_urls`) can be wired into OBS-02 by Phase 2 without schema change — Phase 2 reads the existing result dict and emits CloudWatch from it.

### QUAL-01: car_generations data loader

- **D-25:** Extract the 8,412-line Python literal in `backend/app/core/car_generations_data.py` to `backend/app/core/car_generations_data.json` (package-adjacent). Resolve the path at runtime via `importlib.resources.files("app.core").joinpath("car_generations_data.json")` — works in dev, in tests, and inside the App Runner container image.
- **D-26:** Loader API: a new `backend/app/core/car_generations.py` module with `@functools.lru_cache(maxsize=1)` on the load function. Signature: `load_car_generations() -> dict`. Lazy: the JSON is read + parsed on first call, cached for all subsequent calls. `uvicorn --reload` startup does NOT trigger the load — the first request that touches car-data endpoints pays the one-time cost (~hundreds of ms), everything after is memoized.
- **D-27:** Conversion method: a one-shot script `backend/scripts/export_car_generations.py` that imports the old `car_generations_data.py` module, calls `json.dump(sort_keys=True, indent=2)`, writes to the target path. The script stays in the repo so data regeneration is reproducible. Run once in the same PR as the loader landing; commit the JSON; delete `car_generations_data.py` (replace with a stub that raises `ImportError` with a pointer to the new module, so any stale imports surface loudly instead of silently).
- **D-28:** Acceptance evidence for "measurably reduced startup latency": plan includes a before/after measurement. Methodology: `time uvicorn app.main:app --reload` (from cold boot; Ctrl+C at first "Application startup complete"), three runs each, record median. Capture numbers in the PR description. No CI gate — one-time measurement sufficient.
- **D-29:** Public API shape of `load_car_generations()` matches the existing dict structure returned by `backend/app/core/car_generations_data.py` (whatever top-level name it exports). Callers keep working without change. JSON is flat/nested exactly as the Python literal is today — no schema redesign in this phase.

### QUAL-02, QUAL-03: Pydantic v1 / on_event regression guards

- **D-30:** Current codebase scout confirmed 0 hits for `@validator`, `@root_validator`, `class Config:`, `.dict()`, `.parse_obj(`, and `@app.on_event` inside `backend/app/`. QUAL-02 and QUAL-03 are **verify-and-lock** rather than active migrations.
- **D-31:** Add regression tests that run in CI and fail on reintroduction:
  - QUAL-02: a pytest in `backend/tests/test_pydantic_v1_regression.py` that uses `warnings.filterwarnings("error", category=pydantic.PydanticDeprecatedSince20)` and runs a sample schema round-trip (load + dump on one representative Pydantic v2 schema from `app.api.schemas`). Also a grep-based test that scans `backend/app/**/*.py` for forbidden patterns (`@validator\b`, `@root_validator\b`, `class Config:\s*$`, `\.parse_obj(`, `\.dict\(\)` — with allow-listed false-positives for unrelated `.dict()` on non-Pydantic objects).
  - QUAL-03: a grep-based test that scans `backend/app/**/*.py` for `@app\.on_event\(` and asserts zero matches.
- **D-32:** If the one-time `pytest -W error::pydantic.PydanticDeprecatedSince20` run surfaces any v1 warnings that the grep missed (rare, but possible for programmatic v1 API use), fix them in-phase before marking QUAL-02 complete.

### QUAL-07: logger migration sweep

- **D-33:** Scope: migrate ALL 10 files containing `logger: logging.Logger = Depends(get_logger)` in one atomic Phase 3 sweep. File list (65 total sites):
  - `backend/app/api/endpoints/auth.py` (19 sites)
  - `backend/app/api/endpoints/users.py`
  - `backend/app/api/endpoints/votes.py`
  - `backend/app/api/endpoints/reports.py`
  - `backend/app/api/endpoints/bug_reports.py`
  - `backend/app/api/utils/base_endpoint_router.py`
  - `backend/app/api/utils/base_vote_router.py`
  - `backend/app/api/utils/base_report_router.py`
  - `backend/app/api/utils/common_patterns.py`
  - `backend/app/api/utils/admin_endpoint_patterns.py`
- **D-34:** Migration pattern (mechanical, apply identically everywhere):
  1. Add at module top after imports: `logger = logging.getLogger(__name__)`
  2. Delete `from app.core.logging import get_logger` import
  3. Delete `logger: logging.Logger = Depends(get_logger),` parameter from every function signature
  4. All existing `logger.info(...)` / `logger.warning(...)` / etc. inside each function now resolve to the module-level `logger` with identical behavior
- **D-35:** Phase 5 (auth.py split) inherits this convention: each new `auth/` package module (`core.py`, `two_factor.py`, `webauthn.py`, `oauth.py`, `_helpers.py`) gets its own module-level `logger = logging.getLogger(__name__)`. Phase 3's sweep means Phase 5 has a clean pattern to copy instead of a mixed regime. No Phase-3 / Phase-5 coupling beyond the convention.
- **D-36:** Consider keeping `backend/app/core/logging.py::get_logger` export available (not removed) until after Phase 5 completes — Phase 3 acceptance is "zero Depends(get_logger) call sites in app code". Removing `get_logger` entirely is a trailing-cleanup item for late Phase 5 / early Phase 6. If nothing else imports it after Phase 3's sweep, Phase 3 may remove the export and its test file — plan step verifies via grep.
- **D-37:** Acceptance evidence: `grep -rn "Depends(get_logger)" backend/app/` returns zero matches after the sweep PR; CI coverage stays ≥ baseline set in Phase 1.

### Phase 2 decoupling

- **D-38:** Every Phase 3 deliverable must land without Phase 2 artifacts (Sentry SDK init, CloudWatch namespace, OBS-03 alarm). The CRAWL-07 job-report email uses existing SES infrastructure; per-adapter failure counts live in the runner's result dict (already consumed by the email). Phase 2 can read the same dict later to emit CloudWatch metrics, with zero schema change required by Phase 3.

### Claude's Discretion

- Exact variable/function names inside `adapters/__init__.py` discovery helpers (`_IMPORT_ERRORS`, `_discover_adapters`, etc.)
- Whether the discovery scan's error path uses `RuntimeError` specifically or a more-specific custom exception
- JSON indentation / key-ordering convention for the committed `car_generations_data.json` (sort_keys preferred for deterministic diffs, but Claude may choose differently if one of the consuming endpoints depends on insertion order — unlikely but verify)
- Sample-URL truncation rule when a URL is >100 chars in the job-report email
- Whether the QUAL-02/03 grep test uses Python `re` module inside pytest or a shell `grep | test $? -ne 0` CI step (both satisfy "fails on reintroduction")
- Whether to bundle the grep test into existing `test_openapi_snapshot.py`-style guard tests or create new dedicated test modules

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone-level framing
- `.planning/PROJECT.md` — Vision, Active requirements list (crawler system hardening + code-quality sweep are explicit milestone items), Out of Scope
- `.planning/REQUIREMENTS.md` §"Crawler System Hardening" (CRAWL-01 through CRAWL-07) and §"General Code Quality & Stack Upgrades" (QUAL-01, QUAL-02, QUAL-03, QUAL-07) — precise acceptance criteria with literal values
- `.planning/ROADMAP.md` §"Phase 3: Non-Breaking Internal Improvements" — Goal, Depends on (Phase 1), Success Criteria (5 TRUE conditions), Note on internal ordering (CRAWL-01/02/03 before CRAWL-05) and concurrency with Phase 2
- `.planning/STATE.md` — Current progress / Phase 1 completion status

### Phase 1 decisions that carry forward
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §D-20 to §D-23 — Crawler adapter characterization tests (5 adapters: briantooleyracing, amsperformance, texasspeed, cobbtuning, subispeed) pin `parse_product_page()` output. D-23 explicitly defers "switch tests to key adapters by `ADAPTER_NAME`" until this phase lands — that switch is a Phase 3 deliverable.
- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` §"Deferred Ideas" — "Crawler `discover_product_urls()` characterization" was deferred to Phase 3; revisit whether the auto-discovery + count-assertion work makes URL-filter characterization valuable here or whether it remains deferred.
- `.planning/phases/01-safety-nets-ci-hardening/01-VERIFICATION.md` — Any outstanding verification gaps the planner should avoid regressing

### Codebase context
- `.planning/codebase/STRUCTURE.md` — Crawler package layout (`backend/app/crawlers/`, `adapters/{tier0_http,tier1_tls,tier2_browser}`)
- `.planning/codebase/CONCERNS.md` — Known adapter + Pydantic-pattern debt items (inform what "clean" looks like after the sweep)
- `.planning/codebase/CONVENTIONS.md` — pytest-xdist (`-n auto`), `ENABLE_RATE_LIMITING=false` in tests, Alembic autogenerate-only

### Files directly touched (expected)
- `backend/app/crawlers/adapters/__init__.py` — Replace hand-maintained registry with auto-discovery scan (CRAWL-01/02/03)
- `backend/app/crawlers/adapters/base.py` — Add `ADAPTER_NAME`, `IS_FALLBACK`, `HEALTH_PROBE_URL`, `check_health()` to `RetailerCrawlerAdapter` base
- `backend/app/crawlers/adapters/generic.py` — Set `IS_FALLBACK = True`
- `backend/app/crawlers/adapters/**/*.py` (111 adapter files) — Add explicit `ADAPTER_NAME` per subclass (D-02)
- `backend/app/crawlers/runner.py` — Delete custom circuit-breaker counter block; wire pybreaker; add `ThreadPoolExecutor`; wire health check + failure-sample accumulator
- `backend/app/crawlers/base.py` — Unchanged retry logic (D-10); minor additions if `check_health()` needs fetcher-layer support
- `backend/app/core/car_generations.py` — NEW module with `@lru_cache` loader (QUAL-01)
- `backend/app/core/car_generations_data.json` — NEW file, output of conversion script
- `backend/app/core/car_generations_data.py` — Replaced with stub that raises `ImportError` with migration pointer
- `backend/scripts/export_car_generations.py` — NEW conversion script
- `backend/app/api/endpoints/{auth,users,votes,reports,bug_reports}.py` — Module-level `logger = logging.getLogger(__name__)`, remove `Depends(get_logger)` params (QUAL-07)
- `backend/app/api/utils/{base_endpoint_router,base_vote_router,base_report_router,common_patterns,admin_endpoint_patterns}.py` — Same QUAL-07 sweep
- `backend/tests/crawlers/test_adapter_discovery.py` — NEW (count assertion + import-errors assertion)
- `backend/tests/test_pydantic_v1_regression.py` — NEW (QUAL-02 guard)
- `backend/tests/test_on_event_regression.py` — NEW (QUAL-03 guard, may merge with above)
- `backend/requirements.txt` — Add `pybreaker`

### No external ADRs required
Requirements are fully captured in REQUIREMENTS.md + the decisions above. No external design docs or specifications referenced.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`backend/app/crawlers/runner.py:64-71, 444-596`** — Existing custom circuit-breaker counter block (`RATE_LIMIT_CIRCUIT_BREAKER_STATUSES`, `consecutive_rate_limited`, `rate_limit_bailout`). This is the code to DELETE when wiring pybreaker — new breaker integrates at roughly the same call sites around the per-URL fetch.
- **`backend/app/crawlers/base.py:339-601`** — Existing `RETRYABLE_STATUS_CODES = (429, 502, 503, 504)` retry loop with `_rate_limit_backoff_sec()` honoring Retry-After. **Preserved unchanged** (D-10). The breaker sits atop this, not in place of it.
- **`backend/app/db/session.py:22-36`** — `DB_POOL_SIZE=25`, `DB_MAX_OVERFLOW=75`, `API_CONNECTION_RESERVE=20` constants. D-14 worker formula pulls directly from these — if they ever change, the worker count auto-adjusts.
- **`backend/app/main.py:70` + `:117`** — `lifespan` async context manager already replaces all `@app.on_event` uses. QUAL-03 is a regression-guard test rather than active migration.
- **`backend/app/core/logging.py:71`** — `get_logger()` function that feeds the `Depends(get_logger)` pattern. Kept exported through Phase 3 to avoid churning callers outside the sweep; removal decision defers to late Phase 5 / early Phase 6 (D-36).
- **`backend/app/crawlers/adapters/__init__.py`** — Current hand-maintained `ADAPTER_REGISTRY` dict at line 134. The auto-discovery scan replaces this dict's population but keeps the same public name so callers at lines 615-617 (`run_crawler` CLI path) work unchanged.
- **`backend/tests/crawlers/fixtures/`** — Phase 1 committed adapter fixtures for the 5 characterization-tested adapters. D-23 from Phase 1 said tests will key by `ADAPTER_NAME` once it lands — Phase 3 plan must update those tests in the same PR that introduces `ADAPTER_NAME`.

### Established Patterns
- **`importlib.resources.files()`** — Safest way to load package-adjacent static resources (JSON) in both dev and Docker image. Prefer over `os.path.join(os.path.dirname(__file__), ...)` which breaks inside zipapps / some deploy envs.
- **`pytest -n auto --dist=loadfile`** from `pytest.ini` — New tests (discovery, regression guards) must be worker-safe. The discovery tests are pure-import/grep assertions — inherently safe. The parallelization tests (if any) must mock `ThreadPoolExecutor` or run serially via `@pytest.mark.serial` if one exists.
- **`EndpointRegistry` router registration at `backend/app/main.py`** — QUAL-07 does not touch router registration; only endpoint-function signatures and the module-top logger declarations.
- **Alembic autogenerate-only rule** (CLAUDE.md) — Not triggered by Phase 3 (no schema changes expected). If a plan surfaces a schema change, re-examine the phase boundary.

### Integration Points
- **Phase 1 Characterization Tests** — `backend/tests/crawlers/test_characterization_*_adapter.py` pin `parse_product_page()` output for 5 adapters. Every Phase 3 change (auto-discovery, breaker, parallelization, health check) MUST keep these tests green. They are the regression guard for "no external contract changes".
- **Phase 1 OpenAPI snapshot** — `backend/tests/fixtures/openapi_snapshot.json` pins the API schema. Phase 3 adds no endpoints, but the QUAL-07 signature changes (removing the `logger` parameter from endpoint functions) could affect the OpenAPI spec if FastAPI surfaces `Depends()` parameters in the schema. Verify: run `python -c "import json; from app.main import app; print(json.dumps(app.openapi(), sort_keys=True))"` before and after the sweep; if it changes, the changed snapshot is committed with the sweep PR (legitimate drift).
- **Phase 1 Migration DROP-guard + naming_convention** — Phase 3 writes no migrations; DROP-guard is not exercised. No coupling.
- **Existing SES job-report email** — Current destination for crawler run summaries. CRAWL-07 extends its body; does not change send-side infra. Template owners / deliverability unchanged.
- **`SessionLocal()` per worker** (D-15) — Pool is already sized for parallel workers (D-14 formula). No config change; just exercise the existing headroom.

</code_context>

<specifics>
## Specific Ideas

- **"Delete before add"** — When replacing the custom breaker counter with pybreaker, delete the old block FIRST in the same PR (D-07). Prevents lingering dead-state variables and ensures test coverage shifts cleanly.
- **"Hard-coded count + git diff = the audit trail"** — D-04 deliberately rejects dynamic baselines. The PR diff IS the proof that a new adapter was intentional.
- **"Retailer politeness is per-adapter, not per-worker"** — D-16: parallelization is across adapters; URLs within an adapter stay serially throttled. Prevents getting a whole retailer to ban the crawler IP.
- **"Phase 5 inherits the pattern, not a migration"** — D-35: after Phase 3's sweep, Phase 5's auth.py split copies a clean module-level logger convention into each new file. No Phase-3 / Phase-5 ordering coupling beyond the convention existing when Phase 5 starts.
- **"Phase 2 reads Phase 3's result dict"** — D-24/D-38: the per-adapter `parse_failures` / `sample_failure_urls` keys Phase 3 adds to the runner's result dict are exactly what Phase 2's CloudWatch emission consumes. Schema-compatible; no Phase-3 dependency on Phase 2 artifacts.
- **"Verify-and-lock, not migrate"** — D-30 to D-32: QUAL-02 and QUAL-03 are currently clean. The Phase 3 value-add is regression tests that fail CI if anyone reintroduces the patterns.

</specifics>

<deferred>
## Deferred Ideas

- **Remove `get_logger` export entirely** — D-36 defers this to late Phase 5 / early Phase 6 after `auth.py` splits and any remaining callers disappear.
- **Retroactive rename of historic adapter test modules to use `ADAPTER_NAME`** — Phase 3 updates the 5 characterization tests (D-23 from Phase 1). A sweep across all 111 adapter-specific tests in `backend/tests/crawlers/` to key everything by `ADAPTER_NAME` is a future tech-debt task, not Phase 3 scope.
- **Crawler `discover_product_urls()` characterization** (deferred from Phase 1) — Still not in Phase 3 scope. The regex-based sitemap filters remain fragile per CONCERNS.md; revisit as a standalone tech-debt task after auto-discovery stabilizes in production.
- **Async rewrite of the crawler runner** — `ThreadPoolExecutor` is chosen (D-13) because it minimizes surface change and pybreaker is thread-compatible. An `asyncio`-based runner would be a larger rewrite; out of scope here.
- **Observability instrumentation of the breaker itself** — pybreaker supports listeners (`on_state_change`, etc.). Wiring those into Sentry / CloudWatch belongs in Phase 2, not Phase 3.
- **S3 lifecycle policy (QUAL-08)** — In REQUIREMENTS.md but not in Phase 3's `Requirements:` list. Belongs to a later phase (infrastructure cleanup) per the traceability table.
- **Pydantic v2 schema audit** — D-30 confirmed no v1 anti-patterns remain. A deeper audit of whether existing v2 schemas fully leverage v2 features (e.g., computed fields, model validators) is a future quality-polish task, not regression-guard scope.
- **Rollback plan if pybreaker introduces flakiness** — Worth thinking about but not captured as a Phase 3 deliverable. Mitigation: the breaker-wrap in D-10 means reverting pybreaker is a delete-the-wrapper-restore-the-counter surgical revert, not a rewrite.

</deferred>

---

*Phase: 03-non-breaking-internal-improvements*
*Context gathered: 2026-04-22*
