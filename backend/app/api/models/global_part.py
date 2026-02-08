from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

from .global_part_car import global_part_cars

if TYPE_CHECKING:
    from .brand import Brand
    from .build_list_part import BuildListPart
    from .car import Car
    from .category import Category
    from .part_listing import PartListing
    from .report import Report
    from .user import User
    from .vote import Vote


class GlobalPart(Base):
    """
    Global catalog part model - represents shared parts in the global catalog.
    These parts can be added to multiple build lists by different users.
    """

    __tablename__ = "global_parts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Gallery images (file keys)

    # New fields for shared architecture
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # Creator
    is_universal: Mapped[bool] = mapped_column(default=False, nullable=False)
    """When True, part fits all cars; no need to list every car_id in global_part_cars."""
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brands.id"), nullable=True, index=True
    )  # Optional brand association
    part_number: Mapped[Optional[str]] = mapped_column(nullable=True)
    gtin: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)  # UPC/EAN/GTIN for dedup
    specifications: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Quality and moderation
    is_verified: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(default="user_created")  # 'user_created', 'scraped', 'verified'
    edit_count: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="global_parts")
    creator: Mapped["User"] = relationship("User", back_populates="global_parts")
    cars: Mapped[List["Car"]] = relationship(
        "Car",
        secondary=global_part_cars,
        back_populates="global_parts",
        lazy="selectin",
    )
    brand: Mapped[Optional["Brand"]] = relationship("Brand", back_populates="global_parts")

    @property
    def car_ids(self) -> List[int]:
        """IDs of cars this part is associated with (empty if is_universal)."""
        return [c.id for c in self.cars]

    build_list_parts: Mapped[list["BuildListPart"]] = relationship(
        "BuildListPart", back_populates="global_part", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(
        "Vote",
        foreign_keys="[Vote.entity_id]",
        primaryjoin="and_(Vote.entity_id == GlobalPart.id, Vote.entity_type == 'global_part')",
        cascade="all, delete-orphan",
        overlaps="votes,votes",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        foreign_keys="[Report.entity_id]",
        primaryjoin="and_(Report.entity_id == GlobalPart.id, Report.entity_type == 'global_part')",
        cascade="all, delete-orphan",
        overlaps="reports,reports",
    )
    part_listings: Mapped[list["PartListing"]] = relationship(
        "PartListing", back_populates="global_part", cascade="all, delete-orphan"
    )
