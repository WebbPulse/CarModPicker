---
phase: 02-observability
reviewed: 2026-04-22T23:32:43Z
depth: standard
files_reviewed: 29
files_reviewed_list:
  - .gitignore
  - backend/app/core/cloudwatch_emf.py
  - backend/app/core/config.py
  - backend/app/core/log_context.py
  - backend/app/core/sentry.py
  - backend/app/crawlers/__main__.py
  - backend/app/crawlers/ecs_rescrape_runner.py
  - backend/app/crawlers/ecs_runner.py
  - backend/app/crawlers/runner.py
  - backend/app/main.py
  - backend/requirements.txt
  - backend/tests/conftest.py
  - backend/tests/test_cloudwatch_emf.py
  - backend/tests/test_log_propagation.py
  - backend/tests/test_sentry_init.py
  - CLAUDE.md
  - frontend/package.json
  - frontend/src/components/common/ErrorBoundary.test.tsx
  - frontend/src/components/common/ErrorBoundary.tsx
  - frontend/src/contexts/AuthContext.tsx
  - frontend/src/lib/sentry.test.ts
  - frontend/src/lib/sentry.ts
  - frontend/src/main.tsx
  - frontend/vite.config.ts
  - terraform/apprunner.tf
  - terraform/ecs.tf
  - terraform/monitoring.tf
  - terraform/README.md
  - terraform/secretsmanager.tf
  - terraform/variables.tf
findings:
  critical: 0
  warning: 3
  info: 6
  total: 9
status: issues_found
---

# Phase 2 (Observability): Code Review Report

**Reviewed:** 2026-04-22T23:32:43Z
**Depth:** standard
**Files Reviewed:** 29
**Status:** issues_found

## Summary

Phase 2 introduces Sentry SDK integration (backend + frontend), CloudWatch EMF emission from the crawler, a composite parse-failure alarm, and log-context propagation. Overall implementation quality is high: the design decisions are well documented, landmines are pinned with static checks (e.g. `test_runner_emits_before_summary`), env gates are layered defensively (TESTING > APP_ENVIRONMENT > DSN), failure isolation is explicit in `emit_crawler_run_metrics`, and test coverage is thoughtful (sentry transport shim, caplog filter augmentation, EMF envelope shape).

Findings are concentrated in two areas:

1. **Bool-coercion of JSON strings in `ecs_runner.py`** — the per-adapter skip map does `bool(v)` on values that may be JSON strings, which silently inverts the intended semantics (`bool("false")` returns `True`). This is the only real correctness bug found.
2. **ECS runner error paths that validate env vars outside the job-notification try/except** — malformed UUIDs in `JOB_ID`, `CRAWLER_DEFAULT_CATEGORY_ID`, or `CRAWLER_USER_ID` raise `ValueError` and exit the task without updating the `BackgroundJob` row or emailing superadmins. The job stays in "running" until the orphan sweeper marks it failed on the next App Runner startup.

No security issues, no Sentry/EMF correctness bugs, no crash paths in the new observability code itself. The remaining items are style/hygiene.

## Warnings

### WR-01: `bool()` on JSON values silently converts string "false" to True

**File:** `backend/app/crawlers/ecs_runner.py:120`
**Issue:** The per-adapter skip map is built with `{k: bool(v) for k, v in json.loads(skip_by_adapter_str).items()}`. If the JSON contains proper booleans (`{"a90shop": false}`) this is correct — `v` is already a Python `False`, `bool(False)` is `False`. But if any caller or orchestrator serializes booleans as strings (`{"a90shop": "false"}`), `bool("false")` returns `True` because non-empty strings are truthy. The sibling env vars `CRAWLER_PARALLEL` (line 114) and `CRAWLER_SKIP_KNOWN_URLS` (line 115) use an explicit `.lower() in (...)` pattern precisely to avoid this trap, and `delays` (line 107) coerces via `float(v)`. Only the boolean map is vulnerable.

If upstream producers always emit real booleans this is dormant; but the inconsistency makes it a footgun for future env producers (EventBridge payload, admin UI JSON, rescrape triggers).

**Fix:**
```python
def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)

skip_by_adapter_str = os.environ.get("CRAWLER_SKIP_KNOWN_URLS_BY_ADAPTER")
skip_known_urls_by_adapter: dict[str, bool] | None = None
if skip_by_adapter_str:
    skip_known_urls_by_adapter = {
        k: _coerce_bool(v) for k, v in json.loads(skip_by_adapter_str).items()
    }
```

### WR-02: Malformed UUID env vars bypass job-failure notification in ECS runners

**File:** `backend/app/crawlers/ecs_runner.py:79, 90, 93` and `backend/app/crawlers/ecs_rescrape_runner.py:83, 91`
**Issue:** Both ECS entry points parse `JOB_ID`, `CRAWLER_DEFAULT_CATEGORY_ID`, and `CRAWLER_USER_ID` with `UUID(...)` *outside* the main `try/except` block that is responsible for calling `job_service.fail_job(...)` and `_notify_completion(...)`. If any of those env vars are present but malformed (truncated, typo, non-UUID value), `UUID(...)` raises `ValueError`, the task exits with a stack trace, and:

  - the `BackgroundJob` row (if `JOB_ID` happened to be valid but another var wasn't) stays in `running` forever until the startup `sweep_orphan_jobs` in `main.py` catches it.
  - no failure email is sent to superadmins.
  - the failure traceback is not persisted to the `BackgroundJob.error_message` field where the admin UI would surface it.

This mirrors a real operational failure mode: the App Runner caller builds a `ecs.run_task` payload and one of the UUIDs is malformed. The Sentry init has already happened (Sentry will catch it) — so the event does reach Sentry, but the DB state is stale.

**Fix:** Move env parsing inside the main `try/except`. In `ecs_runner.py`, pattern after `ecs_rescrape_runner.py:118` and lift the `UUID(...)` calls below the `try:`. Example:

```python
def main() -> None:
    from app.core.sentry import init_sentry
    init_sentry(server_name="ecs-crawler")
    # ... imports ...

    # Parse JOB_ID early (outside try) since we need it for the exception handler
    # — but validate it permissively so the broad except can still call fail_job.
    job_id_str = os.environ.get("JOB_ID")
    try:
        job_id = UUID(job_id_str) if job_id_str else None
    except ValueError:
        logger.exception("JOB_ID=%r is not a valid UUID; aborting without job update.", job_id_str)
        sys.exit(1)

    try:
        # All OTHER env parsing moves here so failures update the job row.
        category_id_str = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
        if not category_id_str:
            raise CrawlerConfigError("CRAWLER_DEFAULT_CATEGORY_ID is required")
        default_category_id = UUID(category_id_str)
        # ... etc ...
        result = run_crawlers(...)
        # ... success path ...
    except Exception:
        logger.exception("ECS crawler task failed")
        if job_id is not None:
            # existing fail_job + _notify_completion path
            ...
        sys.exit(1)
```

### WR-03: Legacy `int()` cast on CRAWLER_USER_ID mismatches current UUID-based User model

**File:** `backend/app/crawlers/runner.py:114-124`
**Issue:** `_get_crawler_user` has a fallback path that reads `CRAWLER_USER_ID` from the env and calls `int(raw)`, then filters `DBUser.id == user_id` (an int). However, the User model is UUID-based (see `DBUser.is_service_account.is_(True)` filter on line 108, and `resolve_crawler_user` on line 137 which uses `UUID` type). The `int(raw)` fallback path is dead in practice — a caller setting `CRAWLER_USER_ID` to a UUID string will hit `ValueError` and raise `CrawlerConfigError("CRAWLER_USER_ID must be an integer.")`, which is a misleading error message for a UUID-valued field. The primary path (service-account lookup via `is_service_account.is_(True)`) makes this fallback legacy/vestigial.

This is pre-existing code that the Phase 2 changes did not introduce, but Phase 2 docstrings and `ecs_runner.py` pass user IDs as `UUID`, leaving this inconsistency more visible.

**Fix:** Either delete the fallback (preferred — the service account seed runs on every startup) or replace `int(raw)` with `UUID(raw)`:

```python
raw = os.environ.get("CRAWLER_USER_ID")
if raw:
    try:
        user_id = UUID(raw)
    except ValueError as exc:
        raise CrawlerConfigError("CRAWLER_USER_ID must be a valid UUID.") from exc
    user = db.query(DBUser).filter(DBUser.id == user_id).first()
    # ...
```

## Info

### IN-01: `start_ts` and `t0` are redundant aliases

**File:** `backend/app/crawlers/runner.py:528-529`
**Issue:** `start_ts = time.monotonic(); t0 = start_ts` assigns two names to the same value. The docstring explains the aliasing is intentional (EMF uses `start_ts` at line 693, return dict uses `t0` at line 745), but there's no functional difference and future refactors could accidentally diverge them.
**Fix:** Use one name and comment that both consumers (EMF emit + return dict) reference it:
```python
# Same wall-clock anchor for EMF emit and return dict's elapsed_seconds.
t0 = time.monotonic()
# ... later ...
elapsed_seconds=time.monotonic() - t0,  # EMF emit
# ... and ...
"elapsed_seconds": round(time.monotonic() - t0, 3),  # return dict
```

### IN-02: Inconsistent boolean env-var parsing patterns across `ecs_runner.py`

**File:** `backend/app/crawlers/ecs_runner.py:114-120`
**Issue:** `CRAWLER_PARALLEL` uses `.lower() not in ("false", "0", "no")` (default True); `CRAWLER_SKIP_KNOWN_URLS` uses `.lower() in ("true", "1", "yes")` (default False). The default-True and default-False semantics are intentional, but the two predicates are logically different (not exact negations — e.g. the value `"maybe"` is truthy for PARALLEL but falsy for SKIP_KNOWN_URLS). Consolidating into a shared helper would prevent future drift.
**Fix:** Extract a helper:
```python
def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")

parallel = _env_bool("CRAWLER_PARALLEL", default=True)
skip_known_urls = _env_bool("CRAWLER_SKIP_KNOWN_URLS", default=False)
```

### IN-03: ECS runners do not set `request_id_var` for log context

**File:** `backend/app/crawlers/ecs_runner.py:63-170` and `backend/app/crawlers/ecs_rescrape_runner.py:64-169`
**Issue:** `__main__.py` (CLI) sets `request_id_var.set(f"cli:{os.getpid()}")` so every log line is grep-distinguishable. `main.py` (App Runner) uses `request_context_middleware` to populate it per-request. Neither ECS runner sets anything, so their log lines default to `request_id="-"`, `user_id="-"`. This works for Sentry's `_before_send` (it skips the sentinel) but loses the grep affordance mentioned in `log_context.py`'s docstring ("CloudWatch grep `filter @message like /req=bg:crawler/` works"). ECS crawler logs go to a separate log group (`/ecs/${prefix}-crawler`), so grepping across environments is less pressing, but if an operator ever consolidates or cross-references logs, the context is missing.
**Fix:** Wrap each ECS entry point with `bg_log_context` (if the helper's semantics fit) or set both ContextVars explicitly at the top of `main()`:
```python
request_id_var.set(f"ecs:{os.getpid()}:{job_id or '-'}")
user_id_var.set("ecs")
```
Note: `bg_log_context` is a context manager and would require a `with` block wrapping the whole body; the explicit `set` is simpler if the "re-entrant-safe reset" feature is not needed (ECS tasks never re-enter).

### IN-04: ECS runners use their own `logging.basicConfig`, bypassing `RequestContextFilter`

**File:** `backend/app/crawlers/ecs_runner.py:34-39`, `backend/app/crawlers/ecs_rescrape_runner.py:35-40`, `backend/app/crawlers/runner.py:52-57`
**Issue:** All three files call `logging.basicConfig(...)` at module import. `main.py` configures the root logger with `RequestContextFilter` (and a custom formatter), but ECS runners and the CLI runner install their own basic config without the filter. This reinforces IN-03: even if ContextVars were set, the log format `"%(asctime)s [%(levelname)s] %(name)s: %(message)s"` doesn't include `request_id` / `user_id`. The OBS-04 regression test only guards in-request-scope records against the app logger format (`main.py`).
**Fix:** Consolidate logging setup into a shared helper (e.g. `app/core/logging.py` — which already exists and provides `make_formatter`/`LOG_FORMAT`) that both the web app and ECS/CLI entry points call. Ensure `RequestContextFilter` is attached regardless of entry point.

### IN-05: `_notify_completion` may be skipped on failure path in ECS rescrape runner

**File:** `backend/app/crawlers/ecs_rescrape_runner.py:155-163`
**Issue:** On the exception path:
```python
except Exception:
    if job_id is not None:
        try:
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            _notify_completion(db, job_id)  # skipped if fail_job raises
        except Exception:
            logger.exception("Failed to update job #%s on failure", job_id)
```
If `fail_job` raises (DB connection dead, serialization error, etc.), `_notify_completion` is skipped and superadmins are never emailed. `_notify_completion` itself is already "best-effort — never raises" so there's no reason to gate it behind `fail_job`.
**Fix:** Make the two calls independent:
```python
except Exception:
    logger.exception("ECS archive rescrape task failed")
    if job_id is not None:
        try:
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
        except Exception:
            logger.exception("Failed to update job #%s on failure", job_id)
        _notify_completion(db, job_id)  # always attempt notification
    sys.exit(1)
```
The same pattern applies in `ecs_runner.py:157-165` for consistency.

### IN-06: Redundant `Sentry.captureException` alongside default Sentry console integration

**File:** `frontend/src/components/common/ErrorBoundary.tsx:25-28`
**Issue:** `componentDidCatch` calls both `console.error('ErrorBoundary caught an error:', error, errorInfo);` and `Sentry.captureException(error, { extra: { componentStack: errorInfo.componentStack } });`. If Sentry's `ConsoleLoggingIntegration` (or any console breadcrumb/capture integration) is enabled by default in @sentry/react v10, the console.error call may produce a second breadcrumb/event for the same error. The explicit `Sentry.captureException` is the canonical call (matches the test expectation), so the console.error can stay as a dev-console artifact — but if Sentry captures it as a separate error, operators see duplicates.

Given the fixed sampling config (`replaysOnErrorSampleRate: 1.0`) and that sibling `AuthContext.tsx` also has a `console.error('Auth check failed:', error)` for non-401 errors, the behavior should be verified in a real staging run to ensure only one Sentry event is produced per ErrorBoundary trigger.

**Fix:** Either confirm (document in a comment) that the console.error is purely a dev-tools artifact and is not captured by Sentry's default integrations, or add explicit Sentry integration configuration:
```typescript
Sentry.init({
  // ... existing ...
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration({ ... }),
    // Explicit: do NOT treat console.error as a capturable event.
    // Sentry's default console integration only produces breadcrumbs (not events),
    // so duplicate events are unlikely — but pin it to be safe.
  ],
});
```

---

_Reviewed: 2026-04-22T23:32:43Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
