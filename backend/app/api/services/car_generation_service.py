"""
CarGeneration service that extends BaseCRUDService to eliminate redundancy.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.api.models.car_generation import CarGeneration as DBCarGeneration
from app.api.models.car_make import CarMake
from app.api.models.car_model import CarModel
from app.api.models.user import User as DBUser
from app.api.schemas.car_generation import CarGenerationCreate, CarGenerationRead, CarGenerationUpdate
from app.api.services.base_crud_service import BaseCRUDService
from app.api.utils.common_operations import (
    apply_pagination_and_ordering,
    delete_entity,
    validate_pagination_params,
    verify_entity_access,
    verify_entity_exists,
)


def _car_generation_query_with_make_model(db: Session):
    """Base query for CarGeneration with car_model and car_make eager-loaded."""
    return db.query(DBCarGeneration).options(
        joinedload(DBCarGeneration.car_model).joinedload(CarModel.car_make),
    )


class CarGenerationService(
    BaseCRUDService[DBCarGeneration, CarGenerationCreate, CarGenerationRead, CarGenerationUpdate]
):
    """
    CarGeneration service that provides CRUD operations for car generations.

    car_make/car_model filtering uses joins to CarMake and CarModel.
    """

    def __init__(self) -> None:
        super().__init__(
            model=DBCarGeneration,
            entity_name="car_generation",
        )

    def get_by_id(
        self,
        db: Session,
        entity_id: UUID,
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> DBCarGeneration:
        """Get car generation by ID with car_model and car_make loaded."""
        if current_user and not allow_public:
            verify_entity_access(db, self.model, entity_id, current_user, self.entity_name, allow_public)
        else:
            verify_entity_exists(db, self.model, entity_id, self.entity_name)

        gen = _car_generation_query_with_make_model(db).filter(DBCarGeneration.id == entity_id).first()
        if gen is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"{self.entity_name.title()} not found")
        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id}")
        return gen

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
    ) -> List[DBCarGeneration]:
        """List car generations with car_model and car_make loaded."""
        validate_pagination_params(skip, limit)
        query = _car_generation_query_with_make_model(db)

        if search and search_fields:
            if (
                "car_make_name" in search_fields
                or "car_model_name" in search_fields
                or "generation_name" in search_fields
            ):
                query = query.join(DBCarGeneration.car_model).join(CarModel.car_make)
                conditions = []
                if "car_make_name" in search_fields:
                    conditions.append(CarMake.name.ilike(f"%{search}%"))
                if "car_model_name" in search_fields:
                    conditions.append(CarModel.name.ilike(f"%{search}%"))
                if "generation_name" in search_fields:
                    conditions.append(DBCarGeneration.generation_name.ilike(f"%{search}%"))
                if conditions:
                    query = query.filter(or_(*conditions))

        query = apply_pagination_and_ordering(query, skip, limit, order_by, order_direction)
        entities = query.all()
        if logger:
            logger.info(f"Retrieved {len(entities)} {self.entity_name} entities")
        return entities

    def get_by_ids(
        self,
        db: Session,
        ids: List[UUID],
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCarGeneration]:
        """Return car generations whose IDs are in the provided list."""
        if not ids:
            return []
        gens = _car_generation_query_with_make_model(db).filter(DBCarGeneration.id.in_(ids)).all()
        if logger:
            logger.info(f"Retrieved {len(gens)} car_generations by ID batch")
        return gens

    def get_car_generations_by_make_model(
        self,
        db: Session,
        car_make_name: Optional[str] = None,
        car_model_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCarGeneration]:
        """
        Get car generations filtered by car_make and/or car_model.
        """
        validate_pagination_params(skip, limit)
        query = _car_generation_query_with_make_model(db).join(DBCarGeneration.car_model).join(CarModel.car_make)

        if car_make_name:
            query = query.filter(CarMake.name == car_make_name)
        if car_model_name:
            query = query.filter(CarModel.name == car_model_name)

        query = apply_pagination_and_ordering(query, skip, limit, "created_at", "desc")
        entities = query.all()
        if logger:
            logger.info(f"Retrieved {len(entities)} car_generations by car_make/car_model")
        return entities

    def search_car_generations(
        self,
        db: Session,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[DBCarGeneration]:
        """
        Search car generations by car_make, car_model, or generation name.
        """
        validate_pagination_params(skip, limit)
        query = (
            _car_generation_query_with_make_model(db)
            .join(DBCarGeneration.car_model)
            .join(CarModel.car_make)
            .filter(
                or_(
                    CarMake.name.ilike(f"%{search_term}%"),
                    CarModel.name.ilike(f"%{search_term}%"),
                    DBCarGeneration.generation_name.ilike(f"%{search_term}%"),
                )
            )
        )
        query = apply_pagination_and_ordering(query, skip, limit, "created_at", "desc")
        entities = query.all()
        if logger:
            logger.info(f"Retrieved {len(entities)} car_generations for search")
        return entities

    def delete(
        self,
        db: Session,
        entity_id: UUID,
        current_user: DBUser,
        logger: Optional[logging.Logger] = None,
    ) -> DBCarGeneration:
        """
        Delete a car generation (admin only; no ownership check since managed centrally).
        """
        if logger is None:
            logger = logging.getLogger(__name__)

        gen = self.get_by_id(
            db=db,
            entity_id=entity_id,
            allow_public=True,
            logger=logger,
        )

        delete_entity(
            db=db,
            entity=gen,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )
        return gen
