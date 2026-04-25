# Phase 2: Observability - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Production errors are visible in Sentry (backend + frontend), per-adapter crawler metrics flow to CloudWatch, and a parse-failure alarm fires on drift — all without changing any URL, schema, or external contract. Phase 2 is additive-only; it may execute concurrently with Phase 3 because neither phase touches the other's surface.

Phase 2 delivers five things: (1) `sentry_sdk.init()` wired into FastAPI + both ECS crawler runners, (2) per-adapter `CarModPicker/Crawlers` EMF metrics emitted from inside `run_crawler`, (3) a CloudWatch parse-failure alarm that reuses the existing `${prefix}-alarms` SNS topic, (4) `@sentry/react` integrated into the existing `ErrorBoundary` with sourcemap upload, and (5) an audit + regression-test that proves `request_id` / `user_id` propagate through every log line including background tasks.

</domain>

<decisions>
## Implementation Decisions

### Sentry — backend SDK integration (OBS-01)

- **D-01:** DSN injected via AWS Secrets Manager on both App Runner and ECS Fargate. `sentry_sdk.init()` only runs when `SENTRY_DSN` is non-empty AND `APP_ENVIRONMENT in {staging, production}`. Local dev + `TESTING=true` stay silent even if a DSN is exported. Matches the existing Secrets Manager pattern for `DATABASE_URL` / `SECRET_KEY`.
- **D-02:** `release` = `os.environ["SENTRY_RELEASE"]` baked at image build time. GitHub Actions sets `SENTRY_RELEASE={git_commit_sha}` when building the backend Docker image. Commit-grade attribution so regressions tie to a specific PR.
- **D-03:** PII scrubbing: rely on `send_default_pii=False` (REQUIREMENTS-locked) + Sentry's default scrub list. No custom `before_send` this phase. Matches PROJECT.md's "attainable 90%" security posture. Revisit only if a concrete PII leak surfaces.
- **D-04:** `LoggingIntegration` enabled at default levels — event_level=ERROR, breadcrumb_level=INFO. Captures `logger.error(...)` / `logger.exception(...)` calls as Sentry events. Critical for crawler error paths in `runner.py` that log-without-raise (e.g., `"Adapter X done. Ingested=0"` ERROR summary line).
- **D-05:** Shared helper `backend/app/core/sentry.py::init_sentry()` is called from every process entry point: `app/main.py` (FastAPI), `app/crawlers/__main__.py` (CLI), `app/crawlers/ecs_runner.py` (Fargate live crawl), `app/crawlers/ecs_rescrape_runner.py` (Fargate archive rescrape). Idempotent; safe to call multiple times.
- **D-06:** `traces_sampler` function forces `sample_rate=0` for `/health`, `/ready`, `/openapi.json`; keeps the REQUIREMENTS-locked 0.05 for everything else. Protects the 5% transaction budget from being burned on App Runner's health-probe cadence.
- **D-07:** `ignore_errors=[HTTPException, RateLimitExceeded]` at init. Intentional 4xx responses and 429s are not bugs; skipping them keeps Sentry focused on unhandled issues + 5xx. Do NOT ignore boto3 / requests transient errors — they might indicate real infra problems.
- **D-08:** Single Sentry project for both staging and production, distinguished by `environment` tag (`staging` or `production`, auto-derived from `APP_ENVIRONMENT` env var). Easier to spot regressions that staging caught before prod. Fits the Sentry free-tier quota envelope better than two separate projects.
- **D-09:** Scope processor attaches `user_id` (from `user_id_var` ContextVar) via `scope.set_user({id: user_id})` and `request_id` (from `request_id_var`) via `scope.set_tag("request_id", ...)`. Also attaches `adapter` tag when a crawler error is in scope. Satisfies OBS-01 success criterion "exceptions appear in Sentry with request ID, user ID... attached" without leaking email/username.
- **D-10:** Tag strategy: `environment`, `request_id`, `adapter` (when crawler work is in scope). Tight set, high signal. Crawler errors filterable by adapter at a glance — essential for the 114-adapter fleet.
- **D-11:** Distinct `server_name` per process: `server_name="apprunner-backend"` (FastAPI) and `server_name="ecs-crawler"` (Fargate). Sentry groups by service so a crawler crash is visually distinct from a request crash.
- **D-12:** `sentry_sdk.init()` is the first thing in `app/main.py` after imports, before `FastAPI()` instantiation. Catches crashes during router registration and lifespan startup.
- **D-13:** Test suite suppression: `init_sentry()` bails early when `TESTING=true` is set (matches the existing `ENABLE_RATE_LIMITING=false` pattern in `conftest.py`). Prevents test-run events from polluting the prod Sentry project.
- **D-14:** `sentry-sdk` pinned to `>=2.0,<3` in `backend/requirements.txt`. SDK 2.x is stable (April 2026). Dependabot (SAFE-10) picks up patches weekly.
- **D-15:** Docs: docstring at the top of `backend/app/core/sentry.py` explains DSN source, release tag, ignored exceptions, server_name list, and scope processor behavior. One-line pointer added to `CLAUDE.md` "Architecture / Backend" section. No dedicated `OBSERVABILITY.md` this phase.

### CloudWatch metrics (OBS-02)

- **D-16:** Emission mechanism: **CloudWatch Embedded Metric Format (EMF)** via structured log lines. Use the `aws-embedded-metrics` Python library (pinned in `requirements.txt`). Library handles buffering, dimension limits, and envelope shape. Zero `PutMetricData` API calls — metrics ride the existing CloudWatch Logs path. No additional IAM beyond what App Runner + ECS already have for Logs.
- **D-17:** Emission point: inside `run_crawler` at the end-of-run summary block (around `runner.py:608`, where `logger.log(summary_level, "Adapter %s done...")` is already called). One EMF record per adapter run. `run_crawlers()` parallel invocations still get one emission per adapter because they flow through the shared `run_crawler` path.
- **D-18:** Metrics emitted (REQUIREMENTS-locked scope): `Ingested` (Count), `ParseFailures` (Count), `ElapsedSeconds` (Seconds). Computed from existing `ingested`, `skipped_not_product`, and a new elapsed-timer around the URL loop. Namespace: `CarModPicker/Crawlers`. No additional counters this phase — if signal gaps surface, add in a future phase.
- **D-19:** Dimensions: `AdapterName` + `Environment` + `RunType`. `RunType` is `"live"` for `run_crawler` invocations and `"rescrape"` for `ecs_rescrape_runner.py` invocations. `Environment` derived from `APP_ENVIRONMENT`. Parse-failure alarm (OBS-03) filters to `RunType=live` so rescrape baselines don't skew it. Cardinality: 114 adapters × 2 envs × 2 run types = 456 time series — well under CloudWatch's 10K/month free tier.
- **D-20:** Dev / test behavior: the EMF helper early-returns when `APP_ENVIRONMENT != staging/production` OR `TESTING=true`. Local `python -m app.crawlers` runs are silent. Pytest captures the emission call via an assertion stub (not moto). Matches the Sentry DSN-env gate pattern (D-01).
- **D-21:** Rescrape runs emit with `RunType=rescrape`. Same metrics, same namespace — distinguishable at the alarm-filter and dashboard layers rather than via namespace split.

### Parse-failure alarm (OBS-03)

- **D-22:** Alarm math: **metric-math expression** `m2 / (m1 + m2) > 0.5` where `m1=Ingested`, `m2=ParseFailures`, both filtered to `RunType=live`. Semantically matches "half of attempted pages failed to parse." Not influenced by robots-skipped / 404-gone URLs (noise).
- **D-23:** Small-sample noise suppression: the metric-math expression returns NaN when `(m1 + m2) < 10`. Combined with `treat_missing_data=notBreaching`, adapters with fewer than 10 attempted URLs never fire. Threshold 10 is picked to match `runner.py`'s existing `total >= 10` gate for the WARNING-level drift log.
- **D-24:** Notification path: **reuse the existing `${prefix}-alarms` SNS topic** in `terraform/monitoring.tf`. Already subscribed to `tyler@webbpulse.com` and `tylert2610@gmail.com` via direct `aws_sns_topic_subscription` (protocol=email). REQUIREMENTS says "SNS → SES"; we treat that as "alarm reaches operator email" which SNS→email satisfies identically. Note the deviation in the execution plan for traceability. Avoids adding a Lambda to maintain.
- **D-25:** Evaluation period: `period=3600` (1 hour), `evaluation_periods=1`, `treat_missing_data=notBreaching`. Crawler schedules typically run hourly-or-slower; a 1-hour bucket catches the most recent adapter run. Idle adapters stay quiet. Matches the cadence of the existing RDS/AppRunner alarms.
- **D-26:** `ok_actions = [aws_sns_topic.alarms.arn]` — recovery notifications so you can see when a bad adapter self-resolves. Matches the pattern in every existing alarm in `terraform/monitoring.tf`.
- **D-27:** Alarm description carries a runbook link: `"Parse-failure rate > 50% on adapter {name}. Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"`. Description is surfaced in the SNS email so the operator lands on instructions immediately.
- **D-28:** Runbook lives as a new "Crawler Drift Runbook" section in `.planning/codebase/CONCERNS.md`. Steps: check adapter HTML fixture, re-run the adapter characterization test from Phase 1 (SAFE-07), patch selectors, redeploy. Matches the "codebase maps are authoritative" convention established by PROJECT.md.
- **D-29:** **Granularity split across phases:** Phase 2 ships a **single composite alarm** — `SUM(ParseFailures) / SUM(Ingested) > 0.5` across all adapters in the `live` RunType. Closes the Phase 2 success criterion ("a CloudWatch alarm triggers... when parse-failure rate exceeds 50%") at aggregate granularity. **Phase 3 converts to per-adapter alarms** after CRAWL-01/02 adapter auto-discovery lands (it will emit an `adapter_names.txt` or equivalent artifact terraform can read). Per-adapter alarm cost: 114 alarms × $0.10/mo = $11.40/mo. User explicitly accepted this cost for per-adapter precision.
- **D-30:** **Phase 3 handoff marker:** Terraform leaves a `# TODO(phase-3): convert composite alarm to per-adapter via for_each = toset(file("adapter_names.txt"))` comment beside the composite alarm. 02-CONTEXT.md's Deferred section (below) names this explicitly.
- **D-31:** **Mute mechanism:** `var.disabled_parse_alarms = ["adapter_x"]` terraform list. `for_each` skips any name in the list. When an adapter is known-broken and awaiting selector patches, disable via PR (reversible, auditable). Emergency mute = disable in AWS console; follow-up PR to persist. Avoids commenting out terraform.

### Frontend Sentry (OBS-05)

- **D-32:** Package set: `@sentry/react` (errors + unhandled rejections + Performance) + `@sentry/vite-plugin` (sourcemap upload). Session Replay **enabled on-error only** — `replaysSessionSampleRate=0`, `replaysOnErrorSampleRate=1.0`. No ambient replay recording; replay attaches only when an error event fires. Keeps us well under the Sentry free-tier 500-replays/month cap regardless of traffic.
- **D-33:** DSN injection: `VITE_SENTRY_DSN` env var baked into the bundle at `npm run build` time via Vite. GitHub Actions sets the env var from a repository secret. Frontend is statically served from S3 so there is no runtime env anyway. DSNs are safe to expose in public bundles — this is the standard Vite pattern.
- **D-34:** Sourcemap upload: `@sentry/vite-plugin` enabled in CI only (gated on `SENTRY_AUTH_TOKEN` being set). Local `npm run build` skips upload. Stack traces point to real source files in Sentry UI — the main reason to bother with frontend Sentry.
- **D-35:** Integration with the existing `frontend/src/components/common/ErrorBoundary.tsx`: add `Sentry.captureException(error, { extra: { errorInfo } })` inside `componentDidCatch` where it already calls `console.error`. Keep the existing class component + styled fallback UI. 3-line change. No `Sentry.ErrorBoundary` HOC swap.
- **D-36:** Session Replay PII masking: `maskAllText: true`, `maskAllInputs: true` (Sentry defaults). Emails, names, prices, and form inputs render as '***' in replay. Matches the backend `send_default_pii=False` posture.
- **D-37:** Auth-route replay blocking: `beforeErrorSampling` (or equivalent hook) drops replay attachment when `window.location.pathname` matches `/login`, `/register`, `/oauth-callback`, `/reset-password`, `/2fa`. Errors on those pages still report to Sentry; only the replay is dropped. Defense-in-depth against token-bearing URL fragments.
- **D-38:** `tracesSampleRate: 0.05` — same rate as backend. Correlates frontend spans with backend spans via shared `trace_id` when fetch instrumentation is enabled. Low cost at current traffic.
- **D-39:** `Sentry.init()` is called at the top of `frontend/src/main.tsx`, before `createRoot`. Lives in a new `frontend/src/lib/sentry.ts` module that exports `initSentry()` + any helper. Matches the backend `app/core/sentry.py` pattern. Init is a no-op if `VITE_SENTRY_DSN` is empty OR `import.meta.env.MODE === 'development'`.
- **D-40:** User context: `AuthContext` `useEffect` calls `Sentry.setUser({id: String(user.id)})` when the user loads and `Sentry.setUser(null)` on logout. No email, no username — matches backend D-09 posture.
- **D-41:** Session Replay quota: trust Sentry's server-side quota enforcement. No client-side throttle. Sentry silently drops past-quota replays.
- **D-42:** Env gate: Sentry init fires when `VITE_SENTRY_DSN` is set AND `import.meta.env.MODE !== 'development'`. Local `npm run dev` silent; staging + prod builds active.
- **D-43:** Package pinning: `@sentry/react` pinned to `^10.0.0` (current major, April 2026). `@sentry/vite-plugin` at its current major. Dependabot picks up patch/minor weekly.

### OBS-04 — request_id / user_id propagation audit

- **D-44:** The existing `RequestContextFilter` + `request_id_var` / `user_id_var` ContextVars (`backend/app/core/log_context.py`) + root-logger filter attachment (`main.py:50–63`) already covers the happy path. OBS-04 is predominantly **audit + regression guard**, not build-from-scratch.
- **D-45:** Regression guard: add a pytest fixture (`backend/tests/conftest.py` or a sibling) that uses `caplog` to assert every log record produced inside a request scope has non-default `request_id` and `user_id` attributes. Applied to a representative set of existing endpoint tests (not all — `xdist` parallelism + the filter's idempotence makes spot coverage sufficient). Fails CI if a future dev adds a handler that drops the filter or uses `print()` for a runtime log.
- **D-46:** Background-task context convention: wrap background tasks (crawler runner, orphan-job sweep, EventBridge callback handler) to set `request_id_var.set(f"bg:{task_name}:{job_id}")` and `user_id_var.set("bg")`. Keeps CloudWatch grep usable (`filter @message like /req=bg:crawler/`). ~10-line decorator in `backend/app/core/log_context.py` or a new `bg_context.py` helper.
- **D-47:** CLI context: `backend/app/crawlers/__main__.py` sets `request_id_var.set(f"cli:{os.getpid()}")` and `user_id_var.set("cli")` at startup. 3 lines.
- **D-48:** Third-party logger propagation verified: the root logger in `main.py` attaches `RequestContextFilter` and sets the formatter; sqlalchemy / botocore / requests log through the root propagation path. Audit step confirms this via a test that captures a sqlalchemy log inside a request and asserts `request_id` attr. If propagation is broken for any third-party logger, fix during the audit plan.

### Testing strategy

- **D-49:** Sentry events: in-memory transport fixture captures events during tests. Assertions cover (a) events fire on unhandled exceptions, (b) `user_id` and `request_id` are attached, (c) `HTTPException` and `RateLimitExceeded` are ignored. No network, no live Sentry project.
- **D-50:** EMF metrics: capture via pytest `caplog`; assert the `_aws` block shape, dimension set, and metric values for a simulated `run_crawler` invocation. No moto, no boto3 mocking needed since EMF is logs-only.
- **D-51:** Frontend Sentry: unit tests via vitest with a mocked `@sentry/react`. Assert `initSentry()` only calls `Sentry.init` when the env gate passes; assert `ErrorBoundary.componentDidCatch` calls `Sentry.captureException` with the error and errorInfo.
- **D-52:** Coverage: new Python + TS code brings its own tests so the Phase 1 `--cov-fail-under=51` gate (backend) + vitest `lines: 60` threshold (frontend, once SAFE-03 is locked in Phase 1 or alongside Phase 2) do not regress.

### Execution sequencing inside Phase 2

- **D-53:** Plan order: **OBS-04 audit + regression test → Sentry backend (OBS-01) → CloudWatch metrics (OBS-02) → Frontend Sentry (OBS-05) → Parse-failure alarm (OBS-03 composite)**. Rationale:
  1. Nail request_id / user_id propagation first (zero-risk, fixes any gaps so Sentry events + EMF lines land with correct context when they go live).
  2. Backend Sentry second — now pulls the audit-verified context into events.
  3. CloudWatch metrics third — independent subsystem; lands per-adapter EMF.
  4. Frontend Sentry fourth — separate stack, separate DSN, no coupling to backend work.
  5. Parse-failure alarm last — needs metrics flowing before the composite alarm has data.

### Secrets & rollout

- **D-54:** Sentry project creation is manual: operator creates one Sentry project for the backend and one for the frontend (or one dual-purpose project — operator's call at creation time, does not affect code). Two DSNs. One `SENTRY_AUTH_TOKEN` (for sourcemap uploads).
- **D-55:** `SENTRY_DSN` stored in AWS Secrets Manager; terraform adds an `aws_secretsmanager_secret` + `aws_secretsmanager_secret_version` for it (value populated out-of-band by operator `aws secretsmanager put-secret-value`). Injected into App Runner + ECS Fargate as `SENTRY_DSN` env via the existing `runtime_environment_secrets` mechanism.
- **D-56:** Frontend build secrets: `VITE_SENTRY_DSN` + `SENTRY_AUTH_TOKEN` + `SENTRY_ORG` + `SENTRY_PROJECT` added as GitHub Actions secrets for the frontend build job.
- **D-57:** `terraform/README.md` gets a "Bootstrap: Sentry" section enumerating: create Sentry project → create Secrets Manager secret + version → add GHA secrets → redeploy. Manual but documented.
- **D-58:** **Rollout cadence: staging first, bake 24h, then prod.** Merge to main triggers staging deploy; visible Sentry events + CloudWatch metrics + alarm behavior confirmed in staging for 24 hours; then a follow-up deploy to prod. Catches PII leaks and alarm-too-sensitive misconfigurations before prod.

### Cost posture (global to Phase 2)

- **D-59:** Project cost target: **< $50/mo total** across all AWS + SaaS. Benefit:cost ratio drives every choice. Phase 2's ongoing cost contribution: Sentry free tier ($0), CloudWatch metric cardinality inside free tier ($0), EMF log ingestion negligible (<$0.10/mo at current traffic), composite alarm in Phase 2 ($0.10/mo), per-adapter alarms in Phase 3 (~$11.40/mo). Total Phase 2 ongoing: ~$0.10/mo. Total after Phase 3 conversion: ~$11.50/mo. Both inside the $50/mo envelope.
- **D-60:** Sentry plan: **stay on free tier**. Upgrade to Developer ($26/mo) only if we breach 5K errors/mo two months running.
- **D-61:** CloudWatch Logs retention stays at 14 days (matches existing `terraform/monitoring.tf`). Metrics extracted from EMF retain 15 months independently — history survives log rotation.

### Success verification

- **D-62:** Phase 2 closes with a HUMAN-UAT checklist at `02-HUMAN-UAT.md` (mirrors Phase 1's `01-HUMAN-UAT.md`). Items cover:
  1. Backend: trigger a 500 against staging → see it in Sentry with `request_id` + `user_id` attached.
  2. Backend: trigger a crawler `logger.error` → see it as a Sentry event with `adapter` tag.
  3. Backend: confirm `HTTPException` does NOT appear in Sentry (ignored).
  4. Metrics: run a small adapter crawl against staging → see EMF-extracted metrics in CloudWatch `CarModPicker/Crawlers` namespace with correct dimensions.
  5. Alarm: simulate a parse-failure wave in staging (limit crawl to an adapter with a broken selector, or manually PutMetricData) → alarm fires → SNS email arrives → alarm recovers after emissions stop → recovery email arrives.
  6. Frontend: trigger an unhandled error in staging frontend → see it in Sentry with sourcemaps resolving to real files → confirm no ambient replay → confirm replay attached to the error-triggering session.
  7. OBS-04: run a staging request → CloudWatch log group shows `[req=<uuid>] user=<id>` on every line (including sqlalchemy query logs if debug is on).

### Claude's Discretion

- Exact naming of the EMF helper module (`backend/app/core/cloudwatch_emf.py` vs `backend/app/core/metrics.py`) and its public API shape — as long as it uses `aws-embedded-metrics` and no-ops outside staging/prod.
- Exact naming of the background-task log-context wrapper/decorator (`with_bg_context`, `bg_log_context`, etc.).
- Terraform file layout: extending `terraform/monitoring.tf` vs creating `terraform/observability.tf` — planner decides based on file size growth.
- Where the pytest fixture for OBS-04 regression lives (`backend/tests/conftest.py` vs a new `backend/tests/test_log_propagation.py`).
- Whether Sentry scope processor lives in `app/core/sentry.py` or `app/core/log_context.py`.
- Release identifier format beyond "commit sha" (e.g., `{env}-{sha}` vs raw sha) — planner picks.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone-level framing

- `.planning/PROJECT.md` — Vision, Active requirements, Out of Scope (Observability entry + excluded Prometheus/Grafana/OpenTelemetry), Key Decisions, "attainable 90%" security posture
- `.planning/REQUIREMENTS.md` §"Observability" — OBS-01 through OBS-05 with locked parameters (`traces_sample_rate=0.05`, `send_default_pii=False`, `FastApiIntegration + SqlalchemyIntegration`, namespace `CarModPicker/Crawlers`, metrics `Ingested/ParseFailures/ElapsedSeconds`)
- `.planning/REQUIREMENTS.md` §"v2 Requirements / Observability Deepening" — OBS-V2-01 (OpenTelemetry/X-Ray) + OBS-V2-02 (synthetic monitoring) are explicitly deferred
- `.planning/ROADMAP.md` §"Phase 2: Observability" — Goal, Depends on (Phase 1), Success Criteria (4 TRUE conditions), concurrency note with Phase 3
- `.planning/STATE.md` — Phase 1 completion status and recent decisions

### Phase 1 context (Phase 2 depends on Phase 1)

- `.planning/phases/01-safety-nets-ci-hardening/01-CONTEXT.md` — Safety nets (coverage floors, DROP-guard, characterization tests) that new observability code must respect
- `.planning/phases/01-safety-nets-ci-hardening/01-VERIFICATION.md` — Phase 1 verification report; confirms baseline that Phase 2 ships on top of
- `.planning/phases/01-safety-nets-ci-hardening/01-05-PLAN.md` + `01-05-SUMMARY.md` — OpenAPI snapshot test; Phase 2 Sentry integration must not silently change OpenAPI shape
- `.planning/phases/01-safety-nets-ci-hardening/01-06-PLAN.md` + `01-06-SUMMARY.md` — Auth characterization tests; the 7 flows must still pass after Sentry wiring

### Codebase context

- `.planning/codebase/INTEGRATIONS.md` §"Monitoring & Observability" — Current state (no Sentry, python-json-logger wired, RequestContextFilter in place, CloudWatch alarms already live for RDS + App Runner)
- `.planning/codebase/INTEGRATIONS.md` §"Environment Configuration" — Existing env var + Secrets Manager pattern to follow for `SENTRY_DSN`
- `.planning/codebase/ARCHITECTURE.md` — App Runner + ECS Fargate + RDS topology; backend entry points (main.py, crawlers CLI, ecs_runner, ecs_rescrape_runner)
- `.planning/codebase/CONVENTIONS.md` — Logging conventions, Secrets Manager pattern, terraform structure, `-n auto` pytest convention
- `.planning/codebase/CONCERNS.md` — Parse-failure signal currently invisible (debt OBS addresses); runbook section to be added per D-28
- `.planning/codebase/TESTING.md` — conftest fixture conventions (caplog, mock_s3, TESTING env guard)

### Files Phase 2 will touch

**Backend**
- `backend/app/main.py` — call `init_sentry()` before `FastAPI()`, already has RequestContextFilter wiring
- `backend/app/core/sentry.py` — NEW file; `init_sentry()` + scope processor + ignored exceptions
- `backend/app/core/log_context.py` — possibly extend with a background-task context helper/decorator
- `backend/app/core/cloudwatch_emf.py` (or equivalent) — NEW file; `aws-embedded-metrics`-based helper
- `backend/app/crawlers/__main__.py` — init Sentry + set CLI log context
- `backend/app/crawlers/runner.py` — emit EMF metrics at the summary block (line ~608)
- `backend/app/crawlers/ecs_runner.py` — init Sentry; pass RunType="live"
- `backend/app/crawlers/ecs_rescrape_runner.py` — init Sentry; pass RunType="rescrape"
- `backend/requirements.txt` — add `sentry-sdk>=2.0,<3`, `aws-embedded-metrics`
- `backend/tests/conftest.py` (or sibling) — Sentry transport stub fixture + log-propagation regression fixture
- `backend/tests/test_sentry_init.py` (new) — unit tests for init gating + scope processor
- `backend/tests/test_cloudwatch_emf.py` (new) — unit tests for EMF emission shape

**Frontend**
- `frontend/src/main.tsx` — call `initSentry()` at top, before `createRoot`
- `frontend/src/lib/sentry.ts` — NEW file; `initSentry()` + env gate
- `frontend/src/components/common/ErrorBoundary.tsx` — add `Sentry.captureException` in `componentDidCatch`
- `frontend/src/contexts/AuthContext.tsx` — set/clear `Sentry.setUser` on auth state changes
- `frontend/package.json` — add `@sentry/react@^10`, `@sentry/vite-plugin`
- `frontend/vite.config.ts` — add `@sentry/vite-plugin` for sourcemap upload (CI-only via env gate)
- `frontend/src/test/` — new vitest for sentry init + ErrorBoundary integration

**Terraform**
- `terraform/monitoring.tf` — add `aws_cloudwatch_metric_alarm` for composite parse-failure + `# TODO(phase-3)` marker + `var.disabled_parse_alarms` variable definition
- `terraform/secretsmanager.tf` — add `aws_secretsmanager_secret` for `SENTRY_DSN`
- `terraform/apprunner.tf` — add `SENTRY_DSN` to `runtime_environment_secrets` + `SENTRY_RELEASE` / `SENTRY_SERVICE_NAME` / `APP_ENVIRONMENT`-tied env vars
- `terraform/ecs.tf` — add `SENTRY_DSN` to task definition secrets + `SENTRY_SERVICE_NAME=ecs-crawler`
- `terraform/README.md` — "Bootstrap: Sentry" section per D-57

**Docs**
- `CLAUDE.md` — one-line pointer to `backend/app/core/sentry.py` under Architecture / Backend
- `.planning/codebase/CONCERNS.md` — add "Crawler Drift Runbook" section per D-28 (anchor `#crawler-drift-runbook`)
- `.planning/phases/02-observability/02-HUMAN-UAT.md` — success-criteria checklist per D-62

### External library references (downstream agents consult these)

- Sentry Python SDK 2.x docs — FastApiIntegration, SqlalchemyIntegration, LoggingIntegration, scope/hub API, `ignore_errors`, `traces_sampler`, `before_send`, `server_name`, `release` parameters
- `@sentry/react` 10.x docs — `Sentry.init`, `Sentry.ErrorBoundary` (not used — we keep custom), `Sentry.captureException`, `Sentry.setUser`, Session Replay on-error integration, `beforeErrorSampling`
- `@sentry/vite-plugin` docs — sourcemap upload, auth token config, release tagging
- `aws-embedded-metrics` Python library — buffered emission, dimension declaration, namespace + metric name API
- CloudWatch EMF spec — `_aws` JSON envelope shape, CloudWatchMetrics dimension limits
- CloudWatch Metric Math — alarm expressions returning NaN for sample-count suppression
- AWS App Runner runtime_environment_secrets — how Secrets Manager values land as env vars
- AWS ECS Fargate task definition `secrets[]` — parallel mechanism for crawler tasks

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`backend/app/core/log_context.py`** — `RequestContextFilter`, `request_id_var`, `user_id_var` ContextVars already wired. Phase 2 extends with a background-task helper but does NOT redesign the pattern.
- **`backend/app/api/middleware/request_context.py`** — HTTP middleware that sets `request_id_var` per request, echoes `X-Request-ID` response header. Zero changes needed for OBS-04.
- **`backend/app/api/dependencies/auth.py`** — already calls `user_id_var.set(str(user.id))` in `get_current_user` / `get_optional_current_user` / `get_current_admin_user`. Sentry scope processor (D-09) reads the same ContextVar, so no dependency on auth refactor timing.
- **`backend/app/main.py:50–63`** — root + uvicorn loggers already have `RequestContextFilter` attached. Phase 2 confirms this coverage via test (OBS-04 audit) rather than rewiring.
- **`backend/app/core/logging.py`** — `LOG_FORMAT` + `JSON_LOG_FORMAT` both include `%(request_id)s %(user_id)s`. Prod (non-TTY) emits structured JSON via `python-json-logger` — EMF lines from `aws-embedded-metrics` ride the same handler.
- **`backend/app/api/middleware/error_handler.py`** — `general_exception_handler` currently calls `logger.error(..., exc_info=True)` for unhandled exceptions. Sentry's `LoggingIntegration` (D-04) picks these up as events without any handler change required. Verify in testing that Sentry's own FastAPI integration doesn't double-capture.
- **`frontend/src/components/common/ErrorBoundary.tsx`** — functional shell already in place, used in both `main.tsx` and `App.tsx`. D-35 is a 3-line drop-in.
- **`frontend/src/contexts/AuthContext.tsx`** — existing auth-state lifecycle is the hook point for `Sentry.setUser` (D-40).
- **`terraform/monitoring.tf`** — `aws_sns_topic.alarms` + 2 email subscriptions + 5 existing alarms. Phase 2 adds 1 composite alarm; Phase 3 expands to per-adapter for_each.
- **`terraform/secretsmanager.tf`** — established pattern (`DATABASE_URL`, `SECRET_KEY`, `EMAIL_FROM`) for injecting secrets into App Runner. Follow it for `SENTRY_DSN`.
- **Existing CloudWatch Logs setup** — App Runner + RDS + ECS already write to CloudWatch Logs with 14-day retention. EMF metrics ride this without new infra.
- **`backend/tests/conftest.py`** — existing fixtures (`caplog`-compatible, `TESTING=true` env guard, `client`) are the entry point for Sentry transport stub + log-propagation regression tests.

### Established Patterns

- **Env var + Secrets Manager for env-specific configuration** — every env-specific secret (DATABASE_URL, SECRET_KEY, EMAIL_FROM) flows through AWS Secrets Manager → App Runner `runtime_environment_secrets`. `SENTRY_DSN` follows this pattern without exception.
- **Gate by `APP_ENVIRONMENT`** — EMAIL_ENABLED default false with prod override, rate limiting off in tests via ENABLE_RATE_LIMITING, S3_ENDPOINT_URL for MinIO vs AWS. Sentry + EMF follow the same env-gate philosophy.
- **ContextVar-based request metadata** — `request_id_var` / `user_id_var` already give us thread-safe + async-safe access. Do NOT introduce thread-locals or a separate request state object.
- **Pydantic v2 settings** — `backend/app/core/config.py` manages env var parsing. New Sentry env vars (`SENTRY_DSN`, `SENTRY_RELEASE`, `SENTRY_SERVICE_NAME`) go there.
- **`pytest -n auto --dist=loadfile`** — all new backend tests must be worker-safe. Sentry transport stub + caplog fixtures compose cleanly with xdist.
- **`alembic autogenerate` only** — no Phase 2 migration work is expected, but if any occurs (unlikely), it must go through autogenerate per CLAUDE.md.
- **Structured JSON logs in prod (non-TTY), colorized text locally** — EMF lines are JSON-shaped log records; they naturally ride the existing `python-json-logger` output.

### Integration Points

- **App Runner `runtime_environment_secrets`** — the injection path for `SENTRY_DSN`. Adding a new secret requires (a) Secrets Manager entry (b) IAM grant (existing `apprunner_instance_secrets` covers this via wildcard on the project's secret prefix — verify) (c) terraform reference in `apprunner.tf`.
- **ECS task definition `secrets[]`** — the parallel injection path for Fargate crawler runs. Requires the same Secrets Manager entry + IAM grant on `ecs_task` role.
- **GitHub Actions frontend workflow** — where `VITE_SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` env vars are set for the sourcemap-upload build step.
- **GitHub Actions backend workflow** — where `SENTRY_RELEASE={git_commit_sha}` is set as a Docker build ARG.
- **`aws_sns_topic.alarms` (terraform/monitoring.tf)** — alarm notification sink; already subscribed to 2 emails.
- **`CloudWatch Logs → Metric Filters`** — CloudWatch auto-extracts metrics from EMF log records in App Runner + ECS log groups. No configuration required.
- **Phase 1's OpenAPI snapshot test (`backend/tests/test_openapi_snapshot.py`)** — Sentry's `FastApiIntegration` hooks middleware; confirm the snapshot is unchanged post-integration. If it does change, regenerate and confirm the diff is semantic-only.
- **Phase 1 auth characterization tests** — must still pass after Sentry wiring; Sentry init is expected to be inert during test runs (D-13).
- **Phase 3 handoff (CRAWL-01/02 auto-discovery)** — consumes the `adapter_names.txt` artifact to convert Phase 2's composite alarm into per-adapter for_each. Phase 2 leaves the hook comment; Phase 3 fills it.

</code_context>

<specifics>
## Specific Ideas

- **"Measure, alert, then drill down"** — Phase 2 ships the signal layer; the per-adapter precision comes in Phase 3 when adapter auto-discovery makes the alarm list maintainable. Don't try to solve observability AND adapter-registry maintenance in one phase.
- **"EMF because we already have Logs"** — We already pay for CloudWatch Logs. EMF rides that path with no new IAM, no new API cost, no new failure mode. Direct `PutMetricData` would have been simpler to reason about but pays $0.01/1000 for nothing we gain.
- **"Session Replay on-error only"** — Sentry's replay feature has real free-tier constraints (500/mo). On-error sampling means replay cost scales with bug count, not session count. High benefit at near-zero quota burn.
- **"Free tier first, upgrade on evidence"** — Sentry Developer plan ($26/mo) is half the project budget. Stay on free until quota evidence justifies the upgrade.
- **"Don't pay for precision we don't need yet"** — User chose per-adapter alarms ($11.40/mo) over per-tier ($0.30/mo) because single-adapter drift is the dominant failure mode for a 114-adapter fleet. The benefit:cost math is explicit — documented so Phase 3 can revisit if the evidence shifts.
- **"Staging bakes the config"** — 24h in staging before prod catches PII leaks and alarm-too-sensitive misconfigurations before they hit real users or real quota.
- **"The audit is a test, not a doc"** — OBS-04's "every log line" claim is load-bearing for Sentry event enrichment and CloudWatch correlation. A pytest fixture that fails CI on regression is stronger than a one-time audit.
- **"Deviation: SNS → email, not SNS → SES"** — REQUIREMENTS OBS-03 specifies "SNS → SES email." The existing `aws_sns_topic.alarms` is subscribed to emails directly (SNS → email protocol, not via SES). Operator experience is identical. Using the literal SNS → Lambda → SES chain adds a Lambda to maintain. Captured here so the execution plan doesn't surprise the verifier.

</specifics>

<deferred>
## Deferred Ideas

### Deferred to Phase 3 (concurrent with Phase 2 per ROADMAP)

- **Per-adapter parse-failure alarms** — Blocked on CRAWL-01/02 adapter auto-discovery (Phase 3) which emits the `adapter_names.txt` (or equivalent) artifact. Phase 2 ships a single composite alarm + `# TODO(phase-3)` terraform marker + this entry. Expected cost at Phase 3 conversion: ~$11.40/mo.
- **Per-adapter CloudWatch dashboard** — Deferred until per-adapter alarms land (would reference the same adapter list).

### Deferred to Phase 6 or later

- **Frontend sourcemap retention policy** — `@sentry/vite-plugin` uploads sourcemaps; we don't have a deletion policy. Sentry retains for 90 days on free tier. Revisit if a past-90-day regression investigation needs older maps.
- **Sentry alert rules (Slack / PagerDuty)** — Out of scope; Phase 2 only wires the capture side. Alert routing past email defaults is a separate workflow choice.
- **Frontend performance budgets + assertions** — BrowserTracing is enabled but no p75/p95 budget is enforced. Future phase if the frontend becomes the bottleneck.
- **Synthetic monitoring / canary crawler** — Explicitly deferred to v2 per REQUIREMENTS (OBS-V2-02).
- **OpenTelemetry / X-Ray distributed tracing** — Explicitly deferred to v2 per REQUIREMENTS (OBS-V2-01). Sentry performance tracing covers ~90% at current traffic.
- **Prometheus + Grafana stack** — Explicitly out of scope per REQUIREMENTS (CloudWatch covers the need at zero ops cost).

### Noted but not a Phase 2 deliverable

- **Scrubbing scope expansion** — If the "default only" PII scrub (D-03) proves insufficient, add a custom `before_send` in a future phase. Event in Sentry will show the leak before we act on it — acceptable.
- **Sentry project splitting (staging vs prod)** — Same-project-with-environment-tag (D-08) is the starting point. Split projects only if alert rules diverge significantly.
- **`logger.error` ignore_loggers refinement** — LoggingIntegration captures all ERROR logs. If a specific logger proves noisy (e.g., an intentionally-loud crawler path), add to `ignore_loggers` then. Don't pre-tune.
- **Replay quota client-side throttle** — Trust Sentry's server-side quota enforcement (D-41). Revisit only if it becomes a problem.
- **OBS-04 "process-wide" audit** — Current scope is "every log line during a request" + "bg:/cli: prefix for non-request contexts." We are not claiming every single `print()` in third-party code is captured; the audit is bounded to our logger config.

</deferred>

---

*Phase: 02-observability*
*Context gathered: 2026-04-22*
