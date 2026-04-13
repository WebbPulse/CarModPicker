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
    "/makes/count",
    response_model=dict,
    responses=standard_responses(success_description="Make count retrieved successfully"),
)
async def count_makes(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Get total count of Make entities (e.g. Honda, Toyota)."""
    from app.api.models.make import Make

    db = deps["db"]
    logger = deps["logger"]
    count = db.query(Make).count()
    logger.info(f"Retrieved makes count: {count}")
    return {"count": count}


@router.get(
    "/car-models/count",
    response_model=dict,
    responses=standard_responses(success_description="Car model count retrieved successfully"),
)
async def count_car_models(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Get total count of CarModel entities (e.g. Civic, Camry under a Make)."""
    from app.api.models.car_model import CarModel

    db = deps["db"]
    logger = deps["logger"]
    count = db.query(CarModel).count()
    logger.info(f"Retrieved car models count: {count}")
    return {"count": count}


@router.get(
    "/stats/makes",
    response_model=dict[str, int],
    responses=standard_responses(success_description="Car make statistics retrieved successfully"),
)
async def get_car_make_stats(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """Get statistics of cars by make (via Make entity)."""
    from sqlalchemy import func

    from app.api.models.car_model import CarModel
    from app.api.models.make import Make

    db = deps["db"]
    logger = deps["logger"]

    stats = (
        db.query(Make.name, func.count(DBCar.id).label("count"))
        .select_from(DBCar)
        .join(DBCar.car_model)
        .join(CarModel.make)
        .group_by(Make.name)
        .order_by(func.count(DBCar.id).desc())
        .all()
    )

    result = {row[0]: row[1] for row in stats}
    logger.info(f"Retrieved car make statistics: {len(result)} makes")
    return result


@router.get(
    "/by-ids",
    response_model=List[CarRead],
    responses=standard_responses(success_description="Cars retrieved successfully"),
)
async def get_cars_by_ids(
    ids: List[int] = Query(..., description="Car IDs to fetch"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarRead]:
    """Batch-fetch cars by a list of IDs. Used by the frontend to resolve car names for the catalog table."""
    db = deps["db"]
    logger = deps["logger"]
    cars = car_service.get_by_ids(db=db, ids=ids, logger=logger)
    return [CarRead.model_validate(car) for car in cars]


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
