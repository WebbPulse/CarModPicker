"""Admin statistics endpoints (table counts, crawl bucket listing)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.associations.crawler_schedule_adapter import CrawlerScheduleAdapter as DBCrawlerScheduleAdapter
from app.api.models.associations.part_car import part_cars
from app.api.models.background_job import BackgroundJob as DBBackgroundJob
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.models.build_log import BuildLog as DBBuildLog
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.crawler_adapter_config import CrawlerAdapterConfig as DBCrawlerAdapterConfig
from app.api.models.crawler_schedule import CrawlerSchedule as DBCrawlerSchedule
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.models.oauth_account import OAuthAccount as DBOAuthAccount
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.report import Report as DBReport
from app.api.models.user import User as DBUser
from app.api.models.vote import Vote as DBVote
from app.api.models.webauthn_credential import WebAuthnCredential as DBWebAuthnCredential
from app.api.utils.approximate_count import approximate_count
from app.api.utils.endpoint_decorators import standard_responses
from app.api.services.crawl_archive import count_crawl_bucket_object_summary
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/table-counts",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Supplemental table and polymorphic vote/report counts",
        forbidden=True,
    ),
)
async def get_admin_table_counts(
    current_user: DBUser = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Admin-only: counts for internal tables not exposed elsewhere, plus votes/reports by entity_type.

    Table totals are approximate (pg_class.reltuples) so this stays O(1) even on large
    tables; exact counts are used on SQLite/tests. For the crawl bucket summary see
    ``GET /admin/stats/crawl-bucket`` — that one does a full S3 list and is therefore
    on-demand rather than part of this response.
    """
    _ = current_user

    vote_rows = db.execute(select(DBVote.entity_type, func.count(DBVote.id)).group_by(DBVote.entity_type)).all()
    votes_by_entity_type = {str(row[0]): int(row[1]) for row in vote_rows}

    report_rows = db.execute(select(DBReport.entity_type, func.count(DBReport.id)).group_by(DBReport.entity_type)).all()
    reports_by_entity_type = {str(row[0]): int(row[1]) for row in report_rows}

    return {
        "build_list_phases": approximate_count(db, DBBuildListPhase),
        "crawled_pages": approximate_count(db, DBCrawledPage),
        "part_listings": approximate_count(db, DBPartListing),
        "part_price_histories": approximate_count(db, DBPartPriceHistory),
        "image_source_mappings": approximate_count(db, DBImageSourceMapping),
        "build_logs": approximate_count(db, DBBuildLog),
        "part_cars": approximate_count(db, part_cars),
        "background_jobs": approximate_count(db, DBBackgroundJob),
        "oauth_accounts": approximate_count(db, DBOAuthAccount),
        "webauthn_credentials": approximate_count(db, DBWebAuthnCredential),
        "crawler_adapter_configs": approximate_count(db, DBCrawlerAdapterConfig),
        "crawler_schedules": approximate_count(db, DBCrawlerSchedule),
        "crawler_schedule_adapters": approximate_count(db, DBCrawlerScheduleAdapter),
        "votes_by_entity_type": votes_by_entity_type,
        "reports_by_entity_type": reports_by_entity_type,
    }


@router.get(
    "/crawl-bucket",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Full S3 list of CRAWL_BUCKET — on-demand because it scans every key",
        forbidden=True,
    ),
)
async def get_admin_crawl_bucket_summary(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Admin-only: full object listing of the crawl HTML bucket.

    This performs a paginated S3 ``list_objects_v2`` over the entire bucket on every
    call, which can take seconds on large archives. It is intentionally not folded
    into the dashboard's main stats payload — the admin triggers it manually when
    they actually want the number.
    """
    _ = current_user
    return count_crawl_bucket_object_summary()
