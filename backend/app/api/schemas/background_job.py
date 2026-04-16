from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BackgroundJobRead(BaseModel):
    """Public representation of a background job record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: str
    status: str
    triggered_by: str
    params: Optional[Any] = None
    result_summary: Optional[Any] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_by_user_id: Optional[UUID] = None


class BackgroundJobList(BaseModel):
    """Paginated list of background jobs."""

    items: list[BackgroundJobRead]
    total: int
    limit: int
    offset: int
