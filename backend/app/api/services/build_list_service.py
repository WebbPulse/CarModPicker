"""
Build list service that extends the base CRUD service.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.api.models.build_list import BuildList as DBBuildList
from app.api.models.build_list_part import BuildListPart as DBBuildListPart
from app.api.models.build_log import BuildLog as DBBuildLog
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
        build_list = super().create(
            db=db,
            data=data,
            current_user=current_user,
            logger=logger,
            additional_data=additional_data,
        )

        # Auto-create a build log thread for this build list
        build_log = DBBuildLog(
            build_list_id=build_list.id,
            title=f"Build Log: {build_list.name}",
        )
        db.add(build_log)
        db.flush()

        logger.info(f"Auto-created build log thread {build_log.id} for build list {build_list.id}")

        return build_list

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

    def delete(
        self,
        db: Session,
        entity_id: int,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> Dict[str, str]:
        """
        Delete a build list and all its associated parts.

        This method ensures that all build list parts are deleted before
        deleting the build list itself to maintain data integrity.

        Args:
            db: Database session
            entity_id: ID of the build list to delete
            current_user: Current authenticated user
            logger: Logger instance

        Returns:
            Success message

        Raises:
            HTTPException: If build list not found, access denied, or deletion fails
        """
        from app.api.utils.common_operations import delete_entity, verify_entity_ownership

        # Verify ownership
        build_list = verify_entity_ownership(db, DBBuildList, entity_id, current_user, self.entity_name)

        # Delete all associated build list parts first
        # This ensures proper cascade deletion and avoids foreign key constraint violations
        build_list_parts = db.query(DBBuildListPart).filter(DBBuildListPart.build_list_id == entity_id).all()
        for part in build_list_parts:
            db.delete(part)

        # Commit the deletion of parts before deleting the build list
        db.flush()

        # Now delete the build list itself
        return delete_entity(
            db=db,
            entity=build_list,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
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

    def copy_build_list(
        self,
        db: Session,
        build_list_id: int,
        current_user: DBUser,
        logger: logging.Logger,
        new_name: Optional[str] = None,
    ) -> DBBuildList:
        """
        Copy a build list and all its parts for the current user.

        This method creates completely new, independent entities:
        - A new BuildList entity with a new primary key
        - New BuildListPart entities (one for each original part) with new primary keys
        - Each new BuildListPart references the same GlobalPart (by global_part_id)
          but is a separate entity in the database

        This ensures that modifications or deletions to the original build list
        or its parts do not affect the copied build list, as they are completely
        independent entities in separate dependency chains.

        Args:
            db: Database session
            build_list_id: ID of the build list to copy
            current_user: Current authenticated user (will own the copy)
            logger: Logger instance
            new_name: Optional new name for the copied build list. If not provided,
                     defaults to "Copy of {original_name}"

        Returns:
            The newly created build list copy

        Raises:
            HTTPException: If build list not found or copy fails
        """
        # Get the original build list
        original_build_list = verify_entity_exists(db, DBBuildList, build_list_id, "build list")

        # Generate the new name
        if new_name is None:
            new_name = f"Copy of {original_build_list.name}"

        # Create a NEW BuildList entity (new primary key, independent entity)
        new_build_list = DBBuildList(
            name=new_name,
            description=original_build_list.description,
            car_id=original_build_list.car_id,
            image_url=original_build_list.image_url,
            user_id=current_user.id,
        )
        db.add(new_build_list)
        db.flush()  # Get the ID without committing yet

        # Auto-create a build log thread for the copied build list
        build_log = DBBuildLog(
            build_list_id=new_build_list.id,
            title=f"Build Log: {new_build_list.name}",
        )
        db.add(build_log)
        db.flush()

        # Get all build list parts from the original build list
        original_parts = db.query(DBBuildListPart).filter(DBBuildListPart.build_list_id == build_list_id).all()

        # Create NEW BuildListPart entities for each original part
        # Each new part is a completely separate entity with its own primary key
        # They reference the same GlobalPart entities (by global_part_id) but are
        # independent relationship entities, ensuring separate dependency chains
        for original_part in original_parts:
            # Create a new BuildListPart entity (new primary key, independent from original)
            new_part = DBBuildListPart(
                build_list_id=new_build_list.id,  # Points to the new build list
                global_part_id=original_part.global_part_id,  # References same global part (correct - we share global parts)
                added_by=current_user.id,  # New owner
                quantity=original_part.quantity,  # Copy the quantity value
                notes=original_part.notes,  # Copy the notes value
                # added_at will be set automatically by the model's default
            )
            db.add(new_part)

        db.commit()
        db.refresh(new_build_list)

        logger.info(
            f"User {current_user.id} copied build list {build_list_id} to new build list {new_build_list.id} "
            f"with {len(original_parts)} new independent build list part entities"
        )

        return new_build_list
