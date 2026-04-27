"""QUAL-03 regression guard: no `@app.on_event(...)` — use lifespan context.

FastAPI's `@app.on_event("startup"/"shutdown")` decorators are deprecated in
favour of the `lifespan` context manager (see `backend/app/main.py::70`).
This test fails if any file under `backend/app/` reintroduces `@<app>.on_event(`.

Tree baseline (03-RESEARCH §D-30, verified 2026-04-22): zero `@app.on_event(`
occurrences; the canonical pattern is the `lifespan` async context manager
registered on the `FastAPI(...)` constructor.
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
        "@app.on_event found — use the lifespan context manager instead " f"(see backend/app/main.py): {offenders!r}"
    )
