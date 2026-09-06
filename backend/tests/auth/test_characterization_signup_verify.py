"""SAFE-06 flow 1: signup → email verification.

Asserts the 2-step flow completes end-to-end with the committed DB effects.
Per D-19 we pin HTTP status, response-key presence, and DB state change
(user created + email_verified flipped to True).

The verify-email flow in this codebase works in two steps:
  1. POST /api/users/                              — creates user (email_verified=False in prod)
  2. GET  /api/auth/verify-email/confirm?token=<jwt>  — flips email_verified=True

In the TESTING environment, /api/users/ auto-sets email_verified=True (CLAUDE.md
explains tests use TESTING=true).  To characterize the full 2-step confirmation
path we create the user directly in the DB with email_verified=False, then drive
the confirm endpoint with a real JWT token — identical to the pattern already
used in tests/api/endpoints/test_auth.py::test_verify_email_confirm_success.
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
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_signup_and_verify_email(client: TestClient, db_session: Any) -> None:
    """Flow 1: user is created unverified, then email_verified is flipped by the confirm endpoint."""
    username = _uniq("sig_verify")
    email = f"{username}@example.com"
    password = "test_password_123!"

    # --- Step 1: Create unverified user directly in DB ---
    # (In production the POST /api/users/ creates unverified users; in TESTING mode
    # it auto-verifies.  We create directly to characterize the unverified→verified transition.)
    db_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            email_verified=False,
            disabled=False,
        )
    )

    # DB: user exists; email_verified is False
    assert db_user is not None
    assert db_user.email_verified is False

    # --- Step 2: Generate verification token (same logic as auth.py verify_email endpoint) ---
    token = create_access_token(
        data={"sub": email, "purpose": "verify_email"},
        expires_delta=timedelta(hours=1),
    )

    # --- Step 3: Confirm via GET (redirects; follow_redirects=False) ---
    confirm = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm",
        params={"token": token},
        follow_redirects=False,
    )
    # The endpoint redirects to the frontend with status=success
    assert confirm.status_code == 302, confirm.text
    assert "status=success" in confirm.headers["location"]

    # DB: email_verified flipped to True
    db_user = UserRepository().get_or_raise(db_user.id)
    assert db_user.email_verified is True
