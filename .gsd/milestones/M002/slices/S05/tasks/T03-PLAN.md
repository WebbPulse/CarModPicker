---
estimated_steps: 36
estimated_files: 3
skills_used: []
---

# T03: Add `POST /api/parts/price-history` batch summary endpoint (1–100 IDs → min/max/last/trend per part)

Add a new POST handler in `backend/app/api/endpoints/parts.py` at path `/parts/price-history` (NOT under `/parts/{id}/...` — this is a list-route POST). Body: `PriceHistoryBatchRequest{ part_ids: list[UUID] (min 1, max 100), window: Optional[str] = '90d' }`. Response: `PriceHistoryBatchResponse{ summaries: dict[UUID, PriceHistoryBatchSummaryItem], window: str, requested_count: int, found_count: int }`.

Why POST and not GET: a 100-ID query string is unwieldy and trips proxy URL-length limits at scale. POST with a JSON body is the standard for batch-fetch operations and matches the REST-ish convention the existing endpoints use (e.g. `POST /parts/{id}/append-images` carries a JSON body for a fundamentally read-shaped op).

Handler steps:
- Decode body via Pydantic schema (T01 ships the schema with `Field(..., min_length=1, max_length=100)` on `part_ids` so FastAPI auto-422s out-of-bounds requests with a structured error).
- Validate `window` via `parse_window`; on ValueError raise `HTTPException(422, {error_code: 'INVALID_WINDOW'})`.
- Call `aggregate_batch(db, body.part_ids, body.window)`.
- Return `PriceHistoryBatchResponse` with the summaries dict + meta. `found_count` = number of dict entries with `observation_count > 0`.
- Emit one structured INFO log: `price_history_aggregation: endpoint=batch part_count=<n> window=<window> link_groups_resolved=<n> rows_scanned=<n> elapsed_ms=<n>`. Same fields/format as T02.

Positioning in `parts.py`: place the new POST handler BEFORE the `BaseEndpointRouter` instantiation (`base_router = BaseEndpointRouter(...)` at L1170) so route-collision precedence is correct. Add it right after the existing `get_part_price_history` handler (T02) for code locality.

No auth required (matches `/parts/{id}/price-history` and the rest of the public-read parts surface). The endpoint is idempotent and side-effect-free, so this is safe.

Tests added to `backend/tests/api/endpoints/test_parts_price_history.py` (same file as T02):
- `test_post_batch_price_history_basic` — seed 3 parts with history; POST with all 3 IDs; assert response has 3 summaries dict entries, `requested_count == 3`, `found_count == 3`.
- `test_post_batch_price_history_includes_empty_entries` — POST with 3 IDs where 1 has no history; assert dict has 3 keys, the empty one has `observation_count == 0`, `min_cents is None`, `trend == 'flat'`. `found_count == 2`.
- `test_post_batch_price_history_window_default_90d` — body without `window` field; assert response `window == '90d'`.
- `test_post_batch_price_history_window_custom` — body with `window='30d'`; assert filtering applies.
- `test_post_batch_price_history_invalid_window_returns_422` — body with `window='xyz'`; assert 422 with `error_code: INVALID_WINDOW`.
- `test_post_batch_price_history_empty_part_ids_returns_422` — body with `part_ids: []`; assert 422 (Pydantic min_length).
- `test_post_batch_price_history_too_many_ids_returns_422` — body with 101 UUIDs; assert 422 (Pydantic max_length) with the limit named in the error.
- `test_post_batch_price_history_unknown_ids_return_empty_entries` — body with 2 random (nonexistent) UUIDs; assert response status 200, dict has 2 entries, both empty-summary shape (NOT 404 — batch endpoints never 404 on missing IDs, that's a per-item concern).
- `test_post_batch_price_history_aggregates_link_group` — seed canonical A + duplicate B; POST with `[A.id]`; assert A's summary includes B's listings (no double-count even if both A and B are in the request).
- `test_post_batch_price_history_query_count` — wrap with `query_counter`; for a 50-ID request, assert ≤ 6 SQL statements (validates the no-N+1 contract end-to-end through the endpoint layer, not just the service).

Update `backend/tests/fixtures/openapi_snapshot.json` for the new endpoint shape (regenerate as in T02).

FAILURE MODES (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `aggregate_batch` | bubble up to FastAPI default 500 handler | n/a (sync) | n/a — service guarantees a dict-keyed-by-uuid response shape |
| Pydantic body validation | FastAPI auto-422 with structured error including the offending field | n/a | n/a |
| `parse_window` | catch ValueError → 422 with `error_code: INVALID_WINDOW` | n/a | n/a |

LOAD PROFILE (Q6):
- Shared resources: same as T02 — SQLAlchemy session per request, Postgres conn budget
- Per-operation cost: independent of batch size — 1 link-group resolve + 2 grouped SELECTs (min/max/count + last). For batch=50, total round-trips ≤ 4. This is the property D-04 and R019 are betting on; T05 measures it.
- 10x breakpoint: at 10× current traffic with batch=50 the dominant cost is the grouped query against `part_price_history`; the existing `(part_listing_id, observed_at)` composite index keeps it cheap. If the gate misses (R019 fails), R036 (materialized table) opens.

NEGATIVE TESTS (Q7):
- Malformed inputs: empty list (422), > 100 IDs (422), non-UUID strings in `part_ids` (422 from Pydantic), missing `part_ids` key (422), body is empty object (422)
- Error paths: all-unknown-IDs (200 with all-empty dict — this is by design, batch endpoints don't 404), service exception (500 + structured error)
- Boundary conditions: exactly 1 ID (works), exactly 100 IDs (works), `window='all'` with 100 IDs and millions of history rows (slow but correct — T05 measures whether 'slow' falls inside budget)

## Inputs

- ``backend/app/api/services/part_price_aggregation_service.py` — `aggregate_batch`, `parse_window` from T01`
- ``backend/app/api/schemas/part_price_history.py` — `PriceHistoryBatchRequest`, `PriceHistoryBatchResponse`, `PriceHistoryBatchSummaryItem` from T01`
- ``backend/app/api/endpoints/parts.py` — existing module to extend (after T02's edits)`
- ``backend/tests/api/endpoints/test_parts_price_history.py` — existing test file from T02 to extend`

## Expected Output

- ``backend/app/api/endpoints/parts.py` — new `post_batch_price_history` handler registered at `/parts/price-history` BEFORE the BaseEndpointRouter instantiation`
- ``backend/tests/api/endpoints/test_parts_price_history.py` — extended with the 10 batch-endpoint cases enumerated above`
- ``backend/tests/fixtures/openapi_snapshot.json` — regenerated snapshot reflecting the new POST endpoint`

## Verification

TESTING=true pytest backend/tests/api/endpoints/test_parts_price_history.py backend/tests/api/test_openapi_snapshot.py -n auto --rootdir=backend -q --no-cov

## Observability Impact

Signals added/changed: one structured INFO log per batch request mirroring T02 (`price_history_aggregation: endpoint=batch ...`) — same field set so a single `grep price_history_aggregation` surfaces both surfaces' traffic. How a future agent inspects this: tail the log; the `part_count` field disambiguates batch from single. Failure state exposed: a 422 carries a structured `error_code` (`INVALID_WINDOW` or Pydantic's default field-error structure for body shape errors); a 500 means service-level failure and the FastAPI error handler logs the exception trace.
