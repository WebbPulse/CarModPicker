from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.db.dynamo import client as dynamo_client
from app.db.dynamo import search
from app.db.dynamo.models import TimestampedDynamoModel
from app.db.dynamo.repository import DynamoRepository
from app.db.dynamo.tables import TableSpec, gsi

GADGETS = TableSpec(
    suffix="gadgets",
    indexes=(gsi("owner_id", "created_at"),),
    lowercase_mirrors=(("name", "name_lower"),),
)


class Gadget(TimestampedDynamoModel):
    name: str
    owner_id: str
    price_cents: int | None = None
    note: str | None = None


@pytest.fixture
def gadgets(dynamo_tables: Any) -> DynamoRepository[Gadget]:
    dynamo_tables.create_table(**GADGETS.create_table_request(dynamo_client.table_name(GADGETS)))
    repo = DynamoRepository(Gadget, GADGETS)
    base = datetime(2024, 1, 1, tzinfo=UTC)
    items = []
    for index in range(300):
        family = "Turbo" if index % 3 == 0 else ("Brake" if index % 3 == 1 else "Exhaust")
        items.append(
            Gadget(
                name=f"{family} Kit {index:03d}",
                owner_id=f"owner-{index % 7}",
                price_cents=None if index % 25 == 0 else (index * 37) % 5000,
                note="stage two upgrade" if index % 10 == 0 else None,
                created_at=base + timedelta(minutes=index),
                updated_at=base + timedelta(minutes=index),
            )
        )
    repo.batch_put(items)
    return repo


def _collect(repo: DynamoRepository[Gadget], matched: list[Gadget], sort_key, limit: int) -> list[Gadget]:
    seen: list[Gadget] = []
    cursor = None
    while True:
        page = search.paginate(matched, limit=limit, cursor=cursor, sort_key=sort_key, transform=lambda g: g)
        seen.extend(page.items)
        assert len(page.items) <= limit
        if not page.has_next:
            assert page.next_cursor is None
            return seen
        assert page.next_cursor is not None
        cursor = page.next_cursor


def test_contains_is_case_insensitive_substring(gadgets: DynamoRepository[Gadget]) -> None:
    term = search.normalize_term("  tURBO ")
    matched = search.scan_matching(gadgets, lambda g: search.contains(term, g.name, g.note))
    assert len(matched) == 100
    assert all("Turbo" in g.name for g in matched)


def test_contains_matches_across_fields(gadgets: DynamoRepository[Gadget]) -> None:
    term = search.normalize_term("STAGE TWO")
    matched = search.scan_matching(gadgets, lambda g: search.contains(term, g.name, g.note))
    assert len(matched) == 30
    assert all(g.note == "stage two upgrade" for g in matched)


def test_starts_with_and_empty_term(gadgets: DynamoRepository[Gadget]) -> None:
    matched = search.scan_matching(gadgets, lambda g: search.starts_with("brake", g.name))
    assert len(matched) == 100
    assert search.contains("", None) is True
    assert search.starts_with("", None) is True
    assert search.contains("kit", None) is False


def test_scan_page_limit_caps_pages_read(gadgets: DynamoRepository[Gadget]) -> None:
    partial = search.scan_matching(gadgets, lambda g: True, page_limit=2, page_size=40)
    assert len(partial) == 80
    full = search.scan_matching(gadgets, lambda g: True, page_limit=100, page_size=40)
    assert len(full) == 300


def test_cursor_walk_is_complete_and_ordered_by_name(gadgets: DynamoRepository[Gadget]) -> None:
    matched = search.scan_matching(gadgets, lambda g: True, page_size=50)
    walked = _collect(gadgets, matched, lambda g: search.text_key(g.name), limit=17)
    assert len(walked) == 300
    assert len({g.id for g in walked}) == 300
    names = [g.name for g in walked]
    assert names == sorted(names, key=str.lower)


def test_numeric_sort_ascending_puts_missing_last(gadgets: DynamoRepository[Gadget]) -> None:
    matched = search.scan_matching(gadgets, lambda g: True)
    walked = _collect(gadgets, matched, lambda g: search.numeric_key(g.price_cents), limit=64)
    prices = [g.price_cents for g in walked]
    present = [p for p in prices if p is not None]
    assert present == sorted(present)
    assert prices[-12:] == [None] * 12


def test_numeric_sort_descending(gadgets: DynamoRepository[Gadget]) -> None:
    matched = search.scan_matching(gadgets, lambda g: g.price_cents is not None)
    walked = _collect(gadgets, matched, lambda g: search.numeric_key(g.price_cents, descending=True), limit=50)
    prices = [g.price_cents for g in walked]
    assert prices == sorted(prices, reverse=True)  # type: ignore[type-var]
    assert len(prices) == 288


def test_datetime_sort_descending(gadgets: DynamoRepository[Gadget]) -> None:
    matched = search.scan_matching(gadgets, lambda g: True)
    walked = _collect(gadgets, matched, lambda g: search.datetime_key(g.created_at, descending=True), limit=99)
    stamps = [g.created_at for g in walked]
    assert stamps == sorted(stamps, reverse=True)
    ascending = _collect(gadgets, matched, lambda g: search.datetime_key(g.created_at), limit=99)
    assert [g.created_at for g in ascending] == sorted(stamps)


def test_compound_key_orders_by_primary_then_secondary(gadgets: DynamoRepository[Gadget]) -> None:
    matched = search.scan_matching(gadgets, lambda g: True)
    walked = _collect(
        gadgets,
        matched,
        lambda g: search.compound_key(search.text_key(g.owner_id), search.datetime_key(g.created_at, descending=True)),
        limit=41,
    )
    pairs = [(g.owner_id, g.created_at) for g in walked]
    assert pairs == sorted(pairs, key=lambda pair: (pair[0], -pair[1].timestamp()))
