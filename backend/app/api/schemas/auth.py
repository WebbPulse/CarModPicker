"""Password bounds and the OAuth account read that outlive the legacy auth routers.

Row 13 deleted the `/api/auth` routers and every model only they declared. The
password bounds still constrain the users domain's own schemas, and the 72 byte
bcrypt cap is expressed in characters so a value that validates always hashes.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 72


class OAuthAccountRead(BaseModel):
    """A linked OAuth account as returned to clients."""

    id: UUID
    provider: str
    email: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
