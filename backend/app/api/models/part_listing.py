import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .part import Part
    from .part_price_history import PartPriceHistory
    from .retailer import Retailer


class PartListing(Base):
    """
    "This part at this retailer" - one row per (part_id, retailer_id).
    Holds the product URL for that part at that retailer and optional latest price snapshot.
    """

    __tablename__ = "part_listings"
    __table_args__ = (UniqueConstraint("part_id", "retailer_id", name="uq_part_listing_part_retailer"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("parts.id"), nullable=False, index=True)
    retailer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retailers.id"), nullable=False, index=True
    )
    product_url: Mapped[Optional[str]] = mapped_column(nullable=True)  # product page at this retailer
    last_known_price_cents: Mapped[Optional[int]] = mapped_column(nullable=True)
    last_price_updated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    part: Mapped["Part"] = relationship("Part", back_populates="part_listings")
    retailer: Mapped["Retailer"] = relationship("Retailer", back_populates="part_listings")
    price_history: Mapped[list["PartPriceHistory"]] = relationship(
        "PartPriceHistory",
        back_populates="part_listing",
        cascade="all, delete-orphan",
    )
