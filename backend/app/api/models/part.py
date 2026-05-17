import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

from .associations.part_car import part_cars

if TYPE_CHECKING:
    from .build_list_part import BuildListPart
    from .car_generation import CarGeneration
    from .category import Category
    from .part_listing import PartListing
    from .part_manufacturer import PartManufacturer
    from .report import Report
    from .user import User
    from .vote import Vote


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    is_universal: Mapped[bool] = mapped_column(default=False, nullable=False)
    """When True, part fits all cars; no need to list every car_id in part_cars."""
    part_manufacturer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("part_manufacturers.id"), nullable=True, index=True
    )
    part_number: Mapped[Optional[str]] = mapped_column(nullable=True)
    #: Canonical alphanumeric-uppercase form of ``part_number`` used for dedup.
    #: Computed via :func:`app.crawlers.parsing.part_number_canonical` — strips
    #: separators and uppercases so ``"AEM-30-2400"`` and ``"AEM 30/2400"`` map
    #: to the same key. Indexed jointly with ``part_manufacturer_id`` for the
    #: linker's primary lookup path.
    part_number_normalized: Mapped[Optional[str]] = mapped_column(nullable=True)
    gtin: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)

    canonical_part_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """When set, this part is a duplicate whose surface representation is the referenced canonical part."""

    edit_count: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="parts")
    creator: Mapped["User"] = relationship("User", back_populates="parts")
    car_generations: Mapped[List["CarGeneration"]] = relationship(
        "CarGeneration",
        secondary=part_cars,
        back_populates="parts",
        lazy="selectin",
    )
    part_manufacturer: Mapped[Optional["PartManufacturer"]] = relationship("PartManufacturer", back_populates="parts")

    @property
    def car_ids(self) -> List[uuid.UUID]:
        """IDs of cars this part is associated with (empty if is_universal)."""
        return [c.id for c in self.car_generations]

    build_list_parts: Mapped[list["BuildListPart"]] = relationship(
        "BuildListPart", back_populates="part", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == Part.id, Vote.entity_type == 'part')",
        cascade="all, delete-orphan",
        overlaps="votes,votes",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == Part.id, Report.entity_type == 'part')",
        cascade="all, delete-orphan",
        overlaps="reports,reports",
    )
    part_listings: Mapped[list["PartListing"]] = relationship(
        "PartListing", back_populates="part", cascade="all, delete-orphan"
    )
