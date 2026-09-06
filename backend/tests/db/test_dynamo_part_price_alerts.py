"""Price alert repository and service on DynamoDB (moto-backed)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from uuid6 import uuid7

from app.api.schemas.part_price_alert import PartPriceAlertCreate, PartPriceAlertRead, PartPriceAlertUpdate
from app.api.services import part_price_alert_service as service
from app.db.dynamo.part_price_alerts import PartPriceAlert, PartPriceAlertRepository


def _alert(user_id: UUID, part_id: UUID, threshold_cents: int = 100, **extra: Any) -> PartPriceAlert:
    return PartPriceAlert(user_id=user_id, part_id=part_id, threshold_cents=threshold_cents, **extra)


def test_defaults_active_and_no_last_fired(dynamo_tables: Any) -> None:
    repo = PartPriceAlertRepository()
    created = repo.create(_alert(uuid7(), uuid7(), 1500))
    stored = repo.get_or_raise(created.id)

    assert stored.active is True
    assert stored.last_fired_at is None
    assert stored.threshold_cents == 1500
    assert stored.created_at is not None and stored.updated_at is not None
    assert PartPriceAlertRead.model_validate(stored).id == created.id


def test_upsert_reuses_the_user_part_pair(dynamo_tables: Any) -> None:
    repo = PartPriceAlertRepository()
    user_id, part_id = uuid7(), uuid7()

    first = service.create_or_update_alert(user_id, part_id, 5000)
    service.update_alert(first, active=False)
    second = service.create_or_update_alert(user_id, part_id, 7500)

    assert second.id == first.id
    assert second.threshold_cents == 7500 and second.active is True
    assert len(repo.list_by_part(part_id)) == 1
    assert repo.get_for_user_part(user_id, part_id) is not None
    assert repo.get_for_user_part(user_id, uuid7()) is None


def test_same_user_different_parts_and_different_users_same_part(dynamo_tables: Any) -> None:
    repo = PartPriceAlertRepository()
    alice, bob, part_a, part_b = uuid7(), uuid7(), uuid7(), uuid7()
    a1 = repo.create(_alert(alice, part_a, 1))
    a2 = repo.create(_alert(alice, part_b, 2))
    b1 = repo.create(_alert(bob, part_a, 3))

    assert {alert.id for alert in repo.list_by_user(alice)} == {a1.id, a2.id}
    assert {alert.id for alert in repo.list_by_part(part_a)} == {a1.id, b1.id}
    assert [alert.id for alert in repo.list_active_by_user(alice)] == [a2.id, a1.id]


def test_active_at_or_below_and_last_fired_at_round_trip(dynamo_tables: Any) -> None:
    repo = PartPriceAlertRepository()
    part_id = uuid7()
    cheap = repo.create(_alert(uuid7(), part_id, 5000))
    repo.create(_alert(uuid7(), part_id, 10000, active=False))
    pricey = repo.create(_alert(uuid7(), part_id, 20000))

    assert {alert.id for alert in repo.active_at_or_below(part_id, 8000)} == {pricey.id}
    assert {alert.id for alert in repo.active_at_or_below(part_id, 5000)} == {cheap.id, pricey.id}

    fired_at = datetime.now(UTC) - timedelta(hours=1)
    repo.update(cheap.id, last_fired_at=fired_at)
    assert repo.get_or_raise(cheap.id).last_fired_at == fired_at


def test_owner_checks_and_purges(dynamo_tables: Any) -> None:
    repo = PartPriceAlertRepository()
    alice, bob, part_id = uuid7(), uuid7(), uuid7()
    alert = repo.create(_alert(alice, part_id))

    assert service.get_alert_for_owner(alert.id, bob) is None
    assert service.deactivate_alert(alert.id, bob) is False
    assert service.deactivate_alert(alert.id, alice) is True
    assert service.deactivate_alert(alert.id, alice) is False
    assert service.deactivate_by_id(uuid7()) is None
    assert service.deactivate_by_id(alert.id) is not None

    assert repo.delete_for_parts([part_id]) == 1
    assert repo.get(alert.id) is None
    repo.create(_alert(bob, uuid7()))
    assert repo.delete_for_user(bob) == 1
    assert repo.count() == 0


def test_schemas_enforce_non_negative_threshold() -> None:
    with pytest.raises(ValidationError):
        PartPriceAlertCreate(part_id=uuid7(), threshold_cents=-1)
    assert PartPriceAlertCreate(part_id=uuid7(), threshold_cents=0).threshold_cents == 0
    with pytest.raises(ValidationError):
        PartPriceAlertUpdate(threshold_cents=-5)
    empty = PartPriceAlertUpdate()
    assert empty.threshold_cents is None and empty.active is None
    with pytest.raises(ValidationError):
        PartPriceAlert(user_id=uuid7(), part_id=uuid7(), threshold_cents=-1)
