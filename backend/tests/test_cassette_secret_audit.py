"""Fails a committed VCR cassette that still carries a real bearer token, cookie, client secret or provider key.

Passes trivially when no cassette is committed, so the guard is in place before the first one lands.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
CASSETTE_ROOTS = [
    _HERE / "cassettes",
    _HERE / "auth" / "cassettes",
]

BANNED_PATTERNS: dict[str, re.Pattern[str]] = {
    "authorization_bearer": re.compile(r"(?i)authorization:\s*Bearer\s+[A-Za-z0-9._\-]{16,}"),
    "set_cookie_real": re.compile(r"(?i)set-cookie:\s*\S{16,}"),
    "client_secret_real": re.compile(r"client_secret[\"'=:\s]+(?!REDACTED)[A-Za-z0-9._\-]{8,}"),
    "refresh_token_real": re.compile(r"refresh_token[\"'=:\s]+(?!REDACTED)[A-Za-z0-9._\-]{8,}"),
    "google_access_token": re.compile(r"\bya29\.[A-Za-z0-9._\-]{20,}"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
}


def _all_cassettes() -> list[Path]:
    """Collect every committed cassette from the shared and per module layouts."""
    cassettes: list[Path] = []
    for root in CASSETTE_ROOTS:
        if root.is_dir():
            cassettes.extend(root.rglob("*.yaml"))
    return cassettes


@pytest.mark.parametrize("cassette_path", _all_cassettes(), ids=lambda p: str(p.name))
def test_cassette_contains_no_unscrubbed_secrets(cassette_path: Path) -> None:
    """Each committed cassette must NOT match any banned pattern."""
    content = cassette_path.read_text(encoding="utf-8", errors="replace")
    hits: list[str] = []
    for name, pattern in BANNED_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = match.group(0)[:40] + "..."
            hits.append(f"{name}: {snippet}")
    assert not hits, (
        f"Cassette {cassette_path.name} contains un-scrubbed secrets: {hits}. "
        f"Extend vcr_config filter in tests/conftest.py, delete cassette, "
        f"and re-record with `pytest -n 0 --record-mode=once`."
    )


def test_cassette_audit_detection_works_with_leaked_token(tmp_path: Path) -> None:
    """A synthetic cassette carrying a leaked token trips the banned patterns."""
    fake_cassette = tmp_path / "leaked_token_test.yaml"
    fake_cassette.write_text(
        "interactions:\n"
        "- request:\n"
        "    headers:\n"
        "      Authorization:\n"
        "      - 'Bearer ya29.A0ARrdaM_fake_token_that_should_be_caught_12345'\n"
        "  response:\n"
        "    status:\n"
        "      code: 200\n",
        encoding="utf-8",
    )
    content = fake_cassette.read_text(encoding="utf-8")
    hits: list[str] = []
    for name, pattern in BANNED_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = match.group(0)[:40] + "..."
            hits.append(f"{name}: {snippet}")
    assert hits, "Detection failed: leaked token pattern was not caught by BANNED_PATTERNS"
    assert any(
        "google_access_token" in h or "authorization_bearer" in h for h in hits
    ), f"Expected google_access_token or authorization_bearer detection, got: {hits}"


def test_cassette_audit_passes_for_redacted_cassette(tmp_path: Path) -> None:
    """A properly scrubbed cassette does not false positive."""
    scrubbed_cassette = tmp_path / "scrubbed_test.yaml"
    scrubbed_cassette.write_text(
        "interactions:\n"
        "- request:\n"
        "    headers:\n"
        "      Authorization:\n"
        "      - REDACTED\n"
        "      Cookie:\n"
        "      - REDACTED\n"
        "  response:\n"
        "    headers:\n"
        "      Set-Cookie:\n"
        "      - REDACTED\n"
        "    status:\n"
        "      code: 200\n",
        encoding="utf-8",
    )
    content = scrubbed_cassette.read_text(encoding="utf-8")
    hits: list[str] = []
    for name, pattern in BANNED_PATTERNS.items():
        match = pattern.search(content)
        if match:
            snippet = match.group(0)[:40] + "..."
            hits.append(f"{name}: {snippet}")
    assert not hits, f"False-positive: properly scrubbed cassette triggered banned patterns: {hits}"


def test_cassette_audit_redacted_markers_present_when_cassettes_exist() -> None:
    """At least one REDACTED marker appears when cassettes carry scrub eligible fields."""
    cassettes = _all_cassettes()
    if not cassettes:
        pytest.skip("No cassettes committed yet — audit-meta guard trivially OK")

    combined = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in cassettes)

    scrub_eligible_keys = (
        "authorization",
        "cookie",
        "set-cookie",
        "client_secret",
        "refresh_token",
        "api_key",
        "access_token",
    )
    if not any(key in combined.lower() for key in scrub_eligible_keys):
        pytest.skip("No scrub-eligible fields present in any cassette — " "REDACTED marker not required")

    assert "REDACTED" in combined, (
        "No `REDACTED` marker found across committed cassettes — vcr_config "
        "filter_headers / filter_post_data_parameters may not be wired up. "
        "Check tests/conftest.py vcr_config fixture."
    )
