from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .global_part import GlobalPartRead


# Schema for request body when adding a part to a build list
class BuildListPartCreate(BaseModel):
    global_part_id: Optional[UUID] = None
    quantity: int = Field(1, ge=1, description="Quantity of the part")
    notes: Optional[str] = None
    build_list_phase_id: Optional[UUID] = None


# Schema for request body when updating a part in a build list
class BuildListPartUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1, description="Quantity of the part")
    notes: Optional[str] = None
    purchased: Optional[bool] = None
    build_list_phase_id: Optional[UUID] = None


# Schema for response body when reading a build list part
class BuildListPartRead(BaseModel):
    id: UUID
    build_list_id: UUID
    global_part_id: UUID
    added_by: UUID
    quantity: int
    notes: Optional[str] = None
    purchased: bool
    added_at: datetime
    build_list_phase_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


# Schema for response body when reading a build list part with global part details
class BuildListPartReadWithGlobalPart(BaseModel):
    id: UUID
    build_list_id: UUID
    global_part_id: UUID
    added_by: UUID
    quantity: int
    notes: Optional[str] = None
    purchased: bool
    added_at: datetime
    build_list_phase_id: Optional[UUID] = None
    phase_name: Optional[str] = None
    global_part: GlobalPartRead

    model_config = ConfigDict(from_attributes=True)


class CreateGlobalPartAndAddToBuildListRequest(BaseModel):
    """Request model for creating a global part and adding it to a build list."""

    # Global part fields
    name: str
    description: str | None = None
    image_urls: List[str] | None = None
    product_url: str | None = None
    category_id: UUID
    car_ids: list[UUID] | None = None  # Car IDs this part fits; ignored when is_universal
    is_universal: bool = False  # When True, part fits all cars
    brand_id: UUID  # Required brand association
    part_number: str | None = None
    gtin: str | None = Field(None, description="UPC/EAN/GTIN for dedup (digits only stored)")
    specifications: dict[str, Any] | None = None
    # Optional: link to retailer for dedup and price history
    retailer_id: UUID | None = None
    price_cents: int | None = Field(None, ge=0, le=2147483647, description="Price in cents for this retailer")

    # Build list part fields
    quantity: int = Field(1, ge=1, description="Quantity of the part")
    notes: str | None = None
    build_list_phase_id: UUID | None = None

    @field_validator("price_cents")
    @classmethod
    def validate_price_cents(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError("Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)")
        return v
