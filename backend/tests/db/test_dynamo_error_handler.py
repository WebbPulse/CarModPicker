"""The repository exceptions' rendering, pinned field by field.

Moving a handler into the shared package cannot change what a caller receives.
"""

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.testclient import TestClient
from webbpulse.dynamodb import ConditionFailed, ItemNotFound, TransactionCanceled
from webbpulse.http import ErrorSpec

from app.api.middleware.error_handler import register_error_handlers
from app.api.middleware.request_context import request_context_middleware
from app.db.dynamo.users import UniqueAttributeTaken

NOT_FOUND_BODY = {
    "success": False,
    "status": 404,
    "message": "Resource not found",
    "error_code": "NOT_FOUND",
}
CONFLICT_BODY = {
    "success": False,
    "status": 409,
    "message": "Resource already exists or was modified concurrently",
    "error_code": "CONFLICT",
}
TAKEN_BODY = {
    "success": False,
    "status": 409,
    "message": "That username or email is already taken",
    "error_code": "CONFLICT",
}
INTERNAL_BODY = {
    "success": False,
    "status": 500,
    "message": "Internal server error",
    "error_code": "INTERNAL_ERROR",
}


def assert_body(body: Dict[str, Any], expected: Dict[str, Any]) -> None:
    """The whole envelope, with a real request id and nothing else besides."""
    assert body.keys() == expected.keys() | {"request_id"}
    assert {key: body[key] for key in expected} == expected
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"
    assert "detail" not in body


def build_app() -> FastAPI:
    """An application with the error handlers and one route per repository exception."""
    app = FastAPI()
    app.middleware("http")(request_context_middleware)
    register_error_handlers(app)

    @app.get("/missing")
    def missing() -> None:
        """Raise ItemNotFound."""
        raise ItemNotFound("test-users", {"id": "abc"})

    @app.get("/duplicate")
    def duplicate() -> None:
        """Raise ConditionFailed."""
        raise ConditionFailed("test-users", "attribute_not_exists(id)", {"id": "abc"})

    @app.get("/taken")
    def taken() -> None:
        """Raise UniqueAttributeTaken."""
        raise UniqueAttributeTaken("username")

    @app.get("/canceled-conditional")
    def canceled_conditional() -> None:
        """Raise TransactionCanceled with a failed condition reason."""
        raise TransactionCanceled([{"Code": "None"}, {"Code": "ConditionalCheckFailed"}])

    @app.get("/canceled-other")
    def canceled_other() -> None:
        """Raise TransactionCanceled with a conflict reason."""
        raise TransactionCanceled([{"Code": "TransactionConflict"}])

    return app


def test_item_not_found_maps_to_404() -> None:
    """Mapped by `exception_map`; the table name and key are logged, not returned."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/missing")
    assert response.status_code == 404
    assert_body(response.json(), NOT_FOUND_BODY)
    assert "test-users" not in response.text


def test_condition_failed_maps_to_409() -> None:
    """Mapped by `exception_map`; the DynamoDB condition never reaches the caller."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/duplicate")
    assert response.status_code == 409
    assert_body(response.json(), CONFLICT_BODY)
    assert "attribute_not_exists" not in response.text


def test_unique_attribute_taken_maps_to_409() -> None:
    """A taken username or email is a conflict, not a fault.

    The identity register flow reaches this through the `create_user` hook, so
    without the mapping a duplicate signup renders as a 500.
    """
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/taken")
    assert response.status_code == 409
    assert_body(response.json(), TAKEN_BODY)


def test_conditional_transaction_cancel_maps_to_409() -> None:
    """A cancellation caused by a failed condition reads as an ordinary lost race."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/canceled-conditional")
    assert response.status_code == 409
    assert_body(response.json(), CONFLICT_BODY)


def test_other_transaction_cancel_maps_to_500() -> None:
    """Anything else is a real fault, which is why this one is not in `exception_map`."""
    client = TestClient(build_app(), raise_server_exceptions=False)
    response = client.get("/canceled-other")
    assert response.status_code == 500
    assert_body(response.json(), INTERNAL_BODY)
    assert "TransactionConflict" not in response.text


def test_exception_map_declares_the_unique_attribute_rendering() -> None:
    """The map now holds only `UniqueAttributeTaken`.

    `ItemNotFound` and `ConditionFailed` moved to the package's own handlers, and
    `TransactionCanceled` stays out because mapping it would flatten a real fault
    into a 409.
    """
    from app.api.middleware.error_handler import DYNAMO_EXCEPTION_MAP

    assert set(DYNAMO_EXCEPTION_MAP) == {UniqueAttributeTaken}
    assert ItemNotFound not in DYNAMO_EXCEPTION_MAP
    assert ConditionFailed not in DYNAMO_EXCEPTION_MAP
    assert TransactionCanceled not in DYNAMO_EXCEPTION_MAP

    taken = DYNAMO_EXCEPTION_MAP[UniqueAttributeTaken]
    assert isinstance(taken, ErrorSpec)
    assert (taken.status, taken.message, taken.error_code) == (
        409,
        TAKEN_BODY["message"],
        TAKEN_BODY["error_code"],
    )


def test_package_handlers_render_the_configured_messages() -> None:
    """The 404 and 409 wording comes from the constants handed to the package."""
    from app.api.middleware.error_handler import CONFLICT_MESSAGE, NOT_FOUND_MESSAGE

    assert NOT_FOUND_MESSAGE == NOT_FOUND_BODY["message"]
    assert CONFLICT_MESSAGE == CONFLICT_BODY["message"]
