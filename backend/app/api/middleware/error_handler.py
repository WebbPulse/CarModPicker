"""Error handlers, delegating to the shared `webbpulse` envelope.

Every error response in this API is the org standard envelope::
{"success": false, "status": 404, "message": "...", "request_id": "...",
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from webbpulse.dynamodb import TransactionCanceled
from webbpulse.http import ErrorSpec, error_body

from app.db.dynamo.users import UniqueAttributeTaken

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = "Resource not found"

CONFLICT_MESSAGE = "Resource already exists or was modified concurrently"

DYNAMO_EXCEPTION_MAP: dict[type[BaseException], int | ErrorSpec] = {
    UniqueAttributeTaken: ErrorSpec(
        status.HTTP_409_CONFLICT,
        message="That username or email is already taken",
        error_code="CONFLICT",
    ),
}


def register_error_handlers(app: FastAPI) -> None:
    """Install the shared envelope handlers plus CarModPicker's DynamoDB ones.

    `error_codes=True` keeps the `error_code` key every existing client and test
    reads. `validation_details=True` keeps the 422 `details` list. A route that
    """
    from webbpulse.http import install_dynamodb_error_handlers
    from webbpulse.http import register_error_handlers as register_shared_handlers

    register_shared_handlers(
        app,
        error_codes=True,
        validation_details=True,
        dynamodb=True,
        exception_map=DYNAMO_EXCEPTION_MAP,
    )

    install_dynamodb_error_handlers(
        app,
        error_codes=True,
        not_found_message=NOT_FOUND_MESSAGE,
        conflict_message=CONFLICT_MESSAGE,
    )

    @app.exception_handler(TransactionCanceled)
    async def transaction_canceled_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: TransactionCanceled
    ) -> JSONResponse:
        """Map a cancelled DynamoDB transaction to a 409 or 500 response.

        Stays local because the package renders its unhandled branch as
        "Internal server error." with a trailing period, and this API's 500 body
        has carried the unpunctuated string since before the package existed.
        """
        if exc.conditional_check_failed:
            logger.warning("DynamoDB condition failed: %s", exc)
            return JSONResponse(
                content=error_body(
                    status.HTTP_409_CONFLICT,
                    CONFLICT_MESSAGE,
                    request,
                    error_code="CONFLICT",
                ),
                status_code=status.HTTP_409_CONFLICT,
            )
        logger.error(f"Transaction canceled in {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            content=error_body(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Internal server error",
                request,
                error_code="INTERNAL_ERROR",
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
