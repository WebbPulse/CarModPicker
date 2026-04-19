"""
Crawler schedule reconciliation service.

The DB tables ``crawler_schedules`` (and their membership join) are the source
of truth. This module reconciles each row to a corresponding EventBridge
Scheduler schedule named ``{prefix}-crawler-sched-{schedule.name}``.

Target.Input is intentionally minimal — just ``{"schedule_id": "<uuid>"}``.
The run endpoint dereferences members and per-adapter configs at firing time,
so membership edits and config tuning don't require an AWS reconcile; only
``enabled`` and ``schedule_expression`` changes do.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.api.models.crawler_schedule import CrawlerSchedule
from app.core.config import settings

logger = logging.getLogger(__name__)

CRON_PRESETS: Dict[str, str] = {
    "monthly": "cron(0 2 1 * ? *)",
    "weekly": "cron(0 2 ? * MON *)",
    "daily": "cron(0 2 * * ? *)",
}


class AwsSchedulerUnavailable(RuntimeError):
    """Raised when EventBridge Scheduler plumbing is not configured."""


def resolve_preset_or_expression(
    *,
    preset: Optional[str],
    expression: Optional[str],
    current: Optional[str] = None,
) -> Optional[str]:
    """
    Return the expression to use given a preset/expression pair from the body
    and the current expression. ``preset`` takes priority. Returns ``current``
    when neither is supplied (no change). Raises ``ValueError`` for unknown
    presets.
    """
    if preset is not None:
        if preset not in CRON_PRESETS:
            raise ValueError(f"Unknown preset '{preset}'. Available: {list(CRON_PRESETS)}")
        return CRON_PRESETS[preset]
    if expression is not None:
        return expression
    return current


def preset_name_for_expression(expression: str) -> str:
    """Return the matching preset key for an expression, or 'custom' if none match."""
    for name, expr in CRON_PRESETS.items():
        if expr == expression:
            return name
    return "custom"


def _prefix() -> str:
    """Return the deployment prefix (e.g. ``carmodpicker-production``)."""
    base = settings.scheduler_crawler_schedule_name
    if base.endswith("-crawler-run"):
        return base[: -len("-crawler-run")]
    return base


def schedule_name_for(schedule_name: str) -> str:
    """Full EventBridge Scheduler schedule name for a ``CrawlerSchedule.name``."""
    return f"{_prefix()}-crawler-sched-{schedule_name}"


def _get_scheduler_client() -> Any:
    return boto3.client("scheduler", region_name=settings.AWS_REGION)


def _require_target_config() -> tuple[str, str]:
    bus = settings.SCHEDULER_TARGET_EVENT_BUS_ARN
    role = settings.SCHEDULER_TARGET_ROLE_ARN
    if not bus or not role:
        raise AwsSchedulerUnavailable(
            "Scheduler not configured. SCHEDULER_TARGET_EVENT_BUS_ARN and SCHEDULER_TARGET_ROLE_ARN must be set."
        )
    return bus, role


def _build_target(schedule_id: str) -> Dict[str, Any]:
    """Build the Target payload. Input carries only the schedule id; the run
    endpoint dereferences the rest at firing time."""
    bus_arn, role_arn = _require_target_config()
    return {
        "Arn": bus_arn,
        "RoleArn": role_arn,
        "Input": json.dumps({"schedule_id": schedule_id}),
        "EventBridgeParameters": {
            "DetailType": "crawler-run",
            "Source": "carmodpicker.scheduler",
        },
        "RetryPolicy": {
            "MaximumRetryAttempts": 1,
            "MaximumEventAgeInSeconds": 3600,
        },
    }


def reconcile_schedule(db: Session, row: CrawlerSchedule) -> None:
    """
    Push ``row`` to EventBridge Scheduler (create or update). On success stamps
    ``last_reconciled_at``; on failure stores ``last_reconcile_error`` and
    re-raises.
    """
    name = schedule_name_for(row.name)
    group = settings.SCHEDULER_GROUP_NAME
    state = "ENABLED" if row.enabled else "DISABLED"

    try:
        target = _build_target(str(row.id))
        client = _get_scheduler_client()
        try:
            client.get_schedule(Name=name, GroupName=group)
            exists = True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code", "") == "ResourceNotFoundException":
                exists = False
            else:
                raise

        if exists:
            client.update_schedule(
                Name=name,
                GroupName=group,
                ScheduleExpression=row.schedule_expression,
                ScheduleExpressionTimezone="UTC",
                State=state,
                FlexibleTimeWindow={"Mode": "OFF"},
                Target=target,
            )
        else:
            client.create_schedule(
                Name=name,
                GroupName=group,
                ScheduleExpression=row.schedule_expression,
                ScheduleExpressionTimezone="UTC",
                State=state,
                FlexibleTimeWindow={"Mode": "OFF"},
                Target=target,
                Description=row.description or f"CarModPicker crawler schedule '{row.name}'",
            )
    except (ClientError, BotoCoreError, AwsSchedulerUnavailable) as e:
        row.last_reconcile_error = str(e)
        db.add(row)
        db.commit()
        logger.exception("Failed to reconcile crawler schedule %s: %s", row.name, e)
        raise

    row.last_reconciled_at = datetime.now(UTC)
    row.last_reconcile_error = None
    db.add(row)
    db.commit()
    logger.info(
        "Reconciled crawler schedule: name=%s state=%s expression=%s",
        row.name,
        state,
        row.schedule_expression,
    )


def delete_schedule(schedule_name: str) -> None:
    """
    Delete the AWS schedule for ``schedule_name`` if it exists. Idempotent —
    ResourceNotFoundException is treated as success.
    """
    name = schedule_name_for(schedule_name)
    group = settings.SCHEDULER_GROUP_NAME
    try:
        client = _get_scheduler_client()
        client.delete_schedule(Name=name, GroupName=group)
        logger.info("Deleted crawler schedule: %s", name)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code", "") == "ResourceNotFoundException":
            return
        raise


def reconcile_all(db: Session) -> list[dict[str, Any]]:
    """Reconcile every schedule row. Returns per-row results."""
    rows = db.query(CrawlerSchedule).order_by(CrawlerSchedule.name).all()
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            reconcile_schedule(db, row)
            results.append({"schedule_name": row.name, "ok": True, "error": None})
        except Exception as e:
            results.append({"schedule_name": row.name, "ok": False, "error": str(e)})
    return results


def sweep_orphan_schedules(db: Session) -> list[str]:
    """
    Delete EventBridge schedules under our prefix that don't correspond to a
    live ``crawler_schedules`` row. Also cleans up any legacy per-adapter
    schedules from the previous implementation. Best-effort; returns the list
    of names that were deleted.

    Relies on the IAM ``scheduler:ListSchedules`` permission granted in
    Terraform.
    """
    prefix = _prefix()
    our_prefix = f"{prefix}-crawler-"
    group = settings.SCHEDULER_GROUP_NAME
    live_names = {schedule_name_for(r.name) for r in db.query(CrawlerSchedule.name).all()}

    deleted: list[str] = []
    try:
        client = _get_scheduler_client()
        next_token: Optional[str] = None
        while True:
            kwargs: Dict[str, Any] = {
                "GroupName": group,
                "NamePrefix": our_prefix,
                "MaxResults": 100,
            }
            if next_token:
                kwargs["NextToken"] = next_token
            resp = client.list_schedules(**kwargs)
            for item in resp.get("Schedules", []):
                name = item.get("Name", "")
                if not name.startswith(our_prefix):
                    continue
                if name in live_names:
                    continue
                try:
                    client.delete_schedule(Name=name, GroupName=group)
                    deleted.append(name)
                    logger.info("Swept orphan schedule: %s", name)
                except ClientError as e:
                    if e.response.get("Error", {}).get("Code", "") == "ResourceNotFoundException":
                        continue
                    logger.warning("Failed to delete orphan schedule %s: %s", name, e)
            next_token = resp.get("NextToken")
            if not next_token:
                break
    except (ClientError, BotoCoreError) as e:
        logger.warning("Orphan sweep failed (non-fatal): %s", e)
    return deleted
