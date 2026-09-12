"""Tests for the backend Sentry initialisation: gating, kwargs, sampling and scope."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from webbpulse.log_context import request_id_var, user_id_var

from app.core.sentry import _before_send, _traces_sampler, init_sentry


class TestInitGating:
    """The three conditions under which initialisation is skipped."""

    def test_testing_true_skips_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Initialisation is skipped while the testing flag is set."""
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "true")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 0

    def test_wrong_environment_skips_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Initialisation is skipped outside the enabled environments."""
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setattr("app.core.sentry.settings.APP_ENVIRONMENT", "development")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 0

    def test_empty_dsn_skips_init(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Initialisation is skipped when no DSN is configured."""
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setenv("SENTRY_DSN", "")
        monkeypatch.setattr("app.core.sentry.settings.APP_ENVIRONMENT", "staging")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 0


class TestInitKwargs:
    """The arguments passed to the SDK when initialisation does fire."""

    @pytest.fixture
    def active_init(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """Initialise Sentry against a mock SDK and return the mock."""
        mock_init = MagicMock()
        monkeypatch.setattr("app.core.sentry.sentry_sdk.init", mock_init)
        monkeypatch.setenv("TESTING", "")
        monkeypatch.setenv("SENTRY_DSN", "http://key@localhost/1")
        monkeypatch.setenv("SENTRY_RELEASE", "abc123")
        monkeypatch.setattr("app.core.sentry.settings.APP_ENVIRONMENT", "staging")
        init_sentry(server_name="apprunner-backend")
        assert mock_init.call_count == 1
        return mock_init

    def test_send_default_pii_false(self, active_init: MagicMock) -> None:
        """Personally identifiable information is not sent by default."""
        kwargs = active_init.call_args.kwargs
        assert kwargs["send_default_pii"] is False

    def test_server_name_passed(self, active_init: MagicMock) -> None:
        """The server name reaches the SDK."""
        assert active_init.call_args.kwargs["server_name"] == "apprunner-backend"

    def test_release_from_env(self, active_init: MagicMock) -> None:
        """The release is taken from the environment."""
        assert active_init.call_args.kwargs["release"] == "abc123"

    def test_environment_tag(self, active_init: MagicMock) -> None:
        """The environment tag is taken from the settings."""
        assert active_init.call_args.kwargs["environment"] == "staging"

    def test_traces_sampler_is_callable(self, active_init: MagicMock) -> None:
        """A traces sampler callable is supplied rather than a fixed rate."""
        assert callable(active_init.call_args.kwargs["traces_sampler"])

    def test_ignore_errors_strings(self, active_init: MagicMock) -> None:
        """Ignored errors are named as strings, which is what this SDK version matches on."""
        ignore = active_init.call_args.kwargs["ignore_errors"]
        assert "fastapi.exceptions.HTTPException" in ignore
        assert "starlette.exceptions.HTTPException" in ignore
        assert "slowapi.errors.RateLimitExceeded" in ignore

    def test_all_three_integrations_loaded(self, active_init: MagicMock) -> None:
        """Starlette, FastAPI and logging integrations are all passed explicitly."""
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        integrations = active_init.call_args.kwargs["integrations"]
        types = {type(i) for i in integrations}
        assert StarletteIntegration in types
        assert FastApiIntegration in types
        assert LoggingIntegration in types


class TestTracesSampler:
    """The sampling rate the traces sampler returns per transaction."""

    @pytest.mark.parametrize("path", ["/health", "/ready", "/openapi.json", "health_check", "api/ready", "openapi"])
    def test_health_routes_zero(self, path: str) -> None:
        """Health transactions are never sampled."""
        assert _traces_sampler({"transaction_context": {"name": path}}) == 0.0

    @pytest.mark.parametrize("path", ["/api/users/me", "users.read_user_by_id", "/api/cars/1"])
    def test_real_routes_sampled(self, path: str) -> None:
        """Ordinary transactions are sampled at the default rate."""
        assert _traces_sampler({"transaction_context": {"name": path}}) == 0.05

    def test_empty_name_sampled(self) -> None:
        """A missing transaction name falls through to the default rate."""
        assert _traces_sampler({}) == 0.05


class TestBeforeSend:
    """The scope processor that attaches the request and user ids."""

    def test_attaches_request_id_when_set(self) -> None:
        """A set request id is attached as a tag."""
        token = request_id_var.set("abc-123")
        try:
            event = _before_send({}, None)
            assert event["tags"]["request_id"] == "abc-123"
        finally:
            request_id_var.reset(token)

    def test_attaches_user_id_when_set(self) -> None:
        """A set user id is attached to the event's user."""
        token = user_id_var.set("42")
        try:
            event = _before_send({}, None)
            assert event["user"]["id"] == "42"
        finally:
            user_id_var.reset(token)

    def test_no_tag_when_default(self) -> None:
        """With the context variables unset neither tag nor user is added."""
        event = _before_send({}, None)
        assert "tags" not in event or "request_id" not in event.get("tags", {})
        assert "user" not in event or "id" not in event.get("user", {})


class TestIgnoreErrorsIntegration:
    """Ignored errors through the real SDK and a capturing transport."""

    def test_http_exception_not_captured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An HTTP exception produces no envelope, so the ignore list matches."""
        import sentry_sdk

        from tests.conftest import _CapturingTransport

        sentry_sdk.init(
            dsn="http://key@localhost/1",
            transport=_CapturingTransport,
            ignore_errors=[
                "fastapi.exceptions.HTTPException",
                "starlette.exceptions.HTTPException",
            ],
        )
        _CapturingTransport.events = []

        from fastapi import HTTPException

        try:
            raise HTTPException(status_code=404, detail="not found")
        except HTTPException as exc:
            sentry_sdk.capture_exception(exc)

        assert len(_CapturingTransport.events) == 0, (
            "HTTPException leaked to Sentry — ignore_errors string format "
            "not working on this SDK version (Landmine 1)"
        )
        client = sentry_sdk.get_client()
        if client is not None:
            client.close()

    def test_runtime_error_captured(self, sentry_events) -> None:
        """A runtime error does produce an envelope, proving the transport works."""
        import sentry_sdk

        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            sentry_sdk.capture_exception(exc)
        sentry_sdk.flush(timeout=2.0)
        from tests.conftest import _CapturingTransport

        assert len(_CapturingTransport.events) >= 1 or len(sentry_events) >= 1
