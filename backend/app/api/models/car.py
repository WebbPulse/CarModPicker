from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .report import Report
    from .user import User
    from .vote import Vote


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    make: Mapped[str] = mapped_column(index=True, nullable=False)
    model: Mapped[str] = mapped_column(index=True, nullable=False)
    year: Mapped[int] = mapped_column(index=True, nullable=False)
    trim: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # owner
    user: Mapped["User"] = relationship("User", back_populates="cars")
    # children
    build_lists: Mapped[List["BuildList"]] = relationship(
        "BuildList", back_populates="car", cascade="all, delete-orphan"
    )
    # votes and reports
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == Car.id, Vote.entity_type == 'car')",
        cascade="all, delete-orphan",
        overlaps="votes",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == Car.id, Report.entity_type == 'car')",
        cascade="all, delete-orphan",
        overlaps="reports",
    )
