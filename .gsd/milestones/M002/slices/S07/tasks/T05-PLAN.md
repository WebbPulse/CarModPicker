---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T05: Frontend: /account/alerts management page + auth-gated route

Build the subscription-management page promised by the demo. New page `frontend/src/pages/account/AccountAlerts.tsx` (also create the directory if it doesn't exist). Page renders: heading 'Your price-drop alerts', and a list of `PartPriceAlertRead` rows from `partPriceAlertsApi.listMine()` (active=True only — the backend filters this for /me). Each row shows: part name (linked to `/parts/${alert.part_id}` — fetched via a parallel `getPart(part_id)` per-row, OR add a backend endpoint variant returning hydrated alerts; for this slice, the simpler approach is per-row lazy-load via the existing `partsApi.getPart` — flag in 'Follow-ups' if scale becomes an issue), threshold formatted as USD, `created_at` formatted via `toLocaleDateString()`, last_fired_at status ('Last sent <date>' if non-null else 'Not sent yet'), and an 'Unsubscribe' button that DELETEs `/part-price-alerts/{id}` and refetches the list. Empty state when zero alerts: 'You have no active price-drop alerts. Visit a part page to create one.' with a link to `/parts`. Loading + error states must match the existing `useApiRequest` patterns used in ViewPart. Add the route in `frontend/src/App.tsx` inside the auth-required group: `<Route path='/account/alerts' element={<AccountAlerts />} />`. Lazy-load via the existing `lazy(() => import('./pages/account/AccountAlerts'))` pattern used for other auth pages (check the existing imports at the top of App.tsx for the pattern). Tests: `frontend/src/pages/account/AccountAlerts.test.tsx` covers loading state, empty state, single-alert render, multi-alert render, unsubscribe → confirm row removed, redirect-to-login if 401 (or — if the route guard handles this — assert that the page renders nothing because the guard intercepts).

## Inputs

- ``frontend/src/api/part_price_alerts.ts``
- ``frontend/src/types/Api.ts``
- ``frontend/src/App.tsx``
- ``frontend/src/pages/builder/ViewPart.tsx``
- ``frontend/src/hooks/useApiRequest.ts``
- ``frontend/src/api/parts.ts``

## Expected Output

- ``frontend/src/pages/account/AccountAlerts.tsx``
- ``frontend/src/pages/account/AccountAlerts.test.tsx``
- ``frontend/src/App.tsx``

## Verification

cd frontend && npm test -- --run src/pages/account/AccountAlerts.test.tsx && npm run type-check
