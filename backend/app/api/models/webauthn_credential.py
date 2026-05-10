import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, BigInteger, ForeignKey, LargeBinary, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .user import User


class WebAuthnCredential(Base):
    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credential_id: Mapped[bytes] = mapped_column(LargeBinary, unique=True, nullable=False, index=True)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    transports: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    aaguid: Mapped[Optional[str]] = mapped_column(nullable=True)
    nickname: Mapped[str] = mapped_column(nullable=False)
    backup_eligible: Mapped[bool] = mapped_column(default=False, nullable=False)
    backup_state: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="webauthn_credentials")
