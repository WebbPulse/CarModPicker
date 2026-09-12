"""Error handlers, delegating to the shared `webbpulse` envelope.

Every error response in this API is the org standard envelope::
{"success": false, "status": 404, "message": "...", "request_id": "...",
"""

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


def register_error_handlers(app: FastAPI) -> None:
    """Install the shared envelope handlers plus CarModPicker's DynamoDB ones.

    `error_codes=True` keeps the `error_code` key every existing client and test
    reads. `validation_details=True` keeps the 422 `details` list. A route that
    """
    from webbpulse.http import DynamoDBErrorHandlerOptions
    from webbpulse.http import register_error_handlers as register_shared_handlers

    register_shared_handlers(
        app,
        error_codes=True,
        validation_details=True,
        dynamodb=True,
        dynamodb_errors=DynamoDBErrorHandlerOptions(
            not_found_message=NOT_FOUND_MESSAGE,
            conflict_message=CONFLICT_MESSAGE,
            internal_error_message=INTERNAL_ERROR_MESSAGE,
        ),
        exception_map=DYNAMO_EXCEPTION_MAP,
    )
