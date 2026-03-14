from pydantic import BaseModel, ConfigDict, Field


class BuildListPhaseCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Phase name (e.g. Phase 1, Must Have)")
    sort_order: int = Field(0, ge=0, description="Display order")


class BuildListPhaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, description="Phase name")
    sort_order: int | None = Field(None, ge=0, description="Display order")


class BuildListPhaseRead(BaseModel):
    id: int
    build_list_id: int
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)
