"""
Car service that extends BaseCRUDService to eliminate redundancy.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.api.models.car import Car as DBCar
from app.api.models.user import User as DBUser
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.common_operations import delete_entity


class CarService(BaseCRUDService[DBCar, CarCreate, CarRead, CarUpdate]):
    """
    Car service that provides CRUD operations for cars.

    This service eliminates redundancy by extending BaseCRUDService
    and only implementing car-specific logic.
    """

    def __init__(self) -> None:
        """Initialize the car service."""
        # Cars are now centrally managed, so no subscription check needed
        super().__init__(
            model=DBCar,
            entity_name="car",
            subscription_check_method=None,  # Cars are admin-managed, no subscription check
        )

    def get_cars_by_make_model(
        self,
        db: Session,
        make: Optional[str] = None,
        model: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCar]:
        """
        Get cars filtered by make and/or model.

        Args:
            db: Database session
            make: Car make to filter by
            model: Car model to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of cars matching the filters
        """
        filters: Dict[str, Any] = {}
        if make:
            filters["make"] = make
        if model:
            filters["model"] = model

        return self.list_all(
            db=db,
            skip=skip,
            limit=limit,
            filters=filters,
            logger=logger,
        )

    def search_cars(
        self,
        db: Session,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCar]:
        """
        Search cars by make, model, or generation name.

        Args:
            db: Database session
            search_term: Search term to look for
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of cars matching the search term
        """
        return self.list_all(
            db=db,
            skip=skip,
            limit=limit,
            search=search_term,
            search_fields=["make", "model", "generation_name"],
            logger=logger,
        )

    def delete(
        self,
        db: Session,
        entity_id: int,
        current_user: DBUser,
        logger: Optional[logging.Logger] = None,
    ) -> DBCar:
        """
        Delete a car (admin only, no ownership check since cars are centrally managed).

        Args:
            db: Database session
            entity_id: ID of the car to delete
            current_user: Current authenticated user (must be admin)
            logger: Logger instance

        Returns:
            The deleted car entity

        Raises:
            HTTPException: If car not found or deletion fails
        """
        # Get the car first (no ownership check since cars are centrally managed)
        car = self.get_by_id(
            db=db,
            entity_id=entity_id,
            allow_public=True,  # Public read, but delete requires admin (checked by endpoint)
            logger=logger,
        )

        # Delete the entity (returns a message dict, but we return the car object)
        delete_entity(
            db=db,
            entity=car,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

        # Return the car that was deleted
        return car
