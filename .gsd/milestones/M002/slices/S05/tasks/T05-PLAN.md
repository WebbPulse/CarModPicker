---
estimated_steps: 44
estimated_files: 8
skills_used: []
---

# T05: Add Locust load test + perf-gate script (10× baseline RPS, GET p95 < 200 ms, POST p95 < 500 ms, error rate 0%)

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

## Inputs

- ``backend/app/api/endpoints/parts.py` — endpoints that get hit by the load test (after T02/T03)`
- ``scripts/populate_sample_data.py` — sample-data seeder the script's preflight check verifies`
- ``backend/pyproject.toml` — dev dependencies block to extend with locust`
- ``.gsd/REQUIREMENTS.md` — R019 (perf gate) and R036 (materialized fallback) referenced in the FAIL output`
- ``.gsd/DECISIONS.md` — D004 referenced in README cross-link`

## Expected Output

- ``backend/scripts/perf/locustfile_price_history.py` — locust scenario file with weighted GET/POST tasks against the new endpoints`
- ``backend/scripts/perf/run_price_history_loadtest.sh` — bash runner that orchestrates preflight, locust run, CSV parse, p95 assertion, evidence-file write`
- ``backend/scripts/perf/README.md` — perf-gate doc cross-referencing D004 and R019`
- ``backend/tests/test_perf_gate_script.py` — pytest gate-on-the-gate that asserts the script exits non-zero on synthetic FAIL CSV`
- ``backend/tests/fixtures/perf/locust_stats_passing.csv` — synthetic PASS fixture`
- ``backend/tests/fixtures/perf/locust_stats_failing.csv` — synthetic FAIL fixture`
- ``backend/pyproject.toml` — locust added to dev dependencies`
- ``.gitignore` — `backend/.perf-runs/` added`

## Verification

PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py -n0 --rootdir=backend -q --no-cov && bash -n backend/scripts/perf/run_price_history_loadtest.sh && python -c 'import locust; print(locust.__version__)'

## Observability Impact

Signals added/changed: every perf-gate run writes a JSON evidence file under `backend/.perf-runs/price-history-{PASSED,FAILED}-<iso8601>.json` containing the percentile dump, parameters used, and verdict. The locust raw CSVs persist alongside under `locust-<ts>_stats.csv` etc. How a future agent inspects this: `ls -lt backend/.perf-runs/` shows the most recent run; `cat backend/.perf-runs/price-history-PASSED-<latest>.json | jq` shows the percentile breakdown. Failure state exposed: a FAILED file's existence IS the failure signal; the file's `remediation` field literally names R036 so the next agent doesn't have to re-derive the decision tree.
