---
id: T02
parent: S13
milestone: M002
key_files:
  - .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json
  - backend/.perf-runs/price-history-PASSED-20260426T051456Z.json
  - .gsd/REQUIREMENTS.md
key_decisions:
  - PASSED at 10× — kept R036 deferred per D004 instead of opening it. The perf gate's whole point is conditionally opening R036; PASS means query-time aggregation stays the strategy through M003.
  - Promoted R019 with a validation field that names the date, exact percentiles, locked config (50/10/60s), and the committed evidence path — so the validation claim is reproducible without re-running the gate.
  - Did NOT modify run_price_history_loadtest.sh to auto-load backend/.env. The DATABASE_URL gotcha is a runtime invocation contract — captured as MEM136 instead. Modifying the script would change a contract that S05 tests assert against.
duration: 
verification_result: passed
completed_at: 2026-04-26T05:16:34.939Z
blocker_discovered: false
---

# T02: Re-ran S05 perf gate at 10× against live stack — PASSED (GET p95=95ms, POST p95=130ms, 0 failures across 1893 reqs); R019 promoted to validated, R036 stays deferred per D004

**Re-ran S05 perf gate at 10× against live stack — PASSED (GET p95=95ms, POST p95=130ms, 0 failures across 1893 reqs); R019 promoted to validated, R036 stays deferred per D004**

## What Happened

Executed `bash backend/scripts/perf/run_price_history_loadtest.sh` against the live uvicorn stack on :8000. Locked 10× config (50 users, 10 spawn-rate, 60s, 4:1 GET:POST). Locust drove 1500 GET + 393 POST requests across 500 part IDs from the catalog. Parser asserted both p95 budgets and zero-failure constraint, wrote `backend/.perf-runs/price-history-PASSED-20260426T051456Z.json`, exited 0.

PASSED budgets:
- GET /api/parts/{id}/price-history: requests=1500, failures=0, p50=8ms, p95=95ms (budget <200ms), p99=140ms, max=160ms
- POST /api/parts/price-history: requests=393, failures=0, p50=43ms, p95=130ms (budget <500ms), p99=160ms, max=170ms

Both endpoints sat at roughly half their budgets — query-time aggregation is the right call at current catalog size, validating D004's bet.

Mirrored the verdict file from the gitignored `backend/.perf-runs/` to the committed `.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json` so M002-VALIDATION.md (T06) and downstream auditors have a tracked artifact.

Promoted R019 from active → validated via `gsd_requirement_update` with a validation field that names the date, config, observed percentiles, and evidence path. R036 (materialized `part_price_summary`) stays deferred per D004 — its precondition (perf gate miss) was not met.

**Setup gotcha encountered and fixed:** First `bash backend/scripts/perf/run_price_history_loadtest.sh` invocation from repo root failed at the part-id-pool builder with `sqlite3.OperationalError: no such table: part_price_history`. Pydantic Settings reads `.env` relative to CWD, but the file lives at `backend/.env` — without an exported `DATABASE_URL`, SessionLocal silently fell back to `sqlite:///./test.db`. Resolved by `set -a; source backend/.env; set +a` before running. Captured as MEM136 (gotcha) so future agents don't re-derive this. Did NOT modify the script — this is a runtime invocation contract, not a script bug.

Did NOT set `blocker_discovered: true` — the slice plan was sound, the perf gate passed cleanly on the first real run, and R019 promotion is the planned PASS branch.

## Verification

Concrete verification commands run:
- `bash backend/scripts/perf/run_price_history_loadtest.sh` → exit 0, PASSED.json written, both p95 budgets met inside locked thresholds, zero failures.
- `cat backend/.perf-runs/price-history-PASSED-20260426T051456Z.json` confirms verdict=PASSED, failed_assertions=[].
- `cp ... .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json` + `ls -la` confirms committed evidence file exists (857 bytes).
- `test -f .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json` (slice-plan verification gate) → exit 0.
- `grep "^### R019" .gsd/REQUIREMENTS.md -A 3` confirms `Status: validated` after `gsd_requirement_update`.
- Live stack confirmed pre-run: `curl /health` → 200 healthy, `curl /ready` → 200 db=up.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash backend/scripts/perf/run_price_history_loadtest.sh` | 0 | ✅ pass | 90000ms |
| 2 | `test -f .gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json` | 0 | ✅ pass | 5ms |
| 3 | `curl -fsS http://localhost:8000/health` | 0 | ✅ pass | 50ms |
| 4 | `curl -fsS http://localhost:8000/ready` | 0 | ✅ pass | 30ms |
| 5 | `grep '^### R019' .gsd/REQUIREMENTS.md -A 2 (post-update status check)` | 0 | ✅ pass — Status: validated | 10ms |

## Deviations

Slice plan said T02 reuses T01's live stack. T01's stack was actually on `main` (uvicorn PID 424971 from operator), not the M002 worktree. Backend code is identical between branches (verified in T01-SUMMARY), so this is a benign deviation — the perf gate is testing HTTP behavior of identical backend code, not branch-specific code paths. No action needed.

Hit one setup-issue (exit 1 from pool-builder due to missing DATABASE_URL on first invocation). Plan said "exit codes 2-6 are mechanical setup failures, not perf misses — diagnose env first" — followed exactly that branch, fixed env (sourced backend/.env), re-ran, got PASS on the next attempt. No retry-loop on a real perf miss.

## Known Issues

backend/scripts/perf/run_price_history_loadtest.sh has an uncommitted local fix (Part → PartListing → PartPriceHistory join) that landed earlier in this slice — git status shows it as M. Pool-builder works correctly with this fix; without it the script would also fail. This commit-staging concern is for the slice's auto-commit step, not this task.

The 4 stale locust CSVs from the failed earlier run (locust-20260426T045752Z_*.csv) sit in backend/.perf-runs/ alongside the new ones. backend/.perf-runs/ is gitignored so they don't pollute git, and the script's evidence-file naming uses the new timestamp so the verdict file is unambiguous.

## Files Created/Modified

- `.gsd/milestones/M002/slices/S13/uat-evidence/perf-gate-PASSED.json`
- `backend/.perf-runs/price-history-PASSED-20260426T051456Z.json`
- `.gsd/REQUIREMENTS.md`
