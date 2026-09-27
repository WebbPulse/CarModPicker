"""Schemas for Stripe billing sessions and webhook acknowledgements."""

from pydantic import BaseModel


class BillingSessionRead(BaseModel):
    """A hosted Stripe page the browser is redirected to."""

    url: str


class StripeWebhookAck(BaseModel):
    """The acknowledgement returned to Stripe for a webhook delivery."""

    received: bool = True
    handled: bool
    duplicate: bool = False
