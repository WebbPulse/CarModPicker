"""What each entrypoint may import, and what it may need to start.

Each domain image carries only its own domain and builds with no credentials.
"""

from __future__ import annotations

import json
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from app.common.composition import wiring
from app.common.composition.domains import DOMAIN_NAMES, ENTRYPOINT_MODULES

BACKEND = Path(__file__).resolve().parents[2]

UNREADABLE_SECRET_ARN = "arn:aws:secretsmanager:us-west-2:000000000000:secret:carmodpicker-nonexistent-AAAAAA"

PROBE = """
import json, sys
import app.domains.{module}.entrypoint as entrypoint

app = entrypoint.build_app()
endpoints = sorted(
    name
    for name in sys.modules
    if name.startswith("app.domains.") and ".endpoints." in name and name.count(".") == 4
)
print(json.dumps({{
    "endpoints": endpoints,
    "routes": len(app.routes),
    "domain": entrypoint.DOMAIN.name,
    "service_name": entrypoint.DOMAIN.service_name,
    "requires_secrets": list(entrypoint.DOMAIN.requires_secrets),
}}))
"""


def _run(code: str, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Run one snippet in a fresh interpreter with an all but empty environment.

    The stripped environment is the point, so only PATH and PYTHONPATH are set.
    """
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


@pytest.fixture(scope="module")
def probes() -> Dict[str, Dict[str, Any]]:
    """One subprocess per domain, reused across the tests in this module."""
    return {
        domain: _run(
            PROBE.format(module=ENTRYPOINT_MODULES[domain]),
            env={"APP_SECRETS_ARN": UNREADABLE_SECRET_ARN},
        )
        for domain in DOMAIN_NAMES
    }


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_builds_with_no_credentials(domain: str, probes: Dict[str, Dict[str, Any]]) -> None:
    """Every entrypoint builds its application with no AWS credentials available."""
    assert probes[domain]["routes"] > 0
    assert probes[domain]["domain"] == domain


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_imports_only_its_own_endpoint_modules(domain: str, probes: Dict[str, Dict[str, Any]]) -> None:
    """The claim that makes nine images smaller than nine copies of one image."""
    from app.common.composition.domains import DOMAINS

    expected = sorted(
        {
            ".".join(route.endpoint.__module__.split(".")[:5])
            for router, _, _ in DOMAINS[domain].load_routers()
            for route in router.routes
            if getattr(route, "endpoint", None) is not None
            and route.endpoint.__module__.startswith("app.domains.")
            and ".endpoints." in route.endpoint.__module__
        }
    )
    imported = probes[domain]["endpoints"]
    if domain == "identity":
        assert expected == []
        assert imported == []
        return
    assert imported, f"{domain} imported no endpoint module at all"
    assert imported == expected, f"{domain} imported {imported}, but owns {expected}"


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_reports_its_own_service_name(domain: str, probes: Dict[str, Dict[str, Any]]) -> None:
    """Each entrypoint reports the service name of its own domain."""
    assert probes[domain]["service_name"] == f"carmodpicker-{domain}"


def test_only_the_domains_that_verify_a_legacy_token_need_the_secret(
    probes: Dict[str, Dict[str, Any]],
) -> None:
    """The least-privilege claim the split rests on, asserted rather than assumed.

    After row 13 of `docs/identity-adoption.md` exactly one domain names
    `SECRET_KEY`, and the inversion is the point of this test.

    Before row 13 seven domains named it, because `get_current_user` and its
    siblings decoded a legacy HS256 session before falling back to an identity
    access token. Row 13 deleted that legacy branch from every resolver, so
    those dependencies now resolve an identity RS256 token that the API Gateway
    JWT authorizer verified against the issuer's JWKS. Verifying it needs no
    application secret at all, which is why eight of the nine functions should
    now hold no `secretsmanager:GetSecretValue` grant and carry no
    `APP_SECRETS_ARN`.

    `admin` is the exception, and it is an exception for exactly one route.
    `GET /api/part-price-alerts/unsubscribe` reads a 30 day HS256 token that
    `app/core/email.py` mints into a price-drop alert email. The recipient of
    that email is by construction not signed in, so there is no identity access
    token equivalent for the link, and `SECRET_KEY` cannot leave the estate
    until that link is replaced.

    **`requires_secrets` is not the same question as the Terraform grant, and
    this test does not answer the second one.** `requires_secrets` says which
    names `check_signing_key` turns into a hard startup requirement, which means
    a *settings field* that must be present. The `identity` domain reads two
    keys of the same `carmodpicker-<env>/app` secret, the Google and GitHub
    OAuth client secrets, through `build_oauth_client_secrets` in
    `app/composition/identity.py`, which calls `app_secrets` directly and
    deliberately never routes them through `Settings`. They are optional, so
    naming them here would fail a cold start over a supported state. So
    `identity` declares nothing and still needs the grant, and
    `terraform/lambda_domains.tf` keeps `secrets = true` on it for that reason.
    Anybody deriving a Terraform grant from this list alone will take that grant
    away and silently turn off OAuth sign in.
    """
    for domain in DOMAIN_NAMES:
        expected = ["SECRET_KEY"] if domain == "admin" else []
        assert probes[domain]["requires_secrets"] == expected, (
            f"{domain} declares {probes[domain]['requires_secrets']}, expected {expected}. "
            "After row 13 only `admin` reads SECRET_KEY, for the price alert "
            "unsubscribe link. See docs/identity-adoption.md row 13."
        )


def test_importing_the_descriptors_imports_no_endpoint_module() -> None:
    """Importing the domain descriptors imports no endpoint module.

    Routers load through a callable so no entrypoint pulls in all nine domains.
    """
    result = _run(
        "import json, sys\n"
        "import app.common.composition.domains\n"
        "print(json.dumps(sorted(m for m in sys.modules "
        "if m.startswith('app.domains.') and '.endpoints.' in m)))\n"
    )
    assert result == []


def test_no_entrypoint_imports_the_monolith_composition_root() -> None:
    """No entrypoint imports app.main, which would build every domain at import."""
    for domain in DOMAIN_NAMES:
        source = (BACKEND / "app" / "domains" / ENTRYPOINT_MODULES[domain] / "entrypoint.py").read_text()
        assert "app.main" not in source
        assert "from ..main" not in source


@pytest.mark.parametrize("domain", sorted(DOMAIN_NAMES))
def test_an_entrypoint_exposes_the_runtime_wiring(domain: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every entrypoint exposes a build_app and the main the process runs.

    `main` is the closure `domain_entrypoint` returns, so what it calls cannot be
    read off the syntax tree the way the hand-written `main` allowed. It is run
    instead, with the three wiring helpers and the uvicorn runner replaced, which
    asserts the stronger thing the old parse only approximated: that running the
    process actually configures logging, then tracing, then checks the secrets,
    and only then serves. Sentry initialisation is asserted absent by
    test_otel_wiring.py, since these functions report through OpenTelemetry.
    """
    module = __import__(f"app.domains.{ENTRYPOINT_MODULES[domain]}.entrypoint", fromlist=["main"])
    assert callable(module.build_app)
    assert callable(module.main)

    called: List[str] = []
    monkeypatch.setattr(wiring, "configure_logging", lambda **_: called.append("configure_logging"))
    monkeypatch.setattr(wiring, "configure_tracing", lambda *_: called.append("configure_tracing"))
    monkeypatch.setattr(wiring, "check_signing_key", lambda *_: called.append("check_signing_key"))
    monkeypatch.setattr(module, "build_domain_app", lambda *_, **__: called.append("build_domain_app"))
    monkeypatch.setattr("webbpulse.composition._run_uvicorn", lambda _: called.append("run_uvicorn"))

    module.main()

    assert called == [
        "configure_logging",
        "configure_tracing",
        "check_signing_key",
        "build_domain_app",
        "run_uvicorn",
    ], f"{domain} entrypoint's main ran {called}"


SANCTIONED_FOREIGN_IMPORTS = frozenset(
    {
        "app.domains.identity",
        "app.domains.identity.package_glue",
    }
)
"""The one foreign package every non-identity image has always carried.

`add_shared_middleware` imports `build_identity_settings` so the local authorizer
can stand in for the gateway's JWT authorizer, which every domain needs and only
the identity domain defines. It is two modules of settings construction that pull
in no endpoint module and no store, which is why the endpoint-module check above
has always passed. `assert_entrypoint_isolation` counts whole domain packages, so
it sees them where this product's own check does not.
"""


def test_each_entrypoint_imports_only_its_own_domain() -> None:
    """The package's own isolation check over this product's registry.

    The shipped form of what the per-domain endpoint-module test asserts above,
    kept alongside it because the package's probe covers every module of a
    foreign domain rather than its endpoint modules alone. Anything foreign
    beyond the identity settings seam is a regression.
    """
    from webbpulse.testing import entrypoint_imports

    for domain in DOMAIN_NAMES:
        package = ENTRYPOINT_MODULES[domain]
        result = entrypoint_imports(
            domain,
            module=f"app.domains.{package}.entrypoint",
            package=package,
            package_root="app.domains.",
            cwd=BACKEND,
            env={"APP_SECRETS_ARN": UNREADABLE_SECRET_ARN},
        )
        assert set(result.foreign) <= SANCTIONED_FOREIGN_IMPORTS, (
            f"the {domain} image also imported {sorted(set(result.foreign) - SANCTIONED_FOREIGN_IMPORTS)}"
        )
