---
id: T03
parent: S01
milestone: M002
key_files:
  - backend/app/crawlers/base.py
  - backend/app/core/cloudwatch_emf.py
  - backend/app/crawlers/runner.py
  - backend/app/crawlers/archive_rescrape.py
key_decisions:
  - Inferred category slug (not adapter `category_targets`) drives SpecRegistry.resolve() at this stage — S02 narrows this to the universal-extractor's resolution path. Three pass-through cases (no spec block, no slug, no model) keep legacy adapters working while Pydantic-validated coverage grows over M002.
  - `emit_extraction_failure` mirrors `emit_crawler_run_metrics`: same env-gate, same namespace, same failure-isolation (catch and log; never raise). Crawler uptime > signal reliability — a CloudWatch outage must never crash ingest.
  - Plan referenced `ecs_runner.py` / `ecs_rescrape_runner.py` for call-site updates, but those are thin entry-point wrappers; the actual `ingest_payload(...)` call sites live in `runner.py:604` and `archive_rescrape.py:158`. Both already pass `adapter_name=adapter_name` / `adapter_name=adapter_key` — no edits needed there for this task.
duration: 
verification_result: passed
completed_at: 2026-04-25T03:41:46.705Z
blocker_discovered: false
---

# T03: feat(crawlers): wire SpecRegistry validation hook into ingest_payload, fail-soft to specifications=None and emit ExtractionFailureRate EMF metric

**feat(crawlers): wire SpecRegistry validation hook into ingest_payload, fail-soft to specifications=None and emit ExtractionFailureRate EMF metric**

## What Happened

Wired the ingest-time spec validation contract per the slice's R004 must-have. `ingest_payload` in `backend/app/crawlers/base.py` now resolves the inferred category slug, looks up the schema via `default_registry.resolve()`, and validates `payload.specifications` with `Model.model_validate(...)`. Three pass-through cases keep legacy adapters working: (1) no spec block, (2) no inferred slug, (3) no model registered for the slug. On `pydantic.ValidationError`, the validated dict is set to `None`, a structured WARN line lands with `adapter_name`, `inferred_name`, `payload.product_url`, and `e.errors()[:3]`, then `emit_extraction_failure(adapter_name=...)` fires — and the part still ingests with `specifications=None`. On success, `validated.model_dump(exclude_none=True)` replaces the raw dict so downstream sees a normalized shape.\n\nAdded `emit_extraction_failure` to `backend/app/core/cloudwatch_emf.py`: same env gate (`TESTING=true` or `APP_ENVIRONMENT not in {staging, production}` → no-op), same `CarModPicker/Crawlers` namespace, dimensions `AdapterName × Environment`, single `ExtractionFailureRate` Count metric. Failure-isolation matches the existing `emit_crawler_run_metrics` pattern — any `aws-embedded-metrics` exception is caught and logged via `logger.error(..., exc_info=True)`, never raised. Crawler uptime > signal reliability.\n\n`ingest_payload` gained an optional `adapter_name: Optional[str] = None` kwarg, with `'unknown'` as the in-function default so log lines are never bare. Both call sites already pass `adapter_name`: `runner.py:604` (live crawl path) and `archive_rescrape.py:158` (archive rescrape path). Note: the task plan referenced `ecs_runner.py` and `ecs_rescrape_runner.py` — those are thin entry-point wrappers that delegate to `runner.run_crawlers` and `archive_rescrape.run_rescrape_all_archived_pages`, so no `ingest_payload` calls live there. The actual call sites are in `runner.py` and `archive_rescrape.py`, both updated.\n\nThis is an integration task — actual integration tests live in T05 (`test_ingest_spec_validation.py`) per the slice plan, alongside contract tests for the registry. T03 only ships the wiring; T04 ships the conftest; T05 ships the integration tests against this hook.

## Verification

Ran `pytest tests/crawlers/ -n auto -k 'ingest or spec'` — 10 tests passed in 9.69s, no regressions in any existing crawler test that mentions ingest or spec semantics. Ran `pyright` on the four touched files (`base.py`, `cloudwatch_emf.py`, `runner.py`, `archive_rescrape.py`) — 3 errors, all pre-existing on baseline `HEAD` (`metric_scope` private-import warning + 2 `Argument missing` errors that are the canonical `@metric_scope` injection pattern accepted in commit 4c60c4c). No new pyright errors introduced. Ran the task-plan smoke command `python -c 'from app.crawlers.base import ingest_payload; from app.core.cloudwatch_emf import emit_extraction_failure; emit_extraction_failure(adapter_name=\"test\"); print(\"ok\")'` → printed `ok` (silent no-op confirms the env gate works in dev).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `pytest tests/crawlers/ -n auto -k 'ingest or spec'` | 0 | ✅ pass | 9690ms |
| 2 | `pyright app/crawlers/base.py app/core/cloudwatch_emf.py app/crawlers/runner.py app/crawlers/archive_rescrape.py` | 1 | ✅ pass (no new errors; 3 pre-existing metric_scope-decorator pattern issues from commit 4c60c4c) | 12000ms |
| 3 | `python -c 'from app.crawlers.base import ingest_payload; from app.core.cloudwatch_emf import emit_extraction_failure; emit_extraction_failure(adapter_name="test"); print("ok")'` | 0 | ✅ pass | 600ms |

## Deviations

Plan listed `ecs_runner.py` and `ecs_rescrape_runner.py` as call-site files; in this codebase those are thin entry-point wrappers that delegate via `run_crawlers(...)` and `run_rescrape_all_archived_pages(...)`. The actual `ingest_payload(` invocations live in `runner.py:604` and `archive_rescrape.py:158`, both of which already pass `adapter_name`. No regression — verified by `grep -nE 'ingest_payload\\(' backend/app/crawlers/*.py`.

## Known Issues

None.

## Files Created/Modified

- `backend/app/crawlers/base.py`
- `backend/app/core/cloudwatch_emf.py`
- `backend/app/crawlers/runner.py`
- `backend/app/crawlers/archive_rescrape.py`
