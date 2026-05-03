"""canonicalize_manufacturers

Revision ID: 080fc6916478
Revises: f99b709f371a
Create Date: 2026-05-02 22:11:20.435726

Tier-1 data-quality fix: collapse duplicate manufacturer rows (brand
sub-divisions, casing/spacing variants, corporate-suffix variants), rename
``Genuine <Make>`` / ``OEM <Make>`` rows to the canonical ``<Make> OEM``
form, drop the sentinel ``Unknown`` / ``OEM`` / ``Aftermarket`` parents,
and clean up a stray Holley duplicate.

Idempotent on every step (each UPDATE/DELETE is gated by an EXISTS check or
no-ops if the loser row is already gone). Uses plain SQL parameterized via
:bindings so it runs identically on PostgreSQL and the SQLite in-memory
test DB.

The DB column ``parts.part_manufacturer_id`` is already nullable; the
``Unknown``/``OEM``/``Aftermarket`` cleanup just sets parts pointing at
those sentinel rows to NULL and then deletes the rows.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "080fc6916478"
down_revision: Union[str, None] = "f99b709f371a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Cluster merges: parts pointing at any of ``losers`` get repointed to the
# row whose name == ``canonical``. Loser rows are then deleted.
# Names are matched case-insensitively (LOWER(name) = LOWER(:name)) because
# the unique index on curated rows is on ``LOWER(name)``.
_CLUSTERS: list[tuple[str, list[str]]] = [
    ("APR", ["APR Performance"]),
    ("COBB Tuning", ["COBB"]),
    ("PRL Motorsports", ["PRL"]),
    ("Katech", ["Katech Engineering", "Katech Inc.", "Katech Inc"]),
    ("AMS Performance", ["AMS"]),
    ("AWE Tuning", ["AWE"]),
    ("ARMYTRIX", ["ARMYTRIX USA"]),
    ("A'PEX-i", ["APEXi", "Apex-i", "Apexi"]),
    ("Studio RSR", ["StudioRSR"]),
    ("CSF", ["CSF Inc.", "CSF Inc"]),
    ("Vibrant", ["Vibrant Performance"]),
    ("BorgWarner", ["Borg Warner"]),
    ("Burger Motorsport", ["Burger", "Burger Motorsports"]),
    ("AEM", ["AEM Electronics", "AEM Induction"]),
    ("Hawk Performance", ["Hawk"]),
    ("McLeod Racing", ["Mcleod"]),
    ("Corsa Performance", ["Corsa"]),
    ("Perrin", ["PERRIN", "Perrin Performance"]),
    ("SuperPro", ["Super Pro"]),
    ("Titan 7", ["Titan7", "Titan 7 LLC"]),
    ("DeatschWerks", ["Deatsch Werks"]),
    ("K&N", ["KN"]),
    ("Techna-Fit", ["TechnaFit"]),
    ("StopTech", ["Stop Tech"]),
    ("Power Stop", ["PowerStop"]),
    ("Redline", ["Red Line", "Redline Tuning"]),
    # Holley parens-suffix duplicate.
    ("Holley", ["Holley (bought Advanced Engine Management)"]),
]

# OEM-style renames: ``Genuine <Make>`` / ``OEM <Make>`` / ``<Make> Genuine
# Parts`` => ``<Make> OEM``. The canonical row is created if missing
# (matches the existing ``Porsche OEM`` row), then merged.
_OEM_RENAMES: list[tuple[str, list[str]]] = [
    ("BMW OEM", ["Genuine BMW", "Genuine BMW Motorsport"]),
    ("Nissan OEM", ["OEM Nissan"]),
    ("Ford OEM", ["Ford Genuine Parts"]),
]

# Sentinel rows: parts pointing at these get part_manufacturer_id set to NULL,
# then the rows themselves are deleted.
_SENTINEL_ROWS: list[str] = ["Unknown", "OEM", "Aftermarket"]


def _merge_cluster(conn: sa.engine.Connection, canonical: str, losers: list[str]) -> None:
    """Repoint parts.part_manufacturer_id from each loser to canonical, then drop the loser row.

    No-ops cleanly when the canonical row is missing (skips the cluster) or
    when a loser row is already gone (the UPDATE simply matches zero rows).

    Also normalizes the canonical row's name to the exact requested casing so
    rows discovered by case-insensitive match (e.g. ``PERRIN``) end up named
    ``Perrin`` after the migration.
    """
    canonical_id_row = conn.execute(
        sa.text("SELECT id, name FROM part_manufacturers " "WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
        {"name": canonical},
    ).first()
    if canonical_id_row is None:
        return
    canonical_id = canonical_id_row[0]
    if canonical_id_row[1] != canonical:
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
    """Create a curated manufacturer row if no case-insensitive match exists.

    UUID is minted in Python so the SQL is identical across PostgreSQL and
    SQLite (the test backend has no ``gen_random_uuid()``).
    """
    existing = conn.execute(
        sa.text("SELECT id FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
        {"name": name},
    ).first()
    if existing is not None:
        return
    new_id = str(uuid.uuid4())
    conn.execute(
        sa.text(
            "INSERT INTO part_manufacturers "
            "(id, name, is_active, is_curated, created_at, updated_at) "
            "VALUES (:id, :name, :active, :curated, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": new_id, "name": name, "active": True, "curated": True},
    )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # 1) Cluster merges (brand sub-divisions, casing/spacing variants).
    #    Create the canonical row first if missing (e.g. ``Katech`` exists
    #    in the audit only as ``Katech Engineering`` / ``Katech Inc.``).
    for canonical, losers in _CLUSTERS:
        _ensure_canonical_row(conn, canonical)
        _merge_cluster(conn, canonical, losers)

    # 2) OEM-style renames. Create the canonical ``<Make> OEM`` row first
    #    so the merge step has something to repoint into.
    for canonical, losers in _OEM_RENAMES:
        _ensure_canonical_row(conn, canonical)
        _merge_cluster(conn, canonical, losers)

    # 3) Sentinel cleanup: NULL out parts pointing at Unknown/OEM/Aftermarket,
    #    then delete the rows. ``parts.part_manufacturer_id`` is nullable.
    for sentinel in _SENTINEL_ROWS:
        row = conn.execute(
            sa.text("SELECT id FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
            {"name": sentinel},
        ).first()
        if row is None:
            continue
        sentinel_id = row[0]
        conn.execute(
            sa.text("UPDATE parts SET part_manufacturer_id = NULL WHERE part_manufacturer_id = :sid"),
            {"sid": sentinel_id},
        )
        conn.execute(
            sa.text("DELETE FROM part_manufacturers WHERE id = :sid"),
            {"sid": sentinel_id},
        )


def downgrade() -> None:
    """Downgrade schema.

    Cluster-merge / sentinel-deletion is a destructive consolidation: loser
    rows are dropped entirely, so a faithful reverse would require
    re-creating them with new UUIDs and re-attributing parts using stored
    provenance, which we don't keep. No-op is the standard posture for
    other data-cleanup migrations in this repo.
    """
    pass
