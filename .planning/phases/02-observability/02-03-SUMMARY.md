---
phase: 02-observability
plan: 3
subsystem: observability
tags: [emf, cloudwatch, metrics, aws-embedded-metrics, crawler, obs-02]

# Dependency graph
requires:
  - phase: 01-safety-nets-ci-hardening
    provides: [pytest -n auto harness, 51% coverage floor, SAFE-05 openapi, SAFE-06 auth, SAFE-07 crawler characterization]
  - phase: 02-observability
    plan: 1
    provides: [request_id_var / user_id_var ContextVars (not read by EMF today, but OBS-04 compliant for downstream)]
  - phase: 02-observability
    plan: 2
    provides: [AWS_EMF_ENVIRONMENT=Local terraform wiring on App Runner + ECS (activates stdout sink at runtime — Landmine 4)]
  - phase: 03-non-breaking-internal-improvements
    plan: 3
    provides: [runner.py elapsed_seconds + parse_failures result-dict fields (OBS-02 reads skipped_not_product directly, elapsed_seconds recomputed from start_ts)]

provides:
  - emit_crawler_run_metrics(*, adapter_name, run_type, ingested, parse_failures, elapsed_seconds) -> None — env-gated EMF emitter in backend/app/core/cloudwatch_emf.py
  - Live-path emission from backend/app/crawlers/runner.py with run_type="live" BEFORE the summary log (Landmine 3 pinned)
  - Rescrape-path emission from backend/app/crawlers/ecs_rescrape_runner.py with run_type="rescrape", adapter_name="aggregate"
  - 10 tests in backend/tests/test_cloudwatch_emf.py pinning OBS-02 envelope, dimensions, metric names/units/values, env gate, emission position, failure isolation

affects:
  - 02-05 (parse-failure alarm) — can now build the composite alarm on CarModPicker/Crawlers/ParseFailures with dimension filter RunType=live
  - Future CloudWatch dashboards — Ingested/ParseFailures/ElapsedSeconds per adapter available in metric explorer (staging: after first crawl; prod: after first crawl)

# Tech tracking
tech-stack:
  added:
    - aws-embedded-metrics>=3.0,<4 (3.5.0 local wheel; pinned major-range in requirements.txt)
  patterns:
    - "@metric_scope decorator auto-flush — caller stays sync, avoids Landmine 5 asyncio dance"
    - "EnvironmentCache patch + AWS_EMF_ENVIRONMENT=Local in test fixture — forces stdout sink when library config was initialized before tests"
    - "email.py log-but-never-raise analog for EMF emission (T-02-EMF-CRASH mitigation)"
    - "Static code-position assertion (TestEmissionPosition) — parse runner.py source, compare line numbers, pins Landmine 3"

key-files:
  created:
    - backend/app/core/cloudwatch_emf.py
    - backend/tests/test_cloudwatch_emf.py
  modified:
    - backend/app/crawlers/runner.py
    - backend/app/crawlers/ecs_rescrape_runner.py
    - backend/requirements.txt

key-decisions:
  - "emit_crawler_run_metrics wraps aws-embedded-metrics via @metric_scope auto-flush — caller stays sync, no asyncio.run() at call sites (Landmine 5)"
  - "start_ts is a fresh variable aliased to the existing t0 (Plan 03-03) so the EMF emission uses the same wall-clock window as runner.py's return-dict elapsed_seconds field. Single monotonic start, two readers, no drift."
  - "Rescrape path emits ONE aggregate record with adapter_name='aggregate', NOT per-adapter. run_rescrape_all_archived_pages returns an outcome-count dict without per-adapter breakdown, and plan 02-05's alarm filters on RunType=live — rescrape metrics are purely informational for dashboards, so aggregate is sufficient."
  - "Rescrape maps parsed_ok -> Ingested and parse_failed -> ParseFailures (the rescrape analogs of skipped_not_product per D-22). ingest_failed is intentionally omitted from the 3-metric set to keep OBS-02 schema stable."
  - "Test fixture patches aws_embedded_metrics.config.environment = 'Local' AND clears EnvironmentCache.environment = None in addition to setting AWS_EMF_ENVIRONMENT=Local. The library reads os.environ ONCE at config-module import; by pytest-collection time it's already cached. Terraform-provided env var works in production because it's set BEFORE process start."
  - "Failure isolation via try/except-log-but-never-raise at the public wrapper, not inside _emit_scoped. This preserves @metric_scope's auto-flush on the happy path while still catching any library-internal raise via the outer wrapper (T-02-EMF-CRASH)."

requirements-completed: [OBS-02]

# Metrics
duration: ~16min
completed: 2026-04-22
---

# Phase 02 Plan 03: CloudWatch EMF Crawler Metrics (OBS-02) Summary

**emit_crawler_run_metrics helper + live-path + rescrape-path emission + aws-embedded-metrics pin + 10-test OBS-02 regression suite. One EMF JSON line per run lands on stdout in the `CarModPicker/Crawlers` namespace with three metrics (Ingested/ParseFailures/ElapsedSeconds) and three dimensions (AdapterName × Environment × RunType). Landmines 3, 4, 5 pinned; email.py analog prevents emission failures from crashing run_crawler.**

## Performance

- Duration: ~16 min
- Started: 2026-04-22T22:03:37Z (approx)
- Completed: 2026-04-22T22:19:00Z (approx)
- Tasks: 2 (both TDD-flagged; implementation + test pair per plan 02-02 acknowledged pattern)
- Files created: 2
- Files modified: 3

## Accomplishments

- emit_crawler_run_metrics helper with triple-gated no-op (TESTING=true, APP_ENVIRONMENT not in {staging, production}, library exception) and all three metric units (Count/Count/Seconds)
- _emit_scoped with @metric_scope decorator — library auto-flushes on function exit, no async boilerplate at call sites (Landmine 5)
- runner.py live-path emission: from app.core.cloudwatch_emf import emit_crawler_run_metrics at top; start_ts = time.monotonic() before URL loop (aliased to existing t0); emit_crawler_run_metrics(run_type="live", parse_failures=skipped_not_product, ...) BEFORE logger.log summary line
- ecs_rescrape_runner.py rescrape-path emission: rescrape_start = time.monotonic() before rescrape call; emit_crawler_run_metrics(adapter_name="aggregate", run_type="rescrape", ingested=parsed_ok, parse_failures=parse_failed, ...) after rescrape returns and before complete_job
- requirements.txt: aws-embedded-metrics>=3.0,<4 in Observability block
- 10-test suite across 4 classes with autouse env-active fixture; passes under pytest -n auto
- Phase 1 SAFE gates preserved: 2229 pass, 6 skip (pre-existing). coverage fail-under=51 exits 0. OpenAPI snapshot unchanged (SAFE-05). Crawler characterization 5/5 (SAFE-07). Auth characterization 5/7 (2 pre-existing OAuth VCR cassette skips from Plan 02-01). test_log_propagation 6/6 (Plan 02-01 OBS-04 regression guard). test_sentry_init 25/25 (Plan 02-02 OBS-01 regression guard).

## Task Commits

1. Task 1 (feat 02-03): `4c60c4c` — cloudwatch_emf.py + runner.py + ecs_rescrape_runner.py + requirements.txt
2. Task 2 (test 02-03): `7b8ec02` — test_cloudwatch_emf.py (10 tests across 4 classes)

## Files Created/Modified

### Created

- `backend/app/core/cloudwatch_emf.py` — public emit_crawler_run_metrics + private @metric_scope-decorated _emit_scoped. Module docstring documents D-16..D-22 + Landmines 3/4/5 + email.py failure-isolation analog.
- `backend/tests/test_cloudwatch_emf.py` — 10 tests:
  - TestEnvGate (2): test_no_op_when_testing_true, test_no_op_when_development
  - TestEMFShape (6): test_envelope_namespace, test_dimension_set, test_top_level_dimension_values, test_metric_names_and_units, test_metric_values, test_rescrape_run_type
  - TestFailureIsolation (1): test_exception_does_not_propagate (email.py analog — T-02-EMF-CRASH)
  - TestEmissionPosition (1): test_runner_emits_before_summary (static code check — Landmine 3 gate)

### Modified

- `backend/app/crawlers/runner.py` — added `from app.core.cloudwatch_emf import emit_crawler_run_metrics` (line 36); added `start_ts = time.monotonic()` aliased to existing `t0` (line 528); added `emit_crawler_run_metrics(...)` call BEFORE the `logger.log(summary_level, "Adapter %s done...")` line (line 688 vs 697). Landmine 3 ordering pinned by `awk` line-compare + TestEmissionPosition.
- `backend/app/crawlers/ecs_rescrape_runner.py` — added `import time`; added lazy `from app.core.cloudwatch_emf import emit_crawler_run_metrics` inside main() (mirrors Sentry's lazy-import pattern); added `rescrape_start = time.monotonic()` before resolve_crawler_user; added `emit_crawler_run_metrics(adapter_name="aggregate", run_type="rescrape", ...)` after run_rescrape_all_archived_pages returns, BEFORE the downstream logger.info summary (Landmine 3 still applies even with an aggregate emission). Module docstring expanded to document the aggregate-vs-per-adapter decision.
- `backend/requirements.txt` — section heading relabeled `# Observability (Phase 2 / OBS-01 + OBS-02)`; appended `aws-embedded-metrics>=3.0,<4` after `sentry-sdk>=2.0,<3` with a comment referencing Landmine 4 runtime requirement.

## Rescrape Emission Placement Decision

The rescrape path (`run_rescrape_all_archived_pages` in archive_rescrape.py) returns an AGGREGATE outcome-count dict:
```python
{"parsed_ok": int, "parse_failed": int, "ingest_failed": int,
 "skipped_no_adapter": int, "skipped_no_html": int, "failures": list, ...}
```
It does NOT break down by adapter. Splitting by adapter would require a second pass over the crawled_pages table or threading per-adapter accumulators through the worker pool — not worth the complexity given plan 02-05's alarm filters on `RunType=live` (rescrape noise is explicitly excluded from the alarm by design).

**Decision:** emit ONE EMF record per rescrape task with `adapter_name="aggregate"` and the aggregate counts mapped as:
- `Ingested = parsed_ok` (successful re-parses)
- `ParseFailures = parse_failed` (rescrape analog of live path's `skipped_not_product`, per D-22 alias semantics)
- `ElapsedSeconds = wall-clock around the full main() body`

`ingest_failed`, `skipped_no_adapter`, `skipped_no_html` are intentionally omitted from the 3-metric set to keep the OBS-02 schema stable across live and rescrape — CloudWatch sees exactly the same metric names for both RunTypes, which lets dashboards and plan 02-05's alarm use a single metric query shape. The full outcome dict remains available in the BackgroundJob.result_summary DB row and the operator job-report email, so no signal is lost — just not promoted to custom CloudWatch metrics.

## HUMAN-UAT Prerequisite

After the App Runner + ECS deploy that ships this plan, the `CarModPicker/Crawlers` namespace in the target region (`us-east-1` per terraform) will NOT be populated until the first crawler run completes. Before plan 02-05's alarm UAT step 4 (`aws cloudwatch list-metrics --namespace CarModPicker/Crawlers`) can succeed:

1. Operator confirms `AWS_EMF_ENVIRONMENT=Local` is set in the App Runner service config (`aws apprunner describe-service --service-arn <arn> | jq '.Service.SourceConfiguration.ImageRepository.ImageConfiguration.RuntimeEnvironmentVariables.AWS_EMF_ENVIRONMENT'` should return `"Local"`). Set by plan 02-02 terraform — just a verification step here.
2. Operator confirms `AWS_EMF_ENVIRONMENT=Local` is set in the ECS task definition (`aws ecs describe-task-definition --task-definition <family> | jq '.taskDefinition.containerDefinitions[0].environment[] | select(.name == "AWS_EMF_ENVIRONMENT")'`). Same terraform source, same verification-only step.
3. Trigger at least one crawler run from the admin UI (or `python -m app.crawlers --adapter <small-adapter> --limit 10` via ECS task).
4. Wait ~5 min for CloudWatch EMF ingestion + metric extraction.
5. Run `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers --region us-east-1 | jq '.Metrics | length'` — expect ≥ 3 metric names × N adapters crawled.

If step 5 returns zero metrics despite a successful crawl, the diagnostic is:
- Grep CloudWatch Logs for the EMF line: `aws logs filter-log-events --log-group-name <apprunner log group> --filter-pattern '"_aws"'` — if lines appear, CloudWatch metric extraction didn't run (verify log group is in the same region as metrics query).
- If no EMF lines in logs, AWS_EMF_ENVIRONMENT wasn't applied or the library fell back to DefaultEnvironment — re-verify terraform apply succeeded and check the pod's environ for the var.

This UAT becomes plan 02-05's step 4 gate (same list-metrics command, same adapter-run-first prerequisite).

## Confirmation Plan 02-01 ContextVars Still Populated

Sanity check per output requirement: this plan's emit_crawler_run_metrics does NOT currently read `request_id_var` / `user_id_var` from plan 02-01's log_context module. EMF dimensions are bounded to `{AdapterName, Environment, RunType}` for cardinality reasons (D-19; adding request_id would blow up time-series count per run — one time series per invocation, useless for aggregates). The ContextVars remain populated in production:
- Plan 02-01's CLI bootstrap (`app/crawlers/__main__.py`) sets `request_id_var = f"cli:{os.getpid()}"` and `user_id_var = "cli"` BEFORE `main()` is invoked, which fires before `run_crawler()`.
- Plan 02-02's Sentry scope processor reads those ContextVars on every captured event.
- `test_log_propagation.py::test_cli_log_context` remains green in this plan's test runs.

If a future iteration wants per-request correlation between EMF records and log lines / Sentry events, the correct approach is NOT adding a 4th dimension but emitting `request_id` as a top-level EMF field (searchable via CloudWatch Logs Insights but not promoted to a metric). Out of scope for OBS-02.

## Phase 1 Gate Preservation

- SAFE-05 (OpenAPI snapshot): `pytest tests/test_openapi_snapshot.py` exits 0. No route changes in this plan.
- SAFE-06 (Auth characterization): 5/7 pass (2 pre-existing OAuth VCR cassette skips from Plan 02-01's STATE.md — test_characterization_oauth_link + test_characterization_oauth_signin rely on cassettes not in the repo).
- SAFE-07 (Crawler characterization): 5/5 pass. runner.py's start_ts + emit call + ecs_rescrape_runner.py's aggregate emission did NOT change adapter parsing behavior.
- Coverage fail-under=51: full suite exits 0 with 2229 passed, 6 skipped (app/core/cloudwatch_emf.py contributes +26 statements, all covered by the new 10-test suite).
- Plan 02-01 OBS-04 regression guard: test_log_propagation 6/6 pass.
- Plan 02-02 OBS-01 regression guard: test_sentry_init 25/25 pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] aws-embedded-metrics library config cache requires EnvironmentCache patch in tests**
- Found during: Task 2 (first pytest run — 6/10 TestEMFShape tests failed with no EMF line on stdout + error logs showing the library fell through to DefaultEnvironment -> TCP agent sink at 0.0.0.0:25888 -> Connection refused).
- Issue: The plan's test skeleton assumed `monkeypatch.setenv("AWS_EMF_ENVIRONMENT", "Local")` would force the Local (stdout) sink. In practice, `aws_embedded_metrics.config` reads `os.environ["AWS_EMF_ENVIRONMENT"]` ONCE at module import and caches the result. By the time the test fixture runs, the config is already frozen to empty-string (since conftest.py doesn't set AWS_EMF_ENVIRONMENT at import time). The library's environment_detector then probes Lambda -> EC2 -> DefaultEnvironment and caches the detected env in EnvironmentCache.environment. Both layers of cache need to be overridden for the fixture to work.
- Fix: In the TestEMFShape.`_active_env` autouse fixture, in addition to `monkeypatch.setenv("AWS_EMF_ENVIRONMENT", "Local")`, explicitly patch `get_config().environment = "Local"` and reset `EnvironmentCache.environment = None`. `monkeypatch.setattr` handles cleanup on test exit so no leakage between tests.
- Files modified: backend/tests/test_cloudwatch_emf.py (autouse fixture extended — visible in file lines ~71-80).
- Verification: All 10 tests pass on second run. `_active_env` comment in the test file documents the reasoning so future maintainers don't re-hit this.
- Committed in: `7b8ec02` (Task 2 test-suite commit — the fix landed as part of the initial test-file write, not a separate commit, because TDD-pair structure batches test+fixture together).
- Note: This does NOT affect production behavior — terraform sets `AWS_EMF_ENVIRONMENT=Local` at process start, BEFORE the library's config module is imported, so the library picks it up correctly on startup.

**2. [Rule 3 - Acknowledged] Python env missing aws-embedded-metrics at plan start**
- Found during: Task 1 signature verification (`python -c "from app.core.cloudwatch_emf import emit_crawler_run_metrics"`).
- Issue: `ModuleNotFoundError: No module named 'aws_embedded_metrics'` — package not yet installed in the local pyenv (plan had just added it to requirements.txt, but `pip install` hadn't run).
- Fix: `pip install 'aws-embedded-metrics>=3.0,<4'` (resolved to 3.5.0). No repo changes.
- Files modified: None (env-only).
- Verification: `python -c "from aws_embedded_metrics import metric_scope; print('ok')"` succeeds.
- Committed in: N/A (environment-only fix; aws-embedded-metrics pinned in requirements.txt via `4c60c4c`).

### Acknowledged — Plan structure

**3. [Plan structure] TDD tasks 1 + 2 as implementation+test pair, not interleaved RED/GREEN**
- Context: Both tasks have `tdd="true"`. Task 1's `<verify>` block references only pre-existing characterization tests, not tests from the new file. Task 2 creates the test file. A literal RED-then-GREEN cycle would require Task 1 to emit a failing import against a not-yet-existing module, which doesn't match the plan's structure.
- Resolution: Task 1 = implementation commit (`4c60c4c`); Task 2 = test-suite commit (`7b8ec02`). Commit order `feat -> test` (inverse of canonical `RED -> GREEN`) matches the plan's literal task sequence. Same pattern was used and documented in Plan 02-02's SUMMARY.md "Acknowledged" section 3.
- Impact: No functional impact; TDD intent (tests pin behavior) is preserved because all 10 tests pass against the already-existing module on first run (after the Deviation #1 fix).

### Deviations total

- 1 Rule 3 blocking fix (EnvironmentCache patch)
- 1 env-only fix (pip install, no repo change)
- 1 plan-structure acknowledgement (feat-then-test, precedent: Plan 02-02)

## Known Stubs

None. All production code paths are live:
- emit_crawler_run_metrics is called from both runner.py (live) and ecs_rescrape_runner.py (rescrape).
- Staging + production will emit EMF records as soon as the first crawler run completes.
- Dev + test environments correctly no-op via the env gate.
- Test fixture overrides are test-only; production uses terraform's `AWS_EMF_ENVIRONMENT=Local` at process start.

## Threat Flags

None beyond those declared in 02-03-PLAN.md threat_model. All five STRIDE threats mitigated and pinned:

- **T-02-METRIC-CARD** (cost / DoS): Bounded dimension cardinality — AdapterName values are code-defined (ADAPTER_REGISTRY keys, not user input). 114 adapters × 2 envs × 2 RunTypes = 456 time series × 3 metrics = 1,368 possible. Only billed on emit; active footprint starts at ~60 metrics after one full crawl. HUMAN-UAT prerequisite documents the `list-metrics | length <= 456` check.
- **T-02-TEST-POLLUTION**: TestEnvGate::test_no_op_when_testing_true + test_no_op_when_development pin both gate branches. `grep -n "TESTING.*true" backend/app/core/cloudwatch_emf.py` returns 1 match. conftest.py sets TESTING=true at import time.
- **T-02-EMF-DROPPED** (Landmine 3): TestEmissionPosition::test_runner_emits_before_summary static code check AND `awk` line-compare both confirm emit < summary in runner.py. Any future reordering trips the test at PR time.
- **T-02-EMF-SINK-DRIFT** (Landmine 4): Out of scope for this plan (terraform work done by plan 02-02); HUMAN-UAT step 2 + step 5 verify runtime state. Test fixture overrides explicitly document this production-vs-test asymmetry.
- **T-02-EMF-CRASH**: Emission wrapped in try/except with logger.error; TestFailureIsolation::test_exception_does_not_propagate asserts no exception escapes. `grep -n "except Exception" backend/app/core/cloudwatch_emf.py` returns 1 match.

## TDD Gate Compliance

Both tasks have `tdd="true"`. Commit order was feat(02-03) -> test(02-03) per Deviation #3 (same pattern as Plan 02-02). If the TDD gate validator requires a RED commit, none exists by name — both commits pass their <verify> blocks, and the test-suite commit's 10 tests all pass against the now-existing cloudwatch_emf.py module.

Note: the plan itself does not have `type: tdd` at the frontmatter level — only individual tasks carry `tdd="true"`. The plan is `type: execute`, wave 3 — the plan-level TDD gate enforcement flow in the GSD workflow does not apply.

## Issues Encountered

- aws-embedded-metrics config cache required a test-fixture adjustment (Deviation #1) — surfaced only on first pytest run; fixed in the same commit as the test file since TDD-pair commits batch test+fixture together.
- Local pyenv missing aws-embedded-metrics at plan start — fixed via pip install (Deviation #2); no repo change.

## User Setup Required

None beyond what plan 02-02 already specified. `AWS_EMF_ENVIRONMENT=Local` is set by plan 02-02's terraform on both App Runner and ECS. This plan's code changes will no-op locally (development env) and emit on every crawler run in staging/production automatically.

HUMAN-UAT (once staging is deployed with this code + plan 02-02's terraform): trigger ONE crawler run, then run `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers` to verify metrics arrived. Full runbook in the "HUMAN-UAT Prerequisite" section above.

## Next Phase Readiness

- **Plan 02-05 (CloudWatch composite parse-failure alarm)**: Unblocked. Can now reference `CarModPicker/Crawlers/ParseFailures` with `Dimensions.RunType=live` for the alarm metric_query. `adapter_name="aggregate"` records from rescrape will NOT match the alarm filter by construction (RunType=rescrape, not live). Alarm threshold math per D-22: ParseFailures >= skipped_not_product threshold.
- **Future CloudWatch dashboards**: Can render per-adapter Ingested/ParseFailures/ElapsedSeconds time series out of the box. Plan 02-02's AWS_EMF_ENVIRONMENT=Local wiring + this plan's EMF emission = zero additional terraform needed for dashboards.
- **Phase 3 completion**: No blockers — additive changes to runner.py (single line: the `emit_crawler_run_metrics(...)` call block) and ecs_rescrape_runner.py (main() body), no behavior change on non-emission paths. Plan 03-03's result-dict schema is untouched.

## Self-Check: PASSED

Files created/modified exist:
- backend/app/core/cloudwatch_emf.py — FOUND
- backend/tests/test_cloudwatch_emf.py — FOUND
- backend/app/crawlers/runner.py — FOUND (modified, emission at line 688)
- backend/app/crawlers/ecs_rescrape_runner.py — FOUND (modified, aggregate emission in main())
- backend/requirements.txt — FOUND (modified, aws-embedded-metrics>=3.0,<4 at line 64)
- .planning/phases/02-observability/02-03-SUMMARY.md — FOUND (this file)

Commits in git log:
- 4c60c4c feat(02-03): EMF crawler run metrics + runner/rescrape emission (OBS-02) — FOUND
- 7b8ec02 test(02-03): OBS-02 EMF envelope + dimension + position tests — FOUND

All grep acceptance criteria verified. All Phase 1 SAFE gates + plan 02-01 + plan 02-02 regression tests green. 10 OBS-02 tests all pass. EMF emission position verified by awk line-compare and TestEmissionPosition static code check.

---
*Phase: 02-observability*
*Completed: 2026-04-22*
