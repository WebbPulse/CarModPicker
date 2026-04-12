"""
Endpoints for crawled page HTML archival and admin re-parse.

POST /crawled-pages/html         - Authenticated user; Chrome extension submits full page HTML.
GET  /crawled-pages/             - Admin; list archived pages with filters.
POST /crawled-pages/{id}/re-parse - Admin; fetch stored HTML and re-run adapter parsing.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
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
    Admin: fetch archived HTML for a crawled page and re-run its adapter's parser.
    Only works for pages whose source matches a registered backend adapter (not chrome_extension).
    """
    from app.crawlers.adapters import ADAPTER_REGISTRY, get_adapter
    from app.crawlers.base import _get_crawl_s3_client, ingest_payload
    from app.crawlers.runner import _resolve_crawler_user, _resolve_default_category_id

    page = db.get(DBCrawledPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="CrawledPage not found")

    if page.source == "chrome_extension" or page.source not in ADAPTER_REGISTRY:
        raise HTTPException(
            status_code=422,
            detail=(
                f"No adapter available for source '{page.source}'. "
                "Re-parse requires a registered backend adapter (not chrome_extension)."
            ),
        )

    # Retrieve HTML from storage
    html: Optional[str] = None

    if page.html_s3_key:
        s3_client, bucket_name = _get_crawl_s3_client()
        if s3_client is not None and bucket_name is not None:
            try:
                obj = s3_client.get_object(Bucket=bucket_name, Key=page.html_s3_key)
                html = obj["Body"].read().decode("utf-8", errors="replace")
            except Exception as e:
                logger.warning("Could not fetch HTML from S3 key %s: %s", page.html_s3_key, e)

    if html is None and page.html_local_path:
        try:
            html = Path(page.html_local_path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Could not read local HTML %s: %s", page.html_local_path, e)

    if html is None:
        raise HTTPException(
            status_code=404,
            detail="HTML not found in storage for this page. It may not have been archived yet.",
        )

    # Run adapter parser
    adapter = get_adapter(page.source)
    payload = adapter.parse_product_page(html, page.url)
    now = datetime.now(timezone.utc)

    if payload is None:
        page.parse_status = "failed"
        page.last_parsed_at = now
        db.commit()
        return ReparseResponse(
            crawled_page_id=page.id,
            global_part_id=page.global_part_id,
            parse_status="failed",
            message="Adapter returned None — page is not a product page or parse failed.",
        )

    # Ingest using crawler user and default category from env
    try:
        crawler_user = _resolve_crawler_user(db)
        cat_id = _resolve_default_category_id(db)
        part = ingest_payload(
            db,
            payload,
            current_user=crawler_user,
            default_category_id=cat_id,
            logger=logger,
            source="re_parsed",
        )
        page.global_part_id = part.id
        page.parse_status = "parsed"
        page.last_parsed_at = now
        db.commit()
        return ReparseResponse(
            crawled_page_id=page.id,
            global_part_id=part.id,
            parse_status="parsed",
            message="Re-parse and ingest succeeded.",
        )
    except Exception as e:
        db.rollback()
        page.parse_status = "failed"
        page.last_parsed_at = now
        db.commit()
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}") from e
