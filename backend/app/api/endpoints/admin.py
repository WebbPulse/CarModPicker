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
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.car import Car as DBCar
from app.api.models.car_model import CarModel as DBCarModel
from app.api.models.category import Category as DBCategory
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.make import Make as DBMake
from app.api.models.part import Part as DBPart
from app.api.models.part_car import part_cars
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
        db.query(DBVote).filter(DBVote.entity_type == "car").delete(synchronize_session=False)
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
    """Request body for running crawlers."""

    adapters: list[str] = Field(
        ...,
        description="Adapter names to run (e.g. ['a90shop']). Use ['all'] to run all adapters.",
    )
    crawler_user_id: Optional[UUID] = Field(
        default=None,
        description="User ID to attribute crawler-created parts to. Defaults to the crawler service account.",
    )
    crawler_default_category_id: UUID = Field(
        ...,
        description="Category ID for new parts.",
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
        description="Seconds between requests per crawler (default: 2.5). Use 5+ for conservative/large runs.",
    )
    crawl_html_save_dir: Optional[str] = Field(
        default=None,
        description="Kept for backward compatibility. HTML is always archived for every URL crawled.",
    )
    skip_known_urls: bool = Field(
        default=False,
        description="If True, URLs already in crawled_pages with parse_status='parsed' are skipped before the limit is applied.",
    )


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
    """
    adapters = list(ADAPTER_REGISTRY.keys())
    return {"adapters": adapters}


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

    env_overrides = [
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
) -> None:
    """
    Dev-only fallback: run crawlers in an asyncio background thread.
    Only used when ECS is not configured (i.e. local development).
    In production, _launch_ecs_crawler_task is always used instead.
    """
    try:
        result = await asyncio.to_thread(
            run_crawlers,
            adapters,
            limits=limits,
            global_limit=global_limit,
            parallel=parallel,
            delay_sec=delay_sec,
            user_id=user_id,
            default_category_id=default_category_id,
            stop_event=stop_event,
            skip_known_urls=skip_known_urls,
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
    cat = db.query(DBCategory).filter(DBCategory.id == body.crawler_default_category_id).first()
    if not cat or not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"crawler_default_category_id={body.crawler_default_category_id}: not found or inactive.",
        )

    adapters = body.adapters
    if adapters == ["all"]:
        adapters = list(ADAPTER_REGISTRY.keys())
    elif not adapters:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="adapters cannot be empty. Use ['all'] to run all crawlers.",
        )

    invalid = [a for a in adapters if a not in ADAPTER_REGISTRY]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown adapter(s): {invalid}. Available: {list(ADAPTER_REGISTRY.keys())}",
        )

    logger.info(
        "Crawler job starting: adapters=%s triggered_by=%s user=%s",
        adapters,
        triggered_by,
        acting_user_id,
    )

    delay_sec = body.delay_sec if body.delay_sec is not None else DEFAULT_REQUEST_DELAY_SEC

    job = job_service.create_job(
        db,
        job_type="crawler_run",
        triggered_by=triggered_by,
        params={
            "adapters": adapters,
            "limits": body.limits,
            "global_limit": body.global_limit,
            "parallel": body.parallel,
            "delay_sec": delay_sec,
            "crawler_user_id": str(crawler_user.id),
            "default_category_id": str(body.crawler_default_category_id),
            "skip_known_urls": body.skip_known_urls,
        },
        created_by_user_id=acting_user_id,
    )

    if settings.crawler_ecs_configured:
        # Production path: launch a Fargate task that spins up, runs, and tears down.
        try:
            task_arn = _launch_ecs_crawler_task(
                job_id=job.id,
                adapters=adapters,
                default_category_id=body.crawler_default_category_id,
                user_id=crawler_user.id,
                limits=body.limits,
                global_limit=body.global_limit,
                delay_sec=delay_sec,
                parallel=body.parallel,
                skip_known_urls=body.skip_known_urls,
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
                limits=body.limits,
                global_limit=body.global_limit,
                parallel=body.parallel,
                delay_sec=delay_sec,
                user_id=crawler_user.id,
                default_category_id=body.crawler_default_category_id,
                job_id=job.id,
                stop_event=stop_event,
                skip_known_urls=body.skip_known_urls,
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
            )
            job_service.complete_job(db, job_id, result_summary=counts)
            _notify_job_completion(job_id)
        except Exception as e:
            logger.exception("In-process archive rescrape job #%s failed: %s", job_id, e)
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            _notify_job_completion(job_id)
        finally:
            db.close()
            _job_tasks.pop(job_id, None)
            _job_stop_events.pop(job_id, None)

    await asyncio.to_thread(_blocking)


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
# Cron / EventBridge Scheduler management endpoints
# ---------------------------------------------------------------------------

_CRON_PRESETS: Dict[str, str] = {
    "monthly": "cron(0 2 1 * ? *)",  # 2 AM UTC on the 1st of each month
    "weekly": "cron(0 2 ? * MON *)",  # 2 AM UTC every Monday
    "daily": "cron(0 2 * * ? *)",  # 2 AM UTC every day
}


def _get_scheduler_client() -> Any:
    return boto3.client("scheduler", region_name=settings.AWS_REGION)


def _get_crawler_schedule() -> Dict[str, Any]:
    """
    Fetch the current crawler schedule from EventBridge Scheduler.
    Returns a simplified dict with enabled, schedule_expression, and preset.
    Raises HTTPException on AWS errors or when the scheduler is not configured.
    """
    name = settings.scheduler_crawler_schedule_name
    group = settings.SCHEDULER_GROUP_NAME
    if not name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler not configured (SCHEDULER_CRAWLER_SCHEDULE_NAME is empty).",
        )
    try:
        client = _get_scheduler_client()
        resp = client.get_schedule(Name=name, GroupName=group)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "ResourceNotFoundException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule '{name}' not found in EventBridge Scheduler.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AWS error fetching schedule: {e}",
        )
    except BotoCoreError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AWS connection error: {e}",
        )

    expression = resp.get("ScheduleExpression", "")
    enabled = resp.get("State", "DISABLED") == "ENABLED"
    preset = next((k for k, v in _CRON_PRESETS.items() if v == expression), "custom")
    return {
        "enabled": enabled,
        "schedule_expression": expression,
        "preset": preset,
        "presets": _CRON_PRESETS,
        "schedule_name": name,
        "group_name": group,
    }


@router.get(
    "/cron/crawler",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Current crawler cron schedule state",
        forbidden=True,
    ),
)
async def get_crawler_cron(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Return the current state of the EventBridge crawler cron schedule (admin only).

    Returns enabled status, the cron expression, and which preset it matches (if any).
    """
    return await asyncio.to_thread(_get_crawler_schedule)


class CrawlerCronUpdateRequest(BaseModel):
    """Request body for updating the crawler cron schedule."""

    enabled: Optional[bool] = Field(
        default=None,
        description="Set to true/false to enable or disable the schedule. Omit to leave unchanged.",
    )
    schedule_expression: Optional[str] = Field(
        default=None,
        description=(
            "EventBridge cron or rate expression (UTC), e.g. 'cron(0 2 1 * ? *)'. "
            "Use the preset name shorthand ('monthly', 'weekly', 'daily') or a full expression. "
            "Omit to leave unchanged."
        ),
    )
    preset: Optional[str] = Field(
        default=None,
        description="Shorthand preset: 'monthly', 'weekly', or 'daily'. Overrides schedule_expression if both are set.",
    )


@router.patch(
    "/cron/crawler",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Crawler cron schedule updated",
        forbidden=True,
    ),
)
async def update_crawler_cron(
    body: CrawlerCronUpdateRequest,
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Update the EventBridge crawler cron schedule (admin only).

    Can toggle enabled/disabled and change the schedule expression without a Terraform apply.
    All fields are optional — send only what you want to change.
    """
    if body.enabled is None and body.schedule_expression is None and body.preset is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of: enabled, schedule_expression, preset.",
        )

    def _do_update() -> Dict[str, Any]:
        current = _get_crawler_schedule()
        name = current["schedule_name"]
        group = current["group_name"]

        new_expression = current["schedule_expression"]
        new_state = "ENABLED" if current["enabled"] else "DISABLED"

        if body.preset is not None:
            if body.preset not in _CRON_PRESETS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown preset '{body.preset}'. Available: {list(_CRON_PRESETS)}",
                )
            new_expression = _CRON_PRESETS[body.preset]
        elif body.schedule_expression is not None:
            new_expression = body.schedule_expression

        if body.enabled is not None:
            new_state = "ENABLED" if body.enabled else "DISABLED"

        try:
            client = _get_scheduler_client()
            raw = client.get_schedule(Name=name, GroupName=group)
            # update_schedule requires all mandatory fields; carry over existing target/window.
            client.update_schedule(
                Name=name,
                GroupName=group,
                ScheduleExpression=new_expression,
                ScheduleExpressionTimezone=raw.get("ScheduleExpressionTimezone", "UTC"),
                State=new_state,
                FlexibleTimeWindow=raw["FlexibleTimeWindow"],
                Target=raw["Target"],
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AWS error updating schedule ({code}): {e}",
            )
        except BotoCoreError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AWS connection error: {e}",
            )

        logger.info(
            "Admin %s updated crawler cron schedule: state=%s expression=%s",
            current_user.id,
            new_state,
            new_expression,
        )
        return _get_crawler_schedule()

    return await asyncio.to_thread(_do_update)


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
    """
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
