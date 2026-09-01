"""
Endpoints for chrome-extension HTML archival and generic page parsing.

POST /crawled-pages/scrape  - Authenticated user; extension submits page HTML,
                              server runs the generic JSON-LD/OG parser and
                              returns best-guess part attributes. Archives HTML.
POST /crawled-pages/html    - Authenticated user; archive-only upload.
GET  /crawled-pages/        - Admin; list archived pages with filters.
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.api.services.crawl_archive import (
    canonicalize_url,
    crawl_html_fingerprint,
    save_extension_html,
)
from app.api.services.page_html_sanitizer import sanitize_html
from app.api.services.page_parser import parse_page
from app.core.category_inference import infer_category
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_CRAWL_UPLOAD_RESPONSES: dict[int | str, dict[str, Any]] = {
    413: {
        "description": "HTML payload exceeds the configured maximum UTF-8 byte size.",
        "content": {"application/json": {"schema": {"type": "object", "properties": {"detail": {"type": "string"}}}}},
    }
}


def _split_storage_key(storage_key: str) -> tuple[Optional[str], Optional[str]]:
    if storage_key.startswith("/"):
        return None, storage_key
    return storage_key, None


def _enforce_max_crawl_html_size(
    html_size_bytes: int,
    *,
    user_id: UUID,
    url: str,
    content_length: Optional[str],
) -> None:
    max_b = settings.CRAWLED_PAGE_MAX_HTML_BYTES
    if html_size_bytes <= max_b:
        return
    logger.warning(
        "Crawled page HTML rejected over max size user_id=%s url=%s html_bytes=%s max_bytes=%s content_length=%s",
        user_id,
        url,
        html_size_bytes,
        max_b,
        content_length,
    )
    raise HTTPException(
        status_code=413,
        detail=(
            f"HTML payload exceeds maximum size ({max_b} UTF-8 bytes); "
            f"submitted html is {html_size_bytes} bytes. "
            "Increase CRAWLED_PAGE_MAX_HTML_BYTES if this limit is too strict."
        ),
    )


def _persist_extension_crawl_archive(
    db: Session,
    *,
    url: str,
    html: str,
    html_utf8: bytes,
    html_sha256: str,
    now: datetime,
) -> Tuple[Optional[str], bool, bool]:
    """
    Save extension HTML and upsert ``crawled_pages`` for ``url``.

    Returns ``(storage_key, archived, skipped_duplicate_write)``.
    When ``archived`` is False, no DB upsert is performed and ``skipped_duplicate_write`` is False.
    """
    existing = db.scalars(select(DBCrawledPage).where(DBCrawledPage.url == url)).first()
    skipped = bool(
        existing and existing.html_sha256 == html_sha256 and (existing.html_s3_key or existing.html_local_path)
    )
    if skipped:
        assert existing is not None
        storage_key = existing.html_s3_key or existing.html_local_path
        assert storage_key is not None
    else:
        storage_key = save_extension_html(url, html, html_utf8=html_utf8, logger_instance=logger)

    if storage_key is None:
        return None, False, False

    html_s3_key, html_local_path = _split_storage_key(storage_key)
    insert_vals: dict = {
        "url": url,
        "source": "chrome_extension",
        "crawled_at": now,
        "parse_status": "pending",
        "html_s3_key": html_s3_key,
        "html_local_path": html_local_path,
        "html_sha256": html_sha256,
    }
    if skipped:
        update_vals: dict = {"crawled_at": now, "html_sha256": html_sha256}
    else:
        update_vals = {
            "crawled_at": now,
            "html_sha256": html_sha256,
            "html_s3_key": html_s3_key,
            "html_local_path": html_local_path,
        }

    stmt = (
        pg_insert(DBCrawledPage).values(**insert_vals).on_conflict_do_update(index_elements=["url"], set_=update_vals)
    )
    db.execute(stmt)
    db.commit()
    return storage_key, True, skipped


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class HtmlUploadRequest(BaseModel):
    url: str
    html: str


class HtmlUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    html_s3_key: Optional[str]
    html_local_path: Optional[str]
    html_size_bytes: int
    html_sha256: str
    archive_skipped_duplicate: bool = False


class ScrapeRequest(BaseModel):
    url: str
    html: str


class ScrapeResponse(BaseModel):
    """Parsed part attributes returned to the Chrome extension after server-side inference."""

    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None  # cents
    image_urls: List[str] = []
    product_url: str
    part_manufacturer: Optional[str] = None
    part_number: Optional[str] = None
    adapter_used: str  # e.g. "a90shop", "studiorsr", "generic"
    inferred_category: Optional[str] = None  # category name slug, e.g. "exhaust", "suspension"
    archived: bool = True  # False when S3/local write failed; extension may warn the user
    html_size_bytes: int = 0
    html_sha256: str = ""
    archive_skipped_duplicate: bool = False


class CrawledPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    source: str
    html_s3_key: Optional[str]
    html_local_path: Optional[str]
    crawled_at: datetime
    last_parsed_at: Optional[datetime]
    parse_status: str
    part_id: Optional[UUID]
    html_sha256: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /scrape  — Chrome extension: archive HTML + server-side parse
# ---------------------------------------------------------------------------


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    status_code=status.HTTP_200_OK,
    responses=_CRAWL_UPLOAD_RESPONSES,
)
async def scrape_page_from_extension(
    request: Request,
    body: ScrapeRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScrapeResponse:
    """
    Accept full page HTML from the Chrome extension, archive it, and parse part attributes.

    Picks the registered site-specific adapter when the URL matches a known retailer;
    falls back to the generic parser for all other sites. Returns best-guess part
    attributes for the user to review before submitting.
    """
    raw_url = body.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="url is required")
    if not body.html:
        raise HTTPException(status_code=400, detail="html is required")

    url = canonicalize_url(raw_url)
    now = datetime.now(timezone.utc)
    _, raw_size_bytes, _ = crawl_html_fingerprint(body.html)
    _enforce_max_crawl_html_size(
        raw_size_bytes,
        user_id=current_user.id,
        url=url,
        content_length=request.headers.get("content-length"),
    )

    # Strip PII-risk content (autofilled form values, personalized scripts, etc.)
    # before anything leaves this request — archive and parse operate on the
    # sanitized HTML only. JSON-LD scripts are preserved for adapters.
    sanitized_html = sanitize_html(body.html)
    html_utf8, html_size_bytes, html_sha256 = crawl_html_fingerprint(sanitized_html)

    _, archived, skipped_dup = _persist_extension_crawl_archive(
        db,
        url=url,
        html=sanitized_html,
        html_utf8=html_utf8,
        html_sha256=html_sha256,
        now=now,
    )
    if not archived:
        logger.warning("save_extension_html returned None for %s; skipping DB upsert to avoid phantom row", url)

    try:
        payload = parse_page(sanitized_html, url)
    except Exception as exc:
        logger.warning("Generic parser failed on %s: %s", url, exc)
        payload = None

    if payload is None:
        logger.info("Generic parser returned None for %s, returning empty ScrapeResponse", url)
        return ScrapeResponse(
            product_url=url,
            adapter_used="generic",
            archived=archived,
            html_size_bytes=html_size_bytes,
            html_sha256=html_sha256,
            archive_skipped_duplicate=skipped_dup,
        )

    inferred = infer_category(payload.name, payload.description)

    return ScrapeResponse(
        name=payload.name,
        description=payload.description,
        price=payload.price_cents,
        image_urls=payload.image_urls or [],
        product_url=payload.product_url,
        part_manufacturer=payload.part_manufacturer,
        part_number=payload.part_number,
        adapter_used="generic",
        inferred_category=inferred,
        archived=archived,
        html_size_bytes=html_size_bytes,
        html_sha256=html_sha256,
        archive_skipped_duplicate=skipped_dup,
    )


# ---------------------------------------------------------------------------
# POST /html  — Chrome extension HTML upload (archive only, legacy)
# ---------------------------------------------------------------------------


@router.post(
    "/html",
    response_model=HtmlUploadResponse,
    status_code=status.HTTP_200_OK,
    responses=_CRAWL_UPLOAD_RESPONSES,
)
async def upload_html_from_extension(
    request: Request,
    body: HtmlUploadRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HtmlUploadResponse:
    """
    Accept full page HTML from the Chrome extension and archive it to CRAWL_BUCKET.
    Creates or updates a CrawledPage record for the URL so it can be re-parsed later.
    """
    raw_url = body.url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="url is required")
    if not body.html:
        raise HTTPException(status_code=400, detail="html is required")

    url = canonicalize_url(raw_url)
    now = datetime.now(timezone.utc)
    _, raw_size_bytes, _ = crawl_html_fingerprint(body.html)
    _enforce_max_crawl_html_size(
        raw_size_bytes,
        user_id=current_user.id,
        url=url,
        content_length=request.headers.get("content-length"),
    )

    sanitized_html = sanitize_html(body.html)
    html_utf8, html_size_bytes, html_sha256 = crawl_html_fingerprint(sanitized_html)

    _, archived, skipped_dup = _persist_extension_crawl_archive(
        db,
        url=url,
        html=sanitized_html,
        html_utf8=html_utf8,
        html_sha256=html_sha256,
        now=now,
    )

    if not archived:
        logger.warning("save_extension_html returned None for %s; skipping DB upsert to avoid phantom row", url)
        page = db.scalars(select(DBCrawledPage).where(DBCrawledPage.url == url)).first()
        if page is None:
            raise HTTPException(
                status_code=503,
                detail="HTML could not be saved to storage; archive unavailable. Please try again.",
            )
        return HtmlUploadResponse(
            id=page.id,
            url=page.url,
            html_s3_key=page.html_s3_key,
            html_local_path=page.html_local_path,
            html_size_bytes=html_size_bytes,
            html_sha256=html_sha256,
            archive_skipped_duplicate=False,
        )

    page = db.scalars(select(DBCrawledPage).where(DBCrawledPage.url == url)).first()
    assert page is not None
    return HtmlUploadResponse(
        id=page.id,
        url=page.url,
        html_s3_key=page.html_s3_key,
        html_local_path=page.html_local_path,
        html_size_bytes=html_size_bytes,
        html_sha256=html_sha256,
        archive_skipped_duplicate=skipped_dup,
    )


# ---------------------------------------------------------------------------
# GET /count — Admin: row count
# ---------------------------------------------------------------------------


@router.get("/count", response_model=dict[str, int])
async def count_crawled_pages(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Admin only: total crawled_pages rows."""
    count = db.scalar(select(func.count()).select_from(DBCrawledPage)) or 0
    logger.info("Admin %s retrieved crawled_pages count: %s", current_user.id, count)
    return {"count": count}


# ---------------------------------------------------------------------------
# GET /counts-by-source — Admin: row counts grouped by source
# ---------------------------------------------------------------------------


@router.get("/counts-by-source", response_model=dict[str, int])
async def count_crawled_pages_by_source(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Admin only: crawled_pages row count per source (adapter name or chrome_extension)."""
    rows = db.execute(select(DBCrawledPage.source, func.count(DBCrawledPage.id)).group_by(DBCrawledPage.source)).all()
    result = {source: count for source, count in rows}
    logger.info("Admin %s retrieved crawled_pages counts-by-source: %s sources", current_user.id, len(result))
    return result


# ---------------------------------------------------------------------------
# GET /counts-by-source-and-status — Admin: catalog completeness breakdown
# ---------------------------------------------------------------------------


@router.get("/counts-by-source-and-status", response_model=dict[str, dict[str, int]])
async def count_crawled_pages_by_source_and_status(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, dict[str, int]]:
    """Admin only: crawled_pages row count per (source, parse_status). Drives the
    parsed/total progress indicator in CrawlerAdmin — lets us see how close each
    adapter is to a full catalog even across interrupted runs."""
    rows = db.execute(
        select(DBCrawledPage.source, DBCrawledPage.parse_status, func.count(DBCrawledPage.id)).group_by(
            DBCrawledPage.source, DBCrawledPage.parse_status
        )
    ).all()
    result: dict[str, dict[str, int]] = {}
    for source, status, count in rows:
        result.setdefault(source, {})[status] = count
    logger.info(
        "Admin %s retrieved crawled_pages counts-by-source-and-status: %s sources",
        current_user.id,
        len(result),
    )
    return result


# ---------------------------------------------------------------------------
# GET /  — Admin: list archived pages
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[CrawledPageRead])
async def list_crawled_pages(
    source: Optional[str] = Query(None, description="Filter by source (adapter name or 'chrome_extension')"),
    parse_status: Optional[str] = Query(None, description="Filter by parse_status ('pending', 'parsed', 'failed')"),
    from_date: Optional[datetime] = Query(None, description="Filter crawled_at >= this datetime"),
    to_date: Optional[datetime] = Query(None, description="Filter crawled_at <= this datetime"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> List[DBCrawledPage]:
    """Admin: list HTML-archived pages with optional filters."""
    stmt = select(DBCrawledPage)
    if source:
        stmt = stmt.where(DBCrawledPage.source == source)
    if parse_status:
        stmt = stmt.where(DBCrawledPage.parse_status == parse_status)
    if from_date:
        stmt = stmt.where(DBCrawledPage.crawled_at >= from_date)
    if to_date:
        stmt = stmt.where(DBCrawledPage.crawled_at <= to_date)
    return list(db.scalars(stmt.order_by(DBCrawledPage.crawled_at.desc()).offset(skip).limit(limit)).all())
