"""Every presigned URL caller passes the ownership check and the expiry is capped (CAR-26)."""

import hashlib
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

import app.common.api.services.storage_service as ss_module
from app.common.api.services.storage_service import PRESIGNED_URL_MAX_EXPIRATION, StorageService
from app.common.core.config import settings
from app.common.db.dynamo.users import User as DBUser
from tests.conftest import auth_headers, login_user

URL = f"{settings.API_STR}/images/presigned-url"


def key_for(user_id: UUID) -> str:
    """A well formed file key owned by ``user_id``."""
    user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
    return f"user/{user_hash}/{uuid4().hex[:8]}.jpg"


def test_anonymous_caller_is_refused(client: TestClient, test_user: DBUser) -> None:
    """An anonymous caller cannot mint a URL, even for a real key."""
    with patch("app.domains.media.endpoints.images.storage_service.get_presigned_url") as mint:
        response = client.get(URL, params={"file_key": key_for(test_user.id)})
    assert response.status_code == 401
    mint.assert_not_called()


def test_signed_in_caller_is_refused_another_users_key(client: TestClient, test_user: DBUser) -> None:
    """A signed-in caller gets the same ownership check and cannot mint someone else's URL."""
    headers = auth_headers(login_user(client, test_user.username))
    with patch("app.domains.media.endpoints.images.storage_service.get_presigned_url") as mint:
        response = client.get(URL, params={"file_key": key_for(uuid4())}, headers=headers)
    assert response.status_code == 403
    mint.assert_not_called()


def test_signed_in_caller_gets_own_key(client: TestClient, test_user: DBUser) -> None:
    """The owner of a key gets its URL, with the requested expiry passed through."""
    headers = auth_headers(login_user(client, test_user.username))
    key = key_for(test_user.id)
    with patch(
        "app.domains.media.endpoints.images.storage_service.get_presigned_url",
        return_value="https://example.com/signed",
    ) as mint:
        response = client.get(URL, params={"file_key": key, "expiration": 3600}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"presigned_url": "https://example.com/signed", "file_key": key}
    mint.assert_called_once_with(key, expiration=3600)


def configured_service() -> StorageService:
    """A storage service with a stub client, so presigning skips the lazy connect."""
    service = StorageService()
    service.bucket_name = "bucket"
    service.s3_client = MagicMock()
    return service


def test_expiry_above_cap_is_clamped() -> None:
    """A requested expiry above the cap is signed at the cap."""
    service = configured_service()
    with patch.object(ss_module, "presigned_get") as presign:
        presign.return_value.url = "https://example.com/signed"
        assert service.get_presigned_url("user/abc/k.jpg", expiration=PRESIGNED_URL_MAX_EXPIRATION * 90) == (
            "https://example.com/signed"
        )
    assert presign.call_args.args[2] == PRESIGNED_URL_MAX_EXPIRATION


def test_expiry_within_cap_is_kept() -> None:
    """A requested expiry under the cap is signed as asked."""
    service = configured_service()
    with patch.object(ss_module, "presigned_get") as presign:
        service.get_presigned_url("user/abc/k.jpg", expiration=600)
    assert presign.call_args.args[2] == 600
