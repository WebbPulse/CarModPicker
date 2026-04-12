import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.endpoints import (
    admin,
    auth,
    brands,
    bug_reports,
    build_list_parts,
    build_list_phases,
    build_lists,
    build_logs,
    cars,
    categories,
    crawled_pages,
    global_parts,
    images,
    reports,
    retailers,
    search,
    users,
    votes,
)
from .api.middleware import rate_limit_middleware
from .api.middleware.error_handler import register_error_handlers
from .api.utils.endpoint_registry import EndpointRegistry
from .core.config import settings
from .core.init_service_accounts import init_crawler_service_account
from .core.logging import LOG_FORMAT, ColorizedFormatter
from .db.session import SessionLocal, check_db_ready

# Configure logging for the entire application (single format, colorized levels)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()],
)
_coloured = ColorizedFormatter(LOG_FORMAT)
_root = logging.getLogger()
for _h in _root.handlers:
    _h.setFormatter(_coloured)

# Apply same format and colors to uvicorn loggers
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _log = logging.getLogger(_name)
    for _h in _log.handlers:
        _h.setFormatter(_coloured)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    db = SessionLocal()
    try:
        init_crawler_service_account(db)
    except Exception:
        logger.exception("Failed to initialize service accounts on startup")
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_STR}/openapi.json",
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Add CORS middleware
# Restrict methods and headers for better security
# Note: Chrome extensions send requests with null origin (service workers) or
# chrome-extension:// origin (popup/content scripts). We allow both via:
# - allow_origins includes "null" for service workers
# - allow_origin_regex allows chrome-extension:// origins
# Note: When allow_credentials=True, we can still use allow_origin_regex,
# but it must be used alongside allow_origins (not instead of)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"chrome-extension://.*",  # Allow all Chrome extensions
    allow_origins=settings.allowed_origins_list,  # Includes "null" for service workers + web origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Restrict to needed methods
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-Admin-Cron-Key",
    ],  # Restrict to needed headers
    expose_headers=["*"],  # Expose all headers for debugging
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
    build_list_phases.router,
    entity_name="build-list-phases",
    description="Build list phase update/delete operations",
)

endpoint_registry.register_crud_endpoint(
    categories.router,
    entity_name="categories",
    description="Category management operations",
)

endpoint_registry.register_crud_endpoint(
    brands.router,
    entity_name="brands",
    description="Brand management operations",
)

endpoint_registry.register_crud_endpoint(
    retailers.router,
    entity_name="retailers",
    description="Retailer (store) management operations",
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
    description="Image upload and management operations using S3",
)

# Crawled pages HTML archival
endpoint_registry.register_endpoint(
    crawled_pages.router,
    prefix="/crawled-pages",
    tags=["crawled-pages"],
    description="HTML archival for crawled pages (extension upload and admin re-parse)",
)

# Build logs endpoint
endpoint_registry.register_endpoint(
    build_logs.router,
    prefix="/build-logs",
    tags=["build-logs"],
    description="Forum-style build log threads for build lists",
)

# Admin endpoint
endpoint_registry.register_endpoint(
    admin.router,
    prefix="/admin",
    tags=["admin"],
    description="Admin-only system management operations",
)


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "CarModPicker API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check() -> dict[str, Any]:
    """Health check endpoint for monitoring (liveness: app is running)."""
    return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}


@app.get("/ready", response_model=None)
def readiness_check() -> dict[str, Any] | JSONResponse:
    """
    Readiness check: returns 200 when DB is reachable, 503 otherwise.

    Use this so load balancers or the frontend can wait until the backend
    (and DB) have finished spooling before sending traffic. During serverless
    cold start, poll /ready until 200, then call other endpoints.
    """
    if check_db_ready():
        return {"status": "ready", "database": "up"}
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "message": "Service starting; database not ready. Please retry.",
            "error_code": "SERVICE_UNAVAILABLE",
        },
        headers={"Retry-After": "2"},
    )
