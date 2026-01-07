"""Tests for email sending functionality."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

# Disable rate limiting for tests
os.environ["ENABLE_RATE_LIMITING"] = "false"

from app.core.email import send_email  # noqa: E402


@pytest.mark.skip(reason="SendGrid subscription is currently disabled")
class TestEmailService:
    """Test cases for email service."""

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_success(self, mock_sendgrid_client: Mock) -> None:
        """Test successful email sending."""
        # Mock the SendGrid client and response
        mock_response = MagicMock()
        mock_response.status_code = 202  # SendGrid success code
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sendgrid_client.return_value = mock_sg_instance

        # Test sending email
        to_email = "test@example.com"
        template_id = "d-template123"
        dynamic_data = {"verify_email_link": "https://example.com/verify"}

        result = send_email(to_email, template_id, dynamic_data)

        # Verify result
        assert result == 202
        mock_sendgrid_client.assert_called_once()
        mock_sg_instance.send.assert_called_once()

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_api_error(self, mock_sendgrid_client: Mock) -> None:
        """Test email sending with API error."""
        # Mock the SendGrid client to raise an exception
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = Exception("SendGrid API Error")
        mock_sendgrid_client.return_value = mock_sg_instance

        # Test sending email with error
        to_email = "test@example.com"
        template_id = "d-template123"
        dynamic_data = {"verify_email_link": "https://example.com/verify"}

        result = send_email(to_email, template_id, dynamic_data)

        # Should return None on error
        assert result is None
        mock_sendgrid_client.assert_called_once()

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_with_complex_template_data(self, mock_sendgrid_client: Mock) -> None:
        """Test sending email with complex template data."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sendgrid_client.return_value = mock_sg_instance

        # Test with complex template data
        to_email = "user@example.com"
        template_id = "d-complex-template"
        dynamic_data = {
            "username": "testuser",
            "action_url": "https://example.com/action",
            "support_email": "support@example.com",
        }

        result = send_email(to_email, template_id, dynamic_data)

        assert result == 202
        mock_sg_instance.send.assert_called_once()

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_network_error(self, mock_sendgrid_client: Mock) -> None:
        """Test email sending with network error."""
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.side_effect = ConnectionError("Network error")
        mock_sendgrid_client.return_value = mock_sg_instance

        result = send_email(
            "test@example.com",
            "d-template123",
            {"data": "value"},
        )

        assert result is None

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_invalid_template(self, mock_sendgrid_client: Mock) -> None:
        """Test email sending with invalid template."""
        mock_response = MagicMock()
        mock_response.status_code = 400  # Bad request
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sendgrid_client.return_value = mock_sg_instance

        # Should still return the status code even if it's an error
        result = send_email(
            "test@example.com",
            "d-invalid-template",
            {"data": "value"},
        )

        assert result == 400

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_creates_proper_from_and_to(self, mock_sendgrid_client: Mock) -> None:
        """Test that email properly sets from and to addresses."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sendgrid_client.return_value = mock_sg_instance

        to_email = "recipient@example.com"
        result = send_email(to_email, "d-template", {})

        assert result == 202

        # Verify send was called
        mock_sg_instance.send.assert_called_once()

    @patch("app.core.email.SendGridAPIClient")
    def test_send_email_with_empty_dynamic_data(self, mock_sendgrid_client: Mock) -> None:
        """Test email sending with empty dynamic template data."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_instance = MagicMock()
        mock_sg_instance.send.return_value = mock_response
        mock_sendgrid_client.return_value = mock_sg_instance

        result = send_email("test@example.com", "d-template", {})

        assert result == 202
        mock_sg_instance.send.assert_called_once()
