"""Test-only SQLAlchemy model.

The generic SQL helpers in ``app.api.utils`` (``common_operations``,
``common_patterns``, ``pagination_utils``) are still exercised by tests but
no longer have a real domain table to run against. This stand-in keeps those
tests meaningful until the helpers themselves are removed.
"""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from app.db.base_class import Base


class StubRecord(Base):
    __tablename__ = "test_stub_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
