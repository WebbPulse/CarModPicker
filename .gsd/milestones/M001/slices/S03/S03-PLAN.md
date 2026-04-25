# S03: Non-Breaking Internal Improvements

**Status:** ✅ completed 2026-04-22
**Goal:** Crawler subsystem hardened end-to-end (auto-discovery, circuit breaker, parallelization, pre-crawl health check, parse-failure reporting); startup latency reduced; Pydantic v1 anti-patterns eliminated — without touching any external API contract.
**Demo:** ADAPTER_REGISTRY auto-populated to 108 entries; pybreaker opens after 3 failures; uvicorn startup measurably faster; pytest run produces zero Pydantic v1 deprecation warnings.

## Must-Haves

- Adapter auto-discovery via `pkgutil.iter_modules` (108 adapters)
- pybreaker per-adapter (fail_max=3, reset_timeout=120) replacing custom counter
- Pre-crawl `robots.txt` health check (HEALTH_PROBE_URL opt-in)
- ThreadPoolExecutor parallelization with per-worker SessionLocal
- `car_generations_data.py` (8,412 LOC) → JSON + `@lru_cache`
- 68-site `Depends(get_logger)` → module-level logger sweep

## Tasks

> Detail preserved in `.planning/milestones/v1.0-phases/03-non-breaking-internal-improvements/` (5 PLAN/SUMMARY pairs: 03-01 through 03-05).

## Files Likely Touched

`backend/app/crawlers/adapters/__init__.py`, `backend/app/crawlers/runner.py`, `backend/app/core/car_generations*.py`
