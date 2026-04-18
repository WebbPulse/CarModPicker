"""
Per-adapter crawler schedule service.

The DB table ``adapter_schedules`` is the source of truth for crawler
scheduling. This module reconciles each row to a corresponding
EventBridge Scheduler schedule named ``{prefix}-crawler-{adapter_name}``
in ``settings.SCHEDULER_GROUP_NAME``.

The schedule target is the shared ``carmodpicker.scheduler`` event bus (wired
in Terraform to an API Destination → App Runner POST /admin/crawlers/run). The
per-adapter payload is the schedule's ``Target.Input`` JSON.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.api.models.adapter_schedule import AdapterSchedule
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
    current: str,
) -> str:
    """
    Given a preset/expression pair from a PATCH body and the current expression,
    return the new expression. ``preset`` takes priority when both are set.
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


def _schedule_name_for(adapter_name: str) -> str:
    """Return the fully qualified EventBridge Scheduler name for an adapter."""
    base = settings.scheduler_crawler_schedule_name
    if base.endswith("-crawler-run"):
        prefix = base[: -len("-crawler-run")]
    else:
        prefix = base
    return f"{prefix}-crawler-{adapter_name}"


def _get_scheduler_client() -> Any:
    return boto3.client("scheduler", region_name=settings.AWS_REGION)


def _require_target_config() -> tuple[str, str]:
    """Return (event_bus_arn, scheduler_role_arn); raise if missing."""
    bus = settings.SCHEDULER_TARGET_EVENT_BUS_ARN
    role = settings.SCHEDULER_TARGET_ROLE_ARN
    if not bus or not role:
        raise AwsSchedulerUnavailable(
            "Scheduler not configured. SCHEDULER_TARGET_EVENT_BUS_ARN and " "SCHEDULER_TARGET_ROLE_ARN must be set."
        )
    return bus, role


def _build_target(row: AdapterSchedule) -> Dict[str, Any]:
    """Build the Target payload for create/update_schedule from a row."""
    bus_arn, role_arn = _require_target_config()

    payload: Dict[str, Any] = {
        "adapters": [row.adapter_name],
        "crawler_default_category_id": str(row.default_category_id),
        "parallel": False,
        "delay_sec": row.delay_sec,
        "skip_known_urls": row.skip_known_urls,
    }
    if row.per_run_limit is not None:
        payload["global_limit"] = row.per_run_limit

    return {
        "Arn": bus_arn,
        "RoleArn": role_arn,
        "Input": json.dumps(payload),
        "EventBridgeParameters": {
            "DetailType": "crawler-run",
            "Source": "carmodpicker.scheduler",
        },
        "RetryPolicy": {
            "MaximumRetryAttempts": 1,
            "MaximumEventAgeInSeconds": 3600,
        },
    }


def reconcile_adapter_schedule(db: Session, row: AdapterSchedule) -> None:
    """
    Push ``row`` state to EventBridge Scheduler, creating or updating the
    per-adapter schedule. On success stamps ``last_reconciled_at``; on failure
    stores ``last_reconcile_error`` and re-raises.
    """
    name = _schedule_name_for(row.adapter_name)
    group = settings.SCHEDULER_GROUP_NAME
    state = "ENABLED" if row.enabled else "DISABLED"

    try:
        target = _build_target(row)
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
                Description=f"CarModPicker crawler schedule for adapter '{row.adapter_name}'",
            )
    except (ClientError, BotoCoreError, AwsSchedulerUnavailable) as e:
        row.last_reconcile_error = str(e)
        db.add(row)
        db.commit()
        logger.exception("Failed to reconcile adapter schedule %s: %s", row.adapter_name, e)
        raise

    row.last_reconciled_at = datetime.now(UTC)
    row.last_reconcile_error = None
    db.add(row)
    db.commit()
    logger.info(
        "Reconciled adapter schedule: adapter=%s state=%s expression=%s",
        row.adapter_name,
        state,
        row.schedule_expression,
    )


def delete_adapter_schedule(adapter_name: str) -> None:
    """Delete the AWS schedule for ``adapter_name`` if it exists. Idempotent."""
    name = _schedule_name_for(adapter_name)
    group = settings.SCHEDULER_GROUP_NAME
    try:
        client = _get_scheduler_client()
        client.delete_schedule(Name=name, GroupName=group)
        logger.info("Deleted adapter schedule: %s", name)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code", "") == "ResourceNotFoundException":
            return
        raise


def reconcile_all(db: Session) -> list[dict[str, Any]]:
    """
    Reconcile every row. Returns a list of ``{adapter_name, ok, error}`` results.
    Individual failures are reported but do not abort the batch.
    """
    rows = db.query(AdapterSchedule).order_by(AdapterSchedule.adapter_name).all()
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            reconcile_adapter_schedule(db, row)
            results.append({"adapter_name": row.adapter_name, "ok": True, "error": None})
        except Exception as e:
            results.append({"adapter_name": row.adapter_name, "ok": False, "error": str(e)})
    return results
