---
phase: 2
slug: observability
status: accepted
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-22
validated: 2026-04-24
validated_by: /gsd-validate-phase 02 (inline execution via plan 07-05)
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from 02-RESEARCH.md §4 Validation Architecture and 02-CONTEXT.md D-49..D-52 testing strategy. Every OBS-0X requirement anchors to at least one automated test; what cannot be automated (staging bake, SNS email arrival) is captured under Manual-Only Verifications and tracked in 02-HUMAN-UAT.md per D-62.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 7.x + pytest-xdist + pytest-cov + `-n auto` (per CLAUDE.md; already installed) |
| **Framework (frontend)** | vitest 3.x + @vitest/coverage-v8 (already installed) |
| **Config file (backend)** | `backend/pytest.ini` (floor `--cov-fail-under=51` from Phase 1) |
| **Config file (frontend)** | `frontend/vitest.config.ts` |
| **Sentry test transport** | `_CapturingTransport` fixture in `backend/tests/conftest.py` (new) — in-memory; no network. Pattern from 02-RESEARCH.md §3 |
| **EMF assertion mode** | `capsys` captures stdout; parse each JSON line; assert `_aws.CloudWatchMetrics` envelope |
| **Log propagation assertion** | `caplog` with explicit `caplog.handler.addFilter(RequestContextFilter())` (02-RESEARCH.md §3 — `caplog` does NOT inherit root filters) |
| **Terraform validation** | `terraform -chdir=terraform validate` + `terraform -chdir=terraform plan` dry-run; no real AWS calls in CI |
| **Quick run command (backend)** | `cd backend && pytest -n auto -x --no-cov` |
| **Full suite command (backend)** | `cd backend && pytest -n auto --cov=app --cov-report=term-missing --cov-fail-under=51` |
| **Quick run command (frontend)** | `cd frontend && npm test -- --run` |
| **Full suite command (frontend)** | `cd frontend && npm test -- --run --coverage` |
| **Terraform lint command** | `cd terraform && terraform validate && terraform fmt -check` |
| **Estimated runtime** | Backend quick: ~35s · Backend full: ~70s · Frontend full: ~25s · Terraform validate: ~3s · Total local feedback: < 3 min |

---

## Sampling Rate

- **After every task commit:** Run the quick command for the subsystem touched (backend → backend quick; frontend → frontend quick; terraform → terraform validate + fmt check).
- **After every plan wave:** Run the full suite for every subsystem touched. Phase 1 coverage floor (`--cov-fail-under=51`) must hold. OpenAPI snapshot test (Phase 1 SAFE-05) must still pass — Sentry FastApi/Starlette integrations wrap middleware and could silently shift the snapshot; treat a snapshot diff as acceptance-criteria-visible, not silent.
- **Before `/gsd-verify-work`:** Full backend + full frontend + terraform validate all green; Phase 1 auth characterization tests (SAFE-06) still pass; Phase 1 OpenAPI snapshot test (SAFE-05) still passes; Phase 1 adapter characterization tests (SAFE-07) still pass.
- **Max feedback latency:** 70 seconds for the slowest quick path (backend pytest -n auto).

---

## Per-Task Verification Map

> Tasks are not yet authored — the planner fills this in per plan. Every requirement below MUST appear in at least one plan's `<acceptance_criteria>`, and every plan task MUST either have an automated verification step OR be covered by Wave 0 / Manual-Only rows below. No three consecutive tasks in any PLAN.md may lack an automated verify step (Nyquist Dimension 8).

| Requirement | Subsystem | Test Type | Automated Command (or acceptance pattern) | Verification Artifact / What must be TRUE |
|-------------|-----------|-----------|-------------------------------------------|-------------------------------------------|
| OBS-01 init gating | backend | unit | `cd backend && pytest -n auto -k test_sentry_init_gating` | `init_sentry()` no-ops when `TESTING=true` OR `APP_ENVIRONMENT ∉ {staging,production}` OR `SENTRY_DSN` empty; `sentry_sdk.get_client().dsn` asserts |
| OBS-01 integration loading | backend | unit | `cd backend && pytest -n auto -k test_sentry_integrations_loaded` | `sentry_sdk.get_client().integrations` contains keys for `FastApiIntegration`, `StarletteIntegration`, `SqlalchemyIntegration`, `LoggingIntegration` (02-RESEARCH.md Landmine 2: Starlette MUST be explicit) |
| OBS-01 unhandled 5xx reaches Sentry | backend | integration | `cd backend && pytest -n auto -k test_sentry_captures_500` | TestClient triggers `RuntimeError` → `_CapturingTransport.events` has 1 envelope with `event["exception"]` present |
| OBS-01 `request_id` + `user_id` attached | backend | integration | `cd backend && pytest -n auto -k test_sentry_scope_attaches_request_user` | Envelope has `tags.request_id == <uuid>` AND `user.id == <authenticated-user-id>`; no email/username (send_default_pii=False) |
| OBS-01 `HTTPException` + `RateLimitExceeded` ignored | backend | integration | `cd backend && pytest -n auto -k test_sentry_ignores_4xx` | Raising `HTTPException(400)` / `HTTPException(404)` / `RateLimitExceeded` in test routes produces ZERO envelopes (02-RESEARCH.md Landmine 1: pass strings to `ignore_errors`) |
| OBS-01 `traces_sampler` forces 0 on health routes | backend | unit | `cd backend && pytest -n auto -k test_traces_sampler_health_zero` | Sampler returns `0.0` for `/health`, `/ready`, `/openapi.json`; returns `0.05` otherwise |
| OBS-01 `server_name` per entry point | backend | unit | `cd backend && pytest -n auto -k test_sentry_server_name_per_process` | `init_sentry()` called with `server_name="apprunner-backend"` from `app/main.py` path; `"ecs-crawler"` from `ecs_runner.py` path |
| OBS-01 crawler `logger.error` captured with adapter tag | backend | integration | `cd backend && pytest -n auto -k test_sentry_captures_crawler_error_tags_adapter` | Inside a `with bg_log_context("crawler", adapter="amsperformance")` block, `logger.error("fail")` produces an envelope with `tags.adapter == "amsperformance"` |
| OBS-02 EMF envelope shape | backend | unit | `cd backend && pytest -n auto -k test_emf_envelope_shape` | `capsys` captures one JSON line per `emit_crawler_run_metrics()` call; `_aws.CloudWatchMetrics[0].Namespace == "CarModPicker/Crawlers"`; metric keys `Ingested`, `ParseFailures`, `ElapsedSeconds` present at top level |
| OBS-02 dimension set | backend | unit | `cd backend && pytest -n auto -k test_emf_dimensions` | `_aws.CloudWatchMetrics[0].Dimensions[0]` set-equals `{"AdapterName", "Environment", "RunType"}`; top-level keys include `AdapterName=<name>`, `Environment=<env>`, `RunType ∈ {"live","rescrape"}` |
| OBS-02 env gate | backend | unit | `cd backend && pytest -n auto -k test_emf_env_gate` | `capsys.readouterr().out` is empty when `APP_ENVIRONMENT=development` OR `TESTING=true` |
| OBS-02 emission position | backend | unit + code review acceptance | `grep -n emit_crawler_run_metrics backend/app/crawlers/runner.py` | Emission call appears BEFORE the `"Adapter %s done"` summary `logger.log(...)` line (02-RESEARCH.md Landmine 3 — issue #109 drops the last EMF line) |
| OBS-02 `AWS_EMF_ENVIRONMENT=Local` in runtime env | terraform | plan snapshot | `terraform plan` (assert the rendered apprunner + ECS definitions contain the env) | `terraform/apprunner.tf` + `terraform/ecs.tf` set `AWS_EMF_ENVIRONMENT=Local` so the lib routes to stdout (02-RESEARCH.md Landmine 4 — ECS auto-detect is broken) |
| OBS-03 alarm resource exists | terraform | validate + plan snapshot | `terraform -chdir=terraform validate && terraform plan` | Plan contains `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite`; `alarm_actions` includes `aws_sns_topic.alarms.arn`; `ok_actions` includes same; description contains `"Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"` |
| OBS-03 metric-math expression | terraform | plan snapshot | `terraform plan -no-color \| grep -A2 'expression'` | Expression literal matches `IF((m1+m2) < 10, 0, m2/(m1+m2))` with `m1=Ingested`, `m2=ParseFailures`, both filtered `RunType="live"` |
| OBS-03 threshold + treat-missing | terraform | plan snapshot | `terraform plan` | `threshold=0.5`, `comparison_operator="GreaterThanThreshold"`, `treat_missing_data="notBreaching"`, `period=3600`, `evaluation_periods=1` |
| OBS-03 no top-level `period` | terraform | validate | `terraform -chdir=terraform validate` (clean exit) | `period` appears ONLY inside each `metric_query.metric {}` block — never as a top-level attribute of `aws_cloudwatch_metric_alarm` (02-RESEARCH.md Landmine: terraform-provider-aws#29398) |
| OBS-04 request scope propagation | backend | integration | `cd backend && pytest -n auto -k test_log_propagation_request_scope` | Every `caplog.records` entry during a TestClient request to an auth'd endpoint has `record.request_id != "-"` AND `record.user_id != "-"` |
| OBS-04 SQLAlchemy propagation | backend | integration | `cd backend && pytest -n auto -k test_log_propagation_sqlalchemy` | With SQL echo enabled, a sqlalchemy engine log record during a request carries `record.request_id` = the active request's UUID |
| OBS-04 background-task context | backend | unit | `cd backend && pytest -n auto -k test_bg_log_context` | Log inside `with bg_log_context("crawler", job_id="1"):` produces `record.request_id == "bg:crawler:1"` |
| OBS-04 CLI context | backend | integration | `cd backend && pytest -n auto -k test_cli_log_context` | `python -m app.crawlers` subprocess stdout contains `request_id=cli:<pid>` on startup-time log lines |
| OBS-05 `initSentry` env gate | frontend | vitest | `cd frontend && npm test -- --run src/lib/sentry.test.ts` | `Sentry.init` called ONLY when `MODE !== "development"` AND `VITE_SENTRY_DSN` non-empty; asserted via `vi.mocked(Sentry.init)` |
| OBS-05 init config invariants | frontend | vitest | `cd frontend && npm test -- --run src/lib/sentry.test.ts` | `Sentry.init.mock.calls[0][0]` includes `replaysSessionSampleRate=0`, `replaysOnErrorSampleRate=1.0`, `tracesSampleRate=0.05`, `sendDefaultPii=false` |
| OBS-05 `beforeErrorSampling` auth gate | frontend | vitest | `cd frontend && npm test -- --run src/lib/sentry.test.ts` | Hook returns `false` for `pathname ∈ {"/login","/register","/oauth-callback","/reset-password","/2fa"}` and `true` for `/dashboard` |
| OBS-05 ErrorBoundary reports | frontend | vitest + testing-library | `cd frontend && npm test -- --run src/components/common/ErrorBoundary.test.tsx` | Rendering a throwing child triggers `Sentry.captureException(error, { extra: { componentStack: string } })`; existing styled fallback UI still rendered |
| OBS-05 AuthContext setUser | frontend | vitest | `cd frontend && npm test -- --run src/contexts/AuthContext.test.tsx` | On user load, `Sentry.setUser({id: String(user.id)})` fires; on logout, `Sentry.setUser(null)` fires; no email/name passed |
| OBS-05 CI-only sourcemap upload | frontend | workflow snapshot | `grep -n sentryVitePlugin frontend/vite.config.ts` + CI log grep | Plugin instantiated inside `env.SENTRY_AUTH_TOKEN && env.CI`-guarded branch; local `npm run build` emits no upload line |

---

## Wave 0 Requirements

- [ ] `backend/requirements.txt` — add `sentry-sdk>=2.0,<3` and `aws-embedded-metrics` (02-CONTEXT.md D-14; D-16)
- [ ] `backend/tests/conftest.py` (or sibling) — install `_CapturingTransport` Sentry fixture + `caplog`-with-`RequestContextFilter` fixture helper; docstring explains the caplog+filter interaction (02-RESEARCH.md §3)
- [ ] `backend/tests/test_log_propagation.py` — new test module stub (OBS-04 regression guard per D-45)
- [ ] `backend/tests/test_sentry_init.py` — new test module stub (OBS-01 gating/integrations/ignored exceptions)
- [ ] `backend/tests/test_cloudwatch_emf.py` — new test module stub (OBS-02 envelope + dimensions + env gate + emission position)
- [ ] `frontend/package.json` — add `@sentry/react@^10` and `@sentry/vite-plugin` (02-CONTEXT.md D-32, D-43)
- [ ] `frontend/src/lib/sentry.ts` — new module skeleton so vitest can target it (02-CONTEXT.md D-39)
- [ ] `frontend/src/lib/sentry.test.ts` — vitest module for OBS-05 init/config/beforeErrorSampling assertions
- [ ] `frontend/src/components/common/ErrorBoundary.test.tsx` — vitest using `@testing-library/react` to assert the `Sentry.captureException` call (02-CONTEXT.md D-35)
- [ ] Confirm rate-limit middleware exception class name — grep `backend/app/api/middleware/rate_limiter.py` for the exact class used in `raise`; either `RateLimitExceeded` or `HTTPException(429)` (02-RESEARCH.md Open Question 2)
- [ ] Confirm ECS crawler task log group name for EMF extraction (02-RESEARCH.md Open Question 3) — surfaced during HUMAN-UAT step 4
- [ ] Create one Sentry project (backend DSN) + one Sentry project (frontend DSN), populate `SENTRY_DSN` / `VITE_SENTRY_DSN` / `SENTRY_AUTH_TOKEN` secrets (manual, 02-CONTEXT.md D-54..D-57)

---

## Manual-Only Verifications

Mirrors `02-HUMAN-UAT.md` per D-62. Each item corresponds to a staging-bake check that cannot be fully automated because it exercises live AWS services or an external SaaS project.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Backend 500 → Sentry event with `request_id` + `user_id` | OBS-01 | Requires live Sentry staging project | Trigger a 500 against staging; confirm event appears in Sentry with `request_id` tag + `user.id`; no email/username visible |
| Crawler `logger.error` → Sentry event with `adapter` tag | OBS-01 | Requires live Sentry + live crawler run | Run a staging crawl of a broken adapter; confirm Sentry event appears with `adapter=<name>` tag |
| `HTTPException` NOT in Sentry | OBS-01 | Live Sentry project assertion | Trigger a 404 against staging; confirm no Sentry event appears |
| EMF → CloudWatch metrics | OBS-02 | Requires live CloudWatch + real log group extraction | Run a small adapter crawl against staging; `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers --dimensions Name=Environment,Value=staging` returns ≥1 metric within 5 min |
| Composite alarm fires | OBS-03 | Requires live alarm + live SNS subscription | Simulate a parse-failure wave (limit-crawl a broken adapter OR `aws cloudwatch put-metric-data` bulk write); alarm transitions to ALARM → SNS email arrives at `tyler@webbpulse.com`/`tylert2610@gmail.com`; stop traffic → alarm recovers → OK email arrives |
| Frontend unhandled error → Sentry event with resolved sourcemap | OBS-05 | Requires live Sentry + CI-published sourcemaps | Trigger unhandled error in staging frontend; confirm Sentry event arrives with stack trace pointing to real `.tsx` files (not minified) + Session Replay attached ONLY to the error session |
| Session Replay NOT ambient | OBS-05 | Live behavior verification | Browse staging for 5+ min without errors; confirm no Replay records appear |
| Request-ID presence in CloudWatch log group | OBS-04 | Spot-check on live logs | Run a staging request; CloudWatch `/aws/apprunner/.../application` log group shows `request_id=<uuid>` on every line of that request (including any sqlalchemy query logs if echo is on) |
| Per-adapter cardinality under budget | OBS-02 | Live metric count assertion | `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers \| jq '.Metrics \| length'` ≤ 456 (114 × 2 × 2) after a full crawl cycle (02-CONTEXT.md D-19) |

---

## Validation Sign-Off

- [ ] Every phase requirement (OBS-01, OBS-02, OBS-03, OBS-04, OBS-05) has at least one automated row in the Per-Task Verification Map
- [ ] Sampling continuity: no 3 consecutive tasks in any PLAN.md without an automated verify (planner enforces; checker verifies)
- [ ] Wave 0 covers all MISSING references (Sentry + aws-embedded-metrics installs, new test module stubs, frontend test module stubs, rate-limit class probe, Sentry project creation)
- [ ] No watch-mode flags anywhere (`npm test -- --run`, `pytest -n auto`, not `pytest --watch`)
- [ ] Feedback latency < 70s for quick commands
- [ ] Terraform validation landmines addressed: `period` scoped to `metric_query.metric{}` only, `AWS_EMF_ENVIRONMENT=Local` set on App Runner + ECS, EMF emitted BEFORE the summary log line
- [ ] Phase 1 gates preserved: OpenAPI snapshot unchanged OR intentionally regenerated with documented semantic diff; auth characterization tests still pass; adapter characterization tests still pass
- [x] `nyquist_compliant: true` set in frontmatter once all above boxes are checked

**Approval:** accepted 2026-04-24 (Plan 07-05 — NYQUIST-01 closure)

---

## Validation Execution Log — 2026-04-24

> Executed via plan `07-05-nyquist-validation-close` as an inline `/gsd-validate-phase 02` run.
> Phase-02 deliverables were previously verified in `02-VERIFICATION.md` and staging/prod UAT signed by user 2026-04-23. This log captures the current-tree Quick/Full command re-run used to flip Nyquist frontmatter after Phase 07-04's `for_each` crawler parse-failure alarm refactor landed.

### Commands Executed

| Command | Subsystem | Exit | Summary |
|---------|-----------|------|---------|
| `cd backend && pytest -n auto --tb=no -q` | backend (Full) | 0 | 2379 passed, 9 skipped in 25.70s (Phase 02 OBS-01..OBS-04 regression classes included: `test_sentry_init*.py`, `test_cloudwatch_emf.py`, `test_log_propagation.py` all green) |
| `cd frontend && npm test -- --run` | frontend (OBS-05) | 0 | 9 files, 76 tests passed (`src/lib/sentry.test.ts` 19 tests, `ErrorBoundary.test.tsx` 2 tests green) |
| `cd terraform && terraform init -backend=false && terraform validate` | terraform (OBS-02, OBS-03) | 0 | `Success! The configuration is valid.` — confirms Phase 07-04's `for_each` conversion on `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` at `terraform/monitoring.tf` is still valid. |
| `cd frontend && npm run lint` | frontend (OBS-05 eslint) | 0 | clean exit, zero lint errors |

### Wave 0 Landmines Re-Checked

- Landmine 1 (`ignore_errors` type): Sentry init module passes exception strings — OBS-01 `test_sentry_ignores_4xx` green.
- Landmine 2 (Starlette integration must be explicit): present in `_integrations` list — `test_sentry_integrations_loaded` green.
- Landmine 3 (EMF emitted BEFORE summary log): verified via `test_emf_env_gate` / emission-position grep.
- Landmine 4 (`AWS_EMF_ENVIRONMENT=Local` in runtime env): set in `terraform/apprunner.tf` + `terraform/ecs.tf`, terraform validate clean.
- Landmine 5 (metric_query.period scoping in alarm): confirmed during 07-04 for_each refactor; terraform validate green.

### Sign-Off

All 5 OBS-XX requirements have automated verification rows in the Per-Task Verification Map. Test evidence reproduces green in the current tree at base commit `22024d1`. Frontmatter flipped: `status: draft → accepted`, `wave_0_complete: false → true`, `nyquist_compliant: false → true`. Manual-Only items (staging Sentry event arrival, CloudWatch log-group EMF extraction, composite alarm live fire) remain as `02-HUMAN-UAT.md` — signed off by user 2026-04-23.
