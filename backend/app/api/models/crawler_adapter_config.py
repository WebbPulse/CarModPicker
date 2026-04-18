import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .category import Category


class CrawlerAdapterConfig(Base):
    """
    Per-adapter retailer tuning that travels with the adapter across every
    schedule it's a member of.

    One row per name in ``ADAPTER_REGISTRY``; seeded on startup. Rows are NOT
    deleted when an adapter is removed from a schedule, so tuning learned for a
    retailer (e.g. a safe delay that avoids bans) is preserved and reused if
    the adapter is later re-added.
    """

    __tablename__ = "crawler_adapter_configs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    adapter_name: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)

    delay_sec: Mapped[float] = mapped_column(default=5.0, nullable=False)
    per_run_limit: Mapped[Optional[int]] = mapped_column(nullable=True)
    skip_known_urls: Mapped[bool] = mapped_column(default=False, nullable=False)

    default_category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    default_category: Mapped["Category"] = relationship("Category")
