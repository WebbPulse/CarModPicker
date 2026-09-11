"""Every protected route under /api/auth requires a valid token.

Public auth routes are listed explicitly, so a new one is a deliberate addition.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.route_enumeration import schema_routes

PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/token/2fa"),
    ("POST", "/api/auth/verify-email"),
    ("GET", "/api/auth/verify-email/confirm"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/reset-password/confirm"),
    ("POST", "/api/auth/oauth/google"),
    ("POST", "/api/auth/oauth/google/signup"),
    ("POST", "/api/auth/oauth/google/link"),
    ("POST", "/api/auth/oauth/2fa"),
    ("POST", "/api/auth/webauthn/login/options"),
    ("POST", "/api/auth/webauthn/login/verify"),
}


def _protected_auth_routes() -> list[tuple[str, str]]:
    """Every (method, path) under /api/auth that is not on the public allow list."""
    out: list[tuple[str, str]] = []
    for method, path in schema_routes():
        if path.startswith("/api/auth") and (method, path) not in PUBLIC_ROUTES:
            out.append((method, path))
    return out


AUTH_PROTECTED_ROUTES = _protected_auth_routes()


def _fill_path_params(path: str) -> str:
    """Replace each path parameter with a placeholder UUID."""
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", AUTH_PROTECTED_ROUTES)
def test_auth_route_requires_token(method: str, path: str, client: TestClient) -> None:
    """An unauthenticated request to a protected auth route returns 401."""
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code} (expected 401)"


def test_auth_protected_route_count_at_or_above_expected() -> None:
    """The protected route count stays at or above the expected floor, guarding against drift."""
    assert len(AUTH_PROTECTED_ROUTES) >= 12, (
        f"Too few protected auth routes: {len(AUTH_PROTECTED_ROUTES)} (expected >=12). "
        f"Check PUBLIC_ROUTES allow-list drift or accidental route removal."
    )


def test_public_routes_still_return_non_401() -> None:
    """A public route never answers 401 unauthenticated, whatever else it rejects."""
    client = TestClient(app)
    for method, path in sorted(PUBLIC_ROUTES):
        resolved = _fill_path_params(path)
        resp = client.request(method, resolved)
        assert resp.status_code != 401, (
            f"Public route {method} {path} returned 401 — auth dep leaked in! "
            f"Remove Depends(get_current_user) or move to PUBLIC_ROUTES allow-list."
        )
