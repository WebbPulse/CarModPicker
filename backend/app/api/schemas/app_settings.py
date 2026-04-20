from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppSettingsRead(BaseModel):
    """Global app settings returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    ads_disabled_global: bool
    updated_at: datetime


class AppSettingsUpdate(BaseModel):
    """Partial update for global app settings. All fields optional."""

    ads_disabled_global: bool | None = None
