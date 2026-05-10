from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.api.schemas.token import TokenData
from app.core.config import settings
from app.core.log_context import user_id_var
from app.db.session import get_db

ALGORITHM = settings.JWT_ALGORITHM


# OAuth2 scheme for Bearer token extraction (FastAPI standard)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/token")
# auto_error=False for optional endpoints that can work without auth
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_STR}/auth/token", auto_error=False)

# --- Password Utilities ---


def verify_password(plain_password: str, hashed_password_str: Optional[str]) -> bool:
    """Verifies a plain password against a hashed password.

    Returns False if the user has no password set (OAuth-only account).
    """
    if not hashed_password_str:
        return False
    hashed_password_bytes = hashed_password_str.encode("utf-8")
    plain_password_bytes = plain_password.encode("utf-8")
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed_bytes = bcrypt.hashpw(password_bytes, salt)
    # Store as string
    return hashed_bytes.decode("utf-8")


# --- JWT Utilities ---


def get_access_token_expires_delta_for_user(user: DBUser) -> timedelta:
    """Returns the access token expiry duration for a user (their preference clamped to server bounds)."""
    minutes = getattr(user, "session_expire_minutes", None)
    if minutes is None:
        minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    minutes = max(
        settings.ACCESS_TOKEN_EXPIRE_MINUTES_MIN,
        min(settings.ACCESS_TOKEN_EXPIRE_MINUTES_MAX, minutes),
    )
    return timedelta(minutes=minutes)


def create_access_token(data: dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Use default expiration from settings
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return str(encoded_jwt)


# --- Dependency to Get Current User ---


async def get_current_user(
    token: str = Depends(oauth2_scheme),  # Bearer token from Authorization header (FastAPI standard)
    db: Session = Depends(get_db),
) -> DBUser:
    """
    Decodes JWT Bearer token from Authorization header, validates credentials, and returns the user.
    Uses standard OAuth2 Bearer token authentication.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception

    user = db.scalars(select(DBUser).where(DBUser.username == token_data.username)).first()
    if user is None:
        raise credentials_exception
    if user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email not verified")
    user_id_var.set(str(user.id))
    return user


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[DBUser]:
    """
    Decodes JWT Bearer token and returns the user, or None if not authenticated.
    This is for endpoints that can work with or without authentication.
    Uses standard OAuth2 Bearer token authentication.
    """
    if token is None:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None
        token_data = TokenData(username=username)
    except InvalidTokenError:
        return None

    user = db.scalars(select(DBUser).where(DBUser.username == token_data.username)).first()
    if user is None or user.disabled or not user.email_verified:
        return None

    user_id_var.set(str(user.id))
    return user


async def get_current_active_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: Session = Depends(get_db),
) -> Optional[DBUser]:
    """
    Optionally returns the current active user if a valid Bearer token is present.
    Returns None if no token, token is invalid/expired, user not found, or user is inactive.
    Uses standard OAuth2 Bearer token authentication.
    """
    if token is None:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None  # Invalid token payload
        token_data = TokenData(username=username)
    except InvalidTokenError:  # Covers expired, invalid signature, etc.
        return None  # Token is invalid or expired

    user = db.scalars(select(DBUser).where(DBUser.username == token_data.username)).first()
    if user is None:
        return None  # User from token not found in DB

    if user.disabled:
        return None  # User is inactive, so not considered an "active user"

    user_id_var.set(str(user.id))
    return user


# --- Admin/Superuser Dependencies ---


async def get_current_admin_user(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Dependency that requires the current user to be an admin.
    """
    if not current_user.is_admin and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def get_current_superuser(
    current_user: DBUser = Depends(get_current_user),
) -> DBUser:
    """
    Dependency that requires the current user to be a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required",
        )
    return current_user
