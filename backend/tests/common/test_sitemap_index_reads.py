"""The sitemap reads canonical parts through the sparse canonical index, never a parts Scan (CAR-36)."""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.common.db.dynamo import client as dynamo_client
from app.common.db.dynamo.catalog import Part as DBPart
from app.common.db.dynamo.catalog import PartRepository
from app.common.db.dynamo.tables import PART_CANONICAL_LISTING_ATTRIBUTE, PART_CANONICAL_LISTING_PARTITION, PARTS
from app.common.db.dynamo.users import User
from tests.conftest import get_default_category_id, save_catalog


@pytest.fixture
def no_part_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if anything scans the parts table."""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        """Stand in for a Scan the sitemap must never issue."""
        raise AssertionError("the parts table was scanned")

    monkeypatch.setattr(PartRepository, "scan_all", refuse)
    monkeypatch.setattr(PartRepository, "scan", refuse)


def _part(db: Any, user: User, name: str, canonical: DBPart | None = None) -> DBPart:
    """Create a catalogue part, linked to `canonical` when given."""
    return save_catalog(
        DBPart(
            name=name,
            category_id=get_default_category_id(db),
            user_id=user.id,
            is_universal=True,
            canonical_part_id=canonical.id if canonical is not None else None,
        )
    )


def _query_error(message: str) -> ClientError:
    """A ValidationException as DynamoDB raises it from a Query."""
    return ClientError({"Error": {"Code": "ValidationException", "Message": message}}, "Query")


def test_sitemap_reads_canonical_parts_without_a_scan(
    client: TestClient, db_session: Any, test_user: User, no_part_scans: None
) -> None:
    """The sitemap index and the parts sitemap list canonical parts from the index and skip duplicates."""
    canonical = _part(db_session, test_user, "Canonical")
    duplicate = _part(db_session, test_user, "Duplicate", canonical)

    assert client.get("/sitemap.xml").status_code == 200
    response = client.get("/sitemap-parts.xml")
    assert response.status_code == 200
    assert f"/parts/{canonical.id}<" in response.text
    assert f"/parts/{duplicate.id}<" not in response.text


def test_linking_and_unlinking_moves_a_part_through_the_canonical_index(
    db_session: Any, test_user: User, no_part_scans: None
) -> None:
    """Linking a part drops its canonical index key and unlinking writes it back."""
    repo = PartRepository()
    target = _part(db_session, test_user, "Target")
    part = _part(db_session, test_user, "Part")
    assert {p.id for p in repo.list_canonical()} == {target.id, part.id}

    linked = repo.update_unique(part, canonical_part_id=target.id)
    assert {p.id for p in repo.list_canonical()} == {target.id}
    stored = dynamo_client.get_table(PARTS).get_item(Key={"id": str(part.id)}).get("Item", {})
    assert stored and PART_CANONICAL_LISTING_ATTRIBUTE not in stored

    repo.update_unique(linked, canonical_part_id=None)
    assert {p.id for p in repo.list_canonical()} == {target.id, part.id}


def test_soft_deleted_canonical_part_leaves_the_sitemap(
    client: TestClient, db_session: Any, test_user: User, no_part_scans: None
) -> None:
    """Tombstoning a canonical part drops its canonical index key, so neither sitemap lists it (CAR-39)."""
    kept = _part(db_session, test_user, "Kept")
    deleted = _part(db_session, test_user, "Deleted")
    repo = PartRepository()

    repo.update(str(deleted.id), deleted=True)
    stored = dynamo_client.get_table(PARTS).get_item(Key={"id": str(deleted.id)}).get("Item", {})
    assert stored and PART_CANONICAL_LISTING_ATTRIBUTE not in stored
    assert [p.id for p in repo.list_canonical()] == [kept.id]

    assert client.get("/sitemap.xml").status_code == 200
    response = client.get("/sitemap-parts.xml")
    assert response.status_code == 200
    assert f"/parts/{kept.id}<" in response.text
    assert f"/parts/{deleted.id}<" not in response.text


def test_full_put_of_a_tombstoned_part_omits_the_canonical_index_key(db_session: Any, test_user: User) -> None:
    """A full write of a tombstoned canonical part never derives the canonical index key."""
    part = _part(db_session, test_user, "Part")
    PartRepository().put(part.model_copy(update={"deleted": True}))
    stored = dynamo_client.get_table(PARTS).get_item(Key={"id": str(part.id)}).get("Item", {})
    assert stored and PART_CANONICAL_LISTING_ATTRIBUTE not in stored


def test_list_canonical_filters_tombstoned_rows_still_keyed(
    db_session: Any, test_user: User, no_part_scans: None
) -> None:
    """A tombstoned row that still carries the canonical index key is filtered out on read."""
    part = _part(db_session, test_user, "Part")
    dynamo_client.get_table(PARTS).update_item(
        Key={"id": str(part.id)},
        UpdateExpression="SET #deleted = :deleted, #listing = :listing",
        ExpressionAttributeNames={"#deleted": "deleted", "#listing": PART_CANONICAL_LISTING_ATTRIBUTE},
        ExpressionAttributeValues={":deleted": True, ":listing": PART_CANONICAL_LISTING_PARTITION},
    )
    assert PartRepository().list_canonical() == []


def test_partial_update_clearing_the_tombstone_is_refused(db_session: Any, test_user: User) -> None:
    """Clearing a tombstone needs a full put, since only that can restore the canonical index key."""
    part = _part(db_session, test_user, "Part")
    with pytest.raises(ValueError):
        PartRepository().update(str(part.id), deleted=False)


def test_partial_update_of_canonical_part_id_is_refused(db_session: Any, test_user: User) -> None:
    """A partial update cannot change canonical_part_id, so the sparse key never goes stale."""
    part = _part(db_session, test_user, "Part")
    with pytest.raises(ValueError):
        PartRepository().update(str(part.id), canonical_part_id=None)


def test_list_canonical_falls_back_to_a_scan_while_the_index_backfills(
    db_session: Any, test_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Query on an index DynamoDB is still building falls back to the filtered Scan."""
    canonical = _part(db_session, test_user, "Canonical")
    _part(db_session, test_user, "Duplicate", canonical)

    def backfilling(*args: Any, **kwargs: Any) -> Any:
        """Stand in for a Query on an index that is still backfilling."""
        raise _query_error("Cannot read from backfilling global secondary index: canonical_listing-created_at-index")

    monkeypatch.setattr(PartRepository, "query_all", backfilling)
    assert [p.id for p in PartRepository().list_canonical()] == [canonical.id]


def test_list_canonical_raises_other_query_errors(monkeypatch: pytest.MonkeyPatch, dynamo_tables: Any) -> None:
    """Any other Query error is raised rather than hidden behind a Scan."""

    def broken(*args: Any, **kwargs: Any) -> Any:
        """Stand in for a Query failing for an unrelated reason."""
        raise _query_error("One or more parameter values were invalid")

    monkeypatch.setattr(PartRepository, "query_all", broken)
    with pytest.raises(ClientError):
        PartRepository().list_canonical()
