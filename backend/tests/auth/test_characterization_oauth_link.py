"""SAFE-06 flow 6: link Google OAuth account to an existing email/password user.

Uses pytest-recording: the cassette at:

    backend/tests/auth/cassettes/test_characterization_oauth_link/
        test_google_oauth_link_existing_user.yaml

records the JWKS HTTPS roundtrip to Google. Cassette regeneration:

    cd backend
    rm -rf tests/auth/cassettes/test_characterization_oauth_link
    pytest -n 0 --record-mode=once tests/auth/test_characterization_oauth_link.py::test_google_oauth_link_existing_user

MUST use -n 0 to avoid pytest-xdist write races (Pitfall 3).

The Google link flow for EXISTING users (email already matches) uses
POST /api/auth/google → returns link_token → POST /api/auth/google/link.
The link_token encodes the google_sub from the verified ID token.

After recording, run:
    cd backend && pytest -n auto tests/auth/test_characterization_oauth_link.py -v
and confirm the test reports PASSED (not SKIPPED).

pytest-recording default cassette layout:
    <test-file-dir>/cassettes/<test-module-basename>/<test-function-name>.yaml
"""

import os
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import OAuthAccountRepository
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository

# pytest-recording stores cassettes at: <test_dir>/cassettes/<module_basename>/<test_name>.yaml
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
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


@pytest.mark.vcr
def test_google_oauth_link_existing_user(client: TestClient, db_session: Session) -> None:
    """Flow 6: link Google to an EXISTING email/password user.

    The Google link flow:
      1. POST /api/auth/google with the Google id_token — because the user's
         email already exists, the endpoint returns a link_token (not an access_token).
      2. POST /api/auth/google/link with {link_token, password} — verifies password,
         creates the OAuthAccount row, returns access_token.

    The id_token, nonce, and email below must match the values captured in the
    cassette. The email MUST be the same as the email on the Google sandbox account
    used during recording. Update these placeholders after recording.
    """
    id_token_from_cassette = "<ID_TOKEN_FROM_CASSETTE>"
    nonce_from_cassette = "<NONCE_FROM_CASSETTE>"
    email_from_cassette = "<EMAIL_FROM_CASSETTE>"
    password = "testpass123!"
    username = _uniq("oauth_link")

    # Step 1 — create an email/password user whose email matches the cassette Google account
    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email_from_cassette,
            hashed_password=get_password_hash(password),
            email_verified=True,
            disabled=False,
        )
    )

    # Step 2 — POST /api/auth/oauth/google → should return link_token (email match, no existing link)
    google_resp = client.post(
        f"{settings.API_STR}/auth/oauth/google",
        json={"id_token": id_token_from_cassette, "nonce": nonce_from_cassette},
    )
    assert google_resp.status_code == 200, google_resp.text
    google_body = google_resp.json()
    assert "link_token" in google_body, f"Expected link_token, got: {list(google_body.keys())}"
    link_token = google_body["link_token"]

    # Step 3 — POST /api/auth/oauth/google/link → verifies password + creates OAuthAccount
    link_resp = client.post(
        f"{settings.API_STR}/auth/oauth/google/link",
        json={"link_token": link_token, "password": password},
    )
    assert link_resp.status_code == 200, link_resp.text
    link_body = link_resp.json()
    assert "access_token" in link_body

    # DB state: OAuthAccount row now exists for this user
    oauth = OAuthAccountRepository().get_for_user_provider(user.id, "google")
    assert oauth is not None
    assert oauth.provider == "google"
