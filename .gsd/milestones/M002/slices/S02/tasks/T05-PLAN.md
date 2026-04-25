---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T05: Tests for universal extractor, suppression, slug bridge, and base-class hook + CLI demo script + demo subprocess test

Write the verification suite that proves S02's slice goal and produces the demo script. Four new test files plus one runnable CLI module, plus an extension to the existing ingest-validation test file.

**(1) `backend/tests/crawlers/test_universal_extractor.py`** — unit tests for the 5 extractors from T01. For each extractor, cover: high-confidence happy path (JSON-LD or labeled spec row), medium-confidence path (body text), low-confidence path where applicable, no-match returns None, malformed input returns None (empty string, None — should never raise), and unit normalization (kg→g, lb→g, oz→g for weight). Most extractor tests just call the functions directly with raw HTML strings. Add one ReDoS-resistance test: build a 100KB pathological string (long repeating digits, e.g. `'1' * 100_000`) and assert each extractor returns within 1 second wallclock. Use existing tracked fixture HTML from `tests/crawlers/fixtures/<adapter>/product.html` for at least 3 of the 5 extractors so tests prove the extractor works on real archived pages, not just hand-crafted strings.

**(2) `backend/tests/crawlers/test_universal_extraction_hook.py`** — base-class hook tests. (a) Construct a minimal test adapter that subclasses RetailerCrawlerAdapter, declares `category_targets=['coilover']`, and returns a fixed ScrapedPayload from parse_product_page. Call `adapter.apply_universal_extraction(html, payload)` with HTML that contains a labeled 'Weight: 25 lb' row; assert the returned payload's specifications dict has `weight_grams` set to ~11340 (25 lb in grams) and `weight_grams_confidence` set. (b) Suppression test: declare a second test adapter with `suppress_universal=['weight_grams']`; assert weight_grams is absent from specifications even though the HTML contains it. (c) Adapter-wins merge: declare an adapter that returns a payload with `specifications={'weight_grams': 999.0, 'weight_grams_confidence': 'high'}` and call the hook on HTML that contains different weight text — assert the adapter's value is preserved (hook merges only fields the adapter didn't set). (d) Empty-HTML safety: hook returns the payload unchanged when extract_universal_fields returns {}. (e) Validation gate at __init_subclass__: declaring an adapter with `suppress_universal=['not_a_real_field']` raises TypeError at class-definition time.

**(3) `backend/tests/crawlers/test_category_slug_bridge.py`** — `category_to_subslug` unit tests. Cover the mapping branches: `('suspension', name='ST X35 Coilovers')` → 'coilover'; `('brakes', name='Big Brake Kit')` → 'brake'; `('engine', name='K04 Turbo')` → 'turbo'; `('engine', name='Cold Air Intake')` → 'universal' (engine without turbo keyword); `('exhaust', name='Catback')` → 'universal' (no sub-slug for exhaust yet); `(None, ...)` → None. Confirm that the resolved slug, fed into `default_registry.resolve()`, returns a CategorySpec subclass for every non-None case.

**(4) Extend `backend/tests/crawlers/test_ingest_spec_validation.py`** — add a new test `test_ingest_uses_bridge_to_resolve_subslug` that calls ingest_payload with a coilover-keyword payload and asserts the validated specifications were validated against CoiloverSpec (not UniversalSpec) — proves the bridge fired in production. Keep all 7 existing tests passing; the registry save/restore fixture from S01 can stay unchanged for those tests.

**(5) `backend/app/crawlers/universal_extractor_demo.py`** — runnable CLI module. Top-level `if __name__ == '__main__':` block that, for each of the 5 tracked adapter fixtures (amsperformance, briantooleyracing, cobbtuning, subispeed, texasspeed): loads `tests/crawlers/fixtures/<adapter>/product.html`, instantiates the adapter (look up via `ADAPTER_REGISTRY` in `app/crawlers/adapters/__init__.py`), calls `adapter.parse_product_page(html, fixture_url)`, calls `adapter.apply_universal_extraction(html, payload)`, and prints a one-line summary: `<adapter_slug>: <field1>=<value> (<conf>), <field2>=<value> (<conf>), ...` (or `(no universal fields extracted)` when empty). `sys.exit(0)` on full success, `sys.exit(1)` on any exception. Path lookups use `pathlib.Path(__file__).resolve().parents[2] / 'tests' / 'crawlers' / 'fixtures'` — all under git-tracked paths.

**(6) Add `test_universal_extractor_demo_cli` test inside `test_universal_extractor.py`** — invokes the demo script via `subprocess.run(['python', '-m', 'app.crawlers.universal_extractor_demo'], cwd=str(Path(__file__).parents[2]), capture_output=True, check=False)` and asserts `result.returncode == 0` plus that stdout contains all 5 adapter slugs. Wrapping the CLI demo in a pytest test means the slice's verify command stays a single pytest invocation — no `&&` chaining (per MEM019: the gate splits on `&&`, breaking multi-command verifies).

All new test files run under the existing pytest -n auto convention.

## Inputs

- ``backend/app/crawlers/parsing.py` — extract_universal_fields and 5 extractors from T01`
- ``backend/app/crawlers/specs/base.py` — UniversalSpec field set from T02`
- ``backend/app/crawlers/specs/universal.py` — UniversalSpec model from T02`
- ``backend/app/crawlers/specs/category_bridge.py` — category_to_subslug from T03`
- ``backend/app/crawlers/adapters/base.py` — apply_universal_extraction + suppress_universal from T03`
- ``backend/app/crawlers/base.py` — bridge-aware ingest_payload from T03`
- ``backend/app/crawlers/runner.py` — wired call site from T04 (read-only confirmation)`
- ``backend/tests/crawlers/conftest.py` — load_fixture_html + make_scraped_payload helpers from S01/T04`
- ``backend/tests/crawlers/fixtures/amsperformance/product.html` — tracked fixture for demo + extractor tests`
- ``backend/tests/crawlers/fixtures/briantooleyracing/product.html` — tracked fixture for demo`
- ``backend/tests/crawlers/fixtures/cobbtuning/product.html` — tracked fixture for demo`
- ``backend/tests/crawlers/fixtures/subispeed/product.html` — tracked fixture for demo`
- ``backend/tests/crawlers/fixtures/texasspeed/product.html` — tracked fixture for demo`

## Expected Output

- ``backend/tests/crawlers/test_universal_extractor.py` — unit tests for 5 extractors with confidence + ReDoS guards + CLI subprocess demo test`
- ``backend/tests/crawlers/test_universal_extraction_hook.py` — base-class hook + suppression + adapter-wins merge tests`
- ``backend/tests/crawlers/test_category_slug_bridge.py` — sub-slug bridge mapping tests`
- ``backend/tests/crawlers/test_ingest_spec_validation.py` — extended with bridge-resolves-to-CoiloverSpec test`
- ``backend/app/crawlers/universal_extractor_demo.py` — runnable CLI module that demos extraction across 5 fixtures`

## Verification

pytest backend/tests/crawlers/test_universal_extractor.py backend/tests/crawlers/test_universal_extraction_hook.py backend/tests/crawlers/test_category_slug_bridge.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto -v --rootdir=backend

## Observability Impact

Demo script's stdout summary becomes the manual-inspection surface for tuning extractor confidence levels in S03 retrofit. Tests assert presence of T03's DEBUG log lines via caplog — ensures the per-field extraction trace stays observable when S03 starts retrofitting 108 adapters.
