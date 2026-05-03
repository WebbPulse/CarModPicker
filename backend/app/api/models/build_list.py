import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list_labor_estimate import BuildListLaborEstimate
    from .build_list_part import BuildListPart
    from .build_list_phase import BuildListPhase
    from .build_log import BuildLog
    from .car_generation import CarGeneration
    from .report import Report
    from .user import User
    from .vote import Vote


class BuildList(Base):
    __tablename__ = "build_lists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(index=True, nullable=True)
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Build list cover image(s)
    car_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("car_generations.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    car_generation: Mapped[Optional["CarGeneration"]] = relationship("CarGeneration", back_populates="build_lists")
    owner: Mapped["User"] = relationship("User", back_populates="build_lists")
    build_list_parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart",
        back_populates="build_list",
        cascade="all, delete-orphan",
        lazy="raise",  # Phase 4 D-28 / DATA-10 — catches future N+1 regressions; paired with selectinload in callers
    )
    build_list_phases: Mapped[List["BuildListPhase"]] = relationship(
        "BuildListPhase",
        back_populates="build_list",
        cascade="all, delete-orphan",
        order_by="BuildListPhase.sort_order",
        lazy="raise",  # Phase 4 D-28 / DATA-10 — catches future N+1 regressions; paired with selectinload in callers
    )
    build_list_labor_estimates: Mapped[List["BuildListLaborEstimate"]] = relationship(
        "BuildListLaborEstimate",
        back_populates="build_list",
        cascade="all, delete-orphan",
        order_by="BuildListLaborEstimate.sort_order",
        lazy="raise",
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
    build_log: Mapped[Optional["BuildLog"]] = relationship(
        "BuildLog",
        back_populates="build_list",
        uselist=False,
        cascade="all, delete-orphan",
    )
