---
phase: 02-observability
fixed_at: 2026-04-23T05:51:21Z
review_path: .planning/phases/02-observability/02-REVIEW.md
iteration: 2
findings_in_scope: 9
fixed: 8
skipped: 1
status: all_fixed
---

# Phase 2 (Observability): Code Review Fix Report

**Fixed at:** 2026-04-23T05:51:21Z
**Source review:** `.planning/phases/02-observability/02-REVIEW.md`
**Iteration:** 2 (cumulative with iteration 1 warnings)

**Summary:**
- Findings in scope: 9 (3 warnings + 6 info; no criticals)
- Fixed: 8 (3 warnings in iteration 1; 5 info in iteration 2)
- Skipped (already-fixed): 1 (IN-05 was absorbed by the WR-02 fix in iteration 1)

Iteration 1 (`fix_scope=critical_warning`) resolved all three warnings on 2026-04-23T05:42:04Z. Iteration 2 (`fix_scope=all`) resolved the six info findings; IN-05 was already in place from the WR-02 restructure in iteration 1 and required no additional change.

Verification:
- Backend: `pytest -n auto` from `backend/` — 2283 passed, 8 skipped, 0 regressions.
- Frontend: `npm test --run` from `frontend/` — 32 passed (4 test files), 0 regressions. Required a `npm install` refresh because `@sentry/react` was missing from the local `node_modules/` (stale install from before Phase 2 added the dep to `package.json`); the install issue is environmental, not caused by any fix in this report.

## Fixed Issues

### WR-01: `bool()` on JSON values silently converts string "false" to True

**Files modified:** `backend/app/crawlers/ecs_runner.py`
**Commit:** b3ef5c9 (iteration 1)
**Applied fix:** Added a module-level `_coerce_bool` helper that handles the three JSON cases (bool -> bool, string -> `.lower() in ("true","1","yes")`, other -> `bool(v)`), and rewired the `skip_known_urls_by_adapter` dict comprehension to use it. Mirrors the `.lower() in (...)` pattern already used for the sibling `CRAWLER_PARALLEL` / `CRAWLER_SKIP_KNOWN_URLS` env vars. Inline comment cross-references WR-01 so future editors understand why `bool()` cannot be used directly.

### WR-02: Malformed UUID env vars bypass job-failure notification in ECS runners

**Files modified:** `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`
**Commit:** 623a32f (iteration 1)
**Applied fix:** Restructured both ECS entry points so that only `JOB_ID` is parsed outside the main `try/except` (with its own `ValueError` handler that exits early — no job row exists to update). All other env parsing — `CRAWLER_DEFAULT_CATEGORY_ID`, `CRAWLER_USER_ID`, the JSON-valued env vars in `ecs_runner.py`, the `adapters` / `limits` / `delays` parsing — now lives inside the main try block. A malformed UUID or missing required value therefore raises inside the block, `fail_job` updates the BackgroundJob row with the traceback, and `_notify_completion` emails superadmins. Also made `_notify_completion` independent of `fail_job` in both runners' failure handlers (per IN-05 guidance) so the superadmin email fires even if the DB update itself raises. This independent-notification pattern is the reason IN-05 needed no iteration-2 work.

### WR-03: Legacy `int()` cast on CRAWLER_USER_ID mismatches current UUID-based User model

**Files modified:** `backend/app/crawlers/runner.py`
**Commit:** 245b6b0 (iteration 1)
**Applied fix:** Replaced the `int(raw)` cast in `_get_crawler_user`'s legacy-env-var fallback with `UUID(raw)`, matching the UUID-based `User.id` schema used by the primary path (`is_service_account.is_(True)` filter) and by `resolve_crawler_user` above. Updated the error message from "must be an integer." to "must be a valid UUID." so operators setting a UUID string with a typo receive an accurate diagnostic. Kept the `CrawlerConfigError` type and `from exc` chaining intact. Added an inline WR-03 comment explaining why the fallback was vestigial (the primary service-account lookup covers the normal case; the env fallback survives only for local CLI usage before the startup seed runs).

### IN-01: `start_ts` and `t0` are redundant aliases

**Files modified:** `backend/app/crawlers/runner.py`
**Commit:** cdb9926 (iteration 2)
**Applied fix:** Collapsed the `start_ts = time.monotonic(); t0 = start_ts` pair into a single `t0 = time.monotonic()` assignment, and updated the `emit_crawler_run_metrics(elapsed_seconds=time.monotonic() - start_ts)` call to use `- t0` instead. The consolidated comment now explicitly calls out both consumers (EMF emit at line 708 + return-dict `elapsed_seconds` at line 759) referencing the same anchor. Matches the reviewer's preferred "one name + comment" form; the prior aliasing is noted in the comment as IN-01 historical context.

### IN-02: Inconsistent boolean env-var parsing patterns across `ecs_runner.py`

**Files modified:** `backend/app/crawlers/ecs_runner.py`
**Commit:** 9646469 (iteration 2)
**Applied fix:** Extracted an `_env_bool(name, default)` helper at module scope that reads the env var and returns `raw.strip().lower() in ("true", "1", "yes")` when set, else the `default`. Replaced the existing `CRAWLER_PARALLEL` (negative predicate, default True) and `CRAWLER_SKIP_KNOWN_URLS` (positive predicate, default False) parse lines with calls to the helper. Both callsites now share the same truthy vocabulary (`"true"`/`"1"`/`"yes"`); values like `"maybe"` are now consistently falsy for both vars (previously `"maybe"` mapped to True for PARALLEL but False for SKIP_KNOWN_URLS). Default-True vs default-False semantics preserved via the helper's `default=` keyword. The `_env_bool` docstring cross-references IN-02 and notes the semantic alignment with `_coerce_bool` (which handles the JSON-decoded per-adapter override maps).

### IN-03: ECS runners do not set `request_id_var` for log context

**Files modified:** `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`
**Commit:** 76fe6ed (iteration 2)
**Applied fix:** At the top of each ECS runner's `main()` (immediately after the `JOB_ID` parse so the job UUID can be interpolated), added explicit `request_id_var.set(f"ecs:{os.getpid()}:{job_id or '-'}")` and `user_id_var.set("ecs")` calls. Chose the explicit `set` over wrapping the body in `bg_log_context` because ECS tasks are single-shot and never re-enter the scope — the re-entrant-safe reset semantics of the context manager are not needed. Matches the `cli:<pid>` / `cli` pattern in `__main__.py` so App Runner / CLI / ECS log streams each carry a distinct prefix convention for CloudWatch grepping. Import of `request_id_var` / `user_id_var` moved inside `main()` (function-scoped like the other late imports) to preserve the no-side-effects-on-import invariant that keeps test collection and the Sentry init path clean.

### IN-04: ECS runners use their own `logging.basicConfig`, bypassing `RequestContextFilter`

**Files modified:** `backend/app/core/logging.py`, `backend/app/crawlers/runner.py`, `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`
**Commit:** 33ed717 (iteration 2)
**Applied fix:** Added a new `configure_root_logging(level=logging.INFO)` helper in `app/core/logging.py` that (1) calls `logging.basicConfig` with the shared `LOG_FORMAT` (which includes `[req=%(request_id)s user=%(user_id)s]`), (2) applies `make_formatter()` (JSON in non-TTY production, colorized text locally), and (3) attaches `RequestContextFilter` to every handler on the root logger. The helper is idempotent — duplicate `RequestContextFilter` instances on the same handler are avoided via an `isinstance` check, so repeated calls in a single process (tests, re-imports) don't stack filters. Replaced the three bespoke `logging.basicConfig` blocks in `runner.py`, `ecs_runner.py`, and `ecs_rescrape_runner.py` with a call to the new helper. The entry points now share `main.py`'s formatter choice and filter wiring, closing the IN-03 loop (the ContextVars set there now actually appear in emitted log records). Verified by running `pytest -n auto tests/test_log_propagation.py` (5 passed, 1 skipped — the regression guard for `RequestContextFilter` propagation still passes).

### IN-06: Redundant `Sentry.captureException` alongside default Sentry console integration

**Files modified:** `frontend/src/components/common/ErrorBoundary.tsx`
**Commit:** ce7555f (iteration 2)
**Applied fix:** Chose the less-invasive documentation option (the reviewer's first fix alternative) because the second option — verifying the behavior in a real staging run — is not accessible from this fix pass. Added a multi-line comment inside `componentDidCatch` explaining that (a) `Sentry.captureException` is the canonical reporting path (its presence is asserted by `ErrorBoundary.test.tsx`), and (b) under `@sentry/react` v10's default console integration the `console.error` call produces only a breadcrumb, not a separate event, so a single ErrorBoundary trigger still yields exactly one Sentry event. The breadcrumb is retained intentionally because it carries the raw React `errorInfo` argument (which `captureException`'s `extra.componentStack` only captures as a string). No behavior change; `npm test --run` confirms both `ErrorBoundary.test.tsx` (2 tests) and `sentry.test.ts` (19 tests) still pass.

## Already-Fixed Issues (no iteration-2 action required)

### IN-05: `_notify_completion` may be skipped on failure path in ECS rescrape runner

**Files examined:** `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`
**Status:** Already fixed by commit 623a32f (iteration 1, under WR-02).
**Verification:** Spot-checked the except paths in both runners. `ecs_rescrape_runner.py:185-195` calls `_notify_completion(db, job_id)` independently of the inner `try: job_service.fail_job ... except: logger.exception(...)` block. `ecs_runner.py:242-256` has the same structure (inner try for `fail_job`, outer `_notify_completion` call). In both files the comment "call it independently of fail_job so superadmins are emailed even if the DB update failed (mirrors IN-05 pattern)" documents the intent. No additional change needed.

---

_Fixed: 2026-04-23T05:51:21Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
