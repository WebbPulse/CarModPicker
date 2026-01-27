from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.api.utils.image_utils import get_presigned_url_from_file_key


# Schema for request body when creating a part
class GlobalPartCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: Optional[int] = Field(None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)")
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    category_id: int
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


# Schema for request body when updating a part (all fields optional)
class GlobalPartUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = Field(None, ge=0, le=2147483647, description="Price in cents (max 21,474,836.47)")
    image_url: Optional[str] = None
    product_url: Optional[str] = None
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
    product_url: Optional[str] = None
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


# Schema for response body when reading a part with vote summary
class GlobalPartReadWithVotes(GlobalPartRead):
    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None
