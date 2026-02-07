from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.api.utils.image_utils import get_presigned_url_from_file_key


# Schema for request body when creating/updating a build list
class BuildListCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: int = Field(..., description="Car ID is required - build lists must be associated with a car")
    image_url: Optional[str] = None


# Schema for request body when updating a build list (all fields optional)
class BuildListUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Build list name cannot be empty")
    description: Optional[str] = None
    car_id: Optional[int] = None
    image_url: Optional[str] = None


# Schema for response body when reading a build list
class BuildListRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    car_id: Optional[int] = None
    user_id: int
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_url")
    def serialize_image_url(self, value: Optional[str]) -> Optional[str]:
        """Convert file key to presigned URL when serializing response."""
        return get_presigned_url_from_file_key(value)


# Schema for response body when reading a build list with vote summary
class BuildListReadWithVotes(BuildListRead):
    upvotes: int = 0
    downvotes: int = 0
    total_votes: int = 0
    user_vote: Optional[str] = None  # 'upvote', 'downvote', or None
    total_cost_cents: Optional[int] = Field(
        None,
        description="Sum of (part quantity * best price) for all parts in the build list",
    )
