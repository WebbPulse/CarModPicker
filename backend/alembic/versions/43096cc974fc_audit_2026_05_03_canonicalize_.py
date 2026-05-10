"""audit_2026_05_03_canonicalize_manufacturers

Revision ID: 43096cc974fc
Revises: 55c6af0ee3e2
Create Date: 2026-05-03 15:43:13.923312

Second canonicalization pass after the 2026-05-03 data audit. Reverses some
prior canonical picks and adds new clusters discovered by the audit's
manufacturer agent. The prior migration ``080fc6916478`` preferred long forms
(``AMS Performance``, ``AWE Tuning``, ``Hawk Performance``, ``Burger
Motorsport``); per audit decision (memory item 4: brand sub-divisions collapse
to bare brand) those flip to ``AMS`` / ``AWE`` / ``Hawk`` / ``Burger
Motorsports``. Also folds in: AEM Induction Systems → AEM, Injen Technology →
Injen, KW + KW Suspension → KW Suspensions, Genuine BMW Motorsport → BMW OEM,
Vibrant Performance → Vibrant (re-codified — same direction as the prior
migration, but the prior migration's loser-row would be re-created if a
contributor re-imports it from upstream data).

Idempotent: each merge no-ops when the canonical row is missing or the loser
row is already gone. Safe to run on a fresh DB (after ``080fc6916478``) and
on the live DB (where the audit agent already applied these in-place).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '43096cc974fc'
down_revision: Union[str, None] = '55c6af0ee3e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (canonical, [losers]) — losers' parts get repointed to canonical, then losers deleted.
_CLUSTERS: list[tuple[str, list[str]]] = [
    ("AMS", ["AMS Performance"]),
    ("AWE", ["AWE Tuning"]),
    ("Hawk", ["Hawk Performance"]),
    ("Injen", ["Injen Technology"]),
    ("Vibrant", ["Vibrant Performance"]),
    ("Perrin", ["Perrin Performance", "PERRIN"]),
    ("AEM", ["AEM Electronics", "AEM Induction", "AEM Induction Systems"]),
    ("Burger Motorsports", ["Burger", "Burger Motorsport", "BM"]),
    ("KW Suspensions", ["KW", "KW Suspension"]),
    ("Katech", ["Katech Engineering"]),
    ("Lingenfelter", ["Lingenfelter Performance Engineering"]),
    ("ARMYTRIX", ["ARMYTRIX USA"]),
    ("APR", ["APR Performance"]),
    ("COBB Tuning", ["COBB"]),
    ("PRL Motorsports", ["PRL"]),
    ("TiAL", ["TiALSport"]),
    ("American Racing Headers", ["American Racing Headers (ARH)", "American"]),
]

# OEM-style renames: ensure canonical exists then merge into it.
_OEM_RENAMES: list[tuple[str, list[str]]] = [
    ("BMW OEM", ["Genuine BMW", "Genuine BMW Motorsport"]),
    ("Nissan OEM", ["OEM Nissan"]),
    ("Ford OEM", ["Ford Genuine Parts"]),
]


def _merge_cluster(conn: sa.engine.Connection, canonical: str, losers: list[str]) -> None:
    canonical_row = conn.execute(
        sa.text("SELECT id, name FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
        {"name": canonical},
    ).first()
    if canonical_row is None:
        return
    canonical_id = canonical_row[0]
    if canonical_row[1] != canonical:
        conn.execute(
            sa.text("UPDATE part_manufacturers SET name = :name WHERE id = :id"),
            {"name": canonical, "id": canonical_id},
        )
    for loser in losers:
        loser_row = conn.execute(
            sa.text("SELECT id FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
            {"name": loser},
        ).first()
        if loser_row is None:
            continue
        loser_id = loser_row[0]
        if loser_id == canonical_id:
            continue
        conn.execute(
            sa.text("UPDATE parts SET part_manufacturer_id = :cid WHERE part_manufacturer_id = :lid"),
            {"cid": canonical_id, "lid": loser_id},
        )
        conn.execute(
            sa.text("DELETE FROM part_manufacturers WHERE id = :lid"),
            {"lid": loser_id},
        )


def _ensure_canonical_row(conn: sa.engine.Connection, name: str) -> None:
    import uuid
    existing = conn.execute(
        sa.text("SELECT 1 FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
        {"name": name},
    ).first()
    if existing is not None:
        return
    conn.execute(
        sa.text(
            "INSERT INTO part_manufacturers (id, name, is_active, is_curated, created_at, updated_at) "
            "VALUES (:id, :name, true, true, now(), now())"
        ),
        {"id": str(uuid.uuid4()), "name": name},
    )


def upgrade() -> None:
    conn = op.get_bind()
    for canonical, losers in _CLUSTERS:
        _merge_cluster(conn, canonical, losers)
    for canonical, losers in _OEM_RENAMES:
        _ensure_canonical_row(conn, canonical)
        _merge_cluster(conn, canonical, losers)


def downgrade() -> None:
    """Downgrade is intentionally a no-op.

    Manufacturer merges are destructive (the loser row's UUID is gone after
    its parts are repointed). Recreating the loser rows would not restore
    the original UUIDs, and the parts that were repointed cannot be
    re-distinguished from those that were originally on the canonical row.
    Per project convention for canonicalization migrations, downgrade is a
    no-op rather than a partial restore.
    """
