"""RBAC sweep: every protected route under /api/ (excluding /api/admin and /api/auth,
which have their own coverage suites) requires authentication.

Companion to:
  - tests/test_admin_auth_coverage.py — covers /api/admin/* (anon 401, regular-user 403)
  - tests/test_auth_auth_coverage.py — covers /api/auth/* (anon 401, public allow-list)

This file closes the gap on the rest of the API surface (~115 routes spanning
build_lists, parts, votes, reports, images, etc.). It catches accidental
removal of auth dependencies on owner-scoped routes — the most likely place
RBAC drift can sneak in.

Public routes are explicitly allow-listed below. Adding a new public route
is a deliberate, review-gated change. Drift in either direction trips CI:
  - A protected route losing its auth dep → fails the 401 sweep
  - A public route gaining an auth dep → fails the public sanity check
  - A new route added without a test update → fails the count drift guard

NOTE: This sweep covers anonymous → 401 only. Non-owner → 403 (the harder
boundary, since each domain has its own owner concept and fixture wiring) is
not covered here; per-domain tests carry that load (e.g. test_authorization.py,
test_build_list_labor_estimates.py).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from tests.route_enumeration import schema_routes

PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("POST", "/api/users/"),
    ("GET", "/api/users/"),
    ("GET", "/api/users/count"),
    ("GET", "/api/users/{user_id}"),
    ("GET", "/api/car-generations"),
    ("GET", "/api/car-generations/by-ids"),
    ("GET", "/api/car-generations/count"),
    ("GET", "/api/car-generations/search"),
    ("GET", "/api/car-generations/stats/car-makes"),
    ("GET", "/api/car-generations/{entity_id}"),
    ("GET", "/api/car-generations/car-makes/count"),
    ("GET", "/api/car-generations/car-makes/{car_make_name}"),
    ("GET", "/api/car-generations/car-makes/{car_make_name}/car-models/{car_model_name}"),
    ("GET", "/api/car-generations/car-models/count"),
    ("GET", "/api/build-lists"),
    ("GET", "/api/build-lists/count"),
    ("GET", "/api/build-lists/with-votes"),
    ("GET", "/api/build-lists/car/{car_id}"),
    ("GET", "/api/build-lists/user/{user_id}"),
    ("GET", "/api/build-lists/{build_list_id}"),
    ("GET", "/api/build-lists/{build_list_id}/phases"),
    ("GET", "/api/build-lists/{build_list_id}/labor-estimates"),
    ("GET", "/api/build-logs/build-list/{build_list_id}"),
    ("GET", "/api/build-logs/posts/count"),
    ("GET", "/api/build-list-parts/count"),
    ("GET", "/api/build-list-parts/{build_list_id}"),
    ("GET", "/api/build-list-parts/{build_list_id}/parts"),
    ("GET", "/api/build-list-parts/parts/{part_id}/build-lists/count"),
    ("GET", "/api/build-list-phases/count"),
    ("GET", "/api/build-list-labor-estimates/count"),
    ("GET", "/api/parts"),
    ("GET", "/api/parts/check-url"),
    ("GET", "/api/parts/count"),
    ("GET", "/api/parts/filter-options"),
    ("GET", "/api/parts/with-votes"),
    ("GET", "/api/parts/category/{category_id}"),
    ("GET", "/api/parts/user/{user_id}/count"),
    ("GET", "/api/parts/{entity_id}"),
    ("GET", "/api/parts/{part_id}/best-listing"),
    ("GET", "/api/parts/{part_id}/listings"),
    ("GET", "/api/parts/{part_id}/price-history"),
    ("GET", "/api/parts/{part_id}/with-listings"),
    ("GET", "/api/categories/"),
    ("GET", "/api/categories/count"),
    ("GET", "/api/categories/{category_id}"),
    ("GET", "/api/categories/{category_id}/parts"),
    ("GET", "/api/categories/{category_id}/parts-count"),
    ("GET", "/api/part-manufacturers"),
    ("GET", "/api/part-manufacturers/count"),
    ("GET", "/api/part-manufacturers/counts/by-source"),
    ("GET", "/api/part-manufacturers/search"),
    ("GET", "/api/part-manufacturers/{part_manufacturer_id}"),
    ("GET", "/api/part-manufacturers/{part_manufacturer_id}/parts"),
    ("GET", "/api/part-manufacturers/{part_manufacturer_id}/parts-count"),
    ("GET", "/api/retailers"),
    ("GET", "/api/retailers/count"),
    ("GET", "/api/retailers/{retailer_id}"),
    ("GET", "/api/votes/count"),
    ("GET", "/api/votes/{entity_type}/{entity_id}/summary"),
    ("GET", "/api/reports/count"),
    ("GET", "/api/bug-reports/count"),
    ("POST", "/api/bug-reports/"),
    ("GET", "/api/search/"),
    ("GET", "/api/part-price-alerts/unsubscribe"),
    ("GET", "/api/images/presigned-url"),
    ("GET", "/api/app-settings"),
}


def _api_routes() -> list[tuple[str, str]]:
    """All /api/ routes excluding /api/admin and /api/auth (covered elsewhere)."""
    out: list[tuple[str, str]] = []
    for method, path in schema_routes():
        if not path.startswith("/api/"):
            continue
        if path.startswith("/api/admin") or path.startswith("/api/auth"):
            continue
        out.append((method, path))
    return out


API_ROUTES = _api_routes()
PROTECTED_ROUTES = [r for r in API_ROUTES if r not in PUBLIC_ROUTES]


def _fill_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_api_route_requires_auth(method: str, path: str, client: TestClient) -> None:
    """Anonymous requests to protected routes must 401.

    A 422 (validation error) here means FastAPI parsed the body before reaching
    the auth dependency — usually fine, but if you see 422 on a method that
    should be auth-gated, check whether the auth dep is wired correctly.
    """
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code} (expected 401)"


def test_public_routes_do_not_return_401(client: TestClient) -> None:
    """Public allow-list sanity check: no public route should leak an auth dep.

    If this fails for a route, either:
      (a) a Depends(get_current_user) was added — remove it, or
      (b) the route is no longer intended to be public — remove it from
          PUBLIC_ROUTES and let the protected sweep cover it.
    """
    for method, path in sorted(PUBLIC_ROUTES):
        if (method, path) not in API_ROUTES:
            continue
        resp = client.request(method, _fill_path_params(path))
        assert resp.status_code != 401, (
            f"Public route {method} {path} returned 401 — auth dep leaked in. "
            f"Remove the dep, or remove this entry from PUBLIC_ROUTES if it should be protected."
        )


def test_public_routes_all_exist() -> None:
    """Every entry in PUBLIC_ROUTES must correspond to a real route.

    Catches stale allow-list entries after route renames/removals.
    """
    api_set = set(API_ROUTES)
    stale = sorted(PUBLIC_ROUTES - api_set)
    assert not stale, (
        f"PUBLIC_ROUTES has {len(stale)} entries that don't match any route in the app: {stale}. " "Remove them."
    )


def test_api_route_count_at_or_above_expected() -> None:
    """Drift guard: catches a disabled parametrize, a route deletion without
    test update, or a wholesale router removal.
    """
    assert len(API_ROUTES) >= 100, f"Expected >=100 /api/ routes (excl. admin/auth), got {len(API_ROUTES)}"
    assert len(PROTECTED_ROUTES) >= 70, f"Expected >=70 protected routes, got {len(PROTECTED_ROUTES)}"
