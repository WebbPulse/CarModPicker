"""Sweeps every protected route under /api/ outside /api/admin and /api/auth and asserts anonymous requests get a 401.

Public routes are allow-listed, so drift in either direction fails: a lost auth
dependency, a leaked one, or a new route nobody classified.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from tests.route_enumeration import schema_routes

PUBLIC_ROUTES: set[tuple[str, str]] = {
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
    """All /api/ routes excluding /api/admin (swept elsewhere) and /api/auth (the package's)."""
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
    """Substitute a placeholder UUID for every path parameter in a route template."""
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
def test_api_route_requires_auth(method: str, path: str, client: TestClient) -> None:
    """An anonymous request to a protected route is a 401."""
    resp = client.request(method, _fill_path_params(path))
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code} (expected 401)"


def test_public_routes_do_not_return_401(client: TestClient) -> None:
    """No allow-listed public route has picked up an auth dependency."""
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
        f"PUBLIC_ROUTES has {len(stale)} entries that don't match any route in the app: {stale}. Remove them."
    )


def test_api_route_count_at_or_above_expected() -> None:
    """Drift guard: catches a disabled parametrize, a route deletion without
    test update, or a wholesale router removal.
    """
    assert len(API_ROUTES) >= 100, f"Expected >=100 /api/ routes (excl. admin/auth), got {len(API_ROUTES)}"
    assert len(PROTECTED_ROUTES) >= 70, f"Expected >=70 protected routes, got {len(PROTECTED_ROUTES)}"
