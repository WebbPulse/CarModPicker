"""The DynamoDB layer's public surface: models, repositories and table specs."""

from webbpulse.dynamodb import ConditionFailed, DynamoError, ItemNotFound, TransactionCanceled

from app.common.db.dynamo.models import DynamoModel, TimestampedDynamoModel, utc_now
from app.common.db.dynamo.repository import DynamoRepository, Page, RangeCondition
from app.common.db.dynamo.tables import TABLES, IndexSpec, TableSpec, table_by_suffix

__all__ = [
    "TABLES",
    "ConditionFailed",
    "DynamoError",
    "DynamoModel",
    "DynamoRepository",
    "IndexSpec",
    "ItemNotFound",
    "Page",
    "RangeCondition",
    "TableSpec",
    "TimestampedDynamoModel",
    "TransactionCanceled",
    "table_by_suffix",
    "utc_now",
]
