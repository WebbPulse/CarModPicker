"""Tests for the rate limiting middleware and its exemption list.

The limiter's own counting behaviour lives in `test_shared_rate_limiter.py`; what
this file pins is which paths reach it and what the middleware does with its answer.
"""

import os
import unittest.mock
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.middleware.rate_limiter as rate_limiter_module
import app.api.middleware.shared_rate_limiter as shared_rate_limiter_module
from app.api.middleware.rate_limiter import (
    is_rate_limit_exempt,
    is_rate_limit_exempt_method,
    rate_limit_middleware,
    rate_limiting_enabled,
)
from app.api.middleware.shared_rate_limiter import (
    ADMIN_CLASS,
    AUTH_CLASS,
    DEFAULT_CLASS,
    GET_CLASS,
    SharedRateLimiter,
)
from app.main import app


class StubLimiter:
    """A limiter that answers from a script rather than from DynamoDB."""

    def __init__(self, allowed: int, *, retry_after: Optional[int] = 42, request_class: str = DEFAULT_CLASS) -> None:
        """Allow `allowed` calls, then report every later one as limited."""
        self.allowed = allowed
        self.retry_after = retry_after
        self.request_class = request_class
        self.identities: list[str] = []

    def check(self, identity: str) -> tuple[bool, Optional[int]]:
        """Count one call and report whether it should be rejected."""
        self.identities.append(identity)
        if len(self.identities) <= self.allowed:
            return False, None
        return True, self.retry_after

    @staticmethod
    def client_key(identity: str) -> str:
        """A stable handle for one caller, safe to log."""
        return f"stub:{identity}"


def _stub_registry(limiter: object) -> dict[str, Any]:
    """Install one stub limiter for every class, so any class routes to it."""
    return {name: limiter for name in (GET_CLASS, AUTH_CLASS, ADMIN_CLASS, DEFAULT_CLASS)}


@contextmanager
def _limiters_enabled(limiters: dict[str, Any]) -> Iterator[None]:
    """Enable rate limiting and install the given per-class limiters globally.

    The suite disables limiting through both the environment and settings, so both
    are overridden.
    """
    original = shared_rate_limiter_module.shared_rate_limiters
    shared_rate_limiter_module.shared_rate_limiters = limiters  # type: ignore[assignment]
    with (
        unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
        unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
        unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", True),
    ):
        try:
            yield
        finally:
            shared_rate_limiter_module.shared_rate_limiters = original


@contextmanager
def _limiter_enabled(limiter: object) -> Iterator[None]:
    """Enable rate limiting with one stub limiter serving every class."""
    with _limiters_enabled(_stub_registry(limiter)):
        yield


class FakeRegistryTable:
    """A minimal in-memory stand-in for the rate limits table.

    Enough of DynamoDB's conditional counter semantics for the middleware to
    count real requests against real caps.
    """

    def __init__(self) -> None:
        """Start with no rows."""
        self.items: dict[str, dict[str, Any]] = {}

    def get_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Return the stored row for a key, or an empty response."""
        item = self.items.get(str(kwargs["Key"]["pk"]))
        return {"Item": dict(item)} if item is not None else {}

    def put_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Store a row under its partition key."""
        item = dict(kwargs["Item"])
        self.items[str(item["pk"])] = item
        return {}

    def update_item(self, **kwargs: Any) -> Mapping[str, Any]:
        """Increment the counter, seeding the row and its expiry on first use."""
        pk = str(kwargs["Key"]["pk"])
        values = kwargs["ExpressionAttributeValues"]
        item = self.items.setdefault(pk, {"pk": pk, "requests": 0, "expires_at": int(values[":ttl"])})
        item["requests"] = int(item["requests"]) + int(values[":one"])
        return {"Attributes": dict(item)}


def _real_limiters(table: FakeRegistryTable) -> dict[str, SharedRateLimiter]:
    """Real limiters at their configured caps, counting in a fake table."""
    return shared_rate_limiter_module.build_limiters(table_client=table)


def _build_app() -> FastAPI:
    """A test app carrying one limited route and two exempt ones."""
    test_app = FastAPI()
    test_app.middleware("http")(rate_limit_middleware)

    @test_app.get("/api/parts")
    def parts_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """A non-exempt API route."""
        return {"message": "parts"}

    @test_app.api_route("/api/parts", methods=["OPTIONS"])
    def parts_preflight() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """A preflight for the non-exempt API route."""
        return {"message": "preflight"}

    @test_app.post("/api/parts")
    def create_part() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """A default-class write."""
        return {"message": "created"}

    @test_app.post("/api/auth/login")
    def login_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """An auth-class write."""
        return {"message": "login"}

    @test_app.post("/api/auth/refresh")
    def refresh_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """A refresh, which is default class rather than auth."""
        return {"message": "refresh"}

    @test_app.post("/api/admin/users")
    def admin_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """An admin-class write."""
        return {"message": "admin"}

    @test_app.get("/health")
    def health_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """An exempt health route."""
        return {"status": "healthy"}

    @test_app.get("/docs/oauth2-redirect")
    def docs_endpoint() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        """An exempt docs route."""
        return {"message": "docs"}

    return test_app


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


class TestRateLimitingEnabled:
    """Both switches, plus the environment override the suite relies on."""

    def test_disabled_by_the_master_setting(self) -> None:
        """`ENABLE_RATE_LIMITING=False` turns the middleware off outright."""
        with unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", False):
            assert not rate_limiting_enabled()

    def test_disabled_by_the_environment_override(self) -> None:
        """The environment disables limiting even when the setting is on."""
        with (
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", True),
            unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "false"}),
        ):
            assert not rate_limiting_enabled()

    def test_disabled_when_the_shared_limiter_is_off(self) -> None:
        """With no shared limiter there is no limiter at all."""
        with (
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", False),
            unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
        ):
            assert not rate_limiting_enabled()

    def test_enabled_when_both_switches_are_on(self) -> None:
        """Both settings on and no environment override means the limiter runs."""
        with (
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", True),
            unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
        ):
            assert rate_limiting_enabled()


class TestRateLimitMiddlewareEnforcement:
    """The middleware limits non-exempt paths and leaves exempt ones alone."""

    def test_api_path_is_rate_limited(self) -> None:
        """A normal API path is limited once the shared limiter says so."""
        limiter = StubLimiter(allowed=2)

        with _limiter_enabled(limiter):
            client = TestClient(_build_app())

            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 200

            response = client.get("/api/parts")

        assert response.status_code == 429
        assert response.json() == {
            "detail": "Too many requests",
            "message": "Rate limit exceeded",
            "retry_after": 42,
        }
        assert response.headers["Retry-After"] == "42"
        assert response.headers["X-RateLimit-Remaining-Minute"] == "0"

    def test_retry_after_falls_back_to_a_minute(self) -> None:
        """An unreadable window yields the default Retry-After rather than none."""
        limiter = StubLimiter(allowed=0, retry_after=None)

        with _limiter_enabled(limiter):
            response = TestClient(_build_app()).get("/api/parts")

        assert response.status_code == 429
        assert response.json()["retry_after"] == 60
        assert response.headers["Retry-After"] == "60"

    def test_exempt_paths_are_never_limited(self) -> None:
        """Exempt paths stay unlimited and never reach the limiter."""
        limiter = StubLimiter(allowed=0)

        with _limiter_enabled(limiter):
            client = TestClient(_build_app())

            for _ in range(5):
                assert client.get("/health").status_code == 200
                assert client.get("/docs/oauth2-redirect").status_code == 200

        assert limiter.identities == []

    def test_exempt_paths_do_not_consume_the_api_allowance(self) -> None:
        """Requests to exempt paths do not count against a non-exempt path."""
        limiter = StubLimiter(allowed=2)

        with _limiter_enabled(limiter):
            client = TestClient(_build_app())

            for _ in range(5):
                assert client.get("/health").status_code == 200

            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 429

    def test_the_limiter_is_not_consulted_when_limiting_is_disabled(self) -> None:
        """With limiting off the middleware passes every request straight through."""
        limiter = StubLimiter(allowed=0)
        original = shared_rate_limiter_module.shared_rate_limiters
        shared_rate_limiter_module.shared_rate_limiters = _stub_registry(limiter)
        try:
            with unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", False):
                client = TestClient(_build_app())
                for _ in range(3):
                    assert client.get("/api/parts").status_code == 200
        finally:
            shared_rate_limiter_module.shared_rate_limiters = original

        assert limiter.identities == []


class TestRateLimitExemptMethods:
    """Preflights are never counted, whatever path they target."""

    def test_options_is_exempt(self) -> None:
        """The CORS preflight method is exempt."""
        assert is_rate_limit_exempt_method("OPTIONS")

    def test_options_is_exempt_case_insensitively(self) -> None:
        """Method matching does not depend on casing."""
        assert is_rate_limit_exempt_method("options")

    def test_other_methods_are_not_exempt(self) -> None:
        """Every method that can carry or change data is counted."""
        for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
            assert not is_rate_limit_exempt_method(method), method

    def test_preflights_never_reach_the_limiter(self) -> None:
        """A burst of preflights spends none of the caller's allowance."""
        limiter = StubLimiter(allowed=0)

        with _limiter_enabled(limiter):
            client = TestClient(_build_app())

            for _ in range(30):
                assert client.options("/api/parts").status_code == 200

        assert limiter.identities == []

    def test_preflights_do_not_consume_the_get_allowance(self) -> None:
        """Preflights before a GET leave the GET allowance untouched."""
        limiter = StubLimiter(allowed=2)

        with _limiter_enabled(limiter):
            client = TestClient(_build_app())

            for _ in range(29):
                assert client.options("/api/parts").status_code == 200

            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 429


class TestRateLimitClassesInTheMiddleware:
    """Each class counts in its own limiter, so one cannot spend another's."""

    @staticmethod
    def _registry() -> dict[str, StubLimiter]:
        """A distinct stub limiter per class, each allowing one request."""
        return {
            name: StubLimiter(allowed=1, request_class=name)
            for name in (GET_CLASS, AUTH_CLASS, ADMIN_CLASS, DEFAULT_CLASS)
        }

    def test_each_class_gets_its_own_counter(self) -> None:
        """Spending the GET allowance leaves the auth and admin ones intact."""
        limiters = self._registry()

        with _limiters_enabled(dict(limiters)):
            client = TestClient(_build_app())

            assert client.get("/api/parts").status_code == 200
            assert client.get("/api/parts").status_code == 429

            assert client.post("/api/auth/login").status_code == 200
            assert client.post("/api/admin/users").status_code == 200
            assert client.post("/api/parts").status_code == 200

        assert len(limiters[GET_CLASS].identities) == 2
        assert len(limiters[AUTH_CLASS].identities) == 1
        assert len(limiters[ADMIN_CLASS].identities) == 1
        assert len(limiters[DEFAULT_CLASS].identities) == 1

    def test_refresh_counts_against_the_default_class(self) -> None:
        """A refresh runs on every page load and must not spend the auth cap."""
        limiters = self._registry()

        with _limiters_enabled(dict(limiters)):
            assert TestClient(_build_app()).post("/api/auth/refresh").status_code == 200

        assert limiters[AUTH_CLASS].identities == []
        assert len(limiters[DEFAULT_CLASS].identities) == 1

    def test_a_get_burst_of_sixty_one_is_not_limited(self) -> None:
        """The GET cap is well above the default, so a page fanout survives."""
        with _limiters_enabled(dict(_real_limiters(FakeRegistryTable()))):
            client = TestClient(_build_app())
            statuses = {client.get("/api/parts").status_code for _ in range(61)}

        assert statuses == {200}


class TestRateLimitMiddlewareOnTheRealApp:
    """The composed application's own exempt routes stay reachable."""

    def test_middleware_skips_health_check(self) -> None:
        """The health probe is never rate limited."""
        response = TestClient(app).get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_middleware_skips_docs(self) -> None:
        """The Swagger UI is never rate limited."""
        assert TestClient(app).get("/docs").status_code == 200

    def test_middleware_skips_redoc(self) -> None:
        """The ReDoc UI is never rate limited."""
        assert TestClient(app).get("/redoc").status_code == 200
