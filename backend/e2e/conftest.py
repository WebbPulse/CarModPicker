"""Product wiring for the `webbpulse.e2e` post-deploy suite.

Supplies what the plugin cannot know: the merged OpenAPI document the deployed gateway
routes against, the header names `@webbpulse/api-client` sends on a cross origin request,
the cleanup that deletes what an e2e run leaves behind, and the browser contract naming
the login form, every frontend route and the product journeys the shared suite drives.

This directory sits outside `tests/` so the unit CI, whose `testpaths` is `tests`, never
collects it. It installs as the `e2e` dependency group alone.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

import pytest
from webbpulse.e2e import (
    Click,
    ExpectText,
    ExpectUrl,
    ExpectVisible,
    Fill,
    Goto,
    Journey,
    LoginForm,
    Record,
    RouteSpec,
)

pytest_plugins = ["webbpulse.e2e"]

STALE_SECONDS = 3600

CORS_REQUEST_HEADERS = (
    "authorization",
    "content-type",
    "x-request-id",
    "x-retry-attempt",
)

SOCIAL_LINKS_RESET = "reset-social-links"

SOCIAL_LINKS_BASELINE_URL = "https://youtube.com/@carmodpicker-e2e-baseline"

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
        "IDENTITY_EPHEMERAL_USERS_ENABLED": "true",
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

    from app.domains.identity import extension as identity_extension

    for module in (router, oauth_routes, passkey_routes, identity_extension):
        module.JSONResponse = JSONResponse  # type: ignore[attr-defined]


def e2e_openapi_document() -> Mapping[str, Any]:
    """The merged document the deployed gateway sees, built from the product app factory.

    CarModPicker deploys one FastAPI application per domain, and
    `tests/entrypoints/test_route_split.py` pins that the union of the nine equals Root A
    exactly. So Root A, which `app.common.composition.app.build_app` returns, is the merged
    document: one operation per route, each under its own domain's `/api` path, with the
    identity package's `/api/auth` routes included.

    Called at collection time, before any fixture runs, because the coverage and
    reachability groups are parametrised per operation.
    """
    os.environ.update(_identity_environment())
    _bind_json_response()

    from app.common.composition.app import build_app

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


def _reset_social_links(client: Any) -> str:
    """Put the e2e user's YouTube URL back to its baseline, returning a problem or "".

    The social links journey writes a per run marker into the user's own record rather
    than creating a resource, so the sweep restores the field instead of deleting a row.

    It overwrites rather than clears on purpose. `PUT /api/users/{id}` drops every None
    from the update before applying it, so sending null leaves the old value in place and
    still answers 200. A constant baseline URL is therefore the only way back to a known
    state, and it keeps the journey re-runnable because each run overwrites the last.
    """
    try:
        me = client.get("/api/users/me")
    except Exception as error:
        return f"GET /api/users/me raised {type(error).__name__}"
    if me.status_code != 200:
        return f"GET /api/users/me answered {me.status_code}, so the social links were not reset"
    try:
        response = client.put(f"/api/users/{me.json()['id']}", json={"youtube_url": SOCIAL_LINKS_BASELINE_URL})
    except Exception as error:
        return f"resetting the social links raised {type(error).__name__}"
    return "" if response.status_code == 200 else f"resetting the social links answered {response.status_code}"


def _sweep_one(client: Any, resource: Any) -> str:
    """Undo one recorded resource, by marker or by delete path."""
    if resource == SOCIAL_LINKS_RESET:
        return _reset_social_links(client)
    return _delete_quietly(client, str(resource))


def pytest_e2e_cleanup(env: Any, phase: str, created: Sequence[Any]) -> Any:
    """Undo the e2e user's `e2e-` resources: stale ones at the start, this run's at the end.

    `created` carries the delete paths the product flows appended to `created_resources`,
    plus the `SOCIAL_LINKS_RESET` marker the browser journey records, which is a field to
    restore rather than a row to delete. Returns a description of what could not be undone,
    which the plugin surfaces as a warning rather than a failure.
    """
    client = _cleanup_client(env)
    if client is None:
        return "the e2e user could not sign in, so nothing was swept"
    try:
        if phase == "start":
            leftovers = _sweep_stale(client, "e2e-")
            leftovers.extend(problem for problem in (_reset_social_links(client),) if problem)
        else:
            leftovers = [problem for item in created if (problem := _sweep_one(client, item))]
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


PUBLIC_ROUTES = (
    ("/", "public"),
    ("/about", "public"),
    ("/privacy-policy", "public"),
    ("/terms-of-service", "public"),
    ("/contact-us", "public"),
    ("/support", "public"),
    ("/pricing", "public"),
    ("/bug-report", "public"),
    ("/search", "public"),
    ("/build-lists", "public"),
    ("/verify-email/confirm", "public"),
    ("/extension-auth", "public"),
    ("/nonexistent-route-for-404-test", "public"),
)

GUEST_ONLY_ROUTES = (
    ("/login", "guest-only"),
    ("/register", "guest-only"),
    ("/forgot-password", "guest-only"),
)

PROTECTED_ROUTES = (
    ("/profile", "protected"),
    ("/builder", "protected"),
    ("/my-parts", "protected"),
)


def pytest_e2e_login_form(env: Any) -> LoginForm:
    """Where CarModPicker's login form lives and which elements prove the state changed.

    Every locator but one is the plugin's own default, because `Login.tsx` and `Header.tsx`
    carry the conventional `data-testid` attributes. `signed_in_marker` is the header's
    account link, which renders on every authenticated page rather than only on the one
    the sign-in landed on. `signed_out_marker` is the header's login link rather than the
    login submit button, because signing out lands on `/`, where no login form renders.

    `protected_redirect` is left empty so it defaults to `/login`, which is where
    `ProtectedRoute` and `EmailVerifiedRoute` both send an anonymous visitor, and
    `guest_redirect` stays `/`, which is where `GuestRoute` sends a signed-in one.
    """
    return LoginForm(path="/login", signed_out_marker="[data-testid=signed-out]")


def pytest_e2e_routes(env: Any) -> list[RouteSpec]:
    """Every frontend route the app serves, and who is allowed to see it.

    Mirrors the `ALL_ROUTES` table in `frontend/src/test/route-coverage-list.ts`, which is
    the enumeration the frontend's own drift guard holds against `App.tsx`, minus three
    kinds of entry the deployed browser suite cannot assert on:

    - the admin routes, which `App.tsx` wraps in no guard at all and whose pages bounce a
      non-admin to `/` from inside an effect. The durable e2e user is deliberately not an
      admin, so declaring them `protected` would assert a redirect the router never makes
      and declaring them `public` would assert a page the user may not see.
    - the parameterised routes, whose ids the coverage list fills with all-zero UUIDs that
      resolve to nothing on a real stage, so the page renders its own not-found state.
    - `/_kitchen-sink`, which is mounted only under `import.meta.env.DEV` and does not
      exist in a deployed bundle.

    `/checkout` and `/verify-email` are left out for the same reason as the admin pages:
    the first redirects to `/` whenever the premium system is disabled, and the second is
    behind `VerifyEmailRoute`, which bounces the e2e user because their address is already
    verified.

    No route overrides the root locator. The app mounts on `#root`, the first of the
    plugin's own candidates, and the render check asks only whether that mount point has
    children, which is what separates a painted page from the shipped blank one a 200
    cannot see. Naming a heading instead would assert content the check is not for and
    would fail on the auth pages, which render their title as an `h2` through `AuthCard`.
    """
    declared = PUBLIC_ROUTES + GUEST_ONLY_ROUTES + PROTECTED_ROUTES
    return [RouteSpec(path=path, access=access) for path, access in declared]


def pytest_e2e_journeys(env: Any) -> list[Journey]:
    """Short flows through the real CarModPicker UI, one read only and one mutating.

    The catalog journey is the read path a signed-out visitor takes: the header's own
    navigation to the build lists catalog, which has to fetch and paint a list from the
    deployed API rather than only serve the shell.

    The social links journey is the write path, and it writes the one thing the durable
    e2e user owns outright: a URL on their own profile. Creating a build list through the
    UI would need the three cascading make, model and generation selects, whose options
    come from whatever the stage's catalog happens to hold, so it would fail on the data
    rather than on the app. The marker carries `{run_id}`, so a value left behind by a run
    that died mid-way is recognisable, and the `Record` step hands the cleanup hook the
    reset that puts the field back.
    """
    return [
        Journey(
            name="browse the build lists catalog",
            signed_in=False,
            steps=[
                Goto("/"),
                Click("header a[href='/build-lists']"),
                ExpectUrl("/build-lists"),
                ExpectText("main h1", "Build Lists Catalog"),
                ExpectVisible("main h1"),
            ],
        ),
        Journey(
            name="update the profile social links",
            signed_in=True,
            mutates=True,
            steps=[
                Goto("/profile"),
                ExpectVisible("#youtube_url"),
                Fill("#youtube_url", "https://youtube.com/@e2e-{run_id}"),
                Click("form:has(#youtube_url) button[type=submit]"),
                ExpectText("main", "Social links updated successfully!"),
                Record(SOCIAL_LINKS_RESET),
            ],
        ),
    ]
