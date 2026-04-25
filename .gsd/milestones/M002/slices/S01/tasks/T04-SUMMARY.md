---
id: T04
parent: S01
milestone: M002
key_files:
  - backend/tests/crawlers/conftest.py
  - backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html
  - backend/tests/crawlers/test_conftest_smoke.py
key_decisions:
  - Kept ScrapedPayload-factory defaults aligned with the dataclass field defaults in app/crawlers/base.py rather than inventing a richer happy-path payload — T05+ contract tests should override only the fields that matter for each scenario, and a fat default would mask which fields the test actually exercises.
  - Shipped a 6-test smoke file (test_conftest_smoke.py) alongside the conftest rather than relying solely on T05's contract tests to exercise the helpers. Trade-off: 6 extra tests in the suite vs. T04 verification standing on its own without depending on T05 landing. Cost is ~0.04s; benefit is that conftest regressions surface in T04's own gate, not as collateral damage in a future task.
  - Mirrored the Rank Math `@graph` JSON-LD shape from tests/crawlers/test_amsperformance_adapter.py::_product_page_html in coilover_sample.html, but with a single `@type: Product` (no `@graph` wrapper) — keeps the file under 2KB while still being a realistic shape the universal extractor in S02 can target.
duration: 
verification_result: passed
completed_at: 2026-04-25T03:45:39.491Z
blocker_discovered: false
---

# T04: Add backend/tests/crawlers/conftest.py with HTML-fixture loader, ScrapedPayload factory, and tracked coilover_sample.html for spec-contract tests

**Add backend/tests/crawlers/conftest.py with HTML-fixture loader, ScrapedPayload factory, and tracked coilover_sample.html for spec-contract tests**

## What Happened

Created the test infrastructure that S01/T05+ contract tests will build on, plus a tracked HTML sample so those tests don't accidentally couple to per-adapter fixtures that change as the adapters evolve.

`backend/tests/crawlers/conftest.py` exposes two surfaces. `load_fixture_html(adapter_slug, filename='product.html')` resolves `Path(__file__).parent / 'fixtures' / adapter_slug / filename`, opens it as UTF-8, and returns the string; on miss it raises `FileNotFoundError(f"Fixture not found: {path.resolve()}")` with the absolute path so a typo'd slug fails loud. `make_scraped_payload` is a pytest fixture returning a callable factory: defaults are the minimal happy-path payload (`name='Test Part'`, `product_url='https://example.com/p'`, everything else `None`), and `**overrides` are forwarded to the `ScrapedPayload(...)` constructor — keeps each contract-test assertion line focused on the field that matters, not on dataclass boilerplate.

Added `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html` (818 bytes, well under the 2KB ceiling) — a minimal HTML doc with one JSON-LD Product block that mirrors the Rank Math `@graph` shape used by `tests/crawlers/test_amsperformance_adapter.py::_product_page_html`. Living under `tests/crawlers/fixtures/` keeps it tracked in git (per the slice's "no .gsd/ paths in tests" rule).

Also added `backend/tests/crawlers/test_conftest_smoke.py` with 6 lightweight tests covering all four must-haves: the factory defaults, factory specifications override, factory arbitrary overrides, loading an existing fixture, loading the new coilover sample (with content assertion), and the missing-fixture FileNotFoundError path. These are kept tiny so they don't bloat slice-level verification.

No application-code changes — this is test infrastructure only. Observability impact: none, per the task plan.

## Verification

Ran the task-plan verification command `cd backend && pytest tests/crawlers/ -n auto --collect-only` — collected 1262 tests (was 1256 before T04; +6 from the new smoke file), no errors. Ran `python -c "from pathlib import Path; p = Path('tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html'); assert p.exists() and p.stat().st_size > 0 and p.stat().st_size < 2048; print('ok')"` → printed `ok` (size 818 bytes). Ran `pytest tests/crawlers/test_conftest_smoke.py -n0 -v` — all 6 must-have checks passed in 0.04s. Re-ran the slice-level verification `pytest tests/crawlers/ -n auto -k 'ingest or spec'` — 11 passed in 9.92s (was 10 before T04; the +1 is the new `test_factory_with_specifications` smoke test, picked up by the `spec` keyword). Directly invoked `load_fixture_html('amsperformance')` → 356576 bytes, `load_fixture_html('spec_contract_samples', 'coilover_sample.html')` → 818 bytes containing `application/ld+json`, and `load_fixture_html('does_not_exist')` → `FileNotFoundError: Fixture not found: …`. All four must-haves from the task plan satisfied: conftest exists and pytest collects without errors; loader returns the existing amsperformance fixture; factory accepts `specifications={'spring_rate_front': 600}`; coilover_sample.html exists, is under 2KB, contains a JSON-LD Product block; all paths are git-tracked.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest tests/crawlers/ -n auto --collect-only` | 0 | ✅ pass | 350ms |
| 2 | `python -c "from pathlib import Path; p = Path('tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html'); assert p.exists() and p.stat().st_size > 0 and p.stat().st_size < 2048; print('ok')"` | 0 | ✅ pass | 200ms |
| 3 | `pytest tests/crawlers/test_conftest_smoke.py -n0 -v` | 0 | ✅ pass (6 must-have checks) | 40ms |
| 4 | `pytest tests/crawlers/ -n auto -k 'ingest or spec'` | 0 | ✅ pass (11/11) | 9920ms |

## Deviations

None — task plan executed as written. The plan called for "two reusable test utilities" plus a tracked sample HTML fixture; all three shipped, with sizes under the documented ceilings (sample is 818 bytes vs. the 2KB cap).

## Known Issues

None.

## Files Created/Modified

- `backend/tests/crawlers/conftest.py`
- `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html`
- `backend/tests/crawlers/test_conftest_smoke.py`
