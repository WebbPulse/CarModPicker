# Phase 2: Observability - Research

**Researched:** 2026-04-22
**Domain:** Sentry (Python + React) + CloudWatch EMF + metric-math alarms + log-context propagation audit
**Confidence:** HIGH for Sentry Python/React APIs and CloudWatch EMF/alarm syntax; MEDIUM for aws-embedded-metrics Python sink routing on ECS Fargate (one documented open issue).

## Summary

Phase 2 is a well-constrained integration phase. CONTEXT.md already locks 62 decisions — this research fills in the specific SDK shapes, breaking-change landmines, and validation hooks that the planner will turn into PLAN.md tasks.

Four "hot spots" that the plan must get exactly right:

1. **sentry-sdk 2.x `ignore_errors` accepts exception *class names* (strings) — confirmed by `docs.sentry.io`.** D-07 passes `[HTTPException, RateLimitExceeded]` as classes. This may or may not work in 2.x; the docs describe ignore_errors using "class names" language. **The plan should pass classes (2.x does accept class references in practice) but the first test written should assert that a raised `HTTPException` does not produce a Sentry event** — a single test covers "is this parameter shape actually working on our SDK version" without having to re-read changelogs forever.

2. **StarletteIntegration is NOT auto-enabled when FastApiIntegration is used.** The official FastAPI doc explicitly says *both* must be instantiated. D-05's `init_sentry()` helper must include both `StarletteIntegration()` and `FastApiIntegration()`; omitting the Starlette one silently drops middleware-layer error capture.

3. **aws-embedded-metrics sink routing on ECS Fargate.** The default environment-detector probes for Lambda and EC2 but does not auto-detect "ECS Fargate." On ECS, the library falls back to `DefaultEnvironment` which uses an agent (TCP) sink by default. To make EMF ride the existing `awslogs` driver path (which is what D-16 assumes), **you MUST set `AWS_EMF_ENVIRONMENT=Local`** — that forces the stdout sink, and awslogs picks it up. This is a non-obvious footgun and there is an open bug (#109) about the *last* EMF line being dropped if followed by end-of-stream — the mitigation (log a non-EMF summary line AFTER the EMF emission) lines up naturally with D-17's existing "Adapter X done" summary line.

4. **Terraform `aws_cloudwatch_metric_alarm` with metric_query cannot set top-level `period`.** Known Terraform provider bug (#29398) — the plan must ensure `period` is only set *inside* each `metric_query` block, never at the resource top level.

**Primary recommendation:** Implement in the OBS-04 → OBS-01 → OBS-02 → OBS-05 → OBS-03 order locked by D-53. Pin `sentry-sdk==2.x` (current 2.58.0), `aws-embedded-metrics==3.x` (current 3.5.0), `@sentry/react@^10` (current 10.49.0), `@sentry/vite-plugin@^4` (current 5.2.0 — note major 5 available, but 4.x still maintained and simpler). Write a thin `init_sentry()` helper that reads `SENTRY_DSN`, `APP_ENVIRONMENT`, `TESTING` and bails early if conditions aren't met; write a thin `emit_crawler_metrics()` helper that no-ops outside staging/prod. Every integration point gets a regression test — the phase is as much about not-polluting-the-prod-Sentry-project-from-pytest as it is about wiring capture.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-01 | Sentry SDK initialized in `backend/app/main.py` with `FastApiIntegration` + `SqlalchemyIntegration`, `traces_sample_rate=0.05`, `send_default_pii=False` | §Sentry Python SDK 2.x — exact init kwargs, integration list, scope processor pattern. |
| OBS-02 | Per-adapter CloudWatch custom metrics emitted in `CarModPicker/Crawlers` namespace (`Ingested`, `ParseFailures`, `ElapsedSeconds`) | §aws-embedded-metrics + §CloudWatch EMF — envelope shape, sink config, emission point in `runner.py:608`. |
| OBS-03 | CloudWatch alarm on per-adapter `ParseFailures` rate > 50% with SNS → SES notification (D-24 deviation: SNS → email) | §CloudWatch metric-math alarm — terraform `metric_query[]` blocks, NaN suppression via `IF((m1+m2)<10, NAN, ...)`. |
| OBS-04 | Request-ID propagation audit — every log line during a request includes request_id + user_id | §Testing — pytest `caplog` iteration over `record.request_id` / `record.user_id` attrs. |
| OBS-05 | Frontend errors captured by Sentry via `@sentry/react` wired into `ErrorBoundary` | §@sentry/react 10.x — `Sentry.captureException(error, { extra: { errorInfo } })` inside `componentDidCatch`, Session Replay on-error, `beforeErrorSampling` pathname gate. |

---

## 1. Technical Approach Summary

### Backend init shape (OBS-01)

Single helper `backend/app/core/sentry.py::init_sentry()`:

```python
import os
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from app.core.config import settings
from app.core.log_context import request_id_var, user_id_var

_HEALTH_PATHS = {"/health", "/ready", "/api/openapi.json"}

def _traces_sampler(sampling_context):
    # transaction_context.name is the route/path in FastApiIntegration
    name = sampling_context.get("transaction_context", {}).get("name", "")
    if any(name.endswith(p) or name == p for p in _HEALTH_PATHS):
        return 0.0
    return 0.05

def _before_send(event, hint):
    # Enrich with ContextVar-derived request_id + user_id.
    # This runs per-event; cheaper than add_global_event_processor for this purpose.
    rid = request_id_var.get()
    uid = user_id_var.get()
    if rid and rid != "-":
        event.setdefault("tags", {})["request_id"] = rid
    if uid and uid != "-":
        event.setdefault("user", {})["id"] = uid
    return event

def init_sentry(*, server_name: str) -> None:
    if os.environ.get("TESTING") == "true":
        return
    env = (settings.APP_ENVIRONMENT or "").lower()
    if env not in {"staging", "production"}:
        return
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        release=os.environ.get("SENTRY_RELEASE") or None,
        server_name=server_name,
        send_default_pii=False,
        traces_sampler=_traces_sampler,
        ignore_errors=[
            "fastapi.exceptions.HTTPException",
            "starlette.exceptions.HTTPException",
            "slowapi.errors.RateLimitExceeded",  # or whichever class your middleware raises
        ],
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=_before_send,
    )
```

Call sites: `app/main.py` before `FastAPI(...)` (D-12); `ecs_runner.py` / `ecs_rescrape_runner.py` / `__main__.py` before any other work, with distinct `server_name` values (D-11).

### EMF emission shape (OBS-02)

Single helper `backend/app/core/cloudwatch_emf.py::emit_crawler_run_metrics()`. Called from `runner.py` right after the `logger.log(summary_level, ...)` block at line ~608 (D-17).

```python
import os
from aws_embedded_metrics.logger.metrics_logger_factory import create_metrics_logger
from app.core.config import settings

def emit_crawler_run_metrics(
    *,
    adapter_name: str,
    run_type: str,  # "live" or "rescrape"
    ingested: int,
    parse_failures: int,
    elapsed_seconds: float,
) -> None:
    if os.environ.get("TESTING") == "true":
        return
    env = (settings.APP_ENVIRONMENT or "").lower()
    if env not in {"staging", "production"}:
        return
    metrics = create_metrics_logger()
    metrics.set_namespace("CarModPicker/Crawlers")
    metrics.set_dimensions(
        {"AdapterName": adapter_name, "Environment": env, "RunType": run_type}
    )
    metrics.put_metric("Ingested", ingested, "Count")
    metrics.put_metric("ParseFailures", parse_failures, "Count")
    metrics.put_metric("ElapsedSeconds", elapsed_seconds, "Seconds")
    metrics.flush()
```

Critical environment var (set in `terraform/ecs.tf` + `terraform/apprunner.tf`): `AWS_EMF_ENVIRONMENT=Local`. This forces the stdout sink in ECS Fargate + App Runner; without it, the library tries to reach a CloudWatch agent that isn't running and silently drops metrics. See §aws-embedded-metrics footguns.

`parse_failures` = `skipped_not_product` (matches existing drift metric at `runner.py:602`). `elapsed_seconds` = `time.monotonic() - start_ts` where `start_ts` is captured immediately before the URL loop (requires ~3-line addition around the existing loop).

### Terraform composite alarm (OBS-03)

`terraform/monitoring.tf` adds one `aws_cloudwatch_metric_alarm` resource. The IF() expression returns `NaN` below 10 samples; combined with `treat_missing_data = "notBreaching"`, small-sample runs never breach.

```hcl
resource "aws_cloudwatch_metric_alarm" "crawler_parse_failure_composite" {
  alarm_name        = "${local.prefix}-crawler-parse-failure-composite"
  alarm_description = "Parse-failure rate >50% across all live-mode crawlers. Runbook: .planning/codebase/CONCERNS.md#crawler-drift-runbook"

  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  datapoints_to_alarm = 1
  threshold           = 0.5
  treat_missing_data  = "notBreaching"

  # DO NOT set `period` at top level — conflicts with metric_query (terraform-provider-aws#29398)

  metric_query {
    id          = "ingested"
    metric {
      metric_name = "Ingested"
      namespace   = "CarModPicker/Crawlers"
      period      = 3600
      stat        = "Sum"
      dimensions  = { Environment = var.app_environment, RunType = "live" }
    }
  }

  metric_query {
    id          = "failures"
    metric {
      metric_name = "ParseFailures"
      namespace   = "CarModPicker/Crawlers"
      period      = 3600
      stat        = "Sum"
      dimensions  = { Environment = var.app_environment, RunType = "live" }
    }
  }

  metric_query {
    id          = "rate"
    expression  = "IF((ingested + failures) < 10, 0, failures / (ingested + failures))"
    label       = "Parse failure rate (suppressed below 10 samples)"
    return_data = true
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  # TODO(phase-3): convert composite to per-adapter via
  # for_each = toset(file("${path.module}/adapter_names.txt"))
  # after CRAWL-01/02 auto-discovery lands; use metric_query AdapterName dimension.
}
```

Note: the expression uses `0` (not NaN) as the below-sample fallback because NaN + `GreaterThanThreshold` triggers the "missing data" path which `treat_missing_data=notBreaching` handles correctly — but CloudWatch docs show `0` is the canonical, portable pattern and compares cleanly.

### Frontend init + ErrorBoundary (OBS-05)

```typescript
// frontend/src/lib/sentry.ts
import * as Sentry from '@sentry/react';

const AUTH_PATHS = ['/login', '/register', '/oauth-callback', '/reset-password', '/2fa'];

export function initSentry(): void {
  if (import.meta.env.MODE === 'development') return;
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE, // "production" | "staging"
    release: import.meta.env.VITE_SENTRY_RELEASE,
    sendDefaultPii: false,
    tracesSampleRate: 0.05,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 1.0,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        maskAllText: true,
        maskAllInputs: true,
        blockAllMedia: true,
        beforeErrorSampling: () => {
          const path = window.location.pathname;
          return !AUTH_PATHS.some((p) => path.startsWith(p));
        },
      }),
    ],
  });
}
```

ErrorBoundary: a single 3-line addition in `componentDidCatch` (D-35):
```typescript
import * as Sentry from '@sentry/react';
// ...
override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  console.error('ErrorBoundary caught an error:', error, errorInfo);
  Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
}
```

AuthContext: set user on load, clear on logout (D-40):
```typescript
useEffect(() => {
  Sentry.setUser(user ? { id: String(user.id) } : null);
}, [user]);
```

### OBS-04 audit shape

Regression test fixture (auto-applied or per-test):

```python
# backend/tests/test_log_propagation.py
import logging
import pytest

@pytest.fixture
def assert_request_context(caplog):
    """After the test, assert every captured log record has non-default
    request_id and user_id attrs."""
    yield
    for rec in caplog.records:
        assert getattr(rec, "request_id", "-") != "-", (
            f"log record '{rec.getMessage()}' missing request_id "
            f"(logger={rec.name}, filter not applied)"
        )
        assert getattr(rec, "user_id", "-") != "-", (
            f"log record '{rec.getMessage()}' missing user_id (logger={rec.name})"
        )

def test_endpoint_logs_have_context(client, test_user, assert_request_context, caplog):
    caplog.set_level(logging.DEBUG)
    client.get("/api/users/me", headers={"Authorization": f"Bearer {test_user.token}"})
    # fixture asserts on teardown
```

Background-task helper `with_bg_context(task_name, job_id)`:

```python
# backend/app/core/log_context.py (extend)
from contextlib import contextmanager

@contextmanager
def bg_log_context(task_name: str, job_id: str | None = None):
    rid_token = request_id_var.set(f"bg:{task_name}:{job_id or '-'}")
    uid_token = user_id_var.set("bg")
    try:
        yield
    finally:
        request_id_var.reset(rid_token)
        user_id_var.reset(uid_token)
```

---

## 2. Library API Details

### Sentry Python SDK 2.x

**Version:** Latest `2.58.0` (2026-04 per PyPI index). Pin `>=2.0,<3` per D-14. Python 3.6+ supported (we run 3.13 — compatible).

#### init() signature — relevant kwargs

All confirmed via `docs.sentry.io/platforms/python/configuration/options/`:

| kwarg | Type | Phase 2 value | Notes |
|-------|------|---------------|-------|
| `dsn` | str | `os.environ["SENTRY_DSN"]` | Empty/None disables. |
| `environment` | str | `settings.APP_ENVIRONMENT` (staging / production) | D-08: single project, tag differentiates. |
| `release` | str | `os.environ["SENTRY_RELEASE"]` (commit sha) | D-02. |
| `server_name` | str | `apprunner-backend`, `ecs-crawler`, `cli-crawler` | D-11. Sentry groups events by server. |
| `send_default_pii` | bool | `False` | REQUIREMENTS-locked + D-03. |
| `traces_sampler` | `Callable[[dict], float]` | See helper above | D-06: 0 for health, else 0.05. |
| `ignore_errors` | `list[type | str]` | Class-name strings (see footgun) | D-07. |
| `integrations` | list | Starlette + FastApi + Sqlalchemy + Logging | See below. |
| `before_send` | `Callable[[event, hint], event \| None]` | Attach request_id/user_id from ContextVars | D-09. |
| `include_local_variables` | bool | leave default (True) | Renamed from `with_locals` in 2.0. |
| `max_request_body_size` | str | leave default (`"medium"`) | Renamed from `request_bodies` in 2.0. |

**Sampling context keys** (for `traces_sampler`):
- `transaction_context: {"name": str, "op": str}` — the route/path for FastApiIntegration with `transaction_style="endpoint"` resolves to the endpoint function name; with `"url"` (default) it's the URL template. **CONTEXT.md D-06 says "filter /health /ready /openapi.json" — confirm filter matches the chosen transaction_style.** Easiest: use `"endpoint"` (matches our existing endpoint naming) and sample on substring match.
- `parent_sampled: bool | None`
- Other `start_span` kwargs may appear; rely only on `transaction_context.name`.

**ignore_errors footgun (2.x):** Sentry docs describe "a list of exception class names" — this implies string class paths. In practice, the code accepts both exception class references *and* strings, but only strings are documented as the supported format in 2.x. **Recommendation:** Use strings. This also avoids Python import order issues (e.g., `slowapi` may not be importable at config time in tests).

```python
ignore_errors=[
    "fastapi.exceptions.HTTPException",
    "starlette.exceptions.HTTPException",
    "slowapi.errors.RateLimitExceeded",
]
```

**StarletteIntegration + FastApiIntegration — BOTH required.** Official docs: *"Because FastAPI is based on the Starlette framework, both integrations... must be instantiated."* Omitting StarletteIntegration silently loses middleware-layer exception capture (including the `general_exception_handler` path).

**SqlalchemyIntegration** — pass-through (no args needed). Hooks ORM events to attach query breadcrumbs to error events.

**LoggingIntegration** — `event_level=logging.ERROR` (default) captures `logger.error()` and `logger.exception()` as Sentry events. `level=logging.INFO` (default) captures INFO+ as breadcrumbs. This is what D-04 locks. To suppress a noisy logger later (deferred per CONTEXT.md): `from sentry_sdk.integrations.logging import ignore_logger; ignore_logger("some.module")`.

**Breaking changes 1.x → 2.x relevant to us** (from `docs.sentry.io/platforms/python/migration/1.x-to-2.x`):
- `with_locals` → `include_local_variables` (we don't set either — safe)
- `request_bodies` → `max_request_body_size` (we don't set — safe)
- `profiles_sample_rate` / `profiler_mode` no longer in `_experiments` (we don't enable profiling — safe)
- `configure_scope()` / `push_scope()` deprecated → use `new_scope()` / `isolation_scope()` (we use `before_send` instead — safe)
- `last_event_id()` removed and re-added in 2.2.0 — we don't call it
- Python 3.6+ only (we're on 3.13 — safe)
- `before_emit_metric` callback signature changed — we don't emit Sentry metrics (we use CloudWatch EMF)

**Test-time suppression:** D-13 pattern — `init_sentry()` checks `os.environ.get("TESTING") == "true"` and bails. This mirrors `backend/tests/conftest.py:15` which already sets `os.environ["TESTING"] = "true"`.

**In-memory transport for assertions:** `sentry_sdk.transport.Transport` subclass that captures envelopes in a list. Canonical pattern:

```python
from sentry_sdk.transport import Transport

class CapturingTransport(Transport):
    def __init__(self, options=None):
        super().__init__(options)
        self.envelopes = []
    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)

# In test:
import sentry_sdk
sentry_sdk.init(dsn="http://key@host/1", transport=CapturingTransport)
# trigger error...
# inspect sentry_sdk.Hub.current.client.transport.envelopes
```

Note the 2.x transport API uses `capture_envelope` (not `capture_event` — that was deprecated in 2.0).

**Docs:**
- https://docs.sentry.io/platforms/python/integrations/fastapi/
- https://docs.sentry.io/platforms/python/integrations/sqlalchemy/
- https://docs.sentry.io/platforms/python/integrations/logging/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/configuration/sampling/
- https://docs.sentry.io/platforms/python/migration/1.x-to-2.x

### @sentry/react 10.x + @sentry/vite-plugin

**Versions:** `@sentry/react` 10.49.0 (2026-04-16). `@sentry/vite-plugin` 5.2.0 (2026-04-08) — 4.x still maintained. Pin `^10.0.0` per D-43. Node 20+ + React 19 + Vite 6+ all supported.

#### `Sentry.init()` shape (v10)

Confirmed kwargs for Phase 2:
- `dsn: string` — from `import.meta.env.VITE_SENTRY_DSN`
- `environment: string` — `import.meta.env.MODE` resolves to "staging" or "production" when built with `vite build --mode=staging` (our existing pattern)
- `release: string` — inject `VITE_SENTRY_RELEASE` via GitHub Actions; auto-linked with sourcemaps
- `sendDefaultPii: false` (v10.4.0+: when false, IP address NOT collected either — verified in v9→v10 migration notes)
- `tracesSampleRate: 0.05` — D-38
- `replaysSessionSampleRate: 0` — D-32 (no ambient replay)
- `replaysOnErrorSampleRate: 1.0` — D-32 (100% when an error fires)
- `integrations: [...]` — `browserTracingIntegration()`, `replayIntegration({...})`

#### `replayIntegration()` — relevant args (v10)

From `docs.sentry.io/platforms/javascript/guides/react/session-replay/configuration/`:
- `maskAllText: true` (default) — D-36 ✓
- `maskAllInputs: true` — D-36 ✓
- `blockAllMedia: true` (default) — ✓
- `beforeErrorSampling: (event) => boolean` — **return false to skip replay capture for this error**. Called in buffer mode (i.e., with `replaysOnErrorSampleRate > 0`). Exact signature `(event: SentryEvent) => boolean`. D-37 ✓
- `mask: string[]` — CSS selectors to mask
- `block: string[]` — CSS selectors to completely drop from replay
- `ignore: string[]` — CSS selectors to ignore for interaction recording

**Auth-route gate (D-37) using `beforeErrorSampling`:**
```typescript
beforeErrorSampling: () => {
  const p = window.location.pathname;
  return !['/login', '/register', '/oauth-callback', '/reset-password', '/2fa']
    .some((route) => p.startsWith(route));
}
```

Note: `beforeErrorSampling` decides whether to attach a replay to the error — the error itself still reports. This matches D-37's intent.

#### v9 → v10 breaking changes relevant to us

From `docs.sentry.io/platforms/javascript/migration/v9-to-v10/`:
- `enableLogs` / `beforeSendLog` moved out of `_experiments` to top-level `init()` — we don't use them
- `BaseClient` → `Client`, `hasTracingEnabled()` → `hasSpansEnabled()` — internal, we don't call
- IP-address inference now *strictly* gated on `sendDefaultPii` (was previously partial) — safe, we explicitly set false
- FID web vital removed in favor of INP — we don't reference FID
- `replayIntegration` + `browserTracingIntegration` API unchanged between v9 and v10 — safe

The 3-line `componentDidCatch` addition (D-35):
```typescript
import * as Sentry from '@sentry/react';
override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  console.error('ErrorBoundary caught an error:', error, errorInfo);
  Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
}
```
`extra` is the standard "attached context" field in v10 (same API as v9/v8). Passing `errorInfo` directly via `extra` serializes cleanly because `componentStack` is a string.

#### @sentry/vite-plugin — CI-only gate

**Package:** `@sentry/vite-plugin` 4.x or 5.x. Current is 5.2.0; 4.x still maintained. D-34 doesn't specify major — pick 4.x for minimum surface, or track 5.x for Dependabot alignment.

**CI-only detection pattern** (the key technical question from the objective):

```typescript
// frontend/vite.config.ts
import { sentryVitePlugin } from '@sentry/vite-plugin';

const isCI = !!process.env.CI && !!process.env.SENTRY_AUTH_TOKEN;

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(isCI ? [sentryVitePlugin({
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
      release: { name: process.env.SENTRY_RELEASE },
      sourcemaps: { filesToDeleteAfterUpload: ['./dist/**/*.map'] },
    })] : []),
  ],
  build: { sourcemap: 'hidden' }, // required for sourcemap upload
});
```

**Rationale for `CI` env check:** GitHub Actions sets `CI=true` automatically (along with every major CI provider — CircleCI, GitLab, Travis, Jenkins). Gating on `SENTRY_AUTH_TOKEN` being non-empty is also reasonable — the plugin itself logs a warning if token is missing, but fails the build on some versions. The belt-and-suspenders "both must be set" gate is the least brittle.

**Why `build.sourcemap: 'hidden'` matters:** without this, Vite doesn't emit `.map` files at all. `'hidden'` emits maps but doesn't include `//# sourceMappingURL=...` comments in the bundle — the plugin uploads them to Sentry (where stack traces resolve) without exposing them to end users.

**Docs:**
- https://docs.sentry.io/platforms/javascript/guides/react/
- https://docs.sentry.io/platforms/javascript/guides/react/session-replay/configuration/
- https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
- https://docs.sentry.io/platforms/javascript/migration/v9-to-v10/
- https://www.npmjs.com/package/@sentry/react
- https://www.npmjs.com/package/@sentry/vite-plugin

### aws-embedded-metrics (Python)

**Version:** 3.5.0 (recent). Pin `>=3.0,<4` to ride 3.x for the phase. Active maintenance (release 2025-11).

#### Core API shape

Preferred pattern for our use (synchronous, one-shot emission per adapter run): **direct `create_metrics_logger()`** — NOT the `@metric_scope` decorator, because the decorator is designed for handler-style invocation (Lambda). For our case, `run_crawler` is a long-running function that emits once at the end.

```python
from aws_embedded_metrics.logger.metrics_logger_factory import create_metrics_logger

metrics = create_metrics_logger()
metrics.set_namespace("CarModPicker/Crawlers")
metrics.set_dimensions({"AdapterName": name, "Environment": env, "RunType": run_type})
metrics.put_metric("Ingested", ingested, "Count")
metrics.put_metric("ParseFailures", parse_failures, "Count")
metrics.put_metric("ElapsedSeconds", elapsed_seconds, "Seconds")
await metrics.flush()  # ← flush is async
```

**Async flush footgun:** `flush()` returns a coroutine. In async contexts (like App Runner where we're already in an event loop), just `await` it. In synchronous contexts (crawler runner is synchronous — it's a plain function called from ECS entry point, not an ASGI handler), wrap with `asyncio.run(metrics.flush())` or use `asyncio.get_event_loop().run_until_complete(...)`. **This is a real pitfall — the library is async-first despite being "just logging."**

Alternative: `@metric_scope` decorator auto-flushes on function exit:
```python
from aws_embedded_metrics import metric_scope

@metric_scope
def _emit(metrics, *, adapter_name, run_type, ingested, parse_failures, elapsed_seconds):
    metrics.set_namespace("CarModPicker/Crawlers")
    metrics.set_dimensions({"AdapterName": adapter_name, "Environment": ..., "RunType": run_type})
    metrics.put_metric("Ingested", ingested, "Count")
    # ... (no explicit flush)
```

**Recommendation:** Use `@metric_scope` — auto-flush is worth the magic, and it works for both sync and async callers. The decorator injects `metrics` as the first arg.

#### Sink routing (the critical footgun)

Environment detection order: `LambdaEnvironment` → `EC2Environment` → `DefaultEnvironment`.

- In Lambda: auto-detected, writes EMF JSON to stdout (Lambda picks it up via CloudWatch Logs automatic integration).
- In EC2: writes to TCP agent sink (expects the CloudWatch Agent on `localhost:25888`).
- On **ECS Fargate + App Runner: library falls through to `DefaultEnvironment` which ALSO uses the agent sink** — there is no auto-ECS detection.

**Solution (confirmed via issue #13 discussion and the docs):** Set `AWS_EMF_ENVIRONMENT=Local` in the task definition. This forces `LocalEnvironment` which uses the **stdout sink**. The awslogs driver on ECS Fargate and the App Runner log router pick up EMF-formatted stdout lines and write them to CloudWatch Logs, which then auto-extracts metrics.

**All relevant `AWS_EMF_*` env vars:**
| Var | Purpose | Phase 2 value |
|-----|---------|---------------|
| `AWS_EMF_ENVIRONMENT` | Force environment + sink | `Local` (forces stdout sink on ECS + App Runner) |
| `AWS_EMF_NAMESPACE` | Default namespace | *(leave unset; we call set_namespace explicitly)* |
| `AWS_EMF_SERVICE_NAME` | Auto-tags | *(leave unset)* |
| `AWS_EMF_SERVICE_TYPE` | Auto-tags | *(leave unset)* |
| `AWS_EMF_LOG_GROUP_NAME` | For agent sink only | *(not used)* |
| `AWS_EMF_LOG_STREAM_NAME` | For agent sink only | *(not used)* |
| `AWS_EMF_DISABLE_METRIC_EXTRACTION` | Disables `_aws` envelope emission (still logs property fields) | *(leave default `false`)* |

**Known bug — issue #109 — last-line dropped.** When an EMF line is the *final* line in a log stream, `awslogs` sometimes drops it. Mitigation: the existing `logger.log(summary_level, "Adapter X done...")` summary line at `runner.py:608` is a NON-EMF log that naturally fires AFTER the EMF emission. This is already our pattern and serves as the "follow-up non-EMF line" that issue #109's workaround recommends. **Emit EMF BEFORE the summary log** (not after), so the summary acts as the awslogs flush trigger.

#### Stdlib logging vs stdout

`LocalEnvironment` writes EMF JSON to `sys.stdout` directly (not through stdlib logging). This means:
- EMF lines do NOT go through `python-json-logger` — they appear as raw JSON on stdout.
- That's fine for CloudWatch Logs extraction (it just reads the line and matches the `_aws` envelope).
- But it also means EMF lines don't get our `request_id` / `user_id` context filter applied. **This is expected and correct** — EMF dimensions are the "context" for CloudWatch metrics, not log-line metadata.
- Our existing JSON-formatted application logs continue to flow through stdlib logging and get the filter.
- CloudWatch Logs receives both — they're separate log events in the same stream.

#### Test suppression

Environment-gate in the emission helper (check `TESTING == "true"` and `APP_ENVIRONMENT` not in {staging, production}). This beats any `AWS_EMF_DISABLE_METRIC_EXTRACTION` magic because it prevents the library from even being called.

For tests that *want* to assert emission shape: use `caplog` + `capsys` (the library writes to stdout, so `capsys.readouterr().out` contains the JSON). Parse and assert on the `_aws` envelope structure.

**Docs:**
- https://github.com/awslabs/aws-embedded-metrics-python
- https://github.com/awslabs/aws-embedded-metrics-python/blob/master/README.md
- https://github.com/awslabs/aws-embedded-metrics-python/issues/13 (ECS auto-detection gap)
- https://github.com/awslabs/aws-embedded-metrics-python/issues/109 (last-line drop bug)
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html

### CloudWatch EMF envelope + metric-math alarm

#### Exact `_aws` envelope shape

```json
{
  "_aws": {
    "Timestamp": 1745328000000,
    "CloudWatchMetrics": [
      {
        "Namespace": "CarModPicker/Crawlers",
        "Dimensions": [["AdapterName", "Environment", "RunType"]],
        "Metrics": [
          {"Name": "Ingested", "Unit": "Count"},
          {"Name": "ParseFailures", "Unit": "Count"},
          {"Name": "ElapsedSeconds", "Unit": "Seconds"}
        ]
      }
    ]
  },
  "AdapterName": "summit_racing",
  "Environment": "staging",
  "RunType": "live",
  "Ingested": 147,
  "ParseFailures": 3,
  "ElapsedSeconds": 42.7
}
```

**Invariants our tests must assert:**
- Top-level key `_aws` exists
- `_aws.Timestamp` is a positive integer (ms since epoch)
- `_aws.CloudWatchMetrics[0].Namespace == "CarModPicker/Crawlers"`
- Dimension set matches `["AdapterName", "Environment", "RunType"]`
- Metric names match `{"Ingested", "ParseFailures", "ElapsedSeconds"}`
- Each dimension and metric name exists as a top-level JSON key
- Dimension values are strings; metric values are numbers

#### Dimension cardinality

- 114 adapters × 2 envs × 2 RunTypes = 456 time series total
- CloudWatch free tier: 10 custom metrics free, $0.30/metric/mo above
- **Custom metric count = 456 × 3 metrics = 1,368 metrics** → ~$400/mo if billed as standard
- BUT custom metrics are only billed for metrics that receive data — idle adapters don't cost. At 10 active adapters × 3 metrics × 2 envs × 1 RunType = 60 metrics initially, well inside budget
- Dimension limit per EMF record: 30 dimensions (we use 3 — safe)
- Metrics per record: 100 (we use 3 — safe)
- EMF record size: 1 MB (we're well under — single line)

CONTEXT.md D-59 pegs ongoing cost at ~$0.10/mo for Phase 2. Verify against reality after staging bake (some metrics will not fire if an adapter isn't scheduled).

#### CloudWatch auto-extraction

App Runner + ECS Fargate with awslogs driver: log lines matching the EMF envelope shape are automatically extracted into CloudWatch Metrics by CloudWatch Logs (no IAM config needed beyond standard `logs:PutLogEvents`). This is a feature of CloudWatch Logs itself, not a task-definition property.

**Verification step the planner should include:** after staging deploy, run one adapter, then use `aws logs filter-log-events` to confirm the EMF line appears in the log group, AND `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers` to confirm extraction worked.

#### Metric-math alarm semantics

- `metric_query { id = "m", metric {...} }` defines a data source
- `metric_query { id = "e", expression = "...", return_data = true }` defines a derived metric; **exactly one** `metric_query` must have `return_data = true` — that's the alarm's data stream
- Expressions reference other `metric_query.id`s by name
- `IF(condition, value_if_true, value_if_false)` — can return a numeric value or `NaN`
- `NaN` in the alarm's data stream triggers `treat_missing_data` behavior — for us, `notBreaching` = alarm stays OK
- **Using `0` (as in our proposed expression) is equivalent to NaN + notBreaching** because `0 > 0.5` is false. Either approach works; `0` is the more portable choice that compares cleanly to the threshold regardless of `treat_missing_data`

**Canonical AWS-blog expression for "ratio alarm with sample-count suppression":**
```
IF((m1 + m2) >= 10, m2 / (m1 + m2), 0)
```
This evaluates to `0` (below threshold) when there are <10 samples — alarm stays quiet.

#### Terraform `aws_cloudwatch_metric_alarm` landmines

1. **Do NOT set top-level `period` when using `metric_query[]`** — terraform-provider-aws issue #29398 causes apply failure. Set `period` only inside each `metric_query.metric {}` block.
2. **`datapoints_to_alarm` vs `evaluation_periods`** — both must be set when using "M of N" semantics. For our phase, we want "1 of 1" so both are `1`.
3. **`ok_actions` vs `alarm_actions`** — set both to the same SNS topic; "ok" fires when the alarm recovers (matches every existing alarm in `monitoring.tf`).
4. **`treat_missing_data` options:** `missing` (alarm state stays as-is), `ignore` (remove from evaluation), `breaching` (treat as alarm), `notBreaching` (treat as OK). For an idle-adapter-safe alarm: `notBreaching`.
5. **`comparison_operator`:** `GreaterThanThreshold` (we want rate > 0.5) — NOT `GreaterThanOrEqualToThreshold` (would fire on exactly 0.5).

**Docs:**
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Create-alarm-on-metric-math-expression.html
- https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/using-metric-math.html
- https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm
- https://github.com/hashicorp/terraform-provider-aws/issues/29398

---

## 3. Testing Approach

### Sentry backend (OBS-01)

**In-memory transport fixture** (`backend/tests/conftest.py`):

```python
import pytest
from sentry_sdk.transport import Transport

class _CapturingTransport(Transport):
    events: list = []
    def __init__(self, options=None):
        super().__init__(options)
        self.__class__.events = []
    def capture_envelope(self, envelope):
        self.__class__.events.append(envelope)
    # Required no-ops:
    def flush(self, timeout=None, callback=None): pass
    def kill(self): pass

@pytest.fixture
def sentry_events(monkeypatch):
    import sentry_sdk
    monkeypatch.setenv("TESTING", "")  # temporarily disable test-suppression
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("SENTRY_DSN", "http://key@localhost/1")
    # Re-init with capturing transport:
    sentry_sdk.init(
        dsn="http://key@localhost/1",
        transport=_CapturingTransport,
        before_send=lambda ev, h: ev,  # passthrough
    )
    yield _CapturingTransport.events
    sentry_sdk.get_client().close()
```

**Assertions to cover (D-49 + D-62 UAT):**
- Unhandled exception (trigger 500 via a test endpoint that raises `RuntimeError`) → event in `sentry_events`
- Event tags contain `request_id` (from header or auto-assigned UUID) and `user` has `id`
- Deliberate `HTTPException` / `RateLimitExceeded` → no event (ignore_errors filter works)
- `logger.error("...")` inside a crawler test → event with `adapter` tag
- Scope processor attaches `request_id` and `user_id` — assert by iterating `event.get("tags")` + `event.get("user")`

**Init-order regression test:** Assert that `init_sentry()` is called from `app.main` module scope (not inside `lifespan`) — D-12 says "before FastAPI instantiation." A unit test can `importlib.reload(app.main)` and inspect `sentry_sdk.Hub.current.client` to verify init fired.

### EMF (OBS-02)

Use `capsys` (library writes directly to stdout):

```python
import json

def test_emit_crawler_metrics_shape(capsys, monkeypatch):
    monkeypatch.setenv("TESTING", "")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("AWS_EMF_ENVIRONMENT", "Local")

    from app.core.cloudwatch_emf import emit_crawler_run_metrics
    emit_crawler_run_metrics(
        adapter_name="summit_racing", run_type="live",
        ingested=147, parse_failures=3, elapsed_seconds=42.7,
    )

    captured = capsys.readouterr().out.strip().splitlines()
    emf_lines = [line for line in captured if line.startswith("{") and "_aws" in line]
    assert len(emf_lines) == 1

    record = json.loads(emf_lines[0])
    assert record["_aws"]["CloudWatchMetrics"][0]["Namespace"] == "CarModPicker/Crawlers"
    dims = record["_aws"]["CloudWatchMetrics"][0]["Dimensions"][0]
    assert set(dims) == {"AdapterName", "Environment", "RunType"}
    assert record["AdapterName"] == "summit_racing"
    assert record["RunType"] == "live"
    assert record["Environment"] == "staging"
    assert record["Ingested"] == 147
    assert record["ParseFailures"] == 3
    assert record["ElapsedSeconds"] == 42.7
```

**Gate test:** assert emission is silent when `APP_ENVIRONMENT=development` or `TESTING=true`.

### Frontend Sentry (OBS-05)

Vitest with mocked `@sentry/react`:

```typescript
// frontend/src/lib/__tests__/sentry.test.ts
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('@sentry/react', () => ({
  init: vi.fn(),
  captureException: vi.fn(),
  setUser: vi.fn(),
  browserTracingIntegration: vi.fn(),
  replayIntegration: vi.fn((opts) => opts), // return opts so we can inspect
}));

import * as Sentry from '@sentry/react';
import { initSentry } from '../sentry';

describe('initSentry', () => {
  beforeEach(() => vi.clearAllMocks());

  it('no-ops in development', () => {
    vi.stubEnv('MODE', 'development');
    initSentry();
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('no-ops when DSN is missing', () => {
    vi.stubEnv('MODE', 'production');
    vi.stubEnv('VITE_SENTRY_DSN', '');
    initSentry();
    expect(Sentry.init).not.toHaveBeenCalled();
  });

  it('initializes with expected config in production', () => {
    vi.stubEnv('MODE', 'production');
    vi.stubEnv('VITE_SENTRY_DSN', 'https://x@y/1');
    initSentry();
    expect(Sentry.init).toHaveBeenCalledTimes(1);
    const cfg = (Sentry.init as any).mock.calls[0][0];
    expect(cfg.replaysSessionSampleRate).toBe(0);
    expect(cfg.replaysOnErrorSampleRate).toBe(1.0);
    expect(cfg.tracesSampleRate).toBe(0.05);
    expect(cfg.sendDefaultPii).toBe(false);
  });
});
```

**ErrorBoundary test:** render a child that throws; assert `Sentry.captureException` called with the error.

### OBS-04 log propagation

```python
# backend/tests/test_log_propagation.py
import logging
import pytest

def test_endpoint_log_records_have_request_context(client, test_user, caplog):
    caplog.set_level(logging.DEBUG)
    r = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {test_user.token}"},
    )
    assert r.status_code == 200
    assert len(caplog.records) > 0
    for rec in caplog.records:
        assert getattr(rec, "request_id", "-") != "-", f"missing request_id on '{rec.getMessage()}'"
        assert getattr(rec, "user_id", "-") != "-", f"missing user_id on '{rec.getMessage()}'"

def test_bg_context_sets_ids(caplog):
    from app.core.log_context import bg_log_context
    logger = logging.getLogger("app.test.bg")
    caplog.set_level(logging.DEBUG)
    with bg_log_context("crawler", "job-123"):
        logger.info("running bg task")
    rec = [r for r in caplog.records if "running bg task" in r.getMessage()][0]
    assert rec.request_id == "bg:crawler:job-123"
    assert rec.user_id == "bg"

def test_cli_context_sets_ids(caplog):
    from app.core.log_context import request_id_var, user_id_var
    caplog.set_level(logging.DEBUG)
    request_id_var.set("cli:12345")
    user_id_var.set("cli")
    logging.getLogger("app.test.cli").info("cli startup")
    rec = [r for r in caplog.records if "cli startup" in r.getMessage()][0]
    assert rec.request_id == "cli:12345"
    assert rec.user_id == "cli"
```

**SQLAlchemy propagation test (D-48):** enable SQL echo in a test, query against the test DB, assert the `sqlalchemy.engine` logger's records carry the request_id/user_id (confirms the root filter reaches third-party loggers).

Note: `caplog` attaches its own handler at the root logger level, which does NOT inherit the `RequestContextFilter` installed in `main.py`. The test must either (a) explicitly add `RequestContextFilter` to caplog's handler (`caplog.handler.addFilter(RequestContextFilter())` — see pytest docs on `caplog.filtering()` context manager), or (b) use a dedicated fixture that installs the filter. **Document this in the fixture** so future devs understand the caplog + filter interaction.

---

## 4. Validation Architecture

Each OBS-0X requirement maps to observation points, measurements, test approach, and guarded-against failure modes. These items are phrased as acceptance criteria for direct lift into task plans.

### OBS-01 — Sentry backend

| Observation point | Measurement | Test approach | Failure mode guarded |
|-------------------|-------------|---------------|---------------------|
| `sentry_sdk.init()` return (via `Hub.current.client`) after `main.py` imports | `sentry_sdk.get_client().dsn` is non-empty when env is staging/prod + SENTRY_DSN is set; `None` otherwise | Unit: monkeypatch env + reload `app.main`; assert on client state | Init fires in tests/local and pollutes prod Sentry project |
| Unhandled exception in test endpoint | Captured envelope in `_CapturingTransport.events` with `event["exception"]` present | Integration: FastAPI TestClient POST to a route that raises `RuntimeError` | 5xx path doesn't reach Sentry (e.g., `general_exception_handler` swallows exc before Sentry sees it) |
| `FastApiIntegration` + `StarletteIntegration` + `SqlalchemyIntegration` + `LoggingIntegration` all loaded | `sentry_sdk.get_client().integrations` dict contains all 4 by key | Unit: assert dict keys | Silent missing of one integration (common regression when refactoring the init helper) |
| `HTTPException` raised inside a route | NO envelope captured (ignore_errors filter works) | Integration: raise `HTTPException(400)` and `HTTPException(404)` in a test route; assert `_CapturingTransport.events` empty | ignore_errors type vs. string format mismatch in 2.x; intentional 4xxs flood Sentry |
| `logger.error("...")` inside a crawler adapter | Envelope captured with `tags.request_id` present (if in request scope) or `bg:...` prefix (if in bg scope) | Integration: call a test function wrapped in `bg_log_context("crawler", "1")`, log an error, assert envelope + tag value | LoggingIntegration not wired; bg-context not wired; tag not populated |
| `traces_sampler` called | `GET /health` + `GET /ready` produce transactions with `sample_rate=0.0`; `GET /api/users/me` with `0.05` | Integration with `traces_sampler` hooked to record decisions | Health-probe transactions burn the 0.05 budget; missed paths waste the entire quota |
| `sentry_sdk.get_client().options["server_name"]` | Equals `apprunner-backend` in main.py; `ecs-crawler` in ecs_runner.py | Unit per entry point | Events from different processes collide into one server group in Sentry UI |

### OBS-02 — CloudWatch EMF metrics

| Observation point | Measurement | Test approach | Failure mode guarded |
|-------------------|-------------|---------------|---------------------|
| `emit_crawler_run_metrics()` call at end of `run_crawler` | JSON line on stdout matching EMF schema: `_aws.CloudWatchMetrics[0].Namespace == "CarModPicker/Crawlers"` | Unit with `capsys`; parse JSON; assert schema | Namespace typo breaks OBS-03 alarm silently |
| Dimension set | `_aws.CloudWatchMetrics[0].Dimensions[0] == ["AdapterName", "Environment", "RunType"]` (order may vary; compare as set) | Unit | Dimension omission (forgetting RunType) collapses live + rescrape data together → OBS-03 alarm sees rescrape noise |
| Metric names + values | Top-level keys `Ingested`, `ParseFailures`, `ElapsedSeconds` present with values matching fn args | Unit | Metric name typo (e.g., "Ingest" vs "Ingested") causes silent metric loss |
| Environment gate | `APP_ENVIRONMENT=development` or `TESTING=true` → NO stdout emission | Unit with `capsys`; assert stdout empty | Dev runs pollute prod namespace (charges metric fees, skews alarm) |
| Production runtime env | ECS task definition contains `AWS_EMF_ENVIRONMENT=Local` | Terraform plan snapshot / manual UAT | Library falls back to agent sink on ECS; metrics never reach CloudWatch |
| Post-staging-deploy check | `aws cloudwatch list-metrics --namespace CarModPicker/Crawlers --dimensions Name=Environment,Value=staging` returns ≥1 metric within 5min of a test crawl | HUMAN-UAT (D-62 item 4) | CloudWatch Logs extraction rule broken (extremely rare but possible) |
| EMF line position | Emission happens BEFORE the `"Adapter X done"` summary log line, not after | Code review (task acceptance) | awslogs drops trailing EMF line (issue #109) |

### OBS-03 — Parse-failure alarm

| Observation point | Measurement | Test approach | Failure mode guarded |
|-------------------|-------------|---------------|---------------------|
| Terraform apply | `aws_cloudwatch_metric_alarm.crawler_parse_failure_composite` exists; `alarm_actions` contains `aws_sns_topic.alarms.arn`; description contains runbook anchor | Terraform plan snapshot / `aws cloudwatch describe-alarms` | Alarm created but not wired to SNS; operator never gets email |
| Alarm expression shape | `metric_query` with `return_data=true` has `expression == "IF((ingested+failures) < 10, 0, failures/(ingested+failures))"` | Terraform plan snapshot | Expression off-by-one causes premature alarm or permanent silence |
| Composite dimensions | Both `ingested` and `failures` `metric_query` blocks filter `dimensions = { Environment = ..., RunType = "live" }` | Terraform plan snapshot | Rescrape traffic (RunType=rescrape) bleeds into live-mode alarm; false positives on rescrape |
| Threshold and comparison | `threshold == 0.5`, `comparison_operator == "GreaterThanThreshold"` | Terraform plan snapshot | Alarm fires at exactly 0.5 (includes `>=` bug) or stays quiet because threshold is wrong |
| `treat_missing_data` | `notBreaching` | Terraform plan snapshot | Idle adapters with no data put alarm into ALARM permanently |
| Alarm fires in staging | Simulated parse-failure wave (limit-crawl against a broken adapter; or `aws cloudwatch put-metric-data` bulk-write) → alarm state transitions to ALARM → SNS email arrives; traffic stops → alarm recovers to OK → recovery email arrives | HUMAN-UAT (D-62 item 5) | Alarm exists but something in the chain (IAM, SNS subscription confirmation) fails silently |
| No top-level `period` | `period` attribute is NOT set on the `aws_cloudwatch_metric_alarm` resource directly | `terraform validate` / plan | terraform-provider-aws#29398 apply failure |

### OBS-04 — Propagation audit

| Observation point | Measurement | Test approach | Failure mode guarded |
|-------------------|-------------|---------------|---------------------|
| Every log record produced during a request | `record.request_id != "-"` AND `record.user_id != "-"` | pytest `caplog` iteration in a test that hits `GET /api/users/me` as an authenticated user | Future dev adds a handler that bypasses `RequestContextFilter` |
| Third-party logger propagation | SQL query log record during a request has `record.request_id` = the request's UUID | Enable `echo=True` on SQLAlchemy test engine; assert | A `logging.getLogger("sqlalchemy")` config change drops root propagation |
| Background task context | Log inside `with bg_log_context("crawler", "job-1"):` produces `record.request_id == "bg:crawler:job-1"` | Unit test using `caplog` + context manager | Background tasks log with default `-` ContextVar values → CloudWatch grep by request ID finds nothing |
| CLI context | Log inside `python -m app.crawlers` produces `record.request_id` prefixed with `cli:` | Integration (invoke CLI via subprocess + parse stdout) OR unit test that simulates CLI startup | CLI runs identified as `-` in logs; operator can't distinguish CLI vs request context |
| Post-deploy staging verification | Spot-check the CloudWatch log group for `/aws/apprunner/.../application` — all recent lines contain `request_id=<uuid>` or `request_id=bg:...` or `request_id=cli:...` | HUMAN-UAT (D-62 item 7) | The happy path is green but production log drift exposes a missed logger config |

### OBS-05 — Frontend Sentry

| Observation point | Measurement | Test approach | Failure mode guarded |
|-------------------|-------------|---------------|---------------------|
| `initSentry()` behavior | `Sentry.init` called exactly when `MODE !== "development"` AND `VITE_SENTRY_DSN` is non-empty; no-op otherwise | Vitest with mocked `@sentry/react`; stub `import.meta.env` | Dev builds send events to Sentry; or prod builds silently skip init |
| Init config invariants | Passed-config has `replaysSessionSampleRate=0`, `replaysOnErrorSampleRate=1.0`, `tracesSampleRate=0.05`, `sendDefaultPii=false` | Vitest: inspect `Sentry.init.mock.calls[0][0]` | Session Replay ambient recording burns Sentry free-tier quota |
| `beforeErrorSampling` pathname gate | Given `window.location.pathname = "/login/foo"`, `beforeErrorSampling(event)` returns `false`; given `/dashboard`, returns `true` | Vitest: extract `replayIntegration` opts and call the hook directly | Replays capture token-bearing URL fragments on auth pages |
| `ErrorBoundary.componentDidCatch` → Sentry | Rendering a component that throws triggers `Sentry.captureException(error, { extra: { componentStack: string } })` | Vitest `@testing-library/react`: render component that throws; assert mock was called with the error | ErrorBoundary catches error + shows fallback UI but doesn't report to Sentry (silent error = no production visibility) |
| `AuthContext` setUser hook | When user loads, `Sentry.setUser({id: String(user.id)})` fires; on logout, `Sentry.setUser(null)` fires | Vitest: render `AuthProvider` wrapper, dispatch login/logout, assert calls | Error events land in Sentry without user correlation; can't link frontend crash to affected user |
| CI sourcemap upload | In CI (`CI=true` + `SENTRY_AUTH_TOKEN` set), `@sentry/vite-plugin` runs during `npm run build`; locally, plugin is absent from plugin list | Integration: CI build log grep for "Sentry Vite plugin: uploaded" line | Sourcemaps never uploaded → Sentry shows minified stacks, useless for debugging |
| HUMAN-UAT | Staging frontend triggers an unhandled error → Sentry event arrives with resolved-source stack trace + attached Session Replay | D-62 item 6 | All of the above pieces wire up but something in the deploy pipeline is broken |

---

## 5. Landmines / Footguns (Explicit)

1. **`ignore_errors` format ambiguity in 2.x.** Docs say "class names" (suggests strings); some example code in the wild passes classes directly. Both work in practice but strings are safer. **If you use classes and a test fails**, convert to strings — don't spelunk.

2. **`StarletteIntegration` MUST be explicitly added** alongside `FastApiIntegration`. No auto-enable. Official FastAPI integration doc is explicit about this.

3. **sentry-sdk transport API renamed in 2.0** — `capture_event` → `capture_envelope`. Test fixtures for a `Transport` subclass must implement `capture_envelope` (and `flush` + `kill` as no-ops).

4. **`aws-embedded-metrics` does NOT auto-detect ECS Fargate.** Without `AWS_EMF_ENVIRONMENT=Local`, metrics silently route to an agent sink that doesn't exist on ECS Fargate. Your metrics never reach CloudWatch and no error is raised. Must set the env var in terraform (both `apprunner.tf` and `ecs.tf`).

5. **`aws-embedded-metrics` flush is async.** Use `@metric_scope` decorator so auto-flush handles the async-loop dance, or explicitly `asyncio.run(metrics.flush())` in synchronous contexts. Synchronous `metrics.flush()` without await is a no-op warning.

6. **aws-embedded-metrics last-EMF-line dropped bug (issue #109).** Emit EMF BEFORE your summary log line, not after. Our existing `logger.log(summary_level, ...)` at `runner.py:608` serves as the post-EMF flush trigger — DO NOT reorder it to come first.

7. **Terraform `aws_cloudwatch_metric_alarm` top-level `period` conflicts with `metric_query`** — bug terraform-provider-aws#29398. Period goes inside each `metric_query.metric {}` block, never at the resource top level.

8. **CloudWatch metric-math expression returning NaN vs 0.** Both suppress alarm when `treat_missing_data=notBreaching`, but `0` compares cleanly to `>0.5` threshold regardless of missing-data config. Prefer `0` in the IF-false branch.

9. **`datapoints_to_alarm` must be ≤ `evaluation_periods`**; Terraform will reject otherwise. For "1 of 1": both = 1.

10. **GreaterThanThreshold vs GreaterThanOrEqualToThreshold** — rate > 0.5 (strict) is what we want; `GreaterThanOrEqualToThreshold` with threshold 0.5 fires on rates exactly at 0.5 (boundary case).

11. **`@sentry/react` v10 `sendDefaultPii=false` strictly excludes IP address** (change from v9). If a downstream phase wants IP collection, it must flip this flag.

12. **`@sentry/vite-plugin` requires `build.sourcemap: 'hidden'`** in Vite config. Without it, no `.map` files are generated and the plugin has nothing to upload — build succeeds but stack traces stay minified in Sentry.

13. **CI detection via `process.env.CI` is cross-CI standard.** GitHub Actions / CircleCI / GitLab / Travis all set `CI=true`. Don't use `process.env.GITHUB_ACTIONS` — that works but ties the build to a single CI.

14. **`beforeErrorSampling` decides replay attach, NOT error reporting.** Auth-page errors still report to Sentry (correct behavior per D-37); only the replay gets dropped. This is what we want — naming is confusing.

15. **pytest `caplog` does NOT inherit root-logger filters** installed in `main.py`. The OBS-04 propagation test must either (a) explicitly add `RequestContextFilter` to `caplog.handler`, or (b) use `caplog.filtering(RequestContextFilter())` context manager. Forgetting this causes `record.request_id` AttributeError in the test despite the filter working fine in production.

16. **`sentry_sdk.init()` is process-global.** Calling it a second time (e.g., from a test that re-imports `app.main`) replaces the client and discards the previous one. Make sure test fixtures either fully tear down with `sentry_sdk.get_client().close()` or re-init per test.

17. **FastApiIntegration's `transaction_style="endpoint"` names transactions by Python function name** (e.g., `users.read_user_by_id`), while `"url"` (default) names by URL template. D-06's traces_sampler filters on path-like strings — choose one style and filter accordingly. Recommendation: `"endpoint"` gives cleaner Sentry UI groupings; filter on substring match for `"health"` / `"ready"` / `"openapi"` accordingly.

18. **Sentry free tier has hard quotas** — 5K errors/month, 10K performance transactions/month, 500 Session Replays/month. At 0.05 trace sample rate we should stay under transactions. Replay-on-error with a 5K error budget keeps us well under 500 replays. Set up a Sentry-internal spend cap as belt-and-suspenders.

---

## 6. Open Questions

1. **`/openapi.json` route path shape in traces_sampler.** With `transaction_style="endpoint"` the transaction name is the function name (something like `app.openapi` or an anonymous function). Filter needs to match both `"/openapi"` as a substring AND the function name — our implementation should filter on path OR function name. **Resolution:** write the `_traces_sampler` to check both `transaction_context["name"]` and (if available) any URL-like fields in `sampling_context`. Iterate once we see real samples in staging.

2. **aws-embedded-metrics + `@metric_scope` thread safety.** The library uses a thread-local `MetricsContext`. `run_crawlers()` uses `ThreadPoolExecutor` (Phase 3 change; Phase 2 we're pre-parallelization per `runner.py:_compute_adapter_workers`). If Phase 3 lands concurrent with Phase 2 and parallelizes before Phase 2's metrics land, verify thread safety. **Resolution:** D-17 says emission is at the end of `run_crawler` (per-adapter); the thread-local scope should be naturally isolated. Confirm in integration test.

3. **Crawler log group name for EMF extraction.** ECS Fargate crawler task writes to what log group? If not explicitly configured, ECS default is `/ecs/<task-family>` — but CloudWatch auto-extracts EMF from any log group. Should work without explicit config. **Resolution:** in HUMAN-UAT step 4, confirm extraction works from the actual log group.

4. **Which specific exception does `slowapi` raise for rate-limit?** D-07 names `RateLimitExceeded` but our codebase has a custom rate limiter in `backend/app/api/middleware/rate_limiter.py` — it may raise a different class. **Resolution:** before writing `ignore_errors`, grep the middleware for the raise statement. Likely `HTTPException(status_code=429)` — in which case it's already covered by the `HTTPException` entry and there's no separate class needed.

5. **Does `SqlalchemyIntegration` require a specific SQLAlchemy version?** We're on 2.0.41; docs generally say 1.4+ is supported. No version concern surfaced during research. **Resolution:** leave default, verify via test.

---

## 7. Documentation Links

### Sentry Python 2.x
- FastAPI integration: https://docs.sentry.io/platforms/python/integrations/fastapi/
- SQLAlchemy integration: https://docs.sentry.io/platforms/python/integrations/sqlalchemy/
- Logging integration: https://docs.sentry.io/platforms/python/integrations/logging/
- Configuration options: https://docs.sentry.io/platforms/python/configuration/options/
- Sampling: https://docs.sentry.io/platforms/python/configuration/sampling/
- Filtering: https://docs.sentry.io/platforms/python/configuration/filtering/
- 1.x → 2.x migration: https://docs.sentry.io/platforms/python/migration/1.x-to-2.x
- Transport API: https://docs.sentry.io/platforms/python/configuration/transports/
- PyPI: https://pypi.org/project/sentry-sdk/

### @sentry/react 10.x + vite-plugin
- React guide: https://docs.sentry.io/platforms/javascript/guides/react/
- Session Replay configuration: https://docs.sentry.io/platforms/javascript/guides/react/session-replay/configuration/
- Vite sourcemap uploading: https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
- v9 → v10 migration: https://docs.sentry.io/platforms/javascript/migration/v9-to-v10/
- npm @sentry/react: https://www.npmjs.com/package/@sentry/react
- npm @sentry/vite-plugin: https://www.npmjs.com/package/@sentry/vite-plugin

### AWS CloudWatch + EMF
- EMF specification: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html
- Embedding metrics overview: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format.html
- Metric math syntax: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/using-metric-math.html
- Create metric-math alarm: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Create-alarm-on-metric-math-expression.html
- Treat missing data: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html#alarms-and-missing-data
- aws-embedded-metrics Python: https://github.com/awslabs/aws-embedded-metrics-python
- EMF ECS stdout discussion: https://github.com/awslabs/aws-embedded-metrics-python/issues/13
- Last-line dropped bug: https://github.com/awslabs/aws-embedded-metrics-python/issues/109

### Terraform
- aws_cloudwatch_metric_alarm: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/cloudwatch_metric_alarm
- period+metric_query conflict bug: https://github.com/hashicorp/terraform-provider-aws/issues/29398

### Pytest testing
- Managing logging (caplog): https://docs.pytest.org/en/stable/how-to/logging.html
- caplog.filtering(): https://docs.pytest.org/en/stable/reference/reference.html#pytest.LogCaptureFixture.filtering

---

## Metadata

**Confidence breakdown:**
- Sentry Python 2.x API: HIGH — confirmed from official docs with explicit version-marked content
- @sentry/react 10.x API: HIGH — docs explicit; beforeErrorSampling signature confirmed
- @sentry/vite-plugin CI gating: MEDIUM-HIGH — no official "CI-only" doc but multiple blog posts + issues confirm the `process.env.CI` + `process.env.SENTRY_AUTH_TOKEN` pattern is standard
- aws-embedded-metrics library behavior: MEDIUM — maintained, docs incomplete for ECS Fargate case; `AWS_EMF_ENVIRONMENT=Local` behavior confirmed from issue discussion + AWS-observability-best-practices but not from official README
- CloudWatch EMF spec: HIGH — official AWS spec doc
- Terraform `aws_cloudwatch_metric_alarm` with metric_query: HIGH — registry docs + known bug #29398 confirms landmine
- Backend + frontend existing-code integration points: HIGH — read source directly

**Research date:** 2026-04-22
**Valid until:** ~2026-07-22 (3 months — Sentry SDKs move fast; aws-embedded-metrics moves slowly)

## RESEARCH COMPLETE
