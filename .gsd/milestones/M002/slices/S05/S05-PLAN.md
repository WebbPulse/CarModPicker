# S05: Price-history aggregation API + perf gate

**Goal:** Ship query-time price-history aggregation as two read endpoints — `GET /api/parts/{id}/price-history?window=90d` (per-part: per-retailer breakdown + listing-level history) and `POST /api/parts/price-history` (batch: min/max/last/trend per part for up to 100 IDs in one round-trip) — backed by a new `part_price_aggregation_service` module that respects the canonical link group via `link_group_part_ids`. Wire typed clients in `frontend/src/api/parts.ts` and types in `frontend/src/types/Api.ts` so S06 can consume them. Lock the perf gate from D004 with a Locust load test that hits both endpoints at 10× current traffic on the current catalog and asserts p95 inside budget — if the gate misses, R036 (materialized `part_price_summary`) opens as a follow-up; if it passes, we ship query-time and move on.
**Demo:** Call GET /api/parts/{id}/price-history?window=90d — returns retailer breakdowns and listing-level history. Call POST /api/parts/price-history with [part_id_1..part_id_50] — returns min/max/last/trend per part. Run load test (k6 or locust) at 10x current traffic on current catalog size — p95 inside budget.

## Must-Haves

- `pytest backend/tests/services/test_part_price_aggregation_service.py -n auto --rootdir=backend -q --no-cov` is green: covers single-part window slicing, retailer-breakdown summary across canonical link group, batch min/max/last/trend, empty-history short-circuit, invalid-window rejection.
- `pytest backend/tests/api/endpoints/test_parts_price_history.py -n auto --rootdir=backend -q --no-cov` is green: covers GET window param contract (default `90d`, `30d`, `1y`, `all`), POST batch contract (1, 50, 100 IDs), 422 on >100 IDs, 422 on malformed window, link-group aggregation parity with `link_group_part_ids`.
- `pytest backend/tests/api/test_openapi_snapshot.py` stays green (or its snapshot is intentionally regenerated with the new endpoint shape committed in this slice).
- `pytest backend/tests/api/endpoints/test_parts.py -n auto --rootdir=backend -q --no-cov` stays green — no regression on the existing `/{part_id}/price-history` contract callers (the frontend `getPartPriceHistory` keeps working via the `legacy=true` query-param shim added in T02).
- `npm test -- --run src/api/parts.test.ts` (in `frontend/`) is green: covers the new `getPartPriceHistorySummary` and `getBatchPriceHistorySummary` client methods.
- `bash backend/scripts/perf/run_price_history_loadtest.sh` exits 0 against a freshly populated sample DB (uses `scripts/populate_sample_data.py` then runs the locust scenario in headless mode for 60s at 10× baseline RPS) — the script asserts: GET p95 < 200 ms, POST(50 IDs) p95 < 500 ms, error rate 0%. Exit 1 (and the script writes `backend/.perf-runs/price-history-FAILED-<ts>.json` with the failing percentiles + a remediation note pointing at R036) if any assertion fails. The summary JSON must be inspectable by a future agent: `cat backend/.perf-runs/price-history-PASSED-<ts>.json` shows the percentile breakdown and the parameters used.
- THREAT SURFACE — the new POST batch endpoint and the enhanced GET are the only attack surfaces in this slice; both are public-read (matching existing `/{part_id}/price-history` posture). Abuse: attacker submits a 100-UUID batch to amplify backend SQL cost, or repeatedly hammers the endpoint to denial-of-service the perf budget. Mitigated by: Pydantic `max_length=100` on `part_ids` (FastAPI auto-422 anything larger); the existing rate-limiter middleware (registered in `app/main.py` for the `/api` prefix) covers the new path automatically — verified by hitting the new path from `tests/middleware/test_rate_limiting.py` patterns. Data exposure: response includes part IDs, retailer names, prices — all public-read data, matches the existing surface; no PII or auth context. Input trust: untrusted `part_ids` reach a SQL `IN(...)` clause — fully parameterized via SQLAlchemy ORM (no raw f-string SQL anywhere in the new service); `window` query param is whitelisted via `parse_window` to a fixed enum so it cannot reach SQL as user-controlled string.
- REQUIREMENT IMPACT — Requirements touched: R007 (price-history read endpoints — primary), R019 (perf gate at 10× baseline — primary). Re-verify: existing `/{part_id}/price-history` callers (frontend `partsApi.getPartPriceHistory`, Chrome extension if any) must keep working — covered by the `legacy=true` shim in T02 plus `test_parts.py` regression run; existing `test_openapi_snapshot.py` must regenerate or stay green. Decisions revisited: D004 (price-history aggregation strategy) — this slice is the live test of D004's bet that query-time aggregation holds at 10× without materialization; if R019 misses, R036 opens per D004's revisability clause. D008 (admin extraction-health DB-derived signal, not EMF) — unaffected, separate domain.

## Proof Level

- This slice proves: integration

- Real runtime required: yes — load test hits a live uvicorn server against the local sample-data catalog (locust headless mode)
- Human/UAT required: no — both endpoints and the perf gate are mechanically verifiable

## Integration Closure

- Upstream surfaces consumed: `app/api/services/part_linker_service.py::link_group_part_ids` (canonical link-group resolution — duplicates' listings count toward the canonical's history), `app/api/models/part_listing.py::PartListing` (`(part_id, retailer_id)` uniqueness, `last_known_price_cents`, `last_price_updated_at`), `app/api/models/part_price_history.py::PartPriceHistory` (`(part_listing_id, observed_at)` time-series; D-04 confirms the composite index is in place), `app/api/models/retailer.py::Retailer.name`, `app/api/utils/common_patterns.py::PublicEndpointDeps + get_standard_public_endpoint_dependencies`, `scripts/populate_sample_data.py` (load-test fixture seed).
- New wiring introduced in this slice: `app/api/services/part_price_aggregation_service.py` (new module — pure read service, no imports from endpoints), two updated route handlers in `app/api/endpoints/parts.py` (GET rewritten in place with a `legacy=true` shim for backwards compatibility; POST appended), one new typed object on the frontend client (`partsApi.getPartPriceHistorySummary`, `partsApi.getBatchPriceHistorySummary`), and a new perf-runner shell script + locust file under `backend/scripts/perf/`. `backend/.perf-runs/` added to `.gitignore`.
- What remains before the milestone is truly usable end-to-end: S06 consumes the typed client to render sparklines + retailer breakdowns; S07 reuses `part_price_aggregation_service` to evaluate alert thresholds. Nothing in S05 ships a user-visible surface — this slice opens the data seam only.

## Verification

- Runtime signals: every aggregation request emits one structured INFO log line: `price_history_aggregation: endpoint=<single|batch> part_count=N window=<window> link_groups_resolved=N rows_scanned=N elapsed_ms=N`. The perf-gate script writes one summary JSON file per run under `backend/.perf-runs/price-history-{PASSED,FAILED}-<iso8601>.json` with the locust percentile dump + the assertion verdict.
- Inspection surfaces: `backend/.perf-runs/` (gitignored) is the single canonical location for perf-gate evidence; the most recent file is what S13 milestone verification re-reads. Single endpoint is reachable via `curl -s 'http://localhost:8000/api/parts/<id>/price-history?window=90d' | jq` and the batch via `curl -X POST -H 'Content-Type: application/json' -d '{"part_ids":["..."]}' http://localhost:8000/api/parts/price-history | jq` once the server is running.
- Failure visibility: an aggregation that produces zero rows still returns a well-formed empty payload (`{"summary": {"min_cents": null, "max_cents": null, "last_cents": null, "trend": "flat", "observation_count": 0}, "retailers": [], "history": []}`) — the empty-vs-error distinction is preserved by HTTP status (200 = part exists, 404 = part missing). Locust's headless `--csv` output captures every failed request with status code, so a CI run that goes red is diagnosable from the CSV alone — no need to replay traffic.
- Redaction constraints: none — no PII or secrets touched. Endpoints are public-read.

## Tasks

- [x] **T01: Add `app/api/services/part_price_aggregation_service.py` with windowed single + batch aggregation primitives** `est:3h`
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
  - Files: `backend/app/api/services/part_price_aggregation_service.py`, `backend/app/api/schemas/part_price_history.py`, `backend/tests/services/test_part_price_aggregation_service.py`
  - Verify: TESTING=true pytest backend/tests/services/test_part_price_aggregation_service.py -n auto --rootdir=backend -q --no-cov

- [x] **T02: Enhance `GET /api/parts/{id}/price-history` with `window` param + retailer-breakdown summary response (legacy shim for old callers)** `est:2h`
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
  - Files: `backend/app/api/endpoints/parts.py`, `backend/tests/api/endpoints/test_parts_price_history.py`, `backend/tests/fixtures/openapi_snapshot.json`
  - Verify: TESTING=true pytest backend/tests/api/endpoints/test_parts_price_history.py backend/tests/api/test_openapi_snapshot.py backend/tests/api/endpoints/test_parts.py -n auto --rootdir=backend -q --no-cov

- [x] **T03: Add `POST /api/parts/price-history` batch summary endpoint (1–100 IDs → min/max/last/trend per part)** `est:2h`
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
  - Files: `backend/app/api/endpoints/parts.py`, `backend/tests/api/endpoints/test_parts_price_history.py`, `backend/tests/fixtures/openapi_snapshot.json`
  - Verify: TESTING=true pytest backend/tests/api/endpoints/test_parts_price_history.py backend/tests/api/test_openapi_snapshot.py -n auto --rootdir=backend -q --no-cov

- [x] **T04: Wire frontend client + types for both new endpoints (`getPartPriceHistorySummary`, `getBatchPriceHistorySummary`)** `est:1h`
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
  - Files: `frontend/src/api/parts.ts`, `frontend/src/api/parts.test.ts`, `frontend/src/types/Api.ts`
  - Verify: cd frontend && npm run type-check && npm run lint && npm test -- --run src/api/parts.test.ts

- [ ] **T05: Add Locust load test + perf-gate script (10× baseline RPS, GET p95 < 200 ms, POST p95 < 500 ms, error rate 0%)** `est:3h`
  Stand up the perf gate that R019 / D004 require. The gate is the falsifiable check that says 'query-time aggregation is fast enough — DON'T open R036 materialization' (or, if it fires, 'open R036 now'). Use Locust (pure-Python, integrates with the existing pytest+uvicorn stack) — NOT k6 (extra binary, JS scenario file, drifts from the Python codebase). The roadmap mentions k6 OR locust; we choose locust to minimize new dependencies.

New files:

**`backend/scripts/perf/locustfile_price_history.py`** — Locust scenario:
- Two `@task` weights — GET (weight=4 — single GET is the dominant frontend call from sparkline rendering) and POST (weight=1 — batch is called once per page load to populate sparkline summaries).
- The GET task picks a random `part_id` from a pool loaded from `backend/.perf-runs/part-id-pool.json` (the runner script generates this pool by querying the DB before the locust run starts).
- The POST task batches 50 random part_ids per call.
- `--users` and `--spawn-rate` derived from baseline: assume current baseline is 1 RPS (very low — pre-launch app); 10× = 10 RPS sustained. For locust this is `--users 50 --spawn-rate 10 --run-time 60s` (50 concurrent users with a 1–2s think time across the two tasks gives ~10 RPS aggregate).
- Use `locust.stats.stats_history` and `events.test_stop` to dump a JSON summary at the end with `p50, p95, p99, max, num_failures` per endpoint.

**`backend/scripts/perf/run_price_history_loadtest.sh`** — bash runner:
- Validates that the backend is running (`curl -fsS http://localhost:8000/health` — exits 1 with a useful message if not).
- Validates that sample data is loaded (queries the DB count of `part_price_history` rows; exits 1 with `Run scripts/populate_sample_data.py first` if zero).
- Generates `part-id-pool.json` from the DB (top 500 parts by observation count — gives the load test a realistic mix instead of one hot row).
- Runs `locust -f backend/scripts/perf/locustfile_price_history.py --headless --users 50 --spawn-rate 10 --run-time 60s --host http://localhost:8000 --csv backend/.perf-runs/locust-<ts>` (timestamp = `date -u +%Y%m%dT%H%M%SZ`).
- Reads the `*_stats.csv` output, extracts p95 for each endpoint, asserts:
  - GET `/parts/<id>/price-history` p95 < 200 ms
  - POST `/parts/price-history` p95 < 500 ms
  - Error rate (failures / total) == 0
- On PASS, writes `backend/.perf-runs/price-history-PASSED-<ts>.json` with the percentile dump and `verdict: PASSED`.
- On FAIL, writes `backend/.perf-runs/price-history-FAILED-<ts>.json` with the percentile dump, `verdict: FAILED`, the failing assertion, and a remediation note: `'Perf gate missed. Open R036 (materialized part_price_summary) per D004 — see .gsd/REQUIREMENTS.md.'` Exit 1.
- On PASS, exit 0. Print the percentile breakdown to stdout in either case.
- Add an OPTIONAL `--csv-fixture <path>` flag that skips locust entirely and parses an existing CSV (used by the pytest gate-on-the-gate in this task to test the assertion logic without running a real load).

**`backend/scripts/perf/README.md`** — short doc: what the perf gate is, what budget it enforces, how to run it (`bash backend/scripts/perf/run_price_history_loadtest.sh` from repo root), where evidence lands (`backend/.perf-runs/`), what to do if it fails (open R036). Cross-reference D004 and R019.

**`backend/.gitignore` (or root `.gitignore`)** — add `backend/.perf-runs/` so transient evidence files don't get committed. Verify with `git check-ignore backend/.perf-runs/anything.json` returning the path.

**`backend/pyproject.toml`** — add `locust>=2.20` to the dev-dependencies group (mirror the existing `pyright`/`black` placement; check whether the project uses `[tool.poetry.group.dev.dependencies]`, `[project.optional-dependencies]`, or another mechanism). Run the project's lockfile-update command and commit the lockfile delta. Verify the install succeeds.

Tests:
- `backend/tests/test_perf_gate_script.py` — single test that asserts the gate script exits non-zero when given a synthetic CSV with p95 above budget. Use `subprocess.run` against the script with `--csv-fixture <fixture-path>`.
- Two CSV fixtures under `backend/tests/fixtures/perf/`: one with passing p95s, one with failing p95s.
- The test only runs in CI when `PERF_GATE_TEST=true` is set (locust install is heavy; default-skip via `pytest.mark.skipif`). For the slice's verify command we run with the env var set.

The load test itself does NOT run in CI by default — it requires a live uvicorn server with sample data, which is a manual `bash backend/scripts/perf/run_price_history_loadtest.sh` invocation. The slice's success criteria require ONE successful run (most recent file under `backend/.perf-runs/` ends in `-PASSED-<ts>.json`), which is recorded as evidence in the slice SUMMARY when the executor runs T05.

FAILURE MODES (Q5):
| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| Locust process | non-zero exit → bash script propagates exit 2 with stderr capture | 60s `--run-time` is the hard cap; locust exits cleanly | n/a (CSV is locust's own format) |
| Backend not running | curl fails → script exits 1 with `Start uvicorn first: cd backend && uvicorn app.main:app --port 8000` | n/a (curl --max-time 5) | n/a |
| Sample data not loaded | DB count = 0 → script exits 1 with `Run python scripts/populate_sample_data.py first` | n/a | n/a |
| Locust CSV parsing | malformed CSV → script exits 3 with the offending line | n/a | exit 3 + offending line |

LOAD PROFILE (Q6):
- Shared resources: this script IS the load — uvicorn worker pool, Postgres connection pool. Run against a local dev server on a separate port if needed.
- Per-operation cost: 1 HTTP request → 1 backend handler → 1–4 SQL round-trips (see T01/T02/T03).
- 10x breakpoint: this is the gate. If p95 misses budget, R036 opens.

NEGATIVE TESTS (Q7):
- Malformed inputs: missing CSV file (script exits 4), CSV with no rows (script exits 5), CSV missing the `Aggregated` row locust always emits (script exits 6 with diag).
- Error paths: synthetic FAIL CSV → script exit 1 + writes FAILED.json + prints remediation pointing at R036. This is exercised by the pytest test.
- Boundary conditions: exactly-at-budget p95 (script treats as PASS; uses `<` strict not `<=`); zero requests in CSV (script exits 5 — locust didn't actually run); 100% error rate (script exits 1 — gate FAIL).
  - Files: `backend/scripts/perf/locustfile_price_history.py`, `backend/scripts/perf/run_price_history_loadtest.sh`, `backend/scripts/perf/README.md`, `backend/tests/test_perf_gate_script.py`, `backend/tests/fixtures/perf/locust_stats_passing.csv`, `backend/tests/fixtures/perf/locust_stats_failing.csv`, `backend/pyproject.toml`, `.gitignore`
  - Verify: PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py -n0 --rootdir=backend -q --no-cov && bash -n backend/scripts/perf/run_price_history_loadtest.sh && python -c 'import locust; print(locust.__version__)'

## Files Likely Touched

- backend/app/api/services/part_price_aggregation_service.py
- backend/app/api/schemas/part_price_history.py
- backend/tests/services/test_part_price_aggregation_service.py
- backend/app/api/endpoints/parts.py
- backend/tests/api/endpoints/test_parts_price_history.py
- backend/tests/fixtures/openapi_snapshot.json
- frontend/src/api/parts.ts
- frontend/src/api/parts.test.ts
- frontend/src/types/Api.ts
- backend/scripts/perf/locustfile_price_history.py
- backend/scripts/perf/run_price_history_loadtest.sh
- backend/scripts/perf/README.md
- backend/tests/test_perf_gate_script.py
- backend/tests/fixtures/perf/locust_stats_passing.csv
- backend/tests/fixtures/perf/locust_stats_failing.csv
- backend/pyproject.toml
- .gitignore
