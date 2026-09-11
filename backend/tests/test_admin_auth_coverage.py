"""Every route under /api/admin requires admin authorization.

Parametrized over the admin routes the OpenAPI schema declares at collection time.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from tests.conftest import create_and_login_user, login_user
from tests.route_enumeration import schema_routes

DUAL_AUTH_ROUTES = {
    ("POST", "/api/admin/crawlers/run"),
    ("POST", "/api/admin/crawlers/rescrape-archives"),
}


def _admin_routes() -> list[tuple[str, str]]:
    """Every (method, path) the schema declares under /api/admin."""
    out: list[tuple[str, str]] = []
    for method, path in schema_routes():
        if path.startswith("/api/admin"):
            out.append((method, path))
    return out


ADMIN_ROUTES = _admin_routes()


def _fill_path_params(path: str) -> str:
    """Replace each path parameter with a placeholder UUID."""
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_auth(method: str, path: str, client: TestClient) -> None:
    """An unauthenticated request to an admin route is refused."""
    resp = client.request(method, _fill_path_params(path))
    if (method, path) in DUAL_AUTH_ROUTES:
        assert resp.status_code in (401, 403), f"{method} {path} -> {resp.status_code}"
    else:
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_forbids_regular_user(method: str, path: str, client: TestClient) -> None:
    """A regular user's token is forbidden on every admin route."""
    username = f"cov_user_{method.lower()}_{abs(hash(path)) & 0xFFFF:04x}"
    create_and_login_user(client, username=username)
    token = login_user(client, username)
    resp = client.request(method, _fill_path_params(path), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, f"{method} {path} with regular user -> {resp.status_code} (expected 403)"


def test_admin_route_count_at_or_above_expected() -> None:
    """The admin route count stays at or above the expected floor, guarding against drift."""
    assert len(ADMIN_ROUTES) >= 6, f"Expected >=6 admin routes, got {len(ADMIN_ROUTES)}"
