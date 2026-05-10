import uuid
from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

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
