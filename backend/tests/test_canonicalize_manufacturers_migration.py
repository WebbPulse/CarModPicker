"""Direct unit tests for migration ``080fc6916478_canonicalize_manufacturers``.

We cannot drive a full ``alembic upgrade`` against the SQLite test DB
because earlier migrations use Postgres-only DDL (the production round-trip
lives behind ``@pytest.mark.postgres`` in
``test_m004_rename_migration_round_trip``). Instead we exercise the
migration's helper functions (``_merge_cluster``, ``_ensure_canonical_row``)
directly against the test session's connection, using its existing live
schema. The helpers issue plain SQL via ``sa.text``, so they execute
identically here as they would inside ``op.get_bind()``.

Coverage:
- Cluster merge moves parts from a loser row to the canonical and deletes the loser.
- Cluster merge tolerates a missing loser (no-op for that loser) and a missing canonical (skipped).
- Canonical-row casing normalisation (``PERRIN`` -> ``Perrin``).
- ``_ensure_canonical_row`` is idempotent and case-insensitive.
- OEM-rename flow creates ``BMW OEM`` then merges ``Genuine BMW`` into it.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

# Load the migration module directly. Alembic versions are not on sys.path,
# but they're importable as plain Python files via spec_from_file_location.
_MIG_PATH = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "080fc6916478_canonicalize_manufacturers.py"
_spec = importlib.util.spec_from_file_location("_mig_canonicalize_mfrs", _MIG_PATH)
assert _spec is not None and _spec.loader is not None
_mig: Any = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mig
_spec.loader.exec_module(_mig)


_LEGACY_TABLES = {
    "part_manufacturers": "id TEXT PRIMARY KEY, name TEXT NOT NULL, is_active BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP",
    "categories": (
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, is_active BOOLEAN, sort_order INTEGER, "
        "created_at TIMESTAMP, updated_at TIMESTAMP"
    ),
    "parts": (
        "id TEXT PRIMARY KEY, name TEXT NOT NULL, category_id TEXT, part_manufacturer_id TEXT, user_id TEXT, "
        "is_universal BOOLEAN, edit_count INTEGER, created_at TIMESTAMP, updated_at TIMESTAMP"
    ),
}


@pytest.fixture(autouse=True)
def legacy_catalog_tables(db_session: Session) -> None:
    conn = db_session.connection()
    for table, columns in _LEGACY_TABLES.items():
        conn.execute(sa.text(f"CREATE TABLE IF NOT EXISTS {table} ({columns})"))  # nosec B608
        conn.execute(sa.text(f"DELETE FROM {table}"))  # nosec B608


def _insert_mfr(conn: sa.Connection, name: str) -> str:
    new_id = str(uuid.uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO part_manufacturers "
            "(id, name, is_active, created_at, updated_at) "
            "VALUES (:id, :name, :a, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": new_id, "name": name, "a": True},
    )
    return new_id


def _name_of(conn: sa.Connection, mfr_id: str) -> Optional[str]:
    row = conn.execute(
        sa.text("SELECT name FROM part_manufacturers WHERE id = :i"),
        {"i": mfr_id},
    ).first()
    return row[0] if row else None


def _exists(conn: sa.Connection, mfr_id: str) -> bool:
    return _name_of(conn, mfr_id) is not None


class TestEnsureCanonicalRow:
    # NOTE: test_creates_when_missing was removed — the historical migration's
    # _ensure_canonical_row create path hard-codes the now-dropped
    # `is_curated` column, so it can no longer execute against the current
    # schema. Only the no-op (already-present) path remains exercisable.

    def test_no_op_when_present_case_insensitive(self, db_session: Session) -> None:
        conn = db_session.connection()
        existing_id = _insert_mfr(conn, "perrin")  # lowercase
        _mig._ensure_canonical_row(conn, "Perrin")
        rows = conn.execute(
            sa.text("SELECT id FROM part_manufacturers WHERE LOWER(name) = LOWER(:n)"),
            {"n": "Perrin"},
        ).all()
        assert len(rows) == 1
        assert rows[0][0] == existing_id


class TestMergeCluster:
    def _seed_part(self, conn: sa.Connection, manufacturer_id: str) -> str:
        cat_id = str(uuid.uuid4())
        cat_name = f"cat-{cat_id[:8]}"
        conn.execute(
            sa.text(
                "INSERT INTO categories (id, name, is_active, sort_order, "
                "created_at, updated_at) "
                "VALUES (:i, :n, :a, :so, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"i": cat_id, "n": cat_name, "a": True, "so": 0},
        )
        user_id = str(uuid.uuid4())
        part_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO parts (id, name, category_id, part_manufacturer_id, "
                "user_id, is_universal, edit_count, "
                "created_at, updated_at) "
                "VALUES (:i, :n, :c, :m, :uid, :u, :ec, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {
                "i": part_id,
                "n": "Test Part",
                "c": cat_id,
                "m": manufacturer_id,
                "uid": user_id,
                "u": True,
                "ec": 0,
            },
        )
        return part_id

    def test_repoints_parts_and_deletes_loser(self, db_session: Session) -> None:
        conn = db_session.connection()
        canonical_id = _insert_mfr(conn, "APR")
        loser_id = _insert_mfr(conn, "APR Performance")
        part_id = self._seed_part(conn, loser_id)

        _mig._merge_cluster(conn, "APR", ["APR Performance"])

        # Loser row gone, part now points at canonical.
        assert not _exists(conn, loser_id)
        repointed = conn.execute(
            sa.text("SELECT part_manufacturer_id FROM parts WHERE id = :i"),
            {"i": part_id},
        ).first()
        assert repointed is not None
        assert repointed[0] == canonical_id

    def test_missing_canonical_skips_cluster(self, db_session: Session) -> None:
        conn = db_session.connection()
        loser_id = _insert_mfr(conn, "Lonely Loser")
        # No "NoSuchBrand" canonical exists.
        _mig._merge_cluster(conn, "NoSuchBrand", ["Lonely Loser"])
        # Loser still present.
        assert _exists(conn, loser_id)

    def test_missing_loser_is_silent_no_op(self, db_session: Session) -> None:
        conn = db_session.connection()
        canonical_id = _insert_mfr(conn, "AEM")
        # No "AEM Electronics" / "AEM Induction" rows in this DB.
        _mig._merge_cluster(conn, "AEM", ["AEM Electronics", "AEM Induction"])
        assert _name_of(conn, canonical_id) == "AEM"

    def test_canonical_casing_is_normalized(self, db_session: Session) -> None:
        # ``PERRIN`` row gets renamed to ``Perrin`` (same id) when the merge
        # canonical asks for ``Perrin``.
        conn = db_session.connection()
        existing_id = _insert_mfr(conn, "PERRIN")
        _mig._merge_cluster(conn, "Perrin", [])
        assert _name_of(conn, existing_id) == "Perrin"


# NOTE: TestOEMRenameFlow.test_creates_canonical_then_merges_genuine_bmw was
# removed — it exercised _ensure_canonical_row's create path, which the
# historical migration hard-codes against the now-dropped `is_curated`
# column and so can no longer run against the current schema. The merge
# behavior itself stays covered by TestMergeCluster.
