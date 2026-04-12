"""
Admin endpoints for system management operations.

This module provides admin-only endpoints for system maintenance tasks
such as running database migrations, initializing seed data (car
generations, part categories), and running retailer crawlers.
"""

import asyncio
import logging
import os
import subprocess  # nosec B404 - Used safely for running database migrations
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.brand import Brand as DBBrand
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.car import Car as DBCar
from app.api.models.car_model import CarModel as DBCarModel
from app.api.models.category import Category as DBCategory
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.global_part_car import global_part_cars
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.make import Make as DBMake
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.report import Report as DBReport
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.utils.endpoint_decorators import standard_responses
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC, count_crawl_bucket_object_summary
from app.crawlers.runner import _resolve_crawler_user, _resolve_default_category_id, run_crawlers
from app.db.session import SessionLocal, get_db

logger = logging.getLogger(__name__)

router = APIRouter()

# Strong references to fire-and-forget tasks so they are not garbage-collected
# mid-execution. Tasks remove themselves on completion via add_done_callback.
_background_tasks: set[asyncio.Task[None]] = set()


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

    global_part_car_rows = db.query(func.count()).select_from(global_part_cars).scalar()
    global_part_car_count = int(global_part_car_rows or 0)

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
        "global_part_cars": global_part_car_count,
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
    global_part_cars links, then deletes all Car, CarModel, and Make rows so
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
    crawler_user_id: int = Field(
        ...,
        description="User ID to attribute crawler-created parts to (must have create permission).",
    )
    crawler_default_category_id: int = Field(
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
        description="If set, save full page HTML for post-processing (new URLs only unless crawl_html_save_on_recrawl is True).",
    )
    crawl_html_save_on_recrawl: Optional[bool] = Field(
        default=None,
        description="If True and crawl_html_save_dir is set, also overwrite saved HTML when recrawling known URLs.",
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


async def _run_crawlers_background(
    adapters: list[str],
    *,
    limits: Optional[Dict[str, int]] = None,
    global_limit: Optional[int] = None,
    parallel: bool,
    delay_sec: float,
    user_id: int,
    default_category_id: int,
    triggered_by_user_id: int,
    crawl_html_save_dir: Optional[str] = None,
    crawl_html_save_on_recrawl: Optional[bool] = None,
) -> None:
    """
    Run crawlers in a background thread. Logs completion or failure.
    Can be extended to send a completion report (e.g. via SES).
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
            crawl_html_save_dir=crawl_html_save_dir,
            crawl_html_save_on_recrawl=crawl_html_save_on_recrawl,
        )
        logger.info(
            "Crawler job completed (triggered by user %s): %s",
            triggered_by_user_id,
            result,
        )
        # TODO: Send completion report (e.g. SES) with result summary
    except Exception as e:
        logger.exception(
            "Crawler job failed (triggered by user %s): %s",
            triggered_by_user_id,
            e,
        )
        # TODO: Send failure notification (e.g. SES)


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
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Start retailer crawlers (admin only). Returns immediately after enqueueing the job.

    - Run individual crawlers or desired combinations.
    - Run all crawlers with adapters: ["all"].
    - Set per-crawler limits via limits: {"a90shop": 10, "example": 5}.
    - Set a global limit for all crawlers via global_limit.
    - When running more than one crawler, they run in parallel by default.
    - A completion report can be sent when the job finishes (e.g. via SES).
    """
    # Validate crawler user and category upfront so we return 400 instead of 200 + silent failure
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

    logger.info("Admin %s starting crawler job: %s", current_user.id, adapters)

    delay_sec = body.delay_sec if body.delay_sec is not None else DEFAULT_REQUEST_DELAY_SEC
    task = asyncio.create_task(
        _run_crawlers_background(
            adapters,
            limits=body.limits,
            global_limit=body.global_limit,
            parallel=body.parallel,
            delay_sec=delay_sec,
            user_id=body.crawler_user_id,
            default_category_id=body.crawler_default_category_id,
            triggered_by_user_id=current_user.id,
            crawl_html_save_dir=body.crawl_html_save_dir,
            crawl_html_save_on_recrawl=body.crawl_html_save_on_recrawl,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "status": "started",
        "adapters": adapters,
        "message": "Crawler job has been started. A completion report will be sent when finished.",
    }


class RescrapeArchivesRequest(BaseModel):
    """Request body for re-parsing all archived HTML into global parts (same as crawler ingest)."""

    crawler_user_id: int = Field(
        ...,
        description="User ID to attribute created/updated parts to (must exist and not be disabled).",
    )
    default_category_id: int = Field(
        ...,
        description="Fallback category ID when inference cannot pick a category.",
    )


def _rescrape_archives_background(
    *,
    crawler_user_id: int,
    default_category_id: int,
    triggered_by_user_id: int,
) -> None:
    """Re-parse every archived page in a background thread; logs per-outcome counts."""
    db = SessionLocal()
    try:
        crawler_user = _resolve_crawler_user(db, crawler_user_id)
        cat_id = _resolve_default_category_id(db, default_category_id)
        counts = run_rescrape_all_archived_pages(
            db,
            crawler_user=crawler_user,
            default_category_id=cat_id,
            log=logger,
        )
        logger.info(
            "Archive rescrape job completed (triggered by admin %s): %s",
            triggered_by_user_id,
            counts,
        )
    except Exception as e:
        logger.exception(
            "Archive rescrape job failed (triggered by admin %s): %s",
            triggered_by_user_id,
            e,
        )
    finally:
        db.close()


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
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Start a background job that re-parses every crawled page with stored HTML.

    For each row: load archived HTML, run the appropriate retailer parser (including
    extension-sourced URLs matched by host), then ``ingest_payload`` so parts are
    created/updated with full inference and listing refresh. Price history is updated
    when the parsed payload includes a price (same path as live crawls).

    HTML is stored under one canonical object per URL (``crawl_html/by_url/…``).
    """
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
    cat = db.query(DBCategory).filter(DBCategory.id == body.default_category_id).first()
    if not cat or not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"default_category_id={body.default_category_id}: not found or inactive.",
        )

    logger.info("Admin %s queued rescrape of all archived HTML pages", current_user.id)
    task = asyncio.create_task(
        asyncio.to_thread(
            _rescrape_archives_background,
            crawler_user_id=body.crawler_user_id,
            default_category_id=body.default_category_id,
            triggered_by_user_id=current_user.id,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "status": "started",
        "message": (
            "Archive rescrape job started. Each page is re-parsed from stored HTML; "
            "check server logs for parsed_ok / failed / skipped counts when the job finishes."
        ),
    }


class DeleteAllGlobalPartsResponse(BaseModel):
    """Response for delete-all global parts (admin only)."""

    deleted_count: int = Field(..., description="Number of global parts deleted")


@router.post(
    "/global-parts/delete-all",
    response_model=DeleteAllGlobalPartsResponse,
    responses=standard_responses(
        success_description="All global parts deleted",
        forbidden=True,
    ),
)
async def delete_all_global_parts(
    current_user: DBUser = Depends(get_current_admin_user),
) -> DeleteAllGlobalPartsResponse:
    """
    Delete all global parts (admin only).

    Cascades to part listings, votes, reports, build list parts, and car associations.
    This action cannot be undone.
    """
    db = SessionLocal()
    try:
        parts = db.query(DBGlobalPart).all()
        count = len(parts)
        for part in parts:
            db.delete(part)
        db.commit()
        logger.info("Admin %s deleted all %s global parts", current_user.id, count)
        return DeleteAllGlobalPartsResponse(deleted_count=count)
    except Exception as e:
        db.rollback()
        logger.exception("Delete all global parts failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
    finally:
        db.close()


class DeleteAllBrandsResponse(BaseModel):
    """Response for delete-all part brands (admin only)."""

    deleted_count: int = Field(..., description="Number of part brands deleted")


@router.post(
    "/brands/delete-all",
    response_model=DeleteAllBrandsResponse,
    responses=standard_responses(
        success_description="All part brands deleted",
        forbidden=True,
    ),
)
async def delete_all_brands(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> DeleteAllBrandsResponse:
    """
    Delete all part brands (admin only).

    First nullifies brand_id on all global parts, then deletes all brands.
    This action cannot be undone.
    """
    try:
        # Nullify brand_id on all global parts so we can delete brands
        db.query(DBGlobalPart).filter(DBGlobalPart.brand_id.isnot(None)).update(
            {DBGlobalPart.brand_id: None}, synchronize_session=False
        )
        brands = db.query(DBBrand).all()
        count = len(brands)
        for brand in brands:
            db.delete(brand)
        db.commit()
        logger.info("Admin %s deleted all %s part brands", current_user.id, count)
        return DeleteAllBrandsResponse(deleted_count=count)
    except Exception as e:
        db.rollback()
        logger.exception("Delete all part brands failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
