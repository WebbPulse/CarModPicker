"""
Part manufacturers endpoint.

Two classes of manufacturer share this table:

- **Curated** (``is_curated=True``) — created by the crawler service account
  or admins. The catalog list/search/facet UIs only show these.
- **UGC** (``is_curated=False``) — created by regular users while making a
  Part. Scoped to a single ``created_by_user_id``. Reachable by id (no read
  boundary) but excluded from catalog browsing so one user's "Honda" entry
  doesn't pollute everyone else's autocomplete and search results.

Routing of ``POST /``:
  - service-account or admin caller -> curated row.
  - regular user -> UGC row scoped to them, with auto-link-to-curated dedup.

Edit/delete authorization:
  - admin/superuser: any row.
  - creator of a UGC row: their own row only (and only if no parts use it).
"""

from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.user import User as DBUser
from app.api.schemas.part import PartRead
from app.api.schemas.part_manufacturer import (
    PartManufacturerAdminUpdate,
    PartManufacturerCreate,
    PartManufacturerResponse,
    PartManufacturerUpdate,
)
from app.api.services.base_crud_service import BaseCRUDService
from app.api.services.part_listing_service import (
    get_or_create_curated_part_manufacturer,
    get_or_create_ugc_part_manufacturer,
)
from app.api.utils.authorization import (
    require_part_manufacturer_delete_permission,
    require_part_manufacturer_edit_permission,
)
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


def _user_is_admin(user: Optional[DBUser]) -> bool:
    return user is not None and (user.is_admin or user.is_superuser)


def _user_is_service_account(user: Optional[DBUser]) -> bool:
    return user is not None and user.is_service_account


def _resolve_include_ugc(requested: bool, user: Optional[DBUser]) -> bool:
    """Honor ``include_ugc=true`` only for admins/superusers; ignore otherwise.

    Catalog browse must never surface UGC to regular users — the whole point
    of the boundary. Admins are allowed to opt in for moderation views.
    """
    return requested and _user_is_admin(user)


class PartManufacturerService(
    BaseCRUDService[DBPartManufacturer, PartManufacturerCreate, PartManufacturerResponse, PartManufacturerUpdate]
):
    """Part manufacturer service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBPartManufacturer,
            entity_name="part manufacturer",
        )

    def get_active_part_manufacturers(
        self, db: Session, *, include_ugc: bool = False
    ) -> List[DBPartManufacturer]:
        """Get active part manufacturers ordered by name. Curated-only by default."""
        stmt = select(DBPartManufacturer).where(DBPartManufacturer.is_active.is_(True))
        if not include_ugc:
            stmt = stmt.where(DBPartManufacturer.is_curated.is_(True))
        return list(db.scalars(stmt.order_by(DBPartManufacturer.name)).all())


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
    include_ugc: bool = Query(
        False,
        description="Include user-created (UGC) manufacturers. Honored only for admins; ignored otherwise.",
    ),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[PartManufacturerResponse]:
    """List part manufacturers. Curated-only by default; admins may opt-in to UGC."""
    db = deps["db"]
    effective_include_ugc = _resolve_include_ugc(include_ugc, current_user)
    if active_only:
        part_manufacturers = part_manufacturer_service.get_active_part_manufacturers(
            db, include_ugc=effective_include_ugc
        )
    else:
        stmt = select(DBPartManufacturer)
        if not effective_include_ugc:
            stmt = stmt.where(DBPartManufacturer.is_curated.is_(True))
        part_manufacturers = list(db.scalars(stmt.order_by(DBPartManufacturer.name)).all())
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
    include_ugc: bool = Query(
        False,
        description="Include user-created (UGC) manufacturers. Honored only for admins; ignored otherwise.",
    ),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[PartManufacturerResponse]:
    """Search part manufacturers. Curated-only by default; admins may opt-in to UGC."""
    db = deps["db"]
    skip, limit = validate_pagination_params(skip, limit)
    effective_include_ugc = _resolve_include_ugc(include_ugc, current_user)

    like_term = f"%{q}%"
    stmt = select(DBPartManufacturer).where(
        (DBPartManufacturer.name.ilike(like_term)) | (DBPartManufacturer.description.ilike(like_term))
    )
    if not effective_include_ugc:
        stmt = stmt.where(DBPartManufacturer.is_curated.is_(True))
    stmt = stmt.order_by(DBPartManufacturer.name).offset(skip).limit(limit)
    part_manufacturers = list(db.scalars(stmt).all())
    return [PartManufacturerResponse.model_validate(pm) for pm in part_manufacturers]


@router.get("/{part_manufacturer_id}", response_model=PartManufacturerResponse)
async def get_part_manufacturer(
    part_manufacturer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartManufacturerResponse:
    """Get a manufacturer by id. Public; no read boundary between curated and UGC."""
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
    """Parts that reference this manufacturer.

    Curated mfr: catalog-only (excludes ``source='user_created'`` parts).
    UGC mfr: only the creator's parts (a UGC mfr only ever has one creator).
    """
    db = deps["db"]
    pm = get_entity_or_404(db, DBPartManufacturer, part_manufacturer_id, "part manufacturer")
    skip, limit = validate_pagination_params(skip, limit)

    stmt = select(DBPart).where(DBPart.part_manufacturer_id == part_manufacturer_id)
    if pm.is_curated:
        stmt = stmt.where(DBPart.source != "user_created")
    elif pm.created_by_user_id is not None:
        stmt = stmt.where(DBPart.user_id == pm.created_by_user_id)

    parts = list(db.scalars(stmt.offset(skip).limit(limit)).all())
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
    """Create a manufacturer.

    - service-account or admin caller -> curated row.
    - regular user -> UGC row scoped to them. If a curated row matches the
      name (case-insensitive), the user's part silently links to the curated
      row instead of creating a duplicate.
    """
    db = deps["db"]
    name = part_manufacturer.name.strip() if part_manufacturer.name else ""
    if not name:
        ResponsePatterns.raise_bad_request("Part manufacturer name is required", "PART_MANUFACTURER_NAME_REQUIRED")

    if _user_is_service_account(current_user) or _user_is_admin(current_user):
        pm = get_or_create_curated_part_manufacturer(db, name)
    else:
        pm = get_or_create_ugc_part_manufacturer(db, name, creator_id=current_user.id)

    if pm is None:
        ResponsePatterns.raise_bad_request("Part manufacturer name is required", "PART_MANUFACTURER_NAME_REQUIRED")

    if part_manufacturer.description and not pm.description:
        pm.description = part_manufacturer.description
        db.add(pm)
    db.commit()
    db.refresh(pm)
    return PartManufacturerResponse.model_validate(pm)


@router.put(
    "/{part_manufacturer_id}",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "update"),
)
async def update_part_manufacturer(
    part_manufacturer_id: UUID,
    part_manufacturer: PartManufacturerAdminUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartManufacturerResponse:
    """Update a manufacturer.

    - admin/superuser: any row, including ``is_curated`` toggle.
    - creator of a UGC row: name/description/is_active only. ``is_curated``
      changes are silently dropped for non-admin callers.
    """
    db = deps["db"]
    db_pm = get_entity_or_404(db, DBPartManufacturer, part_manufacturer_id, "part manufacturer")
    require_part_manufacturer_edit_permission(current_user, db_pm)

    update_data = part_manufacturer.model_dump(exclude_unset=True)
    # is_curated toggle is admin-only; silently drop for non-admins so a UGC
    # creator can't promote their own row by editing it.
    if not _user_is_admin(current_user):
        update_data.pop("is_curated", None)

    new_name = update_data.get("name")
    if new_name and new_name != db_pm.name:
        # Conflict check uses the same uniqueness model as the partial unique
        # indexes: curated rows are globally unique by lower(name); UGC rows
        # are unique per (lower(name), created_by_user_id).
        conflict_stmt = select(DBPartManufacturer).where(
            DBPartManufacturer.id != db_pm.id,
            DBPartManufacturer.name.ilike(new_name),
        )
        if db_pm.is_curated:
            conflict_stmt = conflict_stmt.where(DBPartManufacturer.is_curated.is_(True))
        else:
            conflict_stmt = conflict_stmt.where(
                DBPartManufacturer.is_curated.is_(False),
                DBPartManufacturer.created_by_user_id == db_pm.created_by_user_id,
            )
        if db.scalars(conflict_stmt).first():
            ResponsePatterns.raise_conflict(
                "Part manufacturer with this name already exists", "PART_MANUFACTURER_EXISTS"
            )

    for field, value in update_data.items():
        setattr(db_pm, field, value)

    try:
        db.add(db_pm)
        db.commit()
        db.refresh(db_pm)
        return PartManufacturerResponse.model_validate(db_pm)
    except Exception as e:
        db.rollback()
        handle_integrity_error(e, "part manufacturer")
        raise


@router.delete(
    "/{part_manufacturer_id}",
    response_model=PartManufacturerResponse,
    responses=crud_responses("part manufacturer", "delete"),
)
async def delete_part_manufacturer(
    part_manufacturer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartManufacturerResponse:
    """Delete a manufacturer.

    - admin/superuser: any row.
    - creator of a UGC row: their own row only.
    Cannot delete if any Part still references it.
    """
    db = deps["db"]
    db_pm = get_entity_or_404(db, DBPartManufacturer, part_manufacturer_id, "part manufacturer")
    require_part_manufacturer_delete_permission(current_user, db_pm)

    parts_count = (
        db.scalar(
            select(func.count()).select_from(DBPart).where(DBPart.part_manufacturer_id == part_manufacturer_id)
        )
        or 0
    )
    if parts_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete part manufacturer that has {parts_count} associated parts",
            "PART_MANUFACTURER_IN_USE",
        )

    pm_response = PartManufacturerResponse.model_validate(db_pm)
    db.delete(db_pm)
    db.commit()
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
    """Count of parts referencing this manufacturer (no UGC/curated filter)."""
    get_entity_or_404(deps["db"], DBPartManufacturer, part_manufacturer_id, "part manufacturer")

    parts_count = (
        deps["db"].scalar(
            select(func.count()).select_from(DBPart).where(DBPart.part_manufacturer_id == part_manufacturer_id)
        )
        or 0
    )
    return {"parts_count": parts_count}


base_router.add_count_endpoint()


@router.get(
    "/counts/by-source",
    responses=standard_responses(success_description="Counts of curated vs UGC part manufacturers"),
)
async def get_part_manufacturer_counts_by_source(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Total/curated/UGC manufacturer counts for the admin dashboard."""
    db = deps["db"]
    curated = db.scalar(
        select(func.count()).select_from(DBPartManufacturer).where(DBPartManufacturer.is_curated.is_(True))
    ) or 0
    ugc = db.scalar(
        select(func.count()).select_from(DBPartManufacturer).where(DBPartManufacturer.is_curated.is_(False))
    ) or 0
    return {"total": curated + ugc, "curated": curated, "ugc": ugc}
