"""
Parts endpoint using base classes to eliminate redundancy.
"""

import logging
from typing import Any, Dict, List, Optional, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies.auth import get_current_user, get_optional_current_user
from app.api.models.associations.part_car import part_cars
from app.api.models.car_generation import CarGeneration as DBCar
from app.api.models.car_make import CarMake as DBMake
from app.api.models.car_model import CarModel as DBCarModel
from app.api.models.category import Category as DBCategory
from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.schemas.part import (
    MAX_IMAGES_PER_PART,
    PartAppendImages,
    PartCreate,
    PartRead,
    PartReadWithListings,
    PartReadWithVotes,
    PartUpdate,
    SetPrimaryImageRequest,
)
from app.api.schemas.part_listing import PartListingCreate, PartListingReadWithRetailer
from app.api.schemas.part_price_history import PartPriceHistoryReadWithRetailer
from app.api.services.base_crud_service import BaseCRUDService
from app.api.services.part_linker_service import link_group_part_ids, link_new_part
from app.api.services.part_listing_service import (
    create_or_update_listing_and_price,
    find_existing_part_for_ugc_create,
    find_part_by_part_manufacturer_and_part_number,
    find_part_by_product_url,
    normalize_gtin,
    normalize_part_number,
)
from app.api.utils.authorization import require_part_edit_permission
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_operations import create_entity, delete_entity, update_entity, verify_entity_exists
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    apply_standard_filters,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import pagination_responses, standard_responses
from app.api.utils.pagination_utils import create_paginated_response
from app.api.utils.response_patterns import ResponsePatterns

# Create router
router = APIRouter()


# Create base CRUD service
class PartService(BaseCRUDService[DBPart, PartCreate, PartRead, PartUpdate]):
    """Part service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBPart,
            entity_name="part",
        )

    def create(
        self,
        db: Session,
        data: PartCreate,
        current_user: DBUser,
        logger: logging.Logger,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> DBPart:
        """
        Ingest a scraped or user-created part.

        Two ingest paths diverge on ``source``:

        **Scraped / archive_rescrape** (``source != "user_created"``):
        - URL-level dedup: if this product URL already owns a PartListing on a
          non-UGC Part, refresh that Part in place (scrape-wins) and append a
          price history point. Do NOT create a new Part row.
        - Otherwise create a new row and run the canonical linker, which
          inspects GTIN / manufacturer+part_number and links duplicates under
          a canonical.

        **User-created** (``source == "user_created"``, the default for
        extension/web submits):
        - UGC is isolated from the scraped catalog. Before creating, refuse if
          a non-UGC part already covers this product (return 409 pointing at
          it) or if the same user already has a UGC row for it (return 409
          pointing at their own prior row). Different-user UGC is allowed to
          coexist — no URL uniqueness.
        - On success, the row stays a standalone singleton: no URL-refresh,
          no ``link_new_part``, no ``canonical_part_id``.
        """
        source_val = (additional_data or {}).get("source") or "user_created"
        is_ugc = source_val == "user_created"

        if is_ugc:
            blocker = find_existing_part_for_ugc_create(
                db,
                creator_id=current_user.id,
                product_url=data.product_url,
            )
            if blocker is not None:
                existing, reason = blocker
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "PART_ALREADY_EXISTS",
                        "reason": reason,
                        "message": (
                            "A scraped part already covers this product."
                            if reason == "non_ugc_exists"
                            else "You already have a community-contributed part for this product."
                        ),
                        "existing_part_id": str(existing.id),
                        "existing_part_name": existing.name,
                        "existing_part_source": existing.source,
                    },
                )
        elif data.product_url and data.product_url.strip():
            existing = find_part_by_product_url(db, data.product_url)
            if existing is not None:
                return self._refresh_part_from_reingest(db, existing, data, logger, additional_data)

        entity_data = data.model_dump()
        entity_data.pop("retailer_id", None)
        entity_data.pop("price_cents", None)
        entity_data.pop("product_url", None)
        entity_data.pop("price", None)
        entity_data.pop("car_ids", None)
        if additional_data:
            for _k, _v in additional_data.items():
                entity_data[_k] = _v
        entity_data["user_id"] = current_user.id
        entity_data["part_number"] = (
            normalize_part_number(data.part_number) if data.part_number else entity_data.get("part_number")
        )
        if data.gtin:
            entity_data["gtin"] = normalize_gtin(data.gtin) or entity_data.get("gtin")
        if entity_data.get("image_urls") is not None:
            entity_data["image_urls"] = entity_data["image_urls"][:MAX_IMAGES_PER_PART]

        part = create_entity(
            db=db,
            model=DBPart,
            data=entity_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

        if not is_ugc:
            link_new_part(db, part, product_url=data.product_url)

        if data.retailer_id and (data.product_url or data.price_cents is not None):
            _ = get_entity_or_404(db, DBRetailer, data.retailer_id, "retailer")
            create_or_update_listing_and_price(
                db,
                part.id,
                data.retailer_id,
                product_url=data.product_url,
                price_cents=data.price_cents,
            )

        if not part.is_universal and data.car_ids:
            for cid in data.car_ids:
                get_entity_or_404(db, DBCar, cid, "car")
            part.car_generations = [db.get(DBCar, cid) for cid in data.car_ids]
        else:
            part.car_generations = []
        db.commit()
        db.refresh(part)

        return part

    def _refresh_part_from_reingest(
        self,
        db: Session,
        existing_part: DBPart,
        data: PartCreate,
        logger: logging.Logger,
        additional_data: Optional[Dict[str, Any]],
    ) -> DBPart:
        """
        Apply a repeat ingest of an already-known product URL onto the existing Part.

        Scrape-wins policy for parsed fields (name, description, images, category,
        manufacturer, cars, GTIN, part_number, specifications). Only non-null
        fields from the new payload are written, so a parser that loses a field
        on one run doesn't erase it. PartListing + PartPriceHistory get an
        upsert/append so price history stays continuous.
        """
        if data.name:
            existing_part.name = data.name
        if data.description is not None:
            existing_part.description = data.description
        if data.image_urls is not None:
            existing_part.image_urls = data.image_urls[:MAX_IMAGES_PER_PART]
        if data.category_id is not None:
            existing_part.category_id = data.category_id
        if data.part_manufacturer_id is not None:
            existing_part.part_manufacturer_id = data.part_manufacturer_id
        if data.part_number is not None:
            normalized_pn = normalize_part_number(data.part_number)
            if normalized_pn:
                existing_part.part_number = normalized_pn
        if data.gtin is not None:
            normalized_gtin = normalize_gtin(data.gtin)
            if normalized_gtin:
                existing_part.gtin = normalized_gtin
        if data.specifications is not None:
            existing_part.specifications = data.specifications
        if data.is_universal is not None:
            existing_part.is_universal = data.is_universal
        if additional_data and "source" in additional_data:
            existing_part.source = additional_data["source"]

        if existing_part.is_universal:
            existing_part.car_generations = []
        elif data.car_ids is not None:
            if data.car_ids:
                for cid in data.car_ids:
                    get_entity_or_404(db, DBCar, cid, "car")
                existing_part.car_generations = [db.get(DBCar, cid) for cid in data.car_ids]
            else:
                existing_part.car_generations = []

        db.add(existing_part)
        db.flush()

        if data.retailer_id and (data.product_url or data.price_cents is not None):
            _ = get_entity_or_404(db, DBRetailer, data.retailer_id, "retailer")
            create_or_update_listing_and_price(
                db,
                existing_part.id,
                data.retailer_id,
                product_url=data.product_url,
                price_cents=data.price_cents,
            )

        db.commit()
        db.refresh(existing_part)
        logger.debug(
            "Re-ingest: refreshed part %s in place (URL already known)",
            existing_part.id,
        )
        return existing_part

    def list_all(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        order_by: str = "created_at",
        order_direction: str = "desc",
        logger: Optional[logging.Logger] = None,
    ) -> List[DBPart]:
        """List canonical parts only — duplicates are hidden from the public catalog."""
        from app.api.utils.common_operations import build_filtered_query, build_search_query

        validate_pagination_params(skip, limit)
        stmt: Select[Any] = select(DBPart).where(DBPart.canonical_part_id.is_(None))
        if filters:
            stmt = build_filtered_query(stmt, filters)
        if search and search_fields:
            stmt = build_search_query(stmt, search, search_fields)
        order_field = getattr(DBPart, order_by, DBPart.created_at)
        stmt = stmt.order_by(order_field.desc() if order_direction == "desc" else order_field.asc())
        return list(db.scalars(stmt.offset(skip).limit(limit)).all())

    def update(
        self,
        db: Session,
        entity_id: UUID,
        data: PartUpdate,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> DBPart:
        """Update an existing part with proper authorization check."""
        entity = verify_entity_exists(db, self.model, entity_id, self.entity_name)
        require_part_edit_permission(current_user, entity)

        update_data = data.model_dump(exclude_unset=True)
        car_ids = update_data.pop("car_ids", None)
        if update_data.get("image_urls") is not None:
            update_data["image_urls"] = update_data["image_urls"][:MAX_IMAGES_PER_PART]
        if "gtin" in update_data and update_data["gtin"] is not None:
            update_data["gtin"] = normalize_gtin(update_data["gtin"])
        if car_ids is not None:
            is_universal_after = (
                update_data.get("is_universal") if "is_universal" in update_data else entity.is_universal
            )
            if not is_universal_after and car_ids:
                for cid in car_ids:
                    get_entity_or_404(db, DBCar, cid, "car")
                entity.car_generations = [db.get(DBCar, cid) for cid in car_ids]
            else:
                entity.car_generations = []
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
        entity_id: UUID,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> Dict[str, str]:
        """Delete an existing part with proper authorization check."""
        from app.api.utils.authorization import can_delete_part

        entity = verify_entity_exists(db, self.model, entity_id, self.entity_name)

        if not can_delete_part(current_user, entity):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail="Not authorized to delete this part. Only the creator or admin can delete parts.",
            )

        return delete_entity(
            db=db,
            entity=entity,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )


part_service = PartService()


@router.get(
    "/with-votes",
    response_model=Dict[str, Any],
    responses=pagination_responses("part", allow_public_read=True),
)
async def read_parts_with_votes(
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    category_id: Optional[UUID] = Query(None, description="Filter by category ID (single; use category_ids for multi)"),
    category_ids: Optional[List[UUID]] = Query(None, description="Filter by category IDs (parts matching any)"),
    car_id: Optional[UUID] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[UUID]] = Query(
        None, description="Filter by car IDs (e.g. all generations for a make or model)"
    ),
    part_manufacturer_id: Optional[UUID] = Query(
        None, description="Filter by part_manufacturer ID (single; use part_manufacturer_ids for multi)"
    ),
    part_manufacturer_ids: Optional[List[UUID]] = Query(
        None, description="Filter by part_manufacturer IDs (parts matching any)"
    ),
    retailer_id: Optional[UUID] = Query(None, description="Filter to parts that have a listing from this retailer"),
    user_id: Optional[UUID] = Query(None, description="Filter to parts created by this user (for 'My Parts' view)"),
    sort: Optional[str] = Query(
        None,
        description="Sort: votes_desc (default), votes_asc, lowest_price, highest_price, name_asc, name_desc, part_number_asc, part_number_desc, part_manufacturer_asc, part_manufacturer_desc, category_asc, category_desc",
    ),
    search: Optional[str] = Query(None, description="Search in part names and descriptions"),
    min_price_cents: Optional[int] = Query(None, ge=0, description="Filter to parts with best price >= this (cents)"),
    max_price_cents: Optional[int] = Query(None, ge=0, description="Filter to parts with best price <= this (cents)"),
    universal: Optional[bool] = Query(
        None, description="When true, return only parts that fit all cars (is_universal)"
    ),
    include_ugc: bool = Query(
        True,
        description=(
            "When false, hide community-contributed parts (source='user_created') "
            "from the catalog. Scraped parts are unaffected."
        ),
    ),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: Optional[DBUser] = Depends(get_optional_current_user),
) -> Dict[str, Any]:
    """Get all parts with vote data and optional filtering and search."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)
    effective_category_ids = category_ids if category_ids else ([category_id] if category_id is not None else None)
    effective_part_manufacturer_ids = (
        part_manufacturer_ids
        if part_manufacturer_ids
        else ([part_manufacturer_id] if part_manufacturer_id is not None else None)
    )
    effective_car_ids = car_ids if car_ids else ([car_id] if car_id is not None else None)
    has_price_filter = min_price_cents is not None or max_price_cents is not None

    upvote_counts = (
        select(
            DBVote.entity_id,
            func.count(DBVote.id).label("upvote_count"),
        )
        .where(
            DBVote.entity_type == "part",
            DBVote.vote_type == "upvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    downvote_counts = (
        select(
            DBVote.entity_id,
            func.count(DBVote.id).label("downvote_count"),
        )
        .where(
            DBVote.entity_type == "part",
            DBVote.vote_type == "downvote",
        )
        .group_by(DBVote.entity_id)
        .subquery()
    )

    base_stmt: Select[Any] = select(DBPart)
    base_stmt = _apply_parts_list_filters(
        base_stmt,
        effective_category_ids,
        effective_part_manufacturer_ids,
        effective_car_ids,
        search,
        user_id,
        retailer_id,
        universal=universal,
        include_ugc=include_ugc,
    )

    stmt: Select[Any] = (
        select(DBPart)
        .outerjoin(upvote_counts, DBPart.id == upvote_counts.c.entity_id)
        .outerjoin(downvote_counts, DBPart.id == downvote_counts.c.entity_id)
    )
    stmt = _apply_parts_list_filters(
        stmt,
        effective_category_ids,
        effective_part_manufacturer_ids,
        effective_car_ids,
        search,
        user_id,
        retailer_id,
        universal=universal,
        include_ugc=include_ugc,
    )

    # Aggregate listings to their canonical part: a duplicate's listings count
    # toward the canonical's best price. For a canonical (no canonical_part_id)
    # the grouping key is its own id, so this is a no-op there.
    min_price_subq = (
        select(
            func.coalesce(DBPart.canonical_part_id, DBPart.id).label("canonical_id"),
            func.min(DBPartListing.last_known_price_cents).label("min_price"),
        )
        .join(DBPart, DBPart.id == DBPartListing.part_id)
        .where(DBPartListing.last_known_price_cents.isnot(None))
        .group_by(func.coalesce(DBPart.canonical_part_id, DBPart.id))
        .subquery()
    )

    if has_price_filter:
        base_stmt = base_stmt.join(min_price_subq, DBPart.id == min_price_subq.c.canonical_id)
        if min_price_cents is not None:
            base_stmt = base_stmt.where(min_price_subq.c.min_price >= min_price_cents)
        if max_price_cents is not None:
            base_stmt = base_stmt.where(min_price_subq.c.min_price <= max_price_cents)
        stmt = stmt.join(min_price_subq, DBPart.id == min_price_subq.c.canonical_id)
        if min_price_cents is not None:
            stmt = stmt.where(min_price_subq.c.min_price >= min_price_cents)
        if max_price_cents is not None:
            stmt = stmt.where(min_price_subq.c.min_price <= max_price_cents)

    total = db.scalar(select(func.count()).select_from(base_stmt.subquery())) or 0

    net_votes = func.coalesce(upvote_counts.c.upvote_count, 0) - func.coalesce(downvote_counts.c.downvote_count, 0)

    if sort == "lowest_price":
        if not has_price_filter:
            stmt = stmt.outerjoin(min_price_subq, DBPart.id == min_price_subq.c.canonical_id)
        stmt = stmt.order_by(
            min_price_subq.c.min_price.asc().nullslast(),
            DBPart.id.desc(),
        )
    elif sort == "highest_price":
        if not has_price_filter:
            stmt = stmt.outerjoin(min_price_subq, DBPart.id == min_price_subq.c.canonical_id)
        stmt = stmt.order_by(
            min_price_subq.c.min_price.desc().nullslast(),
            DBPart.id.desc(),
        )
    elif sort == "votes_asc":
        stmt = stmt.order_by(net_votes.asc(), DBPart.id.desc())
    elif sort == "name_asc":
        stmt = stmt.order_by(DBPart.name.asc().nullslast(), DBPart.id.desc())
    elif sort == "name_desc":
        stmt = stmt.order_by(DBPart.name.desc().nullslast(), DBPart.id.desc())
    elif sort == "part_number_asc":
        stmt = stmt.order_by(DBPart.part_number.asc().nullslast(), DBPart.id.desc())
    elif sort == "part_number_desc":
        stmt = stmt.order_by(DBPart.part_number.desc().nullslast(), DBPart.id.desc())
    elif sort == "part_manufacturer_asc":
        stmt = stmt.outerjoin(DBPartManufacturer, DBPart.part_manufacturer_id == DBPartManufacturer.id).order_by(
            DBPartManufacturer.name.asc().nullslast(), DBPart.id.desc()
        )
    elif sort == "part_manufacturer_desc":
        stmt = stmt.outerjoin(DBPartManufacturer, DBPart.part_manufacturer_id == DBPartManufacturer.id).order_by(
            DBPartManufacturer.name.desc().nullslast(), DBPart.id.desc()
        )
    elif sort == "category_asc":
        stmt = stmt.join(DBCategory, DBPart.category_id == DBCategory.id).order_by(
            func.coalesce(DBCategory.display_name, DBCategory.name).asc().nullslast(),
            DBPart.id.desc(),
        )
    elif sort == "category_desc":
        stmt = stmt.join(DBCategory, DBPart.category_id == DBCategory.id).order_by(
            func.coalesce(DBCategory.display_name, DBCategory.name).desc().nullslast(),
            DBPart.id.desc(),
        )
    else:
        stmt = stmt.order_by(net_votes.desc(), DBPart.id.desc())

    id_stmt = stmt.with_only_columns(DBPart.id)
    ordered_ids = list(db.scalars(id_stmt.offset(skip).limit(limit)).all())

    if not ordered_ids:
        parts = []
    else:
        parts = list(
            db.scalars(
                select(DBPart)
                .where(DBPart.id.in_(ordered_ids))
                .outerjoin(upvote_counts, DBPart.id == upvote_counts.c.entity_id)
                .outerjoin(downvote_counts, DBPart.id == downvote_counts.c.entity_id)
                .order_by(
                    (
                        func.coalesce(upvote_counts.c.upvote_count, 0)
                        - func.coalesce(downvote_counts.c.downvote_count, 0)
                    ).desc(),
                    DBPart.id.desc(),
                )
            ).all()
        )
        parts_dict = {part.id: part for part in parts}
        parts = [parts_dict[part_id] for part_id in ordered_ids if part_id in parts_dict]
    logger.info(f"Retrieved {len(parts)} parts (skip: {skip}, limit: {limit})")

    if not parts:
        return create_paginated_response(data=[], total=total, skip=skip, limit=limit, entity_name="parts")

    part_ids = [part.id for part in parts]

    vote_counts = db.execute(
        select(
            DBVote.entity_id,
            DBVote.vote_type,
            func.count(DBVote.id).label("count"),
        )
        .where(
            DBVote.entity_type == "part",
            DBVote.entity_id.in_(part_ids),
        )
        .group_by(DBVote.entity_id, DBVote.vote_type)
    ).all()

    upvotes_dict: Dict[UUID, int] = {}
    downvotes_dict: Dict[UUID, int] = {}
    for entity_id, vote_type, count in vote_counts:
        if vote_type == "upvote":
            upvotes_dict[entity_id] = count
        elif vote_type == "downvote":
            downvotes_dict[entity_id] = count

    # Best price per canonical: a duplicate's listings contribute to its canonical's
    # best price, so rows returned (canonicals only) see prices from the whole link group.
    canonical_id_expr = func.coalesce(DBPart.canonical_part_id, DBPart.id).label("canonical_id")
    min_prices = db.execute(
        select(
            canonical_id_expr,
            func.min(DBPartListing.last_known_price_cents).label("min_price"),
        )
        .join(DBPart, DBPart.id == DBPartListing.part_id)
        .where(
            canonical_id_expr.in_(part_ids),
            DBPartListing.last_known_price_cents.isnot(None),
        )
        .group_by(canonical_id_expr)
    ).all()
    best_price_cents_dict: Dict[UUID, int] = {p_id: int(mp) for p_id, mp in min_prices}

    user_votes_dict: Dict[UUID, str] = {}
    if current_user:
        user_votes = db.execute(
            select(DBVote.entity_id, DBVote.vote_type)
            .where(
                DBVote.entity_type == "part",
                DBVote.entity_id.in_(part_ids),
                DBVote.user_id == current_user.id,
            )
        ).all()
        user_votes_dict = {entity_id: vote_type for entity_id, vote_type in user_votes}

    parts_data: List[PartReadWithVotes] = []
    for part in parts:
        part_dict = PartRead.model_validate(part).model_dump()
        part_dict["best_price_cents"] = best_price_cents_dict.get(part.id)
        part_dict["upvotes"] = upvotes_dict.get(part.id, 0)
        part_dict["downvotes"] = downvotes_dict.get(part.id, 0)
        part_dict["total_votes"] = part_dict["upvotes"] + part_dict["downvotes"]
        part_dict["user_vote"] = user_votes_dict.get(part.id, None)
        part_with_votes = PartReadWithVotes(**part_dict)
        parts_data.append(part_with_votes)

    return create_paginated_response(
        data=cast(List[Any], parts_data), total=total, skip=skip, limit=limit, entity_name="parts"
    )


def _apply_parts_list_filters(
    query: Any,
    category_ids: Optional[List[UUID]],
    part_manufacturer_ids: Optional[List[UUID]],
    car_ids: Optional[List[UUID]],
    search: Optional[str],
    user_id: Optional[UUID],
    retailer_id: Optional[UUID],
    *,
    universal: Optional[bool] = None,
    include_ugc: bool = True,
):
    """Apply list filters to a query that has DBPart as root.

    Non-canonical parts (``canonical_part_id IS NOT NULL``) are filtered out of
    the public catalog by default so duplicates don't clutter results. The
    "My Parts" view (``user_id`` set) keeps non-canonicals visible so a user
    still sees every part they created, even those later linked as duplicates.

    ``include_ugc=False`` drops community-contributed parts (``source =
    "user_created"``) so users who want a cleaner, scraper-only catalog can
    toggle UGC out of browse/search. The "My Parts" view ignores this flag so
    a user always sees their own UGC.
    """
    query = apply_standard_filters(
        query=query,
        search=search,
        category_id=None,
        search_fields=["name", "description"],
    )
    if category_ids:
        query = query.where(DBPart.category_id.in_(category_ids))
    if part_manufacturer_ids:
        query = query.where(DBPart.part_manufacturer_id.in_(part_manufacturer_ids))
    if universal is True:
        query = query.where(DBPart.is_universal == True)  # noqa: E712
    elif car_ids:
        part_fits_any_car = exists().where((part_cars.c.part_id == DBPart.id) & (part_cars.c.car_id.in_(car_ids)))
        query = query.where(or_(DBPart.is_universal, part_fits_any_car))
    if user_id is not None:
        query = query.where(DBPart.user_id == user_id)
    else:
        query = query.where(DBPart.canonical_part_id.is_(None))
        if not include_ugc:
            query = query.where(DBPart.source != "user_created")
    if retailer_id is not None:
        query = query.join(DBPartListing).where(
            DBPartListing.part_id == DBPart.id,
            DBPartListing.retailer_id == retailer_id,
        )
    return query


def _parts_base_query(
    db: Session,
    category_ids: Optional[List[UUID]],
    part_manufacturer_ids: Optional[List[UUID]],
    car_ids: Optional[List[UUID]],
    search: Optional[str],
    user_id: Optional[UUID],
    retailer_id: Optional[UUID],
    *,
    universal: Optional[bool] = None,
    include_ugc: bool = True,
):
    """Build base select for parts list with filters applied (no pagination/sort)."""
    q: Select[Any] = select(DBPart)
    return _apply_parts_list_filters(
        q,
        category_ids,
        part_manufacturer_ids,
        car_ids,
        search,
        user_id,
        retailer_id,
        universal=universal,
        include_ugc=include_ugc,
    )


@router.get(
    "/filter-options",
    response_model=Dict[str, Any],
)
async def get_parts_filter_options(
    category_ids: Optional[List[UUID]] = Query(None, description="Filter by category IDs (parts matching any)"),
    part_manufacturer_ids: Optional[List[UUID]] = Query(
        None, description="Filter by part_manufacturer IDs (parts matching any)"
    ),
    car_id: Optional[UUID] = Query(None, description="Filter by car ID (single generation)"),
    car_ids: Optional[List[UUID]] = Query(
        None, description="Filter by car IDs (e.g. all generations for a make or model)"
    ),
    search: Optional[str] = Query(None, description="Search in names and descriptions"),
    user_id: Optional[UUID] = Query(None, description="Filter to parts created by this user (e.g. for My Parts)"),
    universal: Optional[bool] = Query(None, description="When true, scope to parts that fit all cars (is_universal)"),
    include_ugc: bool = Query(
        True,
        description="When false, hide community-contributed parts from the filter option computation.",
    ),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, Any]:
    """
    Return category_ids and part_manufacturer_ids that have at least one part matching the current filters.
    """
    db = deps["db"]
    effective_car_ids = car_ids if car_ids else ([car_id] if car_id is not None else None)
    q = _parts_base_query(
        db,
        category_ids=category_ids,
        part_manufacturer_ids=part_manufacturer_ids,
        car_ids=effective_car_ids,
        search=search,
        user_id=user_id,
        retailer_id=None,
        universal=universal,
        include_ugc=include_ugc,
    )
    available_categories = list(
        db.scalars(
            q.with_only_columns(DBPart.category_id)
            .distinct()
            .where(DBPart.category_id.isnot(None))
        ).all()
    )
    available_part_manufacturers = list(
        db.scalars(
            q.with_only_columns(DBPart.part_manufacturer_id)
            .distinct()
            .where(DBPart.part_manufacturer_id.isnot(None))
        ).all()
    )
    result: Dict[str, Any] = {
        "category_ids": available_categories,
        "part_manufacturer_ids": available_part_manufacturers,
    }

    has_scoping_filters = bool(category_ids or part_manufacturer_ids or (search and search.strip()))
    if has_scoping_filters:
        q_no_car = _parts_base_query(
            db,
            category_ids=category_ids,
            part_manufacturer_ids=part_manufacturer_ids,
            car_ids=None,
            search=search,
            user_id=user_id,
            retailer_id=None,
            universal=universal,
            include_ugc=include_ugc,
        )
        available_car_ids = list(
            db.scalars(
                q_no_car.join(part_cars, DBPart.id == part_cars.c.part_id)
                .with_only_columns(part_cars.c.car_id)
                .distinct()
            ).all()
        )
        result["car_ids"] = available_car_ids
        if available_car_ids:
            make_rows = db.scalars(
                select(DBMake.name)
                .join(DBCarModel, DBCarModel.car_make_id == DBMake.id)
                .join(DBCar, DBCar.car_model_id == DBCarModel.id)
                .where(DBCar.id.in_(available_car_ids))
                .distinct()
            ).all()
            result["make_names"] = sorted({name for name in make_rows if name})
        else:
            result["make_names"] = []

    return result


@router.get(
    "/category/{category_id}",
    response_model=List[PartRead],
    responses=pagination_responses("part", allow_public_read=True),
)
async def get_parts_by_category(
    category_id: UUID,
    skip: int = Query(0, ge=0, description="Number of parts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of parts to return"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartRead]:
    """Get parts by category with pagination."""
    db = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    parts = list(
        db.scalars(
            select(DBPart)
            .where(
                DBPart.category_id == category_id,
                DBPart.canonical_part_id.is_(None),
            )
            .offset(skip)
            .limit(limit)
        ).all()
    )
    logger.info(f"Retrieved {len(parts)} parts for category {category_id}")
    return [PartRead.model_validate(part) for part in parts]


@router.get(
    "/check-url",
    response_model=Dict[str, Optional[UUID]],
    responses=standard_responses(success_description="URL check completed"),
)
async def check_product_url_exists(
    product_url: Optional[str] = Query(None, description="Product URL to check"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, Optional[UUID]]:
    """Check if a product URL already exists in the parts catalog."""
    db = deps["db"]
    logger = deps["logger"]

    try:
        if not product_url or not product_url.strip():
            return {"existing_part_id": None}

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
        return {"existing_part_id": None}


@router.get(
    "/find-by-part-manufacturer-and-part-number",
    response_model=PartRead,
    responses=standard_responses(success_description="Existing part found", not_found=True),
)
async def find_part_by_part_manufacturer_and_part_number_endpoint(
    part_manufacturer_id: UUID = Query(..., description="PartManufacturer ID"),
    part_number: str = Query(..., min_length=1, description="Part number or SKU"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartRead:
    """Find an existing part by part manufacturer and part number (normalized). Returns 404 if not found."""
    db = deps["db"]
    part = find_part_by_part_manufacturer_and_part_number(db, part_manufacturer_id, part_number)
    if not part:
        raise HTTPException(status_code=404, detail="No part found for this part manufacturer and part number")
    return PartRead.model_validate(part)


@router.get(
    "/{part_id}/listings",
    response_model=List[PartListingReadWithRetailer],
    responses=standard_responses(success_description="Part listings retrieved", not_found=True),
)
async def get_part_listings(
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartListingReadWithRetailer]:
    """List all retailer listings for a part (with current price)."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBPart, part_id, "part")
    group_ids = link_group_part_ids(db, part_id)
    listings = list(
        db.scalars(
            select(DBPartListing)
            .where(DBPartListing.part_id.in_(group_ids))
            .options(joinedload(DBPartListing.retailer))
        ).all()
    )
    return [PartListingReadWithRetailer.model_validate(l) for l in listings]


@router.post(
    "/{part_id}/listings",
    response_model=PartListingReadWithRetailer,
    responses=standard_responses(success_description="Part listing created or updated", not_found=True),
)
async def create_or_update_part_listing(
    part_id: UUID,
    data: PartListingCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartListingReadWithRetailer:
    """Create or update a retailer listing for a part (and optionally add a price)."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBPart, part_id, "part")
    _ = get_entity_or_404(db, DBRetailer, data.retailer_id, "retailer")
    if data.part_id != part_id:
        ResponsePatterns.raise_conflict(
            message="Body part_id must match path part_id.",
            error_code="PART_ID_MISMATCH",
        )
    listing = create_or_update_listing_and_price(
        db,
        part_id,
        data.retailer_id,
        product_url=data.product_url,
        price_cents=data.price_cents,
    )
    db.commit()
    db.refresh(listing)
    listing_with_retailer = db.scalars(
        select(DBPartListing)
        .where(DBPartListing.id == listing.id)
        .options(joinedload(DBPartListing.retailer))
    ).first()
    return PartListingReadWithRetailer.model_validate(listing_with_retailer)


@router.post(
    "/{part_id}/append-images",
    response_model=PartRead,
    responses=standard_responses(success_description="Images appended to part", not_found=True),
)
async def append_images_to_part(
    part_id: UUID,
    data: PartAppendImages,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartRead:
    """Append image file keys to a part's gallery."""
    db = deps["db"]
    part = get_entity_or_404(db, DBPart, part_id, "part")
    require_part_edit_permission(current_user, part)

    existing = list(part.image_urls or [])
    if len(existing) >= MAX_IMAGES_PER_PART:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Part already has the maximum number of images ({MAX_IMAGES_PER_PART}).",
        )

    seen = set(existing)
    for fk in data.file_keys:
        if fk and fk not in seen and len(existing) < MAX_IMAGES_PER_PART:
            existing.append(fk)
            seen.add(fk)

    part.image_urls = existing[:MAX_IMAGES_PER_PART]
    db.commit()
    db.refresh(part)
    return PartRead.model_validate(part)


def _get_part_image_file_keys(part: DBPart) -> List[str]:
    """Return ordered list of image file keys. First entry is the primary/display image."""
    return list(part.image_urls or [])


@router.delete(
    "/{part_id}/images/{image_index}",
    response_model=PartRead,
    responses=standard_responses(success_description="Image removed from part", not_found=True),
)
async def remove_image_from_part(
    part_id: UUID,
    image_index: int,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartRead:
    """Remove the image at the given index from the part's gallery."""
    from app.api.services.storage_service import storage_service
    from app.api.utils.image_utils import is_file_key

    db = deps["db"]
    part = get_entity_or_404(db, DBPart, part_id, "part")
    require_part_edit_permission(current_user, part)

    file_keys = _get_part_image_file_keys(part)
    if image_index < 0 or image_index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {image_index}. Part has {len(file_keys)} image(s).",
        )

    removed_key = file_keys[image_index]
    new_keys = [fk for i, fk in enumerate(file_keys) if i != image_index]

    part.image_urls = new_keys if new_keys else None

    if removed_key and is_file_key(removed_key):
        try:
            storage_service.delete_image(removed_key)
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Failed to delete image from storage for part %s: %s",
                part_id,
                e,
            )

    db.commit()
    db.refresh(part)
    return PartRead.model_validate(part)


@router.patch(
    "/{part_id}/primary-image",
    response_model=PartRead,
    responses=standard_responses(success_description="Primary image updated", not_found=True),
)
async def set_primary_image_for_part(
    part_id: UUID,
    data: SetPrimaryImageRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> PartRead:
    """Set the image at the given index as the primary (display) image."""
    db = deps["db"]
    part = get_entity_or_404(db, DBPart, part_id, "part")
    require_part_edit_permission(current_user, part)

    file_keys = _get_part_image_file_keys(part)
    if data.index < 0 or data.index >= len(file_keys):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image index {data.index}. Part has {len(file_keys)} image(s).",
        )

    primary_key = file_keys[data.index]
    new_order = [primary_key] + [fk for i, fk in enumerate(file_keys) if i != data.index]
    part.image_urls = new_order
    db.commit()
    db.refresh(part)
    return PartRead.model_validate(part)


@router.get(
    "/{part_id}/best-listing",
    response_model=PartListingReadWithRetailer,
    responses=standard_responses(success_description="Best (lowest price) listing retrieved", not_found=True),
)
async def get_part_best_listing(
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartListingReadWithRetailer:
    """Get the listing with the lowest current price for this part (across its link group)."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBPart, part_id, "part")
    group_ids = link_group_part_ids(db, part_id)
    best = db.scalars(
        select(DBPartListing)
        .where(
            DBPartListing.part_id.in_(group_ids),
            DBPartListing.last_known_price_cents.isnot(None),
            DBPartListing.last_known_price_cents >= 0,
        )
        .order_by(DBPartListing.last_known_price_cents.asc())
        .options(joinedload(DBPartListing.retailer))
    ).first()
    if not best:
        ResponsePatterns.raise_http_exception(
            status.HTTP_404_NOT_FOUND,
            "No listing with price for this part",
            error_code="NOT_FOUND",
        )
    return PartListingReadWithRetailer.model_validate(best)


@router.get(
    "/{part_id}/with-listings",
    response_model=PartReadWithListings,
    responses=standard_responses(success_description="Part with listings and best listing retrieved", not_found=True),
)
async def get_part_with_listings(
    part_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> PartReadWithListings:
    """Get a part with all retailer listings (aggregated across the link group) and best price."""
    db = deps["db"]
    part = get_entity_or_404(db, DBPart, part_id, "part")
    group_ids = link_group_part_ids(db, part_id)
    listings = list(
        db.scalars(
            select(DBPartListing)
            .where(DBPartListing.part_id.in_(group_ids))
            .options(joinedload(DBPartListing.retailer))
        ).all()
    )
    priced = [l for l in listings if l.last_known_price_cents is not None and l.last_known_price_cents >= 0]
    best_listing = min(priced, key=lambda l: l.last_known_price_cents or 0) if priced else None
    best_serialized = PartListingReadWithRetailer.model_validate(best_listing) if best_listing else None
    part_dict = PartRead.model_validate(part).model_dump()
    part_dict["best_price_cents"] = best_listing.last_known_price_cents if best_listing else None
    return PartReadWithListings(
        **part_dict,
        listings=[PartListingReadWithRetailer.model_validate(l) for l in listings],
        best_listing=best_serialized,
    )


@router.get(
    "/{part_id}/price-history",
    response_model=List[PartPriceHistoryReadWithRetailer],
    responses=standard_responses(success_description="Price history retrieved", not_found=True),
)
async def get_part_price_history(
    part_id: UUID,
    retailer_id: Optional[UUID] = Query(None, description="Filter by retailer ID"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[PartPriceHistoryReadWithRetailer]:
    """Get price history for this part (aggregated across its link group)."""
    db = deps["db"]
    _ = get_entity_or_404(db, DBPart, part_id, "part")
    group_ids = link_group_part_ids(db, part_id)
    stmt = (
        select(DBPartPriceHistory, DBPartListing, DBRetailer)
        .join(DBPartListing, DBPartPriceHistory.part_listing_id == DBPartListing.id)
        .join(DBRetailer, DBPartListing.retailer_id == DBRetailer.id)
        .where(DBPartListing.part_id.in_(group_ids))
    )
    if retailer_id is not None:
        stmt = stmt.where(DBPartListing.retailer_id == retailer_id)
    rows = db.execute(stmt.order_by(DBPartPriceHistory.observed_at.desc())).all()
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
    service=part_service,
    router=router,
    entity_name="part",
    allow_public_read=True,
    additional_create_data={},
    create_schema=PartCreate,
    read_schema=PartRead,
    update_schema=PartUpdate,
    search_fields=["name", "description", "category"],
)


@router.get(
    "/user/{user_id}/count",
    response_model=dict,
    responses=standard_responses(success_description="Count of parts for user", not_found=True),
)
async def count_parts_by_user(
    user_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, int]:
    """Count parts created by a specific user."""
    count = deps["db"].scalar(
        select(func.count()).select_from(DBPart).where(DBPart.user_id == user_id)
    ) or 0
    return {"count": count}


base_router.add_filter_endpoint("category", "category_id")
base_router.add_count_endpoint()
