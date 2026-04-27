"""
Pure read service that aggregates `PartPriceHistory` over a time window.

Two public functions:
- `aggregate_single_part(db, part_id, window)` — full per-retailer breakdown +
  listing-level history for one part (resolved across its canonical link group).
- `aggregate_batch(db, part_ids, window)` — min/max/last/trend per requested
  part_id, dedup'd by canonical link group, in a fixed number of round-trips
  regardless of batch size.

The service does NOT enforce a batch cap — that lives at the endpoint layer
(T03) so this stays reusable from S07 alert evaluation.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session

from app.api.models.part import Part as DBPart
from app.api.models.part_listing import PartListing as DBPartListing
from app.api.models.part_price_history import PartPriceHistory as DBPartPriceHistory
from app.api.models.retailer import Retailer as DBRetailer
from app.api.schemas.part_price_history import (
    PartPriceHistoryReadWithRetailer,
    PriceHistoryBatchSummaryItem,
    PriceHistorySinglePartResponse,
    PriceHistorySummary,
    PriceTrend,
    RetailerPriceBreakdown,
)
from app.api.services.part_linker_service import link_group_part_ids

_VALID_WINDOWS = {"7d", "30d", "90d", "180d", "1y", "all"}
ALLOWED_WINDOWS: list[str] = sorted(_VALID_WINDOWS)


def parse_window(window: str) -> Optional[datetime]:
    """Translate a window literal to the lower-bound `since` timestamp.

    Returns None for `all` (no lower bound). Raises ValueError on anything
    outside the whitelist — the endpoint layer turns this into HTTP 422.
    """
    if window not in _VALID_WINDOWS:
        raise ValueError(f"Invalid window {window!r}; expected one of {sorted(_VALID_WINDOWS)}")
    if window == "all":
        return None
    now = datetime.now(UTC)
    if window == "7d":
        return now - timedelta(days=7)
    if window == "30d":
        return now - timedelta(days=30)
    if window == "90d":
        return now - timedelta(days=90)
    if window == "180d":
        return now - timedelta(days=180)
    # window == "1y"
    return now - timedelta(days=365)


def _empty_summary() -> PriceHistorySummary:
    return PriceHistorySummary(
        min_cents=None,
        max_cents=None,
        last_cents=None,
        last_observed_at=None,
        trend="flat",
        observation_count=0,
    )


def _empty_batch_item() -> PriceHistoryBatchSummaryItem:
    return PriceHistoryBatchSummaryItem(
        min_cents=None,
        max_cents=None,
        last_cents=None,
        last_observed_at=None,
        trend="flat",
        observation_count=0,
    )


def _compute_trend(prices_chronological: list[int]) -> PriceTrend:
    """Linear-regression slope sign on a chronologically ordered price series.

    Threshold: |slope * n| (i.e. total expected drift across the window) compared
    to ±1% of the mean. With <2 observations or zero mean, trend is flat.
    """
    n = len(prices_chronological)
    if n < 2:
        return "flat"
    mean = statistics.fmean(prices_chronological)
    if mean == 0:
        return "flat"
    # x = 0, 1, 2, ... n-1 — uniform spacing is fine for slope-sign purposes; we
    # don't need real-time x-axis precision for an up/down/flat verdict.
    x_mean = (n - 1) / 2.0
    num = 0.0
    den = 0.0
    for i, y in enumerate(prices_chronological):
        dx = i - x_mean
        num += dx * (y - mean)
        den += dx * dx
    if den == 0:
        return "flat"
    slope = num / den
    drift = slope * (n - 1)  # total expected change across the window
    threshold = abs(mean) * 0.01
    if drift > threshold:
        return "up"
    if drift < -threshold:
        return "down"
    return "flat"


# --- Single-part aggregation -------------------------------------------------


def aggregate_single_part(
    db: Session,
    part_id: UUID,
    window: str,
) -> PriceHistorySinglePartResponse:
    """Aggregate price history for one part over the given window.

    Resolves the canonical link group via `link_group_part_ids` so that
    duplicates' listings count toward the canonical's history, mirroring the
    existing `/{part_id}/price-history` and `/{part_id}/best-listing` semantics.

    Empty-history cases return a well-formed empty payload (status 200 from the
    endpoint layer); 404 is the endpoint's call when the part itself is missing.
    """
    since = parse_window(window)
    group_ids = link_group_part_ids(db, part_id)

    # 1) Pull every history row in window, joined to listing + retailer.
    stmt = (
        select(DBPartPriceHistory, DBPartListing, DBRetailer)
        .join(DBPartListing, DBPartPriceHistory.part_listing_id == DBPartListing.id)
        .join(DBRetailer, DBPartListing.retailer_id == DBRetailer.id)
        .where(DBPartListing.part_id.in_(group_ids))
    )
    if since is not None:
        stmt = stmt.where(DBPartPriceHistory.observed_at >= since)
    stmt = stmt.order_by(DBPartPriceHistory.observed_at.desc())
    rows = db.execute(stmt).all()

    history: list[PartPriceHistoryReadWithRetailer] = [
        PartPriceHistoryReadWithRetailer(
            id=h.id,
            part_listing_id=h.part_listing_id,
            price_cents=h.price_cents,
            observed_at=h.observed_at,
            retailer_id=r.id,
            retailer_name=r.name,
        )
        for h, _l, r in rows
    ]

    # Most-recent observation per retailer from BEFORE the window — lets clients
    # anchor a carry-over point on the chart's y-axis so sparse windows don't
    # show stranded points. Pull rows DESC and keep the first per retailer.
    pre_window_anchors: list[PartPriceHistoryReadWithRetailer] = []
    if since is not None:
        anchor_stmt = (
            select(DBPartPriceHistory, DBPartListing, DBRetailer)
            .join(DBPartListing, DBPartPriceHistory.part_listing_id == DBPartListing.id)
            .join(DBRetailer, DBPartListing.retailer_id == DBRetailer.id)
            .where(DBPartListing.part_id.in_(group_ids))
            .where(DBPartPriceHistory.observed_at < since)
            .order_by(DBPartPriceHistory.observed_at.desc())
        )
        seen_retailers: set[UUID] = set()
        for h, _l, r in db.execute(anchor_stmt).all():
            if r.id in seen_retailers:
                continue
            seen_retailers.add(r.id)
            pre_window_anchors.append(
                PartPriceHistoryReadWithRetailer(
                    id=h.id,
                    part_listing_id=h.part_listing_id,
                    price_cents=h.price_cents,
                    observed_at=h.observed_at,
                    retailer_id=r.id,
                    retailer_name=r.name,
                )
            )

    if not rows:
        return PriceHistorySinglePartResponse(
            summary=_empty_summary(),
            retailers=[],
            history=[],
            pre_window_anchors=pre_window_anchors,
            window=window,
        )

    # Cross-retailer summary.
    all_prices = [h.price_cents for h, _l, _r in rows]
    # rows are observed_at DESC; reverse for chronological order to compute slope.
    chrono = list(reversed(all_prices))
    most_recent_h, _ml, _mr = rows[0]
    summary = PriceHistorySummary(
        min_cents=min(all_prices),
        max_cents=max(all_prices),
        last_cents=most_recent_h.price_cents,
        last_observed_at=most_recent_h.observed_at,
        trend=_compute_trend(chrono),
        observation_count=len(all_prices),
    )

    # Per-retailer breakdown.
    by_retailer: dict[UUID, list[tuple[DBPartPriceHistory, DBRetailer]]] = {}
    for h, _l, r in rows:
        by_retailer.setdefault(r.id, []).append((h, r))

    retailer_breakdowns: list[RetailerPriceBreakdown] = []
    for retailer_id, entries in by_retailer.items():
        retailer = entries[0][1]
        prices = [h.price_cents for h, _r in entries]
        # entries inherit the outer DESC order; entries[0] is most recent.
        most_recent = entries[0][0]
        retailer_breakdowns.append(
            RetailerPriceBreakdown(
                retailer_id=retailer_id,
                retailer_name=retailer.name,
                min_cents=min(prices),
                max_cents=max(prices),
                last_cents=most_recent.price_cents,
                last_observed_at=most_recent.observed_at,
                observation_count=len(prices),
            )
        )

    # Stable ordering: retailer_name ASC.
    retailer_breakdowns.sort(key=lambda b: b.retailer_name)

    return PriceHistorySinglePartResponse(
        summary=summary,
        retailers=retailer_breakdowns,
        history=history,
        pre_window_anchors=pre_window_anchors,
        window=window,
    )


def apply_retailer_filter(
    result: PriceHistorySinglePartResponse,
    retailer_id: UUID,
) -> PriceHistorySinglePartResponse:
    """Narrow a single-part aggregation to one retailer slice.

    Filters `history` to entries from the given retailer, keeps at most one
    matching `RetailerPriceBreakdown` in `retailers`, and recomputes `summary`
    from the filtered observations so `min/max/last/trend/observation_count`
    reflect the single-retailer view rather than the cross-retailer aggregate.
    Returns an empty-summary shape (status 200 from the endpoint) when no
    observations match.
    """
    filtered_history = [h for h in result.history if h.retailer_id == retailer_id]
    filtered_retailers = [r for r in result.retailers if r.retailer_id == retailer_id]
    filtered_anchors = [a for a in result.pre_window_anchors if a.retailer_id == retailer_id]

    if not filtered_history:
        return PriceHistorySinglePartResponse(
            summary=_empty_summary(),
            retailers=filtered_retailers,
            history=[],
            pre_window_anchors=filtered_anchors,
            window=result.window,
        )

    prices_desc = [h.price_cents for h in filtered_history]
    chrono = list(reversed(prices_desc))
    most_recent = filtered_history[0]
    summary = PriceHistorySummary(
        min_cents=min(prices_desc),
        max_cents=max(prices_desc),
        last_cents=most_recent.price_cents,
        last_observed_at=most_recent.observed_at,
        trend=_compute_trend(chrono),
        observation_count=len(prices_desc),
    )
    return PriceHistorySinglePartResponse(
        summary=summary,
        retailers=filtered_retailers,
        history=filtered_history,
        pre_window_anchors=filtered_anchors,
        window=result.window,
    )


# --- Batch aggregation -------------------------------------------------------


def aggregate_batch(
    db: Session,
    part_ids: list[UUID],
    window: str,
) -> dict[UUID, PriceHistoryBatchSummaryItem]:
    """Aggregate min/max/last/trend per part over the window.

    Always returns one entry per requested part_id — empty parts get the
    well-formed empty shape so the frontend can iterate without holes. Resolves
    canonical link groups in bulk and runs grouped aggregation queries to keep
    cost independent of batch size.
    """
    since = parse_window(window)

    if not part_ids:
        return {}

    # 1) Resolve every requested part_id to its canonical group in one pass.
    # We need: for each requested part_id, the canonical_id; for each canonical_id,
    # the full list of part_ids in that group (so a request for both A and its
    # duplicate B doesn't double-count).
    rows_self = db.execute(select(DBPart.id, DBPart.canonical_part_id).where(DBPart.id.in_(part_ids))).all()
    canonical_for_requested: dict[UUID, UUID] = {}
    requested_known: set[UUID] = set()
    for pid, canon in rows_self:
        requested_known.add(pid)
        canonical_for_requested[pid] = canon if canon is not None else pid

    canonical_ids = set(canonical_for_requested.values())
    # Pull every sibling that points at any of these canonicals so listings
    # in the link group can be aggregated under the canonical id.
    sibling_rows: Sequence[Row[tuple[UUID, UUID | None]]] = []
    if canonical_ids:
        sibling_rows = db.execute(
            select(DBPart.id, DBPart.canonical_part_id).where(DBPart.canonical_part_id.in_(canonical_ids))
        ).all()
    # Map every part-row in any group → its canonical id.
    part_to_canonical: dict[UUID, UUID] = {}
    for canon in canonical_ids:
        part_to_canonical[canon] = canon  # canonical maps to self
    for sib_id, sib_canon in sibling_rows:
        if sib_canon is not None:
            part_to_canonical[sib_id] = sib_canon

    # 2) Grouped min/max/count per canonical_id (single SELECT).
    canonical_id_expr = func.coalesce(DBPart.canonical_part_id, DBPart.id)
    minmax_stmt = (
        select(
            canonical_id_expr.label("canonical_id"),
            func.min(DBPartPriceHistory.price_cents).label("min_cents"),
            func.max(DBPartPriceHistory.price_cents).label("max_cents"),
            func.count(DBPartPriceHistory.id).label("cnt"),
        )
        .join(DBPartListing, DBPartListing.id == DBPartPriceHistory.part_listing_id)
        .join(DBPart, DBPart.id == DBPartListing.part_id)
        .where(canonical_id_expr.in_(canonical_ids))
        .group_by(canonical_id_expr)
    )
    if since is not None:
        minmax_stmt = minmax_stmt.where(DBPartPriceHistory.observed_at >= since)
    minmax_rows = db.execute(minmax_stmt).all() if canonical_ids else []
    minmax_by_canonical: dict[UUID, tuple[Optional[int], Optional[int], int]] = {
        row.canonical_id: (row.min_cents, row.max_cents, int(row.cnt or 0)) for row in minmax_rows
    }

    # 3) Pull all in-window observations (price + observed_at) per canonical so we
    # can compute `last_cents`/`last_observed_at` and the trend slope without an
    # N+1 fan-out. One SELECT bounded by `canonical_id_expr.in_(canonical_ids)`.
    obs_rows: Sequence[Row[tuple[UUID, int, datetime]]] = []
    if canonical_ids:
        obs_stmt = (
            select(
                canonical_id_expr.label("canonical_id"),
                DBPartPriceHistory.price_cents,
                DBPartPriceHistory.observed_at,
            )
            .join(DBPartListing, DBPartListing.id == DBPartPriceHistory.part_listing_id)
            .join(DBPart, DBPart.id == DBPartListing.part_id)
            .where(canonical_id_expr.in_(canonical_ids))
        )
        if since is not None:
            obs_stmt = obs_stmt.where(DBPartPriceHistory.observed_at >= since)
        obs_stmt = obs_stmt.order_by(DBPartPriceHistory.observed_at.asc())
        obs_rows = db.execute(obs_stmt).all()

    obs_by_canonical: dict[UUID, list[tuple[int, datetime]]] = {}
    for canon_id, price, observed_at in obs_rows:
        obs_by_canonical.setdefault(canon_id, []).append((price, observed_at))

    # 4) Build the per-requested-part response. Multiple requested IDs that share
    # a canonical group resolve to the SAME aggregated value (no double-count).
    result: dict[UUID, PriceHistoryBatchSummaryItem] = {}
    for pid in part_ids:
        if pid not in requested_known:
            # Unknown part — return empty-summary entry (don't 404 here).
            result[pid] = _empty_batch_item()
            continue
        canon_id = canonical_for_requested[pid]
        minmax = minmax_by_canonical.get(canon_id)
        observations = obs_by_canonical.get(canon_id, [])
        if not observations or minmax is None or minmax[2] == 0:
            result[pid] = _empty_batch_item()
            continue
        min_cents, max_cents, count = minmax
        prices_chrono = [p for p, _ts in observations]
        last_price, last_ts = observations[-1]
        result[pid] = PriceHistoryBatchSummaryItem(
            min_cents=min_cents,
            max_cents=max_cents,
            last_cents=last_price,
            last_observed_at=last_ts,
            trend=_compute_trend(prices_chrono),
            observation_count=count,
        )
    return result
