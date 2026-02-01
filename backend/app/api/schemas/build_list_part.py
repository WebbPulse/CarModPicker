from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .global_part import GlobalPartRead


# Schema for request body when adding a part to a build list
class BuildListPartCreate(BaseModel):
    global_part_id: Optional[int] = None
    quantity: int = Field(1, ge=1, description="Quantity of the part")
    notes: Optional[str] = None


# Schema for request body when updating a part in a build list
class BuildListPartUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1, description="Quantity of the part")
    notes: Optional[str] = None
    purchased: Optional[bool] = None


# Schema for response body when reading a build list part
class BuildListPartRead(BaseModel):
    id: int
    build_list_id: int
    global_part_id: int
    added_by: int
    quantity: int
    notes: Optional[str] = None
    purchased: bool
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for response body when reading a build list part with global part details
class BuildListPartReadWithGlobalPart(BaseModel):
    id: int
    build_list_id: int
    global_part_id: int
    added_by: int
    quantity: int
    notes: Optional[str] = None
    purchased: bool
    added_at: datetime
    global_part: GlobalPartRead

    model_config = ConfigDict(from_attributes=True)


class CreateGlobalPartAndAddToBuildListRequest(BaseModel):
    """Request model for creating a global part and adding it to a build list."""

    # Global part fields
    name: str
    description: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    category_id: int
    car_id: int | None = None  # Optional car association
    brand_id: int  # Required brand association
    part_number: str | None = None
    gtin: str | None = Field(None, description="UPC/EAN/GTIN for dedup (digits only stored)")
    specifications: dict[str, Any] | None = None
    # Optional: link to retailer for dedup and price history
    retailer_id: int | None = None
    price_cents: int | None = Field(None, ge=0, le=2147483647, description="Price in cents for this retailer")

    # Build list part fields
    notes: str | None = None

    @field_validator("price_cents")
    @classmethod
    def validate_price_cents(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError("Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)")
        return v
