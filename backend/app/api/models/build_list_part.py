from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .build_list_phase import BuildListPhase
    from .global_part import GlobalPart
    from .user import User


class BuildListPart(Base):
    """
    Build list part relationship model - represents the relationship between
    a catalog part and a build list, with additional metadata like notes.
    This allows users to add global catalog parts to their personal build lists.
    """

    __tablename__ = "build_list_parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_list_id: Mapped[int] = mapped_column(ForeignKey("build_lists.id"), nullable=False)
    global_part_id: Mapped[int] = mapped_column(ForeignKey("global_parts.id"), nullable=False)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(nullable=True)
    purchased: Mapped[bool] = mapped_column(default=False, nullable=False)
    added_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    build_list_phase_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("build_list_phases.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="build_list_parts")
    build_list_phase: Mapped[Optional["BuildListPhase"]] = relationship(
        "BuildListPhase", back_populates="build_list_parts", foreign_keys=[build_list_phase_id]
    )
    global_part: Mapped["GlobalPart"] = relationship("GlobalPart", back_populates="build_list_parts")
    user: Mapped["User"] = relationship("User", back_populates="build_list_parts")
