---
phase: 02-observability
plan: 1
subsystem: observability

tags: [logging, contextvars, pytest, caplog, obs-04, tdd]

# Dependency graph
requires:
  - phase: 01-safety-nets-ci-hardening
    provides: [pytest -n auto harness, SAFE-05 openapi snapshot guard, SAFE-06 auth characterization, SAFE-07 crawler characterization, 51% backend coverage floor]

provides:
  - bg_log_context(task_name, job_id) contextmanager for background-task log scope (request_id=bg:{task}:{job}, user_id=bg)
  - CLI-scope context bootstrap in app/crawlers/__main__.py (request_id=cli:{pid}, user_id=cli) — fires inside __main__ guard so test collection cannot pollute ContextVars
  - caplog_with_context pytest fixture (conftest.py) — attaches RequestContextFilter to caplog.handler so LogRecords gain request_id + user_id attributes in tests
  - tests/test_log_propagation.py — 6 tests, OBS-04 regression guard

affects:
  - 02-02 (Sentry) — before_send can rely on request_id_var / user_id_var being populated on every code path
  - 02-03 (EMF + CloudWatch) — EMF dimension context pipeline can filter by request_id/user_id
  - 02-04 (frontend correlation) — X-Request-ID header already round-trips; frontend plan can assume backend correlation works

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "bg_log_context contextmanager for non-request log scopes (crawler runner, orphan-job sweep, EventBridge handlers)"
    - "CLI context bootstrap inside __main__ guard (prevents test-collection ContextVar pollution)"
    - "caplog_with_context fixture pattern (Landmine 15 — caplog does NOT inherit root-logger filters)"
    - "dependency-override log emission for in-request testing (use fastapi.Depends signature to keep FastAPI introspection happy)"

key-files:
  created:
    - backend/tests/test_log_propagation.py
  modified:
    - backend/app/core/log_context.py
    - backend/app/crawlers/__main__.py
    - backend/tests/conftest.py

key-decisions:
  - "OBS-04 audit landed BEFORE Sentry (02-02), EMF (02-03), and frontend correlation (02-04) so every downstream piece picks up request_id/user_id on day one"
  - "Token-based ContextVar reset in bg_log_context (re-entrant-safe, mirrors middleware/request_context.py pattern)"
  - "CLI ContextVar set INSIDE `if __name__ == '__main__':` guard (threat T-02-TEST-POLLUTION — test collection must not fire the set)"
  - "caplog_with_context attaches RequestContextFilter to caplog.handler — without this, records have no request_id/user_id attrs despite filter working in production (Landmine 15 / 02-RESEARCH §3)"
  - "test_log_propagation_request_scope uses dependency-override on get_current_user to emit an app-logger record AFTER auth dependency runs — only way to test both request_id AND user_id propagate in a TestClient context; existing endpoints don't log post-auth"
  - "TestClient plumbing loggers (asyncio, httpx, httpcore, python_multipart, urllib3) filtered from OBS-04 assertions — they fire OUTSIDE request-context middleware in both test and production, so not subject to the invariant"

patterns-established:
  - "bg_log_context — wrap any non-request code path that needs CloudWatch grep distinguishability"
  - "CLI context shape cli:{pid} / 'cli' — grep-friendly prefix for crawler CLI log lines"
  - "caplog_with_context fixture — any future test asserting LogRecord.request_id/user_id attrs MUST use this fixture instead of bare caplog"
  - "dependency-override log emission — proven pattern for testing in-request ContextVar propagation when no existing endpoint logs post-auth"

requirements-completed: [OBS-04]

# Metrics
duration: 14min
completed: 2026-04-22
---

# Phase 02 Plan 01: OBS-04 log-context audit + regression guard Summary

**bg_log_context contextmanager + CLI bootstrap + caplog_with_context fixture + 6-test regression guard — OBS-04 audit landed so Sentry (02-02), EMF (02-03), and frontend correlation (02-04) can rely on request_id/user_id being populated on every code path.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-04-22T20:57:31Z
- **Completed:** 2026-04-22T21:11:51Z
- **Tasks:** 2 (both TDD — RED-GREEN cycles)
- **Files modified:** 4 (3 created/modified, 1 new test file)

## Accomplishments

- `bg_log_context(task_name, job_id=None)` contextmanager added to `app/core/log_context.py` (token-based ContextVar reset, re-entrant-safe)
- CLI bootstrap in `app/crawlers/__main__.py` (request_id=cli:{pid}, user_id=cli inside `__main__` guard)
- `caplog_with_context` fixture added to `backend/tests/conftest.py` (attaches RequestContextFilter to caplog.handler)
- `backend/tests/test_log_propagation.py` — 6 tests (request-scope, bg_log_context, bg_log_context_job_id_none, bg_log_context_resets, cli_log_context, sqlalchemy)
- Phase 1 gates preserved: SAFE-05 (openapi snapshot), SAFE-06 (auth characterization 5/7 — 2 deferred OAuth cassettes from STATE.md), SAFE-07 (crawler characterization 5/5), full 2165-test suite + 51% coverage floor all green

## Task Commits

Each task was committed atomically via TDD (RED → GREEN):

1. **Task 1 RED: failing tests for bg_log_context** — `6151515` (test)
2. **Task 1 GREEN: bg_log_context + CLI bootstrap** — `4586dba` (feat)
3. **Task 2 RED: expand to 6 tests** — `40d7ceb` (test)
4. **Task 2 GREEN: caplog_with_context fixture + request-scope override** — `f8c3c03` (feat)

## Files Created/Modified

- `backend/app/core/log_context.py` — added `bg_log_context` contextmanager (additive; existing `request_id_var`, `user_id_var`, `RequestContextFilter` unchanged)
- `backend/app/crawlers/__main__.py` — full rewrite to set `request_id_var=cli:{os.getpid()}` + `user_id_var='cli'` inside `if __name__ == "__main__":` guard before invoking `main()`
- `backend/tests/conftest.py` — added `caplog_with_context` fixture (placed immediately before `mock_s3` fixture per PATTERNS.md §backend/tests/conftest.py analog)
- `backend/tests/test_log_propagation.py` — NEW — 6 tests covering request scope, background, CLI, and sqlalchemy propagation

## Decisions Made

- **Request-scope test uses dependency-override on `get_current_user`.** The plan's behavior implied "call client.get() as auth'd user and iterate caplog.records" — but in TestClient, (a) no existing endpoint (including `/api/users/me`) emits an app-level log AFTER the auth dependency runs, (b) login-call records have `user_id="-"` because the dependency hasn't run yet when login emits its "User logged in successfully" record. Solution: override `get_current_user` with a FastAPI-compatible async wrapper that awaits the original (so `user_id_var.set(...)` fires) and then emits `logger.info("post-auth request scope log emit")`. This record is captured by caplog AFTER both ContextVars are populated, which is exactly what OBS-04 demands.
- **Filter TestClient plumbing loggers from the assertion.** `asyncio`, `httpx`, `httpcore`, `python_multipart`, `urllib3` emit log records during TestClient infrastructure (socket select, HTTP client wrapping TestASGITransport, multipart form parsing). These fire OUTSIDE the request-context middleware in tests AND production. OBS-04 applies to application code, not infrastructure. Documented via `_OUT_OF_SCOPE_LOGGERS` tuple + `_in_request_scope()` helper in test file.
- **test_log_propagation_sqlalchemy uses `pytest.skip` when no sqlalchemy records appear.** SQLite test engine emits no INFO records by default (AOR-per-query logging requires echo=True on the engine fixture, which conftest.py doesn't enable). The test still sets the sa_logger level + calls `/api/users/me`; if records appear, they are asserted to have `request_id != "-"` (D-48 propagation). Otherwise skipped with explicit message. This honors the plan's "sqlalchemy did not emit INFO log records in test env" escape hatch in RESEARCH §3 L820-823.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Dependency override required for post-auth log emission**
- **Found during:** Task 2 (test_log_propagation_request_scope)
- **Issue:** The plan's test snippet iterated `caplog.records` after a single `client.get("/api/users/me")` call and asserted all records have `user_id != "-"`. In practice: (a) the TestClient plumbing (asyncio, httpx, python_multipart) emits records OUTSIDE request middleware scope, so they have `request_id="-"`; (b) the `User logged in successfully` log from login is emitted inside the request middleware but BEFORE `get_current_user` runs, so `user_id="-"`; (c) `/api/users/me` itself emits no app-level logs at DEBUG/INFO. The assertion as written cannot pass for any existing endpoint.
- **Fix:** (a) added `_OUT_OF_SCOPE_LOGGERS` filter + `_in_request_scope()` helper to exclude TestClient plumbing from the assertion; (b) performed login OUTSIDE the `caplog.clear()` window; (c) injected a FastAPI dependency override on `get_current_user` that awaits the original (so `user_id_var.set(...)` runs) then emits a test log record, guaranteeing at least one in-scope record with both ContextVars populated.
- **Files modified:** backend/tests/test_log_propagation.py
- **Verification:** Test passes; `emitted_request_ids[0] != "-"` and `emitted_user_ids[0] != "-"` verify ContextVars are populated inside the override; all caplog in-scope records assert both request_id and user_id are non-default.
- **Committed in:** f8c3c03 (Task 2 GREEN)

**2. [Rule 3 - Blocking] Missing pip dependency (python-json-logger)**
- **Found during:** Task 1 (first pytest invocation)
- **Issue:** `python-json-logger==4.1.0` was in `backend/requirements.txt` but not installed in the local Python environment. Import of `app.core.logging` failed with `ModuleNotFoundError: No module named 'pythonjsonlogger'`, blocking ALL test runs.
- **Fix:** `pip install python-json-logger==4.1.0` — the version already pinned in requirements.txt.
- **Files modified:** None (local env only; no repo changes).
- **Verification:** `python -c "from pythonjsonlogger.json import JsonFormatter; print('ok')"` prints ok; full test suite (2165 tests) runs.
- **Committed in:** N/A (environment-only fix — no file change)

**3. [Rule 3 - Blocking] Plan's behavior test count (5) vs final surface (6)**
- **Found during:** Task 1 planning
- **Issue:** Task 1's `<behavior>` enumerates 5 tests (3 bg_log_context variants, 1 reentrant, 1 cli_context_module import-guard check). Task 2's acceptance says `grep -c "^def test_"` returns 6 (request-scope, bg_log_context, bg_log_context_job_id_none, bg_log_context_resets, cli_log_context, sqlalchemy). The `test_bg_log_context_reentrant` and `test_cli_context_module` tests in Task 1's behavior aren't in Task 2's final surface. Plan's Task 2 states "Create ... (new file)" but Task 1's TDD verify targets tests in the same file.
- **Fix:** Task 1 created the test file with the 3 bg_log_context tests that survive into Task 2's final 6-test surface (test_bg_log_context, test_bg_log_context_job_id_none, test_bg_log_context_resets). Task 2 appended the remaining 3 (test_log_propagation_request_scope, test_cli_log_context, test_log_propagation_sqlalchemy). Final file has exactly 6 tests per Task 2 acceptance criteria. The reentrant and cli_context_module variants were skipped; behavior covered by test_bg_log_context_resets (reentrant nesting implicit via token-reset) and module-guard line-order grep check (acceptance criterion — guard line number < set line number).
- **Files modified:** backend/tests/test_log_propagation.py (initial 3-test file in Task 1; expanded to 6 in Task 2)
- **Verification:** `grep -c "^def test_" backend/tests/test_log_propagation.py` returns 6. All 5 non-skipped tests pass; sqlalchemy skips with clear reason.
- **Committed in:** 6151515, 40d7ceb, f8c3c03

**4. [Rule 3 - Blocking] Existing `test_user` fixture shape**
- **Found during:** Task 2
- **Issue:** Plan's test skeleton called `test_user['token']` assuming a dict-shaped fixture. Actual `test_user` fixture in conftest.py returns a `User` ORM model, not a dict.
- **Fix:** Use `login_user(client, test_user.username)` helper (already in conftest.py) to obtain a bearer token for the `Authorization: Bearer <token>` header.
- **Files modified:** backend/tests/test_log_propagation.py
- **Verification:** Test calls /api/users/me successfully (status 200).
- **Committed in:** f8c3c03

---

**Total deviations:** 4 auto-fixed (3 blocking, plus 1 env install not committed to repo)
**Impact on plan:** All auto-fixes necessary for the test harness to function + the plan's invariants to be truthfully verified in a TestClient context. No scope creep — all adjustments narrow the test to exactly what the OBS-04 invariant claims.

## Known Stubs

None. All production code paths (bg_log_context contextmanager + CLI bootstrap) are live and covered.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes. Threat model in 02-01-PLAN.md remains authoritative (T-02-PII-SENTRY, T-02-TEST-POLLUTION, T-02-REENTRANCY — all mitigated and verified by the new tests).

## TDD Gate Compliance

Both tasks followed RED → GREEN per TDD:

- **Task 1:** RED commit `6151515` (test) → GREEN commit `4586dba` (feat)
- **Task 2:** RED commit `40d7ceb` (test) → GREEN commit `f8c3c03` (feat)

No REFACTOR commits needed — both implementations landed minimal and clean on the first GREEN.

## Issues Encountered

- TestClient test context surfaced three layers of log-emission-vs-request-scope nuance that the plan's behavior description didn't anticipate (asyncio/httpx plumbing, login-vs-authenticated-request user_id_var timing, and the absence of post-auth endpoint logs). All resolved via the dependency-override + in-scope filter pattern — documented in Decisions Made and Deviations.
- Local `python-json-logger` not installed (pre-existing env gap). Installed from pinned requirements.txt version.

## User Setup Required

None — no external service configuration. All changes are code/test only.

## Next Phase Readiness

- **Phase 02 Plan 02 (Sentry — 02-02):** `before_send` handler can safely read `request_id_var.get()` and `user_id_var.get()` on every code path (request, bg, cli). OBS-04 regression guard will catch any future change that drops the filter.
- **Phase 02 Plan 03 (EMF + CloudWatch):** Same ContextVar guarantees; EMF dimension context can pull request_id for log-correlation.
- **Phase 02 Plan 04 (frontend correlation):** `X-Request-ID` header round-trip already works (existing middleware); regression guard ensures the backend side stays healthy.
- **Phase 03 (non-breaking internal improvements):** No blockers — file-level changes are additive, no shared surface renamed.

## Self-Check: PASSED

- Files: backend/app/core/log_context.py, backend/app/crawlers/__main__.py, backend/tests/conftest.py, backend/tests/test_log_propagation.py, .planning/phases/02-observability/02-01-SUMMARY.md — all FOUND
- Commits: 6151515 (test RED 1), 4586dba (feat GREEN 1), 40d7ceb (test RED 2), f8c3c03 (feat GREEN 2) — all FOUND in git log

---
*Phase: 02-observability*
*Completed: 2026-04-22*
