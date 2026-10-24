"""Image dedup cache on DynamoDB (moto-backed)."""

from typing import Any
from uuid import uuid4

from app.common.db.dynamo.image_source_mappings import SOURCE_URL_INDEX, ImageSourceMappingRepository
from app.common.db.dynamo.tables import IMAGE_SOURCE_MAPPINGS
from app.domains.media.utils.bucket_orphan_utils import get_all_referenced_file_keys


def test_source_url_index_is_declared() -> None:
    """The table declares the source URL index the lookups rely on."""
    assert [index.name for index in IMAGE_SOURCE_MAPPINGS.indexes] == [SOURCE_URL_INDEX]


def test_lookup_by_source_url(dynamo_tables: Any) -> None:
    """A recorded mapping is found by source URL for its user and an unknown URL returns None."""
    repo = ImageSourceMappingRepository()
    user = uuid4()
    created = repo.record("https://cdn.example.com/a.jpg", "parts/u1/a.jpg", user)

    found = repo.get_by_source_url("https://cdn.example.com/a.jpg", user)
    assert found is not None and found.id == created.id and found.file_key == "parts/u1/a.jpg"
    assert repo.get_by_source_url("https://cdn.example.com/missing.jpg", user) is None


def test_record_keeps_the_first_mapping(dynamo_tables: Any) -> None:
    """Recording the same source URL twice for one user keeps the original file key."""
    repo = ImageSourceMappingRepository()
    user = uuid4()
    first = repo.record("https://cdn.example.com/a.jpg", "parts/u1/a.jpg", user)
    second = repo.record("https://cdn.example.com/a.jpg", "parts/u1/other.jpg", user)

    assert second.id == first.id
    assert second.file_key == "parts/u1/a.jpg"
    assert repo.count() == 1


def test_one_user_cannot_overwrite_another_users_mapping(dynamo_tables: Any) -> None:
    """A second user's upload for the same source URL never replaces or leaks into the first user's mapping."""
    repo = ImageSourceMappingRepository()
    owner, attacker = uuid4(), uuid4()
    repo.record("https://cdn.example.com/a.jpg", "parts/owner/a.jpg", owner)
    repo.record("https://cdn.example.com/a.jpg", "parts/attacker/evil.jpg", attacker)

    owner_mapping = repo.get_by_source_url("https://cdn.example.com/a.jpg", owner)
    attacker_mapping = repo.get_by_source_url("https://cdn.example.com/a.jpg", attacker)
    assert owner_mapping is not None and owner_mapping.file_key == "parts/owner/a.jpg"
    assert attacker_mapping is not None and attacker_mapping.file_key == "parts/attacker/evil.jpg"
    assert repo.get_by_source_url("https://cdn.example.com/a.jpg", uuid4()) is None


def test_all_file_keys_feed_orphan_detection(dynamo_tables: Any) -> None:
    """Every mapped file key reaches the orphan detection sweep."""
    repo = ImageSourceMappingRepository()
    user = uuid4()
    repo.record("https://cdn.example.com/a.jpg", "parts/u1/a.jpg", user)
    repo.record("https://cdn.example.com/b.jpg", "not a file key", user)

    assert repo.all_file_keys() == {"parts/u1/a.jpg", "not a file key"}
    assert "parts/u1/a.jpg" in get_all_referenced_file_keys()
