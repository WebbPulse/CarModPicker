from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from boto3.dynamodb.conditions import Attr

from app.db.dynamo import client as dynamo_client
from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled
from app.db.dynamo.models import DynamoModel, TimestampedDynamoModel
from app.db.dynamo.repository import (
    DynamoRepository,
    RangeCondition,
    decode_cursor,
    encode_cursor,
    transact_write,
)
from app.db.dynamo.tables import PART_CARS, USERS, VOTES, TableSpec, gsi

WIDGETS = TableSpec(
    suffix="widgets",
    indexes=(gsi("owner_id", "created_at"), gsi("name_lower")),
    lowercase_mirrors=(("name", "name_lower"),),
)


class Widget(TimestampedDynamoModel):
    name: str
    owner_id: str
    score: int = 0
    note: str | None = None
    tags: list[str] = []


class User(TimestampedDynamoModel):
    username: str
    email: str


class Vote(TimestampedDynamoModel):
    user_id: str
    entity_type: str
    entity_id: str
    vote_type: str


class PartCar(DynamoModel):
    part_id: str
    car_id: str


@pytest.fixture
def widgets(dynamo_tables: Any) -> DynamoRepository[Widget]:
    dynamo_tables.create_table(**WIDGETS.create_table_request(dynamo_client.table_name(WIDGETS)))
    return DynamoRepository(Widget, WIDGETS)


@pytest.fixture
def users(dynamo_tables: Any) -> DynamoRepository[User]:
    return DynamoRepository(User, USERS)


def make_widgets(owner_id: str, count: int) -> list[Widget]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Widget(name=f"w{i}", owner_id=owner_id, score=i, created_at=base + timedelta(minutes=i)) for i in range(count)
    ]


def test_create_get_update_delete(widgets: DynamoRepository[Widget]) -> None:
    widget = widgets.create(Widget(name="Alpha", owner_id="o1", note="hi", tags=["x"]))
    assert widgets.get(widget.id) == widget
    assert widgets.get_or_raise(widget.id).name == "Alpha"

    updated = widgets.update(widget.id, name="Beta", score=3, note=None)
    assert updated.name == "Beta"
    assert updated.score == 3
    assert updated.note is None
    assert updated.updated_at > widget.updated_at
    assert widgets.query("name_lower-index", "beta").items == [updated]
    assert widgets.query("name_lower-index", "alpha").items == []

    widgets.delete(widget.id)
    assert widgets.get(widget.id) is None
    with pytest.raises(ItemNotFound):
        widgets.get_or_raise(widget.id)
    with pytest.raises(ItemNotFound):
        widgets.delete(widget.id, must_exist=True)


def test_update_missing_item_raises(widgets: DynamoRepository[Widget]) -> None:
    with pytest.raises(ItemNotFound):
        widgets.update("nope", name="x")


def test_update_rejects_key_attributes(widgets: DynamoRepository[Widget]) -> None:
    widget = widgets.create(Widget(name="a", owner_id="o"))
    with pytest.raises(ValueError):
        widgets.update(widget.id, id="other")


def test_update_rejects_composite_key_sources(dynamo_tables: Any) -> None:
    votes = DynamoRepository(Vote, VOTES)
    vote = votes.create(Vote(user_id="u", entity_type="part", entity_id="p", vote_type="upvote"))
    with pytest.raises(ValueError):
        votes.update(vote.id, entity_id="other")


def test_create_rejects_duplicate_id(widgets: DynamoRepository[Widget]) -> None:
    widget = widgets.create(Widget(name="a", owner_id="o"))
    with pytest.raises(ConditionFailed):
        widgets.create(Widget(id=widget.id, name="b", owner_id="o"))
    assert widgets.put(Widget(id=widget.id, name="b", owner_id="o")).name == "b"


def test_put_with_condition(widgets: DynamoRepository[Widget]) -> None:
    widget = widgets.create(Widget(name="a", owner_id="o", score=1))
    with pytest.raises(ConditionFailed):
        widgets.put(widget, condition=Attr("score").eq(99))
    widgets.put(widget.model_copy(update={"score": 2}), condition=Attr("score").eq(1))
    assert widgets.get_or_raise(widget.id).score == 2


def test_gsi_query_with_range_condition_and_pagination(widgets: DynamoRepository[Widget]) -> None:
    mine = make_widgets("me", 7)
    widgets.batch_put(mine + make_widgets("other", 3))

    seen: list[Widget] = []
    cursor: str | None = None
    pages = 0
    while True:
        page = widgets.query("owner_id-created_at-index", "me", limit=3, cursor=cursor)
        pages += 1
        seen.extend(page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert pages == 3
    assert [w.name for w in seen] == [w.name for w in mine]

    newest_first = widgets.query("owner_id-created_at-index", "me", scan_forward=False, limit=2)
    assert [w.name for w in newest_first.items] == ["w6", "w5"]

    since = mine[4].created_at
    recent = widgets.query("owner_id-created_at-index", "me", range_condition=RangeCondition.gte(since))
    assert [w.name for w in recent.items] == ["w4", "w5", "w6"]

    window = widgets.query(
        "owner_id-created_at-index",
        "me",
        range_condition=RangeCondition.between(mine[1].created_at, mine[3].created_at),
    )
    assert [w.name for w in window.items] == ["w1", "w2", "w3"]

    assert len(widgets.query_all("owner_id-created_at-index", "me", page_size=2)) == 7
    filtered = widgets.query("owner_id-created_at-index", "me", filter_expression=Attr("score").gt(4))
    assert [w.name for w in filtered.items] == ["w5", "w6"]


def test_query_range_condition_requires_range_key(widgets: DynamoRepository[Widget]) -> None:
    with pytest.raises(ValueError):
        widgets.query("name_lower-index", "x", range_condition=RangeCondition.eq("y"))
    with pytest.raises(KeyError):
        widgets.query("missing-index", "x")


def test_cursor_round_trip_and_rejection() -> None:
    key = {"id": "abc", "sort_order": 3}
    assert decode_cursor(encode_cursor(key)) == key
    assert encode_cursor(None) is None
    assert decode_cursor(None) is None
    with pytest.raises(ValueError):
        decode_cursor("not-base64-json")


def test_base_table_query_on_composite_key(dynamo_tables: Any) -> None:
    part_cars = DynamoRepository(PartCar, PART_CARS)
    part_cars.batch_put(
        [PartCar(part_id="p1", car_id=f"c{i}") for i in range(3)] + [PartCar(part_id="p2", car_id="c0")]
    )

    assert [row.car_id for row in part_cars.query(None, "p1").items] == ["c0", "c1", "c2"]
    assert [row.part_id for row in part_cars.query("car_id-part_id-index", "c0").items] == ["p1", "p2"]
    assert part_cars.get("p1", "c1") is not None
    with pytest.raises(ValueError):
        part_cars.get("p1")
    part_cars.delete("p1", "c1")
    fetched = part_cars.batch_get([("p1", "c0"), ("p1", "c1"), {"part_id": "p2", "car_id": "c0"}])
    assert [(row.part_id, row.car_id) for row in fetched] == [("p1", "c0"), ("p2", "c0")]


def test_batch_operations_above_chunk_size(widgets: DynamoRepository[Widget]) -> None:
    models = make_widgets("bulk", 60)
    widgets.batch_put(models)
    ids = [w.id for w in models]

    fetched = widgets.batch_get(ids)
    assert {w.id for w in fetched} == set(ids)
    assert len(widgets.scan_all(page_size=7)) == 60

    widgets.batch_delete(ids)
    assert widgets.scan_all() == []


def test_scan_excludes_unique_lookup_items(widgets: DynamoRepository[Widget]) -> None:
    widgets.create(Widget(name="a", owner_id="o", score=1))
    widgets.create(Widget(name="b", owner_id="o", score=2))
    widgets.ensure_unique("name", "a")
    page = widgets.scan()
    assert sorted(w.name for w in page.items) == ["a", "b"]
    only_high = widgets.scan(filter_expression=Attr("score").gt(1))
    assert [w.name for w in only_high.items] == ["b"]


def test_ensure_and_release_unique(users: DynamoRepository[User]) -> None:
    users.ensure_unique("email", "a@b.c", owner_id="u1")
    assert users.is_unique_taken("email", "a@b.c")
    with pytest.raises(ConditionFailed):
        users.ensure_unique("email", "a@b.c", owner_id="u2")
    users.release_unique("email", "a@b.c")
    assert not users.is_unique_taken("email", "a@b.c")
    users.ensure_unique("email", "a@b.c", owner_id="u2")


def test_unique_lookup_rejected_on_composite_table(dynamo_tables: Any) -> None:
    part_cars = DynamoRepository(PartCar, PART_CARS)
    with pytest.raises(ValueError):
        part_cars.ensure_unique("car_id", "x")


def test_transact_write_enforces_uniqueness(users: DynamoRepository[User]) -> None:
    first = User(username="Tyler", email="T@example.com")
    transact_write(
        [
            users.create_action(first),
            users.ensure_unique_action("username", "tyler", owner_id=first.id),
            users.ensure_unique_action("email", "t@example.com", owner_id=first.id),
        ]
    )
    assert users.get_or_raise(first.id).username == "Tyler"
    assert users.query("username_lower-index", "tyler").items == [first]

    second = User(username="tyler", email="other@example.com")
    with pytest.raises(TransactionCanceled) as excinfo:
        transact_write(
            [
                users.create_action(second),
                users.ensure_unique_action("username", "tyler", owner_id=second.id),
                users.ensure_unique_action("email", "other@example.com", owner_id=second.id),
            ]
        )
    assert excinfo.value.conditional_check_failed
    assert users.get(second.id) is None
    assert not users.is_unique_taken("email", "other@example.com")

    transact_write(
        [
            users.update_action(first.id, username="Tyler2"),
            users.release_unique_action("username", "tyler"),
            users.ensure_unique_action("username", "tyler2", owner_id=first.id),
        ]
    )
    assert users.get_or_raise(first.id).username == "Tyler2"
    assert users.query("username_lower-index", "tyler2").items[0].id == first.id
    assert not users.is_unique_taken("username", "tyler")

    transact_write(
        [
            users.delete_action(first.id, must_exist=True),
            users.release_unique_action("username", "tyler2"),
            users.condition_check_action(users.unique_lookup_item("email", "t@example.com")["id"]),
        ]
    )
    assert users.get(first.id) is None
    assert not users.is_unique_taken("username", "tyler2")


def test_transact_write_condition_check_failure(users: DynamoRepository[User]) -> None:
    with pytest.raises(TransactionCanceled):
        transact_write([users.condition_check_action("missing"), users.create_action(User(username="a", email="b"))])
    assert users.scan_all() == []


def test_transact_write_limits() -> None:
    transact_write([])
    with pytest.raises(ValueError):
        transact_write([{"Put": {}}] * 101)


def test_derived_attributes_survive_update(dynamo_tables: Any) -> None:
    votes = DynamoRepository(Vote, VOTES)
    entity_id = str(uuid4())
    vote = votes.create(Vote(user_id="u1", entity_type="part", entity_id=entity_id, vote_type="upvote"))
    votes.update(vote.id, vote_type="downvote")
    found = votes.query("entity_key-user_id-index", f"part#{entity_id}", range_condition=RangeCondition.eq("u1"))
    assert [v.vote_type for v in found.items] == ["downvote"]
