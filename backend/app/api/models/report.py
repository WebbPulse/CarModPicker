import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.db.base_class import Base


class Report(Base):
    """
    Unified report model that can be applied to any entity type.
    Uses polymorphic association to link reports to different entity types.
    """

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    # Polymorphic entity reference
    entity_type: Mapped[str] = mapped_column(nullable=False)  # 'build_list', 'part'
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    reason: Mapped[str] = mapped_column(nullable=False)  # 'inappropriate', 'spam', 'inaccurate', 'duplicate', 'other'
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        default="pending", nullable=False
    )  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_reports_entity", "entity_type", "entity_id"),
        Index("ix_reports_status", "status"),
        Index("ix_reports_user_entity_type", "user_id", "entity_type"),
    )
