"""Tests for the tiered fetcher layer (http / tls / browser)."""

from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.crawlers import fetchers
from app.crawlers.fetchers import (
    FetcherError,
    FlareSolverrError,
    FlareSolverrFetcher,
    FlareSolverrNotConfiguredError,
    HttpFetcher,
    TlsFetcher,
    get_fetcher,
)


class TestHttpFetcher:
    """Tier 0 — the HttpFetcher is a thin wrapper around base.fetch_page."""

    def test_delegates_to_fetch_page(self) -> None:
        with patch.object(fetchers, "fetch_page", return_value="<html>ok</html>") as m:
            html = HttpFetcher().fetch("https://example.com")
        assert html == "<html>ok</html>"
        m.assert_called_once()
        args, kwargs = m.call_args
        assert args[0] == "https://example.com"

    def test_tier_is_http(self) -> None:
        assert HttpFetcher().tier == "http"

    def test_close_is_idempotent(self) -> None:
        # No session attached → close is a no-op and must not raise.
        HttpFetcher().close()


class TestTlsFetcher:
    """Tier 1 — curl_cffi impersonation. We patch curl_cffi in sys.modules
    so the test doesn't require the native dependency."""

    def _install_fake_curl_cffi(self, response: Any) -> MagicMock:
        """Install a fake ``curl_cffi.requests`` module whose Session().get returns ``response``."""
        fake_session = MagicMock()
        fake_session.get.return_value = response
        fake_requests = types.SimpleNamespace(Session=MagicMock(return_value=fake_session))
        fake_curl_cffi = types.ModuleType("curl_cffi")
        fake_curl_cffi.requests = fake_requests  # type: ignore[attr-defined]
        sys.modules["curl_cffi"] = fake_curl_cffi
        sys.modules["curl_cffi.requests"] = fake_requests  # type: ignore[assignment]
        return fake_session

    def test_fetch_returns_text(self) -> None:
        resp = MagicMock(status_code=200, text="<html>vivid</html>", content=b"<html>vivid</html>")
        sess = self._install_fake_curl_cffi(resp)
        try:
            html = TlsFetcher().fetch("https://www.vividracing.com/x")
            assert html == "<html>vivid</html>"
            sess.get.assert_called_once()
        finally:
            sys.modules.pop("curl_cffi", None)
            sys.modules.pop("curl_cffi.requests", None)

    def test_fetch_raises_on_http_error(self) -> None:
        resp = MagicMock(status_code=403, text="", content=b"blocked")
        self._install_fake_curl_cffi(resp)
        try:
            with pytest.raises(FetcherError, match="403"):
                TlsFetcher().fetch("https://www.vividracing.com/x")
        finally:
            sys.modules.pop("curl_cffi", None)
            sys.modules.pop("curl_cffi.requests", None)

    def test_missing_curl_cffi_raises_clear_error(self) -> None:
        # With no curl_cffi in sys.modules and no real install, the import fails.
        # The fetcher should raise a FetcherError with a clear message so the
        # runner's per-URL error counter surfaces it.
        sys.modules.pop("curl_cffi", None)
        sys.modules.pop("curl_cffi.requests", None)
        fetcher = TlsFetcher()
        try:
            import curl_cffi  # type: ignore[import-not-found]  # noqa: F401

            pytest.skip("curl_cffi is actually installed; can't test the import-error path")
        except ImportError:
            pass
        with pytest.raises(FetcherError, match="curl_cffi"):
            fetcher.fetch("https://example.com")

    def test_tier_is_tls(self) -> None:
        assert TlsFetcher().tier == "tls"


class TestFlareSolverrFetcher:
    """Tier 2 — a POST client to a FlareSolverr service. We mock the HTTP session."""

    def _make_fetcher(self, http: requests.Session) -> FlareSolverrFetcher:
        return FlareSolverrFetcher(
            endpoint="http://flaresolverr:8191",
            max_timeout_ms=30_000,
            session_name="test-session",
            http_session=http,
        )

    def test_requires_endpoint(self) -> None:
        with pytest.raises(FlareSolverrNotConfiguredError):
            FlareSolverrFetcher(endpoint="")

    def test_successful_fetch_creates_session_then_requests_page(self) -> None:
        http = MagicMock(spec=requests.Session)
        # Two replies in order: session.create ok, then request.get ok with HTML.
        responses = [
            MagicMock(status_code=200, json=lambda: {"status": "ok", "message": ""}),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "status": "ok",
                    "message": "",
                    "solution": {
                        "status": 200,
                        "response": "<html>jegs</html>",
                        "cookies": [],
                    },
                },
            ),
        ]
        http.post.side_effect = responses

        fetcher = self._make_fetcher(http)
        html = fetcher.fetch("https://www.jegs.com/i/x/y/z/-1")
        assert html == "<html>jegs</html>"
        # Two POSTs: sessions.create, then request.get.
        assert http.post.call_count == 2
        first_payload = http.post.call_args_list[0].kwargs["json"]
        second_payload = http.post.call_args_list[1].kwargs["json"]
        assert first_payload["cmd"] == "sessions.create"
        assert first_payload["session"] == "test-session"
        assert second_payload["cmd"] == "request.get"
        assert second_payload["session"] == "test-session"
        assert second_payload["url"].startswith("https://www.jegs.com")

    def test_session_is_created_once_across_multiple_fetches(self) -> None:
        http = MagicMock(spec=requests.Session)
        create_ok = MagicMock(status_code=200, json=lambda: {"status": "ok", "message": ""})
        page_ok = lambda body: MagicMock(  # noqa: E731
            status_code=200,
            json=lambda: {
                "status": "ok",
                "message": "",
                "solution": {"status": 200, "response": body, "cookies": []},
            },
        )
        http.post.side_effect = [create_ok, page_ok("<a/>"), page_ok("<b/>"), page_ok("<c/>")]

        fetcher = self._make_fetcher(http)
        assert fetcher.fetch("https://x/1") == "<a/>"
        assert fetcher.fetch("https://x/2") == "<b/>"
        assert fetcher.fetch("https://x/3") == "<c/>"
        # 1 create + 3 fetches = 4 POSTs
        assert http.post.call_count == 4

    def test_flaresolverr_error_status_raises(self) -> None:
        http = MagicMock(spec=requests.Session)
        http.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"status": "error", "message": "Something went wrong"},
        )
        with pytest.raises(FlareSolverrError, match="Something went wrong"):
            self._make_fetcher(http).fetch("https://example.com")

    def test_upstream_http_error_raises(self) -> None:
        """solution.status >= 400 means the challenge didn't actually work."""
        http = MagicMock(spec=requests.Session)
        # sessions.create succeeds, then request.get returns solution.status=403.
        http.post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status": "ok", "message": ""}),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "status": "ok",
                    "message": "",
                    "solution": {"status": 403, "response": "<html/>", "cookies": []},
                },
            ),
        ]
        with pytest.raises(FlareSolverrError, match="403"):
            self._make_fetcher(http).fetch("https://example.com")

    def test_non_json_response_raises(self) -> None:
        http = MagicMock(spec=requests.Session)
        bad = MagicMock(status_code=502, text="Bad Gateway")
        bad.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
        http.post.return_value = bad
        with pytest.raises(FlareSolverrError, match="non-JSON"):
            self._make_fetcher(http).fetch("https://example.com")

    def test_network_error_raises(self) -> None:
        http = MagicMock(spec=requests.Session)
        http.post.side_effect = requests.ConnectionError("connection refused")
        with pytest.raises(FlareSolverrError, match="unreachable"):
            self._make_fetcher(http).fetch("https://example.com")

    def test_close_destroys_session(self) -> None:
        http = MagicMock(spec=requests.Session)
        http.post.side_effect = [
            MagicMock(status_code=200, json=lambda: {"status": "ok", "message": ""}),
            MagicMock(
                status_code=200,
                json=lambda: {
                    "status": "ok",
                    "message": "",
                    "solution": {"status": 200, "response": "<x/>", "cookies": []},
                },
            ),
            MagicMock(status_code=200, json=lambda: {"status": "ok", "message": ""}),
        ]
        fetcher = self._make_fetcher(http)
        fetcher.fetch("https://x")
        fetcher.close()
        # sessions.create, request.get, sessions.destroy → 3 POSTs.
        assert http.post.call_count == 3
        destroy_payload = http.post.call_args_list[-1].kwargs["json"]
        assert destroy_payload["cmd"] == "sessions.destroy"
        assert destroy_payload["session"] == "test-session"

    def test_close_without_creating_session_is_noop(self) -> None:
        http = MagicMock(spec=requests.Session)
        fetcher = self._make_fetcher(http)
        fetcher.close()
        http.post.assert_not_called()

    def test_tier_is_browser(self) -> None:
        http = MagicMock(spec=requests.Session)
        assert self._make_fetcher(http).tier == "browser"


class TestGetFetcher:
    """The factory maps tier strings to fetcher instances."""

    def test_http_tier(self) -> None:
        assert isinstance(get_fetcher("http"), HttpFetcher)

    def test_tls_tier(self) -> None:
        assert isinstance(get_fetcher("tls"), TlsFetcher)

    def test_browser_tier_requires_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Ensure settings.FLARESOLVERR_URL is empty and env var is unset.
        from app.core.config import settings

        monkeypatch.setattr(settings, "FLARESOLVERR_URL", "")
        monkeypatch.delenv("FLARESOLVERR_URL", raising=False)
        with pytest.raises(FlareSolverrNotConfiguredError):
            get_fetcher("browser")

    def test_browser_tier_with_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import settings

        monkeypatch.setattr(settings, "FLARESOLVERR_URL", "http://flaresolverr.local:8191")
        fetcher = get_fetcher("browser")
        assert isinstance(fetcher, FlareSolverrFetcher)

    def test_unknown_tier_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown fetcher tier"):
            get_fetcher("quantum")  # type: ignore[arg-type]


class TestAdapterFetcherTierDispatch:
    """The runner should construct a fetcher matching each adapter's declared
    FETCHER_TIER and inject it into the adapter. Existing adapters default to
    the http tier, so no behavioral change for them."""

    def test_default_adapter_gets_http_fetcher(self) -> None:
        from app.crawlers.adapters import get_adapter

        adapter = get_adapter("a90shop")
        assert adapter.FETCHER_TIER == "http"
        assert isinstance(adapter.fetcher, HttpFetcher)

    def test_fetcher_injection(self) -> None:
        """When the runner passes an explicit fetcher, the adapter uses it —
        this is the hook that lets the runner share one Tier 2 session across
        discovery + product fetches for a single adapter run."""
        from app.crawlers.adapters import get_adapter

        custom = HttpFetcher()
        adapter = get_adapter("a90shop", fetcher=custom)
        assert adapter.fetcher is custom
