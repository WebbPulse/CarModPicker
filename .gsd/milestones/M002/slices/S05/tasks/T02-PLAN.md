---
estimated_steps: 35
estimated_files: 3
skills_used: []
---

# T02: Enhance `GET /api/parts/{id}/price-history` with `window` param + retailer-breakdown summary response (legacy shim for old callers)

Replace the current `get_part_price_history` handler in `backend/app/api/endpoints/parts.py` (currently returns `List[PartPriceHistoryReadWithRetailer]`, see L1134–L1167) with a new handler that returns the richer `PriceHistorySinglePartResponse` shape produced by `aggregate_single_part` from T01. Path stays `/{part_id}/price-history`. Adds optional `window` query param (default `90d`, accepts `30d`/`90d`/`180d`/`1y`/`all`); keeps the existing optional `retailer_id` query param.

Response-shape contract — the response is now an OBJECT, not a LIST. To avoid breaking any out-of-band caller before T04 lands, the new endpoint also accepts an OPTIONAL `legacy=true` query param: when present, the response is the legacy `List[PartPriceHistoryReadWithRetailer]` shape (the current behavior). The `legacy=true` shim is removed in S13 final integration once we've audited all callers.

Update `app/api/endpoints/parts.py`:
- Import the new aggregation service: `from app.api.services.part_price_aggregation_service import aggregate_single_part, parse_window`.
- Import the new response schemas from T01: `PriceHistorySinglePartResponse`.
- Replace the existing handler at L1134–L1167. The new handler:
  - Validates `window` via `parse_window` (re-raise ValueError as `HTTPException(422, {error_code: 'INVALID_WINDOW', allowed: [...]})`).
  - Calls `aggregate_single_part(db, part_id, window)` after `get_entity_or_404(db, DBPart, part_id, 'part')`.
  - When `retailer_id` is set, filter the `history` list AND `retailers` list AND recompute the `summary` from the filtered observations (extract a small helper in T01's service, `_apply_retailer_filter(result, retailer_id)`).
  - When `legacy=True`, return only the legacy list shape (call the existing query path inline via a private helper `_legacy_get_part_price_history` so it doesn't drift).
  - Emit one structured INFO log: `price_history_aggregation: endpoint=single part_count=1 window=<window> link_groups_resolved=<n> rows_scanned=<n> elapsed_ms=<n>`. Use `logging.getLogger(__name__)`. Time the call with `time.perf_counter`.

Tests in `backend/tests/api/endpoints/test_parts_price_history.py` (NEW file — keep separate from `test_parts.py` so the perf-history surface is locatable):
- `test_get_price_history_default_window_returns_summary_object` — seed part + 5 history rows; GET `/parts/{id}/price-history` (no window param); assert response is an OBJECT with `summary`, `retailers`, `history` keys; assert `summary.observation_count == 5`.
- `test_get_price_history_window_30d_filters_old` — seed 3 rows in 30d, 2 rows older than 30d; GET with `window=30d`; assert `summary.observation_count == 3` and `len(history) == 3`.
- `test_get_price_history_window_all_includes_everything` — seed rows across 2 years; GET with `window=all`; assert all rows present.
- `test_get_price_history_invalid_window_returns_422` — GET with `window=99x`; assert status 422 with error detail mentioning the allowed values.
- `test_get_price_history_retailer_filter_narrows_summary` — seed 2 retailers with overlapping history; GET with `retailer_id=<one>`; assert `retailers` has 1 entry and `summary` matches that retailer's min/max/count, NOT the cross-retailer aggregate.
- `test_get_price_history_legacy_param_returns_list_shape` — GET with `legacy=true`; assert response is a LIST (not an object) and matches the legacy `PartPriceHistoryReadWithRetailer[]` shape exactly (keeps frontend backwards-compatible until T04 lands).
- `test_get_price_history_part_not_found_returns_404` — GET with a random UUID; assert 404.
- `test_get_price_history_aggregates_link_group` — seed canonical + duplicate with history on each; query the canonical; assert summary includes both.

Also update `backend/tests/fixtures/openapi_snapshot.json` if the OpenAPI snapshot test fails — regenerate per the project's snapshot mechanism (read `backend/tests/api/test_openapi_snapshot.py` to find the regen flag). Commit the regenerated snapshot in this task's diff.

FAILURE MODES (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `aggregate_single_part` | bubble up; FastAPI default 500 handler logs and returns 500 | n/a (sync) | n/a — service guarantees well-formed empty shape on no-data |
| `parse_window` | catch `ValueError` → raise `HTTPException(422, {error_code: 'INVALID_WINDOW', allowed: [...]})` | n/a | n/a |
| `get_entity_or_404` | bubble up its own 404 | n/a | n/a |

LOAD PROFILE (Q6):
- Shared resources: SQLAlchemy session per request (FastAPI dependency-scoped), Postgres conn budget
- Per-operation cost: ≤ 4 round-trips (entity exists check + service's 3 SELECTs)
- 10x breakpoint: same as T01 service — no per-request locks, no extra fan-out; T05 load test is the gate

NEGATIVE TESTS (Q7):
- Malformed inputs: invalid window string (422), invalid UUID for part_id (FastAPI 422 by default), retailer_id that doesn't match any listing (returns empty `retailers` and empty `history`, status 200)
- Error paths: part deleted between auth and aggregation → 404 from `get_entity_or_404` is fine
- Boundary conditions: `window=all` against an empty-history part returns empty-summary shape with status 200; `legacy=true` AND `retailer_id` set together — supported, both filters apply

## Inputs

- ``backend/app/api/services/part_price_aggregation_service.py` — `aggregate_single_part`, `parse_window` from T01`
- ``backend/app/api/schemas/part_price_history.py` — `PriceHistorySinglePartResponse` from T01`
- ``backend/app/api/endpoints/parts.py` — existing `get_part_price_history` handler at L1134–L1167 to replace`
- ``backend/app/api/utils/common_patterns.py` — `PublicEndpointDeps`, `get_standard_public_endpoint_dependencies``
- ``backend/tests/api/test_openapi_snapshot.py` — snapshot regeneration mechanism`

## Expected Output

- ``backend/app/api/endpoints/parts.py` — `get_part_price_history` rewritten to return `PriceHistorySinglePartResponse`, `_legacy_get_part_price_history` extracted as private helper for `legacy=true` shim`
- ``backend/tests/api/endpoints/test_parts_price_history.py` — new test file with the 8 cases enumerated`
- ``backend/tests/fixtures/openapi_snapshot.json` — regenerated snapshot reflecting the new response schema (and the legacy shim still documented)`

## Verification

TESTING=true pytest backend/tests/api/endpoints/test_parts_price_history.py backend/tests/api/test_openapi_snapshot.py backend/tests/api/endpoints/test_parts.py -n auto --rootdir=backend -q --no-cov

## Observability Impact

Signals added/changed: one structured INFO log per request (`price_history_aggregation: endpoint=single ...`) carrying part_count, window, link_groups_resolved, rows_scanned, elapsed_ms. How a future agent inspects this: tail the uvicorn log during a request or `grep price_history_aggregation backend/app.log`. Failure state exposed: a slow query shows up as a high `elapsed_ms` value in the log; a 422 from `parse_window` shows up as a structured error response with `error_code: INVALID_WINDOW` and the allowed window list.
