---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T03: Render per-retailer breakdown + stale 'as of' caveat on /parts/:partId detail view

Extend `frontend/src/pages/builder/ViewPart.tsx` to consume the new aggregation summary alongside the existing legacy price-history fetch. Step 1: add a third api hook usage near the existing `fetchListings` / `fetchPriceHistory` (around line 149-160): `const { data: priceSummary, executeRequest: fetchPriceSummary } = useApiRequest((id: string) => partsApi.getPartPriceHistorySummary(id, { window: '90d' }));`. Trigger it inside the existing useEffect at line 168. Step 2: locate the existing 'Price by retailer' block (line ~645) and INSERT a new sibling block ABOVE it titled 'Price summary (90 days)' that renders, when `priceSummary?.summary.observation_count > 0`: a stat strip with min / max / last / trend, plus a per-retailer table backed by `priceSummary.retailers` showing retailer_name, min_cents, max_cents, last_cents, last_observed_at, observation_count. Format cents via `(cents / 100).toFixed(2)`. Step 3: add the stale caveat — for each row in the EXISTING listings list (line ~677), if `listing.last_price_updated_at` is non-null AND its date is more than 60 days before now, append a `<span className="text-xs text-amber-400 ml-2">(as of {localized date})</span>` after the existing 'updated <date>' span. Pull the 60-day threshold into a const `STALE_LISTING_THRESHOLD_DAYS = 60` at the top of the file. Step 4: the new per-retailer breakdown block must use the S08 `Tabs` primitive ONLY IF retailer count > 3 (one tab per retailer + an 'All' tab); otherwise render a flat list of retailer rows. Import `Tabs, TabsList, TabsTrigger, TabsContent` from `frontend/src/components/ui/tabs`. Step 5: add tests in `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` covering: (a) zero observations → 'Price summary' block does not render, (b) 2 retailers → flat list, no tabs, (c) 5 retailers → tabs render with one trigger per retailer, (d) listing with last_price_updated_at 90 days ago → 'as of' caveat visible, (e) listing with last_price_updated_at 5 days ago → no caveat. Mock the apiClient as in T01/T02. The existing PriceHistoryLineChart block at line 638 stays untouched — it still consumes the legacy array shape via the existing `getPartPriceHistory` shim.

## Inputs

- ``frontend/src/pages/builder/ViewPart.tsx``
- ``frontend/src/api/parts.ts``
- ``frontend/src/types/Api.ts``
- ``frontend/src/components/ui/tabs.tsx``

## Expected Output

- ``frontend/src/pages/builder/ViewPart.tsx``
- ``frontend/src/pages/builder/ViewPart.priceSummary.test.tsx``

## Verification

cd frontend && npm run type-check && npm test -- --run src/pages/builder/ViewPart.priceSummary.test.tsx

## Observability Impact

Detail-page summary fetch failure renders an inline 'Price summary unavailable' message (no throw); existing PriceHistoryLineChart and listings list keep rendering via their own independent fetches. No new backend signals.
