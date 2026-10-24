"""A caller may only attach or delete S3 image keys they uploaded (CAR-6)."""

import hashlib
import os
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.common.api.services.storage_service import StorageService
from app.common.core.config import settings
from app.common.db.dynamo.build_lists import BuildListRepository
from app.common.db.dynamo.users import User as DBUser
from app.common.db.dynamo.users import UserRepository
from tests.conftest import auth_headers, create_car_in_db, login_user


def key_for(user_id: UUID, entity_type: str = "build_list") -> str:
    """A well formed file key owned by ``user_id``."""
    user_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
    return f"{entity_type}/{user_hash}/{uuid4().hex[:8]}.jpg"


def make_victim() -> DBUser:
    """Another user whose uploads the test user must not touch."""
    name = f"victim_{os.getpid()}_{uuid4().hex[:8]}"
    return UserRepository().create_user(DBUser(username=name, email=f"{name}@example.com", email_verified=True))


def test_attach_refuses_another_users_key() -> None:
    """A key carrying someone else's owner hash is refused."""
    with pytest.raises(HTTPException) as exc:
        StorageService().assert_file_keys_attachable([key_for(uuid4())], uuid4())
    assert exc.value.status_code == 403


def test_attach_allows_own_keys_urls_existing_and_admin() -> None:
    """Own keys, external URLs, keys already on the entity and admins all pass."""
    service = StorageService()
    caller = uuid4()
    foreign = key_for(uuid4())
    service.assert_file_keys_attachable([key_for(caller), "https://cdn.example.com/a.jpg", None], caller)
    service.assert_file_keys_attachable([foreign], caller, already_attached=[foreign])
    service.assert_file_keys_attachable([foreign], caller, is_admin=True)


def test_delete_owned_image_refuses_another_users_key() -> None:
    """Deleting someone else's key never reaches S3."""
    service = StorageService()
    with patch.object(service, "delete_image", return_value=True) as delete:
        assert service.delete_owned_image(key_for(uuid4()), uuid4()) is False
    delete.assert_not_called()


def test_delete_owned_image_deletes_own_key() -> None:
    """The owner's key is deleted."""
    service = StorageService()
    caller = uuid4()
    key = key_for(caller)
    with patch.object(service, "delete_image", return_value=True) as delete:
        assert service.delete_owned_image(key, caller) is True
    delete.assert_called_once_with(key)


def create_build_list(client: TestClient, headers: dict[str, str], db_session: Any) -> dict[str, Any]:
    """A build list owned by the caller."""
    car = create_car_in_db(db_session)
    response = client.post(
        f"{settings.API_STR}/build-lists/",
        json={"name": f"bl_{uuid4().hex[:8]}", "car_id": str(car["id"])},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_build_list_with_another_users_key_is_refused(
    client: TestClient, test_user: DBUser, db_session: Any
) -> None:
    """Creating a build list that names another user's key is refused."""
    headers = auth_headers(login_user(client, test_user.username))
    car = create_car_in_db(db_session)
    response = client.post(
        f"{settings.API_STR}/build-lists/",
        json={"name": "stolen", "car_id": str(car["id"]), "image_urls": [key_for(make_victim().id)]},
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_append_another_users_key_is_refused(client: TestClient, test_user: DBUser, db_session: Any) -> None:
    """Appending another user's key to an owned build list is refused and leaves the gallery unchanged."""
    headers = auth_headers(login_user(client, test_user.username))
    build_list = create_build_list(client, headers, db_session)

    response = client.post(
        f"{settings.API_STR}/build-lists/{build_list['id']}/append-images",
        json={"file_keys": [key_for(make_victim().id)]},
        headers=headers,
    )
    assert response.status_code == 403, response.text
    stored = BuildListRepository().get(UUID(build_list["id"]))
    assert stored is not None and not stored.image_urls


def test_removing_another_users_key_keeps_the_object(client: TestClient, test_user: DBUser, db_session: Any) -> None:
    """Removing a copied image owned by someone else unlinks it without deleting their S3 object."""
    headers = auth_headers(login_user(client, test_user.username))
    build_list = create_build_list(client, headers, db_session)
    foreign = key_for(make_victim().id)
    BuildListRepository().update(UUID(build_list["id"]), image_urls=[foreign])

    target = "app.common.api.services.storage_service.storage_service.delete_image"
    with patch(target, return_value=True) as delete:
        response = client.delete(f"{settings.API_STR}/build-lists/{build_list['id']}/images/0", headers=headers)
    assert response.status_code == 200, response.text
    delete.assert_not_called()
    stored = BuildListRepository().get(UUID(build_list["id"]))
    assert stored is not None and not stored.image_urls
