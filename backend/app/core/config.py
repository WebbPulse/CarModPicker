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

    # DATABASE_URL is injected at runtime (Secrets Manager on App Runner, .env locally).
    # This validator ensures the env value takes precedence over the Pydantic default.
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Any) -> str:
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
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
        is_prod = not self.DEBUG and self.APP_ENVIRONMENT.lower() != "development"
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
        if not self.S3_ENDPOINT_URL and self.AWS_ENDPOINT_URL:
            object.__setattr__(self, "S3_ENDPOINT_URL", self.AWS_ENDPOINT_URL)

        return self

    # CORS settings
    ALLOWED_ORIGINS: str = Field(
        default=(
            "http://localhost,http://localhost:3000,http://localhost:4000,"
            "https://carmodpicker.com,"
            "https://www.carmodpicker.com,"
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

    # Runtime environment settings
    PORT: int = 8000
    APP_ENVIRONMENT: str = "development"  # Set to "production" on App Runner via Terraform

    # Security settings
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return not self.DEBUG and self.APP_ENVIRONMENT.lower() != "development"

    @property
    def secure_cookies(self) -> bool:
        """Determine if cookies should use secure flag (HTTPS only)."""
        return self.is_production

    # Email settings
    EMAIL_FROM: str = Field(default="")

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

    # S3 image storage settings (carmodpicker-prod-user-images bucket on AWS).
    # On App Runner, BUCKET and AWS_REGION are set via Terraform env vars; credentials
    # come from the App Runner instance IAM role (AWS_ACCESS_KEY_ID/SECRET left empty).
    # Accepts alternative variable names for local dev flexibility.
    BUCKET: str = Field(
        default="",
        description="S3 bucket name for image uploads. Also accepts S3_BUCKET_NAME.",
    )
    S3_BUCKET_NAME: str = Field(
        default="",
        description="Alternative name for bucket (maps to BUCKET if BUCKET is not set)",
    )
    AWS_ACCESS_KEY_ID: str = Field(
        default="",
        description="AWS access key ID. Leave empty on App Runner to use the instance IAM role.",
    )
    AWS_SECRET_ACCESS_KEY: str = Field(
        default="",
        description="AWS secret access key. Leave empty on App Runner to use the instance IAM role.",
    )
    AWS_REGION: str = Field(
        default="auto",
        description="AWS region for the S3 bucket. Also accepts AWS_DEFAULT_REGION.",
    )
    AWS_DEFAULT_REGION: str = Field(
        default="",
        description="Alternative name for region (maps to AWS_REGION if AWS_REGION is not set)",
    )
    S3_ENDPOINT_URL: str = Field(
        default="",
        description="S3 endpoint URL. Leave empty for native AWS S3.",
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
    PRESIGNED_URL_EXPIRATION: int = Field(
        default=86400,
        description="Presigned URL expiration time in seconds (default: 24 hours)",
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
