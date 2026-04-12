"""Tests for email sending functionality."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ["ENABLE_RATE_LIMITING"] = "false"

from app.core.email import send_reset_password_email, send_verify_email  # noqa: E402


class TestEmailService:
    """Test cases for the SES-based email service."""

    @patch("app.core.email.settings")
    @patch("app.core.email.boto3.client")
    def test_send_verify_email_success(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
        """send_verify_email returns True and calls SES send_email on success."""
        mock_settings.EMAIL_ENABLED = True
        mock_settings.EMAIL_FROM = "noreply@example.com"
        mock_settings.AWS_REGION = "us-east-1"
        mock_ses = MagicMock()
        mock_boto_client.return_value = mock_ses

        result = send_verify_email("user@example.com", "https://example.com/verify?token=abc")

        assert result is True
        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args[1]
        assert call_kwargs["Destination"] == {"ToAddresses": ["user@example.com"]}
        assert "https://example.com/verify?token=abc" in call_kwargs["Content"]["Simple"]["Body"]["Html"]["Data"]

    @patch("app.core.email.settings")
    @patch("app.core.email.boto3.client")
    def test_send_reset_password_email_success(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
        """send_reset_password_email returns True and calls SES send_email on success."""
        mock_settings.EMAIL_ENABLED = True
        mock_settings.EMAIL_FROM = "noreply@example.com"
        mock_settings.AWS_REGION = "us-east-1"
        mock_ses = MagicMock()
        mock_boto_client.return_value = mock_ses

        result = send_reset_password_email("user@example.com", "https://example.com/reset?token=xyz")

        assert result is True
        mock_ses.send_email.assert_called_once()
        call_kwargs = mock_ses.send_email.call_args[1]
        assert call_kwargs["Destination"] == {"ToAddresses": ["user@example.com"]}
        assert "https://example.com/reset?token=xyz" in call_kwargs["Content"]["Simple"]["Body"]["Html"]["Data"]

    @patch("app.core.email.boto3.client")
    def test_send_verify_email_ses_error(self, mock_boto_client: MagicMock) -> None:
        """send_verify_email returns False when SES raises an error."""
        from botocore.exceptions import ClientError

        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = ClientError(
            {"Error": {"Code": "MessageRejected", "Message": "Email address not verified"}},
            "SendEmail",
        )
        mock_boto_client.return_value = mock_ses

        result = send_verify_email("unverified@example.com", "https://example.com/verify")

        assert result is False

    @patch("app.core.email.boto3.client")
    def test_send_reset_password_email_ses_error(self, mock_boto_client: MagicMock) -> None:
        """send_reset_password_email returns False when SES raises an error."""
        from botocore.exceptions import BotoCoreError

        mock_ses = MagicMock()
        mock_ses.send_email.side_effect = BotoCoreError()
        mock_boto_client.return_value = mock_ses

        result = send_reset_password_email("user@example.com", "https://example.com/reset")

        assert result is False

    def test_verify_email_template_contains_placeholder(self) -> None:
        """Rendered verify_email.html template file contains the placeholder token."""
        from app.core.email import _TEMPLATES_DIR

        html = (_TEMPLATES_DIR / "verify_email.html").read_text()
        assert "{{VERIFY_EMAIL_LINK}}" in html

    def test_reset_password_template_contains_placeholder(self) -> None:
        """Rendered reset_password.html template file contains the placeholder token."""
        from app.core.email import _TEMPLATES_DIR

        html = (_TEMPLATES_DIR / "reset_password.html").read_text()
        assert "{{RESET_PASSWORD_LINK}}" in html

    @patch("app.core.email.settings")
    @patch("app.core.email.boto3.client")
    def test_config_set_name_passed_to_ses(self, mock_boto_client: MagicMock, mock_settings: MagicMock) -> None:
        """SES calls include the carmodpicker-transactional configuration set."""
        mock_settings.EMAIL_ENABLED = True
        mock_settings.EMAIL_FROM = "noreply@example.com"
        mock_settings.AWS_REGION = "us-east-1"
        mock_ses = MagicMock()
        mock_boto_client.return_value = mock_ses

        send_verify_email("user@example.com", "https://example.com/verify")

        call_kwargs = mock_ses.send_email.call_args[1]
        assert call_kwargs["ConfigurationSetName"] == "carmodpicker-transactional"
