from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .global_part import GlobalPart
    from .vote import Vote


class Car(Base):
    """
    Centrally managed car entity representing a car generation.
    A generation groups multiple model years together (e.g., "5th Gen Civic" for 2006-2011).
    This is manually managed by admins.
    Build lists can be linked to cars (generations).
    """

    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    make: Mapped[str] = mapped_column(index=True, nullable=False)
    model: Mapped[str] = mapped_column(index=True, nullable=False)
    generation_name: Mapped[str] = mapped_column(nullable=False)  # e.g., "5th Gen", "MK7", "F30"
    start_year: Mapped[int] = mapped_column(nullable=False)
    end_year: Mapped[Optional[int]] = mapped_column(nullable=True)  # None for current/ongoing generations
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    build_lists: Mapped[List["BuildList"]] = relationship("BuildList", back_populates="car")
    global_parts: Mapped[List["GlobalPart"]] = relationship("GlobalPart", back_populates="car")
    # votes
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == Car.id, Vote.entity_type == 'car')",
        cascade="all, delete-orphan",
        overlaps="votes",
    )
