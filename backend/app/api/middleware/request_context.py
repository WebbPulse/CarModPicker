from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import Response
from uuid6 import uuid7

from app.core.log_context import request_id_var


async def request_context_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    req_id = request.headers.get("X-Request-ID") or str(uuid7())
    token = request_id_var.set(req_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
    finally:
        request_id_var.reset(token)
