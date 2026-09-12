"""Covers model defaults and the item serialization layer, including the derived attributes written on save."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.db.dynamo.models import DynamoModel, TimestampedDynamoModel
from app.db.dynamo.serialization import (
    apply_derived_attributes,
    decode_bytes,
    encode_bytes,
    encode_datetime,
    from_dynamo_value,
    from_item,
    to_dynamo_value,
    to_item,
    unique_lookup_key,
)
from app.db.dynamo.tables import PARTS, USERS, VOTES


class Color(str, Enum):
    """A string enum used to check enum serialization."""

    RED = "red"


class Sample(TimestampedDynamoModel):
    """A model covering every field type the serializer handles."""

    name: str
    external_id: UUID | None = None
    secret: bytes | None = None
    score: int = 0
    ratio: float | None = None
    price: Decimal | None = None
    tags: list[str] = []
    meta: dict[str, Any] = {}
    color: Color = Color.RED
    missing: str | None = None


def test_dynamo_model_defaults_to_uuid7_string() -> None:
    """Ids default to uuid7 strings, which sort by creation time."""
    first = DynamoModel()
    second = DynamoModel()
    assert isinstance(first.id, str)
    assert UUID(first.id).version == 7
    assert first.id < second.id


def test_dynamo_model_ignores_extra_attributes() -> None:
    """Derived attributes read back off an item do not become model fields."""
    model = DynamoModel.model_validate({"id": "abc", "username_lower": "x"})
    assert model.id == "abc"
    assert not hasattr(model, "username_lower")


def test_touch_bumps_updated_at() -> None:
    """touch advances updated_at."""
    model = TimestampedDynamoModel()
    before = model.updated_at
    model.touch()
    assert model.updated_at >= before


def test_datetime_encoding_is_fixed_width_utc() -> None:
    """Datetimes encode to fixed width UTC, so string comparison sorts them."""
    naive = datetime(2026, 1, 2, 3, 4, 5)
    aware = datetime(2026, 1, 2, 5, 4, 5, tzinfo=timezone(timedelta(hours=2)))
    assert encode_datetime(naive) == "2026-01-02T03:04:05.000000Z"
    assert encode_datetime(aware) == "2026-01-02T03:04:05.000000Z"
    assert len(encode_datetime(datetime.now(UTC))) == len(encode_datetime(naive))


def test_bytes_round_trip_without_padding() -> None:
    """Bytes round trip through an unpadded encoding."""
    raw = bytes(range(0, 40))
    encoded = encode_bytes(raw)
    assert "=" not in encoded
    assert decode_bytes(encoded) == raw


def test_to_dynamo_value_conversions() -> None:
    """Values convert to their DynamoDB forms, Nones are dropped and unknown types raise."""
    uid = uuid4()
    assert to_dynamo_value(uid) == str(uid)
    assert to_dynamo_value(1.5) == Decimal("1.5")
    assert to_dynamo_value(True) is True
    assert to_dynamo_value(Color.RED) == "red"
    assert to_dynamo_value({"a": None, "b": [uid]}) == {"b": [str(uid)]}
    assert to_dynamo_value((1, 2)) == [1, 2]
    with pytest.raises(TypeError):
        to_dynamo_value(object())


def test_from_dynamo_value_decimals() -> None:
    """Whole Decimals come back as ints and fractional ones as floats, recursively."""
    assert from_dynamo_value(Decimal("3")) == 3
    assert isinstance(from_dynamo_value(Decimal("3")), int)
    assert from_dynamo_value(Decimal("2.5")) == 2.5
    assert from_dynamo_value({"n": [Decimal("1"), Decimal("0.5")]}) == {"n": [1, 0.5]}


def test_to_item_drops_none_and_round_trips() -> None:
    """Serializing drops unset fields and the item round trips back to the model."""
    model = Sample(
        name="Widget",
        external_id=uuid4(),
        secret=b"\x00\xffbinary",
        score=7,
        ratio=0.25,
        price=Decimal("19.99"),
        tags=["a", "b"],
        meta={"nested": {"x": 1.5, "y": [uuid4()]}},
    )
    item = to_item(model)
    assert "missing" not in item
    assert item["external_id"] == str(model.external_id)
    assert item["secret"] == encode_bytes(b"\x00\xffbinary")
    assert item["ratio"] == Decimal("0.25")
    assert item["created_at"].endswith("Z")

    restored = from_item(item, Sample)
    expected = model.model_dump()
    expected["meta"]["nested"]["y"] = [str(value) for value in expected["meta"]["nested"]["y"]]
    assert restored.model_dump() == expected


def test_from_item_decodes_bytes_only_for_bytes_fields() -> None:
    """An encoded string is decoded only where the field is typed bytes."""
    encoded = encode_bytes(b"abc")
    restored = from_item({"id": "1", "name": encoded, "secret": encoded}, Sample)
    assert restored.name == encoded
    assert restored.secret == b"abc"


def test_lowercase_mirrors_computed_on_write() -> None:
    """Lowercase mirror attributes are computed on write."""

    class User(DynamoModel):
        """A minimal user carrying the two mirrored fields."""

        username: str
        email: str

    item = to_item(User(username="TylerW", email="Tyler@Example.com"), USERS)
    assert item["username_lower"] == "tylerw"
    assert item["email_lower"] == "tyler@example.com"


def test_composite_key_computed_on_write() -> None:
    """Composite key attributes are computed on write."""

    class Vote(DynamoModel):
        """A minimal vote carrying the composite key sources."""

        user_id: str
        entity_type: str
        entity_id: UUID

    entity_id = uuid4()
    item = to_item(Vote(user_id="u", entity_type="part", entity_id=entity_id), VOTES)
    assert item["entity_key"] == f"part#{entity_id}"


def test_coalesced_key_prefers_first_present_source() -> None:
    """A coalesced key takes the first source that is present."""

    class Part(DynamoModel):
        """A minimal part carrying the coalesced key source."""

        canonical_part_id: str | None = None

    own = to_item(Part(id="p1"), PARTS)
    assert own["canonical_id"] == "p1"
    duplicate = to_item(Part(id="p2", canonical_part_id="p1"), PARTS)
    assert duplicate["canonical_id"] == "p1"


def test_apply_derived_skips_missing_sources() -> None:
    """A derived attribute whose sources are absent is not written."""
    item = apply_derived_attributes({"id": "x"}, VOTES)
    assert "entity_key" not in item


def test_unique_lookup_key_shape() -> None:
    """The uniqueness sentinel key carries the field and value."""
    assert unique_lookup_key("email", "a@b.c") == "#unique#email#a@b.c"
