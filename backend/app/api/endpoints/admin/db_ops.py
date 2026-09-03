"""Admin database operations: data init, bulk delete."""

from __future__ import annotations

import logging
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
from app.api.models.vote import Vote as DBVote
from app.api.utils.endpoint_decorators import standard_responses
from app.core.init_cars import init_car_generations
from app.core.init_categories import init_part_categories
from app.db.dynamo.users import User as DBUser
from app.db.session import SessionLocal, get_db

logger = logging.getLogger(__name__)
router = APIRouter()


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
