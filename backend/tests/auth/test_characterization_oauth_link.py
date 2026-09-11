"""Characterization of linking Google OAuth to an existing password user.

The JWKS fetch replays from a pytest-recording cassette beside this module.
"""

import os
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import OAuthAccountRepository
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository

_CASSETTE = (
    pathlib.Path(__file__).parent
    / "cassettes"
    / pathlib.Path(__file__).stem
    / "test_google_oauth_link_existing_user.yaml"
)

pytestmark = pytest.mark.skipif(
    not _CASSETTE.exists(),
    reason="Cassette missing — run `cd backend && pytest -n 0 --record-mode=once "
    "tests/auth/test_characterization_oauth_link.py::test_google_oauth_link_existing_user` to generate.",
)


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


@pytest.mark.vcr
def test_google_oauth_link_existing_user(client: TestClient, db_session: Any) -> None:
    """An existing user exchanges a link token and password for a linked Google account."""
    id_token_from_cassette = "<ID_TOKEN_FROM_CASSETTE>"
    nonce_from_cassette = "<NONCE_FROM_CASSETTE>"
    email_from_cassette = "<EMAIL_FROM_CASSETTE>"
    password = "testpass123!"
    username = _uniq("oauth_link")

    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email_from_cassette,
            hashed_password=get_password_hash(password),
            email_verified=True,
            disabled=False,
        )
    )

    google_resp = client.post(
        f"{settings.API_STR}/auth/oauth/google",
        json={"id_token": id_token_from_cassette, "nonce": nonce_from_cassette},
    )
    assert google_resp.status_code == 200, google_resp.text
    google_body = google_resp.json()
    assert "link_token" in google_body, f"Expected link_token, got: {list(google_body.keys())}"
    link_token = google_body["link_token"]

    link_resp = client.post(
        f"{settings.API_STR}/auth/oauth/google/link",
        json={"link_token": link_token, "password": password},
    )
    assert link_resp.status_code == 200, link_resp.text
    link_body = link_resp.json()
    assert "access_token" in link_body

    oauth = OAuthAccountRepository().get_for_user_provider(user.id, "google")
    assert oauth is not None
    assert oauth.provider == "google"
