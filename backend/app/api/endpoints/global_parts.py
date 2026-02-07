"""
Refactored global parts endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseEndpointRouter to provide common CRUD operations
while maintaining global part-specific functionality.
"""

import logging
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.car import Car as DBCar
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.global_part_car import global_part_cars
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.schemas.global_part import (
    MAX_IMAGES_PER_GLOBAL_PART,
    GlobalPartAppendImages,
    GlobalPartCreate,
    GlobalPartRead,
    GlobalPartReadWithListings,
    GlobalPartReadWithVotes,
    GlobalPartUpdate,
    SetPrimaryImageRequest,
)
from app.api.schemas.part_listing import (
    PartListingCreate,
    PartListingReadWithRetailer,
)
from app.api.schemas.part_price_history import PartPriceHistoryReadWithRetailer
from app.api.services.base_crud_service import BaseCRUDService
from app.api.services.part_listing_service import (
    create_or_update_listing_and_price,
    find_part_by_brand_and_part_number,
    find_part_by_gtin,
    find_part_by_product_url,
    get_best_listing_for_part,
    normalize_gtin,
    normalize_part_number,
)
from app.api.utils.authorization import (
    require_global_part_edit_permission,
)
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_operations import (
    check_subscription_limits,
    create_entity,
    delete_entity,
    update_entity,
    verify_entity_exists,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    apply_standard_filters,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import (
    pagination_responses,
    standard_responses,
)
from app.api.utils.pagination_utils import (
    create_paginated_response,
)
from app.api.utils.response_patterns import ResponsePatterns

# Create router
router = APIRouter()


# Create base CRUD service
class GlobalPartService(BaseCRUDService[DBGlobalPart, GlobalPartCreate, GlobalPartRead, GlobalPartUpdate]):
    """Global part service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBGlobalPart,
            entity_name="global part",
            subscription_check_method="can_create_global_part",
        )

    def create(
        self,
        db: Session,
        data: GlobalPartCreate,
        current_user: DBUser,
        logger: logging.Logger,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> DBGlobalPart:
        """
        Create a new global part with dedup by URL, brand+part_number, and GTIN (UPC/EAN).
        If an existing part is found, create/update PartListing and return that part.
        """
        check_subscription_limits(db, current_user, "can_create_global_part", self.entity_name, logger)

        part_by_url: Optional[DBGlobalPart] = None
        part_by_brand: Optional[DBGlobalPart] = None
        part_by_gtin: Optional[DBGlobalPart] = None

        if data.product_url and data.product_url.strip():
            part_by_url = find_part_by_product_url(db, data.product_url)
        if data.brand_id and data.part_number and data.part_number.strip():
            part_by_brand = find_part_by_brand_and_part_number(db, data.brand_id, data.part_number)
        if data.gtin and normalize_gtin(data.gtin):
            part_by_gtin = find_part_by_gtin(db, data.gtin)

        parts = [p for p in (part_by_gtin, part_by_url, part_by_brand) if p is not None]
        ids = {p.id for p in parts}
        if len(ids) > 1:
            logger.info(f"User {current_user.id} part create conflict: dedup keys point to different parts {ids}")
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
            if data.retailer_id and (data.product_url or data.price_cents is not None):
                _ = get_entity_or_404(db, DBRetailer, data.retailer_id, "retailer")
                create_or_update_listing_and_price(
                    db,
                    existing_part.id,
                    data.retailer_id,
                    product_url=data.product_url,
                    price_cents=data.price_cents,
                )
            logger.info(f"User {current_user.id} part create: returning existing part {existing_part.id} (dedup)")
            return existing_part

        entity_data = data.model_dump()
        entity_data.pop("retailer_id", None)
        entity_data.pop("price_cents", None)
        entity_data.pop("product_url", None)  # Only used for listing, not stored on part
        entity_data.pop("price", None)  # Removed: pricing is per-retailer via listings
        entity_data.pop("car_ids", None)  # Synced via association table after create
        if additional_data:
            entity_data.update(additional_data)
        entity_data["user_id"] = current_user.id
        # Store normalized part_number so lookups and future scrapes match
        entity_data["part_number"] = (
            normalize_part_number(data.part_number) if data.part_number else entity_data.get("part_number")
        )
        # Store normalized GTIN (digits only) for dedup
        if data.gtin:
            entity_data["gtin"] = normalize_gtin(data.gtin) or entity_data.get("gtin")
        # Cap gallery size; do not set image_url from scraped gallery (leave null if no manual primary)
        if entity_data.get("image_urls") is not None:
            entity_data["image_urls"] = entity_data["image_urls"][:MAX_IMAGES_PER_GLOBAL_PART]

        part = create_entity(
            db=db,
            model=DBGlobalPart,
            data=entity_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

        if data.retailer_id and (data.product_url or data.price_cents is not None):
            _ = get_entity_or_404(db, DBRetailer, data.retailer_id, "retailer")
            create_or_update_listing_and_price(
                db,
                part.id,
                data.retailer_id,
                product_url=data.product_url,
                price_cents=data.price_cents,
            )

        # Sync car associations: part fits all cars (is_universal) or listed car_ids
        if not part.is_universal and data.car_ids:
            for cid in data.car_ids:
                get_entity_or_404(db, DBCar, cid, "car")
            part.cars = [db.get(DBCar, cid) for cid in data.car_ids]
        else:
            part.cars = []
        db.commit()
        db.refresh(part)

        return part

    def update(
        self,
        db: Session,
        entity_id: int,
        data: GlobalPartUpdate,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> DBGlobalPart:
        """
        Update an existing global part with proper authorization check.
        Allows creator, admin, or superuser to update.
        """
        # Verify entity exists
        entity = verify_entity_exists(db, self.model, entity_id, self.entity_name)

        # Check authorization (allows creator, admin, or superuser)
        require_global_part_edit_permission(current_user, entity)

        # Update the entity; cap image_urls to global limit; normalize gtin
        update_data = data.model_dump(exclude_unset=True)
        car_ids = update_data.pop("car_ids", None)
        if update_data.get("image_urls") is not None:
            update_data["image_urls"] = update_data["image_urls"][:MAX_IMAGES_PER_GLOBAL_PART]
        if "gtin" in update_data and update_data["gtin"] is not None:
            update_data["gtin"] = normalize_gtin(update_data["gtin"])
        # When primary image (image_url) is set (e.g. manual upload), ensure it appears in the carousel
        if update_data.get("image_url"):
            new_primary = update_data["image_url"]
            current_urls: List[str]
            if update_data.get("image_urls") is not None:
                current_urls = list(update_data["image_urls"])
            else:
                current_urls = list(entity.image_urls or []) or (
                    [entity.image_url] if entity.image_url else []
                )
            if new_primary not in current_urls:
                merged = [new_primary] + [u for u in current_urls if u != new_primary]
                update_data["image_urls"] = merged[:MAX_IMAGES_PER_GLOBAL_PART]
        # Sync car associations when car_ids was provided
        if car_ids is not None:
            is_universal_after = (
                update_data.get("is_universal") if "is_universal" in update_data else entity.is_universal
            )
            if not is_universal_after and car_ids:
                for cid in car_ids:
                    get_entity_or_404(db, DBCar, cid, "car")
                entity.cars = [db.get(DBCar, cid) for cid in car_ids]
            else:
                entity.cars = []
        return update_entity(
            db=db,
            entity=entity,
            update_data=update_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def delete(
        self,
        db: Session,
        entity_id: int,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> Dict[str, str]:
        """
        Delete an existing global part with proper authorization check.
        Allows creator, admin, or superuser to delete.
        """
        from app.api.utils.authorization import can_delete_global_part

        # Verify entity exists
        entity = verify_entity_exists(db, self.model, entity_id, self.entity_name)

        # Check authorization (allows creator, admin, or superuser)
        if not can_delete_global_part(current_user, entity):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail=(
                    "Not authorized to delete this global part. " "Only the creator or admin can delete global parts."
                ),
            )

        # Delete the entity
        return delete_entity(
            db=db,
            entity=entity,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )


global_part_service = GlobalPartService()

# Register custom endpoints BEFORE BaseEndpointRouter to ensure proper route precedence
# (More specific routes like /with-votes must be registered before generic routes like /{entity_id})


@router.get(
    "/with-votes",
    response_model=Dict[str, Any],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def read_global_parts_with_votes(
    skip: int = Query(0, ge=0, description="Number of global parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of global parts to return"),
    category_id: Optional[int] = Query(None, description="Filter by category ID (single; use category_ids for multi)"),
    category_ids: Optional[List[int]] = Query(None, description="Filter by category IDs (parts matching any)"),
    car_id: Optional[int] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[int]] = Query(None, description="Filter by car IDs (e.g. all generations for a make or model)"),
    brand_id: Optional[int] = Query(None, description="Filter by brand ID (single; use brand_ids for multi)"),
    brand_ids: Optional[List[int]] = Query(None, description="Filter by brand IDs (parts matching any)"),
    retailer_id: Optional[int] = Query(None, description="Filter to parts that have a listing from this retailer"),
    user_id: Optional[int] = Query(None, description="Filter to parts created by this user (for 'My Parts' view)"),
    sort: Optional[str] = Query(None, description="Sort: default by votes, or 'lowest_price' by best listing price"),
    search: Optional[str] = Query(None, description="Search in global part names and descriptions"),
    min_price_cents: Optional[int] = Query(None, ge=0, description="Filter to parts with best price >= this (cents)"),
    max_price_cents: Optional[int] = Query(None, ge=0, description="Filter to parts with best price <= this (cents)"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Get all global parts with vote data and optional filtering and search."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)
    effective_category_ids = category_ids if category_ids else ([category_id] if category_id is not None else None)
    effective_brand_ids = brand_ids if brand_ids else ([brand_id] if brand_id is not None else None)
    # Car filter: car_ids (make/model) takes precedence over single car_id
    effective_car_ids = car_ids if car_ids else ([car_id] if car_id is not None else None)
    has_price_filter = min_price_cents is not None or max_price_cents is not None

    # Create subquery for upvote counts
    upvote_counts = (
        db.query(
            DBVote.entity_id,
            func.count(DBVote.id).label("upvote_count"),
        )
        .filter(
            DBVote.entity_type == "global_part",
            DBVote.vote_type == "upvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    # Create subquery for downvote counts
    downvote_counts = (
        db.query(
            DBVote.entity_id,
            func.count(DBVote.id).label("downvote_count"),
        )
        .filter(
            DBVote.entity_type == "global_part",
            DBVote.vote_type == "downvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    # Build base query for counting (without joins to avoid JSON DISTINCT issues)
    base_query = db.query(DBGlobalPart)
    base_query = _apply_global_parts_list_filters(
        base_query,
        effective_category_ids,
        effective_brand_ids,
        effective_car_ids,
        search,
        user_id,
        retailer_id,
    )

    # Build main query with LEFT JOINs to vote count subqueries for sorting and retrieval
    query = (
        db.query(DBGlobalPart)
        .outerjoin(upvote_counts, DBGlobalPart.id == upvote_counts.c.entity_id)
        .outerjoin(downvote_counts, DBGlobalPart.id == downvote_counts.c.entity_id)
    )
    query = _apply_global_parts_list_filters(
        query,
        effective_category_ids,
        effective_brand_ids,
        effective_car_ids,
        search,
        user_id,
        retailer_id,
    )

    # Subquery: best (min) price per part from listings
    min_price_subq = (
        db.query(
            DBPartListing.global_part_id,
            func.min(DBPartListing.last_known_price_cents).label("min_price"),
        )
        .filter(DBPartListing.last_known_price_cents.isnot(None))
        .group_by(DBPartListing.global_part_id)
        .subquery()
    )

    # Price range filter: only parts whose best price is within [min_price_cents, max_price_cents]
    if has_price_filter:
        base_query = base_query.join(min_price_subq, DBGlobalPart.id == min_price_subq.c.global_part_id)
        if min_price_cents is not None:
            base_query = base_query.filter(min_price_subq.c.min_price >= min_price_cents)
        if max_price_cents is not None:
            base_query = base_query.filter(min_price_subq.c.min_price <= max_price_cents)
        query = query.join(min_price_subq, DBGlobalPart.id == min_price_subq.c.global_part_id)
        if min_price_cents is not None:
            query = query.filter(min_price_subq.c.min_price >= min_price_cents)
        if max_price_cents is not None:
            query = query.filter(min_price_subq.c.min_price <= max_price_cents)

    # Get total count from base query (after price filter)
    total = base_query.count()

    # Sort: by lowest price (best listing) or by net votes (default)
    if sort == "lowest_price":
        if not has_price_filter:
            query = query.outerjoin(min_price_subq, DBGlobalPart.id == min_price_subq.c.global_part_id)
        query = query.order_by(
            min_price_subq.c.min_price.asc().nullslast(),
            DBGlobalPart.id.desc(),
        )
    else:
        query = query.order_by(
            (
                func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)
            ).desc(),
            DBGlobalPart.id.desc(),
        )

    # Get paginated results
    # Since joins are one-to-one, we can get IDs in order, then fetch full objects
    # This avoids JSON DISTINCT issues
    ordered_ids = [row[0] for row in query.with_entities(DBGlobalPart.id).offset(skip).limit(limit).all()]

    if not ordered_ids:
        parts = []
    else:
        # Fetch full objects in the same order
        parts = (
            db.query(DBGlobalPart)
            .filter(DBGlobalPart.id.in_(ordered_ids))
            .outerjoin(upvote_counts, DBGlobalPart.id == upvote_counts.c.entity_id)
            .outerjoin(downvote_counts, DBGlobalPart.id == downvote_counts.c.entity_id)
            .order_by(
                (
                    func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)
                ).desc(),
                DBGlobalPart.id.desc(),
            )
            .all()
        )
        # Reorder to match the original order (in case the second query changes it)
        parts_dict = {part.id: part for part in parts}
        parts = [parts_dict[part_id] for part_id in ordered_ids if part_id in parts_dict]
    logger.info(f"Retrieved {len(parts)} global parts (skip: {skip}, limit: {limit})")

    if not parts:
        # Return empty response
        return create_paginated_response(data=[], total=total, skip=skip, limit=limit, entity_name="global parts")

    # Get part IDs
    part_ids = [part.id for part in parts]

    # Build vote count dictionaries from the subquery results
    # We already have upvote and downvote counts from the joins, but we need to extract them
    # Since we can't easily access the joined columns after the query, we'll fetch them separately
    # for the parts we retrieved
    vote_counts = (
        db.query(
            DBVote.entity_id,
            DBVote.vote_type,
            func.count(DBVote.id).label("count"),
        )
        .filter(
            DBVote.entity_type == "global_part",
            DBVote.entity_id.in_(part_ids),
        )
        .group_by(DBVote.entity_id, DBVote.vote_type)
        .all()
    )

    # Build vote count dictionaries
    upvotes_dict: Dict[int, int] = {}
    downvotes_dict: Dict[int, int] = {}
    for entity_id, vote_type, count in vote_counts:
        if vote_type == "upvote":
            upvotes_dict[entity_id] = count
        elif vote_type == "downvote":
            downvotes_dict[entity_id] = count

    # Min price per part (from retailer listings) for best_price_cents
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
    best_price_cents_dict: Dict[int, int] = {gp_id: int(mp) for gp_id, mp in min_prices}

    # Bulk fetch user votes if user is authenticated
    user_votes_dict: Dict[int, str] = {}
    if current_user:
        user_votes = (
            db.query(DBVote.entity_id, DBVote.vote_type)
            .filter(
                DBVote.entity_type == "global_part",
                DBVote.entity_id.in_(part_ids),
                DBVote.user_id == current_user.id,
            )
            .all()
        )
        user_votes_dict = {entity_id: vote_type for entity_id, vote_type in user_votes}

    # Convert parts to schema with vote data and best_price_cents
    parts_data: List[GlobalPartReadWithVotes] = []
    for part in parts:
        part_dict = GlobalPartRead.model_validate(part).model_dump()
        part_dict["best_price_cents"] = best_price_cents_dict.get(part.id)
        part_dict["upvotes"] = upvotes_dict.get(part.id, 0)
        part_dict["downvotes"] = downvotes_dict.get(part.id, 0)
        part_dict["total_votes"] = part_dict["upvotes"] + part_dict["downvotes"]
        part_dict["user_vote"] = user_votes_dict.get(part.id, None)
        part_with_votes = GlobalPartReadWithVotes(**part_dict)
        parts_data.append(part_with_votes)

    # Return paginated response
    return create_paginated_response(
        data=cast(List[Any], parts_data), total=total, skip=skip, limit=limit, entity_name="global parts"
    )


def _apply_global_parts_list_filters(
    query: Any,
    category_ids: Optional[List[int]],
    brand_ids: Optional[List[int]],
    car_ids: Optional[List[int]],
    search: Optional[str],
    user_id: Optional[int],
    retailer_id: Optional[int],
):
    """Apply list filters to a query that has DBGlobalPart as root. Returns the query."""
    query = apply_standard_filters(
        query=query,
        search=search,
        category_id=None,
        search_fields=["name", "description"],
    )
    if category_ids:
        query = query.filter(DBGlobalPart.category_id.in_(category_ids))
    if brand_ids:
        query = query.filter(DBGlobalPart.brand_id.in_(brand_ids))
    if car_ids:
        part_fits_any_car = exists().where(
            (global_part_cars.c.global_part_id == DBGlobalPart.id)
            & (global_part_cars.c.car_id.in_(car_ids))
        )
        query = query.filter(or_(DBGlobalPart.is_universal, part_fits_any_car))
    if user_id is not None:
        query = query.filter(DBGlobalPart.user_id == user_id)
    if retailer_id is not None:
        query = query.join(DBPartListing).filter(
            DBPartListing.global_part_id == DBGlobalPart.id,
            DBPartListing.retailer_id == retailer_id,
        )
    return query


def _global_parts_base_query(
    db: Session,
    category_ids: Optional[List[int]],
    brand_ids: Optional[List[int]],
    car_ids: Optional[List[int]],
    search: Optional[str],
    user_id: Optional[int],
    retailer_id: Optional[int],
):
    """Build base query for global parts list with filters applied (no pagination/sort)."""
    q = db.query(DBGlobalPart)
    return _apply_global_parts_list_filters(
        q, category_ids, brand_ids, car_ids, search, user_id, retailer_id
    )


@router.get(
    "/filter-options",
    response_model=Dict[str, Any],
)
async def get_global_parts_filter_options(
    category_ids: Optional[List[int]] = Query(None, description="Filter by category IDs (parts matching any)"),
    brand_ids: Optional[List[int]] = Query(None, description="Filter by brand IDs (parts matching any)"),
    car_id: Optional[int] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[int]] = Query(None, description="Filter by car IDs (e.g. all generations for a make or model)"),
    search: Optional[str] = Query(None, description="Search in names and descriptions"),
    user_id: Optional[int] = Query(None, description="Filter to parts created by this user (e.g. for My Parts)"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, Any]:
    """
    Return category_ids and brand_ids that have at least one part matching the current filters.
    Use this for cascading filters: e.g. when a brand is selected, only show categories that have parts for that brand.
    """
    db = deps["db"]
    effective_car_ids = car_ids if car_ids else ([car_id] if car_id is not None else None)
    q = _global_parts_base_query(
        db,
        category_ids=category_ids,
        brand_ids=brand_ids,
        car_ids=effective_car_ids,
        search=search,
        user_id=user_id,
        retailer_id=None,
    )
    available_categories = [
        row[0]
        for row in q.with_entities(DBGlobalPart.category_id).distinct().filter(DBGlobalPart.category_id.isnot(None)).all()
    ]
    available_brands = [
        row[0]
        for row in q.with_entities(DBGlobalPart.brand_id).distinct().filter(DBGlobalPart.brand_id.isnot(None)).all()
    ]
    return {"category_ids": available_categories, "brand_ids": available_brands}


@router.get(
    "/category/{category_id}",
    response_model=List[GlobalPartRead],
    responses=pagination_responses("global part", allow_public_read=True),
)
async def get_global_parts_by_category(
    category_id: int,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[GlobalPartRead]:
    """Get global parts by category with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    parts = db.query(DBGlobalPart).filter(DBGlobalPart.category_id == category_id).offset(skip).limit(limit).all()
    logger.info(f"Retrieved {len(parts)} parts for category {category_id}")
    return [GlobalPartRead.model_validate(part) for part in parts]


@router.get(
    "/check-url",
    response_model=Dict[str, Optional[int]],
    responses=standard_responses(
        success_description="URL check completed",
    ),
)
async def check_product_url_exists(
    product_url: Optional[str] = Query(None, description="Product URL to check"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, Optional[int]]:
    """
    Check if a product URL already exists in the global parts catalog.
    Returns the part ID if found, null otherwise.
    """
    db = deps["db"]
    logger = deps["logger"]

    try:
        # FastAPI will decode the URL automatically, but let's ensure we handle it properly
        if not product_url or not product_url.strip():
            return {"existing_part_id": None}

        # Normalize the URL by stripping whitespace
        normalized_url = product_url.strip()

        existing_part = find_part_by_product_url(db, normalized_url)

        if existing_part:
            logger.info(f"URL check: Found existing part {existing_part.id} for URL: {normalized_url[:50]}...")
            return {"existing_part_id": existing_part.id}
        else:
            logger.debug(f"URL check: No existing part found for URL: {normalized_url[:50]}...")
            return {"existing_part_id": None}
    except Exception as e:
        logger.error(f"Error checking product URL: {str(e)}", exc_info=True)
        # Return None on error to avoid blocking the user
        return {"existing_part_id": None}


@router.get(
    "/find-by-brand-and-part-number",
    response_model=GlobalPartRead,
    responses=standard_responses(
        success_description="Existing part found",
        not_found=True,
    ),
)
async def find_global_part_by_brand_and_part_number(
    brand_id: int = Query(..., description="Brand ID"),
    part_number: str = Query(..., min_length=1, description="Part number or SKU"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartRead:
    """
    Find an existing global part by brand and part number (normalized).
    Used by scrapers to detect update mode when the same part is scraped from another URL.
    Returns 404 if no matching part exists.
    """
    db = deps["db"]
    part = find_part_by_brand_and_part_number(db, brand_id, part_number)
    if not part:
        raise HTTPException(status_code=404, detail="No global part found for this brand and part number")
    return GlobalPartRead.model_validate(part)


@router.get(
    "/{global_part_id}/listings",
    response_model=List[PartListingReadWithRetailer],
    responses=standard_responses(
        success_description="Part listings retrieved",
        not_found=True,
    ),
)
async def get_global_part_listings(
    global_part_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartListingReadWithRetailer]:
    """List all retailer listings for a global part (with current price)."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    listings = (
        db.query(DBPartListing)
        .filter(DBPartListing.global_part_id == global_part_id)
        .options(joinedload(DBPartListing.retailer))
        .all()
    )
    return [PartListingReadWithRetailer.model_validate(l) for l in listings]


@router.post(
    "/{global_part_id}/listings",
    response_model=PartListingReadWithRetailer,
    responses=standard_responses(
        success_description="Part listing created or updated",
        not_found=True,
    ),
)
async def create_or_update_global_part_listing(
    global_part_id: int,
    data: PartListingCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartListingReadWithRetailer:
    """Create or update a retailer listing for a global part (and optionally add a price)."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    _ = get_entity_or_404(db, DBRetailer, data.retailer_id, "retailer")
    if data.global_part_id != global_part_id:
        ResponsePatterns.raise_conflict(
            message="Body global_part_id must match path global_part_id.",
            error_code="GLOBAL_PART_ID_MISMATCH",
        )
    listing = create_or_update_listing_and_price(
        db,
        global_part_id,
        data.retailer_id,
        product_url=data.product_url,
        price_cents=data.price_cents,
    )
    db.commit()
    db.refresh(listing)
    listing_with_retailer = (
        db.query(DBPartListing)
        .filter(DBPartListing.id == listing.id)
        .options(joinedload(DBPartListing.retailer))
        .first()
    )
    return PartListingReadWithRetailer.model_validate(listing_with_retailer)


@router.post(
    "/{global_part_id}/append-images",
    response_model=GlobalPartRead,
    responses=standard_responses(
        success_description="Images appended to part",
        not_found=True,
    ),
)
async def append_images_to_global_part(
    global_part_id: int,
    data: GlobalPartAppendImages,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartRead:
    """
    Append image file keys to a global part's gallery.
    Used when re-scraping finds new images not yet in the catalog.
    """
    db = deps["db"]
    part = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    require_global_part_edit_permission(current_user, part)

    existing = list(part.image_urls or []) or ([part.image_url] if part.image_url else [])
    if len(existing) >= MAX_IMAGES_PER_GLOBAL_PART:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Global part already has the maximum number of images ({MAX_IMAGES_PER_GLOBAL_PART}).",
        )

    seen = set(existing)
    for fk in data.file_keys:
        if fk and fk not in seen and len(existing) < MAX_IMAGES_PER_GLOBAL_PART:
            existing.append(fk)
            seen.add(fk)

    part.image_urls = existing[:MAX_IMAGES_PER_GLOBAL_PART]
    # Do not set primary image from appended (scraped) images; leave image_url as-is
    db.commit()
    db.refresh(part)
    return GlobalPartRead.model_validate(part)


def _get_part_image_file_keys(part: DBGlobalPart) -> List[str]:
    """Return ordered list of image file keys (gallery + primary if not in gallery)."""
    urls = list(part.image_urls or [])
    if not urls and part.image_url:
        return [part.image_url]
    return urls


@router.delete(
    "/{global_part_id}/images/{image_index}",
    response_model=GlobalPartRead,
    responses=standard_responses(
        success_description="Image removed from part",
        not_found=True,
    ),
)
async def remove_image_from_global_part(
    global_part_id: int,
    image_index: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartRead:
    """
    Remove the image at the given index from the global part's gallery.
    Requires edit permission. Removes from storage when the image is a stored file key.
    """
    from app.api.services.storage_service import storage_service
    from app.api.utils.image_utils import is_file_key

    db = deps["db"]
    part = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    require_global_part_edit_permission(current_user, part)

    file_keys = _get_part_image_file_keys(part)
    if image_index < 0 or image_index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {image_index}. Part has {len(file_keys)} image(s).",
        )

    removed_key = file_keys[image_index]
    new_keys = [fk for i, fk in enumerate(file_keys) if i != image_index]

    part.image_urls = new_keys if new_keys else None
    if part.image_url == removed_key:
        part.image_url = new_keys[0] if new_keys else None

    if removed_key and is_file_key(removed_key):
        try:
            storage_service.delete_image(removed_key)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to delete image from storage for part %s: %s",
                global_part_id,
                e,
            )

    db.commit()
    db.refresh(part)
    return GlobalPartRead.model_validate(part)


@router.patch(
    "/{global_part_id}/primary-image",
    response_model=GlobalPartRead,
    responses=standard_responses(
        success_description="Primary image updated",
        not_found=True,
    ),
)
async def set_primary_image_for_global_part(
    global_part_id: int,
    data: SetPrimaryImageRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> GlobalPartRead:
    """
    Set the image at the given index as the primary (display) image and move it to the front of the gallery.
    Requires edit permission.
    """
    db = deps["db"]
    part = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    require_global_part_edit_permission(current_user, part)

    file_keys = _get_part_image_file_keys(part)
    if data.index < 0 or data.index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {data.index}. Part has {len(file_keys)} image(s).",
        )

    primary_key = file_keys[data.index]
    new_order = [primary_key] + [fk for i, fk in enumerate(file_keys) if i != data.index]
    part.image_urls = new_order
    part.image_url = primary_key
    db.commit()
    db.refresh(part)
    return GlobalPartRead.model_validate(part)


@router.get(
    "/{global_part_id}/best-listing",
    response_model=PartListingReadWithRetailer,
    responses=standard_responses(
        success_description="Best (lowest price) listing retrieved",
        not_found=True,
    ),
)
async def get_global_part_best_listing(
    global_part_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartListingReadWithRetailer:
    """Get the listing with the lowest current price for this part. 404 if no listing has a price."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    best = get_best_listing_for_part(db, global_part_id)
    if not best:
        ResponsePatterns.raise_http_exception(
            status.HTTP_404_NOT_FOUND,
            "No listing with price for this part",
            error_code="NOT_FOUND",
        )
    listing_with_retailer = (
        db.query(DBPartListing).filter(DBPartListing.id == best.id).options(joinedload(DBPartListing.retailer)).first()
    )
    return PartListingReadWithRetailer.model_validate(listing_with_retailer)


@router.get(
    "/{global_part_id}/with-listings",
    response_model=GlobalPartReadWithListings,
    responses=standard_responses(
        success_description="Part with listings and best listing retrieved",
        not_found=True,
    ),
)
async def get_global_part_with_listings(
    global_part_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> GlobalPartReadWithListings:
    """Get a global part with all retailer listings and the best (lowest price) listing."""
    db = deps["db"]
    part = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    listings = (
        db.query(DBPartListing)
        .filter(DBPartListing.global_part_id == global_part_id)
        .options(joinedload(DBPartListing.retailer))
        .all()
    )
    best = get_best_listing_for_part(db, global_part_id)
    best_serialized = None
    if best:
        best_with_retailer = (
            db.query(DBPartListing)
            .filter(DBPartListing.id == best.id)
            .options(joinedload(DBPartListing.retailer))
            .first()
        )
        if best_with_retailer:
            best_serialized = PartListingReadWithRetailer.model_validate(best_with_retailer)
    part_dict = GlobalPartRead.model_validate(part).model_dump()
    part_dict["best_price_cents"] = best.last_known_price_cents if best else None
    return GlobalPartReadWithListings(
        **part_dict,
        listings=[PartListingReadWithRetailer.model_validate(l) for l in listings],
        best_listing=best_serialized,
    )


@router.get(
    "/{global_part_id}/price-history",
    response_model=List[PartPriceHistoryReadWithRetailer],
    responses=standard_responses(
        success_description="Price history retrieved",
        not_found=True,
    ),
)
async def get_global_part_price_history(
    global_part_id: int,
    retailer_id: Optional[int] = Query(None, description="Filter by retailer ID"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartPriceHistoryReadWithRetailer]:
    """Get price history for this part, optionally filtered by retailer. Ordered by observed_at desc."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBGlobalPart, global_part_id, "global part")
    query = (
        db.query(DBPartPriceHistory, DBPartListing, DBRetailer)
        .join(DBPartListing, DBPartPriceHistory.part_listing_id == DBPartListing.id)
        .join(DBRetailer, DBPartListing.retailer_id == DBRetailer.id)
        .filter(DBPartListing.global_part_id == global_part_id)
    )
    if retailer_id is not None:
        query = query.filter(DBPartListing.retailer_id == retailer_id)
    rows = query.order_by(DBPartPriceHistory.observed_at.desc()).all()
    return [
        PartPriceHistoryReadWithRetailer(
            id=h.id,
            part_listing_id=h.part_listing_id,
            price_cents=h.price_cents,
            observed_at=h.observed_at,
            retailer_id=r.id,
            retailer_name=r.name,
        )
        for h, _listing, r in rows
    ]


# Create base endpoint router AFTER custom endpoints to avoid route collision
base_router = BaseEndpointRouter(
    service=global_part_service,
    router=router,
    entity_name="global part",
    allow_public_read=True,  # Global parts can be viewed publicly
    additional_create_data={},  # No additional data needed for global parts
    create_schema=GlobalPartCreate,
    read_schema=GlobalPartRead,
    update_schema=GlobalPartUpdate,
    search_fields=["name", "description", "category"],
)


@router.get(
    "/user/{user_id}/count",
    response_model=dict,
    responses=standard_responses(success_description="Count of global parts for user", not_found=True),
)
async def count_global_parts_by_user(
    user_id: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Count global parts created by a specific user."""
    count = deps["db"].query(DBGlobalPart).filter(DBGlobalPart.user_id == user_id).count()
    return {"count": count}


# Add filter endpoint for category
base_router.add_filter_endpoint("category", "category_id")

# Add count endpoint
base_router.add_count_endpoint()
