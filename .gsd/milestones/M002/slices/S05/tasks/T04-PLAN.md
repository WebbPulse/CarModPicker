---
estimated_steps: 58
estimated_files: 3
skills_used: []
---

# T04: Wire frontend client + types for both new endpoints (`getPartPriceHistorySummary`, `getBatchPriceHistorySummary`)

Add typed API client methods + TypeScript interfaces in `frontend/src/api/parts.ts` and `frontend/src/types/Api.ts` so that S06 (sparkline + detail view) and S07 (alert evaluation) can consume the new endpoints without re-deriving the response shapes.

Update `frontend/src/types/Api.ts` (insert after the existing `PartPriceHistoryReadWithRetailer` at L316):
```ts
export type PriceTrend = 'up' | 'down' | 'flat';

export interface PriceHistorySummary {
  min_cents: number | null;
  max_cents: number | null;
  last_cents: number | null;
  last_observed_at: string | null;
  trend: PriceTrend;
  observation_count: number;
}

export interface RetailerPriceBreakdown {
  retailer_id: string;
  retailer_name: string;
  min_cents: number | null;
  max_cents: number | null;
  last_cents: number | null;
  last_observed_at: string | null;
  observation_count: number;
}

export interface PriceHistorySinglePartResponse {
  summary: PriceHistorySummary;
  retailers: RetailerPriceBreakdown[];
  history: PartPriceHistoryReadWithRetailer[];
  window: string;
}

export interface PriceHistoryBatchSummaryItem extends PriceHistorySummary {}

export interface PriceHistoryBatchRequest {
  part_ids: string[];
  window?: '30d' | '90d' | '180d' | '1y' | 'all';
}

export interface PriceHistoryBatchResponse {
  summaries: Record<string, PriceHistoryBatchSummaryItem>;
  window: string;
  requested_count: number;
  found_count: number;
}
```

Update `frontend/src/api/parts.ts`:
- Import the new types from `../types/Api`.
- KEEP the existing `getPartPriceHistory(partId, params?: { retailer_id?: string })` method working — use the `legacy=true` query-param shim from T02 so any existing caller (Chrome extension, downstream pages) sees the same array shape.
- ADD `getPartPriceHistorySummary: (partId: string, params?: { window?: PriceHistoryBatchRequest['window']; retailer_id?: string }) => apiClient.get<PriceHistorySinglePartResponse>(`/parts/${partId}/price-history`, { params })` — calls the new object-shape endpoint without `legacy`.
- ADD `getBatchPriceHistorySummary: (body: PriceHistoryBatchRequest) => apiClient.post<PriceHistoryBatchResponse>('/parts/price-history', body)`.

Migrate the existing `getPartPriceHistory` to forward to `legacy=true`:
```ts
getPartPriceHistory: (partId, params) =>
  apiClient.get<PartPriceHistoryReadWithRetailer[]>(`/parts/${partId}/price-history`, {
    params: { ...params, legacy: true },
  }),
```

Update `frontend/src/api/parts.test.ts` (vitest): add tests covering the two new methods. Pattern: existing tests in this file use `vi.spyOn(apiClient, 'get'/'post')` and assert the URL + params. Mirror them.
- `getPartPriceHistorySummary forwards window to GET /parts/:id/price-history with object response type`
- `getPartPriceHistorySummary forwards retailer_id when provided`
- `getBatchPriceHistorySummary POSTs body to /parts/price-history`
- `getPartPriceHistory still uses legacy=true shim and returns array shape` (regression guard for the shim contract)

No Load Profile / Negative Tests sections in this task plan — the frontend client wrappers are thin enough that backend-level coverage in T01–T03 covers load and negative behavior. UI-level rendering tests for the new shapes belong in S06.

Check: run `npm run type-check` (in `frontend/`) — must exit 0. Run `npm run lint` — must exit 0.

## Inputs

- ``frontend/src/api/parts.ts` — existing `getPartPriceHistory` method at L86–L91 to migrate to legacy shim`
- ``frontend/src/types/Api.ts` — existing `PartPriceHistoryReadWithRetailer` at L316 to extend`
- ``frontend/src/api/parts.test.ts` — existing test file with vi.spyOn pattern to mirror`
- ``backend/app/api/schemas/part_price_history.py` — source of truth for the response shapes from T01`

## Expected Output

- ``frontend/src/types/Api.ts` — extended with `PriceTrend`, `PriceHistorySummary`, `RetailerPriceBreakdown`, `PriceHistorySinglePartResponse`, `PriceHistoryBatchSummaryItem`, `PriceHistoryBatchRequest`, `PriceHistoryBatchResponse` interfaces`
- ``frontend/src/api/parts.ts` — `getPartPriceHistory` rewritten to use `legacy=true` shim; `getPartPriceHistorySummary` and `getBatchPriceHistorySummary` added`
- ``frontend/src/api/parts.test.ts` — extended with the 4 new test cases enumerated`

## Verification

cd frontend && npm run type-check && npm run lint && npm test -- --run src/api/parts.test.ts

## Observability Impact

Signals added/changed: none — this is a thin client layer. Diagnostic affordances live on the backend (T02/T03 logs) and on axios's existing interceptors. Failure state exposed: a backend 422/500 surfaces as a rejected axios promise the consuming hook will catch.
