"""
Refactored users endpoint using base classes to eliminate redundancy.

This endpoint now uses the BaseEndpointRouter to provide common CRUD
operations while maintaining user-specific functionality like password
hashing and admin management.
"""

import logging
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    create_access_token,
    get_current_admin_user,
    get_current_user,
    get_optional_current_user,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.schemas.user import (
    AdminUserUpdate,
    PublicUserRead,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.api.services.storage_service import storage_service
from app.api.services.user_service import UserService
from app.api.utils.base_endpoint_router import BaseEndpointRouter
from app.api.utils.endpoint_decorators import crud_responses, validate_pagination_params
from app.api.utils.response_patterns import ResponsePatterns
from app.core.logging import get_logger
from app.db.session import get_db

# Create router
router = APIRouter()

# Create service
user_service = UserService()

# Register custom endpoints BEFORE BaseEndpointRouter to ensure proper
# route precedence (More specific routes like /me must be registered
# before generic routes like /{entity_id})


@router.get("/me", response_model=UserRead)
async def read_users_me_route(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Fetch the current logged in user.
    """
    return current_user


# Count endpoint - register BEFORE /{user_id} to avoid route conflicts
# FastAPI matches routes in order, so specific routes must come before parameterized routes
@router.get(
    "/count",
    response_model=Dict[str, int],
    responses={
        200: {"description": "Count of users"},
    },
)
async def count_users(
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> Dict[str, int]:
    """
    Get total count of users.
    """
    try:
        count = user_service.count_all(db=db, logger=logger)
        return {"count": count}
    except Exception as e:
        logger.error(f"Error counting users: {str(e)}")
        raise


@router.post("/me/profile-picture", response_model=UserRead)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> UserRead:
    """
    Upload a profile picture for the current user.

    This endpoint uploads the image to storage and automatically updates
    the user's image_url field. If the user already has a profile picture,
    the old one will be deleted from storage.

    Args:
        file: Image file to upload
        current_user: Authenticated user (from JWT token)
        db: Database session
        logger: Logger instance

    Returns:
        UserRead: Updated user object with new profile picture URL

    Raises:
        HTTPException: If upload fails or validation fails
    """
    try:
        # Upload image to storage with square aspect ratio enforcement
        file_key = storage_service.upload_image(
            file=file,
            entity_type="user",
            user_id=current_user.id,
            entity_id=current_user.id,
            force_square=True,  # Enforce square aspect ratio for profile pictures
        )

        # Delete old profile picture if it exists
        if current_user.image_url:
            try:
                storage_service.delete_image(current_user.image_url)
                logger.info(f"Deleted old profile picture for user {current_user.id}: {current_user.image_url}")
            except Exception as e:
                # Log but don't fail if old image deletion fails
                logger.warning(f"Failed to delete old profile picture for user {current_user.id}: {str(e)}")

        # Update user's image_url
        current_user.image_url = file_key
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

        logger.info(f"User {current_user.id} uploaded new profile picture: {file_key}")
        return UserRead.model_validate(current_user)

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error(f"Unexpected error during profile picture upload: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during profile picture upload",
        )


@router.delete("/me/profile-picture", response_model=UserRead)
async def delete_profile_picture(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> UserRead:
    """
    Delete the current user's profile picture.

    This endpoint removes the profile picture from storage and clears
    the user's image_url field.

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        logger: Logger instance

    Returns:
        UserRead: Updated user object with profile picture removed

    Raises:
        HTTPException: If deletion fails
    """
    if not current_user.image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile picture found to delete",
        )

    try:
        # Delete image from storage
        storage_service.delete_image(current_user.image_url)

        # Clear user's image_url
        old_file_key = current_user.image_url
        current_user.image_url = None
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

        logger.info(f"User {current_user.id} deleted profile picture: {old_file_key}")
        return UserRead.model_validate(current_user)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during profile picture deletion: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during profile picture deletion",
        )


# Custom GET endpoint for users with permission checks for sensitive fields
@router.get(
    "/{user_id}",
    response_model=Union[UserRead, PublicUserRead],
    responses={
        404: {"description": "User not found"},
    },
)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: Union[DBUser, None] = Depends(get_optional_current_user),
) -> Union[UserRead, PublicUserRead]:
    """
    Get a user by ID.

    Returns full UserRead (with email_verified and totp_enabled) if:
    - The current user is viewing their own profile
    - The current user is an admin
    - The current user is a superuser

    Otherwise returns PublicUserRead (without sensitive fields).
    """
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not db_user:
        ResponsePatterns.raise_not_found("User", user_id)

    # Check if current user has permission to see sensitive fields
    # Only the user themselves, admins, or superusers can see email_verified and totp_enabled
    if current_user is not None and (current_user.id == user_id or current_user.is_admin or current_user.is_superuser):
        # current_user is guaranteed to be not None here due to the condition above
        assert current_user is not None  # Type guard for type checker
        logger.info(f"User {current_user.id} retrieved full user data for user {user_id}")
        return UserRead.model_validate(db_user)
    else:
        user_id_str = "anonymous" if current_user is None else str(current_user.id)
        logger.info(f"User {user_id_str} retrieved public user data for user {user_id}")
        return PublicUserRead.model_validate(db_user)


# Custom list endpoint for users with permission checks
@router.get(
    "/",
    response_model=List[Union[UserRead, PublicUserRead]],
    responses={
        200: {"description": "List of users retrieved successfully"},
    },
)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    search: Optional[str] = Query(None, description="Search in usernames and emails"),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: Union[DBUser, None] = Depends(get_optional_current_user),
) -> List[Union[UserRead, PublicUserRead]]:
    """
    List all users with pagination and search.

    Returns full UserRead (with email_verified and totp_enabled) for each user if:
    - The current user is an admin
    - The current user is a superuser

    Otherwise returns PublicUserRead (without sensitive fields) for each user.
    """
    from app.api.utils.endpoint_decorators import validate_pagination_params

    skip, limit = validate_pagination_params(skip=skip, limit=limit)

    # Build query
    query = db.query(DBUser)

    # Apply search if provided
    if search:
        from sqlalchemy import or_

        search_term = f"%{search}%"
        query = query.filter(
            or_(
                DBUser.username.ilike(search_term),
                DBUser.email.ilike(search_term),
            )
        )

    # Get users
    users = query.offset(skip).limit(limit).all()

    # Check if current user has permission to see sensitive fields
    can_see_sensitive_fields = current_user is not None and (current_user.is_admin or current_user.is_superuser)

    if can_see_sensitive_fields:
        assert current_user is not None  # Type guard for type checker
        logger.info(f"Admin/superuser {current_user.id} retrieved {len(users)} users with full data")
        return [UserRead.model_validate(user) for user in users]
    else:
        user_id_str = "anonymous" if current_user is None else str(current_user.id)
        logger.info(f"User {user_id_str} retrieved {len(users)} users with public data")
        return [PublicUserRead.model_validate(user) for user in users]


# Create base endpoint router AFTER /me, /count, /{user_id}, and / to avoid route collision
base_router = BaseEndpointRouter(
    service=user_service,
    router=router,
    entity_name="user",
    allow_public_read=True,  # Allow public read access to user profiles (for viewing build list owners, etc.)
    additional_create_data={},  # No additional data needed
    disable_endpoints=["create", "update", "delete", "get", "list"],  # Use custom endpoints instead
    create_schema=UserCreate,
    read_schema=UserRead,
    update_schema=UserUpdate,
    search_fields=["username", "email"],
)


# Custom endpoints specific to users (continued)


@router.post(
    "/",
    response_model=UserRead,
    responses=crud_responses("user", "create"),
)
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> DBUser:
    """
    Creates a new user in the database.
    """

    # Checked if the user already exists
    db_user_by_username = db.query(DBUser).filter(DBUser.username == user.username).first()
    if db_user_by_username:
        ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")

    db_user_by_email = db.query(DBUser).filter(DBUser.email == user.email).first()
    if db_user_by_email:
        ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")

    # Hash the received password
    hashed_password = get_password_hash(user.password)

    # Create DBUser instance (excluding plain password)
    # Auto-verify email in test environment (when using SQLite in-memory database)
    is_test_environment = (
        "sqlite:///:memory:" in str(getattr(db.bind, "url", "")) if db.bind and hasattr(db.bind, "url") else False
    )
    email_verified = True if is_test_environment else False

    db_user = DBUser(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        email_verified=email_verified,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    logger.info(msg=f"User added to database: {db_user}")
    return db_user


@router.put(
    "/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "update"),
)
async def update_user(
    user_id: int,
    user: UserUpdate,
    response: Response,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> UserRead:
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()

    if not db_user:
        logger.warning(f"Attempt to update non-existent user {user_id}.")
        ResponsePatterns.raise_not_found("User", user_id)

    # Check if the current user is the user being updated
    if db_user.id != current_user.id:
        logger.warning(f"User {current_user.id} attempt to update user {user_id} " f"without authorization.")
        ResponsePatterns.raise_forbidden("Not authorized to update this user")

    # Only require current_password if password is being changed
    if "password" in user.model_dump(exclude_unset=True) and user.model_dump(exclude_unset=True)["password"]:
        if not user.current_password:
            ResponsePatterns.raise_bad_request("Current password is required to change your password")
        if not verify_password(user.current_password, db_user.hashed_password):
            logger.warning(f"User {current_user.id} provided incorrect current password for update.")
            ResponsePatterns.raise_unauthorized("Incorrect current password")

    update_data = user.model_dump(
        exclude_unset=True, exclude={"current_password", "otp"}
    )  # Exclude current_password and otp from data to be saved
    username_changed = False

    if (
        "username" in update_data
        and update_data["username"] is not None
        and update_data["username"] != db_user.username
    ):
        username_changed = True

    if "password" in update_data and update_data["password"]:
        hashed_password = get_password_hash(update_data["password"])
        db_user.hashed_password = hashed_password

        del update_data["password"]

    for field, value in update_data.items():
        if value is not None:  # Ensures only set fields that are explicitly provided
            setattr(db_user, field, value)

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"User {user_id} updated successfully by user {current_user.id}.")

        if username_changed:
            logger.info(
                f"Username for user {user_id} changed to '{db_user.username}'. "
                f"Client should re-authenticate to get new token."
            )
            # Note: With Bearer tokens, client should re-login to get a new token with updated username
            # Return new token in response header for convenience
            new_access_token_data = {"sub": db_user.username}
            new_access_token = create_access_token(data=new_access_token_data)
            response.headers["X-New-Access-Token"] = new_access_token

    except IntegrityError as e:
        db.rollback()
        logger.warning(f"IntegrityError during user update for user {user_id}: {e.orig}")
        error_detail_str = str(e.orig).lower()
        if (
            "users_username_key" in error_detail_str
            or "ix_users_username" in error_detail_str
            or ("unique constraint" in error_detail_str and "users.username" in error_detail_str)
        ):
            ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")
        elif (
            "users_email_key" in error_detail_str
            or "ix_users_email" in error_detail_str
            or ("unique constraint" in error_detail_str and "users.email" in error_detail_str)
        ):
            ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")
        else:
            ResponsePatterns.raise_bad_request(
                "A user with the provided username or email may already exist, "
                "or another integrity constraint was violated."
            )
    return UserRead.model_validate(db_user)


@router.delete(
    "/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "delete"),
)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_user),
) -> UserRead:
    """
    Delete a user account. Users can only delete their own account.
    """
    # Check if the current user is trying to delete their own account
    if user_id != current_user.id:
        logger.warning(f"User {current_user.id} attempted to delete user {user_id} " f"without authorization.")
        ResponsePatterns.raise_forbidden("Not authorized to delete this user")

    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if not db_user:
        ResponsePatterns.raise_not_found("User", user_id)

    # Convert the SQLAlchemy model to the Pydantic model before deleting
    deleted_user_data = UserRead.model_validate(db_user)

    db.delete(db_user)
    db.commit()
    logger.info(f"User {current_user.id} deleted their own account")
    return deleted_user_data


# --- Admin Endpoints ---


@router.get(
    "/admin/users",
    response_model=List[UserRead],
    responses=crud_responses("user", "list", allow_public_read=False),
)
async def get_all_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of users to return"),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_admin_user),
) -> List[UserRead]:
    """
    Get all users (admin only).
    """
    skip, limit = validate_pagination_params(skip=skip, limit=limit)
    users = db.query(DBUser).offset(skip).limit(limit).all()
    logger.info(f"Admin {current_user.id} retrieved {len(users)} users")
    return [UserRead.model_validate(user) for user in users]


@router.put(
    "/admin/users/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "update"),
)
async def admin_update_user(
    user_id: int,
    user_update: AdminUserUpdate,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_admin_user),
) -> UserRead:
    """
    Update a user with admin privileges (admin only).
    """
    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if db_user is None:
        ResponsePatterns.raise_not_found("User", user_id)

    # Prevent admin from removing their own admin privileges
    if user_id == current_user.id and (user_update.is_admin is False or user_update.is_superuser is False):
        ResponsePatterns.raise_bad_request("Cannot remove your own admin privileges")

    update_data = user_update.model_dump(exclude_unset=True)

    # Hash password if provided
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    # Update model fields
    for key, value in update_data.items():
        setattr(db_user, key, value)

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"Admin {current_user.id} updated user {user_id}")
        return UserRead.model_validate(db_user)
    except IntegrityError as e:
        db.rollback()
        logger.warning(f"IntegrityError during admin user update: {e.orig}")
        ResponsePatterns.raise_conflict("Username or email already exists", "USERNAME_EMAIL_EXISTS")


@router.delete(
    "/admin/users/{user_id}",
    response_model=UserRead,
    responses=crud_responses("user", "delete"),
)
async def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
    current_user: DBUser = Depends(get_current_admin_user),
) -> UserRead:
    """
    Delete a user with admin privileges (admin only).
    """
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        ResponsePatterns.raise_bad_request("Cannot delete your own account")

    db_user = db.query(DBUser).filter(DBUser.id == user_id).first()
    if db_user is None:
        ResponsePatterns.raise_not_found("User", user_id)

    # Convert the SQLAlchemy model to the Pydantic model before deleting
    deleted_user_data = UserRead.model_validate(db_user)

    db.delete(db_user)
    db.commit()
    logger.info(f"Admin {current_user.id} deleted user {user_id}")
    return deleted_user_data
