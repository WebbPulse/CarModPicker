#!/usr/bin/env bash
# M002/S05/T05 — price-history perf gate runner.
#
# Orchestrates: preflight (uvicorn up + sample data loaded) → part-id pool
# generation → locust run → CSV parse → p95 assertion → evidence file.
#
# See backend/scripts/perf/README.md for the full contract. Budget is locked
# by D004 / R019: GET p95 < 200 ms, POST p95 < 500 ms, error rate == 0.
#
# Usage:
#   bash backend/scripts/perf/run_price_history_loadtest.sh
#   bash backend/scripts/perf/run_price_history_loadtest.sh --csv-fixture path/to/stats.csv
#
# Exit codes:
#   0  PASS
#   1  FAIL (assertion missed → FAILED.json written → R036 should open)
#   2  locust process exited non-zero
#   3  CSV malformed / parser error
#   4  CSV file missing
#   5  CSV had zero data rows
#   6  CSV missing the per-endpoint stats row

set -u  # don't set -e — we want to inspect locust's exit code explicitly
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PERF_DIR="${REPO_ROOT}/backend/scripts/perf"
EVIDENCE_DIR="${REPO_ROOT}/backend/.perf-runs"
LOCUSTFILE="${PERF_DIR}/locustfile_price_history.py"
PARSER="${PERF_DIR}/_parse_locust_csv.py"
POOL_PATH="${EVIDENCE_DIR}/part-id-pool.json"

HOST="${PERF_HOST:-http://localhost:8000}"
USERS="${PERF_USERS:-50}"
SPAWN_RATE="${PERF_SPAWN_RATE:-10}"
RUN_TIME="${PERF_RUN_TIME:-60s}"

CSV_FIXTURE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --csv-fixture)
      CSV_FIXTURE="${2:-}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,20p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "[perf-gate] unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

mkdir -p "${EVIDENCE_DIR}"

# --- Fixture path: skip locust entirely, just exercise the parser ----------
if [[ -n "${CSV_FIXTURE}" ]]; then
  echo "[perf-gate] fixture mode — parsing ${CSV_FIXTURE}"
  python3 "${PARSER}" \
    --csv "${CSV_FIXTURE}" \
    --evidence-dir "${EVIDENCE_DIR}"
  exit $?
fi

# --- Live mode: preflight ---------------------------------------------------
echo "[perf-gate] preflight: backend at ${HOST}"
if ! curl -fsS --max-time 5 "${HOST}/health" >/dev/null; then
  echo "[perf-gate] FATAL: backend not reachable at ${HOST}/health" >&2
  echo "[perf-gate]        Start uvicorn first: cd backend && uvicorn app.main:app --port 8000" >&2
  exit 1
fi

echo "[perf-gate] preflight: sample data + part-id pool"
# Generate the part-id pool from the DB. Uses TESTING=true so importing
# app.crawlers.* doesn't trigger boto3 head_bucket on import (see MEM008).
# Pool is the top 500 parts by observation count — gives the load test a
# realistic mix instead of one hot row.
PYTHONPATH="${REPO_ROOT}/backend" TESTING=true python3 - <<PYEOF
import json
import sys
from pathlib import Path

# Local import — runs only when the user invokes the live load test.
from app.api.models.part_price_history import PartPriceHistory
from app.api.models.part import Part
from app.db.session import SessionLocal  # type: ignore[import-not-found]
from sqlalchemy import func, select

pool_path = Path("${POOL_PATH}")
db = SessionLocal()
try:
    total = db.scalar(select(func.count()).select_from(PartPriceHistory)) or 0
    if total == 0:
        print(
            "[perf-gate] FATAL: part_price_history is empty. "
            "Run python scripts/populate_sample_data.py first.",
            file=sys.stderr,
        )
        sys.exit(1)
    rows = db.execute(
        select(Part.id, func.count(PartPriceHistory.id).label("obs"))
        .join(PartPriceHistory, PartPriceHistory.part_id == Part.id)
        .group_by(Part.id)
        .order_by(func.count(PartPriceHistory.id).desc())
        .limit(500)
    ).all()
    pool = [str(part_id) for part_id, _obs in rows]
    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps(pool, indent=2))
    print(f"[perf-gate] wrote {len(pool)} part IDs to {pool_path}")
finally:
    db.close()
PYEOF
POOL_RC=$?
if [[ ${POOL_RC} -ne 0 ]]; then
  echo "[perf-gate] FATAL: failed to build part-id pool (rc=${POOL_RC})" >&2
  exit 1
fi

# --- Live mode: run locust --------------------------------------------------
TS="$(date -u +%Y%m%dT%H%M%SZ)"
CSV_PREFIX="${EVIDENCE_DIR}/locust-${TS}"
echo "[perf-gate] running locust: users=${USERS} spawn=${SPAWN_RATE} run-time=${RUN_TIME}"

PART_ID_POOL_PATH="${POOL_PATH}" locust \
  -f "${LOCUSTFILE}" \
  --headless \
  --users "${USERS}" \
  --spawn-rate "${SPAWN_RATE}" \
  --run-time "${RUN_TIME}" \
  --host "${HOST}" \
  --csv "${CSV_PREFIX}"
LOCUST_RC=$?
if [[ ${LOCUST_RC} -ne 0 ]]; then
  echo "[perf-gate] FATAL: locust exited non-zero (rc=${LOCUST_RC})" >&2
  exit 2
fi

# --- Live mode: parse + assert ----------------------------------------------
STATS_CSV="${CSV_PREFIX}_stats.csv"
echo "[perf-gate] parsing ${STATS_CSV}"
python3 "${PARSER}" \
  --csv "${STATS_CSV}" \
  --evidence-dir "${EVIDENCE_DIR}"
exit $?
