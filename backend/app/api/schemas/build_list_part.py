from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .part import PartRead


class BuildListPartCreate(BaseModel):
    part_id: Optional[UUID] = None
    quantity: int = Field(1, ge=1, description="Quantity of the part")
    notes: Optional[str] = None
    build_list_phase_id: Optional[UUID] = None


class BuildListPartUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1, description="Quantity of the part")
    notes: Optional[str] = None
    purchased: Optional[bool] = None
    build_list_phase_id: Optional[UUID] = None


class BuildListPartRead(BaseModel):
    id: UUID
    build_list_id: UUID
    part_id: UUID
    added_by: UUID
    quantity: int
    notes: Optional[str] = None
    purchased: bool
    added_at: datetime
    build_list_phase_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class BuildListPartReadWithPart(BaseModel):
    id: UUID
    build_list_id: UUID
    part_id: UUID
    added_by: UUID
    quantity: int
    notes: Optional[str] = None
    purchased: bool
    added_at: datetime
    build_list_phase_id: Optional[UUID] = None
    phase_name: Optional[str] = None
    part: PartRead

    model_config = ConfigDict(from_attributes=True)


class CreatePartAndAddToBuildListRequest(BaseModel):
    """Request model for creating a part and adding it to a build list."""

    # Part fields
    name: str
    description: str | None = None
    image_urls: List[str] | None = None
    product_url: str | None = None
    category_id: UUID
    car_ids: list[UUID] | None = None
    is_universal: bool = False
    brand_id: UUID
    part_number: str | None = None
    gtin: str | None = Field(None, description="UPC/EAN/GTIN for dedup (digits only stored)")
    specifications: dict[str, Any] | None = None
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
