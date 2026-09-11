"""The route contract, and the agreement between the two composition roots.

Pins the monolith's routes and asserts the per-domain applications partition them.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Iterator, List, Optional, Set, Tuple

import pytest

from app.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "route_contract.json"

ROOT_ROUTES: Set[Tuple[str, str]] = {
    ("GET", "/"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/sitemap.xml"),
    ("GET", "/sitemap-{name}.xml"),
}

DOCS_ROUTES: Set[Tuple[str, str]] = {
    ("GET", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("GET", "/redoc"),
    ("GET", "/api/openapi.json"),
}

DOMAIN_ROUTE_COUNT = 171
ROOT_ROUTE_COUNT = 5
DEPLOYED_ROUTE_COUNT = DOMAIN_ROUTE_COUNT + ROOT_ROUTE_COUNT
TOTAL_WITH_DOCS = DEPLOYED_ROUTE_COUNT + len(DOCS_ROUTES)

EXPECTED_DOMAIN_ROUTES = {
    "identity": 24,
    "users": 14,
    "catalog": 43,
    "vehicles": 11,
    "build-lists": 34,
    "build-logs": 5,
    "moderation": 20,
    "media": 8,
    "admin": 12,
}


def _effective_routes(app: object) -> "Iterator[Any]":
    """Every route an application serves, flattened.

    Handles both the flat and the lazily included shapes app.routes can take.
    """
    for route in getattr(app, "routes", []):
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from contexts()
        else:
            yield route


def _pairs(app: object) -> Set[Tuple[str, str]]:
    """Every (method, path) an application serves, HEAD excluded.

    Starlette pairs HEAD with every GET, which would double the GET counts.
    """
    out: Set[Tuple[str, str]] = set()
    for route in _effective_routes(app):
        path = getattr(route, "path", None)
        if path is None:
            continue
        for method in getattr(route, "methods", None) or []:
            if method != "HEAD":
                out.add((method, path))
    return out


def _root_a() -> Set[Tuple[str, str]]:
    """The (method, path) pairs the monolith serves."""
    from app.main import app

    return _pairs(app)


def _root_b(domain: str) -> Set[Tuple[str, str]]:
    """The (method, path) pairs one domain entrypoint serves."""
    module = importlib.import_module(f"app.entrypoints.{ENTRYPOINT_MODULES[domain]}")
    return _pairs(module.build_app())


def test_root_a_matches_the_committed_route_contract() -> None:
    """The monolith's routing table matches the committed fixture."""
    expected: List[Tuple[str, str]] = [tuple(pair) for pair in json.loads(CONTRACT_PATH.read_text())]  # type: ignore[misc]
    actual = sorted(_root_a())
    assert actual == sorted(expected), (
        "Route drift detected. Review the diff on backend/tests/fixtures/route_contract.json; "
        "if it is intentional, regenerate the fixture and commit it with the change."
    )


def test_root_a_route_counts_reconcile() -> None:
    """The monolith's route counts reconcile with the domain, root and doc totals."""
    pairs = _root_a()
    assert len(pairs) == TOTAL_WITH_DOCS
    assert ROOT_ROUTES <= pairs
    assert DOCS_ROUTES <= pairs
    assert len(pairs - ROOT_ROUTES - DOCS_ROUTES) == DOMAIN_ROUTE_COUNT


def test_root_a_openapi_paths_match_the_contract() -> None:
    """The published document describes the same surface the routing table serves.

    The routes excluded from the schema are named, so a new one is deliberate.
    """
    from app.main import app

    documented = {
        (method.upper(), path)
        for path, operations in app.openapi().get("paths", {}).items()
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "TRACE"}
    }
    in_table = _root_a()
    undocumented = {
        ("GET", "/sitemap.xml"),
        ("GET", "/sitemap-{name}.xml"),
    } | DOCS_ROUTES
    assert documented == in_table - undocumented
    assert len(documented) == DOMAIN_ROUTE_COUNT + ROOT_ROUTE_COUNT - 2


def test_no_route_is_registered_twice() -> None:
    """No (method, path) is registered more than once."""
    from app.main import app

    seen: List[Tuple[str, str]] = []
    for route in _effective_routes(app):
        path = getattr(route, "path", None)
        if path is None:
            continue
        for method in getattr(route, "methods", None) or []:
            if method != "HEAD":
                seen.append((method, path))
    duplicates = sorted({pair for pair in seen if seen.count(pair) > 1})
    assert duplicates == [], f"routes registered more than once: {duplicates}"


def test_the_union_of_root_b_equals_root_a() -> None:
    """The domain entrypoints together serve exactly the monolith's routes."""
    union: Set[Tuple[str, str]] = set()
    for domain in DOMAIN_NAMES:
        union |= _root_b(domain)
    root_a = _root_a()
    assert sorted(union - root_a) == [], "a domain serves a route the composed application does not"
    assert sorted(root_a - union) == [], "the composed application serves a route no domain owns"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_serves_the_routes_section_one_one_gives_it(domain: str) -> None:
    """Each domain serves its own expected route count plus the shared root routes."""
    pairs = _root_b(domain)
    own = pairs - ROOT_ROUTES - DOCS_ROUTES
    assert len(own) == EXPECTED_DOMAIN_ROUTES[domain]
    assert ROOT_ROUTES <= pairs
    assert len(pairs) == EXPECTED_DOMAIN_ROUTES[domain] + ROOT_ROUTE_COUNT + len(DOCS_ROUTES)


def test_the_domains_partition_the_api_surface() -> None:
    """The domains partition the API surface with no overlap."""
    owners: dict[Tuple[str, str], List[str]] = {}
    for domain in DOMAIN_NAMES:
        for pair in _root_b(domain) - ROOT_ROUTES - DOCS_ROUTES:
            owners.setdefault(pair, []).append(domain)
    shared = {pair: names for pair, names in owners.items() if len(names) > 1}
    assert shared == {}, f"routes claimed by more than one domain: {shared}"
    assert len(owners) == DOMAIN_ROUTE_COUNT


def test_the_price_alert_unsubscribe_route_is_registered_first() -> None:
    """The unsubscribe route is registered before the alert id route that could shadow it."""
    from app.main import app

    paths = [
        path
        for route in _effective_routes(app)
        for path in [getattr(route, "path", None)]
        if path is not None and path.startswith("/api/part-price-alerts")
    ]
    unsubscribe = paths.index("/api/part-price-alerts/unsubscribe")
    parameterised = min(index for index, path in enumerate(paths) if "{alert_id}" in path)
    assert unsubscribe < parameterised


def test_the_admin_users_routes_resolve_ahead_of_the_user_id_route() -> None:
    """The admin users subtree resolves ahead of the single-segment user id route."""
    from starlette.routing import Match

    from app.entrypoints.users import build_app

    app = build_app()

    def resolved(path: str) -> Optional[str]:
        """The path pattern that matches a GET of the given path, if any."""
        scope = {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "root_path": "",
        }
        for route in _effective_routes(app):
            match, _ = route.matches(scope)
            if match == Match.FULL:
                return getattr(route, "path", None)
        return None

    assert resolved("/api/users/admin/users") == "/api/users/admin/users"
    assert resolved("/api/users/admin") == "/api/users/{user_id}"
