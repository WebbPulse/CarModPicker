"""
Refactored build lists endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining build list-specific functionality.
"""

from typing import List

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.build_list import BuildListCreate, BuildListRead, BuildListUpdate
from app.api.services.build_list_service import BuildListService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_operations import verify_entity_exists
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
)

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


# Override the GET endpoint to allow read access for all authenticated users
# (but keep update/delete restricted to owners)
@router.get(
    "/{build_list_id}",
    response_model=BuildListRead,
    responses={
        200: {"description": "Build list retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Build list not found"},
    },
)
async def read_build_list(
    build_list_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListRead:
    """
    Retrieve a build list by ID.
    All authenticated users can view any build list (read-only).
    Only owners can edit or delete.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Allow read access for all authenticated users - just verify it exists
    build_list = verify_entity_exists(db, DBBuildList, build_list_id, "build list")

    logger.info(f"User {current_user.id} retrieved build list {build_list_id}")
    return BuildListRead.model_validate(build_list)


# Add custom endpoints specific to build lists
@router.get(
    "/car/{car_id}",
    response_model=List[BuildListRead],
    responses=pagination_responses("build list", allow_public_read=False),
)
async def read_build_lists_by_car(
    car_id: int,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListRead]:
    """
    Retrieve all build lists associated with a specific car with pagination.
    Users can only access build lists for cars they own, or admins can access any car's build lists.
    """
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # First check if the car exists and get its owner
    db_car = get_entity_or_404(db, DBCar, car_id, "car")

    # Check authorization - users can only access build lists for cars they own, or admins can access any
    verify_user_access_or_admin(current_user, db_car.user_id, "access this car's build lists", logger)

    build_lists = db.query(DBBuildList).filter(DBBuildList.car_id == car_id).offset(skip).limit(limit).all()
    if not build_lists:
        logger.info(f"No Build Lists found for car with id {car_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for car {car_id}: {build_lists}")
    return [BuildListRead.model_validate(build_list) for build_list in build_lists]


@router.get(
    "/user/me",
    response_model=List[BuildListRead],
    responses=pagination_responses("build list", allow_public_read=False),
)
async def read_my_build_lists(
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListRead]:
    """
    Retrieve all build lists owned by the current user with pagination.
    """
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    build_lists = db.query(DBBuildList).filter(DBBuildList.user_id == current_user.id).offset(skip).limit(limit).all()
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {current_user.id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {current_user.id}: {build_lists}")
    return [BuildListRead.model_validate(build_list) for build_list in build_lists]


@router.get(
    "/user/{user_id}",
    response_model=List[BuildListRead],
    responses=pagination_responses("build list", allow_public_read=False),
)
async def read_build_lists_by_user(
    user_id: int,
    skip: int = Query(0, ge=0, description="Number of build lists to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of build lists to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> List[BuildListRead]:
    """
    Retrieve all build lists owned by a specific user with pagination.
    Users can only access their own build lists, or admins can access any user's build lists.
    """
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # Check authorization - users can only access their own build lists, or admins can access any
    verify_user_access_or_admin(current_user, user_id, "access this user's build lists", logger)

    build_lists = db.query(DBBuildList).filter(DBBuildList.user_id == user_id).offset(skip).limit(limit).all()
    if not build_lists:
        logger.info(f"No Build Lists found for user with id {user_id}")
    else:
        logger.info(msg=f"Build Lists retrieved for user {user_id}: {build_lists}")
    return [BuildListRead.model_validate(build_list) for build_list in build_lists]


# Add count endpoint
base_router.add_count_endpoint()
