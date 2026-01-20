from datetime import UTC, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_list_id: Mapped[int] = mapped_column(ForeignKey("build_lists.id"), nullable=False, unique=True, index=True)
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

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    build_log_id: Mapped[int] = mapped_column(ForeignKey("build_logs.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Relationships
    build_log: Mapped["BuildLog"] = relationship("BuildLog", back_populates="posts")
    author: Mapped["User"] = relationship("User", back_populates="build_log_posts")
