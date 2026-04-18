"""
CarModel entity - e.g. Civic, Camry, F-150.
Dedicated entity for model line; belongs to a Make. Car (generation) links to CarModel.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .car_generation import CarGeneration
    from .car_make import CarMake


class CarModel(Base):
    """
    Model line (e.g. Civic, Camry) under a Make.
    Unique per make: (make_id, name).
    """

    __tablename__ = "car_models"
    __table_args__ = (UniqueConstraint("car_make_id", "name", name="uq_car_models_car_make_id_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    make_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("car_makes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_make: Mapped["CarMake"] = relationship("CarMake", back_populates="car_models")
    car_generations: Mapped[List["CarGeneration"]] = relationship(
        "Car",
        back_populates="car_model",
        cascade="all, delete-orphan",
    )
