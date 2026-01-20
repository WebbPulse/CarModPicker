from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer

from app.api.utils.image_utils import get_presigned_url_from_file_key


# Schema for request body when creating a user
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


# Schema for request body when updating a user
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = None
    image_url: Optional[str] = None
    current_password: Optional[str] = None
    otp: Optional[str] = None  # Required if 2FA is enabled and changing password


# Schema for admin operations when updating a user
class AdminUserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    disabled: Optional[bool] = None
    password: Optional[str] = None
    image_url: Optional[str] = None
    is_superuser: Optional[bool] = None
    is_admin: Optional[bool] = None
    email_verified: Optional[bool] = None
    subscription_tier: Optional[str] = None  # 'free' or 'premium'
    subscription_status: Optional[str] = None  # 'active', 'cancelled', or 'expired'
    subscription_expires_at: Optional[datetime] = None


# Schema for public user data (excludes sensitive fields like email_verified and totp_enabled)
class PublicUserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    disabled: bool
    image_url: Optional[str] = None
    is_superuser: bool
    is_admin: bool
    subscription_tier: str
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_url")
    def serialize_image_url(self, value: Optional[str]) -> Optional[str]:
        """Convert file key to presigned URL when serializing response."""
        return get_presigned_url_from_file_key(value)


# Schema for response body when reading a user (DO NOT include hashed password)
# Includes sensitive fields that should only be visible to the user themselves, admins, or superusers
class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    disabled: bool
    email_verified: bool
    image_url: Optional[str] = None
    is_superuser: bool
    is_admin: bool
    subscription_tier: str
    subscription_status: str
    subscription_expires_at: Optional[datetime] = None
    totp_enabled: bool = False

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_url")
    def serialize_image_url(self, value: Optional[str]) -> Optional[str]:
        """Convert file key to presigned URL when serializing response."""
        return get_presigned_url_from_file_key(value)
