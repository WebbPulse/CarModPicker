---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T04: Frontend: typed partPriceAlertsApi client + Subscribe button on /parts/:id

Wire the user-facing subscribe surface on the part detail page. Two pieces. (1) API client: `frontend/src/api/part_price_alerts.ts` exporting `partPriceAlertsApi` with `subscribe(data: PartPriceAlertCreate)`, `listMine()`, `updateAlert(id, data: PartPriceAlertUpdate)`, `deleteAlert(id)`, all typed against new interfaces in `frontend/src/types/Api.ts` (`PartPriceAlertCreate { part_id: string; threshold_cents: number }`, `PartPriceAlertUpdate { threshold_cents?: number; active?: boolean }`, `PartPriceAlertRead { id: string; user_id: string; part_id: string; threshold_cents: number; active: boolean; last_fired_at: string | null; created_at: string; updated_at: string }`). Mirror the structure of `frontend/src/api/parts.ts` (apiClient.{get,post,patch,delete} with explicit URL paths). Vitest at `frontend/src/api/part_price_alerts.test.ts` covers: subscribe POSTs body to `/part-price-alerts/`, listMine GETs `/part-price-alerts/me`, updateAlert PATCHes `/part-price-alerts/{id}`, deleteAlert DELETEs `/part-price-alerts/{id}`. (2) Subscribe UI on ViewPart: add a `<PriceAlertSubscribeButton>` component at `frontend/src/components/parts/PriceAlertSubscribeButton.tsx` consuming the S08 Radix `Dialog` + `Input` + `Button` primitives. Component takes `partId: string`, `currentBestPriceCents: number | null` (passed in from ViewPart's existing best-price computation), and `defaultOpen?: boolean` (for tests). Renders a button whose label is 'Notify me on price drop' (when no existing active alert for this part) or 'Manage alert ($X.XX)' (when one exists — fetched on mount via `partPriceAlertsApi.listMine()` filtered to this part). Clicking opens a Dialog with a `<Input type='number'>` prefilled to the current best price (or empty if null), and a 'Subscribe' button that POSTs and closes the dialog on success. Show error inline if the API returns 4xx (e.g. 422 for negative threshold). On 401 (anonymous), clicking the button should redirect to `/login?next=/parts/${partId}` instead of opening the dialog. Wire the button into ViewPart.tsx adjacent to the existing 'Price summary (90 days)' block (NEW — sibling, do not collapse the existing summary). Tests: `frontend/src/components/parts/PriceAlertSubscribeButton.test.tsx` covers anonymous→login-redirect, authenticated-no-existing→subscribe-success, authenticated-existing→pre-fills-current-threshold, threshold-validation-rejected (negative), 422 error display.

## Inputs

- ``frontend/src/api/parts.ts``
- ``frontend/src/api/parts.test.ts``
- ``frontend/src/api/client.ts``
- ``frontend/src/types/Api.ts``
- ``frontend/src/components/ui/dialog.tsx``
- ``frontend/src/components/ui/input.tsx``
- ``frontend/src/components/ui/button.tsx``
- ``frontend/src/pages/builder/ViewPart.tsx``
- ``frontend/src/contexts/AuthContext.tsx``

## Expected Output

- ``frontend/src/api/part_price_alerts.ts``
- ``frontend/src/api/part_price_alerts.test.ts``
- ``frontend/src/types/Api.ts``
- ``frontend/src/components/parts/PriceAlertSubscribeButton.tsx``
- ``frontend/src/components/parts/PriceAlertSubscribeButton.test.tsx``
- ``frontend/src/pages/builder/ViewPart.tsx``

## Verification

cd frontend && npm test -- --run src/api/part_price_alerts.test.ts src/components/parts/PriceAlertSubscribeButton.test.tsx && npm run type-check
