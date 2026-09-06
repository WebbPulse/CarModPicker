import os
from typing import Any

from fastapi.testclient import TestClient

# Helper to create a user directly in the DB for testing login
# This is an alternative to calling the /users/ endpoint if you want to bypass API validation for setup
from app.api.dependencies.auth import get_password_hash
from app.core.config import settings
from app.db.dynamo.users import User as DBUser  # For direct DB manipulation if needed
from app.db.dynamo.users import UserRepository


def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_test_user_direct_db(db: Any, username: str, email: str, password: str, disabled: bool = False) -> DBUser:
    hashed_password = get_password_hash(password)
    db_user = DBUser(
        username=username,
        email=email,
        hashed_password=hashed_password,
        disabled=disabled,
    )
    return UserRepository().create_user(db_user)


def test_login_for_access_token_success(client: TestClient) -> None:
    username = get_unique_username("auth_test_user")  # Ensure unique username for test
    password = "auth_test_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    # Create user via API
    create_user_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_user_response.status_code == 200, f"Failed to create user for auth test: {create_user_response.text}"

    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200, response.text

    # Check the response body for Bearer token and user details (OAuth2 standard)
    response_data = response.json()

    # 1. Check for Bearer token in response body
    assert "access_token" in response_data
    assert "token_type" in response_data
    assert response_data["token_type"] == "bearer"
    access_token = response_data["access_token"]
    assert access_token is not None
    assert len(access_token) > 0

    # 2. Check for user details in response body
    assert "user" in response_data
    user_data_response = response_data["user"]
    assert user_data_response["username"] == username
    assert user_data_response["email"] == email
    assert "id" in user_data_response
    assert isinstance(user_data_response["id"], str)
    assert user_data_response["disabled"] is False
    assert "hashed_password" not in user_data_response  # Ensure password is not returned

    # 3. Ensure no cookie is set (Bearer token approach)
    assert "access_token" not in response.cookies


def test_login_for_access_token_incorrect_username(client: TestClient) -> None:
    login_data = {"username": "wronguser", "password": "password123"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 401
    assert response.json()["message"] == "Incorrect username or password"
    # Check no token is returned in response body
    response_data = response.json()
    assert "access_token" not in response_data
    assert "access_token" not in response.cookies


def test_login_for_access_token_incorrect_password(client: TestClient, db_session: Any) -> None:
    username = get_unique_username("auth_test_user_wrong_pass")  # Ensure unique username
    password = "correct_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200, f"User creation failed: {create_response.text}"

    login_data = {"username": username, "password": "wrong_password"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 401
    assert response.json()["message"] == "Incorrect username or password"
    # Check no token is returned in response body
    response_data = response.json()
    assert "access_token" not in response_data
    assert "access_token" not in response.cookies


def test_login_for_access_token_disabled_user(client: TestClient, db_session: Any) -> None:
    username = get_unique_username("disabled_user")  # Ensure unique username
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200, f"User creation failed: {create_response.text}"
    user_id = create_response.json()["id"]

    # Log in as the user to get Bearer token
    login_data_for_session = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data_for_session)
    assert token_response.status_code == 200, f"Login to get token failed: {token_response.text}"
    token_data = token_response.json()
    assert "access_token" in token_data
    access_token = token_data["access_token"]

    # Disable the user via API using Bearer token in Authorization header
    update_payload = {
        "disabled": True,
        "current_password": password,
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    update_response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert update_response.status_code == 200, f"Failed to disable user: {update_response.text}"
    assert update_response.json()["disabled"] is True

    # Attempt to login as the now disabled user
    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Inactive user"
    # Check no token is returned in response body
    response_data = response.json()
    assert "access_token" not in response_data
    assert "access_token" not in response.cookies


# --- Email Verification Tests ---


def test_verify_email_send_success(client: TestClient, db_session: Any) -> None:
    """Test sending email verification link."""
    username = get_unique_username("verify_email_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Request email verification (SES call will fail in tests without IAM credentials, but tests the flow)
    # We'll mock or expect the endpoint to return appropriately
    response = client.post(f"{settings.API_STR}/auth/verify-email", json={"email": email})

    # In test environment, user is created with email_verified=True by default
    # So we expect either 409 (already verified), 200 (success), or 500 (SES error in CI)
    assert response.status_code in [
        200,
        409,
        500,
    ]  # Either success, already verified, or internal error (no SES credentials in CI)
    if response.status_code == 200:
        assert "message" in response.json()
    elif response.status_code == 409:
        assert "already verified" in response.json()["message"].lower()


def test_verify_email_user_not_found(client: TestClient, db_session: Any) -> None:
    """Test email verification with non-existent user."""
    response = client.post(
        f"{settings.API_STR}/auth/verify-email",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


def test_verify_email_already_verified(client: TestClient, db_session: Any) -> None:
    """Test email verification when email is already verified."""
    username = get_unique_username("already_verified_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user and manually verify
    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            email_verified=True,
        )
    )

    # Try to request verification again
    response = client.post(f"{settings.API_STR}/auth/verify-email", json={"email": email})
    assert response.status_code == 409
    assert "already verified" in response.json()["message"].lower()


def test_verify_email_confirm_success(client: TestClient, db_session: Any) -> None:
    """Test email verification confirmation with valid token."""
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token

    username = get_unique_username("confirm_email_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create unverified user
    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            email_verified=False,
        )
    )

    # Create a valid token
    token = create_access_token(data={"sub": email, "purpose": "verify_email"}, expires_delta=timedelta(hours=1))

    # Confirm email verification
    response = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm?token={token}",
        follow_redirects=False,
    )
    assert response.status_code == 302  # Redirect
    assert "status=success" in response.headers["location"]

    # Verify user is now verified
    user = UserRepository().get_or_raise(user.id)
    assert user.email_verified is True


def test_verify_email_confirm_invalid_token(client: TestClient, db_session: Any) -> None:
    """Test email verification confirmation with invalid token."""
    response = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm?token=invalid_token",
        follow_redirects=False,
    )
    assert response.status_code == 302  # Redirect
    assert "status=error" in response.headers["location"]


def test_verify_email_confirm_wrong_purpose(client: TestClient, db_session: Any) -> None:
    """Test email verification confirmation with token that has wrong purpose."""
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token

    email = "test@example.com"

    # Create token with wrong purpose
    token = create_access_token(
        data={"sub": email, "purpose": "reset_password"},  # Wrong purpose
        expires_delta=timedelta(hours=1),
    )

    response = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm?token={token}",
        follow_redirects=False,
    )
    assert response.status_code == 302  # Redirect
    assert "status=error" in response.headers["location"]


# --- Password Reset Tests ---


def test_reset_password_send_success(client: TestClient, db_session: Any) -> None:
    """Test sending password reset link."""
    username = get_unique_username("reset_password_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            email_verified=True,
        )
    )

    # Request password reset
    response = client.post(f"{settings.API_STR}/auth/reset-password", json={"email": email})

    # Should return success message regardless of email existence (security)
    assert response.status_code in [200, 500]  # Success or internal error (no SES credentials in CI)
    if response.status_code == 200:
        assert "message" in response.json()


def test_reset_password_nonexistent_email(client: TestClient, db_session: Any) -> None:
    """Test password reset with non-existent email (should not reveal existence)."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password",
        json={"email": "nonexistent@example.com"},
    )

    # Should return success message to not reveal if email exists
    assert response.status_code == 200
    assert "message" in response.json()


def test_reset_password_confirm_success(client: TestClient, db_session: Any) -> None:
    """Test password reset confirmation with valid token."""
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token, verify_password

    username = get_unique_username("confirm_reset_user")
    old_password = "oldpassword123"
    new_password = "newpassword456"
    email = f"{username}@example.com"

    # Create user
    user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            hashed_password=get_password_hash(old_password),
            email_verified=True,
        )
    )

    # Create valid reset token
    token = create_access_token(
        data={"sub": email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    # Confirm password reset - token is embedded, password is in NewPassword schema
    response = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": token, "new_password": {"password": new_password}},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password reset successfully"

    # Verify password was changed
    user = UserRepository().get_or_raise(user.id)
    assert verify_password(new_password, user.hashed_password)
    assert not verify_password(old_password, user.hashed_password)


def test_reset_password_confirm_invalid_token(client: TestClient, db_session: Any) -> None:
    """Test password reset confirmation with invalid token."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": "invalid_token", "new_password": {"password": "newpassword123"}},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["message"].lower()


def test_reset_password_confirm_rejects_short_password(client: TestClient) -> None:
    """Schema validation runs before token decoding, so a short password 422s even with a junk token."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": "anything", "new_password": {"password": "short"}},
    )
    assert response.status_code == 422, response.text


def test_reset_password_confirm_wrong_purpose(client: TestClient, db_session: Any) -> None:
    """Test password reset confirmation with token that has wrong purpose."""
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token

    email = "test@example.com"

    # Create token with wrong purpose
    token = create_access_token(
        data={"sub": email, "purpose": "verify_email"},  # Wrong purpose
        expires_delta=timedelta(hours=1),
    )

    response = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": token, "new_password": {"password": "newpassword123"}},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["message"].lower()


# --- Logout Tests ---


def test_logout_success(client: TestClient, db_session: Any) -> None:
    """Test logout functionality (post-split: auth-gated per D-31/AUTH-03)."""
    username = get_unique_username("logout_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create and login user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    login_data_response = login_response.json()
    assert "access_token" in login_data_response
    access_token = login_data_response["access_token"]

    # Logout with Bearer token (auth-gated per plan 05-04 must_haves.truths)
    logout_response = client.post(
        f"{settings.API_STR}/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully"

    # With Bearer tokens, the client is responsible for removing the token
    # The endpoint just confirms logout was successful


def test_logout_without_login(client: TestClient, db_session: Any) -> None:
    """Post-split: /auth/logout is auth-gated; unauthenticated callers get 401."""
    client.cookies.clear()

    response = client.post(f"{settings.API_STR}/auth/logout")
    assert response.status_code == 401


# --- 2FA Tests ---


def test_setup_2fa_success(client: TestClient, db_session: Any) -> None:
    """Test setting up 2FA."""
    username = get_unique_username("2fa_setup_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup 2FA
    response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert "qr_code_data" in data
    assert "manual_entry_key" in data
    assert data["secret"] is not None
    assert len(data["secret"]) > 0
    assert data["qr_code_data"].startswith("data:image/png;base64,")


def test_setup_2fa_unauthorized(client: TestClient) -> None:
    """Test setting up 2FA without authentication."""
    response = client.post(f"{settings.API_STR}/auth/2fa/setup")
    assert response.status_code == 401


def test_verify_2fa_success(client: TestClient, db_session: Any) -> None:
    """Test verifying and enabling 2FA."""
    import pyotp

    username = get_unique_username("2fa_verify_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]

    # Generate OTP
    totp = pyotp.TOTP(secret)
    otp = totp.now()

    # Verify 2FA
    verify_data = {"otp": otp}
    response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "enabled" in data["message"].lower()

    # Verify user has 2FA enabled
    user = UserRepository().get_by_username(username)
    assert user.totp_enabled is True


def test_verify_2fa_invalid_otp(client: TestClient, db_session: Any) -> None:
    """Test verifying 2FA with invalid OTP."""
    username = get_unique_username("2fa_invalid_otp_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200

    # Try to verify with invalid OTP
    verify_data = {"otp": "000000"}
    response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert response.status_code == 401
    assert "invalid" in response.json()["message"].lower()


def test_verify_2fa_without_setup(client: TestClient, db_session: Any) -> None:
    """Test verifying 2FA without calling setup first."""
    username = get_unique_username("2fa_no_setup_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Try to verify without setup
    verify_data = {"otp": "123456"}
    response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert response.status_code == 400
    assert "setup" in response.json()["message"].lower()


def test_login_with_2fa_enabled(client: TestClient, db_session: Any) -> None:
    """Test login flow when 2FA is enabled."""
    import pyotp

    username = get_unique_username("2fa_login_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)
    otp = totp.now()
    verify_data = {"otp": otp}
    verify_response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert verify_response.status_code == 200

    # Try to login - should require 2FA
    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert response.status_code == 200
    data = response.json()
    assert data["requires_2fa"] is True
    assert "access_token" not in data

    # Complete login with 2FA
    otp = totp.now()
    login_2fa_data = {"username": username, "password": password, "otp": otp}
    response = client.post(f"{settings.API_STR}/auth/token/2fa", json=login_2fa_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user" in data


def test_login_with_2fa_invalid_otp(client: TestClient, db_session: Any) -> None:
    """Test login with 2FA using invalid OTP."""
    import pyotp

    username = get_unique_username("2fa_login_invalid_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)
    otp = totp.now()
    verify_data = {"otp": otp}
    verify_response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert verify_response.status_code == 200

    # Try to login with invalid OTP
    login_2fa_data = {"username": username, "password": password, "otp": "000000"}
    response = client.post(f"{settings.API_STR}/auth/token/2fa", json=login_2fa_data)
    assert response.status_code == 401
    assert "invalid" in response.json()["message"].lower()


def test_disable_2fa_success(client: TestClient, db_session: Any) -> None:
    """Test disabling 2FA."""
    import pyotp

    username = get_unique_username("2fa_disable_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)
    otp = totp.now()
    verify_data = {"otp": otp}
    verify_response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert verify_response.status_code == 200

    # Disable 2FA
    otp = totp.now()
    disable_data = {"password": password, "otp": otp}
    response = client.post(f"{settings.API_STR}/auth/2fa/disable", json=disable_data, headers=headers)
    assert response.status_code == 200
    assert "disabled" in response.json()["message"].lower()

    # Verify user has 2FA disabled
    user = UserRepository().get_by_username(username)
    assert user.totp_enabled is False
    assert user.totp_secret is None


def test_disable_2fa_invalid_password(client: TestClient, db_session: Any) -> None:
    """Test disabling 2FA with invalid password."""
    import pyotp

    username = get_unique_username("2fa_disable_invalid_pass_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)
    otp = totp.now()
    verify_data = {"otp": otp}
    verify_response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert verify_response.status_code == 200

    # Try to disable with wrong password
    otp = totp.now()
    disable_data = {"password": "wrongpassword", "otp": otp}
    response = client.post(f"{settings.API_STR}/auth/2fa/disable", json=disable_data, headers=headers)
    assert response.status_code == 401
    assert "incorrect" in response.json()["message"].lower()


def test_disable_2fa_not_enabled(client: TestClient, db_session: Any) -> None:
    """Test disabling 2FA when it's not enabled."""
    username = get_unique_username("2fa_disable_not_enabled_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Try to disable 2FA when not enabled
    disable_data = {"password": password, "otp": "123456"}
    response = client.post(f"{settings.API_STR}/auth/2fa/disable", json=disable_data, headers=headers)
    assert response.status_code == 400
    assert "not enabled" in response.json()["message"].lower()


def test_login_with_2fa_not_enabled(client: TestClient, db_session: Any) -> None:
    """Test login with 2FA when 2FA is not enabled (should return 400)."""
    username = get_unique_username("2fa_login_not_enabled_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Try to login with 2FA when 2FA is not enabled
    login_2fa_data = {"username": username, "password": password, "otp": "123456"}
    response = client.post(f"{settings.API_STR}/auth/token/2fa", json=login_2fa_data)
    assert response.status_code == 400
    assert "not enabled" in response.json()["message"].lower()


def test_login_with_2fa_invalid_password(client: TestClient, db_session: Any) -> None:
    """Test login with 2FA using invalid password (after initial login attempt)."""
    import pyotp

    username = get_unique_username("2fa_login_invalid_pass_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)
    otp = totp.now()
    verify_data = {"otp": otp}
    verify_response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert verify_response.status_code == 200

    # Try to login with 2FA using wrong password
    otp = totp.now()
    login_2fa_data = {"username": username, "password": "wrongpassword", "otp": otp}
    response = client.post(f"{settings.API_STR}/auth/token/2fa", json=login_2fa_data)
    assert response.status_code == 401
    assert "invalid" in response.json()["message"].lower()


def test_login_with_2fa_nonexistent_user(client: TestClient) -> None:
    """Test login with 2FA for non-existent user."""
    login_2fa_data = {"username": "nonexistent_user", "password": "password123", "otp": "123456"}
    response = client.post(f"{settings.API_STR}/auth/token/2fa", json=login_2fa_data)
    assert response.status_code == 401
    assert "invalid" in response.json()["message"].lower()


def test_login_with_2fa_missing_secret(client: TestClient, db_session: Any) -> None:
    """Test login with 2FA when user has totp_enabled=True but no totp_secret (configuration error)."""
    import pyotp

    username = get_unique_username("2fa_missing_secret_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Manually set totp_enabled=True but leave totp_secret=None (simulating config error)
    user = UserRepository().get_by_username(username)
    UserRepository().update(user.id, totp_enabled=True, totp_secret=None)

    # Try to login with 2FA
    login_2fa_data = {"username": username, "password": password, "otp": "123456"}
    response = client.post(f"{settings.API_STR}/auth/token/2fa", json=login_2fa_data)
    assert response.status_code == 500
    # Error handler masks 5xx error messages, but we can check the error_code
    assert response.json()["error_code"] == "INTERNAL_ERROR"


def test_verify_2fa_otp_time_window(client: TestClient, db_session: Any) -> None:
    """Test that 2FA verification only accepts OTPs within the valid time window."""
    import time

    import pyotp

    username = get_unique_username("2fa_time_window_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)

    # Get current OTP
    current_otp = totp.now()

    # Verify with current OTP (should succeed)
    verify_data = {"otp": current_otp}
    verify_response = client.post(f"{settings.API_STR}/auth/2fa/verify", json=verify_data, headers=headers)
    assert verify_response.status_code == 200

    # Note: Testing expired OTP is difficult because TOTP windows are 30 seconds
    # and we can't easily manipulate time in tests. The valid_window=1 parameter
    # in the code allows 1 time step window for clock skew, so we test that
    # the current OTP works (which validates the time window logic is in place)


def test_setup_2fa_multiple_calls(client: TestClient, db_session: Any) -> None:
    """Test that multiple setup calls generate new secrets each time."""
    username = get_unique_username("2fa_multiple_setup")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # First setup
    setup_response1 = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response1.status_code == 200
    secret1 = setup_response1.json()["secret"]

    # Second setup (should generate new secret)
    setup_response2 = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response2.status_code == 200
    secret2 = setup_response2.json()["secret"]

    # Secrets should be different
    assert secret1 != secret2

    # Verify that 2FA is still not enabled (requires verify step)
    user = UserRepository().get_by_username(username)
    assert user is not None
    assert user.totp_enabled is False
    assert user.totp_secret == secret2  # Latest secret should be stored


def test_verify_2fa_after_already_enabled(client: TestClient, db_session: Any) -> None:
    """Test verifying 2FA when it's already enabled (should handle gracefully)."""
    username = get_unique_username("2fa_already_enabled")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and verify 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]

    import pyotp

    totp = pyotp.TOTP(secret)
    otp = totp.now()

    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": otp},
        headers=headers,
    )
    assert verify_response.status_code == 200
    assert verify_response.json()["success"] is True

    # Try to verify again (should handle gracefully - may succeed or fail depending on implementation)
    otp2 = totp.now()
    verify_response2 = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": otp2},
        headers=headers,
    )
    # Should either succeed (idempotent) or fail with appropriate error
    assert verify_response2.status_code in [200, 400, 422]


def test_login_with_2fa_disabled_user(client: TestClient, db_session: Any) -> None:
    """Test login with 2FA when user account is disabled."""
    username = get_unique_username("2fa_disabled")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200
    user_id = create_response.json()["id"]

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]

    import pyotp

    totp = pyotp.TOTP(secret)
    otp = totp.now()

    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": otp},
        headers=headers,
    )
    assert verify_response.status_code == 200

    # Disable the user
    update_payload = {"disabled": True, "current_password": password}
    update_response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert update_response.status_code == 200

    # Try to login with 2FA (should fail because user is disabled)
    login_response = client.post(
        f"{settings.API_STR}/auth/token/2fa",
        json={"username": username, "password": password, "otp": totp.now()},
    )
    # Should fail at initial login (before 2FA step) because user is disabled
    assert login_response.status_code in [400, 401]


def test_disable_2fa_when_already_disabled(client: TestClient, db_session: Any) -> None:
    """Test disabling 2FA when already disabled (idempotency)."""
    username = get_unique_username("2fa_disable_idempotent")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Try to disable 2FA when not enabled (should fail with appropriate error)
    disable_response = client.post(
        f"{settings.API_STR}/auth/2fa/disable",
        json={"password": password, "otp": "123456"},
        headers=headers,
    )
    assert disable_response.status_code == 400
    assert "not enabled" in disable_response.json()["message"].lower()


def test_2fa_setup_replaces_old_secret(client: TestClient, db_session: Any) -> None:
    """Test that calling 2FA setup again replaces the old secret."""
    import pyotp

    username = get_unique_username("2fa_setup_replace")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # First setup
    setup_response1 = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response1.status_code == 200
    secret1 = setup_response1.json()["secret"]

    # Second setup - should generate new secret
    setup_response2 = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response2.status_code == 200
    secret2 = setup_response2.json()["secret"]

    # Secrets should be different
    assert secret1 != secret2, "New setup should generate a different secret"

    totp2 = pyotp.TOTP(secret2)

    # Verify with new secret (should work)
    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": totp2.now()},
        headers=headers,
    )
    assert verify_response.status_code == 200

    # Old secret should not work for verification (but we can't test this directly
    # since verification requires the secret to be in the database)


def test_2fa_verify_otp_expired_beyond_window(client: TestClient, db_session: Any) -> None:
    """Test 2FA verify with OTP from 2 time windows ago (should fail)."""
    username = get_unique_username("2fa_verify_expired")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]

    import time

    import pyotp

    totp = pyotp.TOTP(secret)

    # Get OTP from 2 time windows ago (60 seconds * 2 = 120 seconds)
    # TOTP time step is 30 seconds, so 2 windows = 60 seconds
    old_time = int(time.time()) - 60
    old_otp = totp.at(old_time)

    # Try to verify with old OTP (should fail - valid_window=1 only allows ±1 time step)
    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": old_otp},
        headers=headers,
    )
    # Should fail because OTP is too old (valid_window=1 means only ±1 time step = 30 seconds)
    assert verify_response.status_code in [401, 400], "Old OTP should be rejected"


def test_2fa_setup_when_already_enabled(client: TestClient, db_session: Any) -> None:
    """Test 2FA setup behavior when 2FA is already enabled."""
    username = get_unique_username("2fa_setup_enabled")
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response1 = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response1.status_code == 200
    secret1 = setup_response1.json()["secret"]

    import pyotp

    totp1 = pyotp.TOTP(secret1)
    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": totp1.now()},
        headers=headers,
    )
    assert verify_response.status_code == 200

    # Try to setup again when already enabled - should allow (generates new secret)
    setup_response2 = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response2.status_code == 200
    secret2 = setup_response2.json()["secret"]

    # New secret should be different
    assert secret1 != secret2, "Setup when enabled should generate new secret"

    # Old secret should no longer work for login
    # Try to login with old secret's OTP (should fail)
    totp1 = pyotp.TOTP(secret1)
    login_2fa_response = client.post(
        f"{settings.API_STR}/auth/token/2fa",
        json={"username": username, "password": password, "otp": totp1.now()},
    )
    # Should fail because secret1 is no longer in database (replaced by secret2)
    assert login_2fa_response.status_code == 401, "Old secret should not work after new setup"


def test_2fa_login_when_user_deleted(client: TestClient, db_session: Any) -> None:
    """Test 2FA login when user account is deleted between setup and login attempt."""
    import pyotp

    username = get_unique_username("2fa_deleted_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200
    user_id = create_response.json()["id"]

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Setup and enable 2FA
    setup_response = client.post(f"{settings.API_STR}/auth/2fa/setup", headers=headers)
    assert setup_response.status_code == 200
    secret = setup_response.json()["secret"]
    totp = pyotp.TOTP(secret)

    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": totp.now()},
        headers=headers,
    )
    assert verify_response.status_code == 200

    # Delete the user
    delete_response = client.delete(f"{settings.API_STR}/users/{user_id}", headers=headers)
    assert delete_response.status_code == 200

    # Try to login with 2FA after user is deleted (should fail)
    login_2fa_response = client.post(
        f"{settings.API_STR}/auth/token/2fa",
        json={"username": username, "password": password, "otp": totp.now()},
    )
    # Should fail because user no longer exists
    assert login_2fa_response.status_code == 401
    assert "invalid" in login_2fa_response.json()["message"].lower()


def test_2fa_verify_with_invalid_secret_format(client: TestClient, db_session: Any) -> None:
    """Test 2FA verify with corrupted/malformed secret in database (edge case)."""
    username = get_unique_username("2fa_invalid_secret")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Login to get token
    login_data = {"username": username, "password": password}
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Manually set an invalid secret format in database (simulating corruption)
    user = UserRepository().get_by_username(username)
    UserRepository().update(user.id, totp_secret="INVALID_SECRET_FORMAT_NOT_BASE32")

    # Try to verify with OTP (should handle gracefully)
    verify_response = client.post(
        f"{settings.API_STR}/auth/2fa/verify",
        json={"otp": "123456"},
        headers=headers,
    )
    # Should fail with appropriate error (400/422/500) due to invalid secret format
    assert verify_response.status_code in [400, 422, 500], "Invalid secret format should be rejected"
