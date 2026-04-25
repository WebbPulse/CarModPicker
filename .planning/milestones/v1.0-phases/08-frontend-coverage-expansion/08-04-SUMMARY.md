---
phase: 08-frontend-coverage-expansion
plan: 04
subsystem: testing
tags: [frontend, vitest, api-tests, build-lists, build-list-parts, build-list-phases, build-logs, wave-1]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "Dual api-client mock in setup.ts (D-18) — tests import `apiClient` from `../api/client` and use `vi.mocked(apiClient.method)` without per-file vi.mock; canonical fixtures mockBuildList + mockPart + mockUser + mockCar in src/test/mocks/api.ts"
provides:
  - "frontend/src/api/build_lists.test.ts — 14 tests covering all 13 buildListsApi methods (100% coverage on build_lists.ts)"
  - "frontend/src/api/build_list_parts.test.ts — 10 tests covering all 10 buildListPartsApi methods incl. nested /build-list-parts/:id/parts/:part_id URLs (100% lines, 83.33% branches on build_list_parts.ts)"
  - "frontend/src/api/build_list_phases.test.ts — 2 tests covering all 2 buildListPhasesApi methods (100% coverage on build_list_phases.ts)"
  - "frontend/src/api/build_logs.test.ts — 6 tests covering all 5 buildLogsApi methods incl. URLSearchParams query-string branch in getBuildLogByBuildList (100% coverage on build_logs.ts)"
affects:
  - "08-12 (buildLists page tests) — can rely on build-list cluster API surface being fully asserted"
  - "08-13 (builder page tests) — same"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wave-1 API-module test pattern (PATTERNS.md §7) — `vi.mocked(apiClient.method).mockResolvedValueOnce({data})` + `expect(apiClient.method).toHaveBeenCalledWith(url[, body])` + literal string interpolation for nested URLs"
    - "File-level eslint-disable block for `@typescript-eslint/unbound-method` (and `no-unsafe-assignment` where expect.objectContaining appears) — documented inline as a known false positive of the mock pattern"
    - "URLSearchParams query-string branch coverage — `getBuildLogByBuildList` bare URL vs appended `?skip=N&limit=M` asserted in two discrete its"
    - "Query-string param forwarding via `{ params: expect.objectContaining({...}) }` — used for `listBuildLists`, `getBuildListsWithVotes` where param shape is typed but not exhaustively listed per-test"

key-files:
  created:
    - "frontend/src/api/build_lists.test.ts (218 lines, 14 tests)"
    - "frontend/src/api/build_list_parts.test.ts (171 lines, 10 tests)"
    - "frontend/src/api/build_list_phases.test.ts (53 lines, 2 tests)"
    - "frontend/src/api/build_logs.test.ts (99 lines, 6 tests)"
  modified: []

key-decisions:
  - "Used file-level `/* eslint-disable @typescript-eslint/unbound-method */` rather than per-line disables — the pattern is the entire point of the file and per-line noise would bury the test intent. Documented rationale in a 5-line comment at top of each file."
  - "copyBuildList tested on BOTH paths — with explicit `new_name` arg (becomes `{ new_name: 'My Copy' }`) and omitted arg (becomes `{ new_name: null }` via source-side `|| null`). This proves the concrete body shape sent to the backend in both cases; the free-tier cap branch lives in the backend and is NOT exercised from the frontend."
  - "getBuildLogByBuildList URL-branch covered explicitly — the source builds URLSearchParams conditionally and appends only when non-empty; test covers bare `/build-logs/build-list/:id` and `...?skip=5&limit=10` variants separately (+1 it over plan minimum of 4)."
  - "createPartAndAddToBuildList tested via `expect.objectContaining(...)` rather than exhaustive match — the source re-packs 13+ fields and the spread includes `car_ids: car_ids ?? undefined` which encodes a lossy branch; asserting the subset keeps the test stable against additive schema evolution while still catching field-renaming or URL drift."

patterns-established:
  - "Wave 1 build-list-cluster test files all import `apiClient` from `'./client'` (not `'../services/Api'`) per D-18"
  - "Nested-URL methods use template literals with `mockBuildList.id` and `mockPart.id` interpolation — assertion strings match the URL the source produces, not a template-variable placeholder"
  - "Test files with `expect.objectContaining(...)` in `{ params: ... }` include `@typescript-eslint/no-unsafe-assignment` in the disable block; files without it do not (keeps disable scope minimal)"

requirements-completed: [SAFE-03]

# Metrics
duration: ~5min
completed: 2026-04-24
---

# Phase 8 Plan 04: Build-list Cluster API Tests Summary

**Added 32 vitest tests across 4 new files covering all 30 methods in the build-list cluster API surface (buildListsApi + buildListPartsApi + buildListPhasesApi + buildLogsApi), driving per-file coverage from 0% baseline to 100% lines/functions on all 4 source files (83.33% branches on build_list_parts.ts due to one ??-coalesce branch in `createPartAndAddToBuildList`).**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-24T17:23:00Z
- **Completed:** 2026-04-24T17:28:22Z
- **Tasks:** 2 (each split into RED → GREEN per plan tdd="true")
- **Files created:** 4
- **Files modified:** 0
- **Tests added:** 32 (14 + 10 + 2 + 6)
- **Expect calls:** 40 (17 + 12 + 4 + 8, minus overlap)

## Accomplishments

- **build_lists.ts fully covered (0% → 100%):** 13 buildListsApi methods × 14 tests (copyBuildList gets 2 tests for the explicit-name vs. omitted-name branches).
- **build_list_parts.ts nearly fully covered (0% → 100% lines, 83.33% branches):** 10 methods × 10 tests. All 3 nested-URL patterns (`:buildListId/create-and-add-part`, `:buildListId/parts/:partId`, `:buildListId`) asserted with literal interpolated strings using mockBuildList.id + mockPart.id. Remaining branch gap is the `car_ids ?? undefined` and `is_universal ?? false` coalesce pair inside the createPartAndAddToBuildList spread — exercising both sides needs two fixture variants, deferred as not required by acceptance criteria.
- **build_list_phases.ts fully covered (0% → 100%):** 2 methods × 2 tests (minimal surface — update + delete by phase ID; create lives on buildListsApi which is covered by build_lists.test.ts line 209 createPhase test).
- **build_logs.ts fully covered (0% → 100%):** 5 methods × 6 tests. The URLSearchParams query-string branch in getBuildLogByBuildList is covered by two separate `it` blocks (bare URL vs. `?skip=5&limit=10` appended).
- **Zero test regressions in sibling suites:** only 4 new files created, all imports go through the D-18 dual-mock that was already green before this plan.
- **All acceptance criteria met:** every minimum-count check passes with slack (14 ≥ 8, 17 ≥ 16, 10 ≥ 6, 12 ≥ 12, 2 ≥ 2, 4 ≥ 4, 6 ≥ 4, 8 ≥ 8, zero `.skip(` occurrences, at least one `mockBuildList`/`mockPart` reference in each nested-URL file).

## Task Commits

Each task was committed atomically on this worktree's main branch:

1. **Task 1: Write build_lists.test.ts and build_list_parts.test.ts** — `90db6ef` (test)
2. **Task 2: Write build_list_phases.test.ts and build_logs.test.ts** — `d23ef0d` (test)

_Metadata commit for SUMMARY.md will be made by the orchestrator after this agent returns._

## Files Created

- `frontend/src/api/build_lists.test.ts` — 14 tests. Covers create/get/update/delete (×4), listBuildLists with default + populated params (×2), getBuildListsWithVotes with car_id+sort+min_cost_cents filters, getBuildListsByCar and getBuildListsByUser nested URLs with pagination params, countBuildLists, copyBuildList with and without new_name, getPhases, createPhase.
- `frontend/src/api/build_list_parts.test.ts` — 10 tests. Covers createPartAndAddToBuildList composite body, addPartToBuildList nested URL, updateBuildListPart (by buildListId+partId) PUT, updateBuildListPartById PUT, removeBuildListPart DELETE (nested URL), deleteBuildListPartById DELETE, getBuildListPartsBasic GET, getBuildListParts GET (with /parts suffix), countBuildListsContainingPart nested count URL, countBuildListParts.
- `frontend/src/api/build_list_phases.test.ts` — 2 tests. Covers updatePhase PUT, deletePhase DELETE (by phase ID, independent of parent build list).
- `frontend/src/api/build_logs.test.ts` — 6 tests. Covers getBuildLogByBuildList with no pagination (bare URL) and with skip+limit (query string appended), createBuildLogPost (nested POST to /build-logs/build-list/:id/posts), updateBuildLogPost (PUT to /build-logs/posts/:postId), deleteBuildLogPost (DELETE), countBuildLogPosts.

## Coverage Delta vs Baseline

Source: `.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt` (Plan 01 artifact).

| File                                 | Baseline (Stmts/Branch/Funcs/Lines) | After Plan 04     | Delta                |
| ------------------------------------ | ----------------------------------- | ----------------- | -------------------- |
| `frontend/src/api/build_lists.ts`       | 0 / 0 / 0 / 0                      | 100 / 100 / 100 / 100 | +100 all             |
| `frontend/src/api/build_list_parts.ts`  | 0 / 0 / 0 / 0                      | 100 / 83.33 / 100 / 100 | +100 lines, +83.33 branch |
| `frontend/src/api/build_list_phases.ts` | 0 / 0 / 0 / 0                      | 100 / 100 / 100 / 100 | +100 all             |
| `frontend/src/api/build_logs.ts`        | 0 / 0 / 0 / 0                      | 100 / 100 / 100 / 100 | +100 all             |

**Aggregate `src/api`** directory coverage lifted from Plan 01 baseline (0% on these 4 files) to 16.78% lines / 65.38% branches / 64.44% functions / 16.78% stmts after Plan 04 (remaining 15 domain modules still at 0 until their plans run in Wave 1).

### Branch gap in build_list_parts.ts (83.33% vs 100%)

Unexercised branches are the two `??` coalescents inside `createPartAndAddToBuildList`:

```ts
car_ids: partData.car_ids ?? undefined,
is_universal: partData.is_universal ?? false,
// later:
build_list_phase_id: buildListPartData.build_list_phase_id ?? undefined,
quantity: buildListPartData.quantity ?? 1,
```

Our test supplies `car_ids: null`, `is_universal: false`, `build_list_phase_id: null`, `quantity: 2` — so the "value provided" side of each coalesce fires but the "nullish defaulted" side is implicitly covered only by one of the branches per operator. Fully closing this is a two-fixture test (explicit values + omitted) — deferred as it is not required by acceptance criteria and the plan's minimum (≥6 its, ≥12 expects) is already satisfied with the current 10 tests.

## Branch-Testing Methods (per plan "Note any methods that required branch testing")

- **`copyBuildList`** — 2 tests: one with explicit `new_name: 'My Copy'`, one with omitted arg. Asserts the source's `newName || null` coalesce correctly produces `{ new_name: 'My Copy' }` and `{ new_name: null }` respectively. Plan called this out explicitly (plan §behavior: "copyBuildList test ... asserts the free-tier-cap branch is not exercised in this test — just happy path"); the branch tested here is the frontend argument-coalesce, not the backend free-tier cap.
- **`getBuildLogByBuildList`** — 2 tests: one with no skip/limit (bare URL), one with both (query string appended). Covers the source's `if (skip !== undefined)`, `if (limit !== undefined)`, and `queryString ? `?${queryString}` : ''` conditional branches.
- **`listBuildLists`** — 2 tests: one with default undefined params, one with populated params. Covers the source's `{ params }` forwarding in both the "no filters" and "with filters" cases.

## Decisions Made

See frontmatter `key-decisions` block. Most significant:

- **eslint-disable scope** was narrowed per-file — build_list_phases and build_logs only disable `unbound-method` (they don't use `expect.objectContaining`), while build_lists and build_list_parts disable both `unbound-method` and `no-unsafe-assignment`. When I left `no-unsafe-assignment` in build_list_parts.test.ts initially, eslint emitted an "Unused eslint-disable directive" warning — narrowing fixed it.
- **No `vi.mock('../api/client', ...)` call in any test file.** Relied on the dual mock from `frontend/src/test/setup.ts` (landed in Plan 01 via D-18). This was explicitly called out in the plan read_first: "DO NOT re-mock `../api/client` — setup.ts D-18 handles it."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] ESLint `@typescript-eslint/unbound-method` fires on `vi.mocked(apiClient.get)` and `expect(apiClient.get)` patterns**

- **Found during:** Task 1 (first lint run after writing build_lists.test.ts + build_list_parts.test.ts)
- **Issue:** `frontend/eslint.config.js` applies `tseslint.configs.recommendedTypeChecked` to all src files including `*.test.ts`. That bundle turns on `@typescript-eslint/unbound-method` as an error. The canonical Wave 1 test pattern (PATTERNS.md §7) references `apiClient.get` / `.post` / `.put` / `.delete` as unbound method references in `vi.mocked(...)` and `expect(...).toHaveBeenCalledWith(...)` lines. Every call produces a lint error — ~22 per file on build_lists.test.ts, ~20 per file on build_list_parts.test.ts.
- **Fix:** Added a 5-line comment explaining the false positive and a file-level `/* eslint-disable @typescript-eslint/unbound-method */` (also `, @typescript-eslint/no-unsafe-assignment` in build_lists.test.ts because its `expect.objectContaining({...})` inside `{ params: ... }` triggered two `no-unsafe-assignment` errors). The rule is a false positive here because:
  1. The mock's `vi.fn()` instances are created as object properties on the `mockApiClient` object literal in setup.ts, not as class methods with `this` binding,
  2. Vitest invokes them through the same object identity `mockApiClient.get(...)` internally when dispatched,
  3. The `apiClient` import resolves to the exact same `mockApiClient` object (D-18 proof in 08-01 SUMMARY), so there's no unbound-method risk in practice.
- **Files modified:** frontend/src/api/build_lists.test.ts, frontend/src/api/build_list_parts.test.ts (added disable header), frontend/src/api/build_list_phases.test.ts and frontend/src/api/build_logs.test.ts authored with disable header from the start.
- **Verification:** `npx eslint src/api/build_lists.test.ts src/api/build_list_parts.test.ts src/api/build_list_phases.test.ts src/api/build_logs.test.ts` → 0 errors / 0 warnings. `npm test -- --run <the 4 files>` → all 32 tests pass.
- **Committed in:** 90db6ef (Task 1) — disable header present on both files at commit time.

**2. [Rule 1 - Bug] Missing `expect` in build_list_phases.test.ts deletePhase test pushed expect count below plan minimum of 4**

- **Found during:** Task 2 acceptance check (`grep -c "expect(" src/api/build_list_phases.test.ts` returned 3)
- **Issue:** Plan acceptance criterion requires `grep -c "expect(" frontend/src/api/build_list_phases.test.ts` to return at least 4. My first draft had:
  - updatePhase test: 2 expects (URL+body, result.data.id)
  - deletePhase test: 1 expect (URL+body)
  = 3 total. Plan minimum was 4.
- **Fix:** Added a second expect to the deletePhase test asserting `result.data.id === mockPhaseId`, consistent with the updatePhase test structure. Now 4 expects total (matches plan minimum exactly).
- **Files modified:** frontend/src/api/build_list_phases.test.ts
- **Verification:** `grep -c "expect(" src/api/build_list_phases.test.ts` → 4. Tests still pass.
- **Committed in:** d23ef0d (Task 2) — fix applied before commit.

---

**Total deviations:** 2 auto-fixed (1 blocking / lint rule in the established Wave 1 pattern, 1 bug / acceptance-criterion shortfall in my first deletePhase draft).
**Impact on plan:** No scope creep. All plan acceptance criteria met. The eslint-disable pattern is now the de-facto Wave 1 convention; sibling Wave 1 test files (parts.test.ts, votes.test.ts, car_generations.test.ts, bug_reports.test.ts, reports.test.ts — all present on filesystem as untracked from parallel executors) likely need the same fix independently.

## Issues Encountered

- **Parallel executor artifacts on disk:** Running `git status --short` shows several untracked `src/api/*.test.ts` files (parts, car_generations, votes, bug_reports, reports) dropped by sibling Phase 8 Wave 1 executors working in this shared worktree filesystem. I deliberately ignored them — they are out-of-scope for plan 08-04. Only my 4 files are staged and committed.
- **`coverage/` directory re-emits 3 pre-existing "Unused eslint-disable directive" warnings** in the v8 HTML reporter's bundled JS (block-navigation.js, prettify.js, sorter.js). Same as noted in 08-01 SUMMARY; not introduced by this plan; `frontend/coverage/` is gitignored.

## User Setup Required

None — no external service configuration. All code changes are isolated to the frontend test suite.

## Next Phase Readiness

- **Wave 3 plans 08-12 (buildLists pages) and 08-13 (builder pages) unblocked** — can now assert that calls to `buildListsApi.*`, `buildListPartsApi.*`, `buildListPhasesApi.*`, and `buildLogsApi.*` go to the URLs and methods their tests guarantee.
- **Nested URL patterns (`:buildListId/parts/:partId`) validated** — page tests can trust that calling these helpers produces the exact URL the backend expects, without re-testing the URL construction.
- **Branch-coverage gap in `createPartAndAddToBuildList` (83.33% → 100%) is optional follow-up** — not a blocker. A single additional test with `car_ids: ['car-id']` and `is_universal: true` would close it. Defer to Wave 5 gap-fill or leave if global threshold allows.
- **No blockers, no concerns.**

## Self-Check: PASSED

- `test -f frontend/src/api/build_lists.test.ts` → FOUND (14 its, 17 expects, 80+ lines ✓)
- `test -f frontend/src/api/build_list_parts.test.ts` → FOUND (10 its, 12 expects, 70+ lines ✓)
- `test -f frontend/src/api/build_list_phases.test.ts` → FOUND (2 its, 4 expects, 25+ lines ✓)
- `test -f frontend/src/api/build_logs.test.ts` → FOUND (6 its, 8 expects, 45+ lines ✓)
- `grep -c "\.skip(" frontend/src/api/build_list{s,_parts,_phases,_logs}.test.ts` → 0 across all 4 files ✓
- `grep -c "mockBuildList" frontend/src/api/build_lists.test.ts` → ≥1 (27 usages) ✓
- `grep -c "mockBuildList\|mockPart" frontend/src/api/build_list_parts.test.ts` → ≥2 (21 combined usages) ✓
- `git log --oneline -3` → `d23ef0d` and `90db6ef` commits FOUND
- `cd frontend && npm test -- --run src/api/build_lists.test.ts src/api/build_list_parts.test.ts src/api/build_list_phases.test.ts src/api/build_logs.test.ts` → 32 tests pass, 0 fail
- `cd frontend && npx eslint src/api/build_lists.test.ts src/api/build_list_parts.test.ts src/api/build_list_phases.test.ts src/api/build_logs.test.ts` → 0 errors, 0 warnings
- `cd frontend && npx tsc --noEmit --project tsconfig.app.json` → exits 0 (no errors in my test files)
- Coverage verification: build_lists.ts / build_list_phases.ts / build_logs.ts all at 100% across stmts/branch/funcs/lines; build_list_parts.ts at 100/83.33/100/100 (branch gap documented above)

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
