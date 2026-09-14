"""The identity router's OpenAPI responses describe the statuses the routes really answer.

The `webbpulse.identity` package declares them from its own route tables, so the document
CarModPicker publishes carries the 303, 400 and 401 the routes answer rather than the
FastAPI default alone. The post-deploy suite holds each operation to its own `responses`
table, which is how `POST /api/auth/register` and `GET /api/auth/oauth/callback` failed on
the first full staging run.
"""

from __future__ import annotations

import json
from typing import Any, Iterator

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from webbpulse.testing import FakeKms

from tests.domains.identity.test_identity_row5 import AUDIENCE, DATA_KEY_ARN, ISSUER, KEY_ARN
from tests.domains.identity.test_identity_row5 import private_key as _private_key
from tests.entrypoints.test_route_split import _effective_routes

private_key = _private_key


@pytest.fixture
def every_route_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `IDENTITY_*` environment that mounts every route group the package has.

    Mirrors `e2e/conftest.py`, which builds the document the post-deploy suite reads:
    passkeys on and both OAuth client ids present, so the passkey and OAuth routes mount
    and the table below is checked against the full surface rather than a subset.
    """
    from app.core.config import settings as app_settings

    for name, value in {
        "IDENTITY_ENVIRONMENT": "staging",
        "IDENTITY_ISSUER": ISSUER,
        "IDENTITY_AUDIENCE": AUDIENCE,
        "IDENTITY_SIGNING_KEY_ARNS": json.dumps([KEY_ARN]),
        "IDENTITY_DATA_KEY_ARN": DATA_KEY_ARN,
        "IDENTITY_COOKIE_DOMAIN": "staging.carmodpicker.com",
        "IDENTITY_RP_ID": "staging.carmodpicker.com",
        "IDENTITY_RP_NAME": "CarModPicker",
        "IDENTITY_PRODUCT_NAME": "CarModPicker",
        "IDENTITY_SUPPORT_EMAIL": "support@carmodpicker.com",
        "IDENTITY_FRONTEND_BASE_URL": "https://staging.carmodpicker.com",
        "IDENTITY_EMAIL_FROM": "no-reply@staging.carmodpicker.com",
        "IDENTITY_REGISTRATION_ENABLED": "true",
        "IDENTITY_PASSKEYS_ENABLED": "true",
        "IDENTITY_GOOGLE_CLIENT_ID": "declared-responses-test-only",
        "IDENTITY_GITHUB_CLIENT_ID": "declared-responses-test-only",
        "IDENTITY_OAUTH_REDIRECT_URIS": json.dumps([f"{ISSUER}/oauth/callback"]),
    }.items():
        monkeypatch.setenv(name, value)

    monkeypatch.setattr(app_settings, "IDENTITY_ISSUER", ISSUER)


@pytest.fixture
def every_route_app(
    every_route_env: None,
    private_key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Any]:
    """The identity application with every route group mounted, built without network."""
    import boto3

    def fake_client(service: str, *args: Any, **kwargs: Any) -> Any:
        """The local KMS signer, refusing every service the build should not reach."""
        if service == "kms":
            return FakeKms(private_key)
        if service == "sesv2":
            return object()
        raise AssertionError(f"the identity router asked for an unexpected client: {service}")

    monkeypatch.setattr(boto3, "client", fake_client)

    from app.entrypoints.identity import build_app

    yield build_app()


def _declared(app: Any) -> dict[tuple[str, str], set[int]]:
    """Every (method, path) the application serves, with the statuses it declares.

    Flattened through `_effective_routes` because Starlette 1.x stores one lazy
    `_IncludedRouter` per included router rather than copying the sub-router's routes in,
    so `app.routes` holds no identity route at all. What comes back for an included route
    is a route context rather than an `APIRoute`, so the filter is the presence of a
    `responses` mapping rather than a type.
    """
    return {
        (method, route.path): set(route.responses)
        for route in _effective_routes(app)
        if isinstance(getattr(route, "responses", None), dict)
        for method in getattr(route, "methods", None) or []
    }


def test_register_declares_the_statuses_it_answers(every_route_app: Any) -> None:
    """`POST /api/auth/register` declares the 400 an empty body gets and the 201 a new account gets."""
    statuses = _declared(every_route_app)[("POST", "/api/auth/register")]
    assert {201, 400, 403}.issubset(statuses)


def test_oauth_callback_declares_its_redirect(every_route_app: Any) -> None:
    """`GET /api/auth/oauth/callback` declares the 303 every browser leg answers."""
    assert 303 in _declared(every_route_app)[("GET", "/api/auth/oauth/callback")]


def test_oauth_start_declares_its_redirect(every_route_app: Any) -> None:
    """`GET /api/auth/oauth/{provider}/start` declares the 302 it sends to the provider."""
    assert 302 in _declared(every_route_app)[("GET", "/api/auth/oauth/{provider}/start")]


def test_no_identity_route_declares_only_the_fastapi_default(every_route_app: Any) -> None:
    """No `/api/auth` route is left with 200 and 422 alone.

    That pair is what FastAPI declares on its own, and it is the shape the post-deploy
    suite reads as a route whose real statuses are undeclared.
    """
    bare = sorted(
        f"{method} {path}"
        for (method, path), statuses in _declared(every_route_app).items()
        if path.startswith("/api/auth/") and statuses == {200, 422}
    )
    assert not bare, f"{bare} declare only the FastAPI default, so their real statuses are undeclared"
