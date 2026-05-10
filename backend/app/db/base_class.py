"""Declarative SQLAlchemy Base with explicit naming convention (SAFE-09).

Every Table attached to this Base inherits MetaData.naming_convention, so Alembic
autogenerate produces deterministically-named constraints for all NEW migrations.

Do NOT retroactively rename existing constraints (D-12); running
`alembic revision --autogenerate` immediately after this change will want to
rename every historic constraint — discard that output. The convention takes
effect only for genuinely new schema objects.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import declarative_base

# SQLAlchemy-recommended convention (D-11).
# - ix:   indexes
# - uq:   unique constraints
# - ck:   check constraints
# - fk:   foreign keys (includes referred table for disambiguation)
# - pk:   primary keys
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)
Base = declarative_base(metadata=metadata)
