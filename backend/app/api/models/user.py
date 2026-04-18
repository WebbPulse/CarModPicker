import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .build_list_part import BuildListPart
    from .build_log import BuildLogPost
    from .part import Part
    from .report import Report
    from .vote import Vote


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    username: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Profile picture(s)
    email_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    disabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Admin/Superuser fields
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Service account — machine identity, not a real user. Cannot log in.
    is_service_account: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Subscription fields
    subscription_tier: Mapped[str] = mapped_column(default="free", nullable=False)  # 'free', 'premium'
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    subscription_status: Mapped[str] = mapped_column(
        default="active", nullable=False
    )  # 'active', 'cancelled', 'expired'

    # 2FA fields
    totp_secret: Mapped[Optional[str]] = mapped_column(nullable=True)  # TOTP secret key
    totp_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)  # Whether 2FA is enabled

    # Session preference: how long the user's access token lasts (minutes). None = use server default.
    session_expire_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Social links (optional profile URLs for display only)
    instagram_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    facebook_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    reddit_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    youtube_url: Mapped[Optional[str]] = mapped_column(nullable=True)
    tiktok_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Relationships
    build_lists: Mapped[List["BuildList"]] = relationship(
        "BuildList", back_populates="owner", cascade="all, delete-orphan"
    )
    parts: Mapped[List["Part"]] = relationship("Part", back_populates="creator", cascade="all, delete-orphan")
    build_list_parts: Mapped[List["BuildListPart"]] = relationship(
        "BuildListPart", back_populates="user", cascade="all, delete-orphan"
    )
    # Unified votes and reports
    votes: Mapped[List["Vote"]] = relationship("Vote", back_populates="user", cascade="all, delete-orphan")
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        foreign_keys="Report.user_id",
        back_populates="reporter",
        cascade="all, delete-orphan",
    )
    build_log_posts: Mapped[List["BuildLogPost"]] = relationship("BuildLogPost", back_populates="author")
