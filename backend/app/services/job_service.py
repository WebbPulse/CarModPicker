"""
Service layer for background job lifecycle management.

All functions take an explicit SQLAlchemy Session so callers control transaction
scope. Functions that run inside a background thread must pass their own
SessionLocal() instance (not the request-scoped one).
"""

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.models.background_job import BackgroundJob


def create_job(
    db: Session,
    *,
    job_type: str,
    triggered_by: str,
    params: Optional[dict[str, Any]] = None,
    created_by_user_id: Optional[int] = None,
) -> BackgroundJob:
    """
    Insert a new job record in 'running' status and return it.

    job_type: 'crawler_run' | 'archive_rescrape'
    triggered_by: 'manual' | 'scheduled'
    """
    job = BackgroundJob(
        job_type=job_type,
        status="running",
        triggered_by=triggered_by,
        params=params,
        created_by_user_id=created_by_user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def complete_job(
    db: Session,
    job_id: int,
    result_summary: Optional[dict[str, Any]] = None,
) -> Optional[BackgroundJob]:
    """Mark a job as completed, recording the result summary and finish time.

    If the job was already cancelled (e.g. by an admin while the worker was
    still running), this is a no-op so the cancelled status is preserved.
    """
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
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
    job_id: int,
    error_message: str,
    result_summary: Optional[dict[str, Any]] = None,
) -> Optional[BackgroundJob]:
    """Mark a job as failed, recording the error and any partial result summary."""
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if job is None:
        return None
    job.status = "failed"
    job.completed_at = datetime.now(UTC)
    job.error_message = error_message
    job.result_summary = result_summary
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job_id: int) -> Optional[BackgroundJob]:
    """
    Set a job's status to 'cancelled'.

    This is a best-effort DB flag — it does not interrupt the running asyncio
    task. Callers may check the flag inside long loops to exit early.
    """
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if job is None:
        return None
    job.status = "cancelled"
    job.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> Optional[BackgroundJob]:
    """Return a single job by ID, or None if not found."""
    return db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()


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
    q = db.query(BackgroundJob)
    if status_filter:
        q = q.filter(BackgroundJob.status == status_filter)
    if job_type_filter:
        q = q.filter(BackgroundJob.job_type == job_type_filter)
    total = q.count()
    items = q.order_by(desc(BackgroundJob.started_at)).offset(offset).limit(limit).all()
    return items, total
