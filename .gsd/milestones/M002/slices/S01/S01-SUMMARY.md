---
id: S01
parent: M002
milestone: M002
provides:
  - ["backend/app/crawlers/specs/registry.py — SpecRegistry with method-level register/resolve + module-level default_registry singleton, registered specs in __init__.py", "backend/app/crawlers/specs/base.py — CategorySpec(BaseModel) with ConfigDict(extra='forbid') + paired X/X_confidence convention", "backend/app/crawlers/specs/{coilover,brake,turbo}.py — 3 concrete stub schemas (S03 retrofit will expand fields)", "backend/app/crawlers/adapters/base.py — RetailerCrawlerAdapter.category_targets ClassVar with import-time validation against default_registry", "backend/app/crawlers/base.py — ScrapedPayload.specifications optional dict field; ingest_payload fail-soft validation hook (drop+log+emit on ValidationError, persist Part with specifications=None)", "backend/app/core/cloudwatch_emf.py — emit_extraction_failure(adapter_name) EMF emitter (env-gated, AdapterName x Environment dimensions, failure-isolated)", "backend/tests/crawlers/conftest.py — load_fixture_html() + make_scraped_payload() factory (consumed by S02/S03/S04 tests)", "backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html — tracked test HTML (818 bytes) for spec-extraction tests"]
requires:
  []
affects:
  - ["app/crawlers/specs/ (new package)", "app/crawlers/adapters/base.py (category_targets ClassVar)", "app/crawlers/base.py (ScrapedPayload.specifications + ingest_payload validation hook)", "app/core/cloudwatch_emf.py (emit_extraction_failure)", "tests/crawlers/conftest.py (new)", "tests/crawlers/fixtures/spec_contract_samples/ (new tracked fixture)", "tests/crawlers/fixtures/{amsperformance,briantooleyracing,cobbtuning,subispeed,texasspeed}/expected.json (snapshot refresh after T02 added specifications field)"]
key_files:
  - ["backend/app/crawlers/specs/registry.py", "backend/app/crawlers/specs/base.py", "backend/app/crawlers/specs/coilover.py", "backend/app/crawlers/adapters/base.py", "backend/app/crawlers/base.py", "backend/app/core/cloudwatch_emf.py", "backend/tests/crawlers/conftest.py", "backend/tests/crawlers/test_spec_registry_contract.py", "backend/tests/crawlers/test_ingest_spec_validation.py"]
key_decisions:
  - ["Registry keyed by category SLUGS (not UUIDs) — slugs stable across envs", "Spec registration centralized in app/crawlers/specs/__init__.py (not at the bottom of each spec module) — keeps spec modules side-effect-free for test isolation", "Confidence flags via paired X / X_confidence convention (not metaclass/descriptor) — readability + JSON-Schema export wins over enforcement at this scale", "category_targets validated at import time inside __init_subclass__ (TypeError on unknown slug or empty string) — surfaces typos loudly during S03's 108-adapter retrofit instead of silent runtime no-ops", "Ingest validation is fail-soft (drop+log+emit; never raise) per R004 — silent regression of existing ingest pipeline is the worst-case outcome with extraction new across 108 adapters", "Three pass-through cases in ingest validation (no spec block, no inferred slug, no model) — keeps legacy adapters working while Pydantic-validated coverage grows over M002", "Dropped T05's planned 'test_emitter_exception_does_not_propagate' negative test — ingest_payload has no try/except wrapping the emitter; failure-isolation lives inside emit_extraction_failure itself (per emit_crawler_run_metrics pattern), shipping the test would have documented a non-existent contract"]
patterns_established:
  - ["Spec module package layout: side-effect-free spec modules + centralized registration in __init__.py — keeps tests able to construct fresh SpecRegistry() instances", "Confidence-flag convention: paired X / X_confidence(Optional[Literal['high','medium','low']]) fields, documented in base.py — S02 universal extractors populate per-field confidence without metaclass magic", "Fail-soft ingest validation: drop block, log+emit, ingest Part with specifications=None — never raise from inside ingest_payload (R004)", "EMF emitter pattern: env-gated (TESTING+APP_ENVIRONMENT), CarModPicker/Crawlers namespace, AdapterName x Environment dimensions, all aws-embedded-metrics exceptions caught and logged — crawler uptime > signal reliability", "Lazy-import of default_registry inside __init_subclass__ to keep dependency direction one-way (adapters/ depends on specs/, specs/ never imports adapters/)", "Test patch site: emit_extraction_failure mocked at the IMPORT site (app.crawlers.base.emit_extraction_failure) not the source (app.core.cloudwatch_emf.emit_extraction_failure) — Python resolves bound names at call site", "Save-and-restore registry fixture pattern: process-global default_registry mutations need explicit save/restore with sentinel check; monkeypatch can't roll back dict mutations safely"]
observability_surfaces:
  - ["Structured WARN log on ingest_payload spec validation failure: contains adapter_name + inferred category slug + payload.product_url + e.errors()[:3]", "CloudWatch EMF metric ExtractionFailureRate (Count) in CarModPicker/Crawlers namespace with dimensions AdapterName x Environment — emitted from inside ingest_payload on every Pydantic ValidationError; consumed by S04's admin extraction-health endpoint", "Failure isolation: emit_extraction_failure catches all aws-embedded-metrics exceptions and logs via logger.error(..., exc_info=True), never raises — protects crawler uptime if CloudWatch is degraded"]
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-04-25T04:01:34.373Z
blocker_discovered: false
---

# S01: Schema contract + crawler test infrastructure

**Lays the M002 schema-contract foundation: SpecRegistry + CategorySpec base + 3 concrete models, category_targets opt-in on adapter base, specifications field on ScrapedPayload, fail-soft ingest validation hook with structured WARN + EMF metric, and crawler test infrastructure (conftest + tracked HTML sample) — proven by 23 contract+integration tests.**

## What Happened

S01 ships the schema contract that S02-S04 consume.

**T01** (`app/crawlers/specs/`): new package with `base.py` (CategorySpec(BaseModel) + extra='forbid' + paired X / X_confidence convention), `registry.py` (SpecRegistry class with method-level register/resolve + module-level default_registry), and three concrete stub models — `coilover.py` (spring_rate_front/rear, damper_adjustability literal, height_adjustable bool), `brake.py` (rotor_diameter_mm, pad_compound, piston_count, vented), `turbo.py` (compressor_wheel_mm, turbine_wheel_mm, journal_or_bb literal, housing_ar). Registration of project-shipped specs lives in `__init__.py`, not at the bottom of each spec module — keeps spec modules side-effect-free, importable in isolation by tests that want a fresh `SpecRegistry()`. Slugs ('coilover', 'brake', 'turbo'), not category UUIDs, are the registry key.

**T02** (`adapters/base.py` + `crawlers/base.py`): added `category_targets: ClassVar[list[str]] = []` to `RetailerCrawlerAdapter`, with import-time validation in `__init_subclass__` — each entry must be a non-empty string and must resolve via `default_registry.resolve()`. Lazy-imports default_registry inside the hook to keep the dependency direction one-way (adapters/ depends on specs/, never the reverse). Empty/non-string values raise TypeError separately from unknown-slug to give clearer errors. All 108 existing adapters keep `category_targets=[]` and continue to work unchanged. Extended `ScrapedPayload` dataclass with `specifications: Optional[Dict[str, Any]] = None`.

**T03** (`crawlers/base.py` + `core/cloudwatch_emf.py` + `runner.py` + `archive_rescrape.py`): wired the R004 fail-soft validation hook in `ingest_payload`. When `payload.specifications` is non-None, resolves the inferred category slug → registry → Pydantic model_validate. Three pass-through cases keep legacy adapters working (no spec block, no inferred slug, no model). On ValidationError: drops to None, logs structured WARN with adapter_name + inferred_name + e.errors()[:3], emits `ExtractionFailureRate` EMF metric, and the Part still ingests. Added `emit_extraction_failure(adapter_name)` to cloudwatch_emf — same env-gate, same `CarModPicker/Crawlers` namespace, same failure-isolation as `emit_crawler_run_metrics` (catch and log; never raise). Both `ingest_payload` call sites (`runner.py:604`, `archive_rescrape.py:158`) already pass adapter_name; the plan's reference to ecs_runner.py / ecs_rescrape_runner.py was a planner-side reference drift — those are thin entry-point wrappers.

**T04** (`tests/crawlers/conftest.py` + `fixtures/spec_contract_samples/coilover_sample.html`): test infrastructure — `load_fixture_html(adapter_slug, filename='product.html')` reads under `tests/crawlers/fixtures/<slug>/`, raises FileNotFoundError loudly on miss; `make_scraped_payload` pytest fixture returning a callable factory with sensible ScrapedPayload defaults plus **overrides for per-test customization. Tracked sample HTML (818 bytes, well under 2KB cap) mirrors the Rank Math @graph JSON-LD shape but trimmed to a single @type:Product. 6 smoke tests included so conftest regressions surface in T04's own gate, not as collateral in T05.

**T05** (`tests/crawlers/test_spec_registry_contract.py` + `test_ingest_spec_validation.py`): 23 tests total. Contract suite (16 tests): TestCoiloverSpec/TestBrakeSpec/TestTurboSpec each asserting registry resolution + valid-payload acceptance + multiple malformed-payload rejections (extra='forbid' violation, type-coercion failure, invalid Literal); plus `test_unknown_slug_resolves_to_none`. Integration suite (7 tests): valid specs persist on Part.specifications; invalid specs drop to None and Part still persists (caplog asserts adapter_name + slug land in WARN); type-coercion failure drops to None; emit_extraction_failure mock called once with `adapter_name=...`; pass-through boundaries (no spec block, unregistered slug). Key gotcha encoded as MEM017: patch `app.crawlers.base.emit_extraction_failure` (import site) NOT `app.core.cloudwatch_emf.emit_extraction_failure` (source) — Python resolves bound names at the call site.

**Slice-level fix-up**: T02's addition of `specifications` to `ScrapedPayload` made 5 characterization-test snapshots stale (amsperformance, briantooleyracing, cobbtuning, subispeed, texasspeed) — each `expected.json` now needs `"specifications": null` appended. Fixed in this closer pass. Full crawler suite is now 1284 passed, 1 skipped, 0 failed; full backend suite 2409 passed, 9 skipped.

**Verify-gate fix-up**: T05's verify line was `cd backend && pytest tests/crawlers/...`, which the gate split on `&&` and ran as two separate commands — the second pytest ran from repo root, found no `tests/`, and exited 5 (no tests collected). Updated T05-PLAN.md verify line to `pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto -v --rootdir=backend` (single command, runs from repo root, 23 passed). Captured as MEM019 (convention) so future tasks don't re-author the broken form.

**Open question carried forward (S02 owner)**: `infer_category()` returns DB category names ('suspension', 'brakes', 'engine'), NOT SpecRegistry slugs ('coilover', 'brake', 'turbo') — so the validation hook never fires in production today. S02's universal extractor must bridge this (either category-name → sub-category-slug derivation, or re-key default_registry to category names). Captured as MEM016. T05's integration tests work around this with a save/restore fixture that registers CoiloverSpec under 'suspension' for the test's duration.

## Verification

**Slice-level demo (per S01-PLAN):** `pytest backend/tests/crawlers/ -n auto --rootdir=backend` → 1284 passed, 1 skipped, 0 failed.

**T05 targeted (the gate's verify command):** `pytest backend/tests/crawlers/test_spec_registry_contract.py backend/tests/crawlers/test_ingest_spec_validation.py -n auto -v --rootdir=backend` → 23 passed in 9.27s.

**Full backend test suite:** `pytest backend/tests/ -n auto --rootdir=backend` → 2409 passed, 9 skipped, 0 failed.

**Specific signals from S01-PLAN must-haves verified:**
- `default_registry.resolve('coilover')` returns CoiloverSpec — proven by `TestCoiloverSpec::test_registry_resolves_to_coilover_spec`.
- `default_registry.resolve('unknown_slug')` returns None — proven by `test_unknown_slug_resolves_to_none`.
- Ingest accepts a valid spec block and persists it — proven by `TestIngestAcceptsValidSpecifications::test_ingest_persists_validated_specifications`.
- Ingest rejects malformed spec block, persists Part with specifications=None, logs structured WARN — proven by `TestIngestDropsInvalidSpecifications::test_invalid_specs_drop_to_none_and_part_persists` with caplog assertion that `bad_adapter` and `suspension` land in the WARN line.
- Ingest emits `ExtractionFailureRate` per-adapter on validation failure — proven by `TestIngestEmitsExtractionFailureMetric::test_emit_extraction_failure_called_once_on_invalid_specs` (mock asserted called once with `adapter_name="metric_adapter"`).
- `category_targets` ClassVar present on RetailerCrawlerAdapter base, defaults to `[]`, validates non-empty strings + registered slugs at import time — proven by extended subclass scenarios in T02 (good/bad/empty subclasses) plus all 108 adapters still importing cleanly via `tests/crawlers/test_adapter_discovery.py` (4 passed).

**Fix-up evidence:**
- 5 characterization-test failures (snapshot drift after T02 added `specifications` field) resolved by appending `"specifications": null` to each `backend/tests/crawlers/fixtures/<adapter>/expected.json`. Re-run of full crawler suite goes from 1279 passed/5 failed to 1284 passed/0 failed.
- T05-PLAN verify line updated from broken `cd backend && pytest tests/crawlers/...` (gate splits on `&&`, exit 5) to single-command `pytest backend/tests/crawlers/... --rootdir=backend` (exit 0). T05-VERIFY.json updated to record the passing run.

## Requirements Advanced

None.

## Requirements Validated

- R001 — SpecRegistry + CategorySpec base + 3 concrete models live under backend/app/crawlers/specs/; adapters declare targets via category_targets ClassVar with import-time validation; ingest validates via default_registry.resolve() + Pydantic model_validate. 23 tests passing (16 contract + 7 integration).
- R004 — ingest_payload fail-soft on Pydantic ValidationError: drops to specifications=None, structured WARN log (caplog asserts adapter_name + slug), emits ExtractionFailureRate EMF metric (mock asserts called once with adapter_name), Part still persists. 3 integration tests prove the contract end-to-end with sqlite test DB.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

"1) Validation hook in ingest_payload doesn't fire in production today — infer_category returns DB category names ('suspension'/'brakes'/'engine'), default_registry has slugs ('coilover'/'brake'/'turbo'). S02 universal extractor must bridge or re-key. Pass-through path keeps this benign for legacy adapters. 2) Stub spec models have only 3-5 fields each — S03 retrofit expands them to per-tier coverage. 3) Test fixture coilover_under_suspension monkey-mutates the process-global default_registry; explicit save/restore with sentinel check covers this, but it's still a process-global. S02 should consider whether SpecRegistry needs a context-local instance for parallel test isolation beyond the in-process locking already provided by save/restore."

## Follow-ups

"S02 must resolve the infer_category() / SpecRegistry slug mismatch (MEM016): infer_category returns DB category names ('suspension'), registry has slugs ('coilover'). Either bridge category-name → sub-category-slug in the universal extractor (option a, consistent with M002 plan), or re-key default_registry to category names (option b, lets S01 wiring work unchanged). Until S02 lands one, the validation hook in production is a no-op for every adapter — three pass-through branches keep this benign. T05 integration tests work around with a save/restore fixture registering CoiloverSpec under 'suspension' for the test's duration."

## Files Created/Modified

- `backend/app/crawlers/specs/__init__.py` — New package init — imports concrete specs, registers them in default_registry
- `backend/app/crawlers/specs/base.py` — CategorySpec(BaseModel) + ConfigDict(extra='forbid') + confidence-flag convention docstring
- `backend/app/crawlers/specs/registry.py` — SpecRegistry class + module-level default_registry
- `backend/app/crawlers/specs/coilover.py` — CoiloverSpec stub (spring_rate_front/rear, damper_adjustability literal, height_adjustable)
- `backend/app/crawlers/specs/brake.py` — BrakeSpec stub (rotor_diameter_mm, pad_compound, piston_count, vented)
- `backend/app/crawlers/specs/turbo.py` — TurboSpec stub (compressor_wheel_mm, turbine_wheel_mm, journal_or_bb literal, housing_ar)
- `backend/app/crawlers/adapters/base.py` — Added category_targets ClassVar with import-time validation in __init_subclass__
- `backend/app/crawlers/base.py` — Extended ScrapedPayload with specifications field; wired fail-soft validation hook in ingest_payload
- `backend/app/core/cloudwatch_emf.py` — Added emit_extraction_failure(adapter_name) EMF emitter
- `backend/app/crawlers/runner.py` — ingest_payload call site already passes adapter_name (no change needed beyond confirming signature)
- `backend/app/crawlers/archive_rescrape.py` — ingest_payload call site already passes adapter_name (no change needed beyond confirming signature)
- `backend/tests/crawlers/conftest.py` — New conftest with load_fixture_html() + make_scraped_payload() factory
- `backend/tests/crawlers/fixtures/spec_contract_samples/coilover_sample.html` — Tracked 818-byte sample HTML (Rank Math @graph JSON-LD shape, single @type:Product)
- `backend/tests/crawlers/test_conftest_smoke.py` — 6 smoke tests covering conftest helpers
- `backend/tests/crawlers/test_spec_registry_contract.py` — 16 contract tests across CoiloverSpec/BrakeSpec/TurboSpec + registry-miss
- `backend/tests/crawlers/test_ingest_spec_validation.py` — 7 integration tests: valid persist, invalid drop+log, EMF metric, pass-through boundaries
- `backend/tests/crawlers/fixtures/amsperformance/expected.json` — Snapshot refreshed to include specifications: null after T02 added the field to ScrapedPayload
- `backend/tests/crawlers/fixtures/briantooleyracing/expected.json` — Snapshot refreshed for new specifications field
- `backend/tests/crawlers/fixtures/cobbtuning/expected.json` — Snapshot refreshed for new specifications field
- `backend/tests/crawlers/fixtures/subispeed/expected.json` — Snapshot refreshed for new specifications field
- `backend/tests/crawlers/fixtures/texasspeed/expected.json` — Snapshot refreshed for new specifications field
- `.gsd/milestones/M002/slices/S01/tasks/T05-PLAN.md` — Verify line updated to single-command form (the original 'cd backend && pytest ...' was split by the gate on &&, breaking the second pytest)
- `.gsd/milestones/M002/slices/S01/tasks/T05-VERIFY.json` — Updated to record passing run with the corrected single-command form
