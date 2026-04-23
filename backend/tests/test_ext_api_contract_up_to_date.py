"""AUTH-06 D-36 drift guard: chrome-extension/API_CONTRACT.md matches generator output.

Per D-36, developers regenerate the contract locally when the extension endpoint
list or underlying route signatures change, then commit the new .md. CI fails
here if the committed doc is stale.

IMPORTANT: this test does NOT import the generator as a Python module.
``backend/scripts/`` has no ``__init__.py`` and ``backend/`` itself is not on
``sys.path`` as a package (pytest.ini sets testpaths=tests with rootdir at
``backend/``). A ``from backend.scripts.generate_ext_api_contract import ...``
would raise ``ModuleNotFoundError``. Instead we subprocess-invoke the script
with ``--stdout``, which is how ``test_openapi_snapshot.py`` avoids script-import
issues too (it calls ``app.openapi()`` directly in-process rather than importing
any script).

Same shape as ``test_openapi_snapshot.py`` in spirit — diff IS the review
artifact.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "generate_ext_api_contract.py"
)
CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "chrome-extension" / "API_CONTRACT.md"
)


def test_api_contract_matches_generator() -> None:
    # Subprocess-invoke with --stdout — captures Markdown as the generator emits it.
    # TESTING=true + ENABLE_RATE_LIMITING=false ensure the OpenAPI schema matches the
    # conftest.py env-var setup used by test_openapi_snapshot.py (pitfall 8 in
    # PATTERNS.md).
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
        # Run with backend/ as cwd so `from app.main import app` resolves.
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
