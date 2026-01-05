"""
Unified votes endpoint for all entity types.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    get_current_user,
    get_current_admin_user,
    get_optional_current_user,
)
from app.api.models.user import User as DBUser
from app.api.schemas.vote import (
    VoteCreate,
    VoteRead,
    VoteSummary,
    FlaggedEntitySummary,
    EntityType,
)
from app.api.services.vote_service import VoteService
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.common_patterns import get_standard_public_endpoint_dependencies
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()

# Create service
vote_service = VoteService()


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
    entity_id: int,
    vote_data: VoteCreate,
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
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
    entity_id: int,
    db: Session = Depends(get_db),
    logger=Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> dict:
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No vote found to remove"
        )


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
    entity_id: int,
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
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
    limit: int = Query(
        50, ge=1, le=100, description="Maximum number of flagged entities to return"
    ),
    deps: dict = Depends(get_standard_public_endpoint_dependencies),
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
