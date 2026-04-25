---
id: T05
parent: S05
milestone: M002
key_files:
  - backend/scripts/perf/locustfile_price_history.py
  - backend/scripts/perf/run_price_history_loadtest.sh
  - backend/scripts/perf/_parse_locust_csv.py
  - backend/scripts/perf/README.md
  - backend/tests/test_perf_gate_script.py
  - backend/tests/fixtures/perf/locust_stats_passing.csv
  - backend/tests/fixtures/perf/locust_stats_failing.csv
  - backend/requirements.txt
  - .gitignore
key_decisions:
  - Added locust to backend/requirements.txt (line ~80) instead of backend/pyproject.toml as the plan suggested — this project doesn't use a [project.optional-dependencies] block; requirements.txt is the only dep manifest. Documented in the requirements.txt comment that locust is dev-only.
  - Split the perf gate into a bash orchestrator (preflight, locust invocation, evidence-dir mgmt) and a Python parser/assertion module (CSV → p95 check → evidence-file write). The split exists specifically so the pytest gate-on-the-gate can subprocess the parser directly without bash, and so the bash --csv-fixture flag can bypass locust entirely. Captured as MEM050.
  - Locked the parser exit-code contract (0/1/3/4/5/6) and pinned every code with a dedicated test case so future edits to the parser can't silently change the gate's failure semantics.
duration: 
verification_result: passed
completed_at: 2026-04-25T19:06:23.991Z
blocker_discovered: false
---

# T05: Add Locust load test + perf-gate runner with split bash/Python design and 6-case pytest gate-on-the-gate that exercises PASS/FAIL/missing/empty/malformed paths via --csv-fixture

**Add Locust load test + perf-gate runner with split bash/Python design and 6-case pytest gate-on-the-gate that exercises PASS/FAIL/missing/empty/malformed paths via --csv-fixture**

## What Happened

Stood up the price-history perf gate that R019 / D004 require — the falsifiable check that says "query-time aggregation is fast enough; don't open R036 (materialized part_price_summary)." Implemented as four files under backend/scripts/perf/ plus a pytest gate-on-the-gate.

**Locust scenario** (`locustfile_price_history.py`): `PriceHistoryUser` with two weighted tasks — GET (weight=4) hits `/api/parts/{id}/price-history?window=90d` with a random part_id sampled from a pool, POST (weight=1) hits `/api/parts/price-history` with 50 random IDs per call. Pool is loaded from `backend/.perf-runs/part-id-pool.json` once on `events.test_start` so the per-process load happens before any user spawns. `name=` arg on each request groups all per-id calls under one stats row so the wrapper script can find a stable label (otherwise locust would split the sample one-row-per-UUID).

**Orchestrator** (`run_price_history_loadtest.sh`): Bash runner with two modes. Live mode: `curl /health` preflight → inline Python block to query top-500 parts by observation count and write the pool JSON → spawn locust headless 50 users / 10 spawn rate / 60 s → shell out to the parser. Fixture mode (`--csv-fixture <path>`): skips locust entirely and feeds an existing CSV straight into the parser — this is the bypass the pytest gate exercises.

**Parser + assertion** (`_parse_locust_csv.py`): Pure-Python module deliberately separated from the bash orchestrator so the assertion logic is testable without spinning up a real load. Reads locust's `*_stats.csv`, finds the (Type=GET, Name=...) and (Type=POST, Name=...) rows, asserts p95 < 200 ms / 500 ms with strict `<` (so exactly-at-budget = PASS), and asserts zero failures. Writes `price-history-{PASSED,FAILED}-<iso8601>.json` evidence under `backend/.perf-runs/` with the percentile dump. FAILED.json includes the canonical remediation string `"Open R036 (materialized part_price_summary) per D004"` so the next agent doesn't have to re-derive the decision tree. Locked exit-code contract: 0=PASS, 1=FAIL, 3=malformed CSV, 4=missing, 5=zero rows, 6=missing per-endpoint row.

**Tests** (`test_perf_gate_script.py`): 6 cases, all pytest.mark.skipif unless PERF_GATE_TEST=true. Two synthetic CSV fixtures (`locust_stats_passing.csv` with GET p95=120/POST p95=300/0 failures; `locust_stats_failing.csv` with GET p95=350/POST p95=600/15 failures) drive the happy + sad path. Negative-test branches (Q7) cover missing CSV (exit 4), empty CSV (exit 5), missing endpoint row (exit 6). Final test calls the bash runner end-to-end via `--csv-fixture` and snapshots `backend/.perf-runs/` to clean up only its own artifacts.

**Local adaptations from plan:**
1. Plan said `backend/pyproject.toml` for the dev dep — reality is `requirements.txt` (no `[project.optional-dependencies]` block exists). Added `locust>=2.20` to requirements.txt with a comment explaining it's dev-only and never imported by app code. Pip resolved to locust 2.43.4.
2. Plan implied a single bash script. Split into bash orchestrator + Python parser because (a) parsing locust's CSV in pure bash is brittle and (b) the testability story is much cleaner — pytest can subprocess.run the parser directly without invoking bash. Captured this split as MEM050 (pattern, mirrors MEM034).
3. Pool generation does an inline `python3 - <<PYEOF` instead of a separate script — keeps the runner self-contained and lets it set `TESTING=true` per MEM008 to avoid the boto3 head_bucket import-time crash when importing app.crawlers.* dependents.

Live perf-gate run was NOT executed in this task (requires uvicorn + sample data, not in scope per plan: "load test does NOT run in CI by default"). The PASSED.json under backend/.perf-runs/ that S13 milestone verification re-reads will be produced when the user runs `bash backend/scripts/perf/run_price_history_loadtest.sh` against a live local server.

## Verification

Ran the slice's verify command in three legs:

1. `PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py -n0 --rootdir=backend -q --no-cov` → 6 passed in 0.21s. Covers: passing fixture → exit 0 + PASSED.json; failing fixture → exit 1 + FAILED.json with R036/D004 remediation string + GET/POST/error-rate failures all flagged; missing CSV → exit 4; empty CSV → exit 5; CSV missing endpoint row → exit 6; runner --csv-fixture flag end-to-end.

2. `bash -n backend/scripts/perf/run_price_history_loadtest.sh` → exit 0 (clean shell syntax).

3. `python -c 'import locust; print(locust.__version__)'` → 2.43.4 (install succeeded).

Sanity-ran the parser directly against the passing fixture: exit 0, wrote PASSED.json with the expected percentile breakdown (GET p95=120, POST p95=300).

Re-ran the prior S05 test suites (`test_parts_price_history.py` + `test_part_price_aggregation_service.py`) → 29 passed in 5.26s. No regression from this task's additions.

Confirmed `git check-ignore backend/.perf-runs/anything.json` returns the path → gitignore wired correctly.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PERF_GATE_TEST=true TESTING=true pytest backend/tests/test_perf_gate_script.py -n0 --rootdir=backend -q --no-cov` | 0 | ✅ pass | 210ms |
| 2 | `bash -n backend/scripts/perf/run_price_history_loadtest.sh` | 0 | ✅ pass | 50ms |
| 3 | `python -c 'import locust; print(locust.__version__)'` | 0 | ✅ pass | 800ms |
| 4 | `python3 backend/scripts/perf/_parse_locust_csv.py --csv backend/tests/fixtures/perf/locust_stats_passing.csv --evidence-dir /tmp/perf-smoke` | 0 | ✅ pass | 120ms |
| 5 | `TESTING=true pytest backend/tests/api/endpoints/test_parts_price_history.py backend/tests/services/test_part_price_aggregation_service.py -n auto --rootdir=backend -q --no-cov` | 0 | ✅ pass (no regression) | 5260ms |
| 6 | `git check-ignore backend/.perf-runs/anything.json` | 0 | ✅ pass (path returned) | 30ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend/scripts/perf/locustfile_price_history.py`
- `backend/scripts/perf/run_price_history_loadtest.sh`
- `backend/scripts/perf/_parse_locust_csv.py`
- `backend/scripts/perf/README.md`
- `backend/tests/test_perf_gate_script.py`
- `backend/tests/fixtures/perf/locust_stats_passing.csv`
- `backend/tests/fixtures/perf/locust_stats_failing.csv`
- `backend/requirements.txt`
- `.gitignore`
