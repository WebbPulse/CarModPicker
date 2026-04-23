"""
Part manufacturers endpoint for managing part manufacturers.

Allows users to create and search part manufacturers, with admin-only update/delete operations.
"""

from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.user import User as DBUser
from app.api.schemas.part import PartRead
from app.api.schemas.part_manufacturer import (
    PartManufacturerCreate,
    PartManufacturerResponse,
    PartManufacturerUpdate,
)
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


class PartManufacturerService(
    BaseCRUDService[DBPartManufacturer, PartManufacturerCreate, PartManufacturerResponse, PartManufacturerUpdate]
):
    """Part manufacturer service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBPartManufacturer,
            entity_name="part manufacturer",
        )

    def get_active_part_manufacturers(self, db: Session) -> List[DBPartManufacturer]:
        """Get all active part manufacturers ordered by name."""
        return list(
            db.scalars(
                select(DBPartManufacturer)
                .where(DBPartManufacturer.is_active.is_(True))
                .order_by(DBPartManufacturer.name)
            ).all()
        )


router = APIRouter()

part_manufacturer_service = PartManufacturerService()

base_router = BaseEndpointRouter(
    service=part_manufacturer_service,
    router=router,
    entity_name="part manufacturer",
    allow_public_read=True,
    additional_create_data={},
    disable_endpoints=[
        "list",
        "get",
        "delete",
        "create",
        "update",
    ],
    create_schema=PartManufacturerCreate,
    read_schema=PartManufacturerResponse,
    update_schema=PartManufacturerUpdate,
    search_fields=["name", "description"],
)


@router.get("/", response_model=List[PartManufacturerResponse])
async def get_part_manufacturers(
    active_only: bool = Query(True, description="Only return active part manufacturers"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartManufacturerResponse]:
    """
    Get all part manufacturers (optionally filtered to active only).
    """
    db = deps["db"]
    if active_only:
        part_manufacturers = part_manufacturer_service.get_active_part_manufacturers(db)
    else:
        part_manufacturers = list(db.scalars(select(DBPartManufacturer).order_by(DBPartManufacturer.name)).all())
    return [PartManufacturerResponse.model_validate(pm) for pm in part_manufacturers]


@router.get(
    "/search",
    response_model=List[PartManufacturerResponse],
    responses=search_responses("part manufacturer", allow_public_read=True),
)
async def search_part_manufacturers(
    q: str = Query(..., description="Search term for part manufacturer name or description"),
    skip: int = Query(0, ge=0, description="Number of part manufacturers to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of part manufacturers to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartManufacturerResponse]:
    """Search part manufacturers by name or description with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip, limit)
    part_manufacturers = part_manufacturer_service.list_all(
        db=db, skip=skip, limit=limit, search=q, search_fields=["name", "description"], logger=logger
    )
    return [PartManufacturerResponse.model_validate(pm) for pm in part_manufacturers]


@router.get("/{part_manufacturer_id}", response_model=PartManufacturerResponse)
async def get_part_manufacturer(
    part_manufacturer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartManufacturerResponse:
    """
    Get specific part manufacturer details.
    """
    db = deps["db"]
    pm = get_entity_or_404(db, DBPartManufacturer, part_manufacturer_id, "part manufacturer")
    return PartManufacturerResponse.model_validate(pm)


@router.get(
    "/{part_manufacturer_id}/parts",
    response_model=List[PartRead],
    responses=pagination_responses("part", allow_public_read=True),
)
async def get_parts_by_part_manufacturer(
    part_manufacturer_id: UUID,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartRead]:
    """
    Get global parts by part manufacturer with pagination.
    """
    db = deps["db"]

    _ = get_entity_or_404(db, DBPartManufacturer, part_manufacturer_id, "part manufacturer")

    skip, limit = validate_pagination_params(skip, limit)

    parts = list(db.scalars(select(DBPart).where(DBPart.part_manufacturer_id == part_manufacturer_id).offset(skip).limit(limit)).all())
    return [PartRead.model_validate(part) for part in parts]


@router.post(
    "/",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "create"),
)
async def create_part_manufacturer(
    part_manufacturer: PartManufacturerCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartManufacturerResponse:
    """
    Create a new part manufacturer. Any authenticated user can create part manufacturers.
    """
    db = deps["db"]

    existing_pm = db.scalars(select(DBPartManufacturer).where(DBPartManufacturer.name.ilike(part_manufacturer.name))).first()
    if existing_pm:
        return PartManufacturerResponse.model_validate(existing_pm)

    db_pm = DBPartManufacturer(**part_manufacturer.model_dump())
    db.add(db_pm)
    db.commit()
    db.refresh(db_pm)
    return PartManufacturerResponse.model_validate(db_pm)


@router.put(
    "/{part_manufacturer_id}",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "update"),
)
async def update_part_manufacturer(
    part_manufacturer_id: UUID,
    part_manufacturer: PartManufacturerUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> PartManufacturerResponse:
    """
    Update a part manufacturer (admin only).
    """
    db_pm = get_entity_or_404(deps["db"], DBPartManufacturer, part_manufacturer_id, "part manufacturer")

    if part_manufacturer.name and part_manufacturer.name != db_pm.name:
        existing_pm = deps["db"].scalars(
            select(DBPartManufacturer).where(DBPartManufacturer.name.ilike(part_manufacturer.name))
        ).first()
        if existing_pm:
            ResponsePatterns.raise_conflict(
                "Part manufacturer with this name already exists", "PART_MANUFACTURER_EXISTS"
            )

    update_data = part_manufacturer.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_pm, field, value)

    try:
        deps["db"].add(db_pm)
        deps["db"].commit()
        deps["db"].refresh(db_pm)
        return PartManufacturerResponse.model_validate(db_pm)
    except Exception as e:
        deps["db"].rollback()
        handle_integrity_error(e, "part manufacturer")
        raise  # Type narrowing


@router.delete(
    "/{part_manufacturer_id}",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "delete"),
)
async def delete_part_manufacturer(
    part_manufacturer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> PartManufacturerResponse:
    """
    Delete a part manufacturer (admin only).
    """
    db_pm = get_entity_or_404(deps["db"], DBPartManufacturer, part_manufacturer_id, "part manufacturer")

    parts_count = deps["db"].scalar(select(func.count()).select_from(DBPart).where(DBPart.part_manufacturer_id == part_manufacturer_id)) or 0
    if parts_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete part manufacturer that has {parts_count} associated parts",
            "PART_MANUFACTURER_IN_USE",
        )

    pm_response = PartManufacturerResponse.model_validate(db_pm)

    deps["db"].delete(db_pm)
    deps["db"].commit()
    return pm_response


@router.get(
    "/{part_manufacturer_id}/parts-count",
    responses=standard_responses(
        success_description="Part manufacturer parts count retrieved successfully",
        not_found=True,
    ),
)
async def get_part_manufacturer_parts_count(
    part_manufacturer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """
    Get the count of parts for a specific part manufacturer.
    """
    get_entity_or_404(deps["db"], DBPartManufacturer, part_manufacturer_id, "part manufacturer")

    parts_count = deps["db"].scalar(select(func.count()).select_from(DBPart).where(DBPart.part_manufacturer_id == part_manufacturer_id)) or 0
    return {"parts_count": parts_count}


base_router.add_count_endpoint()
