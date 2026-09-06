# Base for the legacy SQLAlchemy layer; no ORM models remain. Kept until Alembic and the
# SQL session are removed.
# pyright: reportUnusedImport=false
from app.db.base_class import Base  # noqa: F401
