from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer

from app.api.utils.image_utils import get_presigned_url_from_file_key


# Schema for request body when creating a car
class CarCreate(BaseModel):
    make: str
    model: str
    generation_name: str
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_url: Optional[str] = None


# Schema for request body when updating a car (all fields optional)
class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    generation_name: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


# Schema for response body when reading a car
class CarRead(BaseModel):
    id: int
    make: str
    model: str
    generation_name: str
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_url")
    def serialize_image_url(self, value: Optional[str]) -> Optional[str]:
        """Convert file key to presigned URL when serializing response."""
        return get_presigned_url_from_file_key(value)
