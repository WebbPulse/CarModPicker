"""
Authentication endpoints with consistent error handling patterns.

This endpoint uses standardized patterns for error handling and response formatting
while maintaining authentication-specific functionality.
"""

import base64
import binascii
import io
import logging
from datetime import timedelta

import pyotp
import qrcode
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    ALGORITHM,
    create_access_token,
    get_access_token_expires_delta_for_user,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.api.models.user import User as DBUser
from app.api.schemas.auth import (
    NewPassword,
    TOTPDisableRequest,
    TOTPLoginRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPVerifyResponse,
)
from app.api.schemas.user import UserRead
from app.api.utils.response_patterns import ResponsePatterns
from app.core.config import settings
from app.core.email import send_reset_password_email, send_verify_email
from app.core.logging import get_logger
from app.db.session import get_db

router = APIRouter()


@router.post("/token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str | UserRead | bool]:
    """
    Authenticate user and return access token and user details.
    Takes form data: username and password.
    If 2FA is enabled, returns requires_2fa: true and user must call /token/2fa to complete login.
    Returns Bearer token in response body for standard OAuth2 flow.
    """
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for username: {form_data.username}")
        ResponsePatterns.raise_unauthorized("Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    if user.disabled:
        logger.warning(f"Login attempt for disabled user: {user.username}")
        ResponsePatterns.raise_bad_request("Inactive user")

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
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str | UserRead]:
    """
    Complete login with 2FA OTP code.
    User must have called /token first to verify username/password.
    """
    user = db.query(DBUser).filter(DBUser.username == request.username).first()
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
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str]:
    """Send verification email to user."""
    user = db.query(DBUser).filter(DBUser.email == email).first()
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
    logger: logging.Logger = Depends(get_logger),
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

        user = db.query(DBUser).filter(DBUser.email == email).first()
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
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str]:
    """Send password reset email to user."""
    user = db.query(DBUser).filter(DBUser.email == email).first()
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
    logger: logging.Logger = Depends(get_logger),
) -> dict[str, str]:
    """Confirm password reset with token and new password."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        purpose = payload.get("purpose")

        if not email or purpose != "reset_password":
            logger.warning("Invalid password reset token")
            ResponsePatterns.raise_bad_request("Invalid or expired reset token")

        user = db.query(DBUser).filter(DBUser.email == email).first()
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
    logger: logging.Logger = Depends(get_logger),
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
    logger: logging.Logger = Depends(get_logger),
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
    logger: logging.Logger = Depends(get_logger),
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
    logger: logging.Logger = Depends(get_logger),
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
