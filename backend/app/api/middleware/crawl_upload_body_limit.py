"""
Reject oversized JSON bodies on Chrome extension crawl upload routes using Content-Length.

Full UTF-8 validation of the `html` field happens in route handlers; this middleware only
avoids pointless work when the entire HTTP body is already too large.
"""

import logging
from typing import Awaitable, Callable

from fastapi import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)


def _crawl_upload_paths() -> frozenset[str]:
    base = settings.API_STR.rstrip("/")
    return frozenset(
        {
            f"{base}/crawled-pages/scrape",
            f"{base}/crawled-pages/html",
        }
    )


async def crawl_upload_content_length_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method != "POST" or request.url.path not in _crawl_upload_paths():
        return await call_next(request)

    raw_cl = request.headers.get("content-length")
    if not raw_cl:
        return await call_next(request)
    try:
        content_length = int(raw_cl)
    except ValueError:
        return await call_next(request)

    max_body = settings.CRAWLED_PAGE_MAX_HTML_BYTES + settings.CRAWLED_PAGE_UPLOAD_CONTENT_LENGTH_SLACK_BYTES
    if content_length > max_body:
        logger.warning(
            "Crawl upload rejected by Content-Length path=%s content_length=%s max_allowed=%s",
            request.url.path,
            content_length,
            max_body,
        )
        return JSONResponse(
            status_code=413,
            content={
                "detail": (
                    f"Request body exceeds maximum allowed size ({max_body} bytes). "
                    "Reduce page HTML size or raise CRAWLED_PAGE_MAX_HTML_BYTES."
                )
            },
        )

    return await call_next(request)
