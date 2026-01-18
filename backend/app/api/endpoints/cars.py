"""
Refactored cars endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining car-specific functionality.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.car_service import CarService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import (
    crud_responses,
    pagination_responses,
    search_responses,
    standard_responses,
)
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()

# Create service
car_service = CarService()


# Add custom endpoints specific to cars BEFORE base router
# These need to be defined first to avoid conflicts with /{entity_id} route
@router.get(
    "/search",
    response_model=List[CarRead],
    responses=search_responses("car", allow_public_read=True),
)
async def search_cars(
    q: str = Query(..., description="Search term for car make or model"),
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of cars to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Search cars by make or model with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.search_cars(db=db, search_term=q, skip=skip, limit=limit, logger=logger)
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/make/{make}",
    response_model=List[CarRead],
    responses=pagination_responses("car", allow_public_read=True),
)
async def get_cars_by_make(
    make: str,
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of cars to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Get cars by make with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.get_cars_by_make_model(db=db, make=make, skip=skip, limit=limit, logger=logger)
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/make/{make}/model/{model}",
    response_model=List[CarRead],
    responses=pagination_responses("car", allow_public_read=True),
)
async def get_cars_by_make_model(
    make: str,
    model: str,
    skip: int = Query(0, ge=0, description="Number of cars to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of cars to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Get cars by make and model with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    cars = car_service.get_cars_by_make_model(db=db, make=make, model=model, skip=skip, limit=limit, logger=logger)
    return [CarRead.model_validate(car) for car in cars]


@router.get(
    "/stats/makes",
    response_model=dict[str, int],
    responses=standard_responses(success_description="Car make statistics retrieved successfully"),
)
async def get_car_make_stats(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """Get statistics of cars by make."""
    from sqlalchemy import func

    db = deps["db"]
    logger = deps["logger"]

    stats = (
        db.query(DBCar.make, func.count(DBCar.id).label("count"))
        .group_by(DBCar.make)
        .order_by(func.count(DBCar.id).desc())
        .all()
    )

    result = {make: count for make, count in stats}
    logger.info(f"Retrieved car make statistics: {len(result)} makes")
    return result


# Create base endpoint router with only read operations
# Create/update/delete are admin-only and defined below
base_router = BaseEndpointRouter(
    service=car_service,
    router=router,
    entity_name="car",
    allow_public_read=True,  # Cars can be viewed publicly
    additional_create_data={},
    disable_endpoints=["create", "update", "delete"],  # These are admin-only
    create_schema=CarCreate,
    read_schema=CarRead,
    update_schema=CarUpdate,
    search_fields=["make", "model", "generation_name"],
)

# Add count endpoint
base_router.add_count_endpoint()


# --- Admin-only endpoints for car management ---


@router.post(
    "/admin/cars",
    response_model=CarRead,
    responses=crud_responses("car", "create"),
)
async def admin_create_car(
    car_data: CarCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CarRead:
    """Create a new car (admin only)."""
    # Validate year range
    if car_data.start_year > car_data.end_year:
        ResponsePatterns.raise_bad_request("start_year must be less than or equal to end_year")

    car = car_service.create(
        db=db,
        data=car_data,
        current_user=current_user,
        logger=logger,
    )
    logger.info(f"Admin {current_user.id} created car {car.id}")
    return CarRead.model_validate(car)


@router.put(
    "/admin/cars/{car_id}",
    response_model=CarRead,
    responses=crud_responses("car", "update"),
)
async def admin_update_car(
    car_id: int,
    car_data: CarUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CarRead:
    """Update a car (admin only)."""
    car = car_service.get_by_id(
        db=db,
        entity_id=car_id,
        allow_public=True,
        logger=logger,
    )

    # Validate year range if both are being updated
    update_dict = car_data.model_dump(exclude_unset=True)
    start_year = update_dict.get("start_year", car.start_year)
    end_year = update_dict.get("end_year", car.end_year)

    if start_year > end_year:
        ResponsePatterns.raise_bad_request("start_year must be less than or equal to end_year")

    updated_car = car_service.update(
        db=db,
        entity_id=car_id,
        data=car_data,
        current_user=current_user,
        logger=logger,
    )
    logger.info(f"Admin {current_user.id} updated car {car_id}")
    return CarRead.model_validate(updated_car)


@router.delete(
    "/admin/cars/{car_id}",
    response_model=CarRead,
    responses=crud_responses("car", "delete"),
)
async def admin_delete_car(
    car_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CarRead:
    """Delete a car (admin only)."""
    car = car_service.get_by_id(
        db=db,
        entity_id=car_id,
        allow_public=True,
        logger=logger,
    )

    # Check if car has build lists
    if car.build_lists:
        ResponsePatterns.raise_bad_request(
            f"Cannot delete car {car_id}: it has {len(car.build_lists)} build list(s) associated with it"
        )

    deleted_car = car_service.delete(
        db=db,
        entity_id=car_id,
        current_user=current_user,
        logger=logger,
    )
    logger.info(f"Admin {current_user.id} deleted car {car_id}")
    return CarRead.model_validate(deleted_car)
