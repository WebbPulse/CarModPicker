import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .part_listing import PartListing


class PartPriceHistory(Base):
    """
    Time-series price observations for a part at a retailer.
    "Current price" = latest row by observed_at per PartListing.
    """

    __tablename__ = "part_price_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    part_listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("part_listings.id"), nullable=False, index=True
    )
    price_cents: Mapped[int] = mapped_column(nullable=False)
    observed_at: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # Relationships
    part_listing: Mapped["PartListing"] = relationship("PartListing", back_populates="price_history")
