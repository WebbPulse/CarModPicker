# Registers all ORM models for Alembic; Base is defined in base_class.
# Import all models here so they are attached to Base before Alembic loads env.
# pyright: reportUnusedImport=false
from app.api.models.image_source_mapping import ImageSourceMapping  # noqa: F401
from app.db.base_class import Base  # noqa: F401
