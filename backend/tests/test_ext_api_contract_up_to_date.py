"""Fails when chrome-extension/API_CONTRACT.md is stale against its generator.

The generator is run as a subprocess rather than imported, because backend/scripts is not an importable package.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_ext_api_contract.py"
CONTRACT_PATH = Path(__file__).resolve().parents[2] / "chrome-extension" / "API_CONTRACT.md"


def test_api_contract_matches_generator() -> None:
    """The committed contract matches what the generator emits today."""
    env = {
        **os.environ,
        "TESTING": "true",
        "ENABLE_RATE_LIMITING": "false",
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--stdout"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
        cwd=str(SCRIPT_PATH.parent.parent),
    )
    expected = result.stdout
    committed = CONTRACT_PATH.read_text(encoding="utf-8")

    if expected != committed:
        msg = (
            "chrome-extension/API_CONTRACT.md is out of date.\n"
            "Regenerate:\n"
            "\n"
            "    cd backend\n"
            "    TESTING=true ENABLE_RATE_LIMITING=false \\\n"
            "      python scripts/generate_ext_api_contract.py\n"
            "\n"
            "Then commit the regenerated chrome-extension/API_CONTRACT.md."
        )
        assert expected == committed, msg
