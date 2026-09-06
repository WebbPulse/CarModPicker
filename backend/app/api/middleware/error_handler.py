"""
Error handling middleware for standardizing API error responses.

This middleware catches all HTTPExceptions and converts them to
standardized response formats using ResponsePatterns.
"""

import logging
from typing import Any, Awaitable, Callable, Dict, List

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """
    Middleware to catch and standardize all error responses.

    Args:
        request: FastAPI request object
        call_next: Next middleware/endpoint function

    Returns:
        Standardized error response or original response
    """
    try:
        response = await call_next(request)
        return response
    except HTTPException as exc:
        # Handle FastAPI HTTPExceptions
        return handle_http_exception(exc)
    except StarletteHTTPException as exc:
        # Handle Starlette HTTPExceptions - convert to FastAPI HTTPException
        headers_dict = dict(exc.headers) if exc.headers else None
        fastapi_exc = HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers_dict)
        return handle_http_exception(fastapi_exc)
    except RequestValidationError as exc:
        # Handle validation errors
        return handle_validation_error(exc)
    except Exception as exc:
        # Handle unexpected errors
        logger.error(f"Unexpected error in {request.url.path}: {str(exc)}", exc_info=True)
        return handle_unexpected_error(exc)


def handle_http_exception(exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPExceptions and convert to standardized format.

    Args:
        exc: HTTPException instance

    Returns:
        Standardized JSONResponse
    """
    # For 5xx server errors, always return a generic message to prevent exposing
    # stack traces or internal error details to the frontend
    if exc.status_code >= 500:
        # Log the actual error detail for debugging purposes (server-side only)
        logger.error(f"Server error ({exc.status_code}): {str(exc.detail)}", exc_info=False)
        # Return generic message based on status code
        if exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            error_message = "Internal server error"
        elif exc.status_code == status.HTTP_502_BAD_GATEWAY:
            error_message = "Bad gateway"
        elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            error_message = "Service unavailable"
        else:
            error_message = "Server error"
        error_data: Dict[str, str | bool] = {
            "success": False,
            "message": error_message,
            "error_code": get_error_code(exc.status_code),
        }
    else:
        # Handle dict details (for additional error information)
        if isinstance(exc.detail, dict):
            detail_dict: Dict[str, Any] = exc.detail  # type: ignore[assignment]
            error_message: str = str(detail_dict.get("message", str(exc.detail)))  # type: ignore[arg-type, misc]
            error_code: str = str(detail_dict.get("error_code", get_error_code(exc.status_code)))  # type: ignore[arg-type, misc]
            error_data_dict: Dict[str, Any] = {
                "success": False,
                "message": error_message,
                "error_code": error_code,
            }
            # Include additional details if present
            if "details" in detail_dict:
                error_data_dict["details"] = detail_dict["details"]  # type: ignore[index, misc]
            error_data = error_data_dict
        else:
            error_message = str(exc.detail)
            error_data_dict_else: Dict[str, str | bool] = {
                "success": False,
                "message": error_message,
                "error_code": get_error_code(exc.status_code),
            }
            error_data = error_data_dict_else

    return JSONResponse(content=error_data, status_code=exc.status_code, headers=exc.headers)


def handle_validation_error(exc: RequestValidationError) -> JSONResponse:
    """
    Handle validation errors and convert to standardized format.

    Args:
        exc: RequestValidationError instance

    Returns:
        Standardized JSONResponse
    """
    error_details: List[Dict[str, str]] = []
    for error in exc.errors():
        error_details.append(
            {
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    error_data: Dict[str, str | bool | List[Dict[str, str]]] = {
        "success": False,
        "message": "Validation error",
        "error_code": "VALIDATION_ERROR",
        "details": error_details,
    }

    return JSONResponse(content=error_data, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


def handle_unexpected_error(exc: Exception) -> JSONResponse:
    """Handle unexpected errors and convert to standardized format."""
    error_data: Dict[str, str | bool] = {
        "success": False,
        "message": "Internal server error",
        "error_code": "INTERNAL_ERROR",
    }

    return JSONResponse(content=error_data, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def handle_item_not_found(exc: ItemNotFound) -> JSONResponse:
    logger.info("DynamoDB item not found in %s: %s", exc.table, exc.key)
    error_data: Dict[str, str | bool] = {
        "success": False,
        "message": "Resource not found",
        "error_code": get_error_code(status.HTTP_404_NOT_FOUND),
    }
    return JSONResponse(content=error_data, status_code=status.HTTP_404_NOT_FOUND)


def handle_condition_failed(exc: ConditionFailed | TransactionCanceled) -> JSONResponse:
    logger.warning("DynamoDB condition failed: %s", exc)
    error_data: Dict[str, str | bool] = {
        "success": False,
        "message": "Resource already exists or was modified concurrently",
        "error_code": get_error_code(status.HTTP_409_CONFLICT),
    }
    return JSONResponse(content=error_data, status_code=status.HTTP_409_CONFLICT)


def get_error_code(status_code: int) -> str:
    """
    Get standardized error code based on HTTP status code.

    Args:
        status_code: HTTP status code

    Returns:
        Standardized error code string
    """
    error_codes = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "PAYLOAD_TOO_LARGE",
        422: "VALIDATION_ERROR",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }

    return error_codes.get(status_code, "UNKNOWN_ERROR")


def register_error_handlers(app: FastAPI) -> None:
    """
    Register error handlers with FastAPI app.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return handle_http_exception(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return handle_validation_error(exc)

    @app.exception_handler(ItemNotFound)
    async def item_not_found_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ItemNotFound
    ) -> JSONResponse:
        return handle_item_not_found(exc)

    @app.exception_handler(ConditionFailed)
    async def condition_failed_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ConditionFailed
    ) -> JSONResponse:
        return handle_condition_failed(exc)

    @app.exception_handler(TransactionCanceled)
    async def transaction_canceled_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: TransactionCanceled
    ) -> JSONResponse:
        if exc.conditional_check_failed:
            return handle_condition_failed(exc)
        logger.error(f"Transaction canceled in {request.url.path}: {str(exc)}", exc_info=True)
        return handle_unexpected_error(exc)

    @app.exception_handler(Exception)
    async def general_exception_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(f"Unhandled exception in {request.url.path}: {str(exc)}", exc_info=True)
        return handle_unexpected_error(exc)
