from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from .global_part import GlobalPart


class CrawledPage(Base):
    """
    Tracks every web page whose raw HTML has been archived to CRAWL_BUCKET (or local fallback).

    source: adapter name (e.g. "a90shop", "studiorsr") for backend crawls,
            or "chrome_extension" for pages submitted by the browser extension.
    html_s3_key: S3 object key when stored in CRAWL_BUCKET (e.g. "crawl_html/by_url/abc123.html").
    html_local_path: Absolute local filesystem path used as fallback when CRAWL_BUCKET is not configured.
    parse_status: "pending" (HTML saved, not yet parsed), "parsed" (successfully ingested),
                  "failed" (parse or ingest error).
    """

    __tablename__ = "crawled_pages"
    __table_args__ = (UniqueConstraint("url", name="uq_crawled_page_url"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    url: Mapped[str] = mapped_column(index=True, nullable=False)
    source: Mapped[str] = mapped_column(nullable=False)
    html_s3_key: Mapped[Optional[str]] = mapped_column(nullable=True)
    html_local_path: Mapped[Optional[str]] = mapped_column(nullable=True)
    crawled_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    last_parsed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    parse_status: Mapped[str] = mapped_column(default="pending", nullable=False)

    global_part_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("global_parts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    global_part: Mapped[Optional["GlobalPart"]] = relationship("GlobalPart")
