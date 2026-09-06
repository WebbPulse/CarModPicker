from typing import Any


class DynamoError(Exception):
    pass


class ItemNotFound(DynamoError):
    def __init__(self, table: str, key: dict[str, Any]) -> None:
        self.table = table
        self.key = key
        super().__init__(f"{table}: no item with key {key}")


class ConditionFailed(DynamoError):
    def __init__(self, table: str, condition: str, key: dict[str, Any] | None = None) -> None:
        self.table = table
        self.condition = condition
        self.key = key
        super().__init__(f"{table}: condition failed ({condition}) for key {key}")


class TransactionCanceled(DynamoError):
    def __init__(self, reasons: list[dict[str, Any]]) -> None:
        self.reasons = reasons
        super().__init__(f"transaction canceled: {reasons}")

    @property
    def conditional_check_failed(self) -> bool:
        return any(reason.get("Code") == "ConditionalCheckFailed" for reason in self.reasons)
