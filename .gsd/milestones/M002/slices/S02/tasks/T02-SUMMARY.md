---
id: T02
parent: S02
milestone: M002
key_files:
  - backend/app/crawlers/specs/base.py
  - backend/app/crawlers/specs/universal.py
  - backend/app/crawlers/specs/__init__.py
key_decisions:
  - Declared the universal value+confidence pairs on CategorySpec base rather than via metaclass/mixin — keeps schemas trivially readable and JSON-Schema-exportable per MEM014, and concrete subclasses inherit automatically with zero per-spec churn.
  - UniversalSpec adds no fields of its own — inheritance alone delivers the catch-all, and extra='forbid' carries through so unmapped-category extras still raise. This keeps the schema's surface area exactly equal to the universal extractor's output contract.
  - Kept registration in app/crawlers/specs/__init__.py (not the spec module) per MEM007 — preserves the side-effect-free spec-module convention so tests can construct an isolated SpecRegistry() without monkey-patching the global.
duration: 
verification_result: passed
completed_at: 2026-04-25T04:27:32.347Z
blocker_discovered: false
---

# T02: Add 5 universal value+confidence field pairs to CategorySpec and register UniversalSpec catch-all under 'universal' slug

**Add 5 universal value+confidence field pairs to CategorySpec and register UniversalSpec catch-all under 'universal' slug**

## What Happened

Extended `app/crawlers/specs/base.py` so `CategorySpec` declares the five universal value fields plus their paired `*_confidence` companions: `weight_grams`/`material`/`finish`/`warranty_days`/`fitment_notes`, each with `Optional[Literal['high','medium','low']]` confidence. Field shapes match T01's `extract_universal_fields()` return contract exactly. CoiloverSpec / BrakeSpec / TurboSpec inherit them automatically — no concrete-spec changes needed.

Created `app/crawlers/specs/universal.py` declaring `UniversalSpec(CategorySpec)` with no extra fields beyond the inherited universal set. The base's `ConfigDict(extra='forbid')` carries through, so an unmapped category that hands a `spring_rate_front` into a UniversalSpec validation still raises ValidationError — the catch-all only validates universal fields, not arbitrary keys.

Updated `app/crawlers/specs/__init__.py` to import `UniversalSpec`, register it under the `'universal'` slug in `default_registry`, and add it to `__all__`. Registration stays in `__init__.py` per MEM007 (spec modules remain side-effect-free so isolated imports and fresh `SpecRegistry()` instances in tests work cleanly).

Updated the `base.py` module docstring to document the inheritance contract: subclasses only declare category-specific fields; the five universal fields and the UniversalSpec catch-all together let the T03 bridge fall through to a validated extraction path for unmapped categories instead of silently dropping the spec block.

No changes to `test_spec_registry_contract.py` were needed — its assertions don't pin the field set via reflection or schema introspection, so the 16 existing contract tests passed unmodified. The 7 ingest-validation tests also passed without modification: `test_unregistered_slug_passes_through_unchanged` seeds a `'wheels'` category which still resolves to `None` (the bridge that would route it to `'universal'` is T03's job, not T02's).

## Verification

Ran the T02 verify command exactly as written in the task plan: `pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=backend` → 23 passed in 9.13s. Ran the full crawler suite to check for regressions from extra='forbid' surfacing on existing test payloads: `pytest backend/tests/crawlers/ -n auto --rootdir=backend` → 1284 passed, 1 skipped in 11.11s. Pyright on the three touched files: 0 errors. Smoke-script (deleted post-run) confirmed: (a) `default_registry.resolve('universal')` returns `UniversalSpec`; (b) `default_registry.resolve('coilover')` still returns `CoiloverSpec`; (c) `default_registry.resolve('unknown_xyz')` returns `None`; (d) UniversalSpec validates the five universal fields end-to-end and rejects category-specific extras like `spring_rate_front` via extra='forbid'; (e) CoiloverSpec inherits universal fields cleanly (e.g. accepts `weight_grams=5000.0` alongside `spring_rate_front`); (f) confidence Literal validation still rejects values like `'extreme'`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=backend` | 0 | ✅ pass | 9130ms |
| 2 | `pytest backend/tests/crawlers/ -n auto --rootdir=backend (full crawler suite regression check)` | 0 | ✅ pass | 11110ms |
| 3 | `pyright backend/app/crawlers/specs/base.py backend/app/crawlers/specs/universal.py backend/app/crawlers/specs/__init__.py` | 0 | ✅ pass | 3000ms |
| 4 | `python backend/_smoke_t02.py (UniversalSpec resolve + inheritance + extra='forbid' smoke)` | 0 | ✅ pass | 150ms |

## Deviations

None — implementation followed the task plan exactly. Five value+confidence pairs added to CategorySpec, UniversalSpec catch-all created in a new file, registered under 'universal', __all__ updated, no concrete-spec changes needed.

## Known Issues

None for this task. Downstream work as designed: T03 wires the infer_category() → sub-slug bridge so the validation hook actually fires in production (and routes unmapped categories to 'universal'); T04 inserts apply_universal_extraction at the runner / archive_rescrape / extension-scrape call sites; T05 ships the dedicated unit tests against tracked fixture HTML.

## Files Created/Modified

- `backend/app/crawlers/specs/base.py`
- `backend/app/crawlers/specs/universal.py`
- `backend/app/crawlers/specs/__init__.py`
