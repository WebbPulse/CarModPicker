"""Admin extraction-health endpoint (M002/S04 T02).

Returns a single JSON document with three sections — compliance, coverage,
failure-rate — all derivable from authoritative DB state. The failure-rate
signal is sourced from ``crawled_pages.parse_status`` over a rolling 7-day
window rather than the CloudWatch ``ExtractionFailureRate`` EMF stream
(see decision D008): both ``runner.py`` and ``archive_rescrape.py`` write
``parse_status='failed'`` whenever ingest fails, so the DB row is the same
authoritative state without an IAM/network dependency, and it works in dev
and tests where EMF is suppressed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.models.crawled_page import CrawledPage as DBCrawledPage
from app.api.models.part import Part as DBPart
from app.api.models.user import User as DBUser
from app.api.utils.endpoint_decorators import standard_responses
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.adapters.base import UNIVERSAL_FIELD_NAMES
from app.crawlers.compliance_audit import classify_tier, is_compliant
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

#: Hard-coded rolling window for the failure-rate computation. Exposed in
#: the response under ``window`` so the frontend doesn't have to assume.
WINDOW_DAYS = 7

#: Canonical tier order — drives the compliance + coverage payloads.
_TIER_KEYS: tuple[str, ...] = ("http", "tls", "browser")


class CoverageTierBlock(BaseModel):
    parts_with_specs: int
    parts_total: int
    per_field: Dict[str, float]


class CoverageBlock(BaseModel):
    per_tier: Dict[str, CoverageTierBlock]


class ComplianceBlock(BaseModel):
    compliant: int
    total: int
    per_tier: Dict[str, str]


class FailureRateRow(BaseModel):
    adapter: str
    failed: int
    parsed: int
    rate: float
    tier: str


class WindowMeta(BaseModel):
    days: int
    since: str


class ExtractionHealthResponse(BaseModel):
    compliance: ComplianceBlock
    coverage: CoverageBlock
    failure_rate_7d: List[FailureRateRow] = Field(default_factory=list)
    window: WindowMeta


def _empty_specs_or_null():
    """SQLAlchemy clause matching parts whose ``specifications`` JSON is unset.

    Same three-shape match as ``app.crawlers.backfill._empty_specs_filter`` —
    SQL NULL, JSON null literal, JSON empty dict — but inverted callers
    (``isnot_empty``) compose it via ``~``. Keeping the helper local rather
    than importing from ``backfill`` keeps the slice scope tight and avoids
    pulling crawler-runtime imports into the FastAPI request path.
    """
    cast_specs = cast(DBPart.specifications, String)
    return (
        DBPart.specifications.is_(None)
        | (cast_specs == "{}")
        | (cast_specs == "null")
    )


def _field_present_count(
    db: Session,
    field_name: str,
    tier_sources: list[str],
) -> int:
    """Count distinct parts in ``tier_sources`` whose specifications JSON contains ``field_name``.

    Dialect-aware: SQLite uses ``json_extract``; PostgreSQL uses the ``->``
    operator via SQLAlchemy's ``[...]`` accessor. ``field_name`` is sourced
    from the immutable ``UNIVERSAL_FIELD_NAMES`` frozenset (never user input),
    but we still bind the value through SQLAlchemy's parameterized expression
    machinery rather than string-interpolating into the SQL — defense in depth
    in case the caller graph ever widens.
    """
    if not tier_sources:
        return 0

    dialect = db.bind.dialect.name if db.bind is not None else None

    if dialect == "sqlite":
        path = "$." + field_name
        json_value = func.json_extract(DBPart.specifications, path)
        present_clause = json_value.isnot(None)
    elif dialect in ("postgresql", "postgres"):
        # `Part.specifications[field_name]` produces an `->` subscript whose
        # value is `JSON null` for missing keys; isnot(None) on the resulting
        # JSON-typed expression matches present-and-not-null entries.
        present_clause = DBPart.specifications[field_name].isnot(None)
    else:
        raise NotImplementedError(
            f"_field_present_count: unsupported dialect {dialect!r}"
        )

    stmt = (
        select(func.count(func.distinct(DBPart.id)))
        .join(DBCrawledPage, DBCrawledPage.part_id == DBPart.id)
        .where(DBCrawledPage.source.in_(tier_sources))
        .where(DBPart.specifications.isnot(None))
        .where(~_empty_specs_or_null())
        .where(present_clause)
    )
    return int(db.execute(stmt).scalar_one() or 0)


def _compute_compliance() -> ComplianceBlock:
    """Tally compliance per tier directly from ``ADAPTER_REGISTRY``.

    Mirrors the inline counting in ``compliance_audit.audit()`` so the
    endpoint and the script stay aligned. Per-tier render uses the
    ``"<n>/<n>"`` shape that matches the audit's stdout block.
    """
    per_tier_counts: Dict[str, tuple[int, int]] = {k: (0, 0) for k in _TIER_KEYS}
    total_compliant = 0
    total_count = 0

    for _slug, cls in ADAPTER_REGISTRY.items():
        tier = classify_tier(cls)
        if tier not in per_tier_counts:
            # Defensive: a future fetcher tier shouldn't crash the endpoint.
            per_tier_counts[tier] = (0, 0)
        compliant, total = per_tier_counts[tier]
        total += 1
        if is_compliant(cls):
            compliant += 1
            total_compliant += 1
        total_count += 1
        per_tier_counts[tier] = (compliant, total)

    per_tier_str = {
        tier: f"{compliant}/{total}"
        for tier, (compliant, total) in per_tier_counts.items()
    }

    return ComplianceBlock(
        compliant=total_compliant,
        total=total_count,
        per_tier=per_tier_str,
    )


def _adapter_slugs_by_tier() -> Dict[str, list[str]]:
    """Group ``ADAPTER_REGISTRY`` slugs by their fetcher tier."""
    by_tier: Dict[str, list[str]] = {k: [] for k in _TIER_KEYS}
    for slug, cls in ADAPTER_REGISTRY.items():
        tier = classify_tier(cls)
        by_tier.setdefault(tier, []).append(slug)
    return by_tier


def _compute_coverage(db: Session) -> CoverageBlock:
    """Compute per-tier coverage gradient over ``Part.specifications``."""
    slugs_by_tier = _adapter_slugs_by_tier()
    per_tier: Dict[str, CoverageTierBlock] = {}

    for tier in _TIER_KEYS:
        sources = slugs_by_tier.get(tier, [])
        if not sources:
            per_tier[tier] = CoverageTierBlock(
                parts_with_specs=0,
                parts_total=0,
                per_field={field: 0.0 for field in sorted(UNIVERSAL_FIELD_NAMES)},
            )
            continue

        parts_total_stmt = (
            select(func.count(func.distinct(DBPart.id)))
            .join(DBCrawledPage, DBCrawledPage.part_id == DBPart.id)
            .where(DBCrawledPage.source.in_(sources))
        )
        parts_total = int(db.execute(parts_total_stmt).scalar_one() or 0)

        parts_with_specs_stmt = (
            select(func.count(func.distinct(DBPart.id)))
            .join(DBCrawledPage, DBCrawledPage.part_id == DBPart.id)
            .where(DBCrawledPage.source.in_(sources))
            .where(DBPart.specifications.isnot(None))
            .where(~_empty_specs_or_null())
        )
        parts_with_specs = int(db.execute(parts_with_specs_stmt).scalar_one() or 0)

        per_field: Dict[str, float] = {}
        for field in sorted(UNIVERSAL_FIELD_NAMES):
            count = _field_present_count(db, field, sources)
            per_field[field] = (count / parts_total) if parts_total > 0 else 0.0

        per_tier[tier] = CoverageTierBlock(
            parts_with_specs=parts_with_specs,
            parts_total=parts_total,
            per_field=per_field,
        )

    return CoverageBlock(per_tier=per_tier)


def _compute_failure_rate_7d(db: Session, since: datetime) -> List[FailureRateRow]:
    """Group ``crawled_pages`` by source over the last 7 days for parsed/failed counts.

    Skips rows whose ``last_parsed_at`` is NULL (never parsed → not in window)
    and rows whose ``source`` is not in ``ADAPTER_REGISTRY`` (defensive — a
    removed adapter shouldn't show up in the response). ``rate`` is computed
    defensively (``0.0`` when denominator is zero).
    """
    stmt = (
        select(
            DBCrawledPage.source,
            DBCrawledPage.parse_status,
            func.count(DBCrawledPage.id),
        )
        .where(DBCrawledPage.last_parsed_at.isnot(None))
        .where(DBCrawledPage.last_parsed_at >= since)
        .where(DBCrawledPage.parse_status.in_(("parsed", "failed")))
        .group_by(DBCrawledPage.source, DBCrawledPage.parse_status)
    )

    counts: Dict[str, Dict[str, int]] = {}
    for source, parse_status, count in db.execute(stmt).all():
        if source not in ADAPTER_REGISTRY:
            continue
        bucket = counts.setdefault(source, {"parsed": 0, "failed": 0})
        bucket[str(parse_status)] = int(count)

    rows: List[FailureRateRow] = []
    for source in sorted(counts.keys()):
        bucket = counts[source]
        failed = bucket.get("failed", 0)
        parsed = bucket.get("parsed", 0)
        denom = failed + parsed
        rate = (failed / denom) if denom > 0 else 0.0
        tier = classify_tier(ADAPTER_REGISTRY[source])
        rows.append(
            FailureRateRow(
                adapter=source,
                failed=failed,
                parsed=parsed,
                rate=rate,
                tier=tier,
            )
        )
    return rows


@router.get(
    "/",
    response_model=ExtractionHealthResponse,
    responses=standard_responses(
        success_description="Extraction health snapshot (compliance + coverage + failure-rate)",
        forbidden=True,
        unauthorized=True,
    ),
)
async def get_extraction_health(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Return compliance + coverage + 7-day failure-rate (admin only).

    Implementation note: per MEM037, the canonical adapter count is 108
    (T0:83 / T1:15 / T2:10) — the IS_FALLBACK ``GenericHtmlParser`` instances
    are excluded from ``ADAPTER_REGISTRY`` per D-03 and therefore from the
    compliance tally. Failure-rate is sourced from ``crawled_pages.parse_status``
    rather than CloudWatch (D008).
    """
    _ = current_user  # Auth dependency only — exists to enforce the gate.

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    compliance = _compute_compliance()
    coverage = _compute_coverage(db)
    failure_rate = _compute_failure_rate_7d(db, since)

    return {
        "compliance": compliance.model_dump(),
        "coverage": coverage.model_dump(),
        "failure_rate_7d": [row.model_dump() for row in failure_rate],
        "window": {"days": WINDOW_DAYS, "since": since.isoformat()},
    }
