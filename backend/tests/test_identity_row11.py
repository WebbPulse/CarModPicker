"""Tests for resolving a caller from the authorizer's claims, where sub is the user id.

Covers both authorizer shapes, the unchanged legacy session, and the id lookup.
"""

from __future__ import annotations

import json
from typing import Any, Iterator
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from webbpulse.http import REQUEST_CONTEXT_HEADER

from app.api.dependencies.auth import (
    create_access_token,
    get_current_user,
    get_optional_current_user,
    resolve_identity_user,
)
from app.api.dependencies.identity_claims import (
    GATE_CLAIMS_KEY,
    identity_claims,
    identity_subject,
    reset_token_service,
    verify_bearer_subject,
)
from app.api.dependencies.repositories import get_repositories
from app.db.dynamo.users import User, UserRepository

ISSUER = "https://api.staging.carmodpicker.com/api/auth"
AUDIENCE = "carmodpicker-staging-api"


def access_claims(subject: str, **overrides: Any) -> dict[str, str]:
    """A claim set shaped as an authorizer delivers one, with every value a string."""
    claims = {
        "sub": subject,
        "iss": ISSUER,
        "aud": AUDIENCE,
        "typ": "access",
        "iat": "1788938046",
        "exp": "1788938646",
        "jti": "976037a1ea4847da8a633b3338d61f65",
        "username": "whoever",
        "roles": "[]",
    }
    claims.update({key: str(value) for key, value in overrides.items()})
    return claims


def native_context(subject: str, **overrides: Any) -> str:
    """The request context header the native JWT authorizer produces, as plain JSON."""
    return json.dumps({"authorizer": {"jwt": {"claims": access_claims(subject, **overrides)}}})


def gate_context(subject: str, **overrides: Any) -> str:
    """The request context header the staging access gate's Lambda authorizer produces."""
    claims = access_claims(subject, **overrides)
    return json.dumps(
        {
            "authorizer": {
                "lambda": {
                    GATE_CLAIMS_KEY: json.dumps(claims),
                    "jwt.claims.sub": claims["sub"],
                    "jwt.claims.iss": claims["iss"],
                    "jwt.claims.exp": claims["exp"],
                }
            }
        }
    )


@pytest.fixture(autouse=True)
def _clean_token_service() -> Iterator[None]:
    """Drop the memoised token service around every test, since it caches failures too."""
    reset_token_service()
    yield
    reset_token_service()


@pytest.fixture
def identity_user(db_session: Any, dynamo_tables: Any) -> User:
    """A verified, enabled user, which is what `may_authenticate` admits."""
    suffix = str(id(db_session))
    return UserRepository().create_user(
        User(
            username=f"row11_{suffix}",
            email=f"row11_{suffix}@example.com",
            email_verified=True,
            disabled=False,
        )
    )


def _request(header_value: str | None = None, authorization: str | None = None) -> Request:
    """Build a bare ASGI request carrying the headers this resolver reads."""
    headers: list[tuple[bytes, bytes]] = []
    if header_value is not None:
        headers.append((REQUEST_CONTEXT_HEADER.encode(), header_value.encode()))
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_the_native_authorizer_shape_is_read() -> None:
    """Production's `authorizer.jwt.claims` resolves through the package's reader."""
    subject = str(uuid4())
    assert identity_subject(_request(native_context(subject))) == subject


def test_the_staging_gate_shape_is_read() -> None:
    """The staging gate's claims key resolves, which the package alone does not handle."""
    subject = str(uuid4())
    assert identity_subject(_request(gate_context(subject))) == subject


def test_both_shapes_coerce_to_the_same_claims() -> None:
    """Both authorizer shapes coerce to equal Python values, not merely equal subjects."""
    subject = str(uuid4())
    native = identity_claims(_request(native_context(subject)))
    gate = identity_claims(_request(gate_context(subject)))
    assert native is not None and gate is not None
    assert native["exp"] == gate["exp"] == 1788938646
    assert isinstance(native["exp"], int) and isinstance(gate["exp"], int)
    assert native["sub"] == gate["sub"] == subject


def test_a_request_with_no_authorizer_is_nobody_rather_than_an_error() -> None:
    """A request with no authorizer resolves to nobody rather than raising."""
    assert identity_subject(_request()) == ""
    assert identity_subject(_request(json.dumps({"http": {"sourceIp": "203.0.113.1"}}))) == ""


def test_an_unparseable_gate_payload_is_refused_rather_than_guessed() -> None:
    """A claims payload that does not parse resolves to nobody rather than a guess."""
    broken = json.dumps({"authorizer": {"lambda": {GATE_CLAIMS_KEY: "not json at all"}}})
    assert identity_subject(_request(broken)) == ""


def test_in_process_verification_is_off_without_the_identity_environment() -> None:
    """Without the identity environment in-process verification answers nobody."""
    assert verify_bearer_subject(_request(authorization="Bearer whatever")) == ""


def test_sub_resolves_to_the_user_row_by_id(identity_user: User) -> None:
    """The subject is the user id and resolves by a single lookup, with no link table."""
    repos = get_repositories()
    resolved = resolve_identity_user(_request(native_context(str(identity_user.id))), repos)
    assert resolved is not None
    assert resolved.id == identity_user.id
    assert resolved.username == identity_user.username


def test_a_username_in_sub_does_not_resolve(identity_user: User) -> None:
    """A username in the subject resolves to nobody, keeping the two flows apart."""
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context(identity_user.username)), repos) is None


def test_a_sub_that_is_not_a_uuid_resolves_to_nobody() -> None:
    """A token this product did not mint is "no such user" rather than a 500."""
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context("not-a-uuid")), repos) is None


def test_a_disabled_account_is_refused_on_the_identity_path(identity_user: User) -> None:
    """A disabled account is refused even with a token minted before it was disabled."""
    UserRepository().update_user(identity_user.id, disabled=True)
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context(str(identity_user.id))), repos) is None


def test_an_unverified_address_is_refused_on_the_identity_path(identity_user: User) -> None:
    """An unverified account is refused, matching what `get_current_user` already does."""
    UserRepository().update_user(identity_user.id, email_verified=False)
    repos = get_repositories()
    assert resolve_identity_user(_request(native_context(str(identity_user.id))), repos) is None


def _dual_mode_app() -> FastAPI:
    """A minimal application carrying the two resolvers this change touches."""
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: User = Depends(get_current_user)) -> dict[str, str]:
        """Return the authenticated user's id and username."""
        return {"id": str(user.id), "username": user.username}

    @app.get("/maybe")
    async def maybe(user: User | None = Depends(get_optional_current_user)) -> dict[str, str]:
        """Return the optional user's id, or an empty id when nobody is signed in."""
        return {"id": str(user.id)} if user is not None else {"id": ""}

    return app


def test_the_legacy_session_still_resolves(identity_user: User, dynamo_tables: Any) -> None:
    """The legacy HS256 session still resolves unchanged."""
    client = TestClient(_dual_mode_app())
    token = create_access_token({"sub": identity_user.username})
    response = client.get("/whoami", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_an_identity_token_resolves_through_the_gate_context(identity_user: User, dynamo_tables: Any) -> None:
    """An identity caller resolves from the gate context with no authorization header."""
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/whoami",
        headers={REQUEST_CONTEXT_HEADER: gate_context(str(identity_user.id))},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_an_identity_token_resolves_through_the_native_context(identity_user: User, dynamo_tables: Any) -> None:
    """Production's shape resolves end to end too, so the promotion changes nothing here."""
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/whoami",
        headers={REQUEST_CONTEXT_HEADER: native_context(str(identity_user.id))},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_an_unknown_subject_is_a_401_and_not_a_500(dynamo_tables: Any) -> None:
    """A well formed subject naming no user is a quiet 401."""
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/whoami",
        headers={REQUEST_CONTEXT_HEADER: native_context(str(uuid4()))},
    )
    assert response.status_code == 401


def test_the_optional_resolver_is_anonymous_without_a_token(dynamo_tables: Any) -> None:
    """A public read stays public. This is what would break if the optional
    resolver had been made to raise on a missing claim section."""
    client = TestClient(_dual_mode_app())
    response = client.get("/maybe")
    assert response.status_code == 200
    assert response.json()["id"] == ""


def test_the_optional_resolver_reads_an_identity_token(identity_user: User, dynamo_tables: Any) -> None:
    """A public read that carries an identity token sees the user behind it."""
    client = TestClient(_dual_mode_app())
    response = client.get(
        "/maybe",
        headers={REQUEST_CONTEXT_HEADER: gate_context(str(identity_user.id))},
    )
    assert response.status_code == 200
    assert response.json()["id"] == str(identity_user.id)


def test_a_bare_request_still_gets_the_unchanged_401_body(dynamo_tables: Any) -> None:
    """A request carrying no credential gets the same 401 body it always did."""
    client = TestClient(_dual_mode_app())
    response = client.get("/whoami")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
