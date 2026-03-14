from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .build_list_part import BuildListPart


class BuildListPhase(Base):
    """
    Build list phase (or priority group) - user-defined grouping for parts
    within a build list. Each part can be assigned to at most one phase.
    """

    __tablename__ = "build_list_phases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_list_id: Mapped[int] = mapped_column(ForeignKey("build_lists.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    # Relationships
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="build_list_phases")
    build_list_parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart",
        back_populates="build_list_phase",
        foreign_keys="BuildListPart.build_list_phase_id",
    )
