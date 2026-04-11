from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.logging import logger

_TEMPLATES_DIR = Path(__file__).parent / "email_templates"
_CONFIG_SET = "carmodpicker-transactional"

VERIFY_EMAIL_SUBJECT = "Verify your CarModPicker email address"
RESET_PASSWORD_SUBJECT = "Reset your CarModPicker password"


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
