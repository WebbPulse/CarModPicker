import base64
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Generic, Iterable, TypeVar, cast

from boto3.dynamodb.conditions import Attr, ConditionBase, Key
from botocore.exceptions import ClientError

from app.db.dynamo.client import get_client, get_table, table_name
from app.db.dynamo.errors import ConditionFailed, ItemNotFound, TransactionCanceled
from app.db.dynamo.models import DynamoModel, utc_now
from app.db.dynamo.serialization import (
    UNIQUE_KEY_PREFIX,
    from_item,
    to_dynamo_value,
    to_item,
    unique_lookup_key,
)
from app.db.dynamo.tables import IndexSpec, TableSpec

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

TModel = TypeVar("TModel", bound=DynamoModel)

BATCH_WRITE_LIMIT = 25
BATCH_GET_LIMIT = 100
TRANSACT_WRITE_LIMIT = 100
UNPROCESSED_RETRY_ATTEMPTS = 5
UNPROCESSED_RETRY_BASE_DELAY_SEC = 0.05

CONDITIONAL_CHECK_FAILED = "ConditionalCheckFailedException"
TRANSACTION_CANCELED = "TransactionCanceledException"


@dataclass(frozen=True)
class Page(Generic[TModel]):
    items: list[TModel]
    next_cursor: str | None


@dataclass(frozen=True)
class RangeCondition:
    operator: str
    value: Any
    upper: Any = None

    @classmethod
    def eq(cls, value: Any) -> "RangeCondition":
        return cls("eq", value)

    @classmethod
    def lt(cls, value: Any) -> "RangeCondition":
        return cls("lt", value)

    @classmethod
    def lte(cls, value: Any) -> "RangeCondition":
        return cls("lte", value)

    @classmethod
    def gt(cls, value: Any) -> "RangeCondition":
        return cls("gt", value)

    @classmethod
    def gte(cls, value: Any) -> "RangeCondition":
        return cls("gte", value)

    @classmethod
    def begins_with(cls, value: Any) -> "RangeCondition":
        return cls("begins_with", value)

    @classmethod
    def between(cls, low: Any, high: Any) -> "RangeCondition":
        return cls("between", low, high)

    def to_key_condition(self, attribute: str) -> ConditionBase:
        key = Key(attribute)
        if self.operator == "between":
            return key.between(to_dynamo_value(self.value), to_dynamo_value(self.upper))
        method = getattr(key, self.operator)
        return method(to_dynamo_value(self.value))


def encode_cursor(last_evaluated_key: dict[str, Any] | None) -> str | None:
    if not last_evaluated_key:
        return None
    payload = json.dumps(last_evaluated_key, default=_json_default, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        payload = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        decoded = json.loads(payload, parse_float=Decimal)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid pagination cursor") from exc
    if not isinstance(decoded, dict):
        raise ValueError("invalid pagination cursor")
    return cast(dict[str, Any], decoded)


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"cannot encode {type(value).__name__} in cursor")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _chunks(values: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


class DynamoRepository(Generic[TModel]):
    def __init__(self, model_cls: type[TModel], spec: TableSpec) -> None:
        self.model_cls = model_cls
        self.spec = spec

    @property
    def table_name(self) -> str:
        return table_name(self.spec)

    @property
    def table(self) -> "Table":
        return get_table(self.spec)

    def key(self, partition_value: Any, sort_value: Any = None) -> dict[str, Any]:
        key = {self.spec.partition_key.name: to_dynamo_value(partition_value)}
        if self.spec.sort_key is not None:
            if sort_value is None:
                raise ValueError(f"{self.spec.suffix} requires a sort key value")
            key[self.spec.sort_key.name] = to_dynamo_value(sort_value)
        return key

    def key_of(self, model: TModel) -> dict[str, Any]:
        item = to_item(model, self.spec)
        return {name: item[name] for name in self.spec.key_attribute_names}

    def to_item(self, model: TModel) -> dict[str, Any]:
        return to_item(model, self.spec)

    def from_item(self, item: dict[str, Any]) -> TModel:
        return from_item(item, self.model_cls)

    def get(self, partition_value: Any, sort_value: Any = None, *, consistent: bool = False) -> TModel | None:
        response = self.table.get_item(Key=self.key(partition_value, sort_value), ConsistentRead=consistent)
        item = response.get("Item")
        if item is None:
            return None
        return self.from_item(dict(item))

    def get_or_raise(self, partition_value: Any, sort_value: Any = None, *, consistent: bool = False) -> TModel:
        model = self.get(partition_value, sort_value, consistent=consistent)
        if model is None:
            raise ItemNotFound(self.table_name, self.key(partition_value, sort_value))
        return model

    def put(self, model: TModel, *, condition: ConditionBase | None = None) -> TModel:
        item = self.to_item(model)
        kwargs: dict[str, Any] = {"Item": item}
        if condition is not None:
            kwargs["ConditionExpression"] = condition
        try:
            self.table.put_item(**kwargs)
        except ClientError as exc:
            if _error_code(exc) == CONDITIONAL_CHECK_FAILED:
                raise ConditionFailed(self.table_name, "put condition", self.key_of(model)) from exc
            raise
        return model

    def create(self, model: TModel) -> TModel:
        try:
            return self.put(model, condition=Attr(self.spec.partition_key.name).not_exists())
        except ConditionFailed as exc:
            raise ConditionFailed(self.table_name, "attribute_not_exists(id)", exc.key) from exc

    def update(self, partition_value: Any, sort_value: Any = None, /, **changes: Any) -> TModel:
        if not changes:
            return self.get_or_raise(partition_value, sort_value)
        if "updated_at" in self.model_cls.model_fields and "updated_at" not in changes:
            changes["updated_at"] = utc_now()
        for key_name in self.spec.key_attribute_names:
            if key_name in changes:
                raise ValueError(f"cannot update key attribute {key_name!r}")
        expression, names, values = self._build_update_expression(changes)
        names["#pk"] = self.spec.partition_key.name
        kwargs: dict[str, Any] = {
            "Key": self.key(partition_value, sort_value),
            "UpdateExpression": expression,
            "ExpressionAttributeNames": names,
            "ConditionExpression": "attribute_exists(#pk)",
            "ReturnValues": "ALL_NEW",
        }
        if values:
            kwargs["ExpressionAttributeValues"] = values
        try:
            response = self.table.update_item(**kwargs)
        except ClientError as exc:
            if _error_code(exc) == CONDITIONAL_CHECK_FAILED:
                raise ItemNotFound(self.table_name, self.key(partition_value, sort_value)) from exc
            raise
        return self.from_item(dict(response["Attributes"]))

    def _build_update_expression(self, changes: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, Any]]:
        names: dict[str, str] = {}
        values: dict[str, Any] = {}
        sets: list[str] = []
        removes: list[str] = []
        derived = self._derived_changes(changes)
        for index, (attribute, value) in enumerate({**changes, **derived}.items()):
            name_placeholder = f"#u{index}"
            names[name_placeholder] = attribute
            if value is None:
                removes.append(name_placeholder)
                continue
            value_placeholder = f":u{index}"
            values[value_placeholder] = to_dynamo_value(value)
            sets.append(f"{name_placeholder} = {value_placeholder}")
        clauses: list[str] = []
        if sets:
            clauses.append("SET " + ", ".join(sets))
        if removes:
            clauses.append("REMOVE " + ", ".join(removes))
        return " ".join(clauses), names, values

    def _derived_changes(self, changes: dict[str, Any]) -> dict[str, Any]:
        derived: dict[str, Any] = {}
        for source, target in self.spec.lowercase_mirrors:
            if source in changes:
                value = changes[source]
                derived[target] = value.lower() if isinstance(value, str) else None
        for target, sources in self.spec.composite_keys:
            if any(source in changes for source in sources):
                raise ValueError(f"updating {sources} requires a full put because {target!r} is derived from them")
        for target, sources in self.spec.coalesced_keys:
            if any(source in changes for source in sources):
                raise ValueError(f"updating {sources} requires a full put because {target!r} is derived from them")
        return derived

    def delete(self, partition_value: Any, sort_value: Any = None, *, must_exist: bool = False) -> None:
        kwargs: dict[str, Any] = {"Key": self.key(partition_value, sort_value)}
        if must_exist:
            kwargs["ConditionExpression"] = Attr(self.spec.partition_key.name).exists()
        try:
            self.table.delete_item(**kwargs)
        except ClientError as exc:
            if _error_code(exc) == CONDITIONAL_CHECK_FAILED:
                raise ItemNotFound(self.table_name, self.key(partition_value, sort_value)) from exc
            raise

    def query(
        self,
        index: str | None,
        key_value: Any,
        *,
        range_condition: RangeCondition | None = None,
        limit: int | None = None,
        cursor: str | None = None,
        scan_forward: bool = True,
        filter_expression: ConditionBase | None = None,
    ) -> Page[TModel]:
        hash_name, range_name = self._query_key_names(index)
        condition: ConditionBase = Key(hash_name).eq(to_dynamo_value(key_value))
        if range_condition is not None:
            if range_name is None:
                raise ValueError(f"{self.spec.suffix} index {index!r} has no range key")
            condition = condition & range_condition.to_key_condition(range_name)
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": condition,
            "ScanIndexForward": scan_forward,
        }
        if index is not None:
            kwargs["IndexName"] = index
        if limit is not None:
            kwargs["Limit"] = limit
        if filter_expression is not None:
            kwargs["FilterExpression"] = filter_expression
        start_key = decode_cursor(cursor)
        if start_key is not None:
            kwargs["ExclusiveStartKey"] = start_key
        response = self.table.query(**kwargs)
        items = [self.from_item(dict(item)) for item in response.get("Items", [])]
        return Page(items=items, next_cursor=encode_cursor(response.get("LastEvaluatedKey")))

    def query_all(
        self,
        index: str | None,
        key_value: Any,
        *,
        range_condition: RangeCondition | None = None,
        scan_forward: bool = True,
        filter_expression: ConditionBase | None = None,
        page_size: int | None = None,
    ) -> list[TModel]:
        items: list[TModel] = []
        cursor: str | None = None
        while True:
            page = self.query(
                index,
                key_value,
                range_condition=range_condition,
                limit=page_size,
                cursor=cursor,
                scan_forward=scan_forward,
                filter_expression=filter_expression,
            )
            items.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                return items

    def _query_key_names(self, index: str | None) -> tuple[str, str | None]:
        if index is None:
            return self.spec.partition_key.name, self.spec.sort_key.name if self.spec.sort_key else None
        index_spec: IndexSpec = self.spec.index(index)
        return index_spec.hash_key.name, index_spec.range_key.name if index_spec.range_key else None

    def scan(
        self,
        *,
        filter_expression: ConditionBase | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Page[TModel]:
        exclude_lookups: ConditionBase = ~Attr(self.spec.partition_key.name).begins_with(UNIQUE_KEY_PREFIX)
        combined = exclude_lookups if filter_expression is None else exclude_lookups & filter_expression
        kwargs: dict[str, Any] = {"FilterExpression": combined}
        if limit is not None:
            kwargs["Limit"] = limit
        start_key = decode_cursor(cursor)
        if start_key is not None:
            kwargs["ExclusiveStartKey"] = start_key
        response = self.table.scan(**kwargs)
        items = [self.from_item(dict(item)) for item in response.get("Items", [])]
        return Page(items=items, next_cursor=encode_cursor(response.get("LastEvaluatedKey")))

    def scan_all(self, *, filter_expression: ConditionBase | None = None, page_size: int | None = None) -> list[TModel]:
        items: list[TModel] = []
        cursor: str | None = None
        while True:
            page = self.scan(filter_expression=filter_expression, limit=page_size, cursor=cursor)
            items.extend(page.items)
            cursor = page.next_cursor
            if cursor is None:
                return items

    def batch_get(self, keys: list[Any], *, consistent: bool = False) -> list[TModel]:
        found: list[TModel] = []
        key_dicts = [self._coerce_key(key) for key in keys]
        for chunk in _chunks(key_dicts, BATCH_GET_LIMIT):
            request: dict[str, Any] = {self.table_name: {"Keys": chunk, "ConsistentRead": consistent}}
            for attempt in range(UNPROCESSED_RETRY_ATTEMPTS + 1):
                response = get_client().batch_get_item(RequestItems=cast(Any, request))
                found.extend(
                    self.from_item(dict(item)) for item in response.get("Responses", {}).get(self.table_name, [])
                )
                unprocessed = response.get("UnprocessedKeys", {})
                if not unprocessed.get(self.table_name, {}).get("Keys"):
                    break
                if attempt == UNPROCESSED_RETRY_ATTEMPTS:
                    raise RuntimeError(f"{self.table_name}: batch_get left keys unprocessed after retries")
                time.sleep(UNPROCESSED_RETRY_BASE_DELAY_SEC * (2**attempt))
                request = dict(unprocessed)
        return found

    def _coerce_key(self, key: Any) -> dict[str, Any]:
        if isinstance(key, dict):
            return {name: to_dynamo_value(value) for name, value in cast(dict[str, Any], key).items()}
        if isinstance(key, tuple):
            partition_value, sort_value = cast(tuple[Any, Any], key)
            return self.key(partition_value, sort_value)
        return self.key(key)

    def batch_put(self, models: list[TModel]) -> None:
        self._batch_write([{"PutRequest": {"Item": self.to_item(model)}} for model in models])

    def batch_delete(self, keys: list[Any]) -> None:
        self._batch_write([{"DeleteRequest": {"Key": self._coerce_key(key)}} for key in keys])

    def _batch_write(self, requests: list[dict[str, Any]]) -> None:
        for chunk in _chunks(requests, BATCH_WRITE_LIMIT):
            pending: dict[str, Any] = {self.table_name: chunk}
            for attempt in range(UNPROCESSED_RETRY_ATTEMPTS + 1):
                response = get_client().batch_write_item(RequestItems=cast(Any, pending))
                unprocessed = response.get("UnprocessedItems", {})
                if not unprocessed.get(self.table_name):
                    break
                if attempt == UNPROCESSED_RETRY_ATTEMPTS:
                    raise RuntimeError(f"{self.table_name}: batch_write left items unprocessed after retries")
                time.sleep(UNPROCESSED_RETRY_BASE_DELAY_SEC * (2**attempt))
                pending = dict(unprocessed)

    def put_action(self, model: TModel, *, condition: str | None = None) -> dict[str, Any]:
        action: dict[str, Any] = {"TableName": self.table_name, "Item": self.to_item(model)}
        if condition is not None:
            action["ConditionExpression"] = condition
        return {"Put": action}

    def create_action(self, model: TModel) -> dict[str, Any]:
        return {
            "Put": {
                "TableName": self.table_name,
                "Item": self.to_item(model),
                "ConditionExpression": "attribute_not_exists(#pk)",
                "ExpressionAttributeNames": {"#pk": self.spec.partition_key.name},
            }
        }

    def delete_action(
        self, partition_value: Any, sort_value: Any = None, *, must_exist: bool = False
    ) -> dict[str, Any]:
        action: dict[str, Any] = {"TableName": self.table_name, "Key": self.key(partition_value, sort_value)}
        if must_exist:
            action["ConditionExpression"] = "attribute_exists(#pk)"
            action["ExpressionAttributeNames"] = {"#pk": self.spec.partition_key.name}
        return {"Delete": action}

    def condition_check_action(
        self, partition_value: Any, sort_value: Any = None, *, exists: bool = True
    ) -> dict[str, Any]:
        return {
            "ConditionCheck": {
                "TableName": self.table_name,
                "Key": self.key(partition_value, sort_value),
                "ConditionExpression": "attribute_exists(#pk)" if exists else "attribute_not_exists(#pk)",
                "ExpressionAttributeNames": {"#pk": self.spec.partition_key.name},
            }
        }

    def update_action(self, partition_value: Any, sort_value: Any = None, /, **changes: Any) -> dict[str, Any]:
        if "updated_at" in self.model_cls.model_fields and "updated_at" not in changes:
            changes["updated_at"] = utc_now()
        expression, names, values = self._build_update_expression(changes)
        names["#pk"] = self.spec.partition_key.name
        action: dict[str, Any] = {
            "TableName": self.table_name,
            "Key": self.key(partition_value, sort_value),
            "UpdateExpression": expression,
            "ConditionExpression": "attribute_exists(#pk)",
            "ExpressionAttributeNames": names,
        }
        if values:
            action["ExpressionAttributeValues"] = values
        return {"Update": action}

    def unique_lookup_item(self, attribute: str, value: str, owner_id: str | None = None) -> dict[str, Any]:
        if self.spec.is_composite:
            raise ValueError(f"{self.spec.suffix} has a composite key; unique lookups need a single-attribute key")
        item: dict[str, Any] = {self.spec.partition_key.name: unique_lookup_key(attribute, value)}
        if owner_id is not None:
            item["owner_id"] = owner_id
        return item

    def ensure_unique_action(self, attribute: str, value: str, owner_id: str | None = None) -> dict[str, Any]:
        return {
            "Put": {
                "TableName": self.table_name,
                "Item": self.unique_lookup_item(attribute, value, owner_id),
                "ConditionExpression": "attribute_not_exists(#pk)",
                "ExpressionAttributeNames": {"#pk": self.spec.partition_key.name},
            }
        }

    def release_unique_action(self, attribute: str, value: str) -> dict[str, Any]:
        return {
            "Delete": {
                "TableName": self.table_name,
                "Key": {self.spec.partition_key.name: unique_lookup_key(attribute, value)},
            }
        }

    def ensure_unique(self, attribute: str, value: str, owner_id: str | None = None) -> None:
        item = self.unique_lookup_item(attribute, value, owner_id)
        try:
            self.table.put_item(Item=item, ConditionExpression=Attr(self.spec.partition_key.name).not_exists())
        except ClientError as exc:
            if _error_code(exc) == CONDITIONAL_CHECK_FAILED:
                raise ConditionFailed(self.table_name, f"unique {attribute}", item) from exc
            raise

    def release_unique(self, attribute: str, value: str) -> None:
        self.table.delete_item(Key={self.spec.partition_key.name: unique_lookup_key(attribute, value)})

    def is_unique_taken(self, attribute: str, value: str) -> bool:
        response = self.table.get_item(Key={self.spec.partition_key.name: unique_lookup_key(attribute, value)})
        return response.get("Item") is not None


def transact_write(actions: list[dict[str, Any]]) -> None:
    if not actions:
        return
    if len(actions) > TRANSACT_WRITE_LIMIT:
        raise ValueError(f"transact_write accepts at most {TRANSACT_WRITE_LIMIT} actions, got {len(actions)}")
    try:
        get_client().transact_write_items(TransactItems=cast(Any, actions))
    except ClientError as exc:
        if _error_code(exc) == TRANSACTION_CANCELED:
            reasons = cast(list[dict[str, Any]], exc.response.get("CancellationReasons", []))
            raise TransactionCanceled(reasons) from exc
        raise
