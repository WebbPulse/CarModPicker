# Phase 2: Observability — Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 27 (13 backend, 8 frontend, 5 terraform, 1 docs)
**Analogs found:** 27 / 27 (every file has a concrete analog — this is a well-established codebase)

## File Classification

### Backend

| New/Modified | Path | Role | OBS | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| NEW | `backend/app/core/sentry.py` | prod helper (env-gated init) | OBS-01 | `backend/app/core/email.py` + `backend/app/core/log_context.py` | role-match (env-gated helper) |
| NEW | `backend/app/core/cloudwatch_emf.py` | prod helper (env-gated emitter) | OBS-02 | `backend/app/core/email.py::_send` + `aws-embedded-metrics` skeleton in 02-RESEARCH.md §1 L105-140 | role-match (env-gated helper); the library import/usage is net-new |
| MODIFY | `backend/app/core/log_context.py` | prod module (extend with bg_log_context) | OBS-04 | `backend/app/core/log_context.py` itself (file is 13 lines; extension is additive) | in-place |
| MODIFY | `backend/app/main.py` | prod entry point (call init_sentry before FastAPI()) | OBS-01 | `backend/app/main.py:L42-L47` (existing import block + L113 `FastAPI(...)` instantiation) | in-place |
| MODIFY | `backend/app/crawlers/__main__.py` | CLI entry (init Sentry + CLI log context) | OBS-01 + OBS-04 | `backend/app/crawlers/__main__.py` itself (currently 8 lines — trivial insertion before `main()` call) | in-place |
| MODIFY | `backend/app/crawlers/runner.py` | prod crawler (emit EMF at summary, track elapsed) | OBS-02 | `backend/app/crawlers/runner.py:L608-L620` (existing summary log block) | in-place |
| MODIFY | `backend/app/crawlers/ecs_runner.py` | ECS entry (init Sentry, pass RunType="live") | OBS-01 + OBS-02 | `backend/app/crawlers/ecs_runner.py:L34-L40` (existing logging.basicConfig + module setup) | in-place |
| MODIFY | `backend/app/crawlers/ecs_rescrape_runner.py` | ECS entry (init Sentry, pass RunType="rescrape") | OBS-01 + OBS-02 | `backend/app/crawlers/ecs_rescrape_runner.py:L24-L30` (existing logging.basicConfig + module setup) | in-place |
| MODIFY | `backend/app/core/config.py` | settings (add SENTRY_DSN, SENTRY_RELEASE, SENTRY_SERVICE_NAME) | OBS-01 | `backend/app/core/config.py:L151-L158` (EMAIL_ENABLED + EMAIL_FROM Pydantic Field pattern) | exact (same settings file, same Field shape) |
| MODIFY | `backend/requirements.txt` | deps (add sentry-sdk, aws-embedded-metrics) | OBS-01 + OBS-02 | `backend/requirements.txt:L49-L52` (boto3 + Pillow block) | in-place |
| NEW | `backend/tests/test_sentry_init.py` | test (init gating + scope processor + ignore_errors) | OBS-01 | `backend/tests/test_email.py:L22-L56` (monkeypatched settings + MagicMock pattern) + `backend/tests/middleware/test_error_handler.py` for HTTPException raise/assert | role-match (env-gated unit test via monkeypatch + mocked SDK) |
| NEW | `backend/tests/test_cloudwatch_emf.py` | test (EMF envelope shape, env gate) | OBS-02 | `backend/tests/test_email.py:L22-L56` (same monkeypatch + MagicMock pattern) | role-match |
| NEW | `backend/tests/test_log_propagation.py` | test (caplog audit fixture for OBS-04) | OBS-04 | `backend/tests/auth/test_characterization_login.py:L26-L60` (client fixture + DB user + request path) | role-match (test uses client fixture; caplog usage is net-new) |
| MODIFY | `backend/tests/conftest.py` | test fixtures (add sentry stub fixture, assert_request_context fixture) | OBS-01 + OBS-04 | `backend/tests/conftest.py:L420-L469` (`mock_s3` monkeypatch fixture pattern) | in-place |

### Frontend

| New/Modified | Path | Role | OBS | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| NEW | `frontend/src/lib/sentry.ts` | prod helper (env-gated init) | OBS-05 | `frontend/src/test/setup.ts` (env-gated setup) + backend `app/core/sentry.py` shape | role-match (no existing lib/ dir — net-new parallel of backend helper) |
| MODIFY | `frontend/src/main.tsx` | prod entry (call initSentry before createRoot) | OBS-05 | `frontend/src/main.tsx:L1-L17` (existing imports + createRoot) | in-place |
| MODIFY | `frontend/src/components/common/ErrorBoundary.tsx` | prod component (add captureException in componentDidCatch) | OBS-05 | `frontend/src/components/common/ErrorBoundary.tsx:L23-L25` (existing componentDidCatch body) | in-place (3-line D-35 addition) |
| MODIFY | `frontend/src/contexts/AuthContext.tsx` | prod context (setUser on login/logout) | OBS-05 | `frontend/src/contexts/AuthContext.tsx:L51-L53` (existing useEffect) + L55-L58/L60-L73 (login/logout handlers) | in-place |
| NEW | `frontend/src/lib/sentry.test.ts` | test (init gating, mocked Sentry SDK) | OBS-05 | `frontend/src/utils/carUtils.test.ts:L1-L22` (vitest describe/it shape) + `frontend/src/test/setup.ts:L13-L15` (`vi.mock('../services/Api', ...)` pattern) | role-match (vitest + vi.mock analog for `@sentry/react`) |
| NEW | `frontend/src/components/common/ErrorBoundary.test.tsx` | test (@testing-library/react renders throwing child) | OBS-05 | `frontend/src/utils/carUtils.test.ts` structure + `package.json:@testing-library/react@^16` already installed | role-match (no existing component tests; new file uses already-available deps) |
| MODIFY | `frontend/vite.config.ts` | build config (add @sentry/vite-plugin) | OBS-05 | `frontend/vite.config.ts:L1-L7` (existing plugins array) | in-place |
| MODIFY | `frontend/package.json` | deps (add @sentry/react@^10, @sentry/vite-plugin) | OBS-05 | `frontend/package.json:L26-L38` (existing dependencies block) | in-place |

### Terraform

| New/Modified | Path | Role | OBS | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| MODIFY | `terraform/monitoring.tf` | IaC (composite alarm + var marker) | OBS-03 | `terraform/monitoring.tf:L56-L73` (existing `apprunner_5xx` alarm) — closest existing `aws_cloudwatch_metric_alarm` | exact (same resource type, same module) |
| MODIFY | `terraform/secretsmanager.tf` | IaC (SENTRY_DSN secret + version) | OBS-01 + OBS-05 | `terraform/secretsmanager.tf:L13-L22` (`secret_key` pattern: secret + version with var-backed value) | exact (same resource pattern) |
| MODIFY | `terraform/apprunner.tf` | IaC (inject SENTRY_DSN + SENTRY_RELEASE + APP_ENVIRONMENT-tied vars) | OBS-01 | `terraform/apprunner.tf:L218-L257` (existing `runtime_environment_variables` + `runtime_environment_secrets` maps) + L23-L38 (access role secrets IAM) + L59-L75 (instance role secrets IAM) | exact (append to existing maps + existing IAM Resource arrays) |
| MODIFY | `terraform/ecs.tf` | IaC (inject SENTRY_DSN to secrets[], SENTRY_SERVICE_NAME=ecs-crawler to environment[]) | OBS-01 + OBS-02 | `terraform/ecs.tf:L200-L229` (existing `environment = [...]` + `secrets = [...]`) + L75-L89 (exec role secrets IAM grant) | exact |
| MODIFY | `terraform/variables.tf` | IaC (add `disabled_parse_alarms` list variable) | OBS-03 | `terraform/variables.tf:L44-L55` (`secret_key` + `email_from` variable definitions) | exact (standard variable block) |
| MODIFY | `terraform/README.md` | docs (Bootstrap: Sentry section) | OBS-01 + OBS-05 | `terraform/README.md:L1-L40` (existing file map + architecture section) | in-place (append section) |

### Docs

| New/Modified | Path | Role | OBS | Closest Analog | Match Quality |
|---|---|---|---|---|---|
| MODIFY | `CLAUDE.md` | docs (one-line pointer to sentry.py) | OBS-01 | `CLAUDE.md` "Architecture / Backend" section (existing) | in-place |
| MODIFY | `.planning/codebase/CONCERNS.md` | docs (Crawler Drift Runbook section) | OBS-03 | Existing sections in same file (convention: anchor-linked sections) | in-place (append section with `#crawler-drift-runbook` anchor for D-27 alarm description) |
| NEW | `.planning/phases/02-observability/02-HUMAN-UAT.md` | docs (UAT checklist per D-62) | All | `.planning/phases/01-safety-nets-ci-hardening/01-HUMAN-UAT.md` (Phase 1 sibling) | exact (sibling file, same directory structure) |

---

## Pattern Assignments

### `backend/app/core/sentry.py` (NEW — env-gated helper, OBS-01)

**Primary analog (env-gate pattern):** `backend/app/core/email.py:L36-L41`

**Imports pattern to mirror (adapted from `email.py:L1-L10` and `log_context.py:L1-L5`):**
```python
import os
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration  # ← RESEARCH §1 Hot-Spot 2: required even with FastApi
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.core.config import settings
from app.core.log_context import request_id_var, user_id_var
```

**Env-gate pattern** (copy shape from `email.py:L36-L41`):
```python
# email.py — the canonical early-return-when-disabled pattern:
def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send a single transactional email via SES. Returns True on success."""
    if not settings.EMAIL_ENABLED:
        logger.debug(f"Email disabled — skipping send to {to_email} (subject: {subject!r})")
        return False
    try:
        client = boto3.client("sesv2", region_name=settings.AWS_REGION)
```

**Divergence:** `init_sentry()` early-returns on three conditions instead of one:
1. `os.environ.get("TESTING") == "true"` (D-13; matches `conftest.py:L15` guard)
2. `settings.APP_ENVIRONMENT.lower() not in {"staging", "production"}` (D-01; similar to `config.py:L142-L144` `is_production` property)
3. `SENTRY_DSN` empty string (D-01)

Same philosophy as `EMAIL_ENABLED` gate — no-op when not configured rather than crashing.

**ContextVar scope processor** (reads from `log_context.py:L4-L5`):
```python
# log_context.py — the existing ContextVars Sentry's before_send will read:
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
```

Full helper body already laid out in 02-RESEARCH.md §1 lines 41-100. The planner should lift that skeleton verbatim, with `server_name` as a required keyword arg (D-11: `apprunner-backend` vs `ecs-crawler`).

**Divergence notes vs email.py analog:**
- `email.py` gates by `settings.EMAIL_ENABLED` boolean; `sentry.py` gates by three conditions (TESTING env + APP_ENVIRONMENT enum + DSN presence).
- `email.py` returns `bool`; `init_sentry()` returns `None` (it mutates global SDK state).
- Both are idempotent: `_send()` called twice sends twice; `init_sentry()` called twice is safe because `sentry_sdk.init()` replaces the hub (D-05 "idempotent; safe to call multiple times").

---

### `backend/app/core/cloudwatch_emf.py` (NEW — env-gated emitter, OBS-02)

**Primary analog:** `backend/app/core/email.py::_send` (same env-gate shape) + 02-RESEARCH.md §1 L105-140 (library-specific skeleton).

**Pattern to mirror** (from `email.py:L36-L57`):
```python
def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send a single transactional email via SES. Returns True on success."""
    if not settings.EMAIL_ENABLED:
        logger.debug(f"Email disabled — skipping send to {to_email} (subject: {subject!r})")
        return False
    try:
        client = boto3.client("sesv2", region_name=settings.AWS_REGION)
        client.send_email(...)
        return True
    except (BotoCoreError, ClientError) as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        return False
```

**Divergence:**
- Gate is `TESTING=true` OR `APP_ENVIRONMENT not in {staging, production}` (D-20) — same two-condition combo as Sentry D-01.
- No try/except around `metrics.flush()` in the research skeleton — the planner should wrap it so a transient library failure does not crash `run_crawler`. Analog: `email.py:L55-L57` catches `BotoCoreError`/`ClientError` and logs without re-raising.
- Uses `aws-embedded-metrics` library (new dependency); `email.py` uses `boto3` (already installed).
- **Critical footgun** from 02-RESEARCH.md Hot-Spot 3: `AWS_EMF_ENVIRONMENT=Local` must be set at the terraform level (ecs.tf + apprunner.tf environment blocks) to force stdout sink on ECS Fargate. If this env var is missing, the library attempts to reach a CloudWatch agent that isn't there and silently drops metrics.

---

### `backend/app/core/log_context.py` (MODIFY — extend with bg_log_context, OBS-04)

**In-place analog (current file, 13 lines):**
```python
import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()  # type: ignore[attr-defined]
        record.user_id = user_id_var.get()  # type: ignore[attr-defined]
        return True
```

**Addition** (from 02-RESEARCH.md §1 L284-L297):
```python
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

**Secondary analog for the token reset pattern:** `backend/app/api/middleware/request_context.py:L10-L18` — the existing HTTP middleware uses the exact same `var.set() → try/finally → var.reset(token)` shape:
```python
async def request_context_middleware(request: Request, call_next: ...) -> Response:
    req_id = request.headers.get("X-Request-ID") or str(uuid7())
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_var.reset(token)
```

**Divergence:** `bg_log_context` is sync (uses `@contextmanager`, not async middleware). Wraps both `request_id_var` and `user_id_var`, whereas the HTTP middleware only wraps `request_id_var` (user_id is set later by the auth dependency).

---

### `backend/app/main.py` (MODIFY — call init_sentry before FastAPI(), OBS-01)

**Insertion point — current state (L42-L47 existing imports + L113 FastAPI):**
```python
# L40-L47 (current)
from .core.log_context import RequestContextFilter
from .core.logging import LOG_FORMAT, make_formatter
from .core.worker_identity import WORKER_INSTANCE_ID
from .db.session import SessionLocal, check_db_ready
from .services import job_service

# L46-L66 (current): existing logging config block
logging.basicConfig(...)
# ...
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _log = logging.getLogger(_name)
    for _h in _log.handlers:
        _h.setFormatter(_formatter)
        _h.addFilter(_ctx_filter)

logger = logging.getLogger(__name__)

# L113 (current): FastAPI instantiation
app = FastAPI(
    title=settings.PROJECT_NAME,
    ...
)
```

**Diff per D-12** ("first thing in app/main.py after imports, before FastAPI() instantiation"):
- Add import: `from .core.sentry import init_sentry`
- Add call between L66 `logger = ...` and L113 `app = FastAPI(...)`: `init_sentry(server_name="apprunner-backend")`

**No other changes** — the existing `RequestContextFilter` wiring at L50-L64 (already attaches `_ctx_filter` to root and uvicorn loggers) is what Sentry's `LoggingIntegration` (D-04) reads from. Tests (`test_openapi_snapshot.py`) must still pass — Sentry init is inert in tests (D-13).

---

### `backend/app/crawlers/__main__.py` (MODIFY — init Sentry + CLI log context)

**Current full file (8 lines):**
```python
"""
Entry point for running crawlers: python -m app.crawlers --adapter <name>
"""

from app.crawlers.runner import main

if __name__ == "__main__":
    main()
```

**Additions per D-05 + D-47:**
```python
import os
from app.core.sentry import init_sentry
from app.core.log_context import request_id_var, user_id_var
from app.crawlers.runner import main

if __name__ == "__main__":
    init_sentry(server_name="crawler-cli")
    request_id_var.set(f"cli:{os.getpid()}")
    user_id_var.set("cli")
    main()
```

**Divergence:** Module runs on import (not inside a function), so `init_sentry()` must be called at top-of-`__main__` guard, not at module import — otherwise it would fire during test collection.

---

### `backend/app/crawlers/runner.py` (MODIFY — emit EMF at summary, OBS-02)

**Insertion point — current state (L608-L644, the summary log + result dict):**
```python
# L608-L620 (current): logger.log(summary_level, ...) summary block
logger.log(
    summary_level,
    "Adapter %s done. Ingested=%s skipped=%s (robots=%s not_product=%s gone=%s) errors=%s total=%s%s",
    adapter_name,
    ingested,
    skipped,
    skipped_robots,
    skipped_not_product,
    skipped_gone,
    errors,
    total,
    summary_reason,
)
return {
    "adapter": adapter_name,
    "ingested": ingested,
    ...
}
```

**Diff per D-17 + D-18:**
1. **Before the URL loop starts** (top of `run_crawler` body, around where `adapter_name` is resolved): capture `start_ts = time.monotonic()`. `time` is already imported (L22).
2. **After L620 `logger.log(summary_level, ...)` block, before `return {...}` at L621:**
```python
from app.core.cloudwatch_emf import emit_crawler_run_metrics

emit_crawler_run_metrics(
    adapter_name=adapter_name,
    run_type="live",  # overridable via optional kwarg for rescrape path
    ingested=ingested,
    parse_failures=skipped_not_product,  # per D-22: parse_failures = skipped_not_product
    elapsed_seconds=time.monotonic() - start_ts,
)
```

**Per 02-RESEARCH.md Hot-Spot 3 mitigation:** the existing `logger.log(summary_level, ...)` summary line (L608-L620) runs AFTER the EMF emission. This incidentally mitigates aws-embedded-metrics bug #109 ("last EMF line dropped at end-of-stream") — the non-EMF summary line will follow every EMF line.

**Divergence:**
- `run_type` default is `"live"`. `run_crawler` does not currently accept a `run_type` parameter; D-21 says rescrape runs through a different entry point (`ecs_rescrape_runner.py` → `run_rescrape_all_archived_pages`, not `run_crawler`), so `runner.py` hard-codes `"live"`. The rescrape path emits separately with `"rescrape"` (see `ecs_rescrape_runner.py` below).

---

### `backend/app/crawlers/ecs_runner.py` / `ecs_rescrape_runner.py` (MODIFY — init Sentry)

**Analog (current ecs_runner.py:L34-L40):**
```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

**Diff per D-05 + D-11:**
- Add import: `from app.core.sentry import init_sentry`
- Call `init_sentry(server_name="ecs-crawler")` inside `main()` before any other work (not at module import — matches `__main__.py` pattern above to keep tests silent if they ever import these modules).

**Divergence between ecs_runner.py and ecs_rescrape_runner.py:**
- Same `server_name="ecs-crawler"` (D-11 — one tag for all Fargate crawler work).
- If the EMF helper gains a `run_type` param passed from the caller, `ecs_rescrape_runner.py` passes `"rescrape"` and `ecs_runner.py` passes `"live"`. But since the EMF emission currently lives inside `run_crawler` (which only `ecs_runner.py` invokes via `run_crawlers`), rescrape runs will need a separate EMF emission point — likely added inside `run_rescrape_all_archived_pages` or called from `ecs_rescrape_runner.py::main()` after the rescrape returns.

---

### `backend/app/core/config.py` (MODIFY — Sentry settings)

**Analog — existing Field pattern at L151-L158:**
```python
# Email settings
EMAIL_ENABLED: bool = Field(
    default=False,
    description=(
        "Enable email sending via SES. Set to true in production. " "When false, email calls are silently skipped."
    ),
)
EMAIL_FROM: str = Field(default="")
```

**Addition (new fields to append to `Settings` class):**
```python
# Sentry settings
SENTRY_DSN: str = Field(
    default="",
    description="Sentry DSN for error reporting. Empty = Sentry disabled. Injected via Secrets Manager in prod.",
)
SENTRY_RELEASE: str = Field(
    default="",
    description="Release identifier baked at Docker build time (typically git commit SHA).",
)
SENTRY_SERVICE_NAME: str = Field(
    default="",
    description="Per-process server_name tag: 'apprunner-backend', 'ecs-crawler', 'crawler-cli'.",
)
```

**Divergence:** `SENTRY_DSN` has the same "empty = disabled" semantics as `EMAIL_FROM` and `FLARESOLVERR_URL` (L247-L253), keeping the pattern consistent. Per D-05/D-11, the planner should decide whether to read `SENTRY_SERVICE_NAME` from settings or pass `server_name` as an explicit kwarg to `init_sentry()` (the research skeleton uses kwarg; CONTEXT "Claude's Discretion" allows either).

---

### `backend/requirements.txt` (MODIFY)

**Analog (L49-L52 image/storage block):**
```
# Image storage and processing
boto3==1.42.91
boto3-stubs[s3,sesv2]==1.42.91  # Type stubs for boto3 S3 and SES clients
Pillow==12.2.0
```

**Addition (per D-14 + D-16):**
```
# Observability
sentry-sdk>=2.0,<3
aws-embedded-metrics>=3.0,<4
```

**Divergence:** D-14 pins `sentry-sdk` with range operators (`>=2.0,<3`) rather than exact version as `boto3==1.42.91` does. Rationale in decision: Dependabot (SAFE-10) picks up patches weekly. The planner may choose exact pin (matches existing file style) — either is acceptable.

---

### `backend/tests/test_sentry_init.py` (NEW)

**Primary analog:** `backend/tests/test_email.py:L22-L56`

**Pattern to mirror** (from `test_email.py:L22-L38`):
```python
@patch("app.core.email.settings")
@patch("app.core.email.boto3.client")
def test_send_verify_email_success(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
    """send_verify_email returns True and calls SES send_email on success."""
    mock_settings.EMAIL_ENABLED = True
    mock_settings.EMAIL_FROM = "noreply@example.com"
    mock_settings.AWS_REGION = "us-east-1"
    mock_ses = MagicMock()
    mock_boto_client.return_value = mock_ses

    result = send_verify_email("user@example.com", "https://example.com/verify?token=abc")

    assert result is True
    mock_ses.send_email.assert_called_once()
```

**Test cases to cover** (per D-49):
1. `init_sentry()` no-ops when `TESTING=true` (conftest sets this — no mock needed; assert `sentry_sdk.init` NOT called).
2. `init_sentry()` no-ops when `APP_ENVIRONMENT=development`.
3. `init_sentry()` no-ops when `SENTRY_DSN` is empty.
4. `init_sentry()` calls `sentry_sdk.init` with expected kwargs when all conditions pass.
5. Scope processor / `before_send` attaches `request_id` tag from `request_id_var` (research §1 L61-L70).
6. `HTTPException` does not produce a Sentry event (assertion on the in-memory transport, 02-RESEARCH.md Hot-Spot 1).

**Divergence:**
- `test_email.py` uses `@patch(...)` decorator style; this test may use `monkeypatch` fixture + `mocker.patch` (existing test code uses both). Pick one per test file.
- No `boto3` involvement — `sentry_sdk` is the mock target. Use `monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)` or `@patch("app.core.sentry.sentry_sdk.init")`.

---

### `backend/tests/test_cloudwatch_emf.py` (NEW)

**Primary analog:** same as `test_sentry_init.py` — `backend/tests/test_email.py`.

**Test cases** (per D-50):
1. `emit_crawler_run_metrics()` no-ops when `TESTING=true`.
2. `emit_crawler_run_metrics()` no-ops when `APP_ENVIRONMENT=development`.
3. When staging/production, emits an EMF log record with `_aws` envelope containing `CarModPicker/Crawlers` namespace, `AdapterName`/`Environment`/`RunType` dimensions, and `Ingested`/`ParseFailures`/`ElapsedSeconds` metric names.

**Capture mechanism per D-50:** pytest `caplog` — aws-embedded-metrics emits via stdlib logging, so `caplog.records` with JSON parsing of the message payload is the simplest assertion.

**Divergence:** no external library boto3 mock. The test may instead mock `aws_embedded_metrics.logger.metrics_logger_factory.create_metrics_logger` to capture calls, or verify the actual log output via `capsys` / `caplog`. Research says "No moto, no boto3 mocking needed since EMF is logs-only" (D-50).

---

### `backend/tests/test_log_propagation.py` (NEW)

**Primary analog:** `backend/tests/auth/test_characterization_login.py:L26-L60`

**Pattern to mirror:**
```python
def test_login_happy_path(client: TestClient, db_session: Session) -> None:
    """Flow 2: email/password login returns access_token + user details."""
    username = _uniq("login_char")
    # ... create user in DB ...
    response = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
```

**Full shape per 02-RESEARCH.md §1 L256-L280:**
```python
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
```

**Divergence:**
- Uses `caplog` fixture (not used anywhere in the current backend tests — this is a new pattern).
- Fixture yields without a value, then asserts on teardown — common pytest idiom but new to this codebase.
- Research §1 L272 shows `assert_request_context` used as a positional fixture in the test signature — vs the existing style which accepts `client, db_session` only.

---

### `backend/tests/conftest.py` (MODIFY — add Sentry stub + request-context fixture)

**Analog — existing `mock_s3` monkeypatch fixture at L420-L469:**
```python
@pytest.fixture
def mock_s3(monkeypatch: pytest.MonkeyPatch) -> Generator[Dict[str, Any], None, None]:
    """
    Fake in-memory S3 using moto.
    """
    from moto import mock_aws

    with mock_aws():
        import boto3
        # ... setup ...
        monkeypatch.setattr(ss_module.storage_service, "s3_client", s3)
        monkeypatch.setattr(ss_module.storage_service, "s3_client_presigner", s3)
        monkeypatch.setattr(ss_module.storage_service, "bucket_name", "test-user-images")
        yield {...}
```

**Divergence:** The new Sentry stub fixture does NOT need moto. It captures events via Sentry's in-memory transport — `sentry_sdk.transport.Transport` subclass that appends to a list. Example shape (D-49):
```python
@pytest.fixture
def sentry_events(monkeypatch):
    events = []
    class StubTransport:
        def capture_event(self, event):
            events.append(event)
    monkeypatch.setattr("sentry_sdk.transport.Transport", StubTransport)
    yield events
```

Or lighter-weight: just monkeypatch `sentry_sdk.init` to a no-op and assert `sentry_sdk.capture_exception` calls via `unittest.mock`.

**Second fixture** — `assert_request_context` — lives either here (worker-scoped) or in `test_log_propagation.py`. Per CONTEXT "Claude's Discretion" bullet 4, planner picks. Recommendation: keep it in `test_log_propagation.py` to avoid polluting every test with teardown assertions.

---

### `frontend/src/lib/sentry.ts` (NEW)

**Note: `frontend/src/lib/` does not currently exist.** This is a net-new directory. Closest parallels:
- `frontend/src/utils/` — utility-module convention (has `*.test.ts` siblings)
- `frontend/src/services/Api.ts` — module that wraps an external library (axios) for app-wide use

**Primary pattern analog:** `backend/app/core/sentry.py` (cross-stack sibling — same env-gate shape, parallel API).

**Env-gate pattern (from 02-RESEARCH.md §1 L202-L233):**
```typescript
import * as Sentry from '@sentry/react';

const AUTH_PATHS = ['/login', '/register', '/oauth-callback', '/reset-password', '/2fa'];

export function initSentry(): void {
  if (import.meta.env.MODE === 'development') return;
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;

  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
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

**Divergence from backend sentry.py:** Frontend gate is two conditions (MODE + DSN) instead of three (TESTING + APP_ENVIRONMENT + DSN) — per D-42. No ContextVar equivalent; user binding happens in AuthContext via `Sentry.setUser()` (D-40).

---

### `frontend/src/main.tsx` (MODIFY)

**Current state (L1-L17):**
```typescript
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { GoogleOAuthProvider } from '@react-oauth/google';
import App from './App.tsx';
import ErrorBoundary from './components/common/ErrorBoundary';
import { AppSettingsProvider } from './contexts/AppSettingsContext';
import { AuthProvider } from './contexts/AuthContext';
import { GOOGLE_CLIENT_ID } from './config/google';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

createRoot(rootElement).render(
  ...
);
```

**Diff per D-39:**
- Add import: `import { initSentry } from './lib/sentry';`
- Call `initSentry();` between the `./index.css` import and the `const rootElement = ...` line (i.e., first executable statement, before `createRoot`).

**Divergence:** No — trivial insertion. Mirrors D-12 (backend `init_sentry` called before `FastAPI()`).

---

### `frontend/src/components/common/ErrorBoundary.tsx` (MODIFY — 3-line D-35 change)

**Current componentDidCatch (L23-L25):**
```typescript
override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  console.error('ErrorBoundary caught an error:', error, errorInfo);
}
```

**Diff per D-35:**
```typescript
import * as Sentry from '@sentry/react';
// ... existing imports ...

override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
  console.error('ErrorBoundary caught an error:', error, errorInfo);
  Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });
}
```

**Divergence:** Keep existing class component + styled fallback UI (`render()` method L27-L54 unchanged). Do NOT swap to `Sentry.ErrorBoundary` HOC — explicit D-35 decision.

---

### `frontend/src/contexts/AuthContext.tsx` (MODIFY — setUser on login/logout)

**Current state relevant to insertion — L51-L53 existing useEffect:**
```typescript
useEffect(() => {
  void checkAuthStatus();
}, [checkAuthStatus]);
```

**Diff per D-40:** Add a second `useEffect` (or extend the existing one) after the `user` state setter runs:
```typescript
import * as Sentry from '@sentry/react';
// ...
useEffect(() => {
  Sentry.setUser(user ? { id: String(user.id) } : null);
}, [user]);
```

**Divergence:** The existing `logout` handler at L60-L73 calls `setUser(null)` at L68 — the new `useEffect` with `[user]` dependency automatically covers logout too. No need to duplicate in the logout path.

Per D-40: no `email`, no `username` in the Sentry user object — matches backend D-09 PII posture.

---

### `frontend/src/lib/sentry.test.ts` (NEW)

**Primary analog:** `frontend/src/utils/carUtils.test.ts` + `frontend/src/test/setup.ts:L13-L15`

**Pattern from `carUtils.test.ts:L1-L22`:**
```typescript
import { describe, expect, it } from 'vitest';
import { carFullDisplayName } from './carUtils';
import type { CarGenerationRead } from '../types/Api';

function makeCar(partial: Partial<CarGenerationRead>): CarGenerationRead {
  return { ...partial } as CarGenerationRead;
}

describe('carFullDisplayName', () => {
  it('drops duplicated model when generation display includes it', () => {
    const car = makeCar({ ... });
    expect(carFullDisplayName(car)).toBe('Toyota GR86 (ZN8)');
  });
});
```

**`vi.mock` pattern from `setup.ts:L13-L15`:**
```typescript
vi.mock('../services/Api', () => ({
  default: mockApiClient,
}));
```

**Test cases per D-51:**
1. `initSentry()` calls `Sentry.init` once when MODE !== 'development' AND `VITE_SENTRY_DSN` set.
2. `initSentry()` skips `Sentry.init` when MODE === 'development'.
3. `initSentry()` skips when `VITE_SENTRY_DSN` undefined.

**Divergence:** Must mock `@sentry/react` (external npm package), not a relative module. `vi.mock('@sentry/react', () => ({ init: vi.fn(), ... }))`. Must also stub `import.meta.env.MODE` and `import.meta.env.VITE_SENTRY_DSN` — vitest provides `vi.stubEnv` for this.

---

### `frontend/src/components/common/ErrorBoundary.test.tsx` (NEW)

**Note: no existing React component tests in the codebase.** Package.json confirms `@testing-library/react@^16.1.0` and `@testing-library/jest-dom@^6.6.3` are installed — deps are ready, pattern is net-new.

**Primary analog for the vitest shape:** `frontend/src/utils/carUtils.test.ts` (pure vitest structure).

**Additional tools to use** (already in devDependencies):
- `@testing-library/react` — `render()`, `screen.getByText()`
- `@testing-library/jest-dom` — `toBeInTheDocument()` matcher
- `vi.mock('@sentry/react', ...)` for the captureException spy

**Minimal shape:**
```typescript
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ErrorBoundary from './ErrorBoundary';

const mockCapture = vi.fn();
vi.mock('@sentry/react', () => ({
  captureException: mockCapture,
}));

function Thrower(): JSX.Element {
  throw new Error('boom');
}

describe('ErrorBoundary', () => {
  it('renders fallback and calls Sentry.captureException on error', () => {
    // React 19's StrictMode + testing-library suppresses error logs during render
    render(
      <ErrorBoundary>
        <Thrower />
      </ErrorBoundary>
    );
    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    expect(mockCapture).toHaveBeenCalledOnce();
  });
});
```

**Divergence:** First component test in the repo. The `frontend/src/test/setup.ts:L22-L40` `console.error` suppressor covers React's error-log noise during the throw — no extra work needed.

---

### `frontend/vite.config.ts` (MODIFY — @sentry/vite-plugin)

**Current state (L1-L7):**
```typescript
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
```

**Diff per D-34 (gated on `SENTRY_AUTH_TOKEN` presence):**
```typescript
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { sentryVitePlugin } from '@sentry/vite-plugin';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(process.env.SENTRY_AUTH_TOKEN
      ? [sentryVitePlugin({
          org: process.env.SENTRY_ORG,
          project: process.env.SENTRY_PROJECT,
          authToken: process.env.SENTRY_AUTH_TOKEN,
        })]
      : []),
  ],
  // ... existing build/server config ...
});
```

**Divergence:** Conditional array spread pattern — if `SENTRY_AUTH_TOKEN` unset, the plugin array is `[react(), tailwindcss()]` exactly as today. Zero impact on local `npm run build`.

Also per D-34: must enable sourcemap output in the `build` block (`build.sourcemap: true` or `'hidden'`) so the plugin has maps to upload.

---

### `frontend/package.json` (MODIFY — new deps)

**Analog — existing dependencies block:**
```json
"dependencies": {
    "@react-oauth/google": "^0.13.5",
    "@simplewebauthn/browser": "^11.0.0",
    "@tailwindcss/vite": "^4.1.7",
    "axios": "^1.15.0",
    ...
},
"devDependencies": {
    "@eslint/js": "^9.25.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    ...
}
```

**Additions per D-43 + D-32:**
- `dependencies`: `"@sentry/react": "^10.0.0"`
- `devDependencies`: `"@sentry/vite-plugin": "^4.0.0"` (per 02-RESEARCH.md: 4.x simpler than 5.x; both maintained)

---

### `terraform/monitoring.tf` (MODIFY — composite parse-failure alarm)

**Primary analog — `apprunner_5xx` alarm at L56-L73:**
```hcl
resource "aws_cloudwatch_metric_alarm" "apprunner_5xx" {
  alarm_name        = "${local.prefix}-apprunner-5xx"
  alarm_description = "Elevated App Runner 5xx error rate"
  namespace         = "AWS/AppRunner"
  metric_name       = "5xxStatusResponses"
  dimensions = {
    ServiceName = "${local.prefix}-backend"
    ServiceID   = aws_apprunner_service.backend.service_id
  }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 10
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
}
```

**New alarm shape (full body in 02-RESEARCH.md §1 L146-L195):** uses `metric_query[]` blocks instead of top-level `namespace`/`metric_name`. Per 02-RESEARCH.md Hot-Spot 4, `period` MUST appear only inside each `metric_query.metric {}` block — never at the resource top level (terraform-provider-aws bug #29398).

**Key differences vs `apprunner_5xx` analog:**
- Three `metric_query` blocks (m1 `ingested`, m2 `failures`, m3 expression `rate`) instead of a single inline `namespace`+`metric_name`+`dimensions`.
- No top-level `period` or `statistic` — those live in each `metric_query.metric.{period,stat}`.
- `threshold = 0.5` (a rate, not a count) — matches D-22.
- Same `alarm_actions` / `ok_actions` wiring to `aws_sns_topic.alarms.arn` — matches D-24/D-26 and the existing 5-alarm convention (L71-L72, L88-L89, L104-L105, L121-L122, L138-L139 all use the same pair).
- Same `treat_missing_data = "notBreaching"` as L70 (App Runner 5xx alarm).

**Additional terraform in same file:**
- Add `# TODO(phase-3): convert composite alarm to per-adapter via for_each = toset(file("${path.module}/adapter_names.txt"))` comment per D-30.
- Add `var.disabled_parse_alarms` reference for future per-adapter loop (variable itself declared in `variables.tf`).

**Dimensions note:** the expression filters to `RunType = "live"` only (D-22). Rescrape runs emit with `RunType = "rescrape"` and never feed this alarm.

---

### `terraform/secretsmanager.tf` (MODIFY — SENTRY_DSN secret)

**Primary analog — `secret_key` pattern at L13-L22:**
```hcl
resource "aws_secretsmanager_secret" "secret_key" {
  name                    = "${local.prefix}/secret-key"
  description             = "JWT signing key for the FastAPI backend"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "secret_key" {
  secret_id     = aws_secretsmanager_secret.secret_key.id
  secret_string = var.secret_key
}
```

**New block:**
```hcl
resource "aws_secretsmanager_secret" "sentry_dsn" {
  name                    = "${local.prefix}/sentry-dsn"
  description             = "Sentry DSN for backend error reporting (project created manually per D-54)"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "sentry_dsn" {
  secret_id     = aws_secretsmanager_secret.sentry_dsn.id
  secret_string = var.sentry_dsn  # populated out-of-band via `aws secretsmanager put-secret-value` per D-55
}
```

**Divergence:**
- `var.sentry_dsn` needs to be declared in `variables.tf` with `default = ""` and `sensitive = true` — matching the `secret_key` / `cron_secret_key` variable shape (variables.tf:L45-L49, L61-L65).
- Per D-55: operator populates the value via `aws secretsmanager put-secret-value` AFTER first `terraform apply`, so the Terraform variable may be empty on first apply and the Sentry init will no-op until the value is populated (env-gate handles this gracefully).

---

### `terraform/apprunner.tf` (MODIFY — inject SENTRY_DSN)

**Primary analog — `runtime_environment_secrets` map at L252-L257:**
```hcl
# Sensitive values pulled from Secrets Manager at startup
runtime_environment_secrets = {
  DATABASE_URL    = aws_secretsmanager_secret_version.database_url.arn
  SECRET_KEY      = aws_secretsmanager_secret_version.secret_key.arn
  CRON_SECRET_KEY = aws_secretsmanager_secret_version.cron_secret_key.arn
}
```

**Addition:**
```hcl
runtime_environment_secrets = {
  DATABASE_URL    = aws_secretsmanager_secret_version.database_url.arn
  SECRET_KEY      = aws_secretsmanager_secret_version.secret_key.arn
  CRON_SECRET_KEY = aws_secretsmanager_secret_version.cron_secret_key.arn
  SENTRY_DSN      = aws_secretsmanager_secret_version.sentry_dsn.arn
}
```

**Also modify `runtime_environment_variables` (L218-L250) to add:**
```hcl
SENTRY_RELEASE         = var.sentry_release   # set to git SHA by GHA at plan/apply time
SENTRY_SERVICE_NAME    = "apprunner-backend"
AWS_EMF_ENVIRONMENT    = "Local"              # RESEARCH Hot-Spot 3: forces stdout sink
```

**Also modify both IAM policies** (L23-L38 access role + L59-L75 instance role) to add `aws_secretsmanager_secret.sentry_dsn.arn` to each `Resource = [...]` array. Without this, App Runner cannot read the new secret at startup.

**Divergence:** Standard additive change to existing maps and arrays. No new resources, no new module.

---

### `terraform/ecs.tf` (MODIFY — inject SENTRY_DSN)

**Primary analog — existing `secrets = [...]` at L218-L229:**
```hcl
secrets = [
  {
    name      = "DATABASE_URL"
    valueFrom = aws_secretsmanager_secret.database_url.arn
  },
  {
    name      = "SECRET_KEY"
    valueFrom = aws_secretsmanager_secret.secret_key.arn
  },
]
```

**Addition:**
```hcl
secrets = [
  { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.database_url.arn },
  { name = "SECRET_KEY",   valueFrom = aws_secretsmanager_secret.secret_key.arn },
  { name = "SENTRY_DSN",   valueFrom = aws_secretsmanager_secret.sentry_dsn.arn },
]
```

**Also modify `environment = [...]` (L200-L216):**
```hcl
{ name = "SENTRY_RELEASE",      value = var.sentry_release },
{ name = "SENTRY_SERVICE_NAME", value = "ecs-crawler" },
{ name = "AWS_EMF_ENVIRONMENT", value = "Local" },  # RESEARCH Hot-Spot 3
```

**Also modify `aws_iam_role_policy "ecs_task_execution_secrets"` at L75-L89:** append `aws_secretsmanager_secret.sentry_dsn.arn` to the `Resource = [...]` array.

**Divergence:** ECS uses `{name, valueFrom}` list-of-objects shape; App Runner uses `{KEY = ARN}` map shape. Same secret, different injection syntax — both already present in existing terraform for `DATABASE_URL`.

---

### `terraform/variables.tf` (MODIFY — new variables)

**Analog — existing pattern at L44-L55:**
```hcl
variable "secret_key" {
  description = "JWT signing secret for the FastAPI backend"
  type        = string
  sensitive   = true
}

variable "email_from" {
  description = "Sender address for transactional email"
  type        = string
  default     = "no-reply@carmodpicker.com"
}
```

**Additions:**
```hcl
variable "sentry_dsn" {
  description = "Sentry DSN for backend error reporting. Empty = Sentry disabled."
  type        = string
  sensitive   = true
  default     = ""
}

variable "sentry_release" {
  description = "Sentry release identifier (typically git commit SHA, set by GHA)."
  type        = string
  default     = ""
}

variable "disabled_parse_alarms" {
  description = "Adapter names to exclude from per-adapter parse-failure alarms (Phase 3 conversion target; unused in Phase 2 composite alarm)."
  type        = list(string)
  default     = []
}
```

**Divergence:** First `list(string)` variable in the file — nothing today uses that type. Straightforward Terraform primitive, no pattern change.

---

### `terraform/README.md` (MODIFY — Bootstrap: Sentry section per D-57)

**Analog:** existing architecture description + file map table at L1-L40. Append a new "## Bootstrap: Sentry" section near the end. Content: steps from D-54/D-55/D-56 — create Sentry project(s), create Secrets Manager secret + version, set GHA secrets, redeploy.

No code excerpt needed — documentation is free-form text.

---

## Shared Patterns

### Env-gate early-return

**Source pattern:** `backend/app/core/email.py:L36-L41` and `backend/app/core/logging.py:L51-L57`

**Apply to:** `backend/app/core/sentry.py`, `backend/app/core/cloudwatch_emf.py`, `frontend/src/lib/sentry.ts`

**Shape:**
```python
def helper(...) -> ReturnType:
    if not <env gate>:
        # no-op (optionally debug-log)
        return
    # real work
```

**Environment variables already following this pattern:**
| Var | Gate behavior | File |
|---|---|---|
| `EMAIL_ENABLED` | `False` → skip SES call | `email.py:L38-L40` |
| `TESTING` | `"true"` → skip rate limiter, S3 real backend | `conftest.py:L15-L16` |
| `ENABLE_RATE_LIMITING` | `"false"` → rate limit middleware no-ops | `conftest.py:L16` |
| `FLARESOLVERR_URL` | empty → Tier 2 disabled | `config.py:L271` |
| `APP_ENVIRONMENT` | non-prod → colorized logs / no JSON | `logging.py:L52-L57` |

Phase 2 adds: `SENTRY_DSN` (empty → Sentry disabled), `AWS_EMF_ENVIRONMENT` (must be `"Local"` on ECS per RESEARCH Hot-Spot 3), `VITE_SENTRY_DSN` (empty → frontend Sentry disabled).

---

### ContextVar scope propagation

**Source:** `backend/app/core/log_context.py:L4-L5` (definition) + `backend/app/api/middleware/request_context.py:L11-L18` (set/reset via token)

**Apply to:**
- `backend/app/core/sentry.py::_before_send` (reads `request_id_var.get()` and `user_id_var.get()` to enrich events — D-09)
- `backend/app/core/log_context.py::bg_log_context` (new context manager — D-46)
- `backend/app/crawlers/__main__.py` (sets CLI-scope ContextVars — D-47)

**Pattern:**
```python
token = request_id_var.set(<new value>)
try:
    # work
finally:
    request_id_var.reset(token)
```

Using the `token` return value for reset is what makes this re-entrant-safe under ECS Fargate's thread-based crawler parallelism.

---

### Terraform secret → env var injection

**Source pattern:** existing `DATABASE_URL` + `SECRET_KEY` + `CRON_SECRET_KEY` flow:
1. `secretsmanager.tf` — `aws_secretsmanager_secret` + `aws_secretsmanager_secret_version`
2. `apprunner.tf:L252-L257` — `runtime_environment_secrets = { KEY = arn }` (map form)
3. `apprunner.tf:L23-L38 + L59-L75` — IAM policy `Resource = [...]` arrays (access role + instance role both need the ARN)
4. `ecs.tf:L218-L229` — `secrets = [{name, valueFrom}, ...]` (list-of-objects form)
5. `ecs.tf:L75-L89` — IAM policy `Resource = [...]` array (task execution role)

**Apply to:** `SENTRY_DSN` follows exactly this 5-step flow. Any planner omitting one of the IAM-grant steps (3 or 5) will cause App Runner or ECS task launches to fail at startup with "AccessDenied" on the new secret ARN.

---

### CloudWatch alarm with SNS notification

**Source:** `terraform/monitoring.tf:L56-L141` — all 5 existing alarms use the exact same `alarm_actions = [aws_sns_topic.alarms.arn]` + `ok_actions = [aws_sns_topic.alarms.arn]` + `treat_missing_data = "notBreaching"` or `"missing"` shape.

**Apply to:** new `crawler_parse_failure_composite` alarm — same shape, but metric source is `metric_query[]` blocks instead of inline `namespace`/`metric_name` because the alarm is on a metric-math expression.

---

### pytest caplog + monkeypatch for env-gated helpers

**Source analogs:**
- `backend/tests/test_email.py:L22-L56` — `@patch("app.core.email.settings")` + `@patch("app.core.email.boto3.client")` + assertions on mock calls
- `backend/tests/conftest.py:L420-L469` — `mock_s3` using `monkeypatch.setattr` pattern
- `backend/tests/conftest.py:L15-L16` — setting `TESTING=true` at module import time

**Apply to:** `test_sentry_init.py`, `test_cloudwatch_emf.py`, `test_log_propagation.py`. No test should make a real Sentry network call; no test should emit real EMF to stdout (captured via `caplog`).

---

## No Analog Found

Every file has at least a role-match analog. The thinnest analogs are:

| File | Weakness |
|------|----------|
| `frontend/src/components/common/ErrorBoundary.test.tsx` | No existing React component tests in the repo — this test introduces `@testing-library/react render()` usage to the codebase. But deps (`@testing-library/react@^16.1.0`, `@testing-library/jest-dom@^6.6.3`) are already installed per package.json. |
| `frontend/src/lib/sentry.ts` | `frontend/src/lib/` directory doesn't exist yet. Nearest siblings are `src/utils/` and `src/services/`. Planner may place the file in `src/services/sentry.ts` instead if "services" fits the project's grep-by-directory convention better. |
| `backend/tests/test_log_propagation.py` | `caplog` fixture is not used anywhere in the current backend test suite. Research has a concrete skeleton (02-RESEARCH.md §1 L256-L280). |
| `backend/app/core/cloudwatch_emf.py` | `aws-embedded-metrics` library has never been used in this codebase. Research §1 L105-L140 has the concrete skeleton and §"Hot-Spot 3" covers the `AWS_EMF_ENVIRONMENT=Local` footgun. |

---

## Metadata

**Analog search scope:**
- `backend/app/core/` (helpers + config)
- `backend/app/api/middleware/` (error handler, rate limiter, request context)
- `backend/app/crawlers/` (runner + ECS entrypoints)
- `backend/tests/` + `backend/tests/auth/` + `backend/tests/middleware/` (test patterns)
- `frontend/src/` (main.tsx, components/common, contexts, lib, utils, test)
- `terraform/` (all *.tf files + README)

**Files scanned:** 27 existing files read in full or targeted range. No whole-file reads of files >1000 lines (log_context.py = 13 lines, ErrorBoundary.tsx = 57 lines, email.py read in full for the env-gate pattern, runner.py read only L580-L660 around the summary block).

**Pattern extraction date:** 2026-04-22

## PATTERN MAPPING COMPLETE
