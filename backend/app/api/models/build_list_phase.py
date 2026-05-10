import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .build_list_labor_estimate import BuildListLaborEstimate
    from .build_list_part import BuildListPart


class BuildListPhase(Base):
    """
    Build list phase (or priority group) - user-defined grouping for parts
    within a build list. Each part can be assigned to at most one phase.
    """

    __tablename__ = "build_list_phases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    build_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("build_lists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="build_list_phases")
    build_list_parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart",
        back_populates="build_list_phase",
        foreign_keys="BuildListPart.build_list_phase_id",
    )
    build_list_labor_estimates: Mapped[List["BuildListLaborEstimate"]] = relationship(
        "BuildListLaborEstimate",
        back_populates="build_list_phase",
        foreign_keys="BuildListLaborEstimate.build_list_phase_id",
    )
