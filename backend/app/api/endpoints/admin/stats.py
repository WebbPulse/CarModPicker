"""Admin statistics endpoints (table counts)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.associations.part_car import part_cars
from app.api.models.build_list_phase import BuildListPhase as DBBuildListPhase
from app.api.models.build_log import BuildLog as DBBuildLog
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
    tables; exact counts are used on SQLite/tests.
    """
    _ = current_user

    vote_rows = db.execute(select(DBVote.entity_type, func.count(DBVote.id)).group_by(DBVote.entity_type)).all()
    votes_by_entity_type = {str(row[0]): int(row[1]) for row in vote_rows}

    report_rows = db.execute(select(DBReport.entity_type, func.count(DBReport.id)).group_by(DBReport.entity_type)).all()
    reports_by_entity_type = {str(row[0]): int(row[1]) for row in report_rows}

    return {
        "build_list_phases": approximate_count(db, DBBuildListPhase),
        "part_listings": approximate_count(db, DBPartListing),
        "part_price_histories": approximate_count(db, DBPartPriceHistory),
        "image_source_mappings": approximate_count(db, DBImageSourceMapping),
        "build_logs": approximate_count(db, DBBuildLog),
        "part_cars": approximate_count(db, part_cars),
        "oauth_accounts": approximate_count(db, DBOAuthAccount),
        "webauthn_credentials": approximate_count(db, DBWebAuthnCredential),
        "votes_by_entity_type": votes_by_entity_type,
        "reports_by_entity_type": reports_by_entity_type,
    }
