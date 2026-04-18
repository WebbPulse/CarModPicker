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


class Car(Base):
    """
    Centrally managed car entity representing a car generation.
    A generation groups multiple model years together (e.g., "5th Gen Civic" for 2006-2011).
    Links to Make via CarModel (car_model_id -> CarModel -> Make).
    Build lists can be linked to cars (generations).
    """

    __tablename__ = "cars"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    car_model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation_name: Mapped[str] = mapped_column(nullable=False)  # e.g., "5th Gen", "MK7", "F30"
    start_year: Mapped[int] = mapped_column(nullable=False)
    end_year: Mapped[Optional[int]] = mapped_column(nullable=True)  # None for current/ongoing generations
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Car image(s)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_model: Mapped["CarModel"] = relationship("CarModel", back_populates="cars")
    build_lists: Mapped[List["BuildList"]] = relationship("BuildList", back_populates="car")
    parts: Mapped[List["Part"]] = relationship(
        "Part",
        secondary="part_cars",
        back_populates="cars",
    )
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == Car.id, Vote.entity_type == 'car')",
        cascade="all, delete-orphan",
        overlaps="votes",
    )

    # API backward compatibility: expose make/model as properties (from car_model.make.name, car_model.name)
    @property
    def make(self) -> str:
        return self.car_model.make.name

    @property
    def model(self) -> str:
        return self.car_model.name
