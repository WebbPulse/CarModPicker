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
    Type,
    TypedDict,
    TypeVar,
    cast,
)
from uuid import UUID

from fastapi import Depends
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.api.protocols import HasId, UserOwnedModel
from app.api.utils.response_patterns import ResponsePatterns
from app.db.dynamo.users import User as DBUser
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


# IN-03: ``validate_pagination_params`` lived in two modules with identical
# bodies. Kept the canonical definition in ``endpoint_decorators`` (which has
# the ``standard_pagination_params`` FastAPI dependency alongside it) and
# re-export from here so existing ``from common_patterns import
# validate_pagination_params`` call sites keep working without touching every
# endpoint module.
#
# WR-01 (Phase 7): this re-export points at the **clamping** variant in
# ``endpoint_decorators``. A second, semantically-different
# ``validate_pagination_params`` still lives in
# ``app.api.utils.common_operations`` (raises HTTPException on bad input
# instead of clamping) and is consumed by ``base_crud_service`` and
# ``car_generation_service``. The two functions share a name but have
# incompatible contracts — see the docstrings on each definition before
# attempting any further consolidation.
from app.api.utils.endpoint_decorators import validate_pagination_params as validate_pagination_params  # noqa: E402


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


# Vote-related patterns
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
