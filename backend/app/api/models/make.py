"""
Make entity - e.g. Honda, Toyota, Ford.
Dedicated entity for car manufacturer names; Car (generation) links via CarModel.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, List

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .car_model import CarModel


class Make(Base):
    __tablename__ = "makes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_models: Mapped[List["CarModel"]] = relationship("CarModel", back_populates="make", cascade="all, delete-orphan")
