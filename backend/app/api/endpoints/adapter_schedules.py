"""
Admin endpoints for managing per-adapter crawler schedules.

The DB row is the source of truth for each adapter's cron/delay/limit
configuration; every PATCH reconciles that row to an EventBridge Scheduler
schedule via boto3. See app.api.services.adapter_schedule_service.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.adapter_schedule import AdapterSchedule
from app.api.models.category import Category as DBCategory
from app.api.models.user import User as DBUser
from app.api.schemas.adapter_schedule import (
    AdapterScheduleList,
    AdapterScheduleRead,
    AdapterScheduleUpdate,
    ReconcileAllResponse,
)
from app.api.services import adapter_schedule_service
from app.api.services.adapter_schedule_service import CRON_PRESETS
from app.api.utils.endpoint_decorators import standard_responses
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=AdapterScheduleList,
    responses=standard_responses(
        success_description="All adapter schedules",
        forbidden=True,
    ),
)
async def list_adapter_schedules(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> AdapterScheduleList:
    """List every per-adapter crawler schedule row (one per registered adapter)."""
    _ = current_user
    rows = db.query(AdapterSchedule).order_by(AdapterSchedule.adapter_name).all()
    return AdapterScheduleList(
        items=[AdapterScheduleRead.model_validate(r) for r in rows],
        presets=CRON_PRESETS,
    )


@router.patch(
    "/{adapter_name}",
    response_model=AdapterScheduleRead,
    responses=standard_responses(
        success_description="Adapter schedule updated and reconciled",
        forbidden=True,
        not_found=True,
        validation_error=True,
    ),
)
async def update_adapter_schedule(
    adapter_name: str,
    body: AdapterScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> AdapterScheduleRead:
    """
    Update one adapter's schedule fields and reconcile to EventBridge.

    On AWS error the DB update is still persisted, the row's
    ``last_reconcile_error`` is set, and a 502 is returned so the UI can
    surface the error.
    """
    _ = current_user
    if adapter_name not in ADAPTER_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown adapter '{adapter_name}'. Available: {list(ADAPTER_REGISTRY)}",
        )

    row = db.query(AdapterSchedule).filter(AdapterSchedule.adapter_name == adapter_name).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adapter schedule '{adapter_name}' not seeded. Restart the app.",
        )

    if body.default_category_id is not None:
        cat = db.query(DBCategory).filter(DBCategory.id == body.default_category_id).first()
        if not cat or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"default_category_id={body.default_category_id}: not found or inactive.",
            )
        row.default_category_id = body.default_category_id

    try:
        new_expression = adapter_schedule_service.resolve_preset_or_expression(
            preset=body.preset,
            expression=body.schedule_expression,
            current=row.schedule_expression,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    row.schedule_expression = new_expression

    if body.enabled is not None:
        row.enabled = body.enabled
    if body.delay_sec is not None:
        row.delay_sec = body.delay_sec
    if body.clear_per_run_limit:
        row.per_run_limit = None
    elif body.per_run_limit is not None:
        row.per_run_limit = body.per_run_limit
    if body.skip_known_urls is not None:
        row.skip_known_urls = body.skip_known_urls

    db.add(row)
    db.commit()
    db.refresh(row)

    def _do_reconcile() -> None:
        adapter_schedule_service.reconcile_adapter_schedule(db, row)

    try:
        await asyncio.to_thread(_do_reconcile)
    except Exception as e:
        logger.warning("Reconcile failed for adapter %s: %s", adapter_name, e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Adapter '{adapter_name}' saved, but AWS reconcile failed: {e}",
        )

    db.refresh(row)
    return AdapterScheduleRead.model_validate(row)


@router.post(
    "/reconcile",
    response_model=ReconcileAllResponse,
    responses=standard_responses(
        success_description="Reconcile results per adapter",
        forbidden=True,
    ),
)
async def reconcile_all_schedules(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, list]:
    """Force a full reconcile of every adapter schedule. Useful after deploys."""
    _ = current_user
    results = await asyncio.to_thread(adapter_schedule_service.reconcile_all, db)
    return {"results": results}
