"""
Tests for sophisticated rate limiting functionality.
"""

import os
import time
import unittest.mock
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.middleware.rate_limiter as rate_limiter_module
from app.api.middleware.rate_limiter import (
    RateLimitConfig,
    SophisticatedRateLimiter,
    is_rate_limit_exempt,
    rate_limit_middleware,
)
from app.main import app


class TestRateLimitConfig:
    """Test cases for the RateLimitConfig class."""

    def test_rate_limit_config_defaults(self) -> None:
        """Test rate limit config initialization with default values."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.get_requests_per_minute == 120
        assert config.get_requests_per_hour == 2000
        assert config.auth_requests_per_minute == 10
        assert config.auth_requests_per_hour == 100
        assert config.admin_requests_per_minute == 30
        assert config.admin_requests_per_hour == 300

    def test_rate_limit_config_custom_values(self) -> None:
        """Test rate limit config initialization with custom values."""
        config = RateLimitConfig(
            requests_per_minute=30,
            requests_per_hour=500,
            get_requests_per_minute=60,
            get_requests_per_hour=1000,
            auth_requests_per_minute=5,
            auth_requests_per_hour=50,
            admin_requests_per_minute=15,
            admin_requests_per_hour=150,
        )
        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.get_requests_per_minute == 60
        assert config.get_requests_per_hour == 1000
        assert config.auth_requests_per_minute == 5
        assert config.auth_requests_per_hour == 50
        assert config.admin_requests_per_minute == 15
        assert config.admin_requests_per_hour == 150


class TestSophisticatedRateLimiter:
    """Test cases for the SophisticatedRateLimiter class."""

    def test_rate_limiter_initialization(self) -> None:
        """Test rate limiter initialization with default config."""
        limiter = SophisticatedRateLimiter()
        assert limiter.config.requests_per_minute == 60
        assert limiter.config.requests_per_hour == 1000

    def test_rate_limiter_custom_config(self) -> None:
        """Test rate limiter initialization with custom config."""
        config = RateLimitConfig(requests_per_minute=30, requests_per_hour=500)
        limiter = SophisticatedRateLimiter(config)
        assert limiter.config.requests_per_minute == 30
        assert limiter.config.requests_per_hour == 500

    def test_get_client_ip_direct(self) -> None:
        """Test getting client IP from direct connection."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"

        ip = limiter._get_client_ip(request)  # pyright: ignore[reportPrivateUsage]
        assert ip == "192.168.1.1"

    def test_get_client_ip_proxy(self) -> None:
        """Test getting client IP from proxy headers."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
        request.client.host = "10.0.0.1"

        ip = limiter._get_client_ip(request)  # pyright: ignore[reportPrivateUsage]
        assert ip == "203.0.113.1"

    def test_get_rate_limit_key_default(self) -> None:
        """Test rate limit key generation for default endpoints."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        key = limiter._get_rate_limit_key(request)  # pyright: ignore[reportPrivateUsage]
        assert key == "default:192.168.1.1"

    def test_get_rate_limit_key_get(self) -> None:
        """Test rate limit key generation for GET requests."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "GET"

        key = limiter._get_rate_limit_key(request)  # pyright: ignore[reportPrivateUsage]
        assert key == "get:192.168.1.1"

    def test_get_rate_limit_key_auth(self) -> None:
        """Test rate limit key generation for auth endpoints."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/auth/login"
        request.method = "POST"

        key = limiter._get_rate_limit_key(request)  # pyright: ignore[reportPrivateUsage]
        assert key == "auth:192.168.1.1"

    def test_get_rate_limit_key_admin(self) -> None:
        """Test rate limit key generation for admin endpoints."""
        limiter = SophisticatedRateLimiter()
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/admin/users"
        request.method = "GET"

        key = limiter._get_rate_limit_key(request)  # pyright: ignore[reportPrivateUsage]
        assert key == "admin:192.168.1.1"

    def test_rate_limiting_default_minute_limit(self) -> None:
        """Test default minute rate limiting."""
        config = RateLimitConfig(requests_per_minute=2, requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_rate_limiting_get_minute_limit(self) -> None:
        """Test GET minute rate limiting."""
        config = RateLimitConfig(get_requests_per_minute=2, get_requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "GET"

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_rate_limiting_auth_minute_limit(self) -> None:
        """Test auth minute rate limiting."""
        config = RateLimitConfig(auth_requests_per_minute=2, auth_requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/auth/login"
        request.method = "POST"

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited
        assert reason == ""

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_rate_limiting_hour_limit(self) -> None:
        """Test hour rate limiting."""
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=2)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert not is_limited

        is_limited, reason, _ = limiter.is_rate_limited(request)
        assert is_limited
        assert "Rate limit exceeded" in reason

    def test_cleanup_old_requests(self) -> None:
        """Test cleanup of old requests."""
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        current_time = time.time()

        old_time = current_time - 7200
        limiter.minute_requests["default:192.168.1.1"] = [old_time, old_time]
        limiter.hour_requests["default:192.168.1.1"] = [old_time, old_time]

        recent_time = current_time - 30
        limiter.minute_requests["default:192.168.1.1"].append(recent_time)
        limiter.hour_requests["default:192.168.1.1"].append(recent_time)

        assert len(limiter.minute_requests["default:192.168.1.1"]) == 3
        assert len(limiter.hour_requests["default:192.168.1.1"]) == 3

        with unittest.mock.patch("time.time", return_value=current_time):
            limiter._cleanup_old_requests(  # pyright: ignore[reportPrivateUsage]
                "default:192.168.1.1", 60, limiter.minute_requests
            )
            limiter._cleanup_old_requests(  # pyright: ignore[reportPrivateUsage]
                "default:192.168.1.1", 3600, limiter.hour_requests
            )

        assert len(limiter.minute_requests["default:192.168.1.1"]) == 1
        assert len(limiter.hour_requests["default:192.168.1.1"]) == 1
        assert limiter.minute_requests["default:192.168.1.1"][0] == recent_time
        assert limiter.hour_requests["default:192.168.1.1"][0] == recent_time

    def test_get_remaining_requests(self) -> None:
        """Test getting remaining request counts."""
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100)
        limiter = SophisticatedRateLimiter(config)
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        request.url.path = "/api/cars"
        request.method = "POST"

        current_time = time.time()
        limiter.minute_requests["default:192.168.1.1"] = [
            current_time - 10,
            current_time - 20,
        ]
        limiter.hour_requests["default:192.168.1.1"] = [
            current_time - 100,
            current_time - 200,
        ]

        remaining = limiter.get_remaining_requests(request)

        assert remaining["minute_remaining"] == 8
        assert remaining["hour_remaining"] == 98
        assert "minute_reset" in remaining
        assert "hour_reset" in remaining
        assert "minute_limit" in remaining
        assert "hour_limit" in remaining


class TestRateLimitMiddleware:
    """Test cases for the rate limiting middleware."""

    def test_middleware_skips_health_check(self) -> None:
        """Test that middleware skips rate limiting for health checks."""
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_middleware_skips_docs(self) -> None:
        """Test that middleware skips rate limiting for docs."""
        client = TestClient(app)

        response = client.get("/docs")
        assert response.status_code == 200

    def test_middleware_skips_redoc(self) -> None:
        """Test that middleware skips rate limiting for redoc."""
        client = TestClient(app)

        response = client.get("/redoc")
        assert response.status_code == 200

    def test_middleware_rate_limiting(self) -> None:
        """Test that middleware properly rate limits requests."""
        from fastapi import FastAPI

        from app.api.middleware.rate_limiter import (
            RateLimitConfig,
            SophisticatedRateLimiter,
        )

        test_app = FastAPI()
        config = RateLimitConfig(requests_per_minute=1, requests_per_hour=2)
        test_limiter = SophisticatedRateLimiter(config)

        import app.api.middleware.rate_limiter as rate_limiter_module

        original_limiter = rate_limiter_module.rate_limiter
        rate_limiter_module.rate_limiter = test_limiter

        try:
            test_app.middleware("http")(rate_limit_middleware)

            @test_app.get("/test")
            def test_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
                """A route the middleware should limit."""
                return {"message": "test"}

            client = TestClient(test_app)

            response = client.get("/test")
            assert response.status_code == 200

            response = client.get("/test")
            assert response.status_code == 200

        finally:
            rate_limiter_module.rate_limiter = original_limiter


class TestRateLimitExemptPaths:
    """The middleware skip list, exact and prefix entries alike.

    A prefix of "/" would exempt the whole API and silently disable the limiter.
    """

    def test_root_is_exempt(self) -> None:
        """The root path itself is exempt."""
        assert is_rate_limit_exempt("/")

    def test_exact_paths_are_exempt(self) -> None:
        """Single-endpoint skip paths are exempt when matched exactly."""
        for path in ("/health", "/ready", "/openapi.json"):
            assert is_rate_limit_exempt(path), path

    def test_docs_prefixes_are_exempt(self) -> None:
        """The documentation UIs are exempt along with their sub-resources."""
        for path in ("/docs", "/redoc", "/docs/oauth2-redirect"):
            assert is_rate_limit_exempt(path), path

    def test_api_paths_are_not_exempt(self) -> None:
        """API paths are not exempted by the root entry "/"."""
        for path in ("/api/parts", "/api/cars", "/api/auth/login", "/api/admin/users"):
            assert not is_rate_limit_exempt(path), path

    def test_paths_merely_prefixed_by_exact_entries_are_not_exempt(self) -> None:
        """Exact entries do not exempt longer paths that merely start with them."""
        for path in ("/healthcheck", "/ready-set-go", "/openapi.json.bak"):
            assert not is_rate_limit_exempt(path), path


class TestRateLimitMiddlewareEnforcement:
    """Test cases proving the middleware actually limits non-exempt paths."""

    @staticmethod
    def _build_app(config: RateLimitConfig) -> tuple[FastAPI, object]:
        """Build a test app whose middleware uses a limiter with low limits."""
        test_app = FastAPI()
        test_app.middleware("http")(rate_limit_middleware)

        @test_app.get("/api/parts")
        def parts_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            """A non-exempt API route."""
            return {"message": "parts"}

        @test_app.get("/health")
        def health_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            """An exempt health route."""
            return {"status": "healthy"}

        @test_app.get("/docs/oauth2-redirect")
        def docs_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
            """An exempt docs route."""
            return {"message": "docs"}

        return test_app, SophisticatedRateLimiter(config)

    @contextmanager
    def _limiter_enabled(self, limiter: object) -> Iterator[None]:
        """Enable rate limiting and install the given limiter globally.

        The suite disables limiting through both the environment and settings, so both are overridden.
        """
        original_limiter = rate_limiter_module.rate_limiter
        rate_limiter_module.rate_limiter = limiter  # type: ignore[assignment]
        with (
            unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
        ):
            try:
                yield
            finally:
                rate_limiter_module.rate_limiter = original_limiter

    def test_api_path_is_rate_limited(self) -> None:
        """A normal API path is limited once the threshold is exceeded."""
        test_app, limiter = self._build_app(RateLimitConfig(get_requests_per_minute=2, get_requests_per_hour=100))

        with self._limiter_enabled(limiter):
            client = TestClient(test_app)

            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 200

            response = client.get("/api/parts")
            assert response.status_code == 429
            assert response.json()["detail"] == "Too many requests"
            assert response.headers["Retry-After"] == "60"

    def test_rate_limited_response_carries_limit_headers(self) -> None:
        """A successful request advertises the remaining allowance."""
        test_app, limiter = self._build_app(RateLimitConfig(get_requests_per_minute=5, get_requests_per_hour=100))

        with self._limiter_enabled(limiter):
            response = TestClient(test_app).get("/api/parts")

        assert response.status_code == 200
        assert response.headers["X-RateLimit-Limit-Minute"] == "5"
        assert response.headers["X-RateLimit-Remaining-Minute"] == "4"

    def test_exempt_paths_are_never_limited(self) -> None:
        """Exempt paths stay unlimited even well past the threshold."""
        test_app, limiter = self._build_app(RateLimitConfig(get_requests_per_minute=1, get_requests_per_hour=2))

        with self._limiter_enabled(limiter):
            client = TestClient(test_app)

            for _ in range(5):
                assert client.get("/health").status_code == 200
                assert client.get("/docs/oauth2-redirect").status_code == 200

    def test_exempt_paths_do_not_consume_the_api_allowance(self) -> None:
        """Requests to exempt paths do not count against a non-exempt path."""
        test_app, limiter = self._build_app(RateLimitConfig(get_requests_per_minute=2, get_requests_per_hour=100))

        with self._limiter_enabled(limiter):
            client = TestClient(test_app)

            for _ in range(5):
                assert client.get("/health").status_code == 200

            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 429
