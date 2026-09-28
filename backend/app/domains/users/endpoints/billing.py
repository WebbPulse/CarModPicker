"""Stripe billing routes: checkout, the customer portal and the webhook receiver."""

import logging
from typing import Any, NoReturn

import stripe
from fastapi import APIRouter, Depends, Header, Request, status
from starlette.concurrency import run_in_threadpool
from webbpulse.dynamodb import IdempotencyStore
from webbpulse.integrations.stripe import (
    StripeNotConfigured,
    StripeSettings,
    StripeSignatureError,
    verify_webhook_event,
)

from app.common.api.dependencies.auth import get_current_user
from app.common.api.dependencies.repositories import Repositories, get_repositories
from app.common.api.utils.response_patterns import ResponsePatterns
from app.common.db.dynamo.users import User as DBUser
from app.domains.users.schemas.billing import BillingSessionRead, StripeWebhookAck
from app.domains.users.services.billing_service import (
    GatewayFactory,
    PriceNotFound,
    get_gateway_factory,
    get_idempotency_store,
    load_billing_settings,
    portal_return_url,
    process_webhook_event,
    start_checkout,
    user_has_active_premium,
)

logger = logging.getLogger(__name__)

router = APIRouter()

STRIPE_NOT_CONFIGURED = "STRIPE_NOT_CONFIGURED"

_UNAVAILABLE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Stripe is not configured on this stage"},
}

_SESSION_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Not authenticated"},
    status.HTTP_409_CONFLICT: {"description": "The request conflicts with the user's billing state"},
    status.HTTP_502_BAD_GATEWAY: {"description": "Stripe rejected the request"},
    **_UNAVAILABLE,
}


def _raise_not_configured(error: StripeNotConfigured) -> NoReturn:
    """Answer 503 for a stage whose Stripe configuration is incomplete."""
    logger.warning("Stripe is not configured: %s", error)
    ResponsePatterns.raise_http_exception(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Billing is not available right now",
        error_code=STRIPE_NOT_CONFIGURED,
    )


def _raise_stripe_error(error: stripe.StripeError) -> NoReturn:
    """Answer 502 when Stripe refuses or fails a call."""
    logger.error("Stripe call failed: %s", type(error).__name__)
    ResponsePatterns.raise_http_exception(
        status.HTTP_502_BAD_GATEWAY,
        "The payment provider could not complete the request",
        error_code="STRIPE_ERROR",
    )


def _settings_or_503() -> StripeSettings:
    """The Stripe settings, or a 503 when they are incomplete."""
    try:
        return load_billing_settings()
    except StripeNotConfigured as error:
        _raise_not_configured(error)


@router.post(
    "/checkout-session",
    response_model=BillingSessionRead,
    responses=_SESSION_RESPONSES,
)
def create_checkout_session(
    current_user: DBUser = Depends(get_current_user),
    repos: Repositories = Depends(get_repositories),
    gateway_factory: GatewayFactory = Depends(get_gateway_factory),
) -> BillingSessionRead:
    """Start a Stripe Checkout for the premium monthly plan and return its URL."""
    if user_has_active_premium(current_user):
        ResponsePatterns.raise_http_exception(
            status.HTTP_409_CONFLICT,
            "You already have an active premium subscription",
            error_code="ALREADY_PREMIUM",
        )
    gateway = gateway_factory(_settings_or_503())
    try:
        url = start_checkout(current_user, repos.users, gateway)
    except PriceNotFound:
        logger.error("No active Stripe price carries the premium lookup key")
        ResponsePatterns.raise_http_exception(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Billing is not available right now",
            error_code="STRIPE_PRICE_MISSING",
        )
    except stripe.StripeError as error:
        _raise_stripe_error(error)
    return BillingSessionRead(url=url)


@router.post(
    "/portal-session",
    response_model=BillingSessionRead,
    responses=_SESSION_RESPONSES,
)
def create_portal_session(
    current_user: DBUser = Depends(get_current_user),
    gateway_factory: GatewayFactory = Depends(get_gateway_factory),
) -> BillingSessionRead:
    """Open a Stripe Customer Portal session for the current user and return its URL."""
    if not current_user.stripe_customer_id:
        ResponsePatterns.raise_http_exception(
            status.HTTP_409_CONFLICT,
            "There is no billing account to manage yet",
            error_code="NO_BILLING_ACCOUNT",
        )
    gateway = gateway_factory(_settings_or_503())
    try:
        url = gateway.create_portal_session(customer_id=current_user.stripe_customer_id, return_url=portal_return_url())
    except stripe.StripeError as error:
        _raise_stripe_error(error)
    return BillingSessionRead(url=url)


@router.post(
    "/stripe/webhook",
    response_model=StripeWebhookAck,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "The delivery's signature did not verify"},
        **_UNAVAILABLE,
    },
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    repos: Repositories = Depends(get_repositories),
    gateway_factory: GatewayFactory = Depends(get_gateway_factory),
    store: IdempotencyStore = Depends(get_idempotency_store),
) -> StripeWebhookAck:
    """Receive a signed Stripe event and sync the subscription it concerns onto the user."""
    payload = await request.body()
    return await run_in_threadpool(_handle_webhook, payload, stripe_signature, repos, gateway_factory, store)


def _handle_webhook(
    payload: bytes,
    stripe_signature: str | None,
    repos: Repositories,
    gateway_factory: GatewayFactory,
    store: IdempotencyStore,
) -> StripeWebhookAck:
    """Verify, claim and apply one webhook delivery off the event loop."""
    stripe_settings = _settings_or_503()
    try:
        event = verify_webhook_event(payload, stripe_signature, stripe_settings)
    except StripeNotConfigured as error:
        _raise_not_configured(error)
    except StripeSignatureError as error:
        logger.warning("Rejected Stripe webhook: %s", error)
        ResponsePatterns.raise_http_exception(
            status.HTTP_400_BAD_REQUEST,
            "Invalid Stripe signature",
            error_code="STRIPE_SIGNATURE_INVALID",
        )
    gateway = gateway_factory(stripe_settings)
    handled, duplicate = process_webhook_event(event, repos.users, gateway, store)
    logger.info("Stripe event %s (%s) handled=%s duplicate=%s", event.id, event.type, handled, duplicate)
    return StripeWebhookAck(handled=handled, duplicate=duplicate)
