"""OpenTelemetry on in the domain functions, and Sentry gone from the backend.

Each property fails silently in production, so each is asserted on the source.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

BACKEND = Path(__file__).resolve().parents[2]
ENTRYPOINTS = BACKEND / "app" / "entrypoints"


def _source(domain: str) -> str:
    """The source text of one domain's entrypoint module."""
    return (ENTRYPOINTS / f"{ENTRYPOINT_MODULES[domain]}.py").read_text()


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
    source = (BACKEND / "app" / "composition" / "app.py").read_text()
    assert "sentry" not in source.lower()


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_main_configures_tracing_before_it_builds_the_app(domain: str) -> None:
    """Tracing is configured before the application is built, or it is never instrumented."""
    called = _called_names(_main_body(domain))

    assert "configure_tracing" in called, f"{domain}: main does not configure tracing"
    assert "build_app" in called, f"{domain}: main does not build an application"
    assert called.index("configure_tracing") < called.index("build_app"), (
        f"{domain}: main builds the application before configuring tracing, so "
        "the FastAPI instrumentation is never attached"
    )


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_main_configures_logging_before_tracing(domain: str) -> None:
    """Logging is configured before tracing, so tracing warnings land in the JSON format."""
    called = _called_names(_main_body(domain))

    assert called.index("configure_logging") < called.index("configure_tracing"), (
        f"{domain}: tracing is configured before logging, so its warnings are "
        "emitted in whatever format the root logger defaulted to"
    )


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_the_module_level_app_is_not_the_one_main_serves(domain: str) -> None:
    """main builds its own application, since the module-level one predates the provider."""
    body = _main_body(domain)
    called = _called_names(body)

    assert "run_uvicorn" in called, f"{domain}: main does not serve"

    served = [
        statement
        for statement in body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "run_uvicorn"
    ]
    assert len(served) == 1, f"{domain}: expected exactly one run_uvicorn call"

    argument = served[0].value.args[0]
    assert isinstance(argument, ast.Call) and isinstance(argument.func, ast.Name), (
        f"{domain}: run_uvicorn is not passed a freshly built application"
    )
    assert argument.func.id == "build_app", (
        f"{domain}: run_uvicorn serves {ast.dump(argument)} rather than build_app(), "
        "so it serves an application built before tracing was configured"
    )


@pytest.mark.parametrize("filename", ["requirements.txt", "requirements-lambda.txt"])
def test_both_requirements_files_carry_the_aws_otel_extra(filename: str) -> None:
    """Both requirements files carry the aws-otel extra that signs the OTLP export."""
    line = next(
        raw.strip() for raw in (BACKEND / filename).read_text().splitlines() if raw.strip().startswith("webbpulse[")
    )
    extras = line.split("[", 1)[1].split("]", 1)[0].split(",")
    assert "otel" in extras, f"{filename}: the otel extra is what provides configure_tracing"
    assert "aws-otel" in extras, (
        f"{filename}: without the aws-otel extra the exporter posts unsigned and "
        "every span is silently rejected with a 403"
    )
