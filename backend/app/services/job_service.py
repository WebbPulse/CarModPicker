"""
Service layer for background job lifecycle management.

All functions take an explicit SQLAlchemy Session so callers control transaction
scope. Functions that run inside a background thread must pass their own
SessionLocal() instance (not the request-scoped one).
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable, Optional
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.models.background_job import BackgroundJob

logger = logging.getLogger(__name__)

# How long an in-process job may go without a heartbeat before we consider it
# dead (runtime sweep path only — the startup sweep relies on worker-instance
# mismatch, which is unambiguous).
DEFAULT_HEARTBEAT_TIMEOUT_SEC = 180

# Grace period before an unowned running row (no worker_instance_id and no
# ecs_task_arn) is considered a legacy orphan. Every new job stamps its owner
# at create_job time, so unowned rows shouldn't appear at all under current
# code — but if one does slip in (race on commit, old code, partial migration),
# we only fail it once it's clearly not a live in-flight insert.
UNOWNED_GRACE_SEC = 120


def create_job(
    db: Session,
    *,
    job_type: str,
    triggered_by: str,
    params: Optional[dict[str, Any]] = None,
    created_by_user_id: Optional[UUID] = None,
    worker_instance_id: Optional[str] = None,
) -> BackgroundJob:
    """
    Insert a new job record in 'running' status and return it.

    job_type: 'crawler_run' | 'archive_rescrape'
    triggered_by: 'manual' | 'scheduled'
    worker_instance_id: stamp the creating process's worker ID at insert time
        so the orphan sweep can't misclassify a freshly-created row as a
        legacy unowned one in the window before the first heartbeat runs.
        ECS-backed jobs set this too; the sweep excludes them by
        ``params.ecs_task_arn`` regardless.
    """
    now = datetime.now(UTC)
    job = BackgroundJob(
        job_type=job_type,
        status="running",
        triggered_by=triggered_by,
        params=params,
        created_by_user_id=created_by_user_id,
        worker_instance_id=worker_instance_id,
        last_heartbeat_at=now if worker_instance_id is not None else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job_id: UUID,
    result_summary: Optional[dict[str, Any]] = None,
) -> Optional[BackgroundJob]:
    """Mark a job as completed, recording the result summary and finish time.

    If the job was already cancelled (e.g. by an admin while the worker was
    still running), this is a no-op so the cancelled status is preserved.
    """
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.id == job_id)).first()
    if job is None:
        return None
    if job.status == "cancelled":
        return job
    job.status = "completed"
    job.completed_at = datetime.now(UTC)
    job.result_summary = result_summary
    db.commit()
    db.refresh(job)
    return job


def fail_job(
    db: Session,
    job_id: UUID,
    error_message: str,
    result_summary: Optional[dict[str, Any]] = None,
) -> Optional[BackgroundJob]:
    """Mark a job as failed, recording the error and any partial result summary.

    If the job was already cancelled (e.g. by an admin while the worker was
    still running), this is a no-op so the cancelled status is preserved.
    Mirrors the guard in :func:`complete_job` so a cancelled worker that then
    raises during shutdown can't flip the row to "failed" and trigger a second
    superadmin email after the cancel-report has already been sent.
    """
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.id == job_id)).first()
    if job is None:
        return None
    if job.status == "cancelled":
        return job
    job.status = "failed"
    job.completed_at = datetime.now(UTC)
    job.error_message = error_message
    job.result_summary = result_summary
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job_id: UUID) -> Optional[BackgroundJob]:
    """
    Set a job's status to 'cancelled'.

    This is a best-effort DB flag — it does not interrupt the running asyncio
    task. Callers may check the flag inside long loops to exit early.
    """
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.id == job_id)).first()
    if job is None:
        return None
    job.status = "cancelled"
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: UUID) -> Optional[BackgroundJob]:
    """Return a single job by ID, or None if not found."""
    return db.scalars(select(BackgroundJob).where(BackgroundJob.id == job_id)).first()


def heartbeat_job(
    db: Session,
    job_id: UUID,
    worker_instance_id: str,
) -> Optional[BackgroundJob]:
    """
    Record that an in-process worker is still alive and owns this job.

    Stamps ``worker_instance_id`` (first call of the job) and bumps
    ``last_heartbeat_at``. Only applied while the job is still "running"; once
    it's terminal, the heartbeat is a no-op so we don't clobber
    completed/failed/cancelled state.
    """
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.id == job_id)).first()
    if job is None or job.status != "running":
        return job
    job.last_heartbeat_at = datetime.now(UTC)
    if job.worker_instance_id != worker_instance_id:
        job.worker_instance_id = worker_instance_id
    db.commit()
    db.refresh(job)
    return job


def update_job_progress(
    db: Session,
    job_id: UUID,
    result_summary: dict[str, Any],
) -> Optional[BackgroundJob]:
    """
    Write a partial ``result_summary`` to a running job so the admin UI can
    render a live progress bar without a bespoke progress table.

    No-op once the job is terminal — the final ``complete_job`` / ``fail_job``
    write is authoritative and we must not stomp it.
    """
    job = db.scalars(select(BackgroundJob).where(BackgroundJob.id == job_id)).first()
    if job is None or job.status != "running":
        return job
    job.result_summary = result_summary
    db.commit()
    db.refresh(job)
    return job


def _is_ecs_backed(job: BackgroundJob) -> bool:
    """True when this job's execution is owned by an ECS Fargate task."""
    params = job.params or {}
    return bool(params.get("ecs_task_arn"))


def _mark_orphaned(db: Session, job: BackgroundJob, reason: str) -> None:
    """Shared helper: flip a stranded running row to failed with a clear reason."""
    job.status = "failed"
    job.completed_at = datetime.now(UTC)
    job.error_message = reason
    db.add(job)


def _as_utc_naive(dt: datetime) -> datetime:
    """Strip tzinfo for comparison. SQLite round-trips datetimes as naive, so
    callers that store tz-aware UTC timestamps (via PostgreSQL) still compare
    correctly under both engines."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def sweep_orphan_jobs(
    db: Session,
    *,
    current_worker_instance_id: str,
    live_job_ids: Optional[Iterable[UUID]] = None,
    heartbeat_timeout_sec: int = DEFAULT_HEARTBEAT_TIMEOUT_SEC,
) -> list[BackgroundJob]:
    """
    Find "running" jobs whose worker is demonstrably dead and mark them failed.

    Two detection modes:

    * **Process mismatch (startup):** a job owned by a different
      ``worker_instance_id`` than the one running now means the old process
      was killed (uvicorn --reload, SIGKILL, redeploy, crash). Always orphaned.
      Also catches legacy pre-migration rows where ``worker_instance_id`` is
      null but there's no ECS task arn — those can only have been started by a
      prior process.
    * **Stale heartbeat (runtime):** when ``live_job_ids`` is provided (the set
      of job IDs with a live asyncio task in the current process), a running
      job owned by the current instance but *not* in that set and with an old
      heartbeat is treated as orphaned. This is the belt-and-suspenders case
      where the asyncio task died without hitting its cleanup finally block.

    ECS-backed jobs (``params.ecs_task_arn`` set) are never swept here — their
    lifecycle is owned by ECS and reconciled via a separate path.

    Returns the list of jobs that were marked failed.
    """
    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(seconds=heartbeat_timeout_sec)
    unowned_cutoff = now - timedelta(seconds=UNOWNED_GRACE_SEC)
    live_set = {str(jid) for jid in live_job_ids} if live_job_ids is not None else None

    running = list(db.scalars(select(BackgroundJob).where(BackgroundJob.status == "running")).all())
    swept: list[BackgroundJob] = []

    for job in running:
        if _is_ecs_backed(job):
            continue

        owner = job.worker_instance_id
        is_other_process = owner is not None and owner != current_worker_instance_id
        # An unowned row (no worker_instance_id, no ecs_task_arn) is only
        # treated as a legacy orphan after the grace period. This avoids
        # falsely sweeping a row that was just inserted but hasn't yet had its
        # owner stamped (e.g., cross-commit race from pre-fix code paths).
        is_unowned_in_process = owner is None and _as_utc_naive(job.started_at) < _as_utc_naive(unowned_cutoff)

        if is_other_process or is_unowned_in_process:
            reason = (
                "Job orphaned: owning process terminated before completion "
                "(likely uvicorn reload, crash, or redeploy). Automatically marked failed on startup."
            )
            _mark_orphaned(db, job, reason)
            swept.append(job)
            continue

        if live_set is not None and str(job.id) not in live_set:
            hb = job.last_heartbeat_at
            if hb is not None and _as_utc_naive(hb) < _as_utc_naive(stale_cutoff):
                reason = (
                    "Job orphaned: heartbeat is stale and no live worker task exists in this process. "
                    "Likely the asyncio task died without finishing its cleanup."
                )
                _mark_orphaned(db, job, reason)
                swept.append(job)

    if swept:
        db.commit()
        for job in swept:
            db.refresh(job)
        logger.warning("Swept %d orphan background job(s)", len(swept))

    return swept


def list_jobs(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
    job_type_filter: Optional[str] = None,
) -> tuple[list[BackgroundJob], int]:
    """
    Return a page of jobs (newest first) and the total count matching the filters.
    """
    stmt = select(BackgroundJob)
    if status_filter:
        stmt = stmt.where(BackgroundJob.status == status_filter)
    if job_type_filter:
        stmt = stmt.where(BackgroundJob.job_type == job_type_filter)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.order_by(desc(BackgroundJob.started_at)).offset(offset).limit(limit)).all())
    return items, total
