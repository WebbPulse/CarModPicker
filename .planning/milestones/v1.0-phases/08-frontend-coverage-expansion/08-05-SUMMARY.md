---
phase: 08-frontend-coverage-expansion
plan: 05
subsystem: testing
tags: [frontend, vitest, api-tests, votes, reports, bug-reports, polymorphic, wave-1]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "Dual api-client mock in setup.ts (D-18); mockVoteSummary, mockPart, mockBuildList, mockCar in test/mocks/api.ts"
provides:
  - "frontend/src/api/votes.test.ts (18 tests) — full coverage of votesApi + partVotesApi + buildListVotesApi with polymorphic entity_type dispatch verified for part, build_list, car_generation"
  - "frontend/src/api/reports.test.ts (16 tests) — full coverage of reportsApi + partReportsApi with polymorphic dispatch for part and build_list"
  - "frontend/src/api/bug_reports.test.ts (8 tests) — full coverage of bugReportsApi (pure JSON, no FormData at API-module layer)"
  - "Polymorphic dispatch verification template — tests enumerate entity_type values explicitly in URL, body, and filter-params assertions"
affects: ["08-11 through 08-20 (Wave 3 page tests consuming vote widgets and report flows)", "future polymorphic endpoints added to the Phase 8 taxonomy"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Polymorphic-dispatch test pattern: one it-block per (method × entity_type) pair, asserting URL path segments and body shape"
    - "Legacy-wrapper delegation test pattern: partVotesApi / partReportsApi / buildListVotesApi tests assert the downstream polymorphic URL after defaults are applied"
    - "FormData-negation assertion: bug_reports.test.ts confirms the API module sends plain JSON (FormData path lives in page component, not API client)"

key-files:
  created:
    - "frontend/src/api/votes.test.ts (292 lines, 18 tests) — votesApi, partVotesApi, buildListVotesApi"
    - "frontend/src/api/reports.test.ts (261 lines, 16 tests) — reportsApi, partReportsApi"
    - "frontend/src/api/bug_reports.test.ts (169 lines, 8 tests) — bugReportsApi"
  modified: []

key-decisions:
  - "Polymorphic assertions exercise 3 entity types (part, build_list, car_generation) for votesApi.voteOnEntity / removeVote / getVoteSummary / getFlaggedEntities to prove the URL path segment is interpolated not hard-coded"
  - "Legacy-wrapper tests assert the polymorphic URL the wrapper resolves to, not the wrapper signature — this guards against a future refactor that changes the delegation target silently"
  - "bug_reports.test.ts asserts `firstCall?.[1]` is NOT an instance of FormData to document that the API module is pure JSON; the FormData path confirmed to live in pages/BugReport.tsx per plan directive"

patterns-established:
  - "API tests import apiClient from '../api/client' and use vi.mocked(apiClient.<verb>).mockResolvedValueOnce(...) per call — no per-file vi.mock needed (D-18 setup.ts covers it globally)"
  - "PaginatedResponse<T> assertions use the real `{ data, pagination }` shape from types/Api.ts:334-337, not the legacy `{ items, total, skip, limit }` shape"
  - "Polymorphic endpoints are tested with a minimum of 2 entity types (per-plan acceptance criteria); this plan exceeded that with 3 for votesApi"

requirements-completed: [SAFE-03]

# Metrics
duration: 5min 14s
completed: 2026-04-24
---

# Phase 8 Plan 05: Votes + Reports + Bug Reports API Tests Summary

**Added 42 tests across 3 new files (votes.test.ts, reports.test.ts, bug_reports.test.ts) lifting votes/reports cluster source coverage from 0% baseline to 98-100% across all four metrics; polymorphic entity_type dispatch verified for 3 entity types on votesApi and 2 on reportsApi.**

## Performance

- **Duration:** 5 min 14 s
- **Started:** 2026-04-24T17:23:33Z
- **Completed:** 2026-04-24T17:28:47Z
- **Tasks:** 2
- **Files created:** 3 (votes.test.ts, reports.test.ts, bug_reports.test.ts)
- **Files modified:** 0

## Accomplishments

- **votes.test.ts (18 tests, 21 expect calls)** — full coverage of the polymorphic `votesApi` (11 tests across voteOnEntity, removeVote, getVoteSummary, getFlaggedEntities, countVotes) plus its legacy entity-scoped wrappers `partVotesApi` (4 tests) and `buildListVotesApi` (3 tests). `voteOnEntity` + `removeVote` + `getVoteSummary` + `getFlaggedEntities` each tested with at least 2 entity types; `voteOnEntity` and `getFlaggedEntities` exercise all 3 (part, build_list, car_generation).
- **reports.test.ts (16 tests, 19 expect calls)** — full coverage of the polymorphic `reportsApi` (12 tests across reportEntity, getReports, getReportsWithDetails, getMyReports, getReport, updateReport, deleteReport, countReports) plus `partReportsApi` legacy wrapper (4 tests). Polymorphic dispatch verified with part + build_list on reportEntity, getReports, and getReportsWithDetails.
- **bug_reports.test.ts (8 tests, 13 expect calls)** — full coverage of `bugReportsApi` (createBugReport, getBugReports, getBugReportsWithDetails, getBugReport, updateBugReport, deleteBugReport, countBugReports). Confirms the API module uses pure JSON (no FormData at this layer); FormData-negation assertion documents the intentional split.
- **Coverage delta vs. 08-COVERAGE-BASELINE.txt** (lines 1-43 of votes.ts, reports.ts, bug_reports.ts were 0% across all 4 metrics):

  | File | Baseline | After plan 08-05 |
  |------|----------|------------------|
  | `frontend/src/api/votes.ts` | 0 / 0 / 0 / 0 | 98.27 / 92.3 / 92.3 / 98.27 |
  | `frontend/src/api/reports.ts` | 0 / 0 / 0 / 0 | 100 / 91.66 / 100 / 100 |
  | `frontend/src/api/bug_reports.ts` | 0 / 0 / 0 / 0 | 100 / 100 / 100 / 100 |

  (Stmts / Branch / Funcs / Lines; measured via `npm run test:coverage -- --run src/api/votes.test.ts src/api/reports.test.ts src/api/bug_reports.test.ts`.)
- **Polymorphic dispatch cases covered**:
  - `votesApi.voteOnEntity`: part (mockPart.id), build_list (mockBuildList.id), car_generation (mockCar.id)
  - `votesApi.removeVote`: part, build_list
  - `votesApi.getVoteSummary`: part, build_list
  - `votesApi.getFlaggedEntities`: part, build_list, car_generation
  - `reportsApi.reportEntity`: part, build_list
  - `reportsApi.getReports` (filter params): part, build_list
  - `reportsApi.getReportsWithDetails` (filter params): part, build_list

## Task Commits

Each task was committed atomically on this worktree's main branch:

1. **Task 1: Write votes.test.ts covering polymorphic entity types** — `0e16cbb` (test)
2. **Task 2: Write reports.test.ts and bug_reports.test.ts** — `c3712ab` (test)

_Metadata commit for SUMMARY.md will follow._

## Files Created/Modified

### Created

- `frontend/src/api/votes.test.ts` (292 lines, 18 tests) — Covers every method on `votesApi`, `partVotesApi`, and `buildListVotesApi`. Uses a local `makeVoteRead(overrides)` factory to avoid leaking a shared mutable fixture (Pitfall 6). Asserts `vi.mocked(apiClient.<verb>)` call shape for URL + body + params.
- `frontend/src/api/reports.test.ts` (261 lines, 16 tests) — Covers `reportsApi` (polymorphic) and `partReportsApi` (legacy wrapper). Uses local `makeReportRead` + `makeReportWithDetails` + `emptyPaginatedReports` factories. Asserts that `partReportsApi.getReports` pins `entity_type: 'part'` onto whatever params the caller passed.
- `frontend/src/api/bug_reports.test.ts` (170 lines, 8 tests) — Covers every method on `bugReportsApi`. Includes a FormData-negation test to document that this module layer is pure JSON (the file-upload path lives in `pages/BugReport.tsx`, not here).

### Modified

None — this plan is pure test-authoring.

## Decisions Made

- **Polymorphic coverage exceeded the 2-entity-type minimum where it was cheap.** Plan acceptance criteria required at least 2 entity types per polymorphic method. `votesApi.voteOnEntity` and `votesApi.getFlaggedEntities` include a third (`car_generation`) at essentially zero additional cost — the VoteCreate type allows it and the URL template interpolates the same way, so the third case doubles as a regression guard against a future maintainer hard-coding one of the two common cases.
- **Legacy-wrapper tests assert the downstream URL, not just that the wrapper exists.** `partReportsApi.updateReport` coerces its looser input shape (`{ status: string; admin_notes?: string | null }`) into the strict `ReportUpdate` union. Asserting the PUT URL + normalized body catches a class of bugs where the wrapper drops or mutates the payload silently.
- **FormData-negation assertion retained even though FormData absence is "obvious" from reading the source.** Plan action directed reading bug_reports.ts first to decide: the module is pure JSON. The negation test is one cheap expect that blocks a future refactor that accidentally starts building a FormData in the API layer (e.g., if someone moves the screenshot upload from the page component down into the client).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `postCalls[0]` possibly undefined in bug_reports.test.ts FormData-negation assertion**

- **Found during:** Task 2 (type-check after writing both test files)
- **Issue:** `vi.mocked(apiClient.post).mock.calls[0][1]` fails `strict` + `noUncheckedIndexedAccess` TS with error TS2532 "Object is possibly 'undefined'" — `mock.calls` is typed as `Params[]` so `[0]` may be undefined in the general case.
- **Fix:** Added explicit length guard and optional-chain: `expect(postCalls.length).toBeGreaterThan(0)` then `expect(firstCall?.[1]).not.toBeInstanceOf(FormData)`.
- **Files modified:** `frontend/src/api/bug_reports.test.ts` (lines 77-82)
- **Verification:** `npm run type-check` exits 0 for my three new files; `npm test -- --run src/api/bug_reports.test.ts` → 8/8 pass.
- **Committed in:** `c3712ab` (Task 2)

---

**Total deviations:** 1 auto-fixed (1 type-safety bug in my own newly-written code).
**Impact on plan:** No scope creep. Type safety preserved. Test still asserts the FormData-negation guarantee it was meant to.

## Issues Encountered

- **Pre-existing lint errors (`@typescript-eslint/unbound-method`) inherited from base commit.** `npm run lint` at the base commit `3da3aef` already reports 140 errors project-wide (mostly `unbound-method` on the existing `vi.mocked(apiClient.X)` pattern in `build_lists.test.ts` from a sibling parallel-wave plan). My three new test files follow the same canonical Wave 1 skeleton from PATTERNS.md §7 and inherit the same lint signature. Out of scope per SCOPE BOUNDARY — pre-existing warnings not directly caused by this plan's task changes. Sibling plans in Wave 1 (08-02, 08-03, 08-04, 08-06) use the same pattern; if a phase-level lint sweep is needed, it belongs in Wave 5 not Wave 1.
- **Worktree filesystem shows untracked `.test.ts` files from sibling parallel waves** (build_list_parts.test.ts, build_lists.test.ts, car_generations.test.ts, parts.test.ts, build_list_phases.test.ts, build_logs.test.ts). Per destructive_git_prohibition, these are NOT cleaned up — they belong to parallel executor commits and will be reconciled when the phase's parallel-execution results merge. I only staged and committed my own three files.

## User Setup Required

None — pure test authoring. No external service configuration required.

## Next Phase Readiness

- **Wave 3 page tests unblocked for vote-widget and report-flow surfaces.** Pages that embed `<VoteButtons>` (ViewPart, ViewBuildList) or report flows (ReportModal) can mock the underlying API calls knowing exactly which URLs / bodies the mocked calls should match.
- **Polymorphic taxonomy is now a regression-guarded contract.** Any future maintainer adding a fourth entity type to `VoteCreate['entity_type']` will need to either (a) add an explicit test here or (b) verify the URL interpolation is still correct — either way the test file's existing 3-entity-type pattern is the documentation for how to extend.
- **PaginatedResponse shape for reports and bug_reports is locked.** Both `getReportsWithDetails` and `getBugReportsWithDetails` now have tests asserting the `{ data, pagination: { current_page, total_pages, ... } }` shape — future admin pages (Wave 4) can rely on these.
- **No blockers. No concerns.**

## Self-Check: PASSED

- `test -f frontend/src/api/votes.test.ts` → FOUND (292 lines, 18 it-blocks, 21 expect calls, 0 `.skip`)
- `test -f frontend/src/api/reports.test.ts` → FOUND (261 lines, 16 it-blocks, 19 expect calls, 0 `.skip`)
- `test -f frontend/src/api/bug_reports.test.ts` → FOUND (170 lines, 8 it-blocks, 13 expect calls, 0 `.skip`)
- `grep -c "'part'" frontend/src/api/votes.test.ts` → 7 (≥ 1 required)
- `grep -c "'build_list'" frontend/src/api/votes.test.ts` → 10 (≥ 1 required)
- `grep -c "'part'" frontend/src/api/reports.test.ts` → 7 (polymorphism verified)
- `grep -c "'build_list'" frontend/src/api/reports.test.ts` → 6 (polymorphism verified)
- `git log --oneline -3` → `c3712ab`, `0e16cbb`, `3da3aef` FOUND
- `cd frontend && npm test -- --run src/api/votes.test.ts src/api/reports.test.ts src/api/bug_reports.test.ts` → 3 files / 42 tests pass
- `cd frontend && npm run type-check 2>&1 | grep -E "votes\.test|reports\.test|bug_reports\.test"` → no errors in this plan's files (the one parts.test.ts error is an unrelated sibling-worktree file)
- Per-file expect-count > it-count: votes 21>18 ✓, reports 19>16 ✓, bug_reports 13>8 ✓

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
