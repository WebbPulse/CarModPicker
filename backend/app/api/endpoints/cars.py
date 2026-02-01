"""
Cars endpoint - read-only.

Car generations are hardcoded in car_generations_data.py and seeded into the
database on startup. The backend source code is the source of truth; no create/update/delete.
"""

from typing import List

from fastapi import APIRouter, Depends, Query

from app.api.models.car import Car as DBCar
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.car_service import CarService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    search_responses,
    standard_responses,
)

# Create router
router = APIRouter()
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


# Base endpoint router - read-only; cars are seeded from car_generations_data
base_router = BaseEndpointRouter(
    service=car_service,
    router=router,
    entity_name="car",
    allow_public_read=True,
    additional_create_data={},
    disable_endpoints=["create", "update", "delete"],
    create_schema=CarCreate,
    read_schema=CarRead,
    update_schema=CarUpdate,
    search_fields=["make", "model", "generation_name"],
)
base_router.add_count_endpoint()
