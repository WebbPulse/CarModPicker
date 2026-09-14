"""Mounts the `webbpulse.identity` package router onto the identity domain.

The router carries the issuer's own path, so it is mounted with no prefix; a
prefix would double every path to `/api/auth/api/auth/...`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

    from app.core.config import Settings


def build_identity_settings(settings: "Settings") -> Any:
    """`IdentitySettings` for this product, read straight from the environment.

    Every field arrives through an `IDENTITY_*` variable Terraform sets, so this
    is a bare constructor call. Raises `ValidationError` on a bad environment.
    """
    from webbpulse.identity import IdentitySettings

    del settings
    return IdentitySettings()  # pyright: ignore[reportCallIssue]


def build_router(settings: "Settings") -> "APIRouter":
    """The identity router, mounted by the caller with no prefix of its own.

    Which route groups mount depends on what is supplied: credentials mount the
    flow routes, an email sender and token store the email routes, and so on.

    The router's OpenAPI responses are amended on the way out, because the package
    declares every route with the FastAPI default alone.
    """
    import boto3
    from webbpulse.dynamodb import Repository
    from webbpulse.identity import (
        CREDENTIALS_TABLE,
        IDENTITY_TOKENS_TABLE,
        LOGIN_ATTEMPTS_TABLE,
        OAUTH_LINKS_TABLE,
        OAUTH_STATES_TABLE,
        PASSKEYS_TABLE,
        RECOVERY_CODES_TABLE,
        REFRESH_TOKENS_TABLE,
        TOTP_FACTORS_TABLE,
        WEBAUTHN_CHALLENGES_TABLE,
        DynamoCredentialStore,
        DynamoIdentityTokenStore,
        DynamoLoginAttemptStore,
        DynamoOAuthLinkStore,
        DynamoOAuthStateStore,
        DynamoPasskeyStore,
        DynamoRecoveryCodeStore,
        DynamoRefreshTokenStore,
        DynamoTotpFactorStore,
        DynamoWebAuthnChallengeStore,
        IdentityStores,
        build_identity_router,
    )

    from app.composition.identity_hooks import CarModPickerIdentityHooks

    def repository(logical_name: str) -> Repository:
        """A package repository for one of the six identity tables.

        Prefix and endpoint are passed explicitly so this reads the same `Settings`
        as the rest of the backend, and table names are the package's constants.
        """
        return Repository(
            logical_name,
            prefix=settings.dynamodb_table_prefix,
            endpoint_url=settings.DYNAMODB_ENDPOINT_URL or None,
        )

    identity_settings = build_identity_settings(settings)

    stores = IdentityStores(
        credentials=DynamoCredentialStore(repository(CREDENTIALS_TABLE)),
        refresh_tokens=DynamoRefreshTokenStore(repository(REFRESH_TOKENS_TABLE)),
        identity_tokens=DynamoIdentityTokenStore(repository(IDENTITY_TOKENS_TABLE)),
        totp_factors=DynamoTotpFactorStore(repository(TOTP_FACTORS_TABLE)),
        recovery_codes=DynamoRecoveryCodeStore(repository(RECOVERY_CODES_TABLE)),
        oauth_states=DynamoOAuthStateStore(repository(OAUTH_STATES_TABLE)),
        oauth_links=DynamoOAuthLinkStore(repository(OAUTH_LINKS_TABLE)),
        passkeys=DynamoPasskeyStore(repository(PASSKEYS_TABLE)),
        webauthn_challenges=DynamoWebAuthnChallengeStore(repository(WEBAUTHN_CHALLENGES_TABLE)),
    )

    router = build_identity_router(
        identity_settings,
        CarModPickerIdentityHooks(
            package_passkeys=stores.passkeys,
            package_oauth_links=stores.oauth_links,
        ),
        stores,
        kms_client=boto3.client("kms"),
        service="carmodpicker-identity",
        version=IDENTITY_ROUTER_VERSION,
        attempts=DynamoLoginAttemptStore(repository(LOGIN_ATTEMPTS_TABLE)),
        email_sender=build_email_sender(identity_settings),
        oauth_client_secrets=build_oauth_client_secrets(settings),
    )
    declare_identity_responses(router)
    return router


OAUTH_SECRET_KEYS = {
    "google": "OAUTH_GOOGLE_CLIENT_SECRET",
    "github": "OAUTH_GITHUB_CLIENT_SECRET",
}


def build_oauth_client_secrets(settings: "Settings") -> dict[str, str]:
    """The OAuth client secrets from the single app secret, possibly empty.

    An empty result is correct: with no client id the package declares no OAuth
    route. The environment is consulted ahead of the secret, as elsewhere. Since
    row 13 this is the only reason the identity function holds a Secrets Manager
    grant, so `terraform/lambda_domains.tf` keeps `secrets = true` on it even
    though the domain's `requires_secrets` is empty.
    """
    import os

    from webbpulse.security import app_secrets

    arn = os.environ.get("APP_SECRETS_ARN", "") or settings.APP_SECRETS_ARN

    from_env = {provider: os.environ[key] for provider, key in OAUTH_SECRET_KEYS.items() if os.environ.get(key)}
    if len(from_env) == len(OAUTH_SECRET_KEYS) or not arn:
        return from_env

    loaded = app_secrets(arn)
    return {
        provider: from_env.get(provider) or loaded[key]
        for provider, key in OAUTH_SECRET_KEYS.items()
        if from_env.get(provider) or loaded.get(key)
    }


IDENTITY_ROUTER_VERSION = "1.0.0"


def build_email_sender(identity_settings: Any) -> Any:
    """The `EmailSender` for the email routes, or `None` when SES is absent.

    `None` is a supported state: the package then declares no email route rather
    than four that answer 503. The client is built here, never at import.
    """
    if not identity_settings.email_from:
        return None

    import boto3
    from webbpulse.identity.email import SesV2EmailSender

    return SesV2EmailSender.from_settings(identity_settings, boto3.client("sesv2"))


IDENTITY_EXTRA_RESPONSES: dict[tuple[str, str], dict[int, str]] = {
    ("POST", "/api/auth/register"): {
        201: "Account created and signed in",
        400: "The request carried no email address",
        403: "Registration or password sign up is closed on this deployment",
        429: "Too many registration attempts from this address",
    },
    ("POST", "/api/auth/login"): {
        400: "The request carried no email address",
        401: "The credentials were refused",
        403: "The account is locked or password sign in is closed",
        429: "Too many sign in attempts from this address",
    },
    ("POST", "/api/auth/refresh"): {401: "The refresh material was refused"},
    ("POST", "/api/auth/login/totp"): {401: "The code was refused", 403: "The challenge is no longer open"},
    ("POST", "/api/auth/login/passkey/options"): {400: "The request named no account"},
    ("POST", "/api/auth/login/passkey/verify"): {401: "The assertion was refused"},
    ("GET", "/api/auth/oauth/callback"): {
        303: "The browser leg is redirected back to the frontend, on success and on failure alike",
        400: "The state was spent, unknown or malformed",
    },
    ("GET", "/api/auth/oauth/{provider}/start"): {
        302: "The browser is redirected to the provider's authorization endpoint",
        400: "The provider is unknown or the redirect target is not allowed",
        401: "A link start was made without a bearer token",
    },
    ("POST", "/api/auth/oauth/{provider}/link"): {400: "The provider is unknown", 401: "No bearer token was presented"},
    ("DELETE", "/api/auth/oauth/{provider}/link"): {
        400: "The provider is unknown",
        401: "No bearer token was presented",
    },
    ("GET", "/api/auth/oauth/links"): {401: "No bearer token was presented"},
    ("POST", "/api/auth/password"): {401: "The current password was refused"},
    ("POST", "/api/auth/step-up"): {401: "The factor was refused"},
    ("POST", "/api/auth/logout-all"): {401: "No bearer token was presented"},
    ("POST", "/api/auth/recovery-codes"): {401: "No bearer token was presented"},
    ("POST", "/api/auth/totp/enrol"): {401: "No bearer token was presented"},
    ("POST", "/api/auth/totp/activate"): {401: "No bearer token was presented", 403: "The code was refused"},
    ("POST", "/api/auth/totp/disable"): {401: "No bearer token was presented", 403: "The code was refused"},
    ("GET", "/api/auth/passkeys"): {401: "No bearer token was presented"},
    ("POST", "/api/auth/passkeys/register/options"): {401: "No bearer token was presented"},
    ("POST", "/api/auth/passkeys/register/verify"): {
        201: "Passkey registered",
        401: "No bearer token was presented",
    },
    ("PATCH", "/api/auth/passkeys/{credential_id}"): {
        401: "No bearer token was presented",
        404: "No such passkey for this account",
    },
    ("DELETE", "/api/auth/passkeys/{credential_id}"): {
        401: "No bearer token was presented",
        404: "No such passkey for this account",
    },
}
"""The statuses the `webbpulse.identity` routes really answer, keyed by method and path.

The package declares each of its routes with the FastAPI default of 200 plus 422, so the
published document promised statuses the routes do not keep: `POST /api/auth/register`
answers 400 to a body with no email and `GET /api/auth/oauth/callback` answers 303 on
every browser leg. An undeclared status is not cosmetic. The post-deploy suite holds each
operation to its own `responses` table, so the document is the contract that gets checked.

Amended here rather than in the package because CarModPicker mounts the router and owns
the document it publishes.
"""


def declare_identity_responses(router: "APIRouter") -> None:
    """Add the statuses the identity routes answer to their OpenAPI responses.

    Existing entries are left alone, so a status the package already describes keeps the
    package's own description.
    """
    from fastapi.routing import APIRoute

    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or ():
            extra = IDENTITY_EXTRA_RESPONSES.get((method, route.path))
            if not extra:
                continue
            for status_code, description in extra.items():
                route.responses.setdefault(status_code, {"description": description})
