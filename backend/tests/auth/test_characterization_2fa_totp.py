"""Characterization of TOTP enrollment and the two-factor login challenge.

Pins the status codes, response keys and the enabled flag on the user row.
"""

import os
from typing import Any

import pyotp
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_totp_enroll_and_challenge(client: TestClient, db_session: Any) -> None:
    """Flow 3: TOTP enrollment (setup + verify) and subsequent 2FA login challenge."""
    username = _uniq("totp_char")
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

    login_resp = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup_resp = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_resp.status_code == 200, setup_resp.text
    setup_body = setup_resp.json()
    assert "secret" in setup_body
    assert "qr_code_data" in setup_body
    secret = setup_body["secret"]

    user = UserRepository().get_or_raise(user.id)
    assert user.totp_secret == secret
    assert user.totp_enabled is False

    otp_code = pyotp.TOTP(secret).now()
    verify_resp = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        headers=headers,
        json={"otp": otp_code},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    verify_body = verify_resp.json()
    assert verify_body.get("success") is True

    user = UserRepository().get_or_raise(user.id)
    assert user.totp_enabled is True

    login2_resp = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert login2_resp.status_code == 200, login2_resp.text
    login2_body = login2_resp.json()
    assert login2_body.get("requires_2fa") is True
    assert "access_token" not in login2_body

    otp_code2 = pyotp.TOTP(secret).now()
    totp_login_resp = client.post(
        f"{settings.API_STR}/auth/token/2fa",
        json={"username": username, "password": password, "otp": otp_code2},
    )
    assert totp_login_resp.status_code == 200, totp_login_resp.text
    totp_body = totp_login_resp.json()
    assert "access_token" in totp_body
    assert totp_body.get("token_type") == "bearer"
