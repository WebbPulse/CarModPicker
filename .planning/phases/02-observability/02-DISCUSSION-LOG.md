# Phase 2: Observability - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-22
**Phase:** 02-observability
**Areas discussed:** Sentry backend (OBS-01), CloudWatch metrics (OBS-02), Parse-failure alarm (OBS-03), Frontend Sentry (OBS-05), OBS-04 audit, Testing / Secrets / Rollout / Cost

---

## Sentry backend (OBS-01)

### DSN injection + env gate

| Option | Description | Selected |
|--------|-------------|----------|
| Secrets Manager + env gate | SENTRY_DSN in AWS Secrets Manager; init only when DSN non-empty AND APP_ENVIRONMENT in {staging, production} | ✓ |
| Plain env var, init when set | SENTRY_DSN env var only; init on truthy | |
| Per-environment DSN (prod vs staging) | Two Sentry projects, two DSNs selected by APP_ENVIRONMENT | |

**User's choice:** Secrets Manager + env gate (recommended).

### Release tag

| Option | Description | Selected |
|--------|-------------|----------|
| GIT_COMMIT_SHA at build time | Dockerfile bakes COMMIT_SHA as SENTRY_RELEASE via GHA | ✓ |
| Skip release tagging this phase | release=None | |
| Image tag as release | ECR image tag (latest/staging-latest) as release | |

**User's choice:** GIT_COMMIT_SHA at build time (recommended).

### PII scrub

| Option | Description | Selected |
|--------|-------------|----------|
| Default only (send_default_pii=False) | Rely on Sentry defaults + locked flag; no custom before_send | ✓ |
| Default + custom scrub hook | Add before_send redacting email, tokens, session_id | |
| Default + denylist URL patterns | Skip reporting for /api/auth/* | |

**User's choice:** Default only (recommended).

### LoggingIntegration

| Option | Description | Selected |
|--------|-------------|----------|
| LoggingIntegration at ERROR level | Capture ERROR+ as events; WARNING+ as breadcrumbs | ✓ |
| Unhandled exceptions only | Disable LoggingIntegration | |
| LoggingIntegration + custom level per-logger | Custom ignore_loggers thresholds | |

**User's choice:** LoggingIntegration at ERROR level (recommended).

### Where init_sentry() is called

| Option | Description | Selected |
|--------|-------------|----------|
| Shared helper called from every entry point | main.py + crawlers __main__ + ecs_runner + ecs_rescrape_runner | ✓ |
| FastAPI only | Only main.py initializes Sentry | |
| FastAPI + ECS runners, skip CLI | Init everywhere except CLI | |

**User's choice:** Shared helper called from every entry point (recommended).

### Transaction sampling

| Option | Description | Selected |
|--------|-------------|----------|
| Suppress /health, /ready, /openapi.json | traces_sampler forces 0 for these paths; 0.05 elsewhere | ✓ |
| Flat 0.05 for everything | Simple rate, noisier Performance view | |
| Ignore transactions entirely this phase | traces_sample_rate=0 | |

**User's choice:** Suppress /health, /ready, /openapi.json (recommended).

### Ignored exceptions

| Option | Description | Selected |
|--------|-------------|----------|
| Ignore HTTPException + RateLimitExceeded | ignore_errors list at init | ✓ |
| Nothing ignored | Full fidelity, more dashboard noise | |
| Custom ignore list beyond HTTPException | Also ignore requests.ConnectionError, boto3 Throttling | |

**User's choice:** Ignore HTTPException + RateLimitExceeded (recommended).

### Environment split

| Option | Description | Selected |
|--------|-------------|----------|
| Same project, environment tag | staging + prod share a project | ✓ |
| Separate projects | carmodpicker-backend-staging + -prod | |

**User's choice:** Same project, environment tag (recommended).

### Scope enrichment

| Option | Description | Selected |
|--------|-------------|----------|
| Scope processor: user_id + request_id only | Matches send_default_pii=False and OBS-01 success criterion | ✓ |
| Do nothing, FastApiIntegration attaches it | Violates OBS-01 success criterion | |
| Full context: user_id + email + tier + request_id | Leaks PII | |

**User's choice:** Scope processor: user_id + request_id only (recommended).

### Tag strategy

| Option | Description | Selected |
|--------|-------------|----------|
| environment, request_id, adapter (when set) | Tight set, high signal | ✓ |
| Environment + request_id only | No adapter tag | |
| Kitchen-sink tags | user_tier, endpoint_category, fetcher_tier added | |

**User's choice:** environment, request_id, adapter (recommended).

### Process distinction

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct server_name / service via tag | apprunner-backend vs ecs-crawler | ✓ |
| Same service, environment tag only | One service in Sentry | |

**User's choice:** Distinct server_name (recommended).

### Init timing

| Option | Description | Selected |
|--------|-------------|----------|
| Before FastAPI() / any middleware wiring | First thing after imports | ✓ |
| Inside lifespan() startup | Misses pre-mount errors | |

**User's choice:** Before FastAPI() (recommended).

### Test suite suppression

| Option | Description | Selected |
|--------|-------------|----------|
| Suppress when TESTING=true | Matches ENABLE_RATE_LIMITING=false pattern | ✓ |
| Suppress when DSN unset | DSN-gate only | |

**User's choice:** TESTING=true (recommended).

### SDK pinning

| Option | Description | Selected |
|--------|-------------|----------|
| Pin to 2.x minor (>=2.0,<3) | Allow patches + minors via Dependabot | ✓ |
| Pin exact version | sentry-sdk==2.34.0 style | |
| Unpinned major | Risky | |

**User's choice:** Pin to 2.x minor (recommended).

### Docs location

| Option | Description | Selected |
|--------|-------------|----------|
| Docstring in app/core/sentry.py + CLAUDE.md pointer | No separate markdown file | ✓ |
| Dedicated OBSERVABILITY.md | New backend/docs/observability.md | |
| Terraform README only | Ops-only doc | |

**User's choice:** Docstring + CLAUDE.md pointer (recommended).

---

## CloudWatch metrics (OBS-02)

### Emission mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| CloudWatch EMF via structured log lines | Ride existing Logs; zero PutMetricData API calls | ✓ |
| Direct boto3 put_metric_data | Explicit + testable; adds IAM + API cost | |
| Metric filter on existing log lines | Log format becomes contract | |

**User's choice:** CloudWatch EMF via structured log lines (recommended).

### Emission point

| Option | Description | Selected |
|--------|-------------|----------|
| Inside run_crawler, at the summary block | runner.py line ~608 | ✓ |
| In run_crawlers aggregate + per-result loop | Double-count risk | |
| New crawler_metrics.py decorator | Extra layer | |

**User's choice:** Inside run_crawler at the summary block (recommended).

### Dimensions

| Option | Description | Selected |
|--------|-------------|----------|
| AdapterName + Environment | 228 time series | ✓ |
| AdapterName only | No env separation | |
| AdapterName + Environment + FetcherTier | 684 time series | |

**User's choice:** AdapterName + Environment (recommended) — *augmented with RunType at D-19 after the rescrape discussion.*

### Dev / test behavior

| Option | Description | Selected |
|--------|-------------|----------|
| No-op when APP_ENVIRONMENT != staging/production | Early return from helper | ✓ |
| EMF log lines always — harmless locally | CloudWatch ignores without agent | |
| Local moto mock | Only for direct boto3 path | |

**User's choice:** No-op outside staging/prod (recommended).

### Additional metrics beyond REQUIREMENTS-locked 3

| Option | Description | Selected |
|--------|-------------|----------|
| Ingested + ParseFailures + ElapsedSeconds only | 342 time series; focused | ✓ |
| Add RateLimitBailout + HttpErrors (bucketed) | Cardinality inflation | |
| Add all 8 run_crawler summary fields | 912 time series | |

**User's choice:** 3 metrics only (recommended).

### EMF format

| Option | Description | Selected |
|--------|-------------|----------|
| Raw dict via logger.info | ~20 LOC, no new dep | |
| aws-embedded-metrics library | Buffering, flushing, dim limits | ✓ |
| Custom EMF helper module | 30–40 LOC, testable | |

**User's choice:** aws-embedded-metrics library (not the recommended option — user picked more robust).

### Rescrape runs

| Option | Description | Selected |
|--------|-------------|----------|
| Same metrics, distinguish via RunType dimension | Single namespace; alarm can filter | ✓ |
| Rescrape emits no metrics | Out of scope for OBS-02 | |
| Rescrape emits under different namespace | Separates concerns; more dashboards | |

**User's choice:** Same metrics with RunType dimension (recommended).

### Parallel-run flushing

| Option | Description | Selected |
|--------|-------------|----------|
| Per-adapter, immediately when each run_crawler completes | 1 EMF line per adapter | ✓ |
| Batched at end of run_crawlers | Two code paths | |

**User's choice:** Per-adapter immediate (recommended).

---

## Parse-failure alarm (OBS-03)

### Rate math

| Option | Description | Selected |
|--------|-------------|----------|
| ParseFailures / (ParseFailures + Ingested) via metric math | m2 / (m1 + m2) > 0.5 | ✓ |
| ParseFailures / total_urls_attempted | Includes gone + robots-skipped | |
| Absolute ParseFailures threshold | No rate; fires on small runs | |

**User's choice:** Metric-math rate expression (recommended).

### Granularity (initial question)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-adapter metric-math alarms | 114 alarms × $0.10/mo = $11.40/mo | ✓ |
| One composite alarm | Aggregate; cheapest | |
| Per-adapter via anomaly detection | $0.30/metric × 114 | |
| Per-tier (3 alarms) | Middle ground | |

**User's choice:** Per-adapter (recommended) — *later re-examined for cost; user confirmed to keep.*

### Small-sample suppression

| Option | Description | Selected |
|--------|-------------|----------|
| Require attempted_total >= 10 in metric math | Returns NaN below threshold | ✓ |
| No floor | Fires on any small run | |
| Floor at 5 | Softer; more false positives | |

**User's choice:** Floor at 10 (recommended).

### Notification path

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse existing ${prefix}-alarms SNS topic | Already email-subscribed | ✓ |
| SNS → Lambda → SES (literal spec) | Adds Lambda | |
| Dedicated new SNS topic | Separate channel | |

**User's choice:** Reuse existing SNS topic (recommended). *Noted as deviation from literal REQUIREMENTS "SNS → SES" text.*

### Evaluation period

| Option | Description | Selected |
|--------|-------------|----------|
| 1-hour period, 1 evaluation period | Matches crawler cadence | ✓ |
| 5-minute period, 3 eval periods | Mismatched cadence | |
| 24-hour rolling period | Too slow | |

**User's choice:** 1-hour / 1 eval (recommended).

### Adapter list source

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 3 adapter auto-discovery feeds a data file | Phase 2 composite, Phase 3 per-adapter | ✓ |
| Hand-maintained terraform variable list | Drift risk | |
| Emit alarms via Python management script | Diverges from IaC | |
| Flagship allowlist (~5 adapters) | Judgment call per adapter | |

**User's choice:** Phase 3 auto-discovery handoff (recommended).

### Mute mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| AWS console temp + disabled_adapters terraform list | Reversible, auditable | ✓ |
| No explicit mute | Spammy | |
| Slack channel silence via SNS filter | Over-infra | |

**User's choice:** Console temp + terraform list (recommended).

### Phase split

| Option | Description | Selected |
|--------|-------------|----------|
| Ship OBS-02 + OBS-03 scaffold now, per-adapter in Phase 3 | Composite placeholder closes success criterion | ✓ |
| Block Phase 2 on Phase 3 for OBS-03 | Breaks concurrency | |
| Ship per-adapter now with manual adapter list | Accept drift temporarily | |

**User's choice:** Ship scaffold now, per-adapter in Phase 3 (recommended).

### OK action

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, ok_actions = [alarms SNS] | Matches existing alarm pattern | ✓ |
| Alarm only, no recovery emails | Inconsistent with existing pattern | |

**User's choice:** Yes (recommended).

### Alarm body

| Option | Description | Selected |
|--------|-------------|----------|
| Default body, runbook link in alarm description | Description surfaces in email | ✓ |
| Lambda formatter for rich HTML emails | Extra infra | |
| Plain default, skip description | Minimal value | |

**User's choice:** Default + runbook link (recommended).

### Runbook location

| Option | Description | Selected |
|--------|-------------|----------|
| New section in CONCERNS.md | Matches codebase maps convention | ✓ |
| backend/app/crawlers/README.md addition | Co-located with code | |
| Skip runbook this phase | Defers | |

**User's choice:** CONCERNS.md section (recommended).

---

## Frontend Sentry (OBS-05)

### Feature scope (initial)

| Option | Description | Selected |
|--------|-------------|----------|
| Errors only via @sentry/react | Smallest bundle | |
| Errors + Performance (browser tracing) | +20KB | |
| Errors + Performance + Session Replay | +90KB, full observability | ✓ |
| Errors + Profiler only | Narrow use case | |

**User's choice:** Errors + Performance + Session Replay — *replay later downgraded to on-error only for cost.*

### DSN injection

| Option | Description | Selected |
|--------|-------------|----------|
| VITE_SENTRY_DSN env var at build time | Standard Vite pattern | ✓ |
| Runtime fetch from /api/app-settings | +1 hop before init | |
| Hardcoded per environment | Code change for rotation | |

**User's choice:** VITE_SENTRY_DSN at build time (recommended).

### Sourcemap upload

| Option | Description | Selected |
|--------|-------------|----------|
| @sentry/vite-plugin, auth token via GHA secret | Upload in CI only | ✓ |
| No sourcemap upload | Minified traces | |
| Sourcemaps served publicly | Exposes source | |

**User's choice:** @sentry/vite-plugin in CI (recommended).

### ErrorBoundary integration

| Option | Description | Selected |
|--------|-------------|----------|
| Call Sentry.captureException in componentDidCatch | Keep existing class component + fallback UI | ✓ |
| Replace with Sentry.ErrorBoundary HOC | Loses custom fallback | |
| Both (nested boundaries) | Double boundary confusion | |

**User's choice:** Sentry.captureException in componentDidCatch (recommended).

### Session Replay PII masking

| Option | Description | Selected |
|--------|-------------|----------|
| Mask all text + all inputs (Sentry defaults) | Safest | ✓ |
| Mask inputs only, text visible | Leaks rendered text | |
| Custom per-component masking | Error-prone | |

**User's choice:** Mask all text + all inputs (recommended).

### Auth-route replay blocking

| Option | Description | Selected |
|--------|-------------|----------|
| Block replay on auth routes | beforeErrorSampling drops for /login, /oauth-callback, etc. | ✓ |
| Mask URL search params globally | Doesn't help with fragments | |
| Trust masking + send_default_pii=false | Accepts risk | |

**User's choice:** Block replay on auth routes (recommended).

### Frontend tracesSampleRate

| Option | Description | Selected |
|--------|-------------|----------|
| 0.05 to match backend | Trace correlation; low cost | ✓ |
| 0.1 | Higher res, asymmetric | |
| 1.0 | Free-tier overrun | |

**User's choice:** 0.05 (recommended).

### Sentry.init() location

| Option | Description | Selected |
|--------|-------------|----------|
| Top of main.tsx, before createRoot | Pre-mount error coverage | ✓ |
| Inside ErrorBoundary constructor | Misses pre-mount errors | |
| New src/lib/sentry.ts module imported by main.tsx | Separate module; cleaner | |

**User's choice:** Top of main.tsx (recommended) — *final D-39 implementation places the init in src/lib/sentry.ts and calls it from main.tsx, combining intent of both options.*

### User context

| Option | Description | Selected |
|--------|-------------|----------|
| Set Sentry.setUser({id: user.id}) on login | Mirrors backend enrichment | ✓ |
| Don't set user context | Anonymous events | |

**User's choice:** Set user context on login (recommended).

### Replay quota guard

| Option | Description | Selected |
|--------|-------------|----------|
| Trust Sentry's server-side quota | No client-side throttle | ✓ |
| Disable replay on rate-limit event | Over-engineered | |

**User's choice:** Trust server-side quota (recommended).

### Frontend env gate

| Option | Description | Selected |
|--------|-------------|----------|
| Enabled when DSN set AND MODE !== development | Dev silent | ✓ |
| Enabled whenever DSN is set | Slight footgun | |
| Tree-shaken via import.meta.env.PROD | Can't test locally | |

**User's choice:** DSN + MODE gate (recommended).

### @sentry/react pinning

| Option | Description | Selected |
|--------|-------------|----------|
| Pin to major (^10.0.0) | Dependabot bumps patch/minor | ✓ |
| Pin exact version | More PRs | |

**User's choice:** Pin to major (recommended).

---

## OBS-04 audit

### Regression guard

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest fixture + per-test log capture assertion | Catches regressions in CI | ✓ |
| Grep audit at review time, no test | No ongoing guard | |
| Middleware wraps logger to auto-annotate | Duplicate; ContextVars already do this | |

**User's choice:** Pytest fixture + assertion (recommended).

### Background task context

| Option | Description | Selected |
|--------|-------------|----------|
| request_id=bg:<task>:<job_id>, user_id=bg | Greppable prefix | ✓ |
| Leave defaults ('-') | Indistinguishable | |
| Add separate job_id / task_name ContextVars | More fields to update | |

**User's choice:** bg: prefix (recommended).

### Third-party logger propagation

| Option | Description | Selected |
|--------|-------------|----------|
| Root logger already has the filter — audit + add test | Confirm propagation | ✓ |
| Skip — only our own logger lines matter | Loses triage context | |

**User's choice:** Audit + test (recommended).

### CLI context

| Option | Description | Selected |
|--------|-------------|----------|
| request_id=cli:<pid>, user_id=cli | Distinguishable | ✓ |
| Leave defaults | Simplest | |

**User's choice:** cli: prefix (recommended).

---

## Testing / Secrets / Phase handoff / Rollout

### Test harness

| Option | Description | Selected |
|--------|-------------|----------|
| Sentry transport stub + EMF log line assertion | No network; in-memory | ✓ |
| moto for CloudWatch + sentry env disabled | Mostly N/A since we picked EMF | |
| No tests for observability code | Fails Phase 1 coverage floor | |

**User's choice:** Transport stub + EMF assertion (recommended).

### Secrets bootstrap

| Option | Description | Selected |
|--------|-------------|----------|
| Manual Sentry project + Secrets Manager + GHA secret + README | Documented manual steps | ✓ |
| Fully Terraform-managed via Sentry Terraform provider | New provider | |
| Create DSN ad-hoc on first need | Risk of misconfig-at-incident | |

**User's choice:** Manual + documented (recommended).

### Phase 3 handoff

| Option | Description | Selected |
|--------|-------------|----------|
| Deferred item in CONTEXT.md + TODO in terraform | Visible in planning + code | ✓ |
| GitHub issue + label | Outside .planning/ | |
| No explicit handoff | Relies on discipline | |

**User's choice:** CONTEXT.md deferred + terraform TODO (recommended).

### Rollout cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Staging first, bake 24h, then prod | Catches PII + alarm misconfig | ✓ |
| Merge = deploy both simultaneously | Prod is canary | |
| Feature-flag Sentry init by env var | Overkill | |

**User's choice:** Staging first, bake 24h (recommended).

### Execution sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| OBS-04 audit → Sentry backend → CloudWatch metrics → Frontend Sentry → Parse-failure alarm | Each plan dependency-driven | ✓ |
| Parallel: backend Sentry + frontend Sentry + metrics, alarm last | Faster wall-clock | |
| Sentry first (both envs, bake), then metrics + alarm | Subsystem separation | |

**User's choice:** Sequential audit → backend → metrics → frontend → alarm (recommended).

### LoggingIntegration / EMF interaction

| Option | Description | Selected |
|--------|-------------|----------|
| No conflict — EMF INFO becomes breadcrumbs | Sentry default event_level=ERROR | ✓ |
| Raise EMF log level to DEBUG | Breaks CloudWatch extraction | |
| ignore_loggers for the EMF logger | Defensive, unneeded | |

**User's choice:** No conflict (recommended).

### Cost cap discussion

| Option | Description | Selected |
|--------|-------------|----------|
| Monitor + react, don't pre-cap (default recommended) | | |
| Pre-cap: traces_sample_rate=0.01, replay=0.001 | | |
| Disable Session Replay entirely | | |
| Custom free-text | Project budget <$50/mo; optimize benefit:cost | ✓ |

**User's choice (free text):** "I have overall cost concerns with this entire project. I want the project to be relatively sustainable to run at low user counts before launch and I also want moderate usage post launch to not bankrupt me before we prove and expand on our business model. We should try and stay under $50 a month and focus on solutions that provide the best benefit:cost ratios."

### Success verification

| Option | Description | Selected |
|--------|-------------|----------|
| Manual UAT checklist in HUMAN-UAT.md | Matches Phase 1 | ✓ |
| Automated integration test against staging | Fragile | |
| Trust unit tests + code review | No runtime verification | |

**User's choice:** HUMAN-UAT.md checklist (recommended).

---

## Cost re-examination (after $50/mo budget surfaced)

### Alarm granularity (revisited)

| Option | Description | Selected |
|--------|-------------|----------|
| Switch to per-tier alarms (3 alarms, ~$0.30/mo) — recommended for cost | 80% of value at 2.5% of cost | |
| Keep per-adapter alarms in Phase 3 ($11.40/mo) | Best granularity | ✓ |
| Keep composite alarm only ($0.10/mo) | Cheapest; misses single-adapter drift | |
| Allowlist ≈10 flagship adapters ($1/mo) | Middle ground | |

**User's choice:** Keep per-adapter alarms (not the cost-recommended option). Per-adapter precision explicitly worth $11.40/mo.

### Session Replay cost

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Session Replay at 1% session / 100% on-error (recommended) | Won't exceed 500/mo free tier | |
| Drop Session Replay entirely | Smaller bundle, no replay | |
| Session Replay on-error only (replaysSessionSampleRate=0) | Replay only on error events | ✓ |

**User's choice:** On-error only (tighter cost discipline than the default recommended option). **Reverses the earlier "Errors + Performance + Session Replay at 1%/100%" decision to "Errors + Performance + Session Replay at 0%/100%"**.

### Sentry plan

| Option | Description | Selected |
|--------|-------------|----------|
| Start on free, upgrade only if breach 5K/mo | $0/mo | ✓ |
| Pre-upgrade to Developer ($26/mo) | Half the budget | |

**User's choice:** Free tier first (recommended).

### CloudWatch Logs retention

| Option | Description | Selected |
|--------|-------------|----------|
| Keep 14 days | Matches existing | ✓ |
| Drop to 7 days | Marginal savings | |
| Extend to 30 days | ~$1/mo more | |

**User's choice:** 14 days (recommended).

---

## Claude's Discretion

Recorded in CONTEXT.md `<decisions>` "Claude's Discretion" subsection:
- Exact module naming (cloudwatch_emf.py vs metrics.py)
- Background-task log-context wrapper name
- Terraform file layout (extend monitoring.tf vs new observability.tf)
- Pytest fixture file placement for OBS-04
- Sentry scope processor module placement
- Release identifier format beyond raw sha

## Deferred Ideas

Recorded in CONTEXT.md `<deferred>` section:
- Per-adapter parse-failure alarms → Phase 3 (auto-discovery-fed for_each)
- Per-adapter CloudWatch dashboard → Phase 3
- Frontend sourcemap retention policy
- Sentry alert rules (Slack / PagerDuty)
- Frontend performance budgets
- Synthetic monitoring / canary crawler (v2 per REQUIREMENTS)
- OpenTelemetry / X-Ray distributed tracing (v2 per REQUIREMENTS)
- Prometheus + Grafana (explicitly out of scope)
- Custom PII scrub scope expansion (only if leak surfaces)
- Sentry project splitting (only if alert rules diverge)
- LoggingIntegration ignore_loggers refinement (only if noise surfaces)
- Replay quota client-side throttle (only if server-side enforcement proves insufficient)
