from typing import TYPE_CHECKING, Any

import boto3

from app.core.config import settings
from app.db.dynamo.tables import USERS, TableSpec

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

_resource: "DynamoDBServiceResource | None" = None


def _region_name() -> str | None:
    region = settings.AWS_REGION
    if not region or region == "auto":
        return None
    return region


def _resource_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    region = _region_name()
    if region:
        kwargs["region_name"] = region
    if settings.DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.DYNAMODB_ENDPOINT_URL
    return kwargs


def get_resource() -> "DynamoDBServiceResource":
    global _resource
    if _resource is None:
        _resource = boto3.resource("dynamodb", **_resource_kwargs())
    return _resource


def get_client() -> "DynamoDBClient":
    return get_resource().meta.client


def reset_clients() -> None:
    global _resource
    _resource = None


def table_name(spec: TableSpec) -> str:
    return f"{settings.dynamodb_table_prefix}-{spec.suffix}"


def get_table(spec: TableSpec) -> "Table":
    return get_resource().Table(table_name(spec))


def check_db_ready() -> bool:
    """Return True if DynamoDB is reachable (for /ready)."""
    try:
        get_client().describe_table(TableName=table_name(USERS))
        return True
    except Exception:
        return False
