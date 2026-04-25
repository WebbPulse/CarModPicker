---
estimated_steps: 21
estimated_files: 8
skills_used: []
---

# T03: Remove S05 legacy=true price-history shim and regenerate OpenAPI snapshot

Pure code change — the only code increment S13 owes. The S05 explicit follow-up was: remove the `legacy=true` query-param branch on GET /parts/{id}/price-history once the new summary endpoint is the canonical consumer. Audit confirmed (verified at slice planning): the only frontend caller is `frontend/src/pages/builder/ViewPart.tsx:82` (`partsApi.getPartPriceHistory(partId)`), which feeds `frontend/src/components/parts/PriceHistoryLineChart.tsx`. The S06 'Price summary (90 days)' block above already covers the user need. Chrome extension has zero hits for `getPartPriceHistory` or `price-history?legacy` (verified via grep).

Backend changes in `backend/app/api/endpoints/parts.py`:
1. Drop the `legacy: bool = False` query parameter on the `get_part_price_history` route.
2. Drop the entire `_legacy_get_part_price_history` private helper (function ends around line 1190 — read first to confirm exact range).
3. Drop the `if legacy: return _legacy_get_part_price_history(db, part_id, retailer_id)` branch.
4. Drop the `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]` return-type union — narrow to just `PriceHistorySinglePartResponse`.

Frontend changes:
5. `frontend/src/api/parts.ts`: remove the `getPartPriceHistory(partId, params?)` function entirely (it forwards `legacy: true`). It is the only caller of the legacy shim.
6. `frontend/src/api/parts.test.ts`: drop the 3 legacy-regression test cases at lines ~223, ~234, ~250 (`getPartPriceHistory GETs /parts/:id/price-history with legacy=true and no other params`, `getPartPriceHistory forwards retailer_id alongside legacy=true`, `getPartPriceHistory still uses legacy=true shim and returns array shape`).
7. `frontend/src/pages/builder/ViewPart.tsx`: remove the `getPartPriceHistory` import (line 38), remove the legacy useApiRequest call (line 82), remove the entire JSX block that renders `<PriceHistoryLineChart data={priceHistoryData} />` (line 816). The S06 'Price summary (90 days)' block above stays as the canonical price-history surface. Update any types/loading-state accordingly.
8. Delete `frontend/src/components/parts/PriceHistoryLineChart.tsx` (no other consumers).
9. `frontend/src/pages/builder/ViewPart.priceSummary.test.tsx`: drop the comment line at ~117 referencing the removed legacy fetcher; if any test assertion targeted the legacy chart specifically, drop it.

Backend test changes:
10. `backend/tests/api/endpoints/test_parts_price_history.py`: drop the legacy-shape regression-guard test cases. Existing object-shape tests stay green.

OpenAPI regeneration:
11. From `backend/`: `TESTING=true ENABLE_RATE_LIMITING=false python -c 'import json,sys;from app.main import app;sys.stdout.write(json.dumps(app.openapi(),indent=2,sort_keys=True))' > tests/fixtures/openapi_snapshot.json` (per MEM088).

Verification:
- `cd backend && TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --no-cov` exits 0.
- `cd frontend && npm run type-check` exits 0.
- `cd frontend && npm test -- --run src/api/parts.test.ts src/pages/builder/ViewPart.priceSummary.test.tsx` exits 0.
- `grep -rn 'legacy=true\|legacy: true\|getPartPriceHistory\b\|PriceHistoryLineChart' frontend/src backend/app` returns ONLY matches inside .test files that intentionally remain (or zero matches if all consumers removed).

## Inputs

- ``backend/app/api/endpoints/parts.py` — contains `_legacy_get_part_price_history` helper + `legacy=true` branch to remove`
- ``frontend/src/api/parts.ts` — `getPartPriceHistory` function forwards `legacy: true``
- ``frontend/src/pages/builder/ViewPart.tsx` — line 38 imports + line 82 calls + line 816 renders the legacy chart`
- ``frontend/src/components/parts/PriceHistoryLineChart.tsx` — to be deleted`
- ``backend/tests/fixtures/openapi_snapshot.json` — regenerate after endpoint param removal`

## Expected Output

- ``backend/app/api/endpoints/parts.py` — `legacy=true` query param + `_legacy_get_part_price_history` helper + Union return type removed`
- ``backend/tests/api/endpoints/test_parts_price_history.py` — legacy-shape regression-guard tests removed`
- ``backend/tests/fixtures/openapi_snapshot.json` — regenerated`
- ``frontend/src/api/parts.ts` — `getPartPriceHistory` function deleted`
- ``frontend/src/api/parts.test.ts` — 3 legacy-regression test cases deleted`
- ``frontend/src/pages/builder/ViewPart.tsx` — legacy fetch + chart import + chart JSX removed`
- ``frontend/src/components/parts/PriceHistoryLineChart.tsx` — file deleted`
- ``frontend/src/pages/builder/ViewPart.priceSummary.test.tsx` — stale legacy reference comment cleaned`

## Verification

cd backend && TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --no-cov && cd ../frontend && npm run type-check && npm test -- --run src/api/parts.test.ts src/pages/builder/ViewPart.priceSummary.test.tsx && ! grep -rn 'PriceHistoryLineChart' src/

## Observability Impact

No new runtime signals. Removes a deprecated branch — the OpenAPI snapshot regeneration is the durable evidence that the endpoint surface contracted as intended. T06's gauntlet re-runs the snapshot test as a regression check.
