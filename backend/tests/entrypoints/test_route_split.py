"""The route contract, and the agreement between the two composition roots.

Three claims, in order of what they protect.

**Root A serves exactly the routes it served before the split.**
`tests/fixtures/route_contract.json` was captured from `app.main:app` on
`staging` before any of this existed, and is asserted here as a sorted list of
`(method, path)` pairs plus a count. It overlaps
`tests/test_openapi_snapshot.py`, deliberately: the snapshot pins the whole
published document and fails on a schema change as well as a routing one, while
this pins routing alone, so a failure here says "a route moved" rather than
"something in the document changed".

**Root B's routes are Root A's routes, partitioned.** The union of the nine
per-domain applications equals Root A exactly. This is the contract that lets a
cut be verified: when API Gateway starts sending `/api/images` to the `media`
function, the response has to be the one the monolith would have given, and it
can only be if `media`'s application declares the same routes.

**Each domain serves the number of routes the plan says it does.** Section 1.1
lists per-domain counts, and they are asserted individually rather than only in
aggregate, so a route moving between two domains fails loudly instead of
cancelling out in the total.

## 152 against 147

Section 2.7 of the plan speaks of 176 routes and section 1.1's per-domain table
sums to 171. Both were right when they were written, and row 13 of
`docs/identity-adoption.md` subtracted 24 from each: it deleted the four legacy
routers under `/api/auth`, which were the whole of the `identity` domain's own
route list. So the pair is 152 against 147 now, and the difference between them
is still the five root routes.

- 147 are the domain routes under `/api`, and each of the nine per-domain counts
  in section 1.1 is exact. `identity` is 0 of them: it still serves `/api/auth`,
  but every route there is the `webbpulse.identity` package's, mounted by
  `app/composition/wiring.py` and not declared by this application.
- 5 more are `/`, `/health`, `/ready`, `/sitemap.xml` and `/sitemap-{name}.xml`,
  which belong to no domain and which every function serves locally, because the
  Lambda Web Adapter polls `/health` on every cold start and a function that did
  not answer it would never be marked ready.
- 152 is the sum, and it is what a deployed function's route table has to
  contain: its own domain's routes plus those five.

FastAPI adds four more of its own on top, which every count in the plan
excludes: `/docs`, `/docs/oauth2-redirect`, `/redoc` and `/api/openapi.json`.
So Root A serves 156 routes in total, and the constants below name all three
numbers so a future reader does not have to re-derive which is which.

## Counting routes is version dependent

`len(app.routes)` is not that 156 on every supported version, which is why
`_effective_routes` exists. Starlette 1.x, which `requirements.txt` pins via
FastAPI 0.141.1, changed `include_router` to store one lazy `_IncludedRouter`
per included router instead of copying the sub-router's routes into the parent.
On that version `app.routes` has 30 entries for Root A: the 4 doc routes, the 5
root routes, and 21 opaque wrappers whose own `path` and `methods` are `None`.
Walking it naively finds 9 routes and misses all 147. Starlette 0.x flattens on
include and the same walk finds all 156. Row 13 took four of those wrappers with
it, one per legacy auth router.

The difference is invisible in the served application: routing and the OpenAPI
document are identical either way, which is exactly why it is worth a test.
A count taken from `app.routes` silently means something different depending on
which version is installed, so every count here goes through
`_effective_routes`, which handles both shapes.
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

DOMAIN_ROUTE_COUNT = 148
ROOT_ROUTE_COUNT = 5
DEPLOYED_ROUTE_COUNT = DOMAIN_ROUTE_COUNT + ROOT_ROUTE_COUNT
TOTAL_WITH_DOCS = DEPLOYED_ROUTE_COUNT + len(DOCS_ROUTES)

EXPECTED_DOMAIN_ROUTES = {
    "identity": 0,
    "users": 14,
    "catalog": 43,
    "vehicles": 11,
    "build-lists": 34,
    "build-logs": 5,
    "moderation": 20,
    "media": 9,
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
