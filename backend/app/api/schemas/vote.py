from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VoteType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class VoteEntityType(str, Enum):
    CAR_GENERATION = "car_generation"
    BUILD_LIST = "build_list"
    PART = "part"


EntityType = VoteEntityType


class VoteCreate(BaseModel):
    vote_type: VoteType


class VoteUpdate(BaseModel):
    vote_type: VoteType


class VoteRead(BaseModel):
    id: UUID
    user_id: UUID
    vote_type: str
    entity_type: str
    entity_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoteSummary(BaseModel):
    entity_id: UUID
    entity_type: str
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    user_vote: str | None  # 'upvote', 'downvote', or None if user hasn't voted

    model_config = ConfigDict(from_attributes=True)


class FlaggedEntitySummary(BaseModel):
    entity_id: UUID
    entity_type: str
    entity_name: str
    entity_description: Optional[str] = None
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    downvote_ratio: float  # downvotes / total_votes
    recent_downvotes: int  # downvotes in last 7 days
    has_reports: bool  # whether entity has pending reports
    created_at: datetime
    flagged_at: datetime

    model_config = ConfigDict(from_attributes=True)
