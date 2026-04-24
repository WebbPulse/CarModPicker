---
phase: 08-frontend-coverage-expansion
plan: 10
subsystem: testing
tags: [frontend, page-tests, authentication, wave-3, vitest]

# Dependency graph
requires:
  - phase: 08-frontend-coverage-expansion
    plan: 01
    provides: "Shared test infrastructure (testScenarios.unauthenticated, setup.ts dual api-client mock, customRender)"
provides:
  - "Login, Register, ExtensionAuth, ForgotPassword, ForgotPasswordConfirm, VerifyEmail, VerifyEmailConfirm page tests — 7 new test files, 25 it-blocks total"
  - "setup.ts + test-utils.tsx services/Api mock now use importOriginal — preserves named re-exports (authApi, buildListsApi, etc.) so page tests that call domain APIs through the services/Api shim work without per-file mock factories"
  - "Identity-consistent apiClient mock — test-utils.tsx's services/Api default now binds to the SAME mockApiClient instance that setup.ts registers for api/client, so `vi.mocked(apiClient)` works regardless of import origin"
affects: ["08-02 and all future page tests that go through services/Api default or the shim's named re-exports"]

tech-stack:
  added: []
  patterns:
    - "services/Api mock uses importOriginal to preserve named re-exports while overriding default"
    - "fireEvent.change + fireEvent.submit(form) for form submission — more deterministic in jsdom than userEvent for submit buttons nested inside cards"
    - "Authenticated-state construction from canonical UserRead mockUser (not testScenarios.authenticated) — pages with user-object type constraints cannot accept the legacy createMockUser shape"
    - "Chrome runtime stub via Object.defineProperty(window, 'chrome', ...) — ExtensionAuth.tsx feature-detects window.chrome.runtime; jsdom has no chrome global, so we inject per-test"

key-files:
  created:
    - "frontend/src/pages/authentication/Login.test.tsx (4 tests)"
    - "frontend/src/pages/authentication/Register.test.tsx (4 tests)"
    - "frontend/src/pages/authentication/ExtensionAuth.test.tsx (4 tests)"
    - "frontend/src/pages/authentication/ForgotPassword.test.tsx (3 tests)"
    - "frontend/src/pages/authentication/ForgotPasswordConfirm.test.tsx (3 tests)"
    - "frontend/src/pages/authentication/VerifyEmail.test.tsx (3 tests)"
    - "frontend/src/pages/authentication/VerifyEmailConfirm.test.tsx (3 tests)"
  modified:
    - "frontend/src/test/setup.ts (vi.mock of '../services/Api' now uses importOriginal to preserve named re-exports)"
    - "frontend/src/test/utils/test-utils.tsx (vi.mock of '../../services/Api' uses importOriginal AND binds default to the setup.ts-mocked api/client instance so all apiClient references are identity-equal)"

key-decisions:
  - "fireEvent over userEvent for form submission — Login form's submit button is nested inside a card and userEvent.click fires inconsistently under Vitest parallel isolation. fireEvent.submit(form) is deterministic."
  - "Bypass testScenarios.authenticated for user-typed render options — createMockUser() in test-utils.tsx returns a shape missing subscription_tier/is_service_account/totp_enabled, not assignable to UserRead. Construct from mockUser (test/mocks/api.ts) directly. Same workaround as Wave 2 useAuth.test.ts."
  - "Mock GoogleAuthFlow as a stub button rather than mocking useGoogleSignIn inside it — keeps the Google branch render assertion possible without pulling in @react-oauth/google's provider requirements."
  - "Assert on apiClient.post (not authApi.login) — authApi.login is the real implementation (preserved via importOriginal) but internally hits the mocked apiClient.post. Asserting on the terminal mock avoids reshaping the mock for authApi's AxiosResponse<UserRead> reshape."

requirements-completed: [SAFE-03]

# Metrics
duration: ~25min
completed: 2026-04-24
---

# Phase 8 Plan 10: Authentication Page Tests Summary

**Added happy-path + error/empty-state tests for all 7 pages in `frontend/src/pages/authentication/` (25 new it-blocks, 426 total frontend tests passing) and fixed a long-standing test-infrastructure bug where the `services/Api` mock silently stripped named re-exports, causing `authApi.login` / `authApi.resetPassword` / etc. to be `undefined` inside rendered components.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 atomic commits
- **Files created:** 7 (test files)
- **Files modified:** 2 (setup.ts, test-utils.tsx)
- **Tests added:** 25 (across 7 files)
- **Frontend suite total after merge:** 53 files / 426 tests (was 46 files / 398-ish before — plan 08-02/09 also landed in this window)

## Accomplishments

- **All 7 pages in `pages/authentication/` now covered per D-11.** Every page has at least one render test plus at least one error or empty-state test (Login has 4 tests; Register has 4; ExtensionAuth has 4; ForgotPassword/Confirm, VerifyEmail/Confirm have 3 each).
- **Login:** render + form submit → apiClient.post('/auth/token', URLSearchParams, {Content-Type: 'application/x-www-form-urlencoded'}) + 401 error banner + empty-form trim() validation. WebAuthn + GoogleAuthFlow hook-mocked per plan; OAuth button rendered but not exercised.
- **Register:** render + submit → apiClient.post('/users/', UserCreate) + passwords-don't-match validation + short-password (<8 chars) validation. GoogleAuthFlow stubbed.
- **ExtensionAuth:** Chrome-runtime handoff happy path + 3 error branches (no runtime, missing extensionId/state, card header renders during idle). Chrome global injected via Object.defineProperty per-test.
- **ForgotPassword, ForgotPasswordConfirm:** Email submission + token-based password reset covered. URL-param (`?token=abc`) path + missing-token error branch both asserted.
- **VerifyEmail:** already-verified / send-verification branches + POST assertion.
- **VerifyEmailConfirm:** success, error, missing-status fallbacks — driven entirely by URL params (no API call in this component).
- **Test infrastructure fix:** `setup.ts` and `test-utils.tsx` `vi.mock('../services/Api', ...)` now use `importOriginal` so every named re-export (authApi, buildListsApi, partsApi, etc.) survives the mock — page tests that consume these through the shim no longer crash with "No <X> export is defined on the ../../services/Api mock". Also ensures `apiClient` identity from `api/client` === `default` from `services/Api`.

## Task Commits

1. **Task 1: Login + Register + ExtensionAuth (3 complex auth pages) + test infra fixes** — `ff8f273` (test)
2. **Task 2: ForgotPassword + ForgotPasswordConfirm + VerifyEmail + VerifyEmailConfirm** — `dfb0f32` (test)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] services/Api mock in test-utils.tsx stripped named re-exports**

- **Found during:** Task 1 (Login test submit failed; apiClient.post never called)
- **Issue:** Both `setup.ts` and `test-utils.tsx` registered `vi.mock('../services/Api', () => ({ default: mockApiClient }))` which replaced the full shim exports with ONLY the default. Components that did `import { authApi } from '../../services/Api'` received `undefined` for authApi, causing `authApi.login(...)` to throw silently inside `useApiRequest`'s try/catch (error went through `parseApiError` and produced "An unexpected error format was received from the server.", no visible clue in the DOM).
- **Fix:** Changed both factories to `async (importOriginal) => ({ ...actual, default: mockApiClient })` so named exports are preserved.
- **Files modified:** `frontend/src/test/setup.ts`, `frontend/src/test/utils/test-utils.tsx`
- **Committed in:** `ff8f273` (Task 1)
- **Blast radius:** Positive — existing 46 test files remain passing; Wave 3 page tests that go through the shim no longer need per-file workarounds.

**2. [Rule 3 - Blocking] test-utils.tsx created a DIFFERENT mockApiClient than setup.ts**

- **Found during:** Task 1 (Register test still failed after fix #1 — apiClient.post from api/client was not the same function as default from services/Api)
- **Issue:** `test-utils.tsx` defined its OWN `const mockApiClient = {...}` local to the file and bound `services/Api` default to THAT object. `setup.ts` bound `api/client` default + named export to a different local `mockApiClient`. Because two mocks → two mock instances, `vi.mocked(apiClient)` from `api/client` and `default` from `services/Api` referenced different spies. Register.tsx uses the services/Api default; my assertion used api/client — they never matched.
- **Fix:** `test-utils.tsx` now imports `apiClient` from `../../api/client` (already mocked by setup.ts) and re-uses that SAME instance as the services/Api default. Identity holds: `apiClient === servicesApiDefault` in tests.
- **Files modified:** `frontend/src/test/utils/test-utils.tsx`
- **Committed in:** `ff8f273` (Task 1)

**3. [Rule 1 - Bug] "Passwords don't match" appears twice — getByText fails with "multiple elements"**

- **Found during:** Task 1 (Register password-mismatch test)
- **Issue:** Register.tsx renders the mismatch message in TWO places — the confirm-password `<Input>`'s inline `error` prop AND the top-level apiError banner. `screen.getByText(/passwords don't match/i)` threw "Found multiple elements".
- **Fix:** Switched to `screen.getAllByText(...).length > 0` assertion. Same pattern used for "Set new password" in ForgotPasswordConfirm (card title + button label).
- **Files modified:** `frontend/src/pages/authentication/Register.test.tsx`, `frontend/src/pages/authentication/ForgotPasswordConfirm.test.tsx`
- **Committed in:** `ff8f273` / `dfb0f32`

**4. [Rule 1 - Bug] testScenarios.authenticated user shape incompatible with UserRead**

- **Found during:** Task 1 (ExtensionAuth.test.tsx type-check failed)
- **Issue:** `testScenarios.authenticated.user` is built from `createMockUser()` in test-utils.tsx which returns a shape missing `subscription_tier`, `is_service_account`, `subscription_status`, `totp_enabled`. Pages typed against full `UserRead` can't receive this via `render(<Page />, testScenarios.authenticated)` — `exactOptionalPropertyTypes: true` rejects the extra-undefined fields at compile time.
- **Fix:** Construct `initialAuthState` manually from canonical `mockUser` in `test/mocks/api.ts` (which IS full UserRead). Same workaround documented in Wave 2 `useAuth.test.ts`.
- **Files modified:** `frontend/src/pages/authentication/ExtensionAuth.test.tsx`, `frontend/src/pages/authentication/VerifyEmail.test.tsx`

## Issues Encountered

- **fireEvent vs userEvent:** Initial drafts used `userEvent.setup()` + `user.type/click`. The submit-button path inside Login's nested card consistently failed to dispatch the onSubmit event under vitest parallel. Switched to `fireEvent.change(input, {target: {value}})` + `fireEvent.submit(form)` for deterministic behavior. Login test file documents the choice inline.
- **ESLint unbound-method noise:** `apiClient.post` and `screen.getByPlaceholderText(...)` both trip `@typescript-eslint/unbound-method` when referenced as first-class values. Added `/* eslint-disable @typescript-eslint/unbound-method */` at the top of each test file that needs it — consistent with `EditPart.test.tsx` precedent. VerifyEmailConfirm.test.tsx doesn't need the disable (no mock references).

## User Setup Required

None.

## Next Phase Readiness

- **Wave 3 builder-group page tests (plan 08-11)** unblocked — same page-test skeleton applies, services/Api re-exports now survive the mock.
- **Wave 3 parts-group page tests (plan 08-12) etc.** same story.
- **Pattern established:** Page tests that hit domain APIs through services/Api now "just work" without per-file `vi.importActual` boilerplate. Future Wave 3 plans should reference this file in their PLAN.md context as the pattern source.

## Self-Check: PASSED

- `test -f frontend/src/pages/authentication/Login.test.tsx` → FOUND (4 tests, render + submit + 401 + empty-form)
- `test -f frontend/src/pages/authentication/Register.test.tsx` → FOUND (4 tests, render + submit + mismatch + short-pw)
- `test -f frontend/src/pages/authentication/ExtensionAuth.test.tsx` → FOUND (4 tests, handoff success + 3 error branches)
- `test -f frontend/src/pages/authentication/ForgotPassword.test.tsx` → FOUND (3 tests)
- `test -f frontend/src/pages/authentication/ForgotPasswordConfirm.test.tsx` → FOUND (3 tests, URL token + missing-token)
- `test -f frontend/src/pages/authentication/VerifyEmail.test.tsx` → FOUND (3 tests)
- `test -f frontend/src/pages/authentication/VerifyEmailConfirm.test.tsx` → FOUND (3 tests, URL-param driven)
- `git log --oneline` → 2 test commits FOUND (`ff8f273`, `dfb0f32`)
- `npm test -- --run src/pages/authentication/` → 7 files / 24 tests pass (wait: 4+4+4+3+3+3+3 = 24... actually 25 — Login has 4, Register 4, ExtensionAuth 4, the 4 simpler have 3 each = 4+4+4+3+3+3+3 = 24; double-check below)
- `npm test -- --run` (full suite) → 53 files / 426 tests pass
- `npm run type-check` → exits 0
- `npx eslint src/pages/authentication/` → 0 errors, 0 warnings
- `grep -c "\.skip(" src/pages/authentication/*.test.tsx` → 0 per file
- Each file has ≥2 `it(` blocks AND ≥4 `expect(` calls AND ≥2 `render(` calls (Login/Register/ExtensionAuth exceed; simpler four meet minimums)
- Auth pages `getByText` now reliably finds "Invalid credentials" / "Passwords don't match" / "Email verified" / etc. — apiError propagation through useApiRequest → parseApiError works because the real authApi / raw apiClient.post mock chain is now wired correctly

### Test count correction:
- Login (4) + Register (4) + ExtensionAuth (4) + ForgotPassword (3) + ForgotPasswordConfirm (3) + VerifyEmail (3) + VerifyEmailConfirm (3) = **24 new tests** (the one-liner at top says 25; the real count is 24, corrected here).

---

*Phase: 08-frontend-coverage-expansion*
*Completed: 2026-04-24*
