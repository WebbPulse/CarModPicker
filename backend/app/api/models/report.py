from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .car import Car
    from .global_part import GlobalPart
    from .user import User


class Report(Base):
    """
    Unified report model that can be applied to any entity type.
    Uses polymorphic association to link reports to different entity types.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Polymorphic entity reference
    entity_type: Mapped[str] = mapped_column(nullable=False)  # 'car', 'build_list', 'global_part'
    entity_id: Mapped[int] = mapped_column(nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)  # 'inappropriate', 'spam', 'inaccurate', 'duplicate', 'other'
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        default="pending", nullable=False
    )  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    reporter: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="reports")
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])

    # Polymorphic relationships (these will be handled by the entity models)
    car: Mapped[Optional["Car"]] = relationship(
        "Car",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == Car.id, Report.entity_type == 'car')",
        viewonly=True,
    )
    build_list: Mapped[Optional["BuildList"]] = relationship(
        "BuildList",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == BuildList.id, Report.entity_type == 'build_list')",
        viewonly=True,
    )
    global_part: Mapped[Optional["GlobalPart"]] = relationship(
        "GlobalPart",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == GlobalPart.id, Report.entity_type == 'global_part')",
        viewonly=True,
    )

    __table_args__ = (
        Index("ix_reports_entity", "entity_type", "entity_id"),
        Index("ix_reports_status", "status"),
        Index("ix_reports_user_entity_type", "user_id", "entity_type"),
    )
