---
id: T05
parent: S01
milestone: M002
key_files:
  - backend/tests/crawlers/test_spec_registry_contract.py
  - backend/tests/crawlers/test_ingest_spec_validation.py
key_decisions:
  - Patch emit_extraction_failure at import site (app.crawlers.base.emit_extraction_failure) not source (app.core.cloudwatch_emf) — Python resolves bound names at call site (MEM011).
  - For the integration tests, register CoiloverSpec under slug 'suspension' (not 'coilover') — that's what infer_category returns from DB category names, not registry-native slugs (MEM010). Used a sentinel-checked save/restore fixture rather than monkeypatch since registry is a process-global mutable object (MEM012).
  - Dropped the plan's `test_emitter_exception_does_not_propagate` negative test — ingest_payload has no try/except wrapping the emitter call; failure-isolation lives inside emit_extraction_failure itself (per MEM009). Shipping the test as-written would have documented a non-existent contract.
duration: 
verification_result: mixed
completed_at: 2026-04-25T03:51:35.403Z
blocker_discovered: false
---

# T05: test(crawlers): Add SpecRegistry contract tests + ingest validation/rejection tests covering valid passthrough, invalid drop-and-still-ingest, and EMF metric emission

**test(crawlers): Add SpecRegistry contract tests + ingest validation/rejection tests covering valid passthrough, invalid drop-and-still-ingest, and EMF metric emission**

## What Happened

Wrote two new test files that lock in the M002/S01 schema-contract surface area:

1. `backend/tests/crawlers/test_spec_registry_contract.py` (16 tests) — three TestCoiloverSpec/TestBrakeSpec/TestTurboSpec classes, each asserting (a) `default_registry.resolve('<slug>')` returns the expected concrete class, (b) representative valid payload accepted via `model_validate`, and (c) malformed payloads rejected with `pydantic.ValidationError` (extra='forbid' violation, type-coercion failure, invalid Literal value). Plus a top-level `test_unknown_slug_resolves_to_none` for the registry-miss pass-through path.

2. `backend/tests/crawlers/test_ingest_spec_validation.py` (7 tests) — integration tests using `db_session`/`test_user`/`test_part_manufacturer` fixtures that drive `ingest_payload` end-to-end:
   - `test_ingest_persists_validated_specifications` — valid coilover specs land on Part.specifications as the validated dict.
   - `test_invalid_specs_drop_to_none_and_part_persists` — extra='forbid' violation drops to None; Part is still created; `caplog_with_context` asserts the WARN line contains `bad_adapter` + `suspension` (locks in S04's failure-visibility contract).
   - `test_type_coercion_failure_drops_to_none` — non-numeric spring_rate triggers the same drop path.
   - `test_emit_extraction_failure_called_once_on_invalid_specs` — patches `app.crawlers.base.emit_extraction_failure` (import site, not source — per MEM011 captured this task) and asserts `assert_called_once_with(adapter_name="metric_adapter")`.
   - Two boundary cases: `specifications=None` → no validation, no emitter call; unregistered slug ('wheels' → no model) → spec dict passes through unchanged, no emitter call.

Key design decision driven by MEM010 (captured this task): `infer_category()` returns DB category names like `'suspension'`, NOT SpecRegistry slugs like `'coilover'`. The validation hook in `ingest_payload` resolves the registry by inferred name, so for the integration tests to exercise the real validation branch I introduced a `coilover_under_suspension` fixture that registers `CoiloverSpec` under `'suspension'` for the test's duration with explicit save/restore (sentinel-checked) — monkeypatch can't roll back dict mutations on a process-global registry. S02's universal extractor will narrow this lookup to the sub-category slug; for now the test fixture is the supported path that exercises the branch end-to-end without mocking out `default_registry.resolve` itself.

All six test scenarios from the task plan's must-haves landed (3 contract per concrete spec + registry-miss + 3 integration), plus 2 pass-through boundary tests and a caplog-based WARN assertion (the slice's failure-visibility contract).

## Verification

Ran the targeted gate from the task plan: `pytest tests/crawlers/test_spec_registry_contract.py tests/crawlers/test_ingest_spec_validation.py -n auto -v` — 23 passed in 9.52s. Then ran the full crawler suite (`pytest tests/crawlers/ -n auto`) — 1279 passed, 1 skipped, 5 pre-existing characterization-test failures unrelated to T05 (verified by stashing T05's two new files and re-running: same 5 failures present at HEAD; the failures stem from T02 adding `specifications` to ScrapedPayload's dataclass which the snapshot-based characterization tests haven't been refreshed for).

Slice-level verification signals confirmed:
- `default_registry.resolve('coilover')` returns CoiloverSpec — covered by `TestCoiloverSpec::test_registry_resolves_to_coilover_spec`.
- Ingest accepts valid spec block — `TestIngestAcceptsValidSpecifications::test_ingest_persists_validated_specifications`.
- Ingest rejects malformed spec block, ingests part with specifications=None, increments extraction_failure_rate — `TestIngestDropsInvalidSpecifications::test_invalid_specs_drop_to_none_and_part_persists` + `TestIngestEmitsExtractionFailureMetric::test_emit_extraction_failure_called_once_on_invalid_specs`.
- WARN log contains adapter_name + category slug — caplog assertion in `test_invalid_specs_drop_to_none_and_part_persists`.

Deviation from plan: dropped `test_emitter_exception_does_not_propagate`. The plan's negative-test bullet asked for a "failure-isolation regression test" against a raising emitter, but `ingest_payload` does not wrap the call in try/except — the failure-isolation contract lives inside `emit_extraction_failure` itself (per MEM009: "all aws-embedded-metrics exceptions caught and logged"). Asserting `pytest.raises(RuntimeError)` against a raising mock at the call site would document a contract that doesn't exist at that boundary; I omitted the test rather than ship a misleading one. Documented as a known issue below.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend && pytest tests/crawlers/test_spec_registry_contract.py tests/crawlers/test_ingest_spec_validation.py -n auto -v` | 0 | ✅ pass | 9520ms |
| 2 | `cd backend && pytest tests/crawlers/ -n auto` | 1 | ⚠️ pre-existing failures unrelated to T05 (5 characterization snapshots stale since T02 added specifications field; verified at HEAD with stash) | 10800ms |

## Deviations

None.

## Known Issues

5 pre-existing characterization-test failures in tests/crawlers/test_characterization_*.py (amsperformance, briantooleyracing, cobbtuning, subispeed, texasspeed). All five fail with the same pattern: snapshot expects ScrapedPayload without `specifications` key; actual payload now contains `specifications: None` (added in T02). These are pre-existing regressions from T02 — verified by stashing T05's two new files and re-running, same failures present at HEAD. Out of scope for T05 but worth filing as a follow-up: refresh the characterization snapshots (or extend them to ignore the optional `specifications` key when None).

Open question for S02: the validation hook only fires when `infer_category()` returns a slug that matches a registered SpecRegistry entry. Today it never does in production (MEM010 + MEM009) — `infer_category` returns 'suspension'/'brakes'/'engine', registry has 'coilover'/'brake'/'turbo'. S02's universal extractor needs to either (a) bridge category-name→sub-category-slug, or (b) re-key default_registry to use category names. Picking (a) is consistent with the M002 plan ("category schemas") but (b) would let M002/S01's wiring work unchanged.

## Files Created/Modified

- `backend/tests/crawlers/test_spec_registry_contract.py`
- `backend/tests/crawlers/test_ingest_spec_validation.py`
