from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BuildListLaborEstimateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Labor item name (e.g. 'Paint - bumper respray')")
    cost_cents: int = Field(0, ge=0, description="Estimated cost in cents")
    description: Optional[str] = Field(None, max_length=2000, description="Optional details about the labor item")
    build_list_phase_id: Optional[UUID] = Field(None, description="Optional phase to group this labor item under")
    sort_order: int = Field(0, ge=0, description="Display order")


class BuildListLaborEstimateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    cost_cents: Optional[int] = Field(None, ge=0)
    description: Optional[str] = Field(None, max_length=2000)
    build_list_phase_id: Optional[UUID] = None
    sort_order: Optional[int] = Field(None, ge=0)


class BuildListLaborEstimateRead(BaseModel):
    id: UUID
    build_list_id: UUID
    build_list_phase_id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    cost_cents: int
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
