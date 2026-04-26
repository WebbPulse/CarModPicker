---
id: T03
parent: S13
milestone: M002
key_files:
  - backend/app/api/endpoints/parts.py
  - backend/tests/api/endpoints/test_parts_price_history.py
  - backend/tests/fixtures/openapi_snapshot.json
  - frontend/src/api/parts.ts
  - frontend/src/api/parts.test.ts
  - frontend/src/pages/builder/ViewPart.tsx
  - frontend/src/pages/builder/ViewPart.priceSummary.test.tsx
  - frontend/src/components/parts/PriceHistoryLineChart.tsx
key_decisions:
  - Restored response_model=PriceHistorySinglePartResponse on the route decorator after narrowing the return annotation. During the MEM056 transition window response_model had to be None because FastAPI cannot infer a single response schema from a Union[New, Legacy] return type; with the Union gone, the decorator can again carry the canonical schema and OpenAPI now emits the precise response_model 200 shape (visible in the regenerated snapshot).
  - Restructured the ViewPart.tsx side-by-side grid into a single full-width 'Price by retailer' block instead of leaving an orphan one-column md:grid-cols-2 wrapper. The S06 'Price summary (90 days)' block above already provides the canonical price-history surface — keeping a half-width 'Price by retailer' next to empty space would have been visually broken.
  - Pruned PartPriceHistoryReadWithRetailer + DBPartPriceHistory + Union from parts.py imports (their only consumer was the deleted _legacy_get_part_price_history helper). Verified DBRetailer + link_group_part_ids stay because sibling endpoints still use them — checked via grep before removing.
duration: 
verification_result: passed
completed_at: 2026-04-26T05:21:38.023Z
blocker_discovered: false
---

# T03: Removed the S05 legacy=true price-history shim from backend + frontend and regenerated the OpenAPI snapshot — GET /parts/{id}/price-history now exposes only the S05 object shape

**Removed the S05 legacy=true price-history shim from backend + frontend and regenerated the OpenAPI snapshot — GET /parts/{id}/price-history now exposes only the S05 object shape**

## What Happened

Closed out the MEM056 transition window for `GET /api/parts/{id}/price-history`. The slice plan called for a pure code contraction with no new runtime behavior — the OpenAPI snapshot regeneration is the durable evidence that the surface narrowed as intended.

Backend (`backend/app/api/endpoints/parts.py`):
- Dropped the `_legacy_get_part_price_history` private helper (~32 lines) that ran the pre-S05 list-shape query path.
- Dropped the `legacy: bool = Query(False, ...)` parameter and the `if legacy: return ...` branch on `get_part_price_history`.
- Narrowed the return annotation from `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]` to just `PriceHistorySinglePartResponse`, restored `response_model=PriceHistorySinglePartResponse` on the route decorator (was `response_model=None` during the transition window because Union return types disable FastAPI's automatic response_model wiring), updated the success_description and docstring to reflect the single canonical shape.
- Pruned now-unused imports: `Union` from `typing`, `DBPartPriceHistory` (only consumer was the deleted helper), and `PartPriceHistoryReadWithRetailer` (only consumer was the deleted helper). Verified DBRetailer + link_group_part_ids are still used by sibling endpoints before removing them from the prune list.

Frontend:
- `frontend/src/api/parts.ts`: deleted the `getPartPriceHistory` method (the only forwarder of `legacy: true`) and removed the `PartPriceHistoryReadWithRetailer` import (its only consumer).
- `frontend/src/api/parts.test.ts`: dropped the 3 legacy-regression tests at lines ~223/234/250.
- `frontend/src/pages/builder/ViewPart.tsx`: removed the `PriceHistoryLineChart` import (line 38), the `fetchPriceHistoryRequestFn` factory + `useApiRequest` call + the `fetchPriceHistory(partId)` invocation in the data-loading effect (and the matching dependency-array entry), and the entire "Price history" left column of the side-by-side grid that hosted the line chart. Restructured the surrounding grid: the parent was `grid-cols-1 md:grid-cols-2` with Price history left + Price by retailer right; now Price by retailer takes full width via a single `<div className="mb-6">`. The S06 "Price summary (90 days)" block above is the canonical price-history surface as the slice plan called for.
- `frontend/src/components/parts/PriceHistoryLineChart.tsx`: deleted (no other consumers — verified via repo-wide grep).
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`: simplified the `installGetRouting` mock — the helper no longer needs to discriminate between the legacy and summary callers via the `params.legacy === true` branch (MEM077 / MEM084 documented this dual-caller dance, which is now obsolete on the `/parts/:id` surface). Dropped the lengthy explanatory comment about the dual callers.

Backend tests (`backend/tests/api/endpoints/test_parts_price_history.py`):
- Updated the module docstring to note the shim was removed in S13/T03 (was "until S13 audits all callers").
- Dropped `test_get_price_history_legacy_param_returns_list_shape` (the only legacy-shape regression-guard test).

OpenAPI snapshot:
- Regenerated `backend/tests/fixtures/openapi_snapshot.json` per MEM088 with `TESTING=true ENABLE_RATE_LIMITING=false python -c '...' > tests/fixtures/openapi_snapshot.json`. Verified the regenerated file has zero `legacy` matches; previously the route description and success message both mentioned the shim.

Verified per the task plan's verification block: backend pytest (test_parts_price_history.py + test_openapi_snapshot.py) → 18 passed; frontend `npm run type-check` → exit 0; frontend vitest (parts.test.ts + ViewPart.priceSummary.test.tsx) → 28 passed; final repo-wide grep for `legacy=true|legacy: true|getPartPriceHistory\b|PriceHistoryLineChart` across `frontend/src` + `backend/app` → zero matches (excluding the .pyc cache file).

Captured MEM137 documenting the 5-step removal pattern for closing out a MEM056 transition shim, so future agents don't have to rediscover the unused-import sweep + the response_model restoration step.

## Verification

Ran the four-part verification block from the task plan:
1. `cd backend && TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --no-cov` → 18 passed (1 deprecation warning, irrelevant), 5.75s.
2. `cd frontend && npm run type-check` → exit 0, no output (clean tsc).
3. `cd frontend && npm test -- --run src/api/parts.test.ts src/pages/builder/ViewPart.priceSummary.test.tsx` → 2 files, 28 tests, all passed (1.17s).
4. `grep -rn 'legacy=true\|legacy: true\|getPartPriceHistory\b\|PriceHistoryLineChart' frontend/src backend/app` → zero matches (only the auto-generated .pyc still has stale bytecode, which is expected).

OpenAPI snapshot was regenerated successfully and `grep -c legacy backend/tests/fixtures/openapi_snapshot.json` returns 0 — confirming the deprecated shim is fully gone from the published surface.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --no-cov` | 0 | ✅ pass | 5750ms |
| 2 | `npm run type-check` | 0 | ✅ pass | 8000ms |
| 3 | `npm test -- --run src/api/parts.test.ts src/pages/builder/ViewPart.priceSummary.test.tsx` | 0 | ✅ pass | 1170ms |
| 4 | `grep -rn 'legacy=true|legacy: true|getPartPriceHistory\b|PriceHistoryLineChart' frontend/src backend/app` | 1 | ✅ pass (zero matches) | 200ms |

## Deviations

Minor structural deviation from the task plan's step-7: the plan said 'remove the entire JSX block that renders <PriceHistoryLineChart>' but the surrounding parent was a 2-column grid with Price by retailer as its sibling — removing only the chart's column would have left an asymmetric grid with one empty cell. Restructured the parent from `<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 items-start">` containing two `<div className="min-w-0">` columns to a single `<div className="mb-6">` wrapper around just the Price by retailer column, preserving the inner div for layout consistency. Functionally equivalent to the plan's intent (delete the legacy chart, keep the retailer breakdown) and the priceSummary tests still pass.

## Known Issues

None.

## Files Created/Modified

- `backend/app/api/endpoints/parts.py`
- `backend/tests/api/endpoints/test_parts_price_history.py`
- `backend/tests/fixtures/openapi_snapshot.json`
- `frontend/src/api/parts.ts`
- `frontend/src/api/parts.test.ts`
- `frontend/src/pages/builder/ViewPart.tsx`
- `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`
- `frontend/src/components/parts/PriceHistoryLineChart.tsx`
