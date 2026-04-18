from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReportReason(str, Enum):
    INAPPROPRIATE_CONTENT = "inappropriate_content"
    SPAM = "spam"
    INACCURATE = "inaccurate"
    DUPLICATE = "duplicate"
    OTHER = "other"


class ReportStatus(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class EntityType(str, Enum):
    BUILD_LIST = "build_list"
    PART = "part"


class ReportCreate(BaseModel):
    reason: ReportReason
    description: Optional[str] = None


class ReportUpdate(BaseModel):
    status: ReportStatus
    admin_notes: Optional[str] = None


class ReportRead(BaseModel):
    id: UUID
    user_id: UUID
    entity_type: str
    entity_id: UUID
    reason: str
    description: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportWithDetails(ReportRead):
    reporter_username: str
    entity_name: str
    entity_description: Optional[str] = None
    reviewer_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
