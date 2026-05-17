"""Admin database operations: migrations, data init, bulk delete."""

from __future__ import annotations

import logging
import os
import subprocess  # nosec B404 - Used safely for running database migrations
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car_generation import CarGeneration as DBCar
from app.api.models.car_make import CarMake as DBMake
from app.api.models.car_model import CarModel as DBCarModel
from app.api.models.part import Part as DBPart
from app.api.models.part_manufacturer import PartManufacturer as DBPartManufacturer
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.utils.endpoint_decorators import standard_responses
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
from app.db.session import SessionLocal, get_db

logger = logging.getLogger(__name__)
router = APIRouter()


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
    # This file is at: backend/app/api/endpoints/admin/db_ops.py
    # alembic.ini is at: backend/alembic.ini
    # So we need to go up 4 levels from this file (one more than pre-split)
    backend_dir = current_file.parent.parent.parent.parent.parent

    # Verify alembic.ini exists there
    alembic_ini = backend_dir / "alembic.ini"
    if alembic_ini.exists():
        return str(backend_dir)

    # Fallback: try current working directory
    if os.path.exists("alembic.ini"):
        return os.getcwd()

    # Last resort: use the calculated backend directory anyway
    return str(backend_dir)


def _init_result(success: bool, message: str) -> Dict[str, Any]:
    """Standard response for init endpoints."""
    return {"success": success, "message": message}


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
        db.execute(
            sql_update(DBBuildList)
            .where(DBBuildList.car_id.isnot(None))
            .values(car_id=None)
            .execution_options(synchronize_session=False)
        )
        # Remove votes that reference cars
        db.execute(
            sql_delete(DBVote)
            .where(DBVote.entity_type == "car_generation")
            .execution_options(synchronize_session=False)
        )
        count = db.scalar(select(func.count()).select_from(DBCar)) or 0
        db.execute(sql_delete(DBCar).execution_options(synchronize_session=False))
        car_models_count = db.scalar(select(func.count()).select_from(DBCarModel)) or 0
        db.execute(sql_delete(DBCarModel).execution_options(synchronize_session=False))
        makes_count = db.scalar(select(func.count()).select_from(DBMake)) or 0
        db.execute(sql_delete(DBMake).execution_options(synchronize_session=False))
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
        parts = list(db.scalars(select(DBPart)).all())
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


class DeleteCrawlerPartsResponse(BaseModel):
    """Response for delete crawler-created parts (admin only)."""

    deleted_count: int = Field(..., description="Number of parts deleted")
    service_account_count: int = Field(..., description="Number of service-account users whose parts were targeted")


@router.post(
    "/parts/delete-crawler-created",
    response_model=DeleteCrawlerPartsResponse,
    responses=standard_responses(
        success_description="Crawler-created parts deleted",
        forbidden=True,
    ),
)
async def delete_crawler_created_parts(
    current_user: DBUser = Depends(get_current_admin_user),
) -> DeleteCrawlerPartsResponse:
    """
    Delete all parts created by the legacy crawler service account (admin only).

    Targets only parts whose creator is a User with is_service_account=True.
    User-contributed and Chrome-extension parts are unaffected. Cascades to
    part listings, votes, reports, build list parts, and car associations.
    The service account user itself is not deleted. This action cannot be undone.
    """
    db = SessionLocal()
    try:
        service_account_ids = list(db.scalars(select(DBUser.id).where(DBUser.is_service_account.is_(True))).all())
        if not service_account_ids:
            logger.info(
                "Admin %s ran delete crawler-created parts: no service accounts found",
                current_user.id,
            )
            return DeleteCrawlerPartsResponse(deleted_count=0, service_account_count=0)
        parts = list(db.scalars(select(DBPart).where(DBPart.user_id.in_(service_account_ids))).all())
        count = len(parts)
        for part in parts:
            db.delete(part)
        db.commit()
        logger.info(
            "Admin %s deleted %s crawler-created parts from %s service account(s)",
            current_user.id,
            count,
            len(service_account_ids),
        )
        return DeleteCrawlerPartsResponse(
            deleted_count=count,
            service_account_count=len(service_account_ids),
        )
    except Exception as e:
        db.rollback()
        logger.exception("Delete crawler-created parts failed: %s", e)
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
        db.execute(
            sql_update(DBPart)
            .where(DBPart.part_manufacturer_id.isnot(None))
            .values(part_manufacturer_id=None)
            .execution_options(synchronize_session=False)
        )
        part_manufacturers = list(db.scalars(select(DBPartManufacturer)).all())
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
