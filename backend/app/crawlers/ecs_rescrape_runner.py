"""
ECS Fargate task entry point for re-parsing all archived crawled pages.

Invoked as: python -m app.crawlers.ecs_rescrape_runner

Configuration is read from environment variables injected by App Runner
at ecs.run_task() time:

    JOB_ID                       — BackgroundJob ID to update on completion
    CRAWLER_DEFAULT_CATEGORY_ID  — integer; fallback category ID (required)
    CRAWLER_USER_ID              — optional integer; defaults to crawler service account

Static environment (baked into the ECS task definition by Terraform):
    DATABASE_URL, USER_IMAGES_BUCKET, CRAWL_BUCKET, AWS_REGION,
    EMAIL_FROM, EMAIL_ENABLED, APP_ENVIRONMENT
"""

import logging
import os
import sys
import traceback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _notify_completion(db, job_id: int) -> None:
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
    from app.crawlers.archive_rescrape import run_rescrape_all_archived_pages
    from app.crawlers.runner import _resolve_crawler_user, _resolve_default_category_id
    from app.db.session import SessionLocal
    from app.services import job_service

    job_id_str = os.environ.get("JOB_ID")
    job_id = int(job_id_str) if job_id_str else None

    category_id_str = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
    if not category_id_str:
        logger.error("CRAWLER_DEFAULT_CATEGORY_ID is required but not set")
        sys.exit(1)

    user_id_str = os.environ.get("CRAWLER_USER_ID")
    user_id = int(user_id_str) if user_id_str else None

    logger.info("ECS archive rescrape task starting: job_id=%s", job_id)

    db = SessionLocal()
    try:
        crawler_user = _resolve_crawler_user(db, user_id)
        cat_id = _resolve_default_category_id(db, int(category_id_str))

        counts = run_rescrape_all_archived_pages(
            db,
            crawler_user=crawler_user,
            default_category_id=cat_id,
            log=logger,
        )
        logger.info("ECS archive rescrape task completed: %s", counts)

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
