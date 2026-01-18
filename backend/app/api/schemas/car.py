from typing import Optional

from pydantic import BaseModel, ConfigDict


# Schema for request body when creating a car
class CarCreate(BaseModel):
    make: str
    model: str
    generation_name: str
    start_year: int
    end_year: int
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
    end_year: int
    description: Optional[str] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
