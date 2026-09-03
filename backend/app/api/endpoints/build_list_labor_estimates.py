"""
Build list labor estimate endpoints: update and delete labor estimates by ID.
List and create are under build_lists (GET/POST /build-lists/{id}/labor-estimates).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_labor_estimate import BuildListLaborEstimate as DBBuildListLaborEstimate
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.schemas.build_list_labor_estimate import (
    BuildListLaborEstimateRead,
    BuildListLaborEstimateUpdate,
)
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.db.dynamo.users import User as DBUser

router = APIRouter()


def _validate_phase_belongs_to_build_list(
    db: Session,
    phase_id: UUID | None,
    build_list_id: UUID,
) -> None:
    """If a phase id is supplied, ensure it belongs to the given build list."""
    if phase_id is None:
        return
    phase = db.get(DBBuildListPhase, phase_id)
    if phase is None or phase.build_list_id != build_list_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phase does not belong to this build list",
        )


@router.get(
    "/count",
    response_model=dict,
    responses=standard_responses(success_description="Build list labor estimate count retrieved successfully"),
)
async def count_build_list_labor_estimates(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Total count of build list labor estimates (public read, same pattern as other /count endpoints)."""
    db = deps["db"]
    logger = deps["logger"]
    count = db.scalar(select(func.count()).select_from(DBBuildListLaborEstimate)) or 0
    logger.info(f"Retrieved build list labor estimates count: {count}")
    return {"count": count}


@router.put(
    "/{labor_estimate_id}",
    response_model=BuildListLaborEstimateRead,
    responses=standard_responses(
        success_description="Build list labor estimate updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_build_list_labor_estimate(
    labor_estimate_id: UUID,
    body: BuildListLaborEstimateUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListLaborEstimateRead:
    """Update a build list labor estimate. Only build list owner or admin."""
    db = deps["db"]
    logger = deps["logger"]

    db_estimate = get_entity_or_404(db, DBBuildListLaborEstimate, labor_estimate_id, "build list labor estimate")
    db_build_list = get_entity_or_404(db, DBBuildList, db_estimate.build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    update_data = body.model_dump(exclude_unset=True)
    if "build_list_phase_id" in update_data:
        _validate_phase_belongs_to_build_list(db, update_data["build_list_phase_id"], db_estimate.build_list_id)

    for key, value in update_data.items():
        setattr(db_estimate, key, value)

    db.add(db_estimate)
    db.commit()
    db.refresh(db_estimate)

    logger.info(f"Build list labor estimate {labor_estimate_id} updated by user {current_user.id}")
    return BuildListLaborEstimateRead.model_validate(db_estimate)


@router.delete(
    "/{labor_estimate_id}",
    response_model=BuildListLaborEstimateRead,
    responses=standard_responses(
        success_description="Build list labor estimate deleted successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def delete_build_list_labor_estimate(
    labor_estimate_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListLaborEstimateRead:
    """Delete a build list labor estimate. Only build list owner or admin."""
    db = deps["db"]
    logger = deps["logger"]

    db_estimate = get_entity_or_404(db, DBBuildListLaborEstimate, labor_estimate_id, "build list labor estimate")
    db_build_list = get_entity_or_404(db, DBBuildList, db_estimate.build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    deleted_data = BuildListLaborEstimateRead.model_validate(db_estimate)
    db.delete(db_estimate)
    db.commit()

    logger.info(f"Build list labor estimate {labor_estimate_id} deleted by user {current_user.id}")
    return deleted_data
