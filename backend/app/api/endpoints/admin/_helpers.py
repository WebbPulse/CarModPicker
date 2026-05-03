"""Background-job lifecycle helpers shared across admin sub-routers (D-21).

Mirrors auth/_helpers.py for package consistency. Used by crawlers.py (crawler-run
job) and potentially db_ops.py (migrations/run). Leaf module — no sibling
sub-module imports (Risk 4 mitigation).
"""

from __future__ import annotations

import asyncio
import logging
from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.models.user import User as DBUser
from app.core.email import send_job_report_email
from app.core.worker_identity import WORKER_INSTANCE_ID
from app.db.session import SessionLocal
from app.services import job_service

logger = logging.getLogger(__name__)

# How often an in-process job stamps its heartbeat. Short enough that the
# runtime stale-heartbeat sweep (default 180s) has plenty of signal, long
# enough to keep DB write volume negligible.
_HEARTBEAT_INTERVAL_SEC = 15


def stamp_heartbeat(job_id: UUID) -> None:
    """Write a single heartbeat row. Runs in a thread to keep the event loop free."""
    db = SessionLocal()
    try:
        job_service.heartbeat_job(db, job_id, WORKER_INSTANCE_ID)
    finally:
        db.close()


async def heartbeat_loop(job_id: UUID, interval: float = _HEARTBEAT_INTERVAL_SEC) -> None:
    """
    Periodically refresh a job's last_heartbeat_at so the runtime sweep can tell
    the worker is still alive. Cancelled by the caller when the real job task
    finishes; individual heartbeat failures are logged but don't abort the loop.
    """
    while True:
        try:
            await asyncio.sleep(interval)
            await asyncio.to_thread(stamp_heartbeat, job_id)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Heartbeat loop for job #%s hit an error; continuing", job_id)


def _get_superadmin_emails(db: Session) -> List[str]:
    """Return email addresses of all active superusers for job notification."""
    users = db.scalars(select(DBUser.email).where(DBUser.is_superuser.is_(True), DBUser.disabled.is_(False))).all()
    return list(users)


def notify_job_completion(job_id: UUID, *, skip_if_cancelled: bool = True) -> None:
    """
    Send a job-report email to all superadmins.
    Opens its own DB session; safe to call from a background thread.

    The cancel endpoint sends the report itself the moment a job is cancelled,
    so by default this skips when ``job.status == "cancelled"`` to prevent the
    in-process worker's own completion path from double-sending.
    """
    db = SessionLocal()
    try:
        job = job_service.get_job(db, job_id)
        if job is None:
            return
        if skip_if_cancelled and job.status == "cancelled":
            return
        recipients = _get_superadmin_emails(db)
        if recipients:
            sent = send_job_report_email(job, recipients)
            logger.info("Job #%s report sent to %s superadmin(s)", job_id, sent)
    except Exception:
        logger.exception("Failed to send job report email for job #%s", job_id)
    finally:
        db.close()
