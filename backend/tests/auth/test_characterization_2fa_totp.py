"""SAFE-06 flow 3: 2FA-TOTP enrollment + challenge.

Asserts the TOTP enrollment round-trip:
  1. POST /api/auth/2fa/setup   — generates a TOTP secret for the logged-in user.
  2. POST /api/auth/2fa/verify  — verifies the OTP and flips totp_enabled=True.
  3. POST /api/auth/token       — login now returns requires_2fa=True (not a token).
  4. POST /api/auth/token/2fa   — complete login with username + password + OTP.

Per D-19: HTTP status + key presence + DB state change (totp_enabled flipped to True).
"""

import os

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser
from app.core.config import settings


def _uniq(base: str) -> str:
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_totp_enroll_and_challenge(client: TestClient, db_session: Session) -> None:
    """Flow 3: TOTP enrollment (setup + verify) and subsequent 2FA login challenge."""
    username = _uniq("totp_char")
    password = "test_password_123!"
    email = f"{username}@example.com"

    # Create a verified user directly in DB
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

    # --- Login to get Bearer token ---
    login_resp = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # --- Step 1: TOTP setup (POST /api/auth/2fa/setup) ---
    setup_resp = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_resp.status_code == 200, setup_resp.text
    setup_body = setup_resp.json()
    assert "secret" in setup_body
    assert "qr_code_data" in setup_body
    secret = setup_body["secret"]

    # DB: secret stored, but totp_enabled still False
    db_session.refresh(user)
    assert user.totp_secret == secret
    assert user.totp_enabled is False

    # --- Step 2: TOTP verify (POST /api/auth/2fa/verify) ---
    otp_code = pyotp.TOTP(secret).now()
    verify_resp = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        headers=headers,
        json={"otp": otp_code},
    )
    assert verify_resp.status_code == 200, verify_resp.text
    verify_body = verify_resp.json()
    assert verify_body.get("success") is True

    # DB: totp_enabled flipped to True
    db_session.refresh(user)
    assert user.totp_enabled is True

    # --- Step 3: Login now returns requires_2fa (not a token) ---
    login2_resp = client.post(
        f"{settings.API_STR}/auth/token",
        data={"username": username, "password": password},
    )
    assert login2_resp.status_code == 200, login2_resp.text
    login2_body = login2_resp.json()
    assert login2_body.get("requires_2fa") is True
    assert "access_token" not in login2_body

    # --- Step 4: Complete 2FA login (POST /api/auth/token/2fa) ---
    otp_code2 = pyotp.TOTP(secret).now()
    totp_login_resp = client.post(
        f"{settings.API_STR}/auth/token/2fa",
        json={"username": username, "password": password, "otp": otp_code2},
    )
    assert totp_login_resp.status_code == 200, totp_login_resp.text
    totp_body = totp_login_resp.json()
    assert "access_token" in totp_body
    assert totp_body.get("token_type") == "bearer"
