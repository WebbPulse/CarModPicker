"""Tests for which repositories each domain's process carries and which it refuses.

Recomputes the declared bundles from the real import graph and probes cold start imports.
"""

from __future__ import annotations

import ast
import json
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set

import pytest

from app.api.dependencies.repositories import (
    ALL_REPOSITORY_NAMES,
    RepositoryBundle,
    RepositoryNotInBundle,
    build_bundle,
    get_repositories,
)
from app.composition.domains import DOMAIN_NAMES, DOMAINS, ENTRYPOINT_MODULES
from app.db.dynamo.registry import REPOSITORY_SPECS

BACKEND = Path(__file__).resolve().parents[2]

UNREADABLE_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:000000000000:secret:carmodpicker-nonexistent-AAAAAA"

TABLE_OWNERS: Dict[str, str] = {
    "users": "users",
    "oauth_accounts": "identity",
    "webauthn_credentials": "identity",
    "app_settings": "users",
    "parts": "catalog",
    "part_cars": "catalog",
    "part_listings": "catalog",
    "part_price_history": "catalog",
    "part_manufacturers": "catalog",
    "categories": "catalog",
    "retailers": "catalog",
    "car_makes": "vehicles",
    "car_models": "vehicles",
    "car_generations": "vehicles",
    "build_lists": "build-lists",
    "build_list_parts": "build-lists",
    "build_list_phases": "build-lists",
    "build_list_labor_estimates": "build-lists",
    "build_logs": "build-logs",
    "build_log_posts": "build-logs",
    "votes": "moderation",
    "reports": "moderation",
    "bug_reports": "moderation",
    "part_price_alerts": "admin",
    "image_source_mappings": "media",
}

EXPECTED_CROSS_DOMAIN_READS: Dict[str, Set[str]] = {
    "identity": {"users"},
    "users": {"oauth_accounts"},
    "catalog": {
        "users",
        "car_makes",
        "car_models",
        "car_generations",
        "votes",
    },
    "vehicles": {
        "users",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_lists",
        "votes",
    },
    "build-lists": {
        "users",
        "car_makes",
        "car_models",
        "car_generations",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_logs",
        "build_log_posts",
        "votes",
    },
    "build-logs": {"users", "build_lists"},
    "moderation": {"users", "car_makes", "car_models", "car_generations", "parts", "build_lists"},
    "media": {"users", "car_generations", "parts", "build_lists"},
    "admin": {
        "users",
        "oauth_accounts",
        "webauthn_credentials",
        "car_makes",
        "car_models",
        "car_generations",
        "categories",
        "part_manufacturers",
        "retailers",
        "parts",
        "part_cars",
        "part_listings",
        "part_price_history",
        "build_lists",
        "build_list_phases",
        "build_logs",
        "votes",
        "reports",
        "image_source_mappings",
    },
}


def _module_file(module: str) -> Optional[Path]:
    """Resolve a module name to its file, whether it is a module or a package."""
    candidate = BACKEND / (module.replace(".", "/") + ".py")
    if candidate.exists():
        return candidate
    package = BACKEND / module.replace(".", "/") / "__init__.py"
    return package if package.exists() else None


def _app_imports(tree: ast.AST, module: str) -> Set[str]:
    """The `app.*` modules one module imports, including `from x import y` where
    `y` is itself a module rather than a name."""
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
            found.add(node.module)
            for alias in node.names:
                submodule = f"{node.module}.{alias.name}"
                if _module_file(submodule) is not None:
                    found.add(submodule)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names if alias.name.startswith("app"))
    return {name for name in found if _module_file(name) is not None}


def _bundle_accesses(tree: ast.AST) -> Set[str]:
    """Every repository attribute taken off a bundle, under either spelling."""
    found: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr not in REPOSITORY_SPECS:
            continue
        receiver = node.value
        if isinstance(receiver, ast.Name) and receiver.id == "repos":
            found.add(node.attr)
        elif isinstance(receiver, ast.Attribute) and receiver.attr == "repos":
            found.add(node.attr)
    return found


EXTRA_REACHABLE: Dict[str, Set[str]] = {
    "identity": {"users", "oauth_accounts", "webauthn_credentials"},
}


def _reachable_repositories(domain: str) -> Set[str]:
    """Every repository any module the domain's routers reach can access."""
    roots: Set[str] = set()
    source = ast.parse(_read_loader_source(domain))
    for node in ast.walk(source):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.api.endpoints"):
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                roots.add(candidate if _module_file(candidate) is not None else node.module)

    seen: Set[str] = set()
    stack = list(roots)
    accesses: Set[str] = set()
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        path = _module_file(module)
        if path is None:
            continue
        seen.add(module)
        text = path.read_text()
        tree = ast.parse(text)
        accesses |= _bundle_accesses(tree)
        stack.extend(_app_imports(tree, module))
    return accesses | EXTRA_REACHABLE.get(domain, set())


def _read_loader_source(domain: str) -> str:
    """Return the source of a domain's router loader."""
    import inspect

    return inspect.getsource(DOMAINS[domain].load_routers).strip()


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_declares_every_repository_its_routes_reach(domain: str) -> None:
    """A domain declares every repository its routes can reach."""
    declared = set(DOMAINS[domain].repositories)
    reachable = _reachable_repositories(domain)
    missing = sorted(reachable - declared)
    assert missing == [], f"{domain} reaches {missing} but does not declare them"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_declares_no_repository_its_routes_cannot_reach(domain: str) -> None:
    """A domain declares no repository its routes cannot reach."""
    declared = set(DOMAINS[domain].repositories)
    reachable = _reachable_repositories(domain)
    surplus = sorted(declared - reachable)
    assert surplus == [], f"{domain} declares {surplus} but no route reaches them"


def test_every_table_has_exactly_one_owner() -> None:
    """Every table has exactly one owning domain."""
    registry_tables = {spec.table for spec in REPOSITORY_SPECS.values()}
    assert sorted(registry_tables) == sorted(TABLE_OWNERS)
    assert len(REPOSITORY_SPECS) == 25
    assert set(TABLE_OWNERS.values()) <= set(DOMAIN_NAMES)


@pytest.mark.parametrize("table,owner", sorted(TABLE_OWNERS.items()))
def test_the_owning_domain_carries_the_table_it_owns(table: str, owner: str) -> None:
    """An owner that cannot reach its own table cannot serve its own routes."""
    assert table in DOMAINS[owner].tables, f"{owner} owns {table} but its bundle does not carry it"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_no_cross_domain_read_is_undeclared(domain: str) -> None:
    """Every repository a domain carries is its own or a listed cross domain seam."""
    owned = {name for name, spec in REPOSITORY_SPECS.items() if TABLE_OWNERS[spec.table] == domain}
    borrowed = set(DOMAINS[domain].repositories) - owned
    assert borrowed == EXPECTED_CROSS_DOMAIN_READS[domain], (
        f"{domain}'s cross-domain reads changed. "
        f"Added: {sorted(borrowed - EXPECTED_CROSS_DOMAIN_READS[domain])}. "
        f"Removed: {sorted(EXPECTED_CROSS_DOMAIN_READS[domain] - borrowed)}."
    )


def test_media_is_the_narrowest_bundle() -> None:
    """The media bundle stays the narrowest, since it is the first domain cut over."""
    media = DOMAINS["media"]
    assert media.tables == (
        "build_lists",
        "car_generations",
        "image_source_mappings",
        "parts",
        "users",
    )
    assert len(media.repositories) == 5
    assert min(len(DOMAINS[d].repositories) for d in DOMAIN_NAMES) == 3


def test_a_bundle_refuses_a_repository_it_does_not_carry() -> None:
    """And the message names the table, because that is the next question."""
    bundle = build_bundle(DOMAINS["media"].repositories, name="media")
    with pytest.raises(RepositoryNotInBundle) as raised:
        bundle.app_settings
    assert raised.value.repository == "app_settings"
    assert raised.value.table == "app_settings"
    assert "app_settings" in str(raised.value)
    assert "media" in str(raised.value)


def test_the_refusal_is_an_attribute_error() -> None:
    """An undeclared repository raises an attribute error, so hasattr still works."""
    bundle = build_bundle(DOMAINS["media"].repositories, name="media")
    assert issubclass(RepositoryNotInBundle, AttributeError)
    assert getattr(bundle, "app_settings", None) is None
    assert not hasattr(bundle, "app_settings")


def test_a_bundle_builds_nothing_until_a_repository_is_asked_for() -> None:
    """Laziness is the property that makes a cold start proportional."""
    bundle = build_bundle(DOMAINS["media"].repositories, name="media")
    assert "built=[]" in repr(bundle)
    first = bundle.image_source_mappings
    assert "image_source_mappings" in repr(bundle)
    assert bundle.image_source_mappings is first


def test_an_unknown_repository_name_is_rejected_when_the_bundle_is_built() -> None:
    """A typo in a domain's tuple fails at build rather than on one route."""
    with pytest.raises(ValueError, match="typo_repository"):
        build_bundle(("users", "typo_repository"), name="broken")


def test_the_bundle_reports_the_tables_it_can_reach() -> None:
    """What a Terraform IAM policy for the domain has to cover."""
    bundle = build_bundle(DOMAINS["build-logs"].repositories, name="build-logs")
    assert bundle.tables == ("build_lists", "build_log_posts", "build_logs", "users")
    assert bundle.repository_names == DOMAINS["build-logs"].repositories


def test_the_union_of_the_nine_bundles_is_all_twenty_five() -> None:
    """The nine bundles together cover every repository."""
    union: Set[str] = set()
    for domain in DOMAIN_NAMES:
        union |= set(DOMAINS[domain].repositories)
    assert union == set(ALL_REPOSITORY_NAMES)
    assert len(ALL_REPOSITORY_NAMES) == 25


def test_root_a_binds_a_bundle_carrying_all_twenty_five() -> None:
    """The monolith binds a bundle carrying every repository."""
    from app.api.dependencies.repositories import get_repositories as dependency
    from app.main import app

    override = app.dependency_overrides.get(dependency)
    assert override is not None, "Root A did not bind a repository bundle"
    bundle = override()
    assert isinstance(bundle, RepositoryBundle)
    assert set(bundle.repository_names) == set(ALL_REPOSITORY_NAMES)


def test_the_process_default_is_the_full_set() -> None:
    """Outside any application the default bundle is the full set, for scripts."""
    assert set(get_repositories().repository_names) == set(ALL_REPOSITORY_NAMES)


def test_building_one_domain_does_not_disturb_another() -> None:
    """Bundles bind per application, so building one domain does not affect another."""
    import importlib

    media = importlib.import_module("app.entrypoints.media").build_app()
    users = importlib.import_module("app.entrypoints.users").build_app()

    from app.api.dependencies.repositories import get_repositories as dependency

    media_bundle = media.dependency_overrides[dependency]()
    users_bundle = users.dependency_overrides[dependency]()
    assert set(media_bundle.repository_names) == set(DOMAINS["media"].repositories)
    assert set(users_bundle.repository_names) == set(DOMAINS["users"].repositories)
    assert "app_settings" in users_bundle.repository_names
    assert "app_settings" not in media_bundle.repository_names


def _run(code: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Run a snippet in a fresh interpreter with a minimal environment and parse its JSON."""
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    environment.update(env or {})
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", code],
        cwd=str(BACKEND),
        env=environment,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"subprocess failed with an empty environment:\n{result.stderr}"
    return json.loads(result.stdout.strip().splitlines()[-1])


BUNDLE_PROBE = """
import json, sys
from app.entrypoints import {module} as entrypoint
from app.api.dependencies.repositories import get_repositories

app = entrypoint.build_app()
bundle = app.dependency_overrides[get_repositories]()
print(json.dumps({{
    "declared": sorted(bundle.repository_names),
    "tables": sorted(bundle.tables),
    "built": sorted(bundle._built),
    "dynamo_modules": sorted(
        name for name in sys.modules
        if name.startswith("app.db.dynamo.") and name.count(".") == 3
    ),
}}))
"""


@pytest.fixture(scope="module")
def bundle_probes() -> Dict[str, Dict[str, Any]]:
    """Probe each domain in its own interpreter and return what its bundle carries."""
    return {
        domain: _run(
            BUNDLE_PROBE.format(module=ENTRYPOINT_MODULES[domain]),
            env={"APP_SECRETS_ARN": UNREADABLE_SECRET_ARN},
        )
        for domain in DOMAIN_NAMES
    }


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_building_a_domain_constructs_no_repository(domain: str, bundle_probes: Dict[str, Dict[str, Any]]) -> None:
    """Building a domain's application constructs no repository."""
    assert bundle_probes[domain]["built"] == []


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_a_domain_binds_exactly_its_own_bundle(domain: str, bundle_probes: Dict[str, Dict[str, Any]]) -> None:
    """In a fresh interpreter, with no credentials, as a cold start would."""
    assert bundle_probes[domain]["declared"] == sorted(DOMAINS[domain].repositories)
    assert bundle_probes[domain]["tables"] == sorted(DOMAINS[domain].tables)


def test_media_builds_without_importing_another_domains_data_modules(
    bundle_probes: Dict[str, Dict[str, Any]],
) -> None:
    """Building media imports none of the data modules behind repositories it lacks."""
    imported = set(bundle_probes["media"]["dynamo_modules"])
    for module in ("app_settings", "bug_reports", "part_price_alerts", "build_logs"):
        assert f"app.db.dynamo.{module}" not in imported, f"media imported app.db.dynamo.{module}"


def test_importing_the_registry_imports_no_repository_module() -> None:
    """Importing the registry pulls in no repository module, only the shared base."""
    repository_modules = {f"app.db.dynamo.{spec.module}" for spec in REPOSITORY_SPECS.values()}
    assert len(repository_modules) == 9

    imported = _run(
        "import json, sys\n"
        "import app.db.dynamo.registry\n"
        "print(json.dumps(sorted(m for m in sys.modules if m.startswith('app.db.dynamo.'))))\n"
    )
    assert sorted(repository_modules & set(imported)) == []
