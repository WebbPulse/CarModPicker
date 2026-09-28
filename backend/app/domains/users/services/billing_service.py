"""Stripe billing: checkout and portal sessions, and subscription sync from webhooks."""

import logging
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID

import stripe
from webbpulse.dynamodb import IdempotencyStore
from webbpulse.dynamodb import Repository as SharedRepository
from webbpulse.integrations.stripe import (
    StripeNotConfigured,
    StripeSettings,
    claim_webhook_event,
    event_claim_key,
    load_stripe_settings,
    stripe_client,
)

from app.common.core.config import settings
from app.common.db.dynamo.client import resource_kwargs, table_name
from app.common.db.dynamo.tables import IDEMPOTENCY
from app.common.db.dynamo.users import User, UserRepository

logger = logging.getLogger(__name__)

PREMIUM_PRICE_LOOKUP_KEY = "premium_monthly"

PREMIUM_STRIPE_STATUSES = frozenset({"active", "trialing"})

SUBSCRIPTION_EVENTS = frozenset(
    {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)

HANDLED_EVENTS = SUBSCRIPTION_EVENTS | {"checkout.session.completed", "invoice.payment_failed"}


class PriceNotFound(Exception):
    """No active Stripe price carries the premium lookup key."""


def load_billing_settings() -> StripeSettings:
    """The Stripe settings from the environment or the app secret.

    Raises StripeNotConfigured when the API key is missing or invalid.
    """
    return load_stripe_settings(settings.APP_SECRETS_ARN or None)


class StripeGateway:
    """The handful of Stripe calls billing makes, behind one seam tests can fake."""

    def __init__(self, client: stripe.StripeClient) -> None:
        """Wrap a configured Stripe client."""
        self.client = client

    @classmethod
    def from_settings(cls, stripe_settings: StripeSettings) -> "StripeGateway":
        """Build a gateway from resolved Stripe settings."""
        return cls(stripe_client(stripe_settings))

    def find_price_id(self, lookup_key: str) -> str | None:
        """The id of the active price carrying `lookup_key`, or None."""
        prices = self.client.v1.prices.list(params={"lookup_keys": [lookup_key], "active": True, "limit": 1})
        return prices.data[0].id if prices.data else None

    def create_customer(self, *, email: str, user_id: str) -> str:
        """Create a Stripe customer for a user and return its id."""
        customer = self.client.v1.customers.create(params={"email": email, "metadata": {"user_id": user_id}})
        return customer.id

    def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        user_id: str,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a subscription mode Checkout Session and return its URL."""
        session = self.client.v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "customer": customer_id,
                "client_reference_id": user_id,
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {"user_id": user_id},
                "subscription_data": {"metadata": {"user_id": user_id}},
            }
        )
        if not session.url:
            raise stripe.StripeError("Checkout Session has no URL")
        return session.url

    def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        """Create a Customer Portal session and return its URL."""
        session = self.client.v1.billing_portal.sessions.create(
            params={"customer": customer_id, "return_url": return_url}
        )
        return session.url

    def retrieve_subscription(self, subscription_id: str) -> dict[str, Any]:
        """The subscription with this id, as a plain dict."""
        return self.client.v1.subscriptions.retrieve(subscription_id).to_dict()


GatewayFactory = Callable[[StripeSettings], StripeGateway]


def get_gateway_factory() -> GatewayFactory:
    """The dependency building a Stripe gateway from settings, overridden in tests."""
    return StripeGateway.from_settings


def get_idempotency_store() -> IdempotencyStore:
    """The dependency naming the webhook event claim store."""
    kwargs = resource_kwargs()
    repository = SharedRepository(
        IDEMPOTENCY.suffix,
        region_name=kwargs.get("region_name"),
        endpoint_url=kwargs.get("endpoint_url"),
    )
    repository.table_name = table_name(IDEMPOTENCY)
    return IdempotencyStore(repository)


def user_has_active_premium(user: User) -> bool:
    """True when the user holds a live premium subscription."""
    if user.subscription_tier != "premium" or user.subscription_status != "active":
        return False
    return user.subscription_expires_at is None or user.subscription_expires_at > datetime.now(UTC)


def checkout_return_urls() -> tuple[str, str]:
    """The success and cancel URLs Stripe Checkout returns the browser to."""
    base = settings.frontend_base_url
    return (
        f"{base}/checkout?status=success&session_id={{CHECKOUT_SESSION_ID}}",
        f"{base}/checkout?status=cancelled",
    )


def portal_return_url() -> str:
    """The URL the Customer Portal returns the browser to."""
    return f"{settings.frontend_base_url}/profile"


def ensure_customer(user: User, users: UserRepository, gateway: StripeGateway) -> str:
    """The user's Stripe customer id, creating and persisting one when absent."""
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer_id = gateway.create_customer(email=user.email, user_id=str(user.id))
    users.update_user(user.id, stripe_customer_id=customer_id)
    return customer_id


def start_checkout(user: User, users: UserRepository, gateway: StripeGateway) -> str:
    """Create a premium Checkout Session for the user and return its URL.

    Raises PriceNotFound when no price carries the premium lookup key.
    """
    price_id = gateway.find_price_id(PREMIUM_PRICE_LOOKUP_KEY)
    if price_id is None:
        raise PriceNotFound(PREMIUM_PRICE_LOOKUP_KEY)
    customer_id = ensure_customer(user, users, gateway)
    success_url, cancel_url = checkout_return_urls()
    return gateway.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        user_id=str(user.id),
        success_url=success_url,
        cancel_url=cancel_url,
    )


def subscription_state(subscription: dict[str, Any]) -> dict[str, Any]:
    """The tier, status and expiry a Stripe subscription maps to on the user."""
    stripe_status = subscription.get("status", "")
    if stripe_status in PREMIUM_STRIPE_STATUSES:
        tier, status = "premium", "active"
    elif stripe_status == "canceled":
        tier, status = "free", "cancelled"
    else:
        tier, status = "free", "expired"
    period_ends = [
        item["current_period_end"]
        for item in (subscription.get("items") or {}).get("data", [])
        if item.get("current_period_end")
    ]
    if not period_ends and subscription.get("current_period_end"):
        period_ends = [subscription["current_period_end"]]
    expires_at = datetime.fromtimestamp(max(period_ends), UTC) if period_ends else None
    return {
        "subscription_tier": tier,
        "subscription_status": status,
        "subscription_expires_at": expires_at,
    }


def _object_id(value: Any) -> str | None:
    """The id of a Stripe reference that may be an id string or an expanded object."""
    if isinstance(value, dict):
        return value.get("id")
    return value or None


def _invoice_subscription_id(invoice: dict[str, Any]) -> str | None:
    """The subscription an invoice bills, across old and new API shapes."""
    direct = _object_id(invoice.get("subscription"))
    if direct:
        return direct
    details = ((invoice.get("parent") or {}).get("subscription_details")) or {}
    return _object_id(details.get("subscription"))


def _parse_user_id(value: Any) -> UUID | None:
    """A user id parsed from a reference string, or None when it is not a UUID."""
    if not value:
        return None
    try:
        return UUID(str(value))
    except ValueError:
        return None


def find_user(
    users: UserRepository,
    *,
    customer_id: str | None,
    user_ref: Any = None,
) -> User | None:
    """The user a Stripe object belongs to, by user reference first, then by customer id."""
    user_id = _parse_user_id(user_ref)
    if user_id is not None:
        user = users.get(user_id)
        if user is not None:
            return user
    if customer_id:
        return users.get_by_stripe_customer_id(customer_id)
    return None


def _sync_subscription(
    users: UserRepository,
    gateway: StripeGateway,
    *,
    subscription_id: str,
    customer_id: str | None,
    user_ref: Any = None,
) -> bool:
    """Fetch a subscription and write its state onto the owning user."""
    subscription = gateway.retrieve_subscription(subscription_id)
    customer_id = customer_id or _object_id(subscription.get("customer"))
    user_ref = user_ref or (subscription.get("metadata") or {}).get("user_id")
    user = find_user(users, customer_id=customer_id, user_ref=user_ref)
    if user is None:
        logger.warning("Stripe subscription %s matches no user", subscription_id)
        return False
    changes = subscription_state(subscription)
    if customer_id and user.stripe_customer_id != customer_id:
        changes["stripe_customer_id"] = customer_id
    users.update_user(user.id, **changes)
    logger.info("Synced Stripe subscription %s onto user %s", subscription_id, user.id)
    return True


def apply_event(event_type: str, obj: dict[str, Any], users: UserRepository, gateway: StripeGateway) -> bool:
    """Apply one verified Stripe event, answering whether it changed a user."""
    if event_type == "checkout.session.completed":
        subscription_id = _object_id(obj.get("subscription"))
        if not subscription_id:
            return False
        return _sync_subscription(
            users,
            gateway,
            subscription_id=subscription_id,
            customer_id=_object_id(obj.get("customer")),
            user_ref=obj.get("client_reference_id"),
        )
    if event_type in SUBSCRIPTION_EVENTS:
        return _sync_subscription(
            users,
            gateway,
            subscription_id=obj["id"],
            customer_id=_object_id(obj.get("customer")),
        )
    if event_type == "invoice.payment_failed":
        subscription_id = _invoice_subscription_id(obj)
        if not subscription_id:
            return False
        return _sync_subscription(
            users,
            gateway,
            subscription_id=subscription_id,
            customer_id=_object_id(obj.get("customer")),
        )
    return False


def process_webhook_event(
    event: stripe.Event,
    users: UserRepository,
    gateway: StripeGateway,
    store: IdempotencyStore,
) -> tuple[bool, bool]:
    """Claim and apply a verified event, answering (handled, duplicate).

    A failure while applying releases the claim so Stripe's retry can do the work.
    """
    if event.type not in HANDLED_EVENTS:
        return False, False
    if not claim_webhook_event(event, store):
        return False, True
    try:
        payload = event.to_dict()
        apply_event(event.type, payload["data"]["object"], users, gateway)
    except Exception:
        store.release(event_claim_key(event.id))
        raise
    return True, False


__all__ = [
    "HANDLED_EVENTS",
    "PREMIUM_PRICE_LOOKUP_KEY",
    "GatewayFactory",
    "PriceNotFound",
    "StripeGateway",
    "StripeNotConfigured",
    "apply_event",
    "checkout_return_urls",
    "ensure_customer",
    "find_user",
    "get_gateway_factory",
    "get_idempotency_store",
    "load_billing_settings",
    "portal_return_url",
    "process_webhook_event",
    "start_checkout",
    "subscription_state",
    "user_has_active_premium",
]
