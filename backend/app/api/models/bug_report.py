import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.db.base_class import Base


class BugReport(Base):
    """
    Bug report model for users to report bugs/issues with the application.
    """

    __tablename__ = "bug_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)

    # Bug report fields
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    steps_to_reproduce: Mapped[Optional[str]] = mapped_column(nullable=True)
    expected_behavior: Mapped[Optional[str]] = mapped_column(nullable=True)
    actual_behavior: Mapped[Optional[str]] = mapped_column(nullable=True)
    browser_info: Mapped[Optional[str]] = mapped_column(nullable=True)
    device_info: Mapped[Optional[str]] = mapped_column(nullable=True)
    screenshot_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(
        default="pending", nullable=False
    )  # 'pending', 'in_progress', 'resolved', 'dismissed'
    priority: Mapped[str] = mapped_column(default="medium", nullable=False)  # 'low', 'medium', 'high', 'critical'
    admin_notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_bug_reports_status", "status"),
        Index("ix_bug_reports_priority", "priority"),
        Index("ix_bug_reports_user_id", "user_id"),
        Index("ix_bug_reports_created_at", "created_at"),
    )
