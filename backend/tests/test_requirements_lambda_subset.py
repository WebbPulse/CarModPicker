"""Pins requirements-lambda.txt as a strict subset of requirements.txt with character identical specifiers.

A runtime dependency added to only the full file passes every check and then fails at import inside the deployed image.
"""

from __future__ import annotations

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
FULL = BACKEND_DIR / "requirements.txt"
LAMBDA = BACKEND_DIR / "requirements-lambda.txt"


def _parse(path: Path) -> dict[str, str]:
    """Map each PEP 503 normalised distribution name to the line that declared it."""
    requirements: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = line
        for separator in ("[", "=", ">", "<", "!", "~", ";"):
            name = name.split(separator, 1)[0]
        normalized = name.strip().lower().replace("_", "-")
        if normalized:
            requirements[normalized] = line
    return requirements


def test_lambda_requirements_are_a_subset_of_the_full_set() -> None:
    """Nothing may be pinned for the runtime that CI never installs."""
    full = _parse(FULL)
    lambda_only = sorted(set(_parse(LAMBDA)) - set(full))
    assert not lambda_only, (
        "requirements-lambda.txt pins packages absent from requirements.txt, so "
        "the test suite never exercises them: " + ", ".join(lambda_only)
    )


def test_shared_requirements_pin_identical_versions() -> None:
    """A package in both files carries the same whole line, so a dropped extra is caught alongside a version drift."""
    full = _parse(FULL)
    mismatched = {
        name: (spec, full[name]) for name, spec in _parse(LAMBDA).items() if name in full and spec != full[name]
    }
    assert not mismatched, "\n".join(
        f"{name}: requirements-lambda.txt has {lambda_spec!r}, requirements.txt has {full_spec!r}"
        for name, (lambda_spec, full_spec) in sorted(mismatched.items())
    )


def test_the_shared_package_is_installed_by_the_runtime_file() -> None:
    """webbpulse reaches the image, since the application imports it at module scope and its absence is a cold start crash."""
    assert "webbpulse" in _parse(LAMBDA)
