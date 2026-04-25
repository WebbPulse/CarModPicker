---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T01: Build Sparkline + PriceDeltaLine primitives + usePartPriceSummaries hook

Stand up the three reusable client-side surfaces S06 needs. (1) `frontend/src/components/charts/Sparkline.tsx` — pure-SVG inline sparkline (no recharts dep), props `{ history: PartPriceHistoryReadWithRetailer[]; width?: number; height?: number; ariaLabel?: string }`. Renders nothing when `history.length === 0`. Renders a single filled dot when `history.length === 1`. Otherwise renders a polyline normalized to `[0, width] x [0, height]` with `preserveAspectRatio='none'` and a 1.5px stroke using the design-system `hsl(var(--primary))` color. Sort points by `observed_at` ascending before plotting. (2) `frontend/src/components/parts/PriceDeltaLine.tsx` — props `{ summary: PriceHistorySummary | null | undefined }`. When summary is null/undefined OR `summary.observation_count === 0`, render nothing. When `observation_count === 1`, render `"Tracked since <localized date>"`. Otherwise render `"$<min> → $<max> over <N> days"` where min/max are `last_cents` rounded to whole-dollar and N is the calendar-day delta between earliest and `last_observed_at` of the window (use `summary.last_observed_at` for end; the window length comes from the `window` query — render N from `summary.observation_count`-implied span only when both bounds are knowable, else render `"$<min> → $<max>"` without the duration). Trend arrow: prepend `↑` for trend='up', `↓` for trend='down', `·` for 'flat'. (3) `frontend/src/hooks/usePartPriceSummaries.ts` — `function usePartPriceSummaries(partIds: string[], window: PriceHistoryBatchRequest['window'] = '90d'): { summaries: Record<string, PriceHistorySummary>; isLoading: boolean; error: string | null }`. Memoize on a stable sorted-joined key of `partIds`; debounce identical calls within a render cycle via useRef-cached last-key. Skip the fetch when `partIds.length === 0`. On error, log via `console.warn('[usePartPriceSummaries]', err)` and return `{ summaries: {}, error: <message>, isLoading: false }` — never throw. Use `partsApi.getBatchPriceHistorySummary({ part_ids, window })` (already typed and exported from `frontend/src/api/parts.ts`). Write vitest unit tests for all three surfaces in sibling `*.test.tsx` files, covering: (a) Sparkline zero/single/multi rendering, (b) PriceDeltaLine null/zero/single/multi cardinalities AND each trend arrow, (c) the hook's batched-fetch behavior, error path, and empty-IDs short-circuit using the existing global apiClient mock from `src/test/setup.ts` (extend the mock per-test with `vi.mocked(apiClient.post).mockResolvedValueOnce(...)`).

## Inputs

- ``frontend/src/types/Api.ts``
- ``frontend/src/api/parts.ts``
- ``frontend/src/test/setup.ts``
- ``frontend/src/components/ui/button.tsx``

## Expected Output

- ``frontend/src/components/charts/Sparkline.tsx``
- ``frontend/src/components/charts/Sparkline.test.tsx``
- ``frontend/src/components/parts/PriceDeltaLine.tsx``
- ``frontend/src/components/parts/PriceDeltaLine.test.tsx``
- ``frontend/src/hooks/usePartPriceSummaries.ts``
- ``frontend/src/hooks/usePartPriceSummaries.test.ts``

## Verification

cd frontend && npm run type-check && npm test -- --run src/components/charts/Sparkline.test.tsx src/components/parts/PriceDeltaLine.test.tsx src/hooks/usePartPriceSummaries.test.ts

## Observability Impact

Hook logs failures via `console.warn('[usePartPriceSummaries]', err)` so e2e/network failures surface in browser console without throwing. No new metrics or backend signals.
