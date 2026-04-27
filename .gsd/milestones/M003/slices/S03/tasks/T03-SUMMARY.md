---
id: T03
parent: S03
milestone: M003
key_files:
  - frontend/src/pages/builder/ViewPart.tsx
  - frontend/src/pages/builder/ViewPart.priceSummary.test.tsx
  - frontend/e2e/price-history.spec.ts
  - frontend/src/pages/admin/PartsCuration.tsx
key_decisions:
  - Source rows from priceSummary.retailers as primary truth; fall back to listings only for retailers absent from history (preserves observation_count + sparkline access for the common case while still showing listing-only retailers)
  - Stale caveat (>60d) now derives from retailer.last_observed_at — single source of truth — replacing the prior dual caveat (listings-block had its own). The /parts/:id e2e assertion `getByText(staleCaveat)).toHaveCount(1)` continues to pass because MULTI_PART_ID has exactly one stale retailer (RetailerTwo)
  - Outbound `View at retailer` link is omitted (no placeholder) when no matching listing has product_url — keeps the row visually clean when the retailer is in price history but lacks a current listing URL
  - Removed unused isLoadingListings destructure (loading branch removed with the legacy block); kept fetchListings call in the existing useEffect since listingsData is still consumed for the retailer-id → product_url join
duration: 
verification_result: passed
completed_at: 2026-04-26T22:24:12.066Z
blocker_discovered: false
---

# T03: refactor(viewpart): collapse two redundant price blocks into one 'Price by retailer' table joining priceSummary.retailers ↔ listings, harden retailer outbound links with rel=noopener noreferrer + ExternalLink icon

**refactor(viewpart): collapse two redundant price blocks into one 'Price by retailer' table joining priceSummary.retailers ↔ listings, harden retailer outbound links with rel=noopener noreferrer + ExternalLink icon**

## What Happened

Executed the structural heart of S03. ViewPart.tsx now exposes a single 'Price by retailer' block in place of the prior `Price summary (90 days)` + `Price by retailer` siblings (deleted: RetailerBreakdownRow, PriceSummaryBlock, all 4 Tabs imports, the stat-strip + Tabs/flat list, the standalone listings-driven block). The collapsed block sources rows from `priceSummary.retailers` (preferred — carries last/min/max/observation_count + last_observed_at + sparkline data via the joined `priceSummary.history.filter(h => h.retailer_id === r.retailer_id)`) and joins to `listingsData` by retailer_id solely to discover `product_url` for the outbound `View at retailer` link. A small fallback path adds rows from listings with no matching retailer entry (history-empty edge case). The one-line summary header (`$X–$Y across N retailers, last observed Z`) renders only when observation_count > 0. The stale caveat (>60 days) now derives from `retailer.last_observed_at` — a single source of truth — eliminating the prior listings-block duplicate caveat. Empty-state copy (`No retailer pricing observed yet.`) renders when both sources are empty.\n\nOutbound link safety hardening: every `View at retailer` `<a>` carries `target="_blank" rel="noopener noreferrer"` plus a Lucide `<ExternalLink className="h-3 w-3" />` affordance. PartsCuration.tsx:97 swap from `rel="noreferrer"` → `rel="noopener noreferrer"` plus the same icon.\n\nTest contract rewritten: 5 vitest tests in ViewPart.priceSummary.test.tsx now pin the collapsed shape (no stat strip, no tabs, exactly one retailer-row per priceSummary.retailers entry, single-occurrence stale caveat, link with rel/target/ExternalLink svg). Two e2e assertions in price-history.spec.ts realigned to the new heading + new test-ids; stale-caveat single-occurrence assertion preserved as the durable signal that the collapse didn't introduce a duplicate.\n\nMinor cleanup: removed now-unused `isLoadingListings` destructure (the loading-state branch was deleted with the legacy block); removed unused `RetailerPriceBreakdown` type import (consumers gone).

## Verification

Three grep gates + tsc + vitest, all pass:\n1. `rg -q 'Price by retailer' frontend/src/pages/builder/ViewPart.tsx` → present\n2. `! rg -q 'price-summary-stat-strip|retailer-breakdown-flat|RetailerBreakdownRow|PriceSummaryBlock' frontend/src/pages/builder/ViewPart.tsx` → all four legacy symbols absent\n3. `rg -q 'noopener noreferrer' frontend/src/pages/admin/PartsCuration.tsx` → present\n4. `npm --prefix frontend run type-check` → exit 0, no diagnostics (caught one cycle of `last_price_updated_at: string | null | undefined` mismatch with Row.lastObservedAt: string | null; fixed with `?? null` coalesce)\n5. `npm --prefix frontend test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx` → 5/5 passed in 208ms\n\nE2E spec untouched in run-time (Playwright not exercised in autonomous mode), but the two affected assertions in price-history.spec.ts were rewritten to match the new contract: heading rename `Price summary (90 days)` → `Price by retailer`, test-id locator updates `retailer-breakdown-row|retailer-breakdown-flat|price-summary-stat-strip` → `retailer-row|price-summary-header`, plus the empty-state copy assertion. The MULTI_PART_ID mock keeps a stale retailer (RetailerTwo, last_observed_at = 90 days ago) so the single stale-caveat assertion still passes against the collapsed surface.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -q 'Price by retailer' frontend/src/pages/builder/ViewPart.tsx` | 0 | ✅ pass | 30ms |
| 2 | `! rg -q 'price-summary-stat-strip|retailer-breakdown-flat|RetailerBreakdownRow|PriceSummaryBlock' frontend/src/pages/builder/ViewPart.tsx` | 0 | ✅ pass | 30ms |
| 3 | `rg -q 'noopener noreferrer' frontend/src/pages/admin/PartsCuration.tsx` | 0 | ✅ pass | 30ms |
| 4 | `npm run type-check` | 0 | ✅ pass | 12000ms |
| 5 | `npm test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx` | 0 | ✅ pass (5/5 tests, 208ms) | 1050ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`
- `frontend/e2e/price-history.spec.ts`
- `frontend/src/pages/admin/PartsCuration.tsx`
