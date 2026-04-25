---
phase: 08-frontend-coverage-expansion
plan: 19
subsystem: testing
tags: [frontend, vitest, page-tests, admin, crawler, fake-timers, wave-4]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    provides: "plan 08-01 shared test infra — testScenarios.adminAuthenticated, src/test/mocks/admin/{crawlers,jobs}.ts fixture factories, and src/test/utils/async.ts fake-timer helpers (startFakeTimers / stopFakeTimers / advanceTimersAndFlush)"
provides:
  - "frontend/src/pages/admin/CrawlerAdmin.test.tsx — 5 describe blocks (auth-gating + 4 Card sections) with 13 it-blocks and 26 expects covering the largest page in the app (2,665 LOC)"
  - "First in-repo use of vi.useFakeTimers() — Background Jobs polling test exercises startFakeTimers / advanceTimersAndFlush helpers for the first time, proving the Wave 0 async.ts infrastructure"
  - "Concrete fake-timer + React polling pattern: enable fake timers BEFORE render, drive state settling with advanceTimersAndFlush(0), measure poll fetches via mock.calls.length (no waitFor mixing — documented in the Background Jobs describe block's comments)"
affects: ["08-20 (threshold enable — CrawlerAdmin.tsx coverage moves from 0% to covered)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fake-timer polling test: startFakeTimers() BEFORE render → advanceTimersAndFlush(0) twice to flush initial mount → snapshot mock.calls.length → advanceTimersAndFlush(interval_ms) → compare counts"
    - "Admin page test: customRender + testScenarios.adminAuthenticated + vi.mocked(apiClient.{get,post,patch}) per-test responses via defaultGetImpl router"
    - "Never mix waitFor with fake timers: waitFor's internal setInterval retry loop stalls under faked setInterval → use advanceTimersAndFlush + direct mock.calls assertions"

key-files:
  created:
    - "frontend/src/pages/admin/CrawlerAdmin.test.tsx (490 lines, 5 describes, 13 its, 26 expects)"

key-decisions:
  - "Enable fake timers BEFORE render (not after initial waitFor) — setInterval registered under real timers is invisible to vi.advanceTimersByTime; moving the switch earlier makes the polling assertion actually observe the 5 s tick"
  - "No waitFor inside fake-timer describe block — waitFor uses its own setInterval retry loop; under faked setInterval it would never retry. Asserted polling behavior directly via apiClient.get mock.calls.length instead"
  - "defaultGetImpl seeds a synthetic 'other' category so fetchCrawlers auto-picks crawlerDefaultCategoryId — the Run-all / Rescrape POST handlers bail with 'Select a default category' otherwise. Matches production behavior where the seeded 'other' category always exists"
  - "non-admin fixture hand-rolled rather than reusing testScenarios.authenticated — that fixture's createMockUser() predates the is_service_account / subscription_tier / subscription_status / totp_enabled fields on UserRead and fails exactOptionalPropertyTypes. Same workaround used by AdminDashboard.test.tsx"

patterns-established:
  - "CrawlerAdmin polling tests enable fake timers pre-render, flush promises with advanceTimersAndFlush(0), then drive the interval with advanceTimersAndFlush(5000). See Background Jobs describe block comments for the full rationale"
  - "Fake-timer tests assert via mock.calls.length, not waitFor / findBy*"
  - "afterEach always calls stopFakeTimers() — if a test throws between startFakeTimers and the advance step, fake-timer state must not leak"

requirements-completed: [SAFE-03]

# Metrics
duration: 25min
completed: 2026-04-24
---

# Phase 8 Plan 19: CrawlerAdmin Page Coverage Summary

**Added frontend/src/pages/admin/CrawlerAdmin.test.tsx — 5 describe blocks covering auth-gating + all 4 Card sections of the largest page in the app (2,665 LOC), including the first working use of vi.useFakeTimers() in the repo for the Background Jobs 5 s polling path.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-24T11:28Z
- **Completed:** 2026-04-24T11:42Z
- **Tasks:** 3
- **Files created:** 1 (frontend/src/pages/admin/CrawlerAdmin.test.tsx)
- **Files modified:** 0

## Accomplishments

- **All 4 CrawlerAdmin Card sections covered** per RESEARCH.md §1 verified structure: Crawler Schedules (line 1505), Adapter Tuning (1874), Background Jobs (2043), Manual Run (2290). Each section gets its own describe block; no section is skipped. CrawlerAdmin remained a single plan (D-03) because the 4 sections render simultaneously, not as tabs.
- **First in-repo use of vi.useFakeTimers() is stable.** The Background Jobs describe block exercises startFakeTimers / stopFakeTimers / advanceTimersAndFlush from plan 08-01's async.ts. Both the positive (running-job → poll fires at 5 s) and negative (idle-jobs → no poll) paths pass deterministically.
- **Auth-deny paths covered** for both early-return branches: `user === null` → "please log in" ErrorAlert, and `user.is_admin === false` → "no permission" ErrorAlert. Mirrors AdminDashboard.test.tsx's three-way auth gating.
- **Manual Run POST contracts asserted** for both endpoints: `/admin/crawlers/run` (with `adapters: ['all']`, `parallel: true`, and the auto-picked default category id) and `/admin/crawlers/rescrape-archives` (with the default category id, called exactly once).
- **Zero `.skip()`, zero `EventSource` references** — matches VALIDATION.md Wave 4 meta-check and confirms the D-07 decision to delete the SSE stub from async.ts (CrawlerAdmin uses setInterval only).
- **Full frontend suite green:** 71 test files / 484 tests pass, `npm run type-check` exits 0, `npx eslint src/pages/admin/CrawlerAdmin.test.tsx` exits 0.

## Task Commits

Each task was committed atomically on this worktree's branch (`worktree-agent-a75f05f67b5430baa`):

1. **Task 1: Auth gating + Sections 1 (Crawler Schedules) and 2 (Adapter Tuning)** — `4502295` (test)
2. **Task 2: Section 3 (Background Jobs with fake timers)** — `7b7f36c` (test)
3. **Task 3: Section 4 (Manual Run) and finalize** — `722335a` (test)

_Metadata commit for SUMMARY.md is created at the end of this agent's run._

## Files Created/Modified

### Created

- `frontend/src/pages/admin/CrawlerAdmin.test.tsx` — 490-line test file. Imports `apiClient` from `../../api/client` (dual-mock via plan 08-01's setup.ts), admin fixtures from `../../test/mocks/admin/crawlers.ts` and `.../jobs.ts`, fake-timer helpers from `../../test/utils/async.ts`, and `testScenarios.adminAuthenticated` / `testScenarios.unauthenticated`. Provides a `defaultGetImpl` URL-prefix router so each happy-path test only has to override one branch.

## Decisions Made

- **Fake timers enabled BEFORE render, not after.** The polling useEffect's `setInterval(..., 5000)` registers during mount. If fake timers are activated AFTER mount (e.g. after a real-timer waitFor), the interval was scheduled against the real clock and `vi.advanceTimersByTime` never drives it. First attempt flipped timers post-mount and observed zero extra fetches — moving `startFakeTimers()` above `render(...)` fixed it.
- **No waitFor inside fake-timer describe blocks.** @testing-library's `waitFor` uses an internal setInterval retry loop. When the toFake list includes `setInterval`, waitFor never retries → every assertion times out at the 5 s test default. The Background Jobs block asserts polling via `apiClient.get.mock.calls.filter(...).length` directly.
- **defaultGetImpl seeds a synthetic "other" category.** Production CrawlerAdmin auto-selects the first category named "other" into `crawlerDefaultCategoryId`. Without it, all Manual Run POST handlers bail with `setCrawlerError('Select a default category.')`. Keeping "other" in the default GET router means Manual Run tests don't have to repeatedly override `/categories`.
- **Non-admin authenticated fixture hand-rolled.** `testScenarios.authenticated.initialAuthState.user` is produced by the older `createMockUser()` helper which lacks 4 fields on `UserRead` (is_service_account, subscription_tier, subscription_status, totp_enabled), tripping `exactOptionalPropertyTypes`. Built a fresh scenario off the canonical `mockUser` (same workaround used by AdminDashboard.test.tsx).
- **Two `advanceTimersAndFlush(0)` calls after render** — the first flushes the initial fetch promises, the second catches the setState that triggers the polling useEffect's re-run. Empirically one call wasn't enough when multiple setStates fire in the same batch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `waitFor` inside fake-timer mode hangs tests at 5 s timeout**

- **Found during:** Task 2 (Background Jobs section tests) — plan sketch had `startFakeTimers()` in `beforeEach` + `waitFor(...)` inside the test body, which the plan's own PATTERNS.md §12 canonical skeleton also shows.
- **Issue:** Running the skeleton verbatim caused all 3 Background Jobs tests to time out at 5 s. @testing-library's `waitFor` uses its own `setInterval` retry loop — with `toFake: ['setInterval', ...]` active, waitFor never retries unless we advance timers, which defeats the whole retry-until-true pattern.
- **Fix:** Moved `startFakeTimers()` from `beforeEach` into each fake-timer-requiring test (the "renders heading" test doesn't use fake timers at all) and replaced waitFor with direct `apiClient.get.mock.calls.length` inspection. `afterEach` unconditionally calls `stopFakeTimers()` to clean up if a test throws mid-way. Documented the pitfall in the describe block's preamble so the next author doesn't repeat it.
- **Files modified:** frontend/src/pages/admin/CrawlerAdmin.test.tsx
- **Verification:** All 3 Background Jobs tests pass (449 ms total). `grep -c "startFakeTimers\|useFakeTimers" frontend/src/pages/admin/CrawlerAdmin.test.tsx` = 7, meta-check satisfied.
- **Committed in:** `7b7f36c` (Task 2)

**2. [Rule 1 - Bug] Initial polling tick was invisible because fake timers were enabled too late**

- **Found during:** Task 2 — after the waitFor fix above, test still asserted "expected 2 to be greater than 2" on the poll-fires assertion.
- **Issue:** The first refactor entered fake-timer mode AFTER the initial `waitFor(...)` returned (real-timer path). By that point the polling useEffect had already registered its `setInterval` against the REAL clock. `vi.advanceTimersByTime(5000)` drove only the fake clock → real setInterval was never fired → no extra /admin/jobs fetch landed.
- **Fix:** Moved `startFakeTimers()` above `render(<CrawlerAdmin />)` so the setInterval registration happens under the fake clock from the very first call. The initial fetch promise chain still settles because `vi.advanceTimersByTimeAsync` (inside `advanceTimersAndFlush`) processes microtasks.
- **Files modified:** frontend/src/pages/admin/CrawlerAdmin.test.tsx
- **Verification:** The polls-every-5s test now passes; `jobCallsAfter > jobCallsInitial` after `advanceTimersAndFlush(5000)`.
- **Committed in:** `7b7f36c` (Task 2)

**3. [Rule 3 - Blocking] Executor created test file at wrong absolute path**

- **Found during:** Post-Task-3 `git status` check — the worktree's `git status` showed a clean tree even though the file existed on disk.
- **Issue:** The Write tool was called with `/home/tyler-webb/Documents/Github/CarModPicker/frontend/...` (main repo path) instead of `/home/tyler-webb/Documents/Github/CarModPicker/.claude/worktrees/agent-a75f05f67b5430baa/frontend/...` (worktree path). All commits had landed on an empty index.
- **Fix:** `mv` the file from the main repo path to the worktree path, then rebuilt the commit history (3 atomic commits).
- **Files modified:** relocated frontend/src/pages/admin/CrawlerAdmin.test.tsx + symlinked `frontend/node_modules` into the worktree for test execution.
- **Verification:** `git status` in worktree shows the file; `npm test --run` in worktree executes all 13 tests successfully.
- **Committed in:** Task 1 commit `4502295` captures the initial landing.

**4. [Rule 1 - Bug] `userEvent` races with still-resolving initial mount POSTs**

- **Found during:** Task 1 (reconcile-all button test) — plan suggested `await user.click(submitButton)` via `userEvent.setup()`.
- **Issue:** userEvent's auto-flush waits for event loop ticks but the CrawlerAdmin mount triggers 4 parallel fetches; the one clicking schedule-reconcile would sometimes snapshot mock.calls before the handler completed.
- **Fix:** Swapped `userEvent.click(button)` for `button.click()` (native click dispatch) on the Schedules reconcile, Manual Run "Run all", and Rescrape buttons. fireEvent-style synchronous dispatch + subsequent `waitFor(expect(...).toHaveBeenCalledWith(...))` is deterministic across the mount fan-out.
- **Files modified:** frontend/src/pages/admin/CrawlerAdmin.test.tsx
- **Verification:** All 5 button-click tests pass in <100 ms each, no flakes across 3 local reruns.
- **Committed in:** `4502295` (Task 1) / `722335a` (Task 3)

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs in my own test authoring, 2 Rule 3 blocking issues — fake-timer + waitFor interaction, and the worktree path snafu).
**Impact on plan:** No scope creep. Extra content added: a ~15-line preamble to the Background Jobs describe block documenting WHY fake timers are enabled pre-render and WHY no waitFor, and the non-admin fixture workaround. The core deliverable (5 describes, ≥10 its, ≥25 expects, fake-timer use, no EventSource, no .skip) all met with margin.

## Issues Encountered

- **`waitFor` + fake timers interaction was undocumented in the plan.** The plan's PATTERNS.md §12 skeleton showed both together and would have failed verbatim. Documented the fix in the test file's describe-block preamble so future admin-polling tests don't re-run into it.
- **Polling useEffect re-runs on every `jobsList` setState.** Because `jobsList` is a freshly-returned object from the mock, each fetchJobs resolution changes its reference → polling effect re-runs → clears existing setInterval → registers a new 5 s one. Two `advanceTimersAndFlush(0)` calls after render are needed to let those re-registrations settle before the real 5 s advance. Single-flush runs observed zero polling fetches intermittently.
- **Worktree had no `node_modules` directory.** Symlinked main repo's `frontend/node_modules` into the worktree so `npm test` could resolve vitest. No commit needed (gitignored).

## User Setup Required

None — test-only change, no external configuration.

## Next Phase Readiness

- **Wave 4 (admin pages) complete.** This was the 5th and final Wave 4 plan. All admin pages now have page tests: AdminDashboard (08-15), UserManagement (08-16), ReportReview / BugReportReview (08-17 or similar), SystemAdmin / SystemStatistics / PartsCuration (08-18), and CrawlerAdmin (this plan).
- **Wave 0's async.ts is proven load-bearing.** startFakeTimers / stopFakeTimers / advanceTimersAndFlush are now exercised by 3 passing tests. The Pitfall 5 act-wrapper pattern inside `advanceTimersAndFlush` is correct as shipped — do NOT revert it to the sync variant.
- **Ready for Wave 5 (08-20 threshold enable).** CrawlerAdmin.tsx was previously at 0% line coverage (one of the 4 largest uncovered files per 08-COVERAGE-BASELINE.txt). Its 13 tests + admin-path auth-deny coverage should move the file from 0% into the 30-50% range. Wave 5 will measure final coverage and either uncomment the D-06 threshold block or document the gap.
- **No blockers. No unresolved concerns.**

## Self-Check: PASSED

- `test -f frontend/src/pages/admin/CrawlerAdmin.test.tsx` → FOUND (490 lines)
- `grep -c "describe(" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 5 (≥5 required)
- `grep -cE "it\(|test\(" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 13 (≥10 required)
- `grep -c "expect(" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 26 (≥25 required)
- `grep -c "startFakeTimers\|useFakeTimers" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 7 (≥1 required, VALIDATION.md Wave 4 meta-check)
- `grep -c "advanceTimersAndFlush\|advanceTimersByTime" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 12 (≥1 required)
- `grep -cE "makeSchedule|makeCrawlerAdapter|makeJobsList|makeAdapterList|makeAdapterCatalog" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 15 (≥3 required)
- `grep -c "testScenarios.adminAuthenticated" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 11 (≥2 required)
- `grep -cE "testScenarios.unauthenticated|nonAdminAuthenticated" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 3 (≥2 required)
- `grep -c "\.skip(" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 0 (must be 0)
- `grep -c "EventSource" frontend/src/pages/admin/CrawlerAdmin.test.tsx` → 0 (must be 0 per research §1)
- `git log --oneline` → 3 commits FOUND (`4502295`, `7b7f36c`, `722335a`)
- `npm test -- --run src/pages/admin/CrawlerAdmin.test.tsx` → 13 tests / 13 pass
- `npm run type-check` → exits 0
- `npx eslint src/pages/admin/CrawlerAdmin.test.tsx` → exits 0

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
