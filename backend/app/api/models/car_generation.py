import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .car_model import CarModel
    from .part import Part
    from .vote import Vote


class CarGeneration(Base):
    """
    Centrally managed car generation entity.
    A generation groups multiple model years together (e.g., "5th Gen Civic" for 2006-2011).
    Links to CarMake via CarModel (car_model_id -> CarModel -> CarMake).
    Build lists can be linked to car generations.
    """

    __tablename__ = "car_generations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    car_model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_name: Mapped[str] = mapped_column(nullable=False)  # e.g., "5th Gen", "MK7", "F30"
    start_year: Mapped[int] = mapped_column(nullable=False)
    end_year: Mapped[Optional[int]] = mapped_column(nullable=True)  # None for current/ongoing generations
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_model: Mapped["CarModel"] = relationship("CarModel", back_populates="car_generations")
    build_lists: Mapped[List["BuildList"]] = relationship("BuildList", back_populates="car_generation")
    parts: Mapped[List["Part"]] = relationship(
        "Part",
        secondary="part_cars",
        back_populates="car_generations",
    )
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == CarGeneration.id, Vote.entity_type == 'car_generation')",
        cascade="all, delete-orphan",
        overlaps="votes",
    )

    # Denormalized name accessors from the CarMake/CarModel chain
    @property
    def car_make_name(self) -> str:
        return self.car_model.car_make.name

    @property
    def car_model_name(self) -> str:
        return self.car_model.name
