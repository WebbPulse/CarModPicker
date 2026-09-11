"""Characterization of first-time Google OAuth sign-in.

The JWKS fetch replays from a pytest-recording cassette beside this module.
"""

import os
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository

_CASSETTE = pathlib.Path(__file__).parent / "cassettes" / pathlib.Path(__file__).stem / "test_google_oauth_signin.yaml"

pytestmark = pytest.mark.skipif(
    not _CASSETTE.exists(),
    reason="Cassette missing — run `cd backend && pytest -n 0 --record-mode=once "
    "tests/auth/test_characterization_oauth_signin.py::test_google_oauth_signin` to generate.",
)


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


@pytest.mark.vcr
def test_google_oauth_signin(client: TestClient, db_session: Any) -> None:
    """A first-time Google sign-in creates the user and returns tokens."""
    id_token_from_cassette = "<ID_TOKEN_FROM_CASSETTE>"
    nonce_from_cassette = "<NONCE_FROM_CASSETTE>"
    email_from_cassette = "<EMAIL_FROM_CASSETTE>"

    response = client.post(
        f"{settings.API_STR}/auth/oauth/google",
        json={"id_token": id_token_from_cassette, "nonce": nonce_from_cassette},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body

    user = UserRepository().get_by_email(email_from_cassette)
    assert user is not None
    assert user.email_verified is True
