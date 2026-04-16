from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .retailer import RetailerRead


class PartListingBase(BaseModel):
    global_part_id: UUID = Field(..., description="Global part ID")
    retailer_id: UUID = Field(..., description="Retailer ID")
    product_url: Optional[str] = Field(None, description="Product page URL at this retailer")
    last_known_price_cents: Optional[int] = Field(None, ge=0, description="Last known price in cents")
    last_price_updated_at: Optional[datetime] = Field(None, description="When last price was observed")


class PartListingCreate(BaseModel):
    global_part_id: UUID = Field(..., description="Global part ID")
    retailer_id: UUID = Field(..., description="Retailer ID")
    product_url: Optional[str] = Field(None, description="Product page URL at this retailer")
    price_cents: Optional[int] = Field(None, ge=0, description="Initial price in cents (creates first price history)")


class PartListingUpdate(BaseModel):
    product_url: Optional[str] = Field(None, description="Product page URL at this retailer")
    last_known_price_cents: Optional[int] = Field(None, ge=0, description="Last known price in cents")
    last_price_updated_at: Optional[datetime] = Field(None, description="When last price was observed")


class PartListingRead(PartListingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartListingReadWithRetailer(PartListingRead):
    retailer: RetailerRead

    model_config = ConfigDict(from_attributes=True)
