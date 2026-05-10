"""WebAuthn passkey endpoints: register/login ceremonies + credentials management."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends
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


@router.post("/register/options", response_model=WebAuthnRegisterOptionsResponse)
async def webauthn_register_options(
    request: WebAuthnRegisterOptionsRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebAuthnRegisterOptionsResponse:
    """Start passkey registration: generate a challenge + options object for the browser."""
    nickname = request.nickname.strip()
    if not nickname:
        ResponsePatterns.raise_bad_request("Nickname cannot be empty")

    challenge = secrets.token_bytes(32)
    existing = list(db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == current_user.id)).all())
    exclude = [PublicKeyCredentialDescriptor(id=cred.credential_id) for cred in existing]

    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=current_user.id.bytes,
        user_name=current_user.username,
        user_display_name=current_user.username,
        challenge=challenge,
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )

    options_json = options_to_json(options)

    logger.info(f"WebAuthn registration options generated for user: {current_user.username}")
    return WebAuthnRegisterOptionsResponse(
        options=json.loads(options_json),
        challenge_token=_build_challenge_token(WEBAUTHN_REGISTER_PURPOSE, challenge, user_id=str(current_user.id)),
    )


@router.post("/register/verify", response_model=WebAuthnCredentialSummary)
async def webauthn_register_verify(
    request: WebAuthnRegisterVerifyRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebAuthnCredentialSummary:
    """Verify the browser's attestation and persist the new credential."""
    challenge, challenge_user_id = _decode_challenge_token(request.challenge_token, WEBAUTHN_REGISTER_PURPOSE)
    if challenge_user_id != str(current_user.id):
        ResponsePatterns.raise_bad_request("Challenge does not match current user")

    nickname = request.nickname.strip()
    if not nickname:
        ResponsePatterns.raise_bad_request("Nickname cannot be empty")

    try:
        verified = verify_registration_response(
            credential=request.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins_list,
        )
    except InvalidRegistrationResponse as e:
        logger.warning(f"WebAuthn registration verify failed for {current_user.username}: {e}")
        ResponsePatterns.raise_bad_request(f"Registration failed: {e}")

    if db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.credential_id == verified.credential_id)).first():
        ResponsePatterns.raise_conflict("This credential is already registered", "CREDENTIAL_EXISTS")

    transports = None
    raw_response = request.credential.get("response", {}) if isinstance(request.credential, dict) else {}
    raw_transports = raw_response.get("transports") if isinstance(raw_response, dict) else None
    if isinstance(raw_transports, list):
        transports = [str(t) for t in raw_transports]

    cred = WebAuthnCredential(
        user_id=current_user.id,
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=transports,
        aaguid=verified.aaguid,
        nickname=nickname,
        backup_eligible=bool(getattr(verified, "credential_backed_up", False)),
        backup_state=bool(getattr(verified, "credential_backed_up", False)),
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)

    logger.info(f"WebAuthn credential registered for user: {current_user.username}")
    return WebAuthnCredentialSummary.model_validate(cred)


@router.post("/login/options", response_model=WebAuthnLoginOptionsResponse)
async def webauthn_login_options(
    request: WebAuthnLoginOptionsRequest,
    db: Session = Depends(get_db),
) -> WebAuthnLoginOptionsResponse:
    """Start passkey login: generate a challenge. Username is optional (discoverable flow)."""
    challenge = secrets.token_bytes(32)

    allow_credentials: list[PublicKeyCredentialDescriptor] = []
    if request.username:
        user = db.scalars(select(DBUser).where(DBUser.username == request.username)).first()
        if user:
            creds = list(db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)).all())
            allow_credentials = [PublicKeyCredentialDescriptor(id=c.credential_id) for c in creds]

    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        challenge=challenge,
        allow_credentials=allow_credentials or None,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    options_json = options_to_json(options)

    logger.info(f"WebAuthn login options generated (username={request.username or 'discoverable'})")
    return WebAuthnLoginOptionsResponse(
        options=json.loads(options_json),
        challenge_token=_build_challenge_token(WEBAUTHN_LOGIN_PURPOSE, challenge),
    )


@router.post("/login/verify")
async def webauthn_login_verify(
    request: WebAuthnLoginVerifyRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Verify a passkey assertion, bump sign_count, and mint an access token.

    Passkeys are phishing-resistant multi-factor by design, so this path bypasses TOTP.
    """
    challenge, _ = _decode_challenge_token(request.challenge_token, WEBAUTHN_LOGIN_PURPOSE)

    raw_credential_id = request.credential.get("id") if isinstance(request.credential, dict) else None
    if not raw_credential_id:
        ResponsePatterns.raise_bad_request("Invalid credential payload")
    try:
        credential_id_bytes = _b64url_decode(raw_credential_id)
    except (ValueError, binascii.Error):
        ResponsePatterns.raise_bad_request("Invalid credential id")

    cred = db.scalars(select(WebAuthnCredential).where(WebAuthnCredential.credential_id == credential_id_bytes)).first()
    if not cred:
        logger.warning("WebAuthn login: credential not recognized")
        ResponsePatterns.raise_unauthorized("Unknown credential")

    user = db.scalars(select(DBUser).where(DBUser.id == cred.user_id)).first()
    if not user:
        logger.error(f"WebAuthn credential {cred.id} has no matching user")
        ResponsePatterns.raise_unauthorized("Unknown credential")
    if user.disabled:
        ResponsePatterns.raise_bad_request("Inactive user")
    if user.is_service_account:
        ResponsePatterns.raise_unauthorized("Unknown credential")
    # Mirrors get_current_user: unverified users must not be able to acquire a
    # session, even via a previously-registered passkey.
    if not user.email_verified:
        ResponsePatterns.raise_unauthorized("Email not verified")

    try:
        verified = verify_authentication_response(
            credential=request.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins_list,
            credential_public_key=cred.public_key,
            credential_current_sign_count=cred.sign_count,
        )
    except InvalidAuthenticationResponse as e:
        logger.warning(f"WebAuthn login verify failed: {e}")
        ResponsePatterns.raise_unauthorized(f"Authentication failed: {e}")

    cred.sign_count = verified.new_sign_count
    cred.last_used_at = datetime.now(UTC)
    db.commit()

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=get_access_token_expires_delta_for_user(user),
    )
    logger.info(f"User logged in via passkey: {user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


@router.get("/credentials", response_model=list[WebAuthnCredentialSummary])
async def list_webauthn_credentials(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebAuthnCredentialSummary]:
    creds = list(
        db.scalars(
            select(WebAuthnCredential)
            .where(WebAuthnCredential.user_id == current_user.id)
            .order_by(WebAuthnCredential.created_at.desc())
        ).all()
    )
    return [WebAuthnCredentialSummary.model_validate(c) for c in creds]


@router.patch("/credentials/{credential_id}", response_model=WebAuthnCredentialSummary)
async def rename_webauthn_credential(
    credential_id: uuid.UUID,
    request: WebAuthnCredentialRename,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebAuthnCredentialSummary:
    nickname = request.nickname.strip()
    if not nickname:
        ResponsePatterns.raise_bad_request("Nickname cannot be empty")
    cred = db.scalars(
        select(WebAuthnCredential).where(
            WebAuthnCredential.id == credential_id, WebAuthnCredential.user_id == current_user.id
        )
    ).first()
    if not cred:
        ResponsePatterns.raise_not_found("Passkey")
    cred.nickname = nickname
    db.commit()
    db.refresh(cred)
    return WebAuthnCredentialSummary.model_validate(cred)


@router.delete("/credentials/{credential_id}")
async def delete_webauthn_credential(
    credential_id: uuid.UUID,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    cred = db.scalars(
        select(WebAuthnCredential).where(
            WebAuthnCredential.id == credential_id, WebAuthnCredential.user_id == current_user.id
        )
    ).first()
    if not cred:
        ResponsePatterns.raise_not_found("Passkey")
    db.delete(cred)
    db.commit()
    logger.info(f"WebAuthn credential deleted: {credential_id} (user {current_user.username})")
    return {"message": "Passkey removed"}
