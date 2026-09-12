"""Fails if a module under backend/app reintroduces the deprecated @app.on_event.

Modules must use a lifespan context manager instead.
"""

from __future__ import annotations

import re
from pathlib import Path

BACKEND_APP = Path(__file__).resolve().parent.parent / "app"
ON_EVENT_RE = re.compile(r"@\w+\.on_event\(")


def test_no_app_on_event_in_app() -> None:
    """Fail if any `@<anything>.on_event(` is reintroduced in backend/app/."""
    offenders: list[tuple[str, int]] = []
    for pyfile in BACKEND_APP.rglob("*.py"):
        for lineno, line in enumerate(pyfile.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if ON_EVENT_RE.search(line):
                offenders.append((str(pyfile.relative_to(BACKEND_APP)), lineno))
    assert not offenders, (
        f"@app.on_event found — use the lifespan context manager instead (see backend/app/main.py): {offenders!r}"
    )
