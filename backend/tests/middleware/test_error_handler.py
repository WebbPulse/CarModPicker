"""Tests for error handler middleware."""

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.middleware.error_handler import (
    get_error_code,
    handle_http_exception,
    handle_unexpected_error,
    handle_validation_error,
)


class TestErrorHandler:
    """Test cases for error handler middleware."""

    def test_handle_http_exception_4xx(self) -> None:
        """Test handling 4xx HTTP exceptions."""
        exc = HTTPException(status_code=404, detail="Not found")
        response = handle_http_exception(exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        content = response.body.decode()
        assert "Not found" in content
        assert "success" in content
        assert "false" in content.lower()

    def test_handle_http_exception_5xx(self) -> None:
        """Test handling 5xx HTTP exceptions (should sanitize message)."""
        exc = HTTPException(status_code=500, detail="Internal error details")
        response = handle_http_exception(exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        content = response.body.decode()
        # Should not contain internal error details
        assert "Internal error details" not in content
        assert "Internal server error" in content

    def test_handle_validation_error(self) -> None:
        """Test handling validation errors."""
        errors = [
            {"loc": ("body", "name"), "msg": "field required", "type": "value_error.missing"},
            {"loc": ("body", "email"), "msg": "invalid email", "type": "value_error"},
        ]
        exc = RequestValidationError(errors)
        response = handle_validation_error(exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
        content = response.body.decode()
        assert "Validation error" in content
        assert "details" in content

    def test_handle_unexpected_error(self) -> None:
        """Test handling unexpected errors."""
        exc = Exception("Unexpected error")
        response = handle_unexpected_error(exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        content = response.body.decode()
        assert "Internal server error" in content
        assert "Unexpected error" not in content  # Should be sanitized

    def test_get_error_code_known_codes(self) -> None:
        """Test getting error codes for known status codes."""
        assert get_error_code(400) == "BAD_REQUEST"
        assert get_error_code(401) == "UNAUTHORIZED"
        assert get_error_code(403) == "FORBIDDEN"
        assert get_error_code(404) == "NOT_FOUND"
        assert get_error_code(409) == "CONFLICT"
        assert get_error_code(422) == "VALIDATION_ERROR"
        assert get_error_code(500) == "INTERNAL_ERROR"

    def test_get_error_code_unknown_code(self) -> None:
        """Test getting error code for unknown status code."""
        assert get_error_code(999) == "UNKNOWN_ERROR"
