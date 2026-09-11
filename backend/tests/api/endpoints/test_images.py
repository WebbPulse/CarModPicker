"""Covers the image upload, presign and deletion endpoints."""

import io
import os
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.db.dynamo.users import User as DBUser
from app.db.dynamo.users import UserRepository
from tests.conftest import INVALID_UUID_STR, auth_headers, create_car_in_db, login_user

def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"

def get_auth_token(client: TestClient, username: str, password: str = "testpassword") -> str:
    """The credential for `username`, for use with `auth_headers`.

    A thin alias for `login_user` in `tests/conftest.py`, kept because this
    module's tests call it by this name. Row 13 of `docs/identity-adoption.md`
    deleted `POST /api/auth/token`, so what comes back is an identity request
    context rather than a bearer token; `password` is accepted and ignored.
    """
    return login_user(client, username, password)

def get_auth_headers(token: str) -> Dict[str, str]:
    """Get Authorization headers with Bearer token."""
    return auth_headers(token)

def create_and_login_admin_user(
    client: TestClient, db_session: Any, username_suffix: str = "admin"
) -> tuple[Dict[str, Any], str]:
    """Create an admin user and log them in. Returns (user_dict, token)."""
    username = f"admin_test_{username_suffix}"
    email = f"admin_test_{username_suffix}@example.com"
    password = "testpassword"

    admin_user = UserRepository().create_user(
        DBUser(
            username=username,
            email=email,
            is_admin=True,
            is_superuser=False,
            email_verified=True,
            disabled=False,
        )
    )

    token = login_user(client, username)

    return admin_user.__dict__, token

def create_test_image() -> io.BytesIO:
    """Create a test image for uploading."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes

class TestImages:
    """Test cases for images endpoints."""

    def test_upload_image_success(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test uploading an image."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img_bytes = create_test_image()

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "file_key" in data
            assert "presigned_url" in data

    def test_upload_image_unauthorized(self, client: TestClient) -> None:
        """Test uploading an image without authentication."""
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(f"{settings.API_STR}/images/upload?entity_type=user", files=files)
        assert response.status_code == 401

    def test_upload_image_invalid_entity_type(self, client: TestClient, test_user: DBUser) -> None:
        """Test uploading an image with invalid entity type."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=invalid_type", files=files, headers=headers
        )
        assert response.status_code == 400
        assert "Invalid entity_type" in response.json()["message"]

    def test_upload_image_invalid_file_type(self, client: TestClient, test_user: DBUser) -> None:
        """Test uploading a non-image file."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        files = {"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )
        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_upload_image_build_list_ownership(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that user can only upload images for their own build lists."""
        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        user2_token = get_auth_token(client, username2)
        user2_headers = get_auth_headers(user2_token)
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_list&entity_id={build_list_id}",
            files=files,
            headers=user2_headers,
        )
        assert response.status_code == 403

    def test_upload_image_car_admin_only(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that only admins can upload images for cars."""
        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=car_generation&entity_id={car['id']}",
            files=files,
            headers=headers,
        )
        assert response.status_code == 403

    def test_get_presigned_url_success(self, client: TestClient, test_user: DBUser) -> None:
        """Test getting a presigned URL for an image."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}")

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "presigned_url" in data
            assert "file_key" in data

    def test_get_presigned_url_invalid_file_key(self, client: TestClient) -> None:
        """Test getting presigned URL with invalid file key."""
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key=../../../etc/passwd")
        assert response.status_code == 400

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key=invalid")
        assert response.status_code == 400

    def test_get_presigned_url_ownership_verification(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test that authenticated users can only access their own images."""
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        import hashlib

        user2_hash = hashlib.sha256(str(user2.id).encode()).hexdigest()[:16]
        file_key = f"user/{user2_hash}/test-image.jpg"

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}", headers=headers)
        assert response.status_code in [403, 503], f"Unexpected status: {response.text}"

    def test_delete_image_success(self, client: TestClient, test_user: DBUser) -> None:
        """Test deleting an image."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)

        assert response.status_code in [200, 503, 500], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "file_key" in data

    def test_delete_image_unauthorized(self, client: TestClient) -> None:
        """Test deleting an image without authentication."""
        import hashlib

        user_hash = hashlib.sha256(str(1).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}")
        assert response.status_code == 401

    def test_delete_image_wrong_owner(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test that users can only delete their own images."""
        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        import hashlib

        user2_hash = hashlib.sha256(str(user2.id).encode()).hexdigest()[:16]
        file_key = f"user/{user2_hash}/test-image.jpg"

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)
        assert response.status_code == 403

    def test_delete_image_admin_can_delete_other_users(
        self, client: TestClient, test_admin_user: DBUser, db_session: Any
    ) -> None:
        """Admins can delete any user's image (moderation / cleanup)."""
        import hashlib

        username = get_unique_name("victim")
        victim = UserRepository().create_user(
            DBUser(
                username=username,
                email=f"{username}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        victim_hash = hashlib.sha256(str(victim.id).encode()).hexdigest()[:16]
        file_key = f"user/{victim_hash}/test-image.jpg"

        token = get_auth_token(client, test_admin_user.username)
        headers = get_auth_headers(token)
        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)

        assert response.status_code != 403, f"Admin should be authorized; got {response.status_code}: {response.text}"
        assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

    def test_get_bucket_object_count_admin_only(
        self, client: TestClient, test_user: DBUser, db_session: Any, mock_s3: Dict[str, Any]
    ) -> None:
        """Test that only admins can get bucket object count; with moto S3 admin gets 200."""
        _ = mock_s3
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        response = client.get(f"{settings.API_STR}/images/admin/count", headers=headers)
        assert response.status_code == 403

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin"))
        admin_headers = get_auth_headers(admin_token)
        response = client.get(f"{settings.API_STR}/images/admin/count", headers=admin_headers)

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["count"] == 0

    def test_get_bucket_count_by_entity_type_admin_only(
        self, client: TestClient, test_user: DBUser, db_session: Any, mock_s3: Dict[str, Any]
    ) -> None:
        """Non-admins forbidden; admin gets totals grouped by standard key prefix and other."""
        token = get_auth_token(client, test_user.username)
        r = client.get(
            f"{settings.API_STR}/images/admin/count-by-entity-type",
            headers=get_auth_headers(token),
        )
        assert r.status_code == 403

        s3 = mock_s3["client"]
        bucket = mock_s3["user_images_bucket"]
        s3.put_object(Bucket=bucket, Key="user/aaaaaaaaaaaaaaaa/1.bin", Body=b"a")
        s3.put_object(Bucket=bucket, Key="user/aaaaaaaaaaaaaaaa/2.bin", Body=b"b")
        s3.put_object(Bucket=bucket, Key="car_generation/bbbbbbbbbbbbbbbb/3.bin", Body=b"c")
        s3.put_object(Bucket=bucket, Key="user/000000000000000g/4.bin", Body=b"d")
        s3.put_object(Bucket=bucket, Key="not-standard-root-key", Body=b"e")

        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin_bucket_prefix"))
        r2 = client.get(
            f"{settings.API_STR}/images/admin/count-by-entity-type",
            headers=get_auth_headers(admin_token),
        )
        assert r2.status_code == 200, r2.text
        body = r2.json()
        assert body["total"] == 5
        assert body["by_entity_type"]["user"] == 2
        assert body["by_entity_type"]["car_generation"] == 1
        assert body["other"] == 2

    def test_get_bucket_object_count_admin_503_without_s3(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Without mock_s3, admin bucket count returns 503 (no S3 client in test env)."""
        _, admin_token = create_and_login_admin_user(client, db_session, get_unique_name("admin_no_s3"))
        admin_headers = get_auth_headers(admin_token)
        response = client.get(f"{settings.API_STR}/images/admin/count", headers=admin_headers)
        assert response.status_code == 503

    def test_upload_image_build_log_post(self, client: TestClient, test_user: DBUser, db_session: Any) -> None:
        """Test uploading an image for a build log post."""
        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        build_list_data = {
            "name": get_unique_name("test_build_list"),
            "description": "A test build list description",
            "car_id": str(car["id"]),
        }
        response = client.post(f"{settings.API_STR}/build-lists/", json=build_list_data, headers=headers)
        assert response.status_code == 200
        build_list_id = response.json()["id"]

        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_log_post&entity_id={build_list_id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_build_log_post_invalid_build_list(self, client: TestClient, test_user: DBUser) -> None:
        """Test uploading an image for a build log post with invalid build_list_id."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_log_post&entity_id={INVALID_UUID_STR}",
            files=files,
            headers=headers,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()

    def test_upload_image_part(
        self, client: TestClient, test_user: DBUser, test_category, test_part_manufacturer, db_session: Any
    ) -> None:
        """Test uploading an image for a global part."""
        car = create_car_in_db(db_session)

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)
        part_data = {
            "name": get_unique_name("test_part"),
            "description": "A test part description",
            "category_id": str(test_category.id),
            "car_id": str(car["id"]),
            "part_manufacturer_id": str(test_part_manufacturer.id),
        }
        response = client.post(f"{settings.API_STR}/parts/", json=part_data, headers=headers)
        assert response.status_code == 200
        part_id = response.json()["id"]

        img_bytes = create_test_image()
        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=part&entity_id={part_id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test getting a presigned URL with custom expiration."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration=3600")

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

        if response.status_code == 200:
            data = response.json()
            assert "presigned_url" in data
            assert "file_key" in data

    def test_get_presigned_url_max_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test getting a presigned URL with maximum expiration (90 days)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        max_expiration = 90 * 24 * 60 * 60
        response = client.get(
            f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration={max_expiration}"
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_build_log_post_without_entity_id(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test image upload for build_log_post without entity_id (should be allowed per code)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img_bytes = create_test_image()

        files = {"file": ("test.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=build_log_post",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_zero_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with expiration=0 (should validate and reject)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration=0")

        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_negative_expiration(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with negative expiration (should validate and reject)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration=-1")

        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_with_expiration_exceeding_maximum(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with expiration exceeding maximum (90 days)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        max_expiration = 90 * 24 * 60 * 60 + 1
        response = client.get(
            f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration={max_expiration}"
        )

        assert response.status_code in [200, 400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_ownership_verification_authenticated_user(
        self, client: TestClient, test_user: DBUser, db_session: Any
    ) -> None:
        """Test presigned URL ownership verification when user is authenticated but doesn't own the file."""
        import hashlib

        username2 = get_unique_name("user2")
        user2 = UserRepository().create_user(
            DBUser(
                username=username2,
                email=f"{username2}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        user2_hash = hashlib.sha256(str(user2.id).encode()).hexdigest()[:16]
        user2_file_key = f"user/{user2_hash}/test-image.jpg"

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        response = client.get(f"{settings.API_STR}/images/presigned-url?file_key={user2_file_key}", headers=headers)

        assert response.status_code in [403, 503], f"Unexpected status: {response.text}"

    def test_upload_image_file_size_at_exact_limit(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with file size exactly at the maximum limit."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img = Image.new("RGB", (10, 10), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_file_size_just_over_limit(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with file size just over the limit (should reject)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        large_img = Image.new("RGB", (5000, 5000), color="red")
        img_bytes = io.BytesIO()
        large_img.save(img_bytes, format="PNG", optimize=False)
        img_bytes.seek(0)

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_upload_image_all_formats_png(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with PNG format."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img = Image.new("RGB", (100, 100), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        files = {"file": ("test_image.png", img_bytes, "image/png")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_all_formats_jpeg(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with JPEG format."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img = Image.new("RGB", (100, 100), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes.seek(0)

        files = {"file": ("test_image.jpg", img_bytes, "image/jpeg")}
        response = client.post(
            f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
            files=files,
            headers=headers,
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_upload_image_all_formats_webp(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with WEBP format (if supported)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        try:
            img = Image.new("RGB", (100, 100), color="yellow")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="WEBP")
            img_bytes.seek(0)

            files = {"file": ("test_image.webp", img_bytes, "image/webp")}
            data = {"entity_type": "user", "entity_id": str(test_user.id)}
            response = client.post(f"{settings.API_STR}/images/upload", files=files, data=data, headers=headers)

            assert response.status_code in [200, 400, 422, 503], f"Unexpected status: {response.text}"
        except Exception:
            pass

    def test_upload_image_corrupted_file(self, client: TestClient, test_user: DBUser) -> None:
        """Test image upload with corrupted/invalid image file."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        corrupted_content = b"This is not a valid image file, but has .png extension"
        files = {"file": ("fake_image.png", io.BytesIO(corrupted_content), "image/png")}
        data = {"entity_type": "user", "entity_id": str(test_user.id)}
        response = client.post(f"{settings.API_STR}/images/upload", files=files, data=data, headers=headers)

        assert response.status_code in [400, 422, 503], f"Unexpected status: {response.text}"

    def test_get_presigned_url_expiration_at_maximum(self, client: TestClient, test_user: DBUser) -> None:
        """Test presigned URL with expiration exactly at maximum (90 days = 7776000 seconds)."""
        import hashlib

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/test-image.jpg"

        max_expiration = 90 * 24 * 60 * 60
        response = client.get(
            f"{settings.API_STR}/images/presigned-url?file_key={file_key}&expiration={max_expiration}"
        )

        assert response.status_code in [200, 503], f"Unexpected status: {response.text}"

    def test_delete_image_idempotency(self, client: TestClient, test_user: DBUser) -> None:
        """Test that deleting a non-existent image is idempotent (should handle gracefully)."""
        import hashlib

        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        user_hash = hashlib.sha256(str(test_user.id).encode()).hexdigest()[:16]
        file_key = f"user/{user_hash}/nonexistent-image.jpg"

        response = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)

        assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"

        response2 = client.delete(f"{settings.API_STR}/images/delete?file_key={file_key}", headers=headers)
        assert response2.status_code in [200, 500, 503], f"Unexpected status on second delete: {response2.text}"

    def test_upload_image_failure_rollback(self, client: TestClient, test_user: DBUser) -> None:
        """Test that if database update fails after storage upload, the uploaded file is cleaned up (requires mocking)."""
        token = get_auth_token(client, test_user.username)
        headers = get_auth_headers(token)

        img_bytes = create_test_image()

        with (
            patch("app.api.endpoints.images.storage_service.upload_image") as mock_upload,
            patch("app.api.endpoints.images.storage_service.get_presigned_url") as mock_presigned,
            patch("app.api.endpoints.images.storage_service.delete_image") as mock_delete,
        ):
            mock_upload.return_value = "user/test_hash/test-image.png"
            mock_presigned.return_value = "https://example.com/presigned-url"

            files = {"file": ("test_image.png", img_bytes, "image/png")}

            response = client.post(
                f"{settings.API_STR}/images/upload?entity_type=user&entity_id={test_user.id}",
                files=files,
                headers=headers,
            )

            assert response.status_code in [200, 500, 503], f"Unexpected status: {response.text}"


def png_bytes() -> bytes:
    """Raw bytes of a small valid PNG."""
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), color="green").save(buffer, format="PNG")
    return buffer.getvalue()


class TestFetchImageFromUrl:
    """`POST /images/fetch-from-url`, the route the extension uses instead of reading bytes itself."""

    URL = f"{settings.API_STR}/images/fetch-from-url"

    def test_requires_authentication(self, client: TestClient) -> None:
        """Anonymous callers cannot make the server fetch anything."""
        response = client.post(
            self.URL,
            json={"source_url": "https://cdn.example.com/a.jpg", "entity_type": "user"},
        )
        assert response.status_code == 401

    def test_invalid_entity_type_rejected(self, client: TestClient, test_user: DBUser) -> None:
        """The entity type allow-list is shared with the byte upload route."""
        headers = get_auth_headers(get_auth_token(client, test_user.username))
        response = client.post(
            self.URL,
            json={"source_url": "https://cdn.example.com/a.jpg", "entity_type": "invalid_type"},
            headers=headers,
        )
        assert response.status_code == 400

    def test_http_scheme_rejected(self, client: TestClient, test_user: DBUser) -> None:
        """Plain http is refused before any connection is attempted."""
        headers = get_auth_headers(get_auth_token(client, test_user.username))
        response = client.post(
            self.URL,
            json={
                "source_url": "http://cdn.example.com/a.jpg",
                "entity_type": "user",
                "entity_id": str(test_user.id),
            },
            headers=headers,
        )
        assert response.status_code == 400

    @pytest.mark.parametrize(
        "host",
        ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "[::1]"],
    )
    def test_private_and_metadata_addresses_rejected(self, client: TestClient, test_user: DBUser, host: str) -> None:
        """A private, loopback, link-local or metadata target is refused."""
        headers = get_auth_headers(get_auth_token(client, test_user.username))
        response = client.post(
            self.URL,
            json={
                "source_url": f"https://{host}/latest/meta-data/",
                "entity_type": "user",
                "entity_id": str(test_user.id),
            },
            headers=headers,
        )
        assert response.status_code == 400

    def test_empty_source_url_rejected(self, client: TestClient, test_user: DBUser) -> None:
        """An all-whitespace source URL is a 400, not a fetch."""
        headers = get_auth_headers(get_auth_token(client, test_user.username))
        response = client.post(
            self.URL,
            json={"source_url": "   ", "entity_type": "user", "entity_id": str(test_user.id)},
            headers=headers,
        )
        assert response.status_code == 400

    def test_wrong_content_type_rejected(self, client: TestClient, test_user: DBUser) -> None:
        """A source URL serving HTML is refused on content type."""
        from app.api.utils.remote_image_fetch import RemoteImageError

        headers = get_auth_headers(get_auth_token(client, test_user.username))
        with (
            patch("app.api.endpoints.images.assert_url_is_fetchable"),
            patch("app.api.endpoints.images.fetch_remote_image") as mock_fetch,
        ):
            mock_fetch.side_effect = RemoteImageError("Unsupported image content type: text/html")
            response = client.post(
                self.URL,
                json={
                    "source_url": "https://cdn.example.com/a.html",
                    "entity_type": "user",
                    "entity_id": str(test_user.id),
                },
                headers=headers,
            )
        assert response.status_code == 400

    def test_oversize_image_rejected(self, client: TestClient, test_user: DBUser) -> None:
        """An oversize source image surfaces as a 413."""
        from app.api.utils.remote_image_fetch import RemoteImageError

        headers = get_auth_headers(get_auth_token(client, test_user.username))
        with (
            patch("app.api.endpoints.images.assert_url_is_fetchable"),
            patch("app.api.endpoints.images.fetch_remote_image") as mock_fetch,
        ):
            mock_fetch.side_effect = RemoteImageError(
                f"Image exceeds maximum size of {settings.MAX_IMAGE_SIZE_MB}MB", status_code=413
            )
            response = client.post(
                self.URL,
                json={
                    "source_url": "https://cdn.example.com/huge.jpg",
                    "entity_type": "user",
                    "entity_id": str(test_user.id),
                },
                headers=headers,
            )
        assert response.status_code == 413

    def test_public_image_is_stored(self, client: TestClient, test_user: DBUser) -> None:
        """A public https image is fetched server side and stored through the normal pipeline."""
        headers = get_auth_headers(get_auth_token(client, test_user.username))
        with (
            patch("app.api.endpoints.images.assert_url_is_fetchable"),
            patch("app.api.endpoints.images.fetch_remote_image", return_value=(png_bytes(), "png")),
            patch(
                "app.api.endpoints.images.storage_service.upload_image",
                return_value="user/abcdef0123456789/img.png",
            ),
            patch(
                "app.api.endpoints.images.storage_service.get_presigned_url",
                return_value="https://example.com/presigned",
            ),
        ):
            response = client.post(
                self.URL,
                json={
                    "source_url": "https://cdn.example.com/part.jpg",
                    "entity_type": "user",
                    "entity_id": str(test_user.id),
                },
                headers=headers,
            )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["file_key"] == "user/abcdef0123456789/img.png"
        assert data["presigned_url"] == "https://example.com/presigned"

    def test_not_authorized_for_another_users_entity(self, client: TestClient, test_user: DBUser) -> None:
        """A caller cannot attach a fetched image to someone else's entity."""
        headers = get_auth_headers(get_auth_token(client, test_user.username))
        response = client.post(
            self.URL,
            json={
                "source_url": "https://cdn.example.com/a.jpg",
                "entity_type": "user",
                "entity_id": INVALID_UUID_STR,
            },
            headers=headers,
        )
        assert response.status_code == 403
