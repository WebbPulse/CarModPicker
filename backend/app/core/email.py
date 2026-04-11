from typing import Any, Optional, cast

import requests
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import From, Mail, To

from app.core.config import settings
from app.core.logging import logger

VERIFY_EMAIL_TEMPLATE_ID = "d-91e5943cbda84ed8945e83bd6fe781e5"
RESET_PASSWORD_TEMPLATE_ID = "d-20d2121876084bb6a3ed25ef22fd9ad1"


def send_email(to_email: str, template_id: str, dynamic_template_data: dict[str, Any]) -> Optional[int]:
    """
    Send an email using SendGrid.
    Args:
        to_email (str): Recipient's email address.
        template_id (str): ID of the email template to use.
        dynamic_template_data (dict): Dynamic data to populate the email template.
    Returns:
        int: HTTP status code of the response if successful, None if an error occurs.
    """
    message = Mail(
        from_email=From(settings.EMAIL_FROM),
        to_emails=To(to_email),
    )
    message.template_id = template_id
    message.dynamic_template_data = dynamic_template_data

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        # SendGrid's send() returns a requests.Response, but type stubs are incomplete
        response = cast(requests.Response, sg.send(message))  # type: ignore[arg-type]
        # SendGrid response object has status_code attribute
        return int(response.status_code)
    except Exception as e:
        # Log or handle error as needed
        logger.error(f"Failed to send email: {e}")
        return None
