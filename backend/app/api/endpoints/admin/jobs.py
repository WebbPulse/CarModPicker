"""Admin background job list/detail/cancel endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.api.schemas.background_job import BackgroundJobList, BackgroundJobRead
from app.api.utils.endpoint_decorators import standard_responses
from app.core.config import settings
from app.core.worker_identity import WORKER_INSTANCE_ID
from app.db.session import get_db
from app.services import job_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared with crawlers.py: in-process asyncio tasks + cooperative cancellation.
# The cancel endpoint reads these globals to signal the right stop event.
# Import-time circular risk is avoided because both modules only import from
# `admin._helpers` (leaf) and each other at runtime via module-level references.
from app.api.endpoints.admin.crawlers import job_stop_events, job_tasks  # noqa: E402


@router.get(
    "/",
    response_model=BackgroundJobList,
    responses=standard_responses(
        success_description="List of background jobs",
        forbidden=True,
    ),
)
async def list_background_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    job_type_filter: Optional[str] = Query(default=None, alias="job_type"),
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> BackgroundJobList:
    """
    List background jobs (admin only), newest first.

    Filter by ``status`` (running / completed / failed / cancelled) or
    ``job_type`` (crawler_run / archive_rescrape).

    Before returning, reconciles the running-jobs state against this process:
    any "running" row owned by a prior worker instance, or owned by us but
    with a stale heartbeat and no live asyncio task, is marked failed. Covers
    the window between "prior process died" and "admin hits refresh" even if
    the startup sweep was skipped, and catches the asyncio-task-died-without-
    cleanup edge case.
    """
    try:
        job_service.sweep_orphan_jobs(
            db,
            current_worker_instance_id=WORKER_INSTANCE_ID,
            live_job_ids=list(job_tasks.keys()),
        )
    except Exception:
        logger.exception("Runtime orphan-job sweep on list_background_jobs failed")

    items, total = job_service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
        job_type_filter=job_type_filter,
    )
    return BackgroundJobList(
        items=[BackgroundJobRead.model_validate(j) for j in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{job_id}",
    response_model=BackgroundJobRead,
    responses=standard_responses(
        success_description="Background job detail",
        forbidden=True,
    ),
)
async def get_background_job(
    job_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> BackgroundJobRead:
    """Return a single background job by ID (admin only)."""
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")
    return BackgroundJobRead.model_validate(job)


class CrawlerAdapterProgress(BaseModel):
    parsed_this_run: int
    last_parsed_at: Optional[datetime] = None


class CrawlerJobProgress(BaseModel):
    job_id: UUID
    status: str
    started_at: Optional[datetime] = None
    now: datetime
    adapters: dict[str, CrawlerAdapterProgress]


@router.get(
    "/{job_id}/crawler-progress",
    response_model=CrawlerJobProgress,
    responses=standard_responses(
        success_description="Per-adapter live progress for a crawler_run job",
        forbidden=True,
    ),
)
async def get_crawler_job_progress(
    job_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CrawlerJobProgress:
    """
    Per-adapter live progress for a crawler_run job.

    Counts crawled_pages rows whose last_parsed_at falls inside the job's
    lifetime (>= started_at). Because pending rows have no last_parsed_at,
    only successful parses since job start are counted here — which is exactly
    what an operator wants to see as a live "this run has ingested X URLs
    from adapter Y" signal. last_parsed_at for each adapter doubles as a
    liveness indicator (stalled adapters have stale timestamps).
    """
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")
    if job.job_type != "crawler_run":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not a crawler_run job (type={job.job_type}).",
        )

    params = job.params or {}
    selected: list[str] = list(params.get("adapters") or [])

    adapters: dict[str, CrawlerAdapterProgress] = {
        name: CrawlerAdapterProgress(parsed_this_run=0, last_parsed_at=None) for name in selected
    }

    if selected and job.started_at is not None:
        rows = db.execute(
            select(
                DBCrawledPage.source,
                func.count(DBCrawledPage.id),
                func.max(DBCrawledPage.last_parsed_at),
            )
            .where(
                DBCrawledPage.source.in_(selected),
                DBCrawledPage.last_parsed_at.isnot(None),
                DBCrawledPage.last_parsed_at >= job.started_at,
            )
            .group_by(DBCrawledPage.source)
        ).all()
        for source, count, last_at in rows:
            adapters[source] = CrawlerAdapterProgress(
                parsed_this_run=count,
                last_parsed_at=last_at,
            )

    return CrawlerJobProgress(
        job_id=job.id,
        status=job.status,
        started_at=job.started_at,
        now=datetime.now(timezone.utc),
        adapters=adapters,
    )


@router.post(
    "/{job_id}/cancel",
    response_model=BackgroundJobRead,
    responses=standard_responses(
        success_description="Job marked as cancelled",
        forbidden=True,
    ),
)
async def cancel_background_job(
    job_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> BackgroundJobRead:
    """
    Cancel a running background job (admin only).

    Sets the DB status to 'cancelled' and signals the worker's stop event so
    the crawler / rescrape loop exits at the next URL boundary.
    """
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")
    if job.status != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not running (status={job.status}).",
        )
    updated = job_service.cancel_job(db, job_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")

    # For ECS-backed crawler jobs: stop the Fargate task.
    # For in-process jobs (archive rescrape): signal the stop event.
    task_arn = (job.params or {}).get("ecs_task_arn")
    if task_arn:
        try:
            ecs_client = boto3.client("ecs", region_name=settings.AWS_REGION or None)
            ecs_client.stop_task(
                cluster=settings.CRAWLER_ECS_CLUSTER,
                task=task_arn,
                reason="Cancelled by admin",
            )
            logger.info("Job #%s cancel: ECS task %s stopped.", job_id, task_arn)
        except (BotoCoreError, ClientError) as e:
            logger.warning("Job #%s cancel: failed to stop ECS task %s: %s", job_id, task_arn, e)
    else:
        stop_event = job_stop_events.get(job_id)
        if stop_event is not None:
            stop_event.set()
            logger.info("Job #%s cancel: stop event signalled.", job_id)
        else:
            logger.warning("Job #%s cancel: no stop event or ECS task found (job may have already finished).", job_id)

    return BackgroundJobRead.model_validate(updated)
