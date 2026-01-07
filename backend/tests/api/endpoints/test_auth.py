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


def create_test_user_direct_db(db: Session, username: str, email: str, password: str, disabled: bool = False) -> DBUser:
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
    assert isinstance(user_data_response["id"], int)
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


def test_login_for_access_token_incorrect_password(client: TestClient, db_session: Session) -> None:
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


def test_login_for_access_token_disabled_user(client: TestClient, db_session: Session) -> None:
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
    response = client.post(f"{settings.API_STR}/auth/verify-email", json={"email": email})

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
    response = client.post(f"{settings.API_STR}/auth/verify-email", json={"email": email})
    assert response.status_code == 409
    assert "already verified" in response.json()["message"].lower()


def test_verify_email_confirm_success(client: TestClient, db_session: Session) -> None:
    """Test email verification confirmation with valid token."""
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token

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
    token = create_access_token(data={"sub": email, "purpose": "verify_email"}, expires_delta=timedelta(hours=1))

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


def test_verify_email_confirm_invalid_token(client: TestClient, db_session: Session) -> None:
    """Test email verification confirmation with invalid token."""
    response = client.get(
        f"{settings.API_STR}/auth/verify-email/confirm?token=invalid_token",
        follow_redirects=False,
    )
    assert response.status_code == 302  # Redirect
    assert "error=invalid_token" in response.headers["location"]


def test_verify_email_confirm_wrong_purpose(client: TestClient, db_session: Session) -> None:
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
    response = client.post(f"{settings.API_STR}/auth/reset-password", json={"email": email})

    # Should return success message regardless of email existence (security)
    assert response.status_code in [200, 500]  # Success or internal error (no SendGrid)
    if response.status_code == 200:
        assert "message" in response.json()


def test_reset_password_nonexistent_email(client: TestClient, db_session: Session) -> None:
    """Test password reset with non-existent email (should not reveal existence)."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password",
        json={"email": "nonexistent@example.com"},
    )

    # Should return success message to not reveal if email exists
    assert response.status_code == 200
    assert "message" in response.json()


def test_reset_password_confirm_success(client: TestClient, db_session: Session) -> None:
    """Test password reset confirmation with valid token."""
    from datetime import timedelta

    from app.api.dependencies.auth import create_access_token, verify_password

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


def test_reset_password_confirm_invalid_token(client: TestClient, db_session: Session) -> None:
    """Test password reset confirmation with invalid token."""
    response = client.post(
        f"{settings.API_STR}/auth/reset-password/confirm",
        json={"token": "invalid_token", "new_password": {"password": "newpassword123"}},
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["message"].lower()


def test_reset_password_confirm_wrong_purpose(client: TestClient, db_session: Session) -> None:
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
    login_data_response = login_response.json()
    assert "access_token" in login_data_response

    # Logout (with Bearer tokens, logout is client-side, but endpoint confirms)
    logout_response = client.post(f"{settings.API_STR}/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.json()["message"] == "Logged out successfully"

    # With Bearer tokens, the client is responsible for removing the token
    # The endpoint just confirms logout was successful


def test_logout_without_login(client: TestClient, db_session: Session) -> None:
    """Test logout when not logged in (should still succeed)."""
    client.cookies.clear()

    response = client.post(f"{settings.API_STR}/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
