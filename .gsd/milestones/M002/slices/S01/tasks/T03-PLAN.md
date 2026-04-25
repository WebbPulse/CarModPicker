---
estimated_steps: 7
estimated_files: 5
skills_used:
  - observability
  - test
  - lint
---

# T03: Wire ingest validation hook: gate ScrapedPayload.specifications through SpecRegistry, drop on failure, increment extraction_failure_rate

This is the R004 must-have: ingest must validate and gracefully degrade. Modify `ingest_payload` in `backend/app/crawlers/base.py` so that when `payload.specifications` is non-None: (a) resolve the category slug — for now use the inferred category slug (the same `inferred_name` already computed earlier in the function from `infer_category(payload.name, payload.description)`); if no inferred slug, skip validation and pass specs through as-is (sensible default for legacy adapters until S02 narrows this). (b) Look up the model via `default_registry.resolve(slug)`; if no model registered for that slug, pass specs through as-is (we don't yet have a schema for every category — that's fine; Pydantic-validated coverage grows over M002). (c) If a model is registered, run `Model.model_validate(payload.specifications)` inside try/except `pydantic.ValidationError`. On success, replace `payload.specifications` with the validated `model.model_dump(exclude_none=True)` so downstream sees a normalized dict. On failure, log a structured warning containing adapter_name (derive from a new optional kwarg `adapter_name: Optional[str] = None` on `ingest_payload` — pass it through from runner.py and ecs_runner.py call sites; it's ok if some legacy callers omit it, default to 'unknown'), the resolved category slug, the URL, and `e.errors()[:3]` (cap to keep logs tight). Then set the local `validated_specifications = None` and proceed with ingest. Then add the EMF metric: extend `app/core/cloudwatch_emf.py` with a new function `emit_extraction_failure(adapter_name: str)` that emits a single-count `ExtractionFailureRate` metric in the same `CarModPicker/Crawlers` namespace with dimension `AdapterName × Environment`. Same env-gating as `emit_crawler_run_metrics` (silent in tests/dev). Call it from inside the failure branch of ingest_payload. Wire `validated_specifications` into the `PartCreate(...)` constructor (specifications=validated_specifications). Update `runner.py` and `ecs_runner.py` and `ecs_rescrape_runner.py` to pass `adapter_name=adapter.ADAPTER_NAME` to `ingest_payload` (search for existing `ingest_payload(` call sites — there should be a small handful). Do NOT raise on validation failure — the part still ingests with specifications=None.

## Inputs

- ``backend/app/crawlers/base.py` — existing `ingest_payload` function and `ScrapedPayload` (extended in T02 with specifications)`
- ``backend/app/crawlers/specs/registry.py` — `default_registry.resolve()` from T01`
- ``backend/app/core/cloudwatch_emf.py` — existing `emit_crawler_run_metrics` pattern to mirror`
- ``backend/app/api/schemas/part.py` — `PartCreate.specifications: Optional[Dict[str, Any]]``
- ``backend/app/crawlers/runner.py` — call sites of `ingest_payload``
- ``backend/app/crawlers/ecs_runner.py` — call sites of `ingest_payload``
- ``backend/app/crawlers/ecs_rescrape_runner.py` — call sites of `ingest_payload``

## Expected Output

- ``backend/app/crawlers/base.py` — `ingest_payload` validates specifications via SpecRegistry, drops on failure, passes through to PartCreate. New optional `adapter_name` kwarg.`
- ``backend/app/core/cloudwatch_emf.py` — adds `emit_extraction_failure(adapter_name: str)` mirroring the env-gated pattern of `emit_crawler_run_metrics``
- ``backend/app/crawlers/runner.py` — call site passes `adapter_name=adapter.ADAPTER_NAME``
- ``backend/app/crawlers/ecs_runner.py` — call site passes `adapter_name``
- ``backend/app/crawlers/ecs_rescrape_runner.py` — call site passes `adapter_name``

## Verification

cd backend && pytest tests/crawlers/ -n auto -k 'ingest or spec' && python -c "from app.crawlers.base import ingest_payload; from app.core.cloudwatch_emf import emit_extraction_failure; emit_extraction_failure(adapter_name='test'); print('ok')"

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `default_registry.resolve(slug)` | Returns None on unknown slug → pass specs through unchanged | N/A (in-memory dict lookup) | N/A |
| Pydantic `Model.model_validate(specifications)` | Catch `ValidationError`, set `validated_specifications=None`, log WARN, emit metric, continue ingest | N/A | N/A — validation either succeeds or raises |
| `aws-embedded-metrics` library inside `emit_extraction_failure` | Catch all exceptions, log via `logger.error(..., exc_info=True)`, never raise — mirrors `emit_crawler_run_metrics` failure-isolation pattern (crawler uptime > signal reliability) | Library handles its own buffering | N/A |
| `infer_category(name, description)` returns no slug | Pass specs through unchanged — we don't yet have a way to validate without a category | N/A | N/A |

## Load Profile

- **Shared resources**: CloudWatch Logs path (already saturation-tested by existing `emit_crawler_run_metrics`); the existing DB session inside `ingest_payload`; the `_robots_cache` and crawl-bucket S3 client — none of these are touched by validation work.
- **Per-operation cost**: One Pydantic `model_validate` call per ingested part with a non-None spec block — ~10–100 µs on dicts of this size. One stdout JSON line per validation failure (only on the failure path; the success path emits nothing extra).
- **10x breakpoint**: Nowhere near a bottleneck — DB writes and HTML fetches dominate ingest cost by 4+ orders of magnitude. EMF stdout flushes already scale with the existing per-run metrics path; no new failure mode introduced at 10x.

## Negative Tests

- **Malformed inputs**: `payload.specifications = {"unknown_field": 1}` → must drop and emit metric (extra='forbid' catches this). `payload.specifications = {"spring_rate_front": "not-a-number"}` → must drop and emit metric (type coercion fails). `payload.specifications = {}` → must pass (all fields Optional). `payload.specifications = None` → must pass (no validation runs).
- **Error paths**: Mock `Model.model_validate` to raise `ValidationError`; assert WARN log fires AND `emit_extraction_failure` is called AND part still persists with `specifications=None`. Mock `emit_extraction_failure` to raise an arbitrary Exception (simulating EMF library failure); assert ingest still completes and the part persists. (Failure-isolation guarantee.)
- **Boundary conditions**: Inferred category slug is None (no model can resolve) → specs pass through unchanged. Slug resolves but no model is registered for it (e.g., 'wheels') → specs pass through unchanged (current behavior, until M002 adds more spec models).

## Steps

1. In `backend/app/crawlers/base.py`, add `adapter_name: Optional[str] = None` kwarg to `ingest_payload`. Default to `'unknown'` inside the function body if None (so log lines are never bare).
2. After the existing `inferred_name` block (~ line 694), insert the validation block: if `payload.specifications is not None` and `inferred_name`, do `Model = default_registry.resolve(inferred_name)`; if `Model` is not None, `try: validated = Model.model_validate(payload.specifications); validated_specifications = validated.model_dump(exclude_none=True) except pydantic.ValidationError as e: ...`. On the except branch, build a structured WARN with `adapter_name`, `inferred_name`, `payload.product_url`, `e.errors()[:3]`, then call `emit_extraction_failure(adapter_name=adapter_name)`, then set `validated_specifications = None`. Else (no Model registered, or no inferred slug, or no specifications): `validated_specifications = payload.specifications`.
3. Replace `specifications=None` (or any current pass-through) inside the `PartCreate(...)` constructor with `specifications=validated_specifications`.
4. In `backend/app/core/cloudwatch_emf.py`, add `emit_extraction_failure(adapter_name: str) -> None` decorated with `@metric_scope`. Inside: same env gate (`if os.getenv("TESTING") == "true" or settings.APP_ENVIRONMENT.lower() not in ("staging", "production"): return`); set dimensions `{"AdapterName": adapter_name, "Environment": settings.APP_ENVIRONMENT}`; `metrics.set_namespace("CarModPicker/Crawlers")`; `metrics.put_metric("ExtractionFailureRate", 1, "Count")`. Wrap the body in `try/except Exception as e: logger.error("emit_extraction_failure failed: %s", e, exc_info=True)` — never raise.
5. Update `backend/app/crawlers/runner.py`, `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`: at every `ingest_payload(...)` call site, pass `adapter_name=adapter.ADAPTER_NAME` (or the equivalent local). Use `grep -n "ingest_payload(" backend/app/crawlers/*.py` to find them all.
6. Add `from app.core.cloudwatch_emf import emit_extraction_failure` to `backend/app/crawlers/base.py`. Confirm no circular import (cloudwatch_emf does not import from crawlers).
7. Run `pytest tests/crawlers/ -n auto` and `pyright backend/app/crawlers/base.py backend/app/core/cloudwatch_emf.py`.

## Must-Haves

- [ ] `ingest_payload` accepts an optional `adapter_name` kwarg and passes it through the new failure path.
- [ ] Pydantic `ValidationError` on `payload.specifications` results in: (a) part still ingests, (b) `Part.specifications` is None, (c) WARN log fires, (d) `emit_extraction_failure(adapter_name=...)` is called.
- [ ] Valid spec block ingests with `Part.specifications` equal to `model.model_dump(exclude_none=True)`.
- [ ] `emit_extraction_failure` is silent (no-op) when `TESTING=true` or `APP_ENVIRONMENT` is not staging/production. No exception escapes the function under any circumstance.
- [ ] All three runner call sites pass `adapter_name=adapter.ADAPTER_NAME`.
- [ ] Full `pytest tests/crawlers/ -n auto` is green — no existing adapter test regresses.
- [ ] `pyright` passes on the touched files.

## Observability Impact

New WARN log on validation failure: includes adapter_name, category slug, product_url, and capped Pydantic errors[:3]. New EMF metric `ExtractionFailureRate` (Count, AdapterName × Environment). Failure-isolated like `emit_crawler_run_metrics` — any aws-embedded-metrics exception is caught and logged, never raised. A future agent inspects with: CloudWatch Logs Insights `filter @message like /spec validation failed/`, or CloudWatch Metrics in `CarModPicker/Crawlers` namespace under `ExtractionFailureRate`.
