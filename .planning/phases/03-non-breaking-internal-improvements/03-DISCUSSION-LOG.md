# Phase 3: Non-Breaking Internal Improvements - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 03-non-breaking-internal-improvements
**Areas discussed:** Auto-discovery mechanics (CRAWL-01/02/03), Breaker + parallelization runtime (CRAWL-04 + CRAWL-05), Health check + failure reporting (CRAWL-06 + CRAWL-07), Non-crawler cleanup scope (QUAL-01 + QUAL-07)

---

## Auto-discovery mechanics (CRAWL-01/02/03)

### Q1: Where should the 'expected baseline count' of discovered adapters live so CRAWL-02's count-assertion has something to compare against?

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-coded int in a pytest assertion | `assert len(ADAPTER_REGISTRY) == 111` in `test_adapter_discovery.py`. Bump the number in the same PR that adds/removes an adapter. Simplest; git diff surfaces every change. | ✓ |
| Committed manifest file (adapters.yml / adapters.txt) | List under version control; discovery asserts set-equality. Makes adds/removes explicit, but duplicative with the module tree. | |
| Dynamic from a sentinel env var | `EXPECTED_ADAPTER_COUNT=111` in CI env + pytest reads it. Keeps the number out of code; drift between env var and reality is easy to miss. | |

**User's choice:** Hard-coded int in a pytest assertion (Recommended)

### Q2: How should `ADAPTER_NAME: ClassVar[str]` be assigned on each `RetailerCrawlerAdapter` subclass?

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit, required per subclass | Each adapter declares `ADAPTER_NAME = 'briantooleyracing'`. Fails loudly if missing. Renames become grep-able; matches Phase 1 D-23. | ✓ |
| Auto-derived from class name | `BrianTooleyRacingAdapter` → `briantooleyracing`. Zero boilerplate; identity tied to a class name that may be renamed. | |
| Auto-derived from module path | `tier0_http.briantooleyracing` → `briantooleyracing`. Stable-ish; couples identity to directory layout. | |

**User's choice:** Explicit, required per subclass (Recommended)

### Q3: How should the `generic` fallback adapter (no `discover_product_urls()`) be handled by the auto-discovery scan?

| Option | Description | Selected |
|--------|-------------|----------|
| Exclude by ClassVar flag | `IS_FALLBACK: ClassVar[bool] = False` on base; `GenericHtmlParser` sets `True`; discovery skips `IS_FALLBACK=True`. Baseline = crawlable only. | ✓ |
| Exclude by module-path convention | Anything NOT under `tier0_http/`, `tier1_tls/`, or `tier2_browser/` is skipped. Less explicit; silent if a new tier dir is added. | |
| Include but flag as non-crawlable | In registry with `crawlable=False` marker. Runner rejects with clearer error. Extra complexity for one special case. | |

**User's choice:** Exclude by ClassVar flag (Recommended)

### Q4: How should adapter import failures fail CI?

| Option | Description | Selected |
|--------|-------------|----------|
| Discovery raises + pytest asserts it | Scan wraps each import in `try/except`, logs at ERROR; loader raises if any failure or count < expected. Single enforcement point. | ✓ |
| Silent skip + dedicated CI step | Discovery logs ERROR but does not raise at import time. `python -m app.crawlers.verify_adapters` in CI. Separates "broken adapter" from "can't boot". | |
| Hybrid — raise in test env, warn in prod | Use `TESTING=true` to decide. Pragmatic but creates behavioral drift between CI and production. | |

**User's choice:** Discovery raises + pytest asserts it (Recommended)

---

## Breaker + parallelization runtime (CRAWL-04 + CRAWL-05)

### Q1: Where should the `pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120)` instance live?

| Option | Description | Selected |
|--------|-------------|----------|
| Per-adapter-name, process-global registry | `dict[adapter_name, CircuitBreaker]` initialized once; workers share per adapter. pybreaker thread-safe internally. Matches REQ intent. | ✓ |
| Per-worker-thread, local instance | Each worker creates its own breaker. Simpler; effective `fail_max` becomes 3 × workers. Violates CRAWL-04. | |
| Per-adapter-class attribute | `CircuitBreaker` as `ClassVar` on each subclass. Works but couples infra state to adapters. | |

**User's choice:** Per-adapter-name, process-global registry (Recommended)

### Q2: How should the breaker interact with the existing `HttpFetcher.fetch()` retry loop in `base.py` (which retries 429/502/503/504 with Retry-After backoff)?

| Option | Description | Selected |
|--------|-------------|----------|
| Breaker wraps the runner's per-URL call, fetcher retries unchanged | `base.py` keeps its retry-with-backoff. Runner wraps `parse+fetch` in `breaker.call(...)`. Exhausted retry = 1 failure. Clean separation. | ✓ |
| Breaker replaces base.py retry entirely | Delete `RETRYABLE_STATUS_CODES`. Every 429/502/503/504 counts as breaker failure. Loses graceful Retry-After handling. | |
| Breaker only on 429/503, retries stay for 502/504 | Matches "immediate bail on 429/503" wording. Splits breaker concerns across two files. | |

**User's choice:** Breaker wraps the runner's per-URL call, fetcher retries unchanged (Recommended)

### Q3: The REQ says 429/503 triggers 'immediate bail'. How is 'immediate' implemented on top of pybreaker?

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-trip the breaker on first 429/503 | Normal errors count 1-of-3; 429/503 calls `breaker.open()` directly. One 429/503 opens breaker for 120s. Matches REQ intent. | ✓ |
| Exit the adapter loop without touching the breaker | 429/503 raises `AdapterBailException`; breaker unchanged. No 120s cooldown — next run could hammer the retailer. | |
| Use two breakers: fast (429/503, fail_max=1) + slow (other, fail_max=3) | Explicit two-tier semantics. Cleanest logically; doubles state surface. | |

**User's choice:** Pre-trip the breaker on first 429/503 (Recommended)

### Q4: ThreadPoolExecutor worker count — the formula gives `25 + 75 - 20 = 80`. How should the actual worker count be chosen at runtime?

| Option | Description | Selected |
|--------|-------------|----------|
| `min(formula, adapter_count)` with env override | `min(DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE, len(adapters))`. Env var `CRAWLER_MAX_WORKERS` overrides. Caps over-subscription. | ✓ |
| Exact formula value, no cap | Literal 80 regardless of adapter count. Simplest; over-subscribes for smaller adapter sets. | |
| Configurable in `config.py`, no env override | `CRAWLER_MAX_WORKERS = 80` constant. Requires a deploy to tune. | |

**User's choice:** `min(formula, adapter_count)` with env override (Recommended)

---

## Health check + failure reporting (CRAWL-06 + CRAWL-07)

### Q1: For CRAWL-06's pre-crawl health check, what URL should each adapter probe?

| Option | Description | Selected |
|--------|-------------|----------|
| `{base_url}/robots.txt` with per-adapter override | Default probe hits `robots.txt`. `HEALTH_PROBE_URL: ClassVar[str | None]` overrides; None = skip. | ✓ |
| `{base_url}/robots.txt` only, no override | Strict REQ literal. Adapters where robots.txt is blocked get skipped every run. | |
| Adapter root (`{base_url}/`) instead of robots.txt | Truer "is the site reachable" signal; departs from REQ language. | |

**User's choice:** `{base_url}/robots.txt` with per-adapter override (Recommended)

### Q2: What counts as 'unhealthy' and triggers skipping the adapter?

| Option | Description | Selected |
|--------|-------------|----------|
| 4xx or 5xx or timeout/network error, WARN log + metric | Matches REQ literal. Skipped with single `logger.warning` and `{skipped: true, reason: ...}` result row. | ✓ |
| Only 5xx + timeout skip; 4xx is warn-but-continue | 4xx on robots.txt can be benign. Softer but bot-flagged 403 usually cascades anyway. | |
| Any non-200 skips | Strictest. Redirects and 204 would both skip. Likely over-aggressive. | |

**User's choice:** 4xx or 5xx or timeout/network error, WARN log + metric (Recommended)

### Q3: CRAWL-07 parse-failure reporting — where does it go? (Phase 2 CloudWatch lands concurrently but can't be relied on.)

| Option | Description | Selected |
|--------|-------------|----------|
| Extend existing SES job report email | Add per-adapter section with `ParseFailures: {count}/{total}` + `SampleURLs`. Available today. | ✓ |
| Runner CLI stdout only | Print structured per-adapter failure summary at end of run. SES email is where the ops view already lives. | |
| Defer to Phase 2 CloudWatch metrics | Emit `ParseFailures` via OBS-02, rely on OBS-03 alarm. Waits on Phase 2 landing. Risky. | |

**User's choice:** Extend existing SES job report email (Recommended)

### Q4: How many failing URLs should be sampled per adapter in the report?

| Option | Description | Selected |
|--------|-------------|----------|
| Up to 5 URLs, first-N of failures | Small enough for email readability; large enough for pattern recognition. First 5 captures cascade start. | ✓ |
| Up to 3 URLs | REQ literal says "samples", no number. 3 is tersest. | |
| Up to 10 URLs, sampled across the run | Broader coverage; longer emails. | |

**User's choice:** Up to 5 URLs, first-N of failures (Recommended)

---

## Non-crawler cleanup scope (QUAL-01 + QUAL-07)

### Q1: Where should the extracted `car_generations_data.json` live?

| Option | Description | Selected |
|--------|-------------|----------|
| `backend/app/core/car_generations_data.json`, package-adjacent | Resolved via `importlib.resources.files('app.core').joinpath(...)`. Works dev + Docker; keeps data inside the package. | ✓ |
| `backend/data/car_generations.json`, top-level data dir | Easier to swap; needs Dockerfile COPY + path resolution helper. | |
| S3 with lazy download + local cache | Overkill for static reference data; deploy-time network dep. | |

**User's choice:** `backend/app/core/car_generations_data.json`, package-adjacent (Recommended)

### Q2: Lazy load via `@lru_cache(maxsize=1)` on first access, or eager load at lifespan startup?

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy via `@lru_cache(maxsize=1)` | REQ literal. `uvicorn --reload` startup unaffected. First request pays one-time load. | ✓ |
| Eager load at lifespan startup | First real request is fast. Reintroduces the startup latency QUAL-01 removes. | |
| Hybrid — lazy in dev, eager in prod via env flag | `CAR_DATA_EAGER=true` in App Runner. More config surface. | |

**User's choice:** Lazy via `@lru_cache(maxsize=1)` (Recommended)

### Q3: How should the existing 8,412-line Python literal be converted to JSON?

| Option | Description | Selected |
|--------|-------------|----------|
| One-shot conversion script committed alongside | `backend/scripts/export_car_generations.py`. Run once, commit JSON, delete old `.py`. Reproducible. | ✓ |
| Manual conversion (paste/edit) | Error-prone over 8K lines. | |
| Runtime conversion with fallback | Keeps 8K-line dead code; safer rollback. | |

**User's choice:** One-shot conversion script committed alongside (Recommended)

### Q4: QUAL-07 logger migration (65 call sites, 10 files). `auth.py` alone has 19 sites and gets split into `auth/` package in Phase 5. Scope for this phase?

| Option | Description | Selected |
|--------|-------------|----------|
| Sweep all 10 files now; Phase 5 carries the pattern forward | Mechanical migration. Phase 5 copies module-level pattern into each split file. Zero Phase-3 / Phase-5 coupling beyond convention. | ✓ |
| Skip auth.py now; do it inside Phase 5's split PR | 9 files / 46 sites in Phase 3. Less merge conflict risk; incomplete "zero Depends" claim. | |
| Skip auth.py AND users/votes/reports/bug_reports | 5 shared-utils files / ~16 sites. Most conservative; pushes work to Phase 5. | |

**User's choice:** Sweep all 10 files now; Phase 5 carries the pattern forward (Recommended)

---

## Claude's Discretion

No areas were explicitly deferred to Claude's judgment beyond minor implementation details captured in CONTEXT.md §"Claude's Discretion":
- Internal variable/function names for the discovery helper
- Exception type for discovery import-error failures
- JSON key-ordering convention
- Sample-URL truncation rule for long URLs in the email
- Whether QUAL-02/03 grep test is Python `re` or shell `grep`
- Test-module organization for the regression guards

## Deferred Ideas

- Remove `get_logger` export entirely (late Phase 5 / early Phase 6)
- Retroactive rename of all 111 adapter test modules to use `ADAPTER_NAME`
- `discover_product_urls()` characterization (still deferred from Phase 1)
- Async rewrite of the crawler runner
- Observability instrumentation of the breaker itself (Phase 2)
- S3 lifecycle policy QUAL-08 (different phase)
- Deeper Pydantic v2 feature-leverage audit
- Rollback plan if pybreaker introduces flakiness (mitigated by surgical wrap-and-revert shape)
