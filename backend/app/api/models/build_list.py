from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list_part import BuildListPart
    from .car import Car
    from .report import Report
    from .user import User
    from .vote import Vote


class BuildList(Base):
    __tablename__ = "build_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    car_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cars.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car: Mapped[Optional["Car"]] = relationship("Car", back_populates="build_lists")
    owner: Mapped["User"] = relationship("User", back_populates="build_lists")
    build_list_parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart",
        back_populates="build_list",
        cascade="all, delete-orphan",
    )
    # votes and reports
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == BuildList.id, Vote.entity_type == 'build_list')",
        cascade="all, delete-orphan",
        overlaps="votes",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == BuildList.id, Report.entity_type == 'build_list')",
        cascade="all, delete-orphan",
        overlaps="reports",
    )
