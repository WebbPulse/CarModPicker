from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SubscriptionBase(BaseModel):
    tier: str = Field(..., description="Subscription tier: 'free' or 'premium'")
    status: str = Field(..., description="Subscription status: 'active', 'cancelled', or 'expired'")
    expires_at: Optional[datetime] = Field(None, description="When the subscription expires")


class SubscriptionCreate(SubscriptionBase):
    pass


class SubscriptionUpdate(BaseModel):
    tier: Optional[str] = Field(None, description="Subscription tier: 'free' or 'premium'")
    status: Optional[str] = Field(None, description="Subscription status: 'active', 'cancelled', or 'expired'")
    expires_at: Optional[datetime] = Field(None, description="When the subscription expires")


class SubscriptionInDB(SubscriptionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(SubscriptionInDB):
    pass


class SubscriptionStatus(BaseModel):
    tier: str = Field(..., description="Current subscription tier")
    status: str = Field(..., description="Current subscription status")
    expires_at: Optional[datetime] = Field(None, description="When the subscription expires")
    limits: dict[str, Any] = Field(..., description="Current usage limits")
    usage: dict[str, Any] = Field(..., description="Current usage statistics")

    model_config = ConfigDict(from_attributes=True)


class UpgradeRequest(BaseModel):
    tier: str = Field(..., description="Tier to upgrade to: 'premium'")
    payment_method: Optional[str] = Field(None, description="Payment method identifier")
