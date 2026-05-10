import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .associations.crawler_schedule_adapter import CrawlerScheduleAdapter


class CrawlerSchedule(Base):
    """
    User-defined crawler schedule: fires one EventBridge Scheduler schedule
    whose Target.Input is ``{"schedule_id": "<uuid>"}``. The run endpoint
    dereferences members and per-adapter config at firing time, so membership
    and tuning edits don't require an AWS reconcile — only ``enabled`` and
    ``schedule_expression`` changes do.

    The DB row is the source of truth; AWS state is reconciled from it on
    ``enabled``/``schedule_expression`` changes and on schedule
    create/delete.
    """

    __tablename__ = "crawler_schedules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    schedule_expression: Mapped[str] = mapped_column(default="cron(0 2 1 * ? *)", nullable=False)

    last_reconciled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_reconcile_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    adapters: Mapped[list["CrawlerScheduleAdapter"]] = relationship(
        "CrawlerScheduleAdapter",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
