---
id: T03
parent: S06
milestone: M002
key_files:
  - frontend/src/pages/builder/ViewPart.tsx
  - frontend/src/pages/builder/ViewPart.priceSummary.test.tsx
key_decisions:
  - Inserted the new 'Price summary (90 days)' block as a sibling ABOVE the existing two-column price-history/listings grid (per plan Step 2), keeping the legacy chart untouched as required by the slice plan.
  - Hardened the priceSummary render guard to also check `priceSummary.summary` existence — the existing ViewPart.test.tsx mock returns `{data: []}` for the shared `/parts/{id}/price-history` URL, which would otherwise crash the page when accessed via the new summary path. Avoids requiring every existing ViewPart test to special-case the new endpoint.
  - Used `data-testid` markers (`price-summary-stat-strip`, `retailer-breakdown-flat`, `retailer-breakdown-row`) for test-only structural assertions — the Tabs primitive's `role=tablist` is the public-API hook for the >3-retailer branch, so no new test-id was needed there.
  - Implemented the `>3 retailers` rule literally — a 4-retailer list activates Tabs (>3, not ≥3). Plan said 'retailer count > 3' explicitly.
duration: 
verification_result: passed
completed_at: 2026-04-25T21:36:49.051Z
blocker_discovered: false
---

# T03: Render per-retailer price summary block + 60-day stale 'as of' caveat on /parts/:partId detail view

**Render per-retailer price summary block + 60-day stale 'as of' caveat on /parts/:partId detail view**

## What Happened

Extended `frontend/src/pages/builder/ViewPart.tsx` to consume the S05 single-part aggregation summary and the existing legacy price-history fetch in parallel. Added a third `useApiRequest` over `partsApi.getPartPriceHistorySummary(id, { window: '90d' })` and triggered it inside the existing primary-data useEffect alongside `fetchListings` / `fetchPriceHistory`. Inserted a new sibling block titled "Price summary (90 days)" ABOVE the existing two-column "Price history / Price by retailer" grid; the block renders only when `priceSummary?.summary?.observation_count > 0` and shows a 4-cell stat strip (min / max / last / trend with arrow glyph) plus a per-retailer breakdown. The breakdown auto-switches between a flat `<ul>` (≤3 retailers) and the S08 Radix `Tabs` primitive (>3 retailers, one trigger per retailer plus an "All" tab). For the existing listings list, added a 60-day stale caveat: per-row, if `last_price_updated_at` is more than `STALE_LISTING_THRESHOLD_DAYS = 60` days before now, append `<span className="text-xs text-amber-400 ml-2">(as of <localized date>)</span>` after the existing "updated <date>" span. The 60-day threshold is hoisted to a module-level const at the top of the file. Failure path: when the summary fetch errors, the block renders an inline "Price summary unavailable" message rather than throwing — the existing PriceHistoryLineChart and listings list keep rendering via their independent fetches.

Wrote `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` covering all five plan-mandated cases: zero observations hides the block, two retailers render flat (no tablist), five retailers render Tabs with one trigger per retailer plus an "All" trigger, a 90-day-stale listing shows "as of" and a 5-day-fresh listing does not. The existing ViewPart.test.tsx initially regressed because its mock returned `{ data: [] }` for the price-history URL — `useApiRequest` then set `priceSummary` to an array, and `priceSummary.summary` crashed. Hardened the guard to `priceSummary && priceSummary.summary && priceSummary.summary.observation_count > 0` so a malformed shape skips the block silently rather than throwing. Captured the underlying `getPartPriceHistory` vs `getPartPriceHistorySummary` URL-collision footgun as MEM077 — both APIs hit `/parts/{id}/price-history` and only differ by axios params, so future test mocks must discriminate on the params arg.

Implementation note: `RetailerPriceBreakdown` and the `PriceHistorySummary` types were already exported from `frontend/src/types/Api.ts` (S05 work). The Tabs primitive was already in `frontend/src/components/ui/tabs.tsx` (S08 work). No new dependencies, no backend changes.

## Verification

Ran the slice-required commands plus regression coverage. `cd frontend && npm run type-check` exits 0 (no TS errors). `npm test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx` → 5/5 pass (zero observations hides block, ≤3 retailers render flat list, >3 retailers render tablist with N+1 triggers, 90-day-old listing shows "as of" caveat, 5-day-old listing does not). `npm test -- --run src/pages/builder/ViewPart.test.tsx` → 3/3 pass after the guard hardening (no regression in the existing page test). Sibling S06 tests (`Sparkline`, `PriceDeltaLine`, `usePartPriceSummaries`, `SparklineCell`, `PartList.priceHistory`) → 31/31 pass — confirms no spillover regression from the ViewPart edits. The slice-level verification gate is partial at this task: detail-view assertions for retailer breakdown + stale caveat are now covered by unit tests (T03's contribution). The Playwright e2e screenshot/network-count assertions belong to T04 and remain unrun by design.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | ✅ pass | 4500ms |
| 2 | `cd frontend && npm test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx` | 0 | ✅ pass | 941ms |
| 3 | `cd frontend && npm test -- --run src/pages/builder/ViewPart.test.tsx src/pages/builder/ViewPart.priceSummary.test.tsx` | 0 | ✅ pass | 982ms |
| 4 | `cd frontend && npm test -- --run src/components/charts/Sparkline.test.tsx src/components/parts/PriceDeltaLine.test.tsx src/hooks/usePartPriceSummaries.test.ts src/components/parts/SparklineCell.test.tsx src/components/parts/PartList.priceHistory.test.tsx` | 0 | ✅ pass | 820ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`
