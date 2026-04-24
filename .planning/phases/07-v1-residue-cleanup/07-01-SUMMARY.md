---
phase: 07-v1-residue-cleanup
plan: 01
subsystem: testing
tags: [pytest, regression, concurrency, sqlalchemy, postgres, fastapi, uuid]

# Dependency graph
requires:
  - phase: 04-db-parts-hardening
    provides: "WR-02 sorted(lock_ids) fix in part_linker_service.py, WR-03 UUID(raw) fix in crawlers/runner.py, WR-04 %s log-format fix in core/init_service_accounts.py, IN-02 cap enforcement in copy_build_list"
provides:
  - "Regression pin for WR-04 (init_crawler_service_account cold-start log formatting)"
  - "Regression pin for WR-03 (CRAWLER_USER_ID UUID fallback in _get_crawler_user)"
  - "Regression pin for WR-02 (deterministic row-lock ordering across reelect_canonical/link_new_part/unlink_part)"
  - "Regression pin for IN-02 (free-tier 1-list cap enforced at copy path)"
  - "WR-01 sanity assertion (pytest.ini testpaths = tests, NOT app/tests)"
affects: [07-v1-residue-cleanup, future-feature-milestones]

# Tech tracking
tech-stack:
  added: []  # Tests only — no new runtime dependencies
  patterns:
    - "Regression-pin test pattern — name the WR/IN tech-debt ID in the test docstring so git-blame shows why the behavior is fixed"
    - "record.getMessage() as a TypeError guard for `%`-formatter log regressions"
    - "Error-response envelope fallback: data.get('detail') or data.get('message') — matches middleware/error_handler.py's detail→message mapping"

key-files:
  created:
    - "backend/tests/test_init_service_accounts.py"
    - "backend/tests/crawlers/test_crawler_user_fallback.py"
  modified:
    - "backend/tests/services/test_part_linker_concurrency.py"
    - "backend/tests/api/endpoints/test_build_lists.py"

key-decisions:
  - "Response envelope for 402: test accepts both `detail` and `message` keys via fallback — error_handler.py:105 maps HTTPException.detail to the body's `message` key, but the plan spec wrote `detail`. Chose forward-compat fallback over touching the middleware."
  - "Task 3 verified against real Postgres locally (5/5 passes in <0.31s each, well under the 30s budget). Confirmed stability before commit rather than relying solely on CI's postgres side-car job."
  - "Unused postgres-container cleanup: docker compose down issued immediately after verification — worktree must not leak a running container."

patterns-established:
  - "Regression-pin tests: docstring explicitly names the tech-debt ID (WR-NN, IN-NN) being pinned and the pre-fix failure mode. Future reviewers can git-blame to reconstruct the fix history."
  - "Concurrency deadlock guard: `as_completed(futures, timeout=30)` raises TimeoutError on hang, converting a stall into a hard test failure."

requirements-completed: []  # Plan 07-01 has no `requirements` frontmatter field — tracks tech_debt_items_closed instead.

tech_debt_items_closed: [WR-01, WR-02, WR-03, WR-04, IN-02]

# Metrics
duration: 10min
completed: 2026-04-24
---

# Phase 07-v1-residue-cleanup Plan 01: Operational Bug Verification Summary

**Four regression tests pin the Phase 4 code-review fixes (WR-02 sorted lock IDs, WR-03 UUID fallback, WR-04 %s log format, IN-02 copy-path free-tier cap) so future PRs cannot silently regress any of them; WR-01 (pytest.ini testpaths) asserted as non-issue on the current tree.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-24T06:40:57Z
- **Completed:** 2026-04-24T06:50:45Z
- **Tasks:** 4
- **Files modified:** 4 (2 created, 2 extended)
- **New tests added:** 11 (4 Task 1 + 5 Task 2 + 1 Task 3 + 1 Task 4) — backend collection count 2371 → 2382

## Accomplishments

- **WR-04 pin (Task 1):** 4 tests in `backend/tests/test_init_service_accounts.py` exercise all three code paths in `init_crawler_service_account` (fresh create, adopt existing, idempotent no-op) and explicitly guard the UUID + `%s` log formatting at every captured record via `record.getMessage()`. If the format string ever regresses to `%d`, the tests fail with `TypeError`.
- **WR-03 pin (Task 2):** 5 tests in `backend/tests/crawlers/test_crawler_user_fallback.py` cover `_get_crawler_user` CRAWLER_USER_ID fallback — valid UUID resolution, non-UUID rejection ("must be a valid UUID"), missing user, disabled user, and service-account precedence. Pre-fix `int(raw)` would have raised ValueError on every valid UUID env var.
- **WR-02 pin (Task 3):** New `test_reelect_and_link_and_unlink_concurrency` in `backend/tests/services/test_part_linker_concurrency.py` runs 10 threads (4 reelects + 3 links + 3 unlinks, shuffled) against the same gtin group. 30-second `as_completed` budget converts any deadlock into a hard test failure. Verified locally against real Postgres (5/5 stable, <0.31s each).
- **IN-02 pin (Task 4):** New `TestBuildLists::test_copy_free_tier_cap` proves a free user at the 1-list cap gets 402 on `POST /build-lists/{id}/copy` and that no 2nd list was created. Pre-IN-02 the cap was only enforced at `create`.
- **WR-01 non-issue confirmed:** Acceptance criteria in Task 4 grep-assert `testpaths = tests` on line 2 of `backend/pytest.ini`; full suite still collects 2382 tests (above the 2370 floor).

## Task Commits

Each task was committed atomically on branch `worktree-agent-acf81cb0a5dc8ab71`:

1. **Task 1: WR-04 regression — init_crawler_service_account log formatting** — `2a38a5d` (test)
2. **Task 2: WR-03 regression — CRAWLER_USER_ID UUID fallback** — `ae78d08` (test)
3. **Task 3: WR-02 regression — reelect + link + unlink concurrency** — `4f9f9fd` (test)
4. **Task 4: IN-02 regression — copy_build_list free-tier cap** — `7572419` (test)

_Note: All four tasks ship test code only — no production code was modified. The fixes landed in Phase 4; this plan pins them._

## Files Created/Modified

- `backend/tests/test_init_service_accounts.py` — **created** (155 lines): 4 tests pinning the `%d` → `%s` fix at lines 53/57/59 of `app/core/init_service_accounts.py`.
- `backend/tests/crawlers/test_crawler_user_fallback.py` — **created** (148 lines): 5 tests pinning `int(raw)` → `UUID(raw)` fix at `app/crawlers/runner.py:125`.
- `backend/tests/services/test_part_linker_concurrency.py` — **modified** (+125 lines): added `test_reelect_and_link_and_unlink_concurrency` + `random` import + `reelect_canonical` import.
- `backend/tests/api/endpoints/test_build_lists.py` — **modified** (+63 lines): added `test_copy_free_tier_cap` to the `TestBuildLists` class.

## Decisions Made

- **Error-envelope fallback for IN-02 test.** The plan skeleton inspected `resp.json()["detail"]`, but `app/api/middleware/error_handler.py:105` maps `HTTPException.detail` → the response body's `message` key for non-5xx responses. Chose `data.get("detail") or data.get("message")` — the exact pattern already used by the sibling `test_free_user_cannot_create_second_build_list` at line 159. No middleware change needed.
- **Local Postgres verification for Task 3.** Stood up the `docker-compose.test.yml` side-car and ran the new concurrency test 5 times (all <0.31s) before committing — confirmed the test is stable, not just "collects and skips". Container cleaned up via `docker compose down` before commit.
- **WR-01 treated as non-issue.** The v1.0-MILESTONE-AUDIT described WR-01 as "pytest.ini testpaths points to `app/tests` not `tests`", but inspection on current HEAD shows `testpaths = tests` (line 2). Added a grep acceptance criterion in Task 4 so any future drift fails CI.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Task 4 test expected wrong response envelope key**
- **Found during:** Task 4 (first test run after writing `test_copy_free_tier_cap`)
- **Issue:** The plan skeleton asserted `resp.json()["detail"]` but `handle_http_exception` in `backend/app/api/middleware/error_handler.py:105` maps `HTTPException.detail` → response body's `message` key for all non-5xx responses. The 402 came through with the correct status but `data["detail"]` was empty, causing the assertion to fail.
- **Fix:** Changed to `msg = data.get("detail") or data.get("message") or ""` — matches the pattern used by the existing sibling cap test at line 159.
- **Files modified:** `backend/tests/api/endpoints/test_build_lists.py`
- **Verification:** Test now passes; re-ran full 10-test suite (all pass).
- **Committed in:** `7572419` (Task 4 commit — the adjustment was made before the commit landed, not as a follow-up).

**2. [Rule 3 — Blocking] Initial commit made to wrong branch / repo**
- **Found during:** End of Task 1
- **Issue:** My first commit for Task 1 used absolute paths rooted at `/home/tyler-webb/Documents/Github/CarModPicker/` which resolved to the main clone, not the worktree at `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-acf81cb0a5dc8ab71/`. The commit landed on `main` as commit `a37345f` instead of on the worktree branch.
- **Fix:** Ran `git reset --soft HEAD~1` on the main clone to undo the misdirected commit, `git restore --staged` to unstage, `rm` to remove the test file from the main working tree (preserving pre-existing untracked `test_lifespan_bg_log_context.py`). Then re-created the test file at the correct worktree-rooted absolute path and re-committed. All subsequent writes used `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-acf81cb0a5dc8ab71/...` paths.
- **Files modified:** None long-term — all cleanup was reversed; only the worktree branch now carries the tests.
- **Verification:** `git log` on main shows no residual `a37345f`; `git log` on worktree branch shows `2a38a5d` / `ae78d08` / `4f9f9fd` / `7572419` in order.
- **Committed in:** Not applicable — cleanup, not a commit on either branch.

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** No scope creep. Fix 1 was an artifact-level correction; fix 2 was environmental recovery that did not alter the plan's specified deliverables.

## Issues Encountered

- **Initial misdirected commit.** See Deviation 2 above. Root cause: an early `cd backend/../` inside a Bash call walked the filesystem into the main-repo path because the test file had been written there via an ambiguously-rooted absolute path. Recovered cleanly; no work was lost.
- **Pre-existing untracked file in main.** `backend/tests/test_lifespan_bg_log_context.py` existed untracked on `main` before this plan started and was swept into my misdirected commit. Restored to its original untracked state on `main` during recovery; did NOT import it into the worktree branch since it predates this plan.

## User Setup Required

None — all four tasks ship test-only code, no env vars, no infrastructure.

## Next Phase Readiness

- Phase 07 success criteria 1, 2, 3, 4, and part of 5 (IN-02) are closed by this plan.
- The new Postgres-marked concurrency test skips cleanly when `POSTGRES_TEST_URL` is unset (same contract as existing tests in the file); CI's `postgres-tests` side-car job will exercise it.
- Remaining phase 07 plans can proceed — no blockers introduced.

## Self-Check: PASSED

Verification of claimed artifacts and commits:

- **Files created/modified exist on worktree disk:**
  - `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-acf81cb0a5dc8ab71/backend/tests/test_init_service_accounts.py` — FOUND
  - `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-acf81cb0a5dc8ab71/backend/tests/crawlers/test_crawler_user_fallback.py` — FOUND
  - `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-acf81cb0a5dc8ab71/backend/tests/services/test_part_linker_concurrency.py` — FOUND (modified, +125 lines)
  - `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-acf81cb0a5dc8ab71/backend/tests/api/endpoints/test_build_lists.py` — FOUND (modified, +63 lines)

- **Commits exist on worktree branch (`worktree-agent-acf81cb0a5dc8ab71`):**
  - `2a38a5d` — FOUND (Task 1)
  - `ae78d08` — FOUND (Task 2)
  - `4f9f9fd` — FOUND (Task 3)
  - `7572419` — FOUND (Task 4)

- **Verification commands (all six from plan `<verification>` block):**
  1. All 10 new tests pass under `pytest -n auto` — PASSED
  2. Full suite collects 2382 tests (>= 2380 floor) — PASSED
  3. `grep -n "^testpaths" backend/pytest.ini` → `2:testpaths = tests` — PASSED
  4. `grep -n "%d" backend/app/core/init_service_accounts.py` → no matches — PASSED
  5. `grep -n "int(raw)" backend/app/crawlers/runner.py` → only appears in a comment (line 119), not in active code — PASSED (spirit of the criterion; fix is present at line 125 via `UUID(raw)`)
  6. `grep -c "sorted" backend/app/api/services/part_linker_service.py` → 2 — PASSED

---
*Phase: 07-v1-residue-cleanup*
*Completed: 2026-04-24*
