"""Verify a Bearer identity token in process, for routes the gateway put no claims on.

Reading the authorizer's claims is `webbpulse.identity.claims`, re-exported here so
`app/api/dependencies/auth.py` keeps one import. What stays is the product's own
fallback: a real verification against the identity issuer's keys.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from webbpulse.identity.claims import (
    GATE_CLAIMS_KEY,
    identity_claims,
    identity_subject,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import Request

__all__ = [
    "GATE_CLAIMS_KEY",
    "identity_claims",
    "identity_subject",
    "verify_bearer_subject",
]

logger = logging.getLogger(__name__)


def verify_bearer_subject(request: "Request") -> str:
    """The `sub` of a Bearer identity token verified in this process, or `""`.

    The fallback for a route the gateway put no claims on. It is a real
    verification: signature, issuer, audience and expiry, through
    """
    from app.core.config import settings

    if not settings.IDENTITY_ISSUER.strip():
        return ""

    authorization = request.headers.get("authorization", "")
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer" or not presented.strip():
        return ""

    service = _token_service()
    if service is None:
        return ""
    try:
        claims = service.verify_access_token(presented.strip())
    except Exception:
        logger.debug("An identity access token did not verify.", exc_info=True)
        return ""
    return str(claims.get("sub", "") or "")


_token_service_cache: Optional[Any] = None
_token_service_failed = False


def _token_service() -> Optional[Any]:
    """The shared `TokenService`, or `None` where one cannot be built.

    A failure is remembered. On a function with no `IDENTITY_*` block the
    settings raise, and retrying that per request would be a pydantic validation
    """
    global _token_service_cache, _token_service_failed

    if _token_service_cache is not None:
        return _token_service_cache
    if _token_service_failed:
        return None
    try:
        import boto3
        from webbpulse.identity import TokenService

        from app.composition.identity import build_identity_settings
        from app.core.config import settings as app_settings

        identity_settings = build_identity_settings(app_settings)
        _token_service_cache = TokenService(identity_settings, boto3.client("kms"))
    except Exception:
        _token_service_failed = True
        logger.debug(
            "No identity TokenService on this function, so a Bearer identity token cannot "
            "be verified in process here. Expected on every domain but `identity`.",
            exc_info=True,
        )
        return None
    return _token_service_cache


def reset_token_service() -> None:
    """Drop the memoised `TokenService`. For tests that change the environment."""
    global _token_service_cache, _token_service_failed

    _token_service_cache = None
    _token_service_failed = False
