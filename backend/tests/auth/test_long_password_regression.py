"""Regression: a password over bcrypt's 72 byte limit must not fault.

Multi-byte passwords pass the character cap, so they are truncated by byte before hashing.
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient

from app.api.dependencies.auth import create_access_token, get_password_hash, verify_password
from app.api.schemas.auth import PASSWORD_MAX_LENGTH
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository

OVER_LIMIT_PASSWORD = "é" * PASSWORD_MAX_LENGTH


def _uniq(base: str) -> str:
    """A name unique to this worker and process, so parallel runs do not collide."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    return f"{base}_{worker}_{os.getpid()}"


def test_the_test_password_is_the_shape_this_regression_is_about() -> None:
    """Guard the fixture itself: within the char cap, over bcrypt's byte limit."""
    assert len(OVER_LIMIT_PASSWORD) <= PASSWORD_MAX_LENGTH
    assert len(OVER_LIMIT_PASSWORD.encode("utf-8")) > 72


def test_hashing_a_password_over_72_bytes_does_not_raise() -> None:
    """The primitive itself. bcrypt 5 raised ValueError here before the swap."""
    hashed = get_password_hash(OVER_LIMIT_PASSWORD)

    assert hashed.startswith("$2")
    assert hashed.split("$")[2] == "12"
    assert verify_password(OVER_LIMIT_PASSWORD, hashed) is True


def test_a_wrong_password_still_fails_against_an_over_limit_hash() -> None:
    """Truncation must not turn verification into a rubber stamp."""
    hashed = get_password_hash(OVER_LIMIT_PASSWORD)

    assert verify_password("something else entirely", hashed) is False


def test_signup_then_login_with_a_password_over_72_bytes(client: TestClient, db_session: Any) -> None:
    """Signup 500'd on this password before the swap. Now it creates and logs in."""
    username = _uniq("longpw_signup")

    signup = client.post(
        "/api/users/",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": OVER_LIMIT_PASSWORD,
        },
    )
    assert signup.status_code == 200, signup.text

    login = client.post(
        "/api/auth/token",
        data={"username": username, "password": OVER_LIMIT_PASSWORD},
    )
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]


def test_login_rejects_a_wrong_password_on_an_over_limit_account(client: TestClient, db_session: Any) -> None:
    """The account is reachable, but only with the right password."""
    username = _uniq("longpw_wrong")

    signup = client.post(
        "/api/users/",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": OVER_LIMIT_PASSWORD,
        },
    )
    assert signup.status_code == 200, signup.text

    login = client.post(
        "/api/auth/token",
        data={"username": username, "password": "not the right password"},
    )
    assert login.status_code == 401


def test_password_reset_to_a_password_over_72_bytes(client: TestClient, db_session: Any) -> None:
    """Reset confirm 500'd on this password before the swap. Now it resets and logs in."""
    username = _uniq("longpw_reset")
    email = f"{username}@example.com"
    old_password = "old_password_123!"

    UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(old_password),
            email_verified=True,
            disabled=False,
        )
    )

    token = create_access_token(
        data={"sub": email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    confirm = client.post(
        "/api/auth/reset-password/confirm",
        json={"token": token, "new_password": {"password": OVER_LIMIT_PASSWORD}},
    )
    assert confirm.status_code == 200, confirm.text

    login = client.post(
        "/api/auth/token",
        data={"username": username, "password": OVER_LIMIT_PASSWORD},
    )
    assert login.status_code == 200, login.text

    old_login = client.post(
        "/api/auth/token",
        data={"username": username, "password": old_password},
    )
    assert old_login.status_code == 401


def test_an_ascii_password_past_the_char_cap_is_still_a_422(client: TestClient, db_session: Any) -> None:
    """Over-long ASCII is still a validation error, so the schema cap is unchanged."""
    username = _uniq("longpw_ascii")

    signup = client.post(
        "/api/users/",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "a" * (PASSWORD_MAX_LENGTH + 1),
        },
    )
    assert signup.status_code == 422
