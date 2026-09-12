"""Rate limiting middleware, backed by the shared DynamoDB counter.

One layer only. The per-process in-memory limiter this module used to carry was
removed: it could not see across execution environments, so on Lambda it counted
a fraction of the traffic and its headers advertised an allowance no caller had.
"""

import logging
import os
from typing import Awaitable, Callable, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from ...core.config import settings
from .shared_rate_limiter import client_identity, request_route, shared_rate_limiter

logger = logging.getLogger(__name__)

RATE_LIMIT_EXEMPT_EXACT: Tuple[str, ...] = ("/", "/health", "/ready", "/openapi.json")

RATE_LIMIT_EXEMPT_PREFIXES: Tuple[str, ...] = ("/docs", "/redoc")


def is_rate_limit_exempt(path: str) -> bool:
    """Return True when ``path`` is exempt from rate limiting.

    Exemption is deliberately split into two kinds. Entries in
    ``RATE_LIMIT_EXEMPT_EXACT`` are matched exactly, so the root path "/" exempts only
    itself rather than the whole API.
    """
    if path in RATE_LIMIT_EXEMPT_EXACT:
        return True

    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in RATE_LIMIT_EXEMPT_PREFIXES)


def rate_limiting_enabled() -> bool:
    """Whether the middleware should count this process's requests at all."""
    if not settings.ENABLE_RATE_LIMITING:
        return False
    if os.getenv("ENABLE_RATE_LIMITING", "true").lower() == "false":
        return False
    return settings.ENABLE_SHARED_RATE_LIMITING


async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Count one request against the shared window and reject it once spent.

    The limiter fails open on every backend failure, so a DynamoDB outage costs
    availability nothing.
    """
    if not rate_limiting_enabled() or is_rate_limit_exempt(request.url.path):
        return await call_next(request)

    identity = client_identity(request)
    route = request.scope.get("route")
    route_label = getattr(route, "path", None) or request.url.path
    with request_route(route_label):
        limited, retry_after_seconds = shared_rate_limiter.check(identity)

    if limited:
        retry_after = retry_after_seconds or 60
        logger.warning("Shared rate limit exceeded for %s", shared_rate_limiter.client_key(identity))
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests",
                "message": "Rate limit exceeded",
                "retry_after": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Remaining-Minute": "0",
            },
        )

    return await call_next(request)
