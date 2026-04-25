---
id: T02
parent: S05
milestone: M002
key_files:
  - backend/app/api/endpoints/parts.py
  - backend/app/api/services/part_price_aggregation_service.py
  - backend/tests/api/endpoints/test_parts_price_history.py
  - backend/tests/fixtures/openapi_snapshot.json
  - backend/tests/test_part_canonical_read_paths.py
key_decisions:
  - Nested HTTPException 422 detail under `details` (not as a sibling key) to fit `app.api.middleware.error_handler`'s reshape contract — the middleware drops unknown keys, so `allowed` had to live under `details.allowed`. Captured as MEM048.
  - Used `response_model=None` + `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]` return type to support both new-shape and `legacy=true` list-shape from the same route. FastAPI auto-encodes via jsonable_encoder.
  - Extracted `apply_retailer_filter` helper into the service module (not the endpoint) so the post-aggregation retailer slice is testable in isolation and reusable from S07 alert evaluation; the endpoint just calls the service.
  - Updated existing `test_price_history_aggregates_across_link_group` in `tests/test_part_canonical_read_paths.py` to the new object shape rather than passing `legacy=true` — that test is an internal regression check, not an out-of-band caller the shim was designed to protect.
duration: 
verification_result: passed
completed_at: 2026-04-25T18:47:27.386Z
blocker_discovered: false
---

# T02: Rewrite GET /api/parts/{id}/price-history to return aggregated PriceHistorySinglePartResponse with window param + retailer filter + legacy=true list-shape shim

**Rewrite GET /api/parts/{id}/price-history to return aggregated PriceHistorySinglePartResponse with window param + retailer filter + legacy=true list-shape shim**

## What Happened

Replaced the pre-S05 list-returning handler in `backend/app/api/endpoints/parts.py` (formerly L1134–L1167) with one that delegates to `aggregate_single_part` from T01 and returns the new `PriceHistorySinglePartResponse` object shape (`summary`, `retailers`, `history`, `window`). Added optional `window` (default `90d`; literals `30d|90d|180d|1y|all`) and `legacy=true` query params. Kept the existing optional `retailer_id` and made it work against the new shape via a new `apply_retailer_filter(result, retailer_id)` helper extracted into the service module — the helper recomputes summary `min/max/last/trend/observation_count` from the filtered slice rather than the cross-retailer aggregate, which is the contract T05 will load-test against.

The `legacy=true` shim is implemented via a private `_legacy_get_part_price_history(db, part_id, retailer_id)` in `parts.py` that runs the pre-S05 query path verbatim — same DESC ordering, same join, same retailer filter, same `PartPriceHistoryReadWithRetailer` per-row shape — so callers that haven't migrated keep the old contract until S13. To let one route return either an object or a list, I dropped the `response_model=` and annotate the handler return type as `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]`; FastAPI auto-encodes both via `jsonable_encoder`. Added a single structured INFO log per non-legacy request: `price_history_aggregation: endpoint=single part_count=1 window=<...> link_groups_resolved=<count> rows_scanned=<observation_count> elapsed_ms=<n>`, timed with `time.perf_counter`. The legacy branch is intentionally not logged — it's transitional.

FAILURE MODES: discovered that `app.api.middleware.error_handler.handle_http_exception` reshapes `HTTPException(detail=dict)` into a flat `{success, message, error_code, details?}` envelope and drops unknown sibling keys. So my first 422 implementation (`detail={"error_code": "INVALID_WINDOW", "allowed": [...]}`) lost the `allowed` field on the wire. Fixed by nesting the allowed-windows list inside `details` per the middleware contract. Captured MEM048 for future endpoints. Also exposed `ALLOWED_WINDOWS` (sorted list) from the service so the endpoint and tests share the same source of truth.

TESTS: created `backend/tests/api/endpoints/test_parts_price_history.py` with the 8 cases the plan enumerated — default window object shape, `30d` filtering, `all` includes everything, `99x` 422 with structured `error_code: INVALID_WINDOW` + `details.allowed`, retailer filter narrows summary (NOT cross-retailer aggregate), `legacy=true` returns list shape, 404 on unknown part, link-group aggregation. Seeding mirrors the T01 service test helpers (inline retailer/listing/history) so the SQLite in-memory DB used by pytest can carry the schema. Updated the existing `tests/test_part_canonical_read_paths.py::test_price_history_aggregates_across_link_group` to read `body["history"]` from the new object shape — that test isn't an out-of-band caller, just an internal regression check, so the legacy shim doesn't apply.

OPENAPI SNAPSHOT: regenerated `backend/tests/fixtures/openapi_snapshot.json` per the file's documented mechanism (`TESTING=true ENABLE_RATE_LIMITING=false python -c '...' > snapshot`). The actual snapshot test path is `tests/test_openapi_snapshot.py`, not `tests/api/test_openapi_snapshot.py` as the plan referenced — minor plan-snapshot drift, ran the correct file.

## Verification

Ran the slice verification command from `backend/`: `TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py tests/api/endpoints/test_parts.py -n auto --rootdir=. -q --no-cov`. 36 tests passed (8 new endpoint tests + the 1 openapi-snapshot test + 27 pre-existing parts endpoint tests). Also re-ran T01's service unit suite (11/11) and the canonical-read-paths suite (7/7) to confirm no regressions on the T01 service contract or the link-group read paths I touched.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py tests/api/endpoints/test_parts.py -n auto --rootdir=. -q --no-cov` | 0 | pass | 8610ms |
| 2 | `TESTING=true pytest tests/services/test_part_price_aggregation_service.py -n auto --rootdir=. -q --no-cov` | 0 | pass | 8050ms |
| 3 | `TESTING=true pytest tests/test_part_canonical_read_paths.py -n auto --rootdir=. -q --no-cov` | 0 | pass | 8060ms |

## Deviations

Plan referenced `backend/tests/api/test_openapi_snapshot.py`; the actual path is `backend/tests/test_openapi_snapshot.py`. Ran the correct file. The OpenAPI snapshot regenerated cleanly and the snapshot test passes.

## Known Issues

None.

## Files Created/Modified

- `backend/app/api/endpoints/parts.py`
- `backend/app/api/services/part_price_aggregation_service.py`
- `backend/tests/api/endpoints/test_parts_price_history.py`
- `backend/tests/fixtures/openapi_snapshot.json`
- `backend/tests/test_part_canonical_read_paths.py`
