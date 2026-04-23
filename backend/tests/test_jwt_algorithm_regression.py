"""AUTH-04 D-04 regression: every jwt.decode() call MUST specify algorithms=[].

Scoped to backend/app/ per Phase 3/4 precedent (test_session_query_regression.py).
Guards against the CWE-327 / "alg: none" vulnerability class — if a future PR
adds a bare jwt.decode(token, key) call, this test fails at CI.

Companion tests: test_session_query_regression.py, test_pydantic_v1_regression.py,
test_logger_migration_regression.py.
"""

from __future__ import annotations

import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent / "app"

_DECODE_PATTERN = re.compile(r"\bjwt\.decode\(")
_ALG_PATTERN = re.compile(r"algorithms\s*=\s*\[")


def test_every_jwt_decode_specifies_algorithms() -> None:
    offenders: list[tuple[str, int, str]] = []
    for pyfile in APP_DIR.rglob("*.py"):
        lines = pyfile.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _DECODE_PATTERN.search(line):
                # Check same line + next 2 lines (multi-line statements)
                window = "\n".join(lines[lineno - 1:lineno + 2])
                if not _ALG_PATTERN.search(window):
                    offenders.append((str(pyfile.relative_to(APP_DIR)), lineno, line.strip()))
    assert not offenders, (
        "jwt.decode() calls without algorithms=[...] detected (CWE-327 risk):\n"
        + "\n".join(f"  {f}:{ln} -> {code}" for f, ln, code in offenders)
    )
