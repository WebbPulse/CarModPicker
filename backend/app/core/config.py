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

    # JWT algorithm — PyJWT swap (AUTH-04 D-03). HS256 preserved per D-46.
    JWT_ALGORITHM: str = Field(
        default="HS256",
        description="Algorithm used to sign + verify JWTs. Must match on encode and decode.",
    )

    # Google OAuth — frontend uses this client id to mint ID tokens; backend uses it as the
    # `audience` when verifying. The client id itself is not a secret (it's embedded in the
    # frontend bundle anyway), so it lives in source. Override via env if/when rotated.
    GOOGLE_CLIENT_ID: str = Field(
        default="1073035138993-bvba9dfi4pdr354p3d550bi95die8e83.apps.googleusercontent.com",
        description="Google OAuth 2.0 client id. Used as the audience when verifying ID tokens.",
    )

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID)

    # WebAuthn / passkeys — RP ID and origins are derived from APP_ENVIRONMENT.
    # RP ID is the registrable domain users see; origins are the frontend URLs
    # that will call navigator.credentials.*. Passkeys registered on one
    # environment cannot be used on another (different RP IDs).
    @property
    def webauthn_rp_id(self) -> str:
        if not self.is_production:
            return "localhost"
        if self.APP_ENVIRONMENT.lower() == "staging":
            return "staging.carmodpicker.com"
        return "carmodpicker.com"

    @property
    def webauthn_rp_name(self) -> str:
        return self.PROJECT_NAME

    @property
    def webauthn_origins_list(self) -> list[str]:
        if not self.is_production:
            return ["http://localhost:4000", "http://localhost:8000"]
        if self.APP_ENVIRONMENT.lower() == "staging":
            return ["https://staging.carmodpicker.com"]
        return [
            "https://carmodpicker.com",
            "https://www.carmodpicker.com",
        ]

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
        if not self.USER_IMAGES_BUCKET and self.S3_BUCKET_NAME:
            object.__setattr__(self, "USER_IMAGES_BUCKET", self.S3_BUCKET_NAME)

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
    EMAIL_ENABLED: bool = Field(
        default=False,
        description=(
            "Enable email sending via SES. Set to true in production. " "When false, email calls are silently skipped."
        ),
    )
    EMAIL_FROM: str = Field(default="")

    # Sentry settings (Phase 2 / OBS-01)
    SENTRY_DSN: str = Field(
        default="",
        description="Sentry DSN for error reporting. Empty = Sentry disabled. Injected via Secrets Manager in prod (D-01, D-55).",
    )
    SENTRY_RELEASE: str = Field(
        default="",
        description="Release identifier baked at Docker build time (typically git commit SHA, set by GitHub Actions per D-02).",
    )
    SENTRY_SERVICE_NAME: str = Field(
        default="",
        description="Per-process server_name tag: 'apprunner-backend', 'ecs-crawler', 'crawler-cli' (D-11).",
    )

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

    # S3 storage settings. On App Runner, these are set via Terraform env vars; credentials
    # come from the App Runner instance IAM role (AWS_ACCESS_KEY_ID/SECRET left empty).
    # Accepts alternative variable names for local dev flexibility.
    USER_IMAGES_BUCKET: str = Field(
        default="",
        description="S3 bucket name for user image uploads. Also accepts S3_BUCKET_NAME.",
    )
    CRAWL_BUCKET: str = Field(
        default="",
        description="S3 bucket name for crawler HTML snapshots. Separate from user images.",
    )
    # Chrome extension POST /crawled-pages/{scrape,html}: max UTF-8 byte length of the `html` field (reject with 413).
    CRAWLED_PAGE_MAX_HTML_BYTES: int = Field(
        default=8 * 1024 * 1024,
        description="Maximum UTF-8 size in bytes for extension-submitted page HTML.",
    )
    # When Content-Length is set, reject POST bodies larger than max HTML + this slack (JSON wrapper, url field).
    CRAWLED_PAGE_UPLOAD_CONTENT_LENGTH_SLACK_BYTES: int = Field(
        default=64 * 1024,
        description="Extra bytes allowed on Content-Length vs CRAWLED_PAGE_MAX_HTML_BYTES for JSON framing.",
    )
    S3_BUCKET_NAME: str = Field(
        default="",
        description="Alternative name for USER_IMAGES_BUCKET (maps to USER_IMAGES_BUCKET if not set)",
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
