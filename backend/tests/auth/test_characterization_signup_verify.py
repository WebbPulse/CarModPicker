"""Characterization of signup followed by email verification.

The user is created unverified directly, since signup auto-verifies in tests.
"""

import os
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.api.dependencies.auth import create_access_token, get_password_hash
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_signup_and_verify_email(client: TestClient, db_session: Any) -> None:
    """Flow 1: user is created unverified, then email_verified is flipped by the confirm endpoint."""
    username = _uniq("sig_verify")
    email = f"{username}@example.com"
    password = "test_password_123!"

    db_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            email_verified=False,
            disabled=False,
        )
    )

    assert db_user is not None
    assert db_user.email_verified is False

    token = create_access_token(
        data={"sub": email, "purpose": "verify_email"},
        expires_delta=timedelta(hours=1),
    )

    confirm = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm",
        params={"token": token},
        follow_redirects=False,
    )
    assert confirm.status_code == 302, confirm.text
    assert "status=success" in confirm.headers["location"]

    db_user = UserRepository().get_or_raise(db_user.id)
    assert db_user.email_verified is True
