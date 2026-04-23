"""Authentication core endpoints: token issuance, email verification, password reset, logout."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import pyotp
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.schemas.auth import (
    NewPassword,
    TOTPLoginRequest,
)
from app.api.schemas.user import UserRead
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.core.email import send_reset_password_email, send_verify_email
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()
