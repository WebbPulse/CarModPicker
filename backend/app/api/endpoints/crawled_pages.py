"""
Endpoints for crawled page HTML archival and admin re-parse.

POST /crawled-pages/scrape       - Authenticated user; Chrome extension submits full page HTML,
                                   server picks the right adapter (or generic fallback) and returns
                                   parsed part attributes. Also archives the HTML.
POST /crawled-pages/html         - Authenticated user; Chrome extension submits full page HTML
                                   for archival only (legacy, kept for backward compat).
GET  /crawled-pages/             - Admin; list archived pages with filters.
POST /crawled-pages/{id}/re-parse - Admin; fetch stored HTML, parse, and ingest (full pipeline).
"""

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user, get_current_user
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.core.category_inference import infer_category
from app.core.config import settings
from app.crawlers.adapters import adapter_name_for_product_url, get_adapter
from app.crawlers.base import canonicalize_url, crawl_html_fingerprint, save_crawl_page_html
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
    user_id: int,
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
    existing = db.query(DBCrawledPage).filter(DBCrawledPage.url == url).first()
    skipped = bool(
        existing and existing.html_sha256 == html_sha256 and (existing.html_s3_key or existing.html_local_path)
    )
    if skipped:
        assert existing is not None
        storage_key = existing.html_s3_key or existing.html_local_path
        assert storage_key is not None
    else:
        storage_key = save_crawl_page_html(
            "chrome_extension", url, html, "", html_utf8=html_utf8, logger_instance=logger
        )

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

    id: int
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
    image_url: Optional[str] = None
    image_urls: List[str] = []
    product_url: str
    brand: Optional[str] = None
    part_number: Optional[str] = None
    adapter_used: str  # e.g. "a90shop", "studiorsr", "generic"
    inferred_category: Optional[str] = None  # category name slug, e.g. "exhaust", "suspension"
    archived: bool = True  # False when S3/local write failed; extension may warn the user
    html_size_bytes: int = 0
    html_sha256: str = ""
    archive_skipped_duplicate: bool = False


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
    html_sha256: Optional[str] = None


class ReparseResponse(BaseModel):
    crawled_page_id: int
    global_part_id: Optional[int]
    parse_status: str
    message: str


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
    html_utf8, html_size_bytes, html_sha256 = crawl_html_fingerprint(body.html)
    _enforce_max_crawl_html_size(
        html_size_bytes,
        user_id=current_user.id,
        url=url,
        content_length=request.headers.get("content-length"),
    )

    _, archived, skipped_dup = _persist_extension_crawl_archive(
        db,
        url=url,
        html=body.html,
        html_utf8=html_utf8,
        html_sha256=html_sha256,
        now=now,
    )
    if not archived:
        logger.warning("save_crawl_page_html returned None for %s; skipping DB upsert to avoid phantom row", url)

    # Select adapter by URL host, falling back to generic
    adapter_name = adapter_name_for_product_url(url)
    adapter = get_adapter(adapter_name)

    try:
        payload = adapter.parse_product_page(body.html, url)
    except Exception as exc:
        logger.warning("Adapter %s failed to parse %s: %s", adapter_name, url, exc)
        payload = None

    if payload is None:
        # Parser returned nothing useful — return empty fields so the user can fill manually
        logger.info("Adapter %s returned None for %s, returning empty ScrapeResponse", adapter_name, url)
        return ScrapeResponse(
            product_url=url,
            adapter_used=adapter_name,
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
        image_url=payload.image_url,
        image_urls=payload.image_urls or [],
        product_url=payload.product_url,
        brand=payload.brand,
        part_number=payload.part_number,
        adapter_used=adapter_name,
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
    html_utf8, html_size_bytes, html_sha256 = crawl_html_fingerprint(body.html)
    _enforce_max_crawl_html_size(
        html_size_bytes,
        user_id=current_user.id,
        url=url,
        content_length=request.headers.get("content-length"),
    )

    _, archived, skipped_dup = _persist_extension_crawl_archive(
        db,
        url=url,
        html=body.html,
        html_utf8=html_utf8,
        html_sha256=html_sha256,
        now=now,
    )

    if not archived:
        logger.warning("save_crawl_page_html returned None for %s; skipping DB upsert to avoid phantom row", url)
        page = db.query(DBCrawledPage).filter(DBCrawledPage.url == url).first()
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

    page = db.query(DBCrawledPage).filter(DBCrawledPage.url == url).first()
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
    from app.crawlers.archive_rescrape import rescrape_crawled_page_from_archive
    from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id

    page = db.get(DBCrawledPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="CrawledPage not found")

    if not page.html_s3_key and not page.html_local_path:
        raise HTTPException(
            status_code=404,
            detail="HTML not found in storage for this page. It may not have been archived yet.",
        )

    crawler_user = resolve_crawler_user(db)
    cat_id = resolve_default_category_id(db)

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
