import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.logging import logger

if TYPE_CHECKING:
    from app.api.models.background_job import BackgroundJob

_TEMPLATES_DIR = Path(__file__).parent / "email_templates"
_CONFIG_SET = "carmodpicker-transactional"

VERIFY_EMAIL_SUBJECT = "Verify your CarModPicker email address"
RESET_PASSWORD_SUBJECT = "Reset your CarModPicker password"

_JOB_TYPE_LABELS: dict[str, str] = {
    "crawler_run": "Crawler Run",
    "archive_rescrape": "Archive Rescrape",
}
_STATUS_COLORS: dict[str, str] = {
    "completed": "#16a34a",
    "failed": "#dc2626",
    "cancelled": "#d97706",
}


def _load_template(name: str) -> str:
    return (_TEMPLATES_DIR / f"{name}.html").read_text(encoding="utf-8")


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send a single transactional email via SES. Returns True on success."""
    try:
        client = boto3.client("sesv2", region_name=settings.AWS_REGION)
        client.send_email(
            FromEmailAddress=settings.EMAIL_FROM,
            Destination={"ToAddresses": [to_email]},
            Content={
                "Simple": {
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
                }
            },
            ConfigurationSetName=_CONFIG_SET,
        )
        return True
    except (BotoCoreError, ClientError) as exc:
        logger.error(f"Failed to send email to {to_email}: {exc}")
        return False


def send_verify_email(to_email: str, verify_url: str) -> bool:
    """Send the email-verification message."""
    html = _load_template("verify_email").replace("{{VERIFY_EMAIL_LINK}}", verify_url)
    return _send(to_email, VERIFY_EMAIL_SUBJECT, html)


def send_reset_password_email(to_email: str, reset_url: str) -> bool:
    """Send the password-reset message."""
    html = _load_template("reset_password").replace("{{RESET_PASSWORD_LINK}}", reset_url)
    return _send(to_email, RESET_PASSWORD_SUBJECT, html)


def send_job_report_email(job: "BackgroundJob", recipients: list[str]) -> int:
    """
    Send a job completion/failure report to a list of recipient email addresses.

    Returns the number of emails successfully sent.
    """
    if not recipients:
        return 0

    status = job.status
    job_type_label = _JOB_TYPE_LABELS.get(job.job_type, job.job_type.replace("_", " ").title())
    status_label = status.upper()
    status_color = _STATUS_COLORS.get(status, "#6b7280")

    started_str = _fmt_dt(job.started_at)
    completed_str = _fmt_dt(job.completed_at) if job.completed_at else "—"
    duration_str = _fmt_duration(job.started_at, job.completed_at)

    result_text = (
        json.dumps(job.result_summary, indent=2, default=str)
        if job.result_summary
        else "(none)"
    )

    error_block = ""
    if job.error_message:
        error_block = (
            '<table align="center" width="100%" border="0" cellpadding="0" cellspacing="0"'
            ' role="presentation" style="padding:16px 40px 0">'
            "<tbody><tr>"
            '<td style="background-color:#fef2f2;border-radius:8px;padding:16px;border:1px solid #fca5a5">'
            '<p style="font-size:13px;font-weight:700;color:#991b1b;margin:0 0 6px 0">Error</p>'
            f'<p style="font-size:13px;color:#7f1d1d;margin:0;white-space:pre-wrap;word-break:break-all">'
            f"{_escape_html(job.error_message)}</p>"
            "</td></tr></tbody></table>"
        )

    subject = f"[CarModPicker] {job_type_label} Job #{job.id} — {status_label}"

    template = _load_template("job_report")
    html = (
        template.replace("{{JOB_ID}}", str(job.id))
        .replace("{{JOB_TYPE_LABEL}}", job_type_label)
        .replace("{{STATUS_LABEL}}", status_label)
        .replace("{{STATUS_COLOR}}", status_color)
        .replace("{{TRIGGERED_BY}}", job.triggered_by.capitalize())
        .replace("{{STARTED_AT}}", started_str)
        .replace("{{COMPLETED_AT}}", completed_str)
        .replace("{{DURATION}}", duration_str)
        .replace("{{RESULT_SUMMARY}}", result_text)
        .replace("{{ERROR_BLOCK}}", error_block)
    )

    sent = 0
    for email in recipients:
        if _send(email, subject, html):
            sent += 1
    return sent


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_duration(started_at: datetime, completed_at: Optional[datetime]) -> str:
    if completed_at is None:
        return "—"
    s = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
    e = completed_at if completed_at.tzinfo else completed_at.replace(tzinfo=timezone.utc)
    total_seconds = int((e - s).total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
