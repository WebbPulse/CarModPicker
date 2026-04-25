---
estimated_steps: 4
estimated_files: 2
skills_used:
  - test
---

# T04: Add backend/tests/crawlers/conftest.py with HTML-fixture loader and spec-payload factories

Create `backend/tests/crawlers/conftest.py` (it does not exist yet — verified). The conftest provides two reusable test utilities: (1) `load_fixture_html(adapter_slug: str, filename: str = 'product.html') -> str` — reads an HTML file from `backend/tests/crawlers/fixtures/<adapter_slug>/<filename>`. Existing fixtures live under that path (e.g., `fixtures/amsperformance/product.html`). The function takes a Path argument internally, opens UTF-8, returns the string. Raises FileNotFoundError with a clear message if the path is missing. IMPORTANT: only read paths under `backend/tests/crawlers/fixtures/` which is tracked in git — DO NOT plan or write any path under `.gsd/`, `.audits/`, or other gitignored directories. (2) A pytest fixture `make_scraped_payload(name='Test Part', product_url='https://example.com/p', specifications=None, **overrides) -> ScrapedPayload` — factory returning a ScrapedPayload with sensible defaults plus any field overrides; used by T05's contract tests so each assertion line stays focused on the scenario, not on payload boilerplate. Both helpers should be importable from `tests.crawlers.conftest` (they will be auto-discovered by pytest in this directory). Add a single tracked sample HTML fixture under `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html` containing a minimal product page (just a JSON-LD Product block) so the tests have something to point at without depending on the existing per-adapter fixtures (which can shift). Keep it under 2KB.

## Inputs

- ``backend/tests/crawlers/fixtures/amsperformance/product.html` — existing fixture pattern to mirror`
- ``backend/app/crawlers/base.py` — `ScrapedPayload` dataclass (extended in T02) for the factory`
- ``backend/tests/conftest.py` — top-level conftest for project-wide fixtures (do not modify; just confirm the import surface works)`

## Expected Output

- ``backend/tests/crawlers/conftest.py` — `load_fixture_html(adapter_slug, filename)` helper + `make_scraped_payload` pytest fixture`
- ``backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html` — small tracked HTML sample (<2KB) for spec contract tests`

## Verification

cd backend && pytest tests/crawlers/ -n auto --collect-only | head -20 && python -c "from pathlib import Path; p = Path('tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html'); assert p.exists() and p.stat().st_size > 0 and p.stat().st_size < 2048; print('ok')"

## Steps

1. Create `backend/tests/crawlers/conftest.py`. Implement `load_fixture_html(adapter_slug: str, filename: str = 'product.html') -> str` that reads from `Path(__file__).parent / "fixtures" / adapter_slug / filename`, opens UTF-8, returns the string. Raise `FileNotFoundError(f"Fixture not found: {path}")` with the resolved absolute path on miss.
2. Implement a `make_scraped_payload` pytest fixture returning a callable factory. Defaults: `name='Test Part'`, `product_url='https://example.com/p'`, `description=None`, `price_cents=None`, `part_manufacturer=None`, `part_number=None`, `image_urls=None`, `gtin=None`, `specifications=None`. Accept `**overrides` and merge into the constructor call. Return type is `ScrapedPayload`.
3. Create `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html` — a minimal HTML doc with a JSON-LD Product block (name, sku, brand, description, price). Keep it under 2KB. Mirror the shape used in `tests/crawlers/test_amsperformance_adapter.py::_product_page_html` for consistency.
4. Run `pytest tests/crawlers/ -n auto --collect-only` to confirm discovery and the verify size-check command.

## Must-Haves

- [ ] `backend/tests/crawlers/conftest.py` exists and is importable (pytest collects without errors).
- [ ] `load_fixture_html('amsperformance', 'product.html')` returns a non-empty string (existing fixture).
- [ ] `make_scraped_payload(specifications={'spring_rate_front': 600})` returns a ScrapedPayload with that field.
- [ ] `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html` exists, is under 2KB, contains a JSON-LD Product block.
- [ ] All fixture paths are under git-tracked directories — no reads/writes to `.gsd/`, `.audits/`, etc.

## Observability Impact

None — test infrastructure only.
