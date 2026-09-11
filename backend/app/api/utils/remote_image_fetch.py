"""SSRF-hardened fetch of a caller-supplied remote image into memory."""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 3
CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 15.0

ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}


class RemoteImageError(HTTPException):
    """A remote image could not be fetched, with a client-safe reason."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> None:
        """Build a 4xx carrying a reason that leaks nothing about internal topology."""
        super().__init__(status_code=status_code, detail=detail)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for any address that is not a routable public destination.

    IPv4-mapped IPv6 forms are unwrapped so the inner address is judged, and the
    explicit range checks back up `is_global` across Python versions.
    """
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return _is_blocked_ip(ip.ipv4_mapped)
    if not ip.is_global:
        return True
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)


def _resolve_host(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a hostname to every address it answers with, or raise a 400."""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise RemoteImageError("Image host could not be resolved")
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addresses:
        raise RemoteImageError("Image host could not be resolved")
    return addresses


def assert_url_is_fetchable(url: str) -> None:
    """Reject anything but https pointing at a public address.

    Every resolved address must be public, not merely the first, since the one
    approved here is not necessarily the one the connection uses.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise RemoteImageError("Image URL must use https")
    host = parsed.hostname
    if not host:
        raise RemoteImageError("Image URL has no host")

    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None

    addresses = [literal] if literal is not None else _resolve_host(host)
    for address in addresses:
        if address is not None and _is_blocked_ip(address):
            raise RemoteImageError("Image URL resolves to a disallowed address")


def _content_type_extension(content_type: Optional[str]) -> str:
    """Map a response content type to an allowed image extension, or raise a 400."""
    base = (content_type or "").split(";")[0].strip().lower()
    extension = ALLOWED_CONTENT_TYPES.get(base)
    if extension is None:
        raise RemoteImageError(f"Unsupported image content type: {base or 'unknown'}")
    return extension


def fetch_remote_image(url: str) -> tuple[bytes, str]:
    """Fetch an image over https and return its bytes and file extension.

    Redirects are followed manually so every hop is re-checked by
    `assert_url_is_fetchable`, and the body streams against the upload size cap.
    """
    max_bytes = settings.max_image_size_bytes
    current_url = url
    timeout = httpx.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS)

    with httpx.Client(follow_redirects=False, timeout=timeout) as client:
        for _ in range(MAX_REDIRECTS + 1):
            assert_url_is_fetchable(current_url)
            try:
                with client.stream("GET", current_url) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise RemoteImageError("Image URL redirected without a destination")
                        current_url = str(response.url.join(location))
                        continue

                    if response.status_code != 200:
                        raise RemoteImageError(
                            f"Image host returned status {response.status_code}",
                            status_code=status.HTTP_502_BAD_GATEWAY,
                        )

                    extension = _content_type_extension(response.headers.get("content-type"))

                    declared = response.headers.get("content-length")
                    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                        raise RemoteImageError(
                            f"Image exceeds maximum size of {settings.MAX_IMAGE_SIZE_MB}MB",
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        )

                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > max_bytes:
                            raise RemoteImageError(
                                f"Image exceeds maximum size of {settings.MAX_IMAGE_SIZE_MB}MB",
                                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            )
                        chunks.append(chunk)

                    content = b"".join(chunks)
                    if not content:
                        raise RemoteImageError("Image host returned an empty body")
                    return content, extension
            except httpx.HTTPError as exc:
                logger.warning("Remote image fetch failed: %s", exc)
                raise RemoteImageError(
                    "Could not fetch the image from its source",
                    status_code=status.HTTP_502_BAD_GATEWAY,
                )

    raise RemoteImageError("Image URL redirected too many times")
