"""
Helpers for archiving extension-uploaded HTML to S3 (or local disk fallback)
and computing the canonical URL key used for dedup.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional, Protocol, cast
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

logger = logging.getLogger(__name__)

CRAWL_HTML_HASH_BYTES = 16

_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "twclid",
        "ref",
        "source",
    }
)


class _S3PutObjectProtocol(Protocol):
    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str) -> object: ...
    def get_object(self, *, Bucket: str, Key: str) -> dict: ...
    def list_objects_v2(self, **kwargs: object) -> dict: ...


_crawl_s3_client: Optional[_S3PutObjectProtocol] = None
_crawl_bucket_name: Optional[str] = None


def crawl_html_utf8_bytes(html: str) -> bytes:
    return html.encode("utf-8", errors="replace")


def crawl_html_fingerprint(html: str) -> tuple[bytes, int, str]:
    """Return (utf8_bytes, byte_length, sha256_hexdigest)."""
    b = crawl_html_utf8_bytes(html)
    return b, len(b), hashlib.sha256(b).hexdigest()


def canonicalize_url(url: str) -> str:
    """Lowercase scheme/host, drop fragment, strip tracking params, normalize root path."""
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    path = parsed.path
    if path == "/":
        path = ""

    qs_filtered = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k.lower() not in _TRACKING_PARAMS
    }
    query = urlencode(qs_filtered, doseq=True)

    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def get_crawl_s3_client() -> tuple[Optional[_S3PutObjectProtocol], Optional[str]]:
    """Return (s3_client, bucket_name) for the crawl-archive bucket; else (None, None)."""
    global _crawl_s3_client, _crawl_bucket_name
    if _crawl_s3_client is not None or _crawl_bucket_name is not None:
        return _crawl_s3_client, _crawl_bucket_name
    try:
        from app.core.config import settings

        bucket = (settings.CRAWL_BUCKET or "").strip()
        if not bucket:
            return None, None
        import boto3
        from botocore.config import Config as BotoConfig

        client_kwargs: dict[str, Any] = {
            "region_name": settings.AWS_REGION or None,
            "endpoint_url": settings.S3_ENDPOINT_URL or None,
            "config": BotoConfig(max_pool_connections=100),
        }
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _crawl_s3_client = cast(_S3PutObjectProtocol, boto3.client("s3", **client_kwargs))
        _crawl_bucket_name = bucket
        return _crawl_s3_client, _crawl_bucket_name
    except Exception as e:
        logger.info("Crawl HTML bucket not available: %s", e)
        return None, None


def save_extension_html(
    product_url: str,
    html: str,
    *,
    html_utf8: Optional[bytes] = None,
    logger_instance: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Save extension HTML to S3 (or local disk fallback). Returns the storage key
    (S3 key or absolute local path) on success, ``None`` on failure.
    """
    log = logger_instance or logger
    canonical = canonicalize_url(product_url)
    url_hash = hashlib.sha256(canonical.encode()).hexdigest()[:CRAWL_HTML_HASH_BYTES]
    html_key = f"crawl_html/by_url/{url_hash}.html"
    url_key = f"crawl_html/by_url/{url_hash}.url"
    body_bytes = html_utf8 if html_utf8 is not None else html.encode("utf-8", errors="replace")

    s3_client, bucket_name = get_crawl_s3_client()
    if s3_client is not None and bucket_name is not None:
        try:
            s3_client.put_object(Bucket=bucket_name, Key=html_key, Body=body_bytes, ContentType="text/html; charset=utf-8")
            s3_client.put_object(Bucket=bucket_name, Key=url_key, Body=product_url.encode("utf-8"), ContentType="text/plain; charset=utf-8")
            log.debug("Saved page copy to bucket: %s", html_key)
            return html_key
        except Exception as e:
            log.warning("Could not save page copy to bucket %s: %s", html_key, e)
            return None

    base_path = Path("crawl_html")
    if not base_path.exists():
        base_path.mkdir(parents=True, exist_ok=True)
    dir_path = base_path / "by_url"
    dir_path.mkdir(parents=True, exist_ok=True)
    html_path = dir_path / f"{url_hash}.html"
    url_path = dir_path / f"{url_hash}.url"
    try:
        html_path.write_bytes(body_bytes)
        url_path.write_bytes(product_url.encode("utf-8"))
        return str(html_path.resolve())
    except Exception as e:
        log.warning("Could not save page copy locally: %s", e)
        return None
