"""Admin statistics endpoints (table counts)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.models.image_source_mapping import ImageSourceMapping as DBImageSourceMapping
from app.api.utils.approximate_count import approximate_count
from app.api.utils.endpoint_decorators import standard_responses
from app.db.dynamo.users import User as DBUser
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
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Any]:
    """
    Admin-only: counts for internal tables not exposed elsewhere, plus votes/reports by entity_type.

    SQL table totals are approximate (pg_class.reltuples) so this stays O(1) even on large
    tables; exact counts are used on SQLite/tests. DynamoDB table totals come from the
    table's item count.
    """
    _ = current_user

    votes_by_entity_type = repos.votes.count_by_entity_type()
    reports_by_entity_type = repos.reports.count_by_entity_type()

    return {
        "build_list_phases": len(repos.build_list_phases.scan_all()),
        "part_listings": repos.part_listings.count(),
        "part_price_histories": repos.part_price_history.count(),
        "image_source_mappings": approximate_count(db, DBImageSourceMapping),
        "build_logs": repos.build_logs.count(),
        "part_cars": repos.part_cars.count(),
        "oauth_accounts": repos.oauth_accounts.count(),
        "webauthn_credentials": repos.webauthn_credentials.count(),
        "votes_by_entity_type": votes_by_entity_type,
        "reports_by_entity_type": reports_by_entity_type,
    }
