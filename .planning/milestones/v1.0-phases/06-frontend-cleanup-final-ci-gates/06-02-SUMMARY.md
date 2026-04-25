---
phase: 06-frontend-cleanup-final-ci-gates
plan: 02
subsystem: ui
tags: [typescript, eslint, axios, react, vitest, refactor, frontend]

# Dependency graph
requires:
  - phase: 06-frontend-cleanup-final-ci-gates
    provides: "Strict ESLint rules (no-explicit-any + no-unsafe-*) flipped to error in plan 06-01; LINT-BASELINE.txt scope-visibility artifact captured"
provides:
  - "frontend/src/api/client.ts (Axios instance + interceptors + token helpers)"
  - "19 per-backend-domain API modules under frontend/src/api/* (D-22 split)"
  - "frontend/src/services/Api.ts reduced to a 27-line re-export shim (zero export const)"
  - "ComponentType<Record<string, unknown>> generic bound on lazyWithReload (D-06 Option B; Option A unknown failed inference)"
  - "Test-mock typing: vi.fn<() => MockAuthState>() removes the only no-unsafe-return violation"
  - "Frontend lint surface clean — npm run lint exits 0 with strict typing rules in force"
affects:
  - "06-03 (FE-03 route-group error boundaries) — can rely on api/* domain split for any new typed callers"
  - "06-04 (PR-A FastAPI 0.136 + Pydantic 2.13) — frontend type-narrowing surface stable; no api drift before backend upgrade"
  - "All future frontend plans — api modules now mirror backend endpoint domain layout"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-backend-domain API client modules (one .ts per backend endpoints/* file) under frontend/src/api/"
    - "Co-located response/request types per D-04 (WebAuthn helpers in auth.ts; Search envelope in search.ts; Image upload/presigned in images.ts; AppSettings in app_settings.ts; admin-only types in admin.ts)"
    - "Re-export shim strategy (Strategy A) for module relocation — preserves all 56 import sites without rewrite churn"
    - "vi.fn<() => T>() generic typing for vitest mocks under exactOptionalPropertyTypes:true"

key-files:
  created:
    - "frontend/src/api/client.ts"
    - "frontend/src/api/admin.ts"
    - "frontend/src/api/app_settings.ts"
    - "frontend/src/api/auth.ts"
    - "frontend/src/api/bug_reports.ts"
    - "frontend/src/api/build_list_parts.ts"
    - "frontend/src/api/build_list_phases.ts"
    - "frontend/src/api/build_lists.ts"
    - "frontend/src/api/build_logs.ts"
    - "frontend/src/api/car_generations.ts"
    - "frontend/src/api/categories.ts"
    - "frontend/src/api/images.ts"
    - "frontend/src/api/part_manufacturers.ts"
    - "frontend/src/api/parts.ts"
    - "frontend/src/api/reports.ts"
    - "frontend/src/api/retailers.ts"
    - "frontend/src/api/search.ts"
    - "frontend/src/api/users.ts"
    - "frontend/src/api/utility.ts"
    - "frontend/src/api/votes.ts"
  modified:
    - "frontend/src/utils/lazyWithReload.ts (any -> Record<string, unknown>)"
    - "frontend/src/test/utils/test-mocks.ts (vi.fn<...>() typing)"
    - "frontend/src/services/Api.ts (1520-line implementation -> 27-line re-export shim)"
    - "frontend/06-LINT-BASELINE.txt (deleted; baseline obsolete after fixes landed)"

key-decisions:
  - "Strategy A (re-export shim in services/Api.ts) chosen over Strategy B (rewrite 56 import sites) — lowest blast radius; future cleanup can delete the shim once stable"
  - "lazyWithReload generic bound = ComponentType<Record<string, unknown>> (D-06 Option B). Option A (ComponentType<unknown>) was tried first and rejected because FC<{}> route components are not assignable to FunctionComponent<unknown> ('unknown' is not assignable to '{}')"
  - "Lint baseline file (frontend/06-LINT-BASELINE.txt) deleted rather than overwritten with the empty lint output — D-02 said reconcile-or-delete; deletion is the cleaner option"
  - "crawled_pages.ts module dropped — no crawledPagesApi/crawlerPagesApi export existed in services/Api.ts; the plan's frontmatter listed it as optional and grep confirmed absence"
  - "Re-export of BucketEntityTypeCountResponse from admin.ts (sourced from images.ts) preserves cross-domain back-compat for admin pages that previously imported the type from services/Api"

patterns-established:
  - "Per-domain API module layout: frontend/src/api/<domain>.ts mirrors backend endpoints/<domain>.py one-for-one"
  - "Shared apiClient + token helpers + interceptors live in frontend/src/api/client.ts; every domain module imports from './client'"
  - "Co-located response/request types (D-04) live in the same domain module as the API surface that produces/consumes them"
  - "Re-export shim pattern for migrating shared modules without churning import sites — 'export *' over each new module preserves wildcard back-compat"

requirements-completed:
  - "FE-01"
  - "FE-04"

# Metrics
duration: 71 min
completed: 2026-04-24
---

# Phase 6 Plan 02: FE-01 Typing + FE-04 D-22 API Split Summary

**lazyWithReload `any` removed; 1520-line services/Api.ts split into client.ts + 19 per-backend-domain modules under frontend/src/api/* with co-located response types; back-compat preserved via 27-line re-export shim; all four CI gates (lint/type-check/test/build) green.**

## Performance

- **Duration:** ~71 min
- **Started:** 2026-04-24T02:13:00Z
- **Completed:** 2026-04-24T03:24:00Z
- **Tasks:** 2 (atomic commits per task)
- **Files modified:** 23 (20 new under api/, 2 modified, 1 deleted)

## Accomplishments

- **FE-01 closes:** zero `@typescript-eslint/no-explicit-any` and `no-unsafe-*` violations across `frontend/src/**`. Strict-rule flip from plan 06-01 is now CI-green.
- **FE-04 / D-22 closes:** services/Api.ts (1520 lines, 24 export const blocks) split into 19 per-backend-domain modules + shared client.ts under `frontend/src/api/`. Co-located response types per D-04.
- **All 56 existing import sites still resolve** via the re-export shim — zero call-site churn this plan.
- **lazyWithReload.ts `any` removed** (D-06): `ComponentType<Record<string, unknown>>` bound threads through all ~40 lazyWithReload call sites in App.tsx without breakage.
- **Lint baseline artifact retired:** `frontend/06-LINT-BASELINE.txt` deleted (D-02 reconcile path).

## Task Commits

Each task was committed atomically:

1. **Task 1: FE-01 typing fixes — lazyWithReload `any` removal + test-mock typing** — `4d6bf2d` (fix)
2. **Task 2: FE-04 D-22 split services/Api.ts into api/client.ts + per-domain modules** — `7dca0bf` (refactor)

## Files Created

**API client + per-domain modules (20 files, 1635 lines):**

- `frontend/src/api/client.ts` — Axios instance, base-URL resolver (`normalizeApiUrl`/`getApiBaseUrl`), `paramsSerializer` for array-valued query params (load-bearing for `ids`/`category_ids`), token helpers, request/response interceptors
- `frontend/src/api/admin.ts` — `adminApi` + ~25 co-located admin response/request types (background jobs, crawler schedules, canonical part link groups, rescan diff, bucket summaries)
- `frontend/src/api/app_settings.ts` — `appSettingsApi` + `AppSettings`/`AppSettingsUpdate`
- `frontend/src/api/auth.ts` — `authApi` + `WebAuthnOptionsResponse`/`WebAuthnCredentialSummary`
- `frontend/src/api/bug_reports.ts` — `bugReportsApi`
- `frontend/src/api/build_list_parts.ts` — `buildListPartsApi`
- `frontend/src/api/build_list_phases.ts` — `buildListPhasesApi`
- `frontend/src/api/build_lists.ts` — `buildListsApi`
- `frontend/src/api/build_logs.ts` — `buildLogsApi`
- `frontend/src/api/car_generations.ts` — `carGenerationsApi`
- `frontend/src/api/categories.ts` — `categoriesApi`
- `frontend/src/api/images.ts` — `imageApi` + `ImageUploadResponse`/`PresignedUrlResponse`/`BucketEntityTypeCountResponse`
- `frontend/src/api/part_manufacturers.ts` — `partManufacturersApi`
- `frontend/src/api/parts.ts` — `partsApi`
- `frontend/src/api/reports.ts` — `reportsApi` + legacy `partReportsApi` wrapper
- `frontend/src/api/retailers.ts` — `retailersApi`
- `frontend/src/api/search.ts` — `searchApi` + `SearchCategoryResults<T>`/`SearchResults`
- `frontend/src/api/users.ts` — `usersApi`
- `frontend/src/api/utility.ts` — `utilityApi`
- `frontend/src/api/votes.ts` — `votesApi` + legacy `partVotesApi`/`buildListVotesApi` wrappers

## Files Modified

- `frontend/src/utils/lazyWithReload.ts` — `ComponentType<any>` -> `ComponentType<Record<string, unknown>>`; eslint-disable directive removed
- `frontend/src/test/utils/test-mocks.ts` — `mockUseAuth = vi.fn()` -> `vi.fn<() => MockAuthState>()` with `MockAuthState` derived from `AuthContextType` (each prop allows `| undefined` for `exactOptionalPropertyTypes:true` compatibility)
- `frontend/src/services/Api.ts` — 1520-line implementation replaced with 27-line re-export shim (zero `export const`; uses `export *` over each domain module)

## Files Deleted

- `frontend/06-LINT-BASELINE.txt` — baseline scope-visibility artifact obsolete after fixes landed (D-02 reconcile)

## Decisions Made

1. **Strategy A (re-export shim) over Strategy B (import-site rewrite).** The plan offered both; Strategy A is the recommended lower-blast-radius option. Zero changes to the 56 existing import sites in `hooks/`, `components/`, `pages/`, `contexts/`. A future cleanup phase can delete the shim and rewrite sites once stability is proven.

2. **D-06 Option B (`ComponentType<Record<string, unknown>>`).** Option A (`ComponentType<unknown>`) was attempted first per plan recommendation, and it failed type-check at App.tsx with: `Type 'FC<{}>' is not assignable to type 'ComponentType<unknown>'. Type 'FunctionComponent<{}>' is not assignable to type 'FunctionComponent<unknown>'. Type 'unknown' is not assignable to type '{}'`. Option B threads cleanly through all `FC<{}>` route components. The plan explicitly anticipated this fall-back path.

3. **`crawled_pages.ts` omitted.** Grep on `services/Api.ts` for `crawledPagesApi` / `crawlerPagesApi` returned no results — the export name listed in the plan's `files_modified` frontmatter does not actually exist. The crawled-pages count endpoints live on `adminApi.getCrawledPageCountsBySource{,AndStatus}` and remain there. Final domain count = 19 (still ≥17 D-22 floor).

4. **Wildcard re-export shim (`export *`)** chosen over named-export shim. Named-exports gave the same back-compat but ballooned the shim to 79 lines; `export *` collapses to 27 lines, satisfies the plan's `<50 lines` cap, and preserves every named symbol from each domain module without manual enumeration.

5. **Test-mock typing pattern.** `mockUseAuth` was the sole remaining `no-unsafe-return` violation. Typing it as `vi.fn<() => MockAuthState>()` (where `MockAuthState` is `Partial<AuthContextType>` with each prop also allowing `| undefined` for `exactOptionalPropertyTypes:true`) removes the violation without weakening the mock surface for callers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Option A bound failed type-check, switched to Option B**

- **Found during:** Task 1 (lazyWithReload generic bound)
- **Issue:** `ComponentType<unknown>` (D-06 Option A, plan's recommended bound) caused `tsc` to fail with TS2322 across 3 App.tsx route components — `FC<{}>` is not assignable to `FunctionComponent<unknown>` because `unknown` is not assignable to `{}`.
- **Fix:** Switched to D-06 Option B (`ComponentType<Record<string, unknown>>`). The plan explicitly anticipated this fall-back: "If TypeScript complains about the ~40 `lazy(() => import('./pages/...'))` call sites in App.tsx, fall back to Option B." Both options remove `any`; Option B is the working bound.
- **Files modified:** `frontend/src/utils/lazyWithReload.ts`
- **Verification:** `npm run type-check` exits 0; lazyWithReload comment documents the rationale for future readers.
- **Committed in:** `4d6bf2d` (Task 1 commit)

**2. [Rule 1 - Bug] Initial `Partial<AuthContextType>` mock typing failed exactOptionalPropertyTypes**

- **Found during:** Task 1 (test-mocks.ts typing)
- **Issue:** First attempt typed `mockUseAuth = vi.fn<() => Partial<AuthContextType>>()`. TestProviders passes `{ user: undefined, isLoading: undefined }` from a Partial-shaped initialAuthState; `Partial<T>` produces `T?` which under `exactOptionalPropertyTypes:true` excludes explicit `undefined`, causing TS2379 at `mockUseAuth.mockReturnValue({...})`.
- **Fix:** Defined `type MockAuthState = { [K in keyof AuthContextType]?: AuthContextType[K] | undefined }` — each prop allows both omission and explicit `undefined`. Documented the rationale inline.
- **Files modified:** `frontend/src/test/utils/test-mocks.ts`
- **Verification:** `npm run type-check` exits 0; tests still pass.
- **Committed in:** `4d6bf2d` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 bug fixes — narrow type-system corrections during the typing rollout; the plan anticipated each one).
**Impact on plan:** Both auto-fixes were necessary to land the typing gate without breaking type-check. No scope creep — Option B was an explicit fall-back path in the plan, and the test-mock typing is a one-line generic narrowing.

## Issues Encountered

- **Lint scope smaller than expected.** Plan 06-01's baseline captured only 1 violation (test-mocks.ts via test-utils.tsx). This means the original scout (D-01) was accurate — the codebase had only the single `lazyWithReload` `any` and one stray no-unsafe-return in test-utils. No directory-chunked fix sweep was needed (Task 1 STEP 2 enumerated chunks but found nothing to fix beyond the two known sites). The plan's chunked-commit guidance still applies as a discipline; in practice it collapsed to one commit.

- **Shim line budget vs comprehensive type re-exports.** Initial named-export shim was 79 lines (over the plan's <50 cap) because admin.ts alone exposes ~25 types that consumers import via `services/Api`. Switched to `export *` over each domain module — 27 lines, zero implementation, zero `export const`, satisfies all acceptance criteria.

## User Setup Required

None — no external service configuration changes.

## Self-Check: PASSED

**Files verified to exist:**

- `frontend/src/api/client.ts` — FOUND
- `frontend/src/api/admin.ts` — FOUND
- `frontend/src/api/app_settings.ts` — FOUND
- `frontend/src/api/auth.ts` — FOUND
- `frontend/src/api/bug_reports.ts` — FOUND
- `frontend/src/api/build_list_parts.ts` — FOUND
- `frontend/src/api/build_list_phases.ts` — FOUND
- `frontend/src/api/build_lists.ts` — FOUND
- `frontend/src/api/build_logs.ts` — FOUND
- `frontend/src/api/car_generations.ts` — FOUND
- `frontend/src/api/categories.ts` — FOUND
- `frontend/src/api/images.ts` — FOUND
- `frontend/src/api/part_manufacturers.ts` — FOUND
- `frontend/src/api/parts.ts` — FOUND
- `frontend/src/api/reports.ts` — FOUND
- `frontend/src/api/retailers.ts` — FOUND
- `frontend/src/api/search.ts` — FOUND
- `frontend/src/api/users.ts` — FOUND
- `frontend/src/api/utility.ts` — FOUND
- `frontend/src/api/votes.ts` — FOUND
- `frontend/src/services/Api.ts` (shim, 27 lines) — FOUND

**File correctly deleted:**

- `frontend/06-LINT-BASELINE.txt` — CONFIRMED ABSENT

**Commits verified to exist:**

- `4d6bf2d` (Task 1: FE-01 typing fixes) — FOUND
- `7dca0bf` (Task 2: FE-04 D-22 Api.ts split) — FOUND

**Verification gates (all green):**

- `cd frontend && npm run lint` -> 0 errors
- `cd frontend && npm run type-check` -> 0 errors
- `cd frontend && npm test -- --run` -> 7/7 files, 35/35 tests
- `cd frontend && npm run build` -> green (Vite + prerender)
- `ls frontend/src/api/*.ts | wc -l` -> 20 (≥17 floor)
- `grep -l apiClient frontend/src/api/*.ts | wc -l` -> 20
- `wc -l frontend/src/services/Api.ts` -> 27 (<50 cap)
- `grep -c "^export const" frontend/src/services/Api.ts` -> 0
- `grep -rn "as any" frontend/src/api/` -> 0 hits
- `grep -n "ComponentType<any>" frontend/src/utils/lazyWithReload.ts` -> 0 hits

## Next Phase Readiness

- **FE-01 closed.** Strict typing rules in CI; lint surface clean; lazyWithReload `any` removed.
- **FE-04 / D-22 closed.** Per-backend-domain API client layout established. Future plans should add new API surface to the appropriate `frontend/src/api/<domain>.ts` and avoid re-introducing `services/Api.ts` content.
- **Wave 3 unblocked.** 06-03 (FE-03 route-group error boundaries) can proceed against the new API module layout if it imports any clients.
- **Wave 4 unblocked.** 06-04 (PR-A FastAPI 0.136 + Pydantic 2.13) — frontend type-narrowing surface stable; no api drift before backend upgrade.
- **No deferred items from this plan.**

---

*Phase: 06-frontend-cleanup-final-ci-gates*
*Plan: 02*
*Completed: 2026-04-24*
