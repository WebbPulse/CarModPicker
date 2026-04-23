"""TOTP 2FA endpoints: setup, verify, disable (all auth-gated)."""

from __future__ import annotations

import base64
import binascii
import io
import logging

import pyotp
import qrcode
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    get_current_user,
    verify_password,
)
from app.api.endpoints.auth._helpers import _issue_login_response  # noqa: F401 — reserved for future use
from app.api.models.user import User as DBUser
from app.api.schemas.auth import (
    TOTPDisableRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPVerifyResponse,
)
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()
