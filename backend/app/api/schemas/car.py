from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer

from app.api.schemas.global_part import _serialize_image_urls


# Schema for request body when creating a car
class CarCreate(BaseModel):
    make: str
    model: str
    generation_name: str
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


# Schema for request body when updating a car (all fields optional)
class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    generation_name: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


# Schema for response body when reading a car
class CarRead(BaseModel):
    id: UUID
    make: str
    model: str
    generation_name: str
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return _serialize_image_urls(value)
