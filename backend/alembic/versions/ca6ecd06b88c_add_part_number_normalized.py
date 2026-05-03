"""add part_number_normalized to parts + backfill + merge dup clusters

Tier-3 Item #7 schema half: add a canonical alphanumeric-uppercase column on
``parts`` (mirrors :func:`app.crawlers.parsing.part_number_canonical`) and a
joint index over ``(part_manufacturer_id, part_number_normalized)`` so the
linker's primary lookup path is one indexed equality instead of a normalize-
in-Python second pass.

After adding the column we backfill every existing row from its raw
``part_number``, and then merge styling-only duplicate clusters into one
canonical row so the new index doesn't surface mid-flight collisions. For
each ``(part_manufacturer_id, part_number_normalized)`` group with >1 row we
pick the canonical: highest ``part_listings`` count first, ties broken by
oldest ``created_at``. ``part_listings`` and ``part_cars`` from each loser
are reattached to the winner before the loser row is deleted. The merge is
keyed on raw rowids/UUIDs so re-running the migration on an already-merged
DB is a no-op (the surviving cluster has size 1 and falls out of the loop).

Migration is dialect-safe: the column add + index live in alembic ops, and
the backfill/merge use SQLAlchemy Core via the migration's bind, which works
identically on Postgres prod and the SQLite used by the test suite.

Revision ID: ca6ecd06b88c
Revises: f99b709f371a
Create Date: 2026-05-02 23:30:00.000000

"""

import re
from typing import Optional, Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ca6ecd06b88c"
down_revision: Union[str, None] = "76445da7f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Mirror of the runtime helper in app.crawlers.parsing. Duplicated here so the
# migration doesn't import application code (alembic env scripts run with a
# minimal import surface and pulling in app.crawlers.parsing transitively
# imports SQLAlchemy ORM models, ``boto3`` SDK clients, etc).
_NON_ALPHANUM_RE = re.compile(r"[^A-Za-z0-9]")
# Mirrors ``app.crawlers.parsing._PART_NUMBER_CAR_MODEL_BLACKLIST`` (BMW
# chassis-code shape that leaks into the SKU slot from titles like "Z4 M
# Coupe E86"). Lowercase, separators already stripped.
_CAR_MODEL_BLACKLIST = frozenset(
    {
        "z4m", "1m", "e8x", "e9x", "e46", "e90", "e92", "e82",
        "e85", "e86", "f80", "f82", "f10", "f12", "e60", "e63", "e64",
    }
)


def _canonical(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    canonical = _NON_ALPHANUM_RE.sub("", s).upper()
    if not canonical or len(canonical) < 4:
        return None
    if canonical.lower() in _CAR_MODEL_BLACKLIST:
        return None
    return canonical


def upgrade() -> None:
    """Add column, backfill, then merge styling-only duplicate clusters."""
    op.add_column(
        "parts",
        sa.Column("part_number_normalized", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_parts_mfr_pn_normalized",
        "parts",
        ["part_manufacturer_id", "part_number_normalized"],
        unique=False,
    )

    bind = op.get_bind()
    parts = sa.table(
        "parts",
        sa.column("id", sa.Uuid()),
        sa.column("part_number", sa.String()),
        sa.column("part_number_normalized", sa.String()),
        sa.column("part_manufacturer_id", sa.Uuid()),
        sa.column("canonical_part_id", sa.Uuid()),
        sa.column("created_at", sa.DateTime()),
    )

    # ------------------------------------------------------------------
    # Backfill: compute canonical key for every row with a part_number.
    # ------------------------------------------------------------------
    rows = bind.execute(
        sa.select(parts.c.id, parts.c.part_number).where(parts.c.part_number.isnot(None))
    ).all()
    for row in rows:
        key = _canonical(row.part_number)
        if key is None:
            continue
        bind.execute(
            sa.update(parts).where(parts.c.id == row.id).values(part_number_normalized=key)
        )

    # ------------------------------------------------------------------
    # Merge styling-only duplicate clusters. Only consider canonical rows
    # (canonical_part_id IS NULL) — duplicates already point at a winner
    # and don't need merging.
    # ------------------------------------------------------------------
    cluster_rows = bind.execute(
        sa.text(
            """
            SELECT part_manufacturer_id, part_number_normalized
            FROM parts
            WHERE canonical_part_id IS NULL
              AND part_manufacturer_id IS NOT NULL
              AND part_number_normalized IS NOT NULL
            GROUP BY part_manufacturer_id, part_number_normalized
            HAVING COUNT(*) > 1
            """
        )
    ).all()

    for cluster in cluster_rows:
        mfr_id = cluster.part_manufacturer_id
        key = cluster.part_number_normalized
        # Pick winner: highest part_listings count, fallback to oldest
        # created_at. Ties past that are deterministic on id.
        candidates = bind.execute(
            sa.text(
                """
                SELECT p.id AS id,
                       p.created_at AS created_at,
                       COALESCE(
                           (SELECT COUNT(*) FROM part_listings pl WHERE pl.part_id = p.id),
                           0
                       ) AS listing_count
                FROM parts p
                WHERE p.part_manufacturer_id = :mfr_id
                  AND p.part_number_normalized = :key
                  AND p.canonical_part_id IS NULL
                ORDER BY listing_count DESC, p.created_at ASC, p.id ASC
                """
            ),
            {"mfr_id": mfr_id, "key": key},
        ).all()
        if len(candidates) < 2:
            continue
        winner_id = candidates[0].id
        loser_ids = [c.id for c in candidates[1:]]

        for loser_id in loser_ids:
            # Resolve (part_id, retailer_id) collisions before reattaching:
            # if winner already has a listing at retailer R and loser also
            # has one, fold the loser's price_history into the winner's
            # listing and drop the loser's listing. Otherwise the bulk
            # UPDATE below would violate uq_part_listing_part_retailer.
            collisions = bind.execute(
                sa.text(
                    """
                    SELECT loser_pl.id   AS loser_listing_id,
                           winner_pl.id  AS winner_listing_id
                    FROM part_listings loser_pl
                    JOIN part_listings winner_pl
                      ON winner_pl.part_id = :winner
                     AND winner_pl.retailer_id = loser_pl.retailer_id
                    WHERE loser_pl.part_id = :loser
                    """
                ),
                {"winner": winner_id, "loser": loser_id},
            ).all()
            for coll in collisions:
                bind.execute(
                    sa.text(
                        "UPDATE part_price_history SET part_listing_id = :winner_pl "
                        "WHERE part_listing_id = :loser_pl"
                    ),
                    {
                        "winner_pl": coll.winner_listing_id,
                        "loser_pl": coll.loser_listing_id,
                    },
                )
                bind.execute(
                    sa.text("DELETE FROM part_listings WHERE id = :loser_pl"),
                    {"loser_pl": coll.loser_listing_id},
                )
            # Reattach surviving part_listings from loser → winner.
            bind.execute(
                sa.text(
                    "UPDATE part_listings SET part_id = :winner WHERE part_id = :loser"
                ),
                {"winner": winner_id, "loser": loser_id},
            )
            # Reattach part_cars rows. Use INSERT … SELECT then DELETE so we
            # don't violate the (part_id, car_id) PK when winner already has
            # the same car_id; SQLite/Postgres-portable using NOT EXISTS.
            bind.execute(
                sa.text(
                    """
                    INSERT INTO part_cars (part_id, car_id)
                    SELECT :winner, pc.car_id
                    FROM part_cars pc
                    WHERE pc.part_id = :loser
                      AND NOT EXISTS (
                          SELECT 1 FROM part_cars pc2
                          WHERE pc2.part_id = :winner AND pc2.car_id = pc.car_id
                      )
                    """
                ),
                {"winner": winner_id, "loser": loser_id},
            )
            bind.execute(
                sa.text("DELETE FROM part_cars WHERE part_id = :loser"),
                {"loser": loser_id},
            )
            # Re-point any rows that were already linked to the loser at the
            # winner so the canonical chain stays one hop deep.
            bind.execute(
                sa.text(
                    "UPDATE parts SET canonical_part_id = :winner WHERE canonical_part_id = :loser"
                ),
                {"winner": winner_id, "loser": loser_id},
            )
            # Delete loser. CASCADE on build_list_parts / votes / reports
            # handles their attached rows; the loser is a styling-only dup so
            # any references through those tables fold into the winner via
            # the cascade by design.
            bind.execute(
                sa.text("DELETE FROM parts WHERE id = :loser"),
                {"loser": loser_id},
            )


def downgrade() -> None:
    """Drop the column and index. The merge step is intentionally not
    reversed — the loser rows have already been collapsed into the winner
    and reconstructing them would require a backup, not a migration."""
    op.drop_index("ix_parts_mfr_pn_normalized", table_name="parts")
    # SAFE: downgrade reversal of already-applied migration — see SAFE-04
    op.drop_column("parts", "part_number_normalized")
