from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BugReportStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class BugReportPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BugReportCreate(BaseModel):
    title: str
    description: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    browser_info: Optional[str] = None
    device_info: Optional[str] = None
    screenshot_url: Optional[str] = None


class BugReportUpdate(BaseModel):
    status: Optional[BugReportStatus] = None
    priority: Optional[BugReportPriority] = None
    admin_notes: Optional[str] = None
    assigned_to: Optional[int] = None


class BugReportRead(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    description: str
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    browser_info: Optional[str] = None
    device_info: Optional[str] = None
    screenshot_url: Optional[str] = None
    status: str
    priority: str
    admin_notes: Optional[str] = None
    assigned_to: Optional[int] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BugReportWithDetails(BugReportRead):
    reporter_username: Optional[str] = None
    assignee_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
