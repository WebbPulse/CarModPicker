"""Error handlers, delegating to the shared `webbpulse` envelope.

Every error response in this API is the org standard envelope::
{"success": false, "status": 404, "message": "...", "request_id": "...",
"""

from typing import Any

from fastapi import FastAPI, status
from webbpulse.http import ErrorSpec

from app.db.dynamo.users import UniqueAttributeTaken

NOT_FOUND_MESSAGE = "Resource not found"

CONFLICT_MESSAGE = "Resource already exists or was modified concurrently"

INTERNAL_ERROR_MESSAGE = "Internal server error"

DYNAMO_EXCEPTION_MAP: dict[type[BaseException], int | ErrorSpec] = {
    UniqueAttributeTaken: ErrorSpec(
        status.HTTP_409_CONFLICT,
        message="That username or email is already taken",
        error_code="CONFLICT",
    ),
}


def error_handler_options() -> dict[str, Any]:
    """CarModPicker's error handler arguments, shared by `create_app` and the suite.

    `error_codes=True` keeps the `error_code` key every existing client and test
    reads. `validation_details=True` keeps the 422 `details` list. `error_envelope`
    is deliberately unset: the exact-body tests pin the current shape.
    """
    from webbpulse.http import DynamoDBErrorHandlerOptions

    return {
        "error_codes": True,
        "validation_details": True,
        "dynamodb_handlers": True,
        "dynamodb_error_handlers": DynamoDBErrorHandlerOptions(
            not_found_message=NOT_FOUND_MESSAGE,
            conflict_message=CONFLICT_MESSAGE,
            internal_error_message=INTERNAL_ERROR_MESSAGE,
        ),
        "exception_map": DYNAMO_EXCEPTION_MAP,
    }


def register_error_handlers(app: FastAPI) -> None:
    """Install the shared envelope handlers plus CarModPicker's DynamoDB ones.

    The standalone path, for an app not built through `create_app`.
    """
    from webbpulse.http import register_error_handlers as register_shared_handlers

    options = error_handler_options()
    register_shared_handlers(
        app,
        error_codes=options["error_codes"],
        validation_details=options["validation_details"],
        dynamodb=options["dynamodb_handlers"],
        dynamodb_errors=options["dynamodb_error_handlers"],
        exception_map=options["exception_map"],
    )
