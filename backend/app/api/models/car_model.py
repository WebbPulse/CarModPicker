"""
CarModel entity - e.g. Civic, Camry, F-150.
Dedicated entity for model line; belongs to a Make. Car (generation) links to CarModel.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .car import Car
    from .make import Make


class CarModel(Base):
    """
    Model line (e.g. Civic, Camry) under a Make.
    Unique per make: (make_id, name).
    """

    __tablename__ = "car_models"
    __table_args__ = (UniqueConstraint("make_id", "name", name="uq_car_models_make_id_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    make_id: Mapped[int] = mapped_column(ForeignKey("makes.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    make: Mapped["Make"] = relationship("Make", back_populates="car_models")
    cars: Mapped[List["Car"]] = relationship(
        "Car",
        back_populates="car_model",
        cascade="all, delete-orphan",
    )
