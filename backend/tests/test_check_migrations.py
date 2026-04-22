"""SAFE-04 unit tests for backend/scripts/check_migrations.py.

Covers:
- PASS: destructive op with same-line SAFE annotation
- PASS: destructive op with preceding-line SAFE annotation
- FAIL: destructive op with no annotation
- FAIL: destructive op with annotation 2 lines above (not immediately preceding)
- FAIL defense (T-03-02): "SAFE:" token embedded in a docstring/text above
  the destructive op does NOT satisfy the annotation requirement
- DoS defense (T-03-01): script completes in < 1 second on a pathological
  input (many destructive ops in one file)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# backend/scripts/ is not on sys.path by default; add it at collection time.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_migrations import check_file  # noqa: E402  # pyright: ignore[reportMissingImports]


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "001_test_migration.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_pass_same_line_annotation(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'op.drop_column("users", "legacy_avatar_path")  # SAFE: column is empty on prod; see ADR-007\n',
    )
    assert check_file(path) == []


def test_pass_preceding_line_annotation(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "# SAFE: table has zero rows on prod (verified via COUNT(*) 2026-04-18)\n"
        'op.drop_table("abandoned_experiments")\n',
    )
    assert check_file(path) == []


def test_fail_no_annotation(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'op.drop_constraint("fk_parts_canonical", "parts", type_="foreignkey")\n',
    )
    violations = check_file(path)
    assert len(violations) == 1
    assert violations[0][0] == 1
    assert "drop_constraint" in violations[0][1]


def test_fail_annotation_two_lines_above(tmp_path: Path) -> None:
    """Annotation must be IMMEDIATELY preceding — a 1-line gap is a miss."""
    path = _write(
        tmp_path,
        "# SAFE: this is the destructive sweep\n" "some_other_line = 1\n" 'op.drop_column("users", "legacy_field")\n',
    )
    violations = check_file(path)
    assert len(violations) == 1
    assert violations[0][0] == 3


def test_fail_safe_in_docstring_does_not_count(tmp_path: Path) -> None:
    """T-03-02 defense: 'SAFE:' inside a docstring or non-comment line
    does not satisfy the annotation requirement."""
    path = _write(
        tmp_path,
        '"""This migration SAFE: does a thing."""\n' 'op.drop_table("abandoned")\n',
    )
    violations = check_file(path)
    assert len(violations) == 1
    assert violations[0][0] == 2


def test_pass_drop_column_with_inline_comment_and_trailing_whitespace(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'op.drop_column("t", "c")   #   SAFE:   reason text here   \n',
    )
    assert check_file(path) == []


def test_multiple_violations_collected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        'op.drop_column("t", "a")\n' 'op.drop_table("old")\n' 'op.drop_constraint("fk", "t", type_="foreignkey")\n',
    )
    violations = check_file(path)
    assert len(violations) == 3
    assert [v[0] for v in violations] == [1, 2, 3]


def test_non_destructive_ops_ignored(tmp_path: Path) -> None:
    """op.add_column, op.create_table etc. are NOT destructive and need no annotation."""
    path = _write(
        tmp_path,
        'op.add_column("t", sa.Column("new", sa.String()))\n'
        'op.create_table("new_t", sa.Column("id", sa.Integer()))\n'
        'op.create_foreign_key("fk_name", "t", "u", ["c"], ["id"])\n',
    )
    assert check_file(path) == []


def test_redos_safe_on_pathological_input(tmp_path: Path) -> None:
    """T-03-01 defense: script handles a large pathological input in < 1s."""
    body_lines: list[str] = []
    for i in range(2000):
        body_lines.append("# SAFE: batch cleanup reason " + str(i))
        body_lines.append(f'op.drop_column("t{i}", "c{i}")')
    path = _write(tmp_path, "\n".join(body_lines) + "\n")

    start = time.perf_counter()
    violations = check_file(path)
    elapsed = time.perf_counter() - start

    assert violations == []
    assert elapsed < 1.0, f"check_file took {elapsed:.3f}s on 4000-line input — ReDoS risk"


def test_pass_drop_constraint_none_with_preceding_safe(tmp_path: Path) -> None:
    """Legacy-style drop_constraint(None, ...) with preceding SAFE annotation passes."""
    path = _write(
        tmp_path,
        "# SAFE: legacy drop_constraint(None) superseded by forward-only repair in aa583927d86a — see SAFE-08\n"
        'op.drop_constraint(None, "parts", type_="foreignkey")\n',
    )
    assert check_file(path) == []


def test_pass_drop_constraint_named_with_preceding_safe(tmp_path: Path) -> None:
    """Named drop_constraint with preceding SAFE annotation passes (repair migration shape)."""
    path = _write(
        tmp_path,
        "# SAFE: repair invalid drop_constraint(None) — see SAFE-08\n"
        'op.drop_constraint("parts_canonical_part_id_fkey", "parts", type_="foreignkey")\n',
    )
    assert check_file(path) == []


def test_pass_multiline_drop_constraint_preceding_safe(tmp_path: Path) -> None:
    """Multi-line drop_constraint where the SAFE annotation is on the preceding line passes."""
    path = _write(
        tmp_path,
        "# SAFE: repair invalid drop_constraint(None) — see SAFE-08\n"
        "op.drop_constraint(\n"
        '    "build_list_parts_build_list_phase_id_fkey",\n'
        '    "build_list_parts",\n'
        '    type_="foreignkey",\n'
        ")\n",
    )
    assert check_file(path) == []
