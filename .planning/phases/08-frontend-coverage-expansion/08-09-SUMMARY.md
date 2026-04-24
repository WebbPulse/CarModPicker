---
phase: 08-frontend-coverage-expansion
plan: 09
subsystem: testing
tags: [frontend, vitest, context-tests, wave-2, coverage-backfill]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "Dual api-client mock in setup.ts (D-18); mockUser fixture in test/mocks/api.ts; vi.mocked(apiClient) pattern established"
provides:
  - "AuthContext.tsx provider coverage: 0% → 97.67% lines / 93.33% branches / 100% functions (only the unused non-401 console.error branch at lines 45-46 uncovered)"
  - "AppSettingsContext.tsx provider coverage: 0% → 100% across all four axes"
  - "Canonical pattern for context provider tests with named-export mock extension via vi.importActual (needed when setup.ts global mock only exposes `default`)"
  - "Pattern reference for future context tests: in-file <Consumer> + real provider + MemoryRouter gating only when provider calls useNavigate()"
affects: ["08-20 (threshold enablement — line/function/branch counts lifted meaningfully by these two files)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "vi.importActual inside vi.mock factory to EXTEND a global setup.ts mock with named exports the global mock didn't expose (authApi, removeStoredToken, appSettingsApi)"
    - "In-file <Consumer> component exercising real provider via useContext — distinct from hook-test renderHook pattern and from test-utils customRender (which mocks useAuth)"
    - "Sentry.setUser stub in context tests to avoid touching the real @sentry/react module (AuthContext calls it unconditionally on every user change)"

key-files:
  created:
    - "frontend/src/contexts/AuthContext.test.tsx (213 lines, 6 tests, 18 expects)"
    - "frontend/src/contexts/AppSettingsContext.test.tsx (165 lines, 4 tests, 14 expects)"
  modified: []

key-decisions:
  - "Mock strategy: extend setup.ts global mock via vi.importActual rather than re-declaring a fresh mockApiClient. Keeps a single source of truth for the Axios surface and avoids the dual-singleton leak risk."
  - "No MemoryRouter in AppSettingsContext test: AppSettingsProvider never calls useNavigate(), unlike AuthProvider. Wrapping in MemoryRouter would be dead weight."
  - "Sync fireEvent.click (no act wrapper) after the initial mount waitFor: fireEvent auto-wraps in act internally; a second explicit act(async) was tripping @typescript-eslint/require-await without buying any flush semantics we didn't already get from waitFor."
  - "6 tests on AuthContext (not the plan's 4-minimum) because the provider has three distinct mount paths (resolve-user / resolve-null / 401-reject) worth covering separately — all three hit different branches of the useEffect's try/catch."

patterns-established:
  - "Context-test skeleton: (a) vi.hoisted for shared mock fns, (b) vi.mock('../services/Api', async () => ({ ...(await importActual), namedExport: stub })) to extend global mock, (c) in-file Consumer using useAuth / useAppSettings, (d) render with MemoryRouter only if provider navigates."
  - "Coverage-backfill signal: tests are written against an EXISTING provider that is not changing; they pass on first write. No RED step needed."

requirements-completed: [SAFE-03]

# Metrics
duration: ~14min
completed: 2026-04-24
---

# Phase 8 Plan 09: Context Provider Tests Summary

**Covered both context providers (AuthContext + AppSettingsContext) with 10 tests exercising real providers through in-file `<Consumer>` components; lifted provider coverage from 0% to 97.67%/100% on lines.**

## Performance

- **Duration:** ~14 min
- **Started:** 2026-04-24T17:44:00Z (approx — worktree reset)
- **Completed:** 2026-04-24T17:58:00Z
- **Tasks:** 2 (both passed on first write — coverage-backfill flow, no RED)
- **Files created:** 2
- **Files modified:** 0

## Accomplishments

- **AuthContext.tsx coverage: 0% → 97.67% lines / 93.33% branches / 100% functions.** Six tests cover the checkAuthStatus useEffect on mount (resolve-user, resolve-null, and 401-reject branches), direct login(), and logout() happy + failure paths. Only the non-401 console.error branch (lines 45-46, a defensive log for unexpected non-401 status codes) stays uncovered — reaching it requires mocking a 500 response, which adds no signal beyond what the 401 branch already proves.
- **AppSettingsContext.tsx coverage: 0% → 100% across all four axes.** Four tests cover the mount fetch (resolve + reject), setSettings direct mutation, and refresh() re-fetch.
- **Global suite regression-free:** `npm test -- --run` runs 31 files / 328 tests green — the previous 21-file / 318-test baseline plus this plan's 2 files / 10 tests.
- **Established the "named-export extend" mock pattern:** `vi.importActual` inside a local `vi.mock` factory lets downstream context/page tests extend the setup.ts global mock with whatever named exports the provider under test imports — without clobbering the singleton mockApiClient.

## Task Commits

Each task was committed atomically on this worktree's main branch:

1. **Task 1: Write AuthContext.test.tsx** — `39927e9` (test)
2. **Task 2: Write AppSettingsContext.test.tsx** — `8d34cd5` (test)

_Metadata commit for SUMMARY.md will be made by this agent at the end._

## Files Created/Modified

### Created

- `frontend/src/contexts/AuthContext.test.tsx` (213 lines) — 6 tests covering:
  1. `authenticates on mount when /users/me resolves with a user` — happy-path checkAuthStatus success.
  2. `stays unauthenticated when /users/me returns 401 and clears the stored token` — invalid-token cleanup branch (asserts `removeStoredToken` call).
  3. `stays unauthenticated when /users/me resolves with null data (no token)` — resolve-but-empty branch (no token removal).
  4. `flips state to authenticated when login() is called directly` — login() transition.
  5. `flips state from authenticated to unauthenticated on logout and calls authApi.logout` — logout() happy path (asserts both state flip and `authApi.logout` call count).
  6. `still clears auth state when authApi.logout rejects` — logout's catch branch (network down → still clears token + state).

- `frontend/src/contexts/AppSettingsContext.test.tsx` (165 lines) — 4 tests covering:
  1. `fetches settings on mount and exposes them to consumers` — initial useEffect fetch + state propagation.
  2. `leaves settings null and flips isLoading idle when the fetch rejects` — rejection branch (settings stay null, loading settles).
  3. `setSettings updates the consumer view without refetching` — direct-setter path, asserts no second GET.
  4. `refresh() re-fetches settings and replaces the cached value` — refresh() re-fetch returning a different payload.

### Modified

None. Both contexts under test were unchanged — coverage backfill only.

## Decisions Made

- **Extended setup.ts global mock via `vi.importActual` rather than rolling a fresh local mock.** The `../services/Api` module is globally mocked in `src/test/setup.ts` as `{ default: mockApiClient }` — nothing else. AuthContext.tsx imports `default`, named `authApi`, and named `removeStoredToken`; AppSettingsContext.tsx imports named `appSettingsApi`. Wrapping the mock factory with `async () => ({ ...(await vi.importActual(...)), authApi: {...}, removeStoredToken: ... })` preserves the global `default` singleton (so `vi.mocked(apiClient.get)` works via the same identity) while adding the named exports the provider needs. This is cleaner than defining a per-file mockApiClient that would diverge from the global one.

- **Used `fireEvent.click` directly without an `act(async () => { ... })` wrapper.** The initial implementation wrapped clicks in `await act(async () => { fireEvent.click(...); })` to match PATTERNS.md §10's skeleton. That pattern tripped `@typescript-eslint/require-await` (the async callback had no internal await) AND `@typescript-eslint/unbound-method` in multiple places. Switching to bare `fireEvent.click(...)` followed by `await waitFor(...)` satisfies both lints and produces identical test behavior — `fireEvent` already wraps in `act` internally, and `waitFor` handles the async state settle. Rule 1 fix.

- **Mocked `@sentry/react` in AuthContext.test.tsx.** AuthContext has a second `useEffect` that calls `Sentry.setUser({ id: ... })` on every user change (D-40 backend-mirror PII posture). Without the stub, tests would make real `setUser` calls against whatever Sentry state the module-level singleton inherited. Stub is inert (`vi.fn()`).

- **Wrote 6 AuthContext tests, not the plan-minimum 4.** The checkAuthStatus `useEffect` has three distinct branches (resolve-with-user, resolve-with-null-data, reject-401) that exercise different code paths — the 401 path calls `removeStoredToken`, the resolve-null path does not, and the resolve-with-user path flips state. Covering each separately produces cleaner failure diagnostics than bundling them.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ESLint `@typescript-eslint/unbound-method` + `@typescript-eslint/require-await` on first draft**

- **Found during:** Task 1 (post-write lint run)
- **Issue:** First draft used `vi.mocked(apiClient.get)` and `await act(async () => { fireEvent.click(...); })` patterns directly from PATTERNS.md §10. Produced 12 lint errors: 9 `unbound-method` (vi.mocked reading `apiClient.get` as an unbound reference) and 3 `require-await` (async callbacks with no internal await).
- **Fix:**
  - For `unbound-method`: added a single file-level `/* eslint-disable @typescript-eslint/unbound-method */` directive with an inline justification comment — `vi.mocked(apiClient.get)` is the canonical Vitest pattern and the returned value is only ever invoked as a mock helper (`.mockResolvedValueOnce` / `.mockReset` / matcher args), never as a bound method on `apiClient`. Suppressing the rule is correct; the alternative (aliasing `apiClient.get` to a local const) would re-bind the reference and cause the mock override to miss.
  - For `require-await`: dropped the `act(async () => { fireEvent.click(...); })` wrapper entirely. `fireEvent.click` is sync and auto-wraps in `act` internally; any async state settling that follows is handled by `await waitFor(...)`.
- **Files modified:** `frontend/src/contexts/AuthContext.test.tsx`
- **Verification:** `npx eslint src/contexts/AuthContext.test.tsx` exits 0 (no errors, no warnings). All 6 tests still pass.
- **Committed in:** `39927e9` (Task 1)

**2. [Rule 1 - Bug] Unused eslint-disable directive in AppSettingsContext.test.tsx**

- **Found during:** Task 2 (post-write lint run)
- **Issue:** Initial draft of AppSettingsContext.test.tsx copied the `/* eslint-disable @typescript-eslint/unbound-method */` directive from the AuthContext test, but the AppSettings test ended up using the hoisted `mockGet` / `mockUpdate` fns directly rather than `vi.mocked(apiClient.get)`. The directive produced no rule violations, so ESLint flagged it as unused (warning).
- **Fix:** Removed the now-unused `/* eslint-disable */` block.
- **Files modified:** `frontend/src/contexts/AppSettingsContext.test.tsx`
- **Verification:** `npx eslint src/contexts/AppSettingsContext.test.tsx` exits 0 with no output.
- **Committed in:** `8d34cd5` (Task 2)

---

**Total deviations:** 2 auto-fixed (2 bugs — both in my own newly-authored code). No architectural changes. No scope creep.

## Issues Encountered

- **Acceptance-criterion wording mismatch on `vi.mocked(apiClient` count.** The plan's literal-grep acceptance criterion says `grep -c "vi.mocked(apiClient"` must return at least 2. My first draft used a hoisted `mockApiClient` object (pattern-equivalent, produces the same test behavior) and would have returned 0. I refactored to use `vi.mocked(apiClient.get)` / `vi.mocked(apiClient.post)` directly — which satisfies the literal-grep check AND matches PATTERNS.md §10's skeleton more closely. Final count: 10 occurrences in AuthContext.test.tsx.

- **Baseline file only lists files that had some test-covered import path at baseline capture time.** `AppSettingsContext.tsx` isn't in `08-COVERAGE-BASELINE.txt` because the v8 coverage reporter filters out files that weren't imported by any test file. Functional baseline for the delta: 0%/0%/0%/0% (no test imported it). Post-plan: 100% across all four axes.

## User Setup Required

None — test code only, no external service configuration.

## Next Phase Readiness

- **Wave 2 (hooks + contexts) is COMPLETE when plan 08-08 also lands.** Plan 08-08 covers the 11 hook tests; this plan (08-09) covered the 2 context provider tests. Wave 3 (customer pages) unblocked.
- **New mock-extension pattern available to Wave 3/4 page tests.** Any page test whose source transitively imports a named export from `../services/Api` that setup.ts doesn't expose can follow the `vi.importActual + spread` pattern established here.
- **No blockers. No concerns.** Per-task commits, SUMMARY.md created, no STATE.md or ROADMAP.md modifications (per plan execution context directive).

## Self-Check: PASSED

- `test -f frontend/src/contexts/AuthContext.test.tsx` → FOUND (213 lines, 6 `it` blocks, 18 `expect` calls, 4 `MemoryRouter` references, 4 `AuthProvider` references, 4 `fireEvent/act(` references, 10 `vi.mocked(apiClient` references, 0 `.skip(` calls)
- `test -f frontend/src/contexts/AppSettingsContext.test.tsx` → FOUND (165 lines, 4 `it` blocks, 14 `expect` calls, 2 `AppSettingsProvider` references, 3 `fireEvent` references, 0 `.skip(` calls)
- `git log --oneline | grep "08-09"` → 2 commits FOUND (`39927e9` + `8d34cd5`)
- `npm test -- --run src/contexts/` → 2 files / 10 tests pass
- `npm test -- --run` → 31 files / 328 tests pass (no regressions)
- `npx eslint src/contexts/AuthContext.test.tsx` → 0 errors, 0 warnings
- `npx eslint src/contexts/AppSettingsContext.test.tsx` → 0 errors, 0 warnings
- Coverage delta: AuthContext.tsx 0% → 97.67% lines; AppSettingsContext.tsx 0% → 100% lines

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
