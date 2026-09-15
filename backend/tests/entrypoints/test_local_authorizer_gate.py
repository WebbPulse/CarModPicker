"""The local authorizer gate never builds the package identity settings when deployed.

Every deployed function carries `IDENTITY_ISSUER`, but only the identity function carries
signing key ARNs, and the package settings refuse to construct without them. A gate that
built those settings before reading the application environment took every other domain
down at startup, so the environment check has to come first and this proves it does.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from app.common.composition import wiring
from app.common.composition.domains import DOMAINS
from app.common.core.config import settings
from app.domains.identity import package_glue


@pytest.fixture
def deployed_without_signing_keys(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A staging function's environment: an issuer, no signing key ARNs."""
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "staging")
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "IDENTITY_ISSUER", "https://staging.carmodpicker.com/api/auth")
    monkeypatch.setenv("IDENTITY_ISSUER", "https://staging.carmodpicker.com/api/auth")
    monkeypatch.setenv("IDENTITY_ENVIRONMENT", "staging")
    monkeypatch.delenv("IDENTITY_SIGNING_KEY_ARNS", raising=False)
    yield


def test_a_deployed_function_never_builds_the_identity_settings(
    deployed_without_signing_keys: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate returns before the package settings are constructed."""

    def refuse(*args: object, **kwargs: object) -> None:
        """Fail the test if the gate reaches for the package settings at all."""
        raise AssertionError("build_identity_settings was called outside the local environment")

    monkeypatch.setattr(package_glue, "build_identity_settings", refuse)

    app = wiring.build_domain_app(DOMAINS["catalog"], startup_tasks=lambda: None)

    assert wiring.add_local_authorizer(app) is False


@pytest.mark.parametrize("domain", sorted(name for name in DOMAINS if name != "identity"))
def test_every_non_identity_domain_builds_without_signing_keys(
    deployed_without_signing_keys: None, domain: str
) -> None:
    """Each deployed domain function starts with an issuer and no signing key ARNs."""
    app = wiring.build_domain_app(DOMAINS[domain], title=DOMAINS[domain].title, startup_tasks=lambda: None)

    assert app.title == DOMAINS[domain].title


def test_a_local_stack_without_an_issuer_adds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local but issuerless mounts no identity routes, so there is no token to verify."""
    monkeypatch.setattr(settings, "APP_ENVIRONMENT", "local")
    monkeypatch.setattr(settings, "environment", "local")
    monkeypatch.setattr(settings, "IDENTITY_ISSUER", "")

    app = wiring.build_domain_app(DOMAINS["catalog"], startup_tasks=lambda: None)

    assert wiring.add_local_authorizer(app) is False
