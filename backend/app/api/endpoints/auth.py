"""
Authentication endpoints with consistent error handling patterns.

This endpoint uses standardized patterns for error handling and response formatting
while maintaining authentication-specific functionality.
"""

import base64
import binascii
import io
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
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
    get_password_hash,
    verify_password,
)
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
    NewPassword,
    OAuthAccountRead,
    OAuthTwoFactorRequest,
    TOTPDisableRequest,
    TOTPLoginRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPVerifyResponse,
)
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
from app.api.utils.google_oauth import GoogleIdentity, GoogleTokenError, verify_google_id_token
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.core.email import send_reset_password_email, send_verify_email
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead | bool]:
    """
    Authenticate user and return access token and user details.
    Takes form data: username and password.
    If 2FA is enabled, returns requires_2fa: true and user must call /token/2fa to complete login.
    Returns Bearer token in response body for standard OAuth2 flow.
    """
    user = db.scalars(select(DBUser).where(DBUser.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        ResponsePatterns.raise_unauthorized("Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    if user.disabled:
        logger.warning(f"Login attempt for disabled user: {user.username}")
        ResponsePatterns.raise_bad_request("Inactive user")
    if user.is_service_account:
        logger.warning(f"Login attempt for service account: {user.username}")
        ResponsePatterns.raise_unauthorized("Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})

    # Check if 2FA is enabled
    if user.totp_enabled:
        logger.info(f"2FA enabled for user: {user.username}, requiring OTP verification")
        return {
            "requires_2fa": True,
            "message": "2FA is enabled. Please provide OTP code.",
        }

    access_token_data = {"sub": user.username}
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data=access_token_data, expires_delta=expires_delta)

    logger.info(f"User logged in successfully: {user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


@router.post("/token/2fa")
async def login_with_2fa(
    request: TOTPLoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """
    Complete login with 2FA OTP code.
    User must have called /token first to verify username/password.
    """
    user = db.scalars(select(DBUser).where(DBUser.username == request.username)).first()
    if not user:
        logger.warning(f"2FA login attempt for non-existent user: {request.username}")
        ResponsePatterns.raise_unauthorized("Invalid credentials", headers={"WWW-Authenticate": "Bearer"})

    if user.disabled:
        logger.warning(f"2FA login attempt for disabled user: {user.username}")
        ResponsePatterns.raise_bad_request("Inactive user")

    if not user.totp_enabled:
        ResponsePatterns.raise_bad_request("2FA is not enabled for this user")

    if not user.totp_secret:
        logger.error(f"2FA enabled but no secret found for user: {user.username}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    # Verify password again for security
    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Invalid password in 2FA login for user: {user.username}")
        ResponsePatterns.raise_unauthorized("Invalid credentials", headers={"WWW-Authenticate": "Bearer"})

    # Verify OTP
    try:
        totp = pyotp.TOTP(user.totp_secret)
    except Exception as e:
        logger.error(f"Invalid TOTP secret format for user: {user.username}, error: {str(e)}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    if not totp.verify(request.otp, valid_window=1):  # Allow 1 time step window for clock skew
        logger.warning(f"Invalid OTP provided for user: {user.username}")
        ResponsePatterns.raise_unauthorized("Invalid OTP code", headers={"WWW-Authenticate": "Bearer"})

    access_token_data = {"sub": user.username}
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data=access_token_data, expires_delta=expires_delta)

    logger.info(f"User logged in successfully with 2FA: {user.username}")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


@router.post("/verify-email")
async def verify_email(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Send verification email to user."""
    user = db.scalars(select(DBUser).where(DBUser.email == email)).first()
    if not user:
        logger.warning(f"Email verification requested for non-existent email: {email}")
        ResponsePatterns.raise_not_found("User")
    if user.email_verified:
        logger.info(f"Email verification requested for already verified email: {email}")
        ResponsePatterns.raise_conflict("Email already verified", "EMAIL_ALREADY_VERIFIED")

    token = create_access_token(
        data={"sub": user.email, "purpose": "verify_email"},
        expires_delta=timedelta(hours=1),
    )

    if settings.DEBUG:
        verify_url = f"http://localhost:8000/api/auth/verify-email/confirm?token={token}"
    else:
        verify_url = f"https://api.carmodpicker.com/api/auth/verify-email/confirm?token={token}"

    if not send_verify_email(user.email, verify_url):
        ResponsePatterns.raise_internal_server_error("Failed to send verification email")
    logger.info(f"Verification email sent to: {email}")
    return {"message": "Verification email sent"}


@router.get("/verify-email/confirm")
async def verify_email_confirm(
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Confirm email verification with token."""
    if settings.DEBUG:
        frontend_base_url = "http://localhost:4000/verify-email/confirm"
    else:
        frontend_base_url = "https://www.carmodpicker.com/verify-email/confirm"

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "verify_email":
            logger.warning("Invalid email verification token")
            return RedirectResponse(
                url=f"{frontend_base_url}?status=error&message=Invalid+or+expired+verification+link",
                status_code=302,
            )

        user = db.scalars(select(DBUser).where(DBUser.email == email)).first()
        if not user:
            logger.warning(f"Email verification attempted for non-existent user: {email}")
            return RedirectResponse(
                url=f"{frontend_base_url}?status=error&message=User+not+found",
                status_code=302,
            )

        if user.email_verified:
            logger.info(f"Email verification attempted for already verified user: {email}")
            return RedirectResponse(
                url=f"{frontend_base_url}?status=info&message=Email+already+verified",
                status_code=302,
            )

        user.email_verified = True
        db.commit()
        logger.info(f"Email verified successfully for user: {email}")
        return RedirectResponse(
            url=f"{frontend_base_url}?status=success&message=Email+verified+successfully",
            status_code=302,
        )

    except JWTError as e:
        logger.warning(f"JWT error during email verification: {e}")
        return RedirectResponse(
            url=f"{frontend_base_url}?status=error&message=Invalid+or+expired+verification+link",
            status_code=302,
        )
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {e}")
        return RedirectResponse(
            url=f"{frontend_base_url}?status=error&message=Something+went+wrong.+Please+try+again.",
            status_code=302,
        )


@router.post("/reset-password")
async def reset_password(
    email: str = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Send password reset email to user."""
    user = db.scalars(select(DBUser).where(DBUser.email == email)).first()
    if not user:
        logger.warning(f"Password reset requested for non-existent email: {email}")
        # Don't reveal if email exists or not for security
        return {"message": "If the email exists, a password reset link has been sent"}

    token = create_access_token(
        data={"sub": user.email, "purpose": "reset_password"},
        expires_delta=timedelta(hours=1),
    )

    if settings.DEBUG:
        reset_url = f"http://localhost:4000/forgot-password/confirm?token={token}"
    else:
        reset_url = f"https://www.carmodpicker.com/forgot-password/confirm?token={token}"

    if not send_reset_password_email(user.email, reset_url):
        ResponsePatterns.raise_internal_server_error("Failed to send password reset email")
    logger.info(f"Password reset email sent to: {email}")
    return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password/confirm")
async def reset_password_confirm(
    token: str = Body(..., embed=True),
    new_password: NewPassword = Body(...),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Confirm password reset with token and new password."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "reset_password":
            logger.warning("Invalid password reset token")
            ResponsePatterns.raise_bad_request("Invalid or expired reset token")

        user = db.scalars(select(DBUser).where(DBUser.email == email)).first()
        if not user:
            logger.warning(f"Password reset attempted for non-existent user: {email}")
            ResponsePatterns.raise_not_found("User")

        # Hash the new password
        hashed_password = get_password_hash(new_password.password)
        user.hashed_password = hashed_password
        db.commit()

        logger.info(f"Password reset successfully for user: {email}")
        return {"message": "Password reset successfully"}

    except JWTError as e:
        logger.warning(f"JWT error during password reset: {e}")
        ResponsePatterns.raise_bad_request("Invalid or expired reset token")
    except HTTPException:
        # Re-raise HTTPException so it's not caught by the generic handler
        raise
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {e}")
        ResponsePatterns.raise_internal_server_error("Failed to reset password")


@router.post("/logout")
async def logout(
) -> dict[str, str]:
    """
    Logout endpoint for client-side token removal.
    Note: With Bearer tokens, the client is responsible for removing the token from storage.
    """
    logger.info("User logged out successfully")
    return {"message": "Logged out successfully"}


# --- 2FA Endpoints ---


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def setup_2fa(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TOTPSetupResponse:
    """
    Generate a new 2FA secret and QR code for the current user.
    This does not enable 2FA - the user must verify the OTP first.
    """
    # Generate a new secret
    secret = pyotp.random_base32()

    # Store the secret temporarily (will be saved when verified)
    current_user.totp_secret = secret
    db.commit()

    # Create TOTP object
    totp = pyotp.TOTP(secret)

    # Generate provisioning URI
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name=settings.PROJECT_NAME,
    )

    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, "PNG")  # Save as PNG format
    qr_code_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

    # Format secret for manual entry (add spaces every 4 characters)
    manual_entry_key = " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))

    logger.info(f"2FA setup initiated for user: {current_user.username}")
    return TOTPSetupResponse(
        secret=secret,
        qr_code_data=f"data:image/png;base64,{qr_code_data}",
        manual_entry_key=manual_entry_key,
    )


@router.post("/2fa/verify", response_model=TOTPVerifyResponse)
async def verify_2fa(
    request: TOTPVerifyRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TOTPVerifyResponse:
    """
    Verify the OTP code and enable 2FA for the current user.
    The user must have called /2fa/setup first to generate a secret.
    """
    if not current_user.totp_secret:
        ResponsePatterns.raise_bad_request("2FA setup not initiated. Please call /2fa/setup first.")

    # Verify OTP - handle invalid secret format gracefully
    try:
        totp = pyotp.TOTP(current_user.totp_secret)
    except (ValueError, TypeError, binascii.Error) as e:
        logger.error(f"Invalid TOTP secret format for user: {current_user.username}, error: {str(e)}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    # Verify OTP - exception can also be raised here if secret is invalid during verification
    try:
        if not totp.verify(request.otp, valid_window=1):
            logger.warning(f"Invalid OTP during 2FA verification for user: {current_user.username}")
            ResponsePatterns.raise_unauthorized("Invalid OTP code")
    except (ValueError, TypeError, binascii.Error) as e:
        logger.error(
            f"Invalid TOTP secret format during verification for user: {current_user.username}, error: {str(e)}"
        )
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    # Enable 2FA
    current_user.totp_enabled = True
    db.commit()

    logger.info(f"2FA enabled successfully for user: {current_user.username}")
    return TOTPVerifyResponse(
        success=True,
        message="2FA has been enabled successfully",
    )


@router.post("/2fa/disable")
async def disable_2fa(
    request: TOTPDisableRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Disable 2FA for the current user.
    Requires both password and OTP code for security.
    """
    if not current_user.totp_enabled:
        ResponsePatterns.raise_bad_request("2FA is not enabled for this user")

    # Verify password
    if not verify_password(request.password, current_user.hashed_password):
        logger.warning(f"Invalid password provided during 2FA disable for user: {current_user.username}")
        ResponsePatterns.raise_unauthorized("Incorrect password")

    # Verify OTP
    if not current_user.totp_secret:
        logger.error(f"2FA enabled but no secret found for user: {current_user.username}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    try:
        totp = pyotp.TOTP(current_user.totp_secret)
    except Exception as e:
        logger.error(f"Invalid TOTP secret format for user: {current_user.username}, error: {str(e)}")
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    if not totp.verify(request.otp, valid_window=1):
        logger.warning(f"Invalid OTP provided during 2FA disable for user: {current_user.username}")
        ResponsePatterns.raise_unauthorized("Invalid OTP code")

    # Disable 2FA
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.commit()

    logger.info(f"2FA disabled for user: {current_user.username}")
    return {"message": "2FA has been disabled successfully"}


# --- WebAuthn / Passkey Endpoints ---


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
    except JWTError:
        ResponsePatterns.raise_bad_request("Invalid or expired challenge")
    if payload.get("purpose") != expected_purpose:
        ResponsePatterns.raise_bad_request("Invalid challenge")
    challenge_b64 = payload.get("challenge")
    if not challenge_b64:
        ResponsePatterns.raise_bad_request("Invalid challenge")
    return _b64url_decode(challenge_b64), payload.get("user_id")


@router.post("/webauthn/register/options", response_model=WebAuthnRegisterOptionsResponse)
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


@router.post("/webauthn/register/verify", response_model=WebAuthnCredentialSummary)
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


@router.post("/webauthn/login/options", response_model=WebAuthnLoginOptionsResponse)
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


@router.post("/webauthn/login/verify")
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


@router.get("/webauthn/credentials", response_model=list[WebAuthnCredentialSummary])
async def list_webauthn_credentials(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebAuthnCredentialSummary]:
    creds = list(db.scalars(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.user_id == current_user.id)
        .order_by(WebAuthnCredential.created_at.desc())
    ).all())
    return [WebAuthnCredentialSummary.model_validate(c) for c in creds]


@router.patch("/webauthn/credentials/{credential_id}", response_model=WebAuthnCredentialSummary)
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
        select(WebAuthnCredential)
        .where(WebAuthnCredential.id == credential_id, WebAuthnCredential.user_id == current_user.id)
    ).first()
    if not cred:
        ResponsePatterns.raise_not_found("Passkey")
    cred.nickname = nickname
    db.commit()
    db.refresh(cred)
    return WebAuthnCredentialSummary.model_validate(cred)


@router.delete("/webauthn/credentials/{credential_id}")
async def delete_webauthn_credential(
    credential_id: uuid.UUID,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    cred = db.scalars(
        select(WebAuthnCredential)
        .where(WebAuthnCredential.id == credential_id, WebAuthnCredential.user_id == current_user.id)
    ).first()
    if not cred:
        ResponsePatterns.raise_not_found("Passkey")
    db.delete(cred)
    db.commit()
    logger.info(f"WebAuthn credential deleted: {credential_id} (user {current_user.username})")
    return {"message": "Passkey removed"}


# --- Google sign-in / OAuth endpoints ---


GOOGLE_LINK_PURPOSE = "google_link"
GOOGLE_SIGNUP_PURPOSE = "google_signup"
OAUTH_2FA_PURPOSE = "oauth_2fa"
GOOGLE_PROVIDER = "google"


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


def _issue_login_response(user: DBUser) -> dict[str, str | UserRead]:
    expires_delta = get_access_token_expires_delta_for_user(user)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=expires_delta)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserRead.model_validate(user),
    }


def _maybe_2fa_challenge(user: DBUser) -> Optional[dict[str, str | bool]]:
    """If user has TOTP enabled, mint an otp_token bound to them and return the challenge payload."""
    if not user.totp_enabled:
        return None
    otp_token = create_access_token(
        data={"purpose": OAUTH_2FA_PURPOSE, "user_id": str(user.id), "source": GOOGLE_PROVIDER},
        expires_delta=timedelta(minutes=5),
    )
    return {"requires_2fa": True, "otp_token": otp_token}


@router.post("/google")
async def google_sign_in(
    request: GoogleSignInRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify a Google ID token and route to the right next step.

    Outcomes:
      - Google `sub` is already linked → log the user in (or 2FA challenge).
      - Email matches an existing user → return a `link_token`; client prompts for password.
      - No match → return a `signup_token`; client collects a username.
    """
    _ensure_google_enabled()
    identity = _verify_google_or_400(request.id_token, request.nonce, logger)

    existing_link = db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == identity.sub,
        )
    ).first()
    if existing_link is not None:
        user = db.scalars(select(DBUser).where(DBUser.id == existing_link.user_id)).first()
        if user is None:
            logger.error(f"OAuth link {existing_link.id} points to missing user {existing_link.user_id}")
            ResponsePatterns.raise_unauthorized("Account not available")
        if user.disabled:
            ResponsePatterns.raise_bad_request("Inactive user")
        if user.is_service_account:
            ResponsePatterns.raise_unauthorized("Account not available")
        challenge = _maybe_2fa_challenge(user)
        if challenge is not None:
            logger.info(f"Google sign-in: 2FA required for user {user.username}")
            return challenge
        logger.info(f"Google sign-in: existing link, logging in user {user.username}")
        return _issue_login_response(user)

    email_match = db.scalars(select(DBUser).where(DBUser.email == identity.email)).first()
    if email_match is not None:
        if email_match.disabled or email_match.is_service_account:
            ResponsePatterns.raise_bad_request("Account not available")
        link_token = create_access_token(
            data={
                "purpose": GOOGLE_LINK_PURPOSE,
                "google_sub": identity.sub,
                "email": identity.email,
            },
            expires_delta=timedelta(minutes=10),
        )
        logger.info(f"Google sign-in: email match for {identity.email}, link required")
        return GoogleSignInLinkRequired(
            link_token=link_token,
            email=identity.email,
            display_name=identity.name,
            has_totp=email_match.totp_enabled,
        ).model_dump()

    signup_token = create_access_token(
        data={
            "purpose": GOOGLE_SIGNUP_PURPOSE,
            "google_sub": identity.sub,
            "email": identity.email,
        },
        expires_delta=timedelta(minutes=15),
    )
    suggested_username = _suggest_username(identity.email, db)
    logger.info(f"Google sign-in: no match for {identity.email}, signup required")
    return GoogleSignInSignupRequired(
        signup_token=signup_token,
        email=identity.email,
        suggested_username=suggested_username,
    ).model_dump()


def _decode_purpose_token(token: str, expected_purpose: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token") from e
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    return payload


@router.post("/google/link")
async def google_link(
    request: GoogleLinkRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Merge a Google identity into an existing password account.

    Required after the initial /auth/google call returned `requires_link: true`.
    Verifies the user's password (and OTP if 2FA is enabled), creates the oauth_accounts row,
    and returns an access token.
    """
    _ensure_google_enabled()
    payload = _decode_purpose_token(request.link_token, GOOGLE_LINK_PURPOSE)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    user = db.scalars(select(DBUser).where(DBUser.email == email)).first()
    if user is None or user.disabled or user.is_service_account:
        ResponsePatterns.raise_unauthorized("Account not available")
    assert user is not None  # for type checker

    if not verify_password(request.password, user.hashed_password):
        logger.warning(f"Google link: bad password for user {user.username}")
        ResponsePatterns.raise_unauthorized("Incorrect password")

    if user.totp_enabled:
        if not request.otp:
            ResponsePatterns.raise_bad_request("OTP required")
        if not user.totp_secret:
            logger.error(f"2FA enabled but no secret for user {user.username}")
            ResponsePatterns.raise_internal_server_error("2FA configuration error")
        try:
            totp = pyotp.TOTP(user.totp_secret)
            if not totp.verify(request.otp, valid_window=1):
                ResponsePatterns.raise_unauthorized("Invalid OTP code")
        except (ValueError, TypeError, binascii.Error):
            ResponsePatterns.raise_internal_server_error("2FA configuration error")

    # Race-safety: another concurrent link could have inserted the row. Check both
    # constraints we'll hit and return clear errors instead of a 500 IntegrityError.
    if db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == google_sub,
        )
    ).first() is not None:
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")
    if db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == GOOGLE_PROVIDER,
        )
    ).first() is not None:
        ResponsePatterns.raise_conflict("Account already has Google linked", "OAUTH_ACCOUNT_EXISTS")

    link = OAuthAccount(
        user_id=user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=google_sub,
        email=email,
    )
    db.add(link)
    db.commit()
    logger.info(f"Google linked to existing user {user.username}")
    return _issue_login_response(user)


@router.post("/google/signup")
async def google_signup(
    request: GoogleSignupRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Create a brand-new account from a Google identity. The email had no existing match
    when /auth/google was called; the client collected a username and submits it here.
    """
    _ensure_google_enabled()
    payload = _decode_purpose_token(request.signup_token, GOOGLE_SIGNUP_PURPOSE)
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not google_sub or not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    username = request.username.strip()
    if not username:
        ResponsePatterns.raise_bad_request("Username cannot be empty")

    if db.scalars(select(DBUser).where(DBUser.username == username)).first() is not None:
        ResponsePatterns.raise_conflict("Username already registered", "USERNAME_EXISTS")
    if db.scalars(select(DBUser).where(DBUser.email == email)).first() is not None:
        # Race: someone else (or another tab) signed up with this email between the initial
        # call and this one. Force them through the merge flow instead.
        ResponsePatterns.raise_conflict("Email already registered", "EMAIL_EXISTS")
    if db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == google_sub,
        )
    ).first() is not None:
        ResponsePatterns.raise_conflict("This Google account is already linked", "OAUTH_ALREADY_LINKED")

    user = DBUser(
        username=username,
        email=email,
        hashed_password=None,
        email_verified=True,
    )
    db.add(user)
    db.flush()  # populate user.id without committing yet
    link = OAuthAccount(
        user_id=user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=google_sub,
        email=email,
    )
    db.add(link)
    db.commit()
    db.refresh(user)
    logger.info(f"Google signup: created user {user.username} (email {user.email})")
    return _issue_login_response(user)


@router.post("/oauth/2fa")
async def oauth_two_factor(
    request: OAuthTwoFactorRequest,
    db: Session = Depends(get_db),
) -> dict[str, str | UserRead]:
    """Complete 2FA after an OAuth sign-in. Accepts the otp_token + OTP only — no password,
    since OAuth-only users may not have one.
    """
    payload = _decode_purpose_token(request.otp_token, OAUTH_2FA_PURPOSE)
    user_id_str = payload.get("user_id")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from e

    user = db.scalars(select(DBUser).where(DBUser.id == user_uuid)).first()
    if user is None or user.disabled or user.is_service_account:
        ResponsePatterns.raise_unauthorized("Account not available")
    assert user is not None
    if not user.totp_enabled or not user.totp_secret:
        ResponsePatterns.raise_bad_request("2FA is not enabled for this user")

    try:
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(request.otp, valid_window=1):
            ResponsePatterns.raise_unauthorized("Invalid OTP code")
    except (ValueError, TypeError, binascii.Error):
        ResponsePatterns.raise_internal_server_error("2FA configuration error")

    logger.info(f"OAuth 2FA completed for user {user.username}")
    return _issue_login_response(user)


@router.post("/google/connect", response_model=OAuthAccountRead)
async def google_connect(
    request: GoogleConnectRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OAuthAccountRead:
    """Link a Google account to the *currently logged-in* user.

    Refuses if the Google email matches a *different* user — the user must instead sign out
    and use the merge flow from the login page. This preserves the invariant that no two
    accounts share an email.
    """
    _ensure_google_enabled()
    identity = _verify_google_or_400(request.id_token, request.nonce, logger)

    existing_link = db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.provider == GOOGLE_PROVIDER,
            OAuthAccount.provider_account_id == identity.sub,
        )
    ).first()
    if existing_link is not None:
        if existing_link.user_id == current_user.id:
            ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")
        ResponsePatterns.raise_conflict(
            "This Google account is linked to a different user", "OAUTH_LINKED_TO_OTHER_USER"
        )

    if db.scalars(
        select(OAuthAccount).where(
            OAuthAccount.user_id == current_user.id,
            OAuthAccount.provider == GOOGLE_PROVIDER,
        )
    ).first() is not None:
        ResponsePatterns.raise_conflict("Google is already linked to this account", "OAUTH_ACCOUNT_EXISTS")

    email_match = db.scalars(select(DBUser).where(DBUser.email == identity.email)).first()
    if email_match is not None and email_match.id != current_user.id:
        ResponsePatterns.raise_conflict(
            "Another account already uses this Google email — sign out and use 'Sign in with Google' to merge.",
            "EMAIL_BELONGS_TO_OTHER_USER",
        )

    link = OAuthAccount(
        user_id=current_user.id,
        provider=GOOGLE_PROVIDER,
        provider_account_id=identity.sub,
        email=identity.email,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    logger.info(f"Google connected to user {current_user.username}")
    return OAuthAccountRead.model_validate(link)


@router.get("/oauth", response_model=list[OAuthAccountRead])
async def list_oauth_accounts(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OAuthAccountRead]:
    rows = list(db.scalars(
        select(OAuthAccount)
        .where(OAuthAccount.user_id == current_user.id)
        .order_by(OAuthAccount.created_at.desc())
    ).all())
    return [OAuthAccountRead.model_validate(r) for r in rows]


@router.delete("/oauth/{account_id}")
async def delete_oauth_account(
    account_id: uuid.UUID,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Remove a linked OAuth provider.

    Refuses if removing it would leave the user with no way to sign in: no password set,
    no other linked OAuth accounts, and no passkeys.
    """
    link = db.scalars(select(OAuthAccount).where(OAuthAccount.id == account_id, OAuthAccount.user_id == current_user.id)).first()
    if link is None:
        ResponsePatterns.raise_not_found("OAuth account")
    assert link is not None

    if not current_user.hashed_password:
        other_oauth = db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id,
                OAuthAccount.id != link.id,
            )
        ).first()
        passkey = db.scalars(
            select(WebAuthnCredential).where(WebAuthnCredential.user_id == current_user.id)
        ).first()
        if other_oauth is None and passkey is None:
            ResponsePatterns.raise_bad_request(
                "Set a password or register a passkey before removing your only sign-in method"
            )

    db.delete(link)
    db.commit()
    logger.info(f"OAuth account {account_id} removed (user {current_user.username})")
    return {"message": "Connected account removed"}
