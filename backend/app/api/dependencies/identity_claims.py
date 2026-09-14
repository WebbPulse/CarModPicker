"""Verify a Bearer identity token in process, for routes the gateway put no claims on.

Reading the authorizer's claims is `webbpulse.identity.claims`, re-exported here so
`app/api/dependencies/auth.py` keeps one import. What stays is the product's own
fallback: a real verification against the identity issuer's keys.

**Why the fallback exists.** Claims reach a domain function only through the authorizer
context, and the gateway publishes them only for the route keys it enforces a token on.
An optional auth route is never one of those: production runs a native JWT authorizer,
which refuses an anonymous caller, so an optional route cannot carry one. Without this,
every signed in caller on those routes reads as anonymous.

**Two verifiers, picked by what the function's environment holds.** The identity function
has `IDENTITY_SIGNING_KEY_ARNS` and a KMS grant, so it uses `TokenService`, which reads
its public keys through `kms:GetPublicKey`. A domain function has only the issuer and the
audience, so it uses `JwksVerifier`, which fetches the published key set over HTTPS and
needs no KMS grant. Giving the nine domains the signing key ARNs instead would let every
one of them mint tokens, since `kms:Sign` and `kms:GetPublicKey` are granted together.
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
    "bearer_token",
    "identity_claims",
    "identity_subject",
    "reset_token_service",
    "verify_bearer_subject",
]

logger = logging.getLogger(__name__)


def bearer_token(request: "Request") -> str:
    """The presented Bearer credential, or `""` when there is no usable one."""
    authorization = request.headers.get("authorization", "")
    scheme, _, presented = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return presented.strip()


def verify_bearer_subject(request: "Request") -> str:
    """The `sub` of a Bearer identity token verified in this process, or `""`.

    The fallback for a route the gateway put no claims on. A real verification:
    RS256 signature, issuer, audience, expiry and not-before. Every failure is
    `""` rather than a raise, so a bad or expired token on an optional auth
    route is an anonymous caller and not an error.
    """
    from app.core.config import settings

    if not settings.IDENTITY_ISSUER.strip():
        return ""

    presented = bearer_token(request)
    if not presented:
        return ""

    verifier = _verifier()
    if verifier is None:
        return ""
    try:
        claims = verifier(presented)
    except Exception:
        logger.debug("An identity access token did not verify.", exc_info=True)
        return ""
    return str(claims.get("sub", "") or "")


_verifier_cache: Optional[Any] = None
_verifier_failed = False


def _verifier() -> Optional[Any]:
    """The memoised callable that verifies a token, or `None` where none can be built.

    `TokenService` where this function signs (the identity function), otherwise
    `JwksVerifier` against the issuer's published key set. A failure is
    remembered: without the environment the settings raise, and retrying that
    per request would be a pydantic validation on every call.
    """
    global _verifier_cache, _verifier_failed

    if _verifier_cache is not None:
        return _verifier_cache
    if _verifier_failed:
        return None

    from app.core.config import settings as app_settings

    try:
        if _signing_key_arns_present():
            import boto3
            from webbpulse.identity import TokenService

            from app.composition.identity import build_identity_settings

            service = TokenService(build_identity_settings(app_settings), boto3.client("kms"))
            _verifier_cache = service.verify_access_token
        else:
            from webbpulse.identity import JwksVerifier

            audience = app_settings.IDENTITY_AUDIENCE.strip()
            if not audience:
                raise ValueError("IDENTITY_AUDIENCE is required to verify a token in process")

            verifier = JwksVerifier(
                issuer=app_settings.IDENTITY_ISSUER.strip(),
                audience=audience,
                jwks_uri=app_settings.IDENTITY_JWKS_URL.strip() or None,
            )
            _verifier_cache = verifier.verify
    except Exception:
        _verifier_failed = True
        logger.debug(
            "No in-process identity verifier on this function, so a Bearer identity token "
            "cannot be verified here and an optional auth caller reads as anonymous.",
            exc_info=True,
        )
        return None
    return _verifier_cache


def _signing_key_arns_present() -> bool:
    """Whether this function holds identity signing keys, which only `identity` does."""
    import os

    return bool(os.environ.get("IDENTITY_SIGNING_KEY_ARNS", "").strip())


def reset_token_service() -> None:
    """Drop the memoised verifier. For tests that change the environment."""
    global _verifier_cache, _verifier_failed

    _verifier_cache = None
    _verifier_failed = False
