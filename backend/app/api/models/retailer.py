import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .part_listing import PartListing


class Retailer(Base):
    """
    Retailer (store/site) where parts are sold.
    Distinct from PartManufacturer (part manufacturer). e.g. A90Shop, Summit Racing.
    """

    __tablename__ = "retailers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    name: Mapped[str] = mapped_column(nullable=False, index=True)
    domain: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)  # e.g. "a90shop.com"
    base_url: Mapped[Optional[str]] = mapped_column(nullable=True)  # e.g. "https://www.a90shop.com"
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    part_listings: Mapped[list["PartListing"]] = relationship(
        "PartListing", back_populates="retailer", cascade="all, delete-orphan"
    )
