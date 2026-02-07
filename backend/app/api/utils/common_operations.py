"""
Common operations and utilities for API endpoints.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Type, TypeVar, cast

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session
from sqlalchemy.sql.elements import ColumnElement

from app.api.models.user import User as DBUser
from app.api.protocols import HasId

# Generic type for different models - bound to HasId protocol to ensure id attribute exists
ModelType = TypeVar("ModelType", bound=HasId)


def verify_entity_exists(db: Session, model: Type[ModelType], entity_id: int, entity_name: str = "entity") -> ModelType:
    """
    Verify that an entity exists in the database.

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: ID of the entity to verify
        entity_name: Human-readable name of the entity type

    Returns:
        The found entity

    Raises:
        HTTPException: If entity not found
    """
    entity = db.query(model).filter(model.id == entity_id).first()  # type: ignore[arg-type]
    if not entity:
        raise HTTPException(status_code=404, detail=f"{entity_name.title()} not found")
    return entity


def verify_entity_ownership(
    db: Session,
    model: Type[ModelType],
    entity_id: int,
    current_user: DBUser,
    entity_name: str = "entity",
) -> ModelType:
    """
    Verify that an entity exists and belongs to the current user.

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: ID of the entity to verify
        current_user: Current authenticated user
        entity_name: Human-readable name of the entity type

    Returns:
        The found entity

    Raises:
        HTTPException: If entity not found or not owned by user
    """
    entity = verify_entity_exists(db, model, entity_id, entity_name)

    if hasattr(entity, "user_id") and getattr(entity, "user_id", None) != current_user.id:
        raise HTTPException(
            status_code=403,
            detail=f"Not authorized to perform this action on this {entity_name}",
        )

    return entity


def verify_entity_access(
    db: Session,
    model: Type[ModelType],
    entity_id: int,
    current_user: DBUser,
    entity_name: str = "entity",
    allow_public: bool = False,
) -> ModelType:
    """
    Verify that an entity exists and user has access to it.

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: ID of the entity to verify
        current_user: Current authenticated user
        entity_name: Human-readable name of the entity type
        allow_public: Whether to allow public access (no ownership check)

    Returns:
        The found entity

    Raises:
        HTTPException: If entity not found or access denied
    """
    entity = verify_entity_exists(db, model, entity_id, entity_name)

    if not allow_public and hasattr(entity, "user_id"):
        if getattr(entity, "user_id", None) != current_user.id:
            raise HTTPException(
                status_code=403,
                detail=f"Not authorized to access this {entity_name}",
            )

    return entity


def verify_admin_access(current_user: DBUser) -> None:
    """
    Verify that the current user has admin access.

    Args:
        current_user: Current authenticated user

    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin access required")


def apply_pagination_and_ordering(
    query: Query[Any],
    skip: int = 0,
    limit: int = 100,
    order_by_field: str = "created_at",
    order_direction: str = "desc",
) -> Query[Any]:
    """
    Apply pagination and ordering to a database query.

    Args:
        query: Base query to modify
        skip: Number of records to skip
        limit: Maximum number of records to return
        order_by_field: Field to order by
        order_direction: Order direction ('asc' or 'desc')

    Returns:
        Modified query with pagination and ordering
    """
    # Apply ordering
    if hasattr(query.column_descriptions[0]["type"], order_by_field):
        order_field = getattr(query.column_descriptions[0]["type"], order_by_field)
        if order_direction.lower() == "desc":
            query = query.order_by(order_field.desc())
        else:
            query = query.order_by(order_field.asc())

    # Apply pagination
    return query.offset(skip).limit(limit)


def build_filtered_query(base_query: Query[Any], filters: Dict[str, Any]) -> Query[Any]:
    """
    Build a filtered query based on provided filters.

    Args:
        base_query: Base query to apply filters to
        filters: Dictionary of field names and values to filter by

    Returns:
        Query with applied filters
    """
    for field_name, value in filters.items():
        if value is not None:
            if hasattr(base_query.column_descriptions[0]["type"], field_name):
                field = getattr(base_query.column_descriptions[0]["type"], field_name)
                base_query = base_query.filter(field == value)

    return base_query


def build_search_query(base_query: Query[Any], search_term: str, search_fields: List[str]) -> Query[Any]:
    """
    Build a search query with ILIKE filters on multiple fields.

    Args:
        base_query: Base query to apply search to
        search_term: Search term to look for
        search_fields: List of field names to search in

    Returns:
        Query with search filters applied
    """
    if not search_term:
        return base_query

    from sqlalchemy import or_

    search_conditions: List[ColumnElement[bool]] = []
    model = base_query.column_descriptions[0]["type"]

    for field_name in search_fields:
        if hasattr(model, field_name):
            field = getattr(model, field_name)
            # Only apply ilike to actual columns (not relationships)
            if hasattr(field, "property") and hasattr(field.property, "columns"):
                # This is a column attribute, safe to use ilike
                search_conditions.append(field.ilike(f"%{search_term}%"))

    if search_conditions:
        base_query = base_query.filter(or_(*search_conditions))

    return base_query


def log_operation(
    logger: logging.Logger,
    operation: str,
    entity_type: str,
    entity_id: int,
    user_id: int,
    additional_info: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an operation with consistent formatting.

    Args:
        logger: Logger instance
        operation: Description of the operation performed
        entity_type: Type of entity being operated on
        entity_id: ID of the entity
        user_id: ID of the user performing the operation
        additional_info: Additional information to log
    """
    log_message = f"{operation}: {entity_type} {entity_id} by user {user_id}"

    if additional_info:
        log_message += f" - {additional_info}"

    logger.info(log_message)


def create_error_response(
    status_code: int, detail: str, additional_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a standardized error response.

    Args:
        status_code: HTTP status code
        detail: Error detail message
        additional_info: Additional error information

    Returns:
        Standardized error response dictionary
    """
    error_response: Dict[str, Any] = {
        "error": {
            "status_code": status_code,
            "detail": detail,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    }

    if additional_info:
        error_response["error"]["additional_info"] = additional_info

    return error_response


def validate_pagination_params(skip: int, limit: int, max_limit: int = 1000) -> None:
    """
    Validate pagination parameters.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        max_limit: Maximum allowed limit value

    Raises:
        HTTPException: If pagination parameters are invalid
    """
    if skip < 0:
        raise HTTPException(status_code=400, detail="Skip value must be non-negative")

    if limit < 1:
        raise HTTPException(status_code=400, detail="Limit value must be positive")

    if limit > max_limit:
        raise HTTPException(status_code=400, detail=f"Limit value cannot exceed {max_limit}")


def get_entity_details(db: Session, entity: HasId, detail_fields: List[str]) -> Dict[str, Any]:
    """
    Get additional details for an entity.

    Args:
        db: Database session
        entity: Entity to get details for
        detail_fields: List of field names to get details for

    Returns:
        Dictionary of entity details
    """
    details: Dict[str, Any] = {}

    for field_name in detail_fields:
        if hasattr(entity, field_name):
            field_value = getattr(entity, field_name)

            # If it's a foreign key, get the related entity
            if field_name.endswith("_id") and field_value:
                related_model_name = field_name.replace("_id", "")
                # This would need to be implemented based on your model structure
                # For now, just store the ID
                details[related_model_name] = field_value
            else:
                details[field_name] = field_value

    return details


def create_entity(
    db: Session,
    model: Type[ModelType],
    data: Dict[str, Any],
    user_id: int,
    logger: logging.Logger,
    entity_name: str = "entity",
) -> ModelType:
    """
    Create a new entity with consistent logging and error handling.

    Args:
        db: Database session
        model: SQLAlchemy model class
        data: Data to create entity with
        user_id: ID of the user creating the entity
        logger: Logger instance
        entity_name: Human-readable name of the entity type

    Returns:
        The created entity
    """
    from sqlalchemy.exc import IntegrityError

    try:
        db_entity = model(**data)
        db.add(db_entity)
        db.commit()
        db.refresh(db_entity)

        log_operation(
            logger=logger,
            operation="Created",
            entity_type=entity_name,
            entity_id=db_entity.id,
            user_id=user_id,
        )

        return db_entity
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Failed to create {entity_name}: {str(e)}")

        # Handle common integrity errors
        error_detail_str = str(e).lower()
        if "unique constraint" in error_detail_str or "duplicate" in error_detail_str:
            if "name" in error_detail_str:
                raise HTTPException(
                    status_code=400,
                    detail=f"{entity_name.title()} with this name already exists",
                )
            elif "email" in error_detail_str:
                raise HTTPException(
                    status_code=400,
                    detail=f"{entity_name.title()} with this email already exists",
                )
            else:
                raise HTTPException(status_code=400, detail=f"This {entity_name} already exists")
        else:
            raise HTTPException(status_code=400, detail=f"Data validation failed for {entity_name}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create {entity_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create {entity_name}")


def update_entity(
    db: Session,
    entity: ModelType,
    update_data: Dict[str, Any],
    user_id: int,
    logger: logging.Logger,
    entity_name: str = "entity",
) -> ModelType:
    """
    Update an existing entity with consistent logging and error handling.

    Args:
        db: Database session
        entity: Entity to update
        update_data: Data to update entity with
        user_id: ID of the user updating the entity
        logger: Logger instance
        entity_name: Human-readable name of the entity type

    Returns:
        The updated entity
    """
    from sqlalchemy.exc import IntegrityError

    try:
        # Handle image deletion if image_url is being updated
        if "image_url" in update_data and hasattr(entity, "image_url"):
            old_image_url = getattr(entity, "image_url", None)
            new_image_url = update_data["image_url"]

            # If the old image exists and is different from the new one, delete it
            if old_image_url and old_image_url != new_image_url:
                from app.api.services.storage_service import storage_service
                from app.api.utils.image_utils import is_file_key

                # Only delete if it's a file key (not a regular URL)
                if is_file_key(old_image_url):
                    try:
                        storage_service.delete_image(old_image_url)
                        logger.info(f"Deleted old image for {entity_name} {entity.id}: {old_image_url}")
                    except Exception as e:
                        # Log but don't fail the update if image deletion fails
                        logger.warning(f"Failed to delete old image for {entity_name} {entity.id}: {str(e)}")

                # Remove the deleted primary image from image_urls so the gallery does not
                # keep a broken reference (edit form often only sends image_url, not image_urls).
                if hasattr(entity, "image_urls") and "image_urls" not in update_data:
                    current_urls = cast(list[str], getattr(entity, "image_urls", None) or [])
                    if old_image_url in current_urls:
                        from app.api.schemas.global_part import MAX_IMAGES_PER_GLOBAL_PART

                        update_data["image_urls"] = [k for k in current_urls if k != old_image_url][
                            :MAX_IMAGES_PER_GLOBAL_PART
                        ]

        # Handle image_urls deletion when gallery is being updated
        if "image_urls" in update_data and hasattr(entity, "image_urls"):
            from app.api.schemas.global_part import MAX_IMAGES_PER_GLOBAL_PART
            from app.api.services.storage_service import storage_service
            from app.api.utils.image_utils import is_file_key

            old_urls = cast(list[str], getattr(entity, "image_urls", None) or [])
            new_urls = (update_data["image_urls"] or [])[:MAX_IMAGES_PER_GLOBAL_PART]
            update_data["image_urls"] = new_urls

            for old_key in old_urls:
                if old_key and old_key not in new_urls and is_file_key(old_key):
                    try:
                        storage_service.delete_image(old_key)
                        logger.info(f"Deleted old gallery image for {entity_name} {entity.id}: {old_key}")
                    except Exception as e:
                        logger.warning(f"Failed to delete gallery image for {entity_name} {entity.id}: {str(e)}")

        # Update model fields
        for key, value in update_data.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        db.add(entity)
        db.commit()
        db.refresh(entity)

        log_operation(
            logger=logger,
            operation="Updated",
            entity_type=entity_name,
            entity_id=entity.id,
            user_id=user_id,
        )

        return entity
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Failed to update {entity_name} {entity.id}: {str(e)}")

        # Handle common integrity errors
        error_detail_str = str(e).lower()
        if "unique constraint" in error_detail_str or "duplicate" in error_detail_str:
            if "name" in error_detail_str:
                raise HTTPException(
                    status_code=400,
                    detail=f"{entity_name.title()} with this name already exists",
                )
            elif "email" in error_detail_str:
                raise HTTPException(
                    status_code=400,
                    detail=f"{entity_name.title()} with this email already exists",
                )
            else:
                raise HTTPException(status_code=400, detail=f"This {entity_name} already exists")
        else:
            raise HTTPException(status_code=400, detail=f"Data validation failed for {entity_name}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update {entity_name} {entity.id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update {entity_name}")


def delete_entity(
    db: Session,
    entity: HasId,
    user_id: int,
    logger: logging.Logger,
    entity_name: str = "entity",
) -> Dict[str, str]:
    """
    Delete an entity with consistent logging and error handling.

    Args:
        db: Database session
        entity: Entity to delete
        user_id: ID of the user deleting the entity
        logger: Logger instance
        entity_name: Human-readable name of the entity type

    Returns:
        Success message
    """
    from sqlalchemy.exc import IntegrityError

    try:
        entity_id = getattr(entity, "id")

        # Delete associated images if they exist
        from app.api.services.storage_service import storage_service
        from app.api.utils.image_utils import is_file_key

        if hasattr(entity, "image_url"):
            image_url = getattr(entity, "image_url", None)
            if image_url:
                if is_file_key(image_url):
                    try:
                        storage_service.delete_image(image_url)
                        logger.info(f"Deleted image for {entity_name} {entity_id}: {image_url}")
                    except Exception as e:
                        logger.warning(f"Failed to delete image for {entity_name} {entity_id}: {str(e)}")

        if hasattr(entity, "image_urls"):
            image_urls = cast(list[str], getattr(entity, "image_urls", None) or [])
            for img_key in image_urls:
                if img_key and is_file_key(img_key):
                    try:
                        storage_service.delete_image(img_key)
                        logger.info(f"Deleted gallery image for {entity_name} {entity_id}: {img_key}")
                    except Exception as e:
                        logger.warning(f"Failed to delete gallery image for {entity_name} {entity_id}: {str(e)}")

        db.delete(entity)
        db.commit()

        log_operation(
            logger=logger,
            operation="Deleted",
            entity_type=entity_name,
            entity_id=entity_id,
            user_id=user_id,
        )

        return {"message": f"{entity_name.title()} deleted successfully"}
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Failed to delete {entity_name} {getattr(entity, 'id')}: {str(e)}")

        # Handle foreign key constraint errors
        error_detail_str = str(e).lower()
        if "foreign key" in error_detail_str or "constraint failed" in error_detail_str:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete {entity_name} because it is referenced by other records",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete {entity_name} due to data integrity constraints",
            )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete {entity_name} {getattr(entity, 'id')}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete {entity_name}")


def get_entities_with_pagination(
    db: Session,
    model: Type[ModelType],
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
    Get entities with pagination, filtering, search, and ordering.

    Args:
        db: Database session
        model: SQLAlchemy model class
        skip: Number of records to skip
        limit: Maximum number of records to return
        filters: Dictionary of field names and values to filter by
        search: Search term to look for
        search_fields: List of field names to search in
        order_by: Field to order by
        order_direction: Order direction ('asc' or 'desc')
        logger: Optional logger instance for logging

    Returns:
        List of entities
    """
    query = db.query(model)

    # Apply filters
    if filters:
        query = build_filtered_query(query, filters)

    # Apply search
    if search and search_fields:
        query = build_search_query(query, search, search_fields)

    # Apply pagination and ordering
    query = apply_pagination_and_ordering(query, skip, limit, order_by, order_direction)

    entities = query.all()

    if logger:
        logger.info(f"Retrieved {len(entities)} {model.__name__} entities")

    return entities
