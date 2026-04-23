"""DATA-08 regression: backfill migration shape (idempotent + no-op downgrade).

Phase 4 plan 04-02 task 3. Static file-read tests — no live Postgres required.
A full migration round-trip is reviewer-gated per D-31 / plan 04-06.
"""
from __future__ import annotations

import pathlib
import re


VERSIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _find_backfill_migration() -> pathlib.Path:
    matches = list(VERSIONS_DIR.glob("*backfill_build_logs*legacy*build_lists*.py"))
    assert len(matches) == 1, f"Expected exactly one backfill migration; found {matches}"
    return matches[0]


def test_migration_sql_is_idempotent() -> None:
    """The backfill SQL must use Postgres-native UUID gen, sa.text wrapping,
    and a WHERE NOT EXISTS guard so re-runs insert at most once."""
    body = _find_backfill_migration().read_text()
    assert "gen_random_uuid()" in body, "Must use Postgres-native UUID generation"
    assert "uuid7(" not in body, "Python-side uuid7() must NOT appear (Pitfall 2)"
    assert "WHERE NOT EXISTS" in body, "Missing idempotent guard"
    assert "sa.text(" in body, "Missing sa.text() wrapper"
    assert "INSERT INTO build_logs" in body, "Missing INSERT"
    assert "'Build Log: ' || bl.name" in body, "Title format must match eager-create"


def test_migration_downgrade_is_no_op() -> None:
    """The downgrade() body must be a deliberate no-op with the SAFE-04
    annotation so the Phase 1 DROP-guard recognizes the intent (D-26)."""
    body = _find_backfill_migration().read_text()
    m = re.search(r"def downgrade\(\).*?(?=\ndef |\Z)", body, re.DOTALL)
    assert m, "downgrade() function missing"
    downgrade = m.group(0)
    for tok in ("op.drop_column", "op.drop_table", "op.drop_constraint", "op.alter_column"):
        assert tok not in downgrade, f"downgrade() must be no-op; found {tok}"
    assert "# SAFE: forward-only data backfill; no reversal needed" in downgrade
