"""Tests that the smoke script's legacy list never claims a package-owned path.

`LEGACY_OPERATIONS` exists to prove the deleted legacy `/api/auth` routes stay
deleted. The shared identity package serves its own routes under that same
prefix, so a package-owned path listed as legacy turns normal package behaviour
into a smoke failure, which is exactly what `POST /api/auth/logout` did. The
owned set is read from the package's route constants rather than restated here,
so a path the package adds later is covered without touching this file.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from identity_smoke import LEGACY_OPERATIONS, probes_for

IDENTITY_PREFIX = "/api/auth"


def owned_paths() -> set[str]:
    """Every path the identity package serves, as a full `/api/auth` path.

    Read from the `_PATH` constants of the three modules that register routes,
    which is where the routers themselves get them. `verification.py` is left
    out deliberately: its `RESET_LINK_PATH` and `VERIFY_LINK_PATH` are frontend
    link targets baked into emails, not API routes, and one of them collides
    with the genuinely legacy `POST /api/auth/reset-password`.
    """
    pytest.importorskip("webbpulse.identity")
    from webbpulse.identity import oauth_routes, passkey_routes, router

    paths: set[str] = set()
    for module in (router, oauth_routes, passkey_routes):
        for name in dir(module):
            if not name.endswith("_PATH"):
                continue
            value = getattr(module, name)
            if isinstance(value, str) and value.startswith("/"):
                paths.add(f"{IDENTITY_PREFIX}{value}")
    return paths


def concrete(path: str) -> str:
    """Fill a templated path segment with the value the smoke script would send."""
    return path.replace("{provider}", "google")


def test_no_legacy_entry_collides_with_a_package_owned_path():
    owned = owned_paths()
    concrete_owned = {concrete(path) for path in owned}
    collisions = sorted(
        f"{method} {path}"
        for method, path in LEGACY_OPERATIONS
        if path in owned or path in concrete_owned
    )
    assert collisions == [], (
        "these legacy expectations name paths the identity package owns, so the "
        f"package's own answer reads as a smoke failure: {collisions}"
    )


def test_logout_is_not_expected_to_be_absent():
    assert ("POST", f"{IDENTITY_PREFIX}/logout") not in LEGACY_OPERATIONS


def test_logout_is_covered_by_a_positive_probe():
    logout = [
        probe
        for probe in probes_for("smoke-user")
        if probe.path == f"{IDENTITY_PREFIX}/logout"
    ]
    assert len(logout) == 1
    probe = logout[0]
    assert probe.method == "POST"
    assert probe.ok == (200,)
    assert probe.expect_json == {"signed_out": True}


def test_every_legacy_path_sits_under_the_identity_prefix():
    assert all(path.startswith(IDENTITY_PREFIX) for _, path in LEGACY_OPERATIONS)
