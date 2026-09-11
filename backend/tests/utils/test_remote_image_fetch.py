"""SSRF guards on the server side image fetch.

These are the cases the browser used to make impossible by refusing the fetch
outright. Now that the server performs it, each one has to be refused here.
"""

from __future__ import annotations

import io
from typing import Any, Iterator

import httpx
import pytest

from app.api.utils.remote_image_fetch import (
    ALLOWED_CONTENT_TYPES,
    MAX_REDIRECTS,
    RemoteImageError,
    assert_url_is_fetchable,
    fetch_remote_image,
)
from app.core.config import settings

PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def resolve_public(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every hostname to a public address unless a test overrides it."""
    monkeypatch.setattr(
        "app.api.utils.remote_image_fetch.socket.getaddrinfo",
        lambda host, *a, **k: [(2, 1, 6, "", (PUBLIC_IP, 0))],
    )


def resolve_to(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    """Point named hosts at chosen addresses, leaving the rest public."""

    def fake(host: str, *args: Any, **kwargs: Any) -> list[tuple[int, int, int, str, tuple[str, int]]]:
        return [(2, 1, 6, "", (mapping.get(host, PUBLIC_IP), 0))]

    monkeypatch.setattr("app.api.utils.remote_image_fetch.socket.getaddrinfo", fake)


class TestUrlGuards:
    """`assert_url_is_fetchable` rejects everything that is not public https."""

    def test_http_scheme_rejected(self) -> None:
        with pytest.raises(RemoteImageError) as exc:
            assert_url_is_fetchable("http://example.com/a.jpg")
        assert "https" in str(exc.value.detail)

    @pytest.mark.parametrize(
        "scheme_url", ["file:///etc/passwd", "ftp://example.com/a.jpg", "data:image/png;base64,AA"]
    )
    def test_non_http_schemes_rejected(self, scheme_url: str) -> None:
        with pytest.raises(RemoteImageError):
            assert_url_is_fetchable(scheme_url)

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1",
            "10.0.0.5",
            "192.168.1.1",
            "172.16.0.1",
            "169.254.169.254",
            "[::1]",
            "[::ffff:127.0.0.1]",
            "0.0.0.0",
        ],
    )
    def test_private_and_metadata_literals_rejected(self, host: str) -> None:
        with pytest.raises(RemoteImageError) as exc:
            assert_url_is_fetchable(f"https://{host}/a.jpg")
        assert "disallowed address" in str(exc.value.detail)

    def test_hostname_resolving_to_metadata_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resolve_to(monkeypatch, {"evil.example.com": "169.254.169.254"})
        with pytest.raises(RemoteImageError) as exc:
            assert_url_is_fetchable("https://evil.example.com/a.jpg")
        assert "disallowed address" in str(exc.value.detail)

    def test_hostname_resolving_to_private_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        resolve_to(monkeypatch, {"internal.example.com": "10.1.2.3"})
        with pytest.raises(RemoteImageError):
            assert_url_is_fetchable("https://internal.example.com/a.jpg")

    def test_public_host_allowed(self) -> None:
        assert_url_is_fetchable("https://cdn.example.com/a.jpg")

    def test_unresolvable_host_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*args: Any, **kwargs: Any) -> None:
            raise __import__("socket").gaierror("nope")

        monkeypatch.setattr("app.api.utils.remote_image_fetch.socket.getaddrinfo", boom)
        with pytest.raises(RemoteImageError) as exc:
            assert_url_is_fetchable("https://nowhere.example.com/a.jpg")
        assert "resolved" in str(exc.value.detail)


def mount_transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    """Make the module's httpx.Client answer from a mock transport."""
    real_init = httpx.Client.__init__

    def patched(self: httpx.Client, *args: Any, **kwargs: Any) -> None:
        kwargs["transport"] = httpx.MockTransport(handler)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr("app.api.utils.remote_image_fetch.httpx.Client.__init__", patched)


def image_response(content: bytes = b"\xff\xd8\xff\xe0fake", content_type: str = "image/jpeg") -> httpx.Response:
    """A plain 200 carrying image bytes."""
    return httpx.Response(200, content=content, headers={"content-type": content_type})


class TestFetchRemoteImage:
    """The fetch itself: content types, size cap, redirects and errors."""

    def test_fetches_public_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mount_transport(monkeypatch, lambda request: image_response())
        content, extension = fetch_remote_image("https://cdn.example.com/a.jpg")
        assert content == b"\xff\xd8\xff\xe0fake"
        assert extension == "jpg"

    @pytest.mark.parametrize("content_type,expected", sorted(ALLOWED_CONTENT_TYPES.items()))
    def test_allowed_content_types(self, monkeypatch: pytest.MonkeyPatch, content_type: str, expected: str) -> None:
        mount_transport(monkeypatch, lambda request: image_response(content_type=content_type))
        _, extension = fetch_remote_image("https://cdn.example.com/a")
        assert extension == expected

    @pytest.mark.parametrize("content_type", ["text/html", "application/json", "image/svg+xml", "application/pdf", ""])
    def test_wrong_content_type_rejected(self, monkeypatch: pytest.MonkeyPatch, content_type: str) -> None:
        mount_transport(monkeypatch, lambda request: image_response(content_type=content_type))
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a")
        assert exc.value.status_code == 400
        assert "content type" in str(exc.value.detail)

    def test_oversize_by_declared_length_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        too_big = settings.max_image_size_bytes + 1

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=b"x",
                headers={"content-type": "image/png", "content-length": str(too_big)},
            )

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.png")
        assert exc.value.status_code == 413

    def test_oversize_body_rejected_while_streaming(self, monkeypatch: pytest.MonkeyPatch) -> None:
        over = settings.max_image_size_bytes + 1024

        def handler(request: httpx.Request) -> httpx.Response:
            def chunks() -> Iterator[bytes]:
                sent = 0
                while sent < over:
                    block = b"x" * 65536
                    sent += len(block)
                    yield block

            return httpx.Response(200, content=chunks(), headers={"content-type": "image/png"})

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.png")
        assert exc.value.status_code == 413

    def test_empty_body_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mount_transport(monkeypatch, lambda request: image_response(content=b""))
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert "empty" in str(exc.value.detail)

    def test_non_200_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mount_transport(monkeypatch, lambda request: httpx.Response(404, content=b"no"))
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert exc.value.status_code == 502

    def test_transport_error_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused", request=request)

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert exc.value.status_code == 502

    def test_redirect_to_public_followed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/start.jpg":
                return httpx.Response(302, headers={"location": "https://cdn2.example.com/final.jpg"})
            return image_response()

        mount_transport(monkeypatch, handler)
        content, extension = fetch_remote_image("https://cdn.example.com/start.jpg")
        assert extension == "jpg"
        assert content

    def test_redirect_to_private_ip_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "cdn.example.com":
                return httpx.Response(302, headers={"location": "https://10.0.0.5/secret.jpg"})
            return image_response()

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert "disallowed address" in str(exc.value.detail)

    def test_redirect_to_metadata_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "cdn.example.com":
                return httpx.Response(
                    302,
                    headers={"location": "https://169.254.169.254/latest/meta-data/iam/security-credentials/"},
                )
            return image_response()

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert "disallowed address" in str(exc.value.detail)

    def test_redirect_to_http_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.scheme == "https":
                return httpx.Response(302, headers={"location": "http://cdn.example.com/a.jpg"})
            return image_response()

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert "https" in str(exc.value.detail)

    def test_redirect_loop_gives_up(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return httpx.Response(302, headers={"location": f"https://cdn.example.com/{len(seen)}.jpg"})

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert "too many times" in str(exc.value.detail)
        assert len(seen) == MAX_REDIRECTS + 1

    def test_redirect_without_location_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mount_transport(monkeypatch, lambda request: httpx.Response(302))
        with pytest.raises(RemoteImageError) as exc:
            fetch_remote_image("https://cdn.example.com/a.jpg")
        assert "without a destination" in str(exc.value.detail)

    def test_private_target_never_connects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"guard let a request through to {request.url}")

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError):
            fetch_remote_image("https://169.254.169.254/latest/meta-data/")

    def test_http_url_never_connects(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError(f"guard let a request through to {request.url}")

        mount_transport(monkeypatch, handler)
        with pytest.raises(RemoteImageError):
            fetch_remote_image("http://cdn.example.com/a.jpg")


def real_png_bytes() -> bytes:
    """A small valid PNG, for the route level tests that reach Pillow."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(buffer, format="PNG")
    return buffer.getvalue()
