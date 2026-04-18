from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# EventBridge Scheduler names must be <=64 chars matching [0-9A-Za-z-_.]; with
# our ``{prefix}-crawler-sched-`` prefix the longest allowed user-supplied name
# is 26 chars (prefix "carmodpicker-production-crawler-sched-" = 38 chars).
# We restrict further to a conservative slug form for readability.
SCHEDULE_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]{0,25}$"


class CrawlerScheduleAdapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adapter_name: str


class CrawlerScheduleRead(BaseModel):
    """A user-defined crawler schedule plus its adapter membership."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    enabled: bool
    schedule_expression: str
    last_reconciled_at: Optional[datetime] = None
    last_reconcile_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    adapters: list[CrawlerScheduleAdapterRead] = Field(default_factory=list)


class CrawlerScheduleCreate(BaseModel):
    name: str = Field(
        pattern=SCHEDULE_NAME_PATTERN,
        description="Slug used in the EventBridge schedule name: lowercase letters, digits, hyphen. 1-26 chars.",
    )
    description: Optional[str] = None
    enabled: bool = False
    schedule_expression: Optional[str] = Field(
        default=None,
        description="Full EventBridge cron/rate expression (UTC), e.g. 'cron(0 2 1 * ? *)'. One of schedule_expression or preset is required.",
    )
    preset: Optional[str] = Field(
        default=None,
        description="Shorthand preset: 'monthly', 'weekly', or 'daily'.",
    )
    adapters: list[str] = Field(
        default_factory=list,
        description="Adapter names to include. Must already exist in ADAPTER_REGISTRY.",
    )

    @field_validator("adapters")
    @classmethod
    def _validate_adapters_unique(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("adapters must be unique")
        return v


class CrawlerScheduleUpdate(BaseModel):
    """Partial update. Only provided fields change. ``adapters`` fully replaces membership when provided."""

    description: Optional[str] = None
    enabled: Optional[bool] = None
    schedule_expression: Optional[str] = None
    preset: Optional[str] = None
    adapters: Optional[list[str]] = None

    @field_validator("adapters")
    @classmethod
    def _validate_adapters_unique(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and len(v) != len(set(v)):
            raise ValueError("adapters must be unique")
        return v


class CrawlerScheduleList(BaseModel):
    items: list[CrawlerScheduleRead]
    presets: dict[str, str]


class ReconcileResult(BaseModel):
    schedule_name: str
    ok: bool
    error: Optional[str] = None


class ReconcileAllResponse(BaseModel):
    results: list[ReconcileResult]
