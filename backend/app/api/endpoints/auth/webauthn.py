"""WebAuthn passkey endpoints: register/login ceremonies + credentials management."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
)
from app.api.models.user import User as DBUser
from app.api.models.webauthn_credential import WebAuthnCredential
from app.api.schemas.user import UserRead
from app.api.schemas.webauthn import (
    WebAuthnCredentialRename,
    WebAuthnCredentialSummary,
    WebAuthnLoginOptionsRequest,
    WebAuthnLoginOptionsResponse,
    WebAuthnLoginVerifyRequest,
    WebAuthnRegisterOptionsRequest,
    WebAuthnRegisterOptionsResponse,
    WebAuthnRegisterVerifyRequest,
)
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# --- WebAuthn-local helpers (D-19 — stay in this module) ---

WEBAUTHN_REGISTER_PURPOSE = "webauthn_register"
WEBAUTHN_LOGIN_PURPOSE = "webauthn_login"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _build_challenge_token(purpose: str, challenge: bytes, user_id: str | None = None) -> str:
    payload: dict[str, str] = {"purpose": purpose, "challenge": _b64url_encode(challenge)}
    if user_id is not None:
        payload["user_id"] = user_id
    return create_access_token(data=payload, expires_delta=timedelta(minutes=5))


def _decode_challenge_token(token: str, expected_purpose: str) -> tuple[bytes, str | None]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        ResponsePatterns.raise_bad_request("Invalid or expired challenge")
    if payload.get("purpose") != expected_purpose:
        ResponsePatterns.raise_bad_request("Invalid challenge")
    challenge_b64 = payload.get("challenge")
    if not challenge_b64:
        ResponsePatterns.raise_bad_request("Invalid challenge")
    return _b64url_decode(challenge_b64), payload.get("user_id")
