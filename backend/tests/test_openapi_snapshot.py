"""Pins the OpenAPI schema against a formatted JSON snapshot, so the diff is the schema review.

Regenerate under TESTING=true ENABLE_RATE_LIMITING=false only; other overrides change the title and paths.
"""

from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"


def test_openapi_snapshot_matches() -> None:
    """The live schema matches the committed snapshot.

    app is imported inside the function so conftest's env setup lands first; a module
    level import leaks rate limit responses into the schema.
    """
    from app.main import app

    actual = json.dumps(app.openapi(), indent=2, sort_keys=True)
    expected = SNAPSHOT_PATH.read_text(encoding="utf-8")

    if actual != expected:
        msg = (
            "OpenAPI schema drift detected.\n"
            "Review the diff on backend/tests/fixtures/openapi_snapshot.json carefully.\n"
            "If the drift is intentional, regenerate the snapshot:\n"
            "\n"
            "    cd backend\n"
            "    TESTING=true ENABLE_RATE_LIMITING=false \\\n"
            "      python -c 'import json, sys; from app.main import app; "
            "sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True))' "
            "> tests/fixtures/openapi_snapshot.json\n"
            "\n"
            "Then commit the regenerated file."
        )
        assert actual == expected, msg
