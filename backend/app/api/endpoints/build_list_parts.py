"""
Refactored build list parts endpoint using common patterns to eliminate redundancy.

This endpoint now uses standardized patterns for pagination, error handling,
and response documentation while maintaining build list part-specific functionality.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_part import BuildListPart as DBBuildListPart
from app.api.models.category import Category as DBCategory
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_part import (
    BuildListPartCreate,
    BuildListPartRead,
    BuildListPartReadWithGlobalPart,
    BuildListPartUpdate,
    CreateGlobalPartAndAddToBuildListRequest,
)
from app.api.schemas.global_part import GlobalPartRead
from app.api.services.part_listing_service import (
    create_or_update_listing_and_price,
    find_part_by_brand_and_part_number,
    find_part_by_gtin,
    find_part_by_product_url,
    get_best_listing_for_part,
    normalize_gtin,
)
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

# Create router
router = APIRouter()


@router.get(
    "/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of build list parts",
    ),
)
async def count_build_list_parts(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Get total count of build list parts."""
    db = deps["db"]
    logger = deps["logger"]

    try:
        count = db.query(DBBuildListPart).count()
        logger.info(f"Retrieved build list parts count: {count}")
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting build list parts: {str(e)}")
        raise


@router.post(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Global part added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def add_global_part_to_build_list(
    build_list_id: int,
    global_part_id: int,
    build_list_part: BuildListPartCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Add an existing global part to a build list as a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists and user owns it or is admin
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    # Verify global part exists
    _ = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")

    # Check if global part is already in build list
    existing_relationship = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.global_part_id == global_part_id,
        )
        .first()
    )
    if existing_relationship:
        ResponsePatterns.raise_conflict("Global part already exists in build list")

    # Create the relationship
    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        global_part_id=global_part_id,
        added_by=current_user.id,
        quantity=build_list_part.quantity,
        notes=build_list_part.notes,
    )

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Global part {global_part_id} added to build list {build_list_id} "
        f"as build list part {db_build_list_part.id} by user {current_user.id}"
    )
    return BuildListPartRead.model_validate(db_build_list_part)


@router.get(
    "/{build_list_id}",
    response_model=List[BuildListPartRead],
    responses=standard_responses(
        success_description="Build list parts retrieved successfully",
        not_found=True,
    ),
)
async def get_build_list_parts(
    build_list_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[BuildListPartRead]:
    """Get all build list parts in a build list.
    Public read access - anyone can view build list parts.
    Only owners can modify them.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists - allow public read access
    _ = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    db_build_list_parts = db.query(DBBuildListPart).filter(DBBuildListPart.build_list_id == build_list_id).all()

    build_list_parts = [BuildListPartRead.model_validate(part) for part in db_build_list_parts]

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}")
    return build_list_parts


@router.put(
    "/{build_list_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Build list part updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_build_list_part(
    build_list_part_id: int,
    build_list_part: BuildListPartUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Find the build list part
    db_build_list_part = get_entity_or_404(db, DBBuildListPart, build_list_part_id, "build list part")

    # Get the build list for authorization check
    db_build_list = get_entity_or_404(db, DBBuildList, db_build_list_part.build_list_id, "build list")

    # Check authorization - user who added the part, build list owner, or admin can edit it
    require_build_list_part_edit_permission(current_user, db_build_list_part, db, db_build_list)

    # Update the fields
    update_data = build_list_part.model_dump(exclude_unset=True)
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
        success_description="Build list part deleted successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def delete_build_list_part(
    build_list_part_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Delete a build list part."""
    db = deps["db"]
    logger = deps["logger"]

    # Find the build list part
    db_build_list_part = get_entity_or_404(db, DBBuildListPart, build_list_part_id, "build list part")

    # Check authorization - only the user who added the part or admin can delete it
    require_build_list_part_delete_permission(current_user, db_build_list_part)

    # Convert to response model before deleting
    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(f"Build list part {db_build_list_part.id} deleted by user {current_user.id}")
    return deleted_data


@router.post(
    "/{build_list_id}/create-and-add-part",
    response_model=BuildListPartReadWithGlobalPart,
    responses=standard_responses(
        success_description="Global part created and added to build list successfully",
        not_found=True,
        forbidden=True,
        conflict=True,
    ),
)
async def create_global_part_and_add_to_build_list(
    build_list_id: int,
    request: CreateGlobalPartAndAddToBuildListRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartReadWithGlobalPart:
    """
    Create a new global part and automatically add it to the specified
    build list as a build list part.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists and user owns it or is admin
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    # Verify category exists
    _ = get_entity_or_404(db, DBCategory, request.category_id, "category")

    # Dedup: find existing part by URL, brand+part_number, or GTIN
    part_by_url: Optional[DBGlobalPart] = None
    part_by_brand: Optional[DBGlobalPart] = None
    part_by_gtin: Optional[DBGlobalPart] = None
    if request.product_url and request.product_url.strip():
        part_by_url = find_part_by_product_url(db, request.product_url)
    if request.brand_id and request.part_number and request.part_number.strip():
        part_by_brand = find_part_by_brand_and_part_number(db, request.brand_id, request.part_number)
    if request.gtin and normalize_gtin(request.gtin):
        part_by_gtin = find_part_by_gtin(db, request.gtin)

    parts = [p for p in (part_by_gtin, part_by_url, part_by_brand) if p is not None]
    ids = {p.id for p in parts}
    if len(ids) > 1:
        ResponsePatterns.raise_conflict(
            message="Product URL, brand+part number, or GTIN point to different existing parts.",
            error_code="PART_DEDUP_CONFLICT",
            details={
                "gtin_part_id": part_by_gtin.id if part_by_gtin else None,
                "url_part_id": part_by_url.id if part_by_url else None,
                "brand_part_id": part_by_brand.id if part_by_brand else None,
            },
        )

    existing_part = part_by_gtin or part_by_url or part_by_brand
    if existing_part:
        if request.retailer_id and (request.product_url or request.price_cents is not None):
            _ = get_entity_or_404(db, DBRetailer, request.retailer_id, "retailer")
            create_or_update_listing_and_price(
                db,
                existing_part.id,
                request.retailer_id,
                product_url=request.product_url,
                price_cents=request.price_cents,
            )
        db_build_list_part = DBBuildListPart(
            build_list_id=build_list_id,
            global_part_id=existing_part.id,
            added_by=current_user.id,
            quantity=request.quantity,
            notes=request.notes,
        )
        db.add(db_build_list_part)
        db.commit()
        db.refresh(db_build_list_part)
        db.refresh(existing_part)
        logger.info(
            f"User {current_user.id} added existing part {existing_part.id} to build list "
            f"{build_list_id} as build list part {db_build_list_part.id} (dedup)"
        )
        best = get_best_listing_for_part(db, existing_part.id)
        global_part_dict = GlobalPartRead.model_validate(existing_part).model_dump()
        global_part_dict["best_price_cents"] = best.last_known_price_cents if best else None
        return BuildListPartReadWithGlobalPart(
            id=db_build_list_part.id,
            build_list_id=db_build_list_part.build_list_id,
            global_part_id=db_build_list_part.global_part_id,
            added_by=db_build_list_part.added_by,
            quantity=db_build_list_part.quantity,
            notes=db_build_list_part.notes,
            purchased=db_build_list_part.purchased,
            added_at=db_build_list_part.added_at,
            global_part=GlobalPartRead(**global_part_dict),
        )

    # No match: create new global part
    global_part_dict: Dict[str, Any] = {
        "name": request.name,
        "description": request.description,
        "image_url": request.image_url,
        "category_id": request.category_id,
        "car_id": request.car_id,
        "brand_id": request.brand_id,
        "part_number": request.part_number,
        "specifications": request.specifications,
        "user_id": current_user.id,
    }
    if request.gtin and normalize_gtin(request.gtin):
        global_part_dict["gtin"] = normalize_gtin(request.gtin)

    db_global_part = DBGlobalPart(**global_part_dict)
    db.add(db_global_part)
    db.flush()

    if request.retailer_id and (request.product_url or request.price_cents is not None):
        _ = get_entity_or_404(db, DBRetailer, request.retailer_id, "retailer")
        create_or_update_listing_and_price(
            db,
            db_global_part.id,
            request.retailer_id,
            product_url=request.product_url,
            price_cents=request.price_cents,
        )

    db_build_list_part = DBBuildListPart(
        build_list_id=build_list_id,
        global_part_id=db_global_part.id,
        added_by=current_user.id,
        quantity=request.quantity,
        notes=request.notes,
    )
    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_global_part)
    db.refresh(db_build_list_part)

    logger.info(
        f"Global part {db_global_part.id} created and added to build list "
        f"{build_list_id} as build list part {db_build_list_part.id} by user {current_user.id}"
    )
    best = get_best_listing_for_part(db, db_global_part.id)
    global_part_dict = GlobalPartRead.model_validate(db_global_part).model_dump()
    global_part_dict["best_price_cents"] = best.last_known_price_cents if best else None
    return BuildListPartReadWithGlobalPart(
        id=db_build_list_part.id,
        build_list_id=db_build_list_part.build_list_id,
        global_part_id=db_build_list_part.global_part_id,
        added_by=db_build_list_part.added_by,
        quantity=db_build_list_part.quantity,
        notes=db_build_list_part.notes,
        purchased=db_build_list_part.purchased,
        added_at=db_build_list_part.added_at,
        global_part=GlobalPartRead(**global_part_dict),
    )


@router.get(
    "/{build_list_id}/global-parts",
    response_model=List[BuildListPartReadWithGlobalPart],
    responses=standard_responses(
        success_description="Global parts in build list retrieved successfully",
        not_found=True,
    ),
)
async def get_global_parts_in_build_list(
    build_list_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> List[BuildListPartReadWithGlobalPart]:
    """Get all build list parts in a build list.
    Public read access - anyone can view build list parts.
    Only owners can modify them.
    """
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists - allow public read access
    _ = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    db_build_list_parts = (
        db.query(DBBuildListPart)
        .options(joinedload(DBBuildListPart.global_part))
        .filter(DBBuildListPart.build_list_id == build_list_id)
        .all()
    )

    # Pull lowest available price for every related global part (from retailer listings)
    part_ids = [p.global_part_id for p in db_build_list_parts]
    best_price_cents_dict: Dict[int, int] = {}
    if part_ids:
        min_prices = (
            db.query(
                DBPartListing.global_part_id,
                func.min(DBPartListing.last_known_price_cents).label("min_price"),
            )
            .filter(
                DBPartListing.global_part_id.in_(part_ids),
                DBPartListing.last_known_price_cents.isnot(None),
            )
            .group_by(DBPartListing.global_part_id)
            .all()
        )
        best_price_cents_dict = {gp_id: int(mp) for gp_id, mp in min_prices}

    def global_part_read_with_best_price(db_global_part: DBGlobalPart) -> GlobalPartRead:
        part_dict = GlobalPartRead.model_validate(db_global_part).model_dump()
        part_dict["best_price_cents"] = best_price_cents_dict.get(db_global_part.id)
        return GlobalPartRead(**part_dict)

    build_list_parts = [
        BuildListPartReadWithGlobalPart(
            id=part.id,
            build_list_id=part.build_list_id,
            global_part_id=part.global_part_id,
            added_by=part.added_by,
            quantity=part.quantity,
            notes=part.notes,
            purchased=part.purchased,
            added_at=part.added_at,
            global_part=global_part_read_with_best_price(part.global_part),
        )
        for part in db_build_list_parts
    ]

    user_info = f"User {current_user.id}" if current_user else "Anonymous user"
    logger.info(f"{user_info}: Retrieved {len(build_list_parts)} build list parts from build list {build_list_id}")
    return build_list_parts


@router.put(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Global part in build list updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_global_part_in_build_list(
    build_list_id: int,
    global_part_id: int,
    build_list_part: BuildListPartUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Update a build list part's notes in a build list."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists
    db_build_list = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Find the relationship
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.global_part_id == global_part_id,
        )
        .first()
    )
    if not db_build_list_part:
        ResponsePatterns.raise_not_found("Build list part not found in build list")

    # Check authorization - user who added the part, build list owner, or admin can edit it
    require_build_list_part_edit_permission(current_user, db_build_list_part, db, db_build_list)

    # Update the notes
    update_data = build_list_part.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_build_list_part, key, value)

    db.add(db_build_list_part)
    db.commit()
    db.refresh(db_build_list_part)

    logger.info(
        f"Build list part {db_build_list_part.id} updated in build list " f"{build_list_id} by user {current_user.id}"
    )
    return BuildListPartRead.model_validate(db_build_list_part)


@router.delete(
    "/{build_list_id}/global-parts/{global_part_id}",
    response_model=BuildListPartRead,
    responses=standard_responses(
        success_description="Global part removed from build list successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def remove_global_part_from_build_list(
    build_list_id: int,
    global_part_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPartRead:
    """Remove a build list part from a build list."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify build list exists
    _ = get_entity_or_404(db, DBBuildList, build_list_id, "build list")

    # Find the relationship
    db_build_list_part = (
        db.query(DBBuildListPart)
        .filter(
            DBBuildListPart.build_list_id == build_list_id,
            DBBuildListPart.global_part_id == global_part_id,
        )
        .first()
    )
    if not db_build_list_part:
        ResponsePatterns.raise_not_found("Build list part not found in build list")

    # Check authorization - only the user who added the part or admin can delete it
    require_build_list_part_delete_permission(current_user, db_build_list_part)

    # Convert to response model before deleting
    deleted_data = BuildListPartRead.model_validate(db_build_list_part)

    db.delete(db_build_list_part)
    db.commit()

    logger.info(
        f"Build list part {db_build_list_part.id} removed from build list " f"{build_list_id} by user {current_user.id}"
    )
    return deleted_data


@router.get(
    "/global-parts/{global_part_id}/build-lists/count",
    response_model=Dict[str, int],
    responses=standard_responses(
        success_description="Count of build lists containing the global part",
        not_found=True,
    ),
)
async def count_build_lists_containing_global_part(
    global_part_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Count the number of build lists that contain a specific global part."""
    db = deps["db"]
    logger = deps["logger"]

    # Verify global part exists
    _ = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")

    # Count distinct build lists that contain this global part
    count = (
        db.query(DBBuildListPart.build_list_id)
        .filter(DBBuildListPart.global_part_id == global_part_id)
        .distinct()
        .count()
    )

    logger.info(f"Global part {global_part_id} is contained in {count} build list(s)")
    return {"count": count}
