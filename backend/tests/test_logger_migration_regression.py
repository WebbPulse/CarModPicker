"""Fails if an endpoint signature under backend/app reintroduces Depends(get_logger).

Endpoints must use a module level logger instead.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"
DEPENDS_GET_LOGGER_RE = re.compile(r"Depends\(\s*get_logger\s*\)")


def test_no_depends_get_logger_in_app() -> None:
    """Fail if `Depends(get_logger)` is reintroduced anywhere in backend/app/."""
    offenders: list[tuple[str, int]] = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if DEPENDS_GET_LOGGER_RE.search(line):
                offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno))
    assert not offenders, (
        f"Depends(get_logger) found ({len(offenders)} sites) — use a module-level "
        f"`logger = logging.getLogger(__name__)` at module top instead. Offenders: "
        f"{offenders!r}"
    )
