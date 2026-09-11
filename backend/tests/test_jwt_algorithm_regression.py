"""Every JWT decode in the application names its allowed algorithms.

Guards against an unsigned or attacker-chosen algorithm being accepted.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

_DECODE_PATTERN = re.compile(r"\bjwt\.decode\(")
_ALG_PATTERN = re.compile(r"algorithms\s*=\s*\[")


def test_every_jwt_decode_specifies_algorithms() -> None:
    """No jwt.decode call in the application omits an algorithms argument."""
    offenders: list[tuple[str, int, str]] = []
    for pyfile in APP_DIR.rglob("*.py"):
        lines = pyfile.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _DECODE_PATTERN.search(line):
                window = "\n".join(lines[lineno - 1 : lineno + 2])
                if not _ALG_PATTERN.search(window):
                    offenders.append((str(pyfile.relative_to(APP_DIR)), lineno, line.strip()))
    assert not offenders, "jwt.decode() calls without algorithms=[...] detected (CWE-327 risk):\n" + "\n".join(
        f"  {f}:{ln} -> {code}" for f, ln, code in offenders
    )


def test_the_app_decodes_only_through_decode_access_token() -> None:
    """Every decode goes through the single helper that names the algorithm."""
    offenders: list[str] = []
    for pyfile in APP_DIR.rglob("*.py"):
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import jwt", "from jwt import")):
                offenders.append(f"  {pyfile.relative_to(APP_DIR)}:{lineno} -> {stripped}")
    assert not offenders, (
        "PyJWT is imported directly in app/ again. Decoding belongs in "
        "app.api.dependencies.auth.decode_access_token, which is the one place "
        "the algorithm list is set:\n" + "\n".join(offenders)
    )
