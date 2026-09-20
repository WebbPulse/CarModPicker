"""Mounts the `webbpulse.identity` package router onto the identity domain.

The router carries the issuer's own path, so it is mounted with no prefix; a
prefix would double every path to `/api/auth/api/auth/...`.

The signing client follows the package's own `IDENTITY_SIGNER` switch rather than
being a `boto3.client("kms")` this module names, so a local stack signs in process
with no AWS credential at all. The package refuses the local signer in production
in two places, so the switch cannot put a seed derived key in front of real users.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from fastapi import APIRouter

    from app.common.core.config import Settings


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

    The package declares the statuses every mounted route answers, so the document
    this router publishes needs no amendment here.
    """
    from webbpulse.identity import build_dynamo_router, dynamo_stores

    from app.domains.identity.identity_hooks import CarModPickerIdentityHooks

    prefix = settings.dynamodb_table_prefix
    endpoint_url = settings.DYNAMODB_ENDPOINT_URL or None
    identity_settings = build_identity_settings(settings)

    stores = dynamo_stores(prefix, endpoint_url=endpoint_url)

    return build_dynamo_router(
        identity_settings,
        CarModPickerIdentityHooks(
            package_passkeys=stores.passkeys,
            package_oauth_links=stores.oauth_links,
        ),
        prefix=prefix,
        endpoint_url=endpoint_url,
        service="carmodpicker-identity",
        version=IDENTITY_ROUTER_VERSION,
        stores=stores,
        email_sender=build_email_sender(identity_settings),
        oauth_client_secrets=build_oauth_client_secrets(settings),
    )


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
