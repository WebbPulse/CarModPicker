# S02: Universal-field extractor + base-class auto-run — UAT

**Milestone:** M002
**Written:** 2026-04-25T04:52:45.610Z

# S02 UAT — Universal-field extractor + base-class auto-run

## Preconditions

- Repo at HEAD with S02 changes merged.
- Working directory: `backend/`.
- Python 3.13 env active with backend deps installed (no Postgres or Docker required — tests use SQLite in-memory; demo reads tracked fixture HTML from `tests/crawlers/fixtures/`).
- No external network access required.

## UAT-1 — CLI demo against 5 archived adapter fixtures (slice plan's primary demo)

**Steps:**

1. From `backend/`, run: `python -m app.crawlers.universal_extractor_demo`
2. Inspect stdout.
3. Inspect exit code: `echo $?`

**Expected:**

- Exit code is `0`.
- Stdout contains exactly 5 lines, one per adapter slug, in order: `amsperformance`, `briantooleyracing`, `cobbtuning`, `subispeed`, `texasspeed`.
- `amsperformance` line shows at least `weight_grams=907.2 (high)` (real archived weight: 2 lb → 907.2 g, high confidence from the labeled spec row) plus a `fitment_notes=...` (medium) entry.
- `subispeed` line shows `material=carbon fiber (low)` (canonicalized from "carbon-fiber" in body text).
- The other three (`briantooleyracing`, `cobbtuning`, `texasspeed`) print the sentinel `(parse_product_page returned None)` — known parser-coverage gap on those archived snapshots, NOT an extractor failure.
- No exceptions, no traceback in stderr.

**Edge case:** If you delete a tracked `tests/crawlers/fixtures/<adapter>/product.html` and re-run, the demo prints `(fixture missing)` and still exits 0 (the wrapper `subprocess.run` test does not require every adapter to find its fixture, only that all 5 slugs appear in stdout).

## UAT-2 — Suppression contract (slice plan's second demo requirement)

**Steps:**

1. Run: `pytest tests/crawlers/test_universal_extraction_hook.py::TestApplyUniversalExtractionSuppression -n auto --rootdir=. -v`
2. Run: `pytest tests/crawlers/test_universal_extraction_hook.py::TestSuppressUniversalValidationGate -n auto --rootdir=. -v`

**Expected:**

- Both class-level test groups pass.
- `test_suppressed_field_is_absent_from_specifications`: a test adapter declares `suppress_universal=['weight_grams']`; the hook is fed HTML containing `'Weight: 25 lb'`; the returned payload's `specifications` dict does NOT contain `weight_grams` and does NOT contain `weight_grams_confidence`. Other universal fields present in the HTML (e.g. `material`, `finish`) still merge.
- `test_unknown_field_in_suppress_universal_raises_at_class_creation`: declaring an adapter subclass with `suppress_universal=['not_a_real_field']` raises `TypeError` at class-definition time; the error message names the offending adapter qualname.
- `test_suppress_universal_rejects_non_list_value` and `test_suppress_universal_rejects_non_string_entry`: structural validation gate also rejects malformed shapes (string instead of list, int entry).

## UAT-3 — Auto-extraction merges into specifications with adapter-wins semantics

**Steps:**

1. Run: `pytest tests/crawlers/test_universal_extraction_hook.py::TestApplyUniversalExtractionAutoExtracts -n auto --rootdir=. -v`
2. Run: `pytest tests/crawlers/test_universal_extraction_hook.py::TestApplyUniversalExtractionAdapterWins -n auto --rootdir=. -v`
3. Run: `pytest tests/crawlers/test_universal_extraction_hook.py::TestApplyUniversalExtractionEmptyInputs -n auto --rootdir=. -v`

**Expected:**

- All 7 tests pass.
- `test_labeled_weight_lands_in_specifications`: HTML with `'Weight: 25 lb'` produces `specifications['weight_grams']` ≈ 11340.0 with `weight_grams_confidence` set to a Literal value.
- `test_debug_log_emitted_per_extracted_field`: caplog captures one `universal_extraction: adapter=X field=... confidence=...` DEBUG line per merged field.
- `test_adapter_set_value_is_preserved`: an adapter pre-populates `specifications={'weight_grams': 999.0, 'weight_grams_confidence': 'high'}`; hook is fed HTML with conflicting weight; resulting payload preserves the adapter's 999.0 (universal layer is a floor, not a ceiling).
- `test_unset_universal_fields_still_fill_in`: even when one universal field is adapter-set, the other four still merge.
- `test_payload_none_is_a_noop` / `test_empty_html_leaves_payload_unchanged` / `test_html_without_universal_signals_leaves_payload_unchanged` / `test_null_specifications_become_dict_when_extraction_fires`: empty-input safety contracts hold.

## UAT-4 — Category bridge resolves DB category names to registry slugs

**Steps:**

1. Run: `pytest tests/crawlers/test_category_slug_bridge.py -n auto --rootdir=. -v`

**Expected:**

- All bridge tests pass.
- `('suspension', name='ST X35 Coilovers')` → `'coilover'`.
- `('brakes', name='Big Brake Kit')` → `'brake'` (always — no keyword check needed for brakes).
- `('engine', name='K04 Turbo')` → `'turbo'`.
- `('engine', name='Cold Air Intake')` → `'universal'` (engine without turbo keyword).
- `('exhaust', name='Catback')` → `'universal'` (no sub-slug for exhaust yet).
- `('wheels', ...)` → `'universal'` (single fallback for unmapped categories).
- `(None, ...)` → `None` (preserves S01 pass-through).
- Parametrized round-trip test confirms every non-None bridge result resolves to a CategorySpec subclass via `default_registry.resolve()`.

## UAT-5 — Ingest validation hook fires in production via the bridge

**Steps:**

1. Run: `pytest tests/crawlers/test_ingest_spec_validation.py::TestIngestUsesBridgeToResolveSubslug -n auto --rootdir=. -v`
2. Run: `pytest tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=. -v`

**Expected:**

- All 9+ ingest validation tests pass.
- Coilover-keyword payload validates against `CoiloverSpec` (proves the bridge resolves to the category-specific schema, not the universal fallback).
- A wheels-categorized payload with a coilover-spec field (e.g. `spring_rate_front`) drops to `specifications=None` and increments `ExtractionFailureRate` (proves wheels routes to UniversalSpec, which `extra='forbid'`s the category-specific extra).
- A pure universal-fields payload on a wheels category validates and persists (UniversalSpec accepts the universal field set).
- A None-category payload preserves S01's pass-through (no validation, payload persists unchanged).
- WARN log on validation failure includes both the inferred DB category AND the bridged sub-slug.

## UAT-6 — ReDoS budget on 100KB pathological input

**Steps:**

1. Run: `pytest tests/crawlers/test_universal_extractor.py -k ReDoS -n auto --rootdir=. -v`

**Expected:**

- Each per-extractor test completes in under 1 second on a 100K-char digit pile (`'1' * 100_000`).
- The aggregator test completes in under 5 seconds.
- No test reports an extractor returning a value (all should return None on the pathological input).
- No exceptions, no hangs.

## UAT-7 — Full S02 verify line + full crawler suite regression

**Steps:**

1. Run the slice verify line: `pytest tests/crawlers/test_universal_extractor.py tests/crawlers/test_universal_extraction_hook.py tests/crawlers/test_category_slug_bridge.py tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=. -v`
2. Run the full crawler suite: `pytest tests/crawlers/ -n auto --rootdir=. --no-cov -q`

**Expected:**

- Step 1: 86 passed (no failures, no errors).
- Step 2: 1364 passed, 1 skipped (the skip is the postgres-only test from S01; not an S02 regression).
- Total wallclock: well under 30 seconds for both runs combined.
- No new warnings, no `extra='forbid'` failures on existing test payloads.

## UAT-8 — Three call-site insertions sit in correct positions

**Steps:**

1. `grep -n 'apply_universal_extraction' backend/app/crawlers/runner.py backend/app/crawlers/archive_rescrape.py backend/app/api/endpoints/crawled_pages.py`

**Expected:**

- One match per file (no duplicates).
- `runner.py` match is positioned AFTER the None-skip branch (`if payload is None: ... continue`) and BEFORE archive + `ingest_payload`.
- `archive_rescrape.py` match is positioned AFTER the None-skip + `parse_status='failed'` branch and BEFORE the existing `try: ingest_payload(...)`.
- `crawled_pages.py` match uses `sanitized_html` (not the raw uploaded body) and is on the success path AFTER the None-skip ScrapeResponse short-circuit.
- All three call sites use the reflexive shape: `payload = adapter.apply_universal_extraction(html, payload)`.

## Pass criteria

UAT passes if and only if **all 8** UAT cases produce the expected outcomes with no exceptions, no test failures, and no fixture drift. Specifically:

- Real extraction signal observed on at least one of the 5 archived fixtures (amsperformance weight is the canary).
- Suppression mechanism demonstrably blocks extraction for the named field at the named adapter.
- Ingest validation hook fires in production: the bridge resolves real DB category names to CategorySpec subclasses (not just a stub) and `ExtractionFailureRate` increments on UniversalSpec validation failure for wheels-with-coilover-fields payloads.
- 86/86 slice-prescribed tests pass; 1364/1365 full crawler suite passes (1 postgres-only skip).
- ReDoS budget held on 100KB pathological input.
