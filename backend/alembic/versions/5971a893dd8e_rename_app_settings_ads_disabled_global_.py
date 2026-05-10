"""rename app_settings.ads_disabled_global to premium_disabled

Revision ID: 5971a893dd8e
Revises: 097024200e60
Create Date: 2026-04-21 19:01:38.128199

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5971a893dd8e"
down_revision: Union[str, None] = "097024200e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "app_settings",
        "ads_disabled_global",
        new_column_name="premium_disabled",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "app_settings",
        "premium_disabled",
        new_column_name="ads_disabled_global",
    )
