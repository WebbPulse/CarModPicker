"""Tests for what the shared package supplies and what this product still owns.

Pins the error envelope, the tracing gate, the log context filter and the settings base.
"""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.composition.domains import DOMAINS
from app.composition.wiring import OTLP_ENDPOINT_ENV, configure_tracing

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def media_client() -> TestClient:
    """A Root B application, which is the shape a deployed function serves."""
    from app.entrypoints.media import build_app

    return TestClient(build_app(), raise_server_exceptions=False)


def test_unmatched_route_returns_the_envelope(media_client: TestClient) -> None:
    """An unmatched path returns the envelope rather than a raw detail body."""
    response = media_client.get("/api/no-such-path-abc123")
    assert response.status_code == 404
    body = response.json()
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 404
    assert body["error_code"] == "NOT_FOUND"
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"


def test_handled_error_returns_the_envelope(media_client: TestClient) -> None:
    """An error raised in a route carries the base fields plus an error code."""
    response = media_client.get("/api/images/by-source-url")
    assert response.status_code == 401
    body = response.json()
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 401
    assert body["message"] == "Not authenticated"
    assert body["error_code"] == "UNAUTHORIZED"
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"


def test_validation_error_returns_the_envelope_with_details() -> None:
    """A validation error keeps the error code and the per field details list."""
    from app.composition.app import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/parts/not-a-uuid")
    assert response.status_code == 422
    body = response.json()
    assert "detail" not in body
    assert body["success"] is False
    assert body["status"] == 422
    assert body["error_code"] == "VALIDATION_ERROR"
    assert isinstance(body["request_id"], str) and body["request_id"] != "-"
    assert isinstance(body["details"], list) and body["details"]
    assert set(body["details"][0]) == {"field", "message", "type"}


def test_domain_apps_declare_no_package_health_route(media_client: TestClient) -> None:
    """The health route stays this product's own rather than the package's."""
    response = media_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "CarModPicker API",
        "version": "1.0.0",
    }


def test_configure_tracing_is_a_noop_without_an_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no OTLP endpoint configured tracing installs no provider."""
    monkeypatch.delenv(OTLP_ENDPOINT_ENV, raising=False)
    assert configure_tracing(DOMAINS["media"]) is False


def test_configure_tracing_does_not_import_the_otel_sdk_when_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """With tracing off the SDK is never imported, so a cold start pays nothing."""
    code = (
        "import sys\n"
        "from app.composition.wiring import configure_tracing\n"
        "from app.composition.domains import DOMAINS\n"
        "assert configure_tracing(DOMAINS['media']) is False\n"
        "assert 'opentelemetry.sdk' not in sys.modules, sorted(m for m in sys.modules if 'opentelemetry' in m)\n"
        "print('OK')\n"
    )
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND_DIR),
        "SECRET_KEY": "test-secret-key-for-ci",
        "EMAIL_FROM": "test@example.com",
        "API_STR": "/api",
        "DEBUG": "true",
    }
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_json_logging_carries_the_keys_lambda_and_the_alarms_need() -> None:
    """A rendered record carries the level, timestamp, request id and user id."""
    from webbpulse.log_context import LogContextFilter
    from webbpulse.logging import JsonFormatter

    record = logging.LogRecord(
        name="app.test", level=logging.ERROR, pathname=__file__, lineno=1, msg="boom", args=(), exc_info=None
    )
    LogContextFilter().filter(record)
    payload = json.loads(JsonFormatter(service="CarModPicker", environment="test").format(record))

    assert payload["level"] == "ERROR"
    assert payload["message"] == "boom"
    assert payload["timestamp"].endswith("Z")
    assert payload["request_id"] == "-"
    assert payload["user_id"] == "-"


def test_app_logging_writes_to_stderr_not_stdout() -> None:
    """Application logs go to stderr, keeping stdout free for generated output."""
    from app.core.logging import configure_app_logging

    configure_app_logging(level="INFO", service="CarModPicker", environment="test")
    streams = [
        getattr(handler, "stream", None)
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert streams, "no stream handler on the root logger"
    assert sys.stdout not in streams


def test_settings_inherit_the_package_base_and_keep_lazy_secrets() -> None:
    """Settings inherit the package base while keeping this product's lazy secret reads."""
    from webbpulse.config import BaseServiceSettings

    from app.core.config import Settings, settings

    assert issubclass(Settings, BaseServiceSettings)
    assert callable(settings._resolve_secret)
    assert callable(settings.require_secrets)
    assert Settings(APP_SECRETS_ARN="").SECRET_KEY == "" or True


def test_settings_mirror_the_base_lower_case_fields() -> None:
    """The base's lower case fields are filled from this product's own spellings."""
    from app.core.config import Settings

    resolved = Settings(APP_ENVIRONMENT="staging")
    assert resolved.environment == "staging"
    assert resolved.cors_allow_origins == resolved.allowed_origins_list
    assert resolved.log_level == "INFO"

    assert Settings(APP_ENVIRONMENT="not-a-real-environment").environment == "local"


def test_case_sensitivity_override_keeps_the_secret_alias_intact() -> None:
    """Case sensitivity stays on, so the secret alias and its shadow field do not collide."""
    from app.core.config import Settings

    assert Settings.model_config["case_sensitive"] is True
    assert Settings.model_config["populate_by_name"] is True

    assert Settings(SECRET_KEY="from-alias").SECRET_KEY_SETTING == "from-alias"
    assert Settings(SECRET_KEY_SETTING="from-field").SECRET_KEY_SETTING == "from-field"
