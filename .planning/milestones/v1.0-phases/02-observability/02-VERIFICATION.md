---
phase: 02-observability
verified: 2026-04-22T23:40:00Z
status: verified
score: 5/5 must-haves verified; live-ops UAT manually signed off by user 2026-04-23
overrides_applied: 0
human_verification:
  - test: "Backend unhandled exception reaches Sentry with request_id + user_id + SQLAlchemy context"
    expected: "Sentry event appears in staging/prod Sentry project with tags.request_id (uuid), user.id (stringified id), environment=staging|production, server_name=apprunner-backend, SQLAlchemy breadcrumbs attached. No email/username visible (send_default_pii=False)."
    why_human: "Requires live Sentry project + deployed App Runner + populated SENTRY_DSN secret. Cannot verify dashboard receipt or SQLAlchemy breadcrumb enrichment from source alone — integrations are loaded + scope processor is unit-tested, but end-to-end event delivery is a live-AWS observation (02-HUMAN-UAT.md Item 1)."
  - test: "Crawler background-task logger.error reaches Sentry with bg:crawler request_id + server_name=ecs-crawler"
    expected: "Sentry event captured from ECS crawler task with tags.request_id starting with 'bg:crawler:', server_name=ecs-crawler, environment tag matches deploy target."
    why_human: "Requires staging ECS crawler deploy + populated SENTRY_DSN. bg_log_context is unit-tested, Sentry init is unit-tested, but the interaction (events captured inside bg_log_context carry bg: prefix in live Sentry) requires ECS run + Sentry dashboard observation (02-HUMAN-UAT.md Item 2)."
  - test: "HTTPException / 4xx response does NOT appear in Sentry (ignore_errors working)"
    expected: "After triggering a 404 in staging, no new Sentry event arrives within 2 minutes."
    why_human: "Integration test in test_sentry_init.py pins the string-form ignore_errors behavior in isolation, but real-world confirmation against a live DSN that the envelopes are in fact suppressed (not silently sent) is an operator observation (02-HUMAN-UAT.md Item 3)."
  - test: "EMF metrics land in CloudWatch CarModPicker/Crawlers namespace after a crawler run"
    expected: "`aws cloudwatch list-metrics --namespace CarModPicker/Crawlers --dimensions Environment=staging RunType=live` returns ≥1 metric per crawled adapter with metric names {Ingested, ParseFailures, ElapsedSeconds} and dimensions {AdapterName, Environment, RunType}."
    why_human: "Env-gated emission is unit-tested (stdout EMF envelope pinned). Actual EMF extraction by CloudWatch Logs + metric promotion requires the awslogs driver pipeline to function on App Runner/ECS Fargate with AWS_EMF_ENVIRONMENT=Local. Landmine 4 (auto-detect gap) is a runtime concern (02-HUMAN-UAT.md Item 4)."
  - test: "Parse-failure alarm fires SNS email when rate exceeds 50%, recovers when rate drops"
    expected: "After synthetic put-metric-data writes (ParseFailures=50, Ingested=5 with Environment=staging, RunType=live), within ~2h the carmodpicker-<env>-crawler-parse-failure-composite alarm transitions to ALARM, SNS email arrives at both subscribed addresses with 'Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook' in the body, and after traffic stops the alarm transitions back to OK with recovery email."
    why_human: "Alarm resource is statically verified in terraform/monitoring.tf (metric_query structure, expression, threshold, treat_missing_data, ok_actions symmetry). Actual firing + SNS delivery requires deployed terraform + AWS clock advancing through the 3600s evaluation window (02-HUMAN-UAT.md Item 5)."
  - test: "Frontend unhandled error reaches Sentry with resolved sourcemap + on-error replay attached"
    expected: "Throwing in a staging page produces a Sentry event within ~30s with stack trace pointing to real .tsx paths (sourcemap upload worked), Session Replay attached (on-error=1.0), no ambient replay for non-throwing sessions, user.id attached if logged in (no email/username). Errors on /login do NOT get replay attached (beforeErrorSampling)."
    why_human: "Vitest unit tests pin env gate + config invariants + beforeErrorSampling behavior, but sourcemap upload requires GitHub Actions CI with SENTRY_AUTH_TOKEN + ORG + PROJECT secrets, and live replay attachment requires a real Sentry project (02-HUMAN-UAT.md Item 6)."
  - test: "OBS-04 request_id propagation on every CloudWatch log line during a live request"
    expected: "In CloudWatch Logs Insights, filtering /aws/apprunner/.../application by a known request_id returns ≥1 record, EVERY record during that request carries request_id=<uuid> and user_id=<id> (never '-'), and sqlalchemy.engine records during that request also carry the same request_id."
    why_human: "caplog_with_context + test_log_propagation pins the invariant at unit-test scope, but Landmine 4-style issues where production log config drops the filter can only be caught against live CloudWatch Logs (02-HUMAN-UAT.md Item 7)."
  - test: "Staging → Prod Promotion Gate (D-58): 24h staging bake with zero unexplained Sentry events before prod terraform apply"
    expected: "Staging deploy remains up for ≥24h with no unexplained Sentry events, all 7 UAT items pass, then operator runs `terraform -chdir=terraform apply -var-file=prod.tfvars`."
    why_human: "This is explicitly an operator-gated step per 02-05-PLAN.md frontmatter `autonomous: false`. The executor agent's scope ends at code/docs/UAT-file artifacts. Prod apply + 24h bake observation is human-only by design."
---

# Phase 02: Observability Verification Report

**Phase Goal:** Production errors are visible in Sentry, per-adapter crawler metrics flow into CloudWatch, and a parse-failure alarm fires automatically — all without changing any URL, schema, or external contract.
**Verified:** 2026-04-22T23:40:00Z
**Status:** human_needed
**Re-verification:** No — initial verification.

## Goal Achievement

### Observable Truths

| # | Truth (from ROADMAP Success Criteria) | Status | Evidence |
|---|---------------------------------------|--------|----------|
| 1 | Unhandled exceptions in the FastAPI app appear in Sentry with request ID, user ID, and SQLAlchemy query context attached | ✓ CODE-VERIFIED / ? live-ops pending | `backend/app/core/sentry.py::_before_send` attaches `tags.request_id` from `request_id_var.get()` and `user.id` from `user_id_var.get()` (lines 90-104). `init_sentry` registers `SqlalchemyIntegration()` (line 143) + `FastApiIntegration(transaction_style="endpoint")` (line 141) + `StarletteIntegration(transaction_style="endpoint")` (line 141). Called in `main.py:72` BEFORE `app = FastAPI()`. 18 tests in `test_sentry_init.py` (40 pass, 0 fail — TestInitGating ×3, TestInitKwargs ×7 including `test_all_four_integrations_loaded`, TestTracesSampler ×3, TestBeforeSend ×3, TestIgnoreErrorsIntegration ×2). Live Sentry dashboard receipt is a human-UAT gate. |
| 2 | After a crawler run, CloudWatch shows per-adapter Ingested, ParseFailures, ElapsedSeconds metrics in CarModPicker/Crawlers namespace | ✓ CODE-VERIFIED / ? live-ops pending | `backend/app/core/cloudwatch_emf.py::_emit_scoped` (lines 109-132) calls `metrics.set_namespace("CarModPicker/Crawlers")`, `metrics.set_dimensions({"AdapterName", "Environment", "RunType"})`, and `metrics.put_metric` for Ingested/Count, ParseFailures/Count, ElapsedSeconds/Seconds. Called from `runner.py:688` with `run_type="live"` BEFORE `logger.log(summary_level, "Adapter %s done")` at `runner.py:695` (Landmine 3 pinned by `TestEmissionPosition::test_runner_emits_before_summary`). Rescrape path emits at `ecs_rescrape_runner.py:137` with `run_type="rescrape"`, `adapter_name="aggregate"`. 10 tests in `test_cloudwatch_emf.py` all pass. AWS_EMF_ENVIRONMENT=Local set in both `terraform/apprunner.tf:260` + `terraform/ecs.tf:225`. CloudWatch ingestion from awslogs pipeline is a human-UAT gate. |
| 3 | A CloudWatch alarm triggers an SNS → SES email when any adapter's parse-failure rate exceeds 50% | ✓ CODE-VERIFIED / ? live-ops pending (with D-24 deviation: SNS → email, not SNS → SES) | `terraform/monitoring.tf:165-220` defines `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` with `comparison_operator="GreaterThanThreshold"` (strict `>`), `threshold=0.5`, `evaluation_periods=1`, `datapoints_to_alarm=1`, `treat_missing_data="notBreaching"`, metric_query blocks for Ingested (Sum, `RunType=live`, `Environment=var.environment`), ParseFailures (Sum, same filter), and expression `IF((ingested + failures) < 10, 0, failures / (ingested + failures))` with `return_data=true`. `alarm_actions=[aws_sns_topic.alarms.arn]` + `ok_actions=[aws_sns_topic.alarms.arn]` (D-26 symmetry). `alarm_description` contains the literal `"Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"` (D-27). `# TODO(phase-3)` for_each marker present (line 216). `terraform validate` + `terraform fmt -check` both exit 0. **Deviation:** Per D-24 + 02-HUMAN-UAT.md deviation log, SNS fan-out is via `email` protocol (not SES) — operator email identical. Live alarm firing + SNS delivery is a human-UAT gate. |
| 4 | Frontend runtime errors appear in Sentry (or equivalent) via an ErrorBoundary integration | ✓ CODE-VERIFIED / ? live-ops pending | `frontend/src/components/common/ErrorBoundary.tsx:24-29` calls `Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } })` in `componentDidCatch`, additive to existing styled fallback UI. `frontend/src/main.tsx:13` calls `initSentry()` BEFORE `createRoot`. `frontend/src/lib/sentry.ts` defines env-gated init (MODE!=='development' + non-empty DSN) with `sendDefaultPii: false`, `tracesSampleRate: 0.05`, `replaysSessionSampleRate: 0`, `replaysOnErrorSampleRate: 1.0`, `beforeErrorSampling` blocking `/login`, `/register`, `/oauth-callback`, `/reset-password`, `/2fa`. `frontend/src/contexts/AuthContext.tsx:60` calls `Sentry.setUser(user ? { id: String(user.id) } : null)` (id-only, no email/username per D-40). `@sentry/react@^10.0.0` + `@sentry/vite-plugin@^4.0.0` pinned in package.json. `vite.config.ts:44` sets `sourcemap: 'hidden'` (Landmine 12). `sentryVitePlugin` gated on `process.env.CI && process.env.SENTRY_AUTH_TOKEN` (line 8). 21 vitest tests all pass. Live sourcemap upload + event receipt is a human-UAT gate. |
| 5 | OBS-04 log propagation regression guard (every log line during a request includes request_id + user_id) | ✓ CODE-VERIFIED / ? live-ops pending | `backend/app/core/log_context.py` defines `bg_log_context(task_name, job_id=None)` (lines 17-34) using token-based ContextVar set/reset (re-entrant-safe). CLI bootstrap in `backend/app/crawlers/__main__.py:21-23` sets `request_id_var=cli:{pid}` + `user_id_var=cli` INSIDE `if __name__ == "__main__":` guard (T-02-TEST-POLLUTION mitigation). `caplog_with_context` fixture in `backend/tests/conftest.py:421-433` attaches `RequestContextFilter` to caplog.handler (Landmine 15 mitigation). 6 tests in `test_log_propagation.py` all pass (1 skip: sqlalchemy echo off in test DB — graceful skip per plan). Live CloudWatch Logs propagation is a human-UAT gate. |

**Score:** 5/5 truths verified at code/infrastructure scope. Live-ops validation deferred to operator UAT per 02-HUMAN-UAT.md (explicit plan-level `autonomous: false` on 02-05).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/core/log_context.py` | `bg_log_context` contextmanager exported (re-entrant via token reset) | ✓ VERIFIED | Lines 17-34: `@contextmanager def bg_log_context(task_name, job_id=None)` with `request_id_var.set(f"bg:{task_name}:{job_id or '-'}")`, `user_id_var.set("bg")`, try/finally token reset. Existing `request_id_var`, `user_id_var`, `RequestContextFilter` unchanged. |
| `backend/app/crawlers/__main__.py` | CLI context init + init_sentry(crawler-cli) inside `__main__` guard | ✓ VERIFIED | Lines 16-23: `from app.core.sentry import init_sentry` at module top; inside `if __name__ == "__main__":` guard sequentially `init_sentry(server_name="crawler-cli")` → `request_id_var.set(f"cli:{os.getpid()}")` → `user_id_var.set("cli")` → `main()`. |
| `backend/tests/test_log_propagation.py` | OBS-04 regression test module, ≥60 lines, 6 tests | ✓ VERIFIED | File exists (7684 bytes); `grep -c "^def test_"` returns 6 (test_log_propagation_request_scope, test_bg_log_context, test_bg_log_context_job_id_none, test_bg_log_context_resets, test_cli_log_context, test_log_propagation_sqlalchemy). All pass. |
| `backend/tests/conftest.py` | `caplog_with_context` fixture + `_CapturingTransport` + `sentry_events` fixture | ✓ VERIFIED | Line 421: `def caplog_with_context(...)`. Line 446: `class _CapturingTransport(_SentryTransport)`. Line 472: `def sentry_events(...)`. Both pin Landmine 15 (caplog filter not inherited) and Landmine 3 (2.x `capture_envelope` API). |
| `backend/app/core/sentry.py` | `init_sentry(*, server_name)` + `_traces_sampler` + `_before_send`, ≥60 lines | ✓ VERIFIED | 148 lines. Line 107: `def init_sentry(*, server_name: str)`. Triple env gate (TESTING / APP_ENVIRONMENT / DSN). All 4 integrations (FastApi, Starlette, Sqlalchemy, Logging) attached. `ignore_errors` strings for HTTPException + RateLimitExceeded. `send_default_pii=False`. |
| `backend/app/core/config.py` | `SENTRY_DSN`, `SENTRY_RELEASE`, `SENTRY_SERVICE_NAME` Pydantic fields | ✓ VERIFIED | All three fields present (grep confirmed in plan 02-02 SUMMARY); attribute presence verified via `python -c "from app.core.config import settings; assert hasattr(settings, 'SENTRY_DSN')..."` passing per plan 02-02 acceptance. |
| `backend/requirements.txt` | `sentry-sdk>=2.0,<3` + `aws-embedded-metrics>=3.0,<4` | ✓ VERIFIED | Line 58: `sentry-sdk>=2.0,<3`. Line 64: `aws-embedded-metrics>=3.0,<4`. |
| `backend/tests/test_sentry_init.py` | OBS-01 unit + integration coverage, ≥100 lines, ≥15 tests | ✓ VERIFIED | 8466 bytes. `grep -c "^    def test_"` returns 18 (includes parametrized subtests; 5 test classes across TestInitGating, TestInitKwargs, TestTracesSampler, TestBeforeSend, TestIgnoreErrorsIntegration). All 18 pass. |
| `backend/app/core/cloudwatch_emf.py` | `emit_crawler_run_metrics(*, adapter_name, run_type, ingested, parse_failures, elapsed_seconds)`, ≥40 lines | ✓ VERIFIED | 133 lines. Line 60: `def emit_crawler_run_metrics(*, ...)` with keyword-only args. Triple gate (TESTING/APP_ENVIRONMENT/exception). `@metric_scope` decorator on `_emit_scoped` (line 109 — Landmine 5 auto-flush). |
| `backend/app/crawlers/runner.py` | `start_ts` before URL loop, `emit_crawler_run_metrics(..., run_type="live")` BEFORE summary log | ✓ VERIFIED | Line 36: `from app.core.cloudwatch_emf import emit_crawler_run_metrics`. Line 688: emit call (before line 695 `logger.log(summary_level,...)` — Landmine 3 preserved). `parse_failures=skipped_not_product` (D-22 pinned at line 692). |
| `backend/app/crawlers/ecs_rescrape_runner.py` | Rescrape emission with `run_type="rescrape"` | ✓ VERIFIED | Line 69: `init_sentry(server_name="ecs-crawler")`. Line 76: lazy import. Line 137: `emit_crawler_run_metrics(adapter_name="aggregate", run_type="rescrape", ...)`. |
| `backend/tests/test_cloudwatch_emf.py` | OBS-02 envelope + dimensions + metrics + env gate + emission position, ≥80 lines, ≥9 tests | ✓ VERIFIED | 7684 bytes. `grep -c "^    def test_"` returns 10 (TestEnvGate ×2, TestEMFShape ×6, TestFailureIsolation ×1, TestEmissionPosition ×1). All 10 pass. |
| `frontend/src/lib/sentry.ts` | `initSentry()` with env gate + Session Replay on-error + `beforeErrorSampling` auth gate, ≥30 lines | ✓ VERIFIED | 73 lines. `export function initSentry()` at line 36. Dual env gate (MODE!=='development' + non-empty DSN). `sendDefaultPii: false`, `tracesSampleRate: 0.05`, `replaysSessionSampleRate: 0`, `replaysOnErrorSampleRate: 1.0`. `beforeErrorSampling` blocks `/login`, `/register`, `/oauth-callback`, `/reset-password`, `/2fa`. |
| `frontend/src/main.tsx` | `initSentry()` call BEFORE `createRoot` | ✓ VERIFIED | Line 10: import. Line 13: `initSentry();` (line < line 20 `createRoot(...)`). |
| `frontend/src/components/common/ErrorBoundary.tsx` | `Sentry.captureException` in `componentDidCatch`, additive | ✓ VERIFIED | Line 1: `import * as Sentry from '@sentry/react'`. Lines 26-28: `Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } })` inside `componentDidCatch` after existing console.error. Class component + styled fallback UI preserved (lines 31-58). |
| `frontend/src/contexts/AuthContext.tsx` | `Sentry.setUser({id})` in useEffect on `[user]` | ✓ VERIFIED | Line 2: `import * as Sentry from '@sentry/react'`. Line 60: `Sentry.setUser(user ? { id: String(user.id) } : null)` in useEffect with `[user]` dep. No email/username (D-40 + T-02-PII-SENTRY). |
| `frontend/src/lib/sentry.test.ts` | OBS-05 vitest coverage, ≥80 lines | ✓ VERIFIED | 5348 bytes, 19 tests (env gate ×3, config invariants ×4, beforeErrorSampling ×12 parametrized). All pass. |
| `frontend/src/components/common/ErrorBoundary.test.tsx` | render-throwing-child → `Sentry.captureException` assertion, ≥30 lines | ✓ VERIFIED | 2882 bytes, 2 tests (safe children path + throwing child → captureException called once with componentStack extra). All pass. |
| `frontend/package.json` | `@sentry/react@^10` + `@sentry/vite-plugin@^4` | ✓ VERIFIED | grep returns 2 matches for the two dep patterns. |
| `frontend/vite.config.ts` | Conditional sentryVitePlugin + `build.sourcemap: 'hidden'` | ✓ VERIFIED | Line 1: import. Line 8: `const isCIBuild = !!process.env.CI && !!process.env.SENTRY_AUTH_TOKEN`. Lines 15-24: conditional spread. Line 44: `sourcemap: 'hidden'`. |
| `terraform/secretsmanager.tf` | `aws_secretsmanager_secret.sentry_dsn` + version | ✓ VERIFIED | Lines 39-47: resource + version + `secret_id` + `var.sentry_dsn`. |
| `terraform/variables.tf` | `sentry_dsn` (sensitive), `sentry_release`, `disabled_parse_alarms` | ✓ VERIFIED | Lines 133, 140, 146 (all three declared; `sentry_dsn` has `sensitive = true`). |
| `terraform/apprunner.tf` | SENTRY_DSN secret inject + 3 env vars + IAM grants on BOTH access + instance roles | ✓ VERIFIED | Line 36 (access role policy Resource), Line 73 (instance role policy Resource), Line 258 (SENTRY_RELEASE), Line 259 (SENTRY_SERVICE_NAME="apprunner-backend"), Line 260 (AWS_EMF_ENVIRONMENT="Local"), Line 268 (SENTRY_DSN in runtime_environment_secrets). `grep -c "aws_secretsmanager_secret.sentry_dsn.arn"` returns 2 — both IAM policies hit (T-02-IAM-DRIFT mitigated). |
| `terraform/ecs.tf` | SENTRY_DSN secret inject + env vars + IAM grant on task execution role | ✓ VERIFIED | Line 87 (task execution role policy Resource), Line 223 (SENTRY_RELEASE), Line 224 (SENTRY_SERVICE_NAME="ecs-crawler"), Line 225 (AWS_EMF_ENVIRONMENT="Local"), Lines 240-241 (SENTRY_DSN secrets[] entry). `grep -c "aws_secretsmanager_secret.sentry_dsn.arn"` returns 2. |
| `terraform/monitoring.tf` | `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` with metric-math + TODO marker | ✓ VERIFIED | Lines 165-220 (resource definition). `GreaterThanThreshold`, `threshold=0.5`, `evaluation_periods=1`, `datapoints_to_alarm=1`, `treat_missing_data=notBreaching`. Three metric_query blocks (ingested/failures/rate). Expression literal `"IF((ingested + failures) < 10, 0, failures / (ingested + failures))"`. `return_data=true` on rate. NO top-level `period` (Landmine 7). `alarm_actions` + `ok_actions` both `[aws_sns_topic.alarms.arn]`. Description contains runbook anchor. `# TODO(phase-3)` marker at line 216. |
| `.planning/codebase/CONCERNS.md` | Crawler Drift Runbook section at `#crawler-drift-runbook` | ✓ VERIFIED | Line 226: `## Crawler Drift Runbook`. Line 228: `<a id="crawler-drift-runbook"></a>` — matches the anchor referenced in `terraform/monitoring.tf:167` alarm_description. |
| `.planning/phases/02-observability/02-HUMAN-UAT.md` | 7-item D-62 checklist + D-58 staging→prod gate, ≥80 lines | ✓ VERIFIED | 138 lines. `grep -c "^### Item "` returns 7 (items 1-7 across OBS-01 ×3, OBS-02, OBS-03, OBS-04, OBS-05). "Staging → Prod Promotion Gate (D-58)" section present with 24h bake requirement. SNS → email deviation documented (D-24). `var.environment` substitution documented. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `backend/app/core/sentry.py::_before_send` | `backend/app/core/log_context.py::request_id_var + user_id_var` | ContextVar.get() inside before_send callback | ✓ WIRED | Lines 98-99: `rid = request_id_var.get()` + `uid = user_id_var.get()`. Attaches to `event["tags"]["request_id"]` + `event["user"]["id"]` only when non-default. Pinned by TestBeforeSend (3 tests). |
| `backend/app/main.py` | `backend/app/core/sentry.py::init_sentry` | call with server_name='apprunner-backend' BEFORE FastAPI() instantiation | ✓ WIRED | Line 42: import. Line 72: `init_sentry(server_name="apprunner-backend")`. Line 72 < line of `app = FastAPI(...)` (per plan 02-02 acceptance). |
| `backend/app/crawlers/__main__.py` | `init_sentry` + `bg/cli context` | Sentry init + ContextVar set inside `__main__` guard | ✓ WIRED | Lines 20-22: `init_sentry(server_name="crawler-cli")` → `request_id_var.set(f"cli:{os.getpid()}")` → `user_id_var.set("cli")` — all inside guard. |
| `backend/app/crawlers/ecs_runner.py` | `init_sentry` | inside main() body (lazy import) | ✓ WIRED | Line 67: `from app.core.sentry import init_sentry`. Line 69: `init_sentry(server_name="ecs-crawler")`. |
| `backend/app/crawlers/ecs_rescrape_runner.py` | `init_sentry` + `emit_crawler_run_metrics` | inside main() body | ✓ WIRED | Line 69: init_sentry. Line 76: EMF import. Line 137: emit call with `run_type="rescrape"`. |
| `backend/app/crawlers/runner.py` | `emit_crawler_run_metrics` | call AFTER URL loop, BEFORE logger.log summary | ✓ WIRED | Line 688 (emit) < line 695 (logger.log summary). Landmine 3 static-check test passing. |
| `terraform/apprunner.tf runtime_environment_secrets` | `aws_secretsmanager_secret_version.sentry_dsn.arn` | ARN reference | ✓ WIRED | Line 268: `SENTRY_DSN = aws_secretsmanager_secret_version.sentry_dsn.arn`. |
| `terraform/apprunner.tf IAM policies (BOTH access + instance roles)` | `aws_secretsmanager_secret.sentry_dsn.arn` | Resource arrays | ✓ WIRED | Lines 36 + 73 — both hit. T-02-IAM-DRIFT mitigated. |
| `terraform/ecs.tf task execution role IAM` | `aws_secretsmanager_secret.sentry_dsn.arn` | Resource array + secrets[] | ✓ WIRED | Lines 87 + 241 — both hit. |
| `frontend/src/main.tsx` | `initSentry` | BEFORE createRoot | ✓ WIRED | Line 13 (initSentry) < line 20 (createRoot). |
| `frontend/src/contexts/AuthContext.tsx useEffect` | `Sentry.setUser` | `[user]` dependency | ✓ WIRED | Line 60 inside useEffect with `[user]` dep. Null on logout (user becomes null → setUser(null)). |
| `frontend/src/components/common/ErrorBoundary.tsx componentDidCatch` | `Sentry.captureException` | extra.componentStack | ✓ WIRED | Lines 26-28 — component stack forwarded. |
| `frontend/vite.config.ts plugins[]` | `sentryVitePlugin` | conditional spread on CI + SENTRY_AUTH_TOKEN | ✓ WIRED | Line 8 (isCIBuild) gates lines 15-24 (conditional spread). |
| `alarm description` → `.planning/codebase/CONCERNS.md#crawler-drift-runbook` | string description surfaced in SNS email | ✓ WIRED | `terraform/monitoring.tf:167` alarm_description literal matches CONCERNS.md anchor `<a id="crawler-drift-runbook"></a>` at line 228. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `_before_send` (backend sentry.py) | `rid`, `uid` | `request_id_var.get()`, `user_id_var.get()` | Yes — populated by request_context_middleware (HTTP), bg_log_context (bg tasks), `__main__.py` CLI bootstrap | ✓ FLOWING |
| `emit_crawler_run_metrics` (runner.py call) | `adapter_name`, `ingested`, `skipped_not_product` | runner local variables that accumulate during URL loop | Yes — incremented in adapter loop (observed in runner.py body) | ✓ FLOWING |
| `emit_crawler_run_metrics` (ecs_rescrape_runner.py) | `parsed_ok`, `parse_failed` | `run_rescrape_all_archived_pages` return dict | Yes — aggregate result dict from rescrape subsystem | ✓ FLOWING |
| alarm `metric_query` | Ingested + ParseFailures Sum from CloudWatch | CloudWatch ingests EMF JSON emitted by emit_crawler_run_metrics on crawler runs | Live-ops dependency — staging requires crawler run + AWS_EMF_ENVIRONMENT=Local pipeline | ? LIVE-OPS |
| `Sentry.setUser({id})` (AuthContext) | `user.id` | AuthContext state (populated after login via `/api/auth/me`) | Yes — real user state from API | ✓ FLOWING |
| `ErrorBoundary.captureException` | `error` + `errorInfo.componentStack` | React runtime in componentDidCatch | Yes — real error + component stack from React | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend obs tests pass (test_log_propagation, test_sentry_init, test_cloudwatch_emf) | `cd backend && pytest -n auto tests/test_log_propagation.py tests/test_sentry_init.py tests/test_cloudwatch_emf.py -x --no-header -q` | 40 passed, 1 skipped in 4.30s (1 sqlalchemy.engine skip is graceful per plan) | ✓ PASS |
| Frontend obs tests pass (sentry.test.ts + ErrorBoundary.test.tsx) | `cd frontend && npm test -- --run src/lib/sentry.test.ts src/components/common/ErrorBoundary.test.tsx` | 21 passed (19 + 2) in 994ms | ✓ PASS |
| Terraform validate + fmt | `cd terraform && terraform validate && terraform fmt -check` | Success! The configuration is valid. `terraform fmt -check` exit 0 | ✓ PASS |
| Sentry init helper importable | (run during plan 02-02 acceptance) `python -c "from app.core.sentry import init_sentry, _traces_sampler, _before_send; print('ok')"` | per 02-02-SUMMARY.md Self-Check: PASSED | ✓ PASS |
| EMF helper importable | `python -c "from app.core.cloudwatch_emf import emit_crawler_run_metrics; print('ok')"` | per 02-03-SUMMARY.md Self-Check: PASSED | ✓ PASS |
| Live AWS behavior (alarm firing, EMF extraction, Sentry event receipt, SNS email delivery, sourcemap upload) | Requires deployed staging + populated secrets + AWS clock | Cannot be tested from source | ? SKIP — see human_verification items |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OBS-01 | 02-02 | Sentry SDK in FastAPI with FastApiIntegration + SqlalchemyIntegration, traces_sample_rate=0.05, send_default_pii=False | ✓ SATISFIED (code) / ? LIVE | All four integrations loaded per `test_all_four_integrations_loaded` (Landmine 2). `send_default_pii=False` asserted. `_traces_sampler` returns 0.05 for non-health routes. Live-ops confirmation in UAT Item 1. |
| OBS-02 | 02-03 | Per-adapter CloudWatch custom metrics Ingested/ParseFailures/ElapsedSeconds in CarModPicker/Crawlers namespace | ✓ SATISFIED (code) / ? LIVE | EMF envelope namespace + metrics + dimensions pinned by 10 tests. Landmines 3/4/5 addressed. Live-ops confirmation in UAT Item 4. |
| OBS-03 | 02-05 | CloudWatch alarm on per-adapter ParseFailures rate >50% with SNS → SES notification | ✓ SATISFIED (code, with D-24 deviation) / ? LIVE | Composite alarm exists with strict `>` threshold, NaN-via-0 expression, RunType=live filter, SNS action, ok_actions symmetry, runbook description, Phase 3 TODO. Deviation: `email` protocol not SES — same operator outcome. Live alarm fire/recovery in UAT Item 5. |
| OBS-04 | 02-01 | Request-ID propagation — every log line during a request includes request_id + user_id | ✓ SATISFIED (code) / ? LIVE | `bg_log_context` + CLI bootstrap + 6 regression tests (test_log_propagation.py) pin the invariant. `caplog_with_context` fixture attaches RequestContextFilter. Live CloudWatch confirmation in UAT Item 7. |
| OBS-05 | 02-04 | Frontend errors captured by Sentry via @sentry/react wired into ErrorBoundary | ✓ SATISFIED (code) / ? LIVE | `@sentry/react@^10` installed, `initSentry` env-gated, `ErrorBoundary.componentDidCatch` calls `Sentry.captureException`, `AuthContext` sets user id-only, beforeErrorSampling blocks auth routes, vite-plugin CI-gated. 21 vitest tests pass. Live event receipt + sourcemap upload in UAT Item 6. |

**Orphaned requirements:** None. REQUIREMENTS.md Phase 2 list is exactly [OBS-01..OBS-05]; all five are claimed by plans and verified.

### Anti-Patterns Found

Scanned modified files (`backend/app/core/sentry.py`, `backend/app/core/cloudwatch_emf.py`, `backend/app/core/log_context.py`, `backend/app/main.py`, `backend/app/crawlers/__main__.py`, `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`, `backend/app/crawlers/runner.py`, `backend/app/core/config.py`, `frontend/src/lib/sentry.ts`, `frontend/src/components/common/ErrorBoundary.tsx`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/main.tsx`, `frontend/vite.config.ts`, `terraform/*.tf`) for:

- TODO/FIXME/placeholder comments
- Empty implementations (return null/{}/[])
- Hardcoded empty data
- Console.log only

**Findings:**

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `terraform/monitoring.tf` | 216 | `# TODO(phase-3): convert composite alarm to per-adapter via for_each` | ℹ️ Info | Intentional Phase 3 handoff marker per D-30. Not a stub — composite alarm is live + correct. |
| `frontend/src/components/common/ErrorBoundary.tsx` | 25 | `console.error('ErrorBoundary caught an error:', error, errorInfo)` | ℹ️ Info | Pre-existing behavior retained alongside new `Sentry.captureException` per D-35 additive diff. Not a stub. |
| `backend/app/core/sentry.py` | 108-147 | Triple early-return pattern (TESTING/env/DSN) | ℹ️ Info | Intentional env-gate (D-01, D-13). Tests (TestInitGating ×3) pin each gate branch. Not a stub. |
| `backend/app/core/cloudwatch_emf.py` | 85-89 | Triple early-return pattern | ℹ️ Info | Intentional env-gate (D-20). Tests (TestEnvGate ×2) pin. Not a stub. |

**No blocker or warning-severity anti-patterns.** All `return` patterns are intentional env gates with test coverage.

### Human Verification Required

The phase's deliverables are CODE-COMPLETE and INFRASTRUCTURE-DEFINED; live-ops validation requires a deployed staging environment with populated secrets and actual AWS event propagation. The plan explicitly marks 02-05 as `autonomous: false` and defines these steps in `02-HUMAN-UAT.md`:

1. **Backend 500 → Sentry event w/ request_id + user_id (OBS-01)** — UAT Item 1
2. **Crawler bg logger.error → Sentry event w/ adapter + bg: request_id (OBS-01)** — UAT Item 2
3. **HTTPException NOT in Sentry (OBS-01 ignore_errors)** — UAT Item 3
4. **EMF → CloudWatch metrics (staging crawl) (OBS-02)** — UAT Item 4
5. **Alarm fires → SNS email → recovers → recovery email (OBS-03)** — UAT Item 5
6. **Frontend error → Sentry w/ sourcemap + on-error replay (OBS-05)** — UAT Item 6
7. **OBS-04 log propagation spot-check in CloudWatch Logs Insights** — UAT Item 7
8. **Staging → Prod Promotion Gate (D-58): 24h bake + terraform apply to prod**

All 7 human verification items are documented in `.planning/phases/02-observability/02-HUMAN-UAT.md` (138 lines) with explicit "Do / Expected / Evidence" fields per item.

### Gaps Summary

No code/infra gaps found. Every must_have artifact exists, every key link is wired, every automated test passes, `terraform validate` + `fmt -check` both exit 0, all 5 ROADMAP success criteria are satisfied at source/terraform scope. Deviations documented by the planner (D-24 SNS→email vs SNS→SES; `var.environment` vs `var.app_environment`; deferred `terraform plan` per missing sandbox credentials) are all benign and captured in 02-HUMAN-UAT.md's Deviation Log.

The phase cannot be marked `passed` because the ROADMAP success criteria include live-ops observables (events arriving in Sentry, metrics in CloudWatch, alarm firing, sourcemap resolution) that are provable only against a deployed AWS stack — and plan 02-05 is explicitly `autonomous: false` gated on 24-hour staging bake. The correct status is `human_needed`: automated checks pass, operator UAT must close.

---

*Verified: 2026-04-22T23:40:00Z*
*Verifier: Claude (gsd-verifier)*
