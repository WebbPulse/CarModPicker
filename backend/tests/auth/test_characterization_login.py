"""SAFE-06 flow 2: email/password login.

Asserts the login endpoint returns an access token and correct user details.
Per D-19: HTTP status + response-key presence.  No DB state change (login
is read-only).

Pattern lifted from tests/api/endpoints/test_auth.py::test_login_for_access_token_success
and adapted to the SAFE-06 characterization shape.
"""

import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
from app.core.config import settings


def _uniq(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_login_happy_path(client: TestClient, db_session: Session) -> None:
    """Flow 2: email/password login returns access_token + user details."""
    username = _uniq("login_char")
    password = "test_password_123!"
    email = f"{username}@example.com"

    # Create a verified user directly in DB (avoids needing to go through
    # the signup → verify-email flow here; that is covered by flow 1)
    user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        email_verified=True,
        disabled=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # POST form-encoded credentials (OAuth2PasswordRequestForm)
    response = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )

    # D-19: status + key presence
    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert body.get("token_type") == "bearer"
    assert "user" in body
    assert body["user"]["username"] == username
    assert body["user"]["email"] == email
    # Security: hashed_password must never appear in login response
    assert "hashed_password" not in body["user"]
