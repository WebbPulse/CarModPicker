"""The public build list listing reads through index Queries, never a table Scan (CAR-24)."""

from datetime import UTC, datetime, timedelta
from typing import Any, Iterator, List
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from uuid6 import uuid7

from app.common.core.config import settings
from app.common.db.dynamo import client as dynamo_client
from app.common.db.dynamo.build_lists import BuildList, BuildListRepository
from app.common.db.dynamo.tables import BUILD_LISTS

LISTING_URL = f"{settings.API_STR}/build-lists/with-votes"


@pytest.fixture
def no_build_list_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail the test if anything scans the build lists table."""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        """Stand in for a Scan the listing must never issue."""
        raise AssertionError("the build lists table was scanned")

    monkeypatch.setattr(BuildListRepository, "scan_all", refuse)
    monkeypatch.setattr(BuildListRepository, "scan", refuse)


@pytest.fixture
def queried_indexes(monkeypatch: pytest.MonkeyPatch) -> Iterator[List[str | None]]:
    """Record the index of every build lists Query the request issues."""
    seen: List[str | None] = []
    original = BuildListRepository.query

    def spy(self: BuildListRepository, index: str | None, key_value: Any, **kwargs: Any) -> Any:
        """Note the index, then run the real Query."""
        seen.append(index)
        return original(self, index, key_value, **kwargs)

    monkeypatch.setattr(BuildListRepository, "query", spy)
    yield seen


def _seed(
    repo: BuildListRepository, *, user_id: UUID, car_id: UUID | None, price: int, age_minutes: int
) -> BuildList:
    """Write one build list with a fixed price and creation time."""
    created = datetime(2026, 1, 1, tzinfo=UTC) - timedelta(minutes=age_minutes)
    return repo.create(
        BuildList(
            name=f"listing-{price}-{age_minutes}",
            user_id=user_id,
            car_id=car_id,
            base_price_cents=price,
            created_at=created,
            updated_at=created,
        )
    )


def test_writes_carry_the_listing_key_and_page_newest_first(dynamo_tables: Any) -> None:
    """A created build list holds the listing attribute, and list_public pages it newest first."""
    repo = BuildListRepository()
    user_id = uuid7()
    lists = [_seed(repo, user_id=user_id, car_id=None, price=100, age_minutes=age) for age in (30, 10, 20)]

    raw = dynamo_client.get_table(BUILD_LISTS).get_item(Key={"id": str(lists[0].id)})["Item"]
    assert raw["listing"] == "build_list"

    first = repo.list_public(limit=2)
    second = repo.list_public(limit=2, cursor=first.next_cursor)
    paged = [bl.id for bl in first.items + second.items]
    assert paged == [lists[1].id, lists[2].id, lists[0].id]
    assert second.next_cursor is None
    assert [bl.id for bl in repo.all_public()] == paged


def test_unfiltered_listing_queries_the_listing_index(
    client: TestClient, dynamo_tables: Any, no_build_list_scans: None, queried_indexes: List[str | None]
) -> None:
    """The unfiltered listing reads every build list through the listing index, ordered as before."""
    repo = BuildListRepository()
    seeded = [
        _seed(repo, user_id=uuid7(), car_id=None, price=price, age_minutes=age)
        for price, age in ((300, 1), (100, 2), (200, 3))
    ]

    response = client.get(f"{LISTING_URL}?sort=price_asc")
    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["data"]] == [str(seeded[1].id), str(seeded[2].id), str(seeded[0].id)]
    assert body["total"] == 3
    assert set(body) == {"data", "total", "skip", "limit", "pagination"}
    assert {"upvotes", "downvotes", "total_votes", "user_vote", "total_cost_cents"} <= set(body["data"][0])
    assert queried_indexes == [BuildListRepository.listing_index]

    response = client.get(LISTING_URL)
    expected = sorted((str(bl.id) for bl in seeded), reverse=True)
    assert [item["id"] for item in response.json()["data"]] == expected

    response = client.get(f"{LISTING_URL}?sort=price_desc&skip=1&limit=1")
    page = response.json()
    assert [item["id"] for item in page["data"]] == [str(seeded[2].id)]
    assert page["total"] == 3


def test_car_and_owner_filters_query_their_own_indexes(
    client: TestClient, dynamo_tables: Any, no_build_list_scans: None, queried_indexes: List[str | None]
) -> None:
    """A car filter queries the car index per car, and an owner filter queries the user index."""
    repo = BuildListRepository()
    owner, other = uuid7(), uuid7()
    car_a, car_b, car_c = uuid7(), uuid7(), uuid7()
    on_a = _seed(repo, user_id=owner, car_id=car_a, price=100, age_minutes=1)
    on_b = _seed(repo, user_id=other, car_id=car_b, price=200, age_minutes=2)
    _seed(repo, user_id=other, car_id=car_c, price=300, age_minutes=3)

    response = client.get(f"{LISTING_URL}?car_ids={car_a}&car_ids={car_b}&sort=price_asc")
    assert [item["id"] for item in response.json()["data"]] == [str(on_a.id), str(on_b.id)]
    assert queried_indexes == ["car_id-created_at-index", "car_id-created_at-index"]

    queried_indexes.clear()
    response = client.get(f"{LISTING_URL}?owner_id={owner}")
    assert [item["id"] for item in response.json()["data"]] == [str(on_a.id)]
    assert queried_indexes == ["user_id-created_at-index"]
