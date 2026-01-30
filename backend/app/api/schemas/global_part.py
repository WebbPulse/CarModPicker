from datetime import datetime
from typing import Any, Dict, List, Optional

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
    price: Optional[int] = Field(None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)")
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_GLOBAL_PART,
        description="Gallery image file keys (uploaded via images API); max 10",
    )
    product_url: Optional[str] = Field(
        None, description="Product URL at retailer (used only with retailer_id for listing)"
    )
    category_id: int
    car_id: Optional[int] = None  # Optional car association
    brand_id: int  # Required brand association
    part_number: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    # Optional: link to retailer listing for dedup and price history
    retailer_id: Optional[int] = Field(None, description="Retailer ID when product_url is from a known retailer")
    price_cents: Optional[int] = Field(
        None, ge=0, le=2147483647, description="Price in cents for this retailer (creates/updates listing)"
    )

    @field_validator("price", "price_cents")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError("Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)")
        return v


# Schema for request body when updating a part (all fields optional)
class GlobalPartUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = Field(None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)")
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_GLOBAL_PART,
        description="Gallery image file keys; max 10",
    )
    category_id: Optional[int] = None
    car_id: Optional[int] = None  # Optional car association
    brand_id: int  # Required brand association
    part_number: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 2147483647):
            raise ValueError("Price must be between 0 and 2,147,483,647 (max PostgreSQL integer)")
        return v


# Schema for response body when reading a part
class GlobalPartRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: Optional[int] = None
    image_url: Optional[str] = None
    image_urls: Optional[List[str]] = None
    category_id: int
    user_id: int  # Creator
    car_id: Optional[int] = None  # Optional car association
    brand_id: Optional[int] = None  # Optional brand association
    part_number: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    is_verified: bool
    source: str
    edit_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_url")
    def serialize_image_url(self, value: Optional[str]) -> Optional[str]:
        """Convert file key to presigned URL when serializing response."""
        return get_presigned_url_from_file_key(value)

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
        description="File keys to append (from images/upload API); max 10",
    )


# Schema for response when reading a part with listings and best listing
class GlobalPartReadWithListings(GlobalPartRead):
    listings: List[PartListingReadWithRetailer] = Field(
        default_factory=list, description="Retailer listings with current price"
    )
    best_listing: Optional[PartListingReadWithRetailer] = Field(None, description="Listing with lowest current price")
