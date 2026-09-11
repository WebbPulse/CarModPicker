"""Tests that the gateway's authenticated route keys match what the application enforces.

The set is recomputed from the real application, never listed here, so the two cannot drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterator, Set, Tuple

BACKEND = Path(__file__).resolve().parents[2]
APIGATEWAY_TF = BACKEND.parent / "terraform" / "apigateway.tf"

REQUIRES_CALLER = {
    "get_current_user",
    "get_current_admin_user",
    "get_current_superuser",
}

TOLERATES_ANONYMOUS = {
    "get_optional_current_user",
    "get_current_active_user_optional",
    "require_api_key_or_admin",
}

IDENTITY_PREFIX = "/api/auth"

ROOT_PATHS = {
    "/",
    "/health",
    "/ready",
    "/sitemap.xml",
    "/sitemap-{name}.xml",
}

DOMAIN_LIST = re.compile(
    r'^\s*"?(?P<domain>[a-z][a-z-]*)"?\s*=\s*\[(?P<body>[^\]]*)\]',
    re.MULTILINE,
)

GUARD_ENTRY = re.compile(
    r'"(?P<key>(?:ANY|GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) /[^"]*)"\s*='
    r'\s*\{\s*integration\s*=\s*"(?P<integration>[^"]+)"\s*\}'
)


def _terraform_source() -> str:
    """Read the API Gateway Terraform file."""
    return APIGATEWAY_TF.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """Drop whole line comments, so route keys quoted in prose are not read as configuration."""
    return "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))


def _block(source: str, name: str) -> str:
    """Extract a named local's body by brace balance, since route keys contain braces."""
    start = source.index(f"{name} = {{")
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"local.{name} is not brace balanced in {APIGATEWAY_TF}")


def terraform_domain_route_keys() -> Dict[str, str]:
    """Every route key in `local.domain_identity_jwt_route_paths`, to its domain."""
    block = _block(_strip_comments(_terraform_source()), "domain_identity_jwt_route_paths")
    out: Dict[str, str] = {}
    for match in DOMAIN_LIST.finditer(block):
        domain = match.group("domain")
        for key in re.findall(r'"([^"]+)"', match.group("body")):
            assert key not in out, f"{key} is written twice in local.domain_identity_jwt_route_paths"
            out[key] = domain
    return out


def terraform_guard_route_keys() -> Dict[str, str]:
    """Every route key in `local.domain_anonymous_guard_route_keys`, to its domain."""
    block = _block(_strip_comments(_terraform_source()), "domain_anonymous_guard_route_keys")
    return {match.group("key"): match.group("integration") for match in GUARD_ENTRY.finditer(block)}


def terraform_domain_prefixes() -> Dict[str, str]:
    """Each `/api` prefix in `local.lambda_domain_path_prefixes`, to its domain."""
    block = _block(_strip_comments(_terraform_source()), "lambda_domain_path_prefixes")
    out: Dict[str, str] = {}
    for match in DOMAIN_LIST.finditer(block):
        for prefix in re.findall(r'"([^"]+)"', match.group("body")):
            out[prefix] = match.group("domain")
    return out


def _effective_routes(app: object) -> Iterator[Any]:
    """Flatten every route an application serves, across both Starlette router shapes."""
    for route in getattr(app, "routes", []):
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            yield from contexts()
        else:
            yield route


def _dependency_names(route: object) -> Set[str]:
    """Every dependency callable name in a route's flattened dependant tree."""
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return set()
    names: Set[str] = set()
    stack = [dependant]
    seen: Set[int] = set()
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        call = getattr(current, "call", None)
        if call is not None:
            names.add(getattr(call, "__name__", ""))
        stack.extend(getattr(current, "dependencies", []) or [])
    return names


def _route_key(method: str, path: str) -> str:
    """`<METHOD> <path>`, with the trailing slash removed.

    A route key may not end in a slash: API Gateway rejects that spelling at
    create time. It does not normalise an inbound trailing slash onto the bare
    key either, so a flagged route whose FastAPI path keeps the slash is never
    matched. See `test_no_flagged_route_is_declared_with_a_trailing_slash`.
    """
    return f"{method} {path.rstrip('/') or path}"


def _application_routes() -> Iterator[Tuple[str, str, Set[str]]]:
    """`(method, path, dependency names)` for every route the monolith serves."""
    from app.main import app

    for route in _effective_routes(app):
        path = getattr(route, "path", None)
        if path is None:
            continue
        names = _dependency_names(route)
        for method in getattr(route, "methods", None) or []:
            if method != "HEAD":
                yield method, path, names


def _in_scope(path: str) -> bool:
    """Whether a path is a domain route this row governs."""
    if path in ROOT_PATHS or not path.startswith("/api"):
        return False
    return not (path == IDENTITY_PREFIX or path.startswith(IDENTITY_PREFIX + "/"))


def application_authenticated_route_keys() -> Set[str]:
    """Every in scope route key whose resolver refuses an anonymous caller."""
    return {
        _route_key(method, path)
        for method, path, names in _application_routes()
        if _in_scope(path) and (names & REQUIRES_CALLER)
    }


def application_anonymous_route_keys() -> Set[str]:
    """Every in scope route key that serves an anonymous caller."""
    return {
        _route_key(method, path)
        for method, path, names in _application_routes()
        if _in_scope(path) and not (names & REQUIRES_CALLER)
    }


def test_terraform_names_exactly_the_routes_that_require_a_caller() -> None:
    """The Terraform route keys equal the routes the application refuses anonymously."""
    expected = application_authenticated_route_keys()
    actual = set(terraform_domain_route_keys())

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    assert not missing, (
        "These routes require an authenticated caller but have no explicit route key in "
        "local.domain_identity_jwt_route_paths, so the gateway would never check them: "
        f"{missing}"
    )
    assert not extra, (
        "These route keys are named in local.domain_identity_jwt_route_paths but the application "
        "does not require an authenticated caller on them, so flagging them would 401 anonymous "
        f"callers: {extra}"
    )


def test_no_named_key_is_served_by_an_optional_resolver() -> None:
    """No flagged key sits on a route that serves anonymous callers."""
    named = set(terraform_domain_route_keys())
    for method, path, names in _application_routes():
        if not _in_scope(path):
            continue
        key = _route_key(method, path)
        if key not in named:
            continue
        overlap = names & TOLERATES_ANONYMOUS
        assert not overlap, (
            f"{key} is named in local.domain_identity_jwt_route_paths but resolves through "
            f"{sorted(overlap)}, which serves anonymous callers. Flagging it would turn a public "
            "route into a 401."
        )
        assert names & REQUIRES_CALLER, (
            f"{key} is named in local.domain_identity_jwt_route_paths but its dependency tree "
            "reaches none of the resolvers that refuse an anonymous caller. Either the route "
            "changed or a resolver was renamed and REQUIRES_CALLER is now stale."
        )


def test_every_named_key_points_at_the_domain_that_serves_its_prefix() -> None:
    """Each key's integration is the domain whose prefix its path falls under."""
    prefixes = terraform_domain_prefixes()
    for key, domain in sorted(terraform_domain_route_keys().items()):
        path = key.split(" ", 1)[1]
        matches = [p for p in prefixes if path == p or path.startswith(p + "/")]
        assert matches, f"{key} falls under no prefix in local.lambda_domain_path_prefixes"
        longest = max(matches, key=len)
        assert prefixes[longest] == domain, (
            f"{key} is listed under {domain!r} but its path falls under {longest!r}, "
            f"which local.lambda_domain_path_prefixes gives to {prefixes[longest]!r}."
        )


def test_no_route_key_ends_in_a_slash() -> None:
    """No route key ends in a slash, which the gateway refuses at apply time."""
    for key in sorted(set(terraform_domain_route_keys()) | set(terraform_guard_route_keys())):
        path = key.split(" ", 1)[1]
        assert path == "/" or not path.endswith("/"), f"{key} ends in a slash and would fail at apply time"


def test_no_flagged_route_is_declared_with_a_trailing_slash() -> None:
    """A flagged route's FastAPI path must match the key the gateway carries.

    API Gateway refuses a route key ending in a slash and does not normalise an
    inbound one onto the bare key, so `POST /api/build-lists/` matched the
    unflagged `ANY /api/build-lists/{proxy+}` instead, arrived with no authorizer
    claims and answered 401 to a valid identity token. Declaring the path without
    the slash makes the flagged key the one that matches; the sibling routes on the
    same base must lose the slash too, or the slashed request answers 405.
    """
    flagged = set(terraform_domain_route_keys())
    offenders = sorted(
        f"{method} {path}"
        for method, path, _ in _application_routes()
        if path.endswith("/") and path != "/" and _route_key(method, path) in flagged
    )
    assert not offenders, (
        f"{offenders} are flagged in apigateway.tf but declared with a trailing slash, so the "
        "gateway routes them to the unflagged {proxy+} key and they answer 401 to a valid "
        'identity token. Declare the path as "" rather than "/".'
    )


def test_no_base_path_mixes_the_slashed_and_bare_spellings() -> None:
    """Every root path must use one spelling across all its methods.

    Starlette redirects a trailing slash only when nothing matches the slashed path,
    so a base carrying `GET "/"` beside `POST ""` answers 405 to `POST /x/` rather
    than redirecting, which breaks callers that still send the slash.
    """
    spellings: dict[str, set[str]] = {}
    for method, path, _ in _application_routes():
        base = path.rstrip("/") or "/"
        spellings.setdefault(base, set()).add(path)
    offenders = sorted(base for base, seen in spellings.items() if len(seen) > 1)
    assert not offenders, (
        f"{offenders} declare both the slashed and bare spelling, so the slashed request "
        "answers 405 instead of redirecting onto the bare key."
    )


def test_anonymous_routes_are_not_captured_by_a_named_path_parameter_key() -> None:
    """No anonymous route is shadowed by a flagged path parameter key on the same method."""
    named = set(terraform_domain_route_keys())
    guards = set(terraform_guard_route_keys())

    def captures(key_path: str, request_path: str) -> bool:
        """Whether a route key path would match a request path segment by segment."""
        left = key_path.strip("/").split("/")
        right = request_path.strip("/").split("/")
        if len(left) != len(right):
            return False
        return all(a == b or (a.startswith("{") and a.endswith("}")) for a, b in zip(left, right))

    for anonymous in sorted(application_anonymous_route_keys()):
        method, path = anonymous.split(" ", 1)
        path = path.rstrip("/") or path
        for key in named:
            key_method, key_path = key.split(" ", 1)
            if key_method != method or key_path == path:
                continue
            if captures(key_path, path):
                assert anonymous in guards, (
                    f"{anonymous} is anonymous but would be captured by the flagged key {key}, "
                    "so it needs a literal key of its own in "
                    "local.domain_anonymous_guard_route_keys to hold the more specific match."
                )


def test_guard_keys_are_anonymous_routes_the_application_serves() -> None:
    """Every guard key names a real anonymous route and none of them is flagged."""
    guards = terraform_guard_route_keys()
    assert guards, "local.domain_anonymous_guard_route_keys is empty; the two count keys are missing"

    anonymous = application_anonymous_route_keys()
    named = set(terraform_domain_route_keys())
    for key in sorted(guards):
        assert key in anonymous, f"{key} is a guard key but the application does not serve it anonymously"
        assert key not in named, f"{key} is both a guard key and a flagged key"


def test_the_flag_is_gated_on_the_variable_rather_than_hardcoded() -> None:
    """The keys land unflagged until the enforcement variable turns them on."""
    source = _strip_comments(_terraform_source())
    assert "require_identity_jwt = var.domain_jwt_enforced" in source, (
        "local.domain_identity_jwt_route_keys must take require_identity_jwt from "
        "var.domain_jwt_enforced, so that the keys can land before enforcement begins."
    )

    variables = (BACKEND.parent / "terraform" / "variables.tf").read_text(encoding="utf-8")
    block = variables[variables.index('variable "domain_jwt_enforced"') :]
    block = block[: block.index("\n}\n") + 3]
    assert re.search(r"^\s*default\s*=\s*false\s*$", block, re.MULTILINE), (
        "var.domain_jwt_enforced must default to false: the frontend still sends the legacy "
        "session token and a flagged route rejects it."
    )
