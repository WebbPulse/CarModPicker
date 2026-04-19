"""
Admin endpoints for managing user-defined crawler schedules.

The DB row (``crawler_schedules``) is the source of truth for each schedule's
name, cron expression, and member adapters. Reconciliation to EventBridge
Scheduler only fires when ``enabled`` or ``schedule_expression`` changes — the
Target.Input is ``{"schedule_id": "<uuid>"}``, so membership and adapter
config edits never require an AWS call.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.associations.crawler_schedule_adapter import CrawlerScheduleAdapter
from app.api.models.crawler_schedule import CrawlerSchedule
from app.api.models.user import User as DBUser
from app.api.schemas.crawler_schedule import (
    CrawlerScheduleCreate,
    CrawlerScheduleList,
    CrawlerScheduleRead,
    CrawlerScheduleUpdate,
    ReconcileAllResponse,
)
from app.api.services import crawler_schedule_service
from app.api.services.crawler_schedule_service import CRON_PRESETS
from app.api.utils.endpoint_decorators import standard_responses
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _validate_adapter_names(names: list[str]) -> None:
    unknown = [n for n in names if n not in ADAPTER_REGISTRY]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown adapter(s): {unknown}. Available: {list(ADAPTER_REGISTRY)}",
        )


def _requires_reconcile(*, enabled_changed: bool, expression_changed: bool, created: bool) -> bool:
    return created or enabled_changed or expression_changed


@router.get(
    "/",
    response_model=CrawlerScheduleList,
    responses=standard_responses(success_description="All crawler schedules", forbidden=True),
)
async def list_schedules(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CrawlerScheduleList:
    _ = current_user
    rows = db.query(CrawlerSchedule).order_by(CrawlerSchedule.name).all()
    return CrawlerScheduleList(
        items=[CrawlerScheduleRead.model_validate(r) for r in rows],
        presets=CRON_PRESETS,
    )


@router.post(
    "/",
    response_model=CrawlerScheduleRead,
    status_code=status.HTTP_201_CREATED,
    responses=standard_responses(
        success_description="Schedule created and reconciled",
        forbidden=True,
        validation_error=True,
        conflict=True,
    ),
)
async def create_schedule(
    body: CrawlerScheduleCreate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CrawlerScheduleRead:
    _ = current_user
    if db.query(CrawlerSchedule).filter(CrawlerSchedule.name == body.name).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Schedule '{body.name}' already exists.",
        )
    _validate_adapter_names(body.adapters)

    try:
        expression = crawler_schedule_service.resolve_preset_or_expression(
            preset=body.preset,
            expression=body.schedule_expression,
            current=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if expression is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One of 'schedule_expression' or 'preset' is required.",
        )

    row = CrawlerSchedule(
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        schedule_expression=expression,
    )
    for name in body.adapters:
        row.adapters.append(CrawlerScheduleAdapter(adapter_name=name))
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        await asyncio.to_thread(crawler_schedule_service.reconcile_schedule, db, row)
    except Exception as e:
        logger.warning("Reconcile failed for new schedule %s: %s", row.name, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Schedule '{row.name}' saved, but AWS reconcile failed: {e}",
        )

    db.refresh(row)
    return CrawlerScheduleRead.model_validate(row)


@router.get(
    "/{schedule_id}",
    response_model=CrawlerScheduleRead,
    responses=standard_responses(success_description="Schedule read", forbidden=True, not_found=True),
)
async def read_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CrawlerScheduleRead:
    _ = current_user
    row = db.query(CrawlerSchedule).filter(CrawlerSchedule.id == schedule_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule {schedule_id} not found")
    return CrawlerScheduleRead.model_validate(row)


@router.patch(
    "/{schedule_id}",
    response_model=CrawlerScheduleRead,
    responses=standard_responses(
        success_description="Schedule updated",
        forbidden=True,
        not_found=True,
        validation_error=True,
    ),
)
async def update_schedule(
    schedule_id: UUID,
    body: CrawlerScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CrawlerScheduleRead:
    _ = current_user
    row = db.query(CrawlerSchedule).filter(CrawlerSchedule.id == schedule_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule {schedule_id} not found")

    enabled_before = row.enabled
    expression_before = row.schedule_expression

    if body.description is not None:
        row.description = body.description
    if body.enabled is not None:
        row.enabled = body.enabled

    try:
        new_expression = crawler_schedule_service.resolve_preset_or_expression(
            preset=body.preset,
            expression=body.schedule_expression,
            current=row.schedule_expression,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if new_expression is not None:
        row.schedule_expression = new_expression

    if body.adapters is not None:
        _validate_adapter_names(body.adapters)
        # Replace membership: clear existing, add new.
        row.adapters.clear()
        db.flush()
        for name in body.adapters:
            row.adapters.append(CrawlerScheduleAdapter(adapter_name=name))

    db.add(row)
    db.commit()
    db.refresh(row)

    needs_reconcile = _requires_reconcile(
        enabled_changed=row.enabled != enabled_before,
        expression_changed=row.schedule_expression != expression_before,
        created=False,
    )
    if needs_reconcile:
        try:
            await asyncio.to_thread(crawler_schedule_service.reconcile_schedule, db, row)
        except Exception as e:
            logger.warning("Reconcile failed for schedule %s: %s", row.name, e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Schedule '{row.name}' saved, but AWS reconcile failed: {e}",
            )
        db.refresh(row)
    return CrawlerScheduleRead.model_validate(row)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=standard_responses(
        success_description="Schedule deleted",
        forbidden=True,
        not_found=True,
    ),
)
async def delete_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> None:
    _ = current_user
    row = db.query(CrawlerSchedule).filter(CrawlerSchedule.id == schedule_id).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule {schedule_id} not found")

    schedule_name = row.name
    # Delete the AWS schedule first so a re-create with the same name won't
    # collide with a ghost. The orphan sweep is a belt, not the suspenders.
    try:
        await asyncio.to_thread(crawler_schedule_service.delete_schedule, schedule_name)
    except Exception as e:
        logger.warning("Failed to delete AWS schedule %s: %s", schedule_name, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to delete AWS schedule for '{schedule_name}': {e}",
        )

    db.delete(row)
    db.commit()
    return None


@router.post(
    "/reconcile",
    response_model=ReconcileAllResponse,
    responses=standard_responses(success_description="Reconcile results", forbidden=True),
)
async def reconcile_all_schedules(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, list]:
    _ = current_user
    results = await asyncio.to_thread(crawler_schedule_service.reconcile_all, db)
    return {"results": results}
