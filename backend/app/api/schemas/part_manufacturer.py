from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartManufacturerBase(BaseModel):
    name: str = Field(..., description="Part manufacturer name")
    description: Optional[str] = Field(None, description="Part manufacturer description")
    is_active: bool = Field(True, description="Whether the part manufacturer is active")


class PartManufacturerCreate(PartManufacturerBase):
    """User-supplied create payload."""

    pass


class PartManufacturerUpdate(BaseModel):
    """Update payload for the manufacturer."""

    name: Optional[str] = Field(None, description="Part manufacturer name")
    description: Optional[str] = Field(None, description="Part manufacturer description")
    is_active: Optional[bool] = Field(None, description="Whether the part manufacturer is active")


class PartManufacturerAdminUpdate(PartManufacturerUpdate):
    """Admin-only update payload (same fields; kept as a distinct type for the admin route)."""

    pass


class PartManufacturerInDB(PartManufacturerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartManufacturerResponse(PartManufacturerInDB):
    pass
