"""
Build list service that extends the base CRUD service.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.build_list import BuildListCreate, BuildListRead, BuildListUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.common_operations import verify_entity_exists
from app.core.logging import get_logger

logger = get_logger()


class BuildListService(BaseCRUDService[DBBuildList, BuildListCreate, BuildListRead, BuildListUpdate]):
    """Build list service that extends the base CRUD service."""

    def __init__(self) -> None:
        super().__init__(
            model=DBBuildList,
            entity_name="build list",
            subscription_check_method="can_create_build_list",
        )

    def create(
        self,
        db: Session,
        data: BuildListCreate,
        current_user: DBUser,
        logger: logging.Logger,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> DBBuildList:
        """
        Create a new build list, ensuring the associated car exists.

        Args:
            db: Database session
            data: Build list creation data
            current_user: Current authenticated user
            logger: Logger instance
            additional_data: Additional data to include

        Returns:
            The created build list

        Raises:
            HTTPException: If car not found or creation fails
        """
        # Verify the car exists
        verify_entity_exists(db, DBCar, data.car_id, "car")

        # Call parent create method
        return super().create(
            db=db,
            data=data,
            current_user=current_user,
            logger=logger,
            additional_data=additional_data,
        )

    def update(
        self,
        db: Session,
        entity_id: int,
        data: BuildListUpdate,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> DBBuildList:
        """
        Update a build list, ensuring the associated car exists if car_id is being updated.

        Args:
            db: Database session
            entity_id: ID of the build list to update
            data: Build list update data
            current_user: Current authenticated user
            logger: Logger instance

        Returns:
            The updated build list

        Raises:
            HTTPException: If car not found or update fails
        """
        # If car_id is being updated, verify the car exists (if not None)
        update_dict = data.model_dump(exclude_unset=True)
        if "car_id" in update_dict and update_dict["car_id"] is not None:
            verify_entity_exists(db, DBCar, update_dict["car_id"], "car")

        # Call parent update method
        return super().update(
            db=db,
            entity_id=entity_id,
            data=data,
            current_user=current_user,
            logger=logger,
        )

    def get_build_lists_by_car(
        self,
        db: Session,
        car_id: int,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBBuildList]:
        """Get build lists by car ID with pagination."""
        log = logger if logger is not None else get_logger()
        build_lists = db.query(DBBuildList).filter(DBBuildList.car_id == car_id).offset(skip).limit(limit).all()

        log.info(f"Retrieved {len(build_lists)} build lists for car {car_id}")
        return build_lists

    def get_build_lists_by_user(
        self,
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBBuildList]:
        """Get build lists by user ID with pagination."""
        log = logger if logger is not None else get_logger()
        build_lists = db.query(DBBuildList).filter(DBBuildList.user_id == user_id).offset(skip).limit(limit).all()

        log.info(f"Retrieved {len(build_lists)} build lists for user {user_id}")
        return build_lists

    def count_by_user(
        self,
        db: Session,
        user_id: int,
        logger: Optional[logging.Logger] = None,
    ) -> int:
        """Count build lists owned by a specific user."""
        log = logger if logger is not None else get_logger()
        count = db.query(DBBuildList).filter(DBBuildList.user_id == user_id).count()
        log.info(f"Counted {count} build lists for user {user_id}")
        return count
