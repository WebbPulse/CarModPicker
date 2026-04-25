import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .part import Part
    from .user import User


class PartPriceAlert(Base):
    """
    Per-user subscription to a per-part price threshold.
    A user is notified by email when an observed price for the part drops to or below threshold_cents.
    Unique on (user_id, part_id) — re-subscribing updates the threshold instead of creating a duplicate.
    """

    __tablename__ = "part_price_alerts"
    __table_args__ = (
        UniqueConstraint("user_id", "part_id", name="uq_part_price_alert_user_part"),
        CheckConstraint("threshold_cents >= 0", name="threshold_cents_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    part_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("parts.id"), nullable=False, index=True
    )
    threshold_cents: Mapped[int] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    user: Mapped["User"] = relationship("User")
    part: Mapped["Part"] = relationship("Part")
