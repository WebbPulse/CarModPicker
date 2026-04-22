---
phase: 03-non-breaking-internal-improvements
plan: 04
subsystem: backend-core
tags: [performance, lazy-load, importlib-resources, lru-cache, car-generations, quality, json-asset]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: existing car_generations_data.py (8,412-line literal) and callers (alembic migration 30e2e2139a2e, models/car_generation.py, models/car_model.py, tests/test_init_cars_display_name.py)
provides:
  - app/core/car_generations.py loader with @functools.lru_cache(maxsize=1) reading JSON via importlib.resources.files()
  - app/core/car_generations_data.json (352,511 bytes, deterministic sort_keys=True) as canonical data source
  - app/core/car_generations_data.py reduced to 108-line thin shim preserving full public API (slugify, CarGenerationData, CarModelData, CAR_GENERATIONS, get_all_car_generations)
  - scripts/export_car_generations.py one-shot ETL for reproducible data regeneration
  - tests/test_car_generations_loader.py 4-test suite (loader identity, lru_cache memoization, shim equivalence, JSON round-trip)
affects: [phase-04-onwards, any-future-data-updates, dev-startup-latency]

# Tech tracking
tech-stack:
  added: [importlib.resources.files (stdlib Python 3.9+), functools.lru_cache(maxsize=1) pattern]
  patterns: [lazy-json-loader-with-lru-cache, thin-shim-preserves-public-api, one-shot-etl-script-committed]

key-files:
  created:
    - backend/app/core/car_generations.py
    - backend/app/core/car_generations_data.json
    - backend/scripts/export_car_generations.py
    - backend/tests/test_car_generations_loader.py
  modified:
    - backend/app/core/car_generations_data.py (8,412 → 108 lines; now thin shim)

key-decisions:
  - "Preserve the car_generations_data module as a thin shim (not a raising stub) so existing callers import slugify/CAR_GENERATIONS/get_all_car_generations without modification (DISC-05 / PATTERNS CR-4)"
  - "Store JSON as package-adjacent asset loaded via importlib.resources.files() rather than pathlib.Path — supports zipapp/namespace-package edge cases (Pitfall JS-02)"
  - "Commit the one-shot export script to scripts/ rather than deleting it — future data edits can regenerate JSON reproducibly (D-27)"
  - "lru_cache(maxsize=1) holds the parsed dict for the lifetime of the process — trade a few MB memory for amortized O(1) access after first call (Threat T-03-04-05 accepted)"

patterns-established:
  - "Pattern: large static Python dict → JSON asset + @functools.lru_cache(maxsize=1) loader using importlib.resources (QUAL-01 blueprint for future large-literal extractions)"
  - "Pattern: thin shim module re-exports public API when extracting data to sibling loader — zero caller-side changes required"
  - "Pattern: one-shot ETL scripts committed to backend/scripts/ for reproducible data regeneration alongside migrations"

requirements-completed: [QUAL-01]

# Metrics
duration: 6min
completed: 2026-04-22
---

# Phase 03 Plan 04: car_generations JSON Extraction Summary

**Extracted the 8,316-line CAR_GENERATIONS Python dict literal into a package-adjacent JSON asset loaded lazily via @functools.lru_cache(maxsize=1) + importlib.resources.files(), reducing the data module from 8,412 to 108 lines while preserving the full public API as a thin shim (QUAL-01).**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-04-22T20:58:05Z
- **Completed:** 2026-04-22T21:04:09Z
- **Tasks:** 2 of 3 executed (Task 3 is a manual-evidence checkpoint — see below)
- **Files created:** 4
- **Files modified:** 1

## Accomplishments

- Created `app/core/car_generations.py` loader with `@functools.lru_cache(maxsize=1)` and `importlib.resources.files('app.core').joinpath('car_generations_data.json').read_text(encoding='utf-8')` per PATTERNS §6 / RESEARCH Pattern 5.
- Generated `app/core/car_generations_data.json` (352,511 bytes; `sort_keys=True`, `indent=2`; 39 top-level makes including Honda, Toyota, BMW, etc.) as canonical data source.
- Converted `app/core/car_generations_data.py` from 8,412-line Python literal to a 108-line thin shim: preserves `slugify`, `CarGenerationData`, `CarModelData`, `CAR_GENERATIONS`, `get_all_car_generations()` — the shim's module-level `CAR_GENERATIONS` IS the lru_cached loader output (CR-4 invariant verified by `test_shim_and_loader_agree`).
- Committed `scripts/export_car_generations.py` as a one-shot ETL for reproducible future data regeneration (D-27 / PATTERNS §9).
- Added `tests/test_car_generations_loader.py` with 4 tests: loader shape, `@lru_cache` identity (`a is load_car_generations()`), shim-loader equivalence (`CAR_GENERATIONS is load_car_generations()`), and JSON asset existence + parse via `importlib.resources`.
- **Zero caller-side edits required** — alembic migration `30e2e2139a2e_*.py`, `models/car_generation.py`, `models/car_model.py`, `tests/test_init_cars_display_name.py` all import `slugify` / `CAR_GENERATIONS` unchanged.
- Broader backend test suite: **932 pass, 4 skipped, 0 fail** (no regression).

## Task Commits

1. **Task 1: RED failing loader tests** — `e7b85e8` (test)
2. **Task 2: Loader + export script + JSON + thin shim** — `e8e9179` (feat)
3. **Task 3: Human-verify uvicorn latency measurement** — PENDING (manual evidence gate; see below)

## Files Created/Modified

- `backend/app/core/car_generations.py` (NEW, ~22 lines) — `@functools.lru_cache(maxsize=1)` loader reading `car_generations_data.json` via `importlib.resources.files()`
- `backend/app/core/car_generations_data.json` (NEW, 352,511 bytes) — deterministic JSON export of 39-make / 8,316-line dict literal (sort_keys=True, indent=2, ensure_ascii=False)
- `backend/app/core/car_generations_data.py` (MODIFIED, 8,412 → 108 lines) — thin shim preserving full public API; `CAR_GENERATIONS = load_car_generations()` delegates to cached loader
- `backend/scripts/export_car_generations.py` (NEW, ~36 lines) — one-shot ETL for reproducible data regeneration (must be run on a branch where the big dict literal still exists)
- `backend/tests/test_car_generations_loader.py` (NEW, 43 lines) — 4 tests: loader shape, `@lru_cache` identity, shim-loader equivalence, JSON asset parse

## Decisions Made

- **Thin shim, not raising stub** (DISC-05 / PATTERNS CR-4): preserving `car_generations_data` as a thin re-export shim keeps all existing callers working unchanged — zero blast radius. The alternative (raising stub) would have required editing 4+ caller files and the alembic migration.
- **`importlib.resources.files()` over `pathlib.Path(__file__).parent`**: the former is the stable Python 3.9+ public API for package-adjacent resources and works in zipapp / namespace-package layouts. Avoids Pitfall JS-02 from 03-RESEARCH.md.
- **`@functools.lru_cache(maxsize=1)` over a module-level constant**: defers the JSON parse until the first caller, and `maxsize=1` makes the cache self-documenting (one entry only — the parsed dict). Process-lifetime memoization with trivial memory cost (~a few MB).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing backend dependencies in worktree env**
- **Found during:** Task 1 RED verification
- **Issue:** Fresh worktree Python env missing `uuid6` and `python-json-logger` packages (both in `requirements.txt` but not pre-installed). Tests failed with `ModuleNotFoundError` on `conftest.py` import.
- **Fix:** Ran `pip install -r backend/requirements.txt` to bring env up to date. No source changes required.
- **Files modified:** None (env-only)
- **Verification:** `pytest tests/test_car_generations_loader.py` imports conftest successfully after install.
- **Committed in:** N/A (env setup, not source)

**2. [Rule 2 - Test assertion strength] Strengthened `test_lru_cache_single_load` identity checks**
- **Found during:** Task 1 acceptance-criteria grep
- **Issue:** Original test had single `a is b` assertion; plan acceptance required ≥2 `is load_car_generations()` identity assertions to make the lru_cache invariant explicit at the function-call boundary.
- **Fix:** Rewrote test body to `assert a is load_car_generations()` + `assert load_car_generations() is load_car_generations()` — both assertions pin identity against the direct function call, not just between local refs.
- **Files modified:** backend/tests/test_car_generations_loader.py
- **Verification:** `grep -c 'is load_car_generations()' tests/test_car_generations_loader.py` now returns 3 (≥2 required).
- **Committed in:** e7b85e8 (Task 1 commit, pre-RED)

---

**Total deviations:** 2 auto-fixed (1 blocking env, 1 test-assertion strength)
**Impact on plan:** Both adjustments were strictly about enabling correct verification. No source changes outside the planned set; no scope creep.

## Issues Encountered

- **Worktree env missing dependencies:** The parallel worktree inherits the repo but not the installed Python packages — expected in a fresh-worktree context. Resolved via `pip install -r requirements.txt`.
- No blocking issues in the core loader/shim conversion.

## Task 3 Checkpoint: Manual uvicorn Startup Measurement

**Status: PARTIALLY AUTOMATED — automated AST-parse measurement captured below. Full `uvicorn --reload` end-to-end cold-boot measurement is the remaining operator task for the PR description per D-28.**

### Automated measurements (captured by executor)

AST parse cost of `car_generations_data.py` — the module that gets re-parsed on every `uvicorn --reload` cycle:

| State | File size (lines) | AST parse (3 runs, ms) | Median |
| ----- | ----------------- | ---------------------- | ------ |
| BEFORE (dict literal) | 8,412 | 12.6, 12.1, 12.3 | **12.3 ms** |
| AFTER (thin shim)     | 108   |  0.2,  0.2,  0.2 | **0.2 ms** |

Net AST-parse savings per reload: **~12.1 ms (98% reduction)**.

One-time deferred cost — first call to `load_car_generations()` on cold cache:

| State | JSON load (3 runs, ms) | Median |
| ----- | ---------------------- | ------ |
| AFTER (first call) | 3.9, 3.8, 3.7 | **3.8 ms** |

Subsequent calls are O(1) dict lookup (`@lru_cache(maxsize=1)` hits).

### Operator task for PR description (remaining)

Per plan D-28, record BEFORE vs AFTER cold-boot `uvicorn --reload` startup latency by:
1. `git checkout HEAD~1 -- backend/app/core/car_generations_data.py && rm backend/app/core/car_generations.py backend/app/core/car_generations_data.json` (restore BEFORE state)
2. Time 3 cold `uvicorn app.main:app --reload` runs from invocation to "Application startup complete" (record each real value)
3. Restore AFTER state, time 3 more runs
4. Add to PR description under "QUAL-01 startup latency" section. PR body MUST contain strings `Startup latency (before):` and `Startup latency (after):`, each followed by the 3 timings.

The AST-parse measurement above already provides quantitative evidence that the change reduces per-reload parse cost by ~12ms; the full uvicorn cold-boot timing is the final human-verified evidence gate.

## User Setup Required

None — this is a pure internal refactor. No env vars, no dashboard config.

## Next Phase Readiness

- **Fully independent of Plans 03-01/02/03/05** (Wave 1 parallel plan per plan frontmatter). No handoff required.
- **Pattern available for future large-literal extractions**: the `car_generations.py` + JSON + shim triplet is a reusable template for similar QUAL-xx items if other 1000+ line Python literals surface.
- **Post-merge task:** Record full uvicorn cold-boot BEFORE/AFTER median in PR description per Task 3 checkpoint.

## Self-Check: PASSED

- File `backend/app/core/car_generations.py` — FOUND
- File `backend/app/core/car_generations_data.json` — FOUND (352,511 bytes)
- File `backend/app/core/car_generations_data.py` — FOUND (108 lines; thin shim)
- File `backend/scripts/export_car_generations.py` — FOUND
- File `backend/tests/test_car_generations_loader.py` — FOUND (43 lines, 4 tests)
- Commit `e7b85e8` (test RED) — FOUND in git log
- Commit `e8e9179` (feat GREEN) — FOUND in git log
- Invariant `CAR_GENERATIONS is load_car_generations()` — verified via `python -c` and `test_shim_and_loader_agree`
- Existing caller test `test_init_cars_display_name.py` — 13/13 GREEN (no regression)
- Broader suite — 932/932 GREEN, 4 skipped (no regression)

---
*Phase: 03-non-breaking-internal-improvements*
*Completed: 2026-04-22*
