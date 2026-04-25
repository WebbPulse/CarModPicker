---
id: S05
parent: M002
milestone: M002
provides:
  - ["backend/app/api/services/part_price_aggregation_service.py — pure-read aggregation service with aggregate_single_part, aggregate_batch, parse_window, apply_retailer_filter; canonical-coalesce dedup; 4 SELECTs per batch independent of input size", "backend/app/api/endpoints/parts.py — GET /api/parts/{id}/price-history rewritten to return PriceHistorySinglePartResponse (summary + retailers + history + window) with optional retailer_id and legacy=true shim; POST /api/parts/price-history (1-100 IDs)", "backend/app/api/schemas/part_price_history.py — PriceTrend/PriceWindow literals, PriceHistorySummary, RetailerPriceBreakdown, PriceHistorySinglePartResponse, PriceHistoryBatchSummaryItem, PriceHistoryBatchRequest (Pydantic min_length=1/max_length=100), PriceHistoryBatchResponse", "frontend/src/types/Api.ts — TS interfaces for the new aggregation shapes", "frontend/src/api/parts.ts — getPartPriceHistorySummary, getBatchPriceHistorySummary; getPartPriceHistory migrated to legacy=true shim", "backend/scripts/perf/locustfile_price_history.py — Locust scenario (weight=4 GET / weight=1 POST) with part_id pool", "backend/scripts/perf/run_price_history_loadtest.sh — bash orchestrator with live + --csv-fixture modes", "backend/scripts/perf/_parse_locust_csv.py — pure-Python parser/assertion module with locked exit-code contract (0/1/3/4/5/6)", "backend/.perf-runs/ — gitignored evidence directory (price-history-{PASSED,FAILED}-<iso8601>.json)", "Structured INFO log per aggregation request: 'price_history_aggregation: endpoint=<single|batch> part_count=N window=<w> link_groups_resolved=N rows_scanned=N elapsed_ms=N'"]
requires:
  - slice: M001 (existing schema)
    provides: PartPriceHistory time-series, PartListing (part_id, retailer_id) uniqueness, Retailer.name, link_group_part_ids canonical resolver, populate_sample_data.py seed
affects:
  - ["S06: consumes typed frontend client (getPartPriceHistorySummary, getBatchPriceHistorySummary) for sparkline + per-part detail view", "S07: reuses part_price_aggregation_service (uncapped) for alert threshold evaluation in observation-write hook", "S13: removes the legacy=true shim once all callers migrated; promotes R019 to validated after manual perf-gate run", "Frontend Chrome extension + existing pages: kept on legacy array shape via getPartPriceHistory shim — no migration required this slice"]
key_files:
  - ["backend/app/api/services/part_price_aggregation_service.py", "backend/app/api/endpoints/parts.py", "backend/app/api/schemas/part_price_history.py", "backend/tests/services/test_part_price_aggregation_service.py", "backend/tests/api/endpoints/test_parts_price_history.py", "backend/tests/fixtures/openapi_snapshot.json", "frontend/src/types/Api.ts", "frontend/src/api/parts.ts", "frontend/src/api/parts.test.ts", "backend/scripts/perf/locustfile_price_history.py", "backend/scripts/perf/run_price_history_loadtest.sh", "backend/scripts/perf/_parse_locust_csv.py", "backend/scripts/perf/README.md", "backend/tests/test_perf_gate_script.py", "backend/tests/fixtures/perf/locust_stats_passing.csv", "backend/tests/fixtures/perf/locust_stats_failing.csv", "backend/requirements.txt", ".gitignore"]
key_decisions:
  - ["aggregate_single_part computes last_cents/last_observed_at/trend from a single ordered observation SELECT instead of a row_number() OVER subquery — keeps the round-trip budget at 4 SELECTs for batch and avoids dialect-specific window-function quirks; the same SELECT also feeds trend computation", "Trend threshold uses slope × (n-1) vs ±1% of mean (total expected drift across window), not raw slope vs 1%, so the verdict reflects window-level change rather than per-step delta", "Service does NOT enforce a batch cap — that lives at the endpoint layer (Pydantic min_length=1/max_length=100) so the service is reusable from S07 alert evaluation without arbitrary limits", "Dual-shape GET via Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]] + response_model=None — FastAPI auto-encodes both via jsonable_encoder; legacy=true branches to private _legacy_get_part_price_history helper running the pre-rewrite query verbatim", "INVALID_WINDOW 422 detail nested under 'details' (not as sibling of error_code) to fit middleware/error_handler reshape contract — middleware drops unknown sibling keys (MEM048/MEM051)", "found_count derived endpoint-side from observation_count > 0 rather than tracked in the service — keeps aggregate_batch interface unchanged and avoids drift", "Locust 2.43.4 added to backend/requirements.txt (not pyproject.toml, which has no [project.optional-dependencies] block) with dev-only comment", "Perf-gate harness split bash orchestrator + pure-Python parser/assertion module — testability without bash dependency in CI; --csv-fixture flag bypasses locust entirely", "Locked parser exit-code contract (0=PASS, 1=FAIL, 3=malformed, 4=missing, 5=empty, 6=missing-row) with one test per code — future edits cannot silently change failure semantics", "PriceHistoryBatchSummaryItem declared as 'type X = PriceHistorySummary' alias instead of empty-extending interface to satisfy @typescript-eslint/no-empty-object-type"]
patterns_established:
  - ["Canonical-coalesce SQL expression as single canonicalization point in aggregation queries: func.coalesce(DBPart.canonical_part_id, DBPart.id) — duplicates count toward canonical without per-row Python", "Endpoint-vs-service split for batch caps: service stays uncapped for downstream reuse (S07 alert eval), endpoint enforces 1-100 via Pydantic min_length/max_length", "Dual-shape route via Union[New, Legacy] + legacy=true query-param shim + private _legacy_* helper running pre-rewrite query verbatim — transition window for caller migration; remove in audit slice", "Trend classification via slope × (n-1) (total expected drift) vs ±1% of mean — captures window-level change, not per-step delta; <2 obs or zero mean short-circuit to flat", "Perf-gate harness split bash orchestrator + pure-Python parser/assertion module — pytest subprocesses parser directly via --csv-fixture without bash or locust import", "Locked exit-code contract for gate parsers (0=PASS, 1=FAIL, 3=malformed, 4=missing, 5=empty, 6=missing-row), one test per code, FAILED.json includes canonical remediation string", "Backend dev-only Python deps live in backend/requirements.txt with inline dev-only comment (no [project.optional-dependencies] block in this project)", "When TS interface would just extend with no new fields, declare 'type X = Y' alias to avoid @typescript-eslint/no-empty-object-type"]
observability_surfaces:
  - ["Structured INFO log per non-legacy aggregation request: 'price_history_aggregation: endpoint=<single|batch> part_count=N window=<w> link_groups_resolved=N rows_scanned=N elapsed_ms=N' — single source of truth for tracing slow queries; same fields for both endpoints", "Perf-gate evidence files at backend/.perf-runs/price-history-{PASSED,FAILED}-<iso8601>.json — most recent file is what S13 re-reads for milestone verification; FAILED.json includes the canonical remediation string pointing at R036/D004", "OpenAPI snapshot at backend/tests/fixtures/openapi_snapshot.json — drift-guard for endpoint shape regressions (test at backend/tests/test_openapi_snapshot.py — note: NO 'api/' segment despite plan drift)", "Pytest query_counter fixture — pinned at ≤5 SELECTs for 10-id service batch and ≤6 for 50-id endpoint batch; regression flags any future N+1 introduction"]
drill_down_paths:
  - [".gsd/milestones/M002/slices/S05/tasks/T01-SUMMARY.md", ".gsd/milestones/M002/slices/S05/tasks/T02-SUMMARY.md", ".gsd/milestones/M002/slices/S05/tasks/T03-SUMMARY.md", ".gsd/milestones/M002/slices/S05/tasks/T04-SUMMARY.md", ".gsd/milestones/M002/slices/S05/tasks/T05-SUMMARY.md", ".gsd/milestones/M002/slices/S05/S05-PLAN.md", "backend/app/api/services/part_price_aggregation_service.py", "backend/app/api/endpoints/parts.py", "backend/scripts/perf/README.md"]
duration: ""
verification_result: passed
completed_at: 2026-04-25T19:13:30.874Z
blocker_discovered: false
---

# S05: Price-history aggregation API + perf gate

**Shipped query-time price-history aggregation as two read endpoints (single GET with retailer breakdown + batch POST for 1-100 IDs) on a pure-read service, wired typed frontend clients, and locked a Locust perf gate that R019 will fire to keep R036 (materialization) shut.**

## What Happened

S05 opens the read seam over the price-history write path that's been live since M001. Five tasks landed across backend service + endpoints, frontend client, and a perf-gate harness — 89 tests green at slice close (57 backend + 6 perf-gate + 26 frontend), no regressions on neighbouring suites.

**T01 — service layer.** Stood up `backend/app/api/services/part_price_aggregation_service.py` exporting `parse_window`, `aggregate_single_part`, `aggregate_batch`, and `apply_retailer_filter`. The window contract translates the 5 literals (30d/90d/180d/1y/all) into a `since: datetime | None` lower bound — anything else raises `ValueError`. Both aggregation entry points respect the canonical link group: the single-part path resolves siblings via `link_group_part_ids` and joins history → listing → retailer in one query; the batch path bulk-resolves canonical mapping in two SELECTs, then runs two grouped aggregation SELECTs keyed by `func.coalesce(DBPart.canonical_part_id, DBPart.id)` — the same canonicalization expression `read_parts_with_votes::min_price_subq` already uses. That keeps per-batch cost independent of input size: 4 SELECTs total. Trend (up/down/flat) is computed from a hand-rolled linear-regression slope over chronologically-ordered prices with the verdict bar set at total-expected-drift (slope × (n−1)) vs ±1% of mean — captures what actually changed across the window, not a tiny per-step delta. The service deliberately enforces no batch cap so S07 alert evaluation can reuse it freely; the cap lives at the endpoint layer. 11 unit tests green; query counter pinned at ≤5 SELECTs for a 10-id batch.

**T02 — single GET rewrite.** Replaced the pre-S05 list-returning `GET /parts/{id}/price-history` handler with one that delegates to `aggregate_single_part` and returns `PriceHistorySinglePartResponse` (summary + retailers + history + window). Added optional `window` (default 90d, 5 literals), kept `retailer_id` (now applied via `apply_retailer_filter` so it recomputes summary from the filtered slice rather than the cross-retailer aggregate), and added a `legacy=true` shim that runs the pre-rewrite query path verbatim via a private `_legacy_get_part_price_history` helper — keeps Chrome extension and any out-of-band callers on the old contract until S13 audits all callers. The dual-shape route uses `Union[PriceHistorySinglePartResponse, List[PartPriceHistoryReadWithRetailer]]` as the return type with `response_model=None` so FastAPI auto-encodes both via `jsonable_encoder`. One structured INFO log per non-legacy request: `price_history_aggregation: endpoint=single part_count=1 window=<...> link_groups_resolved=N rows_scanned=N elapsed_ms=N`, timed via `time.perf_counter`. Discovered MEM048/MEM051: `app.api.middleware.error_handler.handle_http_exception` reshapes `HTTPException(detail=dict)` and DROPS unknown sibling keys — fixed the 422 INVALID_WINDOW response by nesting the allowed-windows list under `details`. OpenAPI snapshot regenerated. 8 endpoint tests + 1 OpenAPI snapshot test green.

**T03 — batch POST.** New `POST /api/parts/price-history` handler placed before the `BaseEndpointRouter` instantiation for route-precedence. Pydantic enforces 1-100 IDs (`min_length=1, max_length=100` on `part_ids`), so out-of-bounds requests auto-422 with structured errors. The handler probes `parse_window` to surface a structured INVALID_WINDOW 422 if a caller bypasses the schema, calls `aggregate_batch`, and returns `PriceHistoryBatchResponse{summaries, window, requested_count, found_count}` where `found_count` is derived endpoint-side from `observation_count > 0` (keeps the service interface unchanged). Same INFO log shape as T02. 10 batch test cases including a 50-id query-counter test asserting ≤6 SELECTs; surfaced MEM049/MEM052: materialize ORM attribute reads BEFORE entering `query_counter()` — accessing `.id` on expired ORM instances after `db_session.commit()` triggers per-instance lazy-load refreshes (saw 104 SELECTs vs the expected 4). Captured the lesson and the fix together.

**T04 — frontend client + types.** Added `PriceTrend`, `PriceHistorySummary`, `RetailerPriceBreakdown`, `PriceHistorySinglePartResponse`, `PriceHistoryBatchSummaryItem` (declared as `type` alias not `interface extends` to avoid `@typescript-eslint/no-empty-object-type`), `PriceHistoryBatchRequest`, and `PriceHistoryBatchResponse` in `frontend/src/types/Api.ts`. In `frontend/src/api/parts.ts` migrated existing `getPartPriceHistory` to forward `legacy: true` (preserves array-shape contract for Chrome extension + existing pages), added `getPartPriceHistorySummary(partId, { window?, retailer_id? })` for the new object shape, and `getBatchPriceHistorySummary(body)` for the batch endpoint. 26 vitest tests green (4 new + 2 modified shim regression-guards). Type-check exits 0; lint baseline unchanged from main (108 pre-existing errors in unrelated files, none introduced).

**T05 — perf gate harness.** Stood up the price-history perf gate that R019/D004 require — the falsifiable check that says "query-time aggregation is fast enough; don't open R036 (materialized part_price_summary)." Implemented as four files under `backend/scripts/perf/`: a Locust scenario (`locustfile_price_history.py` with weight=4 GET / weight=1 POST tasks, part_id pool loaded from `backend/.perf-runs/part-id-pool.json` on `events.test_start`), a bash orchestrator (`run_price_history_loadtest.sh` with live mode for real loads + `--csv-fixture <path>` mode that bypasses locust for tests), a pure-Python parser (`_parse_locust_csv.py` with locked exit-code contract: 0=PASS, 1=FAIL, 3=malformed, 4=missing, 5=empty, 6=missing-row), and a README cross-referencing D004 and R019. The split between bash orchestrator and Python parser is deliberate (MEM050/MEM053): pytest can subprocess the parser directly without invoking bash or importing locust, and the same `--csv-fixture` flag drives both flows. Six gate-on-the-gate pytest cases (PERF_GATE_TEST=true gated) cover PASS/FAIL/missing/empty/malformed/runner end-to-end via two synthetic CSV fixtures. FAILED.json includes the canonical remediation string `"Open R036 (materialized part_price_summary) per D004"` so future agents don't re-derive the decision tree. Locust 2.43.4 added to `backend/requirements.txt` with a dev-only comment (no `[project.optional-dependencies]` block exists in this project). The live 10× load run is intentionally NOT run in CI — it requires a uvicorn server with sample data and is a manual `bash backend/scripts/perf/run_price_history_loadtest.sh` invocation. Evidence dir `backend/.perf-runs/` is gitignored.

**Cross-cutting decisions and patterns.**
- Canonical-coalesce expression as the single canonicalization point in aggregation SQL — duplicates count toward the canonical's history without per-row Python.
- Endpoint-vs-service split for batch caps — service stays uncapped for S07 reuse, endpoint enforces 1-100.
- Dual-shape route via `Union` + `legacy=true` shim — transition window for caller migration, removed in S13.
- Bash/Python split for perf-gate harness — testability without bash dependency in CI.
- Trend computed via total-expected-drift across window, not per-step slope.

**What S05 does NOT ship.** Zero user-visible surfaces — this slice opens the data seam only. S06 consumes the typed client to render sparklines + per-part detail view; S07 reuses `part_price_aggregation_service` for alert threshold evaluation. The live 10× perf gate run is the only deferred verification — R019 stays active until that lands; R007 (the read-endpoint capability requirement) is now validated by code + tests. R036 (materialized `part_price_summary`) stays unopened unless and until R019's live run misses budget.

## Verification

**Slice-level test gate** ran cleanly:

1. `TESTING=true pytest backend/tests/services/test_part_price_aggregation_service.py backend/tests/api/endpoints/test_parts_price_history.py backend/tests/test_openapi_snapshot.py backend/tests/api/endpoints/test_parts.py -n auto --rootdir=backend -q --no-cov` → **57 passed in 5.99s** (11 service unit tests + 18 price-history endpoint tests [8 GET from T02 + 10 POST from T03] + 1 OpenAPI snapshot + 27 pre-existing parts endpoint regression tests).

2. `PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py -n0 --rootdir=backend -q --no-cov` → **6 passed in 0.20s**. Covers PASS fixture → exit 0 + PASSED.json; FAIL fixture → exit 1 + FAILED.json with R036/D004 remediation string + GET/POST/error-rate failures all flagged; missing CSV → exit 4; empty CSV → exit 5; CSV missing endpoint row → exit 6; runner end-to-end via `--csv-fixture`.

3. `cd frontend && npm test -- --run src/api/parts.test.ts` → **26/26 passed in 591ms**. Covers `getPartPriceHistorySummary` (window forwarding, retailer_id forwarding), `getBatchPriceHistorySummary` (POST body + URL), and the regression guard that `getPartPriceHistory` now forwards `legacy: true` to preserve the array-shape contract.

**Per-task verification** (recorded in task summaries, all four tasks `verification_result: passed`):
- T01: 11/11 service tests; query counter ≤5 SELECTs for 10-id batch.
- T02: 36/36 (endpoint + snapshot + parts regression); MEM048 captured for the middleware-reshape gotcha.
- T03: 46/46 (endpoint + snapshot regression); 50-id query counter pinned at 4 SELECTs (well under ≤6 budget); MEM049 captured for the ORM-after-commit query-counter pollution.
- T04: type-check exit 0; lint baseline unchanged from main (108 pre-existing, none in S05 files); 26/26 vitest cases.
- T05: 6 perf-gate tests + bash syntax check + locust import check; parser sanity-run against passing fixture wrote PASSED.json with expected percentile breakdown; `git check-ignore backend/.perf-runs/anything.json` confirms gitignore wiring; no regression on T01-T04 suites (29 passed in re-run).

**Threat surface verification** (matches slice-plan threat model):
- Pydantic `max_length=100` on `part_ids` → FastAPI auto-422 with structured error before handler runs (covered by `test_post_batch_price_history_too_many_ids_returns_422`).
- Existing rate-limiter middleware covers the new path automatically (registered in `app/main.py` for `/api` prefix).
- All SQL parameterized via SQLAlchemy ORM (no raw f-string SQL anywhere); window literal whitelisted via `parse_window` so it can never reach SQL as user-controlled string.
- Public-read posture matches the existing `/{part_id}/price-history` endpoint — no auth scope drift, no PII surfaces.

**Deferred to manual invocation** (intentional, per slice plan):
- Live 10× Locust load run against a uvicorn server with `populate_sample_data.py` seed. R019 stays `active` until that runs; R036 stays unopened. Evidence will land as `backend/.perf-runs/price-history-PASSED-<iso8601>.json` per the locked filename contract.

## Requirements Advanced

- R019 — Perf-gate infrastructure landed: Locust scenario, bash orchestrator, pure-Python parser with locked exit-code contract, 6-case gate-on-the-gate pytest suite (all green). FAILED.json carries canonical R036/D004 remediation pointer. Live 10× run is intentionally manual (uvicorn + sample data not in CI scope) — R019 stays active until that runs; promotion to validated happens when backend/.perf-runs/ holds a fresh PASSED-<iso8601>.json.
- R008 — Backend aggregation API + frontend typed client surface (getPartPriceHistorySummary, getBatchPriceHistorySummary) are now in place — S06 can render sparklines + delta lines without re-deriving response shapes. R008 remains active until S06 ships the user-visible UI.
- R009 — Per-part detail view's API substrate (retailer breakdowns, listing-level history, summary with last_observed_at for stale caveats) shipped — S06 consumes these for the click-through detail page.
- R010 — aggregate_batch is uncapped at the service layer (cap lives at endpoint) so S07 alert threshold evaluation can reuse the same primitive without arbitrary batch limits.

## Requirements Validated

- R007 — GET /api/parts/{id}/price-history returns PriceHistorySinglePartResponse (summary + retailers + history) with window param + retailer filter + legacy=true list-shape shim; POST /api/parts/price-history accepts 1-100 part_ids → batch min/max/last/trend with link-group dedup; aggregation lives in app/api/services/part_price_aggregation_service.py (pure-read, canonical-coalesce expression, 4-SELECT batch budget); 18 endpoint tests + 11 service tests + OpenAPI snapshot test green; frontend client (getPartPriceHistorySummary + getBatchPriceHistorySummary) wired with TS types; 26 vitest cases green

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

T02/T03/T05 each surfaced the same minor plan drift: the OpenAPI snapshot test path is `backend/tests/test_openapi_snapshot.py` (no `api/` segment), not `backend/tests/api/test_openapi_snapshot.py` as the plan references — pytest exits 5 (no tests collected) on the wrong path instead of failing loudly. Captured as MEM058 (gotcha). T05 also adapted the dev-dep mechanism: plan said `backend/pyproject.toml` but this project has no `[project.optional-dependencies]` block; locust went into `backend/requirements.txt` with a dev-only comment instead. T04 declared `PriceHistoryBatchSummaryItem` as `type` alias (not empty-extending interface) to satisfy `@typescript-eslint/no-empty-object-type`. None of these changed slice scope.

## Known Limitations

The live 10× Locust load test against a uvicorn server with `populate_sample_data.py` seed has NOT been run in this slice — by design, per the slice plan ("load test does NOT run in CI by default"). The harness is fully wired and exercised via the gate-on-the-gate pytest suite, but R019 stays `active` until a manual `bash backend/scripts/perf/run_price_history_loadtest.sh` produces a fresh `backend/.perf-runs/price-history-PASSED-<iso8601>.json`. Until then, R036 (materialized `part_price_summary`) stays unopened on the optimistic assumption that query-time aggregation holds — this is D004's bet, and S05's evidence doesn't yet falsify it. S13 milestone verification will require the live run to ship.

## Follow-ups

- Manual perf-gate run before S13 milestone close: `bash backend/scripts/perf/run_price_history_loadtest.sh` against a uvicorn server with sample data; promote R019 to validated when PASSED.json lands; open R036 if it FAILs.
- S13 audits all callers of GET /api/parts/{id}/price-history and removes the `legacy=true` shim + private `_legacy_get_part_price_history` helper.
- The structured INFO log `price_history_aggregation: ...` emits to stderr at INFO level — once the slice is in production it's a candidate for a CloudWatch metric filter (count + p95 of `elapsed_ms`) so we can see real-traffic latency vs the lab gate. Nice-to-have, not blocking.

## Files Created/Modified

- `backend/app/api/services/part_price_aggregation_service.py` — NEW — pure-read aggregation service: parse_window, aggregate_single_part, aggregate_batch, apply_retailer_filter; canonical-coalesce dedup; 4-SELECT batch budget; trend via total expected drift
- `backend/app/api/endpoints/parts.py` — GET /parts/{id}/price-history rewritten to return PriceHistorySinglePartResponse (with retailer_id filter + legacy=true shim); NEW POST /parts/price-history (1-100 IDs); structured INFO logs on both
- `backend/app/api/schemas/part_price_history.py` — Added PriceTrend, PriceWindow, ALLOWED_WINDOWS, PriceHistorySummary, RetailerPriceBreakdown, PriceHistorySinglePartResponse, PriceHistoryBatchSummaryItem, PriceHistoryBatchRequest, PriceHistoryBatchResponse
- `backend/tests/services/test_part_price_aggregation_service.py` — NEW — 11 unit tests covering single-part basic + window filtering + link group + empty + trend up/down/flat + invalid window; batch entry-per-id + canonical dedup + 10-id query counter ≤5 SELECTs
- `backend/tests/api/endpoints/test_parts_price_history.py` — NEW — 18 endpoint tests (8 GET from T02 + 10 POST from T03) including default-window object shape, window filtering, retailer filter, invalid window 422, legacy=true list shape, link group, batch shape/empty/oversize/unknown-IDs, 50-id query counter ≤6 SELECTs
- `backend/tests/fixtures/openapi_snapshot.json` — Regenerated for the new endpoint shapes (single GET object response + new batch POST)
- `backend/tests/test_part_canonical_read_paths.py` — Updated test_price_history_aggregates_across_link_group to read from new object shape (internal regression test, not an out-of-band caller)
- `frontend/src/types/Api.ts` — Added PriceTrend, PriceHistorySummary, RetailerPriceBreakdown, PriceHistorySinglePartResponse, PriceHistoryBatchSummaryItem (type alias), PriceHistoryBatchRequest, PriceHistoryBatchResponse
- `frontend/src/api/parts.ts` — Migrated getPartPriceHistory to legacy=true shim; added getPartPriceHistorySummary, getBatchPriceHistorySummary
- `frontend/src/api/parts.test.ts` — Added 4 new tests + modified 2 (legacy=true regression guards); 26 total
- `backend/scripts/perf/locustfile_price_history.py` — NEW — Locust scenario (weight=4 GET / weight=1 POST) with part_id pool loaded from .perf-runs/part-id-pool.json on test_start
- `backend/scripts/perf/run_price_history_loadtest.sh` — NEW — bash orchestrator with live + --csv-fixture modes; preflight curl /health + DB row count; pool generation; locust headless 50 users/10 spawn-rate/60s; shells out to parser
- `backend/scripts/perf/_parse_locust_csv.py` — NEW — pure-Python parser/assertion module; locked exit-code contract; writes price-history-{PASSED,FAILED}-<iso8601>.json with FAILED.json including R036/D004 remediation string
- `backend/scripts/perf/README.md` — NEW — perf-gate doc cross-referencing D004 and R019; how to run, where evidence lands, what to do on FAIL
- `backend/tests/test_perf_gate_script.py` — NEW — 6 gate-on-the-gate cases (PERF_GATE_TEST gated): PASS fixture, FAIL fixture, missing CSV, empty CSV, missing endpoint row, runner end-to-end
- `backend/tests/fixtures/perf/locust_stats_passing.csv` — NEW — synthetic locust CSV with GET p95=120ms, POST p95=300ms, 0 failures (under budget)
- `backend/tests/fixtures/perf/locust_stats_failing.csv` — NEW — synthetic locust CSV with GET p95=350ms, POST p95=600ms, 15 failures (over budget)
- `backend/requirements.txt` — Added locust>=2.20 with dev-only comment (resolved to 2.43.4)
- `.gitignore` — Added backend/.perf-runs/ to gitignore
- `.gsd/PROJECT.md` — Marked S05 complete in milestone sequence with one-line summary
