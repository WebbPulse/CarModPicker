"""QUAL-02 regression guard: no Pydantic v1 anti-patterns reintroduced.

Two complementary checks:

1. `test_no_forbidden_patterns_in_app`: a grep scan across `backend/app/**/*.py`
   that fails if any of the Pydantic v1 anti-patterns are found — `@validator`,
   `@root_validator`, `class Config:`, `.parse_obj(`, and (with an allowlist
   for known false-positive `.dict()` callers) `.dict()`.

2. `test_no_pydantic_v1_deprecation_warnings_on_roundtrip`: a schema round-trip
   that runs inside `warnings.catch_warnings()` with
   `simplefilter("error", pydantic.PydanticDeprecatedSince20)`. This is the
   ONLY reliable way to catch v1 deprecations in this repo — per Pitfall QU-01,
   `backend/pytest.ini` has `--disable-warnings`, which suppresses warnings
   globally and causes CLI `-W error` filters to have no effect.

Tree baseline (03-RESEARCH §D-30, verified 2026-04-22): zero Pydantic v1
patterns, zero v1 deprecation warnings emitted on UserRead round-trip. This
test stays green as long as no future PR reintroduces either.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from uuid import uuid4

import pydantic

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"

FORBIDDEN_PATTERNS = [
    (re.compile(r"@validator\b"), "Pydantic v1 @validator — use @field_validator"),
    (re.compile(r"@root_validator\b"), "Pydantic v1 @root_validator — use @model_validator"),
    (re.compile(r"^\s*class\s+Config\s*:"), "Pydantic v1 class Config — use model_config = ConfigDict(...)"),
    (re.compile(r"\.parse_obj\("), "Pydantic v1 .parse_obj() — use .model_validate()"),
]
# Matches any `foo.dict()` call; has false positives on SQLAlchemy row._asdict-adjacent
# code and on stdlib `dict`-subclass callers. Real Pydantic v1 `.dict()` usage on
# BaseModel instances is the target.
DICT_PATTERN = re.compile(r"\b\w+\.dict\(\)")
# Relative paths (under backend/app/) with legitimate non-Pydantic `.dict()` callers.
# Populate with a rationale comment only after confirming the call is NOT on a
# pydantic.BaseModel instance.
DICT_ALLOWLIST: set[str] = set()


def test_no_forbidden_patterns_in_app() -> None:
    """Fail if any Pydantic v1 anti-pattern lives in backend/app/**/*.py."""
    offenders: list[tuple[str, int, str]] = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        text = pyfile.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            # Skip pure-comment lines (but keep inline comments — a forbidden
            # pattern prefixed by code still counts).
            if line.lstrip().startswith("#"):
                continue
            for pat, label in FORBIDDEN_PATTERNS:
                if pat.search(line):
                    offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno, label))
            if DICT_PATTERN.search(line):
                rel = str(pyfile.relative_to(BACKEND_APP))
                if rel not in DICT_ALLOWLIST:
                    offenders.append(
                        (
                            rel,
                            lineno,
                            ".dict() — use .model_dump() (or add to DICT_ALLOWLIST with rationale)",
                        )
                    )
    assert not offenders, "Forbidden Pydantic v1 patterns found:\n" + "\n".join(
        f"  {f}:{n}: {label}" for f, n, label in offenders
    )


def test_no_pydantic_v1_deprecation_warnings_on_roundtrip() -> None:
    """Schema round-trip under catch_warnings — Pitfall QU-01.

    `backend/pytest.ini` has `--disable-warnings`, which means pytest CLI
    `-W error::DeprecationWarning` flags are a no-op. This test installs the
    deprecation-as-error filter locally via `warnings.catch_warnings()` so a
    v1 deprecation on the round-trip becomes a hard failure here.
    """
    from app.api.schemas.user import UserRead

    # UserRead's required fields (verified via UserRead.model_fields):
    # id (UUID), username, email (EmailStr), disabled, email_verified,
    # is_superuser, is_admin, subscription_tier, subscription_status.
    user_payload = {
        "id": uuid4(),
        "username": "regression_test_user",
        "email": "regression_test@example.com",
        "disabled": False,
        "email_verified": True,
        "is_superuser": False,
        "is_admin": False,
        "subscription_tier": "free",
        "subscription_status": "active",
    }

    with warnings.catch_warnings():
        warnings.simplefilter("error", pydantic.PydanticDeprecatedSince20)
        user = UserRead.model_validate(user_payload)
        dumped = user.model_dump()
        reloaded = UserRead.model_validate(dumped)
        assert reloaded == user
