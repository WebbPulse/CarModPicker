import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .build_list_phase import BuildListPhase


class BuildListLaborEstimate(Base):
    """
    Standalone labor / non-part cost line item attached to a build list.
    Captures costs that aren't tied to a specific catalog part (paint,
    install labor, fabrication, tuning, etc.). Optionally rolls into a
    phase the same way parts do.
    """

    __tablename__ = "build_list_labor_estimates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    build_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("build_lists.id"), nullable=False, index=True
    )
    build_list_phase_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("build_list_phases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    cost_cents: Mapped[int] = mapped_column(default=0, nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="build_list_labor_estimates")
    build_list_phase: Mapped[Optional["BuildListPhase"]] = relationship(
        "BuildListPhase", back_populates="build_list_labor_estimates", foreign_keys=[build_list_phase_id]
    )
