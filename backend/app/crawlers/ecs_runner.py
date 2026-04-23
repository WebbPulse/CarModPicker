"""
ECS Fargate task entry point for running retailer crawlers.

Invoked as: python -m app.crawlers.ecs_runner

Per-run configuration is read from environment variables injected by
App Runner at ecs.run_task() time:

    JOB_ID                            — BackgroundJob UUID to update on completion
    CRAWLER_ADAPTERS                  — comma-separated adapter names, or "all"
    CRAWLER_DEFAULT_CATEGORY_ID       — UUID; default category ID (required)
    CRAWLER_DEFAULT_CATEGORY_IDS      — optional JSON dict {"adapter": "<uuid>"} per-adapter override
    CRAWLER_USER_ID                   — optional UUID; defaults to crawler service account
    CRAWLER_LIMITS                    — optional JSON dict {"adapter": limit}
    CRAWLER_GLOBAL_LIMIT              — optional integer
    CRAWLER_DELAY_SEC                 — optional float default (fallback for adapters without a per-adapter delay)
    CRAWLER_DELAYS                    — optional JSON dict {"adapter": float} per-adapter override
    CRAWLER_PARALLEL                  — "true"/"false" (default: "true")
    CRAWLER_SKIP_KNOWN_URLS           — "true"/"false" default (fallback)
    CRAWLER_SKIP_KNOWN_URLS_BY_ADAPTER— optional JSON dict {"adapter": bool} per-adapter override

Static environment (baked into the ECS task definition by Terraform):
    DATABASE_URL, USER_IMAGES_BUCKET, CRAWL_BUCKET, AWS_REGION,
    EMAIL_FROM, EMAIL_ENABLED, APP_ENVIRONMENT
"""

import json
import logging
import os
import sys
import traceback
from uuid import UUID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _coerce_bool(v) -> bool:
    """Coerce a JSON-decoded value to a Python bool.

    Handles the case where an upstream producer serializes booleans as
    strings (e.g. ``{"a90shop": "false"}``): a bare ``bool("false")``
    returns ``True`` because non-empty strings are truthy, which silently
    inverts the intended semantics. This helper mirrors the ``.lower() in
    (...)`` pattern used for sibling env vars like ``CRAWLER_PARALLEL``
    and ``CRAWLER_SKIP_KNOWN_URLS`` (WR-01 from Phase 02 review).
    """
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes")
    return bool(v)


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
    # import-only pathways cannot fire it. No-ops unless TESTING!="true",
    # APP_ENVIRONMENT ∈ {staging, production}, and SENTRY_DSN is set. D-11.
    from app.core.sentry import init_sentry

    init_sentry(server_name="ecs-crawler")

    from app.crawlers.adapters import ADAPTER_REGISTRY
    from app.crawlers.base import DEFAULT_REQUEST_DELAY_SEC
    from app.crawlers.runner import run_crawlers
    from app.db.session import SessionLocal
    from app.services import job_service

    # --- Parse JOB_ID early (outside the main try/except) so the
    # exception handler can reference it. WR-02: validate permissively
    # — a malformed JOB_ID means we have no job row to update, so the
    # best we can do is log and exit (Sentry catches the exception;
    # the App Runner startup orphan sweeper is not applicable because
    # no matching BackgroundJob exists).
    job_id_str = os.environ.get("JOB_ID")
    try:
        job_id = UUID(job_id_str) if job_id_str else None
    except ValueError:
        logger.exception(
            "JOB_ID=%r is not a valid UUID; aborting without job update.",
            job_id_str,
        )
        sys.exit(1)

    # WR-02: all OTHER env parsing (including UUID() calls for
    # CRAWLER_DEFAULT_CATEGORY_ID, CRAWLER_USER_ID, etc.) moves INSIDE
    # the main try/except so that malformed values update the job row
    # via ``job_service.fail_job`` and fire the superadmin email
    # notification via ``_notify_completion`` instead of exiting with an
    # uncaught ``ValueError`` that leaves the job stuck in "running".
    try:
        # --- Parse env vars ---
        adapters_str = os.environ.get("CRAWLER_ADAPTERS", "all")
        adapters = [a.strip() for a in adapters_str.split(",") if a.strip()]
        if adapters == ["all"]:
            adapters = list(ADAPTER_REGISTRY.keys())

        category_id_str = os.environ.get("CRAWLER_DEFAULT_CATEGORY_ID")
        if not category_id_str:
            raise ValueError("CRAWLER_DEFAULT_CATEGORY_ID is required but not set")
        default_category_id = UUID(category_id_str)

        user_id_str = os.environ.get("CRAWLER_USER_ID")
        user_id = UUID(user_id_str) if user_id_str else None

        limits_str = os.environ.get("CRAWLER_LIMITS")
        limits = json.loads(limits_str) if limits_str else None

        global_limit_str = os.environ.get("CRAWLER_GLOBAL_LIMIT")
        global_limit = int(global_limit_str) if global_limit_str else None

        delay_sec_str = os.environ.get("CRAWLER_DELAY_SEC")
        delay_sec = float(delay_sec_str) if delay_sec_str else DEFAULT_REQUEST_DELAY_SEC

        delays_str = os.environ.get("CRAWLER_DELAYS")
        delays: dict[str, float] | None = None
        if delays_str:
            delays = {k: float(v) for k, v in json.loads(delays_str).items()}

        category_ids_str = os.environ.get("CRAWLER_DEFAULT_CATEGORY_IDS")
        default_category_ids: dict[str, UUID] | None = None
        if category_ids_str:
            default_category_ids = {k: UUID(v) for k, v in json.loads(category_ids_str).items()}

        parallel = os.environ.get("CRAWLER_PARALLEL", "true").lower() not in ("false", "0", "no")
        skip_known_urls = os.environ.get("CRAWLER_SKIP_KNOWN_URLS", "false").lower() in ("true", "1", "yes")

        skip_by_adapter_str = os.environ.get("CRAWLER_SKIP_KNOWN_URLS_BY_ADAPTER")
        skip_known_urls_by_adapter: dict[str, bool] | None = None
        if skip_by_adapter_str:
            # WR-01 — use ``_coerce_bool`` so JSON string values like
            # ``{"a90shop": "false"}`` are parsed correctly rather than being
            # silently treated as truthy.
            skip_known_urls_by_adapter = {
                k: _coerce_bool(v) for k, v in json.loads(skip_by_adapter_str).items()
            }

        logger.info(
            "ECS crawler task starting: adapters=%s category_id=%s job_id=%s delay_sec=%s parallel=%s",
            adapters,
            default_category_id,
            job_id,
            delay_sec,
            parallel,
        )

        # --- Run ---
        result = run_crawlers(
            adapters,
            limits=limits,
            global_limit=global_limit,
            delay_sec=delay_sec,
            delays=delays,
            parallel=parallel,
            user_id=user_id,
            default_category_id=default_category_id,
            default_category_ids=default_category_ids,
            skip_known_urls=skip_known_urls,
            skip_known_urls_by_adapter=skip_known_urls_by_adapter,
        )
        logger.info("ECS crawler task completed: %s", result)

        if job_id is not None:
            db = SessionLocal()
            try:
                result_dict = result if isinstance(result, dict) else {"raw": str(result)}
                job_service.complete_job(db, job_id, result_summary=result_dict)
                _notify_completion(db, job_id)
            finally:
                db.close()

    except Exception:
        logger.exception("ECS crawler task failed")
        if job_id is not None:
            db = SessionLocal()
            try:
                try:
                    job_service.fail_job(db, job_id, error_message=traceback.format_exc())
                except Exception:
                    logger.exception("Failed to update job #%s on failure", job_id)
                # _notify_completion is best-effort / never raises; call
                # it independently of fail_job so superadmins are emailed
                # even if the DB update failed (mirrors IN-05 pattern).
                _notify_completion(db, job_id)
            finally:
                db.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
