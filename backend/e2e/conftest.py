"""Product wiring for the `webbpulse.e2e` post-deploy suite.

Supplies the three things the plugin cannot know: the merged OpenAPI document the deployed
gateway routes against, the header names `@webbpulse/api-client` sends on a cross origin
request, and the cleanup that deletes what an e2e run leaves behind.

This directory sits outside `tests/` so the unit CI, whose `testpaths` is `tests`, never
collects it. It installs as the `e2e` dependency group alone.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest

pytest_plugins = ["webbpulse.e2e"]

STALE_SECONDS = 3600

CORS_REQUEST_HEADERS = (
    "authorization",
    "content-type",
    "x-request-id",
    "x-retry-attempt",
)

SWEEPABLE_COLLECTIONS = (
    ("/api/build-lists", "/api/build-lists/{id}", "name"),
    ("/api/part-manufacturers", "/api/part-manufacturers/{id}", "name"),
)


def _identity_environment() -> dict[str, str]:
    """The `IDENTITY_*` variables that decide which identity routes mount.

    `terraform/lambda_domains.tf` sets these on the deployed identity function, and
    `app/composition/wiring.py` mounts the `webbpulse.identity` router only when
    `IDENTITY_ISSUER` is set, its OAuth routes only when a provider client id is present
    and its passkey routes only when passkeys are enabled. A document built without them
    would omit the 26 `/api/auth` operations the gateway declares route keys for, and the
    coverage group would then pass while saying nothing about any of them.

    The issuer is derived from `E2E_API_BASE_URL` exactly as `terraform/identity.tf`
    renders `local.identity_issuer`, so it describes the stage under test rather than
    whichever environment happened to set `E2E_ISSUER`. No value here is read at run time
    by the deployed code; they only decide which routes the document declares.
    """
    api_base_url = os.environ.get("E2E_API_BASE_URL", "").rstrip("/")
    environment = os.environ.get("E2E_ENVIRONMENT", "staging").strip()
    issuer = os.environ.get("E2E_ISSUER", "").rstrip("/") or f"{api_base_url}/api/auth"
    audience = os.environ.get("E2E_AUDIENCE", "") or f"carmodpicker-{environment}-api"
    return {
        "TESTING": "true",
        "ENABLE_RATE_LIMITING": "false",
        "APP_ENVIRONMENT": environment,
        "SECRET_KEY": os.environ.get("SECRET_KEY", "e2e-openapi-build-only"),
        "IDENTITY_ENVIRONMENT": environment,
        "IDENTITY_ISSUER": issuer,
        "IDENTITY_AUDIENCE": audience,
        "IDENTITY_SIGNING_KEY_ARNS": '["arn:aws:kms:us-west-2:000000000000:key/openapi-build-only"]',
        "IDENTITY_REGISTRATION_ENABLED": "true",
        "IDENTITY_PASSKEYS_ENABLED": "true",
        "IDENTITY_GOOGLE_CLIENT_ID": "openapi-build-only",
        "IDENTITY_GITHUB_CLIENT_ID": "openapi-build-only",
        "IDENTITY_OAUTH_REDIRECT_URIS": f'["{issuer}/oauth/callback"]',
    }


def _bind_json_response() -> None:
    """Put `JSONResponse` in the namespace of every module that annotates a route with it.

    `webbpulse.identity.router`, its OAuth and passkey route modules and this product's
    `identity_extension` all import `JSONResponse` inside the function that declares the
    routes, so at module scope the `-> JSONResponse` annotation is an unresolvable forward
    reference and FastAPI raises `PydanticUserError` the moment it builds a response model
    for those operations. The deployed functions never generate their own document, so
    nothing has needed this before. Binding the name is enough to resolve the reference and
    changes no served behaviour.
    """
    from fastapi.responses import JSONResponse
    from webbpulse.identity import oauth_routes, passkey_routes, router

    from app.composition import identity_extension

    for module in (router, oauth_routes, passkey_routes, identity_extension):
        module.JSONResponse = JSONResponse  # type: ignore[attr-defined]


def e2e_openapi_document() -> Mapping[str, Any]:
    """The merged document the deployed gateway sees, built from the product app factory.

    CarModPicker deploys one FastAPI application per domain, and
    `tests/entrypoints/test_route_split.py` pins that the union of the nine equals Root A
    exactly. So Root A, which `app.composition.app.build_app` returns, is the merged
    document: one operation per route, each under its own domain's `/api` path, with the
    identity package's `/api/auth` routes included.

    Called at collection time, before any fixture runs, because the coverage and
    reachability groups are parametrised per operation.
    """
    os.environ.update(_identity_environment())
    _bind_json_response()

    from app.composition.app import build_app

    return build_app().openapi()


@pytest.fixture(scope="session")
def openapi_document() -> Mapping[str, Any]:
    """The same merged document, for the fixtures that take it."""
    return e2e_openapi_document()


@pytest.fixture(scope="session")
def cors_request_headers() -> tuple[str, ...]:
    """The header names `@webbpulse/api-client` sends on every cross origin request.

    Read off `packages/api-client/src/client.ts`, which sets `content-type`,
    `REQUEST_ID_HEADER`, `x-retry-attempt` on a retry and `authorization` when a token is
    held. A gateway allow list missing any one of them rejects the browser's preflight and
    is invisible to a server side probe, which is how `X-Retry-Attempt` shipped missing.
    """
    return CORS_REQUEST_HEADERS


def _delete_quietly(client: Any, path: str) -> str:
    """Delete one resource, returning a description when it could not be deleted."""
    try:
        response = client.delete(path)
    except Exception as error:
        return f"DELETE {path} raised {type(error).__name__}"
    if response.status_code in (200, 202, 204, 404):
        return ""
    return f"DELETE {path} answered {response.status_code}"


def _sweep_stale(client: Any, prefix: str) -> list[str]:
    """Delete e2e resources older than an hour that a died-mid-way run left behind.

    Listed rather than remembered: the run that created them is gone, so the only handle
    left is the `e2e-` prefix on the name. Anything newer than the cutoff is left alone,
    because a concurrent run owns it.
    """
    import time

    leftovers: list[str] = []
    cutoff = time.time() - STALE_SECONDS
    for collection, template, name_field in SWEEPABLE_COLLECTIONS:
        try:
            response = client.get(collection, params={"limit": 100})
        except Exception as error:
            leftovers.append(f"GET {collection} raised {type(error).__name__}")
            continue
        if response.status_code != 200:
            continue
        try:
            items = response.json()
        except ValueError:
            continue
        if isinstance(items, Mapping):
            items = items.get("items") or items.get("data") or []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get(name_field, ""))
            identifier = str(item.get("id", ""))
            if not name.startswith(prefix) or not identifier:
                continue
            if _created_after(item, cutoff):
                continue
            problem = _delete_quietly(client, template.replace("{id}", identifier))
            if problem:
                leftovers.append(problem)
    return leftovers


def _created_after(item: Mapping[str, Any], cutoff: float) -> bool:
    """Whether a listed resource was created after the stale cutoff.

    An unparseable or absent timestamp counts as recent, so a resource another run may
    still be using is never deleted on a guess.
    """
    from datetime import datetime

    raw = item.get("created_at")
    if not raw:
        return True
    try:
        stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return True
    return stamp.timestamp() > cutoff


def pytest_e2e_cleanup(env: Any, phase: str, created: Sequence[Any]) -> Any:
    """Delete the e2e user's `e2e-` resources: stale ones at the start, this run's at the end.

    `created` carries `(method_path, identifier)` pairs the product flows appended to
    `created_resources`, each already a deletable path. Returns a description of what could
    not be deleted, which the plugin surfaces as a warning rather than a failure.
    """
    client = _cleanup_client(env)
    if client is None:
        return "the e2e user could not sign in, so nothing was swept"
    try:
        if phase == "start":
            leftovers = _sweep_stale(client, "e2e-")
        else:
            leftovers = [problem for path in created if (problem := _delete_quietly(client, str(path)))]
    finally:
        client.close()
    return "; ".join(leftovers)


def _cleanup_client(env: Any) -> Any:
    """An authenticated client for the cleanup passes, or None when the login failed.

    The hook runs outside the fixture graph, at session start before `api` exists and at
    session end after it has closed, so it builds its own client rather than reaching for
    one.
    """
    from webbpulse.e2e import GATE_HEADER
    from webbpulse.e2e.client import DEFAULT_PER_MINUTE, E2EClient
    from webbpulse.e2e.identity import login

    gate: dict[str, str] = {}
    if env.gate_ssm_parameter:
        import boto3

        parameter = (
            boto3.session.Session(region_name=env.aws_region)
            .client("ssm")
            .get_parameter(Name=env.gate_ssm_parameter, WithDecryption=True)
        )
        gate = {GATE_HEADER: str(parameter["Parameter"]["Value"])}

    client = E2EClient(
        base_url=env.api_base_url,
        gate_headers=gate,
        per_minute=DEFAULT_PER_MINUTE,
    )
    try:
        return login(client, env.user_email, env.user_password).client
    except Exception:
        client.close()
        return None


@pytest.fixture(scope="session")
def e2e_user_id(api: Any) -> str:
    """The durable e2e user's own id, for the flows that write against their own account."""
    response = api.get("/api/users/me")
    if response.status_code != 200:
        pytest.fail(
            f"GET /api/users/me answered {response.status_code} for the signed in e2e user, "
            "so no product flow below could attribute what it creates."
        )
    return str(response.json()["id"])


@pytest.fixture
def track(created_resources: list[Any]) -> Iterator[Any]:
    """Register a created resource's delete path, so the end sweep removes it on a failure.

    A flow that fails between its create and its delete would otherwise leave the resource
    behind, and the next run's start sweep would only find it an hour later.
    """

    def _track(path: str) -> str:
        """Append one delete path to this run's created resources."""
        created_resources.append(path)
        return path

    yield _track
