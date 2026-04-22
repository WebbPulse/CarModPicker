"""
Admin endpoints for system management operations.

This module provides admin-only endpoints for system maintenance tasks
such as running database migrations, initializing seed data (car
generations, part categories), and running retailer crawlers.
"""

import asyncio
import json
import logging
import os
import secrets
import subprocess  # nosec B404 - Used safely for running database migrations
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.associations.part_car import part_cars
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.car_generation import CarGeneration as DBCar
from app.api.models.car_make import CarMake as DBMake
from app.api.models.car_model import CarModel as DBCarModel
from app.api.models.category import Category as DBCategory
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.crawler_adapter_config import CrawlerAdapterConfig as DBCrawlerAdapterConfig
from app.api.models.crawler_schedule import CrawlerSchedule as DBCrawlerSchedule
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.report import Report as DBReport
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.schemas.background_job import BackgroundJobList, BackgroundJobRead
from app.api.utils.endpoint_decorators import standard_responses
from app.core.config import settings
from app.core.email import send_job_report_email
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
from app.core.worker_identity import WORKER_INSTANCE_ID
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC, count_crawl_bucket_object_summary
from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id, run_crawlers
from app.db.session import SessionLocal, get_db
from app.services import job_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Strong references to fire-and-forget tasks so they are not garbage-collected
# mid-execution. Tasks remove themselves on completion via add_done_callback.
_background_tasks: set[asyncio.Task[None]] = set()

# Per-job asyncio tasks and stop events for cooperative cancellation.
# Entries are cleaned up when the job task finishes.
_job_tasks: dict[UUID, asyncio.Task[None]] = {}
_job_stop_events: dict[UUID, threading.Event] = {}

# How often an in-process job stamps its heartbeat. Short enough that the
# runtime stale-heartbeat sweep (default 180s) has plenty of signal, long
# enough to keep DB write volume negligible.
_HEARTBEAT_INTERVAL_SEC = 15


def _stamp_heartbeat(job_id: UUID) -> None:
    """Write a single heartbeat row. Runs in a thread to keep the event loop free."""
    db = SessionLocal()
    try:
        job_service.heartbeat_job(db, job_id, WORKER_INSTANCE_ID)
    finally:
        db.close()


async def _heartbeat_loop(job_id: UUID, interval: float = _HEARTBEAT_INTERVAL_SEC) -> None:
    """
    Periodically refresh a job's last_heartbeat_at so the runtime sweep can tell
    the worker is still alive. Cancelled by the caller when the real job task
    finishes; individual heartbeat failures are logged but don't abort the loop.
    """
    while True:
        try:
            await asyncio.sleep(interval)
            await asyncio.to_thread(_stamp_heartbeat, job_id)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Heartbeat loop for job #%s hit an error; continuing", job_id)


def _get_superadmin_emails(db: Session) -> List[str]:
    """Return email addresses of all active superusers for job notification."""
    users = db.query(DBUser.email).filter(DBUser.is_superuser.is_(True), DBUser.disabled.is_(False)).all()
    return [row.email for row in users]


def _notify_job_completion(job_id: UUID) -> None:
    """
    Send a job-report email to all superadmins.
    Opens its own DB session; safe to call from a background thread.
    """
    db = SessionLocal()
    try:
        job = job_service.get_job(db, job_id)
        if job is None:
            return
        recipients = _get_superadmin_emails(db)
        if recipients:
            sent = send_job_report_email(job, recipients)
            logger.info("Job #%s report sent to %s superadmin(s)", job_id, sent)
    except Exception:
        logger.exception("Failed to send job report email for job #%s", job_id)
    finally:
        db.close()


def _verify_cron_key(x_admin_cron_key: Optional[str]) -> bool:
    """
    Return True if the provided key matches CRON_SECRET_KEY (constant-time compare).
    Returns False when CRON_SECRET_KEY is not configured.
    """
    expected = settings.CRON_SECRET_KEY
    if not expected or not x_admin_cron_key:
        return False
    return secrets.compare_digest(expected, x_admin_cron_key)


def _get_alembic_directory() -> str:
    """
    Get the directory containing alembic.ini.

    Returns the backend directory where alembic.ini is located.
    """
    # Try production path first (/app)
    if os.path.exists("/app/alembic.ini"):
        return "/app"

    # Find backend directory by looking for alembic.ini
    # Start from this file's location and walk up
    current_file = Path(__file__).resolve()
    # This file is at: backend/app/api/endpoints/admin.py
    # alembic.ini is at: backend/alembic.ini
    # So we need to go up 3 levels from this file
    backend_dir = current_file.parent.parent.parent.parent

    # Verify alembic.ini exists there
    alembic_ini = backend_dir / "alembic.ini"
    if alembic_ini.exists():
        return str(backend_dir)

    # Fallback: try current working directory
    if os.path.exists("alembic.ini"):
        return os.getcwd()

    # Last resort: use the calculated backend directory anyway
    return str(backend_dir)


@router.get(
    "/stats/table-counts",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Supplemental table and polymorphic vote/report counts",
        forbidden=True,
    ),
)
async def get_admin_table_counts(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Admin-only: counts for internal tables not exposed elsewhere, plus votes/reports by entity_type.

    Build list phases and crawled pages also have dedicated /count routes; this endpoint
    duplicates those counts for a single dashboard fetch if desired.
    """
    _ = current_user

    part_car_rows = db.query(func.count()).select_from(part_cars).scalar()
    part_car_count = int(part_car_rows or 0)

    vote_rows = db.query(DBVote.entity_type, func.count(DBVote.id)).group_by(DBVote.entity_type).all()
    votes_by_entity_type = {str(row[0]): int(row[1]) for row in vote_rows}

    report_rows = db.query(DBReport.entity_type, func.count(DBReport.id)).group_by(DBReport.entity_type).all()
    reports_by_entity_type = {str(row[0]): int(row[1]) for row in report_rows}

    crawl_bucket_stats = count_crawl_bucket_object_summary()

    return {
        "build_list_phases": db.query(DBBuildListPhase).count(),
        "crawled_pages": db.query(DBCrawledPage).count(),
        "part_listings": db.query(DBPartListing).count(),
        "part_price_histories": db.query(DBPartPriceHistory).count(),
        "image_source_mappings": db.query(DBImageSourceMapping).count(),
        "build_logs": db.query(DBBuildLog).count(),
        "part_cars": part_car_count,
        "votes_by_entity_type": votes_by_entity_type,
        "reports_by_entity_type": reports_by_entity_type,
        **crawl_bucket_stats,
    }


@router.post(
    "/migrations/run",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Migrations executed successfully",
        forbidden=True,
    ),
)
async def run_migrations(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Run database migrations manually (admin only).

    This endpoint allows admins to trigger database migrations manually
    in case automatic migrations fail or need to be run on-demand.

    Returns:
        - success: Whether migrations completed successfully
        - output: Migration command output
        - error: Error message if migration failed
        - current_revision: Current database revision after migration
    """
    # Determine the correct working directory for alembic
    cwd = _get_alembic_directory()
    alembic_ini = os.path.join(cwd, "alembic.ini")

    if not os.path.exists(alembic_ini):
        error_msg = f"Could not find alembic.ini in {cwd}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    try:
        logger.info(f"Admin {current_user.id} triggered manual migration from {cwd}")

        # Run alembic upgrade head with explicit config file
        # nosec B603, B607 - Hardcoded command for database migrations, not user input
        result = subprocess.run(
            ["alembic", "-c", alembic_ini, "upgrade", "head"],  # nosec B603, B607
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300,  # 5 minute timeout
        )

        # Get current revision
        current_revision = None
        try:
            current_result = subprocess.run(
                ["alembic", "-c", alembic_ini, "current"],  # nosec B603, B607
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            current_revision = current_result.stdout.strip()
        except Exception as e:
            logger.warning(f"Could not get current revision: {e}")

        # Invalidate connection pool to pick up schema changes
        from app.db.session import engine

        engine.dispose(close=False)

        logger.info(f"Migration completed successfully by admin {current_user.id}")

        return {
            "success": True,
            "output": result.stdout,
            "error": None,
            "current_revision": current_revision,
        }
    except subprocess.TimeoutExpired:
        error_msg = "Migration timed out after 5 minutes"
        logger.error(f"Migration timeout: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )
    except subprocess.CalledProcessError as e:
        error_output = e.stderr or e.stdout or str(e)
        logger.error(f"Migration failed: {error_output}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {error_output}",
        )
    except Exception as e:
        error_msg = f"Unexpected error during migration: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.get(
    "/migrations/current",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Current migration revision retrieved",
        forbidden=True,
    ),
)
async def get_current_migration_revision(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Get the current database migration revision (admin only).

    Returns:
        - current_revision: Current database revision
        - output: Full alembic current output
    """
    # Determine the correct working directory for alembic
    cwd = _get_alembic_directory()
    alembic_ini = os.path.join(cwd, "alembic.ini")

    if not os.path.exists(alembic_ini):
        error_msg = f"Could not find alembic.ini in {cwd}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    try:
        result = subprocess.run(
            ["alembic", "-c", alembic_ini, "current"],  # nosec B603, B607
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        return {
            "current_revision": result.stdout.strip(),
            "output": result.stdout,
        }
    except subprocess.CalledProcessError as e:
        error_output = e.stderr or e.stdout or str(e)
        logger.error(f"Failed to get current revision: {error_output}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get current revision: {error_output}",
        )
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


def _init_result(success: bool, message: str) -> Dict[str, Any]:
    """Standard response for init endpoints."""
    return {"success": success, "message": message}


@router.post(
    "/init/car-generations",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Car generations initialized successfully",
        forbidden=True,
    ),
)
async def init_car_generations_endpoint(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Initialize car generations from source of truth (admin only).

    Syncs makes, car models, and car generations from car_generations_data
    into the database. Run this manually after deploying or when seed data
    has been updated.
    """
    try:
        logger.info(f"Admin {current_user.id} triggered car generations init")
        db = SessionLocal()
        try:
            init_car_generations(db)
            return _init_result(True, "Car generations initialized successfully")
        finally:
            db.close()
    except Exception as e:
        logger.exception("Car generations init failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/init/part-categories",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Part categories initialized successfully",
        forbidden=True,
    ),
)
async def init_part_categories_endpoint(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Initialize part categories from source of truth (admin only).

    Syncs part categories from part_categories_data into the database.
    Run this manually after deploying or when seed data has been updated.
    """
    try:
        logger.info(f"Admin {current_user.id} triggered part categories init")
        db = SessionLocal()
        try:
            init_part_categories(db)
            return _init_result(True, "Part categories initialized successfully")
        finally:
            db.close()
    except Exception as e:
        logger.exception("Part categories init failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class DeleteAllCarsResponse(BaseModel):
    """Response for delete-all cars (admin only)."""

    deleted_count: int = Field(..., description="Number of cars (generations) deleted")
    deleted_car_models_count: int = Field(..., description="Number of car models deleted")
    deleted_makes_count: int = Field(..., description="Number of makes deleted")


@router.post(
    "/cars/delete-all",
    response_model=DeleteAllCarsResponse,
    responses=standard_responses(
        success_description="All cars deleted",
        forbidden=True,
    ),
)
async def delete_all_cars(
    current_user: DBUser = Depends(get_current_admin_user),
) -> DeleteAllCarsResponse:
    """
    Delete all cars / car generations (admin only).

    Unlinks build lists from cars (sets car_id to null), removes car votes and
    part_cars links, then deletes all Car, CarModel, and Make rows so
    Init Car Generations can repopulate from a clean slate.
    This action cannot be undone.
    """
    db = SessionLocal()
    try:
        # Unlink build lists from cars so we can delete cars (FK has no ON DELETE)
        db.query(DBBuildList).filter(DBBuildList.car_id.isnot(None)).update(
            {DBBuildList.car_id: None}, synchronize_session=False
        )
        # Remove votes that reference cars
        db.query(DBVote).filter(DBVote.entity_type == "car_generation").delete(synchronize_session=False)
        count = db.query(DBCar).count()
        db.query(DBCar).delete(synchronize_session=False)
        car_models_count = db.query(DBCarModel).count()
        db.query(DBCarModel).delete(synchronize_session=False)
        makes_count = db.query(DBMake).count()
        db.query(DBMake).delete(synchronize_session=False)
        db.commit()
        logger.info(
            "Admin %s deleted all cars: %s cars, %s car models, %s makes",
            current_user.id,
            count,
            car_models_count,
            makes_count,
        )
        return DeleteAllCarsResponse(
            deleted_count=count,
            deleted_car_models_count=car_models_count,
            deleted_makes_count=makes_count,
        )
    except Exception as e:
        db.rollback()
        logger.exception("Delete all cars failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    finally:
        db.close()


# --- Crawler admin endpoints ---


class CrawlerRunRequest(BaseModel):
    """
    Request body for running crawlers.

    Two shapes are accepted:

    1. **Scheduled** — ``schedule_id`` alone (EventBridge Scheduler payload). The
       server dereferences the schedule's members and their per-adapter configs.
    2. **Explicit** — ``adapters`` + ``crawler_default_category_id`` (manual
       admin runs from the UI or API). Per-adapter knobs can be passed as
       dicts.

    Mixing the two forms is rejected by a ``model_validator``.
    """

    schedule_id: Optional[UUID] = Field(
        default=None,
        description="ID of a crawler_schedules row. When set, all other fields except crawler_user_id are ignored and sourced from the schedule + adapter configs.",
    )
    adapters: Optional[list[str]] = Field(
        default=None,
        description="Adapter names to run (e.g. ['a90shop']). Use ['all'] to run all adapters. Required when schedule_id is not set.",
    )
    crawler_user_id: Optional[UUID] = Field(
        default=None,
        description="User ID to attribute crawler-created parts to. Defaults to the crawler service account.",
    )
    crawler_default_category_id: Optional[UUID] = Field(
        default=None,
        description="Category ID for new parts. Required when schedule_id is not set.",
    )
    limits: Optional[Dict[str, int]] = Field(
        default=None,
        description="Per-adapter crawl limits: {'a90shop': 10}. Overrides global_limit when set.",
    )
    global_limit: Optional[int] = Field(
        default=None,
        description="Crawl limit applied to all adapters when no per-adapter limit is set.",
    )
    parallel: bool = Field(
        default=True,
        description="If True and more than one adapter, run crawlers in parallel threads.",
    )
    delay_sec: Optional[float] = Field(
        default=None,
        ge=0.5,
        le=60.0,
        description="Default delay between requests per crawler (default: 2.5). Use 5+ for conservative/large runs.",
    )
    delays: Optional[Dict[str, float]] = Field(
        default=None,
        description="Per-adapter delay override: {'a90shop': 7.5}. Falls back to delay_sec.",
    )
    crawl_html_save_dir: Optional[str] = Field(
        default=None,
        description="Kept for backward compatibility. HTML is always archived for every URL crawled.",
    )
    skip_known_urls: bool = Field(
        default=False,
        description="Default: skip URLs already parsed. Per-adapter overrides via skip_known_urls_by_adapter.",
    )
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Per-adapter override for skip_known_urls.",
    )
    default_category_ids: Optional[Dict[str, UUID]] = Field(
        default=None,
        description="Per-adapter category override: {'a90shop': <uuid>}. Falls back to crawler_default_category_id.",
    )

    @model_validator(mode="after")
    def _validate_shape(self) -> "CrawlerRunRequest":
        if self.schedule_id is not None:
            if self.adapters is not None:
                raise ValueError("Do not pass 'adapters' when using schedule_id; it is derived from the schedule.")
            return self
        if not self.adapters:
            raise ValueError("Either schedule_id or a non-empty adapters list is required.")
        if self.crawler_default_category_id is None:
            raise ValueError("crawler_default_category_id is required when schedule_id is not set.")
        return self


@router.get(
    "/crawlers",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Available crawlers retrieved",
        forbidden=True,
    ),
)
async def list_crawlers(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    List available crawler adapters (admin only).

    Returns both a flat ``adapters`` list (for back-compat) and a richer
    ``adapter_info`` list that carries each adapter's declared fetcher tier
    (``http``, ``tls``, or ``browser``) so the admin UI can visually group
    them by blocking difficulty.
    """
    adapters = list(ADAPTER_REGISTRY.keys())
    adapter_info = [{"name": name, "tier": cls.FETCHER_TIER} for name, cls in ADAPTER_REGISTRY.items()]
    return {"adapters": adapters, "adapter_info": adapter_info}


def _launch_ecs_crawler_task(
    *,
    job_id: UUID,
    adapters: list[str],
    default_category_id: UUID,
    user_id: UUID,
    limits: Optional[Dict[str, int]],
    global_limit: Optional[int],
    delay_sec: float,
    parallel: bool,
    skip_known_urls: bool,
    delays: Optional[Dict[str, float]] = None,
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = None,
    default_category_ids: Optional[Dict[str, UUID]] = None,
) -> str:
    """
    Launch an ECS Fargate task to run the crawler. Returns the ECS task ARN.

    Requires CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, CRAWLER_ECS_SUBNETS,
    and CRAWLER_ECS_SECURITY_GROUP to be configured in settings.
    Raises RuntimeError if ECS is not configured or RunTask fails.
    """
    if not settings.crawler_ecs_configured:
        raise RuntimeError(
            "ECS crawler not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, "
            "CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP."
        )

    ecs_client = boto3.client("ecs", region_name=settings.AWS_REGION or None)

    env_overrides: list[dict[str, str]] = [
        {"name": "JOB_ID", "value": str(job_id)},
        {"name": "CRAWLER_ADAPTERS", "value": ",".join(adapters)},
        {"name": "CRAWLER_DEFAULT_CATEGORY_ID", "value": str(default_category_id)},
        {"name": "CRAWLER_USER_ID", "value": str(user_id)},
        {"name": "CRAWLER_DELAY_SEC", "value": str(delay_sec)},
        {"name": "CRAWLER_PARALLEL", "value": "true" if parallel else "false"},
        {"name": "CRAWLER_SKIP_KNOWN_URLS", "value": "true" if skip_known_urls else "false"},
    ]
    if limits:
        env_overrides.append({"name": "CRAWLER_LIMITS", "value": json.dumps(limits)})
    if global_limit is not None:
        env_overrides.append({"name": "CRAWLER_GLOBAL_LIMIT", "value": str(global_limit)})
    if delays:
        env_overrides.append({"name": "CRAWLER_DELAYS", "value": json.dumps(delays)})
    if skip_known_urls_by_adapter:
        env_overrides.append(
            {"name": "CRAWLER_SKIP_KNOWN_URLS_BY_ADAPTER", "value": json.dumps(skip_known_urls_by_adapter)}
        )
    if default_category_ids:
        env_overrides.append(
            {
                "name": "CRAWLER_DEFAULT_CATEGORY_IDS",
                "value": json.dumps({k: str(v) for k, v in default_category_ids.items()}),
            }
        )

    subnets = [s.strip() for s in settings.CRAWLER_ECS_SUBNETS.split(",") if s.strip()]
    security_groups = [sg.strip() for sg in settings.CRAWLER_ECS_SECURITY_GROUP.split(",") if sg.strip()]

    response = ecs_client.run_task(
        cluster=settings.CRAWLER_ECS_CLUSTER,
        taskDefinition=settings.CRAWLER_ECS_TASK_DEFINITION,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "crawler",
                    "environment": env_overrides,
                }
            ]
        },
    )

    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS RunTask failures: {failures}")

    tasks = response.get("tasks", [])
    if not tasks:
        raise RuntimeError("ECS RunTask returned no tasks and no failures.")

    return tasks[0]["taskArn"]


async def _run_crawlers_in_process(
    adapters: list[str],
    *,
    limits: Optional[Dict[str, int]],
    global_limit: Optional[int],
    parallel: bool,
    delay_sec: float,
    user_id: UUID,
    default_category_id: UUID,
    job_id: UUID,
    stop_event: threading.Event,
    skip_known_urls: bool,
    delays: Optional[Dict[str, float]] = None,
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = None,
    default_category_ids: Optional[Dict[str, UUID]] = None,
) -> None:
    """
    Dev-only fallback: run crawlers in an asyncio background thread.
    Only used when ECS is not configured (i.e. local development).
    In production, _launch_ecs_crawler_task is always used instead.
    """
    # Stamp ownership immediately so a crash before the first heartbeat interval
    # still leaves the row correctly tagged with this process's worker ID.
    await asyncio.to_thread(_stamp_heartbeat, job_id)
    heartbeat_task = asyncio.create_task(_heartbeat_loop(job_id))
    try:
        result = await asyncio.to_thread(
            run_crawlers,
            adapters,
            limits=limits,
            global_limit=global_limit,
            parallel=parallel,
            delay_sec=delay_sec,
            delays=delays,
            user_id=user_id,
            default_category_id=default_category_id,
            default_category_ids=default_category_ids,
            stop_event=stop_event,
            skip_known_urls=skip_known_urls,
            skip_known_urls_by_adapter=skip_known_urls_by_adapter,
        )
        db = SessionLocal()
        try:
            result_dict = result if isinstance(result, dict) else {"raw": str(result)}
            job_service.complete_job(db, job_id, result_summary=result_dict)
            await asyncio.to_thread(_notify_job_completion, job_id)
        finally:
            db.close()
    except Exception as e:
        logger.exception("In-process crawler job #%s failed: %s", job_id, e)
        db = SessionLocal()
        try:
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            await asyncio.to_thread(_notify_job_completion, job_id)
        finally:
            db.close()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        _job_tasks.pop(job_id, None)
        _job_stop_events.pop(job_id, None)


@router.post(
    "/crawlers/run",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Crawler job started",
        forbidden=True,
    ),
)
async def run_crawlers_endpoint(
    body: CrawlerRunRequest,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_admin_user),
    x_admin_cron_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Start retailer crawlers (admin only). Returns immediately after enqueueing the job.

    Accepts either a superadmin JWT (manual trigger from admin UI) or the
    ``X-Admin-Cron-Key`` header (EventBridge Scheduler scheduled trigger).

    - Run individual crawlers or desired combinations.
    - Run all crawlers with adapters: ["all"].
    - Set per-crawler limits via limits: {"a90shop": 10, "example": 5}.
    - Set a global limit for all crawlers via global_limit.
    - When running more than one crawler, they run in parallel by default.
    """
    is_scheduled = _verify_cron_key(x_admin_cron_key)
    if not is_scheduled and current_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    triggered_by = "scheduled" if is_scheduled else "manual"
    acting_user_id: Optional[UUID] = None if is_scheduled else (current_user.id if current_user else None)

    # Validate crawler user and category upfront so we return 400 instead of 200 + silent failure
    if body.crawler_user_id is not None:
        crawler_user = db.query(DBUser).filter(DBUser.id == body.crawler_user_id).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: no user found.",
            )
        if crawler_user.disabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: user is disabled.",
            )
    else:
        # Ensure service account exists before kicking off the job
        crawler_user = db.query(DBUser).filter(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False)).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No crawler service account found. Restart the app to create it.",
            )
    # Resolve the concrete run shape — either from a schedule_id (EB firing or
    # UI-dispatched scheduled run) or from the explicit body. A schedule's
    # ``enabled`` flag is intentionally NOT re-checked here: EventBridge has
    # already made the authoritative "fire" decision by the time we see it.
    adapters: list[str]
    delay_sec: float = body.delay_sec if body.delay_sec is not None else DEFAULT_REQUEST_DELAY_SEC
    limits: Optional[Dict[str, int]] = body.limits
    delays: Optional[Dict[str, float]] = body.delays
    skip_known_urls: bool = body.skip_known_urls
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = body.skip_known_urls_by_adapter
    default_category_id: UUID
    default_category_ids: Optional[Dict[str, UUID]] = body.default_category_ids
    parallel: bool = body.parallel

    if body.schedule_id is not None:
        sched = db.query(DBCrawlerSchedule).filter(DBCrawlerSchedule.id == body.schedule_id).first()
        if not sched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"schedule_id={body.schedule_id}: not found.",
            )
        member_names = [a.adapter_name for a in sched.adapters]
        if not member_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schedule '{sched.name}' has no adapters.",
            )
        configs = db.query(DBCrawlerAdapterConfig).filter(DBCrawlerAdapterConfig.adapter_name.in_(member_names)).all()
        configs_by_name = {c.adapter_name: c for c in configs}
        missing = [n for n in member_names if n not in configs_by_name]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing crawler_adapter_configs for: {missing}. Restart the app to re-seed.",
            )
        adapters = [n for n in member_names if n in ADAPTER_REGISTRY]
        unknown = [n for n in member_names if n not in ADAPTER_REGISTRY]
        if unknown:
            logger.warning(
                "Schedule '%s' references unregistered adapter(s) %s; skipping.",
                sched.name,
                unknown,
            )
        if not adapters:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schedule '{sched.name}' has no currently-registered adapters.",
            )
        delays = {n: configs_by_name[n].delay_sec for n in adapters}
        skip_known_urls_by_adapter = {n: configs_by_name[n].skip_known_urls for n in adapters}
        default_category_ids = {n: configs_by_name[n].default_category_id for n in adapters}
        per_adapter_limits: Dict[str, int] = {}
        for n in adapters:
            lim = configs_by_name[n].per_run_limit
            if lim is not None:
                per_adapter_limits[n] = lim
        limits = per_adapter_limits or None
        default_category_id = configs_by_name[adapters[0]].default_category_id
        parallel = True
        logger.info(
            "Dispatching schedule '%s' (id=%s) with adapters=%s",
            sched.name,
            sched.id,
            adapters,
        )
    else:
        if body.crawler_default_category_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="crawler_default_category_id is required when schedule_id is not set.",
            )
        cat = db.query(DBCategory).filter(DBCategory.id == body.crawler_default_category_id).first()
        if not cat or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_default_category_id={body.crawler_default_category_id}: not found or inactive.",
            )
        raw = body.adapters or []
        if raw == ["all"]:
            adapters = list(ADAPTER_REGISTRY.keys())
        else:
            adapters = raw
        invalid = [a for a in adapters if a not in ADAPTER_REGISTRY]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown adapter(s): {invalid}. Available: {list(ADAPTER_REGISTRY.keys())}",
            )
        default_category_id = body.crawler_default_category_id

    logger.info(
        "Crawler job starting: adapters=%s triggered_by=%s user=%s",
        adapters,
        triggered_by,
        acting_user_id,
    )

    job = job_service.create_job(
        db,
        job_type="crawler_run",
        triggered_by=triggered_by,
        params={
            "adapters": adapters,
            "limits": limits,
            "global_limit": body.global_limit,
            "parallel": parallel,
            "delay_sec": delay_sec,
            "delays": delays,
            "crawler_user_id": str(crawler_user.id),
            "default_category_id": str(default_category_id),
            "default_category_ids": (
                {k: str(v) for k, v in default_category_ids.items()} if default_category_ids else None
            ),
            "skip_known_urls": skip_known_urls,
            "skip_known_urls_by_adapter": skip_known_urls_by_adapter,
            "schedule_id": str(body.schedule_id) if body.schedule_id else None,
        },
        created_by_user_id=acting_user_id,
        worker_instance_id=WORKER_INSTANCE_ID,
    )

    if settings.crawler_ecs_configured:
        # Production path: launch a Fargate task that spins up, runs, and tears down.
        try:
            task_arn = _launch_ecs_crawler_task(
                job_id=job.id,
                adapters=adapters,
                default_category_id=default_category_id,
                user_id=crawler_user.id,
                limits=limits,
                global_limit=body.global_limit,
                delay_sec=delay_sec,
                parallel=parallel,
                skip_known_urls=skip_known_urls,
                delays=delays,
                skip_known_urls_by_adapter=skip_known_urls_by_adapter,
                default_category_ids=default_category_ids,
            )
            # Store the ECS task ARN so the cancel endpoint can stop it.
            job.params = {**(job.params or {}), "ecs_task_arn": task_arn}
            db.add(job)
            db.commit()
            logger.info("Crawler job #%s launched ECS task: %s", job.id, task_arn)
        except Exception as e:
            logger.exception("Failed to launch ECS task for crawler job #%s: %s", job.id, e)
            job_service.fail_job(db, job.id, error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to launch crawler task: {e}",
            )
    elif not settings.is_production:
        # Dev fallback: run in-process as a background asyncio task.
        logger.info("Crawler job #%s: ECS not configured, running in-process (dev mode).", job.id)
        stop_event = threading.Event()
        task = asyncio.create_task(
            _run_crawlers_in_process(
                adapters,
                limits=limits,
                global_limit=body.global_limit,
                parallel=parallel,
                delay_sec=delay_sec,
                user_id=crawler_user.id,
                default_category_id=default_category_id,
                job_id=job.id,
                stop_event=stop_event,
                skip_known_urls=skip_known_urls,
                delays=delays,
                skip_known_urls_by_adapter=skip_known_urls_by_adapter,
                default_category_ids=default_category_ids,
            )
        )
        _job_tasks[job.id] = task
        _job_stop_events[job.id] = stop_event
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    else:
        job_service.fail_job(db, job.id, error_message="ECS crawler not configured in production.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crawler ECS task is not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP.",
        )

    return {
        "status": "started",
        "job_id": job.id,
        "adapters": adapters,
        "triggered_by": triggered_by,
        "message": "Crawler job has been started. A completion report will be sent to superadmins when finished.",
    }


class RescrapeArchivesRequest(BaseModel):
    """Request body for re-parsing all archived HTML into global parts (same as crawler ingest)."""

    crawler_user_id: Optional[UUID] = Field(
        default=None,
        description="User ID to attribute created/updated parts to. Defaults to the crawler service account.",
    )
    default_category_id: UUID = Field(
        ...,
        description="Fallback category ID when inference cannot pick a category.",
    )


def _launch_ecs_rescrape_task(
    *,
    job_id: UUID,
    user_id: UUID,
    default_category_id: UUID,
) -> str:
    """
    Launch an ECS Fargate task to run the archive rescrape. Returns the ECS task ARN.

    Reuses the same cluster and task definition as the crawler, overriding the
    container command to point at the rescrape entry point.
    Raises RuntimeError if ECS is not configured or RunTask fails.
    """
    if not settings.crawler_ecs_configured:
        raise RuntimeError(
            "ECS crawler not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, "
            "CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP."
        )

    ecs_client = boto3.client("ecs", region_name=settings.AWS_REGION or None)

    subnets = [s.strip() for s in settings.CRAWLER_ECS_SUBNETS.split(",") if s.strip()]
    security_groups = [sg.strip() for sg in settings.CRAWLER_ECS_SECURITY_GROUP.split(",") if sg.strip()]

    response = ecs_client.run_task(
        cluster=settings.CRAWLER_ECS_CLUSTER,
        taskDefinition=settings.CRAWLER_ECS_TASK_DEFINITION,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "crawler",
                    "command": ["python", "-m", "app.crawlers.ecs_rescrape_runner"],
                    "environment": [
                        {"name": "JOB_ID", "value": str(job_id)},
                        {"name": "CRAWLER_USER_ID", "value": str(user_id)},
                        {"name": "CRAWLER_DEFAULT_CATEGORY_ID", "value": str(default_category_id)},
                    ],
                }
            ]
        },
    )

    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS RunTask failures: {failures}")

    tasks = response.get("tasks", [])
    if not tasks:
        raise RuntimeError("ECS RunTask returned no tasks and no failures.")

    return tasks[0]["taskArn"]


async def _run_rescrape_in_process(
    *,
    crawler_user_id: UUID,
    default_category_id: UUID,
    job_id: UUID,
    stop_event: threading.Event,
) -> None:
    """
    Dev-only fallback: run archive rescrape in a background thread.
    Only used when ECS is not configured (i.e. local development).
    """

    def _progress(processed: int, total: int, counts_snapshot: dict[str, int]) -> None:
        # Dedicated short-lived session — the driver thread's ``db`` is the
        # main rescrape session and we don't want to share its transaction.
        pdb = SessionLocal()
        try:
            job_service.update_job_progress(
                pdb,
                job_id,
                {**counts_snapshot, "processed": processed, "total": total},
            )
        except Exception:
            logger.exception("Failed to write progress for rescrape job #%s", job_id)
        finally:
            pdb.close()

    def _blocking() -> None:
        db = SessionLocal()
        try:
            crawler_user = resolve_crawler_user(db, crawler_user_id)
            cat_id = resolve_default_category_id(db, default_category_id)
            counts = run_rescrape_all_archived_pages(
                db,
                crawler_user=crawler_user,
                default_category_id=cat_id,
                log=logger,
                stop_event=stop_event,
                progress_callback=_progress,
            )
            job_service.complete_job(db, job_id, result_summary=counts)
            _notify_job_completion(job_id)
        except Exception as e:
            logger.exception("In-process archive rescrape job #%s failed: %s", job_id, e)
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            _notify_job_completion(job_id)
        finally:
            db.close()

    await asyncio.to_thread(_stamp_heartbeat, job_id)
    heartbeat_task = asyncio.create_task(_heartbeat_loop(job_id))
    try:
        await asyncio.to_thread(_blocking)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        _job_tasks.pop(job_id, None)
        _job_stop_events.pop(job_id, None)


@router.post(
    "/crawled-pages/rescrape-archives",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Archive rescrape job started",
        forbidden=True,
    ),
)
async def rescrape_all_archived_crawled_pages(
    body: RescrapeArchivesRequest,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_admin_user),
    x_admin_cron_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Start a background job that re-parses every crawled page with stored HTML.

    Accepts either a superadmin JWT (manual trigger) or ``X-Admin-Cron-Key`` header
    (EventBridge Scheduler scheduled trigger).

    For each row: load archived HTML, run the appropriate retailer parser (including
    extension-sourced URLs matched by host), then ``ingest_payload`` so parts are
    created/updated with full inference and listing refresh. Price history is updated
    when the parsed payload includes a price (same path as live crawls).

    HTML is stored under one canonical object per URL (``crawl_html/by_url/…``).
    """
    is_scheduled = _verify_cron_key(x_admin_cron_key)
    if not is_scheduled and current_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    triggered_by = "scheduled" if is_scheduled else "manual"
    acting_user_id: Optional[UUID] = None if is_scheduled else (current_user.id if current_user else None)

    if body.crawler_user_id is not None:
        crawler_user = db.query(DBUser).filter(DBUser.id == body.crawler_user_id).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: no user found.",
            )
        if crawler_user.disabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: user is disabled.",
            )
    else:
        crawler_user = db.query(DBUser).filter(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False)).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No crawler service account found. Restart the app to create it.",
            )
    cat = db.query(DBCategory).filter(DBCategory.id == body.default_category_id).first()
    if not cat or not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"default_category_id={body.default_category_id}: not found or inactive.",
        )

    logger.info(
        "Archive rescrape job starting: triggered_by=%s user=%s",
        triggered_by,
        acting_user_id,
    )

    job = job_service.create_job(
        db,
        job_type="archive_rescrape",
        triggered_by=triggered_by,
        params={
            "crawler_user_id": str(crawler_user.id),
            "default_category_id": str(body.default_category_id),
        },
        created_by_user_id=acting_user_id,
        worker_instance_id=WORKER_INSTANCE_ID,
    )

    if settings.crawler_ecs_configured:
        # Production path: launch a Fargate task that spins up, runs, and tears down.
        try:
            task_arn = _launch_ecs_rescrape_task(
                job_id=job.id,
                user_id=crawler_user.id,
                default_category_id=body.default_category_id,
            )
            job.params = {**(job.params or {}), "ecs_task_arn": task_arn}
            db.add(job)
            db.commit()
            logger.info("Archive rescrape job #%s launched ECS task: %s", job.id, task_arn)
        except Exception as e:
            logger.exception("Failed to launch ECS task for rescrape job #%s: %s", job.id, e)
            job_service.fail_job(db, job.id, error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to launch rescrape task: {e}",
            )
    elif not settings.is_production:
        # Dev fallback: run in-process as a background asyncio task.
        logger.info("Archive rescrape job #%s: ECS not configured, running in-process (dev mode).", job.id)
        stop_event = threading.Event()
        task = asyncio.create_task(
            _run_rescrape_in_process(
                crawler_user_id=crawler_user.id,
                default_category_id=body.default_category_id,
                job_id=job.id,
                stop_event=stop_event,
            )
        )
        _job_tasks[job.id] = task
        _job_stop_events[job.id] = stop_event
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    else:
        job_service.fail_job(db, job.id, error_message="ECS crawler not configured in production.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crawler ECS task is not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP.",
        )

    return {
        "status": "started",
        "job_id": job.id,
        "triggered_by": triggered_by,
        "message": (
            "Archive rescrape job started. Each page is re-parsed from stored HTML; "
            "a completion report will be sent to superadmins when finished."
        ),
    }


# ---------------------------------------------------------------------------
# Service account endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/service-accounts/crawler",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Crawler service account info",
        forbidden=True,
    ),
)
async def get_crawler_service_account(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Return the crawler service account (admin only).

    This account is created on startup and is used as the default author for all
    crawler-created parts when no explicit user ID is provided.
    """
    user = db.query(DBUser).filter(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler service account not found. Restart the app to create it.",
        )
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_service_account": user.is_service_account,
        "created_at": user.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Background job status endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/jobs",
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
            live_job_ids=list(_job_tasks.keys()),
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
    "/jobs/{job_id}",
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
    "/jobs/{job_id}/crawler-progress",
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
        rows = (
            db.query(
                DBCrawledPage.source,
                func.count(DBCrawledPage.id),
                func.max(DBCrawledPage.last_parsed_at),
            )
            .filter(
                DBCrawledPage.source.in_(selected),
                DBCrawledPage.last_parsed_at.isnot(None),
                DBCrawledPage.last_parsed_at >= job.started_at,
            )
            .group_by(DBCrawledPage.source)
            .all()
        )
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
    "/jobs/{job_id}/cancel",
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
        stop_event = _job_stop_events.get(job_id)
        if stop_event is not None:
            stop_event.set()
            logger.info("Job #%s cancel: stop event signalled.", job_id)
        else:
            logger.warning("Job #%s cancel: no stop event or ECS task found (job may have already finished).", job_id)

    return BackgroundJobRead.model_validate(updated)


# ---------------------------------------------------------------------------


class DeleteAllPartsResponse(BaseModel):
    """Response for delete-all parts (admin only)."""

    deleted_count: int = Field(..., description="Number of parts deleted")


@router.post(
    "/parts/delete-all",
    response_model=DeleteAllPartsResponse,
    responses=standard_responses(
        success_description="All parts deleted",
        forbidden=True,
    ),
)
async def delete_all_parts(
    current_user: DBUser = Depends(get_current_admin_user),
) -> DeleteAllPartsResponse:
    """
    Delete all parts (admin only).

    Cascades to part listings, votes, reports, build list parts, and car associations.
    This action cannot be undone.
    """
    db = SessionLocal()
    try:
        parts = db.query(DBPart).all()
        count = len(parts)
        for part in parts:
            db.delete(part)
        db.commit()
        logger.info("Admin %s deleted all %s parts", current_user.id, count)
        return DeleteAllPartsResponse(deleted_count=count)
    except Exception as e:
        db.rollback()
        logger.exception("Delete all global parts failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    finally:
        db.close()


class DeleteAllPartManufacturersResponse(BaseModel):
    """Response for delete-all part manufacturers (admin only)."""

    deleted_count: int = Field(..., description="Number of part manufacturers deleted")


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
    return (
        db.query(DBPartListing)
        .filter(DBPartListing.part_id == part_id)
        .order_by(DBPartListing.created_at.asc())
        .first()
    )


def _link_group_member(db: Session, part: DBPart, canonical_id: UUID) -> CanonicalLinkGroupMember:
    from app.api.services.part_linker_service import score_metadata_richness

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
    "/parts/lookup-by-url",
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

    listings = (
        db.query(DBPartListing)
        .join(DBPart, DBPart.id == DBPartListing.part_id)
        .filter(DBPartListing.product_url == normalized)
        .order_by(DBPart.source.asc(), DBPart.created_at.asc())
        .all()
    )

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
    "/parts/{part_id}/link-group",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(success_description="Link group retrieved", not_found=True, forbidden=True),
)
async def get_part_link_group(
    part_id: UUID,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Return every part in the same link group as ``part_id``, with richness scores."""
    from app.api.services.part_linker_service import link_group_part_ids

    _ = current_user
    root = db.get(DBPart, part_id)
    if root is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    canonical_id = root.canonical_part_id or root.id
    member_ids = link_group_part_ids(db, part_id)
    parts = db.query(DBPart).filter(DBPart.id.in_(member_ids)).all()
    # Canonical first, then siblings by richness desc, created_at asc.
    from app.api.services.part_linker_service import score_metadata_richness

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
    "/parts/promote-canonical",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(success_description="Canonical re-elected", not_found=True, forbidden=True),
)
async def promote_part_to_canonical(
    body: PromoteCanonicalRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Make ``body.part_id`` the canonical of its link group. Safe on already-canonical parts."""
    from app.api.services.part_linker_service import reelect_canonical

    part = db.get(DBPart, body.part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    reelect_canonical(db, part)
    db.commit()
    logger.info("Admin %s promoted part %s to canonical", current_user.id, body.part_id)
    return await get_part_link_group(body.part_id, current_user=current_user, db=db)


@router.post(
    "/parts/unlink",
    response_model=CanonicalLinkGroupResponse,
    responses=standard_responses(success_description="Part unlinked", not_found=True, forbidden=True),
)
async def unlink_part_from_canonical(
    body: UnlinkPartRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> CanonicalLinkGroupResponse:
    """Detach ``body.part_id`` from its current link group so it becomes its own canonical."""
    from app.api.services.part_linker_service import unlink_part

    part = db.get(DBPart, body.part_id)
    if part is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    unlink_part(db, part)
    db.commit()
    logger.info("Admin %s unlinked part %s", current_user.id, body.part_id)
    return await get_part_link_group(body.part_id, current_user=current_user, db=db)


@router.post(
    "/parts/link",
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
    from app.api.services.part_linker_service import _point_siblings_at  # type: ignore[attr-defined]

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
    "/parts/rescan",
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
    from app.api.services.part_linker_service import (
        find_canonical_candidates,
        score_metadata_richness,
    )

    scanned = 0
    changes = 0
    diff_sample: List[RescanDiffEntry] = []

    def _record(entry: RescanDiffEntry) -> None:
        if len(diff_sample) < _RESCAN_DIFF_SAMPLE_CAP:
            diff_sample.append(entry)

    offset = 0
    batch_size = body.batch_size
    while True:
        batch = (
            db.query(DBPart).order_by(DBPart.created_at.asc(), DBPart.id.asc()).offset(offset).limit(batch_size).all()
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
                    from app.api.services.part_linker_service import reelect_canonical

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


@router.post(
    "/part-manufacturers/delete-all",
    response_model=DeleteAllPartManufacturersResponse,
    responses=standard_responses(
        success_description="All part manufacturers deleted",
        forbidden=True,
    ),
)
async def delete_all_part_manufacturers(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> DeleteAllPartManufacturersResponse:
    """
    Delete all part manufacturers (admin only).

    First nullifies part_manufacturer_id on all global parts, then deletes all part_manufacturers.
    This action cannot be undone.
    """
    try:
        # Nullify part_manufacturer_id on all global parts so we can delete part_manufacturers
        db.query(DBPart).filter(DBPart.part_manufacturer_id.isnot(None)).update(
            {DBPart.part_manufacturer_id: None}, synchronize_session=False
        )
        part_manufacturers = db.query(DBPartManufacturer).all()
        count = len(part_manufacturers)
        for part_manufacturer in part_manufacturers:
            db.delete(part_manufacturer)
        db.commit()
        logger.info("Admin %s deleted all %s part manufacturers", current_user.id, count)
        return DeleteAllPartManufacturersResponse(deleted_count=count)
    except Exception as e:
        db.rollback()
        logger.exception("Delete all part manufacturers failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
