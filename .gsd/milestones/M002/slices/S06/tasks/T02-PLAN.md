---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Wire sparkline + delta line into PartList catalog rows (table + card layouts)

Integrate the T01 primitives into `frontend/src/components/parts/PartList.tsx` (which is what `/parts` actually renders via PartsCatalog). The hook must be called once at the parent level — NEVER one fetch per row. Step 1: in PartList, after `parts` is computed (around line ~501), call `const partIds = useMemo(() => (parts ?? []).map(p => p.id), [parts]);` then `const { summaries } = usePartPriceSummaries(partIds, '90d');`. Step 2: extend the price column rendering. In the **table layout** (around line ~813), replace the current single-line `$X.XX` cell with a vertical stack: top line = existing best-price `$X.XX`, second line = `<PriceDeltaLine summary={summaries[part.id]} />` (renders nothing when no summary). Append a 60×16 `<Sparkline />` immediately to the right of the price cell using a new flex container — the sparkline reads the per-listing history from `summaries[part.id]` is impossible (summary doesn't carry history), so for the catalog cells the sparkline reads from a NEW per-row prop: pass `summaries[part.id]` to a small inner SparklineCell component that itself fetches the per-part history lazily IF the summary indicates `observation_count >= 2` — implementation: SparklineCell uses an in-memory request cache keyed by partId, calls `partsApi.getPartPriceHistorySummary(partId, { window: '90d' })` ONLY when scrolled into view via IntersectionObserver, caches the response history for 5 minutes. (This keeps the catalog batch fast and only pulls history for parts the user actually sees.) Step 3: in the **card layout** (around line ~933), add a third row inside the main content block under the description, rendering `<PriceDeltaLine summary={summaries[part.id]} />` followed by `<SparklineCell partId={part.id} summary={summaries[part.id]} />` at width=120 height=24. Step 4: add an integration test `frontend/src/components/parts/PartList.priceHistory.test.tsx` that renders PartList with three mock parts (zero / single / multi observations), mocks `apiClient.post` to return a fabricated `PriceHistoryBatchResponse`, and asserts: (a) exactly ONE POST to `/parts/price-history` is made for the visible page, (b) the multi-observation card shows a `<svg>` with role=img, (c) the zero-observation card shows no sparkline. Do NOT modify the existing best_price_cents rendering — the new pieces are additive.

## Inputs

- ``frontend/src/components/parts/PartList.tsx``
- ``frontend/src/components/charts/Sparkline.tsx``
- ``frontend/src/components/parts/PriceDeltaLine.tsx``
- ``frontend/src/hooks/usePartPriceSummaries.ts``
- ``frontend/src/api/parts.ts``
- ``frontend/src/types/Api.ts``
- ``frontend/src/test/setup.ts``

## Expected Output

- ``frontend/src/components/parts/PartList.tsx``
- ``frontend/src/components/parts/SparklineCell.tsx``
- ``frontend/src/components/parts/SparklineCell.test.tsx``
- ``frontend/src/components/parts/PartList.priceHistory.test.tsx``

## Verification

cd frontend && npm run type-check && npm test -- --run src/components/parts/SparklineCell.test.tsx src/components/parts/PartList.priceHistory.test.tsx

## Observability Impact

Network panel: exactly one POST /parts/price-history per displayed page (asserted by test). On batch fetch failure, hook returns empty summaries and the catalog falls back to the legacy best-price-only rendering — failure is silent to the user but logged via console.warn from T01.
