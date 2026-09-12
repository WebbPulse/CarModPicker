"""Tests the price history perf gate's own assertion logic against synthetic locust CSVs.

A buggy gate cannot hand out false passes.

Skipped unless PERF_GATE_TEST is set, because locust is a heavy install.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "backend" / "scripts" / "perf" / "run_price_history_loadtest.sh"
FIXTURE_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "perf"
PASSING_FIXTURE = FIXTURE_DIR / "locust_stats_passing.csv"
FAILING_FIXTURE = FIXTURE_DIR / "locust_stats_failing.csv"

pytestmark = pytest.mark.skipif(
    os.environ.get("PERF_GATE_TEST") != "true",
    reason="set PERF_GATE_TEST=true to run the perf-gate gate-on-the-gate",
)


def _run_gate(csv_path: Path, evidence_dir: Path) -> subprocess.CompletedProcess[str]:
    """Run the CSV parser against one fixture and return the completed process."""
    env = os.environ.copy()
    parser = REPO_ROOT / "backend" / "scripts" / "perf" / "_parse_locust_csv.py"
    return subprocess.run(
        [
            sys.executable,
            str(parser),
            "--csv",
            str(csv_path),
            "--evidence-dir",
            str(evidence_dir),
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_passing_fixture_returns_zero_and_writes_passed_evidence(tmp_path: Path) -> None:
    """Happy path: in-budget p95s, zero failures → exit 0 + PASSED.json."""
    result = _run_gate(PASSING_FIXTURE, tmp_path)
    assert result.returncode == 0, (
        f"expected exit 0 on passing CSV, got {result.returncode}\n" f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    passed_files = list(tmp_path.glob("price-history-PASSED-*.json"))
    failed_files = list(tmp_path.glob("price-history-FAILED-*.json"))
    assert len(passed_files) == 1, f"expected one PASSED.json, got {passed_files}"
    assert not failed_files, f"unexpected FAILED.json: {failed_files}"

    payload = json.loads(passed_files[0].read_text())
    assert payload["verdict"] == "PASSED"
    assert payload["failed_assertions"] == []
    assert payload["endpoints"]["get"]["budget_ms"] == 200
    assert payload["endpoints"]["post"]["budget_ms"] == 500
    assert payload["endpoints"]["get"]["stats"]["p95_ms"] == 120
    assert payload["endpoints"]["post"]["stats"]["p95_ms"] == 300


def test_failing_fixture_returns_one_and_writes_failed_evidence_with_remediation(
    tmp_path: Path,
) -> None:
    """The core gate-on-the-gate assertion: when p95 misses, the script MUST
    exit non-zero AND write a FAILED.json that names R036 in the remediation
    field. If this regresses we ship a silent perf gate."""
    result = _run_gate(FAILING_FIXTURE, tmp_path)
    assert result.returncode == 1, (
        f"expected exit 1 on failing CSV, got {result.returncode}\n" f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    failed_files = list(tmp_path.glob("price-history-FAILED-*.json"))
    passed_files = list(tmp_path.glob("price-history-PASSED-*.json"))
    assert len(failed_files) == 1, f"expected one FAILED.json, got {failed_files}"
    assert not passed_files, f"unexpected PASSED.json: {passed_files}"

    payload = json.loads(failed_files[0].read_text())
    assert payload["verdict"] == "FAILED"
    assert payload["failed_assertions"], "FAILED.json must list at least one failure"
    assert "R036" in payload["remediation"]
    assert "D004" in payload["remediation"]
    failure_text = " ".join(payload["failed_assertions"])
    assert "GET" in failure_text
    assert "POST" in failure_text
    assert "error rate" in failure_text


def test_missing_csv_returns_four(tmp_path: Path) -> None:
    """Q7 negative test: missing CSV file → exit 4."""
    result = _run_gate(tmp_path / "does-not-exist.csv", tmp_path)
    assert result.returncode == 4, (
        f"expected exit 4 on missing CSV, got {result.returncode}\n" f"stderr: {result.stderr}"
    )


def test_empty_csv_returns_five(tmp_path: Path) -> None:
    """Q7 negative test: zero data rows → exit 5."""
    empty = tmp_path / "empty.csv"
    empty.write_text("Type,Name,Request Count,Failure Count,50%,95%,99%,100%,Average Response Time\n")
    result = _run_gate(empty, tmp_path)
    assert result.returncode == 5, (
        f"expected exit 5 on header-only CSV, got {result.returncode}\n" f"stderr: {result.stderr}"
    )


def test_csv_missing_endpoint_row_returns_six(tmp_path: Path) -> None:
    """A CSV with no per endpoint row exits 6 rather than passing silently."""
    only_aggregated = tmp_path / "only_aggregated.csv"
    only_aggregated.write_text(
        "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,"
        "Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,"
        "50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%\n"
        ",Aggregated,100,0,90,100,10,200,512,5.0,0.0,90,100,110,120,130,140,160,180,190,195,200\n"
    )
    result = _run_gate(only_aggregated, tmp_path)
    assert result.returncode == 6, (
        f"expected exit 6 on missing endpoint row, got {result.returncode}\n" f"stderr: {result.stderr}"
    )


def test_runner_csv_fixture_flag_invokes_parser(tmp_path: Path) -> None:
    """The bash runner's --csv-fixture branch reaches the parser and writes PASSED.json."""
    evidence_dir = REPO_ROOT / "backend" / ".perf-runs"
    pre_existing = set(evidence_dir.glob("*")) if evidence_dir.exists() else set()
    try:
        result = subprocess.run(
            ["bash", str(RUNNER), "--csv-fixture", str(PASSING_FIXTURE)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"runner --csv-fixture mode should exit 0 on passing CSV, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        new_files = set(evidence_dir.glob("*")) - pre_existing
        passed = [p for p in new_files if "PASSED" in p.name]
        assert passed, f"expected a PASSED.json under {evidence_dir}, new={new_files}"
    finally:
        if evidence_dir.exists():
            for p in set(evidence_dir.glob("*")) - pre_existing:
                p.unlink(missing_ok=True)
