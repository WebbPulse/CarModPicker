"""Tests for the rate limiting middleware and its exemption list.

The limiter's own counting behaviour lives in `test_rate_limit_classes.py`; what
this file pins is which paths reach it and what the middleware does with its answer.
"""

import os
import unittest.mock
from contextlib import contextmanager
from typing import Any, Iterator, Mapping, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from webbpulse.ratelimit import RateLimitDecision

import app.api.middleware.rate_limiter as rate_limiter_module
from app.api.middleware.rate_limiter import (
    ADMIN_CLASS,
    AUTH_CLASS,
    DEFAULT_CLASS,
    GET_CLASS,
    WINDOW_SECONDS,
    build_rate_limit_middleware,
    is_rate_limit_exempt,
    is_rate_limit_exempt_method,
    limit_classes,
    rate_limiting_enabled,
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

    def check(self, identity: str, *, limit: int, window_seconds: int, now: Any = None) -> RateLimitDecision:
        """Count one call and report whether it should be rejected."""
        self.identities.append(identity)
        allowed = len(self.identities) <= self.allowed
        return RateLimitDecision(
            allowed=allowed,
            limit=limit,
            remaining=max(limit - len(self.identities), 0),
            reset_after=0 if allowed or self.retry_after is None else self.retry_after,
            window_seconds=window_seconds,
            limit_name=self.request_class,
        )


_CLASS_NAMES = (GET_CLASS, AUTH_CLASS, ADMIN_CLASS, DEFAULT_CLASS)


def _stub_registry(limiter: object) -> dict[str, Any]:
    """Install one stub limiter for every class, so any class routes to it."""
    return {name: limiter for name in _CLASS_NAMES}


@contextmanager
def _limiters_enabled(limiters: dict[str, Any]) -> Iterator[None]:
    """Enable rate limiting and install the given per-class limiters.

    The suite disables limiting through both the environment and settings, so both
    are overridden. `rate_limiting_enabled` is the shared package's own gate, false
    for every name in `RATE_LIMIT_FREE_ENVIRONMENTS`, which includes the `local`
    the suite runs as; it is forced on here so these tests pin the middleware rather
    than that convention, which `TestRateLimitingEnabled` covers directly.
    """
    with (
        unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
        unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
        unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", True),
        unittest.mock.patch.object(type(rate_limiter_module.settings), "rate_limiting_enabled", True),
    ):
        _INSTALLED.clear()
        _INSTALLED.update(limiters)
        try:
            yield
        finally:
            _INSTALLED.clear()


_INSTALLED: dict[str, Any] = {}


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


def _real_limiters(table: FakeRegistryTable) -> dict[str, Any]:
    """Real limiters at their configured caps, counting in a fake table."""
    from webbpulse.ratelimit import RateLimiter

    limiters = {}
    for name in _CLASS_NAMES:
        limiter = RateLimiter(namespace=name, anchor="first_request", count_attribute="requests")
        limiter._table = table
        limiters[name] = limiter
    return limiters


def _build_app() -> FastAPI:
    """A test app carrying one limited route and two exempt ones."""
    test_app = FastAPI()
    test_app.middleware("http")(build_rate_limit_middleware(limiters=dict(_INSTALLED)))

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


@contextmanager
def _environment(name: str) -> Iterator[None]:
    """Run the block with `settings.environment` mirrored from `APP_ENVIRONMENT`.

    The base class derives `rate_limiting_enabled` from `environment`, and CMP fills
    that field in `_mirror_base_fields`, so the mapping is exercised rather than
    stubbed. Teardown re-mirrors from the restored `APP_ENVIRONMENT` so no derived
    field is left holding the value this block installed.
    """
    settings = rate_limiter_module.settings
    previous_app = settings.APP_ENVIRONMENT
    object.__setattr__(settings, "APP_ENVIRONMENT", name)
    settings._mirror_base_fields()
    try:
        yield
    finally:
        object.__setattr__(settings, "APP_ENVIRONMENT", previous_app)
        settings._mirror_base_fields()


@contextmanager
def _switches_on() -> Iterator[None]:
    """Turn every explicit rate limiting switch on, settings and environment alike."""
    with (
        unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
        unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", True),
        unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
    ):
        yield


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
        """Both settings on and no environment override means the limiter runs.

        Asserted from production, because the shared `rate_limiting_enabled` gate is
        false for every name in `RATE_LIMIT_FREE_ENVIRONMENTS`, the suite's own `local`
        among them, and this pins the two explicit switches rather than that list.
        """
        with (
            _environment("production"),
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", True),
            unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_SHARED_RATE_LIMITING", True),
            unittest.mock.patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "true"}),
        ):
            assert rate_limiting_enabled()

    def test_disabled_in_staging_despite_every_switch_being_on(self) -> None:
        """Staging is never rate limited, whatever the explicit switches say."""
        with _environment("staging"), _switches_on():
            assert not rate_limiting_enabled()

    def test_enabled_in_production(self) -> None:
        """Production keeps its limits under the same shared convention."""
        with _environment("production"), _switches_on():
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
        assert response.json() == {"detail": "Too many requests. Try again in 42 seconds."}
        assert response.headers["Retry-After"] == "42"

    def test_the_429_carries_the_rate_limit_headers(self) -> None:
        """The package envelope emits both header styles, naming the class that rejected."""
        limiter = StubLimiter(allowed=0, request_class=GET_CLASS)

        with _limiter_enabled(limiter):
            response = TestClient(_build_app()).get("/api/parts")

        assert response.status_code == 429
        cap = next(cls.limit for cls in limit_classes() if cls.name == GET_CLASS)
        remaining = cap - 1
        assert response.headers["RateLimit"] == f'"{GET_CLASS}";r={remaining};t=42'
        assert response.headers["RateLimit-Policy"] == f'"{GET_CLASS}";q={cap};w={WINDOW_SECONDS}'
        assert response.headers["X-RateLimit-Limit"] == str(cap)
        assert response.headers["X-RateLimit-Remaining"] == str(remaining)
        assert response.headers["X-RateLimit-Reset"] == "42"

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
        _INSTALLED.clear()
        _INSTALLED.update(_stub_registry(limiter))
        try:
            with unittest.mock.patch.object(rate_limiter_module.settings, "ENABLE_RATE_LIMITING", False):
                client = TestClient(_build_app())
                for _ in range(3):
                    assert client.get("/api/parts").status_code == 200
        finally:
            _INSTALLED.clear()

        assert limiter.identities == []

    def test_staging_passes_every_request_through_untouched(self) -> None:
        """In staging the middleware never consults the limiter, switches on or not."""
        limiter = StubLimiter(allowed=0)
        _INSTALLED.clear()
        _INSTALLED.update(_stub_registry(limiter))
        try:
            with _environment("staging"), _switches_on():
                client = TestClient(_build_app())
                for _ in range(5):
                    assert client.get("/api/parts").status_code == 200
        finally:
            _INSTALLED.clear()

        assert limiter.identities == []

    def test_production_still_limits(self) -> None:
        """The same request in production is counted and rejected once the cap is spent."""
        limiter = StubLimiter(allowed=1)
        _INSTALLED.clear()
        _INSTALLED.update(_stub_registry(limiter))
        try:
            with _environment("production"), _switches_on():
                client = TestClient(_build_app())
                assert client.get("/api/parts").status_code == 200
                assert client.get("/api/parts").status_code == 429
        finally:
            _INSTALLED.clear()

        assert len(limiter.identities) == 2


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
