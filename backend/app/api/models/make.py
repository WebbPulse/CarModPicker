"""
Make entity - e.g. Honda, Toyota, Ford.
Dedicated entity for car manufacturer names; Car (generation) links via CarModel.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .car_model import CarModel


class Make(Base):
    __tablename__ = "makes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_models: Mapped[List["CarModel"]] = relationship("CarModel", back_populates="make", cascade="all, delete-orphan")
