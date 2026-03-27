import os
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API settings
    API_STR: str = "/api"
    PROJECT_NAME: str = "CarModPicker"
    DEBUG: bool = False

    # Database settings
    DATABASE_URL: str = "sqlite:///./test.db"  # will load url from env but will fallback to this if not found

    # Railway-specific database URL (Railway provides this automatically)
    # This will override DATABASE_URL if present
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Any) -> str:
        # If there's a Railway DATABASE_URL in environment, use it
        railway_db_url = os.getenv("DATABASE_URL")
        if railway_db_url:
            # Railway's DATABASE_URL already includes connection parameters
            return railway_db_url
        return str(v)

    # JWT Auth
    SECRET_KEY: str = Field(
        default="",
        description="Secret key for JWT token signing. MUST be set in production!",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Bounds for user-configurable session length (minutes). User preference is clamped to this range.
    ACCESS_TOKEN_EXPIRE_MINUTES_MIN: int = 15
    ACCESS_TOKEN_EXPIRE_MINUTES_MAX: int = 10080  # 7 days

    @model_validator(mode="after")
    def validate_and_normalize_settings(self) -> "Settings":
        """Validate settings and normalize storage variable names."""
        # Validate SECRET_KEY in production
        is_prod = not self.DEBUG and self.RAILWAY_ENVIRONMENT.lower() != "development"
        if not self.SECRET_KEY and is_prod:
            # In production, SECRET_KEY must be set
            import warnings

            warnings.warn(
                "SECRET_KEY is empty in production! JWT tokens will be insecure. "
                "Set SECRET_KEY environment variable.",
                UserWarning,
            )

        # Normalize storage settings to handle both variable naming conventions
        # Handle bucket name
        if not self.BUCKET and self.S3_BUCKET_NAME:
            object.__setattr__(self, "BUCKET", self.S3_BUCKET_NAME)

        # Handle region
        if not self.AWS_REGION or self.AWS_REGION == "auto":
            if self.AWS_DEFAULT_REGION:
                object.__setattr__(self, "AWS_REGION", self.AWS_DEFAULT_REGION)
            else:
                object.__setattr__(self, "AWS_REGION", "auto")

        # Handle endpoint URL
        if not self.S3_ENDPOINT_URL or self.S3_ENDPOINT_URL == "https://storage.railway.app":
            if self.AWS_ENDPOINT_URL:
                object.__setattr__(self, "S3_ENDPOINT_URL", self.AWS_ENDPOINT_URL)

        return self

    # CORS settings
    ALLOWED_ORIGINS: str = Field(
        default=(
            "http://localhost,http://localhost:3000,http://localhost:4000,"
            "https://carmodpicker.com,"
            "https://api.carmodpicker.com,"
            "https://staging.carmodpicker.com,"
            "https://api.staging.carmodpicker.com"
        ),
        description="Comma-separated list of allowed origins",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        """Get ALLOWED_ORIGINS as a list."""
        origins = []
        if self.ALLOWED_ORIGINS:
            origins = [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

        # Allow null origin for Chrome extensions (service workers send null origin)
        # Also allow chrome-extension:// origins for extension popups/content scripts
        origins.append("null")

        return origins

    # Railway deployment settings
    PORT: int = 8000
    RAILWAY_ENVIRONMENT: str = "development"

    # Security settings
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return not self.DEBUG and self.RAILWAY_ENVIRONMENT.lower() != "development"

    @property
    def secure_cookies(self) -> bool:
        """Determine if cookies should use secure flag (HTTPS only)."""
        return self.is_production

    # Email settings
    SENDGRID_API_KEY: str = Field(default="")
    EMAIL_FROM: str = Field(default="")
    SENDGRID_VERIFY_EMAIL_TEMPLATE_ID: str = Field(default="")
    SENDGRID_RESET_PASSWORD_TEMPLATE_ID: str = Field(default="")
    # Hashing settings
    HASH_ALGORITHM: str = "HS256"

    # Rate limiting settings
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_REQUESTS_PER_HOUR: int = 1000

    # Sophisticated rate limiting settings
    RATE_LIMIT_GET_REQUESTS_PER_MINUTE: int = 200
    RATE_LIMIT_GET_REQUESTS_PER_HOUR: int = 20000
    RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE: int = 10
    RATE_LIMIT_AUTH_REQUESTS_PER_HOUR: int = 100
    RATE_LIMIT_ADMIN_REQUESTS_PER_MINUTE: int = 30
    RATE_LIMIT_ADMIN_REQUESTS_PER_HOUR: int = 300

    # Railway Storage Bucket settings for image uploads
    # These variables are automatically provided by Railway when you reference the bucket
    # See: https://docs.railway.com/guides/storage-buckets#railway-provided-variables
    # Accepts both Railway's variable names and alternative names for flexibility
    BUCKET: str = Field(
        default="",
        description="Railway bucket name (from Railway Storage Bucket variable reference). Also accepts S3_BUCKET_NAME.",
    )
    S3_BUCKET_NAME: str = Field(
        default="",
        description="Alternative name for bucket (maps to BUCKET if BUCKET is not set)",
    )
    AWS_ACCESS_KEY_ID: str = Field(
        default="",
        description="Railway bucket access key ID (from Railway Storage Bucket variable reference)",
    )
    AWS_SECRET_ACCESS_KEY: str = Field(
        default="",
        description="Railway bucket secret access key (from Railway Storage Bucket variable reference)",
    )
    AWS_REGION: str = Field(
        default="auto",
        description="Railway bucket region (typically 'auto' for Railway buckets). Also accepts AWS_DEFAULT_REGION.",
    )
    AWS_DEFAULT_REGION: str = Field(
        default="",
        description="Alternative name for region (maps to AWS_REGION if AWS_REGION is not set)",
    )
    S3_ENDPOINT_URL: str = Field(
        default="https://storage.railway.app",
        description="Railway Storage Bucket endpoint URL. Also accepts AWS_ENDPOINT_URL.",
    )
    AWS_ENDPOINT_URL: str = Field(
        default="",
        description="Alternative name for endpoint URL (maps to S3_ENDPOINT_URL if S3_ENDPOINT_URL is not set)",
    )
    # Image upload settings
    MAX_IMAGE_SIZE_MB: int = Field(default=10, description="Maximum image file size in MB")
    ALLOWED_IMAGE_EXTENSIONS: str = Field(
        default="jpg,jpeg,png,gif,webp",
        description="Comma-separated list of allowed image file extensions",
    )
    # Presigned URL expiration (in seconds) - Railway allows up to 90 days (7776000 seconds)
    PRESIGNED_URL_EXPIRATION: int = Field(
        default=86400,
        description="Presigned URL expiration time in seconds (default: 24 hours, max: 90 days)",
    )

    @property
    def allowed_image_extensions_list(self) -> list[str]:
        """Get allowed image extensions as a list."""
        if not self.ALLOWED_IMAGE_EXTENSIONS:
            return []
        return [ext.strip().lower() for ext in self.ALLOWED_IMAGE_EXTENSIONS.split(",") if ext.strip()]

    @property
    def max_image_size_bytes(self) -> int:
        """Get maximum image size in bytes."""
        return self.MAX_IMAGE_SIZE_MB * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings.
    For tests, this can be overridden before the first call.
    """
    return Settings()


# Create settings instance for normal usage
settings = get_settings()
