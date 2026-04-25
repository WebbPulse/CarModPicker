"""CSV parser + p95 assertion for the price-history perf gate.

Separated from the bash runner so the assertion logic is testable in pure
Python (see backend/tests/test_perf_gate_script.py). The bash runner shells
out to this module; the pytest gate-on-the-gate calls it directly via
subprocess with ``--csv-fixture <path>``.

Exit codes (locked contract — referenced by the pytest test and README):
- 0 : PASS  (all p95 budgets met, error rate == 0)
- 1 : FAIL  (one or more assertions missed; FAILED.json written)
- 3 : malformed CSV row (could not parse a numeric column)
- 4 : CSV file does not exist
- 5 : CSV file exists but contains zero data rows
- 6 : CSV is missing the expected per-endpoint stats rows

Inputs:
- --csv <path>          path to locust *_stats.csv (the per-request-type table)
- --evidence-dir <dir>  where to write PASSED.json / FAILED.json
- --get-budget-ms       p95 budget for the GET endpoint (default 200)
- --post-budget-ms      p95 budget for the POST endpoint (default 500)
- --get-name            stats Name column value for GET (default 'GET /api/parts/{id}/price-history')
- --post-name           stats Name column value for POST (default 'POST /api/parts/price-history')

Writes one JSON evidence file per invocation under the evidence dir, named
``price-history-PASSED-<iso>.json`` or ``price-history-FAILED-<iso>.json``.
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# The remediation pointer is part of the gate's contract — when the gate
# fails, the FAILED.json must literally name R036 so the next agent doesn't
# have to re-derive D004.
REMEDIATION_NOTE = (
    "Perf gate missed. Open R036 (materialized part_price_summary) per D004 "
    "— see .gsd/REQUIREMENTS.md."
)

DEFAULT_GET_NAME = "GET /api/parts/{id}/price-history"
DEFAULT_POST_NAME = "POST /api/parts/price-history"
DEFAULT_GET_BUDGET_MS = 200
DEFAULT_POST_BUDGET_MS = 500


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_stats_rows(csv_path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def _find_row(rows: List[Dict[str, str]], type_: str, name: str) -> Optional[Dict[str, str]]:
    """Locust uses Type=GET/POST and Name=label. Match both so an Aggregated
    row with the same Name doesn't shadow the per-method row."""
    for row in rows:
        if row.get("Type", "").strip() == type_ and row.get("Name", "").strip() == name:
            return row
    return None


def _coerce_float(row: Dict[str, str], column: str) -> float:
    raw = row.get(column, "").strip()
    if raw in ("", "N/A"):
        raise ValueError(f"column {column!r} is empty in row {row!r}")
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"column {column!r} not numeric ({raw!r}) in row {row!r}") from exc


def _coerce_int(row: Dict[str, str], column: str) -> int:
    raw = row.get(column, "").strip()
    if raw in ("", "N/A"):
        raise ValueError(f"column {column!r} is empty in row {row!r}")
    try:
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(f"column {column!r} not integer ({raw!r}) in row {row!r}") from exc


def _extract_endpoint_stats(
    rows: List[Dict[str, str]], type_: str, name: str
) -> Dict[str, Any]:
    """Return p50/p95/p99/max/requests/failures for one endpoint row.

    Locust columns of interest:
    - Request Count, Failure Count
    - 50%, 95%, 99%, 100% (response time percentiles in ms; integer-rounded)
    - Average Response Time, Max Response Time
    """
    row = _find_row(rows, type_, name)
    if row is None:
        raise LookupError(f"no stats row for Type={type_!r} Name={name!r}")
    return {
        "requests": _coerce_int(row, "Request Count"),
        "failures": _coerce_int(row, "Failure Count"),
        "p50_ms": _coerce_float(row, "50%"),
        "p95_ms": _coerce_float(row, "95%"),
        "p99_ms": _coerce_float(row, "99%"),
        "max_ms": _coerce_float(row, "100%"),
        "avg_ms": _coerce_float(row, "Average Response Time"),
    }


def _print_breakdown(label: str, stats: Dict[str, Any], budget_ms: int) -> None:
    print(
        f"  {label}: requests={stats['requests']} failures={stats['failures']} "
        f"p50={stats['p50_ms']:.0f}ms p95={stats['p95_ms']:.0f}ms "
        f"p99={stats['p99_ms']:.0f}ms max={stats['max_ms']:.0f}ms "
        f"(budget p95<{budget_ms}ms)"
    )


def evaluate(
    csv_path: Path,
    evidence_dir: Path,
    get_name: str,
    post_name: str,
    get_budget_ms: int,
    post_budget_ms: int,
) -> int:
    """Parse, assert, write evidence, return exit code."""
    if not csv_path.exists():
        print(f"[perf-gate] CSV not found: {csv_path}", file=sys.stderr)
        return 4

    try:
        rows = _read_stats_rows(csv_path)
    except (OSError, csv.Error) as exc:
        print(f"[perf-gate] failed to read CSV {csv_path}: {exc}", file=sys.stderr)
        return 3

    if not rows:
        print(f"[perf-gate] CSV {csv_path} contains zero data rows", file=sys.stderr)
        return 5

    try:
        get_stats = _extract_endpoint_stats(rows, "GET", get_name)
        post_stats = _extract_endpoint_stats(rows, "POST", post_name)
    except LookupError as exc:
        # Missing the per-endpoint Aggregated row contract.
        print(f"[perf-gate] CSV missing expected stats row: {exc}", file=sys.stderr)
        return 6
    except ValueError as exc:
        # Could not parse a numeric column (malformed CSV).
        print(f"[perf-gate] CSV malformed: {exc}", file=sys.stderr)
        return 3

    if get_stats["requests"] == 0 and post_stats["requests"] == 0:
        # Locust ran but no traffic landed — treat as malformed run.
        print(
            f"[perf-gate] CSV {csv_path} reports zero requests on both endpoints",
            file=sys.stderr,
        )
        return 5

    failures: List[str] = []
    if get_stats["p95_ms"] >= get_budget_ms:
        failures.append(
            f"GET p95={get_stats['p95_ms']:.0f}ms >= budget {get_budget_ms}ms"
        )
    if post_stats["p95_ms"] >= post_budget_ms:
        failures.append(
            f"POST p95={post_stats['p95_ms']:.0f}ms >= budget {post_budget_ms}ms"
        )
    total_failures = get_stats["failures"] + post_stats["failures"]
    if total_failures > 0:
        failures.append(f"error rate > 0 (failures={total_failures})")

    verdict = "PASSED" if not failures else "FAILED"
    timestamp = _utc_iso()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    out_path = evidence_dir / f"price-history-{verdict}-{timestamp}.json"

    payload: Dict[str, Any] = {
        "verdict": verdict,
        "generated_at_utc": timestamp,
        "csv_source": str(csv_path),
        "endpoints": {
            "get": {
                "name": get_name,
                "budget_ms": get_budget_ms,
                "stats": get_stats,
            },
            "post": {
                "name": post_name,
                "budget_ms": post_budget_ms,
                "stats": post_stats,
            },
        },
        "failed_assertions": failures,
    }
    if verdict == "FAILED":
        payload["remediation"] = REMEDIATION_NOTE

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print(f"[perf-gate] verdict={verdict} evidence={out_path}")
    _print_breakdown("GET ", get_stats, get_budget_ms)
    _print_breakdown("POST", post_stats, post_budget_ms)
    if failures:
        for line in failures:
            print(f"  FAIL: {line}")
        print(f"  remediation: {REMEDIATION_NOTE}")
        return 1
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Parse locust stats CSV and enforce p95 budget.")
    parser.add_argument("--csv", required=True, type=Path, help="Path to locust *_stats.csv")
    parser.add_argument(
        "--evidence-dir",
        required=True,
        type=Path,
        help="Directory to write PASSED/FAILED JSON evidence",
    )
    parser.add_argument("--get-budget-ms", type=int, default=DEFAULT_GET_BUDGET_MS)
    parser.add_argument("--post-budget-ms", type=int, default=DEFAULT_POST_BUDGET_MS)
    parser.add_argument("--get-name", default=DEFAULT_GET_NAME)
    parser.add_argument("--post-name", default=DEFAULT_POST_NAME)
    args = parser.parse_args(argv)
    return evaluate(
        csv_path=args.csv,
        evidence_dir=args.evidence_dir,
        get_name=args.get_name,
        post_name=args.post_name,
        get_budget_ms=args.get_budget_ms,
        post_budget_ms=args.post_budget_ms,
    )


if __name__ == "__main__":
    sys.exit(main())
