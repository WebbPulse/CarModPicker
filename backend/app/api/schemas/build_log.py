from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Schema for request body when creating a build log post
class BuildLogPostCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Post content cannot be empty")


# Schema for request body when updating a build log post
class BuildLogPostUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, description="Post content cannot be empty")


# Schema for response body when reading a build log post
class BuildLogPostRead(BaseModel):
    id: UUID
    build_log_id: UUID
    user_id: Optional[UUID] = None
    content: str
    created_at: datetime
    updated_at: datetime
    author_username: Optional[str] = None
    author_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Schema for response body when reading a build log with posts
class BuildLogRead(BaseModel):
    id: UUID
    build_list_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    posts: List[BuildLogPostRead] = []

    model_config = ConfigDict(from_attributes=True)


# Schema for paginated build log response
class BuildLogReadPaginated(BaseModel):
    id: UUID
    build_list_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    posts: List[BuildLogPostRead] = []
    pagination: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


# Schema for response body when reading a build log post with author details
class BuildLogPostReadWithAuthor(BaseModel):
    id: UUID
    build_log_id: UUID
    user_id: Optional[UUID] = None
    content: str
    created_at: datetime
    updated_at: datetime
    author_username: str
    author_id: UUID

    model_config = ConfigDict(from_attributes=True)
