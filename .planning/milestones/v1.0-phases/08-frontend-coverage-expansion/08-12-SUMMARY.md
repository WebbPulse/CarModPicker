---
phase: 08-frontend-coverage-expansion
plan: 12
subsystem: frontend-testing
tags: [frontend, page-tests, parts, wave-3, vitest]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "Shared test infrastructure — mockUseAuth singleton in test-mocks.ts, dual api-client mock in setup.ts (D-18), `testScenarios.authenticated`/`unauthenticated` fixtures"
  - phase: 08-frontend-coverage-expansion
    plan: 03
    provides: "parts API domain module tests — confirmed apiClient.get('/parts/with-votes', {params}) shape before wiring page tests to it"
  - phase: 08-frontend-coverage-expansion
    plan: 08
    provides: "usePartsFilters hook test — provided the canonical `vi.mock('../services/Api', async () => {...})` shim-forwarder pattern that this plan reuses"
provides:
  - "PartsCatalog page smoke test — render + /parts/with-votes fetch + empty state + auth-gated shortcut"
  - "EditPart page smoke test — authenticated render + part-fetch + form submit through apiClient.put + permission-denied branch"
  - "UserParts page smoke test — authenticated render + empty state + unauthenticated error gate"
  - "Local renderWithRouter pattern — page tests that bypass test-utils.tsx's services/Api mock without regressing useAuth seeding"
affects: ["08-20 (coverage delta aggregation)", "future frontend/src/pages/ test authoring"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local renderWithRouter: pages that consume named API handles from services/Api wrap children in <MemoryRouter> + optional <Routes> and seed useAuth via mockUseAuth directly — bypasses the services/Api default-only mock that test-utils.tsx registers"
    - "ResizeObserver stub at test-file top level: required anywhere PartList (or any consumer of useContainerWidth) mounts under jsdom — constructor no-op is enough because nothing observes anything meaningful in the test DOM"
    - "PaginatedResponse<PartReadWithVotes> fixture factory: inline make* helper inside the test file rather than adding a new mock to test/mocks/api.ts — tests with diverging vote/pagination needs stay isolated"

key-files:
  created:
    - "frontend/src/pages/parts/PartsCatalog.test.tsx (234 lines, 3 it-blocks, 6 expects)"
    - "frontend/src/pages/parts/EditPart.test.tsx (219 lines, 3 it-blocks, 8 expects)"
    - "frontend/src/pages/parts/UserParts.test.tsx (232 lines, 3 it-blocks, 7 expects)"
  modified: []

key-decisions:
  - "Bypass test-utils.tsx's customRender because its vi.mock('../../services/Api') strips named domain-API exports (partsApi, categoriesApi, etc.) that usePartsFilters + PartList + EditPartForm all import from the shim. When the test file's own vi.mock runs BEFORE test-utils's vi.mock (via hoisting order), test-utils wins and the named exports disappear. The cheapest safe fix is to not import `render` from test-utils at all."
  - "EditPart submit test seeds a fully-populated PartRead (category_id + part_manufacturer_id matching mocked list data) so both HTML5 <select required> validation and EditPartForm's custom validation at line 243 pass through to the PUT. A half-stub surfaces as a validation error and gives no PUT evidence."
  - "mockPart is authored by the canonical owner (mockUser.id === mockPart.user_id) so the authenticated render test doesn't need an admin flag. The permission-denied branch uses a stranger UUID instead — cleaner boundary than flipping is_admin."

patterns-established:
  - "Page tests that touch /parts surface register a per-file vi.mock for `../../services/Api` that imports `../../api/client` (the setup.ts-mocked apiClient) and re-exposes every named domain export as a thin `client.get/post/put` forwarder. Assertions on apiClient calls travel through these forwarders so `expect(apiClient.put).toHaveBeenCalledWith(...)` keeps working."
  - "Page tests for routes that read :id params wrap the component in <MemoryRouter initialEntries={[path]}><Routes><Route path='/real/path' element={children} /></Routes></MemoryRouter>. Without the <Routes> wrapper useParams returns undefined and the page short-circuits."

requirements-completed: [SAFE-03]

# Metrics
duration: ~10min
completed: 2026-04-24
---

# Phase 8 Plan 12: Parts Page Tests Summary

**3 new parts-page test files (PartsCatalog, EditPart, UserParts) with 9 it-blocks total, all passing and type-safe. Tests bypass test-utils.tsx's customRender to avoid a services/Api mock conflict that strips named domain APIs, while reusing the same mockUseAuth singleton so auth scenarios stay behaviorally identical to the standard testScenarios fixtures.**

## Performance

- **Duration:** ~10 min (2026-04-24T18:02Z → 18:13Z)
- **Tasks:** 2 (Task 1: PartsCatalog + UserParts; Task 2: EditPart)
- **Commits:** 3 atomic (efcc682, d878685, 5511a84)
- **Files created:** 3 (one per page)
- **Files modified:** 0 (no changes to existing test infrastructure)

## Test Counts Per File

| File | Lines | it-blocks | expects | Coverage surface |
|------|-------|-----------|---------|------------------|
| `PartsCatalog.test.tsx` | 234 | 3 | 6 | Render + fetch + empty state + auth-gated "My Parts" shortcut |
| `EditPart.test.tsx` | 219 | 3 | 8 | Authenticated owner render + form submit + permission-denied |
| `UserParts.test.tsx` | 232 | 3 | 7 | Authenticated user's parts + empty state + unauthenticated error |
| **Total** | **685** | **9** | **21** | — |

## Coverage Delta (frontend/src/pages/parts/*)

Baseline (from `.planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt`) for the `pages/parts/` route group was 0% across all 3 files — no page tests existed prior to this plan. With this plan's 3 test files:

- `PartsCatalog.tsx` — mount + render path + auth-gated branch + empty-state branch now exercised
- `EditPart.tsx` — owner, non-owner (permission-denied), and submit paths now exercised (the loading + "part not found" branches remain untested)
- `UserParts.tsx` — authenticated + unauthenticated branches exercised (delete-confirmation flow remains untested)

Plan 08-20 will re-run `npm run test:coverage` against the updated file set and report the exact per-file delta numbers.

## Accomplishments

- **All 3 files pass on first commit** (modulo the one flake fix below). 9 passing tests, 0 skipped, 0 type-check errors.
- **Authentication paths fully covered** — each file exercises both the auth-gated happy path and the denied/unauthenticated branch.
- **Real API shapes verified against the source** — `PaginatedResponse<PartReadWithVotes>` is `{ data, pagination }` per `types/Api.ts:334-337` (confirmed before wiring fixtures); `apiClient.put('/parts/${id}', data)` is the actual update call (confirmed at `EditPartForm.tsx:36-39`).
- **Pattern-documented bypass of test-utils conflict** — the file-header comments explain why each test doesn't use `render` from `../../test/utils/test-utils`. Future page-test authors who hit the same services/Api conflict have a reference.
- **Concurrent setup.ts change absorbed** — while this plan was running, plan 08-10 landed an `importOriginal`-based services/Api mock in setup.ts. Our local vi.mock forwarders still work (they override setup.ts's mock in the specific files that need custom handles) and no rework was needed.

## Task Commits

1. **Task 1 — PartsCatalog + UserParts tests** — `efcc682` (test(08-12))
2. **Task 2 — EditPart test** — `d878685` (test(08-12))
3. **Flake fix — waitFor around display-value assertion** — `5511a84` (fix(08-12))

## Files Created

### `frontend/src/pages/parts/PartsCatalog.test.tsx`

- Stubs ResizeObserver at module top level (jsdom doesn't ship one, `PartList → useContainerWidth` requires it).
- Per-file `vi.mock('../../services/Api')` re-exposes `partsApi`, `partVotesApi`, `categoriesApi`, `partManufacturersApi`, `carGenerationsApi`, `buildListPartsApi` as forwarders over the mocked apiClient.
- `vi.mock('../../hooks/useAuth')` returns `mockUseAuth()` — same singleton test-utils uses.
- Local `renderWithRouter(ui, { route })` wraps in `<MemoryRouter initialEntries={[route]}>`.
- `seedAuth({ isAuthenticated, user })` sets up mockUseAuth per-test.
- 3 it-blocks: title + fetch of `/parts/with-votes`, empty-state copy "No parts found. Try adjusting your filters.", and auth-gated "My Parts" shortcut.

### `frontend/src/pages/parts/EditPart.test.tsx`

- Same services/Api forwarder pattern, narrower — only partsApi / categoriesApi / partManufacturersApi / carGenerationsApi (no PartList here).
- `renderAtEditRoute(ui, partId)` wraps in `<MemoryRouter initialEntries={[/parts/:id/edit]}>` PLUS `<Routes><Route path="/parts/:partId/edit" element={children} /></Routes>` so `useParams()` returns the real :partId.
- `mockFullPart = { ...mockPart, category_id, part_manufacturer_id }` + paired mockCategory / mockManufacturer mocks let the form's HTML5 required validation and custom submit validation both pass, enabling the PUT assertion.
- 3 it-blocks: render seeds Part Name input, submit fires apiClient.put with new name, non-owner sees permission-denied ErrorAlert.

### `frontend/src/pages/parts/UserParts.test.tsx`

- Same ResizeObserver stub + services/Api forwarder pattern as PartsCatalog.
- 3 it-blocks: authenticated user's parts list renders, empty-state copy "You haven't created any parts yet.", and unauthenticated login-required ErrorAlert.

## Decisions Made

- **Local renderWithRouter over test-utils customRender.** test-utils.tsx registers `vi.mock('../../services/Api', () => ({ default: mockApiClient }))` which strips every named domain-API export. When our test file ALSO registers a `vi.mock('../../services/Api')` with the needed forwarders, test-utils's mock hoists AFTER ours (because test-utils is imported into our file AFTER the file's own vi.mock statements) and wins. Net effect: our forwarders are silently overridden and `partsApi.getPart` is undefined at runtime. Bypassing `render` removes the conflict.
- **Accept HTML5 + custom validation coupling in the submit test.** EditPartForm has both `<select required>` HTML5 validation on Category and a custom `setValidationError('Part manufacturer is required')` path. Either one short-circuits submit. The test seeds data that satisfies both so the PUT fires, rather than asserting on the validation error message — a post-submit API assertion is a stronger signal than a validation-error assertion.
- **waitFor around `getByDisplayValue` for the form's Part Name input.** EditPartForm seeds formData via `useEffect [part]`, which runs one microtask AFTER part arrives. The title (`part.name` inlined) renders first, so chaining a synchronous `getByDisplayValue` after a `waitFor(title)` works when the file runs alone but flakes under parallel execution. One extra `waitFor` closes the race.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] test-utils.tsx services/Api mock strips named exports**

- **Found during:** Task 1, first test run.
- **Issue:** The plan's action block imports `render` from `../../test/utils/test-utils`. That import chain registers `vi.mock('../../services/Api', () => ({ default: mockApiClient }))` — no named exports. `usePartsFilters` imports `partsApi`, `categoriesApi`, `carGenerationsApi`, and `partManufacturersApi` from that shim. First run failed every test with `No "partsApi" export is defined on the "../../services/Api" mock`. This is the same shape plan 08-08 hit and documented in `usePartsFilters.test.tsx`.
- **Fix:** Bypass `render` from test-utils entirely. Build a local `renderWithRouter` that wraps children in `<MemoryRouter>` and seeds `mockUseAuth` with the same shape test-utils uses — behaviorally identical to `testScenarios.authenticated` / `testScenarios.unauthenticated` without the services/Api mock conflict. Add a per-file `vi.mock('../../services/Api', async () => {...})` that re-exposes every named handle the page tree reaches as a forwarder over the mocked apiClient.
- **Files modified:** All 3 test files (during initial authoring, not a subsequent edit).
- **Verification:** All 9 tests pass; no "No export" errors.
- **Committed in:** `efcc682` (Task 1) + `d878685` (Task 2).

**2. [Rule 2 - Missing critical functionality] ResizeObserver stub**

- **Found during:** Task 1, second test iteration.
- **Issue:** `PartList` (rendered by both `PartsCatalog` and `UserParts`) calls `useContainerWidth`, which calls `new ResizeObserver(...)` on mount. jsdom doesn't ship a ResizeObserver constructor, so mounting throws `ReferenceError: ResizeObserver is not defined`.
- **Fix:** Stub `globalThis.ResizeObserver` at the top of each page test file with a no-op class (observe/unobserve/disconnect return void). Pattern reused from `App.coverage.test.tsx:54-68`.
- **Files modified:** `PartsCatalog.test.tsx`, `UserParts.test.tsx` (EditPart doesn't render PartList so doesn't need the stub).
- **Verification:** Mount succeeds, form/list renders in jsdom.
- **Committed in:** `efcc682` (Task 1).

**3. [Rule 1 - Bug] Flaky `getByDisplayValue` in EditPart render test**

- **Found during:** Task 2, running all 3 parts tests in parallel (intermittent 50% failure rate).
- **Issue:** EditPart's first test asserts `screen.getByDisplayValue(mockPart.name)` synchronously after `await waitFor(() => title)`. EditPartForm seeds `formData.name` via `useEffect [part]`, which runs one microtask AFTER `part.name` is inlined into the title. When the parts suite ran in parallel, timing sometimes ran the synchronous assertion before the effect fired. Alone-file runs always passed; suite runs flaked.
- **Fix:** Wrap the `getByDisplayValue` assertion in its own `waitFor`. Absorbs the microtask gap without any implementation change.
- **Files modified:** `EditPart.test.tsx`.
- **Verification:** 5/5 consecutive `npm test -- --run src/pages/parts/` runs pass. Before: 50% failure. After: 0% failure.
- **Committed in:** `5511a84`.

---

**Total deviations:** 3 auto-fixed (1 blocking / test-infra conflict, 1 missing jsdom stub, 1 race-condition fix).
**Impact on plan:** No scope creep. All deviations are about test-infra mechanics, not about what's being tested. The behavior under test matches the plan's spec exactly: happy path + empty state + auth-gate per file, plus submit for EditPart.

## Issues Encountered

- **Pre-existing failures in Login.test.tsx** (from concurrent parallel worker plan 08-10). 2 unrelated tests fail in that file. None of my 9 tests are affected. Out of scope.
- **Concurrent setup.ts change by another worker.** While this plan was authoring, setup.ts gained an `importOriginal`-based services/Api mock (apparently from plan 08-10 working on authentication pages). My local vi.mock forwarders still take precedence in my files because vi.mock is file-scoped; no adjustment needed. Noted for the phase's integration.

## User Setup Required

None.

## Next Phase Readiness

- **Plan 08-20 (coverage aggregation)** can include parts/ page coverage in its delta calculation.
- **Future page-test authors** hitting the same test-utils services/Api conflict have a reference: see the file-header comments in any of these 3 test files for the bypass rationale and forwarder shape.
- **No blockers.** No concerns.

## Self-Check: PASSED

- `test -f frontend/src/pages/parts/PartsCatalog.test.tsx` → FOUND (234 lines, 3 it-blocks, 6 expects, 0 .skip())
- `test -f frontend/src/pages/parts/EditPart.test.tsx` → FOUND (219 lines, 3 it-blocks, 8 expects, 0 .skip())
- `test -f frontend/src/pages/parts/UserParts.test.tsx` → FOUND (232 lines, 3 it-blocks, 7 expects, 0 .skip())
- `grep -c "mockPart" frontend/src/pages/parts/{PartsCatalog,EditPart,UserParts}.test.tsx` → 4 / 9 / 5 respectively
- `grep -c "render(" frontend/src/pages/parts/*.test.tsx` → 14 / 12 / 9 respectively
- `grep -c "testScenarios.authenticated" frontend/src/pages/parts/EditPart.test.tsx` → 1 (documentation reference)
- `grep -c "\.skip(" frontend/src/pages/parts/*.test.tsx` → 0 / 0 / 0
- `npm test -- --run src/pages/parts/` → 3 files / 9 tests pass, 5/5 consecutive runs stable
- `npm run type-check` → exits 0
- `git log --oneline` commits FOUND: `efcc682`, `d878685`, `5511a84`

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
