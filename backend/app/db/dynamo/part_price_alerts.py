"""Per-user price-drop alert subscriptions on DynamoDB.

One item per (user, part) pair: re-subscribing updates the threshold instead
of creating a duplicate. The ``user_id-part_id-index`` GSI answers both
"this user's alerts" and the per-pair lookup; ``part_id-index`` serves the
evaluator that runs after every price observation.
"""

from datetime import datetime
from typing import Iterable
from uuid import UUID

from pydantic import Field
from uuid6 import uuid7

from app.db.dynamo.models import TimestampedDynamoModel
from app.db.dynamo.repository import DynamoRepository, RangeCondition
from app.db.dynamo.tables import PART_PRICE_ALERTS

USER_INDEX = "user_id-part_id-index"
PART_INDEX = "part_id-index"


class PartPriceAlert(TimestampedDynamoModel):
    """A user's subscription to a price threshold on a part."""

    id: UUID = Field(default_factory=uuid7)  # pyright: ignore[reportIncompatibleVariableOverride]
    user_id: UUID
    part_id: UUID
    threshold_cents: int = Field(ge=0)
    active: bool = True
    last_fired_at: datetime | None = None


class PartPriceAlertRepository(DynamoRepository[PartPriceAlert]):
    def __init__(self) -> None:
        super().__init__(PartPriceAlert, PART_PRICE_ALERTS)

    def get_for_user_part(self, user_id: UUID, part_id: UUID) -> PartPriceAlert | None:
        page = self.query(USER_INDEX, user_id, range_condition=RangeCondition.eq(part_id), limit=1)
        return page.items[0] if page.items else None

    def list_by_user(self, user_id: UUID) -> list[PartPriceAlert]:
        return self.query_all(USER_INDEX, user_id)

    def list_active_by_user(self, user_id: UUID) -> list[PartPriceAlert]:
        """The user's active alerts, newest first."""
        alerts = [alert for alert in self.list_by_user(user_id) if alert.active]
        return sorted(alerts, key=lambda alert: (alert.created_at, str(alert.id)), reverse=True)

    def list_by_part(self, part_id: UUID) -> list[PartPriceAlert]:
        return self.query_all(PART_INDEX, part_id)

    def active_at_or_below(self, part_id: UUID, price_cents: int) -> list[PartPriceAlert]:
        """Active alerts on the part whose threshold the given price meets."""
        return [alert for alert in self.list_by_part(part_id) if alert.active and alert.threshold_cents >= price_cents]

    def count(self) -> int:
        return len(self.scan_all())

    def delete_for_parts(self, part_ids: Iterable[UUID]) -> int:
        keys = [str(alert.id) for part_id in set(part_ids) for alert in self.list_by_part(part_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)

    def delete_for_user(self, user_id: UUID) -> int:
        keys = [str(alert.id) for alert in self.list_by_user(user_id)]
        if keys:
            self.batch_delete(keys)
        return len(keys)
