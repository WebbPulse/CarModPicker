from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.api.schemas.part_listing import PartListingReadWithRetailer
from app.api.utils.image_utils import get_presigned_url_from_file_key

MAX_IMAGES_PER_GLOBAL_PART = 12


def _serialize_image_urls(value: Optional[List[str]]) -> Optional[List[str]]:
    """Convert list of file keys to presigned URLs."""
    if not value:
        return None
    return [get_presigned_url_from_file_key(k) or k for k in value]


# Schema for request body when creating a part
# product_url is only used when retailer_id is set (creates/updates that retailer's listing with this URL)
class GlobalPartCreate(BaseModel):
    name: str
    description: Optional[str] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_GLOBAL_PART,
        description="Images: file keys (from images/upload) and/or external URLs (scraped); max 12. First entry is the primary/display image.",
    )
    product_url: Optional[str] = Field(
        None, description="Product URL at retailer (used only with retailer_id for listing)"
    )
    category_id: UUID
    car_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Car IDs this part fits. Ignored when is_universal is True.",
    )
    is_universal: bool = Field(
        default=False,
        description="When True, part fits all cars; no need to list car_ids.",
    )
    brand_id: UUID  # Required brand association
    part_number: Optional[str] = None
    gtin: Optional[str] = Field(
        None,
        description="UPC/EAN/GTIN barcode for dedup (digits only stored); e.g. 012345678901",
    )
    specifications: Optional[Dict[str, Any]] = None
    # Optional: link to retailer listing for dedup and price history
    retailer_id: Optional[UUID] = Field(None, description="Retailer ID when product_url is from a known retailer")
    price_cents: Optional[int] = Field(
        None, ge=0, le=2147483647, description="Price in cents for this retailer (creates/updates listing)"
    )

    @field_validator("price_cents")
    @classmethod
    def validate_price_cents(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError("Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)")
        return v


# Schema for request body when updating a part (all fields optional)
class GlobalPartUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_GLOBAL_PART,
        description="Images: file keys and/or external URLs; max 12. First entry is the primary/display image.",
    )
    category_id: Optional[UUID] = None
    car_ids: Optional[List[UUID]] = None  # Car IDs this part fits; ignored when is_universal
    is_universal: Optional[bool] = None
    brand_id: UUID  # Required brand association
    part_number: Optional[str] = None
    gtin: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None


# Schema for response body when reading a part
class GlobalPartRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    best_price_cents: Optional[int] = Field(
        None, description="Lowest current price from any retailer listing (computed when available)"
    )
    image_urls: Optional[List[str]] = None
    category_id: UUID
    user_id: UUID  # Creator
    car_ids: List[UUID] = Field(default_factory=list, description="Car IDs this part is associated with")
    is_universal: bool = Field(default=False, description="When True, part fits all cars")
    brand_id: Optional[UUID] = None  # Optional brand association
    part_number: Optional[str] = None
    gtin: Optional[str] = Field(None, description="UPC/EAN/GTIN (digits only)")
    specifications: Optional[Dict[str, Any]] = None
    is_verified: bool
    source: str
    edit_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return _serialize_image_urls(value)


# Schema for response body when reading a part with vote summary
class GlobalPartReadWithVotes(GlobalPartRead):
    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None


# Schema for appending images to a part (used when re-scraping adds new images)
class GlobalPartAppendImages(BaseModel):
    file_keys: List[str] = Field(
        ...,
        max_length=MAX_IMAGES_PER_GLOBAL_PART,
        description="Image references to append: file keys (from images/upload) or external URLs (scraped); max 12.",
    )


# Schema for setting the primary (display) image by index
class SetPrimaryImageRequest(BaseModel):
    index: int = Field(..., ge=0, description="0-based index into the part's image_urls gallery")


def _default_listings() -> list[PartListingReadWithRetailer]:
    """Typed default for listings to satisfy strict type checking (default_factory=list is list[Unknown])."""
    return []


# Schema for response when reading a part with listings and best listing
class GlobalPartReadWithListings(GlobalPartRead):
    listings: list[PartListingReadWithRetailer] = Field(
        default_factory=_default_listings, description="Retailer listings with current price"
    )
    best_listing: Optional[PartListingReadWithRetailer] = Field(None, description="Listing with lowest current price")
