"""What this product adds to `webbpulse.composition`, and nothing the package owns.

`Domain`, the registry, the builder, the tracing gate, the startup secrets check
and the local authorizer are all the package's now. What stays here is the part
that is CarModPicker's: the colorized TTY logging, the repository bundle built
from this product's own registry, the rate limiter, the vehicles seeder and the
five root routes.

Both roots build through `build_domain_app`, so they cannot drift. Composition
is `include_router` and never `mount`, which would empty the OpenAPI document.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, Sequence, Tuple

from fastapi import FastAPI, Query, Response
from fastapi.responses import JSONResponse
from webbpulse.composition import OTLP_ENDPOINT_ENV, Domain, check_secrets, local_authorizer, scope_for
from webbpulse.composition import build_domain_app as _build_domain_app
from webbpulse.composition import configure_tracing as _configure_tracing
from webbpulse.http import DEFAULT_CORS_ALLOW_HEADERS

from app.common.composition.service import OPENAPI_VERSION, SERVICE_NAME_TEMPLATE
from app.common.core.config import settings

logger = logging.getLogger(__name__)

__all__ = [
    "API_PREFIX",
    "CORS_ALLOW_HEADERS",
    "OPENAPI_VERSION",
    "OTLP_ENDPOINT_ENV",
    "SERVICE_NAME_TEMPLATE",
    "Domain",
    "add_root_routes",
    "add_shared_middleware",
    "build_domain_app",
    "bundle_for",
    "check_signing_key",
    "configure_logging",
    "configure_tracing",
    "run_startup_tasks",
    "scope_for",
    "start_domain",
    "tables_for_domain",
]

API_PREFIX = settings.API_STR


def configure_logging(service: "str | None" = None) -> None:
    """The application's log format, applied to the root and uvicorn loggers.

    A thin call into `app.common.core.logging.configure_app_logging`, which is this
    product's own: the package's `configure_logging` has no colorized TTY branch.
    Called at import by `app/main.py`; calling it twice is harmless.
    """
    from app.common.core.logging import configure_app_logging

    configure_app_logging(
        level=settings.log_level,
        service=service or settings.PROJECT_NAME,
        environment=settings.environment,
    )


def configure_tracing(domain: "Domain") -> bool:
    """Wire OpenTelemetry for one domain, but only when an OTLP endpoint is set.

    The package's gate, bound to this product's settings so the consumer
    entrypoints and the domain entrypoints call it the same way.
    """
    return _configure_tracing(domain, settings)


def check_signing_key(domains: "Sequence[Domain]") -> None:
    """Fail fast on a missing secret, once at startup, per the domains served.

    The package's `check_secrets` under this product's own name, kept because the
    consumer entrypoints and the lifespan both call it.
    """
    check_secrets(domains, settings)


def tables_for_domain(domain: "Domain") -> "Tuple[str, ...]":
    """The DynamoDB tables one domain's repositories reach, sorted.

    A function rather than the property the product's own `Domain` carried, because
    the descriptor is the package's now and the repository registry is this
    product's. Read from that registry rather than listed again, so the tables and
    the Terraform IAM policy cannot disagree.
    """
    from app.common.db.dynamo.registry import tables_for

    return tables_for(domain.repositories)


def start_domain(domain: "Domain", _settings: "Any" = None) -> None:
    """Configure logging, then tracing, then verify the secrets one domain needs.

    The `check` hook `domain_entrypoint` runs, and the reason each entrypoint binds
    `settings=None`: the package's own `main` would call the package's
    `configure_logging`, which has no colorized TTY branch, so this product does all
    three itself in the package's order. Logging comes first so a misconfigured
    function fails at cold start with the failure already formatted, and tracing
    precedes the build because the server span middleware can only be injected into
    an unbuilt middleware stack.
    """
    del _settings

    configure_logging(service=domain.service_name)
    configure_tracing(domain)
    check_signing_key([domain])


def bundle_for(domains: "Sequence[Domain]") -> "Any":
    """The bundle carrying exactly the repositories these domains declare.

    Reads the package's `scope_for` for the names rather than recomputing the
    union, and builds this product's own bundle type. Building the bundle
    constructs no repository, so an image's import graph stays proportional to
    the routes it serves.
    """
    from app.common.api.dependencies.repositories import build_bundle

    scope = scope_for(list(domains))
    return build_bundle(list(scope.names), name=scope.name)


def run_startup_tasks() -> None:
    """Seed work that runs once per process, on the first request in the app.

    Only a root serving a domain named in `SEEDING_DOMAINS` wires this, so a
    function with read-only IAM on the car tables never attempts the write.
    """
    from app.common.seeds.init_cars import init_car_generations

    try:
        init_car_generations()
    except Exception:
        logger.exception("Failed to initialize car generations on startup")


CORS_ALLOW_HEADERS: Tuple[str, ...] = (
    *DEFAULT_CORS_ALLOW_HEADERS,
    "X-Requested-With",
    "X-Admin-Cron-Key",
)
"""The package default set, plus the two headers `terraform/apigateway.tf` also allows."""


def add_shared_middleware(app: FastAPI, domains: "Sequence[Domain]" = ()) -> None:
    """Rate limiting and the local authorizer, then this product's repository bundle.

    The order is load-bearing: `build_domain_app` runs this after `create_app` and
    before any router, and Starlette runs middleware outermost-first in the order
    added, so CORS wraps the request id middleware which wraps the rate limiter.
    """
    from app.common.api.dependencies.repositories import bind_repositories
    from app.common.api.middleware import rate_limit_middleware
    from app.domains.identity.package_glue import build_identity_settings

    app.middleware("http")(rate_limit_middleware)
    local_authorizer(app, settings, build_identity_settings=build_identity_settings)
    bind_repositories(app, bundle_for(domains))


def add_local_authorizer(app: FastAPI) -> bool:
    """Stand in for the gateway's JWT authorizer, but only on a local stack.

    The package's `local_authorizer` bound to this product's settings and its own
    identity settings factory, kept as a name so the gate test can call it alone.
    """
    from app.domains.identity.package_glue import build_identity_settings

    return local_authorizer(app, settings, build_identity_settings=build_identity_settings)


_SITEMAP_CACHE = "public, max-age=3600"


def add_root_routes(app: FastAPI, domains: "Sequence[Domain]" = ()) -> None:
    """`/`, `/health`, `/ready` and the two sitemap routes.

    None of the five is published in the OpenAPI document. The gateway declares a route
    key for the sitemaps only, so the other three are reachable by direct Lambda invoke
    alone, which is how the deploy's smoke step probes `/health`. Declaring them would
    describe three operations the gateway answers its own 404 for.
    """
    del domains

    from app.common.api.services import sitemap_service
    from app.common.db.dynamo.client import check_db_ready

    @app.get("/", include_in_schema=False)
    def read_root() -> Dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """Name, version and the two probe paths, for a bare hit on the root."""
        return {
            "name": "CarModPicker API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health", include_in_schema=False)
    def health_check() -> Dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        """Health check endpoint for monitoring (liveness: app is running)."""
        return {"status": "healthy", "service": "CarModPicker API", "version": "1.0.0"}

    @app.get(
        "/ready",
        response_model=None,
        include_in_schema=False,
        description=(
            "Readiness check: returns 200 when DynamoDB is reachable, 503 otherwise.\n\n"
            "Use this so load balancers or the frontend can wait until the backend\n"
            "can reach its tables before sending traffic. During a cold start, poll\n"
            "/ready until 200, then call other endpoints."
        ),
    )
    def readiness_check() -> "Dict[str, Any] | JSONResponse":  # pyright: ignore[reportUnusedFunction]
        """Return 200 when DynamoDB is reachable and 503 otherwise.

        Lets a load balancer or the frontend hold traffic back until the backend
        can reach its tables.
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

    @app.get("/sitemap.xml", include_in_schema=False)
    def sitemap_index() -> Response:  # pyright: ignore[reportUnusedFunction]
        """The sitemap index listing every child sitemap."""
        return Response(
            content=sitemap_service.generate_sitemap_index(),
            media_type="application/xml",
            headers={"Cache-Control": _SITEMAP_CACHE},
        )

    @app.get("/sitemap-{name}.xml", include_in_schema=False)
    def sitemap_child(  # pyright: ignore[reportUnusedFunction]
        name: str,
        page: int = Query(1, ge=1),
    ) -> Response:
        """One page of a named child sitemap, or 404 when the name is unknown."""
        xml = sitemap_service.generate_child_sitemap(name, page)
        if xml is None:
            return Response(
                content="Not found",
                status_code=404,
                media_type="text/plain",
            )
        return Response(
            content=xml,
            media_type="application/xml",
            headers={"Cache-Control": _SITEMAP_CACHE},
        )


def _instrument(app: FastAPI, domains: "Sequence[Domain]" = ()) -> None:
    """Instrument the finished application, after this product's middleware is on.

    Last rather than through `build_domain_app(instrument=True)`, so the server span
    wraps the rate limiter rather than sitting underneath it.
    """
    del domains

    from webbpulse.otel import instrument_fastapi

    instrument_fastapi(app)


def build_domain_app(
    domains: "Domain | str | Sequence[Domain | str]",
    *,
    title: "str | None" = None,
    include_root_routes: bool = True,
    startup_tasks: "Callable[[], None] | None" = None,
) -> FastAPI:
    """Build one application from one domain or many: Root B's whole job.

    The package's builder with this product's hooks. `startup_tasks` is injectable
    so `app.main` can keep the module-level `run_startup_tasks` name the suite patches.
    """
    from webbpulse.composition import resolve_domains

    from app.common.api.middleware.error_handler import error_handler_options
    from app.common.composition.domains import DOMAINS, SEEDING_DOMAINS

    resolved = resolve_domains(domains, DOMAINS)
    seeds = any(domain.name in SEEDING_DOMAINS for domain in resolved)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """Verify the signing key, then run startup seeding when this domain seeds."""
        check_signing_key(resolved)
        if seeds and settings.RUN_STARTUP_TASKS:
            (startup_tasks or run_startup_tasks)()
        yield

    after_routers = [add_root_routes, _instrument] if include_root_routes else [_instrument]

    return _build_domain_app(
        resolved,
        registry=DOMAINS,
        settings=settings,
        title=title if title is not None else settings.PROJECT_NAME,
        service_name=resolved[0].service_name if len(resolved) == 1 else settings.PROJECT_NAME,
        configure=[add_shared_middleware],
        after_routers=after_routers,
        version=OPENAPI_VERSION,
        cors_allow_origins=settings.allowed_origins_list,
        cors_allow_headers=CORS_ALLOW_HEADERS,
        include_health=False,
        openapi_url=f"{settings.API_STR}/openapi.json",
        debug=settings.DEBUG,
        lifespan=lifespan,
        **error_handler_options(),
    )
