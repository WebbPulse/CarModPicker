"""Tests for stale/orphan detection in the background job service."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.models.background_job import BackgroundJob
from app.services import job_service


def _make_running_job(
    db: Session,
    *,
    worker_instance_id: str | None,
    heartbeat_age_seconds: float | None = 0.0,
    params: dict | None = None,
    started_age_seconds: float = 60.0,
) -> BackgroundJob:
    """Insert a row already in 'running' state with controllable heartbeat age."""
    now = datetime.now(UTC)
    last_heartbeat_at = None
    if heartbeat_age_seconds is not None:
        last_heartbeat_at = now - timedelta(seconds=heartbeat_age_seconds)
    job = BackgroundJob(
        job_type="crawler_run",
        status="running",
        triggered_by="manual",
        params=params,
        started_at=now - timedelta(seconds=started_age_seconds),
        last_heartbeat_at=last_heartbeat_at,
        worker_instance_id=worker_instance_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class TestSweepOrphanJobs:
    def test_sweeps_job_owned_by_prior_worker_instance(self, db_session: Session) -> None:
        job = _make_running_job(db_session, worker_instance_id="prior-worker-abc")

        swept = job_service.sweep_orphan_jobs(db_session, current_worker_instance_id="new-worker-xyz")

        assert len(swept) == 1
        assert swept[0].id == job.id
        db_session.refresh(job)
        assert job.status == "failed"
        assert job.completed_at is not None
        assert job.error_message is not None
        assert "orphaned" in job.error_message.lower()

    def test_sweeps_unowned_in_process_job_as_legacy_orphan(self, db_session: Session) -> None:
        """Pre-migration rows (no worker_instance_id, no ecs_task_arn) can only have come from a prior process.

        Age the row past the UNOWNED_GRACE_SEC so it's clearly not in the
        insert-then-stamp race window.
        """
        job = _make_running_job(
            db_session,
            worker_instance_id=None,
            params=None,
            started_age_seconds=300,
        )

        swept = job_service.sweep_orphan_jobs(db_session, current_worker_instance_id="new-worker-xyz")

        assert len(swept) == 1
        db_session.refresh(job)
        assert job.status == "failed"

    def test_fresh_unowned_row_is_left_alone_inside_grace_period(self, db_session: Session) -> None:
        """A row that was just created but hasn't had its owner stamped yet must
        not be swept, otherwise newly-started jobs get killed immediately when
        the admin UI refreshes the list mid-insert."""
        job = _make_running_job(
            db_session,
            worker_instance_id=None,
            params=None,
            started_age_seconds=5,
        )

        swept = job_service.sweep_orphan_jobs(db_session, current_worker_instance_id="any-worker")

        assert swept == []
        db_session.refresh(job)
        assert job.status == "running"

    def test_leaves_current_worker_job_alone_when_heartbeat_fresh(self, db_session: Session) -> None:
        job = _make_running_job(
            db_session,
            worker_instance_id="current-worker",
            heartbeat_age_seconds=5,
        )

        swept = job_service.sweep_orphan_jobs(
            db_session,
            current_worker_instance_id="current-worker",
            live_job_ids=[job.id],
        )

        assert swept == []
        db_session.refresh(job)
        assert job.status == "running"

    def test_leaves_ecs_backed_job_alone_even_if_worker_mismatches(self, db_session: Session) -> None:
        """ECS jobs are owned by Fargate; the in-process sweep must not touch them."""
        job = _make_running_job(
            db_session,
            worker_instance_id=None,
            params={"ecs_task_arn": "arn:aws:ecs:us-east-1:000:task/cluster/abc123"},
        )

        swept = job_service.sweep_orphan_jobs(db_session, current_worker_instance_id="new-worker")

        assert swept == []
        db_session.refresh(job)
        assert job.status == "running"

    def test_runtime_sweep_catches_current_worker_job_with_stale_heartbeat_and_no_live_task(
        self, db_session: Session
    ) -> None:
        """
        Belt-and-suspenders case: the asyncio task died without hitting its finally
        block, so the DB still says running and the worker ID is correct, but the
        task dict lost it and the heartbeat is old.
        """
        job = _make_running_job(
            db_session,
            worker_instance_id="current-worker",
            heartbeat_age_seconds=600,
        )

        swept = job_service.sweep_orphan_jobs(
            db_session,
            current_worker_instance_id="current-worker",
            live_job_ids=[],
            heartbeat_timeout_sec=180,
        )

        assert len(swept) == 1
        db_session.refresh(job)
        assert job.status == "failed"
        assert job.error_message is not None
        assert "stale" in job.error_message.lower()

    def test_runtime_sweep_leaves_current_worker_job_with_recent_heartbeat(self, db_session: Session) -> None:
        """Live worker, recent heartbeat, not in the live set (e.g., startup race) — don't sweep."""
        job = _make_running_job(
            db_session,
            worker_instance_id="current-worker",
            heartbeat_age_seconds=10,
        )

        swept = job_service.sweep_orphan_jobs(
            db_session,
            current_worker_instance_id="current-worker",
            live_job_ids=[],
            heartbeat_timeout_sec=180,
        )

        assert swept == []
        db_session.refresh(job)
        assert job.status == "running"

    def test_completed_jobs_are_not_touched(self, db_session: Session) -> None:
        job = _make_running_job(db_session, worker_instance_id="prior-worker")
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        db_session.commit()

        swept = job_service.sweep_orphan_jobs(db_session, current_worker_instance_id="new-worker")

        assert swept == []
        db_session.refresh(job)
        assert job.status == "completed"


class TestCreateJobStampsOwner:
    def test_create_job_stamps_worker_instance_id_and_initial_heartbeat(self, db_session: Session) -> None:
        """Closes the insert-then-sweep race: the row is owned from the moment it exists."""
        job = job_service.create_job(
            db_session,
            job_type="crawler_run",
            triggered_by="manual",
            worker_instance_id="worker-abc",
        )

        assert job.worker_instance_id == "worker-abc"
        assert job.last_heartbeat_at is not None

    def test_create_job_without_worker_id_leaves_fields_null(self, db_session: Session) -> None:
        """Callers that don't pass a worker id (e.g., tests or legacy flows) get null fields."""
        job = job_service.create_job(
            db_session,
            job_type="archive_rescrape",
            triggered_by="manual",
        )

        assert job.worker_instance_id is None
        assert job.last_heartbeat_at is None

    def test_create_job_then_immediate_sweep_does_not_fail_own_job(self, db_session: Session) -> None:
        """
        Regression for the observed bug: a job created via the endpoint then
        hit by the runtime sweep before any heartbeat refresh used to get
        marked "orphaned" instantly. With the owner stamped at insert time,
        the sweep recognises it as owned by the current worker and leaves it
        running.
        """
        job = job_service.create_job(
            db_session,
            job_type="crawler_run",
            triggered_by="manual",
            worker_instance_id="current-worker",
        )

        swept = job_service.sweep_orphan_jobs(
            db_session,
            current_worker_instance_id="current-worker",
            live_job_ids=[job.id],
        )

        assert swept == []
        db_session.refresh(job)
        assert job.status == "running"


class TestHeartbeatJob:
    def test_stamps_worker_id_and_heartbeat_on_running_job(self, db_session: Session) -> None:
        job = _make_running_job(db_session, worker_instance_id=None, heartbeat_age_seconds=None)
        assert job.worker_instance_id is None
        assert job.last_heartbeat_at is None

        updated = job_service.heartbeat_job(db_session, job.id, "worker-123")

        assert updated is not None
        assert updated.worker_instance_id == "worker-123"
        assert updated.last_heartbeat_at is not None

    def test_refreshes_heartbeat_on_subsequent_call(self, db_session: Session) -> None:
        job = _make_running_job(db_session, worker_instance_id="worker-123", heartbeat_age_seconds=60)
        first = job.last_heartbeat_at
        assert first is not None

        updated = job_service.heartbeat_job(db_session, job.id, "worker-123")

        assert updated is not None
        assert updated.last_heartbeat_at is not None
        assert updated.last_heartbeat_at > first

    def test_no_op_on_terminal_job(self, db_session: Session) -> None:
        """Heartbeat must not resurrect a completed/failed/cancelled row."""
        job = _make_running_job(db_session, worker_instance_id="worker-123")
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        db_session.commit()
        hb_before = job.last_heartbeat_at

        result = job_service.heartbeat_job(db_session, job.id, "worker-123")

        assert result is not None
        assert result.status == "completed"
        assert result.last_heartbeat_at == hb_before
