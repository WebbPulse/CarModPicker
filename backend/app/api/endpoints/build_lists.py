"""
Refactored build lists endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining build list-specific functionality.
"""

from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.schemas.build_list import (
    BuildListCreate,
    BuildListRead,
    BuildListReadWithVotes,
    BuildListUpdate,
)
from app.api.services.build_list_service import BuildListService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_operations import verify_entity_exists
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    apply_standard_filters,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    standard_responses,
)
from app.api.utils.pagination_utils import create_paginated_response

# Create router
router = APIRouter()

# Create service
build_list_service = BuildListService()

# Create base endpoint router
# Disable the base GET endpoint since we have a custom one that allows read access for all authenticated users
base_router = BaseEndpointRouter(
    service=build_list_service,
    router=router,
    entity_name="build list",
    allow_public_read=False,  # Build lists are private
    additional_create_data={},  # No additional data needed
    create_schema=BuildListCreate,
    read_schema=BuildListRead,
    update_schema=BuildListUpdate,
    search_fields=["name", "description"],
    disable_endpoints=["get"],  # Disable base GET endpoint, use custom one below
)


# Register custom endpoints BEFORE BaseEndpointRouter to ensure proper route precedence
# (More specific routes like /with-votes must be registered before generic routes like /{entity_id})


@router.get(
    "/with-votes",
    response_model=Dict[str, Any],
    responses=pagination_responses("build list", allow_public_read=True),
)
async def read_build_lists_with_votes(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    search: Optional[str] = Query(None, description="Search in build list names and descriptions"),
    car_id: Optional[int] = Query(None, description="Filter by car ID"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Get all build lists with vote data and optional filtering and search."""
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
            DBVote.entity_type == "build_list",
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
            DBVote.entity_type == "build_list",
            DBVote.vote_type == "downvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    # Build base query for counting (without joins to avoid JSON DISTINCT issues)
    base_query = db.query(DBBuildList)
    base_query = apply_standard_filters(
        query=base_query,
        search=search,
        category_id=None,  # Build lists don't have categories
        search_fields=["name", "description"],
    )
    if car_id:
        base_query = base_query.filter(DBBuildList.car_id == car_id)

    # Get total count from base query
    total = base_query.count()

    # Build main query with LEFT JOINs to vote count subqueries for sorting and retrieval
    query = (
        db.query(DBBuildList)
        .outerjoin(upvote_counts, DBBuildList.id == upvote_counts.c.entity_id)
        .outerjoin(downvote_counts, DBBuildList.id == downvote_counts.c.entity_id)
    )

    # Apply the same filters
    query = apply_standard_filters(
        query=query,
        search=search,
        category_id=None,
        search_fields=["name", "description"],
    )
    if car_id:
        query = query.filter(DBBuildList.car_id == car_id)

    # Sort by net votes (upvotes - downvotes) descending, then by id for consistent ordering
    query = query.order_by(
        (func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)).desc(),
        DBBuildList.id.desc(),
    )

    # Get paginated results
    ordered_ids = [row[0] for row in query.with_entities(DBBuildList.id).offset(skip).limit(limit).all()]

    if not ordered_ids:
        build_lists = []
    else:
        # Fetch full objects in the same order
        build_lists_query = (
            db.query(DBBuildList)
            .filter(DBBuildList.id.in_(ordered_ids))
            .outerjoin(upvote_counts, DBBuildList.id == upvote_counts.c.entity_id)
            .outerjoin(downvote_counts, DBBuildList.id == downvote_counts.c.entity_id)
            .order_by(
                (
                    func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)
                ).desc(),
                DBBuildList.id.desc(),
            )
        )
        build_lists = build_lists_query.all()
        # Reorder to match the original order (in case the second query changes it)
        build_lists_dict = {bl.id: bl for bl in build_lists}
        build_lists = [build_lists_dict[bl_id] for bl_id in ordered_ids if bl_id in build_lists_dict]
    logger.info(f"Retrieved {len(build_lists)} build lists (skip: {skip}, limit: {limit})")

    if not build_lists:
        # Return empty response
        return create_paginated_response(data=[], total=total, skip=skip, limit=limit, entity_name="build lists")

    # Get build list IDs
    build_list_ids = [bl.id for bl in build_lists]

    # Build vote count dictionaries
    vote_counts = (
        db.query(
            DBVote.entity_id,
            DBVote.vote_type,
            func.count(DBVote.id).label("count"),
        )
        .filter(
            DBVote.entity_type == "build_list",
            DBVote.entity_id.in_(build_list_ids),
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
                DBVote.entity_type == "build_list",
                DBVote.entity_id.in_(build_list_ids),
                DBVote.user_id == current_user.id,
            )
            .all()
        )
        user_votes_dict = {entity_id: vote_type for entity_id, vote_type in user_votes}

    # Convert build lists to schema with vote data
    build_lists_data: List[BuildListReadWithVotes] = []
    for build_list in build_lists:
        build_list_dict = BuildListRead.model_validate(build_list).model_dump()
        build_list_dict["upvotes"] = upvotes_dict.get(build_list.id, 0)
        build_list_dict["downvotes"] = downvotes_dict.get(build_list.id, 0)
        build_list_dict["total_votes"] = build_list_dict["upvotes"] + build_list_dict["downvotes"]
        build_list_dict["user_vote"] = user_votes_dict.get(build_list.id, None)
        build_list_with_votes = BuildListReadWithVotes(**build_list_dict)
        build_lists_data.append(build_list_with_votes)

    # Return paginated response
    return create_paginated_response(
        data=cast(List[Any], build_lists_data), total=total, skip=skip, limit=limit, entity_name="build lists"
    )


# Override the GET endpoint to allow public read access
# (but keep update/delete restricted to owners)
@router.get(
    "/{build_list_id}",
    response_model=BuildListRead,
    responses={
        200: {"description": "Build list retrieved successfully"},
        404: {"description": "Build list not found"},
    },
)
async def read_build_list(
    build_list_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> BuildListRead:
    """
    Retrieve a build list by ID.
    Public read access - anyone can view build lists.
    Only owners can edit or delete.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Allow public read access - just verify it exists
    build_list = verify_entity_exists(db, DBBuildList, build_list_id, "build list")

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info} retrieved build list {build_list_id}")
    return BuildListRead.model_validate(build_list)


# Add custom endpoints specific to build lists
@router.get(
    "/car/{car_id}",
    response_model=Dict[str, Any],
    responses=pagination_responses("build list", allow_public_read=True),
)
async def read_build_lists_by_car(
    car_id: int,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    search: Optional[str] = Query(None, description="Search in build list names and descriptions"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """
    Retrieve all build lists associated with a specific car with pagination.
    Public read access - anyone can view build lists for any car.
    """
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # Verify the car exists (cars are now centrally managed, no ownership check needed)
    get_entity_or_404(db, DBCar, car_id, "car")

    # Build base query with search filter
    base_query = db.query(DBBuildList).filter(DBBuildList.car_id == car_id)
    base_query = apply_standard_filters(
        query=base_query,
        search=search,
        category_id=None,  # Build lists don't have categories
        search_fields=["name", "description"],
    )

    # Get total count
    total = base_query.count()

    # Get paginated results
    build_lists = base_query.offset(skip).limit(limit).all()
    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    if not build_lists:
        logger.info(f"{user_info}: No Build Lists found for car with id {car_id}")
    else:
        logger.info(msg=f"{user_info}: Build Lists retrieved for car {car_id}: {build_lists}")

    build_lists_data = [BuildListRead.model_validate(build_list) for build_list in build_lists]
    return create_paginated_response(
        data=build_lists_data, total=total, skip=skip, limit=limit, entity_name="build lists"
    )


@router.get(
    "/user/me",
    response_model=Dict[str, Any],
    responses=pagination_responses("build list", allow_public_read=False),
)
async def read_my_build_lists(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Retrieve all build lists owned by the current user with pagination.
    """
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # Get total count
    total = db.query(DBBuildList).filter(DBBuildList.user_id == current_user.id).count()

    # Get paginated results
    build_lists = db.query(DBBuildList).filter(DBBuildList.user_id == current_user.id).offset(skip).limit(limit).all()
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {current_user.id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {current_user.id}: {build_lists}")

    build_lists_data = [BuildListRead.model_validate(build_list) for build_list in build_lists]
    return create_paginated_response(
        data=build_lists_data, total=total, skip=skip, limit=limit, entity_name="build lists"
    )


@router.get(
    "/user/{user_id}",
    response_model=List[BuildListRead],
    responses=pagination_responses("build list", allow_public_read=True),
)
async def read_build_lists_by_user(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[BuildListRead]:
    """
    Retrieve all build lists owned by a specific user.
    Public endpoint - build lists are discoverable via search and catalog, so listing by user is allowed for profile pages.
    """
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    build_lists = db.query(DBBuildList).filter(DBBuildList.user_id == user_id).offset(skip).limit(limit).all()
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {user_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {user_id}: {build_lists}")
    return [BuildListRead.model_validate(build_list) for build_list in build_lists]


# Add count endpoint
base_router.add_count_endpoint()


# Schema for copy build list request
class CopyBuildListRequest(BaseModel):
    """Request model for copying a build list."""

    new_name: Optional[str] = None


@router.post(
    "/{build_list_id}/copy",
    response_model=BuildListRead,
    responses=standard_responses(
        success_description="Build list copied successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def copy_build_list(
    build_list_id: int,
    request: CopyBuildListRequest = Body(default=CopyBuildListRequest()),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListRead:
    """
    Copy a build list and all its parts.
    Creates a new build list owned by the current user with all parts from the original.
    All authenticated users can copy any build list.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify the build list exists (any authenticated user can copy any build list)
    verify_entity_exists(db, DBBuildList, build_list_id, "build list")

    # Copy the build list
    new_build_list = build_list_service.copy_build_list(
        db=db,
        build_list_id=build_list_id,
        current_user=current_user,
        logger=logger,
        new_name=request.new_name,
    )

    logger.info(f"User {current_user.id} copied build list {build_list_id} to {new_build_list.id}")
    return BuildListRead.model_validate(new_build_list)
