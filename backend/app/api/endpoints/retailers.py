"""
Retailers endpoint for managing part retailers (stores/sites).

Public read; admin-only create/update/delete.
Authenticated users can get-or-create by domain (for scrapers).
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.retailer import Retailer as DBRetailer
from app.api.models.user import User as DBUser
from app.api.schemas.retailer import RetailerCreate, RetailerRead, RetailerUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.api.services.part_listing_service import get_or_create_retailer
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    handle_integrity_error,
)
from app.api.utils.endpoint_decorators import crud_responses
from app.api.utils.response_patterns import ResponsePatterns


class RetailerService(BaseCRUDService[DBRetailer, RetailerCreate, RetailerRead, RetailerUpdate]):
    """Retailer service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBRetailer,
            entity_name="retailer",
        )

    def get_active_retailers(self, db: Session) -> List[DBRetailer]:
        """Get all active retailers ordered by name."""
        return list(db.scalars(select(DBRetailer).where(DBRetailer.is_active.is_(True)).order_by(DBRetailer.name)).all())


router = APIRouter()
retailer_service = RetailerService()

base_router = BaseEndpointRouter(
    service=retailer_service,
    router=router,
    entity_name="retailer",
    allow_public_read=True,
    additional_create_data={},
    disable_endpoints=["list", "get", "delete", "create", "update"],
    create_schema=RetailerCreate,
    read_schema=RetailerRead,
    update_schema=RetailerUpdate,
    search_fields=["name", "domain"],
)


@router.get("/", response_model=List[RetailerRead])
async def get_retailers(
    active_only: bool = Query(True, description="Only return active retailers"),
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> List[RetailerRead]:
    """Get all retailers (optionally filtered to active only)."""
    db = deps["db"]
    if active_only:
        retailers = retailer_service.get_active_retailers(db)
    else:
        retailers = list(db.scalars(select(DBRetailer).order_by(DBRetailer.name)).all())
    return [RetailerRead.model_validate(r) for r in retailers]


class RetailerGetOrCreateRequest(BaseModel):
    """Request body for get-or-create retailer by domain (scraper use)."""

    domain: str = Field(..., description="Domain e.g. a90shop.com")
    name: str | None = Field(None, description="Display name; derived from domain if omitted")
    base_url: str | None = Field(None, description="Base URL e.g. https://www.a90shop.com")


@router.post(
    "/get-or-create",
    response_model=RetailerRead,
)
async def get_or_create_retailer_by_domain(
    body: RetailerGetOrCreateRequest,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> RetailerRead:
    """
    Get existing retailer by domain or create one. For use by scrapers when
    adding parts from a retailer not yet in the catalog. Any authenticated user.
    """
    db = deps["db"]
    domain = body.domain.strip().lower()
    if not domain:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Domain is required")

    # Derive name from domain if not provided: "a90shop.com" -> "A90Shop"
    name = body.name.strip() if body.name else _domain_to_retailer_name(domain)

    retailer = get_or_create_retailer(
        db,
        name,
        domain=domain,
        base_url=body.base_url,
    )
    db.commit()
    db.refresh(retailer)
    return RetailerRead.model_validate(retailer)


def _domain_to_retailer_name(domain: str) -> str:
    """Convert domain to display name: a90shop.com -> A90Shop."""
    # Remove www. and TLD
    parts = domain.replace("www.", "").split(".")
    base = parts[0] if parts else domain
    if not base:
        return domain
    return base.title()


@router.get("/{retailer_id}", response_model=RetailerRead)
async def get_retailer(
    retailer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> RetailerRead:
    """Get a retailer by ID."""
    db = deps["db"]
    retailer = get_entity_or_404(db, DBRetailer, retailer_id, "retailer")
    return RetailerRead.model_validate(retailer)


@router.post(
    "/",
    response_model=RetailerRead,
    responses=crud_responses("retailer", "create"),
)
async def create_retailer(
    retailer: RetailerCreate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> RetailerRead:
    """Create a new retailer (admin only)."""
    db = deps["db"]
    if retailer.domain:
        existing = db.scalars(select(DBRetailer).where(DBRetailer.domain == retailer.domain)).first()
        if existing:
            ResponsePatterns.raise_conflict(
                f"A retailer with domain '{retailer.domain}' already exists",
                "DUPLICATE_RETAILER_DOMAIN",
                details={"existing_retailer_id": str(existing.id)},
            )
    db_retailer = DBRetailer(**retailer.model_dump())
    db.add(db_retailer)
    db.commit()
    db.refresh(db_retailer)
    return RetailerRead.model_validate(db_retailer)


@router.put(
    "/{retailer_id}",
    response_model=RetailerRead,
    responses=crud_responses("retailer", "update"),
)
async def update_retailer(
    retailer_id: UUID,
    retailer: RetailerUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> RetailerRead:
    """Update a retailer (admin only)."""
    db = deps["db"]
    db_retailer = get_entity_or_404(db, DBRetailer, retailer_id, "retailer")
    if retailer.domain is not None and retailer.domain != db_retailer.domain:
        existing = db.scalars(select(DBRetailer).where(DBRetailer.domain == retailer.domain)).first()
        if existing:
            ResponsePatterns.raise_conflict(
                f"A retailer with domain '{retailer.domain}' already exists",
                "DUPLICATE_RETAILER_DOMAIN",
                details={"existing_retailer_id": str(existing.id)},
            )
    update_data = retailer.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_retailer, field, value)
    try:
        db.add(db_retailer)
        db.commit()
        db.refresh(db_retailer)
        return RetailerRead.model_validate(db_retailer)
    except Exception as e:
        db.rollback()
        handle_integrity_error(e, "retailer")
        raise


@router.delete(
    "/{retailer_id}",
    response_model=RetailerRead,
    responses=crud_responses("retailer", "delete"),
)
async def delete_retailer(
    retailer_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_admin_user),
) -> RetailerRead:
    """Delete a retailer (admin only)."""
    db = deps["db"]
    db_retailer = get_entity_or_404(db, DBRetailer, retailer_id, "retailer")
    listings_count = db.scalar(select(func.count()).select_from(DBPartListing).where(DBPartListing.retailer_id == retailer_id)) or 0
    if listings_count > 0:
        ResponsePatterns.raise_conflict(
            f"Cannot delete retailer that has {listings_count} part listing(s)",
            "RETAILER_IN_USE",
        )
    response_data = RetailerRead.model_validate(db_retailer)
    db.delete(db_retailer)
    db.commit()
    return response_data
