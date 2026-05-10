import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .part import Part
    from .user import User


class PartManufacturer(Base):
    __tablename__ = "part_manufacturers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    name: Mapped[str] = mapped_column(nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    # True only for crawler/admin-created brands. Drives all catalog visibility filters.
    # UGC manufacturers (created by regular users) stay reachable by id but are excluded
    # from catalog list/search/facets so one user's "Honda" entry doesn't pollute browsing.
    is_curated: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    parts: Mapped[list["Part"]] = relationship("Part", back_populates="part_manufacturer")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        # Curated brands are globally unique by case-insensitive name.
        Index(
            "uq_pm_curated_name",
            func.lower(name),
            unique=True,
            postgresql_where=is_curated.is_(True),
            sqlite_where=is_curated.is_(True),
        ),
        # Each user gets at most one UGC row per case-insensitive name.
        Index(
            "uq_pm_ugc_per_user",
            func.lower(name),
            created_by_user_id,
            unique=True,
            postgresql_where=is_curated.is_(False),
            sqlite_where=is_curated.is_(False),
        ),
    )
