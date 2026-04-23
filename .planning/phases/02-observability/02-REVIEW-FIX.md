---
phase: 02-observability
fixed_at: 2026-04-23T05:42:04Z
review_path: .planning/phases/02-observability/02-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 2 (Observability): Code Review Fix Report

**Fixed at:** 2026-04-23T05:42:04Z
**Source review:** `.planning/phases/02-observability/02-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (all 3 warnings; no criticals; info deferred per `fix_scope=critical_warning`)
- Fixed: 3
- Skipped: 0

All in-scope warnings were applied cleanly. The full backend test suite (`pytest -n auto`) passes: 2283 passed, 8 skipped, no regressions.

## Fixed Issues

### WR-01: `bool()` on JSON values silently converts string "false" to True

**Files modified:** `backend/app/crawlers/ecs_runner.py`
**Commit:** b3ef5c9
**Applied fix:** Added a module-level `_coerce_bool` helper that handles the three JSON cases (bool -> bool, string -> `.lower() in ("true","1","yes")`, other -> `bool(v)`), and rewired the `skip_known_urls_by_adapter` dict comprehension to use it. Mirrors the `.lower() in (...)` pattern already used for the sibling `CRAWLER_PARALLEL` / `CRAWLER_SKIP_KNOWN_URLS` env vars. Inline comment cross-references WR-01 so future editors understand why `bool()` cannot be used directly.

### WR-02: Malformed UUID env vars bypass job-failure notification in ECS runners

**Files modified:** `backend/app/crawlers/ecs_runner.py`, `backend/app/crawlers/ecs_rescrape_runner.py`
**Commit:** 623a32f
**Applied fix:** Restructured both ECS entry points so that only `JOB_ID` is parsed outside the main `try/except` (with its own `ValueError` handler that exits early — no job row exists to update). All other env parsing — `CRAWLER_DEFAULT_CATEGORY_ID`, `CRAWLER_USER_ID`, the JSON-valued env vars in `ecs_runner.py`, the `adapters` / `limits` / `delays` parsing — now lives inside the main try block. A malformed UUID or missing required value therefore raises inside the block, `fail_job` updates the BackgroundJob row with the traceback, and `_notify_completion` emails superadmins. Also made `_notify_completion` independent of `fail_job` in both runners' failure handlers (per IN-05 guidance) so the superadmin email fires even if the DB update itself raises. `ecs_rescrape_runner.py` already had a nested try for `fail_job`; `ecs_runner.py` previously didn't, and now does.

### WR-03: Legacy `int()` cast on CRAWLER_USER_ID mismatches current UUID-based User model

**Files modified:** `backend/app/crawlers/runner.py`
**Commit:** 245b6b0
**Applied fix:** Replaced the `int(raw)` cast in `_get_crawler_user`'s legacy-env-var fallback with `UUID(raw)`, matching the UUID-based `User.id` schema used by the primary path (`is_service_account.is_(True)` filter) and by `resolve_crawler_user` above. Updated the error message from "must be an integer." to "must be a valid UUID." so operators setting a UUID string with a typo receive an accurate diagnostic. Kept the `CrawlerConfigError` type and `from exc` chaining intact. Added an inline WR-03 comment explaining why the fallback was vestigial (the primary service-account lookup covers the normal case; the env fallback survives only for local CLI usage before the startup seed runs).

---

_Fixed: 2026-04-23T05:42:04Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
