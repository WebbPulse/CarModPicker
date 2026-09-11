"""Characterization of the password reset confirmation flow.

Drives the confirm endpoint directly, since sending the reset email is disabled in tests.
"""

import os
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.api.dependencies.auth import create_access_token, get_password_hash, verify_password
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_password_reset_request_and_confirm(client: TestClient, db_session: Any) -> None:
    """Flow 7: password reset token confirmed → password changed; old password rejected."""
    username = _uniq("pw_reset_char")
    old_password = "old_password_123!"
    new_password = "new_password_456!"
    email = f"{username}@example.com"

    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(old_password),
            email_verified=True,
            disabled=False,
        )
    )
    original_hash = user.hashed_password

    token = create_access_token(
        data={"sub": email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    confirm = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": token, "new_password": {"password": new_password}},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json().get("message") == "Password reset successfully"

    user = UserRepository().get_or_raise(user.id)
    assert user.hashed_password != original_hash
    assert verify_password(new_password, user.hashed_password)

    login_new = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": new_password},
    )
    assert login_new.status_code == 200, login_new.text
    assert "access_token" in login_new.json()

    login_old = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": old_password},
    )
    assert login_old.status_code == 401, login_old.text
