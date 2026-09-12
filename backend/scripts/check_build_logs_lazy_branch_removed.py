#!/usr/bin/env python
"""Phase 4 DATA-08 (plan 04-02 task 2) — verify the two lazy auto-create branches
have been removed from backend/app/api/endpoints/build_logs.py.

Replaces an inline `python -c "..."` shell invocation whose nested quote escaping
was fragile under the plan's XML-embedded <automated> block (WARN 11).
"""

from __future__ import annotations

import pathlib
import sys


def main() -> int:
    """Check the build_logs endpoint source and return 0 when every check passes.

    Runs from the repo root or from `backend/`; both paths are tried.
    """
    path = pathlib.Path("backend/app/api/endpoints/build_logs.py")
    if not path.exists():
        path = pathlib.Path("app/api/endpoints/build_logs.py")
    src = path.read_text(encoding="utf-8")

    checks: list[tuple[str, bool]] = []

    checks.append(("DBBuildLog( construction absent", "DBBuildLog(" not in src))

    checks.append(
        (
            "auto-create log message absent",
            "Auto-created build log thread" not in src,
        )
    )

    checks.append(
        (
            "orphan error log present",
            "DATA-08 invariant violated" in src,
        )
    )

    raise_count = src.count('''raise_not_found("build log"''') + src.count("""raise_not_found('build log'""")
    checks.append(
        (
            f"raise_not_found count >= 2 (got {raise_count})",
            raise_count >= 2,
        )
    )

    failed: list[str] = [label for label, ok in checks if not ok]
    if failed:
        print("FAIL: " + "; ".join(failed), file=sys.stderr)
        return 1
    print("Lazy-branch deletion OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
