from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PartManufacturerBase(BaseModel):
    name: str = Field(..., description="Part manufacturer name")
    description: Optional[str] = Field(None, description="Part manufacturer description")
    is_active: bool = Field(True, description="Whether the part manufacturer is active")


class PartManufacturerCreate(PartManufacturerBase):
    """User-supplied create payload. is_curated and created_by_user_id are set server-side."""

    pass


class PartManufacturerUpdate(BaseModel):
    """Update payload for the creator (UGC) or admin (curated)."""

    name: Optional[str] = Field(None, description="Part manufacturer name")
    description: Optional[str] = Field(None, description="Part manufacturer description")
    is_active: Optional[bool] = Field(None, description="Whether the part manufacturer is active")


class PartManufacturerAdminUpdate(PartManufacturerUpdate):
    """Admin-only update payload that additionally allows toggling is_curated (promote/demote)."""

    is_curated: Optional[bool] = Field(None, description="Whether the part manufacturer is part of the curated catalog")


class PartManufacturerInDB(PartManufacturerBase):
    id: UUID
    is_curated: bool
    created_by_user_id: Optional[UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartManufacturerResponse(PartManufacturerInDB):
    pass
