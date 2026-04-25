# S05: Price-history aggregation API + perf gate — UAT

**Milestone:** M002
**Written:** 2026-04-25T19:13:30.874Z

## UAT — S05 Price-history aggregation API + perf gate

This slice opens a data seam (no user-visible surface). UAT is mechanical and can be scripted entirely against a running backend + the existing pytest harness. Three preconditions, six test cases, one optional manual perf-gate run.

### Preconditions

- Backend dev server reachable on `http://localhost:8000`. Start with: `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
- Local Postgres seeded with sample data: `cd backend && python ../scripts/populate_sample_data.py` (must produce `part_price_history` rows; the perf-gate runner refuses to start otherwise).
- Frontend dev server (only for UC-04): `cd frontend && npm run dev` on port 4000 with `/api` proxied to 8000.

### UC-01 — Single-part aggregation: default window, object shape

**Steps:**
1. Pick a part_id with at least one observation: `psql -d carmodpicker -c "SELECT p.id FROM parts p JOIN part_listings pl ON pl.part_id = p.id JOIN part_price_history pph ON pph.part_listing_id = pl.id LIMIT 1;"`
2. `curl -s "http://localhost:8000/api/parts/<id>/price-history" | jq`

**Expected:**
- HTTP 200.
- Response is an OBJECT (not an array) with keys: `summary`, `retailers`, `history`, `window`.
- `window` == `"90d"` (default).
- `summary` has `min_cents`, `max_cents`, `last_cents`, `last_observed_at`, `trend` (one of `up`/`down`/`flat`), `observation_count`.
- `retailers` is an array sorted by `retailer_name` ASC; each entry has `retailer_id`, `retailer_name`, `min_cents`, `max_cents`, `last_cents`, `last_observed_at`, `observation_count`.
- `history` is an array of `PartPriceHistoryReadWithRetailer` rows sorted by `observed_at` DESC.

**Edge cases:**
- Part with zero observations: `summary.observation_count == 0`, `summary.min_cents == null`, `summary.trend == "flat"`, `retailers == []`, `history == []`, status 200.
- Random UUID (no such part): status 404.

### UC-02 — Single-part aggregation: window param + retailer filter + invalid window

**Steps:**
1. Window param: `curl -s "http://localhost:8000/api/parts/<id>/price-history?window=30d" | jq '.summary.observation_count, (.history | length)'` → expect both equal and consistent with rows in the last 30 days only.
2. `window=all`: `curl -s "http://localhost:8000/api/parts/<id>/price-history?window=all" | jq '.history | length'` → all-time count.
3. Retailer filter: `curl -s "http://localhost:8000/api/parts/<id>/price-history?retailer_id=<rid>" | jq '.retailers | length, .summary.observation_count'` → exactly 1 retailer entry; summary recomputed from filtered observations only (NOT cross-retailer aggregate).
4. Invalid window: `curl -s -o /dev/null -w '%{http_code}\n' "http://localhost:8000/api/parts/<id>/price-history?window=99x"` → **422**, response body `error_code == "INVALID_WINDOW"`, `details.allowed` lists `30d, 90d, 180d, 1y, all`.

### UC-03 — Single-part aggregation: legacy=true shim returns array shape

**Steps:**
1. `curl -s "http://localhost:8000/api/parts/<id>/price-history?legacy=true" | jq 'type'`

**Expected:**
- HTTP 200.
- `type == "array"` (NOT object).
- Each element matches the legacy `PartPriceHistoryReadWithRetailer` shape (no `summary`/`retailers`/`window` keys at top level).
- Combining `legacy=true` with `retailer_id=<rid>` filters the array to that retailer only.

This guard regresses on the contract Chrome extension and existing pages depend on. The shim is removed in S13.

### UC-04 — Batch endpoint: 1, 50, 100 IDs + boundary 422s

**Steps:**
1. **Batch of 1 with default window:** `curl -s -X POST -H 'Content-Type: application/json' -d '{"part_ids":["<id>"]}' http://localhost:8000/api/parts/price-history | jq`
   - Expect 200; `summaries` has exactly 1 key; `requested_count == 1`; `window == "90d"`; that key's value has `observation_count > 0` if seeded; if not, has the empty-summary shape.
2. **Batch of 50:** generate 50 part_ids and POST; expect 200, 50 summaries entries, query log shows ≤6 SELECTs (per the no-N+1 contract).
3. **Empty list:** POST `{"part_ids":[]}` → **422** (Pydantic min_length).
4. **Over-limit:** generate 101 UUIDs and POST → **422** with the limit named in the error.
5. **Unknown UUIDs:** POST 2 random UUIDs → **200** (not 404), `summaries` has 2 entries both with `observation_count == 0`. Batch endpoints intentionally never 404 on missing IDs.
6. **Custom window:** POST `{"part_ids":["<id>"], "window":"30d"}` → response `window == "30d"` and aggregates filter correctly.
7. **Invalid window:** POST `{"part_ids":["<id>"], "window":"xyz"}` → **422**, error_code `INVALID_WINDOW` or Pydantic `VALIDATION_ERROR` (the schema's Literal rejects the string before the handler runs; either error_code is acceptable).

### UC-05 — Link-group dedup parity

**Steps:**
1. Identify a canonical part `A` with at least one duplicate `B` linked via `canonical_part_id`. Both must have listings + history rows: `psql -c "SELECT p.id, p.canonical_part_id FROM parts p WHERE p.canonical_part_id IS NOT NULL LIMIT 1;"` → returns `B.id` and `A.id` (its canonical).
2. **Single GET:** `curl -s "http://localhost:8000/api/parts/<A.id>/price-history" | jq '.summary.observation_count'`
3. **Batch POST:** `curl -s -X POST -H 'Content-Type: application/json' -d '{"part_ids":["<A.id>","<B.id>"]}' http://localhost:8000/api/parts/price-history | jq '.summaries'`

**Expected:**
- UC-05.2 summary count includes BOTH A's and B's listings' history (canonical aggregates the link group).
- UC-05.3 returns 2 summaries entries; both reflect the same canonical aggregate (no double-counting). The duplicate's entry mirrors the canonical because `link_group_part_ids` resolves both to the same group.

### UC-06 — Frontend typed-client surface

**Steps (in `frontend/`):**
1. `npm test -- --run src/api/parts.test.ts` → 26 passed.
2. `npm run type-check` → exit 0.
3. (Optional manual smoke against running backend.) Open browser console at `http://localhost:4000`, evaluate:
```js
import('./src/api/parts').then(m => m.partsApi.getPartPriceHistorySummary('<id>', { window: '30d' })).then(console.log);
import('./src/api/parts').then(m => m.partsApi.getBatchPriceHistorySummary({ part_ids: ['<id>'], window: '90d' })).then(console.log);
import('./src/api/parts').then(m => m.partsApi.getPartPriceHistory('<id>')).then(r => console.log(Array.isArray(r), r));
```

**Expected:**
- `getPartPriceHistorySummary` resolves with the object shape (`summary`/`retailers`/`history`/`window`).
- `getBatchPriceHistorySummary` resolves with `{summaries, window, requested_count, found_count}`.
- `getPartPriceHistory` still resolves to an ARRAY (`Array.isArray(r) === true`) — the legacy=true shim is honoured.

### UC-07 — Perf gate (manual, optional, R019 evidence)

This is the live load-test the slice plan deferred from CI. It produces the canonical evidence file under `backend/.perf-runs/` that S13 milestone verification re-reads.

**Steps:**
1. With backend running and sample data loaded, from repo root: `bash backend/scripts/perf/run_price_history_loadtest.sh`
2. Wait ~75s (60s locust run + pool generation + assertion).
3. Inspect the most recent file under `backend/.perf-runs/`.

**Expected (PASS path):**
- Exit code 0.
- Most recent file matches `price-history-PASSED-<iso8601>.json` and contains the percentile dump with `verdict: PASSED`.
- GET `/parts/<id>/price-history` p95 < 200 ms; POST `/parts/price-history` p95 < 500 ms; error rate == 0.
- R019 can be promoted to validated; R036 stays unopened.

**Expected (FAIL path — gate fires):**
- Exit code 1.
- Most recent file matches `price-history-FAILED-<iso8601>.json` with `verdict: FAILED`, the failing assertion, and the canonical remediation string `"Open R036 (materialized part_price_summary) per D004 — see .gsd/REQUIREMENTS.md."`.
- Stdout prints the percentile breakdown and the remediation pointer.
- Action: open R036 per D004 and start the materialization slice.

### UC-08 — Negative path: gate-on-the-gate (already in CI)

`PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py -n0 -q --no-cov` → **6 passed**. Exercises both synthetic CSV fixtures (passing + failing) plus 4 negative paths (missing CSV exit 4, empty CSV exit 5, missing endpoint row exit 6, runner `--csv-fixture` end-to-end). This proves the gate's failure semantics are pinned and won't drift when the parser is edited later.

### Acceptance summary

- UC-01..UC-06 are mechanical and re-runnable on demand against any seeded local stack — no human judgment required.
- UC-07 is the only manually-triggered case; deferred per slice plan (live uvicorn + sample data not available in CI). PASS evidence promotes R019; FAIL evidence opens R036.
- UC-08 already passes in the slice's verify command (proven during T05).

UAT is satisfied when UC-01..UC-06 + UC-08 pass against a freshly checked-out tip of S05; UC-07 is queued for the next manual perf-gate window before milestone close.
