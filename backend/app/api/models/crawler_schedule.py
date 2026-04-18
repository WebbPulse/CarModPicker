import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base


class CrawlerScheduleAdapter(Base):
    """
    Join row connecting a ``crawler_schedules`` row to a registered adapter by
    name. ``adapter_name`` is the natural key used by ``ADAPTER_REGISTRY``,
    ``crawler_adapter_configs.adapter_name``, and the run endpoint's payload —
    it's the shared identifier across the crawler subsystem, so we don't route
    through ``crawler_adapter_configs.id`` here.
    """

    __tablename__ = "crawler_schedule_adapters"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("crawler_schedules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    adapter_name: Mapped[str] = mapped_column(primary_key=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)


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
