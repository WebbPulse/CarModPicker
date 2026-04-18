import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .car_generation import CarGeneration
    from .part import Part
    from .user import User


class Vote(Base):
    """
    Unified vote model that can be applied to any entity type.
    Uses polymorphic association to link votes to different entity types.
    """

    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    vote_type: Mapped[str] = mapped_column(nullable=False)  # 'upvote', 'downvote'

    # Polymorphic entity reference
    entity_type: Mapped[str] = mapped_column(nullable=False)  # 'car', 'build_list', 'part'
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="votes")

    # Polymorphic relationships (these will be handled by the entity models)
    car_generation: Mapped[Optional["CarGeneration"]] = relationship(
        "Car",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == CarGeneration.id, Vote.entity_type == 'car_generation')",
        viewonly=True,
    )
    build_list: Mapped[Optional["BuildList"]] = relationship(
        "BuildList",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == BuildList.id, Vote.entity_type == 'build_list')",
        viewonly=True,
    )
    part: Mapped[Optional["Part"]] = relationship(
        "Part",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == Part.id, Vote.entity_type == 'part')",
        viewonly=True,
    )

    # Ensure one vote per user per entity
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="unique_user_entity_vote"),
        Index("ix_votes_entity", "entity_type", "entity_id"),
        Index("ix_votes_user_entity_type", "user_id", "entity_type"),
    )
