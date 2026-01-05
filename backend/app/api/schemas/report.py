from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum


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
    CAR = "car"
    BUILD_LIST = "build_list"
    GLOBAL_PART = "global_part"


class ReportCreate(BaseModel):
    reason: ReportReason
    description: Optional[str] = None


class ReportUpdate(BaseModel):
    status: ReportStatus
    admin_notes: Optional[str] = None


class ReportRead(BaseModel):
    id: int
    user_id: int
    entity_type: str
    entity_id: int
    reason: str
    description: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    reviewed_by: Optional[int] = None
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
