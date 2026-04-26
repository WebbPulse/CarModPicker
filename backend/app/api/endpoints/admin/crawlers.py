"""Admin crawler run, rescrape-archives, service-account endpoints (EventBridge-invokable per D-22)."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading
import traceback
from typing import Any, Dict, Optional
from uuid import UUID

import boto3
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_admin_user
from app.api.endpoints.admin._helpers import (
    heartbeat_loop,
    notify_job_completion,
    stamp_heartbeat,
)
from app.api.models.category import Category as DBCategory
from app.api.models.crawler_adapter_config import CrawlerAdapterConfig as DBCrawlerAdapterConfig
from app.api.models.crawler_schedule import CrawlerSchedule as DBCrawlerSchedule
from app.api.models.user import User as DBUser
from app.api.utils.endpoint_decorators import standard_responses
from app.core.config import settings
from app.core.worker_identity import WORKER_INSTANCE_ID
from app.crawlers.adapters import ADAPTER_REGISTRY
from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC
from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id, run_crawlers
from app.db.session import SessionLocal, get_db
from app.services import job_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Strong references to fire-and-forget tasks so they are not garbage-collected
# mid-execution. Tasks remove themselves on completion via add_done_callback.
_background_tasks: set[asyncio.Task[None]] = set()

# Per-job asyncio tasks and stop events for cooperative cancellation.
# Entries are cleaned up when the job task finishes. jobs.py reads these to
# service the cancel endpoint.
job_tasks: dict[UUID, asyncio.Task[None]] = {}
job_stop_events: dict[UUID, threading.Event] = {}


def _verify_cron_key(x_admin_cron_key: Optional[str]) -> bool:
    """
    Return True if the provided key matches CRON_SECRET_KEY (constant-time compare).
    Returns False when CRON_SECRET_KEY is not configured.
    """
    expected = settings.CRON_SECRET_KEY
    if not expected or not x_admin_cron_key:
        return False
    return secrets.compare_digest(expected, x_admin_cron_key)


class CrawlerRunRequest(BaseModel):
    """
    Request body for running crawlers.

    Two shapes are accepted:

    1. **Scheduled** — ``schedule_id`` alone (EventBridge Scheduler payload). The
       server dereferences the schedule's members and their per-adapter configs.
    2. **Explicit** — ``adapters`` + ``crawler_default_category_id`` (manual
       admin runs from the UI or API). Per-adapter knobs can be passed as
       dicts.

    Mixing the two forms is rejected by a ``model_validator``.
    """

    schedule_id: Optional[UUID] = Field(
        default=None,
        description="ID of a crawler_schedules row. When set, all other fields except crawler_user_id are ignored and sourced from the schedule + adapter configs.",
    )
    adapters: Optional[list[str]] = Field(
        default=None,
        description="Adapter names to run (e.g. ['a90shop']). Use ['all'] to run all adapters. Required when schedule_id is not set.",
    )
    crawler_user_id: Optional[UUID] = Field(
        default=None,
        description="User ID to attribute crawler-created parts to. Defaults to the crawler service account.",
    )
    crawler_default_category_id: Optional[UUID] = Field(
        default=None,
        description="Category ID for new parts. Required when schedule_id is not set.",
    )
    limits: Optional[Dict[str, int]] = Field(
        default=None,
        description="Per-adapter crawl limits: {'a90shop': 10}. Overrides global_limit when set.",
    )
    global_limit: Optional[int] = Field(
        default=None,
        description="Crawl limit applied to all adapters when no per-adapter limit is set.",
    )
    parallel: bool = Field(
        default=True,
        description="If True and more than one adapter, run crawlers in parallel threads.",
    )
    delay_sec: Optional[float] = Field(
        default=None,
        ge=0.5,
        le=60.0,
        description="Default delay between requests per crawler (default: 2.5). Use 5+ for conservative/large runs.",
    )
    delays: Optional[Dict[str, float]] = Field(
        default=None,
        description="Per-adapter delay override: {'a90shop': 7.5}. Falls back to delay_sec.",
    )
    crawl_html_save_dir: Optional[str] = Field(
        default=None,
        description="Kept for backward compatibility. HTML is always archived for every URL crawled.",
    )
    skip_known_urls: bool = Field(
        default=False,
        description="Default: skip URLs already parsed. Per-adapter overrides via skip_known_urls_by_adapter.",
    )
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Per-adapter override for skip_known_urls.",
    )
    default_category_ids: Optional[Dict[str, UUID]] = Field(
        default=None,
        description="Per-adapter category override: {'a90shop': <uuid>}. Falls back to crawler_default_category_id.",
    )

    @model_validator(mode="after")
    def _validate_shape(self) -> "CrawlerRunRequest":
        if self.schedule_id is not None:
            if self.adapters is not None:
                raise ValueError("Do not pass 'adapters' when using schedule_id; it is derived from the schedule.")
            return self
        if not self.adapters:
            raise ValueError("Either schedule_id or a non-empty adapters list is required.")
        if self.crawler_default_category_id is None:
            raise ValueError("crawler_default_category_id is required when schedule_id is not set.")
        return self


@router.get(
    "/",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Available crawlers retrieved",
        forbidden=True,
    ),
)
async def list_crawlers(
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    List available crawler adapters (admin only).

    Returns both a flat ``adapters`` list (for back-compat) and a richer
    ``adapter_info`` list that carries each adapter's declared fetcher tier
    (``http``, ``tls``, or ``browser``) so the admin UI can visually group
    them by blocking difficulty.
    """
    adapters = list(ADAPTER_REGISTRY.keys())
    adapter_info = [{"name": name, "tier": cls.FETCHER_TIER} for name, cls in ADAPTER_REGISTRY.items()]
    return {"adapters": adapters, "adapter_info": adapter_info}


def _launch_ecs_crawler_task(
    *,
    job_id: UUID,
    adapters: list[str],
    default_category_id: UUID,
    user_id: UUID,
    limits: Optional[Dict[str, int]],
    global_limit: Optional[int],
    delay_sec: float,
    parallel: bool,
    skip_known_urls: bool,
    delays: Optional[Dict[str, float]] = None,
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = None,
    default_category_ids: Optional[Dict[str, UUID]] = None,
) -> str:
    """
    Launch an ECS Fargate task to run the crawler. Returns the ECS task ARN.

    Requires CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, CRAWLER_ECS_SUBNETS,
    and CRAWLER_ECS_SECURITY_GROUP to be configured in settings.
    Raises RuntimeError if ECS is not configured or RunTask fails.
    """
    if not settings.crawler_ecs_configured:
        raise RuntimeError(
            "ECS crawler not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, "
            "CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP."
        )

    ecs_client = boto3.client("ecs", region_name=settings.AWS_REGION or None)

    env_overrides: list[dict[str, str]] = [
        {"name": "JOB_ID", "value": str(job_id)},
        {"name": "CRAWLER_ADAPTERS", "value": ",".join(adapters)},
        {"name": "CRAWLER_DEFAULT_CATEGORY_ID", "value": str(default_category_id)},
        {"name": "CRAWLER_USER_ID", "value": str(user_id)},
        {"name": "CRAWLER_DELAY_SEC", "value": str(delay_sec)},
        {"name": "CRAWLER_PARALLEL", "value": "true" if parallel else "false"},
        {"name": "CRAWLER_SKIP_KNOWN_URLS", "value": "true" if skip_known_urls else "false"},
    ]
    if limits:
        env_overrides.append({"name": "CRAWLER_LIMITS", "value": json.dumps(limits)})
    if global_limit is not None:
        env_overrides.append({"name": "CRAWLER_GLOBAL_LIMIT", "value": str(global_limit)})
    if delays:
        env_overrides.append({"name": "CRAWLER_DELAYS", "value": json.dumps(delays)})
    if skip_known_urls_by_adapter:
        env_overrides.append(
            {"name": "CRAWLER_SKIP_KNOWN_URLS_BY_ADAPTER", "value": json.dumps(skip_known_urls_by_adapter)}
        )
    if default_category_ids:
        env_overrides.append(
            {
                "name": "CRAWLER_DEFAULT_CATEGORY_IDS",
                "value": json.dumps({k: str(v) for k, v in default_category_ids.items()}),
            }
        )

    subnets = [s.strip() for s in settings.CRAWLER_ECS_SUBNETS.split(",") if s.strip()]
    security_groups = [sg.strip() for sg in settings.CRAWLER_ECS_SECURITY_GROUP.split(",") if sg.strip()]

    response = ecs_client.run_task(
        cluster=settings.CRAWLER_ECS_CLUSTER,
        taskDefinition=settings.CRAWLER_ECS_TASK_DEFINITION,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "crawler",
                    "environment": env_overrides,
                }
            ]
        },
    )

    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS RunTask failures: {failures}")

    tasks = response.get("tasks", [])
    if not tasks:
        raise RuntimeError("ECS RunTask returned no tasks and no failures.")

    return tasks[0]["taskArn"]


async def _run_crawlers_in_process(
    adapters: list[str],
    *,
    limits: Optional[Dict[str, int]],
    global_limit: Optional[int],
    parallel: bool,
    delay_sec: float,
    user_id: UUID,
    default_category_id: UUID,
    job_id: UUID,
    stop_event: threading.Event,
    skip_known_urls: bool,
    delays: Optional[Dict[str, float]] = None,
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = None,
    default_category_ids: Optional[Dict[str, UUID]] = None,
) -> None:
    """
    Dev-only fallback: run crawlers in an asyncio background thread.
    Only used when ECS is not configured (i.e. local development).
    In production, _launch_ecs_crawler_task is always used instead.
    """
    # Stamp ownership immediately so a crash before the first heartbeat interval
    # still leaves the row correctly tagged with this process's worker ID.
    await asyncio.to_thread(stamp_heartbeat, job_id)
    heartbeat_task = asyncio.create_task(heartbeat_loop(job_id))
    try:
        result = await asyncio.to_thread(
            run_crawlers,
            adapters,
            limits=limits,
            global_limit=global_limit,
            parallel=parallel,
            delay_sec=delay_sec,
            delays=delays,
            user_id=user_id,
            default_category_id=default_category_id,
            default_category_ids=default_category_ids,
            stop_event=stop_event,
            skip_known_urls=skip_known_urls,
            skip_known_urls_by_adapter=skip_known_urls_by_adapter,
        )
        db = SessionLocal()
        try:
            result_dict = result if isinstance(result, dict) else {"raw": str(result)}
            job_service.complete_job(db, job_id, result_summary=result_dict)
            await asyncio.to_thread(notify_job_completion, job_id)
        finally:
            db.close()
    except Exception as e:
        logger.exception("In-process crawler job #%s failed: %s", job_id, e)
        db = SessionLocal()
        try:
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            await asyncio.to_thread(notify_job_completion, job_id)
        finally:
            db.close()
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        job_tasks.pop(job_id, None)
        job_stop_events.pop(job_id, None)


@router.post(
    "/run",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Crawler job started",
        forbidden=True,
    ),
)
async def run_crawlers_endpoint(
    body: CrawlerRunRequest,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_admin_user),
    x_admin_cron_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Start retailer crawlers (admin only). Returns immediately after enqueueing the job.

    Accepts either a superadmin JWT (manual trigger from admin UI) or the
    ``X-Admin-Cron-Key`` header (EventBridge Scheduler scheduled trigger).

    - Run individual crawlers or desired combinations.
    - Run all crawlers with adapters: ["all"].
    - Set per-crawler limits via limits: {"a90shop": 10, "example": 5}.
    - Set a global limit for all crawlers via global_limit.
    - When running more than one crawler, they run in parallel by default.
    """
    is_scheduled = _verify_cron_key(x_admin_cron_key)
    if not is_scheduled and current_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    triggered_by = "scheduled" if is_scheduled else "manual"
    acting_user_id: Optional[UUID] = None if is_scheduled else (current_user.id if current_user else None)

    # Validate crawler user and category upfront so we return 400 instead of 200 + silent failure
    if body.crawler_user_id is not None:
        crawler_user = db.scalars(select(DBUser).where(DBUser.id == body.crawler_user_id)).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: no user found.",
            )
        if crawler_user.disabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: user is disabled.",
            )
    else:
        # Ensure service account exists before kicking off the job
        crawler_user = db.scalars(select(DBUser).where(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False))).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No crawler service account found. Restart the app to create it.",
            )
    # Resolve the concrete run shape — either from a schedule_id (EB firing or
    # UI-dispatched scheduled run) or from the explicit body. A schedule's
    # ``enabled`` flag is intentionally NOT re-checked here: EventBridge has
    # already made the authoritative "fire" decision by the time we see it.
    adapters: list[str]
    delay_sec: float = body.delay_sec if body.delay_sec is not None else DEFAULT_REQUEST_DELAY_SEC
    limits: Optional[Dict[str, int]] = body.limits
    delays: Optional[Dict[str, float]] = body.delays
    skip_known_urls: bool = body.skip_known_urls
    skip_known_urls_by_adapter: Optional[Dict[str, bool]] = body.skip_known_urls_by_adapter
    default_category_id: UUID
    default_category_ids: Optional[Dict[str, UUID]] = body.default_category_ids
    parallel: bool = body.parallel

    if body.schedule_id is not None:
        sched = db.scalars(select(DBCrawlerSchedule).where(DBCrawlerSchedule.id == body.schedule_id)).first()
        if not sched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"schedule_id={body.schedule_id}: not found.",
            )
        member_names = [a.adapter_name for a in sched.adapters]
        if not member_names:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schedule '{sched.name}' has no adapters.",
            )
        configs = list(db.scalars(select(DBCrawlerAdapterConfig).where(DBCrawlerAdapterConfig.adapter_name.in_(member_names))).all())
        configs_by_name = {c.adapter_name: c for c in configs}
        missing = [n for n in member_names if n not in configs_by_name]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing crawler_adapter_configs for: {missing}. Restart the app to re-seed.",
            )
        adapters = [n for n in member_names if n in ADAPTER_REGISTRY]
        unknown = [n for n in member_names if n not in ADAPTER_REGISTRY]
        if unknown:
            logger.warning(
                "Schedule '%s' references unregistered adapter(s) %s; skipping.",
                sched.name,
                unknown,
            )
        if not adapters:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schedule '{sched.name}' has no currently-registered adapters.",
            )
        delays = {n: configs_by_name[n].delay_sec for n in adapters}
        skip_known_urls_by_adapter = {n: configs_by_name[n].skip_known_urls for n in adapters}
        default_category_ids = {n: configs_by_name[n].default_category_id for n in adapters}
        per_adapter_limits: Dict[str, int] = {}
        for n in adapters:
            lim = configs_by_name[n].per_run_limit
            if lim is not None:
                per_adapter_limits[n] = lim
        limits = per_adapter_limits or None
        default_category_id = configs_by_name[adapters[0]].default_category_id
        parallel = True
        logger.info(
            "Dispatching schedule '%s' (id=%s) with adapters=%s",
            sched.name,
            sched.id,
            adapters,
        )
    else:
        if body.crawler_default_category_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="crawler_default_category_id is required when schedule_id is not set.",
            )
        cat = db.scalars(select(DBCategory).where(DBCategory.id == body.crawler_default_category_id)).first()
        if not cat or not cat.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_default_category_id={body.crawler_default_category_id}: not found or inactive.",
            )
        raw = body.adapters or []
        if raw == ["all"]:
            adapters = list(ADAPTER_REGISTRY.keys())
        else:
            adapters = raw
        invalid = [a for a in adapters if a not in ADAPTER_REGISTRY]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown adapter(s): {invalid}. Available: {list(ADAPTER_REGISTRY.keys())}",
            )
        default_category_id = body.crawler_default_category_id

    logger.info(
        "Crawler job starting: adapters=%s triggered_by=%s user=%s",
        adapters,
        triggered_by,
        acting_user_id,
    )

    job = job_service.create_job(
        db,
        job_type="crawler_run",
        triggered_by=triggered_by,
        params={
            "adapters": adapters,
            "limits": limits,
            "global_limit": body.global_limit,
            "parallel": parallel,
            "delay_sec": delay_sec,
            "delays": delays,
            "crawler_user_id": str(crawler_user.id),
            "default_category_id": str(default_category_id),
            "default_category_ids": (
                {k: str(v) for k, v in default_category_ids.items()} if default_category_ids else None
            ),
            "skip_known_urls": skip_known_urls,
            "skip_known_urls_by_adapter": skip_known_urls_by_adapter,
            "schedule_id": str(body.schedule_id) if body.schedule_id else None,
        },
        created_by_user_id=acting_user_id,
        worker_instance_id=WORKER_INSTANCE_ID,
    )

    if settings.crawler_ecs_configured:
        # Production path: launch a Fargate task that spins up, runs, and tears down.
        try:
            task_arn = _launch_ecs_crawler_task(
                job_id=job.id,
                adapters=adapters,
                default_category_id=default_category_id,
                user_id=crawler_user.id,
                limits=limits,
                global_limit=body.global_limit,
                delay_sec=delay_sec,
                parallel=parallel,
                skip_known_urls=skip_known_urls,
                delays=delays,
                skip_known_urls_by_adapter=skip_known_urls_by_adapter,
                default_category_ids=default_category_ids,
            )
            # Store the ECS task ARN so the cancel endpoint can stop it.
            job.params = {**(job.params or {}), "ecs_task_arn": task_arn}
            db.add(job)
            db.commit()
            logger.info("Crawler job #%s launched ECS task: %s", job.id, task_arn)
        except Exception as e:
            logger.exception("Failed to launch ECS task for crawler job #%s: %s", job.id, e)
            job_service.fail_job(db, job.id, error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to launch crawler task: {e}",
            )
    elif not settings.is_production:
        # Dev fallback: run in-process as a background asyncio task.
        logger.info("Crawler job #%s: ECS not configured, running in-process (dev mode).", job.id)
        stop_event = threading.Event()
        task = asyncio.create_task(
            _run_crawlers_in_process(
                adapters,
                limits=limits,
                global_limit=body.global_limit,
                parallel=parallel,
                delay_sec=delay_sec,
                user_id=crawler_user.id,
                default_category_id=default_category_id,
                job_id=job.id,
                stop_event=stop_event,
                skip_known_urls=skip_known_urls,
                delays=delays,
                skip_known_urls_by_adapter=skip_known_urls_by_adapter,
                default_category_ids=default_category_ids,
            )
        )
        job_tasks[job.id] = task
        job_stop_events[job.id] = stop_event
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    else:
        job_service.fail_job(db, job.id, error_message="ECS crawler not configured in production.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crawler ECS task is not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP.",
        )

    return {
        "status": "started",
        "job_id": job.id,
        "adapters": adapters,
        "triggered_by": triggered_by,
        "message": "Crawler job has been started. A completion report will be sent to superadmins when finished.",
    }


class RescrapeArchivesRequest(BaseModel):
    """Request body for re-parsing all archived HTML into global parts (same as crawler ingest)."""

    crawler_user_id: Optional[UUID] = Field(
        default=None,
        description="User ID to attribute created/updated parts to. Defaults to the crawler service account.",
    )
    default_category_id: UUID = Field(
        ...,
        description="Fallback category ID when inference cannot pick a category.",
    )


def _launch_ecs_rescrape_task(
    *,
    job_id: UUID,
    user_id: UUID,
    default_category_id: UUID,
) -> str:
    """
    Launch an ECS Fargate task to run the archive rescrape. Returns the ECS task ARN.

    Reuses the same cluster and task definition as the crawler, overriding the
    container command to point at the rescrape entry point.
    Raises RuntimeError if ECS is not configured or RunTask fails.
    """
    if not settings.crawler_ecs_configured:
        raise RuntimeError(
            "ECS crawler not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, "
            "CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP."
        )

    ecs_client = boto3.client("ecs", region_name=settings.AWS_REGION or None)

    subnets = [s.strip() for s in settings.CRAWLER_ECS_SUBNETS.split(",") if s.strip()]
    security_groups = [sg.strip() for sg in settings.CRAWLER_ECS_SECURITY_GROUP.split(",") if sg.strip()]

    response = ecs_client.run_task(
        cluster=settings.CRAWLER_ECS_CLUSTER,
        taskDefinition=settings.CRAWLER_ECS_TASK_DEFINITION,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnets,
                "securityGroups": security_groups,
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "crawler",
                    "command": ["python", "-m", "app.crawlers.ecs_rescrape_runner"],
                    "environment": [
                        {"name": "JOB_ID", "value": str(job_id)},
                        {"name": "CRAWLER_USER_ID", "value": str(user_id)},
                        {"name": "CRAWLER_DEFAULT_CATEGORY_ID", "value": str(default_category_id)},
                    ],
                }
            ]
        },
    )

    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"ECS RunTask failures: {failures}")

    tasks = response.get("tasks", [])
    if not tasks:
        raise RuntimeError("ECS RunTask returned no tasks and no failures.")

    return tasks[0]["taskArn"]


async def _run_rescrape_in_process(
    *,
    crawler_user_id: UUID,
    default_category_id: UUID,
    job_id: UUID,
    stop_event: threading.Event,
) -> None:
    """
    Dev-only fallback: run archive rescrape in a background thread.
    Only used when ECS is not configured (i.e. local development).
    """

    def _progress(processed: int, total: int, counts_snapshot: dict[str, int]) -> None:
        # Dedicated short-lived session — the driver thread's ``db`` is the
        # main rescrape session and we don't want to share its transaction.
        pdb = SessionLocal()
        try:
            job_service.update_job_progress(
                pdb,
                job_id,
                {**counts_snapshot, "processed": processed, "total": total},
            )
        except Exception:
            logger.exception("Failed to write progress for rescrape job #%s", job_id)
        finally:
            pdb.close()

    def _blocking() -> None:
        db = SessionLocal()
        try:
            crawler_user = resolve_crawler_user(db, crawler_user_id)
            cat_id = resolve_default_category_id(db, default_category_id)
            counts = run_rescrape_all_archived_pages(
                db,
                crawler_user=crawler_user,
                default_category_id=cat_id,
                log=logger,
                stop_event=stop_event,
                progress_callback=_progress,
            )
            job_service.complete_job(db, job_id, result_summary=counts)
            notify_job_completion(job_id)
        except Exception as e:
            logger.exception("In-process archive rescrape job #%s failed: %s", job_id, e)
            job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            notify_job_completion(job_id)
        finally:
            db.close()

    await asyncio.to_thread(stamp_heartbeat, job_id)
    heartbeat_task = asyncio.create_task(heartbeat_loop(job_id))
    try:
        await asyncio.to_thread(_blocking)
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass
        job_tasks.pop(job_id, None)
        job_stop_events.pop(job_id, None)


@router.post(
    "/rescrape-archives",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Archive rescrape job started",
        forbidden=True,
    ),
)
async def rescrape_all_archived_crawled_pages(
    body: RescrapeArchivesRequest,
    db: Session = Depends(get_db),
    current_user: Optional[DBUser] = Depends(get_current_admin_user),
    x_admin_cron_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Start a background job that re-parses every crawled page with stored HTML.

    Accepts either a superadmin JWT (manual trigger) or ``X-Admin-Cron-Key`` header
    (EventBridge Scheduler scheduled trigger).

    For each row: load archived HTML, run the appropriate retailer parser (including
    extension-sourced URLs matched by host), then ``ingest_payload`` so parts are
    created/updated with full inference and listing refresh. Price history is updated
    when the parsed payload includes a price (same path as live crawls).

    HTML is stored under one canonical object per URL (``crawl_html/by_url/…``).
    """
    is_scheduled = _verify_cron_key(x_admin_cron_key)
    if not is_scheduled and current_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    triggered_by = "scheduled" if is_scheduled else "manual"
    acting_user_id: Optional[UUID] = None if is_scheduled else (current_user.id if current_user else None)

    if body.crawler_user_id is not None:
        crawler_user = db.scalars(select(DBUser).where(DBUser.id == body.crawler_user_id)).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: no user found.",
            )
        if crawler_user.disabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"crawler_user_id={body.crawler_user_id}: user is disabled.",
            )
    else:
        crawler_user = db.scalars(select(DBUser).where(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False))).first()
        if not crawler_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No crawler service account found. Restart the app to create it.",
            )
    cat = db.scalars(select(DBCategory).where(DBCategory.id == body.default_category_id)).first()
    if not cat or not cat.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"default_category_id={body.default_category_id}: not found or inactive.",
        )

    logger.info(
        "Archive rescrape job starting: triggered_by=%s user=%s",
        triggered_by,
        acting_user_id,
    )

    job = job_service.create_job(
        db,
        job_type="archive_rescrape",
        triggered_by=triggered_by,
        params={
            "crawler_user_id": str(crawler_user.id),
            "default_category_id": str(body.default_category_id),
        },
        created_by_user_id=acting_user_id,
        worker_instance_id=WORKER_INSTANCE_ID,
    )

    if settings.crawler_ecs_configured:
        # Production path: launch a Fargate task that spins up, runs, and tears down.
        try:
            task_arn = _launch_ecs_rescrape_task(
                job_id=job.id,
                user_id=crawler_user.id,
                default_category_id=body.default_category_id,
            )
            job.params = {**(job.params or {}), "ecs_task_arn": task_arn}
            db.add(job)
            db.commit()
            logger.info("Archive rescrape job #%s launched ECS task: %s", job.id, task_arn)
        except Exception as e:
            logger.exception("Failed to launch ECS task for rescrape job #%s: %s", job.id, e)
            job_service.fail_job(db, job.id, error_message=str(e))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to launch rescrape task: {e}",
            )
    elif not settings.is_production:
        # Dev fallback: run in-process as a background asyncio task.
        logger.info("Archive rescrape job #%s: ECS not configured, running in-process (dev mode).", job.id)
        stop_event = threading.Event()
        task = asyncio.create_task(
            _run_rescrape_in_process(
                crawler_user_id=crawler_user.id,
                default_category_id=body.default_category_id,
                job_id=job.id,
                stop_event=stop_event,
            )
        )
        job_tasks[job.id] = task
        job_stop_events[job.id] = stop_event
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    else:
        job_service.fail_job(db, job.id, error_message="ECS crawler not configured in production.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Crawler ECS task is not configured. Set CRAWLER_ECS_CLUSTER, CRAWLER_ECS_TASK_DEFINITION, CRAWLER_ECS_SUBNETS, and CRAWLER_ECS_SECURITY_GROUP.",
        )

    return {
        "status": "started",
        "job_id": job.id,
        "triggered_by": triggered_by,
        "message": (
            "Archive rescrape job started. Each page is re-parsed from stored HTML; "
            "a completion report will be sent to superadmins when finished."
        ),
    }


@router.get(
    "/service-account",
    response_model=Dict[str, Any],
    responses=standard_responses(
        success_description="Crawler service account info",
        forbidden=True,
    ),
)
async def get_crawler_service_account(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """
    Return the crawler service account (admin only).

    This account is created on startup and is used as the default author for all
    crawler-created parts when no explicit user ID is provided.
    """
    user = db.scalars(select(DBUser).where(DBUser.is_service_account.is_(True), DBUser.disabled.is_(False))).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawler service account not found. Restart the app to create it.",
        )
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_service_account": user.is_service_account,
        "created_at": user.created_at.isoformat(),
    }
