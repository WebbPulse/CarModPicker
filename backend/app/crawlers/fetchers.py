"""
Tiered fetchers for the crawler pipeline.

The crawler's ``fetch_page()`` in ``base.py`` is ``requests.get`` — good for
well-behaved retailers, useless against sites behind Cloudflare Bot Management
or TLS-fingerprint blocks. Fetchers let an adapter declare how "thick" a client
it needs via ``RetailerCrawlerAdapter.FETCHER_TIER`` and keeps the adapter code
fetcher-agnostic.

Tiers
-----

- **http**  (``HttpFetcher``): thin wrapper around ``base.fetch_page`` — plain
  ``requests`` with our existing retry/backoff/jitter/rate-limit logic. Default
  for every existing adapter; nothing changes for them.
- **tls**   (``TlsFetcher``): ``curl_cffi`` with Chrome TLS/JA3 impersonation.
  Solves *fingerprint* blocks where the IP/ASN is fine but plain Python's
  TLS handshake is flagged (e.g. Vivid Racing). No JS execution.
- **browser** (``FlareSolverrFetcher``): POSTs to a FlareSolverr service which
  drives a real Chromium to solve Cloudflare managed JS challenges and returns
  the post-challenge HTML. Solves JEGS / FCP Euro-class challenges. Session-
  backed so the CF-clearance cookie is reused across requests.

Each fetcher returns ``str`` (decoded HTML) so adapters can stay oblivious to
how the bytes arrived. Errors raise ``FetcherError`` (or a subclass) so the
runner can count them uniformly.

See ``crawlers/README.md`` for operational notes — FlareSolverr in particular
has sharp edges (upstream maintenance has been intermittent, Cloudflare
periodically ships detection updates that break it) and the doc enumerates
fallback paths if Tier 2 stops working in production.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional, Protocol, runtime_checkable

import requests

from app.crawlers.base import (
    DEFAULT_TIMEOUT_SEC,
    DEFAULT_USER_AGENT,
    fetch_page,
)

logger = logging.getLogger(__name__)


class FetcherError(RuntimeError):
    """Base class for fetcher failures. Caught by the runner as a per-URL error."""


class FlareSolverrError(FetcherError):
    """FlareSolverr returned status=error or a non-2xx HTTP response itself."""


class FlareSolverrNotConfiguredError(FetcherError):
    """Adapter declared FETCHER_TIER='browser' but FLARESOLVERR_URL is unset."""


@runtime_checkable
class Fetcher(Protocol):
    """
    Fetch a URL and return the HTML body as a string.

    Implementations are responsible for their own retry/backoff semantics; the
    runner only catches exceptions and counts them. The ``close()`` hook exists
    for fetchers that hold server-side state (FlareSolverr sessions) — callers
    should invoke it when finished with the fetcher.
    """

    tier: str

    def fetch(self, url: str, *, timeout: Optional[int] = None) -> str: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Tier 0 — plain HTTP
# ---------------------------------------------------------------------------


class HttpFetcher:
    """
    Plain ``requests`` fetcher with the existing retry/backoff/rate-limit logic
    already implemented in ``base.fetch_page``. This is intentionally a thin
    wrapper — the semantics that existing adapters depend on live in
    ``fetch_page`` and we don't want to fork them.
    """

    tier = "http"

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        session: Optional[requests.Session] = None,
    ) -> None:
        self._user_agent = user_agent
        self._session = session

    def fetch(self, url: str, *, timeout: Optional[int] = None) -> str:
        return fetch_page(
            url,
            timeout=timeout if timeout is not None else DEFAULT_TIMEOUT_SEC,
            user_agent=self._user_agent,
            session=self._session,
        )

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tier 1 — TLS impersonation (curl_cffi)
# ---------------------------------------------------------------------------


# Chrome impersonation profile used by curl_cffi. Bump when real Chrome's
# fingerprint drifts enough that the current profile starts getting flagged.
# Profile names are curl_cffi-specific; see its docs for supported values.
DEFAULT_TLS_IMPERSONATE = "chrome124"


class TlsFetcher:
    """
    TLS-impersonating fetcher backed by ``curl_cffi``. Mimics a real Chrome
    TLS/JA3 handshake + HTTP/2 frame ordering, which is typically enough to
    get past Cloudflare fingerprint rules when the IP itself is not banned.

    Does NOT execute JavaScript — if the site serves a managed JS challenge,
    use the ``browser`` tier instead.

    ``curl_cffi`` is imported lazily so sites that don't need this tier don't
    pay the import (and deployments that don't install the dep don't fail on
    module load).
    """

    tier = "tls"

    def __init__(
        self,
        *,
        impersonate: str = DEFAULT_TLS_IMPERSONATE,
        user_agent: Optional[str] = None,
    ) -> None:
        self._impersonate = impersonate
        # curl_cffi sets UA to match the impersonation profile; overriding
        # would undo the TLS-fingerprint coherence, so we only set UA if the
        # caller explicitly passed one.
        self._user_agent = user_agent
        self._session: Any = None  # curl_cffi.requests.Session, lazily created

    def _ensure_session(self) -> Any:
        if self._session is not None:
            return self._session
        try:
            from curl_cffi import requests as cc_requests  # type: ignore[import-not-found]
        except ImportError as e:
            raise FetcherError(
                "TlsFetcher requires the 'curl_cffi' package. Add it to " "backend/requirements.txt and reinstall."
            ) from e
        self._session = cc_requests.Session(impersonate=self._impersonate)
        return self._session

    def fetch(self, url: str, *, timeout: Optional[int] = None) -> str:
        sess = self._ensure_session()
        kwargs: dict[str, Any] = {
            "timeout": timeout if timeout is not None else DEFAULT_TIMEOUT_SEC,
        }
        if self._user_agent:
            kwargs["headers"] = {"User-Agent": self._user_agent}
        try:
            resp = sess.get(url, **kwargs)
        except Exception as e:
            raise FetcherError(f"TlsFetcher request failed for {url}: {e}") from e
        if resp.status_code >= 400:
            raise FetcherError(
                f"TlsFetcher got HTTP {resp.status_code} for {url} "
                f"(body bytes={len(resp.content) if resp.content else 0})"
            )
        # curl_cffi decodes similarly to requests; .text is str
        text = getattr(resp, "text", None)
        if isinstance(text, bytes):
            text = text.decode("utf-8", errors="replace")
        if not isinstance(text, str):
            raise FetcherError(f"TlsFetcher returned non-text response for {url}")
        return text

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None


# ---------------------------------------------------------------------------
# Tier 2 — headless browser via FlareSolverr
# ---------------------------------------------------------------------------


# FlareSolverr default timeout: the service needs real wall-clock time to solve
# a challenge (page load + JS execution + potential interstitial). 60s is the
# documented FlareSolverr default; challenges usually resolve in <15s.
FLARESOLVERR_DEFAULT_TIMEOUT_MS = 60_000

# How long the requests-layer call to FlareSolverr itself is allowed to take.
# Includes FlareSolverr's own maxTimeout, so this must be strictly greater.
FLARESOLVERR_HTTP_TIMEOUT_SEC_SLACK = 15


class FlareSolverrFetcher:
    """
    Fetches via a running FlareSolverr instance. FlareSolverr drives a real
    Chromium (undetected-chromedriver under the hood) to solve Cloudflare
    managed JS challenges and returns the resulting HTML + cookies.

    We use FlareSolverr *sessions* to amortize challenge cost: once the first
    request solves CF's check, the session's cookie jar holds the
    ``cf_clearance`` cookie (typically valid 30 minutes – hours) and follow-on
    requests are cheap ~1s page loads, not full challenge-solves.

    Configure via settings:
      - ``FLARESOLVERR_URL`` (e.g. ``http://flaresolverr:8191``). Required.
      - ``FLARESOLVERR_MAX_TIMEOUT_MS`` — per-request budget sent to FlareSolverr.
      - ``FLARESOLVERR_SESSION_NAME`` — shared session id across all calls.

    Caveats — see ``crawlers/README.md`` for the long version:
      - FlareSolverr is a single-flight service; all crawler workers share the
        Chromium pool. Keep adapter concurrency modest (1–2).
      - Cloudflare periodically ships detection updates that break FlareSolverr
        until the project catches up. When that happens, Tier 2 returns 403
        even post-challenge and you'll see consecutive ``FlareSolverrError``
        in logs. At that point the realistic options are (a) upgrade /
        fork FlareSolverr, (b) switch to a Patchright- or Camoufox-based
        in-house fetcher, or (c) fall back to the Chrome-extension pipeline
        for affected sites.
    """

    tier = "browser"

    def __init__(
        self,
        *,
        endpoint: str,
        max_timeout_ms: int = FLARESOLVERR_DEFAULT_TIMEOUT_MS,
        session_name: str = "carmodpicker-crawler",
        http_session: Optional[requests.Session] = None,
    ) -> None:
        if not endpoint or not endpoint.strip():
            raise FlareSolverrNotConfiguredError("FlareSolverrFetcher requires FLARESOLVERR_URL to be set.")
        # FlareSolverr's control endpoint is always /v1.
        self._endpoint = endpoint.rstrip("/") + "/v1"
        self._max_timeout_ms = int(max_timeout_ms)
        self._session_name = session_name
        self._http = http_session or requests.Session()
        self._session_created = False
        # Guard against concurrent create/destroy on the single shared session.
        self._session_lock = threading.Lock()

    def _post(self, payload: dict) -> dict:
        http_timeout = (self._max_timeout_ms / 1000.0) + FLARESOLVERR_HTTP_TIMEOUT_SEC_SLACK
        try:
            resp = self._http.post(
                self._endpoint,
                json=payload,
                timeout=http_timeout,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException as e:
            raise FlareSolverrError(f"FlareSolverr unreachable at {self._endpoint}: {e}") from e

        # FlareSolverr always replies 200 on the HTTP layer even for errors;
        # check the JSON ``status`` field.
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError) as e:
            raise FlareSolverrError(
                f"FlareSolverr returned non-JSON (HTTP {resp.status_code}): " f"{resp.text[:200]!r}"
            ) from e

        if data.get("status") != "ok":
            raise FlareSolverrError(
                f"FlareSolverr error: status={data.get('status')!r} " f"message={data.get('message')!r}"
            )
        return data

    def _ensure_session(self) -> None:
        if self._session_created:
            return
        with self._session_lock:
            if self._session_created:
                return
            logger.info("FlareSolverr: creating session %r", self._session_name)
            self._post({"cmd": "sessions.create", "session": self._session_name})
            self._session_created = True

    def fetch(self, url: str, *, timeout: Optional[int] = None) -> str:
        self._ensure_session()
        max_timeout_ms = int(timeout * 1000) if timeout is not None else self._max_timeout_ms
        payload: dict = {
            "cmd": "request.get",
            "url": url,
            "session": self._session_name,
            "maxTimeout": max_timeout_ms,
        }
        data = self._post(payload)
        solution = data.get("solution") or {}
        html = solution.get("response")
        solution_status = solution.get("status")
        if solution_status is not None and int(solution_status) >= 400:
            raise FlareSolverrError(
                f"FlareSolverr: upstream returned HTTP {solution_status} for {url} " f"(challenge may have failed)"
            )
        if not isinstance(html, str):
            raise FlareSolverrError(f"FlareSolverr returned no response body for {url}")
        return html

    def close(self) -> None:
        if not self._session_created:
            return
        with self._session_lock:
            if not self._session_created:
                return
            try:
                self._post({"cmd": "sessions.destroy", "session": self._session_name})
            except FlareSolverrError as e:
                # Best-effort cleanup; log and move on.
                logger.warning("FlareSolverr: failed to destroy session: %s", e)
            finally:
                self._session_created = False
                try:
                    self._http.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


VALID_TIERS = ("http", "tls", "browser")


def get_fetcher(tier: str) -> Fetcher:
    """
    Construct a fetcher for the given tier. Config for the ``browser`` tier is
    read from ``app.core.config.settings`` at call time so test code can
    override the settings cache.
    """
    if tier == "http":
        return HttpFetcher()
    if tier == "tls":
        return TlsFetcher()
    if tier == "browser":
        # Lazy import so the settings read happens at call time (so tests that
        # monkeypatch settings values see the override).
        from app.core.config import settings

        return FlareSolverrFetcher(
            endpoint=(settings.FLARESOLVERR_URL or "").strip(),
            max_timeout_ms=settings.FLARESOLVERR_MAX_TIMEOUT_MS,
            session_name=settings.FLARESOLVERR_SESSION_NAME,
        )
    raise ValueError(f"Unknown fetcher tier: {tier!r}. Valid: {VALID_TIERS}")
