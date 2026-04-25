---
phase: 08-frontend-coverage-expansion
plan: 06
subsystem: testing
tags: [frontend, vitest, api-tests, wave-1, utility-cluster, search, app-settings, utility]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "Dual api-client mock in setup.ts (D-18) so api/*.test.ts can import apiClient from '../api/client' without per-file vi.mock; mockBuildList / mockPart / mockUser factories in test/mocks/api.ts"
provides:
  - "searchApi unit tests — 3 tests covering the single search(params) method (happy path with mixed results, q-only form, empty-results envelope)"
  - "appSettingsApi unit tests — 3 tests covering get (read) and update (update + empty patch body)"
  - "utilityApi unit tests — 2 tests covering getRoot (GET /) and healthCheck (GET /health)"
  - "MockedFunction<typeof apiClient.<verb>> cast pattern — first-use in repo; replaces the vi.mocked(apiClient.verb) pattern that trips @typescript-eslint/unbound-method under the strict-lint config, and replaces vi.mocked(apiClient) that trips @typescript-eslint/no-unsafe-call"
affects: ["08-02 through 08-05 (sibling Wave 1 API-test plans) — they can copy the MockedFunction-cast + inline-eslint-disable pattern verbatim", "all future frontend API-module tests"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level `const <verb>Mock = apiClient.<verb> as MockedFunction<typeof apiClient.<verb>>` with `/* eslint-disable-next-line @typescript-eslint/unbound-method */` above — the canonical way to reference the setup.ts D-18 mock while keeping strict-lint green"
    - "Three it-blocks per domain test file, each asserting URL + call count + response-shape"
    - "Empty-results / empty-body test as the second-most-common assertion after the happy path"

key-files:
  created:
    - "frontend/src/api/search.test.ts (3 tests, 107 lines)"
    - "frontend/src/api/app_settings.test.ts (3 tests, 78 lines)"
    - "frontend/src/api/utility.test.ts (2 tests, 61 lines)"
  modified: []

key-decisions:
  - "utility.ts Option A (test) chosen over Option B (D-15 exclude): both methods hit distinct hard-coded URLs ('/' vs '/health') which IS the behavior worth asserting; testing preserves 9 source lines of coverage that an exclusion would drop"
  - "MockedFunction cast + inline eslint-disable over vi.mocked(apiClient.verb): strict-lint @typescript-eslint/unbound-method fires on the member reference expression, but the cast is semantically safe because setup.ts D-18 guarantees apiClient is the mock object"
  - "Each test file narrows only the verbs it uses (searchApi: getMock; appSettingsApi: getMock + putMock; utilityApi: getMock) rather than re-casting per-call-site"

patterns-established:
  - "api/*.test.ts module-level HTTP-verb mock narrowing: `const getMock = apiClient.get as MockedFunction<typeof apiClient.get>` with a single block-comment eslint-disable above each declaration"
  - "Test structure for tiny API modules: happy-path-with-full-response + minimal-params-form + empty-response, 2-3 tests per file"
  - "D-15 exclusion heuristic refined: URL-routing runtime logic (even 1-line wrappers around apiClient.get) is not zero-runtime — test, do not exclude"

requirements-completed: [SAFE-03]

# Metrics
duration: 7min
completed: 2026-04-24
---

# Phase 8 Plan 06: Utility Cluster API Tests Summary

**searchApi, appSettingsApi, and utilityApi (61 source lines across 3 modules) lifted from 0% to 100% coverage via 8 new tests; utility.ts tested rather than D-15 excluded because its URL-routing runtime logic is deterministic and cheap to assert.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-24T17:24:00Z (after `npm install` in worktree)
- **Completed:** 2026-04-24T17:32:00Z
- **Tasks:** 2
- **Files created:** 3 (search.test.ts, app_settings.test.ts, utility.test.ts)
- **Files modified:** 0

## Accomplishments

- **3 new test files covering the entire Utility cluster** (search.ts, app_settings.ts, utility.ts) — 61 source lines, 8 new tests, all at 100% line/func/branch/stmt coverage.
- **New strict-lint-compatible mock-narrowing pattern landed:** `const getMock = apiClient.get as MockedFunction<typeof apiClient.get>` with a single inline `/* eslint-disable-next-line @typescript-eslint/unbound-method */`. This is the first in-repo pattern for API-test mocking that plays well with setup.ts D-18 AND the strict-lint config (FE-01). Plans 08-02 through 08-05 can copy this verbatim.
- **D-15 exclusion decision made for utility.ts (Option A — test):** the file has runtime logic (URL routing), just trivial runtime logic, so it's not a D-15 candidate per the decision rule ("zero-runtime-logic files"). Documented in this summary and in the utility.test.ts header comment so future plans consulting the precedent see the rationale.
- **Zero-regression proof:** `npm test -- --run` → 12 files / 84 tests pass (baseline was 9 files / 76 tests; net +3 files / +8 tests). `npm run lint` → 0 errors. `npm run type-check` → exits 0.

## Task Commits

Each task was committed atomically on this worktree's branch:

1. **Task 1: Write search.test.ts and app_settings.test.ts** — `f0cfb70` (test)
2. **Task 2: Decide utility.test.ts — test or D-15 exclude (chose test)** — `8597617` (test)

_Metadata commit for SUMMARY.md will follow per the plan's final-commit protocol._

## Files Created/Modified

### Created

- `frontend/src/api/search.test.ts` (107 lines, 3 tests) — covers `searchApi.search({q, skip?, limit?})`. Tests: full-params happy path with populated `build_lists` / `users` / `parts` arrays; q-only form without skip/limit; empty-results envelope for a no-match query. Asserts URL `'/search/'`, params shape, and response-envelope structure.
- `frontend/src/api/app_settings.test.ts` (78 lines, 3 tests) — covers `appSettingsApi.get()` and `appSettingsApi.update(body)`. Tests: GET read path returns the `AppSettings` envelope; PUT update path forwards body + returns updated envelope; PUT with empty patch body `{}` forwards unchanged. Asserts URL `'/app-settings/'` for both verbs.
- `frontend/src/api/utility.test.ts` (61 lines, 2 tests) — covers `utilityApi.getRoot()` (GET `/`) and `utilityApi.healthCheck()` (GET `/health`). Asserts each hits its exact hard-coded URL and returns the `Record<string, *>` envelope verbatim.

### Modified

- None — only new files; no changes to source, setup, or config.

## Decisions Made

- **utility.ts: Option A (test) over Option B (D-15 exclude).** Rationale: Both methods invoke `apiClient.get` with distinct hard-coded URLs. That URL-routing runtime logic IS the testable surface; D-15 is scoped for zero-runtime-logic files (pure re-export barrels, type files). A test for `healthCheck → '/health'` would catch a typo like `/healt` that a coverage exclusion would silently miss. Cost is ~30 LoC of trivial test code; benefit is 9 source lines of preserved coverage (100% of utility.ts). Verdict: test. Evidence — the full 9-line source pasted here for the record:
  ```ts
  // Utility / health API. No backend domain mirror — these are top-level
  // liveness / root probes. Extracted from services/Api.ts (lines 941-944)
  // per Phase 6 D-22.
  import { apiClient } from './client';

  export const utilityApi = {
    getRoot: () => apiClient.get<Record<string, string>>('/'),
    healthCheck: () => apiClient.get<Record<string, unknown>>('/health'),
  };
  ```
- **MockedFunction cast over `vi.mocked(apiClient.verb)`.** Rationale: The strict-lint config (Phase 6 FE-01) has `@typescript-eslint/unbound-method` and `@typescript-eslint/no-unsafe-call` as errors. `vi.mocked(apiClient.get)` trips unbound-method (method reference of a class instance). `vi.mocked(apiClient).get` trips no-unsafe-call (vi.mocked of the full AxiosInstance returns `error` type). The module-level cast `apiClient.get as MockedFunction<typeof apiClient.get>` with an inline disable is the cleanest pattern that's both semantically safe (setup.ts D-18 guarantees apiClient IS the mock) and strict-lint-green at every call site.
- **Three test files landed as two commits.** Task 1 grouped search + app_settings; Task 2 added utility solo. This mirrors the plan's task structure (Task 1 = search+settings, Task 2 = utility decision) and keeps the utility.ts decision-record commit reviewable on its own.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Strict-lint `@typescript-eslint/unbound-method` + `@typescript-eslint/no-unsafe-call` on initial test drafts**

- **Found during:** Task 1 (first lint run after writing search.test.ts + app_settings.test.ts)
- **Issue:** The PATTERNS.md §7 skeleton uses `vi.mocked(apiClient.get).mockResolvedValueOnce(...)` and `expect(apiClient.get).toHaveBeenCalledWith(...)`. Both trip `@typescript-eslint/unbound-method` (14 errors across the two files). Swapping to `vi.mocked(apiClient).get` then tripped `@typescript-eslint/no-unsafe-call` (6 errors) because vi.mocked of the AxiosInstance surface returns an `error`-typed object.
- **Fix:** Introduced a module-level `MockedFunction` cast per-verb (`const getMock = apiClient.get as MockedFunction<typeof apiClient.get>`) guarded by an inline `/* eslint-disable-next-line @typescript-eslint/unbound-method */` block-comment. setup.ts (D-18) guarantees `apiClient.get` IS a `vi.fn()` at runtime, so the cast is semantically accurate; the disable is narrow (1 line per verb).
- **Files modified:** `frontend/src/api/search.test.ts`, `frontend/src/api/app_settings.test.ts` (both rewritten before the Task 1 commit)
- **Verification:** `npm run lint` → 0 errors, 0 warnings. `npm test -- --run` → 6 tests pass.
- **Committed in:** `f0cfb70` (Task 1 commit)

**2. [Rule 1 - Bug] TS4111 on `result.data.status` in utility.test.ts**

- **Found during:** Task 2 (first type-check after writing utility.test.ts)
- **Issue:** `utilityApi.healthCheck` returns `AxiosResponse<Record<string, unknown>>`. Accessing `result.data.status` trips TS4111 under `noPropertyAccessFromIndexSignature` (implied by strict mode) because `status` comes from the string-keyed index signature.
- **Fix:** Changed to bracket notation `result.data['status']` with an inline comment explaining why. No runtime change; matches TS guidance for index-signature access.
- **Files modified:** `frontend/src/api/utility.test.ts` (fixed before Task 2 commit)
- **Verification:** `npm run type-check` → exits 0. `npm test -- --run src/api/utility.test.ts` → 2 tests pass.
- **Committed in:** `8597617` (Task 2 commit)

**3. [Rule 3 - Blocking] `vitest: not found` in worktree**

- **Found during:** Baseline capture before Task 1
- **Issue:** The worktree at `.claude/worktrees/agent-af1e38c06d18ca8d5` has no `node_modules/` after checkout; `npm test` fails with `sh: 1: vitest: not found`.
- **Fix:** Ran `npm install --silent` once in the worktree's `frontend/` directory. This is standard worktree bootstrap and not a code change — no commit needed (node_modules is gitignored).
- **Files modified:** None tracked (only `node_modules/` populated).
- **Verification:** `npm test -- --run` → 9 files / 76 tests pass (baseline confirmed before any new code).
- **Committed in:** n/a (environment bootstrap only)

---

**Total deviations:** 3 auto-fixed (2 strict-lint/type-check bugs in my own newly-authored code, 1 environment bootstrap).
**Impact on plan:** No scope creep. The lint-pattern fix establishes a reusable module-level mock-narrowing convention that plans 08-02 through 08-05 can copy verbatim, so Wave 1's remaining plans get a cheaper path than rediscovering this themselves.

## Test Counts and Coverage Delta

**Per-file tests (plan success criterion):**

| File | it-blocks | expect calls | skip calls | lines |
|------|-----------|--------------|------------|-------|
| `frontend/src/api/search.test.ts` | 3 | 9 | 0 | 107 |
| `frontend/src/api/app_settings.test.ts` | 3 | 9 | 0 | 78 |
| `frontend/src/api/utility.test.ts` | 2 | 6 | 0 | 61 |

All three files: expect-count > it-count (plan verification criterion satisfied).

**Per-source-file coverage (vs. `08-COVERAGE-BASELINE.txt`):**

| File | Baseline | After 08-06 | Δ |
|------|----------|-------------|---|
| `src/api/search.ts` | 0 / 0 / 0 / 0 | 100 / 100 / 100 / 100 | +100 / +100 / +100 / +100 |
| `src/api/app_settings.ts` | 0 / 0 / 0 / 0 | 100 / 100 / 100 / 100 | +100 / +100 / +100 / +100 |
| `src/api/utility.ts` | 0 / 0 / 0 / 0 | 100 / 100 / 100 / 100 | +100 / +100 / +100 / +100 |

Format: Lines / Branches / Functions / Statements.

**Whole-frontend coverage (vs. baseline 4.72 / 37.11 / 21.36 / 4.72):**

- After 08-06: 4.85 / 38.48 / 23.18 / 4.85 (Lines / Branches / Functions / Statements).
- Delta: +0.13 lines, +1.37 branches, +1.82 functions, +0.13 statements.
- Small but measurable delta as expected for the smallest Wave 1 cluster (61 source lines / ~3100 total frontend LoC).

## utility.ts Decision Record

**Decision:** Option A (test).
**Rationale:** See "Decisions Made" §1 above. The 9-line source contains runtime logic (URL routing), just trivial runtime logic; D-15 is scoped for zero-runtime-logic files only.
**Evidence:** 9-line source pasted above. Both exported methods tested with URL + call-count + response-shape assertions (2 `it`-blocks, 6 `expect` calls total).
**Precedent for siblings:** If plans 08-02 through 08-05 encounter similar tiny modules (e.g., `api/retailers.ts` — 8 lines per plan 08-03), follow this precedent: test rather than exclude when each method hits a distinct URL.

## Issues Encountered

- **Coverage run writes `frontend/coverage/` directory on disk.** Gitignored, so no pollution; left behind after `npm run test:coverage -- --run`. Pre-existing v8 coverage-reporter HTML artifact — not introduced by this plan, out of scope.
- **MCP Context7 `unbound-method` query hit a non-obvious fact:** the `@typescript-eslint` docs recommend a separate Jest-specific version of the rule for test files. We chose the narrow inline-disable approach instead to keep the existing eslint.config.js unchanged (Phase 6 FE-01 explicitly removed the test-file override; touching it again would be scope-creep).

## User Setup Required

None — no external service configuration required. Only new test files + a single Markdown summary.

## Next Phase Readiness

- **Plans 08-02 through 08-05 (sibling Wave 1 API-test plans) unblocked and cheaper.** They can copy the `MockedFunction`-cast + inline-`eslint-disable` pattern from any of the three new test files verbatim.
- **Wave 1 coverage target on track.** Three files / 61 source lines at 100%; rest of Wave 1 (plans 08-02, 08-03, 08-04, 08-05) covers the remaining ~1600 API-module source lines.
- **No blockers. No concerns.** The two strict-lint deviations are patterns now established; future API-test authors have a worked example.

## Self-Check: PASSED

- `test -f frontend/src/api/search.test.ts` → FOUND (107 lines, 3 `it` / 9 `expect` / 0 `skip`)
- `test -f frontend/src/api/app_settings.test.ts` → FOUND (78 lines, 3 `it` / 9 `expect` / 0 `skip`)
- `test -f frontend/src/api/utility.test.ts` → FOUND (61 lines, 2 `it` / 6 `expect` / 0 `skip`)
- `git log --oneline` → 2 task commits FOUND (`f0cfb70`, `8597617`)
- `cd frontend && npm test -- --run src/api/search.test.ts src/api/app_settings.test.ts src/api/utility.test.ts` → 8 tests pass
- `cd frontend && npm test -- --run` → 12 files / 84 tests pass (was 9 / 76 at baseline; net +3 / +8)
- `cd frontend && npm run lint` → 0 errors, 0 warnings
- `cd frontend && npm run type-check` → exits 0
- Per-file coverage (search.ts, app_settings.ts, utility.ts) → 100 / 100 / 100 / 100 for all three (was 0 / 0 / 0 / 0 at baseline)

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
