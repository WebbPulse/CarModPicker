"""Gate-on-the-gate (M002/S05/T05).

The price-history perf gate (`backend/scripts/perf/run_price_history_loadtest.sh`)
is the falsifiable check that says "query-time aggregation is fast enough — don't
open R036 (materialized part_price_summary) per D004." If the assertion logic in
the gate is buggy, the gate gives false PASSes and we ship a slow backend.

This test exercises the assertion logic against synthetic CSVs WITHOUT requiring
a live uvicorn server or actual locust traffic. It uses the runner's
``--csv-fixture <path>`` flag to bypass locust entirely and feed a known CSV
into the parser.

Default-skipped (locust install is heavy and not on every contributor's machine).
The S05 verify command sets ``PERF_GATE_TEST=true`` to opt in.
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
    env = os.environ.copy()
    # Route evidence files into the test-scoped tmp dir, not backend/.perf-runs/
    # — keeps tests hermetic and prevents leftover files from poisoning future
    # runs. The runner reads its evidence dir from a hardcoded path, so we
    # invoke the parser directly here for the test-scoped redirect.
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
    # R036 reference is part of the gate's contract — guard it explicitly.
    assert "R036" in payload["remediation"]
    assert "D004" in payload["remediation"]
    # Both budgets missed in this fixture — make sure both are flagged, not just one.
    failure_text = " ".join(payload["failed_assertions"])
    assert "GET" in failure_text
    assert "POST" in failure_text
    # Failure count > 0 in the fixture should also be flagged.
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
    # Header-only — parses cleanly but yields no rows.
    empty.write_text("Type,Name,Request Count,Failure Count,50%,95%,99%,100%,Average Response Time\n")
    result = _run_gate(empty, tmp_path)
    assert result.returncode == 5, (
        f"expected exit 5 on header-only CSV, got {result.returncode}\n" f"stderr: {result.stderr}"
    )


def test_csv_missing_endpoint_row_returns_six(tmp_path: Path) -> None:
    """Q7 negative test: CSV present but missing the per-endpoint stats row → exit 6.

    Locust always emits one row per (Type, Name) — if the GET/POST rows are
    absent the gate can't assert anything and must surface a clear diagnostic
    instead of silently passing or crashing.
    """
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
    """Smoke test the bash runner's --csv-fixture branch end-to-end.

    Confirms the runner's argument plumbing wires up to the parser cleanly —
    no preflight, no locust, just: fixture CSV → exit 0 + PASSED.json under
    the canonical evidence dir. We use a copied evidence dir to avoid mutating
    the repo's backend/.perf-runs/ during tests.
    """
    # The runner writes evidence to backend/.perf-runs/ unconditionally. Snapshot
    # the dir's pre-test contents and clean up only files this test created.
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
        # Cleanup: remove only files this test created.
        if evidence_dir.exists():
            for p in set(evidence_dir.glob("*")) - pre_existing:
                p.unlink(missing_ok=True)
