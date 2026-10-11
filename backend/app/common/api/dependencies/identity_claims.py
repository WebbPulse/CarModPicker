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
audience, so it uses the shared `cached_verifier`, a `JwksVerifier` that fetches the
published key set over HTTPS and needs no KMS grant. Giving the nine domains the signing
key ARNs instead would let every one of them mint tokens, since `kms:Sign` and
`kms:GetPublicKey` are granted together.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Mapping, Optional

from webbpulse.identity import bearer_credential, verified_bearer_subject
from webbpulse.identity.claims import (
    GATE_CLAIMS_KEY,
    identity_claims,
    identity_subject,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from fastapi import Request

__all__ = [
    "GATE_CLAIMS_KEY",
    "bearer_credential",
    "identity_claims",
    "identity_subject",
    "reset_token_service",
    "verify_bearer_subject",
]

logger = logging.getLogger(__name__)


def verify_bearer_subject(request: "Request") -> str:
    """The `sub` of a Bearer identity token verified in this process, or `""`.

    The fallback for a route the gateway put no claims on. A real verification:
    RS256 signature, issuer, audience, expiry and not-before. Every failure is
    `""` rather than a raise, so a bad or expired token on an optional auth
    route is an anonymous caller and not an error. No verifier is built for a
    request that carries no Bearer credential.
    """
    from app.common.core.config import settings

    if not settings.IDENTITY_ISSUER.strip():
        return ""
    if not bearer_credential(request):
        return ""
    return verified_bearer_subject(request, _verifier())


_verifier_cache: Optional[Callable[[str], Mapping[str, Any]]] = None
_verifier_failed = False


def _verifier() -> Optional[Callable[[str], Mapping[str, Any]]]:
    """The memoised callable that verifies a token, or `None` where none can be built.

    `TokenService` where this function signs (the identity function), otherwise
    the process-wide `cached_verifier` against the issuer's published key set. A
    failure is remembered: without the environment the settings raise, and
    retrying that per request would be a pydantic validation on every call.
    """
    global _verifier_cache, _verifier_failed

    if _verifier_cache is not None:
        return _verifier_cache
    if _verifier_failed:
        return None

    from app.common.core.config import settings as app_settings

    try:
        if _signing_key_arns_present():
            import boto3
            from webbpulse.identity import TokenService

            from app.domains.identity.package_glue import build_identity_settings

            service = TokenService(build_identity_settings(app_settings), boto3.client("kms"))
            _verifier_cache = service.verify_access_token
        else:
            from webbpulse.identity import cached_verifier

            verifier = cached_verifier(
                app_settings.IDENTITY_ISSUER,
                app_settings.IDENTITY_AUDIENCE,
                jwks_uri=app_settings.IDENTITY_JWKS_URL,
            )
            if verifier is None:
                raise ValueError("IDENTITY_ISSUER and IDENTITY_AUDIENCE are required to verify a token in process")
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
    """Drop the memoised verifier and the shared verifier cache. For tests that change the environment."""
    global _verifier_cache, _verifier_failed

    from webbpulse.identity import clear_verifier_cache

    _verifier_cache = None
    _verifier_failed = False
    clear_verifier_cache()
