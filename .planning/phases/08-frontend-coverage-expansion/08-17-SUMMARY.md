---
phase: 08-frontend-coverage-expansion
plan: 17
subsystem: testing
tags: [frontend, page-tests, admin, moderation, wave-4, vitest]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "testScenarios.adminAuthenticated (D-05) + makeReportWithDetails / makeBugReportWithDetails factories (D-06) + dual api-client mock (D-18) wired through test-utils customRender"
provides:
  - "Admin moderation page coverage: ReportReview (451 lines) + BugReportReview (608 lines) exercised end-to-end against testScenarios.adminAuthenticated"
  - "Pattern proof: customRender + importOriginal shim resolves named exports (reportsApi.getReportsWithDetails / bugReportsApi.getBugReportsWithDetails) through the mocked apiClient — no per-file vi.mock needed"
  - "First use of testScenarios.adminAuthenticated in the repo (Phase 8 Wave 4 scaffolding now has live consumers)"
affects: ["08-18 (SystemAdmin + SystemStatistics)", "08-19 (UserManagement)", "08-20 (PartsCuration)", "any future admin-page test"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Admin page test skeleton: customRender + testScenarios.adminAuthenticated + vi.mocked(apiClient.get/put) + makeFooWithDetails factory"
    - "Dialog-action flow: findByRole('button', { name: /Review/i }) → click → findByRole('button', { name: /Resolve|Dismiss|Mark In Progress/i }) inside dialog → assert apiClient.put"
    - "Auth-deny inline state pattern: pass explicit initialAuthState with mockUser (non-admin) rather than testScenarios.authenticated to sidestep pre-existing createMockUser typing gap (id:number, missing subscription fields)"

key-files:
  created:
    - "frontend/src/pages/admin/ReportReview.test.tsx (149 lines, 4 tests)"
    - "frontend/src/pages/admin/BugReportReview.test.tsx (146 lines, 4 tests)"
    - ".planning/phases/08-frontend-coverage-expansion/08-17-SUMMARY.md"
  modified: []

key-decisions:
  - "Plan <action> sketches used /admin/reports/:id/approve POST URLs but explicitly said 'Adjust URL shapes per actual source.' Real update path is apiClient.put('/reports/<id>' | '/bug-reports/<id>', { status, admin_notes, … }) via a review dialog — status: 'resolved' | 'dismissed' for reports; status: 'in_progress' | 'resolved' | 'dismissed' for bug reports. Tests match the real surface."
  - "For both pages, the 'approve'/'reject' terminology in the plan maps to 'Resolve Report'/'Dismiss Report' (reports) and 'Mark In Progress'/'Resolve'/'Dismiss' (bug reports). Tests cover resolve+dismiss for reports, in-progress+resolve for bug reports — each page gets two distinct action flows per D-02 + plan success criteria."
  - "Auth-deny test uses inline initialAuthState with mockUser instead of testScenarios.authenticated because the shared createMockUser helper still returns id: number + lacks subscription_tier/subscription_status/is_service_account/totp_enabled (a pre-existing typing gap already visible in AdminDashboard.test.tsx per the main-branch type-check). Inline state avoids importing the gap into new files."
  - "Skipped the plan's suggested makeUserList() dropdown wiring because BugReportReview does NOT have an assignee dropdown — the assign action surfaces as a 'Mark In Progress' status button inside the review dialog, not a user-select UI. The makeUserList fixture is unused by this plan but still available for future admin tabs (UserManagement plan 08-19)."

patterns-established:
  - "Admin page tests: `import { render, screen, testScenarios, waitFor } from '../../test/utils/test-utils'` — no per-file vi.mock('../../services/Api') needed"
  - "Dialog flow: first click opens dialog, second click inside the dialog triggers the mutation — test both clicks in sequence with user.click"

requirements-completed: [SAFE-03]

# Metrics
duration: 4min
completed: 2026-04-24
---

# Phase 8 Plan 17: Admin Moderation Page Coverage Summary

**Added ReportReview.test.tsx (4 tests) + BugReportReview.test.tsx (4 tests) covering list render, two dialog-driven mutation flows, and auth-deny — lifting both admin moderation pages from 0% baseline to 94.35% and 95.73% line coverage respectively, all via `testScenarios.adminAuthenticated` + Wave 0 admin fixture factories with no new test infrastructure.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-24T18:28:40Z
- **Completed:** 2026-04-24T18:32:20Z
- **Tasks:** 2
- **Files created:** 2 test files + 1 SUMMARY
- **Tests added:** 8 (4 per file)
- **New expects:** 16 (8 per file)

## Coverage Delta vs. Baseline

Baseline (from `08-COVERAGE-BASELINE.txt`):

| File                                         | Lines  | Branches | Funcs | Stmts |
| -------------------------------------------- | ------ | -------- | ----- | ----- |
| `frontend/src/pages/admin/ReportReview.tsx`    | 0      | 100*     | 100*  | 0     |
| `frontend/src/pages/admin/BugReportReview.tsx` | 0      | 100*     | 100*  | 0     |

*Vacuous 100% — no branches/funcs executed at baseline because file was never imported by any test.

After plan 08-17 (scoped run over just the two new test files):

| File                                         | Lines  | Branches | Funcs | Stmts |
| -------------------------------------------- | ------ | -------- | ----- | ----- |
| `frontend/src/pages/admin/ReportReview.tsx`    | 94.35  | 80.70    | 62.50 | 94.35 |
| `frontend/src/pages/admin/BugReportReview.tsx` | 95.73  | 71.42    | 50.00 | 95.73 |

**Deltas (real coverage now that the files are exercised):**

- ReportReview.tsx: +94.35 pts lines / +94.35 pts stmts. Branches 80.70 reflects real executed branches; funcs 62.50 reflects that a few helper branches (e.g. `getStatusBadge` fallbacks for 'resolved'/'dismissed' badges, unused pagination callbacks when totalPages=1) are not yet traversed.
- BugReportReview.tsx: +95.73 pts lines / +95.73 pts stmts. Branches 71.42 reflects real executed branches; funcs 50 reflects untraversed helpers (e.g. `getPriorityBadge` fallbacks for low/high/critical, `setSelectedPriority` click handlers, `bugReport.screenshot_url` image branch).

Uncovered line ranges (per coverage output): ReportReview `...69,358,363,370`; BugReportReview `...54,491,496,503` — all pagination guards + priority-filter branches that the happy-path tests don't exercise. Acceptable for D-02's "at-least-2-actions-per-page" policy.

## Accomplishments

### Task 1: ReportReview.test.tsx (4 tests, 149 lines)

1. **renders pending reports list for admin user** — admin-auth render; asserts `apiClient.get('/reports/admin/list-with-details', { params: { status: 'pending', … } })` fires; row heading, entity name, and Review button visible.
2. **resolves (approves) a report via the Resolve Report dialog action** — click Review to open dialog, click 'Resolve Report' in dialog; asserts `apiClient.put('/reports/<uuid>', { status: 'resolved', … })`.
3. **dismisses (rejects) a report via the Dismiss Report dialog action** — same dialog flow, 'Dismiss Report' button; asserts `apiClient.put('/reports/<uuid>', { status: 'dismissed', … })`.
4. **denies access to non-admin authenticated users** — inline non-admin state; asserts permission-denied error visible + no put mutation fires.

Committed: `d40d89e`.

### Task 2: BugReportReview.test.tsx (4 tests, 146 lines)

1. **renders open (pending) bug reports list for admin user** — admin-auth render; asserts `apiClient.get('/bug-reports/admin/list-with-details', { params: { status: 'pending', … } })` fires; title heading, reporter username, Review button visible.
2. **marks a bug report in-progress (assign) via the Mark In Progress dialog action** — open dialog, click 'Mark In Progress'; asserts `apiClient.put('/bug-reports/<uuid>', { status: 'in_progress', … })`.
3. **resolves a bug report via the Resolve dialog action** — open dialog, click 'Resolve'; asserts `apiClient.put('/bug-reports/<uuid>', { status: 'resolved', … })`.
4. **denies access to non-admin authenticated users** — inline non-admin state; asserts bug-report-specific permission-denied text + no put fires.

Committed: `d851a2e`.

## Task Commits

1. **Task 1: ReportReview.test.tsx** — `d40d89e` (test) — `frontend/src/pages/admin/ReportReview.test.tsx`
2. **Task 2: BugReportReview.test.tsx** — `d851a2e` (test) — `frontend/src/pages/admin/BugReportReview.test.tsx`

## Acceptance Criteria — Verified

| Criterion                                                      | Target | ReportReview | BugReportReview |
| -------------------------------------------------------------- | ------ | ------------ | --------------- |
| `npm test -- --run <file>` exits 0                             | —      | pass         | pass            |
| `grep -c "it(\|test("` returns at least 3                      | ≥ 3    | 4            | 4               |
| `grep -c "expect("` returns at least 8                         | ≥ 8    | 8            | 8               |
| `grep -c "render("` returns at least 3                         | ≥ 3    | 4            | 4               |
| `grep -c "makeReport"` / `makeBugReport` returns at least 1    | ≥ 1    | 4            | 4               |
| `grep -c "testScenarios.adminAuthenticated"` returns at least 1 | ≥ 1   | 3            | 3               |
| `grep -c "\.skip("` returns 0                                  | = 0    | 0            | 0               |

`npm run type-check` exits 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] "Test Entity" string appears multiple times in the DOM**

- **Found during:** Task 1 first test run.
- **Issue:** `screen.getByText(/Test Entity/)` threw "Found multiple elements" — `makeReportWithDetails()` defaults `entity_name: 'Test Entity'` AND the `entity_description` string contains the substring, so the text renders in both the header and the details section of a row. `getByText` requires a single match.
- **Fix:** Swapped to `screen.getAllByText(/Test Entity/).length > 0`. Assertion semantics unchanged (still proves the entity name renders) but matches the many-occurrence reality.
- **Files modified:** `frontend/src/pages/admin/ReportReview.test.tsx`
- **Verification:** Task 1 re-run → 4/4 pass.

**2. [Rule 3 - Blocking] testScenarios.authenticated triggers pre-existing typing gap**

- **Found during:** Type-check run after Task 1 edits.
- **Issue:** `testScenarios.authenticated` is built from `createMockUser()` (test-utils.tsx:84-95), which returns `id: number` and omits `is_service_account`, `subscription_tier`, `subscription_status`, `totp_enabled`. UserRead requires UUID-string id + those four fields. AdminDashboard.test.tsx already has this error on main (visible in the prior type-check output), so it's a shared pre-existing gap — fixing it in test-utils.tsx is out of scope for plan 08-17.
- **Fix:** Auth-deny tests use inline `initialAuthState: { isAuthenticated: true, user: mockUser, isLoading: false }` (mockUser from `src/test/mocks/api.ts` has the full UserRead shape). Semantically identical to testScenarios.authenticated — still a non-admin authenticated user — but type-checks cleanly.
- **Files modified:** Both `ReportReview.test.tsx` + `BugReportReview.test.tsx` at creation.
- **Verification:** `npm run type-check` exits 0.
- **Follow-up:** Could be addressed in Wave 5 gap-fill (plan 08-20-something) by repairing createMockUser's shape against UserRead. Out of scope here.

**3. [Rule 1 - Scope Adjustment] Plan's `/admin/reports/:id/approve` URL doesn't exist; real surface uses PUT to `/reports/:id`**

- **Found during:** Reading ReportReview.tsx before writing the test.
- **Issue:** Plan <action> sketch asserted `apiClient.post` to `/admin/reports/:id/approve` / `:id/reject`. In reality the code uses `apiClient.put('/reports/${reportId}', { status, admin_notes })`. Plan explicitly said "Adjust URL shapes per actual source" — this is the intended adjustment, not an unannounced deviation.
- **Fix:** Tests assert `apiClient.put` with URL regex `/^\/reports\/[^/]+$/` and `{ status: 'resolved' | 'dismissed' }` body. Same for bug reports with `/^\/bug-reports\/[^/]+$/`.
- **Files modified:** Both test files at creation.
- **Verification:** Tests pass; URLs match ReportReview.tsx:33 + BugReportReview.tsx:34 exactly.

**4. [Rule 1 - Scope Adjustment] BugReportReview has no assignee dropdown; "assign" = "Mark In Progress"**

- **Found during:** Reading BugReportReview.tsx before writing the test.
- **Issue:** Plan's Task 2 <action> sketched using `makeUserList()` to route `/admin/users` GET, implying an assignee dropdown populated from a user list. The real BugReportReview surface does not have an assignee dropdown — it has a priority select + admin notes textarea + status-change buttons (Mark In Progress / Dismiss / Resolve). The assign-style action maps to the "Mark In Progress" button.
- **Fix:** Task 2 Test 2 uses the "Mark In Progress" button as the assign flow. Did not import `makeUserList()`. The fixture is still available for a future plan that covers UserManagement's user-list tab (plan 08-19).
- **Files modified:** `frontend/src/pages/admin/BugReportReview.test.tsx` at creation.
- **Verification:** Tests pass; asserts match real page UI.

---

**Total deviations:** 4 auto-fixed (1 bug, 1 blocking-typecheck gap, 2 plan-vs-reality URL/UI shape adjustments that the plan explicitly anticipated with "Adjust per actual source").

## Issues Encountered

- **React "update not wrapped in act(...)" warning** appears for the auth-deny tests because the component's internal useEffect tries to `void navigate('/')` on mount for non-admin users, and the assertion runs synchronously before the redirect microtask settles. The tests still pass (the permission-denied error renders before the navigate call fires). Warning is noise, not a failure — same pattern as several Wave 3 tests (e.g., BugReport.test.tsx) that intentionally render and assert before microtasks flush. Out of scope to silence.
- **Coverage numbers (branches/funcs under 100%) do not reflect a regression** — baseline's "100%" was vacuous (0/0 executed). Post-plan numbers (80.70/62.50 and 71.42/50.00) reflect real executed ratios against real denominators. Every Wave 4 admin page will follow this pattern.

## User Setup Required

None — all infrastructure is local test code.

## Next Plan Readiness

- **Plan 08-18 (SystemAdmin + SystemStatistics admin pages) unblocked:** Pattern for admin-authenticated page tests is proven. Plan 08-18 can import `testScenarios.adminAuthenticated` + `makeSystemStats()` from `src/test/mocks/admin/stats.ts` and follow the same render → assert apiClient.get → (optional action) → assert apiClient.verb shape. No vi.mock needed at file level; the test-utils.tsx importOriginal shim handles named exports.
- **Plan 08-19 (UserManagement) unblocked:** `makeAdminUserView` + `makeUserList` factories are unused by plan 08-17 and ready to cover the admin Users tab.
- **Plan 08-20 (PartsCuration) unblocked:** `makeCurationCandidate` + `makeCurationQueue` factories ready.
- **No blockers. No concerns.**

## Self-Check: PASSED

- `test -f frontend/src/pages/admin/ReportReview.test.tsx` → FOUND (4 tests, 8 expects, 4 render calls, 4 makeReport, 3 testScenarios.adminAuthenticated, 0 .skip)
- `test -f frontend/src/pages/admin/BugReportReview.test.tsx` → FOUND (4 tests, 8 expects, 4 render calls, 4 makeBugReport, 3 testScenarios.adminAuthenticated, 0 .skip)
- `npm test -- --run src/pages/admin/ReportReview.test.tsx` → 4/4 pass
- `npm test -- --run src/pages/admin/BugReportReview.test.tsx` → 4/4 pass
- `npm run type-check` → exits 0
- `git log --oneline | grep -E "d40d89e|d851a2e"` → both commits FOUND

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
