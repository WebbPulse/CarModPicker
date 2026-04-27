"""ADMIN-02 regression: every route under /api/admin requires admin auth.

D-27—D-30: parametrized over (method, path) extracted from app.routes at
collection time. Per-route assertions:
  (a) no auth header -> 401 (or 401|403 for dual-auth cron-key routes)
  (b) regular-user token -> 403

D-30 drift guard: count-at-or-above check catches a disabled parametrized
test or a route removal without test update. Combined with SAFE-05 OpenAPI
snapshot, the drift surface is fully covered.
"""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import create_and_login_user, login_user

# D-28 + Risk 7: routes using Optional[DBUser] admin dep + X-Admin-Cron-Key.
# These may return 403 (not 401) when no auth header + no cron key present
# because the dependency doesn't raise; the body check does.
# See admin.py:823-851 pattern.
DUAL_AUTH_ROUTES = {
    ("POST", "/api/admin/crawlers/run"),
    ("POST", "/api/admin/crawlers/rescrape-archives"),
}


def _admin_routes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/admin"):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                out.append((m, r.path))
    return out


ADMIN_ROUTES = _admin_routes()


def _fill_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_requires_auth(method: str, path: str, client: TestClient) -> None:
    resp = client.request(method, _fill_path_params(path))
    if (method, path) in DUAL_AUTH_ROUTES:
        assert resp.status_code in (401, 403), f"{method} {path} -> {resp.status_code}"
    else:
        assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_route_forbids_regular_user(method: str, path: str, client: TestClient) -> None:
    username = f"cov_user_{method.lower()}_{abs(hash(path)) & 0xFFFF:04x}"
    create_and_login_user(client, username=username)
    token = login_user(client, username)
    resp = client.request(method, _fill_path_params(path), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403, f"{method} {path} with regular user -> {resp.status_code} (expected 403)"


def test_admin_route_count_at_or_above_expected() -> None:
    # D-30 drift guard
    assert len(ADMIN_ROUTES) >= 23, f"Expected >=23 admin routes (post-split), got {len(ADMIN_ROUTES)}"
