"""
Base service class for CRUD operations to eliminate code duplication.
"""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.api.models.user import User as DBUser
from app.api.protocols import BaseModel, HasModelDump
from app.api.utils.common_operations import (
    create_entity,
    delete_entity,
    get_entities_with_pagination,
    update_entity,
    validate_pagination_params,
    verify_entity_access,
    verify_entity_exists,
    verify_entity_ownership,
)

# Generic types for different models and schemas
# ModelType must have an 'id' attribute at minimum
ModelType = TypeVar("ModelType", bound=BaseModel)
# Schema types are bound to HasModelDump to ensure they have the model_dump method
CreateSchema = TypeVar("CreateSchema", bound=HasModelDump)
ReadSchema = TypeVar("ReadSchema")
UpdateSchema = TypeVar("UpdateSchema", bound=HasModelDump)


class BaseCRUDService(Generic[ModelType, CreateSchema, ReadSchema, UpdateSchema]):
    """
    Base service class for CRUD operations.

    This class provides common CRUD functionality for all entity types
    to eliminate code duplication across different endpoints.
    """

    def __init__(
        self,
        model: Type[ModelType],
        entity_name: str = "entity",
    ):
        """
        Initialize the base CRUD service.

        Args:
            model: The SQLAlchemy model class
            entity_name: Human-readable name of the entity type
        """
        self.model = model
        self.entity_name = entity_name

    def create(
        self,
        db: Session,
        data: CreateSchema,
        current_user: DBUser,
        logger: logging.Logger,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """
        Create a new entity.

        Args:
            db: Database session
            data: Entity creation data
            current_user: Current authenticated user
            logger: Logger instance
            additional_data: Additional data to include (e.g., user_id)

        Returns:
            The created entity

        Raises:
            HTTPException: If creation fails
        """
        # Prepare data for creation
        # CreateSchema is bound to HasModelDump, so model_dump() is available
        entity_data = data.model_dump()

        # Add user_id if the model has a user_id field
        if hasattr(self.model, "user_id"):
            entity_data["user_id"] = current_user.id

        if additional_data:
            entity_data.update(additional_data)

        return create_entity(
            db=db,
            model=self.model,
            data=entity_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def get_by_id(
        self,
        db: Session,
        entity_id: UUID,
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> ModelType:
        """
        Get an entity by ID.

        Args:
            db: Database session
            entity_id: ID of the entity
            current_user: Current authenticated user (optional)
            allow_public: Whether to allow public access
            logger: Logger instance (optional)

        Returns:
            The found entity

        Raises:
            HTTPException: If entity not found or access denied
        """
        if current_user and not allow_public:
            entity = verify_entity_access(db, self.model, entity_id, current_user, self.entity_name, allow_public)
        else:
            entity = verify_entity_exists(db, self.model, entity_id, self.entity_name)

        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id}")

        return entity

    def get_by_user(
        self,
        db: Session,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        logger: Optional[logging.Logger] = None,
    ) -> List[ModelType]:
        """
        Get entities owned by a specific user.

        Args:
            db: Database session
            user_id: ID of the user
            skip: Number of records to skip
            limit: Maximum number of records to return
            logger: Logger instance (optional)

        Returns:
            List of entities
        """
        validate_pagination_params(skip, limit)

        filters = {"user_id": user_id}
        entities = get_entities_with_pagination(
            db=db,
            model=self.model,
            skip=skip,
            limit=limit,
            filters=filters,
            logger=logger,
        )

        return entities

    def list_all(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        order_by: str = "created_at",
        order_direction: str = "desc",
        logger: Optional[logging.Logger] = None,
    ) -> List[ModelType]:
        """
        List all entities with pagination, filtering, and search.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Dictionary of field names and values to filter by
            search: Search term to look for
            search_fields: List of field names to search in
            order_by: Field to order by
            order_direction: Order direction ('asc' or 'desc')
            logger: Logger instance (optional)

        Returns:
            List of entities
        """
        validate_pagination_params(skip, limit)

        entities = get_entities_with_pagination(
            db=db,
            model=self.model,
            skip=skip,
            limit=limit,
            filters=filters,
            search=search,
            search_fields=search_fields,
            order_by=order_by,
            order_direction=order_direction,
            logger=logger,
        )

        return entities

    def update(
        self,
        db: Session,
        entity_id: UUID,
        data: UpdateSchema,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> ModelType:
        """
        Update an existing entity.

        Args:
            db: Database session
            entity_id: ID of the entity to update
            data: Entity update data
            current_user: Current authenticated user
            logger: Logger instance

        Returns:
            The updated entity

        Raises:
            HTTPException: If entity not found, access denied, or update fails
        """
        # Verify ownership
        entity = verify_entity_ownership(db, self.model, entity_id, current_user, self.entity_name)

        # Update the entity
        # UpdateSchema is bound to HasModelDump, so model_dump() is available
        update_data = data.model_dump(exclude_unset=True)
        return update_entity(
            db=db,
            entity=entity,
            update_data=update_data,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def delete(
        self,
        db: Session,
        entity_id: UUID,
        current_user: DBUser,
        logger: logging.Logger,
    ) -> Dict[str, str]:
        """
        Delete an entity.

        Args:
            db: Database session
            entity_id: ID of the entity to delete
            current_user: Current authenticated user
            logger: Logger instance

        Returns:
            Success message

        Raises:
            HTTPException: If entity not found, access denied, or deletion fails
        """
        # Verify ownership
        entity = verify_entity_ownership(db, self.model, entity_id, current_user, self.entity_name)

        # Delete the entity
        return delete_entity(
            db=db,
            entity=entity,
            user_id=current_user.id,
            logger=logger,
            entity_name=self.entity_name,
        )

    def count_all(self, db: Session, logger: Optional[logging.Logger] = None) -> int:
        """
        Count all entities.

        Args:
            db: Database session
            logger: Logger instance (optional)

        Returns:
            Total count of entities
        """
        count = db.query(self.model).count()

        if logger:
            logger.info(f"Total {self.entity_name} count: {count}")

        return count

    def count_by_user(self, db: Session, user_id: UUID, logger: Optional[logging.Logger] = None) -> int:
        """
        Count entities owned by a specific user.

        Args:
            db: Database session
            user_id: ID of the user
            logger: Logger instance (optional)

        Returns:
            Count of entities
        """
        # Check if model has user_id attribute
        if not hasattr(self.model, "user_id"):
            raise AttributeError(f"Model {self.model.__name__} does not have a user_id attribute")

        # Use getattr for dynamic attribute access
        count = db.query(self.model).filter(getattr(self.model, "user_id") == user_id).count()

        if logger:
            logger.info(f"Counted {count} {self.entity_name}s for user {user_id}")

        return count

    def exists(self, db: Session, entity_id: UUID, logger: Optional[logging.Logger] = None) -> bool:
        """
        Check if an entity exists.

        Args:
            db: Database session
            entity_id: ID of the entity
            logger: Logger instance (optional)

        Returns:
            True if entity exists, False otherwise
        """
        # Use getattr for dynamic attribute access
        exists = db.query(self.model).filter(getattr(self.model, "id") == entity_id).first() is not None

        if logger:
            logger.info(f"Entity {self.entity_name} {entity_id} exists: {exists}")

        return exists

    def get_with_relations(
        self,
        db: Session,
        entity_id: UUID,
        relations: List[str],
        current_user: Optional[DBUser] = None,
        allow_public: bool = False,
        logger: Optional[logging.Logger] = None,
    ) -> ModelType:
        """
        Get an entity with related data loaded.

        Args:
            db: Database session
            entity_id: ID of the entity
            relations: List of relation names to load
            current_user: Current authenticated user (optional)
            allow_public: Whether to allow public access
            logger: Logger instance (optional)

        Returns:
            The found entity with relations loaded

        Raises:
            HTTPException: If entity not found or access denied
        """
        # Build query with relations
        query = db.query(self.model)
        for relation in relations:
            if hasattr(self.model, relation):
                query = query.options(joinedload(getattr(self.model, relation)))

        # Get entity - use getattr for dynamic attribute access
        entity = query.filter(getattr(self.model, "id") == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail=f"{self.entity_name.title()} not found")

        # Check access if user is provided
        if current_user and not allow_public:
            if hasattr(entity, "user_id") and getattr(entity, "user_id", None) != current_user.id:
                if not (current_user.is_admin or current_user.is_superuser):
                    raise HTTPException(
                        status_code=403,
                        detail=f"Not authorized to access this {self.entity_name}",
                    )

        if logger:
            logger.info(f"Retrieved {self.entity_name} {entity_id} with relations")

        return entity
