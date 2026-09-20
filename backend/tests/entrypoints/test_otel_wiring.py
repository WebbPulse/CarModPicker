"""OpenTelemetry on in the domain functions, and Sentry gone from the backend.

Each property fails silently in production, so each is asserted on the source.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest

from app.common.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

BACKEND = Path(__file__).resolve().parents[2]
DOMAINS_ROOT = BACKEND / "app" / "domains"


def _source(domain: str) -> str:
    """The source text of one domain's entrypoint module."""
    return (DOMAINS_ROOT / ENTRYPOINT_MODULES[domain] / "entrypoint.py").read_text()


def _main_body(domain: str) -> list[ast.stmt]:
    """The statements of `main`, so order is asserted on the tree not on text."""
    tree = ast.parse(_source(domain))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node.body
    raise AssertionError(f"{domain}: no main() in its entrypoint")


def _called_names(body: list[ast.stmt]) -> list[str]:
    """Every call in `body`, in source order, by the name being called."""
    names: list[str] = []
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name):
                    names.append(function.id)
                elif isinstance(function, ast.Attribute):
                    names.append(function.attr)
    return names


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_does_not_initialise_sentry(domain: str) -> None:
    """No entrypoint imports or calls init_sentry."""
    tree = ast.parse(_source(domain))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.extend(alias.name for alias in node.names)
            if node.module is not None:
                imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    assert not [name for name in imported if "sentry" in name.lower()], (
        f"{domain} imports Sentry; Sentry is removed from the backend"
    )

    called = _called_names(tree.body)
    assert "init_sentry" not in called, f"{domain} still calls init_sentry"


def test_the_monolith_does_not_initialise_sentry() -> None:
    """The monolith no longer initialises Sentry, since OpenTelemetry is the only instrumentation."""
    source = (BACKEND / "app" / "common" / "composition" / "app.py").read_text()
    assert "sentry" not in source.lower()


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_main_is_the_packages_entrypoint_pair(domain: str) -> None:
    """`main` and `build_app` come from `domain_entrypoint`, not from a local `main`.

    The order these three properties used to be asserted on, logging before
    tracing and tracing before the build, is the order `domain_entrypoint`
    guarantees and `test_an_entrypoint_exposes_the_runtime_wiring` in
    `test_entrypoint_isolation.py` asserts by running `main` with the wiring
    replaced. It cannot be read off the tree any more because `main` is a
    closure the package builds, so what is asserted here is that the entrypoint
    really does delegate to the package rather than growing its own `main` back.
    """
    tree = ast.parse(_source(domain))

    assert not [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"], (
        f"{domain}: its entrypoint defines its own main() again, so the order "
        "domain_entrypoint guarantees is no longer the order the process runs in"
    )
    assert "domain_entrypoint" in _called_names(tree.body), f"{domain}: its entrypoint does not call domain_entrypoint"


def test_the_runtime_dependency_carries_the_aws_otel_extra() -> None:
    """The webbpulse runtime dependency carries the aws-otel extra that signs the OTLP export."""
    project = tomllib.loads((BACKEND / "pyproject.toml").read_text())
    line = next(raw for raw in project["project"]["dependencies"] if raw.startswith("webbpulse["))
    extras = line.split("[", 1)[1].split("]", 1)[0].split(",")
    assert "otel" in extras, "pyproject.toml: the otel extra is what provides configure_tracing"
    assert "aws-otel" in extras, (
        "pyproject.toml: without the aws-otel extra the exporter posts unsigned and "
        "every span is silently rejected with a 403"
    )
