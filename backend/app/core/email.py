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
    if not settings.EMAIL_ENABLED:
        logger.debug(f"Email disabled — skipping send to {to_email} (subject: {subject!r})")
        return False
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

    if job.result_summary:
        if job.job_type == "crawler_run":
            result_html = _render_crawler_result_html(job.result_summary)
        else:
            result_html = _render_json_result_html(job.result_summary)
    else:
        result_html = _render_json_result_html(None)

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
        .replace("{{RESULT_SUMMARY}}", result_html)
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
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _render_json_result_html(summary: Optional[dict]) -> str:
    """Fallback rendering for non-crawler job result summaries — preserves the
    pre-existing monospace JSON block."""
    text = json.dumps(summary, indent=2, default=str) if summary else "(none)"
    return (
        '<div style="background-color:#f8f8f8;border-radius:8px;padding:16px;'
        "border:1px solid #e4e4e7;font-family:monospace;font-size:13px;"
        'color:#374151;white-space:pre-wrap;word-break:break-all">'
        f"{_escape_html(text)}</div>"
    )


def _render_http_error_pills(http_errors: dict) -> str:
    """Render per-status error counters as small inline pills. HTTP 4xx statuses
    are amber, 5xx red, non-HTTP buckets gray."""
    if not http_errors:
        return '<span style="font-size:12px;color:#9ca3af">none</span>'
    entries = sorted(http_errors.items(), key=lambda kv: (-kv[1], kv[0]))
    pieces: list[str] = []
    for bucket, count in entries:
        if bucket.isdigit():
            code = int(bucket)
            if 500 <= code < 600:
                bg, fg = "#fee2e2", "#991b1b"
            elif 400 <= code < 500:
                bg, fg = "#fef3c7", "#92400e"
            else:
                bg, fg = "#e5e7eb", "#374151"
            label = bucket
        else:
            bg, fg = "#e5e7eb", "#374151"
            label = bucket
        pieces.append(
            f'<span style="display:inline-block;background:{bg};color:{fg};'
            "font-family:monospace;font-size:11px;font-weight:600;"
            "padding:2px 6px;border-radius:4px;margin:0 4px 2px 0;"
            f'white-space:nowrap">{_escape_html(label)}×{count}</span>'
        )
    return "".join(pieces)


def _adapter_row_accent(r: dict) -> str:
    """Pick a small colored left-border per adapter to draw the eye to the
    worst offenders without making healthy adapters visually noisy."""
    total = r.get("total", 0)
    ingested = r.get("ingested", 0)
    errors = r.get("errors", 0)
    if total > 0 and ingested == 0:
        return "#dc2626"  # red: parser broken / sitewide failure
    if errors > 0 and errors >= max(1, total // 4):
        return "#f59e0b"  # amber: high error rate
    if r.get("cancelled"):
        return "#6b7280"  # gray: cancelled
    return "#16a34a"  # green: healthy


def _render_crawler_result_html(summary: dict) -> str:
    """Rich per-adapter report for crawler_run jobs. Includes overall totals,
    a per-adapter table with skipped breakdown + HTTP error pills, and a
    failed-adapters block (adapters that raised before completing a run)."""
    results: list[dict] = summary.get("results") or []
    failed: list[dict] = summary.get("failed") or []
    agg = summary.get("summary") or {}

    total_ingested = agg.get("total_ingested", 0)
    total_skipped = agg.get("total_skipped", 0)
    total_errors = agg.get("total_errors", 0)
    total_http_errors = agg.get("total_http_errors") or {}
    total_urls = sum(r.get("total", 0) for r in results)

    # Header strip with aggregate numbers.
    header = (
        '<div style="background-color:#f8f8f8;border:1px solid #e4e4e7;'
        'border-radius:8px;padding:16px;margin-bottom:12px">'
        '<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
        "<tbody><tr>"
        f'<td style="font-size:12px;color:#6b7280;padding-right:16px">Adapters<br/>'
        f'<span style="font-size:18px;color:#18181b;font-weight:700">{len(results)}</span></td>'
        f'<td style="font-size:12px;color:#6b7280;padding-right:16px">URLs<br/>'
        f'<span style="font-size:18px;color:#18181b;font-weight:700">{total_urls:,}</span></td>'
        f'<td style="font-size:12px;color:#6b7280;padding-right:16px">Ingested<br/>'
        f'<span style="font-size:18px;color:#16a34a;font-weight:700">{total_ingested:,}</span></td>'
        f'<td style="font-size:12px;color:#6b7280;padding-right:16px">Skipped<br/>'
        f'<span style="font-size:18px;color:#6b7280;font-weight:700">{total_skipped:,}</span></td>'
        f'<td style="font-size:12px;color:#6b7280">Errors<br/>'
        f'<span style="font-size:18px;color:#dc2626;font-weight:700">{total_errors:,}</span></td>'
        "</tr></tbody></table>"
    )
    if total_http_errors:
        header += (
            '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #e4e4e7">'
            '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;'
            'letter-spacing:0.05em;margin-bottom:6px">Overall HTTP error breakdown</div>'
            f"<div>{_render_http_error_pills(total_http_errors)}</div>"
            "</div>"
        )
    header += "</div>"

    # Per-adapter table.
    if results:
        sorted_results = sorted(
            results,
            key=lambda r: (
                -(r.get("errors", 0) + (1 if r.get("total", 0) > 0 and r.get("ingested", 0) == 0 else 0) * 1000),
                r.get("adapter", ""),
            ),
        )
        rows_html = [
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
            'style="border-collapse:collapse;font-size:13px;margin-top:4px">'
            "<thead><tr>"
            '<th align="left" style="padding:8px 10px;border-bottom:2px solid #e4e4e7;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">Adapter</th>'
            '<th align="right" style="padding:8px 10px;border-bottom:2px solid #e4e4e7;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">Ingested / Total</th>'
            '<th align="right" style="padding:8px 10px;border-bottom:2px solid #e4e4e7;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">Skipped (rb/np/gone)</th>'
            '<th align="right" style="padding:8px 10px;border-bottom:2px solid #e4e4e7;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">Errors</th>'
            '<th align="left" style="padding:8px 10px;border-bottom:2px solid #e4e4e7;color:#6b7280;font-size:11px;text-transform:uppercase;letter-spacing:0.05em;font-weight:600">HTTP breakdown</th>'
            "</tr></thead><tbody>"
        ]
        for r in sorted_results:
            accent = _adapter_row_accent(r)
            name = _escape_html(str(r.get("adapter", "?")))
            ingested = r.get("ingested", 0)
            total = r.get("total", 0)
            skipped_robots = r.get("skipped_robots", 0)
            skipped_not_product = r.get("skipped_not_product", 0)
            skipped_gone = r.get("skipped_gone", 0)
            errors = r.get("errors", 0)
            cancelled_badge = (
                ' <span style="display:inline-block;background:#e5e7eb;color:#374151;'
                "font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;"
                'margin-left:4px">CANCELLED</span>'
                if r.get("cancelled")
                else ""
            )
            error_color = "#dc2626" if errors > 0 else "#9ca3af"
            rows_html.append(
                "<tr>"
                f'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;'
                f'border-left:3px solid {accent};font-family:monospace;font-weight:600;color:#18181b">'
                f"{name}{cancelled_badge}</td>"
                f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #f3f4f6;'
                f'font-variant-numeric:tabular-nums;color:#18181b">'
                f'<span style="color:#16a34a;font-weight:600">{ingested:,}</span>'
                f'<span style="color:#9ca3af"> / </span>{total:,}</td>'
                f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #f3f4f6;'
                f'font-variant-numeric:tabular-nums;color:#6b7280;font-size:12px">'
                f"{skipped_robots}/{skipped_not_product}/{skipped_gone}</td>"
                f'<td align="right" style="padding:8px 10px;border-bottom:1px solid #f3f4f6;'
                f'font-variant-numeric:tabular-nums;color:{error_color};font-weight:600">{errors}</td>'
                f'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6">'
                f"{_render_http_error_pills(r.get('http_errors') or {})}</td>"
                "</tr>"
            )
        rows_html.append("</tbody></table>")
        table_html = (
            '<div style="background-color:#ffffff;border:1px solid #e4e4e7;'
            'border-radius:8px;padding:4px;overflow-x:auto">' + "".join(rows_html) + "</div>"
            '<p style="font-size:11px;color:#9ca3af;margin:6px 0 0 0">'
            "Skipped legend: rb = robots.txt · np = non-product page · gone = HTTP 404/410."
            "</p>"
        )
    else:
        table_html = '<p style="font-size:13px;color:#6b7280;margin:0">No adapters completed.</p>'

    # Adapters that raised before returning a result dict.
    failed_html = ""
    if failed:
        rows = []
        for f in failed:
            name = _escape_html(str(f.get("adapter", "?")))
            err = _escape_html(str(f.get("error", "")))
            rows.append(
                "<tr>"
                f'<td style="padding:6px 10px;border-bottom:1px solid #fecaca;'
                f'font-family:monospace;color:#991b1b;font-weight:600">{name}</td>'
                f'<td style="padding:6px 10px;border-bottom:1px solid #fecaca;'
                f'color:#7f1d1d;white-space:pre-wrap;word-break:break-word;font-size:12px">{err}</td>'
                "</tr>"
            )
        failed_html = (
            '<div style="background-color:#fef2f2;border:1px solid #fca5a5;'
            'border-radius:8px;padding:12px;margin-top:12px">'
            '<p style="font-size:13px;font-weight:700;color:#991b1b;margin:0 0 6px 0">'
            f"Adapters that raised ({len(failed)})</p>"
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
            "<tbody>" + "".join(rows) + "</tbody></table></div>"
        )

    return header + table_html + failed_html
