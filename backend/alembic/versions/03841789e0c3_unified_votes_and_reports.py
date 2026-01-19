"""unified_votes_and_reports

Revision ID: 03841789e0c3
Revises: 5cc5c4be1626
Create Date: 2025-10-08 21:00:42.468857

"""

from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "03841789e0c3"
down_revision: Union[str, None] = "5cc5c4be1626"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get connection and inspector to check existing tables
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # Create unified votes table if it doesn't exist
    if "votes" not in existing_tables:
        op.create_table(
            "votes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("vote_type", sa.String(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "entity_type", "entity_id", name="unique_user_entity_vote"),
        )
        op.create_index(op.f("ix_votes_id"), "votes", ["id"], unique=False)
        op.create_index(op.f("ix_votes_entity"), "votes", ["entity_type", "entity_id"], unique=False)
        op.create_index(
            op.f("ix_votes_user_entity_type"),
            "votes",
            ["user_id", "entity_type"],
            unique=False,
        )

    # Create unified reports table if it doesn't exist
    if "reports" not in existing_tables:
        op.create_table(
            "reports",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("description", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("admin_notes", sa.String(), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["reviewed_by"],
                ["users.id"],
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_reports_id"), "reports", ["id"], unique=False)
        op.create_index(op.f("ix_reports_entity"), "reports", ["entity_type", "entity_id"], unique=False)
        op.create_index(op.f("ix_reports_status"), "reports", ["status"], unique=False)
        op.create_index(
            op.f("ix_reports_user_entity_type"),
            "reports",
            ["user_id", "entity_type"],
            unique=False,
        )

    # Migrate data from old tables to new unified tables (only if old tables exist)
    # Migrate car votes
    if "car_votes" in existing_tables:
        op.execute(
            """
            INSERT INTO votes (user_id, vote_type, entity_type, entity_id, created_at, updated_at)
            SELECT user_id, vote_type, 'car', car_id, created_at, updated_at
            FROM car_votes
            WHERE NOT EXISTS (
                SELECT 1 FROM votes v 
                WHERE v.user_id = car_votes.user_id 
                AND v.entity_type = 'car' 
                AND v.entity_id = car_votes.car_id
            )
        """
        )

    # Migrate build list votes
    if "build_list_votes" in existing_tables:
        op.execute(
            """
            INSERT INTO votes (user_id, vote_type, entity_type, entity_id, created_at, updated_at)
            SELECT user_id, vote_type, 'build_list', build_list_id, created_at, updated_at
            FROM build_list_votes
            WHERE NOT EXISTS (
                SELECT 1 FROM votes v 
                WHERE v.user_id = build_list_votes.user_id 
                AND v.entity_type = 'build_list' 
                AND v.entity_id = build_list_votes.build_list_id
            )
        """
        )

    # Migrate global part votes
    if "global_part_votes" in existing_tables:
        op.execute(
            """
            INSERT INTO votes (user_id, vote_type, entity_type, entity_id, created_at, updated_at)
            SELECT user_id, vote_type, 'global_part', global_part_id, created_at, updated_at
            FROM global_part_votes
            WHERE NOT EXISTS (
                SELECT 1 FROM votes v 
                WHERE v.user_id = global_part_votes.user_id 
                AND v.entity_type = 'global_part' 
                AND v.entity_id = global_part_votes.global_part_id
            )
        """
        )

    # Migrate car reports
    if "car_reports" in existing_tables:
        op.execute(
            """
            INSERT INTO reports (user_id, entity_type, entity_id, reason, description, status, 
                               admin_notes, reviewed_by, reviewed_at, created_at, updated_at)
            SELECT user_id, 'car', car_id, reason, description, status, 
                   admin_notes, reviewed_by, reviewed_at, created_at, updated_at
            FROM car_reports
            WHERE NOT EXISTS (
                SELECT 1 FROM reports r 
                WHERE r.user_id = car_reports.user_id 
                AND r.entity_type = 'car' 
                AND r.entity_id = car_reports.car_id
                AND r.reason = car_reports.reason
            )
        """
        )

    # Migrate build list reports
    if "build_list_reports" in existing_tables:
        op.execute(
            """
            INSERT INTO reports (user_id, entity_type, entity_id, reason, description, status, 
                               admin_notes, reviewed_by, reviewed_at, created_at, updated_at)
            SELECT user_id, 'build_list', build_list_id, reason, description, status, 
                   admin_notes, reviewed_by, reviewed_at, created_at, updated_at
            FROM build_list_reports
            WHERE NOT EXISTS (
                SELECT 1 FROM reports r 
                WHERE r.user_id = build_list_reports.user_id 
                AND r.entity_type = 'build_list' 
                AND r.entity_id = build_list_reports.build_list_id
                AND r.reason = build_list_reports.reason
            )
        """
        )

    # Migrate global part reports
    if "global_part_reports" in existing_tables:
        op.execute(
            """
            INSERT INTO reports (user_id, entity_type, entity_id, reason, description, status, 
                               admin_notes, reviewed_by, reviewed_at, created_at, updated_at)
            SELECT user_id, 'global_part', global_part_id, reason, description, status, 
                   admin_notes, reviewed_by, reviewed_at, created_at, updated_at
            FROM global_part_reports
            WHERE NOT EXISTS (
                SELECT 1 FROM reports r 
                WHERE r.user_id = global_part_reports.user_id 
                AND r.entity_type = 'global_part' 
                AND r.entity_id = global_part_reports.global_part_id
                AND r.reason = global_part_reports.reason
            )
        """
        )

    # Drop old tables if they exist
    if "car_votes" in existing_tables:
        op.drop_table("car_votes")
    if "build_list_votes" in existing_tables:
        op.drop_table("build_list_votes")
    if "global_part_votes" in existing_tables:
        op.drop_table("global_part_votes")
    if "car_reports" in existing_tables:
        op.drop_table("car_reports")
    if "build_list_reports" in existing_tables:
        op.drop_table("build_list_reports")
    if "global_part_reports" in existing_tables:
        op.drop_table("global_part_reports")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate old tables
    op.create_table(
        "car_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("car_id", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["car_id"],
            ["cars.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "car_id", name="unique_user_car_vote"),
    )
    op.create_index(op.f("ix_car_votes_id"), "car_votes", ["id"], unique=False)

    op.create_table(
        "build_list_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("build_list_id", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["build_list_id"],
            ["build_lists.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "build_list_id", name="unique_user_build_list_vote"),
    )
    op.create_index(op.f("ix_build_list_votes_id"), "build_list_votes", ["id"], unique=False)

    op.create_table(
        "global_part_votes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("global_part_id", sa.Integer(), nullable=False),
        sa.Column("vote_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["global_part_id"],
            ["global_parts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "global_part_id", name="unique_user_global_part_vote"),
    )
    op.create_index(op.f("ix_global_part_votes_id"), "global_part_votes", ["id"], unique=False)

    op.create_table(
        "car_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("car_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("admin_notes", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["car_id"],
            ["cars.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_car_reports_id"), "car_reports", ["id"], unique=False)

    op.create_table(
        "build_list_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("build_list_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("admin_notes", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["build_list_id"],
            ["build_lists.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_build_list_reports_id"), "build_list_reports", ["id"], unique=False)

    op.create_table(
        "global_part_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("global_part_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("admin_notes", sa.String(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["global_part_id"],
            ["global_parts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_global_part_reports_id"), "global_part_reports", ["id"], unique=False)

    # Migrate data back from unified tables to old tables
    # Migrate car votes back
    op.execute(
        """
        INSERT INTO car_votes (user_id, car_id, vote_type, created_at, updated_at)
        SELECT user_id, entity_id, vote_type, created_at, updated_at
        FROM votes WHERE entity_type = 'car'
    """
    )

    # Migrate build list votes back
    op.execute(
        """
        INSERT INTO build_list_votes (user_id, build_list_id, vote_type, created_at, updated_at)
        SELECT user_id, entity_id, vote_type, created_at, updated_at
        FROM votes WHERE entity_type = 'build_list'
    """
    )

    # Migrate global part votes back
    op.execute(
        """
        INSERT INTO global_part_votes (user_id, global_part_id, vote_type, created_at, updated_at)
        SELECT user_id, entity_id, vote_type, created_at, updated_at
        FROM votes WHERE entity_type = 'global_part'
    """
    )

    # Migrate car reports back
    op.execute(
        """
        INSERT INTO car_reports (user_id, car_id, reason, description, status, 
                               admin_notes, reviewed_by, reviewed_at, created_at, updated_at)
        SELECT user_id, entity_id, reason, description, status, 
               admin_notes, reviewed_by, reviewed_at, created_at, updated_at
        FROM reports WHERE entity_type = 'car'
    """
    )

    # Migrate build list reports back
    op.execute(
        """
        INSERT INTO build_list_reports (user_id, build_list_id, reason, description, status, 
                                      admin_notes, reviewed_by, reviewed_at, created_at, updated_at)
        SELECT user_id, entity_id, reason, description, status, 
               admin_notes, reviewed_by, reviewed_at, created_at, updated_at
        FROM reports WHERE entity_type = 'build_list'
    """
    )

    # Migrate global part reports back
    op.execute(
        """
        INSERT INTO global_part_reports (user_id, global_part_id, reason, description, status, 
                                       admin_notes, reviewed_by, reviewed_at, created_at, updated_at)
        SELECT user_id, entity_id, reason, description, status, 
               admin_notes, reviewed_by, reviewed_at, created_at, updated_at
        FROM reports WHERE entity_type = 'global_part'
    """
    )

    # Drop unified tables
    op.drop_table("reports")
    op.drop_table("votes")
