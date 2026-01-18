"""
Refactored global parts endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseEndpointRouter to provide common CRUD operations
while maintaining global part-specific functionality.
"""

from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func

from app.api.dependencies.auth import get_optional_current_user
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.schemas.global_part import (
    GlobalPartCreate,
    GlobalPartRead,
    GlobalPartReadWithVotes,
    GlobalPartUpdate,
)
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    apply_standard_filters,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    standard_responses,
)
from app.api.utils.pagination_utils import (
    create_paginated_response,
)

# Create router
router = APIRouter()


# Create base CRUD service
class GlobalPartService(BaseCRUDService[DBGlobalPart, GlobalPartCreate, GlobalPartRead, GlobalPartUpdate]):
    """Global part service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBGlobalPart,
            entity_name="global part",
            subscription_check_method="can_create_global_part",
        )


global_part_service = GlobalPartService()

# Register custom endpoints BEFORE BaseEndpointRouter to ensure proper route precedence
# (More specific routes like /with-votes must be registered before generic routes like /{entity_id})


@router.get(
    "/with-votes",
    response_model=Dict[str, Any],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def read_global_parts_with_votes(
    skip: int = Query(0, ge=0, description="Number of global parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of global parts to return"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    search: Optional[str] = Query(None, description="Search in global part names and descriptions"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Get all global parts with vote data and optional filtering and search."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # Create subquery for upvote counts
    upvote_counts = (
        db.query(
            DBVote.entity_id,
            func.count(DBVote.id).label("upvote_count"),
        )
        .filter(
            DBVote.entity_type == "global_part",
            DBVote.vote_type == "upvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    # Create subquery for downvote counts
    downvote_counts = (
        db.query(
            DBVote.entity_id,
            func.count(DBVote.id).label("downvote_count"),
        )
        .filter(
            DBVote.entity_type == "global_part",
            DBVote.vote_type == "downvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    # Build base query for counting (without joins to avoid JSON DISTINCT issues)
    base_query = db.query(DBGlobalPart)
    base_query = apply_standard_filters(
        query=base_query,
        search=search,
        category_id=category_id,
        search_fields=["name", "description"],
    )

    # Get total count from base query (joins don't affect which parts match filters)
    total = base_query.count()

    # Build main query with LEFT JOINs to vote count subqueries for sorting and retrieval
    query = (
        db.query(DBGlobalPart)
        .outerjoin(upvote_counts, DBGlobalPart.id == upvote_counts.c.entity_id)
        .outerjoin(downvote_counts, DBGlobalPart.id == downvote_counts.c.entity_id)
    )

    # Apply the same filters
    query = apply_standard_filters(
        query=query,
        search=search,
        category_id=category_id,
        search_fields=["name", "description"],
    )

    # Sort by net votes (upvotes - downvotes) descending, then by id for consistent ordering
    # This matches what users see in the UI (the +1, -2, etc. values)
    query = query.order_by(
        (func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)).desc(),
        DBGlobalPart.id.desc(),
    )

    # Get paginated results
    # Since joins are one-to-one, we can get IDs in order, then fetch full objects
    # This avoids JSON DISTINCT issues
    ordered_ids = [row[0] for row in query.with_entities(DBGlobalPart.id).offset(skip).limit(limit).all()]

    if not ordered_ids:
        parts = []
    else:
        # Fetch full objects in the same order
        parts = (
            db.query(DBGlobalPart)
            .filter(DBGlobalPart.id.in_(ordered_ids))
            .outerjoin(upvote_counts, DBGlobalPart.id == upvote_counts.c.entity_id)
            .outerjoin(downvote_counts, DBGlobalPart.id == downvote_counts.c.entity_id)
            .order_by(
                (
                    func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)
                ).desc(),
                DBGlobalPart.id.desc(),
            )
            .all()
        )
        # Reorder to match the original order (in case the second query changes it)
        parts_dict = {part.id: part for part in parts}
        parts = [parts_dict[part_id] for part_id in ordered_ids if part_id in parts_dict]
    logger.info(f"Retrieved {len(parts)} global parts (skip: {skip}, limit: {limit})")

    if not parts:
        # Return empty response
        return create_paginated_response(data=[], total=total, skip=skip, limit=limit, entity_name="global parts")

    # Get part IDs
    part_ids = [part.id for part in parts]

    # Build vote count dictionaries from the subquery results
    # We already have upvote and downvote counts from the joins, but we need to extract them
    # Since we can't easily access the joined columns after the query, we'll fetch them separately
    # for the parts we retrieved
    vote_counts = (
        db.query(
            DBVote.entity_id,
            DBVote.vote_type,
            func.count(DBVote.id).label("count"),
        )
        .filter(
            DBVote.entity_type == "global_part",
            DBVote.entity_id.in_(part_ids),
        )
        .group_by(DBVote.entity_id, DBVote.vote_type)
        .all()
    )

    # Build vote count dictionaries
    upvotes_dict: Dict[int, int] = {}
    downvotes_dict: Dict[int, int] = {}
    for entity_id, vote_type, count in vote_counts:
        if vote_type == "upvote":
            upvotes_dict[entity_id] = count
        elif vote_type == "downvote":
            downvotes_dict[entity_id] = count

    # Bulk fetch user votes if user is authenticated
    user_votes_dict: Dict[int, str] = {}
    if current_user:
        user_votes = (
            db.query(DBVote.entity_id, DBVote.vote_type)
            .filter(
                DBVote.entity_type == "global_part",
                DBVote.entity_id.in_(part_ids),
                DBVote.user_id == current_user.id,
            )
            .all()
        )
        user_votes_dict = {entity_id: vote_type for entity_id, vote_type in user_votes}

    # Convert parts to schema with vote data
    parts_data: List[GlobalPartReadWithVotes] = []
    for part in parts:
        part_dict = GlobalPartRead.model_validate(part).model_dump()
        part_dict["upvotes"] = upvotes_dict.get(part.id, 0)
        part_dict["downvotes"] = downvotes_dict.get(part.id, 0)
        part_dict["total_votes"] = part_dict["upvotes"] + part_dict["downvotes"]
        part_dict["user_vote"] = user_votes_dict.get(part.id, None)
        part_with_votes = GlobalPartReadWithVotes(**part_dict)
        parts_data.append(part_with_votes)

    # Return paginated response
    return create_paginated_response(
        data=cast(List[Any], parts_data), total=total, skip=skip, limit=limit, entity_name="global parts"
    )


@router.get(
    "/category/{category_id}",
    response_model=List[GlobalPartRead],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def get_global_parts_by_category(
    category_id: int,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[GlobalPartRead]:
    """Get global parts by category with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    parts = db.query(DBGlobalPart).filter(DBGlobalPart.category_id == category_id).offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(parts)} parts for category {category_id}")
    return [GlobalPartRead.model_validate(part) for part in parts]


# Create base endpoint router AFTER custom endpoints to avoid route collision
base_router = BaseEndpointRouter(
    service=global_part_service,
    router=router,
    entity_name="global part",
    allow_public_read=True,  # Global parts can be viewed publicly
    additional_create_data={},  # No additional data needed for global parts
    create_schema=GlobalPartCreate,
    read_schema=GlobalPartRead,
    update_schema=GlobalPartUpdate,
    search_fields=["name", "description", "category"],
)


@router.get(
    "/user/{user_id}/count",
    response_model=dict,
    responses=standard_responses(success_description="Count of global parts for user", not_found=True),
)
async def count_global_parts_by_user(
    user_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Count global parts created by a specific user."""
    count = deps["db"].query(DBGlobalPart).filter(DBGlobalPart.user_id == user_id).count()
    return {"count": count}


# Add filter endpoint for category
base_router.add_filter_endpoint("category", "category_id")

# Add count endpoint
base_router.add_count_endpoint()
