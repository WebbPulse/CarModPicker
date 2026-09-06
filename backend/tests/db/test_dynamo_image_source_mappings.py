"""Image dedup cache on DynamoDB (moto-backed)."""

from typing import Any

from app.api.utils.bucket_orphan_utils import get_all_referenced_file_keys
from app.db.dynamo.image_source_mappings import SOURCE_URL_INDEX, ImageSourceMappingRepository
from app.db.dynamo.tables import IMAGE_SOURCE_MAPPINGS


def test_source_url_index_is_declared() -> None:
    assert [index.name for index in IMAGE_SOURCE_MAPPINGS.indexes] == [SOURCE_URL_INDEX]


def test_lookup_by_source_url(dynamo_tables: Any) -> None:
    repo = ImageSourceMappingRepository()
    created = repo.record("https://cdn.example.com/a.jpg", "parts/u1/a.jpg")

    found = repo.get_by_source_url("https://cdn.example.com/a.jpg")
    assert found is not None and found.id == created.id and found.file_key == "parts/u1/a.jpg"
    assert repo.get_by_source_url("https://cdn.example.com/missing.jpg") is None


def test_record_keeps_the_first_mapping(dynamo_tables: Any) -> None:
    repo = ImageSourceMappingRepository()
    first = repo.record("https://cdn.example.com/a.jpg", "parts/u1/a.jpg")
    second = repo.record("https://cdn.example.com/a.jpg", "parts/u2/other.jpg")

    assert second.id == first.id
    assert second.file_key == "parts/u1/a.jpg"
    assert repo.count() == 1


def test_all_file_keys_feed_orphan_detection(dynamo_tables: Any) -> None:
    repo = ImageSourceMappingRepository()
    repo.record("https://cdn.example.com/a.jpg", "parts/u1/a.jpg")
    repo.record("https://cdn.example.com/b.jpg", "not a file key")

    assert repo.all_file_keys() == {"parts/u1/a.jpg", "not a file key"}
    assert "parts/u1/a.jpg" in get_all_referenced_file_keys()
