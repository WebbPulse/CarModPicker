"""Admin canonical-parts management: lookup, link-group, promote, unlink, link, rescan."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.user import User as DBUser
from app.api.services.part_linker_service import (
    _point_siblings_at,  # type: ignore[attr-defined]
    find_canonical_candidates,
    link_group_part_ids,
    reelect_canonical,
    score_metadata_richness,
    unlink_part,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


class CanonicalLinkGroupMember(BaseModel):
    """A part in a canonical link group, with richness score for admin inspection."""

    id: UUID
    name: str
    source: str
    is_canonical: bool
    richness_score: int = Field(..., description="Linker election score; higher wins when picking a canonical.")
    image_url: Optional[str] = Field(None, description="First image file key, if any.")
    product_url: Optional[str] = Field(
        None, description="Product URL at the member's retailer (from the first PartListing)."
    )
    retailer_id: Optional[UUID] = Field(None, description="Retailer of the member's first PartListing.")
    created_at: datetime


class CanonicalLinkGroupResponse(BaseModel):
    canonical_id: UUID
    members: List[CanonicalLinkGroupMember]


class UrlLookupMatch(BaseModel):
    """A Part whose first PartListing's product_url matches a lookup URL."""

    part_id: UUID
    name: str
    source: str
    is_canonical: bool = Field(..., description="True when this part has no canonical_part_id set.")
    canonical_id: UUID = Field(..., description="Canonical of this part's link group (self if canonical).")
    retailer_id: Optional[UUID] = None


class UrlLookupResponse(BaseModel):
    normalized_url: str
    matches: List[UrlLookupMatch] = Field(
        ...,
        description=(
            "All parts with a PartListing at this URL. Non-UGC parts are unique on URL, "
            "but UGC rows intentionally may share a URL so multiple matches are possible."
        ),
    )


class PromoteCanonicalRequest(BaseModel):
    part_id: UUID = Field(..., description="Part to promote to canonical of its link group.")


class UnlinkPartRequest(BaseModel):
    part_id: UUID = Field(..., description="Part to detach from its current link group.")


class ManualLinkRequest(BaseModel):
    duplicate_id: UUID = Field(..., description="Part that should become a duplicate.")
    canonical_id: UUID = Field(..., description="Canonical the duplicate should point at.")


class RescanRequest(BaseModel):
    dry_run: bool = Field(True, description="When true, return a diff without mutating.")
    batch_size: int = Field(500, ge=1, le=5000, description="Parts per commit batch (execute mode only).")


class RescanDiffEntry(BaseModel):
    part_id: UUID
    before_canonical_id: Optional[UUID]
    after_canonical_id: Optional[UUID]
    action: str = Field(..., description="link | reelect | unchanged")


class RescanResponse(BaseModel):
    dry_run: bool
    scanned: int
    changes: int
    diff_sample: List[RescanDiffEntry] = Field(
        ..., description="First N entries of the diff. Capped so the response stays small."
    )
    diff_truncated: bool


def _first_listing_for(db: Session, part_id: UUID) -> Optional[DBPartListing]:
    return db.scalars(
        select(DBPartListing)
        .where(DBPartListing.part_id == part_id)
        .order_by(DBPartListing.created_at.asc())
    ).first()


def _link_group_member(db: Session, part: DBPart, canonical_id: UUID) -> CanonicalLinkGroupMember:
    listing = _first_listing_for(db, part.id)
    first_image = part.image_urls[0] if part.image_urls else None
    return CanonicalLinkGroupMember(
        id=part.id,
        name=part.name,
        source=part.source,
        is_canonical=(part.id == canonical_id),
        richness_score=score_metadata_richness(part),
        image_url=first_image,
        product_url=listing.product_url if listing else None,
        retailer_id=listing.retailer_id if listing else None,
        created_at=part.created_at,
    )


@router.get(
    "/lookup-by-url",
    response_model=UrlLookupResponse,
    responses=standard_responses(success_description="Parts matching URL", forbidden=True),
)
async def lookup_parts_by_product_url(
    url: str = Query(
        ..., min_length=1, description="Product URL to look up (matched against PartListing.product_url)."
    ),
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> UrlLookupResponse:
    """Return every Part (canonical or duplicate, catalog or UGC) whose PartListing has this product_url."""
    _ = current_user
    normalized = url.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL is required")

    listings = list(db.scalars(
        select(DBPartListing)
        .join(DBPart, DBPart.id == DBPartListing.part_id)
        .where(DBPartListing.product_url == normalized)
        .order_by(DBPart.source.asc(), DBPart.created_at.asc())
    ).all())

    matches: List[UrlLookupMatch] = []
    for listing in listings:
        part = listing.part
        canonical_id = part.canonical_part_id or part.id
        matches.append(
            UrlLookupMatch(
                part_id=part.id,
                name=part.name,
                source=part.source,
                is_canonical=part.canonical_part_id is None,
                canonical_id=canonical_id,
                retailer_id=listing.retailer_id,
            )
        )

    return UrlLookupResponse(normalized_url=normalized, matches=matches)


@router.get(
    "/{part_id}/link-group",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(success_description="Link group retrieved", not_found=True, forbidden=True),
)
async def get_part_link_group(
    part_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Return every part in the same link group as ``part_id``, with richness scores."""
    _ = current_user
    root = db.get(DBPart, part_id)
    if root is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    canonical_id = root.canonical_part_id or root.id
    member_ids = link_group_part_ids(db, part_id)
    parts = list(db.scalars(select(DBPart).where(DBPart.id.in_(member_ids))).all())

    # Canonical first, then siblings by richness desc, created_at asc.
    def sort_key(p: DBPart) -> tuple[int, int, float]:
        return (
            0 if p.id == canonical_id else 1,
            -score_metadata_richness(p),
            p.created_at.timestamp() if p.created_at else 0.0,
        )

    parts.sort(key=sort_key)
    return CanonicalLinkGroupResponse(
        canonical_id=canonical_id,
        members=[_link_group_member(db, p, canonical_id) for p in parts],
    )


@router.post(
    "/promote-canonical",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(success_description="Canonical re-elected", not_found=True, forbidden=True),
)
async def promote_part_to_canonical(
    body: PromoteCanonicalRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Make ``body.part_id`` the canonical of its link group. Safe on already-canonical parts."""
    part = db.get(DBPart, body.part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    reelect_canonical(db, part)
    db.commit()
    logger.info("Admin %s promoted part %s to canonical", current_user.id, body.part_id)
    return await get_part_link_group(body.part_id, current_user=current_user, db=db)


@router.post(
    "/unlink",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(success_description="Part unlinked", not_found=True, forbidden=True),
)
async def unlink_part_from_canonical(
    body: UnlinkPartRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Detach ``body.part_id`` from its current link group so it becomes its own canonical."""
    part = db.get(DBPart, body.part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    unlink_part(db, part)
    db.commit()
    logger.info("Admin %s unlinked part %s", current_user.id, body.part_id)
    return await get_part_link_group(body.part_id, current_user=current_user, db=db)


@router.post(
    "/link",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(
        success_description="Part linked as duplicate", not_found=True, forbidden=True, conflict=True
    ),
)
async def manually_link_parts(
    body: ManualLinkRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Link ``duplicate_id`` under ``canonical_id``. The target must itself be a canonical."""
    if body.duplicate_id == body.canonical_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A part cannot be a duplicate of itself")

    duplicate = db.get(DBPart, body.duplicate_id)
    canonical = db.get(DBPart, body.canonical_id)
    if duplicate is None or canonical is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    if canonical.canonical_part_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Target is itself a duplicate. Promote it to canonical first.",
        )

    # If duplicate was canonical of other parts, repoint them to the new canonical first.
    _point_siblings_at(db, body.duplicate_id, body.canonical_id)
    duplicate.canonical_part_id = body.canonical_id
    db.add(duplicate)
    db.commit()
    logger.info(
        "Admin %s manually linked part %s as duplicate of %s",
        current_user.id,
        body.duplicate_id,
        body.canonical_id,
    )
    return await get_part_link_group(body.canonical_id, current_user=current_user, db=db)


_RESCAN_DIFF_SAMPLE_CAP = 200


@router.post(
    "/rescan",
    response_model=RescanResponse,
    responses=standard_responses(success_description="Rescan completed", forbidden=True),
)
async def rescan_parts_for_canonical_linking(
    body: RescanRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> RescanResponse:
    """
    Re-evaluate canonical linking across the parts catalog under the current dedup rules.

    ``dry_run=True`` (default) returns a diff without writing. ``dry_run=False`` applies
    the same operations in per-batch commits. The job can both create new links and
    re-elect within existing groups; it does not unlink parts that no longer match
    (that's an explicit admin action).
    """
    scanned = 0
    changes = 0
    diff_sample: List[RescanDiffEntry] = []

    def _record(entry: RescanDiffEntry) -> None:
        if len(diff_sample) < _RESCAN_DIFF_SAMPLE_CAP:
            diff_sample.append(entry)

    offset = 0
    batch_size = body.batch_size
    while True:
        batch = list(
            db.scalars(
                select(DBPart)
                .order_by(DBPart.created_at.asc(), DBPart.id.asc())
                .offset(offset)
                .limit(batch_size)
            ).all()
        )
        if not batch:
            break
        offset += len(batch)
        for part in batch:
            scanned += 1
            listing = _first_listing_for(db, part.id)
            candidates = find_canonical_candidates(
                db,
                gtin=part.gtin,
                product_url=listing.product_url if listing else None,
                part_manufacturer_id=part.part_manufacturer_id,
                part_number=part.part_number,
                exclude_part_id=part.id,
            )
            before = part.canonical_part_id
            after = before
            action = "unchanged"

            if candidates:
                all_candidates = [*candidates, part]
                chosen = max(
                    all_candidates,
                    key=lambda p: (
                        score_metadata_richness(p),
                        -(p.created_at.timestamp() if p.created_at else 0.0),
                    ),
                )
                if chosen.id == part.id:
                    # Part is richer than any matched canonical — it should be canonical itself.
                    after = None
                    if before != after:
                        action = "reelect" if before is not None else "unchanged"
                else:
                    after = chosen.id
                    if before != after:
                        action = "reelect" if before is not None else "link"

            if action != "unchanged" and not body.dry_run:
                # Apply: if promoting this part to canonical, repoint any siblings it had.
                if after is None and before is not None:
                    reelect_canonical(db, part)
                else:
                    part.canonical_part_id = after
                    db.add(part)

            if action != "unchanged":
                changes += 1
                _record(
                    RescanDiffEntry(
                        part_id=part.id, before_canonical_id=before, after_canonical_id=after, action=action
                    )
                )
        if not body.dry_run:
            db.commit()

    logger.info(
        "Admin %s rescan: scanned=%d changes=%d dry_run=%s",
        current_user.id,
        scanned,
        changes,
        body.dry_run,
    )
    return RescanResponse(
        dry_run=body.dry_run,
        scanned=scanned,
        changes=changes,
        diff_sample=diff_sample,
        diff_truncated=changes > len(diff_sample),
    )
