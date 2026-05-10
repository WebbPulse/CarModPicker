import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base

if TYPE_CHECKING:
    from .build_list import BuildList
    from .user import User


class BuildLog(Base):
    """
    Build log thread model - represents a forum-style thread for a build list.
    Each build list automatically gets one build log thread.
    """

    __tablename__ = "build_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    build_list_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("build_lists.id"), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    build_list: Mapped["BuildList"] = relationship("BuildList", back_populates="build_log")
    posts: Mapped[List["BuildLogPost"]] = relationship(
        "BuildLogPost",
        back_populates="build_log",
        cascade="all, delete-orphan",
        order_by="BuildLogPost.created_at",
    )

    __table_args__ = (UniqueConstraint("build_list_id", name="uq_build_logs_build_list_id"),)


class BuildLogPost(Base):
    """
    Build log post model - represents a post/comment in a build log thread.
    """

    __tablename__ = "build_log_posts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    build_log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("build_logs.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    build_log: Mapped["BuildLog"] = relationship("BuildLog", back_populates="posts")
    author: Mapped["User"] = relationship(
        "User",
        back_populates="build_log_posts",
        lazy="raise",  # Phase 4 D-28 / DATA-10 — catches future N+1 regressions; paired with selectinload in callers
    )
