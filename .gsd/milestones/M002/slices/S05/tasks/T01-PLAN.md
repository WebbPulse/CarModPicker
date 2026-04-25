---
estimated_steps: 48
estimated_files: 3
skills_used: []
---

# T01: Add `app/api/services/part_price_aggregation_service.py` with windowed single + batch aggregation primitives

Stand up `backend/app/api/services/part_price_aggregation_service.py` as a pure read service that the two new endpoints call. Two public functions: `aggregate_single_part(db, part_id, window)` and `aggregate_batch(db, part_ids, window)`. Both must respect the canonical link group by resolving via `link_group_part_ids` from `app/api/services/part_linker_service.py` — duplicates' listings count toward the canonical's history (mirroring the existing `/{part_id}/price-history` and `/{part_id}/best-listing` semantics).

Window contract — accept the literal strings `30d`, `90d` (default for single GET), `180d`, `1y`, `all`. Anything else raises `ValueError` (the endpoint layer translates to HTTP 422). Internal representation: convert to a `since: datetime | None` (None for `all`), so the aggregation SQL filters `PartPriceHistory.observed_at >= since` only when `since is not None`.

`aggregate_single_part(db, part_id, window) -> PriceHistorySinglePartResponse` returns:
- `summary` block: `min_cents`, `max_cents`, `last_cents`, `last_observed_at`, `trend` (one of `up`, `down`, `flat`), `observation_count`. Trend is computed by linear-regression slope sign over the windowed observations: `> +1%` of mean = `up`, `< -1%` of mean = `down`, otherwise `flat`. Use `statistics.fmean` and a hand-rolled slope (no scipy). With <2 observations, trend = `flat`.
- `retailers` list: one entry per Retailer that has any listing in the link group: `{retailer_id, retailer_name, min_cents, max_cents, last_cents, last_observed_at, observation_count}`. Sorted by `retailer_name` ASC for stable ordering.
- `history` list: every `PartPriceHistory` row in the window, joined to `PartListing` and `Retailer`, in `observed_at DESC` order. Same shape as the existing `PartPriceHistoryReadWithRetailer`.

`aggregate_batch(db, part_ids, window) -> dict[UUID, PriceHistoryBatchSummaryItem]` returns one entry per requested part_id (even if it has no observations — the value is the empty-summary shape so the frontend can iterate without holes). Each value has `min_cents`, `max_cents`, `last_cents`, `last_observed_at`, `trend`, `observation_count`. Implementation: resolve all link groups in one pass (single `IN` query against `Part.id` + `Part.canonical_part_id`), then a single windowed aggregation query joining `PartListing → PartPriceHistory` and grouping by canonical part id. Avoid N+1 — the test suite asserts query count.

Query shape (use SQLAlchemy 2.0 `select()` + `func.min/max/count`, NOT raw SQL):
```python
select(
    canonical_id_expr.label('canonical_id'),
    func.min(DBPartPriceHistory.price_cents).label('min'),
    func.max(DBPartPriceHistory.price_cents).label('max'),
    func.count(DBPartPriceHistory.id).label('cnt'),
).join(DBPartListing, DBPartPriceHistory.part_listing_id == DBPartListing.id)
 .join(DBPart, DBPart.id == DBPartListing.part_id)
 .where(canonical_id_expr.in_(canonical_ids), <window>)
 .group_by(canonical_id_expr)
```
where `canonical_id_expr = func.coalesce(DBPart.canonical_part_id, DBPart.id)` — same canonicalization pattern the existing `read_parts_with_votes` uses for `min_price_subq` (parts.py L471–480).

For `last_cents`/`last_observed_at`/`trend`, do a second windowed select that fetches the most-recent observation per canonical group. Window functions DO work in SQLite ≥3.25 (the in-memory test DB), so a `row_number() OVER (PARTITION BY canonical_id ORDER BY observed_at DESC) = 1` subquery is fine for both dialects — prefer that over a Python-side fallback unless a quick spike against `db_session` shows the syntax doesn't compile cleanly; if so, fall back to ordering DESC + `LIMIT 1` per canonical via a CTE.

Batch input cap: callers pass a list of UUIDs; the service does NOT enforce a cap — that lives at the endpoint layer (T03) so the service is reusable from S07 alert evaluation without arbitrary limits.

Tests in `backend/tests/services/test_part_price_aggregation_service.py`:
- `test_aggregate_single_part_basic` — seed 1 part, 1 retailer, 3 history rows across 90 days; assert `summary.min_cents`, `max_cents`, `last_cents`, `observation_count == 3`, `retailers` has 1 entry, `history` has 3 rows in DESC order.
- `test_aggregate_single_part_window_filters_old_observations` — seed 5 history rows spanning 1 year; with `window='30d'`, only the 30-day rows appear in `summary` and `history`.
- `test_aggregate_single_part_includes_link_group_siblings` — seed canonical part A and duplicate B (both with listings + history); query A; assert summary aggregates rows from BOTH A and B's listings.
- `test_aggregate_single_part_empty_history` — seed a part with no listings; assert summary is the well-formed empty shape (`min_cents=None, observation_count=0, trend='flat'`), `retailers=[]`, `history=[]`.
- `test_aggregate_single_part_trend_up_down_flat` — three sub-cases seeding ascending, descending, and flat price series; assert `trend` value.
- `test_aggregate_single_part_invalid_window_raises` — pass `window='99x'`; assert `ValueError`.
- `test_aggregate_batch_returns_entry_per_requested_id` — request 3 part_ids where only 2 have history; assert dict has 3 keys, the empty one matches the empty-summary shape.
- `test_aggregate_batch_canonical_dedup` — request canonical A AND duplicate B (same link group); assert the result aggregates correctly without double-counting.
- `test_aggregate_batch_query_count` — wrap with the existing `query_counter` fixture from `conftest.py` (line 112 reference); for a 10-part-id batch, assert ≤ 5 SQL statements (link-group resolve + min/max/count + last + summary fetch + at most one extra). This pins the no-N+1 contract.

Tests use a small inline retailer fixture (no shared retailer fixture exists in conftest.py — instantiate `Retailer(name=..., is_active=True)` and `PartListing(...)` + `PartPriceHistory(...)` directly via `db_session`, mirroring the pattern in `tests/test_part_canonical_read_paths.py`).

This task introduces NO endpoint changes — the service is exercised entirely from unit tests. T02/T03 wire it.

FAILURE MODES (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `link_group_part_ids` | bubble up — function returns `[part_id]` for unknown IDs by design | n/a (sync DB call) | n/a |
| `db_session` (SQLAlchemy session) | bubble up to caller; endpoint layer translates to 500 | n/a (sync) | n/a |
| Empty link group (part deleted mid-request) | return empty-summary shape (do NOT 404 here — endpoint decides) | n/a | n/a |

LOAD PROFILE (Q6):
- Shared resources: SQLAlchemy SessionLocal pool (one session per request), Postgres connection budget
- Per-operation cost (single): ≤ 3 round-trips (link group + summary + history). Per-operation cost (batch of 50): ≤ 3 round-trips (link groups + grouped min/max/count + last) — INDEPENDENT of batch size. That's the whole point of D-04 query-time aggregation.
- 10x breakpoint: Postgres connection pool exhaustion if endpoints are misused as a hot path; mitigated because the service has no internal locks and grouped queries do the heavy lifting. T05 perf gate is the falsifiable check.

NEGATIVE TESTS (Q7):
- Malformed inputs: `window='99x'` → ValueError; empty `part_ids=[]` for batch → returns `{}` (empty dict, not error)
- Error paths: deleted part_id → empty-summary entry (no exception); link-group lookup raises → propagate
- Boundary conditions: 1-row history (trend='flat'); 2-row history (trend computed cleanly); window='30d' on a 1-year-old part with no recent observations (returns empty summary, NOT the all-time min/max)

## Inputs

- ``backend/app/api/services/part_linker_service.py` — `link_group_part_ids` resolves canonical + duplicates`
- ``backend/app/api/models/part_listing.py` — `PartListing` model with `(part_id, retailer_id)` uniqueness`
- ``backend/app/api/models/part_price_history.py` — `PartPriceHistory` model with `(part_listing_id, observed_at)` time-series`
- ``backend/app/api/models/retailer.py` — `Retailer.name` for retailer-breakdown labels`
- ``backend/app/api/schemas/part_price_history.py` — existing `PartPriceHistoryReadWithRetailer` schema to reuse for the `history` list`
- ``backend/app/api/endpoints/parts.py` — reference for canonical_id_expr pattern (read_parts_with_votes, ~L471)`
- ``backend/tests/conftest.py` — `db_session`, `query_counter` fixtures`
- ``backend/tests/test_part_canonical_read_paths.py` — pattern for inline Retailer/Listing/History seed without a shared fixture`

## Expected Output

- ``backend/app/api/services/part_price_aggregation_service.py` — new pure read service exporting `aggregate_single_part`, `aggregate_batch`, `parse_window``
- ``backend/app/api/schemas/part_price_history.py` — extended with `PriceHistorySummary`, `RetailerPriceBreakdown`, `PriceHistorySinglePartResponse`, `PriceHistoryBatchSummaryItem`, `PriceHistoryBatchRequest`, `PriceHistoryBatchResponse` Pydantic v2 schemas`
- ``backend/tests/services/test_part_price_aggregation_service.py` — new test file with the 9 cases enumerated`

## Verification

TESTING=true pytest backend/tests/services/test_part_price_aggregation_service.py -n auto --rootdir=backend -q --no-cov

## Observability Impact

Signals added/changed: none (pure read service; logging happens at the endpoint layer in T02/T03). Failure state exposed: empty-history case returns well-formed empty shape rather than raising — this is the deliberate failure-visibility contract.
