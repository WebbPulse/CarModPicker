---
id: T05
parent: S07
milestone: M002
key_files:
  - frontend/src/pages/account/AccountAlerts.tsx
  - frontend/src/pages/account/AccountAlerts.test.tsx
  - frontend/src/App.tsx
  - frontend/src/App.coverage.test.tsx
key_decisions:
  - Per-row part hydration uses partsApi.getPart with Promise.allSettled (per task plan) — kept simple O(N) fanout since per-user alert lists are expected to be small (single digits). Flagged in Known Issues for future scale if alert lists grow.
  - Unsubscribe optimistically removes the row from the visible list via a local `removedIds` Set instead of refetching listMine — fewer round trips, and preserves row state during the brief in-flight window. Refetch would only matter if the backend could insert new alerts on the user's behalf, which it cannot.
  - Page does NOT gate on useAuth().user — relies entirely on the route-level <ProtectedRoute /> wrapper to redirect unauthenticated users. A stale-token 401 mid-session surfaces as an inline error message instead of a redirect, since the user already had access to the page. Documented in the test.
duration: 
verification_result: passed
completed_at: 2026-04-25T22:48:26.608Z
blocker_discovered: false
---

# T05: Add /account/alerts page (auth-gated, lazy-loaded) listing user's price-drop alerts with inline unsubscribe, plus ?status= banners for post-token-unsubscribe redirects

**Add /account/alerts page (auth-gated, lazy-loaded) listing user's price-drop alerts with inline unsubscribe, plus ?status= banners for post-token-unsubscribe redirects**

## What Happened

Closed the S07 demo loop with the subscription-management UI. Created `frontend/src/pages/account/AccountAlerts.tsx` — a Card-wrapped list of `PartPriceAlertRead` rows hydrated via `partPriceAlertsApi.listMine()` (uses `useApiRequest` for loading/error symmetry with ViewPart). Each row links to `/parts/${part_id}` (part name lazy-fetched via `partsApi.getPart` with `Promise.allSettled` so a single 404 doesn't break the list), shows formatted threshold ($X.XX), `created_at`, and a `last_fired_at` status of "Last sent <date>" or "Not sent yet", and an inline Unsubscribe button. Unsubscribe DELETEs `/part-price-alerts/{id}` and removes the row from the visible list (via a local `removedIds` set; doesn't refetch the whole list — cheaper, and preserves any pending row state). DELETE failures surface as a row-level error, leaving the row in place for retry.

Per MEM092, the page reads `?status=success|error` from `useSearchParams` and renders a SuccessAlert / ErrorAlert banner — that's the landing page for the token-as-auth public unsubscribe redirect (`GET /api/unsubscribe?token=...` 302s here). Banners have a Dismiss button that strips the param via `setSearchParams({}, { replace: true })`.

Empty state ("You have no active price-drop alerts. Visit a part page to create one.") with a `<Link to="/parts">Browse parts</Link>` matches the task plan copy. The route is wired in App.tsx inside the existing builder group's `<ProtectedRoute />` + `<EmailVerifiedRoute>` wrappers (the same nesting as `/profile`, `/builder`), lazy-loaded via the existing `lazyWithReload as lazy` pattern. Added the corresponding `{ path: '/account/alerts', group: 'builder' }` entry to `App.coverage.test.tsx`'s `ALL_ROUTES` so the FE-03 drift guard accepts the new route (dropped MEM095 to remember this gotcha for future agents).

Tests: 9 cases in `AccountAlerts.test.tsx` covering loading state (pending listMine), empty state (zero alerts + /parts link), single-row render (hydrated part name + threshold + "Not sent yet"), multi-row render (mixed last-fired states, ordering matches listMine), unsubscribe → row removed (DELETE called with right URL, count drops by one), DELETE failure → row-level error stays, listMine 401 → top-level error (no rows), and both `?status=success` / `?status=error` banner cases. Test scaffolding follows MEM093 (build local authedScenario from canonical `mockUser`, NOT testScenarios.authenticated which is stale) and MEM094 (per-file `vi.mock('../../hooks/useAuth', ...)` since vi.mock is hoisted per-file). MEM096 (this slice) records the `route:` option pattern used for the `?status=` cases.

Note on UI auth-gating: the page itself doesn't gate on `useAuth().user` — the route-level `<ProtectedRoute />` redirects unauthenticated visitors to `/login` before AccountAlerts mounts, so a stale-token 401 mid-session is the only way an unauthorized user hits listMine, and that surfaces as an inline error (matches the test's "401 → error message" case). The task plan's "redirect-to-login if 401" alternative was the route-guard interception path; documented that explicitly in the test.

## Verification

Ran the two task-plan-defined verification commands from `frontend/`:
1. `npm test -- --run src/pages/account/AccountAlerts.test.tsx` → 9/9 tests pass (842ms). Single benign React act() warning from the deliberately-pending listMine promise in the loading-state test.
2. `npm run type-check` (`tsc -b --noEmit`) → exit 0, no TypeScript errors.
3. Bonus: ran `npx vitest --run src/App.coverage.test.tsx` to confirm the drift-guard update — 40/40 tests pass (count went from 39 → 40 with the new `/account/alerts` builder-group entry).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm test -- --run src/pages/account/AccountAlerts.test.tsx` | 0 | pass | 847ms |
| 2 | `cd frontend && npm run type-check` | 0 | pass | 4500ms |
| 3 | `cd frontend && npx vitest --run src/App.coverage.test.tsx` | 0 | pass | 1560ms |

## Deviations

"Added `{ path: '/account/alerts', group: 'builder' }` to App.coverage.test.tsx's ALL_ROUTES (small extension to the task scope) — without it, the FE-03/D-10/D-24 drift guard would have failed CI. Captured the pattern as MEM095 for future route additions."

## Known Issues

"Per-row partsApi.getPart fanout is O(N) — fine today (per-user alert lists are tiny), but if usage grows past a couple dozen alerts per user, consider adding a hydrated-list backend variant (e.g. GET /part-price-alerts/me?include=part) or a /parts batch endpoint. The task plan explicitly flagged this as a follow-up."

## Files Created/Modified

- `frontend/src/pages/account/AccountAlerts.tsx`
- `frontend/src/pages/account/AccountAlerts.test.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.coverage.test.tsx`
