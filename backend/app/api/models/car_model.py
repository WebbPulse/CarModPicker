"""
CarModel entity - e.g. Civic, Camry, F-150.
Dedicated entity for model line; belongs to a CarMake. CarGeneration links to CarModel.
"""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid, event
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.core.car_generations_data import slugify
from app.db.base_class import Base

if TYPE_CHECKING:
    from .car_generation import CarGeneration
    from .car_make import CarMake


class CarModel(Base):
    """
    Model line (e.g. Civic, Camry) under a CarMake.
    Unique per car_make: (car_make_id, name).
    """

    __tablename__ = "car_models"
    __table_args__ = (
        UniqueConstraint("car_make_id", "name", name="uq_car_models_car_make_id_name"),
        UniqueConstraint("car_make_id", "slug", name="uq_car_models_car_make_id_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    car_make_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("car_makes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Stable identifier used by init_cars for lookup. Pin it explicitly in seed data to rename `name`
    # without losing the row. Defaults to slugify(name) on first insert; treated as immutable afterwards.
    slug: Mapped[str] = mapped_column(nullable=False, index=True)
    name: Mapped[str] = mapped_column(nullable=False, index=True)
    # Presentation-only label. NEVER feed into car_inference (CAR_ALIASES / PHRASE_TRIPLES).
    # NULL means "fall back to name" in the UI; inference always operates on `name`.
    display_name: Mapped[Optional[str]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_make: Mapped["CarMake"] = relationship("CarMake", back_populates="car_models")
    car_generations: Mapped[List["CarGeneration"]] = relationship(
        "CarGeneration",
        back_populates="car_model",
        cascade="all, delete-orphan",
    )


@event.listens_for(CarModel, "before_insert")
def _autofill_car_model_slug(_mapper, _conn, target: CarModel) -> None:
    """Fill `slug` from `name` if the caller didn't pin one. Matches the field's docstring
    promise ("defaults to slugify(name) on first insert"). init_cars passes `slug` explicitly
    so this only kicks in for ad-hoc inserts (tests, admin flows)."""
    if not getattr(target, "slug", None) and getattr(target, "name", None):
        target.slug = slugify(target.name)
