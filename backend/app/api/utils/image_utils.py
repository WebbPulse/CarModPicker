"""
Utility functions for handling image file keys and presigned URLs.
"""

import logging
from typing import Optional

from app.api.services.storage_service import storage_service

logger = logging.getLogger(__name__)


def is_file_key(value: Optional[str]) -> bool:
    """
    Check if a string is an S3 file key vs a regular URL.

    File keys typically have the format: entity_type/user_hash/entity_id-unique_id.extension
    Regular URLs start with http:// or https://

    Args:
        value: String to check

    Returns:
        True if it looks like a file key, False otherwise
    """
    if not value:
        return False

    # If it starts with http:// or https://, it's a URL, not a file key
    if value.startswith(("http://", "https://")):
        return False

    # File keys typically contain forward slashes and don't start with http
    # They have the pattern: entity_type/user_hash/filename
    if "/" in value and not value.startswith(("http://", "https://")):
        return True

    return False


def get_presigned_url_from_file_key(file_key: Optional[str]) -> Optional[str]:
    """
    Convert a file key to a presigned URL if it's a file key, otherwise return as-is.

    Args:
        file_key: File key from database or URL string

    Returns:
        Presigned URL if file_key is a file key, original value if it's already a URL or None
    """
    if not file_key:
        return None

    # If it's not a file key (already a URL), return as-is
    if not is_file_key(file_key):
        return file_key

    # Convert file key to presigned URL
    try:
        return storage_service.get_presigned_url(file_key)
    except Exception as e:
        logger.warning(f"Failed to generate presigned URL for {file_key}: {str(e)}")
        # Return the file key as fallback (frontend can handle it)
        return file_key
