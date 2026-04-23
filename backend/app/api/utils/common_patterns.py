"""
Common endpoint patterns to reduce redundancy across API endpoints.

This module provides reusable patterns for common operations like pagination,
ownership verification, admin checks, and standard query parameters.
"""

import logging
from collections.abc import Awaitable
from datetime import UTC, datetime
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    ParamSpec,
    Tuple,
    Type,
    TypedDict,
    TypeVar,
    cast,
)
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.user import User as DBUser
from app.api.protocols import HasId, HasUserId, UserOwnedModel
from app.api.utils.response_patterns import ResponsePatterns
from app.db.session import get_db

logger = logging.getLogger(__name__)

# TypeVar for decorator return types
P = ParamSpec("P")
T = TypeVar("T")
ModelT = TypeVar("ModelT", bound=HasId)


class PublicEndpointDeps(TypedDict):
    """Dependencies for public endpoints (no authentication required)."""

    db: Session
    logger: logging.Logger


class AuthenticatedEndpointDeps(TypedDict):
    """Dependencies for authenticated endpoints."""

    db: Session
    logger: logging.Logger
    current_user: DBUser


class AdminEndpointDeps(TypedDict):
    """Dependencies for admin-only endpoints."""

    db: Session
    logger: logging.Logger
    current_user: DBUser


# Standard pagination parameters
def get_standard_pagination_params(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of items to return"),
) -> Tuple[int, int]:
    """
    Standard pagination parameters for endpoints.

    Returns:
        Tuple of (skip, limit) values
    """
    return skip, limit


def validate_pagination_params(skip: int, limit: int) -> Tuple[int, int]:
    """
    Validate and normalize pagination parameters.

    Args:
        skip: Number of items to skip
        limit: Maximum number of items to return

    Returns:
        Tuple of validated (skip, limit) values
    """
    if skip < 0:
        skip = 0
    if limit < 1:
        limit = 1
    elif limit > 1000:
        limit = 1000

    return skip, limit


# Standard endpoint dependencies
def get_standard_endpoint_dependencies() -> Dict[str, Any]:
    """
    Standard dependencies for endpoints that need database and current user.

    Per QUAL-07 / 03-CONTEXT §D-34, endpoint modules take the logger via a
    module-level `logger = logging.getLogger(__name__)` declaration — NOT via
    FastAPI DI. This helper therefore omits the `logger` key; callers import
    `logging.getLogger(__name__)` at the top of their own module.

    Returns:
        Dictionary of Depends objects for FastAPI dependency injection
    """
    return {
        "db": Depends(get_db),
        "current_user": Depends(get_current_user),
    }


def get_standard_public_endpoint_dependencies(
    db: Session = Depends(get_db),
) -> PublicEndpointDeps:
    """
    Standard dependencies for public endpoints that need database and logger.

    Returns:
        Dictionary of standard dependencies
    """
    return {
        "db": db,
        "logger": logger,
    }


# Standard authorization patterns
def verify_user_access_or_admin(
    current_user: DBUser,
    target_user_id: UUID,
    action_description: str = "access this resource",
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Verify that the current user can access a resource or is an admin.

    Args:
        current_user: The authenticated user making the request
        target_user_id: The user ID of the resource owner
        action_description: Description of the action for error messages
        logger: Optional logger for warning messages
    """
    if current_user.id != target_user_id and not current_user.is_admin and not current_user.is_superuser:
        if logger:
            logger.warning(
                f"Access denied: User {current_user.id} " f"attempted to {action_description} for user {target_user_id}"
            )
        ResponsePatterns.raise_forbidden(f"Not authorized to {action_description}")


def verify_entity_ownership_or_admin(
    entity: HasUserId,
    current_user: DBUser,
    entity_name: str = "entity",
    action_description: str = "access this resource",
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Verify that the current user owns an entity or is an admin.

    Args:
        entity: The entity to check ownership of
        current_user: The authenticated user making the request
        entity_name: Name of the entity for error messages
        action_description: Description of the action for error messages
        logger: Optional logger for warning messages
    """
    if not entity:
        ResponsePatterns.raise_not_found(entity_name.title())

    if hasattr(entity, "user_id") and entity.user_id != current_user.id:
        if not current_user.is_admin and not current_user.is_superuser:
            if logger:
                logger.warning(
                    f"Access denied: User {current_user.id} "
                    f"attempted to {action_description} for {entity_name} "
                    f"{getattr(entity, 'id', 'unknown')} owned by user {entity.user_id}"
                )
            ResponsePatterns.raise_forbidden(f"Not authorized to {action_description}")


# Standard pagination response patterns
def get_paginated_response(
    db: Session,
    stmt: Select[Tuple[ModelT]],
    skip: int,
    limit: int,
    logger: logging.Logger,
    entity_name: str = "items",
    user_id: Optional[UUID] = None,
) -> List[ModelT]:
    """
    Get paginated response with consistent logging.

    Args:
        db: Database session
        stmt: SQLAlchemy Select statement
        skip: Number of items to skip
        limit: Maximum number of items to return
        logger: Logger instance
        entity_name: Name of the entity for logging
        user_id: Optional user ID for user-specific queries

    Returns:
        List of paginated items
    """
    items: List[ModelT] = list(db.scalars(stmt.offset(skip).limit(limit)).all())

    if not items:
        if user_id:
            logger.info(f"No {entity_name} found for user {user_id}")
        else:
            logger.info(f"No {entity_name} found")
    else:
        if user_id:
            logger.info(f"{entity_name.title()} retrieved for user {user_id}: " f"{len(items)} items")
        else:
            logger.info(f"{entity_name.title()} retrieved: {len(items)} items")

    return items


# Standard search and filter patterns
def apply_standard_filters(
    query: Select[Any],
    search: Optional[str] = None,
    category_id: Optional[UUID] = None,
    search_fields: Optional[List[str]] = None,
) -> Select[Any]:
    """
    Apply standard search and filter patterns to a Select statement.

    Args:
        query: SQLAlchemy Select statement
        search: Optional search term
        category_id: Optional category ID filter
        search_fields: List of fields to search in

    Returns:
        Modified Select statement
    """
    # Extract the entity class from the select statement
    entity_class = query.column_descriptions[0]["entity"]

    if category_id:
        query = query.where(getattr(entity_class, "category_id") == category_id)

    if search and search_fields:
        search_term = f"%{search}%"
        search_filters: List[ColumnElement[bool]] = []
        for field in search_fields:
            if hasattr(entity_class, field):
                search_filters.append(getattr(entity_class, field).ilike(search_term))

        if search_filters:
            from sqlalchemy import or_

            query = query.where(or_(*search_filters))

    return query


# Ownership verification decorator
def verify_ownership(
    entity_name: str,
    entity_id_param: str = "entity_id",
    user_id_field: str = "user_id",
    not_found_detail: Optional[str] = None,
    forbidden_detail: Optional[str] = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator for verifying entity ownership.

    Args:
        entity_name: Name of the entity for error messages
        entity_id_param: Name of the entity ID parameter
        user_id_field: Name of the user ID field in the entity model
        not_found_detail: Custom not found error detail
        forbidden_detail: Custom forbidden error detail

    Returns:
        Decorator function
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Extract parameters from kwargs with proper typing
            entity_id = kwargs.get(entity_id_param)
            db_value = kwargs.get("db")
            user_value = kwargs.get("current_user")

            if not all([entity_id, db_value, user_value]):
                raise ValueError(f"Missing required parameters for ownership verification: " f"{entity_name}")

            db = cast(Session, db_value)
            current_user = cast(DBUser, user_value)

            model_class = func.__annotations__["return"]
            entity = db.scalars(
                select(model_class).where(getattr(model_class, "id") == entity_id)
            ).first()

            if not entity:
                # IN-02: ``ResponsePatterns.raise_not_found`` builds its own message
                # from ``entity_name`` + ``entity_id`` — the ``not_found_detail``
                # override is intentionally unused here (kept on the decorator
                # signature for API compatibility with call sites that may pass
                # it; only ``forbidden_detail`` flows through below).
                ResponsePatterns.raise_not_found(entity_name, entity_id if isinstance(entity_id, UUID) else None)

            if getattr(entity, user_id_field) != current_user.id:
                detail = forbidden_detail or f"Not authorized to access this {entity_name}"
                ResponsePatterns.raise_forbidden(detail)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# Admin-only decorator
def admin_only(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
    """
    Decorator to ensure only admin users can access an endpoint.
    """

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        user_value = kwargs.get("current_user")
        if not user_value:
            ResponsePatterns.raise_forbidden("Admin access required")
        current_user = cast(DBUser, user_value)
        if not current_user.is_admin:
            ResponsePatterns.raise_forbidden("Admin access required")
        return await func(*args, **kwargs)

    return wrapper


# Common database operations
def get_entity_or_404(
    db: Session,
    model: Type[ModelT],
    entity_id: UUID,
    entity_name: str,
    logger: Optional[logging.Logger] = None,
) -> ModelT:
    """
    Get an entity by ID or raise 404 if not found.

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: Entity ID to find
        entity_name: Name of the entity for error messages
        logger: Optional logger for warnings

    Returns:
        Entity instance

    Raises:
        HTTPException: 404 if entity not found
    """
    entity = db.scalars(select(model).where(model.id == entity_id)).first()  # type: ignore[arg-type]
    if not entity:
        if logger:
            logger.warning(f"Attempt to access non-existent {entity_name} {entity_id}")
        ResponsePatterns.raise_not_found(entity_name, entity_id)
    return entity


def verify_entity_ownership(
    entity: UserOwnedModel,
    current_user: DBUser,
    entity_name: str,
    logger: Optional[logging.Logger] = None,
    custom_forbidden_detail: Optional[str] = None,
) -> None:
    """
    Verify that the current user owns the entity.

    Args:
        entity: Entity instance to check ownership
        current_user: Current authenticated user
        entity_name: Name of the entity for error messages
        logger: Optional logger for warnings
        custom_forbidden_detail: Custom forbidden error detail

    Raises:
        HTTPException: 403 if user doesn't own the entity
    """
    if entity.user_id != current_user.id:
        detail = custom_forbidden_detail or f"Not authorized to access this {entity_name}"
        if logger:
            logger.warning(
                f"User {current_user.id} attempted to access {entity_name} {entity.id} "
                f"owned by user {entity.user_id}"
            )
        ResponsePatterns.raise_forbidden(detail)


# Common query building
def build_search_query(
    query: Select[Any],
    search_term: Optional[str],
    search_fields: List[str],
) -> Select[Any]:
    """
    Build a search query with LIKE filters.

    Args:
        query: Base SQLAlchemy Select statement
        search_term: Search term to filter by
        search_fields: List of field names to search in

    Returns:
        Modified Select with search filters
    """
    if not search_term:
        return query

    search_filters: List[ColumnElement[bool]] = []
    for field in search_fields:
        search_filters.append(getattr(query.column_descriptions[0]["entity"], field).ilike(f"%{search_term}%"))

    if search_filters:
        from sqlalchemy import or_

        query = query.where(or_(*search_filters))

    return query


def build_filtered_query(
    query: Select[Any],
    filters: Dict[str, Any],
) -> Select[Any]:
    """
    Build a filtered query based on filter parameters.

    Args:
        query: Base SQLAlchemy Select statement
        filters: Dictionary of field names and values to filter by

    Returns:
        Modified Select with filters
    """
    for field_name, value in filters.items():
        if value is not None:
            if hasattr(query.column_descriptions[0]["entity"], field_name):
                field = getattr(query.column_descriptions[0]["entity"], field_name)
                query = query.where(field == value)

    return query


def build_sorted_query(
    query: Select[Any],
    sort_by: Optional[str],
    sort_order: str,
    allowed_sort_fields: List[str],
    default_sort: str = "id",
) -> Select[Any]:
    """
    Build a sorted query.

    Args:
        query: Base SQLAlchemy Select statement
        sort_by: Field name to sort by
        sort_order: Sort order (asc/desc)
        allowed_sort_fields: List of allowed field names for sorting
        default_sort: Default field to sort by

    Returns:
        Modified Select with sorting
    """
    if sort_by and sort_by in allowed_sort_fields:
        sort_field = getattr(query.column_descriptions[0]["entity"], sort_by)
    else:
        sort_field = getattr(query.column_descriptions[0]["entity"], default_sort)

    if sort_order.lower() == "desc":
        query = query.order_by(sort_field.desc())
    else:
        query = query.order_by(sort_field.asc())

    return query


# Common response patterns
def create_paginated_response(
    data: List[ModelT],
    total: int,
    skip: int,
    limit: int,
    message: str = "Data retrieved successfully",
) -> Dict[str, Any]:
    """
    Create a standardized paginated response.

    Args:
        data: List of items for current page
        total: Total number of items
        skip: Number of items skipped
        limit: Items per page
        message: Success message

    Returns:
        Dictionary with paginated response structure
    """
    total_pages = (total + limit - 1) // limit
    current_page = (skip // limit) + 1

    return {
        "success": True,
        "message": message,
        "data": data,
        "pagination": {
            "total": total,
            "total_items": total,
            "total_pages": total_pages,
            "current_page": current_page,
            "skip": skip,
            "limit": limit,
            "items_per_page": limit,
            "has_next": current_page < total_pages,
            "has_previous": current_page > 1,
        },
    }


# Common error handling
def handle_integrity_error(
    error: Exception,
    entity_name: str,
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Handle database integrity errors with standardized responses.

    Args:
        error: IntegrityError instance
        entity_name: Name of the entity for error messages
        logger: Optional logger for warnings

    Raises:
        HTTPException: Appropriate error response
    """
    if logger:
        logger.warning(f"IntegrityError during {entity_name} operation: {error}")

    error_detail_str = str(error).lower()

    # Check for common constraint violations
    if "unique constraint" in error_detail_str or "duplicate key" in error_detail_str:
        if "username" in error_detail_str:
            ResponsePatterns.raise_conflict("Username already exists", "USERNAME_EXISTS")
        elif "email" in error_detail_str:
            ResponsePatterns.raise_conflict("Email already exists", "EMAIL_EXISTS")
        else:
            ResponsePatterns.raise_conflict(f"{entity_name.title()} already exists", "DUPLICATE_ENTITY")
    else:
        ResponsePatterns.raise_bad_request(f"Data validation failed for {entity_name}")


# Common dependency injection
def get_common_dependencies() -> Dict[str, Any]:
    """
    Common dependencies for endpoints.

    Per QUAL-07 / 03-CONTEXT §D-34, the logger is obtained via a module-level
    `logger = logging.getLogger(__name__)` at the top of each endpoint module,
    not via FastAPI DI — so no `logger` key is returned here.

    Returns:
        Dictionary of Depends objects for FastAPI dependency injection
    """
    return {
        "db": Depends(get_db),
        "current_user": Depends(get_current_user),
    }


def get_admin_dependencies() -> Dict[str, Any]:
    """
    Admin-only dependencies for endpoints.

    Per QUAL-07 / 03-CONTEXT §D-34, the logger is obtained via a module-level
    `logger = logging.getLogger(__name__)` at the top of each endpoint module,
    not via FastAPI DI — so no `logger` key is returned here.

    Returns:
        Dictionary of Depends objects for FastAPI dependency injection
    """
    return {
        "db": Depends(get_db),
        "current_user": Depends(get_current_admin_user),
    }


# Vote-related patterns
def handle_vote_operation(
    db: Session,
    user_id: UUID,
    entity_id: UUID,
    vote_type: str,
    entity_model: Type[Any],
    vote_model: Type[Any],
    entity_name: str,
    entity_type: str,
    logger: logging.Logger,
    existing_vote: Optional[Any] = None,
) -> Any:
    """
    Handle vote operations (create/update) with consistent patterns for
    unified Vote model.

    Args:
        db: Database session
        user_id: ID of the user voting
        entity_id: ID of the entity being voted on
        vote_type: Type of vote (upvote/downvote)
        entity_model: Model class for the entity
        vote_model: Model class for the vote
        entity_name: Human-readable name of the entity
        entity_type: Entity type for polymorphic association
            ('car', 'build_list', 'part')
        logger: Logger instance
        existing_vote: Existing vote if updating

    Returns:
        The vote object (created or updated)
    """
    # Verify entity exists
    entity = db.scalars(select(entity_model).where(entity_model.id == entity_id)).first()
    if not entity:
        # IN-05: ``ResponsePatterns.raise_not_found`` is typed ``-> NoReturn``,
        # so nothing below executes when the entity is missing.
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    try:
        if existing_vote:
            # Update existing vote
            existing_vote.vote_type = vote_type
            db.commit()
            db.refresh(existing_vote)
            logger.info(f"Vote updated: {existing_vote.id} by user {user_id} " f"on {entity_name} {entity_id}")
            return existing_vote
        else:
            # Create new vote using polymorphic pattern
            new_vote = vote_model(
                user_id=user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                vote_type=vote_type,
            )
            db.add(new_vote)
            db.commit()
            db.refresh(new_vote)
            logger.info(f"Vote created: {new_vote.id} by user {user_id} " f"on {entity_name} {entity_id}")
            return new_vote
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to handle vote operation: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to process vote")


def remove_vote_operation(
    db: Session,
    user_id: UUID,
    entity_id: UUID,
    entity_model: Type[Any],
    vote_model: Type[Any],
    entity_name: str,
    entity_type: str,
    logger: logging.Logger,
) -> Dict[str, str]:
    """
    Handle vote removal with consistent patterns for unified Vote model.

    Args:
        db: Database session
        user_id: ID of the user removing vote
        entity_id: ID of the entity vote is being removed from
        entity_model: Model class for the entity
        vote_model: Model class for the vote
        entity_name: Human-readable name of the entity
        entity_type: Entity type for polymorphic association
            ('car', 'build_list', 'part')
        logger: Logger instance

    Returns:
        Success message
    """
    # Verify entity exists
    entity = db.scalars(select(entity_model).where(entity_model.id == entity_id)).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    # Find and remove vote using polymorphic pattern
    vote = db.scalars(
        select(vote_model).where(
            vote_model.user_id == user_id,
            vote_model.entity_type == entity_type,
            vote_model.entity_id == entity_id,
        )
    ).first()

    if not vote:
        ResponsePatterns.raise_not_found(f"Vote on {entity_name}")

    try:
        db.delete(vote)
        db.commit()
        logger.info(f"Vote removed: {vote.id} by user {user_id} on {entity_name} {entity_id}")
        return {"message": f"Vote on {entity_name} removed successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to remove vote: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to remove vote")


def get_vote_summary(
    db: Session,
    entity_id: UUID,
    entity_model: Type[Any],
    vote_model: Type[Any],
    entity_name: str,
    entity_type: str,
    logger: logging.Logger,
) -> Dict[str, Any]:
    """
    Get vote summary statistics for an entity using unified Vote model.

    Args:
        db: Database session
        entity_id: ID of the entity
        entity_model: Model class for the entity
        vote_model: Model class for the vote
        entity_name: Human-readable name of the entity
        entity_type: Entity type for polymorphic association
            ('car', 'build_list', 'part')
        logger: Logger instance

    Returns:
        Dictionary with vote statistics
    """
    # Verify entity exists
    entity = db.scalars(select(entity_model).where(entity_model.id == entity_id)).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    try:
        # Get vote counts using polymorphic pattern
        vote_counts = db.execute(
            select(vote_model.vote_type, func.count(vote_model.id).label("count"))
            .where(
                vote_model.entity_type == entity_type,
                vote_model.entity_id == entity_id,
            )
            .group_by(vote_model.vote_type)
        ).all()

        # Calculate totals
        upvotes = 0
        downvotes = 0
        for vote_type, count in vote_counts:
            if vote_type == "upvote":
                upvotes = count
            elif vote_type == "downvote":
                downvotes = count

        total_votes = upvotes + downvotes
        score = upvotes - downvotes

        logger.info(f"Retrieved vote summary for {entity_name} {entity_id}")
        return {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "total_votes": total_votes,
            "score": score,
        }
    except Exception as e:
        logger.error(f"Failed to get vote summary: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to get vote summary")


# Report-related patterns
def handle_report_creation(
    db: Session,
    user_id: UUID,
    entity_id: UUID,
    report_data: Dict[str, Any],
    entity_model: Type[Any],
    report_model: Type[Any],
    entity_name: str,
    entity_type: str,
    logger: logging.Logger,
    additional_filters: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Handle report creation with consistent patterns for unified Report model.

    Args:
        db: Database session
        user_id: ID of the user creating the report
        entity_id: ID of the entity being reported
        report_data: Report data dictionary
        entity_model: Model class for the entity
        report_model: Model class for the report
        entity_name: Human-readable name of the entity
        entity_type: Entity type for polymorphic association ('car', 'build_list', 'part')
        logger: Logger instance
        additional_filters: Additional filters for entity lookup

    Returns:
        The created report object
    """
    # Verify entity exists
    entity_stmt = select(entity_model).where(entity_model.id == entity_id)
    if additional_filters:
        for key, value in additional_filters.items():
            entity_stmt = entity_stmt.where(getattr(entity_model, key) == value)

    entity = db.scalars(entity_stmt).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    # Check if user has already reported this entity using polymorphic pattern
    existing_report = db.scalars(
        select(report_model).where(
            report_model.user_id == user_id,
            report_model.entity_type == entity_type,
            report_model.entity_id == entity_id,
        )
    ).first()

    if existing_report:
        ResponsePatterns.raise_conflict(f"User has already reported this {entity_name}")

    try:
        # Create new report using polymorphic pattern
        new_report = report_model(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            **report_data,
        )
        db.add(new_report)
        db.commit()
        db.refresh(new_report)

        logger.info(f"Report created: {new_report.id} by user {user_id} " f"on {entity_name} {entity_id}")
        return new_report
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create report: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to create report")


def get_reports_by_entity(
    db: Session,
    entity_id: UUID,
    entity_model: Type[Any],
    report_model: Type[Any],
    entity_name: str,
    entity_type: str,
    logger: logging.Logger,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
) -> List[Any]:
    """
    Get reports for a specific entity with pagination and filtering for
    unified Report model.

    Args:
        db: Database session
        entity_id: ID of the entity
        entity_model: Model class for the entity
        report_model: Model class for the report
        entity_name: Human-readable name of the entity
        entity_type: Entity type for polymorphic association ('car', 'build_list', 'part')
        logger: Logger instance
        skip: Number of reports to skip
        limit: Maximum number of reports to return
        status_filter: Optional status filter

    Returns:
        List of reports
    """
    # Verify entity exists
    entity = db.scalars(select(entity_model).where(entity_model.id == entity_id)).first()
    if not entity:
        ResponsePatterns.raise_not_found(entity_name, entity_id)

    try:
        # Query using polymorphic pattern
        reports_stmt = select(report_model).where(
            report_model.entity_type == entity_type,
            report_model.entity_id == entity_id,
        )

        if status_filter:
            reports_stmt = reports_stmt.where(report_model.status == status_filter)

        reports = list(db.scalars(reports_stmt.offset(skip).limit(limit)).all())

        logger.info(f"Retrieved {len(reports)} reports for {entity_name} {entity_id}")
        return reports
    except Exception as e:
        logger.error(f"Failed to get reports: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to get reports")


def update_report_status(
    db: Session,
    report_id: UUID,
    new_status: str,
    report_model: Type[Any],
    logger: logging.Logger,
    admin_user_id: UUID,
    resolution_notes: Optional[str] = None,
) -> Dict[str, str]:
    """
    Update report status with consistent patterns.

    Args:
        db: Database session
        report_id: ID of the report to update
        new_status: New status for the report
        report_model: Model class for the report
        logger: Logger instance
        admin_user_id: ID of the admin updating the report
        resolution_notes: Optional notes about the resolution

    Returns:
        Success message
    """
    report = db.scalars(select(report_model).where(report_model.id == report_id)).first()
    if not report:
        ResponsePatterns.raise_not_found("Report", report_id)

    # Type narrowing - report is guaranteed to exist here
    # The check above ensures report is not None, so we can safely proceed

    try:
        report.status = new_status
        report.resolved_at = datetime.now(UTC)
        report.resolved_by = admin_user_id

        if resolution_notes:
            report.resolution_notes = resolution_notes

        db.commit()

        logger.info(f"Report {report_id} status updated to {new_status} " f"by admin {admin_user_id}")
        return {"message": f"Report status updated to {new_status}"}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update report status: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to update report status")
