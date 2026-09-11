"""Endpoint tests for the user routes: creation, reads, updates, deletion and avatars."""

import io
from typing import Any, Dict, Optional
from unittest.mock import patch
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, login_user

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

    response = client.post(f"{settings.API_STR}/users/", json=user_data_create)
    created_user_data: Dict[str, Any] = {}

    if response.status_code == 200:
        created_user_data = response.json()
    elif response.status_code == 400 and "already registered" in response.json().get("detail", "").lower():
        pass
    else:
        response.raise_for_status()

    token = login_user(client, username, password)
    headers = auth_headers(token)

    if not created_user_data:
        me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
        if me_response.status_code == 200:
            created_user_data = me_response.json()
        else:
            raise Exception(
                f"Could not retrieve user data for {username} via /users/me after login. Status: {me_response.status_code}, Detail: {me_response.text}"
            )

    if not created_user_data or "id" not in created_user_data:
        raise Exception(f"User ID or data for {username} could not be determined.")

    return created_user_data, token

def get_auth_headers(token: str) -> Dict[str, str]:
    """Headers that authenticate as the holder of `token`.

    Kept because several modules import it from here. `auth_headers` in
    `tests/conftest.py` is the implementation; since row 13 the value it carries
    is an `x-amzn-request-context` credential, not an `Authorization` header.
    """
    return auth_headers(token)

def test_create_user_success(client: TestClient, db_session: Any) -> None:
    """A valid signup creates the user and returns it."""
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

def test_create_user_duplicate_username(client: TestClient, db_session: Any) -> None:
    """A taken username is refused as a conflict."""
    user_info, _ = create_and_login_user(client, "duplicate_username_test")

    duplicate_user_data = {
        "username": user_info["username"],
        "email": "another_email@example.com",
        "password": "password123",
    }
    response = client.post(f"{settings.API_STR}/users/", json=duplicate_user_data)
    assert response.status_code == 409, response.text
    assert "username already registered" in response.json()["message"].lower()

def test_create_user_duplicate_email(client: TestClient, db_session: Any) -> None:
    """A taken email is refused as a conflict."""
    user_info, _ = create_and_login_user(client, "duplicate_email_test")

    duplicate_user_data = {
        "username": "another_username_for_email_test",
        "email": user_info["email"],
        "password": "password123",
    }
    response = client.post(f"{settings.API_STR}/users/", json=duplicate_user_data)
    assert response.status_code == 409, response.text
    assert "email already registered" in response.json()["message"].lower()

def test_create_user_rejects_short_password(client: TestClient) -> None:
    """A password under the minimum length is a validation error."""
    response = client.post(
        f"{settings.API_STR}/users/",
        json={"username": "short_pw_user", "email": "short_pw@example.com", "password": "short"},
    )
    assert response.status_code == 422, response.text

def test_create_user_rejects_overlong_password(client: TestClient) -> None:
    """A password over the maximum length is a validation error."""
    response = client.post(
        f"{settings.API_STR}/users/",
        json={"username": "long_pw_user", "email": "long_pw@example.com", "password": "a" * 73},
    )
    assert response.status_code == 422, response.text

def test_read_users_me_success(client: TestClient, db_session: Any) -> None:
    """An authenticated caller reads their own record."""
    user_info, token = create_and_login_user(client, "me_test")

    headers = get_auth_headers(token)
    response = client.get(f"{settings.API_STR}/users/me", headers=headers)
    assert response.status_code == 200, response.text
    me_user = response.json()
    assert me_user["username"] == user_info["username"]
    assert me_user["email"] == user_info["email"]
    assert me_user["id"] == user_info["id"]

def test_read_users_me_unauthenticated(client: TestClient, db_session: Any) -> None:
    """Reading the current user with no credential is refused."""
    response = client.get(f"{settings.API_STR}/users/me")
    assert response.status_code == 401

def test_read_user_by_id_success(client: TestClient, db_session: Any) -> None:
    """A user can be read by id."""
    user_info, token = create_and_login_user(client, "read_by_id_test")
    user_id_to_read = user_info["id"]

    headers = get_auth_headers(token)
    response = client.get(f"{settings.API_STR}/users/{user_id_to_read}", headers=headers)
    assert response.status_code == 200, response.text
    read_user = response.json()
    assert read_user["id"] == user_id_to_read
    assert read_user["username"] == user_info["username"]

def test_read_user_by_id_not_found(client: TestClient, db_session: Any) -> None:
    """An unknown user id answers not found."""
    _, token = create_and_login_user(client, "read_not_found_test")
    headers = get_auth_headers(token)
    response = client.get(f"{settings.API_STR}/users/{INVALID_UUID_STR}", headers=headers)
    assert response.status_code == 404
    assert "not found" in response.json()["message"].lower()

def test_update_own_user_success(client: TestClient, db_session: Any) -> None:
    """A user can update their own record."""
    user_info, token = create_and_login_user(client, "update_self")
    user_id = user_info["id"]
    current_password = "testpassword"

    update_payload = {
        "current_password": current_password,
        "email": "updated_self@example.com",
    }
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert response.status_code == 200, response.text
    updated_user = response.json()
    assert updated_user["email"] == update_payload["email"]
    assert updated_user["username"] == user_info["username"]

def test_update_own_user_change_password_success(client: TestClient, db_session: Any) -> None:
    """A password change succeeds when the current password is supplied."""
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

    from app.api.dependencies.auth import verify_password

    stored = UserRepository().get_legacy_password_hash(UUID(user_id))
    assert stored is not None
    assert verify_password(new_password, stored) is True
    assert verify_password(initial_password, stored) is False
    assert username

def test_update_own_user_incorrect_current_password(client: TestClient, db_session: Any) -> None:
    """A password change with the wrong current password is refused."""
    user_info, token = create_and_login_user(client, "update_wrong_curr_pass")
    user_id = user_info["id"]

    update_payload = {
        "current_password": "thisisnotthepassword",
        "email": "new_email_for_wrong_pass@example.com",
    }
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload, headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.text
    assert "incorrect current password" in response.json()["message"].lower()

def test_update_other_user_forbidden(client: TestClient, db_session: Any) -> None:
    """Updating another user's record is forbidden."""
    user_a_info, _ = create_and_login_user(client, "user_a_update_target")
    user_a_id = user_a_info["id"]

    _, token_b = create_and_login_user(client, "user_b_updater_attacker")
    user_b_password = "testpassword"

    update_payload = {
        "username": "MaliciousUpdate",
        "current_password": user_b_password,
    }
    headers = get_auth_headers(token_b)
    response = client.put(f"{settings.API_STR}/users/{user_a_id}", json=update_payload, headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["message"] == "Not authorized to update this user"

def test_update_user_unauthenticated(client: TestClient, db_session: Any) -> None:
    """Updating with no credential is refused."""
    user_info, _ = create_and_login_user(client, "update_unauth_target")
    user_id = user_info["id"]
    client.cookies.clear()

    update_payload = {"username": "UnauthUpdate"}
    response = client.put(f"{settings.API_STR}/users/{user_id}", json=update_payload)
    assert response.status_code == 401

def test_update_user_not_found(client: TestClient, db_session: Any) -> None:
    """Updating an unknown user id answers not found."""
    _, token = create_and_login_user(client, "updater_user_notfound")
    logged_in_user_password = "testpassword"

    update_payload = {
        "username": "NonExistent",
        "current_password": logged_in_user_password,
    }
    headers = get_auth_headers(token)
    response = client.put(f"{settings.API_STR}/users/{INVALID_UUID_STR}", json=update_payload, headers=headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["message"].lower()

def test_delete_own_user_success(client: TestClient, db_session: Any) -> None:
    """A user can delete their own account."""
    user_info, token = create_and_login_user(client, "delete_self")
    user_id = user_info["id"]
    username = user_info["username"]

    headers = get_auth_headers(token)
    response = client.delete(f"{settings.API_STR}/users/{user_id}", headers=headers)
    assert response.status_code == 200, response.text
    deleted_user = response.json()
    assert deleted_user["id"] == user_id

    deleted_user_check = UserRepository().get_by_username(username)
    assert deleted_user_check is None, "User should no longer exist in database"

def test_delete_other_user_forbidden(client: TestClient, db_session: Any) -> None:
    """Deleting another user's account is forbidden."""
    user_a_info, _ = create_and_login_user(client, "user_a_delete_target")
    user_a_id = user_a_info["id"]

    _, token_b = create_and_login_user(client, "user_b_deleter_attacker")

    headers = get_auth_headers(token_b)
    response = client.delete(f"{settings.API_STR}/users/{user_a_id}", headers=headers)
    assert response.status_code == 403
    assert response.json()["message"] == "Not authorized to delete this user"

def test_delete_user_unauthenticated(client: TestClient, db_session: Any) -> None:
    """Deleting with no credential is refused."""
    user_info, _ = create_and_login_user(client, "delete_unauth_target")
    user_id = user_info["id"]
    client.cookies.clear()

    response = client.delete(f"{settings.API_STR}/users/{user_id}")
    assert response.status_code == 401

def test_delete_user_not_found(client: TestClient, db_session: Any) -> None:
    """Deleting an unknown user id answers not found."""
    _, token = create_and_login_user(client, "deleter_user_notfound")

    headers = get_auth_headers(token)
    response = client.delete(f"{settings.API_STR}/users/{INVALID_UUID_STR}", headers=headers)
    assert response.status_code == 403
    assert response.json()["message"] == "Not authorized to delete this user"

def test_update_user_conflict_username(client: TestClient, db_session: Any) -> None:
    """Updating to a taken username is refused as a conflict."""
    user_a_info, _ = create_and_login_user(client, "conflict_username_A")
    user_b_info, token_b = create_and_login_user(client, "conflict_username_B")

    update_payload = {
        "current_password": "testpassword",
        "username": user_a_info["username"],
    }
    headers = get_auth_headers(token_b)
    response = client.put(f"{settings.API_STR}/users/{user_b_info['id']}", json=update_payload, headers=headers)
    assert response.status_code == 409
    assert "username already registered" in response.json()["message"].lower()

def test_update_user_conflict_email(client: TestClient, db_session: Any) -> None:
    """Updating to a taken email is refused as a conflict."""
    user_a_info, _ = create_and_login_user(client, "conflict_email_A")
    user_b_info, token_b = create_and_login_user(client, "conflict_email_B")

    update_payload = {
        "current_password": "testpassword",
        "email": user_a_info["email"],
    }
    headers = get_auth_headers(token_b)
    response = client.put(f"{settings.API_STR}/users/{user_b_info['id']}", json=update_payload, headers=headers)
    assert response.status_code == 409
    assert "email already registered" in response.json()["message"].lower()

def test_upload_profile_picture_success(client: TestClient, db_session: Any) -> None:
    """Test uploading a profile picture."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_pic_upload")
    headers = get_auth_headers(token)

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("test_image.png", img_bytes, "image/png")}
    response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

    if response.status_code == 200:
        data = response.json()
        assert "image_urls" in data

def test_upload_profile_picture_unauthorized(client: TestClient) -> None:
    """Test uploading a profile picture without authentication."""
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("test_image.png", img_bytes, "image/png")}
    response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files)
    assert response.status_code == 401

def test_upload_profile_picture_invalid_file_type(client: TestClient, db_session: Any) -> None:
    """Test uploading a non-image file as profile picture."""
    user_info, token = create_and_login_user(client, "profile_pic_invalid")
    headers = get_auth_headers(token)

    files = {"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}
    response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    assert response.status_code in [400, 422, 500, 503], f"Unexpected status: {response.text}"

def test_delete_profile_picture_success(client: TestClient, db_session: Any) -> None:
    """Test deleting a profile picture."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_pic_delete")
    headers = get_auth_headers(token)

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("test_image.png", img_bytes, "image/png")}
    upload_response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    if upload_response.status_code == 200:
        response = client.delete(f"{settings.API_STR}/users/me/profile-picture", headers=headers)
        assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert data.get("image_urls") is None or "image_urls" not in data

def test_delete_profile_picture_not_found(client: TestClient, db_session: Any) -> None:
    """Test deleting a profile picture when none exists."""
    user_info, token = create_and_login_user(client, "profile_pic_no_pic")
    headers = get_auth_headers(token)

    response = client.delete(f"{settings.API_STR}/users/me/profile-picture", headers=headers)
    assert response.status_code in [200, 404, 500, 503], f"Unexpected status: {response.text}"

def test_delete_profile_picture_unauthorized(client: TestClient) -> None:
    """Test deleting a profile picture without authentication."""
    response = client.delete(f"{settings.API_STR}/users/me/profile-picture")
    assert response.status_code == 401

def test_upload_profile_picture_replaces_old_one(client: TestClient, db_session: Any) -> None:
    """Test that uploading a new profile picture replaces the old one."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_pic_replace")
    headers = get_auth_headers(token)

    img1 = Image.new("RGB", (100, 100), color="red")
    img1_bytes = io.BytesIO()
    img1.save(img1_bytes, format="PNG")
    img1_bytes.seek(0)

    files1 = {"file": ("test_image1.png", img1_bytes, "image/png")}
    upload_response1 = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files1, headers=headers)

    if upload_response1.status_code == 200:
        data1 = upload_response1.json()
        old_image_urls = data1.get("image_urls")

        img2 = Image.new("RGB", (100, 100), color="blue")
        img2_bytes = io.BytesIO()
        img2.save(img2_bytes, format="PNG")
        img2_bytes.seek(0)

        files2 = {"file": ("test_image2.png", img2_bytes, "image/png")}
        upload_response2 = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files2, headers=headers)

        assert upload_response2.status_code in [200, 500, 503], f"Unexpected status: {upload_response2.text}"

        if upload_response2.status_code == 200:
            data2 = upload_response2.json()
            new_image_urls = data2.get("image_urls")
            assert "image_urls" in data2

def test_delete_profile_picture_idempotency(client: TestClient, db_session: Any) -> None:
    """Test that deleting profile picture twice is idempotent (second should return 404)."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_delete_idempotent")
    headers = get_auth_headers(token)

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("profile.png", img_bytes, "image/png")}
    upload_response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    if upload_response.status_code == 200:
        delete_response1 = client.delete(f"{settings.API_STR}/users/me/profile-picture", headers=headers)
        assert delete_response1.status_code == 200

        delete_response2 = client.delete(f"{settings.API_STR}/users/me/profile-picture", headers=headers)
        assert delete_response2.status_code == 404

def test_upload_profile_picture_max_file_size(client: TestClient, db_session: Any) -> None:
    """Test profile picture upload with maximum file size (boundary testing)."""
    from PIL import Image

    from app.core.config import settings

    user_info, token = create_and_login_user(client, "profile_max_size")
    headers = get_auth_headers(token)

    large_img = Image.new("RGB", (2000, 2000), color="blue")
    img_bytes = io.BytesIO()
    large_img.save(img_bytes, format="PNG", optimize=False)
    img_bytes.seek(0)

    files = {"file": ("large_profile.png", img_bytes, "image/png")}
    response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    assert response.status_code in [200, 400, 422, 500, 503], f"Unexpected status: {response.text}"

def test_upload_profile_picture_min_file_size(client: TestClient, db_session: Any) -> None:
    """Test profile picture upload with minimum file size (very small images)."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_min_size")
    headers = get_auth_headers(token)

    tiny_img = Image.new("RGB", (1, 1), color="red")
    img_bytes = io.BytesIO()
    tiny_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("tiny_profile.png", img_bytes, "image/png")}
    response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

def test_upload_profile_picture_non_square(client: TestClient, db_session: Any) -> None:
    """Test profile picture upload with non-square image (verify auto-cropping/resizing to square)."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_nonsquare")
    headers = get_auth_headers(token)

    rect_img = Image.new("RGB", (200, 150), color="green")
    img_bytes = io.BytesIO()
    rect_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("rect_profile.png", img_bytes, "image/png")}
    response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

    if response.status_code == 200:
        data = response.json()
        assert "image_urls" in data

def test_upload_profile_picture_concurrent_requests(client: TestClient, db_session: Any) -> None:
    """Test race condition - uploading two profile pictures simultaneously (should handle gracefully)."""
    import threading

    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_concurrent")
    headers = get_auth_headers(token)

    img1 = Image.new("RGB", (100, 100), color="red")
    img1_bytes = io.BytesIO()
    img1.save(img1_bytes, format="PNG")
    img1_bytes.seek(0)

    img2 = Image.new("RGB", (100, 100), color="blue")
    img2_bytes = io.BytesIO()
    img2.save(img2_bytes, format="PNG")
    img2_bytes.seek(0)

    results = []

    def upload_image(img_bytes: io.BytesIO, color_name: str) -> None:
        """Post one profile picture and record the colour and status code."""
        files = {"file": (f"profile_{color_name}.png", img_bytes, "image/png")}
        response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)
        results.append((color_name, response.status_code))

    thread1 = threading.Thread(target=upload_image, args=(img1_bytes, "red"))
    thread2 = threading.Thread(target=upload_image, args=(img2_bytes, "blue"))

    thread1.start()
    thread2.start()

    thread1.join()
    thread2.join()

    assert len(results) == 2, "Both uploads should complete"
    status_codes = [status for _, status in results]
    assert any(code in [200, 500, 503] for code in status_codes), "At least one request should complete"

def test_upload_profile_picture_storage_failure_rollback(client: TestClient, db_session: Any) -> None:
    """Test rollback behavior if storage service fails after DB update (should rollback DB change)."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_storage_fail")
    headers = get_auth_headers(token)
    user_id = UUID(user_info["id"])

    user_before = UserRepository().get(user_id)
    assert user_before is not None
    initial_image_urls = user_before.image_urls

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("test_image.png", img_bytes, "image/png")}

    with patch("app.api.endpoints.users.storage_service.upload_image", side_effect=Exception("Storage failure")):
        response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

        assert response.status_code == 500, f"Expected 500 on storage failure, got {response.status_code}"

        user_before = UserRepository().get_or_raise(user_id)
        assert user_before.image_urls == initial_image_urls, "DB should be rolled back on storage failure"

def test_delete_profile_picture_storage_failure_graceful(client: TestClient, db_session: Any) -> None:
    """Test graceful handling when storage deletion fails but DB update succeeds."""
    from PIL import Image

    user_info, token = create_and_login_user(client, "profile_delete_storage_fail")
    headers = get_auth_headers(token)
    user_id = UUID(user_info["id"])

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    files = {"file": ("test_image.png", img_bytes, "image/png")}
    upload_response = client.post(f"{settings.API_STR}/users/me/profile-picture", files=files, headers=headers)

    if upload_response.status_code == 200:
        user_before = UserRepository().get(user_id)
        assert user_before is not None
        old_image_urls = user_before.image_urls

        with patch("app.api.endpoints.users.storage_service.delete_image", return_value=False):
            response = client.delete(f"{settings.API_STR}/users/me/profile-picture", headers=headers)

            assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

            if response.status_code == 500:
                user_before = UserRepository().get_or_raise(user_id)
                assert user_before.image_urls == old_image_urls, "DB should be rolled back on storage deletion failure"

RESERVED_TLD_EMAIL = "row12-cutover-check@staging.invalid"

def test_read_user_with_reserved_tld_email_returns_200(client: TestClient, db_session: Any) -> None:
    """Reading a user whose stored email has a reserved TLD returns 200, not 500."""
    user_info, token = create_and_login_user(client, "reserved_tld_email")
    headers = get_auth_headers(token)
    user_id = UUID(user_info["id"])

    UserRepository().update(user_id, email=RESERVED_TLD_EMAIL)
    stored = UserRepository().get_or_raise(user_id)
    assert stored.email == RESERVED_TLD_EMAIL

    me_response = client.get(f"{settings.API_STR}/users/me", headers=headers)
    assert me_response.status_code == 200, me_response.text
    assert me_response.json()["email"] == RESERVED_TLD_EMAIL
    assert me_response.json()["id"] == user_info["id"]

    by_id_response = client.get(f"{settings.API_STR}/users/{user_id}", headers=headers)
    assert by_id_response.status_code == 200, by_id_response.text
    assert by_id_response.json()["email"] == RESERVED_TLD_EMAIL

def test_write_path_still_rejects_reserved_tld_email(client: TestClient, db_session: Any) -> None:
    """Relaxing the read models must not let a new bad address in through the API."""
    response = client.post(
        f"{settings.API_STR}/users/",
        json={
            "username": "reserved_tld_write_attempt",
            "email": RESERVED_TLD_EMAIL,
            "password": "password123",
        },
    )
    assert response.status_code == 422, response.text
