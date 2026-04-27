"""
Admin endpoints for per-adapter crawler tuning.

These rows are seeded from ``ADAPTER_REGISTRY`` at startup and persist across
adapter-registry removals so retailer tuning survives refactors. Edits here
take effect on the NEXT run of any schedule that includes the adapter — no
AWS reconcile is needed because schedule payloads carry only ``schedule_id``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.category import Category as DBCategory
from app.api.models.crawler_adapter_config import CrawlerAdapterConfig
from app.api.models.user import User as DBUser
from app.api.schemas.crawler_adapter_config import (
    CrawlerAdapterConfigList,
    CrawlerAdapterConfigRead,
    CrawlerAdapterConfigUpdate,
)
from app.api.utils.endpoint_decorators import standard_responses
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/",
    response_model=CrawlerAdapterConfigList,
    responses=standard_responses(success_description="All adapter configs", forbidden=True),
)
async def list_adapter_configs(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CrawlerAdapterConfigList:
    _ = current_user
    rows = list(db.scalars(select(CrawlerAdapterConfig).order_by(CrawlerAdapterConfig.adapter_name)).all())
    return CrawlerAdapterConfigList(items=[CrawlerAdapterConfigRead.model_validate(r) for r in rows])


@router.patch(
    "/{adapter_name}",
    response_model=CrawlerAdapterConfigRead,
    responses=standard_responses(
        success_description="Adapter config updated",
        forbidden=True,
        not_found=True,
        validation_error=True,
    ),
)
async def update_adapter_config(
    adapter_name: str,
    body: CrawlerAdapterConfigUpdate,
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> CrawlerAdapterConfigRead:
    _ = current_user
    # adapter_name must still be in ADAPTER_REGISTRY — editing tuning for a
    # removed adapter would be noise. Configs for removed adapters are kept in
    # the table but read-only from this endpoint.
    if adapter_name not in ADAPTER_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown adapter '{adapter_name}'. Available: {list(ADAPTER_REGISTRY)}",
        )
    row = db.scalars(select(CrawlerAdapterConfig).where(CrawlerAdapterConfig.adapter_name == adapter_name)).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adapter config '{adapter_name}' not seeded. Restart the app.",
        )

    if body.default_category_id is not None:
        cat = db.scalars(select(DBCategory).where(DBCategory.id == body.default_category_id)).first()
        if cat is None or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"default_category_id={body.default_category_id}: not found or inactive.",
            )
        row.default_category_id = body.default_category_id

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
    return CrawlerAdapterConfigRead.model_validate(row)
