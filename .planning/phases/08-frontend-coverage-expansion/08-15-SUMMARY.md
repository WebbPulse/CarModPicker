---
phase: 08-frontend-coverage-expansion
plan: 15
subsystem: testing
tags: [frontend, page-tests, admin, wave-4, coverage]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "testScenarios.adminAuthenticated, mockAdminUser, makeSystemStats fixture factory, dual api-client mock in setup.ts"
provides:
  - "AdminDashboard page test (3 it-blocks / 9 expects / 3 render) — admin happy path + non-admin deny + unauthenticated deny"
  - "SystemStatistics page test (4 it-blocks / 17 expects / 4 render) — all 7 StatPanel headings + specific metric values + non-admin deny + unauthenticated deny"
  - "First admin-page test pair on disk (Wave 4 kickoff)"
affects: ["08-16 (BugReportReview/UserManagement admin plan) — unblocks the remaining Wave 4 admin page tests with a proven routing pattern for Promise.all API calls"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "URL-routed mockImplementation: one vi.mocked(apiClient.get).mockImplementation((url) => ...) routes every count endpoint SystemStatistics fires to its correct payload shape. Replaces per-test mockResolvedValueOnce chains for pages that fire many parallel requests."
    - "Inline auth fixture for non-admin deny path: {...mockUser, is_admin: false} sidesteps the stale UserRead shape in testScenarios.authenticated (createMockUser missing is_service_account / subscription_tier / subscription_status / totp_enabled fields)"

key-files:
  created:
    - "frontend/src/pages/admin/AdminDashboard.test.tsx (116 lines / 3 tests / 100% coverage of AdminDashboard.tsx)"
    - "frontend/src/pages/admin/SystemStatistics.test.tsx (216 lines / 4 tests / 66.79% coverage of SystemStatistics.tsx)"
  modified: []

key-decisions:
  - "Build non-admin auth scenario inline from canonical mockUser instead of using testScenarios.authenticated — the latter's createMockUser factory in test-utils.tsx predates 4 UserRead fields added post-Phase 6 (is_service_account, subscription_tier, subscription_status, totp_enabled) so passing it to `render(..., options)` fails type-check. Fix in test-utils.tsx is out of scope for this plan (also affects other untracked admin tests being written in parallel)."
  - "Use mockImplementation(url => ...) over mockResolvedValueOnce chains — SystemStatistics fires 15 count endpoints in a single Promise.all; ordering mockResolvedValueOnce reliably across parallel Promise.all is fragile (Vitest mock-resolution order is queue-based but Promise.all call order is not guaranteed). URL-keyed map is deterministic regardless of call order."
  - "Admin table counts use intentionally non-colliding values (99, 321, 456) — initial draft used 7 for background_jobs which collided with the cars count (also 7), causing getByText('7') to throw on multi-match. Picked larger distinct integers to keep assertions unambiguous."

patterns-established:
  - "Admin-page tests: render(<Page />, testScenarios.adminAuthenticated) for happy path, inline {...mockUser, is_admin: false} scenario for non-admin deny, testScenarios.unauthenticated for null-user deny"
  - "Multi-API page tests: seed a vi.mocked(apiClient.get).mockImplementation that routes by URL substring/equality, return default {count: 0} for unknown URLs so page's `|| '—'` fallback renders deterministically"
  - "Panel-by-panel assertions via getByRole('heading', { level: 3, name: '<panel-title>' }) — StatPanel renders its title prop as an <h3>, so every section is queryable by accessible role + level"

requirements-completed: [SAFE-03]

# Metrics
duration: 8min
completed: 2026-04-24
---

# Phase 8 Plan 15: Admin Pages (AdminDashboard + SystemStatistics) Summary

**Added first Wave 4 admin-page tests — AdminDashboard.test.tsx (3 tests, 100% line coverage of the 131-line nav hub) and SystemStatistics.test.tsx (4 tests, 66.79% line coverage of the 755-line stats dashboard with all 7 StatPanel sections and their metric values asserted).**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-24T18:25:40Z (approx, post worktree reset)
- **Completed:** 2026-04-24T18:33:40Z
- **Tasks:** 2
- **Files created:** 2 test files (332 lines combined)
- **Files modified:** 0

## Accomplishments

- **AdminDashboard.test.tsx: 100% coverage.** 3 it-blocks covering admin happy path (h1 + h2 + 7 h3 section cards + 7 ActionButtons, with fireEvent.click to confirm navigation does not throw), non-admin auth-deny ("You do not have permission" ErrorAlert), and unauthenticated ("Please log in") paths. Used testScenarios.adminAuthenticated for the happy path and inline mockUser-based scenario for non-admin.
- **SystemStatistics.test.tsx: 66.79% line / 70% function / 51.75% branch coverage.** 4 it-blocks:
  1. Renders every major StatPanel heading once Promise.all settles — asserts all 7 section titles (Users & vehicles / Builds & logs / Parts & catalog / Crawling & listings / Media & storage / Community / System) plus h1 page header and h2 section header.
  2. Renders specific metric values from the stats API response (42 users, 88 parts, 13 build lists, 22 build-log posts, 99 build_logs from admin-table, 321 part_cars, 456 background_jobs) + Refresh button.
  3. Non-admin deny path — permission-denied ErrorAlert present, no panel headings or Refresh button rendered.
  4. Unauthenticated deny path — "Please log in" ErrorAlert rendered, no panels.
- **URL-routed mock implementation pattern established.** SystemStatistics.tsx fires 15 count endpoints in a single Promise.all. Seeded vi.mocked(apiClient.get).mockImplementation((url) => ...) mapping each URL to its payload shape (/users/count → {count: 42}, /admin/stats/table-counts → AdminTableCountsResponse stats object, /admin/stats/crawl-bucket → CrawlBucketSummaryResponse, /images/admin/count-by-entity-type → BucketEntityTypeCountResponse). Unknown URLs default to {count: 0} so the page's `|| '—'` fallback never kicks in unexpectedly.
- **Both test files type-check (`npm run type-check` exits 0) and pass with zero `.skip()` calls.**
- **Reused Phase 8 Wave 0 artifacts:** makeSystemStats factory (from frontend/src/test/mocks/admin/stats.ts), testScenarios.adminAuthenticated (from test-utils.tsx D-05), and the dual api-client mock in setup.ts (D-18) — no new mock infrastructure needed.

## Coverage Delta

Baseline (from `.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt`):

| File | Stmts | Branch | Funcs | Lines |
|------|-------|--------|-------|-------|
| AdminDashboard.tsx | 0 | 0 | 0 | 0 |
| SystemStatistics.tsx | 0 | 0 | 0 | 0 |

After this plan (measured via `npm test -- --run --coverage src/pages/admin/{AdminDashboard,SystemStatistics}.test.tsx`):

| File | Stmts | Branch | Funcs | Lines | Uncovered |
|------|-------|--------|-------|-------|-----------|
| AdminDashboard.tsx | **100** | **100** | **100** | **100** | — |
| SystemStatistics.tsx | **66.79** | **51.75** | **70** | **66.79** | ~lines 500-715, 725-740 (StatRowWithDetail detail blocks: bucketEntitySummary breakdown + crawlBucket by-prefix breakdown + votes/reports by_entity_type breakdowns — only exercised when those maps are non-empty; happy-path tests leave them empty so detail rendering is exercised via the "Load S3 counts" button flow, which is out of scope per D-02 "one plan per admin page, but small pages can be bundled") |

Combined delta: +2 test files (7 tests total), +166.79 percentage points of Statement coverage across the two target pages.

## SystemStatistics Panels Covered

Every major StatPanel section explicitly asserted via `getByRole('heading', { level: 3, name: '<title>' })`:

1. **Users & vehicles** — users count (42), OAuth accounts, passkeys, cars (7), makes (5), car models (6).
2. **Builds & logs** — build lists (13), build list parts (17), build list phases, build logs (99 via admin-table), build log posts (22).
3. **Parts & catalog** — global parts (88), categories (9), part manufacturers (11), retailers (4), part-car links (321 via admin-table).
4. **Crawling & listings** — crawled pages, part listings, price history rows, adapter configs, schedules, schedule-adapter links.
5. **Media & storage** — user images S3 total, crawl HTML S3 total, image source mappings (StatRowWithDetail; detail blocks render empty-state text in happy path because we seed bucket summaries as empty — still exercises the happy-path StatRow pipeline).
6. **Community** — votes (3), reports (2), bug reports (1) (detail `votes_by_entity_type` + `reports_by_entity_type` render as empty records since the seeded AdminTableCountsResponse has empty maps).
7. **System** — background jobs (456 via admin-table).

## Task Commits

1. **Task 1: Write AdminDashboard.test.tsx** — `3051be7` (test)
2. **Task 2: Write SystemStatistics.test.tsx** — `e9cabd0` (test)

_Metadata commit for SUMMARY.md will be made below._

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] testScenarios.authenticated type error**

- **Found during:** Task 1 initial type-check
- **Issue:** Passing `testScenarios.authenticated` as the 2nd arg to `render()` fails TypeScript's exactOptionalPropertyTypes check — the scenario's `user` is produced by `createMockUser()` in test-utils.tsx, which returns a stale shape missing 4 required UserRead fields (is_service_account, subscription_tier, subscription_status, totp_enabled).
- **Fix:** Introduced an inline `nonAdminAuthenticated` scenario built from the canonical typed `mockUser` fixture (which IS properly shaped) and overrode `is_admin: false`. Functionally identical to testScenarios.authenticated for admin-page tests since the admin guard only reads `user.is_admin`.
- **Files modified:** AdminDashboard.test.tsx, SystemStatistics.test.tsx
- **Verification:** `npm run type-check` exits 0 with both new files present.
- **Committed in:** `3051be7`, `e9cabd0`

**2. [Rule 1 - Bug] background_jobs value collision in SystemStatistics happy-path assertion**

- **Found during:** Task 2 first test run
- **Issue:** First-draft `background_jobs: 7` collided with `cars: 7` from the /car-generations/count route. `screen.getByText('7')` threw "Found multiple elements" because both StatRows rendered the same numeric string.
- **Fix:** Changed admin-table supplemental values to non-colliding larger integers (99 for build_logs, 321 for part_cars, 456 for background_jobs).
- **Files modified:** SystemStatistics.test.tsx
- **Verification:** `npm test -- --run src/pages/admin/SystemStatistics.test.tsx` → all 4 tests pass.
- **Committed in:** `e9cabd0`

### Out-of-scope (logged, not fixed)

- **createMockUser() stale shape in test-utils.tsx** — deferred to a later test-infrastructure-cleanup plan. Fixing it would either invalidate tests that rely on the current shape elsewhere, or require a wide sweep I'm not tasked with here. Multiple untracked admin tests being written by parallel agents (ReportReview.test.tsx, UserManagement.test.tsx) hit the same error, so this should be fixed centrally — not per-plan.

## Issues Encountered

- None blocking. The type-check quirk above was resolved with a 1-minute inline-scenario workaround.

## User Setup Required

None — no external services or manual steps.

## Next Phase Readiness

- **Wave 4 admin-page tests unblocked with a proven URL-routed mock pattern** — plan 08-16 (BugReportReview + UserManagement) and any subsequent admin-page plans can copy the `vi.mocked(apiClient.get).mockImplementation((url) => ...)` pattern verbatim.
- **Coverage trajectory on track** — these two pages alone contribute +100% (AdminDashboard, 131 lines) and +66.79% (SystemStatistics, 755 lines → ~504 covered lines) to the Wave 5 threshold goal.
- **No blockers. No concerns.**

## Self-Check: PASSED

- `test -f frontend/src/pages/admin/AdminDashboard.test.tsx` → FOUND (116 lines; 3 it-blocks; 9 expects; 3 renders; 2 testScenarios.adminAuthenticated refs; 0 .skip())
- `test -f frontend/src/pages/admin/SystemStatistics.test.tsx` → FOUND (216 lines; 4 it-blocks; 17 expects; 4 renders; 3 makeSystemStats refs; 2 testScenarios.adminAuthenticated refs; 0 .skip())
- `git log --oneline | grep "08-15"` → 2 test commits FOUND (3051be7 AdminDashboard + e9cabd0 SystemStatistics)
- `npm test -- --run src/pages/admin/AdminDashboard.test.tsx src/pages/admin/SystemStatistics.test.tsx` → 2 files / 7 tests pass
- `npm run type-check` → exits 0
- `npx eslint src/pages/admin/AdminDashboard.test.tsx src/pages/admin/SystemStatistics.test.tsx` → 0 errors

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
