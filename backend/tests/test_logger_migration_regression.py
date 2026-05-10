"""QUAL-07 regression guard: zero `Depends(get_logger)` in backend/app/ (D-37).

Phase 3 Plan 05 migrated every endpoint signature from the FastAPI-DI logger
pattern:

    async def handler(..., logger: logging.Logger = Depends(get_logger)):
        ...

to the module-level idiom:

    logger = logging.getLogger(__name__)   # at module top, after imports

    async def handler(...):
        logger.info(...)   # resolves to the module-level logger via closure

This test fails if any future PR reintroduces `Depends(get_logger)` on a
function signature in `backend/app/`. Per 03-CONTEXT §D-36, `get_logger` is
still exported from `backend/app/core/logging.py` through Phase 5 — removal
of the export is a separate late-phase task. This test only asserts absence
of the call-site pattern, not absence of the export.
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
