from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartPriceHistoryBase(BaseModel):
    part_listing_id: UUID = Field(..., description="Part listing ID")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    observed_at: datetime = Field(..., description="When this price was observed")


class PartPriceHistoryCreate(BaseModel):
    part_listing_id: UUID = Field(..., description="Part listing ID")
    price_cents: int = Field(..., ge=0, description="Price in cents")
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="When this price was observed")


class PartPriceHistoryRead(PartPriceHistoryBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class PartPriceHistoryReadWithRetailer(PartPriceHistoryRead):
    """Price history entry with retailer info for API responses."""

    retailer_id: UUID = Field(..., description="Retailer ID")
    retailer_name: str = Field(..., description="Retailer display name")
