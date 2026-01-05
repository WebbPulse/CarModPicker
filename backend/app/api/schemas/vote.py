from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict


class VoteType(str, Enum):
    UPVOTE = "upvote"
    DOWNVOTE = "downvote"


class EntityType(str, Enum):
    CAR = "car"
    BUILD_LIST = "build_list"
    GLOBAL_PART = "global_part"


class VoteCreate(BaseModel):
    vote_type: VoteType


class VoteUpdate(BaseModel):
    vote_type: VoteType


class VoteRead(BaseModel):
    id: int
    user_id: int
    vote_type: str
    entity_type: str
    entity_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoteSummary(BaseModel):
    entity_id: int
    entity_type: str
    upvotes: int
    downvotes: int
    total_votes: int
    vote_score: int  # upvotes - downvotes
    user_vote: str | None  # 'upvote', 'downvote', or None if user hasn't voted

    model_config = ConfigDict(from_attributes=True)


class FlaggedEntitySummary(BaseModel):
    entity_id: int
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
