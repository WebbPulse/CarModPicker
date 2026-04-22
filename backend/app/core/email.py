import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

if TYPE_CHECKING:
    from app.api.models.background_job import BackgroundJob

# IN-07: declare the logger at module level (QUAL-07 idiom) so log records
# emitted from ``email.py`` carry ``name="app.core.email"`` instead of the
# shared ``app.core.logging.logger`` module name. Importing the module-level
# ``logger`` helper directly from ``app.core.logging`` is fine for runtime
# behavior, but it tags records with the logging-module's name and breaks
# log-routing filters keyed on module origin.
logger = logging.getLogger(__name__)

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
        elif job.job_type == "archive_rescrape":
            result_html = _render_archive_rescrape_result_html(job.result_summary)
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
    if r.get("rate_limit_bailout"):
        return "#d97706"  # amber: circuit-breaker trip (upstream shed load)
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
            rate_limit_badge = ""
            if r.get("rate_limit_bailout"):
                after = r.get("rate_limit_bailout_after") or 0
                total_urls = r.get("total", 0)
                rate_limit_badge = (
                    ' <span title="Rate-limit circuit breaker tripped"'
                    ' style="display:inline-block;background:#fef3c7;color:#92400e;'
                    "font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px;"
                    f'margin-left:4px">RATE-LIMITED @ {after}/{total_urls}</span>'
                )
            error_color = "#dc2626" if errors > 0 else "#9ca3af"
            rows_html.append(
                "<tr>"
                f'<td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;'
                f'border-left:3px solid {accent};font-family:monospace;font-weight:600;color:#18181b">'
                f"{name}{cancelled_badge}{rate_limit_badge}</td>"
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
            # CRAWL-07 (Plan 03-03): per-adapter ParseFailures block with up to
            # 5 sample URLs. Silent for healthy adapters (parse_failures==0) or
            # when the runner produced no samples. Rendered as a colspan row
            # directly under the main adapter row so the samples visually
            # belong to that adapter.
            parse_failures = r.get("parse_failures", 0)
            samples = r.get("sample_failure_urls") or []
            if parse_failures > 0 and samples:
                # Pitfall PR-01: truncate URLs > 160 chars (first-120 + ellipsis + last-40).
                # Bounds the row width at ~5 * 160 = 800 chars regardless of how
                # pathological a retailer URL is.
                def _trunc(u: str) -> str:
                    return u if len(u) <= 160 else f"{u[:120]}…{u[-40:]}"

                sample_html = "<br/>".join(_escape_html(_trunc(u)) for u in samples)
                rows_html.append(
                    '<tr><td colspan="5" style="font-size:11px;color:#6b7280;'
                    'padding:0 10px 8px 22px">'
                    f'<strong>ParseFailures:</strong> {parse_failures} / {r.get("total", 0)} — '
                    f"samples: {sample_html}"
                    "</td></tr>"
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

    # Per-adapter failure samples. One collapsed <details> block per adapter
    # so healthy adapters stay invisible but the operator can expand any that
    # had errors or parse misses to see the actual URLs.
    samples_html = _render_crawler_failure_samples(results)

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

    return header + table_html + samples_html + failed_html


def _render_url_sample_list(items: list[dict], max_display: int = 25) -> str:
    """Render up to ``max_display`` URL entries as a compact monospace list.
    Each item may have ``url``, ``status``, ``bucket``, ``error`` or ``outcome``/``source`` keys.
    """
    if not items:
        return ""
    rows: list[str] = []
    for entry in items[:max_display]:
        url = _escape_html(str(entry.get("url", "?")))
        tags: list[str] = []
        for key in ("source", "outcome", "status", "bucket"):
            v = entry.get(key)
            if v is None:
                continue
            tags.append(
                f'<span style="display:inline-block;background:#e5e7eb;color:#374151;'
                f"font-family:monospace;font-size:10px;padding:1px 5px;border-radius:3px;"
                f'margin-right:4px">{_escape_html(str(v))}</span>'
            )
        err = entry.get("error")
        err_html = (
            f'<div style="font-size:11px;color:#7f1d1d;margin-top:2px;'
            f'white-space:pre-wrap;word-break:break-word">{_escape_html(str(err))}</div>'
            if err
            else ""
        )
        rows.append(
            '<div style="padding:6px 0;border-bottom:1px solid #f3f4f6">'
            f'<div style="font-family:monospace;font-size:12px;color:#374151;'
            f'word-break:break-all">{url}</div>'
            f'<div style="margin-top:2px">{"".join(tags)}</div>'
            f"{err_html}</div>"
        )
    remainder = len(items) - max_display
    if remainder > 0:
        rows.append(
            '<div style="padding:6px 0;font-size:11px;color:#9ca3af;font-style:italic">'
            f"…and {remainder} more (sample capped).</div>"
        )
    return "".join(rows)


def _render_crawler_failure_samples(results: list[dict]) -> str:
    """Per-adapter <details> blocks listing sampled error URLs and parse-miss URLs.
    Silent for adapters that had no errors or parse misses."""
    blocks: list[str] = []
    for r in results:
        adapter = _escape_html(str(r.get("adapter", "?")))
        error_urls = r.get("error_urls") or []
        parse_miss_urls = r.get("parse_miss_urls") or []
        errors_total = int(r.get("errors") or 0)
        misses_total = int(r.get("skipped_not_product") or 0)
        if not error_urls and not parse_miss_urls:
            continue
        pieces: list[str] = []
        if error_urls:
            trunc = bool(r.get("error_urls_truncated"))
            pieces.append(
                '<div style="margin-top:8px">'
                '<div style="font-size:11px;color:#991b1b;text-transform:uppercase;'
                'letter-spacing:0.05em;font-weight:600;margin-bottom:4px">'
                f"Errors ({errors_total}{'+' if trunc else ''})</div>"
                f"{_render_url_sample_list(error_urls)}</div>"
            )
        if parse_miss_urls:
            trunc = bool(r.get("parse_miss_urls_truncated"))
            pieces.append(
                '<div style="margin-top:8px">'
                '<div style="font-size:11px;color:#92400e;text-transform:uppercase;'
                'letter-spacing:0.05em;font-weight:600;margin-bottom:4px">'
                f"Parse misses ({misses_total}{'+' if trunc else ''})</div>"
                f"{_render_url_sample_list(parse_miss_urls)}</div>"
            )
        blocks.append(
            '<details style="background:#ffffff;border:1px solid #e4e4e7;'
            'border-radius:8px;padding:10px 12px;margin-top:8px">'
            f'<summary style="cursor:pointer;font-family:monospace;font-weight:600;'
            f'color:#18181b;font-size:13px">{adapter} '
            f'<span style="font-weight:400;color:#6b7280">— '
            f"{errors_total} error(s), {misses_total} parse miss(es)</span></summary>" + "".join(pieces) + "</details>"
        )
    if not blocks:
        return ""
    return (
        '<div style="margin-top:12px">'
        '<div style="font-size:11px;color:#6b7280;text-transform:uppercase;'
        'letter-spacing:0.05em;margin-bottom:4px">Failure samples</div>' + "".join(blocks) + "</div>"
    )


def _render_archive_rescrape_result_html(summary: dict) -> str:
    """
    Rich report for archive_rescrape jobs: outcome-count strip plus a list of
    per-URL failures (bounded by the worker).
    """
    parsed_ok = int(summary.get("parsed_ok") or 0)
    parse_failed = int(summary.get("parse_failed") or 0)
    ingest_failed = int(summary.get("ingest_failed") or 0)
    skipped_no_adapter = int(summary.get("skipped_no_adapter") or 0)
    skipped_no_html = int(summary.get("skipped_no_html") or 0)
    failures = summary.get("failures") or []
    failures_total = int(summary.get("failures_total") or len(failures))
    truncated = bool(summary.get("failures_truncated"))

    def _stat(label: str, value: int, fg: str) -> str:
        return (
            f'<td style="font-size:12px;color:#6b7280;padding-right:16px">{label}<br/>'
            f'<span style="font-size:18px;color:{fg};font-weight:700">{value:,}</span></td>'
        )

    header = (
        '<div style="background-color:#f8f8f8;border:1px solid #e4e4e7;'
        'border-radius:8px;padding:16px;margin-bottom:12px">'
        '<table width="100%" cellpadding="0" cellspacing="0" role="presentation">'
        "<tbody><tr>"
        + _stat("Parsed OK", parsed_ok, "#16a34a")
        + _stat("Parse failed", parse_failed, "#dc2626" if parse_failed else "#9ca3af")
        + _stat("Ingest failed", ingest_failed, "#dc2626" if ingest_failed else "#9ca3af")
        + _stat("No adapter", skipped_no_adapter, "#6b7280")
        + _stat("No HTML", skipped_no_html, "#6b7280")
        + "</tr></tbody></table></div>"
    )

    if not failures:
        return header

    failures_html = _render_url_sample_list(failures, max_display=100)
    trunc_note = (
        f'<p style="font-size:11px;color:#9ca3af;margin:6px 0 0 0">'
        f"Showing {len(failures)} of {failures_total} failure(s); worker capped the sample."
        "</p>"
        if truncated
        else ""
    )
    return (
        header + '<div style="background-color:#ffffff;border:1px solid #fecaca;'
        'border-radius:8px;padding:12px;margin-top:8px">'
        '<p style="font-size:13px;font-weight:700;color:#991b1b;margin:0 0 6px 0">'
        f"Failures ({failures_total})</p>" + failures_html + trunc_note + "</div>"
    )
