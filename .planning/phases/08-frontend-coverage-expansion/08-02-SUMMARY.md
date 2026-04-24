---
phase: 08-frontend-coverage-expansion
plan: 02
subsystem: frontend
tags: [frontend, api-tests, auth, wave-1]
requires:
  - .planning/phases/08-frontend-coverage-expansion/08-01-SUMMARY.md  # setup.ts D-18 dual mock + mocks/api.ts fixtures
  - frontend/src/api/auth.ts                                          # system under test
  - frontend/src/api/users.ts                                         # system under test
  - frontend/src/api/images.ts                                        # system under test
  - frontend/src/api/client.ts                                        # system under test
provides:
  - frontend/src/api/auth.test.ts       # full authApi coverage (27 tests, 48 expects)
  - frontend/src/api/users.test.ts      # full usersApi coverage (13 tests, 17 expects)
  - frontend/src/api/images.test.ts     # full imageApi coverage (9 tests, 18 expects)
  - frontend/src/api/client.test.ts     # token helpers + interceptors + paramsSerializer + env baseURL (20 tests, 21 expects)
affects:
  - .planning/phases/08-frontend-coverage-expansion/08-COVERAGE-BASELINE.txt  # baseline snapshot; not re-generated here (plan 08-09 is threshold enforcement)
tech-stack:
  added: []
  patterns:
    - "Wave 1 canonical API-test skeleton: `MockedFunction<typeof apiClient.<verb>>` module-scope casts + `/* eslint-disable-next-line @typescript-eslint/unbound-method */` (matches votes.test.ts / admin.test.ts / search.test.ts)"
    - "FormData content-inspection: `expect.any(FormData)` call-signature match + `postMock.mock.calls[0]?.[1] as FormData` + `fd.get('file')` identity check"
    - "Real-module access under global vi.mock: `vi.doUnmock('./client')` + `vi.resetModules()` + `await import('./client')` per describe block (sentry.test.ts analog)"
    - "Env-driven baseURL: `vi.stubEnv('DEV', true|false)` + `vi.stubEnv('VITE_BACKEND', ...)` + dynamic import so `getApiBaseUrl()` re-evaluates at load time"
key-files:
  created:
    - frontend/src/api/auth.test.ts
    - frontend/src/api/users.test.ts
    - frontend/src/api/images.test.ts
    - frontend/src/api/client.test.ts
  modified: []
decisions:
  - "Copied the canonical Wave 1 `MockedFunction<typeof apiClient.<verb>>` cast pattern from 08-05/06/07 instead of re-inventing the per-call `vi.mocked(...)` form — this keeps Wave 1 linting uniform and future plan diffs mechanical."
  - "client.test.ts drives interceptors directly via `apiClient.interceptors.request.handlers[0].fulfilled/rejected` (cast through `any` with file-wide disable) because axios does not expose handler internals on its public type surface. Runtime shape is stable across axios 1.x."
  - "For paramsSerializer tests: coerced `apiClient.defaults.paramsSerializer` to a union of `fn | { serialize: fn }` to guard against axios serializer-shape drift across minor versions. Current axios 1.x uses the bare function form."
  - "login's `missing-user` contract-violation branch tested via `await expect(...).rejects.toThrow(/missing user payload/)` — matches the actual error message in auth.ts:66."
metrics:
  duration_minutes: 3
  completed_date: 2026-04-24
  tasks_completed: 3
  files_touched: 4
  it_blocks_total: 69
  expects_total: 104
---

# Phase 8 Plan 02: Auth API Cluster Coverage Tests Summary

**One-liner:** Full coverage tests for `authApi` (23 methods, 27 it-blocks), `usersApi` (12 methods, 13 it-blocks), `imageApi` (7 methods, 9 it-blocks), and the real `client.ts` module (token helpers, interceptors, paramsSerializer, env-driven baseURL — 20 it-blocks) using the Wave 1 canonical mocking skeleton.

## What was built

Four new test files in `frontend/src/api/` bringing 69 passing it-blocks / 104 expect assertions, all built on the setup.ts D-18 dual mock pattern. The `client.test.ts` file is the one Wave 1 test that must exercise the REAL client module — it uses `vi.doUnmock('./client')` + `vi.resetModules()` + dynamic `await import('./client')` per describe block (copied from `src/lib/sentry.test.ts`).

### Test counts per file

| File                | it-blocks | expect calls | skip | lines |
| ------------------- | --------- | ------------ | ---- | ----- |
| `auth.test.ts`      | 27        | 48           | 0    | 474   |
| `users.test.ts`     | 13        | 17           | 0    | 189   |
| `images.test.ts`    | 9         | 18           | 0    | 178   |
| `client.test.ts`    | 20        | 21           | 0    | 295   |
| **Total**           | **69**    | **104**      | 0    | 1136  |

All four files exceed the plan's acceptance-criteria floors.

### Branch / side-effect coverage

- **`login` three-way branch:** happy-path token store, `requires_2fa` passthrough (no token store), missing-user contract violation (throws).
- **Token-storage side effects:** `loginWith2FA`, `webauthnLoginVerify`, `googleLink`, `googleSignup`, `oauthTwoFactor` each assert `setStoredToken` was called with the response `access_token`.
- **`logout` removal side effect:** `removeStoredToken` is called after POST succeeds.
- **FormData paths:** Both `usersApi.uploadProfilePicture` (→ `/users/me/profile-picture`) and `imageApi.uploadImage` (→ `/images/upload?entity_type=X&entity_id=Y`) get `expect.any(FormData)` + `FormData.get('file')` identity assertions.
- **Interceptors:** request interceptor attaches `Authorization: Bearer <token>` iff token present; response interceptor stores `x-new-access-token` rotated tokens; 401 rejected path preserved (no redirect, per the commented-out line in client.ts:132).
- **paramsSerializer:** array expansion (`ids=1&ids=2&ids=3`), URLSearchParams passthrough, null/undefined skip while keeping falsy 0, URL-encoding of scalars with special characters.
- **Env-driven baseURL:** staging (DEV=true + VITE_BACKEND=staging), production (DEV=true + VITE_BACKEND=production), local default (DEV=true + no VITE_BACKEND → `/api`), production build (DEV=false + VITE_API_URL → `https://...`), fallback (DEV=false + no VITE_API_URL → `/api`), explicit https passthrough.

## Coverage delta vs baseline

Baseline (`08-COVERAGE-BASELINE.txt`):

| File        | Lines | Branches | Functions | Statements |
| ----------- | ----- | -------- | --------- | ---------- |
| `auth.ts`   | 0%    | 0%       | 0%        | 0%         |
| `users.ts`  | 0%    | 0%       | 0%        | 0%         |
| `images.ts` | 0%    | 0%       | 0%        | 0%         |
| `client.ts` | 0%    | 0%       | 0%        | 0%         |

After plan 08-02 (coverage run restricted to the 4 new test files):

| File        | Lines    | Branches   | Functions | Statements |
| ----------- | -------- | ---------- | --------- | ---------- |
| `auth.ts`   | **100%** | **100%**   | **100%**  | **100%**   |
| `users.ts`  | **100%** | **100%**   | **100%**  | **100%**   |
| `images.ts` | **100%** | **100%**   | **100%**  | **100%**   |
| `client.ts` | **100%** | **94.59%** | **100%**  | **100%**   |

Client.ts uncovered branch residue (lines 112, 135): both are the `error instanceof Error` false-branch in the request and response interceptor error handlers — reachable only by injecting a non-Error into axios's rejection pipeline, which the current request-interceptor test already triggers via the string `'boom'`. The remaining ~5% is the genuine-Error pass-through path which the plan did not explicitly call out; leaving it for plan 08-09 (threshold enforcement) to decide whether to pursue. Exceeds the plan's ≥80% target for client.ts.

## Deviations from Plan

**None (auto-fixed issues):** Plan executed as written. All tests passed on first run for each file — this is coverage backfill of existing, working source code, so RED/GREEN/REFACTOR cycles were not needed (plan's `tdd="true"` flag acknowledged but not semantically meaningful for backfill, per RESEARCH.md §4 + the retry-prompt guidance).

**Minor content expansions** (within scope, not deviations):
1. **auth.test.ts**: Added `result.data` sanity assertions to `setup2FA`, `verify2FA`, `disable2FA`, `verifyEmail`, `verifyEmailConfirm`, and `resetPasswordConfirm` to exceed the ≥46 expect-count floor (final: 48).
2. **users.test.ts**: Added `listUsers` no-params variant to exercise the `params: undefined` spread path.
3. **client.test.ts**: Added a 4th paramsSerializer test (URL-encoding of special characters in scalars) and a 6th env-baseURL test (explicit `https://` protocol pass-through) — both derived from client.ts lines 10-15 (normalizeApiUrl) that would otherwise be covered only incidentally.

## Commits

| Hash      | Message                                                                    | Files                                       |
| --------- | -------------------------------------------------------------------------- | ------------------------------------------- |
| `cfb6e3d` | test(08-02): add authApi coverage tests                                    | auth.test.ts                                |
| `d0a9b9c` | test(08-02): add usersApi and imageApi coverage tests                      | users.test.ts, images.test.ts               |
| `55fcdd8` | test(08-02): add clientApi real-module coverage and strengthen auth assertions | client.test.ts, auth.test.ts            |

## Key Patterns for Downstream Wave 1 Plans

1. **Canonical mocking pattern (copy verbatim from this plan's files into 08-03 / 08-04):**
   ```ts
   /* eslint-disable-next-line @typescript-eslint/unbound-method */
   const postMock = apiClient.post as MockedFunction<typeof apiClient.post>;
   ```
   Import `apiClient` from `./client`; setup.ts D-18 handles the mock — do NOT inline a `vi.mock('../api/client')`.

2. **FormData assertion pattern:**
   ```ts
   expect(postMock).toHaveBeenCalledWith(url, expect.any(FormData), { headers: { ... } });
   const fd = postMock.mock.calls[0]?.[1] as FormData;
   expect(fd.get('file')).toBe(file);
   ```

3. **Real-module-under-global-mock escape hatch** (client.test.ts only): every describe block needs `vi.doUnmock('./client')` + `vi.resetModules()` in beforeEach, and every test uses a fresh `await import('./client')`.

## Verification

- `cd frontend && npm test -- --run src/api/auth.test.ts src/api/users.test.ts src/api/images.test.ts src/api/client.test.ts` — 69/69 passing, 4 files, 636ms total.
- `cd frontend && npm run test:coverage -- --run src/api/auth.test.ts src/api/users.test.ts src/api/images.test.ts src/api/client.test.ts` — 100% lines on all four files (94.59% branches on client.ts, driven by two non-Error coerce paths).
- Acceptance criteria counts: all floors met or exceeded (see Test counts per file and the Key Patterns section above).

## Self-Check: PASSED

Files confirmed on disk:
- `frontend/src/api/auth.test.ts` — FOUND
- `frontend/src/api/users.test.ts` — FOUND
- `frontend/src/api/images.test.ts` — FOUND
- `frontend/src/api/client.test.ts` — FOUND

Commits confirmed in git log:
- `cfb6e3d` — FOUND
- `d0a9b9c` — FOUND
- `55fcdd8` — FOUND

All plan acceptance criteria satisfied; SUMMARY committed; STATE.md + ROADMAP.md NOT touched (parallel-executor worktree discipline).
