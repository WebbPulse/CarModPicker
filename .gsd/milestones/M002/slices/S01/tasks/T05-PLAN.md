---
estimated_steps: 6
estimated_files: 2
skills_used:
  - test
  - tdd
---

# T05: Write three category-schema contract tests + ingest validation/rejection tests

Write the verification tests that prove the slice's success criteria. Create `backend/tests/crawlers/test_spec_registry_contract.py` with three test classes — one per concrete spec — each asserting: (a) `default_registry.resolve('<slug>')` returns the expected concrete class; (b) the class accepts a representative valid payload via `model_validate(...)`; (c) the class rejects a malformed payload (wrong type, unknown extra field per `extra='forbid'`, or out-of-range value where applicable) by raising `pydantic.ValidationError`. Also add a top-level test asserting `default_registry.resolve('unknown_slug') is None`. Then create `backend/tests/crawlers/test_ingest_spec_validation.py` with three integration tests using the existing test DB session fixture (look at `backend/tests/conftest.py` and existing crawler tests for the pattern — most use `db_session` or similar). Tests: (1) `test_ingest_accepts_valid_specifications` — call `ingest_payload` with a ScrapedPayload whose specifications match `CoiloverSpec`; assert `Part.specifications` equals the validated dict. (2) `test_ingest_drops_invalid_specifications_and_persists_part` — call `ingest_payload` with a malformed spec dict; assert the returned Part has `specifications is None` AND the part was successfully created. (3) `test_ingest_emits_extraction_failure_metric_on_invalid_spec` — patch `app.crawlers.base.emit_extraction_failure` (or the source in `cloudwatch_emf`) with a `MagicMock`, call ingest with a malformed spec; assert the mock was called once with the expected `adapter_name` kwarg. Use `make_scraped_payload` from T04's conftest. For the integration tests, the part must be created with a real category — use the suspension category seed (look up by slug or use whatever fixture pattern other ingest tests use). Run with `pytest -n auto` per the project convention. The whole file count: two new test files. No fixture changes beyond T04.

## Inputs

- ``backend/app/crawlers/specs/registry.py` — default_registry from T01`
- ``backend/app/crawlers/specs/coilover.py` — CoiloverSpec from T01`
- ``backend/app/crawlers/specs/brake.py` — BrakeSpec from T01`
- ``backend/app/crawlers/specs/turbo.py` — TurboSpec from T01`
- ``backend/app/crawlers/base.py` — ingest_payload (with validation hook from T03)`
- ``backend/app/core/cloudwatch_emf.py` — emit_extraction_failure (from T03) for mocking`
- ``backend/tests/crawlers/conftest.py` — make_scraped_payload + load_fixture_html (from T04)`
- ``backend/tests/conftest.py` — top-level db_session/test-user fixtures used by other ingest tests`

## Expected Output

- ``backend/tests/crawlers/test_spec_registry_contract.py` — 3 contract tests (one per category model) + unknown-slug resolution test`
- ``backend/tests/crawlers/test_ingest_spec_validation.py` — 3 integration tests covering valid passthrough, invalid drop-and-still-ingest, EMF metric emission on failure`

## Verification

cd backend && pytest tests/crawlers/test_spec_registry_contract.py tests/crawlers/test_ingest_spec_validation.py -n auto -v

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Test DB session fixture (name varies — check `backend/tests/conftest.py`) | If the fixture name expected by this test doesn't exist, the test errors at collection time — fix by reading the project's actual top-level conftest before writing. | N/A | N/A |
| `default_registry` import from T01 | If T01 isn't done, import fails — task is blocked, not failing. | N/A | N/A |
| `emit_extraction_failure` patch site | If the patch is applied at `app.core.cloudwatch_emf.emit_extraction_failure` instead of `app.crawlers.base.emit_extraction_failure`, the mock won't intercept (Python looks up the name at the call site). Patch at the import site in `app.crawlers.base`. | N/A | N/A |

## Negative Tests

- **Malformed inputs**: `{"unknown_field": 1}` (extra='forbid' rejection); `{"spring_rate_front": "not-a-number"}` (type coercion failure); `{"piston_count": -5}` if range constraints exist (boundary failure). Each must hit the drop-and-emit path.
- **Error paths**: Test that a `ValidationError` raised from inside `model_validate` does NOT propagate out of `ingest_payload` — the function still returns a Part. Test that an exception raised from a mocked `emit_extraction_failure` is caught upstream (failure-isolation regression test).
- **Boundary conditions**: `specifications={}` (empty dict) → all fields optional, validation succeeds, `Part.specifications == {}` (or whatever `model_dump(exclude_none=True)` returns for an empty model — assert the expected shape). `specifications=None` (no spec block) → no validation runs, `Part.specifications IS NULL`. Inferred category is None (e.g., "other") → no validation runs, specs pass through unchanged.

## Steps

1. Read `backend/tests/conftest.py` and one existing crawler-ingest test (e.g., `tests/crawlers/test_adro_adapter.py`) to identify the exact DB session fixture name and the test-user/category setup pattern.
2. Create `backend/tests/crawlers/test_spec_registry_contract.py` with a `TestCoiloverSpec`, `TestBrakeSpec`, `TestTurboSpec` class each asserting (a) registry resolution, (b) valid-payload acceptance, (c) malformed-payload rejection. Add a `test_unknown_slug_resolves_to_none` top-level test.
3. Create `backend/tests/crawlers/test_ingest_spec_validation.py` with `test_ingest_accepts_valid_specifications`, `test_ingest_drops_invalid_specifications_and_persists_part`, `test_ingest_emits_extraction_failure_metric_on_invalid_spec`. Look up the seeded `suspension` category by slug. Use `make_scraped_payload(specifications={...})` from T04's conftest. Inferred category should be 'coilover' or 'suspension' depending on `infer_category`'s behavior — check what slug `infer_category("Test Coilover", ...)` returns and align the test data so the registry actually attempts validation.
4. For the EMF emission test, patch with `monkeypatch.setattr("app.crawlers.base.emit_extraction_failure", mock_emitter)` (NOT at the cloudwatch_emf source — Python resolves the imported name at the call site).
5. Use `caplog` (pytest builtin) with `caplog.set_level(logging.WARNING)` to assert the structured WARN log fires on the validation-failure path. Assert the log message contains the adapter_name and category slug.
6. Run `pytest tests/crawlers/test_spec_registry_contract.py tests/crawlers/test_ingest_spec_validation.py -n auto -v` and confirm all six tests pass.

## Must-Haves

- [ ] `test_spec_registry_contract.py` has at least one valid + one malformed assertion per concrete spec class (coilover, brake, turbo) and a registry-miss test.
- [ ] `test_ingest_spec_validation.py` proves: (a) valid specs persist, (b) invalid specs drop AND part still persists, (c) `emit_extraction_failure` mock is called once with `adapter_name=...`.
- [ ] At least one test asserts the WARN log content via `caplog` (locks in failure-visibility contract for downstream slices).
- [ ] All six tests pass under `pytest -n auto`.
- [ ] No test reads from gitignored paths (`.gsd/`, `.audits/`, etc.) — fixtures are under `backend/tests/crawlers/fixtures/`.

## Observability Impact

Tests assert that the WARN log fires (caplog) and that the EMF metric emitter is called on validation failure. This locks in the failure-visibility contract for downstream slices.
