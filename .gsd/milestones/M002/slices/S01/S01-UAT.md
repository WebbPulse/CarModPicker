# S01: Schema contract + crawler test infrastructure — UAT

**Milestone:** M002
**Written:** 2026-04-25T04:01:34.373Z

## UAT for S01: Schema contract + crawler test infrastructure

**Scope:** No human UAT required (slice plan: "Human/UAT required: no"). This UAT is a developer-runnable verification script that proves every must-have signal from the slice plan and S01's contract surface for downstream consumers.

### Preconditions

1. Repo at HEAD on the S01-completion commit, working directory `/home/tyler-webb/Documents/Github/CarModPicker`.
2. Python 3.13 + project deps installed in the active venv (`pip install -e backend/.[test]` or equivalent).
3. No external services required — tests use SQLite in-memory and mock the EMF emitter.

### Test Cases

#### TC1 — Slice demo command passes

**Steps:**
1. From repo root, run: `pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto -v --rootdir=backend`

**Expected:**
- Exit code 0.
- 23 tests pass.
- Output ends with: `============================== 23 passed in <X.XX>s ==============================`.

#### TC2 — SpecRegistry resolves the three concrete category models by slug

**Steps:**
1. From `backend/`, run:
   ```
   TESTING=true python -c "from app.crawlers.specs import default_registry; from app.crawlers.specs.coilover import CoiloverSpec; from app.crawlers.specs.brake import BrakeSpec; from app.crawlers.specs.turbo import TurboSpec; assert default_registry.resolve('coilover') is CoiloverSpec; assert default_registry.resolve('brake') is BrakeSpec; assert default_registry.resolve('turbo') is TurboSpec; assert default_registry.resolve('unknown_slug') is None; print('ok')"
   ```

**Expected:** Prints `ok`. Exit 0. Slugs (not UUIDs) are the registry key.

#### TC3 — CategorySpec rejects unknown fields (extra='forbid')

**Steps:**
1. From `backend/`, run:
   ```
   TESTING=true python -c "from app.crawlers.specs.coilover import CoiloverSpec; import pydantic; raised=False
   try: CoiloverSpec(unknown_field=1)
   except pydantic.ValidationError: raised=True
   assert raised; print('ok')"
   ```

**Expected:** Prints `ok`. Exit 0.

#### TC4 — Adapter base validates category_targets at import time

**Steps:**
1. Define a temporary adapter subclass with `category_targets = ['nonsense_slug']`.
2. Importing it should raise `TypeError` whose message contains both the adapter qualname and the bad slug.
3. Defining one with `category_targets = ['']` (empty string) should raise `TypeError` with the "non-empty string" branch.
4. Defining one with `category_targets = ['coilover']` should succeed silently.

**Expected:** All three branches behave per spec. (Covered by T02's extended verification.)

#### TC5 — Ingest accepts a valid spec block and persists it

**Steps:**
1. Run: `pytest backend/tests/crawlers/test_ingest_spec_validation.py::TestIngestAcceptsValidSpecifications::test_ingest_persists_validated_specifications -n0 -v --rootdir=backend`

**Expected:** 1 passed. The created Part's `specifications` equals the validated dict (`{'spring_rate_front': 600.0, 'height_adjustable': True}` shape).

#### TC6 — Ingest drops malformed spec block, ingests Part with specifications=None, logs WARN

**Steps:**
1. Run: `pytest backend/tests/crawlers/test_ingest_spec_validation.py::TestIngestDropsInvalidSpecifications -n0 -v --rootdir=backend`

**Expected:**
- 2 passed (`test_invalid_specs_drop_to_none_and_part_persists`, `test_type_coercion_failure_drops_to_none`).
- caplog assertion confirms WARN line contains `bad_adapter` (adapter_name) and `suspension` (resolved category slug). Locks in S04's failure-visibility contract.

#### TC7 — Ingest emits ExtractionFailureRate metric on validation failure

**Steps:**
1. Run: `pytest backend/tests/crawlers/test_ingest_spec_validation.py::TestIngestEmitsExtractionFailureMetric::test_emit_extraction_failure_called_once_on_invalid_specs -n0 -v --rootdir=backend`

**Expected:** 1 passed. Mock at `app.crawlers.base.emit_extraction_failure` called exactly once with `adapter_name="metric_adapter"`.

#### TC8 — Pass-through boundary cases keep legacy adapters working

**Steps:**
1. Run: `pytest backend/tests/crawlers/test_ingest_spec_validation.py::TestIngestPassThroughCases -n0 -v --rootdir=backend`

**Expected:**
- 2 passed.
- `test_no_spec_block_passes_through_as_none`: ingest of a payload with `specifications=None` results in Part with `specifications=None`, no emitter call.
- `test_unregistered_slug_passes_through_unchanged`: ingest of a payload whose inferred slug has no registered model passes specs through unchanged, no emitter call.

#### TC9 — Conftest test infrastructure is discoverable

**Steps:**
1. Run: `pytest backend/tests/crawlers/test_conftest_smoke.py -n0 -v --rootdir=backend`

**Expected:** 6 passed. `load_fixture_html` returns content for an existing slug, raises FileNotFoundError for a missing one. `make_scraped_payload` factory accepts arbitrary overrides including `specifications`.

#### TC10 — Full crawler suite is green (no regression in any of the 108 adapters)

**Steps:**
1. Run: `pytest backend/tests/crawlers/ -n auto --rootdir=backend`

**Expected:**
- Exit code 0.
- Last line: `1284 passed, 1 skipped in <X.XX>s`.
- All 5 characterization tests (amsperformance, briantooleyracing, cobbtuning, subispeed, texasspeed) pass — snapshots updated to include `"specifications": null`.

#### TC11 — Full backend suite is green

**Steps:**
1. Run: `pytest backend/tests/ -n auto --rootdir=backend -q`

**Expected:** 2409 passed, 9 skipped. No new failures introduced by S01.

### Edge Cases Verified

- Empty spec dict `{}` is valid for any CategorySpec (all fields Optional) — covered by `TestCoiloverSpec::test_accepts_empty_payload`.
- ConfigDict(extra='forbid') correctly rejects unknown fields per spec — covered by all three `test_rejects_unknown_field_extra_forbid`.
- Adapter that inherits the empty default `category_targets = []` (the 108-adapter case) imports without triggering any registry lookup — verified via `tests/crawlers/test_adapter_discovery.py` (4 passed).
- `emit_extraction_failure` is silent in TESTING/dev environments and never raises (failure-isolation matches `emit_crawler_run_metrics`).
- Save/restore fixture `coilover_under_suspension` is sentinel-checked so a panicked test exit cannot leave stale registry state across the suite.

### Sign-off

- [x] All 11 test cases pass.
- [x] Slice demo (`pytest backend/tests/crawlers/ -n auto`) green.
- [x] No regression in full backend suite (2409 passed, 9 skipped).
- [x] R001 marked validated. R004 marked validated.
- [x] S02-S04 unblocked (consumes SpecRegistry, category_targets, ingest hook, conftest).
