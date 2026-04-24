"""QUAL-04: bandit HIGH-severity regression test.

Pins the current CI invocation (`bandit -r app -ll`) from silently regressing
to a config that would pass HIGH findings through. Uses a synthetic B602 fixture.

D-18 path A applies: current `-ll` flag empirically exits 1 on HIGH (verified
2026-04-23 on bandit 1.9.4). This test guards that behavior; no CI flag change
was made.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def high_severity_fixture(tmp_path: Path) -> Path:
    """Synthetic file with a bandit B602 HIGH-severity finding."""
    src = tmp_path / "fixture.py"
    src.write_text(
        "import subprocess\n"
        "import os\n"
        "user_input = os.environ.get('CMD', '')\n"
        "subprocess.call(user_input, shell=True)  # B602 HIGH\n"
    )
    return src


def test_bandit_fails_on_high_severity(high_severity_fixture: Path) -> None:
    """`bandit -r <fixture> -ll` MUST exit non-zero on a HIGH-severity finding."""
    result = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", str(high_severity_fixture), "-ll"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        f"bandit -ll unexpectedly exited 0 on HIGH fixture. "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "Severity: High" in result.stdout, (
        f"Expected 'Severity: High' in bandit output, got: {result.stdout!r}"
    )
