"""SAFE-05: OpenAPI schema snapshot test.

Catches unintended route / schema drift. The snapshot is formatted JSON
(indent=2, sort_keys=True) so the diff in PR review IS the schema change
— per D-27 we do NOT use hash comparison.

Regenerate on intentional schema change:

    cd backend
    TESTING=true ENABLE_RATE_LIMITING=false \
      python -c "import json, sys; from app.main import app; sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True))" \
      > tests/fixtures/openapi_snapshot.json

IMPORTANT: Use only TESTING=true ENABLE_RATE_LIMITING=false — no extra env overrides.
conftest.py imports app at module scope so Settings reads the defaults; the snapshot
must be generated under the same conditions or the title/paths will diverge.

Then commit the regenerated file alongside the code change that produced the
drift. The diff on that file is the review artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "openapi_snapshot.json"


def test_openapi_snapshot_matches() -> None:
    """Pin the full OpenAPI schema against the committed snapshot file.

    Pitfall 8: import `app` at FUNCTION scope so conftest.py's env-var setup
    runs first. Importing `app.main` at module top-level wires the rate
    limiter into the OpenAPI schema and leaks rate-limit response codes
    into the snapshot.
    """
    # Function-scope import is intentional — DO NOT move to module top.
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
