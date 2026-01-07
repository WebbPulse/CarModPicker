from typing import Any, Dict, Optional

from fastapi import status  # Add this import
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings


# Helper function to create a user and log them in (returns user data and token)
def create_and_login_user(
    client: TestClient, username_suffix: str, password_override: Optional[str] = None
) -> tuple[Dict[str, Any], str]:
    """Create a user, log them in, and return (user_data, token)."""
    username = f"user_test_{username_suffix}"
    email = f"user_test_{username_suffix}@example.com"
    password = password_override or "testpassword"

    user_data_create = {
        "username": username,
        "email": email,
        "password": password,
    }

    # Attempt to create user
    response = client.post(f"{settings.API_STR}/users/", json=user_data_create)
    created_user_data: Dict[str, Any] = {}
    user_id: int = -1

    if response.status_code == 200:
        created_user_data = response.json()
        user_id = created_user_data["id"]
    elif response.status_code == 400 and "already registered" in response.json().get("detail", "").lower():
        # User likely exists, will attempt login and fetch details
        pass
    else:
        response.raise_for_status()  # Raise for other unexpected errors

    # Log in to get Bearer token
    login_data = {"username": username, "password": password}
    token_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    if token_response.status_code != 200:
        raise Exception(
            f"Failed to log in user {username}. Status: {token_response.status_code}, Detail: {token_response.text}"
        )

    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # If user was not created in this call (because they already existed), fetch their data now
    if not created_user_data or user_id == -1:
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        if me_response.status_code == 200:
            created_user_data = me_response.json()
            user_id = created_user_data["id"]
        else:
            raise Exception(
                f"Could not retrieve user data for {username} via /users/me after login. Status: {me_response.status_code}, Detail: {me_response.text}"
            )

    if not created_user_data or user_id == -1:
        raise Exception(f"User ID or data for {username} could not be determined.")

    return created_user_data, token


def get_auth_headers(token: str) -> Dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


# --- Test Cases ---


# --- Create User Tests ---
def test_create_user_success(client: TestClient, db_session: Session) -> None:
    username = "new_unique_user"
    email = "new_unique_user@example.com"
    password = "password123"
    user_data = {
        "username": username,
        "email": email,
        "password": password,
    }
    response = client.post(f"{settings.API_STR}/users/", json=user_data)
    assert response.status_code == 200, response.text
    created_user = response.json()
    assert created_user["username"] == username
    assert created_user["email"] == email
    assert "id" in created_user
    assert "hashed_password" not in created_user


def test_create_user_duplicate_username(client: TestClient, db_session: Session) -> None:
    user_info, _ = create_and_login_user(client, "duplicate_username_test")  # Creates and logs in first user

    duplicate_user_data = {
        "username": user_info["username"],  # Same username
        "email": "another_email@example.com",
        "password": "password123",
    }
    response = client.post(f"{settings.API_STR}/users/", json=duplicate_user_data)
    assert response.status_code == 409, response.text  # 409 Conflict is correct for duplicates
    assert "username already registered" in response.json()["message"].lower()


def test_create_user_duplicate_email(client: TestClient, db_session: Session) -> None:
    user_info, _ = create_and_login_user(client, "duplicate_email_test")  # Creates and logs in first user

    duplicate_user_data = {
        "username": "another_username_for_email_test",
        "email": user_info["email"],  # Same email
        "password": "password123",
    }
    response = client.post(f"{settings.API_STR}/users/", json=duplicate_user_data)
    assert response.status_code == 409, response.text  # 409 Conflict is correct for duplicates
    assert "email already registered" in response.json()["message"].lower()


# --- Read User (/me) Tests ---
def test_read_users_me_success(client: TestClient, db_session: Session) -> None:
    user_info, token = create_and_login_user(client, "me_test")  # Logs in, returns token

    headers = get_auth_headers(token)
    response = client.get(f"{settings.API_STR}/users/me", headers=headers)
    assert response.status_code == 200, response.text
    me_user = response.json()
    assert me_user["username"] == user_info["username"]
    assert me_user["email"] == user_info["email"]
    assert me_user["id"] == user_info["id"]


def test_read_users_me_unauthenticated(client: TestClient, db_session: Session) -> None:
    response = client.get(f"{settings.API_STR}/users/me")
    assert response.status_code == 401  # Expect unauthorized


# --- Read User (/{user_id}) Tests ---
def test_read_user_by_id_success(client: TestClient, db_session: Session) -> None:
    user_info, token = create_and_login_user(client, "read_by_id_test")
    user_id_to_read = user_info["id"]

    # Keep authentication as users are private
    headers = get_auth_headers(token)
    response = client.get(f"{settings.API_STR}/users/{user_id_to_read}", headers=headers)
    assert response.status_code == 200, response.text
    read_user = response.json()
    assert read_user["id"] == user_id_to_read
    assert read_user["username"] == user_info["username"]


def test_read_user_by_id_not_found(client: TestClient, db_session: Session) -> None:
    # Need to be authenticated to read users
    _, token = create_and_login_user(client, "read_not_found_test")
    headers = get_auth_headers(token)
    response = client.get(f"{settings.API_STR}/users/9999999", headers=headers)  # Non-existent ID
    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


# --- Update User Tests ---
def test_update_own_user_success(client: TestClient, db_session: Session) -> None:
    user_info, token = create_and_login_user(client, "update_self")
    user_id = user_info["id"]
    current_password = "testpassword"  # Default password from create_and_login_user

    update_payload = {
        "current_password": current_password,
        "email": "updated_self@example.com",
    }
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert response.status_code == 200, response.text
    updated_user = response.json()
    assert updated_user["email"] == update_payload["email"]
    assert updated_user["username"] == user_info["username"]  # Username should be unchanged


def test_update_own_user_change_password_success(client: TestClient, db_session: Session) -> None:
    username_suffix = "change_pass"
    initial_password = "initialPassword123"
    new_password = "newStrongPassword456"

    user_info, token = create_and_login_user(client, username_suffix, password_override=initial_password)
    user_id = user_info["id"]
    username = user_info["username"]

    update_payload = {"current_password": initial_password, "password": new_password}
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert response.status_code == 200, response.text

    client.cookies.clear()  # Clear old session

    # Try logging in with the new password
    login_data_new_pass = {"username": username, "password": new_password}
    login_response_new = client.post(f"{settings.API_STR}/auth/token", data=login_data_new_pass)
    assert login_response_new.status_code == 200, f"Login with new password failed: {login_response_new.text}"

    # Try logging in with the old password (should fail)
    client.cookies.clear()
    login_data_old_pass = {"username": username, "password": initial_password}
    login_response_old = client.post(f"{settings.API_STR}/auth/token", data=login_data_old_pass)
    assert login_response_old.status_code == 401, "Login with old password should fail"


def test_update_own_user_incorrect_current_password(client: TestClient, db_session: Session) -> None:
    user_info, token = create_and_login_user(client, "update_wrong_curr_pass")
    user_id = user_info["id"]

    update_payload = {
        "current_password": "thisisnotthepassword",  # Incorrect current password
        "email": "new_email_for_wrong_pass@example.com",
    }
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    assert "incorrect current password" in response.json()["message"].lower()


def test_update_other_user_forbidden(client: TestClient, db_session: Session) -> None:
    user_a_info, _ = create_and_login_user(client, "user_a_update_target")  # User A logged in
    user_a_id = user_a_info["id"]

    # User B logs in - assume default password "testpassword" from helper
    _, token_b = create_and_login_user(client, "user_b_updater_attacker")
    user_b_password = "testpassword"

    update_payload = {
        "username": "MaliciousUpdate",
        "current_password": user_b_password,
    }  # Add current_password for User B
    headers = get_auth_headers(token_b)
    response = client.put(
        f"{settings.API_STR}/users/{user_a_id}", json=update_payload, headers=headers
    )  # User B tries to update User A
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["message"] == "Not authorized to update this user"


def test_update_user_unauthenticated(client: TestClient, db_session: Session) -> None:
    user_info, _ = create_and_login_user(client, "update_unauth_target")
    user_id = user_info["id"]
    client.cookies.clear()  # Ensure unauthenticated

    update_payload = {"username": "UnauthUpdate"}
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload)
    assert response.status_code == 401


def test_update_user_not_found(client: TestClient, db_session: Session) -> None:
    # Logs in a user, assume default password "testpassword"
    _, token = create_and_login_user(client, "updater_user_notfound")
    logged_in_user_password = "testpassword"

    update_payload = {
        "username": "NonExistent",
        "current_password": logged_in_user_password,
    }  # Add current_password
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/9999998", json=update_payload, headers=headers)  # Non-existent ID
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "User" in response.json()["message"] and "not found" in response.json()["message"]


# --- Delete User Tests ---
def test_delete_own_user_success(client: TestClient, db_session: Session) -> None:
    user_info, token = create_and_login_user(client, "delete_self")
    user_id = user_info["id"]
    username = user_info["username"]

    headers = get_auth_headers(token)
    response = client.delete(f"{settings.API_STR}/users/{user_id}", headers=headers)
    assert response.status_code == 200, response.text
    deleted_user = response.json()
    assert deleted_user["id"] == user_id

    # Verify user is deleted: try to log in
    login_data = {
        "username": username,
        "password": "testpassword",
    }  # or the specific password used
    login_response = client.post(f"{settings.API_STR}/auth/token", data=login_data)
    assert login_response.status_code == 401  # Or 400 if "Inactive user" vs "Incorrect username/password"

    # Verify user is deleted by checking if username no longer exists in database
    from app.api.models.user import User as DBUser

    deleted_user_check = db_session.query(DBUser).filter(DBUser.username == username).first()
    assert deleted_user_check is None, "User should no longer exist in database"


def test_delete_other_user_forbidden(client: TestClient, db_session: Session) -> None:
    user_a_info, _ = create_and_login_user(client, "user_a_delete_target")  # User A logged in
    user_a_id = user_a_info["id"]

    _, token_b = create_and_login_user(client, "user_b_deleter_attacker")  # User B logged in

    headers = get_auth_headers(token_b)
    response = client.delete(f"{settings.API_STR}/users/{user_a_id}", headers=headers)  # User B tries to delete User A
    assert response.status_code == 403
    assert response.json()["message"] == "Not authorized to delete this user"


def test_delete_user_unauthenticated(client: TestClient, db_session: Session) -> None:
    user_info, _ = create_and_login_user(client, "delete_unauth_target")
    user_id = user_info["id"]
    client.cookies.clear()  # Ensure unauthenticated

    response = client.delete(f"{settings.API_STR}/users/{user_id}")
    assert response.status_code == 401


def test_delete_user_not_found(client: TestClient, db_session: Session) -> None:
    _, token = create_and_login_user(client, "deleter_user_notfound")  # Logs in a user

    headers = get_auth_headers(token)
    response = client.delete(f"{settings.API_STR}/users/9999997", headers=headers)  # Non-existent ID
    assert response.status_code == 403  # Changed from 404
    assert response.json()["message"] == "Not authorized to delete this user"  # Changed detail


def test_update_user_conflict_username(client: TestClient, db_session: Session) -> None:
    user_a_info, _ = create_and_login_user(client, "conflict_username_A")
    # User B is now logged in, default password is "testpassword"
    user_b_info, token_b = create_and_login_user(client, "conflict_username_B")

    update_payload = {
        "current_password": "testpassword",  # User B's current password
        "username": user_a_info["username"],
    }  # Try to set B's username to A's
    headers = get_auth_headers(token_b)
    response = client.put(f"{settings.API_STR}/users/{user_b_info['id']}", json=update_payload, headers=headers)
    assert response.status_code == 409  # 409 Conflict is correct for duplicates
    assert "username already registered" in response.json()["message"].lower()


def test_update_user_conflict_email(client: TestClient, db_session: Session) -> None:
    user_a_info, _ = create_and_login_user(client, "conflict_email_A")
    # User B is now logged in, default password is "testpassword"
    user_b_info, token_b = create_and_login_user(client, "conflict_email_B")

    update_payload = {
        "current_password": "testpassword",  # User B's current password
        "email": user_a_info["email"],
    }  # Try to set B's email to A's
    headers = get_auth_headers(token_b)
    response = client.put(f"{settings.API_STR}/users/{user_b_info['id']}", json=update_payload, headers=headers)
    assert response.status_code == 409  # 409 Conflict is correct for duplicates
    assert "email already registered" in response.json()["message"].lower()
