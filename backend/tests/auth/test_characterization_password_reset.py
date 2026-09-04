"""SAFE-06 flow 7: password-reset request → reset.

Asserts the 2-step password-reset flow:
  1. POST /api/auth/reset-password/confirm — token + new_password, resets hash.
  2. Login with new password succeeds (200 + access_token).
  3. Login with old password fails (401).

Per D-19: HTTP status + key presence + DB state change (hashed_password changed).

The POST /api/auth/reset-password endpoint tries to send an SES email; in the
test environment email sending is disabled and returns False, causing a 500.
We characterize the token-confirmation path directly by generating the reset
token using the same create_access_token call that auth.py uses — identical to
the pattern in tests/api/endpoints/test_auth.py::test_reset_password_confirm_success.
"""

import os
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import create_access_token, get_password_hash, verify_password
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


def _uniq(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_password_reset_request_and_confirm(client: TestClient, db_session: Session) -> None:
    """Flow 7: password reset token confirmed → password changed; old password rejected."""
    username = _uniq("pw_reset_char")
    old_password = "old_password_123!"
    new_password = "new_password_456!"
    email = f"{username}@example.com"

    # Create a verified user directly in DB
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

    # --- Generate reset token (same logic as auth.py reset_password endpoint) ---
    # The POST /api/auth/reset-password endpoint tries to send an SES email, which
    # fails in the test environment (no credentials). We generate the token directly
    # to characterize the confirmation path — the token format is the contract.
    token = create_access_token(
        data={"sub": email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    # --- Confirm reset (POST /api/auth/reset-password/confirm) ---
    confirm = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": token, "new_password": {"password": new_password}},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json().get("message") == "Password reset successfully"

    # DB: hashed_password changed
    user = UserRepository().get_or_raise(user.id)
    assert user.hashed_password != original_hash
    assert verify_password(new_password, user.hashed_password)

    # --- Login with new password succeeds ---
    login_new = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": new_password},
    )
    assert login_new.status_code == 200, login_new.text
    assert "access_token" in login_new.json()

    # --- Login with old password fails ---
    login_old = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": old_password},
    )
    assert login_old.status_code == 401, login_old.text
