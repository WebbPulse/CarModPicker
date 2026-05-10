"""audit_2026_05_03_canonicalize_manufacturers_pass3

Revision ID: 4edb71f895f0
Revises: 43096cc974fc
Create Date: 2026-05-03 16:32:44.141741

Third canonicalization pass after the 2026-05-03 data audit. Picks up clusters
the prior two passes (``080fc6916478`` + ``43096cc974fc``) didn't touch:

  1. ``Mazda OEM`` — collapses Mazda dealer / division attributions
     (``Mazda North American Operation``, ``Mazda, OCAP``, ``Med Center
     Mazda``) into the canonical ``<Make> OEM`` form mandated by audit
     decision item 3 (matches existing ``Porsche OEM`` / ``BMW OEM`` /
     ``Nissan OEM`` / ``Ford OEM``). The Flyin' Miata Shopify ``vendor``
     field carries whichever wholesale source the FM team typed in for
     each Mazda OEM SKU; consolidating them keeps brand search sane.

  2. Brand-stem typo / spacing / article / suffix collapses (audit decision
     item 4, picked up by difflib SequenceMatcher >= 0.88 over the live
     manufacturer table after stripping ``Performance | Racing | Tuning |
     Inc | LLC | …`` suffix tokens):

       - ``Driveshaft Shop`` ← ``The Driveshaft Shop`` (article variant).
       - ``Edelbrock`` ← ``Edlebrock`` (transposition typo, n=0 loser).
       - ``ST Suspension`` ← ``ST Suspensions`` (plural variant).
       - ``Airflow Research`` ← ``Airflow Research (AFR)`` (acronym suffix).
       - ``Shifteck`` ← ``Shiteck`` (typo).
       - ``Red Line`` ← ``Red Line Synthetic Oil``, ``Redline Oil`` (oil
         division collapse). Distinct from ``Redline Tuning`` (hood lifts) —
         left untouched. Note: ``080fc6916478`` declared a canonical
         ``Redline`` row but the live DB shows ``Red Line`` (n=22) is the
         dominant form, so this pass keeps that as canonical instead.

  3. Retailer-as-manufacturer leakage cleanup. Six Flyin' Miata products
     have JSON-LD ``brand.name`` / Shopify ``vendor`` strings that are
     marketplace storefronts (``Amazon.com``, ``CableWholesale.com``,
     ``Websticker.com``, ``Alibaba.com (Ningbo Dicong Machinery Co. LTD)``)
     or dealer names (the Mazda dealer cluster above) — clearly not the
     actual maker of the part. Plus one ``H.A.S`` row from x-ph.com that
     was extracted from the title of a KW HAS suspension product where the
     real brand is KW (KW = Hochleistungs-Adjustable-Suspension; the title
     heuristic latched onto the abbreviation). The Flyin' Miata adapter
     (``backend/app/crawlers/adapters/tier0_http/flyinmiata.py``) was
     updated in the same audit session to drop these vendor strings via a
     ``_NON_MANUFACTURER_VENDOR_RE`` denylist, so a fresh re-scrape won't
     re-introduce them.

     The two short bad-attribution rows ``line`` / ``woodruff`` are
     side-effects of the first iteration of that adapter fix (the title
     heuristic ran when it shouldn't have); cleaned up here too. The
     adapter's final shape suppresses title heuristics when a vendor was
     declared but discarded.

Idempotent: each merge no-ops when the canonical row is missing or the
loser row is already gone. Sentinel-style deletions of retailer-as-mfr
rows null out ``parts.part_manufacturer_id`` first (the column is
nullable), then delete the row.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4edb71f895f0'
down_revision: Union[str, None] = '43096cc974fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Cluster merges (canonical, [losers]). Losers' parts get repointed to
# canonical, then loser rows deleted.
_CLUSTERS: list[tuple[str, list[str]]] = [
    # Brand-stem collapses
    ("Driveshaft Shop", ["The Driveshaft Shop"]),
    ("Edelbrock", ["Edlebrock"]),
    ("ST Suspension", ["ST Suspensions"]),
    ("Airflow Research", ["Airflow Research (AFR)"]),
    ("Shifteck", ["Shiteck"]),
    ("Red Line", ["Red Line Synthetic Oil", "Redline Oil"]),
]

# OEM-style: ensure the canonical ``<Make> OEM`` row exists, then merge.
# (The prior migrations already landed BMW / Nissan / Ford / Porsche OEM —
# this pass adds Mazda.)
_OEM_RENAMES: list[tuple[str, list[str]]] = [
    (
        "Mazda OEM",
        [
            "Mazda North American Operation",
            "Mazda, OCAP",
            "Med Center Mazda",
        ],
    ),
]

# Retailer-as-manufacturer / title-heuristic-noise leakage. Each row's
# parts get ``part_manufacturer_id = NULL`` and the loser row is deleted.
# The Flyin' Miata adapter was patched in this same audit session to stop
# attributing these values on fresh ingest.
_BAD_ATTRIBUTION_ROWS: list[str] = [
    "Amazon.com",
    "CableWholesale.com",
    "Websticker.com",
    "Alibaba.com (Ningbo Dicong Machinery Co. LTD)",
    "H.A.S",
    "line",
    "woodruff",
]


def _merge_cluster(conn: sa.engine.Connection, canonical: str, losers: list[str]) -> None:
    """Repoint each loser's parts to canonical, then delete the loser row.

    Mirrors the helper in ``080fc6916478`` / ``43096cc974fc``. No-ops when
    the canonical row is absent (skip cluster) or a loser is absent (skip
    that loser). Normalizes the canonical's stored casing to the requested
    form when they differ.
    """
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
    """Create a curated row if no case-insensitive match exists.

    UUID minted in Python so the SQL is identical on PostgreSQL (live)
    and SQLite in-memory (test backend has no ``gen_random_uuid()``).
    Timestamps use ``CURRENT_TIMESTAMP`` for the same reason.
    """
    existing = conn.execute(
        sa.text("SELECT 1 FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
        {"name": name},
    ).first()
    if existing is not None:
        return
    conn.execute(
        sa.text(
            "INSERT INTO part_manufacturers "
            "(id, name, is_active, is_curated, created_at, updated_at) "
            "VALUES (:id, :name, :active, :curated, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"id": str(uuid.uuid4()), "name": name, "active": True, "curated": True},
    )


def _drop_bad_attribution(conn: sa.engine.Connection, name: str) -> None:
    """NULL out parts pointing at ``name``, then delete the row.

    ``parts.part_manufacturer_id`` is nullable (matches the ``Unknown`` /
    ``OEM`` / ``Aftermarket`` sentinel cleanup in ``080fc6916478``).
    """
    row = conn.execute(
        sa.text("SELECT id FROM part_manufacturers WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
        {"name": name},
    ).first()
    if row is None:
        return
    bad_id = row[0]
    conn.execute(
        sa.text("UPDATE parts SET part_manufacturer_id = NULL WHERE part_manufacturer_id = :bid"),
        {"bid": bad_id},
    )
    conn.execute(
        sa.text("DELETE FROM part_manufacturers WHERE id = :bid"),
        {"bid": bad_id},
    )


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # 1) Brand-stem cluster merges.
    for canonical, losers in _CLUSTERS:
        _merge_cluster(conn, canonical, losers)

    # 2) ``<Make> OEM`` renames. Create the canonical row before merging so
    #    losers always have somewhere to repoint into.
    for canonical, losers in _OEM_RENAMES:
        _ensure_canonical_row(conn, canonical)
        _merge_cluster(conn, canonical, losers)

    # 3) Drop retailer-as-manufacturer / title-heuristic-noise rows. NULL
    #    out their parts (no canonical exists for "I bought it from
    #    Amazon"), then delete the row.
    for bad in _BAD_ATTRIBUTION_ROWS:
        _drop_bad_attribution(conn, bad)


def downgrade() -> None:
    """Downgrade is intentionally a no-op.

    Manufacturer merges and bad-attribution deletions are destructive: the
    loser row's UUID is gone after its parts are repointed / nulled, and
    re-creating the row with a fresh UUID would not restore any of the
    repointed parts back to their original (wrong) manufacturer. Per
    project convention for canonicalization migrations, downgrade is a
    no-op rather than a partial restore.
    """
    pass
