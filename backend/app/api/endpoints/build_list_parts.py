"""
Build list parts endpoint.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_part import BuildListPart as DBBuildListPart
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.schemas.build_list_part import (
    BuildListPartCreate,
    BuildListPartRead,
    BuildListPartReadWithPart,
    BuildListPartUpdate,
    CreatePartAndAddToBuildListRequest,
)
from app.api.schemas.part import PartCreate, PartRead
from app.api.services.part_listing_service import (
    best_price_for_group,
    create_or_update_listing_and_price,
    find_part_by_gtin,
    find_part_by_part_manufacturer_and_part_number,
    find_part_by_product_url,
    get_best_listing_for_part,
    link_group_ids,
    normalize_gtin,
)
from app.api.services.part_service import PartService
from app.api.utils.authorization import (
    require_build_list_part_delete_permission,
    require_build_list_part_edit_permission,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.catalog import Part
from app.db.dynamo.users import User as DBUser

# Create router
router = APIRouter()
part_service = PartService()


def _require_part(repos: Repositories, part_id: UUID) -> Part:
    part = repos.parts.get(str(part_id))
    if part is None:
        ResponsePatterns.raise_not_found("part", part_id)
    assert part is not None
    return part


def _part_read_with_best_price(part: Part) -> PartRead:
    best = get_best_listing_for_part(part.id)
    part_dict = PartRead.model_validate(part).model_dump()
    part_dict["best_price_cents"] = best.last_known_price_cents if best else None
    return PartRead(**part_dict)


def _build_list_part_with_part(
    db: Any, db_build_list_part: DBBuildListPart, part_read: PartRead
) -> BuildListPartReadWithPart:
    phase_name = None
    if db_build_list_part.build_list_phase_id:
        ph = db.get(DBBuildListPhase, db_build_list_part.build_list_phase_id)
        phase_name = ph.name if ph else None
    return BuildListPartReadWithPart(
        id=db_build_list_part.id,
        build_list_id=db_build_list_part.build_list_id,
        part_id=db_build_list_part.part_id,
        added_by=db_build_list_part.added_by,
        quantity=db_build_list_part.quantity,
        notes=db_build_list_part.notes,
        purchased=db_build_list_part.purchased,
        added_at=db_build_list_part.added_at,
        build_list_phase_id=db_build_list_part.build_list_phase_id,
        phase_name=phase_name,
        part=part_read,
    )


def _validate_phase_belongs_to_build_list(db, phase_id: Optional[UUID], build_list_id: UUID) -> None:
    """If phase_id is set, verify the phase exists and belongs to the build list."""
    if phase_id is None:
        return
    phase = get_entity_or_404(db, DBBuildListPhase, phase_id, "build list phase")
    if phase.build_list_id != build_list_id:
        ResponsePatterns.raise_not_found("Build list phase does not belong to this build list")


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(success_description="Count of build list parts"),
)
async def count_build_list_parts(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Get total count of build list parts."""
    db = deps["db"]
    logger = deps["logger"]

    try:
        count = db.scalar(select(func.count()).select_from(DBBuildListPart)) or 0
        logger.info(f"Retrieved build list parts count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting build list parts: {str(e)}")
        raise


@router.post(
    "/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Part added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def add_part_to_build_list(
    build_list_id: UUID,
    part_id: UUID,
    build_list_part: BuildListPartCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartRead:
    """Add an existing part to a build list as a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    _require_part(repos, part_id)

    existing_relationship = db.scalars(
        select(DBBuildListPart).where(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.part_id == part_id,
        )
    ).first()
    if existing_relationship:
        ResponsePatterns.raise_conflict("Part already exists in build list")

    _validate_phase_belongs_to_build_list(db, getattr(build_list_part, "build_list_phase_id", None), build_list_id)

    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        part_id=part_id,
        added_by=current_user.id,
        quantity=build_list_part.quantity,
        notes=build_list_part.notes,
        build_list_phase_id=getattr(build_list_part, "build_list_phase_id", None),
    )

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Part {part_id} added to build list {build_list_id} "
        f"as build list part {db_build_list_part.id} by user {current_user.id}"
    )
    return BuildListPartRead.model_validate(db_build_list_part)


@router.get(
    "/{build_list_id}",
    response_model=List[BuildListPartRead],
    responses=standard_responses(success_description="Build list parts retrieved successfully", not_found=True),
)
async def get_build_list_parts(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[BuildListPartRead]:
    """Get all build list parts in a build list. Public read access."""
    db = deps["db"]
    logger = deps["logger"]

    _ = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    db_build_list_parts = list(
        db.scalars(select(DBBuildListPart).where(DBBuildListPart.build_list_id == build_list_id)).all()
    )

    build_list_parts = [BuildListPartRead.model_validate(part) for part in db_build_list_parts]

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}")
    return build_list_parts


@router.put(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Build list part updated successfully", not_found=True, forbidden=True
    ),
)
async def update_build_list_part(
    build_list_part_id: UUID,
    build_list_part: BuildListPartUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    db_build_list_part = get_entity_or_404(db, DBBuildListPart, build_list_part_id, "build list part")
    db_build_list = get_entity_or_404(db, DBBuildList, db_build_list_part.build_list_id, "build list")

    require_build_list_part_edit_permission(current_user, db_build_list_part, db, db_build_list)

    update_data = build_list_part.model_dump(exclude_unset=True)
    if "build_list_phase_id" in update_data:
        _validate_phase_belongs_to_build_list(
            db,
            update_data["build_list_phase_id"],
            db_build_list_part.build_list_id,
        )
    for key, value in update_data.items():
        setattr(db_build_list_part, key, value)

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(f"Build list part {db_build_list_part.id} updated by user {current_user.id}")
    return BuildListPartRead.model_validate(db_build_list_part)


@router.delete(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Build list part deleted successfully", not_found=True, forbidden=True
    ),
)
async def delete_build_list_part(
    build_list_part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Delete a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    db_build_list_part = get_entity_or_404(db, DBBuildListPart, build_list_part_id, "build list part")
    require_build_list_part_delete_permission(current_user, db_build_list_part)

    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(f"Build list part {db_build_list_part.id} deleted by user {current_user.id}")
    return deleted_data


@router.post(
    "/{build_list_id}/create-and-add-part",
    response_model=BuildListPartReadWithPart,
    responses=standard_responses(
        success_description="Part created and added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def create_part_and_add_to_build_list(
    build_list_id: UUID,
    request: CreatePartAndAddToBuildListRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
) -> BuildListPartReadWithPart:
    """Create a new part and automatically add it to the specified build list."""
    db = deps["db"]
    logger = deps["logger"]

    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    if repos.categories.get(str(request.category_id)) is None:
        ResponsePatterns.raise_not_found("category", request.category_id)

    _validate_phase_belongs_to_build_list(db, getattr(request, "build_list_phase_id", None), build_list_id)

    # Dedup: find existing part by URL, part_manufacturer+part_number, or GTIN
    part_by_url: Optional[Part] = None
    part_by_part_manufacturer: Optional[Part] = None
    part_by_gtin: Optional[Part] = None
    if request.product_url and request.product_url.strip():
        part_by_url = find_part_by_product_url(request.product_url)
    if request.part_manufacturer_id and request.part_number and request.part_number.strip():
        part_by_part_manufacturer = find_part_by_part_manufacturer_and_part_number(
            request.part_manufacturer_id, request.part_number
        )
    if request.gtin and normalize_gtin(request.gtin):
        part_by_gtin = find_part_by_gtin(request.gtin)

    parts = [p for p in (part_by_gtin, part_by_url, part_by_part_manufacturer) if p is not None]
    ids = {p.id for p in parts}
    if len(ids) > 1:
        ResponsePatterns.raise_conflict(
            message="Product URL, part manufacturer + part number, or GTIN point to different existing parts.",
            error_code="PART_DEDUP_CONFLICT",
            details={
                "gtin_part_id": part_by_gtin.id if part_by_gtin else None,
                "url_part_id": part_by_url.id if part_by_url else None,
                "part_manufacturer_part_id": part_by_part_manufacturer.id if part_by_part_manufacturer else None,
            },
        )

    existing_part = part_by_gtin or part_by_url or part_by_part_manufacturer
    if existing_part:
        if request.retailer_id and (request.product_url or request.price_cents is not None):
            if repos.retailers.get(str(request.retailer_id)) is None:
                ResponsePatterns.raise_not_found("retailer", request.retailer_id)
            create_or_update_listing_and_price(
                db,
                existing_part.id,
                request.retailer_id,
                product_url=request.product_url,
                price_cents=request.price_cents,
            )
        db_build_list_part = DBBuildListPart(
            build_list_id=build_list_id,
            part_id=existing_part.id,
            added_by=current_user.id,
            quantity=request.quantity,
            notes=request.notes,
            build_list_phase_id=getattr(request, "build_list_phase_id", None),
        )
        db.add(db_build_list_part)
        db.commit()
        db.refresh(db_build_list_part)
        existing_part = repos.parts.get(str(existing_part.id)) or existing_part
        logger.info(
            f"User {current_user.id} added existing part {existing_part.id} to build list "
            f"{build_list_id} as build list part {db_build_list_part.id} (dedup)"
        )
        return _build_list_part_with_part(db, db_build_list_part, _part_read_with_best_price(existing_part))

    part_create = PartCreate(
        name=request.name,
        description=request.description,
        image_urls=request.image_urls,
        product_url=request.product_url,
        category_id=request.category_id,
        car_ids=request.car_ids,
        is_universal=request.is_universal,
        part_manufacturer_id=request.part_manufacturer_id,
        part_number=request.part_number,
        gtin=request.gtin,
        retailer_id=request.retailer_id,
        price_cents=request.price_cents,
    )
    if request.retailer_id and (request.product_url or request.price_cents is not None):
        if repos.retailers.get(str(request.retailer_id)) is None:
            ResponsePatterns.raise_not_found("retailer", request.retailer_id)
    db_part = part_service.create_part(db, part_create, current_user, logger)

    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        part_id=db_part.id,
        added_by=current_user.id,
        quantity=request.quantity,
        notes=request.notes,
        build_list_phase_id=getattr(request, "build_list_phase_id", None),
    )
    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Part {db_part.id} created and added to build list "
        f"{build_list_id} as build list part {db_build_list_part.id} by user {current_user.id}"
    )
    return _build_list_part_with_part(db, db_build_list_part, _part_read_with_best_price(db_part))


@router.get(
    "/{build_list_id}/parts",
    response_model=List[BuildListPartReadWithPart],
    responses=standard_responses(success_description="Parts in build list retrieved successfully", not_found=True),
)
async def get_parts_in_build_list(
    build_list_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
    repos: Repositories = Depends(get_repositories),
) -> List[BuildListPartReadWithPart]:
    """Get all build list parts in a build list. Public read access."""
    db = deps["db"]
    logger = deps["logger"]

    _ = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    db_build_list_parts = list(
        db.scalars(
            select(DBBuildListPart)
            .options(joinedload(DBBuildListPart.build_list_phase))
            .where(DBBuildListPart.build_list_id == build_list_id)
        )
        .unique()
        .all()
    )

    # Resolve each BuildListPart.part to its canonical for display. BuildListPart.part_id
    # stays as stored (no FK repoint) so we preserve the exact part the user added, but
    # the rendered Part data is always the canonical so users see the surface record.
    stored_parts = repos.parts.get_many({p.part_id for p in db_build_list_parts})
    canonical_ids_to_load = {
        part.canonical_part_id for part in stored_parts.values() if part.canonical_part_id is not None
    }
    canonicals: Dict[UUID, Part] = repos.parts.get_many(canonical_ids_to_load) if canonical_ids_to_load else {}

    def effective_part(stored: Part) -> Part:
        if stored.canonical_part_id and stored.canonical_part_id in canonicals:
            return canonicals[stored.canonical_part_id]
        return stored

    best_price_cents_dict: Dict[UUID, Optional[int]] = {}

    def part_read_with_best_price(part: Part) -> PartRead:
        if part.id not in best_price_cents_dict:
            best_price_cents_dict[part.id] = best_price_for_group(link_group_ids(part))
        part_dict = PartRead.model_validate(part).model_dump()
        part_dict["best_price_cents"] = best_price_cents_dict[part.id]
        return PartRead(**part_dict)

    build_list_parts = [
        BuildListPartReadWithPart(
            id=part.id,
            build_list_id=part.build_list_id,
            part_id=part.part_id,
            added_by=part.added_by,
            quantity=part.quantity,
            notes=part.notes,
            purchased=part.purchased,
            added_at=part.added_at,
            build_list_phase_id=part.build_list_phase_id,
            phase_name=part.build_list_phase.name if part.build_list_phase else None,
            part=part_read_with_best_price(effective_part(stored_parts[part.part_id])),
        )
        for part in db_build_list_parts
        if part.part_id in stored_parts
    ]

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}")
    return build_list_parts


@router.put(
    "/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Part in build list updated successfully", not_found=True, forbidden=True
    ),
)
async def update_part_in_build_list(
    build_list_id: UUID,
    part_id: UUID,
    build_list_part: BuildListPartUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part's notes in a build list."""
    db = deps["db"]
    logger = deps["logger"]

    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    db_build_list_part = db.scalars(
        select(DBBuildListPart).where(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.part_id == part_id,
        )
    ).first()
    if not db_build_list_part:
        ResponsePatterns.raise_not_found("Build list part not found in build list")

    require_build_list_part_edit_permission(current_user, db_build_list_part, db, db_build_list)

    update_data = build_list_part.model_dump(exclude_unset=True)
    if "build_list_phase_id" in update_data:
        _validate_phase_belongs_to_build_list(db, update_data["build_list_phase_id"], build_list_id)
    for key, value in update_data.items():
        setattr(db_build_list_part, key, value)

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Build list part {db_build_list_part.id} updated in build list {build_list_id} by user {current_user.id}"
    )
    return BuildListPartRead.model_validate(db_build_list_part)


@router.delete(
    "/{build_list_id}/parts/{part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Part removed from build list successfully", not_found=True, forbidden=True
    ),
)
async def remove_part_from_build_list(
    build_list_id: UUID,
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Remove a build list part from a build list."""
    db = deps["db"]
    logger = deps["logger"]

    _ = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    db_build_list_part = db.scalars(
        select(DBBuildListPart).where(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.part_id == part_id,
        )
    ).first()
    if not db_build_list_part:
        ResponsePatterns.raise_not_found("Build list part not found in build list")

    require_build_list_part_delete_permission(current_user, db_build_list_part)

    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(
        f"Build list part {db_build_list_part.id} removed from build list {build_list_id} by user {current_user.id}"
    )
    return deleted_data


@router.get(
    "/parts/{part_id}/build-lists/count",
    response_model=Dict[str, int],
    responses=standard_responses(success_description="Count of build lists containing the part", not_found=True),
)
async def count_build_lists_containing_part(
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, int]:
    """Count the number of build lists that contain a specific part."""
    db = deps["db"]
    logger = deps["logger"]

    _require_part(repos, part_id)

    count = (
        db.scalar(
            select(func.count(func.distinct(DBBuildListPart.build_list_id))).where(DBBuildListPart.part_id == part_id)
        )
        or 0
    )

    logger.info(f"Part {part_id} is contained in {count} build list(s)")
    return {"count": count}
