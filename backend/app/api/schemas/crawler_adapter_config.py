from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CrawlerAdapterConfigRead(BaseModel):
    """Per-adapter retailer tuning returned to admin clients."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    adapter_name: str
    delay_sec: float
    per_run_limit: Optional[int] = None
    skip_known_urls: bool
    default_category_id: UUID
    created_at: datetime
    updated_at: datetime


class CrawlerAdapterConfigUpdate(BaseModel):
    """Partial update for an adapter config. All fields optional."""

    delay_sec: Optional[float] = Field(default=None, ge=0.5, le=300.0)
    per_run_limit: Optional[int] = Field(default=None, ge=1)
    clear_per_run_limit: bool = Field(
        default=False,
        description="Set to true to clear per_run_limit (unlimited). Takes precedence over per_run_limit.",
    )
    skip_known_urls: Optional[bool] = None
    default_category_id: Optional[UUID] = None


class CrawlerAdapterConfigList(BaseModel):
    items: list[CrawlerAdapterConfigRead]
