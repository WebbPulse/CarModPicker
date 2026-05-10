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


@router.post("/setup", response_model=TOTPSetupResponse)
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


@router.post("/verify", response_model=TOTPVerifyResponse)
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


@router.post("/disable")
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
