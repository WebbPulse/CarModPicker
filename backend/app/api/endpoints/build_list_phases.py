"""
Build list phase endpoints: update and delete phases by ID.
List and create are under build_lists (GET/POST /build-lists/{id}/phases).
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_part import BuildListPart as DBBuildListPart
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.models.user import User as DBUser
from app.api.schemas.build_list_phase import BuildListPhaseRead, BuildListPhaseUpdate
from app.api.utils.common_patterns import (
    PublicEndpointDeps,
    get_entity_or_404,
    get_standard_public_endpoint_dependencies,
    verify_user_access_or_admin,
)
from app.api.utils.endpoint_decorators import standard_responses

router = APIRouter()


@router.get(
    "/count",
    response_model=dict,
    responses=standard_responses(success_description="Build list phase count retrieved successfully"),
)
async def count_build_list_phases(
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
) -> dict:
    """Total count of build list phases (public read, same pattern as other /count endpoints)."""
    db = deps["db"]
    logger = deps["logger"]
    count = db.query(DBBuildListPhase).count()
    logger.info(f"Retrieved build list phases count: {count}")
    return {"count": count}


@router.put(
    "/{phase_id}",
    response_model=BuildListPhaseRead,
    responses=standard_responses(
        success_description="Build list phase updated successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def update_build_list_phase(
    phase_id: UUID,
    body: BuildListPhaseUpdate,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPhaseRead:
    """Update a build list phase. Only build list owner or admin."""
    db = deps["db"]
    logger = deps["logger"]

    db_phase = get_entity_or_404(db, DBBuildListPhase, phase_id, "build list phase")
    db_build_list = get_entity_or_404(db, DBBuildList, db_phase.build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_phase, key, value)

    db.add(db_phase)
    db.commit()
    db.refresh(db_phase)

    logger.info(f"Build list phase {phase_id} updated by user {current_user.id}")
    return BuildListPhaseRead.model_validate(db_phase)


@router.delete(
    "/{phase_id}",
    response_model=BuildListPhaseRead,
    responses=standard_responses(
        success_description="Build list phase deleted successfully",
        not_found=True,
        forbidden=True,
    ),
)
async def delete_build_list_phase(
    phase_id: UUID,
    deps: PublicEndpointDeps = Depends(get_standard_public_endpoint_dependencies),
    current_user: DBUser = Depends(get_current_user),
) -> BuildListPhaseRead:
    """Delete a build list phase. Parts in this phase are unassigned (build_list_phase_id set to NULL)."""
    db = deps["db"]
    logger = deps["logger"]

    db_phase = get_entity_or_404(db, DBBuildListPhase, phase_id, "build list phase")
    db_build_list = get_entity_or_404(db, DBBuildList, db_phase.build_list_id, "build list")
    verify_user_access_or_admin(current_user, db_build_list.user_id, "modify this build list", logger)

    # Unassign parts from this phase
    db.query(DBBuildListPart).filter(DBBuildListPart.build_list_phase_id == phase_id).update(
        {DBBuildListPart.build_list_phase_id: None}
    )

    deleted_data = BuildListPhaseRead.model_validate(db_phase)
    db.delete(db_phase)
    db.commit()

    logger.info(f"Build list phase {phase_id} deleted by user {current_user.id}")
    return deleted_data
