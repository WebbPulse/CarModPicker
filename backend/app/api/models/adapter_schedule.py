import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .category import Category


class AdapterSchedule(Base):
    """
    Per-adapter crawler schedule and run configuration.

    One row per registered crawler adapter (see ADAPTER_REGISTRY). Rows are
    upserted on application startup so the table stays in lock-step with the
    code-registered adapters.

    The reconciler (adapter_schedule_service.reconcile_adapter_schedule) writes
    these settings to an EventBridge Scheduler schedule named
    ``{prefix}-crawler-{adapter_name}`` in SCHEDULER_GROUP_NAME. The DB row is
    always the source of truth; AWS state is reconciled from it on every write.
    """

    __tablename__ = "adapter_schedules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    adapter_name: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)

    enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    schedule_expression: Mapped[str] = mapped_column(default="cron(0 2 1 * ? *)", nullable=False)
    delay_sec: Mapped[float] = mapped_column(default=5.0, nullable=False)
    per_run_limit: Mapped[Optional[int]] = mapped_column(nullable=True)
    skip_known_urls: Mapped[bool] = mapped_column(default=False, nullable=False)

    default_category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    last_reconciled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_reconcile_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    default_category: Mapped["Category"] = relationship("Category")
