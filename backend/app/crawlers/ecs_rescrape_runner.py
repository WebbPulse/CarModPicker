"""
ECS Fargate task entry point for re-parsing all archived crawled pages.

Invoked as: python -m app.crawlers.ecs_rescrape_runner

Configuration is read from environment variables injected by App Runner
at ecs.run_task() time:

    JOB_ID                       — BackgroundJob UUID to update on completion
    CRAWLER_DEFAULT_CATEGORY_ID  — UUID; fallback category ID (required)
    CRAWLER_USER_ID              — optional UUID; defaults to crawler service account

Static environment (baked into the ECS task definition by Terraform):
    DATABASE_URL, USER_IMAGES_BUCKET, CRAWL_BUCKET, AWS_REGION,
    EMAIL_FROM, EMAIL_ENABLED, APP_ENVIRONMENT

OBS-02 / D-21 — rescrape emits a single CloudWatch EMF record with
``RunType="rescrape"`` and ``adapter_name="aggregate"`` at the end of
main(). Rationale: ``run_rescrape_all_archived_pages`` returns an aggregate
outcome-count dict (parsed_ok / parse_failed / ingest_failed / skipped_*)
that is NOT broken down per adapter. Splitting per-adapter would require
a second pass over the crawled_pages table and isn't worth the complexity
— plan 02-05's alarm filters on ``RunType=live``, so the rescrape metric
stream is purely informational for dashboards. ``ParseFailures`` here maps
to ``parse_failed`` (the rescrape analog of ``skipped_not_product``).
"""

import logging
import os
import sys
import time
import traceback
from uuid import UUID

from app.core.logging import configure_root_logging

# IN-04: use the shared logging setup (single LOG_FORMAT +
# RequestContextFilter across all entry points) so ``request_id`` /
# ``user_id`` attributes set by IN-03 actually appear in log output.
configure_root_logging()
logger = logging.getLogger(__name__)


def _notify_completion(db, job_id: UUID) -> None:
    """Send job-report email to superadmins. Best-effort — never raises."""
    try:
        from sqlalchemy import select

        from app.api.models.user import User as DBUser
        from app.core.email import send_job_report_email
        from app.services import job_service

        job = job_service.get_job(db, job_id)
        if job is None:
            return
        recipients = list(
            db.scalars(
                select(DBUser.email).where(
                    DBUser.is_superuser.is_(True), DBUser.disabled.is_(False)
                )
            ).all()
        )
        if recipients:
            sent = send_job_report_email(job, recipients)
            logger.info("Job #%s report sent to %s superadmin(s)", job_id, sent)
    except Exception:
        logger.exception("Failed to send job report email for job #%s", job_id)


def main() -> None:
    # Sentry init — inside main() (not module-level) so test collection /
    # import-only pathways cannot fire it. Same server_name as ecs_runner.py
    # so all Fargate crawler exceptions aggregate under one Sentry "service"
    # (D-11).
    from app.core.sentry import init_sentry

    init_sentry(server_name="ecs-crawler")

    # OBS-02 / D-21 — EMF emitter for rescrape path. Local import mirrors
    # Sentry's pattern (keeps aws-embedded-metrics out of test-collection
    # import graph).
    from app.core.cloudwatch_emf import emit_crawler_run_metrics
    from app.core.log_context import request_id_var, user_id_var
    from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
    from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id
    from app.db.session import SessionLocal
    from app.services import job_service

    # --- Parse JOB_ID early (outside the main try/except) so the
    # exception handler can reference it. WR-02: validate permissively
    # — a malformed JOB_ID means we have no job row to update, so the
    # best we can do is log and exit (Sentry catches the exception).
    job_id_str = os.environ.get("JOB_ID")
    try:
        job_id = UUID(job_id_str) if job_id_str else None
    except ValueError:
        logger.exception(
            "JOB_ID=%r is not a valid UUID; aborting without job update.",
            job_id_str,
        )
        sys.exit(1)

    # IN-03: set log-context ContextVars for the ECS task scope so every
    # log record produced by this process is grep-distinguishable from
    # HTTP requests and CLI runs. Matches the pattern used in
    # ``ecs_runner.py`` so rescrape and live-crawl log streams share a
    # single ``ecs:`` prefix convention.
    request_id_var.set(f"ecs:{os.getpid()}:{job_id or '-'}")
    user_id_var.set("ecs")

    def _progress(processed: int, total: int, counts_snapshot: dict[str, int]) -> None:
        # ECS-backed jobs still have a BackgroundJob row; pushing partial
        # progress there lets the admin UI draw a live bar just like the
        # in-process dev fallback.
        if job_id is None:
            return
        pdb = SessionLocal()
        try:
            job_service.update_job_progress(
                pdb,
                job_id,
                {**counts_snapshot, "processed": processed, "total": total},
            )
        except Exception:
            logger.exception("Failed to write progress for ECS rescrape job #%s", job_id)
        finally:
            pdb.close()

    db = SessionLocal()
    # OBS-02 / D-21 — wall-clock start for the ``ElapsedSeconds`` metric. We
    # measure the full rescrape pass including resolve_crawler_user + DB query
    # so the metric reflects total task-time from the operator's POV.
    rescrape_start = time.monotonic()
    # WR-02: parse CRAWLER_DEFAULT_CATEGORY_ID and CRAWLER_USER_ID INSIDE
    # the main try/except so that malformed UUIDs update the job row via
    # ``job_service.fail_job`` and fire the superadmin email via
    # ``_notify_completion`` instead of exiting with an uncaught
    # ``ValueError`` that leaves the job stuck in "running".
    try:
        category_id_str = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
        if not category_id_str:
            raise ValueError("CRAWLER_DEFAULT_CATEGORY_ID is required but not set")

        user_id_str = os.environ.get("CRAWLER_USER_ID")
        user_id = UUID(user_id_str) if user_id_str else None

        logger.info("ECS archive rescrape task starting: job_id=%s", job_id)

        crawler_user = resolve_crawler_user(db, user_id)
        cat_id = resolve_default_category_id(db, UUID(category_id_str))

        counts = run_rescrape_all_archived_pages(
            db,
            crawler_user=crawler_user,
            default_category_id=cat_id,
            log=logger,
            progress_callback=_progress,
        )
        logger.info("ECS archive rescrape task completed: %s", counts)

        # OBS-02 / D-21 — emit aggregate EMF record BEFORE the logger.info
        # summary below (RESEARCH Landmine 3 — issue #109 drops the last EMF
        # line). Rescrape is a single aggregate run (not per-adapter), so
        # adapter_name="aggregate" per module docstring. ``parse_failures``
        # maps to rescrape's ``parse_failed`` outcome (the analog of
        # ``skipped_not_product`` in the live path, D-22).
        emit_crawler_run_metrics(
            adapter_name="aggregate",
            run_type="rescrape",
            ingested=int(counts.get("parsed_ok") or 0),
            parse_failures=int(counts.get("parse_failed") or 0),
            elapsed_seconds=time.monotonic() - rescrape_start,
        )
        logger.info(
            "ECS archive rescrape EMF emitted: adapter=aggregate run_type=rescrape "
            "parsed_ok=%s parse_failed=%s",
            counts.get("parsed_ok"),
            counts.get("parse_failed"),
        )

        if job_id is not None:
            job_service.complete_job(db, job_id, result_summary=counts)
            _notify_completion(db, job_id)

    except Exception:
        logger.exception("ECS archive rescrape task failed")
        if job_id is not None:
            try:
                job_service.fail_job(db, job_id, error_message=traceback.format_exc())
            except Exception:
                logger.exception("Failed to update job #%s on failure", job_id)
            # _notify_completion is best-effort / never raises; call
            # it independently of fail_job so superadmins are emailed
            # even if the DB update failed (mirrors IN-05 pattern).
            _notify_completion(db, job_id)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
