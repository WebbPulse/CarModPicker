import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .part import Part
    from .user import User


class Report(Base):
    """
    Unified report model that can be applied to any entity type.
    Uses polymorphic association to link reports to different entity types.
    """

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Polymorphic entity reference
    entity_type: Mapped[str] = mapped_column(nullable=False)  # 'build_list', 'part'
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)  # 'inappropriate', 'spam', 'inaccurate', 'duplicate', 'other'
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        default="pending", nullable=False
    )  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    reporter: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="reports")
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])

    # Polymorphic relationships (these will be handled by the entity models)
    build_list: Mapped[Optional["BuildList"]] = relationship(
        "BuildList",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == BuildList.id, Report.entity_type == 'build_list')",
        viewonly=True,
    )
    part: Mapped[Optional["Part"]] = relationship(
        "Part",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == Part.id, Report.entity_type == 'part')",
        viewonly=True,
    )

    __table_args__ = (
        Index("ix_reports_entity", "entity_type", "entity_id"),
        Index("ix_reports_status", "status"),
        Index("ix_reports_user_entity_type", "user_id", "entity_type"),
    )
