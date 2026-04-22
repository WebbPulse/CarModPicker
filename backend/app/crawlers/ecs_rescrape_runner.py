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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _notify_completion(db, job_id: UUID) -> None:
    """Send job-report email to superadmins. Best-effort — never raises."""
    try:
        from app.api.models.user import User as DBUser
        from app.core.email import send_job_report_email
        from app.services import job_service

        job = job_service.get_job(db, job_id)
        if job is None:
            return
        recipients = [
            row.email
            for row in db.query(DBUser.email).filter(DBUser.is_superuser.is_(True), DBUser.disabled.is_(False)).all()
        ]
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
    from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
    from app.crawlers.runner import resolve_crawler_user, resolve_default_category_id
    from app.db.session import SessionLocal
    from app.services import job_service

    job_id_str = os.environ.get("JOB_ID")
    job_id = UUID(job_id_str) if job_id_str else None

    category_id_str = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
    if not category_id_str:
        logger.error("CRAWLER_DEFAULT_CATEGORY_ID is required but not set")
        sys.exit(1)

    user_id_str = os.environ.get("CRAWLER_USER_ID")
    user_id = UUID(user_id_str) if user_id_str else None

    logger.info("ECS archive rescrape task starting: job_id=%s", job_id)

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
    try:
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
                _notify_completion(db, job_id)
            except Exception:
                logger.exception("Failed to update job #%s on failure", job_id)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
