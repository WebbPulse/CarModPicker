from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartManufacturerBase(BaseModel):
    name: str = Field(..., description="Unique part manufacturer name")
    description: Optional[str] = Field(None, description="Part manufacturer description")
    is_active: bool = Field(True, description="Whether the part manufacturer is active")


class PartManufacturerCreate(PartManufacturerBase):
    pass


class PartManufacturerUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Unique part manufacturer name")
    description: Optional[str] = Field(None, description="Part manufacturer description")
    is_active: Optional[bool] = Field(None, description="Whether the part manufacturer is active")


class PartManufacturerInDB(PartManufacturerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartManufacturerResponse(PartManufacturerInDB):
    pass
