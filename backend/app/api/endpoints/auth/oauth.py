"""Google OAuth endpoints: sign-in, signup, link, connect, 2FA, account list/delete."""

from __future__ import annotations

import binascii
import logging
import uuid
from datetime import timedelta
from typing import Any

import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_current_user,
    verify_password,
)
from app.api.endpoints.auth._helpers import _issue_login_response, _maybe_2fa_challenge
from app.api.models.oauth_account import OAuthAccount
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.api.schemas.auth import (
    GoogleConnectRequest,
    GoogleLinkRequest,
    GoogleSignInLinkRequired,
    GoogleSignInRequest,
    GoogleSignInSignupRequired,
    GoogleSignupRequest,
    OAuthAccountRead,
    OAuthTwoFactorRequest,
)
from app.api.schemas.user import UserRead
from app.api.utils.google_oauth import GoogleIdentity, GoogleTokenError, verify_google_id_token
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Google-specific helpers (D-20 — stay in this module) ---

GOOGLE_LINK_PURPOSE = "google_link"
GOOGLE_SIGNUP_PURPOSE = "google_signup"
OAUTH_2FA_PURPOSE = "oauth_2fa"  # Duplicated in _helpers.py per planner decision
GOOGLE_PROVIDER = "google"  # Duplicated in _helpers.py per planner decision


def _ensure_google_enabled() -> None:
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )


def _verify_google_or_400(id_token_str: str, nonce: str, logger: logging.Logger) -> GoogleIdentity:
    try:
        identity = verify_google_id_token(id_token_str, nonce, settings.GOOGLE_CLIENT_ID)
    except GoogleTokenError as e:
        logger.warning(f"Google id_token verification failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)) from e
    if not identity.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account email is not verified",
        )
    return identity


def _suggest_username(email: str, db: Session) -> str:
    """Build a username suggestion from the email local-part. Caller still validates uniqueness."""
    local = email.split("@", 1)[0].lower()
    base = "".join(ch for ch in local if ch.isalnum() or ch in ("_", "-", ".")) or "user"
    candidate = base
    suffix = 1
    while db.scalars(select(DBUser).where(DBUser.username == candidate)).first() is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
        if suffix > 100:
            # Give up on auto-numbering; user picks one. Returning the base is fine —
            # the signup endpoint will reject it if still taken and the form will reprompt.
            return base
    return candidate


def _decode_purpose_token(token: str, expected_purpose: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from e
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    return payload
