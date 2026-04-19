from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, computed_field, field_serializer

from app.api.schemas.part import apply_image_url_presigning


# Schema for request body when creating a car generation
class CarGenerationCreate(BaseModel):
    car_make_name: str
    car_model_name: str
    generation_name: str
    display_name: Optional[str] = None
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


# Schema for request body when updating a car generation (all fields optional)
class CarGenerationUpdate(BaseModel):
    car_make_name: Optional[str] = None
    car_model_name: Optional[str] = None
    generation_name: Optional[str] = None
    display_name: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None


# Schema for response body when reading a car generation
class CarGenerationRead(BaseModel):
    id: UUID
    car_make_name: str
    car_model_name: str
    car_model_display_name: Optional[str] = None
    generation_name: str
    display_name: Optional[str] = None
    start_year: int
    end_year: Optional[int] = None  # None for current/ongoing generations
    description: Optional[str] = None
    image_urls: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

    # Presentation-only fall-throughs. Always non-null strings for the frontend.
    # Keeping both the raw `display_name` fields and these computed labels lets admin UIs
    # distinguish "stored NULL, inherits" from "stored value" while app views get a
    # guaranteed string to render.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_label(self) -> str:
        return self.display_name or self.generation_name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def car_model_display_label(self) -> str:
        return self.car_model_display_name or self.car_model_name

    @field_serializer("image_urls")
    def serialize_image_urls(self, value: Optional[List[str]]) -> Optional[List[str]]:
        """Convert file keys to presigned URLs when serializing response."""
        return apply_image_url_presigning(value)
