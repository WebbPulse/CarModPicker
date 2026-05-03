from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.api.schemas.part import apply_image_url_presigning

MAX_IMAGES_PER_BUILDLIST = 12


# Schema for request body when creating/updating a build list
class BuildListCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: UUID = Field(..., description="Car ID is required - build lists must be associated with a car")
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_BUILDLIST,
        description="Images: file keys (from images/upload) and/or external URLs; max 12. First entry is the primary/display image.",
    )


# Schema for request body when updating a build list (all fields optional)
class BuildListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: Optional[UUID] = None
    image_urls: Optional[List[str]] = Field(
        None,
        max_length=MAX_IMAGES_PER_BUILDLIST,
        description="Images: file keys and/or external URLs; max 12. First entry is the primary/display image.",
    )


# Schema for response body when reading a build list
class BuildListRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    car_id: Optional[UUID] = None
    user_id: UUID
    image_urls: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)


# Schema for response body when reading a build list with vote summary
class BuildListReadWithVotes(BuildListRead):
    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None
    total_cost_cents: Optional[int] = Field(
        None,
        description="Combined cost: sum of (part qty * best price) plus all labor estimate costs",
    )
    total_parts_cost_cents: Optional[int] = Field(
        None,
        description="Sum of (part quantity * best price) for all parts in the build list",
    )
    total_labor_cost_cents: Optional[int] = Field(
        None,
        description="Sum of all labor estimate costs for the build list",
    )


class BuildListAppendImages(BaseModel):
    file_keys: List[str] = Field(
        ...,
        max_length=MAX_IMAGES_PER_BUILDLIST,
        description="Image references to append: file keys (from images/upload) or external URLs; max 12.",
    )


class BuildListSetPrimaryImageRequest(BaseModel):
    index: int = Field(..., ge=0, description="0-based index into the build list's image_urls gallery")
