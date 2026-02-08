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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.brand import Brand as DBBrand
from app.api.models.car import Car as DBCar
from app.api.models.category import Category as DBCategory
from app.api.models.global_part import GlobalPart as DBGlobalPart
from app.api.models.user import User as DBUser
from app.api.utils.endpoint_decorators import standard_responses
from app.core.car_inference import infer_car_generations, resolve_car_triples_to_ids
from app.core.category_inference import infer_category
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC
from app.crawlers.runner import run_crawlers
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
) -> None:
    """
    Run crawlers in a background thread. Logs completion or failure.
    Can be extended to send a completion report (e.g. via SendGrid).
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
        )
        logger.info(
            "Crawler job completed (triggered by user %s): %s",
            triggered_by_user_id,
            result,
        )
        # TODO: Send completion report (e.g. SendGrid) with result summary
    except Exception as e:
        logger.exception(
            "Crawler job failed (triggered by user %s): %s",
            triggered_by_user_id,
            e,
        )
        # TODO: Send failure notification (e.g. SendGrid)


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
    - A completion report can be sent when the job finishes (e.g. via SendGrid).
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
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "status": "started",
        "adapters": adapters,
        "message": "Crawler job has been started. A completion report will be sent when finished.",
    }


class RerunInferenceRequest(BaseModel):
    """Request body for rerunning inference on global parts."""

    reassign_brand: bool = Field(
        default=True,
        description="If True, try to infer brand from part name (e.g. 'Brand - Product' -> Brand). Only matches existing brands.",
    )


class RerunInferenceResponse(BaseModel):
    """Response for rerun-inference on global parts (admin only)."""

    updated_count: int = Field(..., description="Number of global parts updated")
    error_count: int = Field(..., description="Number of parts that failed to update")
    errors: List[str] = Field(default_factory=list, description="First 20 error messages if any")


def _infer_brand_from_name(db: Session, name: Optional[str]) -> Optional[int]:
    """
    Try to infer brand_id from part name. Looks for 'Brand - ' or 'Brand – ' prefix
    and matches against existing brands (case-insensitive). Returns brand id or None.
    """
    if not name or not name.strip():
        return None
    name = name.strip()
    for sep in (" - ", " – ", " — "):
        if sep in name:
            prefix = name.split(sep)[0].strip()
            if prefix:
                brand = db.query(DBBrand).filter(DBBrand.name.ilike(prefix)).first()
                if brand:
                    return brand.id
    return None


def _rerun_inference_impl(db: Session, reassign_brand: bool) -> Dict[str, Any]:
    """
    Rerun category, car, and optionally brand inference on all global parts.
    Returns dict with updated_count, error_count, errors (list of first 20 messages).
    """
    parts = db.query(DBGlobalPart).options(joinedload(DBGlobalPart.part_listings)).order_by(DBGlobalPart.id).all()
    # Resolve category by name (cache); always have "other" fallback
    categories_by_name: Dict[str, int] = {}
    other_cat = db.query(DBCategory).filter(DBCategory.name == "other", DBCategory.is_active).first()
    if other_cat:
        categories_by_name["other"] = other_cat.id

    updated_count = 0
    error_count = 0
    errors: List[str] = []
    max_errors = 20

    for part in parts:
        try:
            product_url: Optional[str] = None
            if part.part_listings:
                first_listing = next((pl for pl in part.part_listings if pl.product_url), None)
                if first_listing:
                    product_url = first_listing.product_url

            # Category
            inferred_cat = infer_category(part.name, part.description)
            cat_name = inferred_cat if inferred_cat else "other"
            if cat_name not in categories_by_name:
                cat = db.query(DBCategory).filter(DBCategory.name == cat_name, DBCategory.is_active).first()
                if cat:
                    categories_by_name[cat_name] = cat.id
                else:
                    cat_name = "other"
            if cat_name in categories_by_name:
                part.category_id = categories_by_name[cat_name]

            # Cars
            triples = infer_car_generations(part.name, part.description, product_url)
            car_ids = resolve_car_triples_to_ids(db, triples) if triples else []
            part.is_universal = not car_ids
            if car_ids:
                part.cars = [db.get(DBCar, cid) for cid in car_ids]
            else:
                part.cars = []

            # Brand (optional)
            if reassign_brand:
                inferred_brand_id = _infer_brand_from_name(db, part.name)
                if inferred_brand_id is not None:
                    part.brand_id = inferred_brand_id

            updated_count += 1
        except Exception as e:
            error_count += 1
            db.refresh(part)  # Discard partial ORM mutations so they are not committed
            if len(errors) < max_errors:
                errors.append(f"Part id={part.id} ({part.name[:50]}...): {e!s}")

    if updated_count > 0:
        db.commit()
    return {
        "updated_count": updated_count,
        "error_count": error_count,
        "errors": errors,
    }


@router.post(
    "/global-parts/rerun-inference",
    response_model=RerunInferenceResponse,
    responses=standard_responses(
        success_description="Inference rerun completed",
        forbidden=True,
    ),
)
async def rerun_global_parts_inference(
    body: RerunInferenceRequest,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> RerunInferenceResponse:
    """
    Rerun category, car, and optionally brand inference on all global parts (admin only).

    For each part, uses name + description (+ product_url from first listing) to infer:
    - category_id (from infer_category)
    - car associations and is_universal (from infer_car_generations + resolve)
    - brand_id (optional): if reassign_brand is True, infers from 'Brand - Product' name prefix using existing brands only.
    """
    try:
        logger.info(
            "Admin %s triggered rerun inference on all global parts (reassign_brand=%s)",
            current_user.id,
            body.reassign_brand,
        )
        result = await asyncio.to_thread(_rerun_inference_impl, db, body.reassign_brand)
        return RerunInferenceResponse(**result)
    except Exception as e:
        db.rollback()
        logger.exception("Rerun inference failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


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
