---
phase: 07-v1-residue-cleanup
plan: 03
subsystem: testing

tags: [pytest, sqlalchemy-2.0, dead-code, common-patterns, conftest, select, scalars]

# Dependency graph
requires:
  - phase: 03-non-breaking-internal
    provides: "test_runner_breaker.py + test_circuit_breaker.py replacement tests (referenced by Task 1 stub deletion)"
  - phase: 04-db-parts-hardening
    provides: "Phase 4 WR-01 audit flagged 6 residual db.query sites in conftest.py (scope was backend/app/ only; Task 3 closes the test-helpers gap)"
provides:
  - "Slimmed common_patterns.py (965 → 537 lines, 428 lines of dead code removed)"
  - "Zero legacy db.query() call sites remain in backend/tests/conftest.py (SQLAlchemy 2.0 migration complete for test helpers)"
  - "test_runner_circuit_breaker.py stub removed; misleading pytest skip marker silenced"
affects: [08-documentation-drift-sync, future-refactors-touching-common_patterns]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLAlchemy 2.0 select()+scalars() style now universal across backend/app/ AND backend/tests/ (was app-only before this plan)"
    - "Dead-code pruning pattern: grep-verify zero external callers → delete function + prune unused imports → pyright + pytest"

key-files:
  created: []
  modified:
    - "backend/tests/crawlers/test_runner_circuit_breaker.py (DELETED — deprecated zero-test stub)"
    - "backend/app/api/utils/common_patterns.py (-428 lines, 11 dead helpers removed)"
    - "backend/tests/conftest.py (+23/-12 lines, 6 db.query sites migrated to select()+scalars())"

key-decisions:
  - "All 11 helpers in common_patterns.py with zero external callers were deleted; 13 live helpers + IN-03 re-export preserved"
  - "get_current_user unused-import warning surfaced by pyright after deleting common dependency helpers — pruned alongside Query/Tuple/HasUserId/get_current_admin_user"
  - "Stale comment at conftest.py:391 referenced '8 residual 1.x db.query() calls' — updated to reflect the actual 6 migrated in this plan (the audit number was pre-split count; 2 of the original 8 were already deleted upstream)"
  - "Substring match on literal 'db.query()' in the updated comment causes `grep -c \"db.query(\"` to return 1 (the comment itself); precise anti-comment regex `grep -cE '^[^#]*\\b(db|db_session)\\.query\\(' backend/tests/conftest.py` returns 0 — acceptance-criterion spirit met"

patterns-established:
  - "Zero-caller verification must be re-run immediately before deletion (not just at planning time) — protects against new callers landing between planning and execution"
  - "When pruning helpers, prune now-unused imports in the same commit to keep pyright clean"

requirements-completed: []
tech_debt_items_closed: [TD-03-01, TD-03-02, TD-04-WR01-conftest]

# Metrics
duration: 12min
completed: 2026-04-24
---

# Phase 07 Plan 03: Dead Code Cleanup Summary

**One-shot cleanup: deleted test_runner_circuit_breaker.py stub, removed 11 zero-caller helpers (428 lines) from common_patterns.py, and migrated the final 6 legacy db.query sites in conftest.py to SQLAlchemy 2.0 select()+scalars() style**

## Performance

- **Duration:** ~12 min (effective; initial minutes lost to working in wrong worktree directory — see Issues)
- **Started:** 2026-04-24T06:40:31Z
- **Completed:** 2026-04-24T06:52:21Z
- **Tasks:** 3
- **Files modified:** 3 (1 deleted, 1 slimmed, 1 modernized)

## Accomplishments

- Deleted `backend/tests/crawlers/test_runner_circuit_breaker.py` — 21-line deprecated stub that emitted a misleading pytest skip marker. Replacement coverage lives in `test_runner_breaker.py` (3 integration tests) + `test_circuit_breaker.py` (3 unit tests), both confirmed collecting.
- Removed 11 dead helpers from `backend/app/api/utils/common_patterns.py` (all grep-verified zero external callers immediately before deletion): `get_standard_pagination_params`, `get_standard_endpoint_dependencies`, `verify_entity_ownership_or_admin`, `get_paginated_response`, `verify_ownership`, `build_sorted_query`, `get_common_dependencies`, `get_admin_dependencies`, `handle_vote_operation`, `remove_vote_operation`, `handle_report_creation`. File shrank 965 → 537 lines.
- Pruned now-unused imports surfaced after helper removal: `Query` (fastapi), `Tuple` (typing), `HasUserId` (app.api.protocols), `get_current_admin_user` and `get_current_user` (app.api.dependencies.auth). pyright clean (0 errors, 0 warnings).
- Migrated the last 6 legacy `db.query(...)` / `db_session.query(...)` call sites in `backend/tests/conftest.py` to `select()` + `scalars()` style: 1 in `get_default_category_id`, 2 in `create_car_in_db`, 3 in `create_car_orm_in_db` (including a joinedload-hydrated CarGeneration reload).
- Updated the stale `IN-11` comment in conftest.py that referenced the pre-migration "8 residual 1.x db.query() calls tracked under WR-01" to reflect current state (0 legacy calls remain).
- Full pytest suite green after each task: 2363 passed, 8 skipped (baseline count for this worktree base commit). High-traffic consumers of the migrated car fixtures verified separately: `test_build_lists.py` 39 passed; `-k part` 343 passed / 2 skipped.

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete test_runner_circuit_breaker.py stub** — `985eefb` (chore)
2. **Task 2: Delete 11 dead helpers from common_patterns.py** — `7327e15` (refactor)
3. **Task 3: Migrate 6 db.query sites in conftest.py to SQLAlchemy 2.0** — `8619e40` (refactor)

Commit revision base: `ea5d2cb` (worktree branch `worktree-agent-a32d7592cec9b3fa8`).

## Files Created/Modified

- `backend/tests/crawlers/test_runner_circuit_breaker.py` — DELETED (21-line stub)
- `backend/app/api/utils/common_patterns.py` — -428 lines; 11 dead helpers + 5 unused imports removed
- `backend/tests/conftest.py` — 6 db.query sites migrated to `db.scalars(select(...).where(...)).first()`; `select` added to `from sqlalchemy import ...`; stale IN-11 comment refreshed

## Decisions Made

- **Scope boundary respected:** Did not touch `backend/app/` during conftest.py migration — DATA-06 sweep already handled the app-side and the guard test (`test_session_query_regression.py`) scopes to `backend/app/` so test helpers were deliberately out of scope until now.
- **Pyright surfaced an additional unused import (`get_current_user`) that the plan did not explicitly list.** Removed it alongside the four planned imports to keep pyright clean — classed as Rule 3 (blocking: would fail pyright CI gate if left). Tracked as `[Rule 3 - Blocking]` in Deviations.
- **TypedDicts `PublicEndpointDeps`, `AuthenticatedEndpointDeps`, `AdminEndpointDeps` preserved** — plan listed them as keep-for-surviving-helpers; verified `get_standard_public_endpoint_dependencies` still references `PublicEndpointDeps`. The other two TypedDicts are not referenced internally but the plan explicitly said "keep" so they remain as documented dependency-injection return contracts.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Pruned one additional unused import beyond plan list**
- **Found during:** Task 2 (post-deletion pyright check)
- **Issue:** After deleting `get_common_dependencies` (the only remaining caller of `get_current_user`), pyright flagged `get_current_user` as unused import. Plan listed only 4 imports to prune (`Query`, `Tuple`, `HasUserId`, `get_current_admin_user`).
- **Fix:** Removed `get_current_user` from `from app.api.dependencies.auth import ...`, collapsing the line to `# (line removed entirely — no other auth imports used in file)`.
- **Files modified:** `backend/app/api/utils/common_patterns.py`
- **Verification:** `pyright backend/app/api/utils/common_patterns.py` → `0 errors, 0 warnings, 0 informations`.
- **Committed in:** `7327e15` (Task 2 commit)

**2. [Rule 1 - Acceptance-criterion literal vs. intent] Literal `db.query()` still matched by plan's grep-count criterion after comment update**
- **Found during:** Task 3 verification
- **Issue:** Plan's acceptance criterion `grep -c "db.query(\|db_session.query(" backend/tests/conftest.py` expects `0`, but the updated IN-11 comment (which the plan itself asked for) contains the literal string `db.query()` as documentation.
- **Fix:** Verified spirit of the criterion with a more precise regex that excludes comment lines: `grep -cE '^[^#]*\b(db|db_session)\.query\(' backend/tests/conftest.py` → `0`. The remaining `1` hit is the intentional comment reference documented in the plan's action block.
- **Files modified:** None (verification-only; no code change).
- **Verification:** `grep -cE '^[^#]*\b(db|db_session)\.query\(' backend/tests/conftest.py` returns `0`. No actual legacy query calls remain.
- **Committed in:** N/A (documentation of acceptance-criterion nuance, not a code change).

---

**Total deviations:** 2 (1 Rule 3 auto-fix; 1 acceptance-criterion nuance noted). No Rule 4 architectural changes.
**Impact on plan:** Both items are housekeeping — neither alters plan scope nor introduces new surface area. The pruned extra import keeps pyright CI gate green; the grep nuance is a test-of-spirit vs. test-of-literal resolution.

## Issues Encountered

- **Initial worktree misdirection:** First pass of all three tasks was accidentally executed in the main repository directory (`/home/tyler-webb/Documents/Github/CarModPicker`) rather than the assigned worktree at `.claude/worktrees/agent-a32d7592cec9b3fa8`, because I prepended `cd /home/tyler-webb/Documents/Github/CarModPicker && ...` to Bash commands. Recognized via `git worktree list` comparison + unexpected parallel-executor commits (07-04) appearing on the shared `main` branch mid-session. Resolution: (a) restored `common_patterns.py` in main (via `git restore`), leaving only the STATE.md modification there which is not mine; (b) the Task 1 commit `e719392` on main is a duplicate of this plan's Task 1 — it can be cherry-picked or rewound during orchestrator merge; (c) replayed all three tasks cleanly in the correct worktree. Final commits in worktree: `985eefb`, `7327e15`, `8619e40`. No work lost; no data corrupted.
- **Read-before-edit hook reminders firing on every Edit call:** The `PreToolUse:Edit` hook printed a reminder before every Edit operation regardless of whether the file had already been read — but the edits themselves succeeded. Noted, worked around by occasional re-reads; no functional blocker.
- **Unexpected modifications on main branch** to `backend/app/main.py` and `.planning/STATE.md` (not mine): these were produced by other parallel executors (07-04 lifespan `bg_log_context` wrap) working in the same shared main checkout. Left untouched per parallel-executor rules (don't modify shared orchestrator artifacts).

## User Setup Required

None — pure internal cleanup, no external services or environment variables touched.

## Next Phase Readiness

- Phase 07 success criterion 6 (dead-code cleanup) fully closed:
  - `test_runner_circuit_breaker.py` stub removed (Task 1)
  - `common_patterns.py` dead helpers deleted, file slimmed 44% (Task 2)
  - 6 residual legacy `db.query(...)` sites in `backend/tests/conftest.py` migrated (Task 3)
- `TD-03-01`, `TD-03-02`, `TD-04-WR01-conftest` all closed.
- Full pytest suite remains green (2363 passed, 8 skipped at this worktree's base commit); no regressions introduced.
- pyright clean on all touched files.
- No blockers for subsequent Phase 07 plans (07-04 integration advisory A01, 07-05 nyquist-validation close, 07-06 documentation drift sync) — they do not depend on any of the removed helpers or touched files.

## Self-Check

Verification commands ran after SUMMARY.md was drafted:

- `[ -f backend/tests/crawlers/test_runner_circuit_breaker.py ]` → FILE GONE (correct)
- `git log --all | grep -q 985eefb` → FOUND: 985eefb (Task 1 commit)
- `git log --all | grep -q 7327e15` → FOUND: 7327e15 (Task 2 commit)
- `git log --all | grep -q 8619e40` → FOUND: 8619e40 (Task 3 commit)
- `wc -l backend/app/api/utils/common_patterns.py` → 537 (pre-change was 965; 428 removed, above 200-line floor)
- `grep -c "^def " backend/app/api/utils/common_patterns.py` → 13 (all live helpers per plan, admin_only included)
- `grep -cE '^[^#]*\b(db|db_session)\.query\(' backend/tests/conftest.py` → 0 (zero legacy live calls)

## Self-Check: PASSED

---
*Phase: 07-v1-residue-cleanup*
*Completed: 2026-04-24*
