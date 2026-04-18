"""
Re-parse archived HTML: full ingest (part create/update, inference, listing, price history).

Used by admin batch "rescrape archives" and by POST /crawled-pages/{id}/re-parse.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional  # Optional still used for load_archived_html return
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.user import User as DBUser
from app.crawlers.adapters import ADAPTER_REGISTRY, adapter_name_for_product_url, get_adapter
from app.crawlers.base import (
    crawl_html_fingerprint,
    get_crawl_s3_client,
    ingest_payload,
    save_crawl_page_html,
)

RescrapeOutcome = Literal[
    "parsed_ok",
    "parse_failed",
    "ingest_failed",
    "skipped_no_adapter",
    "skipped_no_html",
]


def load_archived_html(page: DBCrawledPage, log: logging.Logger) -> Optional[str]:
    """Load raw HTML for a crawled page from S3 or local path."""
    html: Optional[str] = None
    if page.html_s3_key:
        s3_client, bucket_name = get_crawl_s3_client()
        if s3_client is not None and bucket_name is not None:
            try:
                obj = s3_client.get_object(Bucket=bucket_name, Key=page.html_s3_key)
                html = obj["Body"].read().decode("utf-8", errors="replace")
            except Exception as e:
                log.warning("Could not fetch HTML from S3 key %s: %s", page.html_s3_key, e)
    if html is None and page.html_local_path:
        try:
            html = Path(page.html_local_path).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            log.warning("Could not read local HTML %s: %s", page.html_local_path, e)
    return html


def resolve_parse_adapter_name(page: DBCrawledPage) -> str:
    """
    Adapter key to parse this page's HTML.

    Returns a site-specific adapter when one is registered for the source or URL,
    otherwise falls back to ``"generic"`` so every archived page can be re-parsed.
    """
    if page.source in ADAPTER_REGISTRY:
        return page.source
    # For chrome_extension and any other source, pick by URL (always returns a key)
    return adapter_name_for_product_url(page.url)


def rescrape_crawled_page_from_archive(
    db: Session,
    page: DBCrawledPage,
    *,
    crawler_user: DBUser,
    default_category_id: UUID,
    log: logging.Logger,
) -> tuple[RescrapeOutcome, Optional[UUID], Optional[str]]:
    """
    Fetch archived HTML, parse with the right adapter, ingest (including price history).

    Returns (outcome, part_id if parsed_ok else None, error detail for ingest failures).
    Commits on each terminal path (same as legacy re-parse + ingest_payload commits).
    """
    adapter_key = resolve_parse_adapter_name(page)
    html = load_archived_html(page, log)
    if not html:
        return "skipped_no_html", None, None

    html_utf8, _, html_sha = crawl_html_fingerprint(html)

    adapter = get_adapter(adapter_key)
    payload = adapter.parse_product_page(html, page.url)
    now = datetime.now(timezone.utc)

    if payload is None:
        page.parse_status = "failed"
        page.last_parsed_at = now
        db.commit()
        return "parse_failed", None, None

    try:
        part = ingest_payload(
            db,
            payload,
            current_user=crawler_user,
            default_category_id=default_category_id,
            logger=log,
            source="archive_rescrape",
        )
    except Exception as e:
        db.rollback()
        row = db.get(DBCrawledPage, page.id)
        if row is not None:
            row.parse_status = "failed"
            row.last_parsed_at = now
            db.commit()
        return "ingest_failed", None, str(e)

    db.refresh(page)

    # Only re-save HTML when the page was loaded from local disk (migrate to S3) or has no key at
    # all. Skip the put_object round-trip when the HTML was just fetched from html_s3_key — it is
    # already there and writing the same bytes back wastes S3 PUT quota.
    if not page.html_s3_key:
        storage_key = save_crawl_page_html(
            adapter_key,
            page.url,
            html,
            "",
            html_utf8=html_utf8,
            logger_instance=log,
        )
        if storage_key:
            if storage_key.startswith("/"):
                page.html_local_path = storage_key
                page.html_s3_key = None
            else:
                page.html_s3_key = storage_key
                page.html_local_path = None

    page.html_sha256 = html_sha
    page.part_id = part.id
    page.parse_status = "parsed"
    page.last_parsed_at = now
    db.commit()
    return "parsed_ok", part.id, None


def run_rescrape_all_archived_pages(
    db: Session,
    *,
    crawler_user: DBUser,
    default_category_id: UUID,
    log: logging.Logger,
    stop_event: Optional[threading.Event] = None,
) -> dict[str, int]:
    """
    Re-parse every crawled page that has archived HTML (S3 or local).

    ``ingest_payload`` records listing and price history when the parsed payload includes a price.
    If stop_event is provided and set, the loop exits early (cooperative cancellation).
    """
    counts: dict[str, int] = {
        "parsed_ok": 0,
        "parse_failed": 0,
        "ingest_failed": 0,
        "skipped_no_adapter": 0,
        "skipped_no_html": 0,
    }
    q = (
        db.query(DBCrawledPage)
        .filter(
            or_(
                DBCrawledPage.html_s3_key.isnot(None),
                DBCrawledPage.html_local_path.isnot(None),
            )
        )
        .order_by(DBCrawledPage.id)
    )
    for page in q:
        if stop_event is not None and stop_event.is_set():
            log.info("Archive rescrape: stop requested, exiting early.")
            break
        outcome, _, _ = rescrape_crawled_page_from_archive(
            db,
            page,
            crawler_user=crawler_user,
            default_category_id=default_category_id,
            log=log,
        )
        counts[outcome] += 1
    return counts
