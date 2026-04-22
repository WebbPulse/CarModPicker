"""
Unified votes endpoint for all entity types.
"""

import logging
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
)
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.schemas.vote import (
    EntityType,
    FlaggedEntitySummary,
    VoteCreate,
    VoteRead,
    VoteSummary,
)
from app.api.services.vote_service import VoteService
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.db.session import get_db

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Create service
vote_service = VoteService()


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of votes",
    ),
)
async def count_votes(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Get total count of votes."""
    db = deps["db"]
    logger = deps["logger"]

    try:
        count = db.query(DBVote).count()
        logger.info(f"Retrieved votes count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting votes: {str(e)}")
        raise


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=VoteRead,
    responses=standard_responses(
        success_description="Vote created/updated successfully",
        validation_error=True,
        not_found=True,
        conflict=True,
    ),
)
async def vote_on_entity(
    entity_type: EntityType,
    entity_id: UUID,
    vote_data: VoteCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> VoteRead:
    """Vote on an entity (car, build list, or global part)."""
    vote = vote_service.vote_on_entity(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=current_user.id,
        vote_data=vote_data,
        logger=logger,
    )
    return VoteRead.model_validate(vote)


@router.delete(
    "/{entity_type}/{entity_id}",
    responses=standard_responses(
        success_description="Vote removed successfully",
        not_found=True,
    ),
)
async def remove_vote(
    entity_type: EntityType,
    entity_id: UUID,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user),
) -> dict[str, str]:
    """Remove a vote from an entity."""
    removed = vote_service.remove_vote(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=current_user.id,
        logger=logger,
    )

    if removed:
        return {"message": "Vote removed successfully"}
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No vote found to remove")


@router.get(
    "/{entity_type}/{entity_id}/summary",
    response_model=VoteSummary,
    responses=standard_responses(
        success_description="Vote summary retrieved successfully",
        not_found=True,
    ),
)
async def get_vote_summary(
    entity_type: EntityType,
    entity_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> VoteSummary:
    """Get vote summary for an entity (public endpoint, authentication optional)."""
    db = deps["db"]
    logger = deps["logger"]

    user_id = current_user.id if current_user else None
    return vote_service.get_vote_summary(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        logger=logger,
    )


@router.get(
    "/admin/flagged/{entity_type}",
    response_model=List[FlaggedEntitySummary],
    responses=standard_responses(
        success_description="Flagged entities retrieved successfully",
        unauthorized=True,
        forbidden=True,
    ),
)
async def get_flagged_entities(
    entity_type: EntityType,
    limit: int = Query(50, ge=1, le=100, description="Maximum number of flagged entities to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[FlaggedEntitySummary]:
    """Get flagged entities (those with high downvote ratios or reports). Admin only."""
    db = deps["db"]
    logger = deps["logger"]

    return vote_service.get_flagged_entities(
        db=db,
        entity_type=entity_type,
        limit=limit,
        logger=logger,
    )
