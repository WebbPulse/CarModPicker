"""The OAuth account read that outlives the legacy auth routers.

Row 13 deleted the `/api/auth` routers and every model only they declared, and
the users domain follow up deleted the password bounds with the last route that
took a password. This read is still returned inside `UserRead`.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OAuthAccountRead(BaseModel):
    """A linked OAuth account as returned to clients."""

    id: UUID
    provider: str
    email: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
