from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from uuid6 import uuid7


def new_id() -> str:
    return str(uuid7())


def utc_now() -> datetime:
    return datetime.now(UTC)


class DynamoModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: str = Field(default_factory=new_id)


class TimestampedDynamoModel(DynamoModel):
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def touch(self) -> None:
        self.updated_at = utc_now()
