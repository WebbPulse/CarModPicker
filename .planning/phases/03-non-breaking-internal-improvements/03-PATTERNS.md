# Phase 3: Non-Breaking Internal Improvements - Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 22 file groups (12 modified individual files + 108-adapter sweep + 11 new tests + 3 new support files)
**Analogs found:** 22 / 22 strong matches in-repo

---

## Executive Summary for the Planner

**CRITICAL scope-shapers:**

1. **CRITICAL (CR-1) — 108-adapter `ADAPTER_NAME` sweep is mechanical but volumetric.** Every `class *Adapter(RetailerCrawlerAdapter)` across `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/` must gain one line: `ADAPTER_NAME: ClassVar[str] = "<slug>"`. The slugs already exist verbatim as keys in the current `ADAPTER_REGISTRY` dict at `backend/app/crawlers/adapters/__init__.py:134-248` — the executor should **programmatically map existing registry keys → class files and batch-insert** rather than planning one task per adapter. Recommended: a single plan task "add ADAPTER_NAME to all 108 concrete adapters via a one-shot helper script (committed as a tool in `scripts/`), then grep-verify all 108 are present". Do NOT plan 108 separate tasks.

2. **CRITICAL (CR-2) — baseline count is 108, not 111.** Research §DISC-01 confirmed: `ls tier0_http | grep -v __init__ | wc -l` = 83; tier1 = 15; tier2 = 10 → 108. The CONTEXT's 111 is drift from an older snapshot. Test assertion must use `assert len(ADAPTER_REGISTRY) == 108`.

3. **CRITICAL (CR-3) — `ThreadPoolExecutor` already exists** at `runner.py:767-784` with `_compute_adapter_workers` at `runner.py:657-684`. The env var is already `CRAWLER_MAX_ADAPTER_WORKERS` (runner.py:675), not `CRAWLER_MAX_WORKERS` as CONTEXT D-14 states. Plan CRAWL-05 is narrow: wire the pybreaker registry INTO the existing executor; add test coverage; do NOT re-introduce the executor.

4. **CRITICAL (CR-4) — `car_generations_data.py` must become a thin shim, not a raising stub.** Research §DISC-05: `slugify()` is used by Alembic migration `30e2e2139a2e`, `models/car_generation.py:11`, `models/car_model.py:16`, `tests/test_init_cars_display_name.py:17`. A stub raising `ImportError` breaks the migration. Keep lines 1-54 (imports, `slugify`, `CarGenerationData` TypedDict, `CarModelData` TypedDict) as-is; replace the 8,316-line `CAR_GENERATIONS = {...}` literal (lines 58-8372) with `CAR_GENERATIONS = load_car_generations()`; keep `get_all_car_generations()` logic (lines 8374-8412) delegating to the new loader's dict shape.

5. **No `__init_subclass__` exists today** — grep of `backend/app/` returned zero hits. This is genuinely new mechanics for the codebase; the executor should follow the RESEARCH §Pattern 1 excerpt exactly (no existing codebase analog to copy).

6. **No `importlib.resources` use exists today** — grep returned zero hits. QUAL-01 is also new mechanics; follow RESEARCH §Pattern 5. The only existing `@lru_cache` pattern is `backend/app/core/config.py:361` (`get_settings`), which is the closest in-repo analog.

---

## File Classification

| Touched File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/crawlers/adapters/__init__.py` | registry/discovery | event-driven (import-time) | Current self at lines 134-248 (dict-populate pattern) + RESEARCH §Pattern 1 | self-reference + library pattern |
| `backend/app/crawlers/adapters/base.py` | base-class / contract | pure in-process | Current self (63 lines) | exact self-reference; extends |
| `backend/app/crawlers/adapters/generic.py` | fallback adapter | request-response | Current self lines 1-34 | exact self-reference; one-line add |
| `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/*.py` (108 files) | adapter subclass | request-response | `briantooleyracing.py:291-303` and `cobbtuning.py:316-339` | exact — identical `class X(RetailerCrawlerAdapter):` + `FETCHER_TIER` idiom |
| `backend/app/crawlers/runner.py` | worker orchestrator | event-driven + pub-sub (ThreadPoolExecutor) | Current self lines 64-71, 444-582, 767-784 | self-reference; multiple edit zones |
| `backend/app/crawlers/base.py` | transport | request-response | Unchanged per D-10 | N/A — preserved |
| `backend/app/core/car_generations.py` (NEW) | data loader | file-I/O → in-memory | `backend/app/core/config.py:361-371` (`@lru_cache` idiom) | role-match: memoized single-load |
| `backend/app/core/car_generations_data.json` (NEW) | data asset | static | N/A — new resource | no analog (new file type in project) |
| `backend/app/core/car_generations_data.py` | thin shim | re-export | Current self lines 13-54 (keep) + `api/schemas/__init__.py` style re-export | self-reference (90% deleted, 10% preserved) |
| `backend/scripts/export_car_generations.py` (NEW) | one-shot ETL | file-I/O | `backend/scripts/flatten_migrations.py` + `backend/scripts/check_migrations.py` | role-match: batch-ETL one-shot script |
| `backend/app/api/endpoints/auth.py` | controller/route | request-response | Current self lines 80-92 (Depends(get_logger) shape) + `runner.py:55` (module-level logger) | self-reference + in-repo pattern |
| `backend/app/api/endpoints/{users,votes,reports,bug_reports}.py` | controller/route | request-response | Same as auth.py | same |
| `backend/app/api/utils/base_endpoint_router.py` | router factory | request-response | Current self lines 1-17, 85-100 | self-reference |
| `backend/app/api/utils/{base_vote_router,base_report_router,common_patterns,admin_endpoint_patterns}.py` | router factory / shared | request-response | Same as base_endpoint_router.py | same |
| `backend/requirements.txt` | dep manifest | build-time | Current self (add `pybreaker==1.4.1`) | self-reference |
| `backend/tests/crawlers/test_adapter_discovery.py` (NEW) | unit test | pure-import + assertions | `backend/tests/test_metadata_naming_convention.py` (SAFE-09 attribute-assertion pattern) | exact — both are "load-object-and-assert-attributes" guards |
| `backend/tests/crawlers/test_circuit_breaker.py` (NEW) | unit test | in-process | `backend/tests/crawlers/test_runner_circuit_breaker.py` (the one we are REPLACING) | exact — role, structure, fixtures |
| `backend/tests/crawlers/test_runner_breaker.py` (NEW) | integration test | in-process, stubbed | `backend/tests/crawlers/test_runner_circuit_breaker.py` | exact |
| `backend/tests/crawlers/test_compute_adapter_workers.py` (NEW) | unit test | pure-function | `backend/tests/test_metadata_naming_convention.py` (function-boundary assertions w/ monkeypatch env) | role-match |
| `backend/tests/crawlers/test_parallel_session_isolation.py` (NEW) | integration test | multi-thread | `backend/tests/crawlers/test_runner_circuit_breaker.py` (stubbed-executor pattern) | role-match |
| `backend/tests/crawlers/test_health_check.py` (NEW) | unit test | stubbed fetcher | `backend/tests/crawlers/test_characterization_briantooleyracing.py` (adapter-method-under-test idiom) | role-match |
| `backend/tests/crawlers/test_runner_result_dict.py` (NEW) | unit test | in-process stubbed | `backend/tests/crawlers/test_runner_circuit_breaker.py` (assert result dict keys) | exact |
| `backend/tests/test_car_generations_loader.py` (NEW) | unit test | file-I/O | `backend/tests/test_init_cars_display_name.py` (car-generations-data consumer test idiom) | role-match |
| `backend/tests/test_pydantic_v1_regression.py` (NEW) | CI guard grep test | filesystem walk | `backend/tests/test_openapi_snapshot.py` (SAFE-05 snapshot guard idiom) | role-match — CI fail-on-drift guard |
| `backend/tests/test_on_event_regression.py` (NEW, or merged) | CI guard grep test | filesystem walk | same | same |
| `backend/tests/test_logger_migration_regression.py` (NEW) | CI guard grep test | filesystem walk | same | same |
| `backend/tests/crawlers/test_characterization_{amsperformance,briantooleyracing,cobbtuning,subispeed,texasspeed}.py` (MODIFY) | unit test | stubbed | Current self `test_characterization_briantooleyracing.py:19` (import by class) → switch to `ADAPTER_REGISTRY["briantooleyracing"]()` | self-reference; pattern from Phase 1 D-23 |

---

## Pattern Assignments

### 1. `backend/app/crawlers/adapters/base.py` (base-class / contract)

**Role:** new ClassVars + `__init_subclass__` enforcement + `check_health()` method on the existing 63-line base class.

**Analog:** self — current file at lines 1-63. Adds NEW mechanics not present anywhere else in the repo (grep confirmed no `__init_subclass__`, no `importlib.resources`).

**Existing pattern to extend** (lines 24-48):
```python
class RetailerCrawlerAdapter(ABC):
    """Per-retailer adapter: discover product URLs and parse a product page into ScrapedPayload."""

    #: Which fetcher tier to use. Default is plain-HTTP; override on subclasses
    #: that need TLS impersonation or a headless browser.
    FETCHER_TIER: ClassVar[FetcherTier] = "http"

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        self._fetcher: Optional[Fetcher] = fetcher
```

**New additions (fresh mechanics — no in-repo analog to copy; follow RESEARCH §Pattern 1 exactly):**
- Add `ADAPTER_NAME: ClassVar[str] = ""`
- Add `IS_FALLBACK: ClassVar[bool] = False`
- Add `HEALTH_PROBE_URL: ClassVar[str | None] = None` (per DISC-04 Option A — opt-in default)
- Add `__init_subclass__(cls, **kwargs)` that raises `TypeError` when `ADAPTER_NAME` missing/empty — BUT exempt `IS_FALLBACK=True` AND classes still having `__abstractmethods__` (Pitfall AD-01)
- Add `check_health(self) -> HealthResult` method (stub: returns `healthy=True, reason="skipped_by_config"` when `HEALTH_PROBE_URL is None`)
- Import `HealthResult` from a new `@dataclass(frozen=True)` in same module or co-located

**Adaptation notes:**
- Preserve existing `FETCHER_TIER` placement and docstring style.
- `__init_subclass__` MUST NOT raise at import time on `_IMPORT_ERRORS` accumulation path (Pitfall AD-03 recommends *collecting* errors in the registry, not raising); it only raises for ABSENT/EMPTY `ADAPTER_NAME` on non-fallback concrete classes.
- `HealthResult` fields: `healthy: bool`, `reason: str`, `status_code: int | None`.

---

### 2. `backend/app/crawlers/adapters/__init__.py` (discovery/registry)

**Role:** replace `from X import Y` × 108 lines + hand-maintained dict literal with `pkgutil.iter_modules` scan.

**Analog:** self — current file lines 134-248 is the dict shape that the new scan must recreate (same keys, same values). RESEARCH §Pattern 1 provides the new scan code.

**Preserve verbatim:**
- `adapter_name_for_product_url(url)` helper (lines 251-617+ — the URL→adapter mapping).
- Direct import of `GenericHtmlParser` (line 17) — used by the URL-host fallback mapping.
- `get_adapter(name)` helper (referenced by `runner.py:35`).

**Replace** (lines 19-131 of current `__init__.py`, the 113 `from X import Y` lines):
```python
# REMOVE: 113 explicit import lines
# ADD: pkgutil scan per RESEARCH §Pattern 1
import importlib
import pkgutil
from typing import Type

from app.crawlers.adapters.base import RetailerCrawlerAdapter

ADAPTER_REGISTRY: dict[str, Type[RetailerCrawlerAdapter]] = {}
_IMPORT_ERRORS: list[tuple[str, BaseException]] = []


def _discover_adapters() -> None:
    import app.crawlers.adapters.tier0_http as tier0
    import app.crawlers.adapters.tier1_tls as tier1
    import app.crawlers.adapters.tier2_browser as tier2
    for pkg in (tier0, tier1, tier2):
        for modinfo in pkgutil.iter_modules(pkg.__path__, prefix=f"{pkg.__name__}."):
            try:
                module = importlib.import_module(modinfo.name)
            except BaseException as exc:
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
                    name = attr.ADAPTER_NAME
                    if name in ADAPTER_REGISTRY:
                        _IMPORT_ERRORS.append((modinfo.name, ValueError(
                            f"duplicate ADAPTER_NAME {name!r}: "
                            f"{ADAPTER_REGISTRY[name].__module__} vs {attr.__module__}"
                        )))
                        continue
                    ADAPTER_REGISTRY[name] = attr


_discover_adapters()
```

**Adaptation notes:**
- Do NOT raise at import time on `_IMPORT_ERRORS != []` (Pitfall AD-03). Let `test_adapter_discovery.py` assert it.
- Current dict keys at lines 136-247 ARE the required `ADAPTER_NAME` values — feed these verbatim when doing the 108-file sweep (CR-1).
- Discovery must exclude `IS_FALLBACK=True` (i.e., `GenericHtmlParser`) from `ADAPTER_REGISTRY`, but `GenericHtmlParser` remains directly importable from this module for the URL-host fallback.

---

### 3. `backend/app/crawlers/adapters/generic.py` (fallback adapter)

**Role:** set `IS_FALLBACK = True` so the discovery scan skips it.

**Analog:** self. One-line addition inside the existing `GenericHtmlParser` class.

**Current class signature** (`generic.py` — class definition after line 50ish, via grep):
```python
class GenericHtmlParser(RetailerCrawlerAdapter):
    """Site-agnostic fallback parser."""
    # FETCHER_TIER inherited default "http"
    # discover_product_urls() is a no-op
```

**Adaptation:** add `IS_FALLBACK: ClassVar[bool] = True` at the top of the class body. Optionally add `ADAPTER_NAME = "generic"` for consistency (it will NOT be in `ADAPTER_REGISTRY` because `IS_FALLBACK=True` opts it out), but the `__init_subclass__` guard exempts `IS_FALLBACK=True` so this is not required.

---

### 4. `backend/app/crawlers/adapters/{tier0_http,tier1_tls,tier2_browser}/*.py` (108 files — CRITICAL CR-1)

**Role:** add one-line `ADAPTER_NAME: ClassVar[str] = "<slug>"` to every concrete adapter subclass.

**Analog:** `backend/app/crawlers/adapters/tier0_http/briantooleyracing.py:291-303` (representative tier0):
```python
class BrianTooleyRacingAdapter(RetailerCrawlerAdapter):
    """
    Brian Tooley Racing adapter. Magento storefront; plain HTTP fetches.
    ...
    """

    FETCHER_TIER = "http"

    def discover_product_urls(self) -> Iterator[str]:
        ...
```

**Tier1 analog** (`cobbtuning.py:316-339`):
```python
class CobbTuningAdapter(RetailerCrawlerAdapter):
    """..."""

    FETCHER_TIER = "tls"
```

**Tier2 analog** (`ecstuning.py:155-167`):
```python
class ECSTuningAdapter(RetailerCrawlerAdapter):
    """..."""

    FETCHER_TIER = "browser"
```

**Adaptation (per adapter, mechanical):** directly above or below the existing `FETCHER_TIER = "..."` line, insert:
```python
    ADAPTER_NAME: ClassVar[str] = "briantooleyracing"   # <-- exact key from __init__.py:148
```

Add `from typing import ClassVar` to the imports if not present. (Grep may show most adapters already import `ClassVar` or can work without the explicit annotation — the ClassVar is a hint, not required; bare `ADAPTER_NAME = "<slug>"` also works since base-class has the `ClassVar[str]` hint already. Plan may choose either.)

**CRITICAL (CR-1) execution guidance:**
- Write a one-shot helper: `backend/scripts/backfill_adapter_names.py` that reads the existing `ADAPTER_REGISTRY` dict at `adapters/__init__.py:134-248`, walks each module file under `adapters/tier*/`, locates the `class *(RetailerCrawlerAdapter):` line via regex, and inserts `ADAPTER_NAME = "<key>"` under the existing `FETCHER_TIER` declaration.
- Commit this helper alongside the sweep PR so the mechanism is auditable. Do NOT plan 108 discrete tasks.
- Plan verification: single grep — `grep -rE 'ADAPTER_NAME\s*(:|=)' backend/app/crawlers/adapters/tier*/ | wc -l` must equal 108.

---

### 5. `backend/app/crawlers/runner.py` (worker orchestrator)

**Role:** DELETE custom rate-limit counter; wire pybreaker; preserve existing `ThreadPoolExecutor` from lines 767-784; preserve per-worker `SessionLocal` at runner.py:748-ff.

**Analog:** self — the file has five well-defined edit zones:

**DELETE zone 1: constants** (lines 64-71):
```python
RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD = 5
RATE_LIMIT_CIRCUIT_BREAKER_STATUSES = frozenset({429, 502, 503, 504})
```

**DELETE zone 2: state init** (lines 444-451):
```python
# Circuit-breaker state. `consecutive_rate_limited` counts URLs whose retry
# chain exhausted against 429/502/503/504...
consecutive_rate_limited = 0
rate_limit_bailout = False
rate_limit_bailout_after = 0
```

**DELETE zone 3: reset-on-success** (lines 474-477):
```python
# Fetch returned without raising — origin is responsive. Reset the
# circuit-breaker counter regardless...
consecutive_rate_limited = 0
```

**DELETE zone 4: count-on-failure** (lines 536-545):
```python
if status in RATE_LIMIT_CIRCUIT_BREAKER_STATUSES:
    consecutive_rate_limited += 1
elif status is not None:
    consecutive_rate_limited = 0
```

**DELETE zone 5: trip** (lines 569-582):
```python
if consecutive_rate_limited >= RATE_LIMIT_CIRCUIT_BREAKER_THRESHOLD:
    logger.error("Adapter %s: circuit breaker tripped...", adapter_name, ...)
    rate_limit_bailout = True
    rate_limit_bailout_after = i
    break
```

**ADD zone 1: breaker registry** (module-level, below line 71 constants):
```python
# Per-adapter-name process-global pybreaker registry (CRAWL-04 / D-08).
# RESEARCH §Pattern 2 — double-checked locking on module-level dict.
import pybreaker
_BREAKERS: dict[str, pybreaker.CircuitBreaker] = {}
_BREAKERS_LOCK = threading.Lock()


def get_breaker(adapter_name: str) -> pybreaker.CircuitBreaker:
    breaker = _BREAKERS.get(adapter_name)
    if breaker is not None:
        return breaker
    with _BREAKERS_LOCK:
        breaker = _BREAKERS.get(adapter_name)
        if breaker is not None:
            return breaker
        breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=120, name=adapter_name)
        _BREAKERS[adapter_name] = breaker
        return breaker
```

**ADD zone 2: wrap fetch with breaker** (at the existing line 473 `html = adapter.fetcher.fetch(url)`):
```python
breaker = get_breaker(adapter_name)   # once, outside URL loop
...
try:
    html = breaker.call(adapter.fetcher.fetch, url)
except pybreaker.CircuitBreakerError:
    logger.error("Adapter %s: breaker OPEN after %s URLs; bailing.", adapter_name, i)
    rate_limit_bailout = True
    rate_limit_bailout_after = i
    break
```

**ADD zone 3: pre-trip on terminal 429/503** (inside the existing `except Exception as e:` block, replacing deleted zone 4):
```python
if status in (429, 503):
    logger.warning(
        "Adapter %s: terminal %s on URL %s — opening breaker for 120s",
        adapter_name, status, url,
    )
    breaker.open()
```

**ADD zone 4: health check before URL loop** (after adapter instantiation, before `urls = list(adapter.discover_product_urls())`):
```python
health = adapter.check_health()
if not health.healthy:
    logger.warning(
        "skipping %s: health=%s status=%s",
        adapter_name, health.reason, health.status_code,
    )
    return {
        "adapter": adapter_name, "ingested": 0, "skipped": 0, "errors": 0, "total": 0,
        "health_skipped": True,
        "health_reason": f"health_{health.reason}",
        "health_status_code": health.status_code,
    }
```

**ADD zone 5: new result-dict keys** (lines 621-644, extending the existing result dict — NOT replacing):
```python
return {
    # ... existing keys ...
    "rate_limit_bailout": rate_limit_bailout,
    "rate_limit_bailout_after": rate_limit_bailout_after,
    # --- NEW Phase 3 ---
    "parse_failures": skipped_not_product,
    "sample_failure_urls": [p["url"] for p in parse_miss_urls[:5]],
    "elapsed_seconds": round(time.monotonic() - t0, 3),   # t0 set before the URL loop
    "health_skipped": False,
    "health_reason": None,
    "health_status_code": None,
}
```

**PRESERVE verbatim:**
- `_compute_adapter_workers` at lines 657-684 (CR-3 — already correct; env var `CRAWLER_MAX_ADAPTER_WORKERS` stays).
- `ThreadPoolExecutor` at lines 767-784 (CR-3 — already correct).
- Per-worker `SessionLocal()` lifecycle (D-15 — already correct; verify `db.close()` in finally).
- `time.sleep(actual_delay)` at line 463 (D-16).
- All other existing logging, per-URL retry loop semantics (D-10).

**Exception ordering (Pitfall BR-03):** the `except pybreaker.CircuitBreakerError:` handler MUST precede the existing `except Exception as e:` at line 526, or CircuitBreakerErrors get swallowed into the general error bucket.

---

### 6. `backend/app/core/car_generations.py` (NEW module — QUAL-01)

**Role:** lazy JSON loader for car-generations data.

**Analog:** `backend/app/core/config.py:361-371` — the closest in-repo `@lru_cache` idiom:
```python
# backend/app/core/config.py:361-371
@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings.
    For tests, this can be overridden before the first call.
    """
    return Settings()


# Create settings instance for normal usage
settings = get_settings()
```

**New file pattern (combine `config.py` lru_cache + RESEARCH §Pattern 5):**
```python
"""Lazy loader for car-generations data (QUAL-01).

JSON lives at car_generations_data.json; first call reads+parses (~100-200ms),
all subsequent calls return the memoized dict reference.
"""
from __future__ import annotations

import functools
import json
from importlib.resources import files


@functools.lru_cache(maxsize=1)
def load_car_generations() -> dict:
    resource = files("app.core").joinpath("car_generations_data.json")
    return json.loads(resource.read_text(encoding="utf-8"))
```

**Adaptation notes:**
- `functools.lru_cache(maxsize=1)` — zero-arg function with `maxsize=1` is the idiomatic single-load pattern (Pattern 5).
- Do NOT read at module top-level — must be lazy (D-26 locks "uvicorn --reload startup does NOT trigger the load").
- Callers MUST NOT mutate the returned dict (Pitfall JS-01). Document in module docstring.

---

### 7. `backend/app/core/car_generations_data.json` (NEW — QUAL-01)

**Role:** static JSON asset carrying the 8,316-line dict literal.

**Analog:** no in-repo analog (first JSON data asset under `app/core/`). Closest conceptual analog is `backend/tests/fixtures/openapi_snapshot.json` (also package-adjacent JSON, read via `Path`).

**Adaptation notes:**
- Generated by the one-shot `export_car_generations.py` script (below).
- Use `json.dump(..., sort_keys=True, indent=2)` (Claude's discretion per CONTEXT; sort_keys makes diffs deterministic for future re-exports).
- Must be bit-identical to current `CAR_GENERATIONS` dict after JSON round-trip (Runtime State Inventory acceptance: zero diff in `car_generation` table after seed).

---

### 8. `backend/app/core/car_generations_data.py` (REPLACE with thin shim — CR-4)

**Role:** preserve the 4 public symbols (`slugify`, `CarGenerationData`, `CarModelData`, `CAR_GENERATIONS`, `get_all_car_generations`) so existing callers (Alembic migration, 2 model files, 1 test) continue working without edit.

**Analog:** self — current file lines 1-54 (imports + `slugify` + TypedDicts) are preserved verbatim; current lines 8374-8412 (`get_all_car_generations()`) are preserved verbatim.

**Preserve lines 1-54 verbatim:**
```python
"""Car generation data for popular modern cars since the 70s."""
import re
from typing import TypedDict
from typing_extensions import NotRequired


def slugify(value: str) -> str:
    """Convert a name into a stable, url-safe slug..."""
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


class CarGenerationData(TypedDict):
    generation_name: str
    start_year: int
    end_year: int | None
    description: NotRequired[str]
    display_name: NotRequired[str]
    slug: NotRequired[str]


class CarModelData(TypedDict):
    model: str
    generations: list[CarGenerationData]
    model_display_name: NotRequired[str]
    slug: NotRequired[str]
```

**Replace lines 58-8372 (the 8,316-line dict literal)** with a single line:
```python
from app.core.car_generations import load_car_generations

CAR_GENERATIONS: dict[str, list[CarModelData]] = load_car_generations()  # type: ignore[assignment]
```

**Preserve lines 8374-8412 verbatim** (`get_all_car_generations()` — already correct, only reads `CAR_GENERATIONS`).

**Adaptation notes:**
- `CAR_GENERATIONS` is a module-level reference to the cached dict from `load_car_generations()`. Because `lru_cache` returns the same object on every call, module-import-time evaluation is fine — it's the one-and-only cached load.
- Verify no circular import (RESEARCH Open Q #5): `car_generations.py` has zero imports from `car_generations_data.py`; `car_generations_data.py` imports from `car_generations.py`. One-way; no cycle.
- The migration at `backend/alembic/versions/30e2e2139a2e_*.py:24` does `from app.core.car_generations_data import slugify` — this STILL WORKS because lines 1-54 are preserved.

---

### 9. `backend/scripts/export_car_generations.py` (NEW — QUAL-01)

**Role:** one-shot ETL to dump the current Python literal to JSON.

**Analog:** `backend/scripts/check_migrations.py` and `backend/scripts/flatten_migrations.py` are the closest analogs — both are one-shot developer tools. Example structure:
```python
# backend/scripts/check_migrations.py (abridged — shows the one-shot script shape)
#!/usr/bin/env python3
"""Developer tool: <purpose>. Run from backend/."""
from __future__ import annotations
import sys
# ... do work ...
if __name__ == "__main__":
    sys.exit(main())
```

**New file pattern:**
```python
"""One-shot: export CAR_GENERATIONS dict to car_generations_data.json.

Run once per data change, from backend/:
    python scripts/export_car_generations.py

Commits the resulting JSON to git. After running, car_generations_data.py
was already edited to delegate to car_generations.load_car_generations().
"""
from __future__ import annotations

import json
from pathlib import Path

# Must import the PYTHON DICT before we swap car_generations_data.py to a shim.
# Run this script on a branch where the big dict literal still exists.
from app.core.car_generations_data import CAR_GENERATIONS

TARGET = Path(__file__).resolve().parent.parent / "app" / "core" / "car_generations_data.json"


def main() -> int:
    TARGET.write_text(
        json.dumps(CAR_GENERATIONS, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

**Adaptation notes:**
- Committed to `backend/scripts/` alongside the existing dev tools.
- One-shot: run BEFORE converting `car_generations_data.py` to the thin shim (or against a pre-shim checkout).
- Use `sort_keys=True` for deterministic diffs on any future re-export.

---

### 10. Logger migration (QUAL-07 — 10 files, 68 sites)

**Role:** remove `Depends(get_logger)` param from every function signature; add module-level `logger = logging.getLogger(__name__)` at top of module.

**Analog BEFORE** — `backend/app/api/endpoints/auth.py:80-92` (exact current pattern, appears 21× in this file):
```python
# imports include:
from app.core.logging import get_logger

@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str | UserRead | bool]:
    ...
    logger.warning(f"Failed login attempt for username: {form_data.username}")
    ...
```

**Analog AFTER** — `backend/app/crawlers/runner.py:50-55` (existing module-level logger idiom, the target pattern):
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

**Also analog** — `backend/app/db/session.py:1-12`:
```python
import logging
...
logger = logging.getLogger(__name__)
```

**Transformation (mechanical, per D-34 — apply identically to all 10 files):**

```diff
 import logging
 ...
-from app.core.logging import get_logger
 ...
+
+logger = logging.getLogger(__name__)
+

 @router.post("/token")
 async def login_for_access_token(
     form_data: OAuth2PasswordRequestForm = Depends(),
     db: Session = Depends(get_db),
-    logger: logging.Logger = Depends(get_logger),
 ) -> dict[str, str | UserRead | bool]:
     ...
```

**Per-file site counts (verified by research 2026-04-22):**

| File | Sites |
|---|---:|
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

**Utility router sites (Pitfall QU-07):** in `base_endpoint_router.py` (8 sites), the `Depends(get_logger)` lives INSIDE nested function definitions declared within `__init__` — e.g., `base_endpoint_router.py:94-96`:
```python
async def count_entities(
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> Dict[str, int]:
```
Removing the param is still mechanical; the `logger` at the module top-level resolves via closure.

**Adaptation notes:**
- When removing the param from `base_endpoint_router.py`'s nested closures, also remove references like `self.service.count_all(db=db, logger=logger)` if the service's kwarg is keyword-only `logger` — actually service calls already pass module-level `logger` just fine because the name resolves to module scope after removal. Verify each `logger=logger` pass-through: the local `logger` disappears but module-level `logger` binds at the same name.
- Post-sweep verify: `grep -rn "Depends(get_logger)" backend/app/` returns **zero**. This is the single acceptance signal (D-37).
- Post-sweep verify: `backend/tests/test_openapi_snapshot.py` still passes (Pitfall QU-07). If it fails, regenerate the snapshot (the diff should be purely removal of hidden dependency params, which FastAPI already excludes).
- **Do NOT** remove `get_logger` export from `backend/app/core/logging.py` in Phase 3 (D-36 — deferred to late Phase 5 / early Phase 6).

---

### 11. Test: `backend/tests/crawlers/test_adapter_discovery.py` (NEW — CRAWL-01/02/03)

**Role:** CI guard for discovery correctness.

**Analog:** `backend/tests/test_metadata_naming_convention.py` (full file 38 lines — the canonical "load object, assert attributes" guard):
```python
"""SAFE-09: pin the MetaData.naming_convention keys applied to Base."""
from __future__ import annotations


def test_metadata_naming_convention_has_five_expected_keys() -> None:
    """SAFE-09 contract: Base.metadata.naming_convention has exactly 5 keys."""
    from app.db.base_class import Base

    convention = Base.metadata.naming_convention
    assert isinstance(convention, dict)
    assert set(convention.keys()) == {
        "ix", "uq", "ck", "fk", "pk",
    }, f"Unexpected naming_convention keys: {sorted(convention.keys())}"
```

**Adapt for CRAWL-01/02/03:**
```python
"""CRAWL-01/02/03: pin the ADAPTER_REGISTRY produced by pkgutil discovery."""
from __future__ import annotations


def test_adapter_count_baseline() -> None:
    """CR-2: adapter count is 108 (83 tier0 + 15 tier1 + 10 tier2).
    Bumping this number is the PR that adds/removes an adapter."""
    from app.crawlers.adapters import ADAPTER_REGISTRY
    assert len(ADAPTER_REGISTRY) == 108, (
        f"Adapter count drift: got {len(ADAPTER_REGISTRY)}. "
        f"If intentional, bump the expected count in THIS test."
    )


def test_no_import_errors() -> None:
    """CRAWL-03: every adapter module imported cleanly."""
    from app.crawlers.adapters import _IMPORT_ERRORS
    assert _IMPORT_ERRORS == [], f"Adapter import errors:\n{_IMPORT_ERRORS!r}"


def test_all_adapters_have_non_empty_name() -> None:
    """CRAWL-02: every registered adapter declares ADAPTER_NAME."""
    from app.crawlers.adapters import ADAPTER_REGISTRY
    offenders = [cls for cls in ADAPTER_REGISTRY.values() if not cls.ADAPTER_NAME]
    assert not offenders, f"Adapters missing ADAPTER_NAME: {offenders!r}"


def test_adapter_names_are_unique() -> None:
    """CRAWL-02: no two adapters share an ADAPTER_NAME."""
    from app.crawlers.adapters import ADAPTER_REGISTRY
    names = list(ADAPTER_REGISTRY.keys())
    assert len(names) == len(set(names)), f"Duplicate adapter names: {names!r}"
```

**Adaptation notes:**
- Follow the SAFE-09 docstring + helpful error-message style from `test_metadata_naming_convention.py`.
- Pure import-based; inherently `pytest-xdist` safe.
- If `_IMPORT_ERRORS` is non-empty at Phase-3 landing, the planner must debug the offending adapters BEFORE shipping (AD-03 recovery).

---

### 12. Test: `backend/tests/crawlers/test_circuit_breaker.py` + `test_runner_breaker.py` (NEW — CRAWL-04)

**Role:** unit test for `get_breaker()` registry isolation + integration test for runner catching `CircuitBreakerError`.

**Analog:** `backend/tests/crawlers/test_runner_circuit_breaker.py` (full file 173 lines — the current custom-breaker test that we are REPLACING). Its fixture pattern is the exact template for the new tests.

**Current test fixture that the new tests should clone** (`test_runner_circuit_breaker.py:40-93`):
```python
@pytest.fixture()
def seed_user_and_category(db_session: Session) -> tuple[DBUser, DBCategory]:
    user = DBUser(
        id=uuid4(),
        username=f"svc-{uuid4().hex[:8]}",
        email=f"svc-{uuid4().hex[:8]}@example.test",
        hashed_password="x",
        email_verified=True,
        is_service_account=True,
    )
    category = DBCategory(id=uuid4(), name=f"cat-{uuid4().hex[:8]}")
    db_session.add_all([user, category])
    db_session.commit()
    return user, category


def _run_with_stubs(
    db_session: Session,
    *,
    user: DBUser,
    category: DBCategory,
    fetch_side_effects: list,
) -> dict:
    num_urls = len(fetch_side_effects)
    urls = [f"https://example-circuit-breaker.test/p{i}.html" for i in range(num_urls)]

    fake_adapter = MagicMock()
    fake_adapter.FETCHER_TIER = "http"
    fake_adapter.discover_product_urls.return_value = iter(urls)
    fake_adapter.fetcher = MagicMock()
    fake_adapter.fetcher.fetch.side_effect = fetch_side_effects
    fake_adapter.parse_product_page.return_value = None

    db_mock = MagicMock(wraps=db_session)
    db_mock.close = MagicMock()

    with (
        patch.object(runner, "SessionLocal", return_value=db_mock),
        patch.object(runner, "resolve_crawler_user", return_value=user),
        patch.object(runner, "resolve_default_category_id", return_value=category.id),
        patch.object(runner, "get_fetcher"),
        patch.object(runner, "get_adapter", return_value=fake_adapter),
        patch.object(runner, "can_fetch_url", return_value=True),
        patch.object(runner, "get_crawl_delay_sec", return_value=None),
        patch.object(runner, "apply_delay_jitter", return_value=0),
        patch.object(time, "sleep"),
    ):
        return runner.run_crawler("fake_adapter_for_test", delay_sec=0)
```

**Adaptation — `test_circuit_breaker.py`** (unit test for pybreaker registry — no runner involvement):
```python
"""CRAWL-04 unit test: pybreaker registry isolation + semantics."""
import pybreaker
from app.crawlers.runner import get_breaker, _BREAKERS


def test_same_adapter_name_returns_same_breaker() -> None:
    b1 = get_breaker("zephyr")
    b2 = get_breaker("zephyr")
    assert b1 is b2


def test_different_adapter_names_return_different_breakers() -> None:
    b1 = get_breaker("alpha")
    b2 = get_breaker("beta")
    assert b1 is not b2


def test_breaker_config_matches_req() -> None:
    """REQ-CRAWL-04: fail_max=3, reset_timeout=120."""
    b = get_breaker("config_probe")
    assert b.fail_max == 3
    assert b.reset_timeout == 120
```

**Adaptation — `test_runner_breaker.py`** (integration — replaces `test_runner_circuit_breaker.py`):
- Reuse fixture block verbatim.
- Replace `_make_503_error()` + 20-iteration loop with: call `get_breaker("fake_adapter_for_test").open()` from the test BEFORE invoking `run_one`, then assert the runner bailed with `rate_limit_bailout=True, rate_limit_bailout_after=0`.
- Add a complementary test: simulate 3 consecutive generic fetch errors → assert breaker tripped (via catching `CircuitBreakerError` on the 4th) and `rate_limit_bailout=True`.

---

### 13. Test: `backend/tests/crawlers/test_compute_adapter_workers.py` (NEW — CRAWL-05)

**Role:** unit test for the existing `_compute_adapter_workers()` function (runner.py:657-684).

**Analog:** `backend/tests/test_metadata_naming_convention.py` (pure-function attribute test idiom).

**Adaptation:**
```python
"""CRAWL-05 unit test: adapter-worker formula + env override."""
import pytest
from app.crawlers.runner import _compute_adapter_workers
from app.db.session import DB_POOL_SIZE, DB_MAX_OVERFLOW, API_CONNECTION_RESERVE


def test_default_worker_count_is_min_of_budget_and_num_adapters() -> None:
    budget = DB_POOL_SIZE + DB_MAX_OVERFLOW - API_CONNECTION_RESERVE  # = 80
    # Small cohort: bounded by num_adapters, not budget
    assert _compute_adapter_workers(3) == 3
    # Big cohort: bounded by budget, not num_adapters
    assert _compute_adapter_workers(200) == budget


def test_env_override_caps_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """CR-3: env var name is CRAWLER_MAX_ADAPTER_WORKERS (existing)."""
    monkeypatch.setenv("CRAWLER_MAX_ADAPTER_WORKERS", "5")
    assert _compute_adapter_workers(200) == 5


def test_invalid_env_override_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRAWLER_MAX_ADAPTER_WORKERS", "not-an-int")
    assert _compute_adapter_workers(3) == 3
```

---

### 14. Test: `backend/tests/crawlers/test_parallel_session_isolation.py` (NEW — CRAWL-05)

**Role:** integration test that each worker gets its own `SessionLocal`.

**Analog:** `test_runner_circuit_breaker.py:79-93` — the `patch.object(runner, "SessionLocal", return_value=db_mock)` pattern, adapted to return a DIFFERENT `MagicMock` per call (using `side_effect=[m1, m2, m3]`).

**Adaptation:** Run `runner.run_crawlers(["a", "b"], parallel=True)` with stubbed adapters; assert `SessionLocal` was called N times (once per worker) and each returned mock's `.close()` was invoked in the finally block.

---

### 15. Test: `backend/tests/crawlers/test_health_check.py` (NEW — CRAWL-06)

**Role:** unit test `check_health()` behaviors.

**Analog:** `backend/tests/crawlers/test_characterization_briantooleyracing.py` (adapter-method-under-test idiom — instantiate adapter, call method, assert return value).

**Adaptation:** three test methods, one per reason class:
```python
def test_none_probe_skips() -> None:
    """HEALTH_PROBE_URL=None → healthy=True, reason='skipped_by_config'."""
    class _Adapter(RetailerCrawlerAdapter):
        ADAPTER_NAME = "test_skip"
        HEALTH_PROBE_URL = None
        def discover_product_urls(self): return iter([])
        def parse_product_page(self, html, url): return None
    result = _Adapter().check_health()
    assert result.healthy is True
    assert result.reason == "skipped_by_config"


def test_http_4xx_marks_unhealthy(monkeypatch) -> None:
    """Probe returning 4xx → unhealthy, reason='http_4xx'."""
    # stub fetcher.fetch to raise FetcherError with status=404
    ...


def test_timeout_marks_unhealthy(monkeypatch) -> None:
    """Probe timeout → unhealthy, reason='timeout'."""
    ...
```

---

### 16. Test: `backend/tests/crawlers/test_runner_result_dict.py` (NEW — CRAWL-07)

**Role:** assert the new keys (`parse_failures`, `sample_failure_urls`, `elapsed_seconds`) appear in the result dict.

**Analog:** `backend/tests/crawlers/test_runner_circuit_breaker.py` lines 113-119 — assert-on-returned-dict pattern:
```python
assert result["rate_limit_bailout"] is True
assert result["rate_limit_bailout_after"] == threshold
assert result["total"] == 20
assert result["ingested"] == 0
```

**Adaptation:** stub a run with 7 parse-miss URLs; assert `result["parse_failures"] == 7`, `len(result["sample_failure_urls"]) == 5`, and `result["elapsed_seconds"] >= 0`.

---

### 17. Test: `backend/tests/test_car_generations_loader.py` (NEW — QUAL-01)

**Role:** verify `load_car_generations()` returns correct shape + memoizes.

**Analog:** `backend/tests/test_init_cars_display_name.py` (existing test that consumes `CAR_GENERATIONS` — gives the shape expectations).

**Adaptation:**
```python
"""QUAL-01: car_generations JSON loader + lru_cache memoization."""
from __future__ import annotations


def test_load_returns_dict_with_expected_top_level_makes() -> None:
    from app.core.car_generations import load_car_generations
    data = load_car_generations()
    assert isinstance(data, dict)
    # Representative top-level keys verified by grep of current car_generations_data.py
    assert "Honda" in data
    assert "Toyota" in data


def test_lru_cache_single_load() -> None:
    """@lru_cache(maxsize=1) returns same dict object."""
    from app.core.car_generations import load_car_generations
    a = load_car_generations()
    b = load_car_generations()
    assert a is b  # identity, not just equality


def test_shim_and_loader_agree() -> None:
    """CR-4: car_generations_data.CAR_GENERATIONS equals the loader output."""
    from app.core.car_generations import load_car_generations
    from app.core.car_generations_data import CAR_GENERATIONS
    assert CAR_GENERATIONS is load_car_generations()
```

---

### 18. Test: `backend/tests/test_pydantic_v1_regression.py` + `test_on_event_regression.py` + `test_logger_migration_regression.py` (NEW — QUAL-02, 03, 07)

**Role:** grep-based CI regression guards.

**Analog:** `backend/tests/test_openapi_snapshot.py` (SAFE-05 drift guard — full file 58 lines):
```python
"""SAFE-05: OpenAPI schema snapshot test.

Catches unintended route / schema drift. The snapshot is formatted JSON...
"""
from __future__ import annotations
import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"


def test_openapi_snapshot_matches() -> None:
    from app.main import app
    actual = json.dumps(app.openapi(), indent=2, sort_keys=True)
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")
    assert actual == expected, msg
```

**Adaptation — `test_pydantic_v1_regression.py`** (follows RESEARCH §Pattern 7):
```python
"""QUAL-02 regression guard: no Pydantic v1 anti-patterns reintroduced."""
import re
import warnings
from pathlib import Path

import pydantic

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"

FORBIDDEN_PATTERNS = [
    (re.compile(r"@validator\b"),            "Pydantic v1 @validator — use @field_validator"),
    (re.compile(r"@root_validator\b"),       "Pydantic v1 @root_validator — use @model_validator"),
    (re.compile(r"^\s*class\s+Config\s*:"),  "Pydantic v1 class Config — use model_config = ConfigDict(...)"),
    (re.compile(r"\.parse_obj\("),           "Pydantic v1 .parse_obj() — use .model_validate()"),
]


def test_no_forbidden_patterns_in_app() -> None:
    offenders = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for pat, label in FORBIDDEN_PATTERNS:
                if pat.search(line):
                    offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno, label))
    assert not offenders, "Forbidden Pydantic v1 patterns found:\n" + "\n".join(
        f"  {f}:{n}: {label}" for f, n, label in offenders
    )


def test_no_pydantic_v1_deprecation_warnings_on_roundtrip() -> None:
    """Pitfall QU-01: pytest.ini has --disable-warnings — use catch_warnings."""
    # Use a representative v2 schema from app.api.schemas
    from app.api.schemas.user import UserRead
    with warnings.catch_warnings():
        warnings.simplefilter("error", pydantic.PydanticDeprecatedSince20)
        # representative roundtrip — adjust to an actual constructible UserRead shape
        user_dict = UserRead.model_validate({"id": 1, "username": "x", "email_verified": True}).model_dump()
        reloaded = UserRead.model_validate(user_dict)
        assert reloaded is not None
```

**Adaptation — `test_on_event_regression.py`** (may be merged into the Pydantic file):
```python
"""QUAL-03 regression guard: no @app.on_event — use lifespan."""
import re
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"
ON_EVENT_RE = re.compile(r"@\w+\.on_event\(")


def test_no_app_on_event_in_app() -> None:
    offenders = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if ON_EVENT_RE.search(line):
                offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno))
    assert not offenders, f"@app.on_event found — use lifespan context manager: {offenders!r}"
```

**Adaptation — `test_logger_migration_regression.py`** (QUAL-07 acceptance — D-37):
```python
"""QUAL-07 regression guard: zero Depends(get_logger) in backend/app/."""
import re
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"
DEPENDS_GET_LOGGER_RE = re.compile(r"Depends\(\s*get_logger\s*\)")


def test_no_depends_get_logger_in_app() -> None:
    offenders = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if DEPENDS_GET_LOGGER_RE.search(line):
                offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno))
    assert not offenders, (
        f"Depends(get_logger) found ({len(offenders)} sites) — use module-level "
        f"logger = logging.getLogger(__name__): {offenders!r}"
    )
```

---

### 19. Test modifications: `backend/tests/crawlers/test_characterization_{5}.py` (Phase 1 D-23 handoff)

**Role:** switch 5 tests from keying by class-name import to keying by `ADAPTER_REGISTRY[name]`.

**Analog:** `backend/tests/crawlers/test_characterization_briantooleyracing.py:1-19` (current form):
```python
from app.crawlers.adapters.tier0_http.briantooleyracing import BrianTooleyRacingAdapter
...
adapter = BrianTooleyRacingAdapter()
```

**Adaptation after CRAWL-02 lands:**
```python
from app.crawlers.adapters import ADAPTER_REGISTRY
...
adapter = ADAPTER_REGISTRY["briantooleyracing"]()
```

**Files to update (all in same PR as CRAWL-02):**
- `test_characterization_amsperformance.py`
- `test_characterization_briantooleyracing.py`
- `test_characterization_cobbtuning.py`
- `test_characterization_subispeed.py`
- `test_characterization_texasspeed.py`

Each file gets the exact same two-line change.

---

### 20. `backend/requirements.txt` — add pybreaker

**Analog:** self.

**Adaptation:** append one line:
```
pybreaker==1.4.1
```

---

### 21. `backend/app/core/email.py` (MODIFY — CRAWL-07)

**Role:** extend `_render_crawler_result_html` (line 221) with a ParseFailures + sample-URL block per adapter.

**Analog:** self — the existing renderer at `email.py:221-342` already renders per-adapter rows (`rows_html.append(...)` pattern at lines 283+). The new block is additive.

**Additive pattern — inside the existing per-adapter row builder at line 283+:**
```python
# After the existing row's "Skipped" cell, before "HTTP breakdown":
parse_failures = r.get("parse_failures", 0)
samples = r.get("sample_failure_urls") or []
if parse_failures > 0 and samples:
    rows_html.append(
        f'<tr><td colspan="5" style="font-size:11px;color:#6b7280;padding:0 10px 8px 22px">'
        f'<strong>ParseFailures:</strong> {parse_failures} / {r.get("total", 0)} — '
        f'samples: {"<br/>".join(_escape_html(u)[:160] for u in samples)}'
        f'</td></tr>'
    )
```

Also extend `_render_crawler_failure_samples` helper at line 413 if it exists and already renders sample URLs (grep confirmed it does — it's already the renderer for failure samples; CRAWL-07 extends its input).

---

## Shared Patterns (cross-cutting)

### SP-1: Module-level logger (QUAL-07 target)
**Source:** `backend/app/crawlers/runner.py:55` and `backend/app/db/session.py:12`
**Apply to:** all 10 QUAL-07 files (replaces `Depends(get_logger)`)
```python
import logging
logger = logging.getLogger(__name__)
```

### SP-2: `ClassVar` on adapter base
**Source:** `backend/app/crawlers/adapters/base.py:35`
**Apply to:** 108 adapter files gaining `ADAPTER_NAME`
```python
ADAPTER_NAME: ClassVar[str] = "<slug>"
```

### SP-3: `@lru_cache(maxsize=1)` for single-load
**Source:** `backend/app/core/config.py:361-371`
**Apply to:** `backend/app/core/car_generations.py`
```python
@functools.lru_cache(maxsize=1)
def load_car_generations() -> dict: ...
```

### SP-4: Test fixture — stubbed adapter + patched runner
**Source:** `backend/tests/crawlers/test_runner_circuit_breaker.py:40-93`
**Apply to:** all new runner-integration tests (`test_runner_breaker.py`, `test_parallel_session_isolation.py`, `test_runner_result_dict.py`)

### SP-5: Grep-based CI drift guard
**Source:** `backend/tests/test_openapi_snapshot.py:30-58` (structural) and SAFE-04 migration DROP-guard pattern
**Apply to:** `test_pydantic_v1_regression.py`, `test_on_event_regression.py`, `test_logger_migration_regression.py`, and `test_adapter_discovery.py`

### SP-6: Docstring convention for regression guards
**Source:** `backend/tests/test_metadata_naming_convention.py:1-6`
**Apply to:** all new CI guard tests — start with a one-line summary naming the REQ id (e.g., "QUAL-07 regression guard: ...")

---

## No Analog Found

None. Every touched file has a plausible in-repo analog, though two areas use genuinely new mechanics (both have authoritative library-doc patterns in RESEARCH §Pattern 1 and §Pattern 5):

| File | Role | Mechanics | Fallback |
|---|---|---|---|
| `adapters/base.py` (the `__init_subclass__` logic) | base-class enforcement | `__init_subclass__` not used anywhere in `backend/app/` | RESEARCH §Pattern 1 — tested canonical form |
| `core/car_generations.py` (the `importlib.resources` logic) | package-adjacent file load | `importlib.resources.files()` not used anywhere in `backend/app/` | RESEARCH §Pattern 5 — Python 3.13 stdlib docs |

---

## Planner Decision Matrix (for the task breakdown)

| Decision | Pattern says | Alternative | Rec |
|---|---|---|---|
| 108-adapter sweep — per-task or script? | CR-1: one script + one grep-verify task | 108 micro-tasks | **Script + verify** |
| Discovery loader — raise on `_IMPORT_ERRORS`? | AD-03 says NO (raise only from the test) | raise at import time | **Test-only raise** |
| `HEALTH_PROBE_URL` default — `None` or `BASE_URL` sweep? | DISC-04 recommends Option A (None) | 108-file BASE_URL sweep | **Option A** |
| `car_generations_data.py` — shim or stub? | CR-4 says thin shim | ImportError stub | **Thin shim** |
| QUAL-02/03/07 guards — merge or separate files? | Claude's discretion; analog has separate files (`test_openapi_snapshot.py` is standalone) | single file with 3 test funcs | **Separate files** (clearer failures) |
| Env var name for worker cap | CR-3: `CRAWLER_MAX_ADAPTER_WORKERS` (existing) | rename to `CRAWLER_MAX_WORKERS` per D-14 | **Keep existing** |

---

## Metadata

**Analog search scope:**
- `backend/app/` — full tree (api/, core/, crawlers/, db/, services/)
- `backend/tests/` — full tree (crawlers/, fixtures/, top-level regression guards)
- `backend/scripts/` — one-shot dev tools (for QUAL-01 export script analog)

**Files scanned:** ~25 concrete analog reads + grep traversal of `backend/app/**/*.py` for `Depends(get_logger)` (68 sites confirmed), `__init_subclass__` (0 sites), `importlib.resources` (0 sites), `lru_cache` (1 site — config.py), `logger = logging.getLogger(__name__)` (10 sites).

**Pattern extraction date:** 2026-04-22

**Cross-references:**
- CONTEXT §D-01 through D-38 — all mapped to concrete analog
- RESEARCH §DISC-01 through DISC-09 — drift flagged; adjusted recommendations embedded in CR-1..CR-4
- RESEARCH §Pattern 1..8 — referenced for new mechanics (no in-repo analog)
