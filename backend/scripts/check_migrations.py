#!/usr/bin/env python3
"""
SAFE-04: Migration DROP guard.

Fails CI if any file in `backend/alembic/versions/*.py` contains
`op.drop_column`, `op.drop_table`, or `op.drop_constraint` without a
`# SAFE: <reason>` annotation on the SAME line or the IMMEDIATELY PRECEDING
line.

Per D-07 this guard runs at the merge gate (CI), not on developer machines.
Per D-09 the annotation format is exactly `# SAFE: <human-readable reason>`.
Per D-10 `backend/alembic/versions/*.py` is the ONLY scan path.

Exit codes:
    0 — no violations
    1 — one or more violations (printed with filename + line number)
    2 — migrations directory not found (setup error)

Usage:
    python backend/scripts/check_migrations.py

Tests:
    pytest -n auto backend/tests/test_check_migrations.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# <repo>/backend/scripts/check_migrations.py -> parents[2] = <repo>
REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "backend" / "alembic" / "versions"

# Matches `op.drop_column(`, `op.drop_table(`, `op.drop_constraint(`.
# The `\bop\.` prefix avoids false positives on variable names or function
# defs. Bounded quantifiers only (ReDoS-safe — see T-03-01).
DESTRUCTIVE_OP_RE = re.compile(r"\bop\.(drop_column|drop_table|drop_constraint)\s*\(")

# Preceding-line annotation: `# SAFE:` anchored to start-of-line (leading
# whitespace allowed; a docstring body line containing "SAFE:" does NOT
# match — T-03-02 defense).
SAFE_ANNOTATION_RE = re.compile(r"^\s*#\s*SAFE:\s*\S")

# Same-line (inline-comment) annotation: the `#` can appear after code.
INLINE_SAFE_RE = re.compile(r"#\s*SAFE:\s*\S")


def check_file(path: Path) -> list[tuple[int, str]]:
    """Return list of (1-indexed line number, offending line text) for violations."""
    lines = path.read_text(encoding="utf-8").splitlines()
    violations: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if not DESTRUCTIVE_OP_RE.search(line):
            continue
        # Same-line inline annotation?
        if INLINE_SAFE_RE.search(line):
            continue
        # Immediately-preceding-line annotation?
        if idx > 0 and SAFE_ANNOTATION_RE.search(lines[idx - 1]):
            continue
        violations.append((idx + 1, line.rstrip()))
    return violations


def main() -> int:
    if not MIGRATIONS_DIR.is_dir():
        print(f"ERROR: migrations dir not found: {MIGRATIONS_DIR}", file=sys.stderr)
        return 2

    migration_files = sorted(MIGRATIONS_DIR.glob("*.py"))
    failures: list[tuple[Path, int, str]] = []
    for py in migration_files:
        for lineno, text in check_file(py):
            failures.append((py, lineno, text))

    if not failures:
        print(f"check_migrations: OK ({len(migration_files)} files scanned)")
        return 0

    print("check_migrations: FAILURES")
    print()
    for path, lineno, text in failures:
        rel = path.relative_to(REPO_ROOT)
        print(f"  {rel}:{lineno}")
        print(f"    {text}")
        print("    --> Add `# SAFE: <reason>` on this line or the line above.")
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
