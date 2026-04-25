---
estimated_steps: 24
estimated_files: 3
skills_used: []
---

# T03: Add category-name → sub-slug bridge + base-class apply_universal_extraction hook + suppress_universal ClassVar + ingest update

Three connected pieces that together form the auto-run mechanism. Build them in this order so each piece can be unit-tested as you go.

**(a) Sub-slug bridge (`backend/app/crawlers/specs/category_bridge.py`).**
Create a new module exposing `category_to_subslug(category_name: str | None, *, name: str | None = None, description: str | None = None) -> str | None` that maps a DB category name to a SpecRegistry sub-slug using keyword scoring over the part name + description. Mirror the structure of `app/core/category_inference.py` — small per-slug keyword dict, word-boundary matches, best-score-wins. Initial mapping (3 sub-slugs to land + 'universal' fallback):
- `'suspension'` + ('coilover'|'coilovers'|'coil over'|'coil-over' in name/desc) → `'coilover'`
- `'brakes'` (always — single brake sub-slug for now) → `'brake'`
- `'engine'` + ('turbo'|'turbocharger' in name/desc) → `'turbo'`
- Everything else (or 'suspension'/'engine' without the disambiguating keyword): return `'universal'` so the UniversalSpec fallback fires.
- When `category_name is None`: return None (caller should skip validation entirely — preserves S01 pass-through).

Returning `'universal'` when category_name is set but has no sub-slug is the change that makes the S01 hook actually fire across the catalog. Today it never fires because no DB category name resolves to a registry slug; after this, every category with universal-field content gets validated against UniversalSpec.

**(b) Base-class `apply_universal_extraction` method (`backend/app/crawlers/adapters/base.py`).**
Add `def apply_universal_extraction(self, html: str, payload: ScrapedPayload) -> ScrapedPayload` to `RetailerCrawlerAdapter`. Implementation:
1. If payload is None, return payload unchanged.
2. Lazy import: `from app.crawlers.parsing import extract_universal_fields` inside the method to keep the import cycle broken (parsing.py already imports ScrapedPayload from base.py).
3. Call `extract_universal_fields(html)`.
4. Filter out any field listed in `self.suppress_universal` (new ClassVar — see (c)).
5. Build a flat dict `{'<field>': value, '<field>_confidence': conf}` for each surviving extracted field.
6. Merge into `payload.specifications` — preserve any adapter-set keys (adapter wins). Create a new dict if specifications is None. Only assign back to payload if the merged dict is non-empty.
7. Emit `logger.debug('universal_extraction: adapter=%s field=%s confidence=%s', self.ADAPTER_NAME, field, confidence)` for each extracted field.
8. Return the (possibly mutated) payload.

**(c) `suppress_universal: ClassVar[list[str]] = []` on `RetailerCrawlerAdapter`.**
Default empty (every adapter gets all 5 universal fields). Adapters override to opt out. Validate at import time inside the existing `__init_subclass__` hook (alongside `category_targets` validation): each entry must be one of the 5 known field names {'weight_grams','material','finish','warranty_days','fitment_notes'}. Raise TypeError on unknown name with the adapter qualname so typos fail loudly.

**(d) Update `ingest_payload` slug resolution in `backend/app/crawlers/base.py`.**
In the existing validation hook, replace the bare `default_registry.resolve(inferred_name)` with a two-step: first call `category_to_subslug(inferred_name, name=payload.name, description=payload.description)`, then resolve that. If the bridge returns None, keep the existing pass-through (no change). Update the WARN log to include both `inferred_name` AND the bridged sub-slug, so S04's admin endpoint can show per-sub-category failure rates. Use a lazy import for `category_to_subslug` inside the validation hook to avoid pulling specs/category_bridge into the import graph at module load.

No call-site changes in this task — that's T04. This task only adds the bridge + hook + ClassVar + ingest slug resolution.

## Inputs

- ``backend/app/crawlers/parsing.py` — uses extract_universal_fields from T01`
- ``backend/app/crawlers/specs/__init__.py` — uses UniversalSpec registration from T02`
- ``backend/app/crawlers/specs/base.py` — universal field shape from T02 (so the merged dict matches the schema)`
- ``backend/app/crawlers/adapters/base.py` — extending the adapter base`
- ``backend/app/crawlers/base.py` — updating ingest_payload slug resolution`
- ``backend/app/core/category_inference.py` — read-only, mirrors keyword-scoring style`

## Expected Output

- ``backend/app/crawlers/specs/category_bridge.py` — new module with category_to_subslug() resolver`
- ``backend/app/crawlers/adapters/base.py` — apply_universal_extraction method + suppress_universal ClassVar + __init_subclass__ validation`
- ``backend/app/crawlers/base.py` — ingest_payload uses bridge before registry resolve; WARN log includes both names`

## Verification

pytest backend/tests/crawlers/test_category_slug_bridge.py backend/tests/crawlers/test_ingest_spec_validation.py backend/tests/crawlers/test_adapter_discovery.py -n auto --rootdir=backend

## Observability Impact

DEBUG log per extracted universal field (one line per field per page — bounded). WARN log on validation failure now includes both inferred_name and bridged_subslug. S04's admin endpoint will see per-sub-category granularity instead of just per-category. ExtractionFailureRate EMF metric still emits with adapter_name dimension.
