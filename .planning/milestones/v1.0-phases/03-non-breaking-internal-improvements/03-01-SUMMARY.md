---
phase: 03-non-breaking-internal-improvements
plan: 01
subsystem: crawler/adapter-discovery
tags: [crawler, adapter-registry, pkgutil, ci-guard, CRAWL-01, CRAWL-02, CRAWL-03]
requires:
  - phase-1 characterization tests (SAFE-07): 5 test files migrated per D-23 handoff
provides:
  - ADAPTER_REGISTRY populated by pkgutil.iter_modules (auto-discovery, CRAWL-01)
  - __init_subclass__ enforcement of non-empty ADAPTER_NAME on every concrete adapter (CRAWL-02)
  - _IMPORT_ERRORS list + test_no_import_errors CI guard (CRAWL-03)
  - HealthResult dataclass + RetailerCrawlerAdapter.check_health() opt-out stub (Plan 02 wire-up point)
affects:
  - Plan 02 (CRAWL-04/05/06): pybreaker registry can now key by ADAPTER_NAME
tech-stack:
  added: []
  patterns:
    - pkgutil.iter_modules + importlib.import_module auto-discovery
    - __init_subclass__ declarative validation
    - Per-module try/except with _IMPORT_ERRORS accumulation (Pitfall AD-03)
key-files:
  created:
    - backend/tests/crawlers/test_adapter_discovery.py (CI guard, 4 tests, 70 lines)
    - backend/scripts/backfill_adapter_names.py (one-shot AST-based inserter)
  modified:
    - backend/app/crawlers/adapters/base.py (__init_subclass__, ADAPTER_NAME/IS_FALLBACK/HEALTH_PROBE_URL ClassVars, HealthResult dataclass, check_health() stub)
    - backend/app/crawlers/adapters/generic.py (IS_FALLBACK=True)
    - backend/app/crawlers/adapters/__init__.py (replaced 113 explicit imports + 109-entry dict with pkgutil scan; get_adapter('generic') special-case)
    - backend/app/crawlers/adapters/tier0_http/*.py (83 adapters — ADAPTER_NAME inserted)
    - backend/app/crawlers/adapters/tier1_tls/*.py (15 adapters — ADAPTER_NAME inserted)
    - backend/app/crawlers/adapters/tier2_browser/*.py (10 adapters — ADAPTER_NAME inserted)
    - backend/tests/crawlers/test_characterization_amsperformance.py (class-name → ADAPTER_REGISTRY lookup)
    - backend/tests/crawlers/test_characterization_briantooleyracing.py
    - backend/tests/crawlers/test_characterization_cobbtuning.py
    - backend/tests/crawlers/test_characterization_subispeed.py
    - backend/tests/crawlers/test_characterization_texasspeed.py
decisions:
  - ADAPTER_REGISTRY populated by pkgutil scan at import time; 108 keys (excludes "generic" per IS_FALLBACK=True)
  - _discover_adapters() never raises; failures accumulate in _IMPORT_ERRORS so a single CI test is the enforcement point (Pitfall AD-03 overrides CONTEXT D-05's "loader raises" wording)
  - get_adapter("generic") preserved as a reserved name that bypasses ADAPTER_REGISTRY and returns GenericHtmlParser directly (keeps /scrape endpoint + archive rescrape pipeline contract)
  - ADAPTER_NAME slugs copied verbatim from pre-existing ADAPTER_REGISTRY dict keys via AST-based one-shot script (CR-1 audit trail)
metrics:
  duration_minutes: ~45
  completed_date: 2026-04-22
  tasks_completed: 3
  files_created: 2
  files_modified: 116
  tests_passing: 9 (4 discovery + 5 characterization)
  full_crawler_suite: 1236 passed, 1 skipped
  regressions_caught_and_fixed: 1 (Rule 1 - get_adapter('generic'))
---

# Phase 03 Plan 01: Adapter Auto-Discovery + ADAPTER_NAME Enforcement Summary

Landed pkgutil-driven adapter auto-discovery, declarative `ADAPTER_NAME` enforcement via `__init_subclass__`, and a single CI test that fails loudly on any import-time failure across 108 retailer adapters — removing the 113-line hand-maintained import block and unblocking the pybreaker registry in Plan 02 (CRAWL-04/05/06).

## One-liner

Replaced the hand-maintained `ADAPTER_REGISTRY` import block with a `pkgutil.iter_modules` auto-discovery scan, enforced non-empty `ADAPTER_NAME` on every concrete adapter via `__init_subclass__`, and landed a 4-test CI guard pinning the registry at exactly 108 entries with zero import errors.

## What Landed

### Task 1 — Base class extension + RED test (commit `7f83cdc`)

`backend/app/crawlers/adapters/base.py`:
- Added `HealthResult` frozen dataclass (`healthy`, `reason`, `status_code: int | None`) at module level.
- Added `__init_subclass__` hook that raises `TypeError` on class-definition if a concrete subclass does not declare a non-empty `ADAPTER_NAME`. Exempts `IS_FALLBACK=True` and still-abstract intermediate bases (per Pitfall AD-01).
- Added three new `ClassVar` declarations: `ADAPTER_NAME: ClassVar[str] = ""`, `IS_FALLBACK: ClassVar[bool] = False`, `HEALTH_PROBE_URL: ClassVar[str | None] = None`.
- Added `check_health(self) -> HealthResult` opt-out default (per DISC-04 Option A). Plan 02 (CRAWL-06) will wire the probe I/O path; Plan 01 lands the declarative hook.

`backend/app/crawlers/adapters/generic.py`:
- Marked `GenericHtmlParser` with `IS_FALLBACK: ClassVar[bool] = True` so it is exempt from the subclass guard AND excluded from `ADAPTER_REGISTRY` (per D-03).

`backend/tests/crawlers/test_adapter_discovery.py` (new):
- Four CI guard tests per the plan's Behavior block:
  - `test_adapter_count_baseline`: `len(ADAPTER_REGISTRY) == 108`
  - `test_no_import_errors`: `_IMPORT_ERRORS == []`
  - `test_all_adapters_have_non_empty_name`: defense-in-depth for D-02
  - `test_adapter_names_are_unique`: defense-in-depth for T-03-01-02

All four tests failed RED at Task 1 commit (expected — registry wasn't yet discovery-driven and adapters had no `ADAPTER_NAME`).

### Task 2 — One-shot `ADAPTER_NAME` backfill (commit `f8dcdb9`)

`backend/scripts/backfill_adapter_names.py` (new, ~200 lines):
- AST-based inserter that reads `ADAPTER_REGISTRY = { "<slug>": ClassName, ... }` from `adapters/__init__.py` as the single source of truth for each class's canonical slug (per CR-1).
- For every `.py` under `tier0_http/`, `tier1_tls/`, `tier2_browser/`: parses the AST, finds the first `RetailerCrawlerAdapter` subclass, inserts `ADAPTER_NAME: ClassVar[str] = "<slug>"` after the class docstring, and ensures `ClassVar` is in the module's `from typing import ...` line.
- Idempotent (skips classes that already declare `ADAPTER_NAME`).
- Asserts exactly 108 declarations at end of run or exits non-zero.

Running the script produced 108 file modifications — all matching their pre-existing `ADAPTER_REGISTRY` key verbatim (`briantooleyracing`, `cobbtuning`, `ecstuning`, etc.). Script committed alongside the sweep as the audit trail (per CR-1).

### Task 3 — pkgutil auto-discovery + characterization test migration (commit `a0bf301`)

`backend/app/crawlers/adapters/__init__.py`:
- Removed 113 explicit `from app.crawlers.adapters.tierN_XX.modulename import ClassName` lines (lines 19-131 of the pre-edit file).
- Removed the 109-entry hand-maintained `ADAPTER_REGISTRY` dict literal.
- Replaced with `_discover_adapters()`: walks the three tier directories with `pkgutil.iter_modules`, imports each module inside a per-module `try/except BaseException`, and collects concrete `RetailerCrawlerAdapter` subclasses keyed by `ADAPTER_NAME`. Per Pitfall AD-03, never raises at import time — failures accumulate in `_IMPORT_ERRORS`.
- Detects duplicate slugs and appends `ValueError` to `_IMPORT_ERRORS` (T-03-01-02 defense).
- Preserved `adapter_name_for_product_url` and `get_adapter` helpers verbatim.

Migrated 5 Phase-1 characterization tests (D-23 handoff) from class-name imports to `ADAPTER_REGISTRY["<slug>"]()` lookups: `amsperformance`, `briantooleyracing`, `cobbtuning`, `subispeed`, `texasspeed`.

All 4 discovery tests + 5 characterization tests GREEN after Task 3.

## Baseline Committed

- `ADAPTER_REGISTRY`: 108 entries (83 tier0 + 15 tier1 + 10 tier2 — matches DISC-01).
- `_IMPORT_ERRORS`: `[]` at merge.
- `pytest -n auto tests/crawlers/`: 1236 passed, 1 skipped.
- `pytest -n auto tests/test_openapi_snapshot.py`: 1 passed (OpenAPI contract unchanged).
- `pytest -n auto tests/test_crawled_page_storage.py`: 38 passed (after Rule 1 fix).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `get_adapter("generic")` broke after IS_FALLBACK exclusion**

- **Found during:** Task 3 — full-suite verification (`pytest -n auto`) after wiring `_discover_adapters()`.
- **Issue:** `tests/test_crawled_page_storage.py` 3 tests failed with `KeyError: "Unknown adapter: generic"`. The `/scrape` endpoint at `backend/app/api/endpoints/crawled_pages.py:263` calls `get_adapter(adapter_name)` where `adapter_name` comes from `adapter_name_for_product_url(url)`, which returns `"generic"` for unknown hosts (unchanged from the hand-maintained era). Pre-plan, `ADAPTER_REGISTRY` contained `"generic": GenericHtmlParser` as its 109th entry. After the pkgutil scan (which correctly excludes `IS_FALLBACK=True` per D-03), the dict dropped to 108 keys — breaking the `"generic"` lookup contract that the archive rescrape pipeline and the Chrome-extension `/scrape` endpoint depend on.
- **Fix:** Added a special-case branch at the top of `get_adapter()`: `if name == "generic": return GenericHtmlParser(fetcher=fetcher) if fetcher is not None else GenericHtmlParser()`. Preserves the contract without leaking the fallback into `ADAPTER_REGISTRY` (still 108 keys — baseline unchanged). Documented in the `get_adapter` docstring.
- **Files modified:** `backend/app/crawlers/adapters/__init__.py` (get_adapter special-case)
- **Commit:** Part of `a0bf301` (Task 3 commit)
- **Tests:** The 3 previously-failing `test_crawled_page_storage` tests now pass; the 108-count CI guard still holds.

### Deferred Items (out of plan scope)

- `tests/api/endpoints/test_users.py::test_upload_profile_picture_concurrent_requests` flaked once under `pytest -n auto` (xdist worker crashed). Passes solo without xdist. Pre-existing concurrency-test flakiness in the storage/auth paths — unrelated to crawler adapter work. Logged here for phase-level tracking; no action taken per SCOPE BOUNDARY rule.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `ADAPTER_REGISTRY` contains exactly 108 keys (excludes `generic`) | Honors D-03 (fallback excluded) and keeps `test_adapter_count_baseline` from needing a special case. |
| `_discover_adapters()` never raises; failures accumulate in `_IMPORT_ERRORS` | Per Pitfall AD-03 — raising here would poison every test that transitively imports `app.crawlers` with a noisy stack. `test_no_import_errors` is the single CI enforcement point (overrides CONTEXT D-05's "loader raises" wording). |
| `get_adapter("generic")` reserved bypass | Preserves existing `/scrape` + archive-rescrape contract without polluting the auto-discovered registry. See Deviation 1. |
| ADAPTER_NAME slugs copied verbatim from pre-existing dict keys | CR-1 — the registry keys are already the canonical, tested slugs (matched against hostname→slug map in `adapter_name_for_product_url`). Deriving from class names would risk drift (`ECSTuningAdapter` → `ecstuning` vs `ectsuning` etc.). |

## Threat Flags

None — no new security-relevant surface introduced. The threat register's three `mitigate` dispositions (T-03-01-01 per-module import isolation, T-03-01-02 duplicate-slug detection, T-03-01-03 silent-drop count baseline) are all enforced by the shipped code.

## Unblocks

- **Plan 02 (CRAWL-04/05/06)**: pybreaker registry can now key by `ADAPTER_NAME` (every adapter has one, it's globally unique, and `ADAPTER_REGISTRY.keys()` is the canonical iteration order).
- **Plan 02 also**: `RetailerCrawlerAdapter.check_health()` stub + `HEALTH_PROBE_URL` ClassVar are landed; Plan 02 just needs to wire the probe I/O path for the 30+ adapters that want pre-crawl health probing.

## Self-Check: PASSED

Verified all claimed artifacts exist on disk in the worktree and all claimed commits exist in the worktree branch history.

**Files on disk:**
- FOUND: `backend/app/crawlers/adapters/base.py` (107 lines, contains `__init_subclass__`, `HealthResult`, `ADAPTER_NAME`, `IS_FALLBACK`, `HEALTH_PROBE_URL`, `check_health`)
- FOUND: `backend/app/crawlers/adapters/generic.py` (`IS_FALLBACK: ClassVar[bool] = True`)
- FOUND: `backend/app/crawlers/adapters/__init__.py` (472 lines, 0 explicit per-adapter imports, 2 occurrences of `pkgutil.iter_modules`, 4 occurrences of `_IMPORT_ERRORS`, both helpers preserved)
- FOUND: `backend/tests/crawlers/test_adapter_discovery.py` (4 `def test_` functions, 1 occurrence of `== 108`)
- FOUND: `backend/scripts/backfill_adapter_names.py`
- FOUND: 108 `ADAPTER_NAME` declarations across tier0_http/tier1_tls/tier2_browser
- FOUND: 5 `from app.crawlers.adapters import ADAPTER_REGISTRY` lines in `tests/crawlers/test_characterization_*.py`

**Commits in worktree branch:**
- FOUND: `7f83cdc` — test(03-01): add failing adapter-discovery CI guard + base class enforcement (RED)
- FOUND: `f8dcdb9` — feat(03-01): backfill ADAPTER_NAME on 108 concrete adapters via one-shot script
- FOUND: `a0bf301` — feat(03-01): pkgutil auto-discovery + migrate 5 characterization tests (GREEN)

**Test suites:**
- PASSED: `pytest -n auto tests/crawlers/test_adapter_discovery.py tests/crawlers/test_characterization_*.py` → 9 passed
- PASSED: `pytest -n auto tests/crawlers/` → 1236 passed, 1 skipped
- PASSED: `pytest -n auto tests/test_openapi_snapshot.py` → 1 passed
- PASSED: `pytest -n auto tests/test_crawled_page_storage.py` → 38 passed
