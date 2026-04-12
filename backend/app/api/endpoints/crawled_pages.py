"""
Endpoints for crawled page HTML archival and admin re-parse.

POST /crawled-pages/html         - Authenticated user; Chrome extension submits full page HTML.
GET  /crawled-pages/             - Admin; list archived pages with filters.
POST /crawled-pages/{id}/re-parse - Admin; fetch stored HTML, parse, and ingest (full pipeline).
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.crawlers.base import save_crawl_page_html
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class HtmlUploadRequest(BaseModel):
    url: str
    html: str


class HtmlUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    html_s3_key: Optional[str]
    html_local_path: Optional[str]


class CrawledPageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    source: str
    html_s3_key: Optional[str]
    html_local_path: Optional[str]
    crawled_at: datetime
    last_parsed_at: Optional[datetime]
    parse_status: str
    global_part_id: Optional[int]


class ReparseResponse(BaseModel):
    crawled_page_id: int
    global_part_id: Optional[int]
    parse_status: str
    message: str


# ---------------------------------------------------------------------------
# POST /html  — Chrome extension HTML upload
# ---------------------------------------------------------------------------


@router.post("/html", response_model=HtmlUploadResponse, status_code=status.HTTP_200_OK)
async def upload_html_from_extension(
    body: HtmlUploadRequest,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DBCrawledPage:
    """
    Accept full page HTML from the Chrome extension and archive it to CRAWL_BUCKET.
    Creates or updates a CrawledPage record for the URL so it can be re-parsed later.
    """
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    storage_key = save_crawl_page_html("chrome_extension", url, body.html, "")

    page = db.query(DBCrawledPage).filter(DBCrawledPage.url == url).first()
    now = datetime.now(timezone.utc)
    if page is None:
        page = DBCrawledPage(
            url=url,
            source="chrome_extension",
            crawled_at=now,
            parse_status="pending",
        )
        db.add(page)
    if storage_key:
        if storage_key.startswith("/"):
            page.html_local_path = storage_key
        else:
            page.html_s3_key = storage_key
    db.commit()
    db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# GET /count — Admin: row count
# ---------------------------------------------------------------------------


@router.get("/count", response_model=dict[str, int])
async def count_crawled_pages(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Admin only: total crawled_pages rows."""
    count = db.query(DBCrawledPage).count()
    logger.info("Admin %s retrieved crawled_pages count: %s", current_user.id, count)
    return {"count": count}


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
    q = db.query(DBCrawledPage)
    if source:
        q = q.filter(DBCrawledPage.source == source)
    if parse_status:
        q = q.filter(DBCrawledPage.parse_status == parse_status)
    if from_date:
        q = q.filter(DBCrawledPage.crawled_at >= from_date)
    if to_date:
        q = q.filter(DBCrawledPage.crawled_at <= to_date)
    return q.order_by(DBCrawledPage.crawled_at.desc()).offset(skip).limit(limit).all()


# ---------------------------------------------------------------------------
# POST /{page_id}/re-parse  — Admin: fetch stored HTML and re-run adapter
# ---------------------------------------------------------------------------


@router.post("/{page_id}/re-parse", response_model=ReparseResponse)
async def reparse_crawled_page(
    page_id: int,
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Admin: fetch archived HTML for a crawled page and re-run the retailer parser + ingest.

    Uses the row's ``source`` when it is a registered adapter; for ``chrome_extension``,
    picks the adapter from the URL host (e.g. a90shop.com → a90shop).
    """
    from app.crawlers.archive_rescrape import rescrape_crawled_page_from_archive, resolve_parse_adapter_name
    from app.crawlers.runner import _resolve_crawler_user, _resolve_default_category_id

    page = db.get(DBCrawledPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="CrawledPage not found")

    if not page.html_s3_key and not page.html_local_path:
        raise HTTPException(
            status_code=404,
            detail="HTML not found in storage for this page. It may not have been archived yet.",
        )

    if resolve_parse_adapter_name(page) is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No adapter available for source '{page.source}' and this URL's host "
                "does not match a registered retailer. "
                "Re-parse requires a backend adapter or a known retailer URL."
            ),
        )

    crawler_user = _resolve_crawler_user(db)
    cat_id = _resolve_default_category_id(db)

    outcome, part_id, err_detail = rescrape_crawled_page_from_archive(
        db,
        page,
        crawler_user=crawler_user,
        default_category_id=cat_id,
        log=logger,
    )

    if outcome == "skipped_no_html":
        raise HTTPException(
            status_code=404,
            detail="HTML not found in storage for this page. It may not have been archived yet.",
        )

    if outcome == "parse_failed":
        return ReparseResponse(
            crawled_page_id=page.id,
            global_part_id=page.global_part_id,
            parse_status="failed",
            message="Adapter returned None — page is not a product page or parse failed.",
        )

    if outcome == "ingest_failed":
        raise HTTPException(status_code=500, detail=f"Ingest failed: {err_detail}") from None

    return ReparseResponse(
        crawled_page_id=page.id,
        global_part_id=part_id,
        parse_status="parsed",
        message="Re-parse and ingest succeeded.",
    )
