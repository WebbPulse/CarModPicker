import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import JSON, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from app.db.base_class import Base


class BackgroundJob(Base):
    """
    Persisted record for long-running admin background jobs (crawler runs, archive rescrapes).

    job_type: "crawler_run" | "archive_rescrape"
    status: "running" | "completed" | "failed" | "cancelled"
    triggered_by: "manual" (admin UI) | "scheduled" (EventBridge cron)
    params: JSON snapshot of the parameters the job was started with.
    result_summary: JSON aggregate counters returned by the job on completion.
    error_message: set on failure; null otherwise.
    created_by_user_id: null when triggered_by="scheduled".
    worker_instance_id: identifier of the Python process owning an in-process job.
        Regenerated on every app boot so stale "running" rows from a killed
        process (uvicorn hot reload, SIGKILL, crash) can be detected on the next
        startup. Null for ECS-backed jobs, whose liveness is tracked via
        ``params.ecs_task_arn``.
    last_heartbeat_at: in-process jobs refresh this every few seconds while
        running; the sweep treats a stale heartbeat + missing asyncio task as a
        dead worker.
    """

    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid7, index=True)
    job_type: Mapped[str] = mapped_column(nullable=False, index=True)
    status: Mapped[str] = mapped_column(default="running", nullable=False, index=True)
    triggered_by: Mapped[str] = mapped_column(nullable=False)

    params: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    worker_instance_id: Mapped[Optional[str]] = mapped_column(nullable=True, index=True)

    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user: Mapped[Optional[Any]] = relationship("User")
