"""
Tracks source URLs of images we've downloaded and stored.
Used for deduplication: when adding images to a part, we check if we've already
downloaded from this source URL and reuse the existing file_key instead of re-uploading.
"""

from datetime import UTC, datetime

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class ImageSourceMapping(Base):
    """
    Maps external image source URLs to our stored file keys.
    Enables deduplication when the same product image appears across
    multiple parts or scrape sessions.
    """

    __tablename__ = "image_source_mappings"
    __table_args__ = (UniqueConstraint("source_url", name="uq_image_source_mapping_source_url"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_url: Mapped[str] = mapped_column(index=True, nullable=False)
    file_key: Mapped[str] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
    )
