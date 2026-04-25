---
phase: 06-frontend-cleanup-final-ci-gates
plan: 03
subsystem: ui
tags: [react, react-router-7, sentry, error-boundary, vitest, tdd, route-coverage]

# Dependency graph
requires:
  - phase: 02-observability
    provides: "@sentry/react v10 SDK + Session Replay-on-error + app-root ErrorBoundary captureException pattern (OBS-05)"
  - phase: 06-frontend-cleanup-final-ci-gates plan 02
    provides: "FE-01 strict typing rules (no-explicit-any + no-unsafe-* errors) and lazyWithReload<ComponentType<Record<string, unknown>>> bound — both consumed by new component + test"
provides:
  - "RouteGroupBoundary component (Sentry.ErrorBoundary wrapper) with eventId + Retry + Go Home fallback UI"
  - "App.tsx route-group wiring: 4 RouteGroupBoundary parents (admin / authentication / builder / public) over the full 37-route table"
  - "Parametrized App.coverage.test.tsx with drift guard (ALL_ROUTES.length >= 37) — adds CI gate that any new <Route> must be categorised under a route group"
  - "NotFound page (lazy-loaded) extracted from inline 404 element so the catch-all route follows the same lazy pattern as every other page"
affects: [phase-07, phase-08, future-frontend-pages]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-route-group ErrorBoundary using Sentry.ErrorBoundary FallbackRender prop (eventId + resetError + componentStack surface)"
    - "vi.hoisted shared mutable state pattern for parametrized vitest.describe.each route coverage"
    - "ResizeObserver stub pattern for jsdom render of components that use observers (AdBanner)"
    - "Per-test auth-state toggle pattern (mock useAuth/useAppSettings, mutate authState before each render based on the route's group requirements)"

key-files:
  created:
    - "frontend/src/components/common/RouteGroupBoundary.tsx"
    - "frontend/src/components/common/RouteGroupBoundary.test.tsx"
    - "frontend/src/App.coverage.test.tsx"
    - "frontend/src/pages/NotFound.tsx"
  modified:
    - "frontend/src/App.tsx"

key-decisions:
  - "RouteGroupBoundary uses Sentry.ErrorBoundary directly (not subclassing the existing ErrorBoundary) to surface eventId + resetError in the FallbackRender prop without re-implementing them."
  - "Real Sentry.ErrorBoundary runs in RouteGroupBoundary.test.tsx — not mocked, unlike ErrorBoundary.test.tsx — because mocking it would defeat the purpose of asserting eventId surfaces in the fallback."
  - "Auth-redirect mitigation = Option 1 (TestProviders-style mock with per-group state toggle): authentication group routes render under unauthenticated user; builder group routes render under authenticated email-verified user; public/admin paths use defaults. Cleaner than Option 2 (re-classifying entries) because it preserves the exact 21/3/5/8 group counts the plan calls for."
  - "Inline 404 catch-all extracted into a lazy-loaded NotFound page so the parametrized force-throw mock applies uniformly to every Route. Without this, the `*` catch-all rendered the inline JSX (no throw possible via the lazyWithReload mock) and the assertion failed for the 404 case."
  - "ResizeObserver polyfill installed inside App.coverage.test.tsx (not the global setup.ts) to keep the coverage-test surface self-contained — other tests do not currently render AdBanner so they do not need the stub."
  - "Drift-guard floor = 37 (matches `grep -cE 'path=\"' frontend/src/App.tsx`). Adding any Route in App.tsx without categorising it in ALL_ROUTES breaks CI."

patterns-established:
  - "Route-group boundary wrapping idiom: <Route element={<RouteGroupBoundary groupName=...><Outlet /></RouteGroupBoundary>}> wraps each group's children. Auth guards (GuestRoute / ProtectedRoute / EmailVerifiedRoute) nest inside the boundary, not outside."
  - "Force-throw-and-assert-fallback parametrized coverage: mock the lazy loader once, force every Route's element to throw, assert the route-group fallback marker renders. Mirrors backend test_admin_auth_coverage.py pattern."
  - "Drift guard with toBeGreaterThanOrEqual(N) floor + hand-maintained route enumeration: PR review enforces categorisation; floor enforces non-removal."

requirements-completed: [FE-03]

# Metrics
duration: 14min
completed: 2026-04-24
---

# Phase 6 Plan 3: Per-Route ErrorBoundary + Coverage Drift Guard Summary

**Sentry-backed RouteGroupBoundary contains render crashes per route group (admin/auth/builder/public), with a parametrized vitest force-throw test that asserts every one of the 37 App.tsx routes is wrapped — drift guard fails CI on uncategorised additions.**

## Performance

- **Duration:** 14 min (863 s)
- **Started:** 2026-04-24T03:34:26Z
- **Completed:** 2026-04-24T03:48:49Z
- **Tasks:** 3
- **Files modified/created:** 5 (1 modified + 4 new)

## Accomplishments

- Per-route-group containment: a `pages/admin/*` render crash now ONLY blanks the admin section; public, authentication, and builder groups continue rendering with Header + Footer intact (D-07, T-06-12 mitigation).
- Sentry-aware fallback UX: every fallback shows the live `eventId` (correlation token), a `Retry` button (calls `Sentry.ErrorBoundary.resetError`), a `Go Home` button (`navigate('/')`), and the user-safe `error.message` string (D-08).
- Sentry events captured by the route-group boundary carry a `route_group` scope tag (`beforeCapture`), enabling per-group dashboard slicing (T-06-15 mitigation).
- Parametrized App.coverage.test.tsx with 37 enumerated routes + drift-guard floor — a new `<Route>` added to App.tsx without a matching ALL_ROUTES entry now fails CI immediately (D-10, D-24, T-06-13 mitigation).
- Existing app-root `<ErrorBoundary>` (App.tsx:139) and top-level `<Suspense>` (App.tsx:192) preserved exactly as-is per D-09.

## Task Commits

Each task committed atomically (no `--no-verify` skipping investigation; pre-commit hooks bypassed only because the worktree runs without husky in parallel-execution mode):

1. **Task 1: RouteGroupBoundary component + unit tests** — `76c5ae8` (feat)
2. **Task 2: App.tsx Routes tree wraps 4 RouteGroupBoundary groups** — `5785b8f` (feat)
3. **Task 3: Parametrized App route-group coverage test** — `44c1724` (test)

_Note: Tasks 1 and 3 were TDD (RED → GREEN). Task 1's RED commit was rolled into the GREEN commit because the test file failed-import in RED before any commit was created. Task 3 had several iteration cycles inside a single working-tree edit before the GREEN commit landed._

## Files Created/Modified

- `frontend/src/components/common/RouteGroupBoundary.tsx` (new) — Sentry.ErrorBoundary wrapper component with FallbackRender UI (Retry, Go Home, eventId), `beforeCapture` scope-tag, and `RouteGroupName` type.
- `frontend/src/components/common/RouteGroupBoundary.test.tsx` (new) — 3 unit tests: renders children when no error, renders fallback with eventId + data-route-group when child throws, Retry calls resetError and re-renders non-throwing children.
- `frontend/src/App.tsx` (modified) — added Outlet + RouteGroupBoundary imports; wrapped Routes tree in 4 parent `<Route element={<RouteGroupBoundary groupName=...><Outlet /></RouteGroupBoundary>}>` groups; replaced inline 404 JSX with `<NotFound />` lazy import; preserved app-root `<ErrorBoundary>` + `<Suspense>` per D-09.
- `frontend/src/App.coverage.test.tsx` (new) — parametrized vitest describe.each over 37 hand-enumerated routes; vi.hoisted lazyWithReload throwing-stub mock; per-group auth-state toggle (authentication unauth, builder authenticated email-verified); ResizeObserver stub for AdBanner jsdom render; drift guard `expect(ALL_ROUTES.length).toBeGreaterThanOrEqual(37)`.
- `frontend/src/pages/NotFound.tsx` (new) — lazy-loaded 404 page extracted from inline JSX in App.tsx (no visual change). Allows the parametrized coverage test to apply the same throwing-stub mock to the catch-all `*` route.

## Plan Output Requirements

Per the plan's `<output>` block, the SUMMARY records:

- **(a) Auth-redirect mitigation chosen for builder routes:** **Option 1** — TestProviders-style mock of `useAuth` + `useAppSettings` via `vi.mock`, with a hoisted `authState` mutable object that the per-test setup mutates based on the route's group:
  - `authentication` group → `isAuthenticated: false` (GuestRoute lets `/login` etc. through)
  - `builder` group → `isAuthenticated: true, emailVerified: true` (ProtectedRoute + EmailVerifiedRoute let `/profile` etc. through)
  - `public` + `admin` groups → defaults (no auth guards in App.tsx around those routes)
- **(b) Final ALL_ROUTES count:** **37 entries** (21 public + 3 authentication + 5 builder + 8 admin), exactly matching `grep -cE 'path="' frontend/src/App.tsx`.
- **(c) @sentry/react mocking in RouteGroupBoundary.test.tsx:** **NOT mocked.** The real `Sentry.ErrorBoundary` runs cleanly under jsdom. Mocking it would have defeated the purpose of asserting that `eventId` surfaces in the FallbackRender output — the real ErrorBoundary is what populates that prop. PATTERNS.md §Wave 0 documents this as the cleaner option.
- **(d) Force-throw-and-assert-fallback mechanism in place:** **Yes.** A `vi.hoisted` `throwState.shouldThrow` flag (default `true`) drives a `vi.mock('./utils/lazyWithReload')` factory whose returned stub throws `new Error('coverage-test-forced-throw')` on render. Every parametrized case asserts the corresponding `[data-route-group="<group>"]` selector resolves; no test falls back to a happy-path-only observable. The forbidden assertion shape (asserting only that `document.body` exists) is documented as rejected in the file header docstring and absent from the test body.

## Decisions Made

See frontmatter `key-decisions` block for the canonical list. Highlights:

- **`Sentry.ErrorBoundary` not mocked in unit test:** keeps `eventId`/`resetError` semantics under test (real component).
- **Auth state per-group toggle (Option 1):** preserves the plan's expected 21/3/5/8 group counts.
- **NotFound extracted into lazy page:** uniform parametrized coverage; no visual change.
- **ResizeObserver stub local to coverage test:** minimal global-setup churn.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FallbackRender props triggered strict ESLint diagnostics**
- **Found during:** Task 1 (RouteGroupBoundary component)
- **Issue:** Initial RouteGroupBoundary used `onClick={resetError}` (FE-01 `@typescript-eslint/unbound-method` error: `resetError` typed as a method on `FallbackRender`'s arg) and `onClick={() => navigate('/')}` (FE-01 `@typescript-eslint/no-floating-promises`: react-router v7 `navigate()` returns a Promise).
- **Fix:** Restructured fallback render prop to a body-form arrow that destructures `error`/`eventId`, defines local `handleRetry` (calls `errorData.resetError()` inside an arrow, side-stepping `unbound-method` on the destructure site) and `handleGoHome` (calls `void navigate('/')` to mark the floating Promise ignored).
- **Files modified:** `frontend/src/components/common/RouteGroupBoundary.tsx`
- **Verification:** `npm run lint` exits 0; 3/3 RouteGroupBoundary tests pass.
- **Committed in:** `76c5ae8` (Task 1 commit)

**2. [Rule 3 - Blocking] jsdom missing ResizeObserver crashed App tree before route boundaries**
- **Found during:** Task 3 (App.coverage.test.tsx initial run — 21/38 cases failed)
- **Issue:** App.tsx renders `<AdBanner />` for non-promo paths (admin, builder, most public). `AdBanner` constructs `new ResizeObserver(...)`. jsdom does not implement `ResizeObserver` — the construction throws OUTSIDE the per-route boundary (it's a sibling of `<Routes>`), the app-root `<ErrorBoundary>` catches it, and the test never sees the inner `RouteGroupBoundary` fallback.
- **Fix:** Added a structural `ResizeObserverStub` class with no-op constructor + observe/unobserve/disconnect methods at the top of `App.coverage.test.tsx`; assigned to `globalThis.ResizeObserver` only when undefined (so it does not stomp real implementations under future jsdom versions).
- **Files modified:** `frontend/src/App.coverage.test.tsx`
- **Verification:** All 21 previously-failing cases now pass.
- **Committed in:** `44c1724` (Task 3 commit)

**3. [Rule 2 - Missing Critical] Inline 404 element broke parametrized force-throw mechanism**
- **Found during:** Task 3 (1/38 case failing after ResizeObserver fix — `/nonexistent-route-for-404-test`)
- **Issue:** The catch-all `*` Route in App.tsx had an inline JSX 404 element, not a lazy-loaded component. The `vi.mock('./utils/lazyWithReload')` throwing stub therefore did not apply to it — the inline JSX rendered normally without throwing, so no fallback marker appeared and the assertion failed.
- **Fix:** Extracted the 404 JSX into a new `frontend/src/pages/NotFound.tsx` page module, lazy-loaded it in App.tsx (`const NotFound = lazy(() => import('./pages/NotFound.tsx'))`), and replaced the inline element with `<Route path="*" element={<NotFound />} />`. No visual change to the 404 page — same div/glass-card/buttons. This also gives the catch-all the same code-splitting benefit every other page already has.
- **Files modified:** `frontend/src/App.tsx`, `frontend/src/pages/NotFound.tsx` (new)
- **Verification:** All 38 parametrized cases now pass; build green; route count preserved at 37.
- **Committed in:** `44c1724` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (1 bug, 1 blocking, 1 missing critical)
**Impact on plan:** All three deviations were necessary for the success criteria the plan itself defines. None expanded scope beyond Task 3's behavior. The NotFound extraction is the only one that touched non-test source code (App.tsx), and that change is structurally identical to the plan's intent (every Route's element is a lazy-loaded page).

## Issues Encountered

- Auth-mock interaction with `useIsPremium` initially considered: `useIsPremium` calls `useAuth().user` and `useAppSettings().settings.premium_disabled`. Mocking both hooks at module level keeps the surface clean; the per-group `authState` toggle is the only mutation point.
- The `expect(document.body).toBeTruthy()` literal regex in the file's docstring (warning text against the forbidden pattern) initially tripped the strict grep guard. Re-worded the docstring to describe the pattern in prose without including the literal.

## Threat Surface Scan

No new threat surface introduced beyond the plan's `<threat_model>` register. The plan already enumerated:

- T-06-12 Denial of Service (single page crash) — **mitigated** by RouteGroupBoundary scope; Phase 2 app-root ErrorBoundary preserved as last-resort.
- T-06-13 Tampering (route table) — **mitigated** by App.coverage.test.tsx drift guard floor.
- T-06-14 Information Disclosure (error.message in fallback) — **accepted** per `error instanceof Error ? error.message : 'Unknown error'` narrowing; no stack trace in DOM; eventId is a public correlation token.
- T-06-15 Spoofing (route_group Sentry tag) — **mitigated** by typed `RouteGroupName` literal union constraining the tag value at compile time.

No threat flags raised.

## User Setup Required

None — no external service configuration required. The Sentry SDK is already initialised by Phase 2's OBS-05 wiring; the new component reuses that instance via `import * as Sentry from '@sentry/react'`.

## Next Phase Readiness

- **Wave 3 of Phase 6 complete.** Wave 4 (PR-A: FastAPI 0.136 + Pydantic 2.13 + QUAL-06 extension audit) and Wave 5 (PR-B: SQLAlchemy/Alembic/Uvicorn + python-jose removal) are independent of this work and can proceed.
- **FE-03 closes** with FE-01 (typing) and FE-04 (API split) already shipped in Plan 06-02. Wave 6 (FE-07 opportunistic UX polish) can now reference RouteGroupBoundary + the coverage test as established patterns.
- No blockers for next wave.

## Self-Check: PASSED

Files created/modified verified:
- FOUND: `frontend/src/components/common/RouteGroupBoundary.tsx`
- FOUND: `frontend/src/components/common/RouteGroupBoundary.test.tsx`
- FOUND: `frontend/src/App.tsx` (modified)
- FOUND: `frontend/src/App.coverage.test.tsx`
- FOUND: `frontend/src/pages/NotFound.tsx`

Commits verified in `git log`:
- FOUND: `76c5ae8` (Task 1)
- FOUND: `5785b8f` (Task 2)
- FOUND: `44c1724` (Task 3)

Verification gates run before commit:
- `npm test -- --run src/components/common/RouteGroupBoundary.test.tsx` → 3/3 passed
- `npm test -- --run src/App.coverage.test.tsx` → 38/38 passed
- `npm run lint` → exit 0
- `npm run type-check` → exit 0
- `npm run build` → exit 0
- `grep -c 'RouteGroupBoundary groupName' frontend/src/App.tsx` → 4
- `grep -cE 'path="' frontend/src/App.tsx` → 37 (preserved from pre-edit count)
- `frontend/src/components/common/ErrorBoundary.tsx` unmodified (D-09)

---
*Phase: 06-frontend-cleanup-final-ci-gates*
*Completed: 2026-04-24*
