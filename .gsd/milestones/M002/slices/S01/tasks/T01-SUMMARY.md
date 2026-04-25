---
id: T01
parent: S01
milestone: M002
key_files:
  - backend/app/crawlers/specs/__init__.py
  - backend/app/crawlers/specs/base.py
  - backend/app/crawlers/specs/registry.py
  - backend/app/crawlers/specs/coilover.py
  - backend/app/crawlers/specs/brake.py
  - backend/app/crawlers/specs/turbo.py
key_decisions:
  - Registration of project-shipped specs lives in __init__.py, not at the bottom of each spec module — keeps spec modules side-effect-free and safe to import in isolation (tests can build their own empty SpecRegistry()).
  - Confidence-flag convention is mechanical (paired X / X_confidence fields) rather than enforced via a metaclass or descriptor — keeps the schemas trivially readable and JSON-Schema-exportable; the convention is documented in base.py's module docstring for downstream universal-extraction work in S02.
  - Slugs ('coilover', 'brake', 'turbo'), not category UUIDs, are the registry key — slugs are stable across environments per memory MEM001.
duration: 
verification_result: passed
completed_at: 2026-04-25T03:31:45.125Z
blocker_discovered: false
---

# T01: Add SpecRegistry, CategorySpec base, and Coilover/Brake/Turbo stub specs under app/crawlers/specs/

**Add SpecRegistry, CategorySpec base, and Coilover/Brake/Turbo stub specs under app/crawlers/specs/**

## What Happened

Created the schema-contract foundation for M002 structured extraction. New package `backend/app/crawlers/specs/` with six modules: `base.py` defines `CategorySpec(BaseModel)` with `ConfigDict(extra='forbid')` plus the documented confidence-flag companion convention (every value field `X` may carry an Optional[Literal['high','medium','low']] companion `X_confidence`); `registry.py` defines `SpecRegistry` (method-level register/resolve) and a module-level `default_registry` singleton constructed empty; `coilover.py`, `brake.py`, `turbo.py` define the three concrete stub specs with the field sets specified in the task plan (CoiloverSpec: spring_rate_front/rear, damper_adjustability literal, height_adjustable; BrakeSpec: rotor_diameter_mm, pad_compound free-form str, piston_count, vented; TurboSpec: compressor_wheel_mm, turbine_wheel_mm, journal_or_bb literal, housing_ar). `__init__.py` imports all three concrete modules and calls `default_registry.register('coilover'|'brake'|'turbo', ...)` — registration lives in the package init rather than at the bottom of each spec module so the spec modules are side-effect-free and importable in isolation by tests that want a fresh `SpecRegistry()`. No adapter or ingest wiring in this task — purely the contract; downstream tasks in S01 add `category_targets` to the adapter base and the ScrapedPayload extension.

## Verification

Ran the task plan's verify one-liner under TESTING=true (required because the project's storage_service initializes at import time and fails without S3 in raw shells; tests do this via conftest): all assertions pass and 'ok' prints. Ran an extended check that confirms (1) all three slugs resolve to the right model, (2) resolve('unknown_slug') is None, (3) CoiloverSpec(unknown_field=1) raises pydantic.ValidationError with 'extra forbidden' — Must-Have #3 — and (4) constructing each spec with valid kwargs (Literal values, bools, floats) succeeds. Ran pyright on app/crawlers/specs/ — 0 errors, 0 warnings. Verified Must-Have #4 by grepping the new package for 'from app.crawlers.adapters' — no matches, so no circular import path through the adapters package. Slice-level pytest tests/crawlers/test_spec_registry_contract.py and the cross-package pyright are deferred to T02+ (those test files and the wiring they assert on don't exist yet — this task delivers only the contract module that those tests will import).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true python -c '<task-plan verify one-liner: imports default_registry/CategorySpec/CoiloverSpec, asserts resolve(coilover)/resolve(unknown)/issubclass, constructs CoiloverSpec, prints ok>'` | 0 | pass | 1200ms |
| 2 | `TESTING=true python _verify_t01.py (extended must-haves: all 3 slugs resolve, unknown slug returns None, extra=forbid raises ValidationError, all three concrete specs construct cleanly)` | 0 | pass | 1100ms |
| 3 | `pyright app/crawlers/specs/` | 0 | pass (0 errors, 0 warnings) | 4500ms |
| 4 | `grep -rn 'from app.crawlers.adapters' app/crawlers/specs/` | 1 | pass (no matches = no circular import) | 30ms |

## Deviations

Slice-Verification command 'pyright on app/crawlers/specs/ app/crawlers/base.py app/crawlers/adapters/base.py app/core/cloudwatch_emf.py' was scoped down to 'pyright on app/crawlers/specs/' because the wider set covers files modified by T02+ tasks (category_targets on adapter base, EMF emitter, ScrapedPayload extension) that have not run yet. The wider command should be re-run at the end of S01.

## Known Issues

None. The task's Observability Impact section is 'None — pure contract module.' (Plan-stated, intentional.)

## Files Created/Modified

- `backend/app/crawlers/specs/__init__.py`
- `backend/app/crawlers/specs/base.py`
- `backend/app/crawlers/specs/registry.py`
- `backend/app/crawlers/specs/coilover.py`
- `backend/app/crawlers/specs/brake.py`
- `backend/app/crawlers/specs/turbo.py`
