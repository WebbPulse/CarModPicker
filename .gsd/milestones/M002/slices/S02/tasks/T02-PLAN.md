---
estimated_steps: 11
estimated_files: 4
skills_used: []
---

# T02: Add universal fields to CategorySpec base + UniversalSpec catch-all

Make universal-extracted fields validate cleanly against the existing CategorySpec schemas. The existing `CategorySpec(BaseModel)` in `backend/app/crawlers/specs/base.py` uses `ConfigDict(extra='forbid')`, so universal fields must be declared on the schema or validation will reject them.

Approach: define the five universal value-fields plus their paired `_confidence` companions on the `CategorySpec` base itself, so every concrete spec inherits them automatically. Field shapes (matching T01's return contract):
- `weight_grams: Optional[float] = None` + `weight_grams_confidence: Optional[Literal['high','medium','low']] = None`
- `material: Optional[str] = None` + `material_confidence: Optional[Literal['high','medium','low']] = None`
- `finish: Optional[str] = None` + `finish_confidence: Optional[Literal['high','medium','low']] = None`
- `warranty_days: Optional[float] = None` + `warranty_days_confidence: Optional[Literal['high','medium','low']] = None`
- `fitment_notes: Optional[str] = None` + `fitment_notes_confidence: Optional[Literal['high','medium','low']] = None`

Update the module docstring of `base.py` to document that the 5 universal fields are inherited and that subclasses only need to add category-specific fields. CoiloverSpec / BrakeSpec / TurboSpec concrete specs need NO field changes — they automatically gain the universal fields via inheritance.

Also add a `UniversalSpec(CategorySpec)` concrete subclass in a new file `backend/app/crawlers/specs/universal.py` — declares no extra fields beyond the inherited universal set. Register it in `app/crawlers/specs/__init__.py`: `default_registry.register('universal', UniversalSpec)`. The T03 bridge will resolve unmapped categories to 'universal' so an unknown category with universal fields can still ingest a validated specs block instead of silently dropping.

Update `__init__.py`'s `__all__` list to include `UniversalSpec` and import it.

Update `backend/tests/crawlers/test_spec_registry_contract.py` *only* if any existing test pins the field set on CategorySpec via reflection or schema introspection; if it does, extend the assertions to include the new universal fields. Do not break the 16 existing contract tests.

## Inputs

- ``backend/app/crawlers/specs/base.py` — extending the CategorySpec base with universal value+confidence fields`
- ``backend/app/crawlers/specs/__init__.py` — register UniversalSpec under 'universal' slug`
- ``backend/app/crawlers/specs/coilover.py`, `backend/app/crawlers/specs/brake.py`, `backend/app/crawlers/specs/turbo.py` — read-only confirmation that subclasses inherit base fields cleanly`
- ``backend/tests/crawlers/test_spec_registry_contract.py` — existing assertions to extend if they pin the old field set`

## Expected Output

- ``backend/app/crawlers/specs/base.py` — CategorySpec gains 5 paired value/confidence fields`
- ``backend/app/crawlers/specs/universal.py` — new UniversalSpec(CategorySpec) catch-all schema`
- ``backend/app/crawlers/specs/__init__.py` — imports UniversalSpec and registers it under 'universal'`

## Verification

pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto --rootdir=backend

## Observability Impact

No new runtime signals — schema extension only. The S01 ExtractionFailureRate WARN log will now include any failing universal field path in `e.errors()[:3]`.
