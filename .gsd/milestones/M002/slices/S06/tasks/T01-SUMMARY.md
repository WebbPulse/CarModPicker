---
id: T01
parent: S06
milestone: M002
key_files:
  - frontend/src/components/charts/Sparkline.tsx
  - frontend/src/components/charts/Sparkline.test.tsx
  - frontend/src/components/parts/PriceDeltaLine.tsx
  - frontend/src/components/parts/PriceDeltaLine.test.tsx
  - frontend/src/hooks/usePartPriceSummaries.ts
  - frontend/src/hooks/usePartPriceSummaries.test.ts
key_decisions:
  - Pure-SVG inline sparkline using viewBox + preserveAspectRatio='none' and hsl(var(--primary)) stroke — no recharts/visx dependency added
  - PriceDeltaLine multi-observation branch renders the bare '$<min> → $<max>' fallback (no 'over N days' suffix) because PriceHistorySummary has no earliest-observed timestamp; the task plan explicitly defines this fallback when both bounds aren't knowable
  - usePartPriceSummaries memoizes on a primitive sorted-joined string key (not the raw array) and uses a frozen EMPTY_SUMMARIES singleton for empty state to prevent fresh-reference render loops
duration: 
verification_result: passed
completed_at: 2026-04-25T21:25:21.249Z
blocker_discovered: false
---

# T01: Add Sparkline + PriceDeltaLine primitives and usePartPriceSummaries batch-fetch hook for S06 price-history catalog UI

**Add Sparkline + PriceDeltaLine primitives and usePartPriceSummaries batch-fetch hook for S06 price-history catalog UI**

## What Happened

Built the three reusable client-side surfaces S06 needs to render price history on catalog and detail views.

(1) `frontend/src/components/charts/Sparkline.tsx` — pure-SVG inline sparkline (no recharts dep). Renders nothing for zero observations, a centered filled `<circle r=2>` for a single observation, and a normalized `<polyline>` with 1.5px `hsl(var(--primary))` stroke and `preserveAspectRatio="none"` for multi-observation series. Sorts by `observed_at` ascending before plotting and gracefully handles flat series (zero price-range → centered y=height/2).

(2) `frontend/src/components/parts/PriceDeltaLine.tsx` — props `{ summary: PriceHistorySummary | null | undefined }`. Returns null for null/undefined or `observation_count === 0`. Renders `↑/↓/·` trend arrow + `Tracked since <localized date>` for one observation, and `↑/↓/· $<min> → $<max>` for two-or-more. Per the task plan, the duration suffix collapses to the bare min/max range because `PriceHistorySummary` has no earliest-observed timestamp — the calendar-day span between earliest and `last_observed_at` isn't computable from the summary alone, which the plan explicitly handles via the "render `$<min> → $<max>` without the duration" fallback.

(3) `frontend/src/hooks/usePartPriceSummaries.ts` — `usePartPriceSummaries(partIds: string[], window?: '30d'|'90d'|'180d'|'1y'|'all')`. Memoizes on a sorted-joined primitive key, debounces identical re-renders via a `useRef`-cached `lastKeyRef`, short-circuits on empty IDs, calls `partsApi.getBatchPriceHistorySummary({ part_ids, window })`, and on failure logs `console.warn('[usePartPriceSummaries]', err)` and returns `{ summaries: {}, error, isLoading: false }` without throwing.

Each surface has a sibling test file (vitest + Testing Library) that covers the cardinalities and edge cases called out in the task plan: Sparkline zero/single/multi/sort/aria/flat (6 tests), PriceDeltaLine null/undefined/zero/single/multi/round/each-trend-arrow (10 tests), hook empty-IDs short-circuit, batch fetch + window arg propagation, stable-key debounce across rerenders, error path with `console.warn` assertion, and refetch on key change (6 tests). All 22 pass.

One implementation gotcha worth flagging (captured as MEM074): the first cut of the hook included the raw `partIds: string[]` in the effect deps and unconditionally `setSummaries({})` on the empty-IDs branch. Callers passing a new array reference every render combined with the always-fresh `{}` setState put the test runner into an infinite render loop and OOM'd the worker. Fixed by computing a primitive `sortedKey` string via `useMemo`, deriving `sortedIds` from that key (also memoized), gating the empty branch behind `lastKeyRef`, and using a frozen `EMPTY_SUMMARIES` singleton so empty state is a stable reference. After the fix, the test that previously crashed the worker now finishes in 182ms.

## Verification

Ran the slice-plan verification command exactly as specified:

`cd frontend && npm run type-check && npm test -- --run src/components/charts/Sparkline.test.tsx src/components/parts/PriceDeltaLine.test.tsx src/hooks/usePartPriceSummaries.test.ts`

- `npm run type-check` → exit 0 (`tsc -b --noEmit` clean across the whole frontend)
- `npm test` → exit 0; 3 test files, 22 tests passed (Sparkline 6, PriceDeltaLine 10, usePartPriceSummaries 6)
- Lint: ran ESLint on the six new files — 0 errors, 0 warnings.

Slice-level verification status (intermediate task; not all bars apply to T01):
- Runtime signals: deferred to T02+ (no catalog page touched yet).
- Inspection surfaces: Sparkline + PriceDeltaLine props are inspectable in the React tree; tests assert via `data-testid` ("sparkline", "sparkline-polyline", "price-delta-line", "price-delta-arrow") which doubles as a future devtools/e2e selector.
- Failure visibility: hook's `console.warn('[usePartPriceSummaries]', err)` path is exercised by the error-path test and asserted via `vi.spyOn(console, 'warn')`.
- Redaction constraints: n/a — no PII or auth in these surfaces.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd frontend && npm run type-check` | 0 | pass | 1435ms |
| 2 | `cd frontend && npm test -- --run src/components/charts/Sparkline.test.tsx src/components/parts/PriceDeltaLine.test.tsx src/hooks/usePartPriceSummaries.test.ts` | 0 | pass | 1090ms |
| 3 | `cd frontend && npx eslint <6 new files>` | 0 | pass | 3000ms |

## Deviations

Hook `.test.ts` file extension matches the task plan's Expected Output list. Initial implementation of the hook hit an infinite render loop / OOM in tests because the empty-IDs branch unconditionally setState'd `{}` on every render — fixed by gating the empty branch behind `lastKeyRef` and using a frozen `EMPTY_SUMMARIES` singleton. This was an implementation-debugging adjustment, not a deviation from the plan's contract.

## Known Issues

None blocking. PriceDeltaLine's multi-observation "over N days" suffix is not rendered because the summary lacks an earliest-observed timestamp; the task plan anticipated this and specified the bare "$<min> → $<max>" fallback. If the backend summary later exposes earliest-observed (or the hook starts pulling per-part history), the suffix can be added without API churn.

## Files Created/Modified

- `frontend/src/components/charts/Sparkline.tsx`
- `frontend/src/components/charts/Sparkline.test.tsx`
- `frontend/src/components/parts/PriceDeltaLine.tsx`
- `frontend/src/components/parts/PriceDeltaLine.test.tsx`
- `frontend/src/hooks/usePartPriceSummaries.ts`
- `frontend/src/hooks/usePartPriceSummaries.test.ts`
