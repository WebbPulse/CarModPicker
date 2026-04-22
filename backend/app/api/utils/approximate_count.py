"""
Approximate row counts for dashboard / observability use.

On PostgreSQL this reads ``pg_class.reltuples`` (O(1), maintained by autovacuum/ANALYZE).
On SQLite (tests) or when reltuples is unknown (-1 — table never analyzed), it falls back
to an exact ``SELECT COUNT(*)`` so values stay correct in dev/test and on brand-new tables.
"""

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session


def approximate_count(db: Session, table: Any) -> int:
    """Approximate row count for a SQLAlchemy model class or Table object."""
    if hasattr(table, "__tablename__"):
        table_name: str = table.__tablename__
    elif hasattr(table, "name") and hasattr(table, "c"):
        table_name = table.name
    else:
        raise TypeError("approximate_count expects a declarative model class or a Table object")

    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else ""

    if dialect == "postgresql":
        row = db.execute(
            text("SELECT reltuples::bigint FROM pg_class WHERE oid = to_regclass(:name)"),
            {"name": table_name},
        ).scalar()
        # reltuples == -1 means the table has never been ANALYZEd; fall through to exact count
        if row is not None and row >= 0:
            return int(row)

    return int(db.execute(select(func.count()).select_from(table)).scalar() or 0)
