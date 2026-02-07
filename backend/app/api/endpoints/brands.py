"""
Brands endpoint for managing part brands.

Allows users to create and search brands, with admin-only update/delete operations.
"""

from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.brand import Brand as DBBrand
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.brand import BrandCreate, BrandResponse, BrandUpdate
from app.api.schemas.global_part import GlobalPartRead
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    handle_integrity_error,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import (
    crud_responses,
    pagination_responses,
    search_responses,
    standard_responses,
)
from app.api.utils.response_patterns import ResponsePatterns


# Create base CRUD service
class BrandService(BaseCRUDService[DBBrand, BrandCreate, BrandResponse, BrandUpdate]):
    """Brand service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBBrand,
            entity_name="brand",
        )

    def get_active_brands(self, db: Session) -> List[DBBrand]:
        """Get all active brands ordered by name."""
        return db.query(DBBrand).filter(DBBrand.is_active.is_(True)).order_by(DBBrand.name).all()


# Create router
router = APIRouter()

# Create service
brand_service = BrandService()

# Create base endpoint router
base_router = BaseEndpointRouter(
    service=brand_service,
    router=router,
    entity_name="brand",
    allow_public_read=True,  # Brands can be viewed publicly
    additional_create_data={},  # No additional data needed
    disable_endpoints=[
        "list",
        "get",
        "delete",
        "create",
        "update",
    ],  # Disable automatic endpoints - we use custom /search, /{brand_id}, etc.
    create_schema=BrandCreate,
    read_schema=BrandResponse,
    update_schema=BrandUpdate,
    search_fields=["name", "description"],
)


# Custom endpoints specific to brands
@router.get("/", response_model=List[BrandResponse])
async def get_brands(
    active_only: bool = Query(True, description="Only return active brands"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[BrandResponse]:
    """
    Get all brands (optionally filtered to active only).
    """
    db = deps["db"]
    if active_only:
        brands = brand_service.get_active_brands(db)
    else:
        brands = db.query(DBBrand).order_by(DBBrand.name).all()
    return [BrandResponse.model_validate(brand) for brand in brands]


@router.get(
    "/search",
    response_model=List[BrandResponse],
    responses=search_responses("brand", allow_public_read=True),
)
async def search_brands(
    q: str = Query(..., description="Search term for brand name or description"),
    skip: int = Query(0, ge=0, description="Number of brands to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of brands to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[BrandResponse]:
    """Search brands by name or description with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    brands = brand_service.list_all(
        db=db, skip=skip, limit=limit, search=q, search_fields=["name", "description"], logger=logger
    )
    return [BrandResponse.model_validate(brand) for brand in brands]


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> BrandResponse:
    """
    Get specific brand details.
    """
    db = deps["db"]
    brand = get_entity_or_404(db, DBBrand, brand_id, "brand")
    return BrandResponse.model_validate(brand)


@router.get(
    "/{brand_id}/global-parts",
    response_model=List[GlobalPartRead],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def get_global_parts_by_brand(
    brand_id: int,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[GlobalPartRead]:
    """
    Get global parts by brand with pagination.
    """
    db = deps["db"]

    # First verify the brand exists
    _ = get_entity_or_404(db, DBBrand, brand_id, "brand")

    # Validate pagination parameters
    skip, limit = validate_pagination_params(skip, limit)

    parts = db.query(DBGlobalPart).filter(DBGlobalPart.brand_id == brand_id).offset(skip).limit(limit).all()
    return [GlobalPartRead.model_validate(part) for part in parts]


@router.post(
    "/",
    response_model=BrandResponse,
    responses=crud_responses("brand", "create"),
)
async def create_brand(
    brand: BrandCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),  # Any authenticated user can create brands
) -> BrandResponse:
    """
    Create a new brand. Any authenticated user can create brands.
    """
    db = deps["db"]

    # Check if brand with same name already exists (case-insensitive)
    existing_brand = db.query(DBBrand).filter(DBBrand.name.ilike(brand.name)).first()
    if existing_brand:
        # Return existing brand instead of creating duplicate
        return BrandResponse.model_validate(existing_brand)

    db_brand = DBBrand(**brand.model_dump())
    db.add(db_brand)
    db.commit()
    db.refresh(db_brand)
    return BrandResponse.model_validate(db_brand)


@router.put(
    "/{brand_id}",
    response_model=BrandResponse,
    responses=crud_responses("brand", "update"),
)
async def update_brand(
    brand_id: int,
    brand: BrandUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> BrandResponse:
    """
    Update a brand (admin only).
    """
    db_brand = get_entity_or_404(deps["db"], DBBrand, brand_id, "brand")

    # Check if name is being changed and if it conflicts with existing
    if brand.name and brand.name != db_brand.name:
        existing_brand = deps["db"].query(DBBrand).filter(DBBrand.name.ilike(brand.name)).first()
        if existing_brand:
            ResponsePatterns.raise_conflict("Brand with this name already exists", "BRAND_EXISTS")

    # Update fields
    update_data = brand.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_brand, field, value)

    try:
        deps["db"].add(db_brand)
        deps["db"].commit()
        deps["db"].refresh(db_brand)
        return BrandResponse.model_validate(db_brand)
    except Exception as e:
        deps["db"].rollback()
        handle_integrity_error(e, "brand")
        raise  # Type narrowing


@router.delete(
    "/{brand_id}",
    response_model=BrandResponse,
    responses=crud_responses("brand", "delete"),
)
async def delete_brand(
    brand_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> BrandResponse:
    """
    Delete a brand (admin only).
    """
    db_brand = get_entity_or_404(deps["db"], DBBrand, brand_id, "brand")

    # Check if brand is being used by any parts
    parts_count = deps["db"].query(DBGlobalPart).filter(DBGlobalPart.brand_id == brand_id).count()
    if parts_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete brand that has {parts_count} associated parts",
            "BRAND_IN_USE",
        )

    # Convert to response model before deleting
    brand_response = BrandResponse.model_validate(db_brand)

    deps["db"].delete(db_brand)
    deps["db"].commit()
    return brand_response


@router.get(
    "/{brand_id}/parts-count",
    responses=standard_responses(
        success_description="Brand parts count retrieved successfully",
        not_found=True,
    ),
)
async def get_brand_parts_count(
    brand_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """
    Get the count of parts for a specific brand.
    """
    # Verify brand exists
    get_entity_or_404(deps["db"], DBBrand, brand_id, "brand")

    parts_count = deps["db"].query(DBGlobalPart).filter(DBGlobalPart.brand_id == brand_id).count()
    return {"parts_count": parts_count}


# Add count endpoint
base_router.add_count_endpoint()
