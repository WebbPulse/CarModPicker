from datetime import UTC, datetime

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AppSettings(Base):
    """Singleton row holding runtime-mutable global app settings (id is always 1)."""

    __tablename__ = "app_settings"
    __table_args__ = (CheckConstraint("id = 1", name="app_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    ads_disabled_global: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
