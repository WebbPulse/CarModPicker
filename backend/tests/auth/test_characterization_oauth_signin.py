"""SAFE-06 flow 5: Google OAuth first-time sign-in.

Uses pytest-recording: the cassette at:

    backend/tests/auth/cassettes/test_characterization_oauth_signin/
        test_google_oauth_signin.yaml

records the JWKS HTTPS roundtrip to Google. Cassette regeneration (when
Google rotates keys or the endpoint contract changes):

    cd backend
    rm -rf tests/auth/cassettes/test_characterization_oauth_signin
    pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_signin.py::test_google_oauth_signin

MUST use -n 0 to avoid pytest-xdist write races (Pitfall 3). Record against
a dedicated test Google account, never a personal/admin account.

After recording, run:
    cd backend && pytest -n auto tests/auth/test_characterization_oauth_signin.py -v
and confirm the test reports PASSED (not SKIPPED) — a SKIPPED result after the
cassette YAML is present indicates the _CASSETTE path formula is wrong.

pytest-recording default cassette layout:
    <test-file-dir>/cassettes/<test-module-basename>/<test-function-name>.yaml
"""

import os
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.core.config import settings

# pytest-recording stores cassettes at: <test_dir>/cassettes/<module_basename>/<test_name>.yaml
_CASSETTE = pathlib.Path(__file__).parent / "cassettes" / pathlib.Path(__file__).stem / "test_google_oauth_signin.yaml"

pytestmark = pytest.mark.skipif(
    not _CASSETTE.exists(),
    reason="Cassette missing — run `cd backend && pytest -n 0 --record-mode=once "
    "tests/auth/test_characterization_oauth_signin.py::test_google_oauth_signin` to generate.",
)


def _uniq(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


@pytest.mark.vcr
def test_google_oauth_signin(client: TestClient, db_session: Session) -> None:
    """Flow 5: first-time Google sign-in creates a user and returns tokens.

    The id_token and nonce below must match the values captured in the cassette.
    When regenerating, replace these placeholders with the values from the recorded
    request body, then commit the cassette YAML alongside updated placeholders.

    The POST /api/auth/google endpoint requires settings.google_oauth_enabled
    (GOOGLE_CLIENT_ID set in env). When recording locally, set:
        export GOOGLE_CLIENT_ID=<your-test-client-id>
    In CI the cassette replay does not re-verify the token with Google; the
    JWKS response is served from the cassette file.
    """
    # These values must be updated when the cassette is recorded.
    # The nonce is arbitrary; the id_token must be a real token from the
    # Google sandbox account used during recording.
    id_token_from_cassette = "<ID_TOKEN_FROM_CASSETTE>"
    nonce_from_cassette = "<NONCE_FROM_CASSETTE>"
    email_from_cassette = "<EMAIL_FROM_CASSETTE>"

    response = client.post(
        f"{settings.API_STR}/auth/oauth/google",
        json={"id_token": id_token_from_cassette, "nonce": nonce_from_cassette},
    )

    # D-19: status + key presence + DB state change
    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body

    # DB state: user now exists with email_verified=True (OAuth email is trusted)
    user = db_session.query(DBUser).filter(DBUser.email == email_from_cassette).first()
    assert user is not None
    assert user.email_verified is True
