"""add_timestamp_fields_to_cars_and_users

Revision ID: 5cc5c4be1626
Revises: c9985b835f5a
Create Date: 2025-09-01 16:49:26.985078

"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa  # noqa: F401

from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "5cc5c4be1626"
down_revision: Union[str, None] = "c9985b835f5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Get connection and inspector to check existing columns
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    # Check existing columns in cars table
    cars_columns = [col["name"] for col in inspector.get_columns("cars")]

    # Add timestamp fields to cars table if they don't exist
    if "created_at" not in cars_columns:
        op.add_column("cars", sa.Column("created_at", sa.DateTime(), nullable=True))
    if "updated_at" not in cars_columns:
        op.add_column("cars", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Set default values for existing records that have NULL values
    current_time = datetime.now(UTC)
    op.execute(f"UPDATE cars SET created_at = '{current_time}' WHERE created_at IS NULL")
    op.execute(f"UPDATE cars SET updated_at = '{current_time}' WHERE updated_at IS NULL")

    # Make columns non-nullable after setting defaults
    # This is safe to run even if columns already exist - it will only change if needed
    op.alter_column("cars", "created_at", nullable=False, existing_type=sa.DateTime())
    op.alter_column("cars", "updated_at", nullable=False, existing_type=sa.DateTime())

    # Check existing columns in users table
    users_columns = [col["name"] for col in inspector.get_columns("users")]

    # Add timestamp fields to users table if they don't exist
    if "created_at" not in users_columns:
        op.add_column("users", sa.Column("created_at", sa.DateTime(), nullable=True))
    if "updated_at" not in users_columns:
        op.add_column("users", sa.Column("updated_at", sa.DateTime(), nullable=True))

    # Set default values for existing records that have NULL values
    op.execute(f"UPDATE users SET created_at = '{current_time}' WHERE created_at IS NULL")
    op.execute(f"UPDATE users SET updated_at = '{current_time}' WHERE updated_at IS NULL")

    # Make columns non-nullable after setting defaults
    # This is safe to run even if columns already exist - it will only change if needed
    op.alter_column("users", "created_at", nullable=False, existing_type=sa.DateTime())
    op.alter_column("users", "updated_at", nullable=False, existing_type=sa.DateTime())


def downgrade() -> None:
    """Downgrade schema."""
    # Remove timestamp fields from cars table
    op.drop_column("cars", "updated_at")
    op.drop_column("cars", "created_at")

    # Remove timestamp fields from users table
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
