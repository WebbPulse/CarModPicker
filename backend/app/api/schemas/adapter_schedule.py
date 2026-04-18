from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdapterScheduleRead(BaseModel):
    """Per-adapter crawler schedule row returned to admin clients."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    adapter_name: str
    enabled: bool
    schedule_expression: str
    delay_sec: float
    per_run_limit: Optional[int] = None
    skip_known_urls: bool
    default_category_id: UUID
    last_reconciled_at: Optional[datetime] = None
    last_reconcile_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AdapterScheduleUpdate(BaseModel):
    """Partial update for a row. All fields optional; only provided ones change."""

    enabled: Optional[bool] = None
    schedule_expression: Optional[str] = Field(
        default=None,
        description="Full EventBridge cron/rate expression (UTC), e.g. 'cron(0 2 1 * ? *)'.",
    )
    preset: Optional[str] = Field(
        default=None,
        description="Shorthand preset: 'monthly', 'weekly', or 'daily'. Overrides schedule_expression when both set.",
    )
    delay_sec: Optional[float] = Field(default=None, ge=0.5, le=300.0)
    per_run_limit: Optional[int] = Field(default=None, ge=1)
    clear_per_run_limit: bool = Field(
        default=False,
        description="Set to true to clear per_run_limit (unlimited). Takes precedence over per_run_limit.",
    )
    skip_known_urls: Optional[bool] = None
    default_category_id: Optional[UUID] = None


class AdapterScheduleList(BaseModel):
    """Flat list of all adapter schedules (one per registered adapter)."""

    items: list[AdapterScheduleRead]
    presets: dict[str, str]


class ReconcileResult(BaseModel):
    """Outcome of a single reconcile attempt."""

    adapter_name: str
    ok: bool
    error: Optional[str] = None


class ReconcileAllResponse(BaseModel):
    """Aggregate result of reconciling every adapter."""

    results: list[ReconcileResult]
