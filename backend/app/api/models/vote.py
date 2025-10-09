from typing import Optional, TYPE_CHECKING
from datetime import datetime, UTC

from sqlalchemy import ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User
    from .car import Car
    from .build_list import BuildList
    from .global_part import GlobalPart


class Vote(Base):
    """
    Unified vote model that can be applied to any entity type.
    Uses polymorphic association to link votes to different entity types.
    """
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    vote_type: Mapped[str] = mapped_column(nullable=False)  # 'upvote', 'downvote'
    
    # Polymorphic entity reference
    entity_type: Mapped[str] = mapped_column(nullable=False)  # 'car', 'build_list', 'global_part'
    entity_id: Mapped[int] = mapped_column(nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="votes")
    
    # Polymorphic relationships (these will be handled by the entity models)
    car: Mapped[Optional["Car"]] = relationship(
        "Car", 
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == Car.id, Vote.entity_type == 'car')",
        viewonly=True
    )
    build_list: Mapped[Optional["BuildList"]] = relationship(
        "BuildList", 
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == BuildList.id, Vote.entity_type == 'build_list')",
        viewonly=True
    )
    global_part: Mapped[Optional["GlobalPart"]] = relationship(
        "GlobalPart", 
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == GlobalPart.id, Vote.entity_type == 'global_part')",
        viewonly=True
    )

    # Ensure one vote per user per entity
    __table_args__ = (
        UniqueConstraint("user_id", "entity_type", "entity_id", name="unique_user_entity_vote"),
        Index("ix_votes_entity", "entity_type", "entity_id"),
        Index("ix_votes_user_entity_type", "user_id", "entity_type"),
    )
