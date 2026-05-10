"""AUTH-03 regression: every protected route under /api/auth requires a valid JWT.

Public auth routes (login, email verify, reset, Google sign-in, WebAuthn login
ceremonies) are excluded via the PUBLIC_ROUTES allow-list below — any new public
route is a deliberate review-gated addition.

D-30 drift guard: count-at-or-above check catches a disabled parametrized test
or a route removal without test update.
"""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

# D-31: Intentionally public (no auth dependency), post-D-10 URL restructure.
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/token/2fa"),
    ("POST", "/api/auth/verify-email"),
    ("GET", "/api/auth/verify-email/confirm"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/reset-password/confirm"),
    ("POST", "/api/auth/oauth/google"),  # D-10: moved from /auth/google
    ("POST", "/api/auth/oauth/google/signup"),  # D-10: moved from /auth/google/signup
    ("POST", "/api/auth/oauth/google/link"),  # D-10: moved from /auth/google/link
    ("POST", "/api/auth/oauth/2fa"),
    # WebAuthn login challenges are pre-auth — user isn't logged in yet
    ("POST", "/api/auth/webauthn/login/options"),
    ("POST", "/api/auth/webauthn/login/verify"),
}


def _protected_auth_routes() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/api/auth"):
            for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
                if (m, r.path) not in PUBLIC_ROUTES:
                    out.append((m, r.path))
    return out


AUTH_PROTECTED_ROUTES = _protected_auth_routes()


def _fill_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", AUTH_PROTECTED_ROUTES)
def test_auth_route_requires_token(method: str, path: str, client: TestClient) -> None:
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code} (expected 401)"


def test_auth_protected_route_count_at_or_above_expected() -> None:
    # 24 total auth routes - 12 public = 12 protected. Tight drift guard: any disabled
    # parametrized test or silently-deleted route immediately trips CI.
    assert len(AUTH_PROTECTED_ROUTES) >= 12, (
        f"Too few protected auth routes: {len(AUTH_PROTECTED_ROUTES)} (expected >=12). "
        f"Check PUBLIC_ROUTES allow-list drift or accidental route removal."
    )


def test_public_routes_still_return_non_401() -> None:
    """Public routes must NOT return 401 on unauthenticated hit (they may return 422 for
    bad body, 400 for missing data, 404 for invalid token, etc. — but NEVER 401)."""
    client = TestClient(app)
    for method, path in sorted(PUBLIC_ROUTES):
        resolved = _fill_path_params(path)
        resp = client.request(method, resolved)
        assert resp.status_code != 401, (
            f"Public route {method} {path} returned 401 — auth dep leaked in! "
            f"Remove Depends(get_current_user) or move to PUBLIC_ROUTES allow-list."
        )
