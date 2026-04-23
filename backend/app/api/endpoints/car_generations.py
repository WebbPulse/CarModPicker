"""
Car generations endpoint - read-only.

Car generations are hardcoded in car_generations_data.py and seeded into the
database on startup. The backend source code is the source of truth; no create/update/delete.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.models.car_generation import CarGeneration as DBCarGeneration
from app.api.schemas.car_generation import CarGenerationCreate, CarGenerationRead, CarGenerationUpdate
from app.api.services.car_generation_service import CarGenerationService
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
car_generation_service = CarGenerationService()


# Add custom endpoints specific to cars BEFORE base router
# These need to be defined first to avoid conflicts with /{entity_id} route
@router.get(
    "/search",
    response_model=List[CarGenerationRead],
    responses=search_responses("car_generation", allow_public_read=True),
)
async def search_car_generations(
    q: str = Query(..., description="Search term for car make or model"),
    skip: int = Query(0, ge=0, description="Number of generations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of generations to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarGenerationRead]:
    """Search car generations by make or model with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    generations = car_generation_service.search_car_generations(
        db=db, search_term=q, skip=skip, limit=limit, logger=logger
    )
    return [CarGenerationRead.model_validate(gen) for gen in generations]


@router.get(
    "/car-makes/count",
    response_model=dict,
    responses=standard_responses(success_description="CarMake count retrieved successfully"),
)
async def count_car_makes(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Get total count of CarMake entities (e.g. Honda, Toyota)."""
    from app.api.models.car_make import CarMake

    db = deps["db"]
    logger = deps["logger"]
    count = db.scalar(select(func.count()).select_from(CarMake)) or 0
    logger.info(f"Retrieved car_makes count: {count}")
    return {"count": count}


@router.get(
    "/car-models/count",
    response_model=dict,
    responses=standard_responses(success_description="CarModel count retrieved successfully"),
)
async def count_car_models(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Get total count of CarModel entities (e.g. Civic, Camry under a CarMake)."""
    from app.api.models.car_model import CarModel

    db = deps["db"]
    logger = deps["logger"]
    count = db.scalar(select(func.count()).select_from(CarModel)) or 0
    logger.info(f"Retrieved car_models count: {count}")
    return {"count": count}


@router.get(
    "/car-makes/{car_make_name}/car-models/{car_model_name}",
    response_model=List[CarGenerationRead],
    responses=pagination_responses("car_generation", allow_public_read=True),
)
async def get_car_generations_by_car_make_model(
    car_make_name: str,
    car_model_name: str,
    skip: int = Query(0, ge=0, description="Number of generations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of generations to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarGenerationRead]:
    """Get car generations by car make and model with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    generations = car_generation_service.get_car_generations_by_make_model(
        db=db, car_make_name=car_make_name, car_model_name=car_model_name, skip=skip, limit=limit, logger=logger
    )
    return [CarGenerationRead.model_validate(gen) for gen in generations]


@router.get(
    "/car-makes/{car_make_name}",
    response_model=List[CarGenerationRead],
    responses=pagination_responses("car_generation", allow_public_read=True),
)
async def get_car_generations_by_car_make(
    car_make_name: str,
    skip: int = Query(0, ge=0, description="Number of generations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of generations to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarGenerationRead]:
    """Get car generations by car make with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    generations = car_generation_service.get_car_generations_by_make_model(
        db=db, car_make_name=car_make_name, skip=skip, limit=limit, logger=logger
    )
    return [CarGenerationRead.model_validate(gen) for gen in generations]


@router.get(
    "/stats/car-makes",
    response_model=dict[str, int],
    responses=standard_responses(success_description="Car make statistics retrieved successfully"),
)
async def get_car_make_stats(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict[str, int]:
    """Get statistics of car generations by car make."""
    from app.api.models.car_make import CarMake
    from app.api.models.car_model import CarModel

    db = deps["db"]
    logger = deps["logger"]

    stats = db.execute(
        select(CarMake.name, func.count(DBCarGeneration.id).label("count"))
        .select_from(DBCarGeneration)
        .join(DBCarGeneration.car_model)
        .join(CarModel.car_make)
        .group_by(CarMake.name)
        .order_by(func.count(DBCarGeneration.id).desc())
    ).all()

    result = {row[0]: row[1] for row in stats}
    logger.info(f"Retrieved car_make statistics: {len(result)} car_makes")
    return result


@router.get(
    "/by-ids",
    response_model=List[CarGenerationRead],
    responses=standard_responses(success_description="Car generations retrieved successfully"),
)
async def get_car_generations_by_ids(
    ids: List[UUID] = Query(..., description="Car generation IDs to fetch"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CarGenerationRead]:
    """Batch-fetch car generations by a list of IDs."""
    db = deps["db"]
    logger = deps["logger"]
    generations = car_generation_service.get_by_ids(db=db, ids=ids, logger=logger)
    return [CarGenerationRead.model_validate(gen) for gen in generations]


# Base endpoint router - read-only; car generations are seeded from car_generations_data
base_router = BaseEndpointRouter(
    service=car_generation_service,
    router=router,
    entity_name="car_generation",
    allow_public_read=True,
    additional_create_data={},
    disable_endpoints=["create", "update", "delete"],
    create_schema=CarGenerationCreate,
    read_schema=CarGenerationRead,
    update_schema=CarGenerationUpdate,
    search_fields=["car_make_name", "car_model_name", "generation_name"],
)
base_router.add_count_endpoint()
