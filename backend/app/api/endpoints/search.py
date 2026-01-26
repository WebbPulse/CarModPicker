"""
Search endpoint that searches across multiple entity types.

This endpoint provides unified search functionality across:
- Build lists (name, description, and associated car make/model/generation/year range)
- User profiles (username, email)
- Global parts (name, description, brand name, part_number)
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, joinedload

from app.api.models.brand import Brand as DBBrand
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.schemas.build_list import BuildListRead
from app.api.schemas.global_part import GlobalPartRead
from app.api.schemas.user import PublicUserRead
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_standard_public_endpoint_dependencies,
    validate_pagination_params,
)
from app.api.utils.endpoint_decorators import search_responses
from app.api.utils.pagination_utils import get_total_count

# Create router
router = APIRouter()


@router.get(
    "/",
    response_model=Dict[str, Any],
    responses=search_responses("entities", allow_public_read=True),
)
async def search_all(
    q: str = Query(..., description="Search term to search across all entities"),
    skip: int = Query(0, ge=0, description="Number of results to skip per category"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return per category"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> Dict[str, Any]:
    """
    Search across build lists, user profiles, and global parts.
    Returns results separated by entity type.
    """
    db: Session = deps["db"]
    logger = deps["logger"]

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    if not q or not q.strip():
        logger.warning("Empty search query provided")
        return {
            "build_lists": {
                "data": [],
                "total": 0,
                "has_next": False,
                "skip": skip,
                "limit": limit,
            },
            "users": {
                "data": [],
                "total": 0,
                "has_next": False,
                "skip": skip,
                "limit": limit,
            },
            "global_parts": {
                "data": [],
                "total": 0,
                "has_next": False,
                "skip": skip,
                "limit": limit,
            },
            "query": q or "",
        }

    search_term = q.strip()

    # Search build lists (name, description, and associated car make/model/generation/year range)
    build_list_query = (
        db.query(DBBuildList)
        .outerjoin(DBCar, DBBuildList.car_id == DBCar.id)
        .filter(
            or_(
                DBBuildList.name.ilike(f"%{search_term}%"),
                DBBuildList.description.ilike(f"%{search_term}%"),
                DBCar.make.ilike(f"%{search_term}%"),
                DBCar.model.ilike(f"%{search_term}%"),
                DBCar.generation_name.ilike(f"%{search_term}%"),
                # Search years as strings to match partial year searches
                cast(DBCar.start_year, String).ilike(f"%{search_term}%"),
                cast(DBCar.end_year, String).ilike(f"%{search_term}%"),
            )
        )
        .options(joinedload(DBBuildList.car))
    )
    build_list_total = get_total_count(build_list_query)
    build_lists = build_list_query.offset(skip).limit(limit).all()
    build_list_results = [BuildListRead.model_validate(bl) for bl in build_lists]
    build_list_has_next = (skip + limit) < build_list_total

    # Search users (username, email)
    user_query = db.query(DBUser).filter(
        or_(
            DBUser.username.ilike(f"%{search_term}%"),
            DBUser.email.ilike(f"%{search_term}%"),
        )
    )
    user_total = get_total_count(user_query)
    users = user_query.offset(skip).limit(limit).all()
    # Use PublicUserRead to exclude sensitive fields (email_verified, totp_enabled)
    user_results = [PublicUserRead.model_validate(u) for u in users]
    user_has_next = (skip + limit) < user_total

    # Search global parts (name, description, brand name, part_number)
    global_part_query = (
        db.query(DBGlobalPart)
        .outerjoin(DBBrand, DBGlobalPart.brand_id == DBBrand.id)
        .filter(
            or_(
                DBGlobalPart.name.ilike(f"%{search_term}%"),
                DBGlobalPart.description.ilike(f"%{search_term}%"),
                DBBrand.name.ilike(f"%{search_term}%"),
                DBBrand.description.ilike(f"%{search_term}%"),
                DBGlobalPart.part_number.ilike(f"%{search_term}%"),
            )
        )
        .options(joinedload(DBGlobalPart.brand))
    )
    global_part_total = get_total_count(global_part_query)
    global_parts = global_part_query.offset(skip).limit(limit).all()
    global_part_results = [GlobalPartRead.model_validate(gp) for gp in global_parts]
    global_part_has_next = (skip + limit) < global_part_total

    logger.info(
        f"Search for '{search_term}' returned {len(build_list_results)}/{build_list_total} build lists, "
        f"{len(user_results)}/{user_total} users, and {len(global_part_results)}/{global_part_total} global parts"
    )

    return {
        "build_lists": {
            "data": build_list_results,
            "total": build_list_total,
            "has_next": build_list_has_next,
            "skip": skip,
            "limit": limit,
        },
        "users": {
            "data": user_results,
            "total": user_total,
            "has_next": user_has_next,
            "skip": skip,
            "limit": limit,
        },
        "global_parts": {
            "data": global_part_results,
            "total": global_part_total,
            "has_next": global_part_has_next,
            "skip": skip,
            "limit": limit,
        },
        "query": search_term,
    }
