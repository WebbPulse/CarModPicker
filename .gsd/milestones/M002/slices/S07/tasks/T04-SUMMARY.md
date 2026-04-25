---
id: T04
parent: S07
milestone: M002
key_files:
  - frontend/src/api/part_price_alerts.ts
  - frontend/src/api/part_price_alerts.test.ts
  - frontend/src/types/Api.ts
  - frontend/src/components/parts/PriceAlertSubscribeButton.tsx
  - frontend/src/components/parts/PriceAlertSubscribeButton.test.tsx
  - frontend/src/pages/builder/ViewPart.tsx
key_decisions:
  - First consumer of `components/ui/dialog.tsx` (Radix) in the app — verified via grep no other file imports from `ui/dialog`. Pattern set here: use `Dialog open onOpenChange` controlled mode (not `DialogTrigger`) so the trigger button can branch on auth state and either redirect or open the dialog.
  - 401 on subscribe POST also redirects to `/login?next=…` (same as anonymous click), since a token-expiry mid-form is the same UX failure mode as 'never logged in'. Other 4xx (422 invalid threshold, etc.) surface inline so the user can correct without losing form state.
  - Client-side guard rejects negative thresholds BEFORE the API call — the backend `Field(ge=0)` would 422 it anyway, but a roundtrip-free message is better UX and the test plan explicitly called for 'threshold-validation-rejected (negative)' as a separate case from '422 error display'.
  - Placed the button as a flex-row sibling of the 'Price summary (90 days)' `SectionHeader` (not collapsing the existing summary), per the task plan's NEW directive.
duration: 
verification_result: passed
completed_at: 2026-04-25T22:42:32.874Z
blocker_discovered: false
---

# T04: Add typed partPriceAlertsApi client + PriceAlertSubscribeButton on /parts/:id (anonymous → /login redirect, authenticated → Radix dialog with prefilled threshold)

**Add typed partPriceAlertsApi client + PriceAlertSubscribeButton on /parts/:id (anonymous → /login redirect, authenticated → Radix dialog with prefilled threshold)**

## What Happened

Wired the user-facing subscribe surface for the M002/S07 price-drop alert loop.

Two pieces, exactly per the task plan:

1. **Typed API client** — `frontend/src/api/part_price_alerts.ts` exports `partPriceAlertsApi` with `subscribe`, `listMine`, `updateAlert`, `deleteAlert`. Mirrors the structure of `parts.ts` (apiClient.{get,post,patch,delete} with explicit URL paths under the `/part-price-alerts` prefix, which matches the backend router registration in `backend/app/main.py:297-298`). Three new interfaces in `types/Api.ts` — `PartPriceAlertCreate`, `PartPriceAlertUpdate`, `PartPriceAlertRead` — line-for-line match the backend Pydantic schemas in `backend/app/api/schemas/part_price_alert.py` (UUIDs serialized as `string`, `last_fired_at` typed `string | null`).

2. **Subscribe UI** — `frontend/src/components/parts/PriceAlertSubscribeButton.tsx` consumes the S08 Radix `Dialog` + `Input` + `Button` primitives (this is the first consumer of `components/ui/dialog.tsx` in the app — verified via grep). On mount, authenticated users get a `listMine()` fetch and the matched-by-partId active alert flips the trigger label from "Notify me on price drop" to "Manage alert ($X.XX)". Click handler:
   - **Anonymous** → `useNavigate(`/login?next=/parts/${partId}`)`, dialog never opens.
   - **Authenticated** → opens dialog with the threshold input prefilled to either the existing alert's threshold or `currentBestPriceCents`, whichever applies.
   - Submit → `partPriceAlertsApi.subscribe()`. On success, dialog closes and the trigger label flips to "Manage alert". On 4xx, the inline error region (`role="alert"`) shows the FastAPI detail string or the first validation `msg`. On 401 (token expired between page-load and submit), redirect to login same as anonymous.
   - Client-side guard rejects negative thresholds before the network call so users get a clean message instead of burning a 422 roundtrip.

Wired into `pages/builder/ViewPart.tsx` as a sibling of the existing "Price summary (90 days)" `SectionHeader` — placed in a flex row inside the same wrapper `<div className="mb-6">`, so the summary block is preserved exactly as-is below the row. Receives `partId={part.id}` and `currentBestPriceCents={part.best_price_cents ?? null}` from ViewPart's already-loaded part record.

**Test coverage:**
- `api/part_price_alerts.test.ts` (5 tests) — verifies subscribe POSTs to `/part-price-alerts/`, listMine GETs `/part-price-alerts/me`, updateAlert PATCHes `/part-price-alerts/{id}` (with both threshold and active variants), deleteAlert DELETEs `/part-price-alerts/{id}`. All 5 pass.
- `components/parts/PriceAlertSubscribeButton.test.tsx` (5 tests) — anonymous→login-redirect (asserts dialog never renders + listMine never fires), authenticated-no-existing→subscribe-success (POST body shape + dialog closes), authenticated-existing→prefill-current-threshold (label flips to "Manage alert ($75.00)" + input pre-fills to 75 not 100), threshold-validation-rejected (negative value triggers inline error, no API call), 422 error display (server detail msg surfaces inline, dialog stays open). All 5 pass.

**Verification:** `npm test -- --run src/api/part_price_alerts.test.ts src/components/parts/PriceAlertSubscribeButton.test.tsx` → 10/10 passed in 851ms. `npm run type-check` → exit 0.

**Note on prior verification failure:** The first execute attempt's verification failure was `pytest exit code 5` ("no tests collected") because the auto-discovered command tried to run backend pytest paths that don't exist for a frontend task. Re-ran with the task plan's stated frontend verification (`npm test -- --run … && npm run type-check`) and both pass cleanly.

## Verification

Ran the task plan's stated verification: `npm test -- --run src/api/part_price_alerts.test.ts src/components/parts/PriceAlertSubscribeButton.test.tsx && npm run type-check` from `frontend/`. Both succeed: 10/10 tests pass (5 API client + 5 component) in ~850ms; tsc -b --noEmit exits 0 with no errors.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm test -- --run src/api/part_price_alerts.test.ts src/components/parts/PriceAlertSubscribeButton.test.tsx` | 0 | ✅ pass | 851ms |
| 2 | `cd frontend && npm run type-check` | 0 | ✅ pass | 12000ms |

## Deviations

No structural deviations from the inlined task plan. One small adaptation: the existing `frontend/src/test/utils/test-utils.tsx` `testScenarios.{authenticated,unauthenticated}` builds `user` via a stale `createMockUser()` helper missing several `UserRead` fields, which fails type-check under `exactOptionalPropertyTypes: true`. Built local `authedScenario`/`anonScenario` constants from the canonical `mockUser` in `test/mocks/api.ts` instead — captured as MEM093 so future tests don't repeat the dance.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/api/part_price_alerts.ts`
- `frontend/src/api/part_price_alerts.test.ts`
- `frontend/src/types/Api.ts`
- `frontend/src/components/parts/PriceAlertSubscribeButton.tsx`
- `frontend/src/components/parts/PriceAlertSubscribeButton.test.tsx`
- `frontend/src/pages/builder/ViewPart.tsx`
