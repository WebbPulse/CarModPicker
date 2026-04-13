"""crawled_pages_html_sha256

Revision ID: 274bde4f4654
Revises: 42feddff6034
Create Date: 2026-04-12 19:25:56.428801

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "274bde4f4654"
down_revision: Union[str, None] = "42feddff6034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("crawled_pages", sa.Column("html_sha256", sa.String(), nullable=True))
    op.create_index(op.f("ix_crawled_pages_html_sha256"), "crawled_pages", ["html_sha256"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_crawled_pages_html_sha256"), table_name="crawled_pages")
    op.drop_column("crawled_pages", "html_sha256")
