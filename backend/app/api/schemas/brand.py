from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BrandBase(BaseModel):
    name: str = Field(..., description="Unique brand name")
    description: Optional[str] = Field(None, description="Brand description")
    is_active: bool = Field(True, description="Whether the brand is active")


class BrandCreate(BrandBase):
    pass


class BrandUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Unique brand name")
    description: Optional[str] = Field(None, description="Brand description")
    is_active: Optional[bool] = Field(None, description="Whether the brand is active")


class BrandInDB(BrandBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BrandResponse(BrandInDB):
    pass
