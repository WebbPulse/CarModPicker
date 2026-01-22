import logging
import os
import subprocess  # nosec B404 - Used safely for running database migrations
import time
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.endpoints import (
    auth,
    bug_reports,
    build_list_parts,
    build_lists,
    build_logs,
    cars,
    categories,
    global_parts,
    images,
    reports,
    search,
    subscriptions,
    users,
    votes,
)
from .api.middleware import rate_limit_middleware
from .api.middleware.error_handler import register_error_handlers
from .api.utils.endpoint_registry import EndpointRegistry
from .core.config import settings
from .core.init_cars import init_car_generations
from .db.session import SessionLocal

# Configure logging for the entire application
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """Run database migrations on startup with retry logic for Railway deployments."""
    max_retries = 25
    retry_delay = 0.2  # Quick retry delay for serverless (0.5 seconds)

    # Determine the correct working directory for alembic
    cwd = "/app" if os.path.exists("/app/alembic") else os.path.dirname(os.path.dirname(__file__))

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Running database migrations (attempt {attempt}/{max_retries})...")
            # nosec B603, B607 - Hardcoded command for database migrations, not user input
            # alembic is installed via pip, so partial path is safe
            result = subprocess.run(
                ["alembic", "upgrade", "head"],  # nosec B603, B607
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Migrations completed successfully: {result.stdout}")
            # Invalidate connection pool to pick up schema changes
            from app.db.session import engine

            engine.dispose(close=False)  # Close all connections to force reconnection with new schema
            logger.info("Connection pool invalidated to pick up schema changes")
            return  # Success, exit the function
        except subprocess.CalledProcessError as e:
            error_output = e.stderr or e.stdout or str(e)
            logger.warning(f"Migration attempt {attempt}/{max_retries} failed: {error_output}")

            # Check if it's a connection error (database not ready)
            is_connection_error = any(
                keyword in error_output.lower()
                for keyword in ["connection refused", "could not connect", "timeout", "network"]
            )

            if attempt < max_retries and is_connection_error:
                # Quick retry with constant delay for serverless (0.5s per attempt)
                logger.info(f"Database not ready. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                # Last attempt or non-connection error
                if attempt == max_retries:
                    logger.error(
                        f"Migration failed after {max_retries} attempts. "
                        f"Last error: {error_output}. "
                        "App will start but database may not be migrated."
                    )
                else:
                    logger.error(f"Migration failed with non-connection error: {error_output}")
                # Don't fail startup - let the app start and handle DB errors gracefully
                return
        except Exception as e:
            logger.error(f"Unexpected error during migration: {e}")
            # Don't fail startup on unexpected errors either
            return


# Run migrations on startup
run_migrations()


# Initialize car generations after migrations
def init_data() -> None:
    """Initialize application data (car generations) after migrations."""
    try:
        db = SessionLocal()
        try:
            init_car_generations(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to initialize car generations: {e}. App will continue to start.")


init_data()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_STR}/openapi.json",
    debug=settings.DEBUG,
)

# Add CORS middleware
# Restrict methods and headers for better security
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Restrict to needed methods
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],  # Restrict to needed headers
)

# Add rate limiting middleware
app.middleware("http")(rate_limit_middleware)

# Register error handlers for standardized error responses
register_error_handlers(app)

# Create endpoint registry for standardized registration
endpoint_registry = EndpointRegistry(app)

# Register all endpoints using the registry
# Core CRUD endpoints
endpoint_registry.register_crud_endpoint(users.router, entity_name="users", description="User management operations")

endpoint_registry.register_crud_endpoint(cars.router, entity_name="cars", description="Car management operations")

endpoint_registry.register_crud_endpoint(
    build_lists.router,
    entity_name="build-lists",
    description="Build list management operations",
)

endpoint_registry.register_crud_endpoint(
    global_parts.router,
    entity_name="global-parts",
    description="Global part catalog operations",
)

endpoint_registry.register_crud_endpoint(
    build_list_parts.router,
    entity_name="build-list-parts",
    description="Build list part management operations",
)

endpoint_registry.register_crud_endpoint(
    categories.router,
    entity_name="categories",
    description="Category management operations",
)

# Search endpoint
endpoint_registry.register_endpoint(
    search.router,
    prefix="/search",
    tags=["search"],
    description="Unified search across build lists, users, and global parts",
)

# Authentication endpoint
endpoint_registry.register_endpoint(
    auth.router,
    prefix="/auth",
    tags=["authentication"],
    description="User authentication and authorization",
)

# Subscription endpoint
endpoint_registry.register_endpoint(
    subscriptions.router,
    prefix="/subscriptions",
    tags=["subscriptions"],
    description="Subscription and billing operations",
)

# Unified vote and report endpoints
endpoint_registry.register_endpoint(
    votes.router,
    prefix="/votes",
    tags=["votes"],
    description="Unified voting operations for all entity types",
)

endpoint_registry.register_endpoint(
    reports.router,
    prefix="/reports",
    tags=["reports"],
    description="Unified reporting operations for all entity types",
)

# Bug reports endpoint
endpoint_registry.register_endpoint(
    bug_reports.router,
    prefix="/bug-reports",
    tags=["bug-reports"],
    description="Bug report operations for users to report application issues",
)

# Image upload endpoint
endpoint_registry.register_endpoint(
    images.router,
    prefix="/images",
    tags=["images"],
    description="Image upload and management operations using Railway Storage Buckets",
)

# Build logs endpoint
endpoint_registry.register_endpoint(
    build_logs.router,
    prefix="/build-logs",
    tags=["build-logs"],
    description="Forum-style build log threads for build lists",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"Hello": "World"}


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}
