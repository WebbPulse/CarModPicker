"""
Car service that extends BaseCRUDService to eliminate redundancy.
"""

import logging
from typing import List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.models.car import Car as DBCar
from app.api.models.car_model import CarModel
from app.api.models.make import Make
from app.api.models.user import User as DBUser
from app.api.schemas.car import CarCreate, CarRead, CarUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.common_operations import (
    apply_pagination_and_ordering,
    delete_entity,
    validate_pagination_params,
    verify_entity_access,
    verify_entity_exists,
)


def _car_query_with_make_model(db: Session):
    """Base query for Car with car_model and make eager-loaded (for make/model properties)."""
    return db.query(DBCar).options(
        joinedload(DBCar.car_model).joinedload(CarModel.make),
    )


class CarService(BaseCRUDService[DBCar, CarCreate, CarRead, CarUpdate]):
    """
    Car service that provides CRUD operations for cars.

    This service eliminates redundancy by extending BaseCRUDService
    and only implementing car-specific logic. Make/model filtering uses
    joins to Make and CarModel.
    """

    def __init__(self) -> None:
        """Initialize the car service."""
        super().__init__(
            model=DBCar,
            entity_name="car",
        )

    def get_by_id(
        self,
        db: Session,
        entity_id: int,
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> DBCar:
        """Get car by ID with car_model and make loaded (for make/model properties)."""
        if current_user and not allow_public:
            verify_entity_access(db, self.model, entity_id, current_user, self.entity_name, allow_public)
        else:
            verify_entity_exists(db, self.model, entity_id, self.entity_name)

        car = _car_query_with_make_model(db).filter(DBCar.id == entity_id).first()
        if car is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"{self.entity_name.title()} not found")
        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id}")
        return car

    def list_all(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[dict] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        order_by: str = "created_at",
        order_direction: str = "desc",
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCar]:
        """List cars with car_model and make loaded. Ignores make/model filters (use get_cars_by_make_model)."""
        validate_pagination_params(skip, limit)
        query = _car_query_with_make_model(db)

        # Search: make, model (via join), generation_name
        if search and search_fields:
            if "make" in search_fields or "model" in search_fields or "generation_name" in search_fields:
                query = query.join(DBCar.car_model).join(CarModel.make)
                conditions = []
                if "make" in search_fields:
                    conditions.append(Make.name.ilike(f"%{search}%"))
                if "model" in search_fields:
                    conditions.append(CarModel.name.ilike(f"%{search}%"))
                if "generation_name" in search_fields:
                    conditions.append(DBCar.generation_name.ilike(f"%{search}%"))
                if conditions:
                    query = query.filter(or_(*conditions))

        query = apply_pagination_and_ordering(query, skip, limit, order_by, order_direction)
        entities = query.all()
        if logger:
            logger.info(f"Retrieved {len(entities)} {self.entity_name} entities")
        return entities

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
        Get cars filtered by make and/or model (via joins to Make and CarModel).
        """
        validate_pagination_params(skip, limit)
        query = _car_query_with_make_model(db).join(DBCar.car_model).join(CarModel.make)

        if make:
            query = query.filter(Make.name == make)
        if model:
            query = query.filter(CarModel.name == model)

        query = apply_pagination_and_ordering(query, skip, limit, "created_at", "desc")
        entities = query.all()
        if logger:
            logger.info(f"Retrieved {len(entities)} cars by make/model")
        return entities

    def search_cars(
        self,
        db: Session,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCar]:
        """
        Search cars by make, model (via join), or generation name.
        """
        validate_pagination_params(skip, limit)
        query = (
            _car_query_with_make_model(db)
            .join(DBCar.car_model)
            .join(CarModel.make)
            .filter(
                or_(
                    Make.name.ilike(f"%{search_term}%"),
                    CarModel.name.ilike(f"%{search_term}%"),
                    DBCar.generation_name.ilike(f"%{search_term}%"),
                )
            )
        )
        query = apply_pagination_and_ordering(query, skip, limit, "created_at", "desc")
        entities = query.all()
        if logger:
            logger.info(f"Retrieved {len(entities)} cars for search")
        return entities

    def delete(
        self,
        db: Session,
        entity_id: int,
        current_user: DBUser,
        logger: Optional[logging.Logger] = None,
    ) -> DBCar:
        """
        Delete a car (admin only, no ownership check since cars are centrally managed).
        """
        if logger is None:
            logger = logging.getLogger(__name__)

        car = self.get_by_id(
            db=db,
            entity_id=entity_id,
            allow_public=True,
            logger=logger,
        )

        delete_entity(
            db=db,
            entity=car,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )
        return car
