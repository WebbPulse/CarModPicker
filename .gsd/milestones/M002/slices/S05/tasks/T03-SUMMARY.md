---
id: T03
parent: S05
milestone: M002
key_files:
  - backend/app/api/endpoints/parts.py
  - backend/tests/api/endpoints/test_parts_price_history.py
  - backend/tests/fixtures/openapi_snapshot.json
key_decisions:
  - Reserved the endpoint-level `INVALID_WINDOW` 422 branch for service-layer reuse — the Pydantic Literal rejects bad windows from HTTP callers first with `VALIDATION_ERROR`. Test asserts either error_code is acceptable so the contract holds whichever path fires.
  - Derived `found_count` server-side from `observation_count > 0` rather than asking the service to track it — keeps `aggregate_batch` interface unchanged and avoids drift between service and endpoint counts.
  - Materialized `part_ids` into Python strings BEFORE entering the `query_counter` context block in the 50-id test — accessing `.id` on expired ORM instances after `commit()` triggers per-Part SELECT refreshes that pollute the counter (saw 104 vs 4). Captured as MEM049.
duration: 
verification_result: passed
completed_at: 2026-04-25T18:54:48.770Z
blocker_discovered: false
---

# T03: Add POST /api/parts/price-history batch summary endpoint (1–100 IDs → min/max/last/trend per part) with 10 endpoint tests + regenerated OpenAPI snapshot

**Add POST /api/parts/price-history batch summary endpoint (1–100 IDs → min/max/last/trend per part) with 10 endpoint tests + regenerated OpenAPI snapshot**

## What Happened

Wired a new `POST /api/parts/price-history` handler in `backend/app/api/endpoints/parts.py` immediately after the T02 GET handler and before the `BaseEndpointRouter` instantiation so route-collision precedence stays correct. The handler decodes a `PriceHistoryBatchRequest` (Pydantic's `min_length=1`/`max_length=100` on `part_ids` auto-422s out-of-bounds requests), probes `parse_window` to surface a structured `INVALID_WINDOW` 422 for any window that bypasses the schema, calls `aggregate_batch`, and returns a `PriceHistoryBatchResponse` with `requested_count` and a derived `found_count` (entries with `observation_count > 0`). One INFO log line mirrors the T02 single-endpoint shape: `price_history_aggregation: endpoint=batch part_count=N window=... link_groups_resolved=N rows_scanned=N elapsed_ms=N`.

Added 10 batch test cases to `backend/tests/api/endpoints/test_parts_price_history.py`: basic 3-part response shape, mixed-empty entries, default-window echo, custom window filtering, invalid-window 422, empty `part_ids` 422, 101-id 422, unknown-id empty entries (200, never 404), link-group dedup on canonical id, and a 50-id query-count gate that asserts ≤ 6 SELECTs to enforce the no-N+1 contract end-to-end through the endpoint.

The invalid-window test accepts either `INVALID_WINDOW` or `VALIDATION_ERROR` because the schema's `Literal["30d","90d","180d","1y","all"]` rejects free-form strings before the handler runs (Pydantic path); the endpoint-level `INVALID_WINDOW` branch is reserved for callers that bypass the schema (service-layer reuse). The 50-id query-count test initially failed with 104 SELECTs because materializing `[str(p.id) for p in parts]` inside the `with query_counter()` block triggers per-Part lazy-load refreshes after `db_session.commit()`. Fixed by capturing `part_ids` before entering the context — counter then drops to 4 (well under the ≤6 budget). Captured this as MEM049.

Regenerated `backend/tests/fixtures/openapi_snapshot.json` (17,192 lines after) and confirmed the snapshot test passes.

## Verification

Ran the task plan's verification command (`pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py`) plus a regression sweep of `tests/api/endpoints/test_parts.py`. All 46 tests pass — 18 in price-history (8 GET from T02 + 10 new POST), 1 OpenAPI snapshot, 27 in test_parts.py. Confirmed both routes register distinctly via `app.routes` introspection: `/api/parts/{part_id}/price-history` (GET) and `/api/parts/price-history` (POST). The structured INFO log appears in captured stderr matching the documented format.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py -n auto --rootdir=backend -q --no-cov` | 0 | ✅ pass | 8220ms |
| 2 | `TESTING=true pytest tests/api/endpoints/test_parts_price_history.py tests/test_openapi_snapshot.py tests/api/endpoints/test_parts.py -n auto --rootdir=backend -q --no-cov` | 0 | ✅ pass | 8680ms |
| 3 | `TESTING=true pytest tests/api/endpoints/test_parts_price_history.py::test_post_batch_price_history_query_count -n 0 -q --no-cov` | 0 | ✅ pass | 400ms |

## Deviations

The task plan's verification command listed `backend/tests/api/test_openapi_snapshot.py` but the file actually lives at `backend/tests/test_openapi_snapshot.py` (no `api/` segment). Used the correct path; the original gate command returned exit code 5 (no tests collected) because of this path mismatch — fixing the path made the same suite pass.

## Known Issues

none

## Files Created/Modified

- `backend/app/api/endpoints/parts.py`
- `backend/tests/api/endpoints/test_parts_price_history.py`
- `backend/tests/fixtures/openapi_snapshot.json`
