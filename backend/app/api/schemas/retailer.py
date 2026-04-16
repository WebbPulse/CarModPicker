from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetailerBase(BaseModel):
    name: str = Field(..., description="Retailer display name (e.g., A90Shop)")
    domain: Optional[str] = Field(None, description="Domain (e.g., a90shop.com)")
    base_url: Optional[str] = Field(None, description="Base URL (e.g., https://www.a90shop.com)")
    is_active: bool = Field(True, description="Whether the retailer is active")


class RetailerCreate(RetailerBase):
    pass


class RetailerUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Retailer display name")
    domain: Optional[str] = Field(None, description="Domain")
    base_url: Optional[str] = Field(None, description="Base URL")
    is_active: Optional[bool] = Field(None, description="Whether the retailer is active")


class RetailerRead(RetailerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
