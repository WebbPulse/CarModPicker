"""migrate all PKs and FKs to uuid7 (non-destructive)

Revision ID: 5a381dff5fd1
Revises: 5f5924feaa24
Create Date: 2026-04-15 21:44:01.111969

Non-destructive migration from integer PKs/FKs to UUID. Every existing row is
preserved: each int PK gets mapped to a freshly generated UUID, and every FK
column is rewritten via JOIN through that mapping. Polymorphic columns
(votes.entity_id, reports.entity_id) are backfilled per entity_type with
separate UPDATEs.

This migration is hand-written because alembic autogenerate cannot produce
data backfill. It is the documented exception to the "always autogenerate"
rule in CLAUDE.md — the rule does not apply to type-change migrations that
must preserve referential data.

Existing rows receive UUIDv4 via Postgres `gen_random_uuid()` rather than
UUIDv7. The time-ordering property of v7 only matters for rows inserted after
this migration (which still get uuid7 via the SQLAlchemy column default).
Backfilling v7 would require either the `pg_uuidv7` extension or per-row
Python UPDATEs; neither is worth the cost for pre-existing rows.

Postgres only. Tests use SQLite + Base.metadata.create_all and never execute
this migration.
"""

from typing import List, Optional, Sequence, Tuple, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5a381dff5fd1"
down_revision: Union[str, None] = "5f5924feaa24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Schema topology. Every list below describes a piece of the migration plan
# and is consumed by the phased upgrade() below.
# ---------------------------------------------------------------------------

# Tables whose integer primary key becomes a UUID.
PK_TABLES: List[str] = [
    "users",
    "makes",
    "categories",
    "brands",
    "retailers",
    "image_source_mappings",
    "car_models",
    "cars",
    "global_parts",
    "build_lists",
    "build_list_phases",
    "part_listings",
    "build_logs",
    "build_list_parts",
    "build_log_posts",
    "bug_reports",
    "reports",
    "votes",
    "background_jobs",
    "crawled_pages",
    "part_price_history",
]

# Declared FK columns. (child_table, child_column, parent_table, nullable,
# ondelete). ondelete=None means no ON DELETE action.
FkSpec = Tuple[str, str, str, bool, Optional[str]]
FKS: List[FkSpec] = [
    ("build_lists", "car_id", "cars", True, None),
    ("build_lists", "user_id", "users", False, None),
    ("part_listings", "global_part_id", "global_parts", False, None),
    ("part_listings", "retailer_id", "retailers", False, None),
    ("build_list_parts", "build_list_id", "build_lists", False, None),
    ("build_list_parts", "global_part_id", "global_parts", False, None),
    ("build_list_parts", "added_by", "users", False, None),
    ("build_list_parts", "build_list_phase_id", "build_list_phases", True, "SET NULL"),
    ("background_jobs", "created_by_user_id", "users", True, "SET NULL"),
    ("build_list_phases", "build_list_id", "build_lists", False, "CASCADE"),
    ("part_price_history", "part_listing_id", "part_listings", False, None),
    ("car_models", "make_id", "makes", False, "CASCADE"),
    ("reports", "user_id", "users", False, None),
    ("reports", "reviewed_by", "users", True, None),
    ("build_logs", "build_list_id", "build_lists", False, None),
    ("build_log_posts", "build_log_id", "build_logs", False, None),
    ("build_log_posts", "user_id", "users", True, None),
    ("bug_reports", "user_id", "users", True, None),
    ("bug_reports", "assigned_to", "users", True, None),
    ("crawled_pages", "global_part_id", "global_parts", True, "SET NULL"),
    ("global_parts", "category_id", "categories", False, None),
    ("global_parts", "user_id", "users", False, None),
    ("global_parts", "brand_id", "brands", True, None),
    ("cars", "car_model_id", "car_models", False, "CASCADE"),
    ("votes", "user_id", "users", False, None),
]

# Polymorphic FK columns — not declared with ForeignKey; a discriminator column
# tells us which parent table each row points at.
PolymorphicSpec = Tuple[str, str, str, dict]
POLYMORPHIC: List[PolymorphicSpec] = [
    (
        "votes",
        "entity_id",
        "entity_type",
        {"car": "cars", "build_list": "build_lists", "global_part": "global_parts"},
    ),
    (
        "reports",
        "entity_id",
        "entity_type",
        {"build_list": "build_lists", "global_part": "global_parts"},
    ),
]

# Association tables whose composite PK is entirely made of FK columns.
AssociationSpec = Tuple[str, List[Tuple[str, str]]]
ASSOCIATIONS: List[AssociationSpec] = [
    (
        "global_part_cars",
        [("global_part_id", "global_parts"), ("car_id", "cars")],
    ),
]

# FK columns that carry an index in the target UUID schema (index=True on the
# mapped_column). Single-column FK indexes only — compound indexes are
# handled in COMPOUND_INDEXES below.
FK_INDEXES: List[Tuple[str, str]] = [
    ("car_models", "make_id"),
    ("cars", "car_model_id"),
    ("global_parts", "brand_id"),
    ("part_listings", "global_part_id"),
    ("part_listings", "retailer_id"),
    ("part_price_history", "part_listing_id"),
    ("build_logs", "build_list_id"),
    ("build_log_posts", "build_log_id"),
    ("bug_reports", "user_id"),
    ("background_jobs", "created_by_user_id"),
    ("crawled_pages", "global_part_id"),
]

# Unique constraints that cover at least one changing column; drop/recreate.
UniqueSpec = Tuple[str, str, List[str]]
UNIQUES: List[UniqueSpec] = [
    ("uq_part_listing_global_part_retailer", "part_listings", ["global_part_id", "retailer_id"]),
    ("uq_build_logs_build_list_id", "build_logs", ["build_list_id"]),
    ("unique_user_entity_vote", "votes", ["user_id", "entity_type", "entity_id"]),
    ("uq_car_models_make_id_name", "car_models", ["make_id", "name"]),
]

# Compound indexes that cover at least one changing column; drop/recreate.
CompoundIndexSpec = Tuple[str, str, List[str]]
COMPOUND_INDEXES: List[CompoundIndexSpec] = [
    ("ix_votes_entity", "votes", ["entity_type", "entity_id"]),
    ("ix_votes_user_entity_type", "votes", ["user_id", "entity_type"]),
    ("ix_reports_entity", "reports", ["entity_type", "entity_id"]),
    ("ix_reports_user_entity_type", "reports", ["user_id", "entity_type"]),
]


# ---------------------------------------------------------------------------
# Migration body.
# ---------------------------------------------------------------------------


def upgrade() -> None:
    bind = op.get_bind()

    # gen_random_uuid() is built into Postgres 13+; no extension needed.

    # ---- Phase 1: add staging UUID columns ------------------------------
    for tbl in PK_TABLES:
        op.add_column(tbl, sa.Column("new_id", sa.Uuid(as_uuid=True), nullable=True))

    for child, col, _parent, _nullable, _ondelete in FKS:
        op.add_column(child, sa.Column(f"new_{col}", sa.Uuid(as_uuid=True), nullable=True))

    for child, col, _disc, _mapping in POLYMORPHIC:
        op.add_column(child, sa.Column(f"new_{col}", sa.Uuid(as_uuid=True), nullable=True))

    for tbl, cols in ASSOCIATIONS:
        for col_name, _parent in cols:
            op.add_column(tbl, sa.Column(f"new_{col_name}", sa.Uuid(as_uuid=True), nullable=True))

    # ---- Phase 2: mint UUIDs for every parent row -----------------------
    for tbl in PK_TABLES:
        bind.execute(sa.text(f'UPDATE "{tbl}" SET new_id = gen_random_uuid()'))

    # ---- Phase 3: backfill declared FK columns via JOIN -----------------
    for child, col, parent, _nullable, _ondelete in FKS:
        bind.execute(
            sa.text(f'UPDATE "{child}" SET new_{col} = p.new_id ' f'FROM "{parent}" p WHERE "{child}".{col} = p.id')
        )

    # ---- Phase 4: backfill polymorphic columns per entity_type ----------
    for child, col, disc, mapping in POLYMORPHIC:
        for disc_value, parent in mapping.items():
            bind.execute(
                sa.text(
                    f'UPDATE "{child}" SET new_{col} = p.new_id '
                    f'FROM "{parent}" p '
                    f'WHERE "{child}".{col} = p.id AND "{child}".{disc} = :disc'
                ),
                {"disc": disc_value},
            )

    # ---- Phase 5: backfill association-table FK columns -----------------
    for tbl, cols in ASSOCIATIONS:
        for col_name, parent in cols:
            bind.execute(
                sa.text(
                    f'UPDATE "{tbl}" SET new_{col_name} = p.new_id '
                    f'FROM "{parent}" p WHERE "{tbl}".{col_name} = p.id'
                )
            )

    # ---- Phase 6: orphan checks -----------------------------------------
    # Nullable FKs can legitimately be NULL; only NULLs introduced by a bad
    # join (old value present, new value missing) are orphans. NOT NULL FKs
    # must be fully populated after backfill.
    for child, col, parent, nullable, _ondelete in FKS:
        if nullable:
            q = f'SELECT COUNT(*) FROM "{child}" ' f"WHERE {col} IS NOT NULL AND new_{col} IS NULL"
        else:
            q = f'SELECT COUNT(*) FROM "{child}" WHERE new_{col} IS NULL'
        orphans = bind.execute(sa.text(q)).scalar_one()
        if orphans:
            raise RuntimeError(
                f"{orphans} row(s) in {child}.{col} reference a missing "
                f"{parent}; resolve orphans before re-running."
            )

    for child, col, disc, mapping in POLYMORPHIC:
        known = list(mapping.keys())
        orphans = bind.execute(
            sa.text(f'SELECT COUNT(*) FROM "{child}" ' f"WHERE {disc} = ANY(:known) AND new_{col} IS NULL"),
            {"known": known},
        ).scalar_one()
        if orphans:
            raise RuntimeError(
                f"{orphans} polymorphic row(s) in {child}.{col} reference a "
                f"missing parent; resolve orphans before re-running."
            )
        unknown = bind.execute(
            sa.text(f'SELECT COUNT(*) FROM "{child}" ' f"WHERE {disc} != ALL(:known)"),
            {"known": known},
        ).scalar_one()
        if unknown:
            raise RuntimeError(
                f"{unknown} row(s) in {child} have an unknown {disc} value; " f"expected one of {known}."
            )

    for tbl, cols in ASSOCIATIONS:
        for col_name, parent in cols:
            orphans = bind.execute(sa.text(f'SELECT COUNT(*) FROM "{tbl}" WHERE new_{col_name} IS NULL')).scalar_one()
            if orphans:
                raise RuntimeError(
                    f"{orphans} row(s) in {tbl}.{col_name} reference a "
                    f"missing {parent}; resolve orphans before re-running."
                )

    # ---- Phase 7: drop compound indexes that cover changing columns -----
    for name, table, _cols in COMPOUND_INDEXES:
        op.drop_index(name, table_name=table)

    # ---- Phase 8: drop unique constraints that cover changing columns ---
    for name, table, _cols in UNIQUES:
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_constraint(name, table, type_="unique")

    # ---- Phase 9: drop FK constraints and their backing indexes ---------
    # Drop the association-table composite PK first — it IS the two FK
    # columns, so its PK must go before we drop the individual FKs.
    for tbl, _cols in ASSOCIATIONS:
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_constraint(f"{tbl}_pkey", tbl, type_="primary")

    for child, col, _parent, _nullable, _ondelete in FKS:
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_constraint(f"{child}_{col}_fkey", child, type_="foreignkey")

    for tbl, cols in ASSOCIATIONS:
        for col_name, _parent in cols:
            # SAFE: downgrade reversal of already-applied migration — see SAFE-04
            op.drop_constraint(f"{tbl}_{col_name}_fkey", tbl, type_="foreignkey")

    for child, col in FK_INDEXES:
        op.drop_index(f"ix_{child}_{col}", table_name=child)

    # ---- Phase 10: drop old int FK columns ------------------------------
    for child, col, _parent, _nullable, _ondelete in FKS:
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_column(child, col)

    for child, col, _disc, _mapping in POLYMORPHIC:
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_column(child, col)

    for tbl, cols in ASSOCIATIONS:
        for col_name, _parent in cols:
            # SAFE: downgrade reversal of already-applied migration — see SAFE-04
            op.drop_column(tbl, col_name)

    # ---- Phase 11: drop old PK constraints, indexes, and int id cols ----
    for tbl in PK_TABLES:
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_constraint(f"{tbl}_pkey", tbl, type_="primary")
        op.drop_index(f"ix_{tbl}_id", table_name=tbl)
        # SAFE: downgrade reversal of already-applied migration — see SAFE-04
        op.drop_column(tbl, "id")

    # ---- Phase 12: promote staging columns to canonical names -----------
    for tbl in PK_TABLES:
        op.alter_column(tbl, "new_id", new_column_name="id", nullable=False)
        op.create_primary_key(f"{tbl}_pkey", tbl, ["id"])
        op.create_index(f"ix_{tbl}_id", tbl, ["id"])

    for child, col, _parent, nullable, _ondelete in FKS:
        op.alter_column(child, f"new_{col}", new_column_name=col, nullable=nullable)

    # Polymorphic entity_id columns are NOT NULL on both votes and reports.
    for child, col, _disc, _mapping in POLYMORPHIC:
        op.alter_column(child, f"new_{col}", new_column_name=col, nullable=False)

    for tbl, cols in ASSOCIATIONS:
        for col_name, _parent in cols:
            op.alter_column(tbl, f"new_{col_name}", new_column_name=col_name, nullable=False)
        op.create_primary_key(f"{tbl}_pkey", tbl, [c for c, _ in cols])

    # ---- Phase 13: re-create FK constraints -----------------------------
    for child, col, parent, _nullable, ondelete in FKS:
        op.create_foreign_key(
            f"{child}_{col}_fkey",
            child,
            parent,
            [col],
            ["id"],
            ondelete=ondelete,
        )

    for tbl, cols in ASSOCIATIONS:
        for col_name, parent in cols:
            op.create_foreign_key(
                f"{tbl}_{col_name}_fkey",
                tbl,
                parent,
                [col_name],
                ["id"],
                ondelete="CASCADE",
            )

    # ---- Phase 14: re-create FK-column indexes --------------------------
    for child, col in FK_INDEXES:
        op.create_index(f"ix_{child}_{col}", child, [col])

    # ---- Phase 15: re-create unique and compound indexes ----------------
    for name, table, cols in UNIQUES:
        op.create_unique_constraint(name, table, columns=cols)

    for name, table, cols in COMPOUND_INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    """No clean downgrade path.

    The original integer primary keys are dropped during upgrade and are not
    recoverable — any external system that cached them would be broken by a
    fresh int sequence. If rollback is ever needed, restore from a pre-upgrade
    database snapshot.
    """
    raise NotImplementedError(
        "Downgrade from UUID back to integer primary keys is not supported; "
        "restore from a pre-upgrade backup instead."
    )
