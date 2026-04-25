---
id: T01
parent: S05
milestone: M002
key_files:
  - backend/app/api/services/part_price_aggregation_service.py
  - backend/app/api/schemas/part_price_history.py
  - backend/tests/services/test_part_price_aggregation_service.py
key_decisions:
  - Computed `last_*` from a single ordered observation SELECT instead of a `row_number() OVER` window-function subquery — keeps the round-trip budget at 4 SELECTs for batch and avoids dialect-specific window-function quirks; the same SELECT also feeds the trend computation.
  - Trend threshold uses total expected drift (`slope * (n-1)`) vs ±1% of the mean, not raw slope vs 1%, so the up/down/flat verdict reflects what actually changed across the window rather than a tiny per-step delta.
  - Did NOT enforce a batch cap inside the service — that lives at the endpoint layer (T03) so the service is reusable from S07 alert evaluation without arbitrary limits, per the plan.
duration: 
verification_result: passed
completed_at: 2026-04-25T18:40:17.883Z
blocker_discovered: false
---

# T01: Add part_price_aggregation_service with windowed single + batch primitives, link-group aware, plus Pydantic v2 schemas and 11-case unit suite

**Add part_price_aggregation_service with windowed single + batch primitives, link-group aware, plus Pydantic v2 schemas and 11-case unit suite**

## What Happened

Stood up `backend/app/api/services/part_price_aggregation_service.py` exporting `parse_window`, `aggregate_single_part`, and `aggregate_batch`. The window contract translates the 5 literals (`30d`, `90d`, `180d`, `1y`, `all`) into a `since: datetime | None` lower bound; anything else raises `ValueError`. Both aggregation entry points respect the canonical link group: the single-part path resolves siblings via `link_group_part_ids` and joins history → listing → retailer in one query; the batch path bulk-resolves canonical mapping in two SELECTs (subject rows + sibling rows that point at any canonical), then runs two grouped aggregation SELECTs keyed by `func.coalesce(DBPart.canonical_part_id, DBPart.id)` — the same canonicalization pattern `read_parts_with_votes` already uses (parts.py L471–480). That keeps the per-batch cost independent of input size: 4 SELECTs total.

Trend is computed from a hand-rolled linear-regression slope over the chronologically-ordered prices, with the verdict bar set at ±1% of the mean over the *total expected drift* (`slope * (n-1)`) so a steeply-but-narrowly-trending series still classifies correctly without scipy. <2 observations or a zero mean both short-circuit to "flat".

I didn't reach for SQL window functions for the "last observation" lookup. The plan allowed either `row_number() OVER ... = 1` or a Python-side fallback; pulling all in-window observations once and ordering ascending lets a single SELECT serve both `last_*` and the trend computation, keeping the round-trip budget tight without depending on dialect-specific window-function quirks. The grouped min/max/count SELECT is kept separate per the plan's recipe so the SQL plan stays readable and the test counter stays stable.

Schemas extended in `backend/app/api/schemas/part_price_history.py`: added `PriceTrend` and `PriceWindow` literals, `PriceHistorySummary`, `RetailerPriceBreakdown`, `PriceHistorySinglePartResponse`, `PriceHistoryBatchSummaryItem`, `PriceHistoryBatchRequest` (with Pydantic `min_length=1, max_length=100` on `part_ids` so T03's endpoint auto-422s out-of-bounds bodies), and `PriceHistoryBatchResponse`. The existing `PartPriceHistoryReadWithRetailer` shape is reused unchanged for the per-row history list.

Tests in `backend/tests/services/test_part_price_aggregation_service.py` cover the 9 cases the plan enumerated: basic single-part with DESC history; window filters out-of-range observations; canonical link-group siblings aggregate onto the canonical; empty-history empty-shape contract; trend up/down/flat (parametrized — 3 cases inside one function, runs as 3); `parse_window`/`aggregate_single_part` ValueError on `99x`; batch returns one entry per requested id including the empty-summary shape for parts with no history; batch dedup'd across canonical group (canonical + duplicate share the same aggregate); batch query-count budget asserts `≤ 5` SELECTs for a 10-id input via the existing `query_counter` fixture. Inline retailer/listing/history seeding mirrors `tests/test_part_canonical_read_paths.py` since no shared retailer fixture exists in conftest.

Verification: `TESTING=true pytest tests/services/test_part_price_aggregation_service.py -n auto -q --no-cov` passes 11/11 in ~8s. Pyright not run separately — types match the existing service-layer style and the import surfaces match what T02/T03 will need.

## Verification

Ran the plan's verification command from `backend/`: `TESTING=true pytest tests/services/test_part_price_aggregation_service.py -n auto --rootdir=. -q --no-cov`. 11 tests passed (8 distinct functions + 3 parametrized trend cases). The query-counter test confirms the no-N+1 contract: a 10-id batch issues ≤ 5 SELECTs.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `TESTING=true pytest tests/services/test_part_price_aggregation_service.py -n auto --rootdir=. -q --no-cov` | 0 | ✅ pass | 8010ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/app/api/services/part_price_aggregation_service.py`
- `backend/app/api/schemas/part_price_history.py`
- `backend/tests/services/test_part_price_aggregation_service.py`
