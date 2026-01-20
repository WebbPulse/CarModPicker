"""Tests for image utility functions."""

from unittest.mock import MagicMock, patch

from app.api.utils.image_utils import get_presigned_url_from_file_key, is_file_key


class TestImageUtils:
    """Test cases for image utility functions."""

    def test_is_file_key_with_file_key(self) -> None:
        """Test detecting a file key."""
        file_key = "global_parts/user_hash/123-abc.jpg"
        assert is_file_key(file_key) is True

    def test_is_file_key_with_http_url(self) -> None:
        """Test detecting an HTTP URL (not a file key)."""
        url = "http://example.com/image.jpg"
        assert is_file_key(url) is False

    def test_is_file_key_with_https_url(self) -> None:
        """Test detecting an HTTPS URL (not a file key)."""
        url = "https://example.com/image.jpg"
        assert is_file_key(url) is False

    def test_is_file_key_with_none(self) -> None:
        """Test detecting None (not a file key)."""
        assert is_file_key(None) is False

    def test_is_file_key_with_empty_string(self) -> None:
        """Test detecting empty string (not a file key)."""
        assert is_file_key("") is False

    def test_get_presigned_url_from_file_key_with_file_key(self) -> None:
        """Test converting file key to presigned URL."""
        file_key = "global_parts/user_hash/123-abc.jpg"
        expected_url = "https://storage.example.com/presigned-url"

        with patch("app.api.utils.image_utils.storage_service") as mock_storage:
            mock_storage.get_presigned_url.return_value = expected_url
            result = get_presigned_url_from_file_key(file_key)
            assert result == expected_url
            mock_storage.get_presigned_url.assert_called_once_with(file_key)

    def test_get_presigned_url_from_file_key_with_url(self) -> None:
        """Test that regular URL is returned as-is."""
        url = "https://example.com/image.jpg"
        result = get_presigned_url_from_file_key(url)
        assert result == url

    def test_get_presigned_url_from_file_key_with_none(self) -> None:
        """Test that None is returned as None."""
        result = get_presigned_url_from_file_key(None)
        assert result is None

    def test_get_presigned_url_from_file_key_error_handling(self) -> None:
        """Test error handling when presigned URL generation fails."""
        file_key = "global_parts/user_hash/123-abc.jpg"

        with patch("app.api.utils.image_utils.storage_service") as mock_storage:
            mock_storage.get_presigned_url.side_effect = Exception("Storage error")
            # Should return file key as fallback
            result = get_presigned_url_from_file_key(file_key)
            assert result == file_key
