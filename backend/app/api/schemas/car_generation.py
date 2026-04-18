from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer

from app.api.schemas.part import apply_image_url_presigning


# Schema for request body when creating a car generation
class CarGenerationCreate(BaseModel):
    car_make_name: str
    car_model_name: str
    generation_name: str
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


# Schema for request body when updating a car generation (all fields optional)
class CarGenerationUpdate(BaseModel):
    car_make_name: Optional[str] = None
    car_model_name: Optional[str] = None
    generation_name: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


# Schema for response body when reading a car generation
class CarGenerationRead(BaseModel):
    id: UUID
    car_make_name: str
    car_model_name: str
    generation_name: str
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)
