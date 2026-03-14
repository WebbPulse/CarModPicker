from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer, field_validator

from app.api.utils.image_utils import get_presigned_url_from_file_key

# Max length for social profile URLs (RFC 7230 recommends 8000; we use 500 for profile links)
SOCIAL_URL_MAX_LENGTH = 500

# Allowed host substrings per platform (URL host must contain one of these)
SOCIAL_PLATFORM_HOSTS = {
    "instagram": ["instagram.com"],
    "facebook": ["facebook.com", "fb.com", "fb.me"],
    "reddit": ["reddit.com"],
    "youtube": ["youtube.com", "youtu.be"],
    "tiktok": ["tiktok.com"],
}


def _validate_social_url(value: Any, platform: str, allowed_host_substrings: list[str]) -> Optional[str]:
    """Validate optional URL: allow None/empty; otherwise require HTTP(S) and platform domain."""
    if value is None or not (isinstance(value, str) and value.strip()):
        return None
    value = value.strip()
    from pydantic import AnyHttpUrl

    try:
        url = AnyHttpUrl(value)
    except Exception:
        raise ValueError("Must be a valid HTTP or HTTPS URL")
    if len(value) > SOCIAL_URL_MAX_LENGTH:
        raise ValueError(f"URL must be at most {SOCIAL_URL_MAX_LENGTH} characters")
    host_lower = (url.host or "").lower()
    if not any(h in host_lower for h in allowed_host_substrings):
        raise ValueError(f"URL must be a {platform} profile link (e.g. https://{allowed_host_substrings[0]}/...)")
    return str(url)


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
    # Social profile links (optional; validated per platform)
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    session_expire_minutes: Optional[int] = (
        None  # User preference; None = server default. Valid range enforced in backend config.
    )

    @field_validator("instagram_url", mode="before")
    @classmethod
    def validate_instagram_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "Instagram", SOCIAL_PLATFORM_HOSTS["instagram"])

    @field_validator("facebook_url", mode="before")
    @classmethod
    def validate_facebook_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "Facebook", SOCIAL_PLATFORM_HOSTS["facebook"])

    @field_validator("reddit_url", mode="before")
    @classmethod
    def validate_reddit_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "Reddit", SOCIAL_PLATFORM_HOSTS["reddit"])

    @field_validator("youtube_url", mode="before")
    @classmethod
    def validate_youtube_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "YouTube", SOCIAL_PLATFORM_HOSTS["youtube"])

    @field_validator("tiktok_url", mode="before")
    @classmethod
    def validate_tiktok_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_social_url(v, "TikTok", SOCIAL_PLATFORM_HOSTS["tiktok"])


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

    @field_validator("subscription_tier", mode="before")
    @classmethod
    def validate_subscription_tier(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip().lower() if isinstance(v, str) else v
        if s not in ("free", "premium"):
            raise ValueError("subscription_tier must be 'free' or 'premium'")
        return s

    @field_validator("subscription_status", mode="before")
    @classmethod
    def validate_subscription_status(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip().lower() if isinstance(v, str) else v
        if s not in ("active", "cancelled", "expired"):
            raise ValueError("subscription_status must be 'active', 'cancelled', or 'expired'")
        return s


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
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None

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
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    reddit_url: Optional[str] = None
    youtube_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    session_expire_minutes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("image_url")
    def serialize_image_url(self, value: Optional[str]) -> Optional[str]:
        """Convert file key to presigned URL when serializing response."""
        return get_presigned_url_from_file_key(value)
