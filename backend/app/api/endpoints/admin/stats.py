"""Admin statistics endpoints (table counts)."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_current_admin_user
from app.api.dependencies.repositories import Repositories, get_repositories
from app.api.utils.endpoint_decorators import standard_responses
from app.db.dynamo.users import User as DBUser

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
    repos: Repositories = Depends(get_repositories),
) -> Dict[str, Any]:
    """
    Admin-only: counts for internal tables not exposed elsewhere, plus votes/reports by entity_type.

    Totals come from scanning each table; these are small internal tables.
    """
    _ = current_user

    votes_by_entity_type = repos.votes.count_by_entity_type()
    reports_by_entity_type = repos.reports.count_by_entity_type()

    return {
        "build_list_phases": len(repos.build_list_phases.scan_all()),
        "part_listings": repos.part_listings.count(),
        "part_price_histories": repos.part_price_history.count(),
        "image_source_mappings": repos.image_source_mappings.count(),
        "build_logs": repos.build_logs.count(),
        "part_cars": repos.part_cars.count(),
        "oauth_accounts": repos.oauth_accounts.count(),
        "webauthn_credentials": repos.webauthn_credentials.count(),
        "votes_by_entity_type": votes_by_entity_type,
        "reports_by_entity_type": reports_by_entity_type,
    }
