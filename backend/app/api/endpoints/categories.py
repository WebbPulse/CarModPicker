"""
Categories endpoint - read-only.

Part categories are hardcoded in part_categories_data.py and seeded into the
database on startup. The backend source code is the source of truth; no create/update/delete.
"""

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.models.category import Category as DBCategory
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.api.schemas.global_part import GlobalPartRead
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import pagination_responses, standard_responses


# Category service (used only for get_active_categories; no create/update/delete)
class CategoryService(BaseCRUDService[DBCategory, CategoryCreate, CategoryResponse, CategoryUpdate]):
    """Category service - read-only; categories are seeded from part_categories_data."""

    def __init__(self) -> None:
        super().__init__(
            model=DBCategory,
            entity_name="category",
        )

    def get_active_categories(self, db: Session) -> List[DBCategory]:
        """Get all active categories ordered by sort order."""
        return db.query(DBCategory).filter(DBCategory.is_active.is_(True)).order_by(DBCategory.sort_order).all()


# Create router
router = APIRouter()
category_service = CategoryService()

# Base router only for count endpoint; list/create/update/delete are disabled
base_router = BaseEndpointRouter(
    service=category_service,
    router=router,
    entity_name="category",
    allow_public_read=True,
    additional_create_data={},
    disable_endpoints=["list", "delete", "create", "update"],
    create_schema=CategoryCreate,
    read_schema=CategoryResponse,
    update_schema=CategoryUpdate,
    search_fields=["name", "description"],
)


@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[CategoryResponse]:
    """Get all active categories (seeded from backend source code)."""
    db = deps["db"]
    categories = category_service.get_active_categories(db)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> CategoryResponse:
    """Get specific category details."""
    db = deps["db"]
    category = get_entity_or_404(db, DBCategory, category_id, "category")
    return CategoryResponse.model_validate(category)


@router.get(
    "/{category_id}/global-parts",
    response_model=List[GlobalPartRead],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def get_global_parts_by_category(
    category_id: UUID,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[GlobalPartRead]:
    """Get global parts by category with pagination."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBCategory, category_id, "category")
    skip, limit = validate_pagination_params(skip, limit)
    parts = db.query(DBGlobalPart).filter(DBGlobalPart.category_id == category_id).offset(skip).limit(limit).all()
    return [GlobalPartRead.model_validate(part) for part in parts]


@router.get(
    "/{category_id}/parts-count",
    responses=standard_responses(
        success_description="Category parts count retrieved successfully",
        not_found=True,
    ),
)
async def get_category_parts_count(
    category_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """
    Get the count of parts in a specific category.
    """
    # Verify category exists
    get_entity_or_404(deps["db"], DBCategory, category_id, "category")

    parts_count = deps["db"].query(DBGlobalPart).filter(DBGlobalPart.category_id == category_id).count()
    return {"parts_count": parts_count}


# Add count endpoint
base_router.add_count_endpoint()
