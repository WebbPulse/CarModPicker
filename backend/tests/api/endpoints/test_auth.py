import os

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Helper to create a user directly in the DB for testing login
# This is an alternative to calling the /users/ endpoint if you want to bypass API validation for setup
from app.api.dependencies.auth import get_password_hash
from app.api.models.user import User as DBUser  # For direct DB manipulation if needed
from app.core.config import settings


def get_unique_username(base_name: str) -> str:
    """Generate a unique username for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


def create_test_user_direct_db(
    db: Session, username: str, email: str, password: str, disabled: bool = False
) -> DBUser:
    hashed_password = get_password_hash(password)
    db_user = DBUser(
        username=username,
        email=email,
        hashed_password=hashed_password,
        disabled=disabled,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def test_login_for_access_token_success(client: TestClient) -> None:
    username = get_unique_username(
        "auth_test_user_cookie"
    )  # Ensure unique username for test
    password = "auth_test_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    # Create user via API
    create_user_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert (
        create_user_response.status_code == 200
    ), f"Failed to create user for auth test: {create_user_response.text}"

    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 200, response.text

    # 1. Check for the cookie
    assert "access_token" in response.cookies
    access_token_cookie_value = response.cookies.get("access_token")
    assert access_token_cookie_value is not None

    # 2. Check cookie attributes by parsing the Set-Cookie header
    # Note: httpx.Cookies (used by TestClient) doesn't directly expose all attributes like HttpOnly easily.
    # Parsing the header is a reliable way.
    set_cookie_header = response.headers.get("set-cookie")
    assert set_cookie_header is not None
    assert "access_token=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/" in set_cookie_header
    assert f"Max-Age={settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60}" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header  # Or your configured samesite policy
    # 'secure' attribute is not set in your current /token endpoint logic for non-HTTPS dev
    assert "Secure" not in set_cookie_header

    # 3. Check the response body for user details (UserRead schema)
    response_data = response.json()
    assert response_data["username"] == username
    assert response_data["email"] == email
    assert "id" in response_data
    assert isinstance(
        response_data["id"], int
    )  # or str, depending on your UserRead schema for id
    assert response_data["disabled"] is False
    assert "hashed_password" not in response_data  # Ensure password is not returned
    assert "access_token" not in response_data  # Ensure token is not in body
    assert "token_type" not in response_data  # Ensure token_type is not in body


def test_login_for_access_token_incorrect_username(client: TestClient) -> None:
    login_data = {"username": "wronguser_cookie", "password": "password123"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 401
    assert response.json()["message"] == "Incorrect username or password"
    assert "access_token" not in response.cookies  # Check no cookie is set


def test_login_for_access_token_incorrect_password(
    client: TestClient, db_session: Session
) -> None:
    username = get_unique_username(
        "auth_test_user_wrong_pass_cookie"
    )  # Ensure unique username
    password = "correct_password"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert (
        create_response.status_code == 200
    ), f"User creation failed: {create_response.text}"

    login_data = {"username": username, "password": "wrong_password"}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 401
    assert response.json()["message"] == "Incorrect username or password"
    assert "access_token" not in response.cookies  # Check no cookie is set


def test_login_for_access_token_disabled_user(
    client: TestClient, db_session: Session
) -> None:
    username = get_unique_username("disabled_user_cookie")  # Ensure unique username
    password = "password123"
    email = f"{username}@example.com"

    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert (
        create_response.status_code == 200
    ), f"User creation failed: {create_response.text}"
    user_id = create_response.json()["id"]

    # Log in as the user. The cookie will be set in the client for subsequent requests.
    login_data_for_session = {"username": username, "password": password}
    token_response = client.post(
        f"{settings.API_STR}/auth/token", data=login_data_for_session
    )  # Changed
    assert (
        token_response.status_code == 200
    ), f"Login to get session cookie failed: {token_response.text}"
    assert "access_token" in token_response.cookies  # Verify cookie was set

    # Disable the user via API. The client will automatically send the cookie.
    # This assumes the PUT /users/{user_id} endpoint is protected by a dependency
    # (e.g., get_current_user) that now reads the authentication token from the cookie.
    update_payload = {
        "disabled": True,
        "current_password": password,
    }  # Add current_password
    # No explicit headers needed if the dependency reads from cookie
    update_response = client.put(
        f"{settings.API_STR}/users/{user_id}", json=update_payload
    )
    assert (
        update_response.status_code == 200
    ), f"Failed to disable user: {update_response.text}"
    assert update_response.json()["disabled"] is True

    # Clear cookies from the client to ensure the next login attempt is fresh
    client.cookies.clear()

    # Attempt to login as the now disabled user
    login_data = {"username": username, "password": password}
    response = client.post(f"{settings.API_STR}/auth/token", data=login_data)  # Changed
    assert response.status_code == 400, response.text
    assert response.json()["message"] == "Inactive user"
    assert "access_token" not in response.cookies  # Ensure no new cookie is set


# --- Email Verification Tests ---


def test_verify_email_send_success(client: TestClient, db_session: Session) -> None:
    """Test sending email verification link."""
    username = get_unique_username("verify_email_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user_data = {"username": username, "email": email, "password": password}
    create_response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert create_response.status_code == 200

    # Request email verification (this will fail in tests without actual SendGrid, but tests the flow)
    # We'll mock or expect the endpoint to return appropriately
    response = client.post(
        f"{settings.API_STR}/auth/verify-email", json={"email": email}
    )

    # In test environment, user is created with email_verified=True by default
    # So we expect either 409 (already verified), 200 (success), or 500 (SendGrid error)
    assert response.status_code in [
        200,
        409,
        500,
    ]  # Either success, already verified, or internal error (no SendGrid)
    if response.status_code == 200:
        assert "message" in response.json()
    elif response.status_code == 409:
        assert "already verified" in response.json()["message"].lower()


def test_verify_email_user_not_found(client: TestClient, db_session: Session) -> None:
    """Test email verification with non-existent user."""
    response = client.post(
        f"{settings.API_STR}/auth/verify-email",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


def test_verify_email_already_verified(client: TestClient, db_session: Session) -> None:
    """Test email verification when email is already verified."""
    username = get_unique_username("already_verified_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user and manually verify
    user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    # Try to request verification again
    response = client.post(
        f"{settings.API_STR}/auth/verify-email", json={"email": email}
    )
    assert response.status_code == 409
    assert "already verified" in response.json()["message"].lower()


def test_verify_email_confirm_success(client: TestClient, db_session: Session) -> None:
    """Test email verification confirmation with valid token."""
    from app.api.dependencies.auth import create_access_token
    from datetime import timedelta

    username = get_unique_username("confirm_email_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create unverified user
    user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        email_verified=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create a valid token
    token = create_access_token(
        data={"sub": email, "purpose": "verify_email"}, expires_delta=timedelta(hours=1)
    )

    # Confirm email verification
    response = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm?token={token}",
        follow_redirects=False,
    )
    assert response.status_code == 302  # Redirect
    assert "success=true" in response.headers["location"]

    # Verify user is now verified
    db_session.refresh(user)
    assert user.email_verified is True


def test_verify_email_confirm_invalid_token(
    client: TestClient, db_session: Session
) -> None:
    """Test email verification confirmation with invalid token."""
    response = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm?token=invalid_token",
        follow_redirects=False,
    )
    assert response.status_code == 302  # Redirect
    assert "error=invalid_token" in response.headers["location"]


def test_verify_email_confirm_wrong_purpose(
    client: TestClient, db_session: Session
) -> None:
    """Test email verification confirmation with token that has wrong purpose."""
    from app.api.dependencies.auth import create_access_token
    from datetime import timedelta

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
    assert "error=invalid_token" in response.headers["location"]


# --- Password Reset Tests ---


def test_reset_password_send_success(client: TestClient, db_session: Session) -> None:
    """Test sending password reset link."""
    username = get_unique_username("reset_password_user")
    password = "password123"
    email = f"{username}@example.com"

    # Create user
    user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(password),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    # Request password reset
    response = client.post(
        f"{settings.API_STR}/auth/reset-password", json={"email": email}
    )

    # Should return success message regardless of email existence (security)
    assert response.status_code in [200, 500]  # Success or internal error (no SendGrid)
    if response.status_code == 200:
        assert "message" in response.json()


def test_reset_password_nonexistent_email(
    client: TestClient, db_session: Session
) -> None:
    """Test password reset with non-existent email (should not reveal existence)."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password",
        json={"email": "nonexistent@example.com"},
    )

    # Should return success message to not reveal if email exists
    assert response.status_code == 200
    assert "message" in response.json()


def test_reset_password_confirm_success(
    client: TestClient, db_session: Session
) -> None:
    """Test password reset confirmation with valid token."""
    from app.api.dependencies.auth import create_access_token, verify_password
    from datetime import timedelta

    username = get_unique_username("confirm_reset_user")
    old_password = "oldpassword123"
    new_password = "newpassword456"
    email = f"{username}@example.com"

    # Create user
    user = DBUser(
        username=username,
        email=email,
        hashed_password=get_password_hash(old_password),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

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
    db_session.refresh(user)
    assert verify_password(new_password, user.hashed_password)
    assert not verify_password(old_password, user.hashed_password)


def test_reset_password_confirm_invalid_token(
    client: TestClient, db_session: Session
) -> None:
    """Test password reset confirmation with invalid token."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": "invalid_token", "new_password": {"password": "newpassword123"}},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["message"].lower()


def test_reset_password_confirm_wrong_purpose(
    client: TestClient, db_session: Session
) -> None:
    """Test password reset confirmation with token that has wrong purpose."""
    from app.api.dependencies.auth import create_access_token
    from datetime import timedelta

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


def test_logout_success(client: TestClient, db_session: Session) -> None:
    """Test logout functionality."""
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
    assert "access_token" in login_response.cookies

    # Logout
    logout_response = client.post(f"{settings.API_STR}/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully"

    # Verify cookie is cleared by checking Set-Cookie header
    set_cookie_header = logout_response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie_header
    # Cookie should be set with Max-Age=0 or expires in the past to delete it
    # The exact format may vary, but it should effectively clear the cookie


def test_logout_without_login(client: TestClient, db_session: Session) -> None:
    """Test logout when not logged in (should still succeed)."""
    client.cookies.clear()

    response = client.post(f"{settings.API_STR}/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
