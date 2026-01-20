from pydantic import BaseModel


class NewPassword(BaseModel):
    password: str


class TOTPSetupResponse(BaseModel):
    """Response when setting up 2FA - contains QR code data and secret."""

    secret: str
    qr_code_data: str  # Base64 encoded QR code image
    manual_entry_key: str  # Formatted secret for manual entry


class TOTPVerifyRequest(BaseModel):
    """Request to verify and enable 2FA."""

    otp: str  # The 6-digit OTP code


class TOTPVerifyResponse(BaseModel):
    """Response after verifying 2FA setup."""

    success: bool
    message: str


class TOTPLoginRequest(BaseModel):
    """Request for 2FA verification during login."""

    username: str
    password: str
    otp: str  # The 6-digit OTP code


class TOTPDisableRequest(BaseModel):
    """Request to disable 2FA - requires password and OTP."""

    password: str  # Current password
    otp: str  # The 6-digit OTP code
