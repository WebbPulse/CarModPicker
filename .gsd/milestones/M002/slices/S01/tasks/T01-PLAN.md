---
estimated_steps: 5
estimated_files: 6
skills_used:
  - lint
  - test
---

# T01: Build SpecRegistry, CategorySpec base, and three concrete category models

Create the schema contract foundation that every downstream slice consumes. Add a new `app/crawlers/specs/` package with three modules: `base.py` (the abstract `CategorySpec(BaseModel)` with confidence-flag conventions and shared field metadata), `registry.py` (the `SpecRegistry` class with `register()` and `resolve(category_id: str) -> Type[CategorySpec] | None` plus a module-level singleton that auto-registers known specs), and three concrete models in `coilover.py`, `brake.py`, `turbo.py`. CategorySpec uses Pydantic v2 (the project's standard — see `app/api/schemas/`), `ConfigDict(extra='forbid')` so unknown fields fail loudly, and an Optional[str] `confidence` field on every value field via a small helper `SpecField` Annotated alias (e.g., `weight: SpecField[Optional[float]] = None` with companion `weight_confidence: Optional[Literal['high','medium','low']] = None`). Initial fields per the roadmap: CoiloverSpec → spring_rate_front (lb/in), spring_rate_rear, damper_adjustability ('non-adjustable'|'rebound-only'|'rebound-and-compression'|'electronic'), height_adjustable (bool); BrakeSpec → rotor_diameter_mm, pad_compound (str free-form for now), piston_count, vented (bool); TurboSpec → compressor_wheel_mm, turbine_wheel_mm, journal_or_bb ('journal'|'ballbearing'), housing_ar (float). Keep field counts modest — 3-5 each — these are stub schemas to prove the registry contract; the M002 retrofit slices expand them. Registry keys are category slug strings ('coilover', 'brake', 'turbo'), NOT category UUIDs (slugs are stable across environments; UUIDs are not). The registry must be a class with method-level access (not a module global dict) so tests can construct an isolated instance. Provide a default `default_registry` instance with the three specs pre-registered. No runtime hook from adapters or ingest in this task — purely the contract.

## Inputs

- ``backend/app/api/schemas/part.py` — Pydantic v2 conventions (ConfigDict, Optional, Field) used across the project`
- ``backend/app/core/part_categories_data.py` — category slugs ('suspension', 'engine', 'brakes') for context; spec slugs are sub-types ('coilover', 'brake', 'turbo')`

## Expected Output

- ``backend/app/crawlers/specs/__init__.py` — re-exports `CategorySpec`, `SpecRegistry`, `default_registry``
- ``backend/app/crawlers/specs/base.py` — `CategorySpec(BaseModel)` abstract base with `ConfigDict(extra='forbid')` and confidence-flag conventions`
- ``backend/app/crawlers/specs/registry.py` — `SpecRegistry` class (register/resolve) + `default_registry` singleton`
- ``backend/app/crawlers/specs/coilover.py` — `CoiloverSpec(CategorySpec)` with spring rate, damper adjustability, height adjustable`
- ``backend/app/crawlers/specs/brake.py` — `BrakeSpec(CategorySpec)` with rotor diameter, pad compound, piston count, vented`
- ``backend/app/crawlers/specs/turbo.py` — `TurboSpec(CategorySpec)` with compressor/turbine wheel, journal/bb, housing A/R`

## Verification

python -c "from app.crawlers.specs import default_registry, CategorySpec; from app.crawlers.specs.coilover import CoiloverSpec; assert default_registry.resolve('coilover') is CoiloverSpec; assert default_registry.resolve('unknown') is None; assert issubclass(CoiloverSpec, CategorySpec); CoiloverSpec(spring_rate_front=600.0, height_adjustable=True); print('ok')"

## Steps

1. Create `backend/app/crawlers/specs/__init__.py` re-exporting `CategorySpec`, `SpecRegistry`, `default_registry`.
2. Write `backend/app/crawlers/specs/base.py` with `CategorySpec(BaseModel)` using `ConfigDict(extra='forbid')`. Add a `confidence` companion-field convention: every value field `X` may have an Optional[`Literal['high','medium','low']`] companion `X_confidence` for downstream universal extraction (S02). Document the convention in the module docstring.
3. Write `backend/app/crawlers/specs/registry.py` with `class SpecRegistry` exposing `register(slug: str, model: Type[CategorySpec]) -> None` and `resolve(slug: str) -> Type[CategorySpec] | None`. Module-level `default_registry = SpecRegistry()` — empty at construction; the spec modules below register themselves at import time inside `__init__.py`.
4. Write `coilover.py`, `brake.py`, `turbo.py` with the field sets in the description. Each module ends with `default_registry.register('<slug>', <SpecClass>)` (called from `__init__.py` after import to avoid circular imports — `__init__.py` imports the three modules in order).
5. Run the verify one-liner; run `pyright backend/app/crawlers/specs/` to confirm types.

## Must-Haves

- [ ] `default_registry.resolve('coilover')` returns `CoiloverSpec`; same for `brake` and `turbo`.
- [ ] `default_registry.resolve('unknown_slug') is None`.
- [ ] `CoiloverSpec(**{"unknown_field": 1})` raises `pydantic.ValidationError` due to `extra='forbid'`.
- [ ] All three concrete classes import without `from app.crawlers.adapters import ...` — no circular imports through the adapters package.
- [ ] `pyright` passes on the new package.

## Observability Impact

None — pure contract module. No runtime boundary.
