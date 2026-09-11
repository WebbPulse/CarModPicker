"""Characterization of email and password login.

Pins the status code and the response keys the token endpoint returns.
"""

import os
from typing import Any

from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_login_happy_path(client: TestClient, db_session: Any) -> None:
    """Flow 2: email/password login returns access_token + user details."""
    username = _uniq("login_char")
    password = "test_password_123!"
    email = f"{username}@example.com"

    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            email_verified=True,
            disabled=False,
        )
    )

    response = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert body.get("token_type") == "bearer"
    assert "user" in body
    assert body["user"]["username"] == username
    assert body["user"]["email"] == email
    assert "hashed_password" not in body["user"]
